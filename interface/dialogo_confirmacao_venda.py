from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from interface.formatacao import formatar_centavos
from interface.estilo_dialogos import (
    aplicar_padrao_dialogo,
    atualizar_apresentacao_mensagem,
)
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
        aplicar_padrao_dialogo(
            self,
            nome="dialogo_confirmacao_venda",
            tamanho=(620, 500),
            minimo=(540, 430),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        titulo = QLabel("Confirmar venda")
        titulo.setProperty("papelVisual", "titulo")
        layout.addWidget(titulo)
        instrucao = QLabel(
            "Revise o total e os pagamentos. A venda será registrada somente "
            "após esta confirmação."
        )
        instrucao.setWordWrap(True)
        instrucao.setProperty("papelVisual", "instrucao")
        layout.addWidget(instrucao)

        grupo_total = QGroupBox("Resumo financeiro")
        resumo = QFormLayout(grupo_total)
        resumo.setContentsMargins(14, 18, 14, 12)
        self.rotulo_total = QLabel(formatar_centavos(calcular_total(venda)))
        self.rotulo_total.setObjectName("total_confirmacao_venda")
        self.rotulo_total.setProperty("papelVisual", "destaque")
        resumo.addRow("Total da venda:", self.rotulo_total)
        layout.addWidget(grupo_total)

        grupo_pagamentos = QGroupBox("Pagamentos confirmados")
        layout_pagamentos = QVBoxLayout(grupo_pagamentos)
        layout_pagamentos.setContentsMargins(10, 16, 10, 10)
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
        cabecalho = self.tabela_pagamentos.horizontalHeader()
        cabecalho.setStretchLastSection(False)
        cabecalho.setSectionResizeMode(0, cabecalho.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(1, cabecalho.ResizeMode.ResizeToContents)
        self.tabela_pagamentos.setMinimumHeight(120)
        for linha, pagamento in enumerate(pagamentos.pagamentos):
            self.tabela_pagamentos.setItem(
                linha,
                0,
                QTableWidgetItem(pagamento.modalidade),
            )
            valor_item = QTableWidgetItem(
                formatar_centavos(pagamento.valor_centavos)
            )
            valor_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.tabela_pagamentos.setItem(
                linha,
                1,
                valor_item,
            )
        layout_pagamentos.addWidget(self.tabela_pagamentos)
        layout.addWidget(grupo_pagamentos, 1)

        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setObjectName("erro_confirmacao_venda")
        self.rotulo_erro.setWordWrap(True)
        self.rotulo_erro.setProperty("papelVisual", "mensagem")
        self.rotulo_erro.setProperty("semMensagem", True)
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
        self.botao_confirmar.setProperty("papelVisual", "principal")
        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch()
        linha_botoes.addWidget(self.botoes)
        layout.addLayout(linha_botoes)

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
            atualizar_apresentacao_mensagem(self.rotulo_erro, str(erro))
            return

        self.venda_confirmada.emit(resultado)
        super().accept()
