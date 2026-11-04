from datetime import UTC, date, datetime
from decimal import Decimal
import sqlite3

import pytest

from database.conexao import conectar
import database.schema as schema
from database.schema import criar_tabelas
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_em_andamento import VendaEmAndamento
from services.confirmacao_venda_service import confirmar_venda
from services.historico_venda_service import (
    FUSO_SAO_PAULO,
    buscar_venda_resumida_por_id,
    listar_vendas_resumidas_por_data,
)
from services.persistencia_venda_service import (
    gerar_identificador_tentativa,
    persistir_venda_confirmada,
    persistir_venda_confirmada_idempotente,
)


@pytest.fixture
def banco_teste(tmp_path):
    caminho = tmp_path / "historico_vendas.db"
    criar_tabelas(caminho)
    return caminho


def inserir_venda(
    caminho_banco,
    total_centavos: int,
    registrada_em: str,
) -> int:
    conexao = conectar(caminho_banco)
    try:
        venda_id = conexao.execute(
            """
            INSERT INTO vendas (total_centavos, registrada_em)
            VALUES (?, ?)
            """,
            (total_centavos, registrada_em),
        ).lastrowid
        conexao.commit()
        return venda_id
    finally:
        conexao.close()


def criar_confirmacao(total_centavos=1000):
    snapshot = ProdutoSnapshot(
        produto_id=None,
        codigo="HIST",
        nome="Produto histórico",
        forma_venda="UNIDADE",
        preco_referencia_centavos=total_centavos,
    )
    item = ItemVenda(
        origem="MANUAL",
        subtotal_centavos=total_centavos,
        origem_quantidade="INFORMADA",
        produto=snapshot,
        quantidade=Decimal("1"),
    )
    venda = VendaEmAndamento(itens=(item,))
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=total_centavos,
        pagamentos=(Pagamento("PIX", total_centavos),),
    )
    return confirmar_venda(venda, pagamentos)


def contagens(caminho_banco) -> tuple[int, int, int]:
    conexao = conectar(caminho_banco)
    try:
        return tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("vendas", "itens_venda", "pagamentos")
        )
    finally:
        conexao.close()


def preparar_banco_versao_4(caminho_banco) -> int:
    conexao = conectar(caminho_banco)
    try:
        conexao.execute("BEGIN IMMEDIATE")
        conexao.execute(schema._COMANDO_CRIAR_PRODUTOS)
        conexao.execute(schema._COMANDO_CRIAR_VENDAS)
        conexao.execute(schema._COMANDO_CRIAR_ITENS_VENDA)
        conexao.execute(schema._COMANDO_CRIAR_PAGAMENTOS)
        conexao.execute(schema._COMANDO_ADICIONAR_IDENTIFICADOR_TENTATIVA)
        conexao.execute(schema._COMANDO_CRIAR_INDICE_TENTATIVA)
        venda_id = conexao.execute(
            """
            INSERT INTO vendas (total_centavos, registrada_em)
            VALUES (1234, '2026-11-04 12:00:00')
            """
        ).lastrowid
        conexao.execute("PRAGMA user_version = 4")
        conexao.commit()
        return venda_id
    finally:
        conexao.close()


def test_busca_por_id_existente_retorna_resumo_utc(banco_teste) -> None:
    venda_id = inserir_venda(
        banco_teste,
        1234,
        "2026-11-04 15:30:00",
    )

    resumo = buscar_venda_resumida_por_id(venda_id, banco_teste)

    assert resumo is not None
    assert resumo.venda_id == venda_id
    assert resumo.total_centavos == 1234
    assert resumo.registrada_em == datetime(
        2026,
        11,
        4,
        15,
        30,
        tzinfo=UTC,
    )


def test_busca_por_id_inexistente_retorna_none(banco_teste) -> None:
    assert buscar_venda_resumida_por_id(999999, banco_teste) is None


@pytest.mark.parametrize(
    "venda_id",
    [None, True, False, "1", 1.0, 0, -1],
)
def test_busca_rejeita_identificador_invalido(
    banco_teste,
    venda_id,
) -> None:
    erro = (
        TypeError
        if not isinstance(venda_id, int) or isinstance(venda_id, bool)
        else ValueError
    )
    with pytest.raises(erro):
        buscar_venda_resumida_por_id(venda_id, banco_teste)


