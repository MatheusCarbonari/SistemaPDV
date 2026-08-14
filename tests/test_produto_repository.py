import sqlite3
import pytest

from datetime import datetime
from models.produto import Produto
from database.schema import criar_tabelas
from repositories.produto_repository import (
    buscar_produto_banco_pelo_id,
    buscar_produto_por_codigo,
    codigo_existe,
    listar_produtos,
    salvar_produto,
)
import repositories.produto_repository as produto_repository


# Confirma que um código cadastrado é identificado pelo repositório.
def test_codigo_existe_retorna_true_quando_codigo_esta_cadastrado(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"

    criar_tabelas(caminho_banco)

    conexao = sqlite3.connect(caminho_banco)

    try:
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo,
                nome,
                categoria,
                forma_venda,
                preco_venda_centavos,
                origem
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "101",
                "Picanha",
                "BOVINOS",
                "PESO",
                7990,
                "COMPRADO",
            ),
        )

        conexao.commit()
    finally:
        conexao.close()

    assert codigo_existe("101", caminho_banco) is True

# Confirma que um código ausente não é identificado como cadastrado.
def test_codigo_existe_retorna_false_quando_codigo_nao_esta_cadastrado(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"

    criar_tabelas(caminho_banco)

    assert codigo_existe("999", caminho_banco) is False

# Verifica se o cadastro devolve o produto completo com os dados do banco.
def test_salvar_produto_retorna_produto_persistido(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    produto = Produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    produto_salvo = salvar_produto(produto, caminho_banco)

    assert produto_salvo.id is not None
    assert produto_salvo.codigo == "101"
    assert produto_salvo.nome == "Picanha"
    assert produto_salvo.categoria == "BOVINOS"
    assert produto_salvo.forma_venda == "PESO"
    assert produto_salvo.preco_venda_centavos == 7990
    assert produto_salvo.origem == "COMPRADO"
    assert produto_salvo.ativo is True
    assert isinstance(produto_salvo.criado_em, datetime)
    assert isinstance(produto_salvo.atualizado_em, datetime)


# Confirma a persistência com uma consulta independente do retorno da função.
def test_salvar_produto_persiste_dados_no_banco(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    produto = Produto(
        codigo="102",
        nome="Alcatra",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=6990,
        origem="COMPRADO",
    )

    salvar_produto(produto, caminho_banco)

    conexao = sqlite3.connect(caminho_banco)
    conexao.row_factory = sqlite3.Row

    try:
        produto_persistido = conexao.execute(
            """
            SELECT
                codigo,
                nome,
                categoria,
                forma_venda,
                preco_venda_centavos,
                origem,
                ativo
            FROM produtos
            WHERE codigo = ?
            """,
            ("102",),
        ).fetchone()
    finally:
        conexao.close()

    assert produto_persistido is not None
    assert produto_persistido["codigo"] == "102"
    assert produto_persistido["nome"] == "Alcatra"
    assert produto_persistido["categoria"] == "BOVINOS"
    assert produto_persistido["forma_venda"] == "PESO"
    assert produto_persistido["preco_venda_centavos"] == 6990
    assert produto_persistido["origem"] == "COMPRADO"
    assert produto_persistido["ativo"] == 1


# Garante que o repositório respeite a unicidade do código definida no schema.
def test_salvar_produto_nao_permite_codigo_duplicado(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    primeiro_produto = Produto(
        codigo="103",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )
    produto_duplicado = Produto(
        codigo="103",
        nome="Alcatra",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=6990,
        origem="COMPRADO",
    )

    salvar_produto(primeiro_produto, caminho_banco)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        salvar_produto(produto_duplicado, caminho_banco)


# Confirma que a busca usa o ID recebido quando existem vários produtos.
def test_buscar_produto_banco_pelo_id_retorna_registro_correto(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    conexao = sqlite3.connect(caminho_banco)

    try:
        conexao.execute(
            """
            INSERT INTO produtos (
                codigo,
                nome,
                categoria,
                forma_venda,
                preco_venda_centavos,
                origem
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("201", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        )
        cursor = conexao.execute(
            """
            INSERT INTO produtos (
                codigo,
                nome,
                categoria,
                forma_venda,
                preco_venda_centavos,
                origem
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("202", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        )
        segundo_produto_id = cursor.lastrowid
        conexao.commit()
    finally:
        conexao.close()

    produto_buscado = buscar_produto_banco_pelo_id(
        segundo_produto_id,
        caminho_banco,
    )

    assert produto_buscado is not None
    assert produto_buscado["id"] == segundo_produto_id
    assert produto_buscado["codigo"] == "202"
    assert produto_buscado["nome"] == "Alcatra"


# Define None como resultado esperado para um ID inexistente.
def test_buscar_produto_banco_pelo_id_retorna_none_quando_nao_encontrado(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    produto_buscado = buscar_produto_banco_pelo_id(999, caminho_banco)

    assert produto_buscado is None


# Mantém o cadastro quando a releitura pós-commit não encontra o produto.
def test_salvar_produto_retorna_produto_com_id_quando_releitura_falha(
    tmp_path,
    monkeypatch,
) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    produto = Produto(
        codigo="203",
        nome="Fraldinha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=5990,
        origem="COMPRADO",
    )

    monkeypatch.setattr(
        produto_repository,
        "buscar_produto_banco_pelo_id",
        lambda *args: None,
    )

    produto_salvo = salvar_produto(produto, caminho_banco)

    assert produto_salvo.id is not None
    assert produto_salvo.codigo == "203"
    assert produto_salvo.nome == "Fraldinha"
    assert produto_salvo.categoria == "BOVINOS"
    assert produto_salvo.forma_venda == "PESO"
    assert produto_salvo.preco_venda_centavos == 5990
    assert produto_salvo.origem == "COMPRADO"
    assert produto_salvo.criado_em is None
    assert produto_salvo.atualizado_em is None

    conexao = sqlite3.connect(caminho_banco)

    try:
        produto_persistido = conexao.execute(
            """
            SELECT id, codigo
            FROM produtos
            WHERE codigo = ?
            """,
            ("203",),
        ).fetchone()
    finally:
        conexao.close()

    assert produto_persistido is not None
    assert produto_persistido[0] == produto_salvo.id
    assert produto_persistido[1] == "203"

# Confirma que a busca por código devolve o produto correspondente.
def test_buscar_produto_por_codigo_retorna_produto_quando_existe(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    produto = Produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    salvar_produto(produto, caminho_banco)

    produto_buscado = buscar_produto_por_codigo("101", caminho_banco)

    assert produto_buscado is not None
    assert produto_buscado.codigo == "101"
    assert produto_buscado.nome == "Picanha"

# Define None como resultado esperado para um código inexistente.
def test_buscar_produto_por_codigo_retorna_none_quando_nao_existe(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    produto_buscado = buscar_produto_por_codigo("999", caminho_banco)

    assert produto_buscado is None


# Confirma que um banco sem produtos resulta em uma lista vazia.
def test_listar_produtos_retorna_lista_vazia_quando_nao_ha_produtos(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    produtos = listar_produtos(caminho_banco)

    assert produtos == []


# Confirma que todos os registros são convertidos em objetos Produto.
def test_listar_produtos_retorna_todos_os_produtos(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("301", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("302", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )

    produtos = listar_produtos(caminho_banco)

    assert len(produtos) == 2
    assert all(isinstance(produto, Produto) for produto in produtos)
    assert {produto.codigo for produto in produtos} == {"301", "302"}


# Confirma que a listagem mantém a ordenação alfabética definida na consulta.
def test_listar_produtos_retorna_produtos_ordenados_por_nome(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("303", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("304", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )

    produtos = listar_produtos(caminho_banco)

    assert [produto.nome for produto in produtos] == ["Alcatra", "Picanha"]


# Confirma que a listagem padrão retorna somente produtos ativos.
def test_listar_produtos_retorna_somente_ativos_por_padrao(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("305", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("306", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )

    conexao = sqlite3.connect(caminho_banco)
    try:
        conexao.execute(
            "UPDATE produtos SET ativo = 0 WHERE codigo = ?",
            ("306",),
        )
        conexao.commit()
    finally:
        conexao.close()

    produtos = listar_produtos(caminho_banco)

    assert [produto.codigo for produto in produtos] == ["305"]


# Confirma que o filtro False retorna somente produtos inativos.
def test_listar_produtos_retorna_somente_inativos(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("307", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("308", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )

    conexao = sqlite3.connect(caminho_banco)
    try:
        conexao.execute(
            "UPDATE produtos SET ativo = 0 WHERE codigo = ?",
            ("308",),
        )
        conexao.commit()
    finally:
        conexao.close()

    produtos = listar_produtos(caminho_banco, ativo=False)

    assert [produto.codigo for produto in produtos] == ["308"]


# Confirma que o filtro None retorna produtos ativos e inativos.
def test_listar_produtos_retorna_ativos_e_inativos(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("309", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("310", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )

    conexao = sqlite3.connect(caminho_banco)
    try:
        conexao.execute(
            "UPDATE produtos SET ativo = 0 WHERE codigo = ?",
            ("310",),
        )
        conexao.commit()
    finally:
        conexao.close()

    produtos = listar_produtos(caminho_banco, ativo=None)

    assert {produto.codigo for produto in produtos} == {"309", "310"}


# Confirma que o filtro retorna todos os produtos da categoria informada.
def test_listar_produtos_retorna_produtos_da_categoria_existente(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("311", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("312", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("313", "Peito de frango", "AVES", "PESO", 2490, "COMPRADO"),
        caminho_banco,
    )

    produtos = listar_produtos(caminho_banco, categoria="BOVINOS")

    assert {produto.codigo for produto in produtos} == {"311", "312"}


# Confirma que uma categoria não cadastrada resulta em uma lista vazia.
def test_listar_produtos_retorna_lista_vazia_para_categoria_inexistente(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("314", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )

    produtos = listar_produtos(caminho_banco, categoria="SUINOS")

    assert produtos == []


# Confirma que os filtros de categoria e situação são aplicados juntos.
def test_listar_produtos_combina_filtros_de_categoria_e_ativo(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("315", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("316", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("317", "Peito de frango", "AVES", "PESO", 2490, "COMPRADO"),
        caminho_banco,
    )

    conexao = sqlite3.connect(caminho_banco)
    try:
        conexao.execute(
            "UPDATE produtos SET ativo = 0 WHERE codigo = ?",
            ("316",),
        )
        conexao.commit()
    finally:
        conexao.close()

    produtos = listar_produtos(caminho_banco, categoria="BOVINOS")

    assert [produto.codigo for produto in produtos] == ["315"]


# Confirma que categoria e False retornam somente inativos correspondentes.
def test_listar_produtos_combina_categoria_com_ativo_false(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("318", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("319", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("320", "Peito de frango", "AVES", "PESO", 2490, "COMPRADO"),
        caminho_banco,
    )

    conexao = sqlite3.connect(caminho_banco)
    try:
        conexao.execute(
            "UPDATE produtos SET ativo = 0 WHERE codigo IN (?, ?)",
            ("319", "320"),
        )
        conexao.commit()
    finally:
        conexao.close()

    produtos = listar_produtos(
        caminho_banco,
        ativo=False,
        categoria="BOVINOS",
    )

    assert [produto.codigo for produto in produtos] == ["319"]


# Confirma que None ignora a situação, mas mantém o filtro de categoria.
def test_listar_produtos_combina_categoria_com_ativo_none(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"
    criar_tabelas(caminho_banco)

    salvar_produto(
        Produto("321", "Picanha", "BOVINOS", "PESO", 7990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("322", "Alcatra", "BOVINOS", "PESO", 6990, "COMPRADO"),
        caminho_banco,
    )
    salvar_produto(
        Produto("323", "Peito de frango", "AVES", "PESO", 2490, "COMPRADO"),
        caminho_banco,
    )

    conexao = sqlite3.connect(caminho_banco)
    try:
        conexao.execute(
            "UPDATE produtos SET ativo = 0 WHERE codigo = ?",
            ("322",),
        )
        conexao.commit()
    finally:
        conexao.close()

    produtos = listar_produtos(
        caminho_banco,
        ativo=None,
        categoria="BOVINOS",
    )

    assert {produto.codigo for produto in produtos} == {"321", "322"}
