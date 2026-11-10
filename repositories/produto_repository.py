from database.conexao import CAMINHO_BANCO, conectar
from models.categoria import (
    normalizar_identidade_categoria,
    validar_nome_categoria,
)
from models.produto import Produto
from models.comando_produto import (
    ComandoCadastroProduto,
    ComandoEdicaoProduto,
)
from datetime import datetime


class CategoriaProdutoIndisponivelError(ValueError):
    pass


class ConflitoProdutoError(RuntimeError):
    pass


class CodigoProdutoDuplicadoError(ValueError):
    pass


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
        conexao.execute("BEGIN IMMEDIATE")
        if produto.categoria_id is None:
            nome_categoria, chave_categoria, erros_categoria = (
                validar_nome_categoria(produto.categoria)
            )
            if erros_categoria:
                raise CategoriaProdutoIndisponivelError(
                    "Selecione uma categoria ativa."
                )
            conexao.execute(
                """
                INSERT INTO categorias (nome, nome_chave)
                VALUES (?, ?)
                ON CONFLICT(nome_chave) DO NOTHING
                """,
                (nome_categoria, chave_categoria),
            )
            categoria_legada = conexao.execute(
                """
                SELECT id, ativo FROM categorias WHERE nome_chave = ?
                """,
                (chave_categoria,),
            ).fetchone()
            produto.categoria_id = categoria_legada["id"]
        categoria_selecionada = conexao.execute(
            "SELECT ativo FROM categorias WHERE id = ?",
            (produto.categoria_id,),
        ).fetchone()
        if (
            categoria_selecionada is None
            or categoria_selecionada["ativo"] != 1
        ):
            raise CategoriaProdutoIndisponivelError(
                "Selecione uma categoria ativa."
            )
        cursor = conexao.execute(
            """
            INSERT INTO produtos(
                codigo,
                nome,
                categoria_id,
                forma_venda,
                preco_venda_centavos,
                origem
            )
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                produto.codigo,
                produto.nome,
                produto.categoria_id,
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

    except Exception:
        conexao.rollback()
        raise
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
                p.id,
                p.codigo,
                p.nome,
                p.categoria_id,
                c.nome AS categoria,
                p.forma_venda,
                p.preco_venda_centavos,
                p.origem,
                p.ativo,
                p.criado_em,
                p.atualizado_em
            FROM produtos AS p
            JOIN categorias AS c ON c.id = p.categoria_id
            WHERE p.id = ?
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
                p.id,
                p.codigo,
                p.nome,
                p.categoria_id,
                c.nome AS categoria,
                p.forma_venda,
                p.preco_venda_centavos,
                p.origem,
                p.ativo,
                p.criado_em,
                p.atualizado_em
            FROM produtos AS p
            JOIN categorias AS c ON c.id = p.categoria_id
            WHERE p.codigo = ?
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
        categoria_id=produto_buscado["categoria_id"],
    )

    return novo_produto

def listar_produtos_repository(
    caminho_banco=CAMINHO_BANCO,
    ativo: bool | None = True,
    categoria: str | None = None,
    nome: str | None = None,
    termo: str | None = None,
    categoria_id: int | None = None,
) -> list[Produto]:
    conexao = conectar(caminho_banco)

    try:
        consulta = """
            SELECT
                p.id,
                p.codigo,
                p.nome,
                p.categoria_id,
                c.nome AS categoria,
                p.forma_venda,
                p.preco_venda_centavos,
                p.origem,
                p.ativo,
                p.criado_em,
                p.atualizado_em
            FROM produtos AS p
            JOIN categorias AS c ON c.id = p.categoria_id
            """
        condicoes = []
        parametros = []

        if ativo is not None:
            condicoes.append("p.ativo = ?")
            parametros.append(int(ativo))

        if categoria is not None:
            _, chave = normalizar_identidade_categoria(categoria)
            condicoes.append("c.nome_chave = ?")
            parametros.append(chave)

        if categoria_id is not None:
            condicoes.append("p.categoria_id = ?")
            parametros.append(categoria_id)

        if nome is not None:
            condicoes.append("p.nome LIKE ?")
            parametros.append(f"%{nome}%")

        if termo is not None:
            condicoes.append("(p.codigo LIKE ? OR p.nome LIKE ?)")
            parametros.extend((f"%{termo}%", f"%{termo}%"))

        if condicoes:
            consulta += "\nWHERE " + " AND ".join(condicoes)

        consulta += "\nORDER BY p.nome"

        produtos_encontrados = conexao.execute(
            consulta,
            parametros,
        ).fetchall()

    finally:
        conexao.close()

    return [montar_produto(produto) for produto in produtos_encontrados]


# Altera a situação do produto e informa se o ID foi encontrado.
def alterar_situacao_produto_repository(
    produto_id: int,
    ativo: bool,
    caminho_banco=CAMINHO_BANCO,
) -> bool:
    conexao = conectar(caminho_banco)

    try:
        cursor = conexao.execute(
            """
            UPDATE produtos
            SET
                ativo = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (int(ativo), produto_id),
        )
        conexao.commit()

        foi_atualizado = cursor.rowcount > 0
    finally:
        conexao.close()

    return foi_atualizado

