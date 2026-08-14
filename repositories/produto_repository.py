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

# Persiste o produto e devolve seus dados completos após o cadastro.
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
        produto.id = produto_id

        produto_buscado = buscar_produto_banco_pelo_id(produto_id, caminho_banco)

        # Mantém o cadastro disponível mesmo se a releitura não encontrar a linha.
        if produto_buscado is None:
            return produto

        novo_produto = montar_produto(produto_buscado)

    finally:
        conexao.close()

    return novo_produto

# Busca no banco a linha correspondente ao ID informado.
def buscar_produto_banco_pelo_id(produto_id:int, caminho_banco=CAMINHO_BANCO):
    conexao = conectar(caminho_banco)

    try:
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

    finally:
        conexao.close()

    return produto_buscado

# Busca um produto pelo código e devolve None quando não o encontra.
def buscar_produto_por_codigo(codigo:str, caminho_banco=CAMINHO_BANCO) -> Produto | None:
    conexao = conectar(caminho_banco)

    try:
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
            WHERE codigo = ?
            """,
            (codigo,),
        ).fetchone()

    finally:
        conexao.close()

    if produto_buscado is None:
        return None
    
    return montar_produto(produto_buscado)

# Converte uma linha retornada pelo SQLite em uma instância de Produto.
def montar_produto(produto_buscado) -> Produto:
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

    return novo_produto

def listar_produtos_repository(
    caminho_banco=CAMINHO_BANCO,
    ativo: bool | None = True,
    categoria: str | None = None,
    nome: str | None = None,
) -> list[Produto]:
    conexao = conectar(caminho_banco)

    try:
        consulta = """
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
            """
        condicoes = []
        parametros = []

        if ativo is not None:
            condicoes.append("ativo = ?")
            parametros.append(int(ativo))

        if categoria is not None:
            condicoes.append("categoria = ?")
            parametros.append(categoria)

        if nome is not None:
            condicoes.append("nome LIKE ?")
            parametros.append(f"%{nome}%")

        if condicoes:
            consulta += "\nWHERE " + " AND ".join(condicoes)

        consulta += "\nORDER BY nome"

        produtos_encontrados = conexao.execute(
            consulta,
            parametros,
        ).fetchall()

    finally:
        conexao.close()

    return [montar_produto(produto) for produto in produtos_encontrados]
