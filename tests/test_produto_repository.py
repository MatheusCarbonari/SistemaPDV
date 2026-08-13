import sqlite3

from datetime import datetime
from models.produto import Produto
from database.schema import criar_tabelas
from repositories.produto_repository import codigo_existe, salvar_produto


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