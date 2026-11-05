from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from interface.dialogo_recuperacao_acesso import DialogoRecuperacaoAcesso
from repositories.usuario_repository import EstadoIdentidadeInconsistenteError
from services.autenticacao_service import (
    CredenciaisInvalidasError,
    LIMITADOR_LOGIN_PADRAO,
    TentativasLoginExcedidasError,
    autenticar_usuario,
)
from services.recuperacao_acesso_service import LIMITADOR_RECUPERACAO_PADRAO


class DialogoLogin(QDialog):
    def __init__(
        self,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
        *,
        limitador=LIMITADOR_LOGIN_PADRAO,
        limitador_recuperacao=LIMITADOR_RECUPERACAO_PADRAO,
    ) -> None:
        super().__init__(parent)
        self.caminho_banco = caminho_banco
        self.limitador = limitador
        self.limitador_recuperacao = limitador_recuperacao
        self.sessao = None
        self.dialogo_recuperacao = None
        self.setModal(True)
        self.setWindowTitle("Entrar no Sistema-PDV")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Informe sua identificação e senha."))
        formulario = QFormLayout()
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_login")
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_login")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.returnPressed.connect(self.entrar)
        formulario.addRow("Identificação:", self.campo_identificacao)
        formulario.addRow("Senha:", self.campo_senha)
        layout.addLayout(formulario)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_login")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.botao_recuperar = QPushButton("Recuperar acesso")
        self.botao_recuperar.setObjectName("recuperar_acesso")
        self.botao_recuperar.clicked.connect(self.abrir_recuperacao)
        layout.addWidget(self.botao_recuperar)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        self.botoes.accepted.connect(self.entrar)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

    def abrir_recuperacao(self) -> None:
        if self.dialogo_recuperacao is not None:
            return
        dialogo = DialogoRecuperacaoAcesso(
            self.caminho_banco,
            self,
            limitador=self.limitador_recuperacao,
        )
        self.dialogo_recuperacao = dialogo
        dialogo.finished.connect(
            lambda resultado: self._finalizar_recuperacao(dialogo, resultado)
        )
        dialogo.open()

    def _finalizar_recuperacao(self, dialogo, resultado: int) -> None:
        if self.dialogo_recuperacao is dialogo:
            self.dialogo_recuperacao = None
        dialogo.deleteLater()
        self.campo_senha.clear()
        if resultado == QDialog.DialogCode.Accepted:
            self.rotulo_mensagem.setText(
                "Senha redefinida. Entre novamente com a nova senha."
            )
            self.campo_senha.setFocus()

    def entrar(self) -> None:
        try:
            sessao = autenticar_usuario(
                self.campo_identificacao.text(),
                self.campo_senha.text(),
                self.caminho_banco,
                limitador=self.limitador,
            )
        except (CredenciaisInvalidasError, TentativasLoginExcedidasError) as erro:
            self.campo_senha.clear()
            self.rotulo_mensagem.setText(str(erro))
            self.campo_senha.setFocus()
            return
        except EstadoIdentidadeInconsistenteError:
            self.campo_senha.clear()
            self.rotulo_mensagem.setText(
                "A configuração de identidade está inconsistente. "
                "O acesso foi bloqueado com segurança."
            )
            return
        except Exception:
            self.campo_senha.clear()
            self.rotulo_mensagem.setText(
                "Não foi possível validar as credenciais. O acesso foi bloqueado."
            )
            return

        self.sessao = sessao
        self.campo_senha.clear()
        self.accept()
