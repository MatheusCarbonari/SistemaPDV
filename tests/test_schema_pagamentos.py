import sqlite3

import pytest

import database.schema as schema
from database.conexao import conectar
from database.schema import criar_tabelas


@pytest.fixture
def banco_teste(tmp_path):
    caminho_banco = tmp_path / "pagamentos.db"
    criar_tabelas(caminho_banco)
    return caminho_banco


def _inserir_venda(conexao, total_centavos=10000) -> int:
    return conexao.execute(
        "INSERT INTO vendas (total_centavos) VALUES (?)",
        (total_centavos,),
    ).lastrowid


def _inserir_pagamento(
    conexao,
    venda_id,
    modalidade="DINHEIRO",
    valor_centavos=1000,
) -> int:
    return conexao.execute(
        """
        INSERT INTO pagamentos (venda_id, modalidade, valor_centavos)
        VALUES (?, ?, ?)
        """,
        (venda_id, modalidade, valor_centavos),
    ).lastrowid


def _preparar_banco_na_versao(caminho_banco, versao) -> None:
    conexao = conectar(caminho_banco)

    try:
        conexao.execute("BEGIN IMMEDIATE")
        if versao >= 1:
            conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
            conexao.execute(schema._COMANDO_CRIAR_VENDAS)
        if versao >= 2:
            conexao.execute(schema._COMANDO_CRIAR_ITENS_VENDA)
        conexao.execute(f"PRAGMA user_version = {versao}")
        conexao.commit()
    finally:
        conexao.close()


def _criar_banco_versao_2_com_dados(caminho_banco) -> tuple[int, int, int]:
    _preparar_banco_na_versao(caminho_banco, 2)
    conexao = conectar(caminho_banco)

    try:
        produto_id = conexao.execute(
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
            ("234", "Picanha", "BOVINO", "PESO", 7990, "COMPRADO"),
        ).lastrowid
        venda_id = _inserir_venda(conexao)
        item_id = conexao.execute(
            """
            INSERT INTO itens_venda (
                venda_id,
                posicao,
                produto_id,
                codigo_snapshot,
                nome_snapshot,
                forma_venda_snapshot,
                preco_referencia_centavos,
                tipo_item,
                origem,
                origem_quantidade,
                quantidade_decimal,
                codigo_barras,
                subtotal_centavos
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                venda_id,
                0,
                produto_id,
                "234",
                "Picanha",
                "PESO",
                7990,
                "PRODUTO",
                "MANUAL",
                "NAO_INFORMADA",
                None,
                None,
                10000,
            ),
        ).lastrowid
        conexao.commit()
        return produto_id, venda_id, item_id
    finally:
        conexao.close()


def test_banco_novo_cria_tabela_pagamentos_na_versao_3(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        tabela = conexao.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'pagamentos'
            """
        ).fetchone()
        colunas = {
            coluna["name"]: coluna
            for coluna in conexao.execute(
                "PRAGMA table_info(pagamentos)"
            ).fetchall()
        }
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]

        assert tabela["name"] == "pagamentos"
        assert set(colunas) == {
            "id",
            "venda_id",
            "modalidade",
            "valor_centavos",
        }
        assert colunas["id"]["pk"] == 1
        assert colunas["venda_id"]["notnull"] == 1
        assert colunas["modalidade"]["notnull"] == 1
        assert colunas["valor_centavos"]["notnull"] == 1
        assert versao == 3
    finally:
        conexao.close()


def test_pagamentos_referencia_venda_com_exclusao_restrita(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)

    try:
        chave_estrangeira = conexao.execute(
            "PRAGMA foreign_key_list(pagamentos)"
        ).fetchone()

        assert chave_estrangeira["table"] == "vendas"
        assert chave_estrangeira["from"] == "venda_id"
        assert chave_estrangeira["to"] == "id"
        assert chave_estrangeira["on_delete"] == "RESTRICT"
    finally:
        conexao.close()


def test_migracao_da_versao_2_preserva_produto_venda_e_item(tmp_path) -> None:
    caminho_banco = tmp_path / "versao_2.db"
    produto_id, venda_id, item_id = _criar_banco_versao_2_com_dados(
        caminho_banco
    )

    criar_tabelas(caminho_banco)

    conexao = conectar(caminho_banco)
    try:
        produto = conexao.execute(
            "SELECT codigo FROM produtos WHERE id = ?",
            (produto_id,),
        ).fetchone()
        venda = conexao.execute(
            "SELECT total_centavos FROM vendas WHERE id = ?",
            (venda_id,),
        ).fetchone()
        item = conexao.execute(
            "SELECT subtotal_centavos FROM itens_venda WHERE id = ?",
            (item_id,),
        ).fetchone()
        quantidade_pagamentos = conexao.execute(
            "SELECT COUNT(*) FROM pagamentos"
        ).fetchone()[0]
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]

        assert produto["codigo"] == "234"
        assert venda["total_centavos"] == 10000
        assert item["subtotal_centavos"] == 10000
        assert quantidade_pagamentos == 0
        assert versao == 3
    finally:
        conexao.close()


