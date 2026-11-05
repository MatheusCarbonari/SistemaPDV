from decimal import Decimal

import pytest

from tests.helpers_identidade import criar_janela_autenticada
from models.item_venda import ItemVenda
from models.produto_snapshot import ProdutoSnapshot


@pytest.fixture
def janela(qtbot, tmp_path):
    janela_principal = criar_janela_autenticada(tmp_path / "venda_interface.db")
    qtbot.addWidget(janela_principal)
    janela_principal.show()
    qtbot.waitUntil(janela_principal.isVisible)
    qtbot.waitUntil(janela_principal.campo_entrada.hasFocus)
    return janela_principal


def criar_item_produto(
    nome="Produto",
    subtotal=1000,
    quantidade=Decimal("2"),
    origem_quantidade="INFORMADA",
    forma_venda="UNIDADE",
    preco=500,
):
    produto = ProdutoSnapshot(
        produto_id=1,
        codigo="10",
        nome=nome,
        forma_venda=forma_venda,
        preco_referencia_centavos=preco,
    )
    return ItemVenda(
        produto=produto,
        origem="MANUAL",
        subtotal_centavos=subtotal,
        codigo_barras=None,
        quantidade=quantidade,
        origem_quantidade=origem_quantidade,
    )


def criar_item_diversos(subtotal=250):
    return ItemVenda(
        produto=None,
        origem="MANUAL",
        subtotal_centavos=subtotal,
        codigo_barras=None,
        quantidade=None,
        origem_quantidade="NAO_INFORMADA",
        tipo_item="DIVERSOS",
    )


def descricoes_tabela(janela):
    return [
        janela.tabela_itens.item(linha, 0).text()
        for linha in range(janela.tabela_itens.rowCount())
    ]


def test_tabela_mantem_ordem_visual_sem_ordenacao(janela) -> None:
    cabecalhos = [
        janela.tabela_itens.horizontalHeaderItem(coluna).text()
        for coluna in range(janela.tabela_itens.columnCount())
    ]

    assert cabecalhos == [
        "Produto/descrição",
        "Quantidade ou peso",
        "Preço unitário ou preço/kg",
        "Subtotal",
    ]
    assert not janela.tabela_itens.isSortingEnabled()


def test_item_criado_inclui_linha_e_atualiza_total(janela) -> None:
    item = criar_item_produto(subtotal=1234)

    janela.item_criado.emit(item)

    assert janela.estado_venda.venda.itens == (item,)
    assert janela.tabela_itens.rowCount() == 1
    assert janela.tabela_itens.item(0, 0).text() == "Produto"
    assert janela.tabela_itens.item(0, 3).text() == "R$ 12,34"
    assert janela.rotulo_total.text() == "Total: R$ 12,34"


def test_itens_repetidos_permanecem_em_linhas_independentes(janela) -> None:
    item = criar_item_produto()

    janela.item_criado.emit(item)
    janela.item_criado.emit(item)

    assert janela.estado_venda.venda.itens == (item, item)
    assert janela.tabela_itens.rowCount() == 2
    assert janela.rotulo_total.text() == "Total: R$ 20,00"


def test_remover_linha_selecionada_preserva_correspondencia_do_indice(
    janela,
    qtbot,
) -> None:
    itens = tuple(
        criar_item_produto(nome=nome, subtotal=valor)
        for nome, valor in (("Primeiro", 100), ("Segundo", 200), ("Terceiro", 300))
    )
    for item in itens:
        janela.item_criado.emit(item)
    janela.tabela_itens.selectRow(1)

    janela.botao_remover.click()

    assert janela.estado_venda.venda.itens == (itens[0], itens[2])
    assert descricoes_tabela(janela) == ["Primeiro", "Terceiro"]
    assert janela.rotulo_total.text() == "Total: R$ 4,00"
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_remover_sem_selecao_remove_ultimo_item(janela) -> None:
    primeiro = criar_item_produto(nome="Primeiro")
    ultimo = criar_item_produto(nome="Último")
    janela.item_criado.emit(primeiro)
    janela.item_criado.emit(ultimo)
    janela.tabela_itens.clearSelection()

    janela.remover_item_selecionado()

    assert janela.estado_venda.venda.itens == (primeiro,)
    assert descricoes_tabela(janela) == ["Primeiro"]


