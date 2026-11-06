from decimal import Decimal
import sqlite3

import pytest

import database.schema as schema
from database.conexao import conectar
from database.schema import criar_tabelas


@pytest.fixture
def banco_teste(tmp_path):
    caminho_banco = tmp_path / "itens_venda.db"
    criar_tabelas(caminho_banco)
    return caminho_banco


def _inserir_produto(conexao, codigo="234") -> int:
    colunas = {
        coluna["name"]
        for coluna in conexao.execute("PRAGMA table_info(produtos)").fetchall()
    }
    if "categoria_id" not in colunas:
        return conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria, forma_venda,
                preco_venda_centavos, origem
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (codigo, "Picanha", "BOVINO", "PESO", 7990, "COMPRADO"),
        ).lastrowid

    categoria = conexao.execute(
        "SELECT id FROM categorias WHERE nome_chave = 'bovino'"
    ).fetchone()
    categoria_id = (
        categoria[0]
        if categoria is not None
        else conexao.execute(
            "INSERT INTO categorias (nome, nome_chave) "
            "VALUES ('BOVINO', 'bovino')"
        ).lastrowid
    )
    return conexao.execute(
        """
        INSERT INTO produtos (
            codigo,
            nome,
            categoria_id,
            forma_venda,
            preco_venda_centavos,
            origem
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (codigo, "Picanha", categoria_id, "PESO", 7990, "COMPRADO"),
    ).lastrowid


def _inserir_venda(conexao, total_centavos=10000) -> int:
    return conexao.execute(
        "INSERT INTO vendas (total_centavos) VALUES (?)",
        (total_centavos,),
    ).lastrowid


def _inserir_item_produto(conexao, venda_id, **alteracoes) -> int:
    dados = {
        "venda_id": venda_id,
        "posicao": 0,
        "produto_id": None,
        "codigo_snapshot": "234",
        "nome_snapshot": "Picanha",
        "forma_venda_snapshot": "PESO",
        "preco_referencia_centavos": 7990,
        "tipo_item": "PRODUTO",
        "origem": "MANUAL",
        "origem_quantidade": "INFORMADA",
        "quantidade_decimal": "1.250",
        "codigo_barras": None,
        "subtotal_centavos": 9988,
    }
    dados.update(alteracoes)

    return conexao.execute(
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
        VALUES (
            :venda_id,
            :posicao,
            :produto_id,
            :codigo_snapshot,
            :nome_snapshot,
            :forma_venda_snapshot,
            :preco_referencia_centavos,
            :tipo_item,
            :origem,
            :origem_quantidade,
            :quantidade_decimal,
            :codigo_barras,
            :subtotal_centavos
        )
        """,
        dados,
    ).lastrowid


def _criar_banco_versao_1(caminho_banco) -> tuple[int, int]:
    conexao = conectar(caminho_banco)

    try:
        conexao.execute("BEGIN IMMEDIATE")
        conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
        conexao.execute(schema._COMANDO_CRIAR_VENDAS)
        produto_id = _inserir_produto(conexao)
        venda_id = _inserir_venda(conexao)
        conexao.execute("PRAGMA user_version = 1")
        conexao.commit()
        return produto_id, venda_id
    finally:
        conexao.close()