def atualizar_produto_repository(
        produto: Produto,
        caminho_banco=CAMINHO_BANCO
) -> Produto | None:

    conexao = conectar(caminho_banco)

    try:
        conexao.execute("BEGIN IMMEDIATE")
        produto_atual = conexao.execute(
            """
            SELECT preco_venda_centavos, categoria_id
            FROM produtos
            WHERE id = ?
            """,
            (produto.id,),
        ).fetchone()
        if produto_atual is None:
            conexao.rollback()
            return None

        categoria_selecionada = conexao.execute(
            "SELECT ativo FROM categorias WHERE id = ?",
            (produto.categoria_id,),
        ).fetchone()
        if categoria_selecionada is None or (
            categoria_selecionada["ativo"] != 1
            and produto.categoria_id != produto_atual["categoria_id"]
        ):
            raise CategoriaProdutoIndisponivelError(
                "Selecione uma categoria ativa."
            )

        preco_anterior = produto_atual["preco_venda_centavos"]
        cursor = conexao.execute(
            """
            UPDATE produtos
            SET
                codigo = ?,
                nome = ?,
                categoria_id = ?,
                forma_venda = ?,
                preco_venda_centavos = ?,
                origem = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                produto.codigo,
                produto.nome,
                produto.categoria_id,
                produto.forma_venda,
                produto.preco_venda_centavos,
                produto.origem,
                produto.id,
            ),
        )

        if cursor.rowcount == 0:
            conexao.rollback()
            return None

        if preco_anterior != produto.preco_venda_centavos:
            conexao.execute(
                """
                INSERT INTO historico_precos_produtos (
                    produto_id,
                    preco_anterior_centavos,
                    preco_novo_centavos
                )
                VALUES (?, ?, ?)
                """,
                (
                    produto.id,
                    preco_anterior,
                    produto.preco_venda_centavos,
                ),
            )

        conexao.commit()
    except Exception:
        conexao.rollback()
        raise

    finally:
        conexao.close()

    produto_buscado = buscar_produto_banco_pelo_id(
        produto.id,
        caminho_banco
    )

    if produto_buscado is None:
        return None

    return montar_produto(produto_buscado)


def cadastrar_produto_comando_repository(
    comando: ComandoCadastroProduto,
    caminho_banco=CAMINHO_BANCO,
) -> Produto:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        _exigir_categoria_aprovada(conexao, comando.categoria)
        cursor = conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria_id, forma_venda,
                preco_venda_centavos, origem
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                comando.codigo,
                comando.nome,
                comando.categoria.id,
                comando.forma_venda,
                comando.preco_venda_centavos,
                comando.origem,
            ),
        )
        produto_id = cursor.lastrowid
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()
    return montar_produto(
        buscar_produto_banco_pelo_id(produto_id, caminho_banco)
    )


def editar_produto_comando_repository(
    comando: ComandoEdicaoProduto,
    caminho_banco=CAMINHO_BANCO,
) -> Produto:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        atual = conexao.execute(
            """
            SELECT
                p.id, p.codigo, p.nome, p.forma_venda,
                p.preco_venda_centavos, p.origem, p.ativo,
                c.id AS categoria_id, c.nome AS categoria_nome,
                c.nome_chave AS categoria_chave, c.ativo AS categoria_ativa
            FROM produtos AS p
            JOIN categorias AS c ON c.id = p.categoria_id
            WHERE p.id = ?
            """,
            (comando.estado_base.id,),
        ).fetchone()
        if atual is None or not _estado_base_corresponde(
            atual,
            comando.estado_base,
        ):
            raise ConflitoProdutoError(
                "O produto foi alterado após a autorização. Recarregue os "
                "dados e solicite uma nova autorização."
            )
        _exigir_categoria_aprovada(
            conexao,
            comando.categoria,
            permitir_inativa=(
                comando.categoria.id == comando.estado_base.categoria.id
            ),
        )

        codigo_em_uso = conexao.execute(
            """
            SELECT id
            FROM produtos
            WHERE codigo = ? AND id <> ?
            LIMIT 1
            """,
            (comando.codigo, comando.estado_base.id),
        ).fetchone()
        if codigo_em_uso is not None:
            raise CodigoProdutoDuplicadoError(
                "Já existe outro produto com esse código."
            )

        conexao.execute(
            """
            UPDATE produtos
            SET codigo = ?, nome = ?, categoria_id = ?, forma_venda = ?,
                preco_venda_centavos = ?, origem = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                comando.codigo,
                comando.nome,
                comando.categoria.id,
                comando.forma_venda,
                comando.preco_venda_centavos,
                comando.origem,
                comando.estado_base.id,
            ),
        )
        if (
            comando.estado_base.preco_venda_centavos
            != comando.preco_venda_centavos
        ):
            conexao.execute(
                """
                INSERT INTO historico_precos_produtos (
                    produto_id, preco_anterior_centavos, preco_novo_centavos
                ) VALUES (?, ?, ?)
                """,
                (
                    comando.estado_base.id,
                    comando.estado_base.preco_venda_centavos,
                    comando.preco_venda_centavos,
                ),
            )
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()
    return montar_produto(
        buscar_produto_banco_pelo_id(
            comando.estado_base.id,
            caminho_banco,
        )
    )


