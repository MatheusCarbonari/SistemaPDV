from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
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
        self.setModal(True)
        self.setWindowTitle("Solicitar cancelamento")

        layout = QVBoxLayout(self)
        aviso = QLabel(
            "Esta etapa apenas prepara a solicitação. O cancelamento depende "
            "de autorização real, ainda não implementada na INT-D2."
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

        self.botao_prosseguir = QPushButton("Prosseguir para autorização")
        self.botao_prosseguir.setObjectName("prosseguir_autorizacao_cancelamento")
        self.botao_fechar = QPushButton("Desistir")
        self.botao_fechar.setObjectName("fechar_solicitacao_cancelamento")
        layout.addWidget(self.botao_prosseguir)
        layout.addWidget(self.botao_fechar)

        self.botao_prosseguir.clicked.connect(self.preparar_solicitacao)
        self.botao_fechar.clicked.connect(self.reject)

    def preparar_solicitacao(self) -> None:
        motivo = self.campo_motivo.toPlainText().strip()
        if not motivo:
            self.rotulo_mensagem.setText(
                "Informe o motivo antes de solicitar autorização."
            )
            self.campo_motivo.setFocus()
            return

        self.autorizacao_requerida.emit(self.venda.venda_id, motivo)
        self.rotulo_mensagem.setText(
            "Motivo validado. A venda não foi cancelada. A execução permanece "
            "bloqueada até a autorização real da INT-D2."
        )
        self.campo_motivo.setReadOnly(True)
        self.botao_prosseguir.setEnabled(False)
        self.botao_fechar.setText("Fechar")