def test_banco_novo_cria_tabela_itens_venda(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        tabela = conexao.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'itens_venda'
            """
        ).fetchone()
        colunas = {
            coluna["name"]
            for coluna in conexao.execute(
                "PRAGMA table_info(itens_venda)"
            ).fetchall()
        }
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]

        assert tabela["name"] == "itens_venda"
        assert colunas == {
            "id",
            "venda_id",
            "posicao",
            "produto_id",
            "codigo_snapshot",
            "nome_snapshot",
            "forma_venda_snapshot",
            "preco_referencia_centavos",
            "tipo_item",
            "origem",
            "origem_quantidade",
            "quantidade_decimal",
            "codigo_barras",
            "subtotal_centavos",
        }
        assert versao == schema.VERSAO_ESQUEMA
    finally:
        conexao.close()


def test_migracao_da_versao_1_preserva_produto_e_venda(tmp_path) -> None:
    caminho_banco = tmp_path / "versao_1.db"
    produto_id, venda_id = _criar_banco_versao_1(caminho_banco)

    criar_tabelas(caminho_banco)

    conexao = conectar(caminho_banco)
    try:
        produto = conexao.execute(
            "SELECT codigo, nome FROM produtos WHERE id = ?",
            (produto_id,),
        ).fetchone()
        venda = conexao.execute(
            "SELECT total_centavos FROM vendas WHERE id = ?",
            (venda_id,),
        ).fetchone()
        tabela_itens = conexao.execute(
            "SELECT name FROM sqlite_master WHERE name = 'itens_venda'"
        ).fetchone()
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]

        assert tuple(produto) == ("234", "Picanha")
        assert venda["total_centavos"] == 10000
        assert tabela_itens["name"] == "itens_venda"
        assert versao == schema.VERSAO_ESQUEMA
    finally:
        conexao.close()


def test_conexao_habilita_integridade_referencial(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        foreign_keys = conexao.execute("PRAGMA foreign_keys").fetchone()[0]

        assert foreign_keys == 1
    finally:
        conexao.close()


def test_item_exige_venda_existente(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            _inserir_item_produto(conexao, venda_id=999)
    finally:
        conexao.close()


def test_produto_opcional_precisa_existir_quando_informado(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            _inserir_item_produto(
                conexao,
                venda_id,
                produto_id=999,
            )
    finally:
        conexao.close()


def test_venda_e_produto_referenciados_nao_podem_ser_excluidos(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)

    try:
        produto_id = _inserir_produto(conexao)
        venda_id = _inserir_venda(conexao)
        _inserir_item_produto(
            conexao,
            venda_id,
            produto_id=produto_id,
        )

        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conexao.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))

        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conexao.execute("DELETE FROM vendas WHERE id = ?", (venda_id,))
    finally:
        conexao.close()


def test_posicao_nao_pode_repetir_na_mesma_venda(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)
        _inserir_item_produto(conexao, venda_id, posicao=0)

        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            _inserir_item_produto(conexao, venda_id, posicao=0)
    finally:
        conexao.close()


def test_mesma_posicao_e_permitida_em_vendas_diferentes(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        primeira_venda = _inserir_venda(conexao, 1000)
        segunda_venda = _inserir_venda(conexao, 2000)

        primeiro_item = _inserir_item_produto(
            conexao,
            primeira_venda,
            posicao=0,
        )
        segundo_item = _inserir_item_produto(
            conexao,
            segunda_venda,
            posicao=0,
        )

        assert primeiro_item != segundo_item
    finally:
        conexao.close()


def test_snapshot_permanece_apos_alteracao_do_produto(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        produto_id = _inserir_produto(conexao)
        venda_id = _inserir_venda(conexao)
        item_id = _inserir_item_produto(
            conexao,
            venda_id,
            produto_id=produto_id,
        )
        conexao.execute(
            """
            UPDATE produtos
            SET codigo = ?, nome = ?, forma_venda = ?, preco_venda_centavos = ?
            WHERE id = ?
            """,
            ("999", "Alcatra", "UNIDADE", 12345, produto_id),
        )
        item = conexao.execute(
            """
            SELECT
                codigo_snapshot,
                nome_snapshot,
                forma_venda_snapshot,
                preco_referencia_centavos
            FROM itens_venda
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

        assert tuple(item) == ("234", "Picanha", "PESO", 7990)
    finally:
        conexao.close()


def test_quantidade_decimal_preserva_representacao_exata(banco_teste) -> None:
    conexao = conectar(banco_teste)
    quantidade = "0.671714643300"

    try:
        venda_id = _inserir_venda(conexao)
        item_id = _inserir_item_produto(
            conexao,
            venda_id,
            quantidade_decimal=quantidade,
            origem_quantidade="ESTIMADA",
        )
        armazenada = conexao.execute(
            "SELECT quantidade_decimal FROM itens_venda WHERE id = ?",
            (item_id,),
        ).fetchone()[0]

        assert armazenada == quantidade
        assert Decimal(armazenada) == Decimal(quantidade)
    finally:
        conexao.close()


@pytest.mark.parametrize(
    "quantidade_invalida",
    ["", "0", "-1", ".5", "1.", "1..2", "1e3", "texto"],
)
def test_quantidade_decimal_rejeita_formato_invalido(
    banco_teste,
    quantidade_invalida,
) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                quantidade_decimal=quantidade_invalida,
            )
    finally:
        conexao.close()


def test_quantidade_e_origem_da_quantidade_permanecem_coerentes(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                quantidade_decimal=None,
                origem_quantidade="INFORMADA",
            )

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                quantidade_decimal="1",
                origem_quantidade="NAO_INFORMADA",
            )
    finally:
        conexao.close()


