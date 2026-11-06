import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from interface.dialogo_pagamentos import DialogoPagamentos
from models.pagamento import Pagamento
from services.pagamento_service import (
    calcular_saldo_restante,
    calcular_total_pago,
)


@pytest.fixture
def dialogo(qtbot):
    dialogo_pagamentos = DialogoPagamentos(1000)
    qtbot.addWidget(dialogo_pagamentos)
    dialogo_pagamentos.show()
    qtbot.waitUntil(dialogo_pagamentos.isVisible)
    qtbot.waitUntil(dialogo_pagamentos.combo_modalidade.hasFocus)
    return dialogo_pagamentos


def adicionar_por_enter(
    dialogo,
    qtbot,
    modalidade: str,
    valor: str,
) -> None:
    dialogo.combo_modalidade.setCurrentText(modalidade)
    dialogo.campo_valor.setText(valor)
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)


def test_abertura_exibe_total_e_sugere_saldo_restante(dialogo) -> None:
    assert dialogo.rotulo_total.text() == "R$ 10,00"
    assert dialogo.rotulo_total_pago.text() == "R$ 0,00"
    assert dialogo.rotulo_saldo.text() == "R$ 10,00"
    assert dialogo.campo_valor.text() == "10,00"
    assert dialogo.combo_modalidade.currentText() == "DINHEIRO"
    assert not dialogo.botao_concluir.isEnabled()


def test_selecionar_modalidade_preserva_valor_informado(
    dialogo,
) -> None:
    dialogo.campo_valor.setText("1,23")

    dialogo.combo_modalidade.setCurrentText("PIX")

    assert dialogo.campo_valor.text() == "1,23"


def test_enter_adiciona_pagamento_unico_e_habilita_conclusao(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "PIX", "10,00")

    assert dialogo.tabela_pagamentos.rowCount() == 1
    assert dialogo.tabela_pagamentos.item(0, 0).text() == "PIX"
    assert dialogo.tabela_pagamentos.item(0, 1).text() == "R$ 10,00"
    assert calcular_total_pago(dialogo.estado_pagamentos) == 1000
    assert calcular_saldo_restante(dialogo.estado_pagamentos) == 0
    assert dialogo.rotulo_total_pago.text() == "R$ 10,00"
    assert dialogo.rotulo_saldo.text() == "R$ 0,00"
    assert dialogo.botao_concluir.isEnabled()


def test_pagamentos_divididos_e_modalidade_repetida_preservam_ordem(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "PIX", "4,00")
    adicionar_por_enter(dialogo, qtbot, "PIX", "3,00")
    adicionar_por_enter(dialogo, qtbot, "DINHEIRO", "3,00")

    assert dialogo.estado_pagamentos.pagamentos == (
        Pagamento("PIX", 400),
        Pagamento("PIX", 300),
        Pagamento("DINHEIRO", 300),
    )
    assert dialogo.tabela_pagamentos.rowCount() == 3
    assert dialogo.botao_concluir.isEnabled()


def test_editar_pagamento_altera_modalidade_valor_e_recalcula(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "DINHEIRO", "4,00")
    adicionar_por_enter(dialogo, qtbot, "PIX", "3,00")
    dialogo.tabela_pagamentos.selectRow(0)

    assert dialogo._indice_edicao == 0
    assert not dialogo.botao_adicionar.isEnabled()
    assert dialogo.botao_editar.isEnabled()
    dialogo.combo_modalidade.setCurrentText("DEBITO")
    dialogo.campo_valor.setText("5,00")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.estado_pagamentos.pagamentos == (
        Pagamento("DEBITO", 500),
        Pagamento("PIX", 300),
    )
    assert dialogo.rotulo_total_pago.text() == "R$ 8,00"
    assert dialogo.rotulo_saldo.text() == "R$ 2,00"
    assert dialogo._indice_edicao is None


