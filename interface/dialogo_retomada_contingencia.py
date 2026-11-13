"""Confirmação administrativa para retomada operacional do T54."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from interface.estilo_dialogos import (
    aplicar_padrao_dialogo,
    configurar_campo_texto,
)


class DialogoRetomadaContingencia(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Confirmar retomada operacional")
        aplicar_padrao_dialogo(
            self,
            nome="dialogo_retomada_contingencia",
            tamanho=(560, 390),
            minimo=(500, 350),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        titulo = QLabel("Retomar operação normal")
        titulo.setProperty("papelVisual", "titulo")
        layout.addWidget(titulo)
        instrucao = QLabel(
            "A verificação técnica foi satisfatória. Informe credenciais "
            "de Administrador para reconstruir o catálogo e liberar gravações."
        )
        instrucao.setWordWrap(True)
        instrucao.setProperty("papelVisual", "instrucao")
        layout.addWidget(instrucao)

        grupo = QGroupBox("Revalidação administrativa")
        formulario = QFormLayout(grupo)
        formulario.setContentsMargins(14, 18, 14, 12)
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_retomada")
        configurar_campo_texto(self.campo_identificacao)
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_retomada")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        configurar_campo_texto(self.campo_senha)
        formulario.addRow("Administrador:", self.campo_identificacao)
        formulario.addRow("Senha:", self.campo_senha)
        layout.addWidget(grupo)

        self.confirmacao = QCheckBox(
            "Confirmo que os cálculos da contingência não foram registrados "
            "como vendas."
        )
        self.confirmacao.setObjectName("confirmar_retomada")
        layout.addWidget(self.confirmacao)

        alerta = QLabel(
            "A retomada não persiste automaticamente itens, pagamentos ou "
            "tentativas anteriores."
        )
        alerta.setWordWrap(True)
        alerta.setProperty("papelVisual", "destaque")
        layout.addWidget(alerta)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Confirmar retomada"
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Manter contingência"
        )
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

    def dados_confirmacao(self) -> tuple[str, str, bool]:
        return (
            self.campo_identificacao.text(),
            self.campo_senha.text(),
            self.confirmacao.isChecked(),
        )

    def limpar_senha(self) -> None:
        self.campo_senha.clear()
