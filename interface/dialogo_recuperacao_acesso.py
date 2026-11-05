from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from repositories.usuario_repository import EstadoIdentidadeInconsistenteError
from services.autenticacao_service import TentativasLoginExcedidasError
from services.recuperacao_acesso_service import (
    LIMITADOR_RECUPERACAO_PADRAO,
    NovaSenhaInvalidaError,
    RecuperacaoAcessoInvalidaError,
    recuperar_acesso_administrativo,
)


class DialogoRecuperacaoAcesso(QDialog):
    def __init__(
        self,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
        *,
        limitador=LIMITADOR_RECUPERACAO_PADRAO,
    ) -> None:
        super().__init__(parent)
        self.caminho_banco = caminho_banco
        self.limitador = limitador
        self.setModal(True)
        self.setWindowTitle("Recuperar acesso administrativo")

        layout = QVBoxLayout(self)
        aviso = QLabel(
            "Use um código de recuperação ainda não utilizado. Depois da "
            "troca será necessário entrar com a nova senha."
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        formulario = QFormLayout()
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_recuperacao")
        self.campo_codigo = QLineEdit()
        self.campo_codigo.setObjectName("codigo_recuperacao")
        self.campo_codigo.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_nova_senha = QLineEdit()
        self.campo_nova_senha.setObjectName("nova_senha_recuperacao")
        self.campo_nova_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao = QLineEdit()
        self.campo_confirmacao.setObjectName("confirmacao_senha_recuperacao")
        self.campo_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao.returnPressed.connect(self.recuperar)
        formulario.addRow("Administrador:", self.campo_identificacao)
        formulario.addRow("Código:", self.campo_codigo)
        formulario.addRow("Nova senha:", self.campo_nova_senha)
        formulario.addRow("Confirmar senha:", self.campo_confirmacao)
        layout.addLayout(formulario)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_recuperacao")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Redefinir senha"
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Cancelar"
        )
        self.botoes.accepted.connect(self.recuperar)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

    def recuperar(self) -> None:
        try:
            recuperar_acesso_administrativo(
                self.campo_identificacao.text(),
                self.campo_codigo.text(),
                self.campo_nova_senha.text(),
                self.campo_confirmacao.text(),
                self.caminho_banco,
                limitador=self.limitador,
            )
        except NovaSenhaInvalidaError as erro:
            self._limpar_segredos()
            self.rotulo_mensagem.setText(str(erro))
            return
        except (RecuperacaoAcessoInvalidaError, TentativasLoginExcedidasError) as erro:
            self._limpar_segredos()
            self.rotulo_mensagem.setText(str(erro))
            return
        except EstadoIdentidadeInconsistenteError:
            self._limpar_segredos()
            self.rotulo_mensagem.setText(
                "A configuração de identidade está inconsistente. "
                "A recuperação foi bloqueada."
            )
            return
        except Exception:
            self._limpar_segredos()
            self.rotulo_mensagem.setText(
                "Não foi possível concluir a recuperação. Nenhuma sessão foi aberta."
            )
            return

        self._limpar_segredos()
        self.accept()

    def _limpar_segredos(self) -> None:
        self.campo_codigo.clear()
        self.campo_nova_senha.clear()
        self.campo_confirmacao.clear()
