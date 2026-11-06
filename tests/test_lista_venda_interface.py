from decimal import Decimal

import pytest
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import QHeaderView, QLabel, QWidget

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


def _luminancia_relativa(cor: QColor) -> float:
    componentes = (cor.redF(), cor.greenF(), cor.blueF())
    linearizados = tuple(
        componente / 12.92
        if componente <= 0.04045
        else ((componente + 0.055) / 1.055) ** 2.4
        for componente in componentes
    )
    return (
        0.2126 * linearizados[0]
        + 0.7152 * linearizados[1]
        + 0.0722 * linearizados[2]
    )


def _contraste(cor_a: QColor, cor_b: QColor) -> float:
    mais_clara, mais_escura = sorted(
        (_luminancia_relativa(cor_a), _luminancia_relativa(cor_b)),
        reverse=True,
    )
    return (mais_clara + 0.05) / (mais_escura + 0.05)


def test_tabela_mantem_ordem_visual_sem_ordenacao(janela) -> None:
    cabecalhos = [
        janela.tabela_itens.horizontalHeaderItem(coluna).text()
        for coluna in range(janela.tabela_itens.columnCount())
    ]

    assert cabecalhos == [
        "Produto / descrição",
        "Quantidade / peso",
        "Preço unitário / kg",
        "Subtotal",
    ]
    assert not janela.tabela_itens.isSortingEnabled()


@pytest.mark.parametrize("largura,altura", [(900, 640), (1280, 800)])
def test_layout_preserva_leitura_e_cabecalhos_em_tamanhos_usuais(
    janela,
    qtbot,
    largura,
    altura,
) -> None:
    janela.resize(largura, altura)
    qtbot.wait(20)

    assert janela.campo_entrada.width() <= 520
    assert janela.campo_entrada.width() < janela.tabela_itens.width()
    assert janela.rotulo_status.geometry().left() > (
        janela.campo_entrada.geometry().right()
    )
    assert abs(
        janela.rotulo_status.geometry().center().y()
        - janela.campo_entrada.geometry().center().y()
    ) <= 2
    assert janela.rotulo_status.width() >= 300

    cabecalho = janela.tabela_itens.horizontalHeader()
    assert cabecalho.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert cabecalho.sectionResizeMode(1) == QHeaderView.ResizeMode.Fixed
    assert cabecalho.sectionResizeMode(2) == QHeaderView.ResizeMode.Fixed
    assert cabecalho.sectionResizeMode(3) == QHeaderView.ResizeMode.Fixed

    for coluna in range(janela.tabela_itens.columnCount()):
        texto = janela.tabela_itens.horizontalHeaderItem(coluna).text()
        largura_texto = cabecalho.fontMetrics().horizontalAdvance(texto) + 24
        assert janela.tabela_itens.columnWidth(coluna) >= largura_texto

    for botao in (
        janela.botao_remover,
        janela.botao_desfazer,
        janela.botao_verificar_fechamento,
        janela.botao_pagamento,
        janela.botao_confirmar_venda,
    ):
        assert botao.width() >= botao.sizeHint().width()


def test_retorno_visual_distingue_erro_e_item_confirmado(janela) -> None:
    janela._concluir_com_erro(["Código não encontrado."])

    assert janela.rotulo_status.text() == "Código não encontrado."
    assert janela.rotulo_status.property("tipoStatus") == "erro"

    janela._emitir_item(criar_item_produto())

    assert janela.rotulo_status.text() == "Item confirmado."
    assert janela.rotulo_status.property("tipoStatus") == "sucesso"


def test_total_e_acoes_principais_possuem_hierarquia_visual(janela) -> None:
    assert janela.rotulo_total.fontMetrics().height() > (
        janela.rotulo_status.fontMetrics().height()
    )
    assert janela.botao_pagamento.property("papelAcao") == "comercial"
    assert janela.botao_confirmar_venda.property("papelAcao") == "principal"
    assert janela.botao_verificar_fechamento.property("papelAcao") == "alerta"


