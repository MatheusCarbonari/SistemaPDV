from database.conexao import CAMINHO_BANCO, conectar
from models.produto import Produto
from datetime import datetime

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

def salvar_produto(produto:Produto, caminho_banco=CAMINHO_BANCO) -> Produto:
    conexao = conectar(caminho_banco)

    try:
        cursor = conexao.execute(
            """
            INSERT INTO produtos(
                codigo,
                nome,
                categoria,
                forma_venda,
                preco_venda_centavos,
                origem
            )
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                produto.codigo,
                produto.nome,
                produto.categoria,
                produto.forma_venda,
                produto.preco_venda_centavos,
                produto.origem
            )
        )
        conexao.commit()

        produto_id = cursor.lastrowid

        produto_buscado = conexao.execute(
            """
            SELECT
                id,
                codigo,
                nome,
                categoria, 
                forma_venda,
                preco_venda_centavos,
                origem,
                ativo,
                criado_em,
                atualizado_em
            FROM produtos
            WHERE id = ?
            """,
            (produto_id,),
        ).fetchone()

        criado_em = datetime.strptime(
            produto_buscado["criado_em"],
            "%Y-%m-%d %H:%M:%S"
        )

        atualizado_em = datetime.strptime(
            produto_buscado["atualizado_em"],
            "%Y-%m-%d %H:%M:%S"
        )

        novo_produto = Produto(
            codigo=produto_buscado["codigo"],
            nome=produto_buscado["nome"],
            categoria=produto_buscado["categoria"],
            forma_venda=produto_buscado["forma_venda"],
            preco_venda_centavos=produto_buscado["preco_venda_centavos"],
            origem=produto_buscado["origem"],
            ativo=bool(produto_buscado["ativo"]),
            id=produto_buscado["id"],
            criado_em=criado_em,
            atualizado_em=atualizado_em,
        )

    finally:
        conexao.close()

    return novo_produto
