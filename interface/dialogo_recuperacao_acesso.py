from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from interface.estilo_dialogos import (
    aplicar_padrao_dialogo,
    configurar_campo_texto,
    atualizar_apresentacao_mensagem,
)
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
        aplicar_padrao_dialogo(
            self,
            nome="dialogo_recuperacao_acesso",
            tamanho=(590, 480),
            minimo=(520, 440),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        titulo = QLabel("Recuperar acesso administrativo")
        titulo.setProperty("papelVisual", "titulo")
        layout.addWidget(titulo)
        aviso = QLabel(
            "Use um código de recuperação ainda não utilizado. Depois da "
            "troca será necessário entrar com a nova senha."
        )
        aviso.setWordWrap(True)
        aviso.setProperty("papelVisual", "instrucao")
        layout.addWidget(aviso)

        grupo = QGroupBox("Código e nova credencial")
        formulario = QFormLayout(grupo)
        formulario.setContentsMargins(14, 18, 14, 12)
        formulario.setHorizontalSpacing(16)
        formulario.setVerticalSpacing(9)
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_recuperacao")
        configurar_campo_texto(self.campo_identificacao)
        self.campo_codigo = QLineEdit()
        self.campo_codigo.setObjectName("codigo_recuperacao")
        self.campo_codigo.setEchoMode(QLineEdit.EchoMode.Password)
        configurar_campo_texto(self.campo_codigo)
        self.campo_nova_senha = QLineEdit()
        self.campo_nova_senha.setObjectName("nova_senha_recuperacao")
        self.campo_nova_senha.setEchoMode(QLineEdit.EchoMode.Password)
        configurar_campo_texto(self.campo_nova_senha)
        self.campo_confirmacao = QLineEdit()
        self.campo_confirmacao.setObjectName("confirmacao_senha_recuperacao")
        self.campo_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        configurar_campo_texto(self.campo_confirmacao)
        self.campo_confirmacao.returnPressed.connect(self.recuperar)
        formulario.addRow("Administrador:", self.campo_identificacao)
        formulario.addRow("Código:", self.campo_codigo)
        formulario.addRow("Nova senha:", self.campo_nova_senha)
        formulario.addRow("Confirmar senha:", self.campo_confirmacao)
        layout.addWidget(grupo)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_recuperacao")
        self.rotulo_mensagem.setWordWrap(True)
        self.rotulo_mensagem.setProperty("papelVisual", "mensagem")
        self.rotulo_mensagem.setProperty("semMensagem", True)
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
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setProperty(
            "papelVisual", "principal"
        )
        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch()
        linha_botoes.addWidget(self.botoes)
        layout.addLayout(linha_botoes)

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
            atualizar_apresentacao_mensagem(self.rotulo_mensagem, str(erro))
            return
        except (RecuperacaoAcessoInvalidaError, TentativasLoginExcedidasError) as erro:
            self._limpar_segredos()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem, str(erro))
            return
        except EstadoIdentidadeInconsistenteError:
            self._limpar_segredos()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "A configuração de identidade está inconsistente. "
                "A recuperação foi bloqueada."
            )
            return
        except Exception:
            self._limpar_segredos()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "Não foi possível concluir a recuperação. Nenhuma sessão foi aberta."
            )
            return

        self._limpar_segredos()
        self.accept()

    def _limpar_segredos(self) -> None:
        self.campo_codigo.clear()
        self.campo_nova_senha.clear()
        self.campo_confirmacao.clear()
