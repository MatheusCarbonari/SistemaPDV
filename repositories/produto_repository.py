from database.conexao import CAMINHO_BANCO, conectar


# Verifica se o código já pertence a algum produto cadastrado.
def codigo_existe(codigo: str, caminho_banco=CAMINHO_BANCO) -> bool:

    conexao = conectar(caminho_banco)

    try:
        # Consulta somente a existência, sem carregar o produto completo.
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