def test_remover_venda_vazia_nao_altera_estado(janela, qtbot) -> None:
    estado_original = janela.estado_venda

    janela.remover_item_selecionado()

    assert janela.estado_venda is estado_original
    assert janela.tabela_itens.rowCount() == 0
    assert janela.rotulo_total.text() == "Total: R$ 0,00"
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_desfazer_restaura_posicao_original_apenas_uma_vez(
    janela,
    qtbot,
) -> None:
    itens = tuple(
        criar_item_produto(nome=nome)
        for nome in ("Primeiro", "Segundo", "Terceiro")
    )
    for item in itens:
        janela.item_criado.emit(item)
    janela.tabela_itens.selectRow(1)
    janela.remover_item_selecionado()

    janela.desfazer_ultima_remocao()
    estado_restaurado = janela.estado_venda
    janela.desfazer_ultima_remocao()

    assert janela.estado_venda is estado_restaurado
    assert janela.estado_venda.venda.itens == itens
    assert descricoes_tabela(janela) == ["Primeiro", "Segundo", "Terceiro"]
    assert not janela.botao_desfazer.isEnabled()
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_nova_inclusao_invalida_desfazer(janela) -> None:
    primeiro = criar_item_produto(nome="Primeiro")
    novo = criar_item_produto(nome="Novo")
    janela.item_criado.emit(primeiro)
    janela.remover_item_selecionado()

    janela.item_criado.emit(novo)
    janela.desfazer_ultima_remocao()

    assert janela.estado_venda.venda.itens == (novo,)
    assert janela.estado_venda.ultima_remocao is None


def test_exibe_diversos_e_item_legado_sem_inferir_tipo(janela) -> None:
    diversos = criar_item_diversos()
    legado = ItemVenda(
        produto=None,
        origem="MANUAL",
        subtotal_centavos=100,
        codigo_barras=None,
        quantidade=None,
        origem_quantidade="NAO_INFORMADA",
    )

    janela.item_criado.emit(diversos)
    janela.item_criado.emit(legado)

    assert descricoes_tabela(janela) == ["Diversos", "Item sem descrição"]
    assert janela.tabela_itens.item(0, 2).text() == "—"
    assert legado.tipo_item is None


def test_diferencia_quantidade_informada_e_estimada(janela) -> None:
    informado = criar_item_produto(quantidade=Decimal("2.000"))
    estimado = criar_item_produto(
        nome="Peso",
        quantidade=Decimal("0.896"),
        origem_quantidade="ESTIMADA",
        forma_venda="PESO",
        preco=5990,
    )

    janela.item_criado.emit(informado)
    janela.item_criado.emit(estimado)

    assert janela.tabela_itens.item(0, 1).text() == "2.000 un."
    assert janela.tabela_itens.item(1, 1).text() == "0.896 kg (estimada)"
    assert janela.tabela_itens.item(1, 2).text() == "R$ 59,90/kg"


def test_etiqueta_sem_estimativa_preserva_subtotal_e_nao_inventa_quantidade(
    janela,
) -> None:
    produto = ProdutoSnapshot(1, "234", "Picanha", "PESO", 0)
    etiqueta = ItemVenda(
        produto=produto,
        origem="ETIQUETA",
        subtotal_centavos=5367,
        codigo_barras="2023400053672",
        quantidade=None,
        origem_quantidade="NAO_INFORMADA",
    )

    janela.item_criado.emit(etiqueta)

    assert janela.tabela_itens.item(0, 1).text() == "Não informada"
    assert janela.tabela_itens.item(0, 3).text() == "R$ 53,67"
    assert janela.rotulo_total.text() == "Total: R$ 53,67"