def test_remover_pagamento_recalcula_total_e_saldo(dialogo, qtbot) -> None:
    adicionar_por_enter(dialogo, qtbot, "DINHEIRO", "4,00")
    adicionar_por_enter(dialogo, qtbot, "PIX", "6,00")
    dialogo.tabela_pagamentos.selectRow(0)

    qtbot.mouseClick(dialogo.botao_remover, Qt.MouseButton.LeftButton)

    assert dialogo.estado_pagamentos.pagamentos == (Pagamento("PIX", 600),)
    assert dialogo.rotulo_total_pago.text() == "R$ 6,00"
    assert dialogo.rotulo_saldo.text() == "R$ 4,00"
    assert dialogo.campo_valor.text() == "4,00"
    assert not dialogo.botao_concluir.isEnabled()


def test_pagamento_excedente_exibe_erro_sem_corromper_estado(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "DINHEIRO", "6,00")
    estado_antes = dialogo.estado_pagamentos

    adicionar_por_enter(dialogo, qtbot, "PIX", "4,01")

    assert dialogo.estado_pagamentos is estado_antes
    assert dialogo.estado_pagamentos.pagamentos == (Pagamento("DINHEIRO", 600),)
    assert dialogo.tabela_pagamentos.rowCount() == 1
    assert "saldo restante" in dialogo.rotulo_erro.text()


def test_edicao_excedente_preserva_estado_e_contexto_de_edicao(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "DINHEIRO", "6,00")
    adicionar_por_enter(dialogo, qtbot, "PIX", "3,00")
    dialogo.tabela_pagamentos.selectRow(0)
    estado_antes = dialogo.estado_pagamentos
    dialogo.campo_valor.setText("7,01")

    qtbot.mouseClick(dialogo.botao_editar, Qt.MouseButton.LeftButton)

    assert dialogo.estado_pagamentos is estado_antes
    assert dialogo._indice_edicao == 0
    assert "ultrapassar" in dialogo.rotulo_erro.text()


def test_divisao_igual_sugere_valores_sem_criar_pagamentos(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)

    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    assert dialogo.sugestoes_divisao == (334, 333, 333)
    assert dialogo.campo_valor.text() == "3,34"
    assert dialogo.rotulo_sugestao.text() == (
        "Divisão — Próxima: R$ 3,34 | Pendente: R$ 3,33 | "
        "Pendente: R$ 3,33"
    )
    assert dialogo.estado_pagamentos.pagamentos == ()