def test_lista_dia_com_multiplas_vendas_e_dia_sem_movimento(
    banco_teste,
) -> None:
    ids = [
        inserir_venda(banco_teste, 100, "2026-11-04 10:00:00"),
        inserir_venda(banco_teste, 200, "2026-11-04 20:00:00"),
    ]

    vendas = listar_vendas_resumidas_por_data(
        date(2026, 11, 4),
        banco_teste,
    )
    sem_movimento = listar_vendas_resumidas_por_data(
        date(2026, 11, 10),
        banco_teste,
    )

    assert {venda.venda_id for venda in vendas} == set(ids)
    assert sem_movimento == ()


@pytest.mark.parametrize(
    "data_invalida",
    [None, "2026-11-04", datetime(2026, 11, 4), 20261104],
)
def test_lista_rejeita_data_invalida(banco_teste, data_invalida) -> None:
    with pytest.raises(TypeError):
        listar_vendas_resumidas_por_data(data_invalida, banco_teste)


def test_lista_uma_linha_por_venda_com_varios_itens_e_pagamentos(
    banco_teste,
) -> None:
    venda_id = inserir_venda(
        banco_teste,
        1000,
        "2026-11-04 12:00:00",
    )
    conexao = conectar(banco_teste)
    try:
        for posicao, subtotal in enumerate((400, 600)):
            conexao.execute(
                """
                INSERT INTO itens_venda (
                    venda_id, posicao, produto_id, codigo_snapshot,
                    nome_snapshot, forma_venda_snapshot,
                    preco_referencia_centavos, tipo_item, origem,
                    origem_quantidade, quantidade_decimal, codigo_barras,
                    subtotal_centavos
                )
                VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, NULL,
                        'MANUAL', 'NAO_INFORMADA', NULL, NULL, ?)
                """,
                (venda_id, posicao, subtotal),
            )
        for modalidade, valor in (("PIX", 400), ("DINHEIRO", 600)):
            conexao.execute(
                """
                INSERT INTO pagamentos (venda_id, modalidade, valor_centavos)
                VALUES (?, ?, ?)
                """,
                (venda_id, modalidade, valor),
            )
        conexao.commit()
    finally:
        conexao.close()

    vendas = listar_vendas_resumidas_por_data(
        date(2026, 11, 4),
        banco_teste,
    )

    assert len(vendas) == 1
    assert vendas[0].venda_id == venda_id
    assert vendas[0].total_centavos == 1000


def test_ordena_por_data_descendente_e_id_como_desempate(
    banco_teste,
) -> None:
    antigo = inserir_venda(banco_teste, 100, "2026-11-04 10:00:00")
    mesmo_horario_primeiro = inserir_venda(
        banco_teste,
        200,
        "2026-11-04 12:00:00",
    )
    mesmo_horario_segundo = inserir_venda(
        banco_teste,
        300,
        "2026-11-04 12:00:00",
    )

    vendas = listar_vendas_resumidas_por_data(
        date(2026, 11, 4),
        banco_teste,
    )

    assert [venda.venda_id for venda in vendas] == [
        mesmo_horario_segundo,
        mesmo_horario_primeiro,
        antigo,
    ]


def test_converte_dia_de_sao_paulo_para_intervalo_utc_semiaberto(
    banco_teste,
) -> None:
    anterior = inserir_venda(
        banco_teste,
        100,
        "2026-11-04 02:59:59",
    )
    inicio = inserir_venda(
        banco_teste,
        200,
        "2026-11-04 03:00:00",
    )
    fim_incluso = inserir_venda(
        banco_teste,
        300,
        "2026-11-05 02:59:59",
    )
    proximo = inserir_venda(
        banco_teste,
        400,
        "2026-11-05 03:00:00",
    )

    vendas = listar_vendas_resumidas_por_data(
        date(2026, 11, 4),
        banco_teste,
    )

    assert [venda.venda_id for venda in vendas] == [fim_incluso, inicio]
    assert anterior not in {venda.venda_id for venda in vendas}
    assert proximo not in {venda.venda_id for venda in vendas}


