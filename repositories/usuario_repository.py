from datetime import datetime
import sqlite3

from database.conexao import CAMINHO_BANCO, conectar
from models.usuario import Usuario


class AdministradorJaConfiguradoError(RuntimeError):
    pass


class EstadoIdentidadeInconsistenteError(RuntimeError):
    pass


class IdentificacaoUsuarioEmUsoError(RuntimeError):
    pass


def consultar_estado_identidade(caminho_banco=CAMINHO_BANCO) -> str:
    conexao = conectar(caminho_banco)
    try:
        return _consultar_estado_identidade_conexao(conexao)
    finally:
        conexao.close()


def validar_estado_identidade_conexao(conexao) -> str:
    """Valida o singleton de identidade dentro de uma transação existente."""
    return _consultar_estado_identidade_conexao(conexao)


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


def buscar_usuario_para_autenticacao(
    identificacao_acesso: str,
    caminho_banco=CAMINHO_BANCO,
):
    conexao = conectar(caminho_banco)
    try:
        _consultar_estado_identidade_conexao(conexao)
        return conexao.execute(
            """
            SELECT
                id,
                identificacao_acesso,
                perfil,
                senha_hash,
                ativo,
                criado_em
            FROM usuarios
            WHERE identificacao_acesso = ? COLLATE NOCASE
            """,
            (identificacao_acesso,),
        ).fetchone()
    finally:
        conexao.close()


def buscar_usuario_por_id(usuario_id: int, caminho_banco=CAMINHO_BANCO):
    conexao = conectar(caminho_banco)
    try:
        _consultar_estado_identidade_conexao(conexao)
        linha = conexao.execute(
            """
            SELECT id, identificacao_acesso, perfil, ativo, criado_em
            FROM usuarios
            WHERE id = ?
            """,
            (usuario_id,),
        ).fetchone()
        return _montar_usuario(linha) if linha is not None else None
    finally:
        conexao.close()


def criar_usuario_caixa_repository(
    identificacao_acesso: str,
    senha_hash: str,
    caminho_banco=CAMINHO_BANCO,
) -> Usuario:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        _consultar_estado_identidade_conexao(conexao)
        try:
            cursor = conexao.execute(
                """
                INSERT INTO usuarios (
                    identificacao_acesso,
                    perfil,
                    senha_hash
                )
                VALUES (?, 'CAIXA', ?)
                """,
                (identificacao_acesso, senha_hash),
            )
        except sqlite3.IntegrityError as erro:
            if "usuarios.identificacao_acesso" in str(erro):
                raise IdentificacaoUsuarioEmUsoError(
                    "A identificação de acesso já está em uso."
                ) from erro
            raise
        linha = conexao.execute(
            """
            SELECT id, identificacao_acesso, perfil, ativo, criado_em
            FROM usuarios
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        conexao.commit()
        return _montar_usuario(linha)
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def listar_usuarios_caixa_repository(
    caminho_banco=CAMINHO_BANCO,
) -> tuple[Usuario, ...]:
    conexao = conectar(caminho_banco)
    try:
        _consultar_estado_identidade_conexao(conexao)
        linhas = conexao.execute(
            """
            SELECT id, identificacao_acesso, perfil, ativo, criado_em
            FROM usuarios
            WHERE perfil = 'CAIXA'
            ORDER BY identificacao_acesso COLLATE NOCASE, id
            """
        ).fetchall()
        return tuple(_montar_usuario(linha) for linha in linhas)
    finally:
        conexao.close()


def alterar_situacao_usuario_caixa_repository(
    usuario_id: int,
    ativo: bool,
    caminho_banco=CAMINHO_BANCO,
) -> Usuario | None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        _consultar_estado_identidade_conexao(conexao)
        atualizado = conexao.execute(
            """
            UPDATE usuarios
            SET ativo = ?
            WHERE id = ? AND perfil = 'CAIXA'
            """,
            (int(ativo), usuario_id),
        )
        if atualizado.rowcount != 1:
            conexao.rollback()
            return None
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


def redefinir_senha_usuario_caixa_repository(
    usuario_id: int,
    nova_senha_hash: str,
    caminho_banco=CAMINHO_BANCO,
) -> Usuario | None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        _consultar_estado_identidade_conexao(conexao)
        atualizado = conexao.execute(
            """
            UPDATE usuarios
            SET senha_hash = ?
            WHERE id = ? AND perfil = 'CAIXA'
            """,
            (nova_senha_hash, usuario_id),
        )
        if atualizado.rowcount != 1:
            conexao.rollback()
            return None
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
