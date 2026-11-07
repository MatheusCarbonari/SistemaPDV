import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QDialog, QHeaderView

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
    qtbot.waitUntil(
        dialogo_pagamentos.botoes_modalidade["DINHEIRO"].hasFocus
    )
    return dialogo_pagamentos


def adicionar_por_enter(
    dialogo,
    qtbot,
    modalidade: str,
    valor: str,
) -> None:
    dialogo.botoes_modalidade[modalidade].click()
    dialogo.campo_valor.setText(valor)
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)


def _luminancia_relativa(cor: QColor) -> float:
    canais = []
    for canal in (cor.redF(), cor.greenF(), cor.blueF()):
        canais.append(
            canal / 12.92
            if canal <= 0.04045
            else ((canal + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def _contraste(cor_a: QColor, cor_b: QColor) -> float:
    mais_clara, mais_escura = sorted(
        (_luminancia_relativa(cor_a), _luminancia_relativa(cor_b)),
        reverse=True,
    )
    return (mais_clara + 0.05) / (mais_escura + 0.05)


def test_abertura_exibe_total_e_sugere_saldo_restante(dialogo) -> None:
    assert dialogo.rotulo_total.text() == "R$ 10,00"
    assert dialogo.rotulo_total_pago.text() == "R$ 0,00"
    assert dialogo.rotulo_saldo.text() == "R$ 10,00"
    assert dialogo.campo_valor.text() == "10,00"
    assert dialogo.grupo_modalidades.checkedButton().property(
        "modalidade"
    ) == "DINHEIRO"
    assert not dialogo.botao_concluir.isEnabled()


def test_selecionar_modalidade_preserva_valor_informado(
    dialogo,
) -> None:
    dialogo.campo_valor.setText("1,23")

    dialogo.botoes_modalidade["PIX"].click()

    assert dialogo.campo_valor.text() == "1,23"


def test_quatro_modalidades_ficam_visiveis_com_selecao_exclusiva(
    dialogo,
    qtbot,
) -> None:
    assert tuple(dialogo.botoes_modalidade) == (
        "DINHEIRO",
        "CREDITO",
        "DEBITO",
        "PIX",
    )
    assert all(
        botao.isVisible()
        for botao in dialogo.botoes_modalidade.values()
    )
    assert dialogo.grupo_modalidades.exclusive()
    assert dialogo.botoes_modalidade["DINHEIRO"].isChecked()

    qtbot.mouseClick(
        dialogo.botoes_modalidade["CREDITO"],
        Qt.MouseButton.LeftButton,
    )

    assert dialogo.botoes_modalidade["CREDITO"].isChecked()
    assert sum(
        botao.isChecked()
        for botao in dialogo.botoes_modalidade.values()
    ) == 1


def test_enter_adiciona_pagamento_unico_e_habilita_conclusao(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "PIX", "10,00")

    assert dialogo.tabela_pagamentos.rowCount() == 1
    assert dialogo.tabela_pagamentos.item(0, 0).text() == "PIX"
    assert dialogo.tabela_pagamentos.item(0, 1).text() == "R$ 10,00"
    assert dialogo.tabela_pagamentos.item(0, 1).textAlignment() & int(
        Qt.AlignmentFlag.AlignRight
    )
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
    assert dialogo.grupo_lancamento.title() == "Editando pagamento 1"
    assert dialogo.grupo_lancamento.property("modoEdicao")
    assert not dialogo.botao_adicionar.isEnabled()
    assert dialogo.botao_editar.isEnabled()
    dialogo.botoes_modalidade["DEBITO"].click()
    dialogo.campo_valor.setText("5,00")
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.estado_pagamentos.pagamentos == (
        Pagamento("DEBITO", 500),
        Pagamento("PIX", 300),
    )
    assert dialogo.rotulo_total_pago.text() == "R$ 8,00"
    assert dialogo.rotulo_saldo.text() == "R$ 2,00"
    assert dialogo._indice_edicao is None
    assert dialogo.grupo_lancamento.title() == "Novo lançamento"
    assert not dialogo.grupo_lancamento.property("modoEdicao")


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
        "Sugestão válida; a próxima parcela está destacada na tabela."
    )
    assert dialogo.tabela_sugestoes.item(0, 2).text() == "Próxima"
    assert dialogo.tabela_sugestoes.item(1, 2).text() == "Pendente"
    assert dialogo.tabela_sugestoes.item(2, 2).text() == "Pendente"
    assert dialogo.estado_pagamentos.pagamentos == ()


def test_divisao_exibe_base_quantidade_valores_e_situacoes(
    dialogo,
    qtbot,
) -> None:
    adicionar_por_enter(dialogo, qtbot, "PIX", "4,00")
    dialogo.campo_partes.setValue(2)

    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    assert dialogo.rotulo_total.text() == "R$ 10,00"
    assert dialogo.rotulo_base_divisao.text() == "R$ 6,00"
    assert dialogo.rotulo_quantidade_divisao.text() == "2"
    assert dialogo.rotulo_estado_divisao.text() == "Válida"
    assert dialogo.rotulo_estado_divisao.property("estadoSugestao") == "valida"
    assert dialogo.tabela_sugestoes.rowCount() == 2
    assert dialogo.tabela_sugestoes.item(0, 0).text() == "1"
    assert dialogo.tabela_sugestoes.item(0, 1).text() == "R$ 3,00"
    assert dialogo.tabela_sugestoes.item(0, 2).text() == "Próxima"
    assert dialogo.tabela_sugestoes.item(1, 1).text() == "R$ 3,00"
    assert dialogo.tabela_sugestoes.item(1, 2).text() == "Pendente"


def test_divisao_permanece_visivel_e_preenche_segunda_e_terceira_parcelas(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.sugestoes_divisao == (334, 333, 333)
    assert dialogo.campo_valor.text() == "3,33"
    assert dialogo.tabela_sugestoes.item(0, 2).text() == "Utilizada"
    assert dialogo.tabela_sugestoes.item(1, 2).text() == "Próxima"

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.campo_valor.text() == "3,33"
    assert dialogo.tabela_sugestoes.item(0, 2).text() == "Utilizada"
    assert dialogo.tabela_sugestoes.item(1, 2).text() == "Utilizada"
    assert dialogo.tabela_sugestoes.item(2, 2).text() == "Próxima"

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.isVisible()
    assert dialogo.estado_pagamentos.pagamentos == (
        Pagamento("DINHEIRO", 334),
        Pagamento("DINHEIRO", 333),
        Pagamento("DINHEIRO", 333),
    )
    assert all(
        dialogo.tabela_sugestoes.item(linha, 2).text() == "Utilizada"
        for linha in range(3)
    )
    assert "Todas as parcelas" in dialogo.rotulo_sugestao.text()


def test_trocar_modalidade_nao_sobrescreve_parcela_sugerida(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    dialogo.botoes_modalidade["PIX"].click()

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
    assert "referência mantida" in dialogo.rotulo_sugestao.text().lower()
    assert not dialogo._divisao_automatica_ativa


def test_sugestao_desatualizada_preserva_referencia_visual(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)

    dialogo.campo_valor.setText("4,00")

    assert dialogo.rotulo_base_divisao.text() == "R$ 10,00"
    assert dialogo.rotulo_quantidade_divisao.text() == "3"
    assert dialogo.rotulo_estado_divisao.text() == "Desatualizada"
    assert (
        dialogo.rotulo_estado_divisao.property("estadoSugestao")
        == "desatualizada"
    )
    assert dialogo.tabela_sugestoes.rowCount() == 3
    assert dialogo.tabela_sugestoes.item(0, 1).text() == "R$ 3,34"
    assert "nova divisão" in dialogo.rotulo_sugestao.text()
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
    assert "referência mantida" not in dialogo.rotulo_sugestao.text().lower()
    assert dialogo.rotulo_sugestao.text() == (
        "Sugestão válida; a próxima parcela está destacada na tabela."
    )


def test_edicao_de_modalidade_preserva_divisao_e_remocao_a_invalida(
    dialogo,
    qtbot,
) -> None:
    dialogo.campo_partes.setValue(3)
    qtbot.mouseClick(dialogo.botao_dividir, Qt.MouseButton.LeftButton)
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)
    dialogo.tabela_pagamentos.selectRow(0)

    dialogo.botoes_modalidade["PIX"].click()
    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    assert dialogo.campo_valor.text() == "3,33"
    assert "referência mantida" not in dialogo.rotulo_sugestao.text().lower()
    assert dialogo.tabela_sugestoes.item(0, 2).text() == "Utilizada"

    dialogo.tabela_pagamentos.selectRow(0)
    qtbot.mouseClick(dialogo.botao_remover, Qt.MouseButton.LeftButton)

    assert dialogo.estado_pagamentos.pagamentos == ()
    assert dialogo.sugestoes_divisao == (334, 333, 333)
    assert "referência mantida" in dialogo.rotulo_sugestao.text().lower()
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


def test_tab_percorre_modalidades_e_alcanca_valor(dialogo, qtbot) -> None:
    qtbot.keyPress(dialogo.focusWidget(), Qt.Key.Key_Tab)

    qtbot.waitUntil(dialogo.campo_valor.hasFocus)


@pytest.mark.parametrize(
    "largura,altura",
    [(900, 700), (1024, 720), (640, 480)],
)
def test_layout_redimensionavel_preserva_acoes_sem_cortes(
    dialogo,
    qtbot,
    largura,
    altura,
) -> None:
    dialogo.resize(largura, altura)
    qtbot.wait(20)

    assert dialogo.minimumWidth() == 640
    assert dialogo.minimumHeight() == 480
    assert dialogo.isSizeGripEnabled()
    assert dialogo.area_rolagem.viewport().width() > 0
    assert dialogo.botoes.geometry().bottom() <= dialogo.rect().bottom()
    assert dialogo.botao_concluir.isVisible()
    assert dialogo.botao_concluir.width() >= (
        dialogo.botao_concluir.sizeHint().width()
    )
    assert not dialogo.area_rolagem.horizontalScrollBar().isVisible()
    if largura >= 900:
        assert not dialogo._layout_empilhado
        qtbot.waitUntil(
            lambda: not dialogo.area_rolagem.verticalScrollBar().isVisible()
        )
    else:
        assert dialogo._layout_empilhado
        assert dialogo.area_rolagem.verticalScrollBar().isVisible()


def test_layout_simula_escala_125_sem_rolagem_horizontal(
    dialogo,
    qtbot,
) -> None:
    fonte_ampliada = dialogo.font()
    fonte_ampliada.setPointSizeF(fonte_ampliada.pointSizeF() * 1.25)
    dialogo.setFont(fonte_ampliada)
    dialogo.resize(737, 576)

    qtbot.wait(20)

    assert not dialogo.area_rolagem.horizontalScrollBar().isVisible()
    assert dialogo.botao_concluir.isVisible()
    assert dialogo.botoes.geometry().bottom() <= dialogo.rect().bottom()


def test_tabelas_e_campos_usam_larguras_e_contraste_explicitos(dialogo) -> None:
    cabecalho_pagamentos = dialogo.tabela_pagamentos.horizontalHeader()
    assert cabecalho_pagamentos.sectionResizeMode(0) == (
        QHeaderView.ResizeMode.Stretch
    )
    assert cabecalho_pagamentos.sectionResizeMode(1) == (
        QHeaderView.ResizeMode.Stretch
    )
    assert abs(
        dialogo.tabela_pagamentos.columnWidth(0)
        - dialogo.tabela_pagamentos.columnWidth(1)
    ) <= 2
    assert dialogo.campo_valor.maximumWidth() == 160

    paleta_tabela = dialogo.tabela_pagamentos.palette()
    assert _contraste(
        paleta_tabela.color(QPalette.ColorRole.Text),
        paleta_tabela.color(QPalette.ColorRole.Base),
    ) >= 4.5
    assert _contraste(
        paleta_tabela.color(QPalette.ColorRole.HighlightedText),
        paleta_tabela.color(QPalette.ColorRole.Highlight),
    ) >= 4.5

    paleta_campo = dialogo.campo_valor.palette()
    assert _contraste(
        paleta_campo.color(QPalette.ColorRole.Text),
        paleta_campo.color(QPalette.ColorRole.Base),
    ) >= 4.5
    assert "#2474a6" in dialogo.styleSheet()


def test_duas_colunas_e_metadados_nao_se_sobrepoem_em_900x700(
    dialogo,
    qtbot,
) -> None:
    dialogo.resize(900, 700)
    qtbot.wait(20)

    posicao_esquerda = dialogo.layout_colunas.getItemPosition(
        dialogo.layout_colunas.indexOf(dialogo.coluna_esquerda)
    )
    posicao_direita = dialogo.layout_colunas.getItemPosition(
        dialogo.layout_colunas.indexOf(dialogo.grupo_registrados)
    )
    assert posicao_esquerda[:2] == (0, 0)
    assert posicao_direita[:2] == (0, 1)
    assert (
        dialogo.coluna_esquerda.geometry().right()
        < dialogo.grupo_registrados.geometry().left()
    )

    for rotulo in dialogo.rotulos_metadados_divisao.values():
        assert rotulo.width() >= rotulo.sizeHint().width()


def test_estados_das_acoes_acompanham_o_contexto(dialogo, qtbot) -> None:
    assert dialogo.botao_adicionar.isEnabled()
    assert not dialogo.botao_editar.isEnabled()
    assert not dialogo.botao_remover.isEnabled()
    assert dialogo.botao_dividir.isEnabled()
    assert not dialogo.botao_concluir.isEnabled()

    adicionar_por_enter(dialogo, qtbot, "PIX", "4,00")
    dialogo.tabela_pagamentos.selectRow(0)

    assert not dialogo.botao_adicionar.isEnabled()
    assert dialogo.botao_editar.isEnabled()
    assert dialogo.botao_remover.isEnabled()
    assert not dialogo.botao_concluir.isEnabled()

    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)
    adicionar_por_enter(dialogo, qtbot, "DINHEIRO", "6,00")

    assert dialogo.botao_concluir.isEnabled()
    assert not dialogo.botao_dividir.isEnabled()
