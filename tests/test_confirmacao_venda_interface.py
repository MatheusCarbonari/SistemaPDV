import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from database.schema import criar_tabelas
from interface.dialogo_confirmacao_venda import DialogoConfirmacaoVenda
from interface.dialogo_pagamentos import DialogoPagamentos
from tests.helpers_identidade import criar_janela_autenticada
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.venda_em_andamento import VendaEmAndamento


def criar_item(subtotal_centavos: int) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
    )


def criar_pagamentos(total_centavos: int) -> PagamentosEmAndamento:
    return PagamentosEmAndamento(
        total_venda_centavos=total_centavos,
        pagamentos=(Pagamento("PIX", total_centavos),),
    )


@pytest.fixture
def venda_e_pagamentos():
    venda = VendaEmAndamento(itens=(criar_item(1000),))
    return venda, criar_pagamentos(1000)


@pytest.fixture
def janela(qtbot, tmp_path):
    janela_principal = criar_janela_autenticada(tmp_path / "t38.db")
    qtbot.addWidget(janela_principal)
    janela_principal.show()
    qtbot.waitUntil(janela_principal.isVisible)
    qtbot.waitUntil(janela_principal.campo_entrada.hasFocus)
    return janela_principal


def registrar_composicao(
    janela: JanelaPrincipal,
    total_centavos: int,
) -> PagamentosEmAndamento:
    pagamentos = criar_pagamentos(total_centavos)
    janela._emitir_pagamentos_confirmados(pagamentos)
    return pagamentos


def test_enter_confirma_dialogo_e_apresenta_resumo(
    qtbot,
    venda_e_pagamentos,
) -> None:
    venda, pagamentos = venda_e_pagamentos
    dialogo = DialogoConfirmacaoVenda(venda, pagamentos)
    qtbot.addWidget(dialogo)
    resultados = []
    dialogo.venda_confirmada.connect(resultados.append)
    dialogo.show()
    qtbot.waitUntil(dialogo.isVisible)

    assert dialogo.rotulo_total.text() == "R$ 10,00"
    assert dialogo.tabela_pagamentos.rowCount() == 1
    assert dialogo.tabela_pagamentos.item(0, 0).text() == "PIX"
    assert dialogo.tabela_pagamentos.item(0, 1).text() == "R$ 10,00"

    qtbot.keyPress(dialogo, Qt.Key.Key_Return)

    qtbot.waitUntil(lambda: not dialogo.isVisible())
    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert len(resultados) == 1
    assert resultados[0].venda is venda
    assert resultados[0].pagamentos is pagamentos


def test_escape_cancela_dialogo_sem_emitir_confirmacao(
    qtbot,
    venda_e_pagamentos,
) -> None:
    venda, pagamentos = venda_e_pagamentos
    dialogo = DialogoConfirmacaoVenda(venda, pagamentos)
    qtbot.addWidget(dialogo)
    resultados = []
    dialogo.venda_confirmada.connect(resultados.append)
    dialogo.show()
    qtbot.waitUntil(dialogo.isVisible)

    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)

    qtbot.waitUntil(lambda: not dialogo.isVisible())
    assert dialogo.result() == QDialog.DialogCode.Rejected
    assert resultados == []


def test_confirmacao_nao_emite_resultado_duplicado(
    qtbot,
    venda_e_pagamentos,
) -> None:
    venda, pagamentos = venda_e_pagamentos
    dialogo = DialogoConfirmacaoVenda(venda, pagamentos)
    qtbot.addWidget(dialogo)
    resultados = []
    dialogo.venda_confirmada.connect(resultados.append)

    dialogo.accept()
    dialogo.accept()

    assert len(resultados) == 1


def test_composicao_e_confirmacao_exigem_acoes_expressas_separadas(
    janela,
    qtbot,
) -> None:
    janela.item_criado.emit(criar_item(1000))
    confirmacoes = []
    janela.venda_confirmada.connect(confirmacoes.append)

    janela.abrir_dialogo_pagamentos()
    dialogo_pagamentos = janela.dialogo_atual
    qtbot.waitUntil(dialogo_pagamentos.isVisible)
    qtbot.keyPress(dialogo_pagamentos.campo_valor, Qt.Key.Key_Return)

    assert dialogo_pagamentos.isVisible()
    assert janela.composicao_pagamentos is None
    assert confirmacoes == []

    qtbot.mouseClick(
        dialogo_pagamentos.botao_concluir,
        Qt.MouseButton.LeftButton,
    )
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)

    assert janela.composicao_pagamentos is not None
    assert confirmacoes == []

    janela.abrir_dialogo_confirmacao()
    assert isinstance(janela.dialogo_atual, DialogoConfirmacaoVenda)
    qtbot.waitUntil(janela.dialogo_atual.isVisible)
    assert confirmacoes == []
    qtbot.keyPress(janela.dialogo_atual, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)


