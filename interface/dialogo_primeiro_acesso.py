from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from repositories.usuario_repository import (
    AdministradorJaConfiguradoError,
    EstadoIdentidadeInconsistenteError,
)
from services.administrador_inicial_service import criar_administrador_inicial


class DialogoPrimeiroAcesso(QDialog):
    """Configura o administrador inicial sem iniciar uma sessão."""

    def __init__(self, caminho_banco=CAMINHO_BANCO, parent=None) -> None:
        super().__init__(parent)
        self.caminho_banco = caminho_banco
        self.administrador_criado = None
        self.setModal(True)
        self.setWindowTitle("Configuração inicial do administrador")

        layout = QVBoxLayout(self)
        explicacao = QLabel(
            "Crie o administrador inicial. Não existe senha padrão. Após esta "
            "configuração, será necessário autenticar a conta para abrir o PDV."
        )
        explicacao.setWordWrap(True)
        explicacao.setObjectName("aviso_primeiro_acesso")
        layout.addWidget(explicacao)

        formulario = QFormLayout()
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_administrador")
        self.campo_identificacao.setPlaceholderText("administrador")
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_administrador")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao = QLineEdit()
        self.campo_confirmacao.setObjectName("confirmacao_senha_administrador")
        self.campo_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        formulario.addRow("Identificação de acesso:", self.campo_identificacao)
        formulario.addRow("Senha:", self.campo_senha)
        formulario.addRow("Confirmar senha:", self.campo_confirmacao)
        layout.addLayout(formulario)

        politica = QLabel(
            "Use de 12 a 128 caracteres. Frases-senha e caracteres Unicode "
            "são permitidos."
        )
        politica.setWordWrap(True)
        layout.addWidget(politica)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_primeiro_acesso")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Save).setText(
            "Criar administrador"
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Sair"
        )
        self.botoes.accepted.connect(self.criar_administrador)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

    def criar_administrador(self) -> None:
        try:
            usuario, erros = criar_administrador_inicial(
                self.campo_identificacao.text(),
                self.campo_senha.text(),
                self.campo_confirmacao.text(),
                self.caminho_banco,
            )
        except (
            AdministradorJaConfiguradoError,
            EstadoIdentidadeInconsistenteError,
        ) as erro:
            self.rotulo_mensagem.setText(str(erro))
            return
        except Exception:
            self.rotulo_mensagem.setText(
                "Não foi possível concluir a configuração inicial. "
                "Nenhuma credencial foi registrada parcialmente."
            )
            return

        if erros:
            self.rotulo_mensagem.setText("\n".join(erros))
            return

        self.administrador_criado = usuario
        self.campo_senha.clear()
        self.campo_confirmacao.clear()
        self.accept()