def _exigir_categoria_aprovada(
    conexao,
    categoria,
    *,
    permitir_inativa=False,
) -> None:
    atual = conexao.execute(
        "SELECT id, nome, nome_chave, ativo FROM categorias WHERE id = ?",
        (categoria.id,),
    ).fetchone()
    if atual is None or (
        atual["nome"] != categoria.nome
        or atual["nome_chave"] != categoria.nome_chave
        or bool(atual["ativo"]) is not categoria.ativo
        or (not categoria.ativo and not permitir_inativa)
    ):
        raise ConflitoProdutoError(
            "A categoria foi alterada após a autorização. Recarregue os "
            "dados e solicite uma nova autorização."
        )


def _estado_base_corresponde(atual, esperado) -> bool:
    return (
        atual["id"] == esperado.id
        and atual["codigo"] == esperado.codigo
        and atual["nome"] == esperado.nome
        and atual["categoria_id"] == esperado.categoria.id
        and atual["categoria_nome"] == esperado.categoria.nome
        and atual["categoria_chave"] == esperado.categoria.nome_chave
        and bool(atual["categoria_ativa"]) is esperado.categoria.ativo
        and atual["forma_venda"] == esperado.forma_venda
        and atual["preco_venda_centavos"] == esperado.preco_venda_centavos
        and atual["origem"] == esperado.origem
        and bool(atual["ativo"]) is esperado.ativo
    )
