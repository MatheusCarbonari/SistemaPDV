import sqlite3
import pytest

from datetime import datetime
from models.produto import Produto
from database.schema import criar_tabelas
from repositories.produto_repository import (
    buscar_produto_banco_pelo_id,
    codigo_existe,
    salvar_produto,
)
import repositories.produto_repository as produto_repository


# Valida os dois resultados possíveis da consulta de existência do código.
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

def test_codigo_existe_retorna_false_quando_codigo_nao_esta_cadastrado(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_repository.db"

    criar_tabelas(caminho_banco)

    assert codigo_existe("999", caminho_banco) is False

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
