from datetime import datetime

from database.conexao import CAMINHO_BANCO, conectar
from models.usuario import Usuario


class AdministradorJaConfiguradoError(RuntimeError):
    pass


class EstadoIdentidadeInconsistenteError(RuntimeError):
    pass


def consultar_estado_identidade(caminho_banco=CAMINHO_BANCO) -> str:
    conexao = conectar(caminho_banco)
    try:
        return _consultar_estado_identidade_conexao(conexao)
    finally:
        conexao.close()


def criar_administrador_inicial_repository(
    identificacao_acesso: str,
    senha_hash: str,
    caminho_banco=CAMINHO_BANCO,
) -> Usuario:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        estado = _consultar_estado_identidade_conexao(conexao)
        if estado == "CONFIGURADO":
            raise AdministradorJaConfiguradoError(
                "O administrador inicial já foi configurado."
            )
        cursor = conexao.execute(
            """
            INSERT INTO usuarios (
                identificacao_acesso,
                perfil,
                senha_hash
            )
            VALUES (?, 'ADMINISTRADOR', ?)
            """,
            (identificacao_acesso, senha_hash),
        )
        usuario_id = cursor.lastrowid
        atualizado = conexao.execute(
            """
            UPDATE estado_identidade
            SET
                administrador_inicial_id = ?,
                configurado_em = CURRENT_TIMESTAMP
            WHERE id = 1 AND administrador_inicial_id IS NULL
            """,
            (usuario_id,),
        )
        if atualizado.rowcount != 1:
            raise EstadoIdentidadeInconsistenteError(
                "O estado da configuração inicial é inconsistente."
            )
        linha = conexao.execute(
            """
            SELECT id, identificacao_acesso, perfil, ativo, criado_em
            FROM usuarios
            WHERE id = ?
            """,
            (usuario_id,),
        ).fetchone()
        conexao.commit()
        return _montar_usuario(linha)
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def buscar_hash_administrador_inicial(caminho_banco=CAMINHO_BANCO) -> str:
    conexao = conectar(caminho_banco)
    try:
        estado = _consultar_estado_identidade_conexao(conexao)
        if estado != "CONFIGURADO":
            raise EstadoIdentidadeInconsistenteError(
                "O administrador inicial não está configurado."
            )
        linha = conexao.execute(
            """
            SELECT u.senha_hash
            FROM estado_identidade AS e
            JOIN usuarios AS u ON u.id = e.administrador_inicial_id
            WHERE e.id = 1
            """
        ).fetchone()
        return linha["senha_hash"]
    finally:
        conexao.close()


def _consultar_estado_identidade_conexao(conexao) -> str:
    estado = conexao.execute(
        """
        SELECT administrador_inicial_id, configurado_em
        FROM estado_identidade
        WHERE id = 1
        """
    ).fetchone()
    quantidade_estado = conexao.execute(
        "SELECT COUNT(*) FROM estado_identidade"
    ).fetchone()[0]
    quantidade_usuarios = conexao.execute(
        "SELECT COUNT(*) FROM usuarios"
    ).fetchone()[0]

    if estado is None or quantidade_estado != 1:
        raise EstadoIdentidadeInconsistenteError(
            "O estado da configuração inicial é inconsistente."
        )

    administrador_id = estado["administrador_inicial_id"]
    configurado_em = estado["configurado_em"]
    if administrador_id is None and configurado_em is None:
        if quantidade_usuarios == 0:
            return "NAO_CONFIGURADO"
        raise EstadoIdentidadeInconsistenteError(
            "Há usuários sem configuração inicial concluída."
        )

    administrador = conexao.execute(
        """
        SELECT id, perfil, ativo
        FROM usuarios
        WHERE id = ?
        """,
        (administrador_id,),
    ).fetchone()
    if (
        configurado_em is None
        or administrador is None
        or administrador["perfil"] != "ADMINISTRADOR"
        or administrador["ativo"] != 1
    ):
        raise EstadoIdentidadeInconsistenteError(
            "O administrador inicial configurado é inválido."
        )
    return "CONFIGURADO"


def _montar_usuario(linha) -> Usuario:
    return Usuario(
        id=linha["id"],
        identificacao_acesso=linha["identificacao_acesso"],
        perfil=linha["perfil"],
        ativo=bool(linha["ativo"]),
        criado_em=datetime.strptime(linha["criado_em"], "%Y-%m-%d %H:%M:%S"),
    )
