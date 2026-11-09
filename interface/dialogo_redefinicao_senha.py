from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from services.usuario_service import redefinir_senha_conta_caixa


class DialogoRedefinicaoSenha(QDialog):
    """Coleta uma nova credencial sem expor ou solicitar a senha anterior."""

    def __init__(
        self,
        sessao_administrativa: SessaoUsuario,
        usuario_id: int,
        identificacao_operador: str,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.sessao_administrativa = sessao_administrativa
        self.usuario_id = usuario_id
        self.identificacao_operador = identificacao_operador
        self.caminho_banco = caminho_banco
        self.usuario_redefinido = None
        self.setWindowTitle("Redefinir senha do operador")
        self.setObjectName("dialogo_redefinicao_senha_caixa")
        self.resize(520, 300)
        self.setMinimumSize(440, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        self.rotulo_operador = QLabel(
            f"Operador Caixa: {identificacao_operador}"
        )
        self.rotulo_operador.setObjectName("operador_redefinicao_senha")
        layout.addWidget(self.rotulo_operador)
        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_redefinicao_senha")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        formulario = QFormLayout()
        self.campo_nova_senha = QLineEdit()
        self.campo_nova_senha.setObjectName("nova_senha_caixa")
        self.campo_nova_senha.setMaximumWidth(320)
        self.campo_nova_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao = QLineEdit()
        self.campo_confirmacao.setObjectName("confirmacao_nova_senha_caixa")
        self.campo_confirmacao.setMaximumWidth(320)
        self.campo_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao.returnPressed.connect(self.redefinir)
        formulario.addRow("Nova senha:", self.campo_nova_senha)
        formulario.addRow("Confirmar nova senha:", self.campo_confirmacao)
        layout.addLayout(formulario)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_salvar = self.botoes.button(
            QDialogButtonBox.StandardButton.Save
        )
        self.botao_salvar.setText("Redefinir senha")
        self.botoes.accepted.connect(self.redefinir)
        self.botoes.rejected.connect(self.reject)
        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch()
        linha_botoes.addWidget(self.botoes)
        layout.addLayout(linha_botoes)
        self._aplicar_tema_escuro()

    def redefinir(self) -> None:
        if not self.botao_salvar.isEnabled():
            return
        self.botao_salvar.setEnabled(False)
        try:
            usuario, erros = redefinir_senha_conta_caixa(
                self.sessao_administrativa,
                self.usuario_id,
                self.campo_nova_senha.text(),
                self.campo_confirmacao.text(),
                self.caminho_banco,
            )
        except Exception:
            self.rotulo_mensagem.setText(
                "Não foi possível redefinir a senha. "
                "Confirme a sessão administrativa e tente novamente."
            )
            self._limpar_senhas()
            self.botao_salvar.setEnabled(True)
            return

        self._limpar_senhas()
        if erros:
            self.rotulo_mensagem.setText("\n".join(erros))
            self.botao_salvar.setEnabled(True)
            return
        self.usuario_redefinido = usuario
        self.accept()

    def done(self, resultado: int) -> None:
        self._limpar_senhas()
        super().done(resultado)

    def _limpar_senhas(self) -> None:
        self.campo_nova_senha.clear()
        self.campo_confirmacao.clear()

    def _aplicar_tema_escuro(self) -> None:
        self.setStyleSheet(
            """
            QDialog#dialogo_redefinicao_senha_caixa {
                background: #171a1f; color: #e8edf2;
            }
            QLabel { color: #e3e8ed; }
            QLabel#operador_redefinicao_senha {
                color: #f7fbff; font-size: 16px; font-weight: 700;
                background: #1d3040; border: 1px solid #4d83aa;
                border-radius: 5px; padding: 8px 10px;
            }
            QLabel#mensagem_redefinicao_senha { color: #ffb8b1; }
            QLineEdit {
                color: #f5f7fa; background: #23272e; border: 1px solid #5b6570;
                border-radius: 5px; min-height: 32px; padding: 2px 8px;
            }
            QLineEdit:focus { border: 2px solid #4aa3df; }
            QPushButton {
                color: #e8edf2; background: #2a2f36; border: 1px solid #525d68;
                border-radius: 5px; min-height: 32px; padding: 3px 12px;
            }
            QPushButton:hover:enabled { background: #353c44; border-color: #687684; }
            QPushButton:disabled { color: #929ba4; background: #22262c; }
            """
        )
