import pytest
from PySide6.QtCore import Qt

from interface.dialogo_pagamentos import DialogoPagamentos
from interface.janela_principal import JanelaPrincipal
from models.item_venda import ItemVenda


def criar_item(subtotal_centavos: int) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
    )


@pytest.fixture
def janela(qtbot, tmp_path):
    janela_principal = JanelaPrincipal(tmp_path / "nao_utilizado.db")
    qtbot.addWidget(janela_principal)
    janela_principal.show()
    qtbot.waitUntil(janela_principal.isVisible)
    qtbot.waitUntil(janela_principal.campo_entrada.hasFocus)
    return janela_principal


def test_venda_vazia_nao_permite_abrir_pagamentos(janela) -> None:
    estado_antes = janela.estado_venda

    janela.abrir_dialogo_pagamentos()

    assert janela.dialogo_atual is None
    assert janela.estado_venda is estado_antes
    assert not janela.botao_pagamento.isEnabled()
    assert "Adicione ao menos um item" in janela.rotulo_status.text()


def test_venda_com_total_zero_nao_permite_pagamento(janela) -> None:
    janela.item_criado.emit(criar_item(0))
    estado_antes = janela.estado_venda

    janela.abrir_dialogo_pagamentos()

    assert janela.dialogo_atual is None
    assert janela.estado_venda is estado_antes
    assert not janela.botao_pagamento.isEnabled()


def test_botao_abre_dialogo_com_total_da_venda_sem_mudar_estado(
    janela,
    qtbot,
) -> None:
    janela.item_criado.emit(criar_item(1234))
    janela.item_criado.emit(criar_item(66))
    estado_antes = janela.estado_venda

    qtbot.mouseClick(janela.botao_pagamento, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: isinstance(janela.dialogo_atual, DialogoPagamentos)
    )
    dialogo = janela.dialogo_atual
    assert dialogo.estado_pagamentos.total_venda_centavos == 1300
    assert dialogo.rotulo_total.text() == "R$ 13,00"
    assert janela.estado_venda is estado_antes


def test_cancelar_dialogo_preserva_venda_e_restaura_foco(janela, qtbot) -> None:
    janela.item_criado.emit(criar_item(1000))
    estado_antes = janela.estado_venda
    resultados = []
    janela.pagamentos_confirmados.connect(resultados.append)
    janela.abrir_dialogo_pagamentos()
    dialogo = janela.dialogo_atual
    dialogo.campo_valor.setText("4,00")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)

    qtbot.waitUntil(lambda: janela.dialogo_atual is None)
    assert janela.estado_venda is estado_antes
    assert janela.estado_venda.venda.itens == (criar_item(1000),)
    assert resultados == []
    assert janela.rotulo_status.text() == "Operação cancelada."
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_confirmar_disponibiliza_pagamentos_sem_limpar_ou_persistir_venda(
    janela,
    qtbot,
) -> None:
    item = criar_item(1000)
    janela.item_criado.emit(item)
    estado_antes = janela.estado_venda
    resultados = []
    janela.pagamentos_confirmados.connect(resultados.append)
    janela.abrir_dialogo_pagamentos()
    dialogo = janela.dialogo_atual
    dialogo.campo_valor.setText("10,00")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    qtbot.mouseClick(dialogo.botao_concluir, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: janela.dialogo_atual is None)
    assert len(resultados) == 1
    assert resultados[0].total_venda_centavos == 1000
    assert resultados[0].pagamentos[0].valor_centavos == 1000
    assert janela.estado_venda is estado_antes
    assert janela.estado_venda.venda.itens == (item,)
    assert janela.rotulo_total.text() == "Total: R$ 10,00"
    assert janela.rotulo_status.text() == "Pagamentos compostos."
    qtbot.waitUntil(janela.campo_entrada.hasFocus)