def test_divisao_permanece_visivel_e_preenche_segunda_e_terceira_parcelas(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.sugestoes_divisao == (334, 333, 333)
    assert dialogo.campo_valor.text() == "3,33"
    assert "Usada: R$ 3,34" in dialogo.rotulo_sugestao.text()
    assert "Próxima: R$ 3,33" in dialogo.rotulo_sugestao.text()

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.campo_valor.text() == "3,33"
    assert dialogo.rotulo_sugestao.text().count("Usada:") == 2
    assert "Próxima: R$ 3,33" in dialogo.rotulo_sugestao.text()

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.isVisible()
    assert dialogo.estado_pagamentos.pagamentos == (
        Pagamento("DINHEIRO", 334),
        Pagamento("DINHEIRO", 333),
        Pagamento("DINHEIRO", 333),
    )
    assert dialogo.rotulo_sugestao.text().count("Usada:") == 3
    assert "todas adicionadas" in dialogo.rotulo_sugestao.text()


def test_trocar_modalidade_nao_sobrescreve_parcela_sugerida(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    dialogo.combo_modalidade.setCurrentText("PIX")

    assert dialogo.campo_valor.text() == "3,34"


def test_valor_manual_interrompe_automatismo_sem_apagar_referencia(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    dialogo.campo_valor.setText("4,00")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.estado_pagamentos.pagamentos == (
        Pagamento("DINHEIRO", 400),
    )
    assert dialogo.sugestoes_divisao == (334, 333, 333)
    assert dialogo.campo_valor.text() == "6,00"
    assert "referência mantida" in dialogo.rotulo_sugestao.text()
    assert not dialogo._divisao_automatica_ativa


def test_nova_divisao_substitui_referencia_somente_por_acao_expressa(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)
    dialogo.campo_valor.setText("4,00")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    dialogo.campo_partes.setValue(2)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    assert dialogo.sugestoes_divisao == (300, 300)
    assert dialogo.campo_valor.text() == "3,00"
    assert "referência mantida" not in dialogo.rotulo_sugestao.text()
    assert dialogo.rotulo_sugestao.text() == (
        "Divisão — Próxima: R$ 3,00 | Pendente: R$ 3,00"
    )


def test_edicao_de_modalidade_preserva_divisao_e_remocao_a_invalida(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)
    dialogo.tabela_pagamentos.selectRow(0)

    dialogo.combo_modalidade.setCurrentText("PIX")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.campo_valor.text() == "3,33"
    assert "referência mantida" not in dialogo.rotulo_sugestao.text()
    assert "Usada: R$ 3,34" in dialogo.rotulo_sugestao.text()

    dialogo.tabela_pagamentos.selectRow(0)
    qtbot.mouseClick(dialogo.botao_remover, Qt.MouseButton.LeftButton)

    assert dialogo.estado_pagamentos.pagamentos == ()
    assert dialogo.sugestoes_divisao == (334, 333, 333)
    assert "referência mantida" in dialogo.rotulo_sugestao.text()
    assert not dialogo._divisao_automatica_ativa


def test_ctrl_enter_conclui_somente_apos_pagamento_integral(
    dialogo,
    qtbot,
) -> None:
    resultados = []
    dialogo.pagamentos_confirmados.connect(resultados.append)

    qtbot.keyClick(
        dialogo.campo_valor,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert dialogo.isVisible()
    assert resultados == []
    assert dialogo.estado_pagamentos.pagamentos == ()
    assert "todo o saldo" in dialogo.rotulo_erro.text()

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.isVisible()
    assert dialogo.estado_pagamentos.pagamentos == (
        Pagamento("DINHEIRO", 1000),
    )

    qtbot.keyClick(
        dialogo,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ControlModifier,
    )

    qtbot.waitUntil(lambda: not dialogo.isVisible())
    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert resultados == [dialogo.estado_pagamentos]


def test_escape_cancela_edicao_sem_perder_pagamentos(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "PIX", "4,00")
    dialogo.tabela_pagamentos.selectRow(0)
    dialogo.campo_valor.setText("2,00")

    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)

    assert dialogo.isVisible()
    assert dialogo._indice_edicao is None
    assert dialogo.estado_pagamentos.pagamentos == (Pagamento("PIX", 400),)
    assert dialogo.campo_valor.text() == "6,00"


def test_escape_fora_de_edicao_fecha_sem_emitir_resultado(dialogo, qtbot) -> None:
    resultados = []
    dialogo.pagamentos_confirmados.connect(resultados.append)
    adicionar_por_enter(dialogo, qtbot, "PIX", "4,00")

    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)

    qtbot.waitUntil(lambda: not dialogo.isVisible())
    assert dialogo.result() == QDialog.DialogCode.Rejected
    assert resultados == []


def test_conclusao_so_emite_estado_quando_saldo_e_zero(dialogo, qtbot) -> None:
    resultados = []
    dialogo.pagamentos_confirmados.connect(resultados.append)
    adicionar_por_enter(dialogo, qtbot, "PIX", "9,99")

    dialogo.accept()

    assert dialogo.isVisible()
    assert resultados == []
    assert "todo o saldo" in dialogo.rotulo_erro.text()

    adicionar_por_enter(dialogo, qtbot, "DINHEIRO", "0,01")
    qtbot.mouseClick(dialogo.botao_concluir, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: not dialogo.isVisible())
    assert dialogo.result() == QDialog.DialogCode.Accepted
    assert resultados == [dialogo.estado_pagamentos]


def test_tab_move_foco_da_modalidade_para_o_valor(dialogo, qtbot) -> None:
    qtbot.keyPress(dialogo.combo_modalidade, Qt.Key.Key_Tab)

    qtbot.waitUntil(dialogo.campo_valor.hasFocus)
