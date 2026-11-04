import pytest
import sqlite3

import database.schema as schema
from database.conexao import conectar
from database.schema import criar_tabelas


# Cria um banco isolado para cada teste, sem tocar nos dados principais.
@pytest.fixture
def banco_teste(tmp_path):

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


def test_tabela_vendas_existe_com_estrutura_esperada(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        tabela = conexao.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'vendas'
            """
        ).fetchone()
        colunas = {
            coluna["name"]: coluna
            for coluna in conexao.execute("PRAGMA table_info(vendas)").fetchall()
        }

        assert tabela is not None
        assert set(colunas) == {
            "id",
            "total_centavos",
            "registrada_em",
            "identificador_tentativa",
        }
        assert colunas["id"]["type"] == "INTEGER"
        assert colunas["id"]["pk"] == 1
        assert colunas["total_centavos"]["type"] == "INTEGER"
        assert colunas["total_centavos"]["notnull"] == 1
        assert colunas["registrada_em"]["type"] == "TEXT"
        assert colunas["registrada_em"]["notnull"] == 1
        assert colunas["registrada_em"]["dflt_value"] == "CURRENT_TIMESTAMP"
    finally:
        conexao.close()


def test_banco_novo_recebe_versao_atual_do_esquema(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]

        assert versao == schema.VERSAO_ESQUEMA
    finally:
        conexao.close()


def test_migracao_preserva_produto_e_estrutura_de_banco_existente(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "banco_legado.db"
    conexao = conectar(caminho_banco)

    try:
        conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
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
            ("101", "Picanha", "BOVINO", "PESO", 7990, "COMPRADO"),
        )
        conexao.execute(
            "CREATE TABLE configuracoes_legadas (chave TEXT PRIMARY KEY)"
        )
        conexao.execute(
            "INSERT INTO configuracoes_legadas (chave) VALUES (?)",
            ("preservar",),
        )
        conexao.commit()
    finally:
        conexao.close()

    criar_tabelas(caminho_banco)

    conexao = conectar(caminho_banco)
    try:
        produto = conexao.execute(
            "SELECT codigo, nome, preco_venda_centavos FROM produtos"
        ).fetchone()
        configuracao = conexao.execute(
            "SELECT chave FROM configuracoes_legadas"
        ).fetchone()
        tabela_vendas = conexao.execute(
            "SELECT name FROM sqlite_master WHERE name = 'vendas'"
        ).fetchone()

        assert tuple(produto) == ("101", "Picanha", 7990)
        assert configuracao["chave"] == "preservar"
        assert tabela_vendas["name"] == "vendas"
    finally:
        conexao.close()


def test_reexecutar_migracao_preserva_dados_e_nao_duplica_estruturas(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)

    try:
        conexao.execute(
            "INSERT INTO vendas (total_centavos) VALUES (?)",
            (2500,),
        )
        conexao.commit()
    finally:
        conexao.close()

    criar_tabelas(banco_teste)
    criar_tabelas(banco_teste)

    conexao = conectar(banco_teste)
    try:
        venda = conexao.execute(
            "SELECT total_centavos FROM vendas"
        ).fetchone()
        quantidade_tabelas_vendas = conexao.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'vendas'
            """
        ).fetchone()[0]

        assert venda["total_centavos"] == 2500
        assert quantidade_tabelas_vendas == 1
    finally:
        conexao.close()


@pytest.mark.parametrize("total_invalido", [None, 0, -1, 1.5, "invalido"])
def test_venda_rejeita_total_invalido(banco_teste, total_invalido) -> None:
    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                "INSERT INTO vendas (total_centavos) VALUES (?)",
                (total_invalido,),
            )
    finally:
        conexao.close()


def test_venda_exige_total_e_data_de_registro(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute("INSERT INTO vendas DEFAULT VALUES")

        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                """
                INSERT INTO vendas (total_centavos, registrada_em)
                VALUES (?, NULL)
                """,
                (1000,),
            )

        with pytest.raises(sqlite3.IntegrityError):
            conexao.execute(
                """
                INSERT INTO vendas (total_centavos, registrada_em)
                VALUES (?, ?)
                """,
                (1000, "  "),
            )
    finally:
        conexao.close()


def test_venda_valida_recebe_data_automaticamente(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        cursor = conexao.execute(
            "INSERT INTO vendas (total_centavos) VALUES (?)",
            (3750,),
        )
        venda = conexao.execute(
            """
            SELECT id, total_centavos, registrada_em
            FROM vendas
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

        assert venda["id"] == cursor.lastrowid
        assert venda["total_centavos"] == 3750
        assert venda["registrada_em"]
    finally:
        conexao.close()


def test_id_de_venda_e_unico_independente_da_data_e_nao_e_reaproveitado(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)
    mesma_data = "2026-11-03 12:00:00"

    try:
        primeira = conexao.execute(
            """
            INSERT INTO vendas (total_centavos, registrada_em)
            VALUES (?, ?)
            """,
            (1000, mesma_data),
        ).lastrowid
        segunda = conexao.execute(
            """
            INSERT INTO vendas (total_centavos, registrada_em)
            VALUES (?, ?)
            """,
            (2000, mesma_data),
        ).lastrowid
        conexao.execute("DELETE FROM vendas WHERE id = ?", (segunda,))
        terceira = conexao.execute(
            """
            INSERT INTO vendas (total_centavos, registrada_em)
            VALUES (?, ?)
            """,
            (3000, mesma_data),
        ).lastrowid

        assert primeira != segunda
        assert terceira > segunda
    finally:
        conexao.close()


def test_falha_na_migracao_desfaz_todas_as_alteracoes(
    tmp_path,
    monkeypatch,
) -> None:
    caminho_banco = tmp_path / "migracao_incompleta.db"
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_VENDAS",
        "CREATE TABLE vendas (id INTEGER PRIMARY KEY,",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(caminho_banco)

    conexao = conectar(caminho_banco)
    try:
        tabelas = conexao.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]

        assert tabelas == []
        assert versao == 0
    finally:
        conexao.close()


def test_migracao_nao_rebaixa_banco_com_esquema_mais_novo(tmp_path) -> None:
    caminho_banco = tmp_path / "esquema_futuro.db"
    conexao = conectar(caminho_banco)
    versao_futura = schema.VERSAO_ESQUEMA + 1

    try:
        conexao.execute("CREATE TABLE dados_futuros (valor TEXT NOT NULL)")
        conexao.execute(
            "INSERT INTO dados_futuros (valor) VALUES (?)",
            ("preservar",),
        )
        conexao.execute(f"PRAGMA user_version = {versao_futura}")
        conexao.commit()
    finally:
        conexao.close()

    with pytest.raises(RuntimeError, match="versão de esquema mais nova"):
        criar_tabelas(caminho_banco)

    conexao = conectar(caminho_banco)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        dado = conexao.execute("SELECT valor FROM dados_futuros").fetchone()

        assert versao == versao_futura
        assert dado["valor"] == "preservar"
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

def test_preco_zero_nao_aceito(banco_teste) -> None:
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
                    origem
                )
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    "106",
                    "Frango Assado",
                    "ASSADOS",
                    "UNIDADE",
                    0,
                    'PRODUZIDO'
                ),
            )
    finally:
        conexao.close()
