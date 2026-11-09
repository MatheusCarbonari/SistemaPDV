from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
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
        self._processando = False
        self.setModal(True)
        self.setWindowTitle("Solicitar cancelamento")
        self.setObjectName("dialogo_solicitacao_cancelamento")
        self.resize(560, 430)
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        aviso = QLabel(
            "Informe o motivo e solicite autorização para cancelar esta venda."
        )
        aviso.setObjectName("aviso_autorizacao_cancelamento")
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        resumo = venda.resumo
        painel_resumo = QFrame(self)
        painel_resumo.setObjectName("resumo_solicitacao_cancelamento")
        formulario = QFormLayout(painel_resumo)
        formulario.setContentsMargins(12, 10, 12, 10)
        formulario.setHorizontalSpacing(18)
        formulario.setVerticalSpacing(5)
        self.rotulo_id = QLabel(f"Venda nº {resumo.venda_id}")
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
        self.rotulo_itens.setObjectName("quantidade_itens_solicitacao")
        self.rotulo_pagamentos = QLabel(str(len(venda.pagamentos)))
        self.rotulo_pagamentos.setObjectName(
            "quantidade_pagamentos_solicitacao"
        )
        formulario.addRow("Venda:", self.rotulo_id)
        formulario.addRow("Data/hora:", self.rotulo_data)
        formulario.addRow("Total:", self.rotulo_total)
        formulario.addRow("Situação:", self.rotulo_status)
        formulario.addRow("Quantidade de itens:", self.rotulo_itens)
        formulario.addRow("Quantidade de pagamentos:", self.rotulo_pagamentos)
        layout.addWidget(painel_resumo)

        rotulo_motivo = QLabel("Motivo obrigatório:")
        rotulo_motivo.setObjectName("rotulo_motivo_cancelamento")
        layout.addWidget(rotulo_motivo)
        self.campo_motivo = QPlainTextEdit()
        self.campo_motivo.setObjectName("motivo_solicitacao_cancelamento")
        self.campo_motivo.setPlaceholderText(
            "Informe por que a venda deverá ser cancelada"
        )
        self.campo_motivo.setMinimumHeight(72)
        self.campo_motivo.setMaximumHeight(96)
        layout.addWidget(self.campo_motivo)

        dependencia = QLabel(
            "O cancelamento só será executado após autorização administrativa."
        )
        dependencia.setObjectName("dependencia_autorizacao_cancelamento")
        dependencia.setWordWrap(True)
        layout.addWidget(dependencia)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_solicitacao_cancelamento")
        self.rotulo_mensagem.setWordWrap(True)
        self.rotulo_mensagem.setMinimumHeight(20)
        layout.addWidget(self.rotulo_mensagem)
        layout.addStretch(1)

        self.botao_prosseguir = QPushButton(
            "Solicitar autorização administrativa"
        )
        self.botao_prosseguir.setObjectName("prosseguir_autorizacao_cancelamento")
        self.botao_fechar = QPushButton("Desistir")
        self.botao_fechar.setObjectName("fechar_solicitacao_cancelamento")
        self.botao_prosseguir.setMinimumHeight(32)
        self.botao_fechar.setMinimumHeight(32)
        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        botoes.addStretch(1)
        botoes.addWidget(self.botao_fechar)
        botoes.addWidget(self.botao_prosseguir)
        layout.addLayout(botoes)

        self.setStyleSheet(
            """
            QDialog#dialogo_solicitacao_cancelamento {
                color: #e3e8ed;
                background: #15191e;
            }
            QLabel { color: #e3e8ed; }
            QLabel#aviso_autorizacao_cancelamento {
                color: #f7fbff;
                font-size: 15px;
                font-weight: 700;
            }
            QFrame#resumo_solicitacao_cancelamento {
                background: #20262c;
                border: 1px solid #46515c;
                border-radius: 6px;
            }
            QLabel#dependencia_autorizacao_cancelamento {
                color: #f0c66c;
                background: #352e20;
                border: 1px solid #806a35;
                border-radius: 5px;
                padding: 7px 9px;
            }
            QLabel#mensagem_solicitacao_cancelamento { color: #ffb8b1; }
            QPlainTextEdit {
                color: #f5f7fa;
                background: #23272e;
                selection-color: #ffffff;
                selection-background-color: #2f75a6;
                border: 1px solid #5b6570;
                border-radius: 5px;
                padding: 6px;
            }
            QPlainTextEdit:focus { border: 2px solid #4aa3df; }
            QPushButton {
                color: #e8edf2;
                background: #2a2f36;
                border: 1px solid #525d68;
                border-radius: 5px;
                padding: 4px 12px;
            }
            QPushButton:hover:enabled {
                background: #353c44;
                border-color: #687684;
            }
            QPushButton#prosseguir_autorizacao_cancelamento {
                color: #ffe6a6;
                background: #46391f;
                border-color: #b58a2b;
                font-weight: 700;
            }
            QPushButton:disabled {
                color: #929ba4;
                background: #22262c;
                border-color: #3e464e;
            }
            """
        )

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
