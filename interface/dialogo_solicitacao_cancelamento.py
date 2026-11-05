from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from interface.formatacao import formatar_centavos
from models.venda_detalhada import VendaDetalhada
from services.historico_venda_service import FUSO_SAO_PAULO


class DialogoSolicitacaoCancelamento(QDialog):
    """Coleta o motivo sem executar ou autorizar um cancelamento."""

    autorizacao_requerida = Signal(int, str)

    def __init__(self, venda: VendaDetalhada, parent=None) -> None:
        super().__init__(parent)
        self.venda = venda
        self._processando = False
        self.setModal(True)
        self.setWindowTitle("Solicitar cancelamento")

        layout = QVBoxLayout(self)
        aviso = QLabel(
            "Confirme o motivo para solicitar uma autorização administrativa "
            "de uso único. A venda só será cancelada após a autorização."
        )
        aviso.setObjectName("aviso_autorizacao_cancelamento")
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        resumo = venda.resumo
        formulario = QFormLayout()
        self.rotulo_id = QLabel(f"#{resumo.venda_id:06d}")
        self.rotulo_id.setObjectName("id_solicitacao_cancelamento")
        self.rotulo_data = QLabel(
            resumo.registrada_em.astimezone(FUSO_SAO_PAULO).strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )
        self.rotulo_data.setObjectName("data_solicitacao_cancelamento")
        self.rotulo_total = QLabel(formatar_centavos(resumo.total_centavos))
        self.rotulo_total.setObjectName("total_solicitacao_cancelamento")
        self.rotulo_status = QLabel(resumo.status)
        self.rotulo_status.setObjectName("status_solicitacao_cancelamento")
        self.rotulo_itens = QLabel(str(len(venda.itens)))
        self.rotulo_pagamentos = QLabel(str(len(venda.pagamentos)))
        formulario.addRow("Venda:", self.rotulo_id)
        formulario.addRow("Registrada em:", self.rotulo_data)
        formulario.addRow("Total:", self.rotulo_total)
        formulario.addRow("Status:", self.rotulo_status)
        formulario.addRow("Itens:", self.rotulo_itens)
        formulario.addRow("Pagamentos:", self.rotulo_pagamentos)
        layout.addLayout(formulario)

        layout.addWidget(QLabel("Itens originais:"))
        self.tabela_itens = QTableWidget(len(venda.itens), 3)
        self.tabela_itens.setObjectName("itens_solicitacao_cancelamento")
        self.tabela_itens.setHorizontalHeaderLabels(
            ["Posição", "Descrição", "Subtotal"]
        )
        self._configurar_tabela_somente_leitura(self.tabela_itens)
        for linha, item_detalhado in enumerate(venda.itens):
            item = item_detalhado.item
            descricao = (
                item.produto.nome
                if item.produto is not None
                else "Diversos" if item.tipo_item == "DIVERSOS" else "Item legado"
            )
            valores = (
                str(item_detalhado.posicao + 1),
                descricao,
                formatar_centavos(item.subtotal_centavos),
            )
            for coluna, valor in enumerate(valores):
                self.tabela_itens.setItem(linha, coluna, QTableWidgetItem(valor))
        self.tabela_itens.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_itens)

        layout.addWidget(QLabel("Pagamentos originais:"))
        self.tabela_pagamentos = QTableWidget(len(venda.pagamentos), 2)
        self.tabela_pagamentos.setObjectName(
            "pagamentos_solicitacao_cancelamento"
        )
        self.tabela_pagamentos.setHorizontalHeaderLabels(
            ["Modalidade", "Valor"]
        )
        self._configurar_tabela_somente_leitura(self.tabela_pagamentos)
        for linha, pagamento in enumerate(venda.pagamentos):
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
        self.tabela_pagamentos.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_pagamentos)

        layout.addWidget(QLabel("Motivo:"))
        self.campo_motivo = QPlainTextEdit()
        self.campo_motivo.setObjectName("motivo_solicitacao_cancelamento")
        self.campo_motivo.setPlaceholderText(
            "Informe por que a venda deverá ser cancelada"
        )
        layout.addWidget(self.campo_motivo)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_solicitacao_cancelamento")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.botao_prosseguir = QPushButton(
            "Confirmar e solicitar autorização"
        )
        self.botao_prosseguir.setObjectName("prosseguir_autorizacao_cancelamento")
        self.botao_fechar = QPushButton("Desistir")
        self.botao_fechar.setObjectName("fechar_solicitacao_cancelamento")
        layout.addWidget(self.botao_prosseguir)
        layout.addWidget(self.botao_fechar)

        self.botao_prosseguir.clicked.connect(self.preparar_solicitacao)
        self.botao_fechar.clicked.connect(self.reject)

    def preparar_solicitacao(self) -> None:
        if self._processando:
            return
        motivo = self.campo_motivo.toPlainText().strip()
        if not motivo:
            self.rotulo_mensagem.setText(
                "Informe o motivo antes de solicitar autorização."
            )
            self.campo_motivo.setFocus()
            return

        self._definir_processamento(True)
        self.autorizacao_requerida.emit(self.venda.venda_id, motivo)
        if self._processando:
            self.rotulo_mensagem.setText(
                "Aguardando autorização administrativa."
            )

    def permitir_nova_tentativa(self, mensagem: str) -> None:
        self._definir_processamento(False)
        self.rotulo_mensagem.setText(mensagem)

    def _definir_processamento(self, processando: bool) -> None:
        self._processando = processando
        self.campo_motivo.setReadOnly(processando)
        self.botao_prosseguir.setEnabled(not processando)
        self.botao_fechar.setEnabled(not processando)

    @staticmethod
    def _configurar_tabela_somente_leitura(tabela: QTableWidget) -> None:
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabela.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
