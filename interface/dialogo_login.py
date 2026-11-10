from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from interface.dialogo_recuperacao_acesso import DialogoRecuperacaoAcesso
from interface.estilo_dialogos import (
    aplicar_padrao_dialogo,
    configurar_campo_texto,
    atualizar_apresentacao_mensagem,
)
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
        aplicar_padrao_dialogo(
            self,
            nome="dialogo_login",
            tamanho=(500, 370),
            minimo=(440, 330),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        titulo = QLabel("Acessar o Sistema-PDV")
        titulo.setProperty("papelVisual", "titulo")
        layout.addWidget(titulo)
        instrucao = QLabel("Informe a identificação e a senha do operador.")
        instrucao.setProperty("papelVisual", "instrucao")
        layout.addWidget(instrucao)
        grupo = QGroupBox("Credenciais")
        formulario = QFormLayout(grupo)
        formulario.setContentsMargins(14, 18, 14, 12)
        formulario.setHorizontalSpacing(16)
        formulario.setVerticalSpacing(9)
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_login")
        configurar_campo_texto(self.campo_identificacao)
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_login")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        configurar_campo_texto(self.campo_senha)
        self.campo_senha.returnPressed.connect(self.entrar)
        formulario.addRow("Identificação:", self.campo_identificacao)
        formulario.addRow("Senha:", self.campo_senha)
        layout.addWidget(grupo)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_login")
        self.rotulo_mensagem.setWordWrap(True)
        self.rotulo_mensagem.setProperty("papelVisual", "mensagem")
        self.rotulo_mensagem.setProperty("semMensagem", True)
        layout.addWidget(self.rotulo_mensagem)

        linha_acoes = QHBoxLayout()
        self.botao_recuperar = QPushButton("Recuperar acesso")
        self.botao_recuperar.setObjectName("recuperar_acesso")
        self.botao_recuperar.setMaximumWidth(170)
        self.botao_recuperar.setAutoDefault(False)
        self.botao_recuperar.clicked.connect(self.abrir_recuperacao)
        linha_acoes.addWidget(self.botao_recuperar)
        linha_acoes.addStretch()
        layout.addLayout(linha_acoes)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        self.botoes.accepted.connect(self.entrar)
        self.botoes.rejected.connect(self.reject)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setProperty(
            "papelVisual", "principal"
        )
        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch()
        linha_botoes.addWidget(self.botoes)
        layout.addLayout(linha_botoes)

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
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
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
            atualizar_apresentacao_mensagem(self.rotulo_mensagem, str(erro))
            self.campo_senha.setFocus()
            return
        except EstadoIdentidadeInconsistenteError:
            self.campo_senha.clear()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "A configuração de identidade está inconsistente. "
                "O acesso foi bloqueado com segurança."
            )
            return
        except Exception:
            self.campo_senha.clear()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "Não foi possível validar as credenciais. O acesso foi bloqueado."
            )
            return

        self.sessao = sessao
        self.campo_senha.clear()
        self.accept()
