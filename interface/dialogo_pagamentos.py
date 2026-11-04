from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from interface.formatacao import (
    centavos_para_texto,
    formatar_centavos,
    ler_centavos,
)
from models.pagamento import Pagamento, PagamentosEmAndamento
from services.pagamento_service import (
    adicionar_pagamento,
    calcular_saldo_restante,
    calcular_total_pago,
    dividir_valor_igualmente,
    editar_pagamento,
    esta_integralmente_pago,
    remover_pagamento,
)


MODALIDADES_EXIBIDAS = ("DINHEIRO", "CREDITO", "DEBITO", "PIX")
MAXIMO_INTEIRO_QT = 2_147_483_647


class DialogoPagamentos(QDialog):
    pagamentos_confirmados = Signal(object)

    def __init__(
        self,
        total_venda_centavos: int,
        parent=None,
        estado_inicial: PagamentosEmAndamento | None = None,
    ) -> None:
        super().__init__(parent)
        if estado_inicial is not None:
            if not isinstance(estado_inicial, PagamentosEmAndamento):
                raise TypeError(
                    "O estado inicial deve ser PagamentosEmAndamento ou None."
                )
            if estado_inicial.total_venda_centavos != total_venda_centavos:
                raise ValueError(
                    "O estado inicial não corresponde ao total da venda."
                )
            self.estado_pagamentos = estado_inicial
        else:
            self.estado_pagamentos = PagamentosEmAndamento(
                total_venda_centavos
            )
        self._indice_edicao: int | None = None
        self._resultado_confirmado = False
        self.sugestoes_divisao: tuple[int, ...] = ()
        self.setWindowTitle("Pagamentos")
        self.setModal(True)

        layout = QVBoxLayout(self)
        formulario = QFormLayout()

        self.rotulo_total = QLabel(formatar_centavos(total_venda_centavos))
        self.rotulo_total.setObjectName("total_pagamentos")
        formulario.addRow("Total da venda:", self.rotulo_total)

        self.combo_modalidade = QComboBox()
        self.combo_modalidade.setObjectName("modalidade_pagamento")
        self.combo_modalidade.addItems(MODALIDADES_EXIBIDAS)
        formulario.addRow("Modalidade:", self.combo_modalidade)

        self.campo_valor = QLineEdit()
        self.campo_valor.setObjectName("valor_pagamento")
        formulario.addRow("Valor (R$):", self.campo_valor)
        layout.addLayout(formulario)

        self.tabela_pagamentos = QTableWidget(0, 2)
        self.tabela_pagamentos.setObjectName("lista_pagamentos")
        self.tabela_pagamentos.setHorizontalHeaderLabels(
            ["Modalidade", "Valor"]
        )
        self.tabela_pagamentos.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela_pagamentos.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela_pagamentos.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela_pagamentos.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_pagamentos)

        layout_acoes = QHBoxLayout()
        self.botao_adicionar = QPushButton("Adicionar")
        self.botao_adicionar.setObjectName("adicionar_pagamento")
        self.botao_editar = QPushButton("Editar")
        self.botao_editar.setObjectName("editar_pagamento")
        self.botao_remover = QPushButton("Remover")
        self.botao_remover.setObjectName("remover_pagamento")
        layout_acoes.addWidget(self.botao_adicionar)
        layout_acoes.addWidget(self.botao_editar)
        layout_acoes.addWidget(self.botao_remover)
        layout_acoes.addStretch()
        layout.addLayout(layout_acoes)

        layout_divisao = QHBoxLayout()
        layout_divisao.addWidget(QLabel("Dividir saldo em:"))
        self.campo_partes = QSpinBox()
        self.campo_partes.setObjectName("quantidade_partes_pagamento")
        self.campo_partes.setRange(
            1,
            max(1, min(total_venda_centavos, MAXIMO_INTEIRO_QT)),
        )
        self.campo_partes.setValue(min(2, total_venda_centavos))
        layout_divisao.addWidget(self.campo_partes)
        self.botao_dividir = QPushButton("Sugerir divisão")
        self.botao_dividir.setObjectName("dividir_pagamento")
        layout_divisao.addWidget(self.botao_dividir)
        layout_divisao.addStretch()
        layout.addLayout(layout_divisao)

        self.rotulo_sugestao = QLabel("")
        self.rotulo_sugestao.setObjectName("sugestao_divisao_pagamento")
        layout.addWidget(self.rotulo_sugestao)

        resumo = QFormLayout()
        self.rotulo_total_pago = QLabel(formatar_centavos(0))
        self.rotulo_total_pago.setObjectName("total_pago")
        self.rotulo_saldo = QLabel(formatar_centavos(total_venda_centavos))
        self.rotulo_saldo.setObjectName("saldo_restante")
        resumo.addRow("Total pago:", self.rotulo_total_pago)
        resumo.addRow("Saldo restante:", self.rotulo_saldo)
        layout.addLayout(resumo)

        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setObjectName("erro_pagamento")
        layout.addWidget(self.rotulo_erro)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_concluir = self.botoes.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.botao_concluir.setText("Concluir")
        self.botao_concluir.setObjectName("concluir_pagamentos")
        self.botao_concluir.setAutoDefault(False)
        self.botao_concluir.setDefault(False)
        botao_cancelar = self.botoes.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        botao_cancelar.setText("Cancelar")
        botao_cancelar.setAutoDefault(False)
        for botao in (
            self.botao_adicionar,
            self.botao_editar,
            self.botao_remover,
            self.botao_dividir,
        ):
            botao.setAutoDefault(False)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

        self.botao_adicionar.clicked.connect(self._adicionar_pagamento)
        self.botao_editar.clicked.connect(self._editar_pagamento)
        self.botao_remover.clicked.connect(self._remover_pagamento)
        self.botao_dividir.clicked.connect(self._sugerir_divisao)
        self.campo_valor.returnPressed.connect(self._confirmar_lancamento)
        self.combo_modalidade.currentTextChanged.connect(
            self._sugerir_saldo_para_modalidade
        )
        self.tabela_pagamentos.itemSelectionChanged.connect(
            self._carregar_pagamento_selecionado
        )

        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        QTimer.singleShot(0, self.combo_modalidade.setFocus)

    def keyPressEvent(self, evento) -> None:
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            evento.accept()
            return

        if evento.key() == Qt.Key.Key_Escape and self._indice_edicao is not None:
            self._preparar_novo_lancamento()
            evento.accept()
            return

        super().keyPressEvent(evento)

    def accept(self) -> None:
        if self._resultado_confirmado:
            return

        if not esta_integralmente_pago(self.estado_pagamentos):
            self._mostrar_erro(
                ValueError("Informe pagamentos para cobrir todo o saldo.")
            )
            return

        self._resultado_confirmado = True
        self.pagamentos_confirmados.emit(self.estado_pagamentos)
        super().accept()

    def _criar_pagamento_do_formulario(self) -> Pagamento:
        valor_centavos = ler_centavos(self.campo_valor.text())
        return Pagamento(
            modalidade=self.combo_modalidade.currentText(),
            valor_centavos=valor_centavos,
        )

    def _confirmar_lancamento(self) -> None:
        if self._indice_edicao is None:
            self._adicionar_pagamento()
        else:
            self._editar_pagamento()

    def _adicionar_pagamento(self) -> None:
        try:
            pagamento = self._criar_pagamento_do_formulario()
            novo_estado = adicionar_pagamento(
                self.estado_pagamentos,
                pagamento,
            )
        except (TypeError, ValueError) as erro:
            self._mostrar_erro(erro)
            return

        self.estado_pagamentos = novo_estado
        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def _editar_pagamento(self) -> None:
        if self._indice_edicao is None:
            self._mostrar_erro(ValueError("Selecione um pagamento para editar."))
            return

        try:
            pagamento = self._criar_pagamento_do_formulario()
            novo_estado = editar_pagamento(
                self.estado_pagamentos,
                self._indice_edicao,
                pagamento,
            )
        except (TypeError, ValueError, IndexError) as erro:
            self._mostrar_erro(erro)
            return

        self.estado_pagamentos = novo_estado
        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def _remover_pagamento(self) -> None:
        if self._indice_edicao is None:
            self._mostrar_erro(ValueError("Selecione um pagamento para remover."))
            return

        try:
            novo_estado = remover_pagamento(
                self.estado_pagamentos,
                self._indice_edicao,
            )
        except (TypeError, ValueError, IndexError) as erro:
            self._mostrar_erro(erro)
            return

        self.estado_pagamentos = novo_estado
        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def _carregar_pagamento_selecionado(self) -> None:
        linhas = self.tabela_pagamentos.selectionModel().selectedRows()
        if not linhas:
            self._indice_edicao = None
            self._atualizar_botoes_de_edicao()
            return

        self._indice_edicao = linhas[0].row()
        pagamento = self.estado_pagamentos.pagamentos[self._indice_edicao]
        self.combo_modalidade.setCurrentText(pagamento.modalidade)
        self.campo_valor.setText(
            centavos_para_texto(pagamento.valor_centavos)
        )
        self.rotulo_erro.clear()
        self._atualizar_botoes_de_edicao()
        self.campo_valor.setFocus()
        self.campo_valor.selectAll()

    def _preparar_novo_lancamento(self) -> None:
        self._indice_edicao = None
        self.tabela_pagamentos.clearSelection()
        self.rotulo_erro.clear()
        self._limpar_sugestao_divisao()
        saldo = calcular_saldo_restante(self.estado_pagamentos)
        self.campo_valor.setText(
            centavos_para_texto(saldo) if saldo > 0 else ""
        )
        self._atualizar_botoes_de_edicao()
        self.combo_modalidade.setFocus()

    def _sugerir_saldo_para_modalidade(self, modalidade: str) -> None:
        if self._indice_edicao is not None or not modalidade:
            return

        saldo = calcular_saldo_restante(self.estado_pagamentos)
        self.campo_valor.setText(
            centavos_para_texto(saldo) if saldo > 0 else ""
        )

    def _sugerir_divisao(self) -> None:
        saldo = calcular_saldo_restante(self.estado_pagamentos)

        try:
            sugestoes = dividir_valor_igualmente(
                saldo,
                self.campo_partes.value(),
            )
        except (TypeError, ValueError) as erro:
            self._mostrar_erro(erro)
            return

        self.sugestoes_divisao = sugestoes
        self.rotulo_sugestao.setText(
            "Sugestão: "
            + " + ".join(formatar_centavos(valor) for valor in sugestoes)
        )
        self.campo_valor.setText(centavos_para_texto(sugestoes[0]))
        self.rotulo_erro.clear()
        self.campo_valor.setFocus()
        self.campo_valor.selectAll()

    def _atualizar_exibicao(self) -> None:
        pagamentos = self.estado_pagamentos.pagamentos
        self.tabela_pagamentos.setRowCount(len(pagamentos))

        for linha, pagamento in enumerate(pagamentos):
            self.tabela_pagamentos.setItem(
                linha,
                0,
                QTableWidgetItem(pagamento.modalidade),
            )
            self.tabela_pagamentos.setItem(
                linha,
                1,
                QTableWidgetItem(formatar_centavos(pagamento.valor_centavos)),
            )

        total_pago = calcular_total_pago(self.estado_pagamentos)
        saldo = calcular_saldo_restante(self.estado_pagamentos)
        self.rotulo_total_pago.setText(formatar_centavos(total_pago))
        self.rotulo_saldo.setText(formatar_centavos(saldo))
        self.botao_concluir.setEnabled(
            esta_integralmente_pago(self.estado_pagamentos)
        )
        self.botao_dividir.setEnabled(saldo > 0)
        self.campo_partes.setMaximum(
            max(1, min(saldo, MAXIMO_INTEIRO_QT))
        )
        self.botao_adicionar.setEnabled(
            saldo > 0 and self._indice_edicao is None
        )

    def _atualizar_botoes_de_edicao(self) -> None:
        editando = self._indice_edicao is not None
        saldo = calcular_saldo_restante(self.estado_pagamentos)
        self.botao_adicionar.setEnabled(saldo > 0 and not editando)
        self.botao_editar.setEnabled(editando)
        self.botao_remover.setEnabled(editando)

    def _limpar_sugestao_divisao(self) -> None:
        self.sugestoes_divisao = ()
        self.rotulo_sugestao.clear()

    def _mostrar_erro(self, erro: Exception) -> None:
        self.rotulo_erro.setText(str(erro))