@pytest.mark.parametrize("versao_inicial", [0, 1, 2])
def test_bancos_antigos_evoluem_sequencialmente_ate_versao_3(
    tmp_path,
    versao_inicial,
) -> None:
    caminho_banco = tmp_path / f"versao_{versao_inicial}.db"
    _preparar_banco_na_versao(caminho_banco, versao_inicial)

    criar_tabelas(caminho_banco)

    conexao = conectar(caminho_banco)
    try:
        tabelas = {
            linha["name"]
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        versao_final = conexao.execute("PRAGMA user_version").fetchone()[0]

        assert {"produtos", "vendas", "itens_venda", "pagamentos"} <= tabelas
        assert versao_final == 3
    finally:
        conexao.close()


def test_aceita_pagamento_unico_e_multiplos_por_venda(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        primeira_venda = _inserir_venda(conexao, 1000)
        segunda_venda = _inserir_venda(conexao, 10000)
        _inserir_pagamento(conexao, primeira_venda, "DINHEIRO", 1000)
        modalidades = ["DINHEIRO", "CREDITO", "DEBITO", "PIX"]
        for modalidade in modalidades:
            _inserir_pagamento(conexao, segunda_venda, modalidade, 2500)

        primeiro_total = conexao.execute(
            "SELECT COUNT(*) FROM pagamentos WHERE venda_id = ?",
            (primeira_venda,),
        ).fetchone()[0]
        pagamentos_divididos = conexao.execute(
            """
            SELECT modalidade, valor_centavos
            FROM pagamentos
            WHERE venda_id = ?
            ORDER BY id
            """,
            (segunda_venda,),
        ).fetchall()

        assert primeiro_total == 1
        assert [tuple(pagamento) for pagamento in pagamentos_divididos] == [
            ("DINHEIRO", 2500),
            ("CREDITO", 2500),
            ("DEBITO", 2500),
            ("PIX", 2500),
        ]
    finally:
        conexao.close()


def test_modalidade_pode_repetir_na_mesma_venda(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)
        ids = [
            _inserir_pagamento(conexao, venda_id, "PIX", valor)
            for valor in (1000, 2000, 3000)
        ]
        pagamentos = conexao.execute(
            """
            SELECT id, modalidade, valor_centavos
            FROM pagamentos
            WHERE venda_id = ?
            ORDER BY id
            """,
            (venda_id,),
        ).fetchall()

        assert [pagamento["id"] for pagamento in pagamentos] == ids
        assert [pagamento["modalidade"] for pagamento in pagamentos] == [
            "PIX",
            "PIX",
            "PIX",
        ]
    finally:
        conexao.close()


@pytest.mark.parametrize(
    "modalidade_invalida",
    [None, "", "CARTAO", "credito", "CRÉDITO"],
)
def test_rejeita_modalidade_invalida(
    banco_teste,
    modalidade_invalida,
) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError):
            _inserir_pagamento(
                conexao,
                venda_id,
                modalidade=modalidade_invalida,
            )
    finally:
        conexao.close()


@pytest.mark.parametrize(
    "valor_invalido",
    [None, 0, -1, 1.5, "invalido"],
)
def test_rejeita_valor_de_pagamento_invalido(
    banco_teste,
    valor_invalido,
) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError):
            _inserir_pagamento(
                conexao,
                venda_id,
                valor_centavos=valor_invalido,
            )
    finally:
        conexao.close()


def test_rejeita_pagamento_para_venda_inexistente(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            _inserir_pagamento(conexao, venda_id=999)
    finally:
        conexao.close()


def test_venda_com_pagamento_nao_pode_ser_excluida(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)
        _inserir_pagamento(conexao, venda_id)

        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conexao.execute("DELETE FROM vendas WHERE id = ?", (venda_id,))
    finally:
        conexao.close()


def test_pagamento_nao_exige_item_nem_soma_igual_ao_total(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao, total_centavos=10000)
        pagamento_id = _inserir_pagamento(
            conexao,
            venda_id,
            modalidade="DINHEIRO",
            valor_centavos=1,
        )
        quantidade_itens = conexao.execute(
            "SELECT COUNT(*) FROM itens_venda WHERE venda_id = ?",
            (venda_id,),
        ).fetchone()[0]

        assert pagamento_id is not None
        assert quantidade_itens == 0
    finally:
        conexao.close()


def test_reexecutar_migracao_preserva_pagamentos(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)
        pagamento_id = _inserir_pagamento(conexao, venda_id, "PIX", 10000)
        conexao.commit()
    finally:
        conexao.close()

    criar_tabelas(banco_teste)
    criar_tabelas(banco_teste)

    conexao = conectar(banco_teste)
    try:
        pagamento = conexao.execute(
            """
            SELECT id, modalidade, valor_centavos
            FROM pagamentos
            WHERE id = ?
            """,
            (pagamento_id,),
        ).fetchone()

        assert tuple(pagamento) == (pagamento_id, "PIX", 10000)
    finally:
        conexao.close()


def test_falha_na_migracao_3_preserva_versao_2_e_dados(
    tmp_path,
    monkeypatch,
) -> None:
    caminho_banco = tmp_path / "falha_versao_3.db"
    produto_id, venda_id, item_id = _criar_banco_versao_2_com_dados(
        caminho_banco
    )
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_PAGAMENTOS",
        "CREATE TABLE pagamentos (id INTEGER PRIMARY KEY,",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(caminho_banco)

    conexao = conectar(caminho_banco)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        produto = conexao.execute(
            "SELECT id FROM produtos WHERE id = ?",
            (produto_id,),
        ).fetchone()
        venda = conexao.execute(
            "SELECT id FROM vendas WHERE id = ?",
            (venda_id,),
        ).fetchone()
        item = conexao.execute(
            "SELECT id FROM itens_venda WHERE id = ?",
            (item_id,),
        ).fetchone()
        pagamentos = conexao.execute(
            "SELECT name FROM sqlite_master WHERE name = 'pagamentos'"
        ).fetchone()

        assert versao == 2
        assert produto["id"] == produto_id
        assert venda["id"] == venda_id
        assert item["id"] == item_id
        assert pagamentos is None
    finally:
        conexao.close()
