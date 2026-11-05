from collections.abc import Sequence

from database.conexao import CAMINHO_BANCO, conectar
from repositories.usuario_repository import validar_estado_identidade_conexao


def rotacionar_codigos_recuperacao(
    usuario_id: int,
    conjunto_id: str,
    verificadores: Sequence[str],
    caminho_banco=CAMINHO_BANCO,
) -> None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        validar_estado_identidade_conexao(conexao)
        administrador = conexao.execute(
            """
            SELECT id
            FROM usuarios
            WHERE id = ? AND perfil = 'ADMINISTRADOR' AND ativo = 1
            """,
            (usuario_id,),
        ).fetchone()
        if administrador is None:
            raise PermissionError(
                "A emissão exige uma conta administrativa ativa."
            )

        conexao.execute(
            """
            UPDATE codigos_recuperacao
            SET revogado_em = CURRENT_TIMESTAMP
            WHERE usuario_id = ?
              AND consumido_em IS NULL
              AND revogado_em IS NULL
            """,
            (usuario_id,),
        )
        conexao.executemany(
            """
            INSERT INTO codigos_recuperacao (
                usuario_id,
                conjunto_id,
                verificador
            )
            VALUES (?, ?, ?)
            """,
            (
                (usuario_id, conjunto_id, verificador)
                for verificador in verificadores
            ),
        )
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def consumir_codigo_e_atualizar_senha(
    identificacao_acesso: str,
    verificador: str,
    nova_senha_hash: str,
    caminho_banco=CAMINHO_BANCO,
) -> int | None:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        validar_estado_identidade_conexao(conexao)
        registro = conexao.execute(
            """
            SELECT c.id AS codigo_id, u.id AS usuario_id
            FROM usuarios AS u
            JOIN codigos_recuperacao AS c ON c.usuario_id = u.id
            WHERE u.identificacao_acesso = ? COLLATE NOCASE
              AND u.perfil = 'ADMINISTRADOR'
              AND u.ativo = 1
              AND c.verificador = ?
              AND c.consumido_em IS NULL
              AND c.revogado_em IS NULL
            """,
            (identificacao_acesso, verificador),
        ).fetchone()
        if registro is None:
            conexao.rollback()
            return None

        consumido = conexao.execute(
            """
            UPDATE codigos_recuperacao
            SET consumido_em = CURRENT_TIMESTAMP
            WHERE id = ?
              AND consumido_em IS NULL
              AND revogado_em IS NULL
            """,
            (registro["codigo_id"],),
        )
        if consumido.rowcount != 1:
            conexao.rollback()
            return None

        atualizado = conexao.execute(
            """
            UPDATE usuarios
            SET senha_hash = ?
            WHERE id = ? AND perfil = 'ADMINISTRADOR' AND ativo = 1
            """,
            (nova_senha_hash, registro["usuario_id"]),
        )
        if atualizado.rowcount != 1:
            raise RuntimeError("A conta administrativa deixou de estar ativa.")

        conexao.commit()
        return registro["usuario_id"]
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()