def test_preserva_totais_exatos_em_centavos(banco_teste) -> None:
    valores = (1, 1234, 99999999)
    for valor in valores:
        inserir_venda(banco_teste, valor, "2026-11-04 12:00:00")

    vendas = listar_vendas_resumidas_por_data(
        date(2026, 11, 4),
        banco_teste,
    )

    assert sorted(venda.total_centavos for venda in vendas) == list(valores)


def test_consultas_nao_alteram_dados(banco_teste) -> None:
    venda_id = persistir_venda_confirmada(
        criar_confirmacao(),
        banco_teste,
    )
    antes = contagens(banco_teste)
    resumo = buscar_venda_resumida_por_id(venda_id, banco_teste)
    data_local = resumo.registrada_em.astimezone(FUSO_SAO_PAULO).date()

    listar_vendas_resumidas_por_data(data_local, banco_teste)

    assert contagens(banco_teste) == antes


def test_funciona_com_vendas_dos_servicos_t39_e_t40(banco_teste) -> None:
    venda_t39 = persistir_venda_confirmada(
        criar_confirmacao(700),
        banco_teste,
    )
    venda_t40 = persistir_venda_confirmada_idempotente(
        criar_confirmacao(900),
        gerar_identificador_tentativa(),
        banco_teste,
    )
    resumo_t39 = buscar_venda_resumida_por_id(venda_t39, banco_teste)
    resumo_t40 = buscar_venda_resumida_por_id(venda_t40, banco_teste)
    data_local = resumo_t39.registrada_em.astimezone(FUSO_SAO_PAULO).date()

    vendas = listar_vendas_resumidas_por_data(data_local, banco_teste)

    assert resumo_t39.total_centavos == 700
    assert resumo_t40.total_centavos == 900
    assert {venda.venda_id for venda in vendas} >= {venda_t39, venda_t40}


def test_migra_versao_4_para_5_preservando_registros(tmp_path) -> None:
    caminho = tmp_path / "migracao_v4_v5.db"
    venda_id = preparar_banco_versao_4(caminho)

    criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        venda = conexao.execute(
            "SELECT id, total_centavos FROM vendas"
        ).fetchone()
        indices = {
            linha["name"]
            for linha in conexao.execute("PRAGMA index_list(vendas)").fetchall()
        }
        assert versao == 5
        assert tuple(venda) == (venda_id, 1234)
        assert "ux_vendas_identificador_tentativa" in indices
        assert "ix_vendas_registrada_em_id" in indices
    finally:
        conexao.close()


def test_consulta_por_data_utiliza_indice_composto(banco_teste) -> None:
    conexao = conectar(banco_teste)
    try:
        plano = conexao.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT id, total_centavos, registrada_em
            FROM vendas
            WHERE registrada_em >= ? AND registrada_em < ?
            ORDER BY registrada_em DESC, id DESC
            """,
            ("2026-11-04 03:00:00", "2026-11-05 03:00:00"),
        ).fetchall()
    finally:
        conexao.close()

    detalhes = " ".join(linha["detail"] for linha in plano)
    assert "ix_vendas_registrada_em_id" in detalhes


def test_falha_na_migracao_5_preserva_versao_4_e_dados(
    tmp_path,
    monkeypatch,
) -> None:
    caminho = tmp_path / "falha_migracao_v5.db"
    venda_id = preparar_banco_versao_4(caminho)
    monkeypatch.setattr(
        schema,
        "_COMANDO_CRIAR_INDICE_HISTORICO_VENDAS",
        "CREATE INDEX indice_incompleto ON vendas (",
    )

    with pytest.raises(sqlite3.OperationalError):
        criar_tabelas(caminho)

    conexao = conectar(caminho)
    try:
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        venda = conexao.execute(
            "SELECT id, total_centavos FROM vendas"
        ).fetchone()
        indices = {
            linha["name"]
            for linha in conexao.execute("PRAGMA index_list(vendas)").fetchall()
        }
        assert versao == 4
        assert tuple(venda) == (venda_id, 1234)
        assert "ix_vendas_registrada_em_id" not in indices
    finally:
        conexao.close()
