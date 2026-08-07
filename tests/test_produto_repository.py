import sqlite3

from database.schema import criar_tabelas
from repositories.produto_repository import codigo_existe


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
