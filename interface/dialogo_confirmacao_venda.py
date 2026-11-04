from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from interface.formatacao import formatar_centavos
from models.pagamento import PagamentosEmAndamento
from models.venda_em_andamento import VendaEmAndamento
from services.confirmacao_venda_service import (
    confirmar_venda,
    validar_confirmacao_venda,
)
from services.venda_em_andamento_service import calcular_total


class DialogoConfirmacaoVenda(QDialog):
    venda_confirmada = Signal(object)

    def __init__(
        self,
        venda: VendaEmAndamento,
        pagamentos: PagamentosEmAndamento,
        parent=None,
    ) -> None:
        super().__init__(parent)
        validar_confirmacao_venda(venda, pagamentos)
        self.venda = venda
        self.pagamentos = pagamentos
        self._confirmacao_em_processamento = False
        self.setWindowTitle("Confirmar venda")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Revise os dados antes de confirmar a venda."))

        resumo = QFormLayout()
        self.rotulo_total = QLabel(formatar_centavos(calcular_total(venda)))
        self.rotulo_total.setObjectName("total_confirmacao_venda")
        resumo.addRow("Total da venda:", self.rotulo_total)
        layout.addLayout(resumo)

        self.tabela_pagamentos = QTableWidget(
            len(pagamentos.pagamentos),
            2,
        )
        self.tabela_pagamentos.setObjectName("pagamentos_confirmacao_venda")
        self.tabela_pagamentos.setHorizontalHeaderLabels(
            ["Modalidade", "Valor"]
        )
        self.tabela_pagamentos.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela_pagamentos.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.tabela_pagamentos.horizontalHeader().setStretchLastSection(True)
        for linha, pagamento in enumerate(pagamentos.pagamentos):
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
        layout.addWidget(self.tabela_pagamentos)

        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setObjectName("erro_confirmacao_venda")
        layout.addWidget(self.rotulo_erro)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_confirmar = self.botoes.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.botao_confirmar.setText("Confirmar venda")
        self.botao_confirmar.setObjectName("confirmar_venda")
        self.botao_confirmar.setDefault(True)
        self.botao_confirmar.setAutoDefault(True)
        botao_cancelar = self.botoes.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        botao_cancelar.setText("Cancelar")
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

    def keyPressEvent(self, evento) -> None:
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            evento.accept()
            return
        super().keyPressEvent(evento)

    def accept(self) -> None:
        if self._confirmacao_em_processamento:
            return

        self._confirmacao_em_processamento = True
        self.botao_confirmar.setEnabled(False)
        try:
            resultado = confirmar_venda(self.venda, self.pagamentos)
        except (TypeError, ValueError) as erro:
            self._confirmacao_em_processamento = False
            self.botao_confirmar.setEnabled(True)
            self.rotulo_erro.setText(str(erro))
            return

        self.venda_confirmada.emit(resultado)
        super().accept()