def test_frente_caixa_remove_titulo_interno_duplicado(janela) -> None:
    assert janela.pagina_frente_caixa.findChild(
        QLabel,
        "titulo_area_vendas",
    ) is None


def test_barra_superior_compartilha_fundo_e_estilo_visual(
    janela,
    qtbot,
) -> None:
    menu = janela.findChild(QWidget, "menu_superior")

    assert menu is not None
    assert menu.palette().color(QPalette.ColorRole.Window).name() == "#171a1f"
    assert (
        janela.pagina_frente_caixa.palette()
        .color(QPalette.ColorRole.Window)
        .name()
        == "#171a1f"
    )
    assert "QPushButton:checked" in menu.styleSheet()
    assert "QPushButton:hover:enabled" in menu.styleSheet()
    assert "QPushButton:disabled" in menu.styleSheet()
    assert "#2474a6" in menu.styleSheet()
    assert janela.botao_navegar_caixa.isChecked()

    botoes_navegacao = (
        janela.botao_navegar_caixa,
        janela.botao_navegar_historico,
        janela.botao_navegar_produtos,
        janela.botao_navegar_administracao,
    )
    for botao in botoes_navegacao:
        fonte_selecionada = botao.font()
        fonte_selecionada.setBold(True)
        largura_selecionada = QFontMetrics(
            fonte_selecionada
        ).horizontalAdvance(botao.text())
        tamanho_inicial = botao.size()

        assert botao.minimumWidth() >= largura_selecionada + 40
        assert botao.minimumHeight() >= 44
        assert botao.width() >= botao.minimumWidth()

        botao.setChecked(True)
        qtbot.wait(5)
        assert botao.size() == tamanho_inicial

        botao.setEnabled(False)
        qtbot.wait(5)
        assert botao.size() == tamanho_inicial
        botao.setEnabled(True)

    janela.botao_navegar_caixa.setChecked(True)

    for botao in (
        *botoes_navegacao,
        janela.botao_codigos_recuperacao,
        janela.botao_logout,
    ):
        assert botao.height() >= 34
        assert botao.width() >= botao.sizeHint().width()


def test_paleta_da_tabela_e_do_leitor_tem_contraste_explicito(janela) -> None:
    paleta_tabela = janela.tabela_itens.palette()
    assert _contraste(
        paleta_tabela.color(QPalette.ColorRole.Text),
        paleta_tabela.color(QPalette.ColorRole.Base),
    ) >= 4.5
    assert _contraste(
        paleta_tabela.color(QPalette.ColorRole.Text),
        paleta_tabela.color(QPalette.ColorRole.AlternateBase),
    ) >= 4.5
    assert _contraste(
        paleta_tabela.color(QPalette.ColorRole.HighlightedText),
        paleta_tabela.color(QPalette.ColorRole.Highlight),
    ) >= 4.5

    paleta_entrada = janela.campo_entrada.palette()
    assert _contraste(
        paleta_entrada.color(QPalette.ColorRole.Text),
        paleta_entrada.color(QPalette.ColorRole.Base),
    ) >= 4.5
    assert _contraste(
        paleta_entrada.color(QPalette.ColorRole.PlaceholderText),
        paleta_entrada.color(QPalette.ColorRole.Base),
    ) >= 4.5


def test_varias_linhas_e_selecao_permanecem_visiveis(janela, qtbot) -> None:
    itens = (
        criar_item_produto(nome="Produto principal", subtotal=1234),
        criar_item_produto(nome="Produto alternado", subtotal=5678),
        criar_item_produto(nome="Produto selecionado", subtotal=9012),
    )
    for item in itens:
        janela.item_criado.emit(item)

    janela.tabela_itens.selectRow(2)
    qtbot.wait(20)

    assert janela.tabela_itens.rowCount() == 3
    assert not any(janela.tabela_itens.isRowHidden(linha) for linha in range(3))
    assert janela.tabela_itens.selectionModel().selectedRows()[0].row() == 2
    for linha, item in enumerate(itens):
        celula = janela.tabela_itens.item(linha, 0)
        assert celula.text() == item.produto.nome
        assert janela.tabela_itens.visualItemRect(celula).height() > 0


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
