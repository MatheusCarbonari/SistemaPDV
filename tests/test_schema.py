import pytest
from pathlib import Path
import sqlite3

from database.conexao import conectar
from database.schema import criar_tabelas


# Cria um banco isolado para cada teste, sem tocar nos dados principais.
@pytest.fixture
def banco_teste(tmp_path):
    caminho = Path("tests/banco_teste.db")

    caminho = tmp_path / "banco_teste.db"

    criar_tabelas(caminho)

    return caminho


def test_tabela_produtos_existe(banco_teste):
    conexao = conectar(banco_teste)

    try:
        resultado = conexao.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'produtos'
            """
        ).fetchone()

        assert resultado is not None
        assert resultado["name"] == "produtos"
    finally:
        conexao.close()

def test_codigo_produto_nao_pode_repetir(banco_teste) -> None:
    conexao = conectar(banco_teste)

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
                "BOVINO",
                "PESO",
                7990,
                "COMPRADO",
            ),
        )

        conexao.commit()

        with pytest.raises(sqlite3.IntegrityError):
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
                    "Outro produto",
                    "BOVINO",
                    "PESO",
                    5000,
                    "COMPRADO",
                ),
            )
    finally:
        conexao.close()


def test_preco_negativo_nao_e_aceito(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError):
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
                    "102",
                    "Outro produto",
                    "BOVINO",
                    "PESO",
                    -100,
                    "COMPRADO",
                ),
            )
    finally:
        conexao.close()


def test_forma_venda_invalida_nao_e_aceita(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError):
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
                    "102",
                    "Outro produto",
                    "BOVINO",
                    "CAIXA",
                    8990,
                    "COMPRADO",
                ),
            )
    finally:
        conexao.close()


def test_categoria_nao_pode_ser_nula(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError):
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
                    "102",
                    "Outro produto",
                    None,
                    "PESO",
                    8990,
                    "COMPRADO",
                ),
            )
    finally:
        conexao.close()

def test_origem_invalida_nao_e_aceita(banco_teste) -> None:

    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                """
                INSERT INTO  produtos(
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
                    "103",
                    "Picanha",
                    "BOVINO",
                    "PESO",
                    9990,
                    "TERCEIRIZADO"
                ),
            )
    finally:
        conexao.close()

def test_ativo_invalido_nao_e_aceito(banco_teste) -> None:

    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                """
                INSERT INTO produtos(
                    codigo,
                    nome,
                    categoria,
                    forma_venda,
                    preco_venda_centavos,
                    origem,
                    ativo
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "103",
                    "Frango Assado",
                    "ASSADOS",
                    "UNIDADE",
                    6000,
                    "PRODUZIDO",
                    2,
                ),
            )
    finally:
        conexao.close()

def test_produto_valido_e_cadastrado_com_valores_automaticos(banco_teste)->None:

    conexao = conectar(banco_teste)

    try:
        conexao.execute(
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
                "106",
                "Frango Assado",
                "ASSADOS",
                "UNIDADE",
                6000,
                'PRODUZIDO'
            ),
        )

        conexao.commit()

        resultado = conexao.execute(
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
            ("106",),

        ).fetchone()

        assert resultado is not None
        assert resultado["id"] is not None
        assert resultado["codigo"] == "106"
        assert resultado["nome"] == "Frango Assado"
        assert resultado["categoria"] == "ASSADOS"
        assert resultado["forma_venda"] == "UNIDADE"
        assert resultado["preco_venda_centavos"] == 6000
        assert resultado["origem"] == "PRODUZIDO"
        assert resultado["ativo"] == 1
        assert resultado["criado_em"] is not None
        assert resultado["atualizado_em"] is not None

    finally:
        conexao.close()
