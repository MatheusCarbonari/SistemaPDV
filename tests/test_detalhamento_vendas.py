from datetime import UTC, datetime
from decimal import Decimal

import pytest

from database.conexao import conectar
from database.schema import criar_tabelas
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_detalhada import VendaDetalhada
from models.venda_em_andamento import VendaEmAndamento
from services.confirmacao_venda_service import confirmar_venda
from services.historico_venda_service import buscar_venda_detalhada_por_id
from services.persistencia_venda_service import (
    gerar_identificador_tentativa,
    persistir_venda_confirmada,
    persistir_venda_confirmada_idempotente,
)


@pytest.fixture
def banco_teste(tmp_path):
    caminho = tmp_path / "detalhamento_vendas.db"
    criar_tabelas(caminho)
    return caminho


def inserir_produto_atual(banco_teste) -> int:
    conexao = conectar(banco_teste)
    try:
        produto_id = conexao.execute(
            """
            INSERT INTO produtos (
                codigo, nome, categoria, forma_venda,
                preco_venda_centavos, origem
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "ATUAL",
                "Cadastro atual",
                "TESTE",
                "UNIDADE",
                9999,
                "COMPRADO",
            ),
        ).lastrowid
        conexao.commit()
        return produto_id
    finally:
        conexao.close()


def criar_item_produto(
    subtotal_centavos: int,
    *,
    produto_id=None,
    codigo="SNAP",
    nome="Produto histórico",
    forma_venda="UNIDADE",
    preco_centavos=1234,
    quantidade=Decimal("1"),
    origem="MANUAL",
    origem_quantidade="INFORMADA",
    codigo_barras=None,
) -> ItemVenda:
    return ItemVenda(
        origem=origem,
        subtotal_centavos=subtotal_centavos,
        origem_quantidade=origem_quantidade,
        produto=ProdutoSnapshot(
            produto_id=produto_id,
            codigo=codigo,
            nome=nome,
            forma_venda=forma_venda,
            preco_referencia_centavos=preco_centavos,
        ),
        codigo_barras=codigo_barras,
        quantidade=quantidade,
    )


def criar_item_sem_produto(
    subtotal_centavos: int,
    tipo_item,
) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
        tipo_item=tipo_item,
    )


def criar_confirmacao(
    itens: tuple[ItemVenda, ...],
    pagamentos: tuple[Pagamento, ...],
):
    total = sum(item.subtotal_centavos for item in itens)
    return confirmar_venda(
        VendaEmAndamento(itens=itens),
        PagamentosEmAndamento(
            total_venda_centavos=total,
            pagamentos=pagamentos,
        ),
    )


@pytest.fixture
def venda_rica(banco_teste):
    produto_id = inserir_produto_atual(banco_teste)
    etiqueta = criar_item_produto(
        5367,
        produto_id=produto_id,
        codigo="234",
        nome="Picanha vendida",
        forma_venda="PESO",
        preco_centavos=7990,
        quantidade=Decimal("0.671714643300"),
        origem="ETIQUETA",
        origem_quantidade="ESTIMADA",
        codigo_barras="2023400053672",
    )
    manual_sem_fk = criar_item_produto(
        1000,
        produto_id=None,
        codigo="SEM-FK",
        nome="Produto sem vínculo",
        preco_centavos=400,
        quantidade=Decimal("2.500"),
        origem_quantidade="INFORMADA",
    )
    diversos = criar_item_sem_produto(500, "DIVERSOS")
    legado = criar_item_sem_produto(100, None)
    itens = (
        etiqueta,
        etiqueta,
        manual_sem_fk,
        diversos,
        legado,
    )
    pagamentos = (
        Pagamento("PIX", 4000),
        Pagamento("PIX", 3334),
        Pagamento("DINHEIRO", 5000),
    )
    confirmacao = criar_confirmacao(itens, pagamentos)
    venda_id = persistir_venda_confirmada(confirmacao, banco_teste)

    conexao = conectar(banco_teste)
    try:
        conexao.execute(
            """
            UPDATE produtos
            SET codigo = ?, nome = ?, preco_venda_centavos = ?
            WHERE id = ?
            """,
            ("NOVO", "Cadastro alterado", 15000, produto_id),
        )
        conexao.commit()
    finally:
        conexao.close()

    return {
        "venda_id": venda_id,
        "produto_id": produto_id,
        "confirmacao": confirmacao,
    }


def contar_registros(banco_teste) -> tuple[int, int, int, int]:
    conexao = conectar(banco_teste)
    try:
        return tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in (
                "produtos",
                "vendas",
                "itens_venda",
                "pagamentos",
            )
        )
    finally:
        conexao.close()


def test_venda_existente_retorna_cabecalho_itens_e_pagamentos(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )

    assert isinstance(detalhe, VendaDetalhada)
    assert detalhe.venda_id == venda_rica["venda_id"]
    assert detalhe.total_centavos == 12334
    assert detalhe.registrada_em.tzinfo is UTC
    assert len(detalhe.itens) == 5
    assert len(detalhe.pagamentos) == 3


def test_id_inexistente_retorna_none(banco_teste) -> None:
    assert buscar_venda_detalhada_por_id(999999, banco_teste) is None


@pytest.mark.parametrize(
    "venda_id",
    [None, True, False, "1", 1.0, 0, -1],
)
def test_rejeita_identificador_invalido(banco_teste, venda_id) -> None:
    erro = (
        TypeError
        if not isinstance(venda_id, int) or isinstance(venda_id, bool)
        else ValueError
    )
    with pytest.raises(erro):
        buscar_venda_detalhada_por_id(venda_id, banco_teste)


def test_preserva_ordem_e_itens_repetidos_independentes(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )

    assert [item.posicao for item in detalhe.itens] == [0, 1, 2, 3, 4]
    assert detalhe.itens[0].item == detalhe.itens[1].item
    assert detalhe.itens[0] is not detalhe.itens[1]
    assert detalhe.itens[0].item is not detalhe.itens[1].item


def test_preserva_snapshot_apos_alteracao_do_cadastro(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )
    snapshot = detalhe.itens[0].item.produto

    assert snapshot.produto_id == venda_rica["produto_id"]
    assert snapshot.codigo == "234"
    assert snapshot.nome == "Picanha vendida"
    assert snapshot.forma_venda == "PESO"
    assert snapshot.preco_referencia_centavos == 7990


def test_preserva_quantidades_exatas_ausentes_e_suas_origens(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )

    assert detalhe.itens[0].item.quantidade == Decimal("0.671714643300")
    assert format(detalhe.itens[0].item.quantidade, "f") == "0.671714643300"
    assert detalhe.itens[0].item.origem_quantidade == "ESTIMADA"
    assert detalhe.itens[2].item.quantidade == Decimal("2.500")
    assert format(detalhe.itens[2].item.quantidade, "f") == "2.500"
    assert detalhe.itens[2].item.origem_quantidade == "INFORMADA"
    assert detalhe.itens[3].item.quantidade is None
    assert detalhe.itens[3].item.origem_quantidade == "NAO_INFORMADA"
    assert detalhe.itens[4].item.quantidade is None


def test_preserva_diversos_legado_e_produto_sem_fk(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )
    produto_sem_fk = detalhe.itens[2].item
    diversos = detalhe.itens[3].item
    legado = detalhe.itens[4].item

    assert produto_sem_fk.tipo_item == "PRODUTO"
    assert produto_sem_fk.produto.produto_id is None
    assert diversos.tipo_item == "DIVERSOS"
    assert diversos.produto is None
    assert legado.tipo_item is None
    assert legado.produto is None


def test_etiqueta_preserva_codigo_origem_e_subtotal_sem_recalcular(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )
    etiqueta = detalhe.itens[0].item

    assert etiqueta.origem == "ETIQUETA"
    assert etiqueta.codigo_barras == "2023400053672"
    assert etiqueta.subtotal_centavos == 5367
    assert (
        etiqueta.quantidade * etiqueta.produto.preco_referencia_centavos
        != Decimal(etiqueta.subtotal_centavos)
    )


def test_preserva_ordem_e_modalidades_repetidas_dos_pagamentos(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )

    assert detalhe.pagamentos == (
        Pagamento("PIX", 4000),
        Pagamento("PIX", 3334),
        Pagamento("DINHEIRO", 5000),
    )


def test_multiplos_itens_e_pagamentos_nao_multiplicam_linhas(
    banco_teste,
    venda_rica,
) -> None:
    detalhe = buscar_venda_detalhada_por_id(
        venda_rica["venda_id"],
        banco_teste,
    )

    assert len(detalhe.itens) == 5
    assert len(detalhe.pagamentos) == 3
    assert [item.posicao for item in detalhe.itens] == list(range(5))


def test_consulta_vendas_persistidas_pelos_servicos_t39_e_t40(
    banco_teste,
) -> None:
    confirmacao_t39 = criar_confirmacao(
        (criar_item_produto(700),),
        (Pagamento("DINHEIRO", 700),),
    )
    confirmacao_t40 = criar_confirmacao(
        (criar_item_produto(900),),
        (Pagamento("DEBITO", 900),),
    )
    venda_t39 = persistir_venda_confirmada(confirmacao_t39, banco_teste)
    venda_t40 = persistir_venda_confirmada_idempotente(
        confirmacao_t40,
        gerar_identificador_tentativa(),
        banco_teste,
    )

    detalhe_t39 = buscar_venda_detalhada_por_id(venda_t39, banco_teste)
    detalhe_t40 = buscar_venda_detalhada_por_id(venda_t40, banco_teste)

    assert detalhe_t39.total_centavos == 700
    assert detalhe_t39.pagamentos == (Pagamento("DINHEIRO", 700),)
    assert detalhe_t40.total_centavos == 900
    assert detalhe_t40.pagamentos == (Pagamento("DEBITO", 900),)


def test_consulta_nao_altera_o_banco(
    banco_teste,
    venda_rica,
) -> None:
    antes = contar_registros(banco_teste)

    buscar_venda_detalhada_por_id(venda_rica["venda_id"], banco_teste)

    assert contar_registros(banco_teste) == antes


def test_retorna_total_registrado_sem_recomputar_colecoes(
    banco_teste,
) -> None:
    conexao = conectar(banco_teste)
    try:
        venda_id = conexao.execute(
            "INSERT INTO vendas (total_centavos) VALUES (1000)"
        ).lastrowid
        conexao.execute(
            """
            INSERT INTO itens_venda (
                venda_id, posicao, produto_id, codigo_snapshot,
                nome_snapshot, forma_venda_snapshot,
                preco_referencia_centavos, tipo_item, origem,
                origem_quantidade, quantidade_decimal, codigo_barras,
                subtotal_centavos
            )
            VALUES (?, 0, NULL, NULL, NULL, NULL, NULL, NULL,
                    'MANUAL', 'NAO_INFORMADA', NULL, NULL, 900)
            """,
            (venda_id,),
        )
        conexao.execute(
            """
            INSERT INTO pagamentos (venda_id, modalidade, valor_centavos)
            VALUES (?, 'PIX', 800)
            """,
            (venda_id,),
        )
        conexao.commit()
    finally:
        conexao.close()

    detalhe = buscar_venda_detalhada_por_id(venda_id, banco_teste)

    assert detalhe.total_centavos == 1000
    assert detalhe.itens[0].item.subtotal_centavos == 900
    assert detalhe.pagamentos[0].valor_centavos == 800
    assert detalhe.registrada_em == detalhe.registrada_em.astimezone(UTC)