def test_reabre_composicao_e_cancelar_edicao_preserva_anterior(
    janela,
    qtbot,
) -> None:
    janela.item_criado.emit(criar_item(1000))
    composicao_anterior = registrar_composicao(janela, 1000)

    janela.abrir_dialogo_pagamentos()
    dialogo = janela.dialogo_atual
    qtbot.waitUntil(dialogo.isVisible)

    assert isinstance(dialogo, DialogoPagamentos)
    assert dialogo.estado_pagamentos is composicao_anterior
    assert dialogo.tabela_pagamentos.rowCount() == 1

    dialogo.tabela_pagamentos.selectRow(0)
    dialogo.campo_valor.setText("9,00")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)
    assert dialogo.estado_pagamentos is not composicao_anterior
    assert dialogo.estado_pagamentos.pagamentos == (Pagamento("PIX", 900),)

    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)

    assert janela.composicao_pagamentos is composicao_anterior
    assert janela.composicao_pagamentos.pagamentos == (
        Pagamento("PIX", 1000),
    )


@pytest.mark.parametrize("alteracao", ["inclusao", "remocao", "desfazer"])
def test_invalida_composicao_apos_alterar_itens(
    janela,
    alteracao,
) -> None:
    janela.item_criado.emit(criar_item(700))
    janela.item_criado.emit(criar_item(300))

    if alteracao == "inclusao":
        registrar_composicao(janela, 1000)
        janela.item_criado.emit(criar_item(100))
    elif alteracao == "remocao":
        registrar_composicao(janela, 1000)
        janela.remover_item_selecionado()
    else:
        janela.remover_item_selecionado()
        registrar_composicao(janela, 700)
        janela.desfazer_ultima_remocao()

    assert janela.composicao_pagamentos is None
    assert janela.resultado_confirmacao is None
    assert "pagamentos foram invalidados" in janela.rotulo_status.text()


def test_invalida_composicao_quando_alteracao_mantem_total_igual(
    janela,
) -> None:
    janela.item_criado.emit(criar_item(1000))
    registrar_composicao(janela, 1000)

    janela.item_criado.emit(criar_item(0))

    assert janela.estado_venda.venda.itens == (
        criar_item(1000),
        criar_item(0),
    )
    assert janela.composicao_pagamentos is None
    assert "pagamentos foram invalidados" in janela.rotulo_status.text()


def test_permite_nova_composicao_apos_invalidacao(janela, qtbot) -> None:
    janela.item_criado.emit(criar_item(1000))
    composicao_anterior = registrar_composicao(janela, 1000)
    janela.item_criado.emit(criar_item(500))

    janela.abrir_dialogo_pagamentos()
    dialogo = janela.dialogo_atual
    qtbot.waitUntil(dialogo.isVisible)

    assert isinstance(dialogo, DialogoPagamentos)
    assert dialogo.estado_pagamentos is not composicao_anterior
    assert dialogo.estado_pagamentos.pagamentos == ()
    assert dialogo.estado_pagamentos.total_venda_centavos == 1500

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)
    qtbot.mouseClick(dialogo.botao_concluir, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)

    assert janela.composicao_pagamentos is dialogo.estado_pagamentos
    assert janela.composicao_pagamentos.total_venda_centavos == 1500
    assert janela.composicao_pagamentos.pagamentos == (
        Pagamento("DINHEIRO", 1500),
    )


def test_cancelar_confirmacao_preserva_venda_e_pagamentos(
    janela,
    qtbot,
) -> None:
    item = criar_item(1000)
    janela.item_criado.emit(item)
    venda_anterior = janela.estado_venda.venda
    pagamentos_anteriores = registrar_composicao(janela, 1000)

    janela.abrir_dialogo_confirmacao()
    dialogo = janela.dialogo_atual
    qtbot.waitUntil(dialogo.isVisible)
    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)

    assert janela.estado_venda.venda is venda_anterior
    assert janela.estado_venda.venda.itens == (item,)
    assert janela.composicao_pagamentos is pagamentos_anteriores
    assert janela.resultado_confirmacao is None


def test_confirmar_entrega_resultado_ao_fechamento_operacional(
    janela,
    qtbot,
) -> None:
    item = criar_item(1000)
    janela.item_criado.emit(item)
    venda_anterior = janela.estado_venda.venda
    pagamentos_anteriores = registrar_composicao(janela, 1000)
    caminho_banco = janela.caminho_banco
    resultados = []
    janela.venda_confirmada.connect(resultados.append)

    criar_tabelas(caminho_banco)

    janela.abrir_dialogo_confirmacao()
    qtbot.waitUntil(janela.dialogo_atual.isVisible)
    qtbot.keyPress(janela.dialogo_atual, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)

    assert len(resultados) == 1
    assert resultados[0].venda is venda_anterior
    assert resultados[0].pagamentos is pagamentos_anteriores
    assert janela.estado_venda.venda.itens == ()
    assert janela.composicao_pagamentos is None
    assert caminho_banco.exists()
