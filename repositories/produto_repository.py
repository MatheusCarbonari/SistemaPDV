from database.conexao import CAMINHO_BANCO, conectar


def codigo_existe(codigo: str, caminho_banco=CAMINHO_BANCO) -> bool:

    conexao = conectar(caminho_banco)

    try:
        resposta = conexao.execute(
            """
            SELECT 1
            FROM produtos
            WHERE codigo = ?
            LIMIT 1
            """,
            (codigo,)
        ).fetchone()
    finally:
        conexao.close()

    return resposta is not None