def test_aceita_itens_de_etiqueta_manual_diversos_e_legado(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)

    try:
        produto_id = _inserir_produto(conexao)
        venda_id = _inserir_venda(conexao)
        _inserir_item_produto(
            conexao,
            venda_id,
            posicao=0,
            produto_id=produto_id,
            origem="ETIQUETA",
            origem_quantidade="ESTIMADA",
            quantidade_decimal="0.671",
            codigo_barras="2023400053672",
            subtotal_centavos=5367,
        )
        _inserir_item_produto(
            conexao,
            venda_id,
            posicao=1,
            produto_id=None,
            origem="MANUAL",
            codigo_barras=None,
        )
        _inserir_item_produto(
            conexao,
            venda_id,
            posicao=2,
            produto_id=None,
            codigo_snapshot=None,
            nome_snapshot="Diversos",
            forma_venda_snapshot=None,
            preco_referencia_centavos=None,
            tipo_item="DIVERSOS",
            origem="MANUAL",
            origem_quantidade="NAO_INFORMADA",
            quantidade_decimal=None,
            codigo_barras=None,
            subtotal_centavos=500,
        )
        _inserir_item_produto(
            conexao,
            venda_id,
            posicao=3,
            produto_id=None,
            codigo_snapshot=None,
            nome_snapshot=None,
            forma_venda_snapshot=None,
            preco_referencia_centavos=None,
            tipo_item=None,
            origem="MANUAL",
            origem_quantidade="NAO_INFORMADA",
            quantidade_decimal=None,
            codigo_barras=None,
            subtotal_centavos=100,
        )
        itens = conexao.execute(
            """
            SELECT posicao, tipo_item, origem
            FROM itens_venda
            WHERE venda_id = ?
            ORDER BY posicao
            """,
            (venda_id,),
        ).fetchall()

        assert [tuple(item) for item in itens] == [
            (0, "PRODUTO", "ETIQUETA"),
            (1, "PRODUTO", "MANUAL"),
            (2, "DIVERSOS", "MANUAL"),
            (3, None, "MANUAL"),
        ]
    finally:
        conexao.close()


def test_diversos_nao_aceita_produto_ou_snapshot_de_produto(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)

    try:
        produto_id = _inserir_produto(conexao)
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                produto_id=produto_id,
                tipo_item="DIVERSOS",
            )

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                produto_id=None,
                tipo_item="DIVERSOS",
                nome_snapshot="Nome livre",
            )

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                produto_id=None,
                codigo_snapshot=None,
                tipo_item="DIVERSOS",
                nome_snapshot=None,
                forma_venda_snapshot=None,
                preco_referencia_centavos=None,
            )
    finally:
        conexao.close()


def test_etiqueta_exige_codigo_e_item_manual_o_rejeita(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                origem="ETIQUETA",
                codigo_barras=None,
            )

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                origem="MANUAL",
                codigo_barras="2023400053672",
            )
    finally:
        conexao.close()


def test_itens_repetidos_permanecem_independentes_e_ordenados(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)
        primeiro_id = _inserir_item_produto(conexao, venda_id, posicao=0)
        segundo_id = _inserir_item_produto(conexao, venda_id, posicao=1)
        itens = conexao.execute(
            """
            SELECT id, posicao, codigo_snapshot, subtotal_centavos
            FROM itens_venda
            WHERE venda_id = ?
            ORDER BY posicao
            """,
            (venda_id,),
        ).fetchall()

        assert [item["id"] for item in itens] == [primeiro_id, segundo_id]
        assert [item["posicao"] for item in itens] == [0, 1]
        assert itens[0]["codigo_snapshot"] == itens[1]["codigo_snapshot"]
        assert itens[0]["subtotal_centavos"] == itens[1]["subtotal_centavos"]
    finally:
        conexao.close()


@pytest.mark.parametrize(
    ("campo", "valor_invalido"),
    [
        ("posicao", -1),
        ("posicao", 1.5),
        ("subtotal_centavos", -1),
        ("subtotal_centavos", 1.5),
        ("tipo_item", "OUTRO"),
        ("origem", "OUTRA"),
        ("origem_quantidade", "OUTRA"),
        ("codigo_snapshot", None),
        ("nome_snapshot", None),
        ("forma_venda_snapshot", None),
        ("forma_venda_snapshot", "CAIXA"),
        ("preco_referencia_centavos", None),
        ("preco_referencia_centavos", 0),
    ],
)
def test_item_rejeita_valores_fora_do_contrato(
    banco_teste,
    campo,
    valor_invalido,
) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            _inserir_item_produto(
                conexao,
                venda_id,
                **{campo: valor_invalido},
            )
    finally:
        conexao.close()


def test_reexecutar_migracao_preserva_itens(banco_teste) -> None:
    conexao = conectar(banco_teste)

    try:
        venda_id = _inserir_venda(conexao)
        item_id = _inserir_item_produto(conexao, venda_id)
        conexao.commit()
    finally:
        conexao.close()

    criar_tabelas(banco_teste)
    criar_tabelas(banco_teste)

    conexao = conectar(banco_teste)
    try:
        item = conexao.execute(
            "SELECT id, subtotal_centavos FROM itens_venda"
        ).fetchone()

        assert tuple(item) == (item_id, 9988)
    finally:
        conexao.close()


def test_falha_na_migracao_2_preserva_versao_1_e_seus_dados(
    tmp_path,
    monkeypatch,
) -> None:
    caminho_banco = tmp_path / "falha_versao_2.db"
    produto_id, venda_id = _criar_banco_versao_1(caminho_banco)
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_ITENS_VENDA",
        "CREATE TABLE itens_venda (id INTEGER PRIMARY KEY,",
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
        itens = conexao.execute(
            "SELECT name FROM sqlite_master WHERE name = 'itens_venda'"
        ).fetchone()

        assert versao == 1
        assert produto["id"] == produto_id
        assert venda["id"] == venda_id
        assert itens is None
    finally:
        conexao.close()
