from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import EstadoIdentidadeInconsistenteError
from services.autenticacao_service import (
    CredenciaisInvalidasError,
    LIMITADOR_LOGIN_PADRAO,
    TentativasLoginExcedidasError,
)
from services.autorizacao_pontual_service import (
    GERENCIADOR_AUTORIZACOES,
    GerenciadorAutorizacoesPontuais,
)


class DialogoAutorizacaoAdministrativa(QDialog):
    """Emite uma capacidade pontual sem trocar a sessão operacional."""

    def __init__(
        self,
        sessao_solicitante: SessaoUsuario,
        operacao: str,
        recurso_id: int,
        descricao_operacao: str,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
        *,
        dados_autorizados_hash: str | None = None,
        gerenciador: GerenciadorAutorizacoesPontuais = GERENCIADOR_AUTORIZACOES,
        limitador=LIMITADOR_LOGIN_PADRAO,
    ) -> None:
        super().__init__(parent)
        self.sessao_solicitante = sessao_solicitante
        self.operacao = operacao
        self.recurso_id = recurso_id
        self.caminho_banco = caminho_banco
        self.dados_autorizados_hash = dados_autorizados_hash
        self.gerenciador = gerenciador
        self.limitador = limitador
        self.capacidade = None
        self.setModal(True)
        self.setWindowTitle("Autorização administrativa")

        layout = QVBoxLayout(self)
        descricao = QLabel(descricao_operacao)
        descricao.setObjectName("descricao_operacao_critica")
        descricao.setWordWrap(True)
        layout.addWidget(descricao)

        formulario = QFormLayout()
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_autorizador")
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_autorizador")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.returnPressed.connect(self.autorizar)
        formulario.addRow("Administrador:", self.campo_identificacao)
        formulario.addRow("Senha:", self.campo_senha)
        layout.addLayout(formulario)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_autorizacao")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Autorizar uma vez"
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Cancelar"
        )
        self.botoes.accepted.connect(self.autorizar)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

    def autorizar(self) -> None:
        try:
            capacidade = self.gerenciador.emitir(
                self.sessao_solicitante,
                self.operacao,
                self.recurso_id,
                self.campo_identificacao.text(),
                self.campo_senha.text(),
                self.caminho_banco,
                dados_autorizados_hash=self.dados_autorizados_hash,
                limitador=self.limitador,
            )
        except (CredenciaisInvalidasError, TentativasLoginExcedidasError) as erro:
            self.campo_senha.clear()
            self.rotulo_mensagem.setText(str(erro))
            return
        except EstadoIdentidadeInconsistenteError:
            self.campo_senha.clear()
            self.rotulo_mensagem.setText(
                "A configuração de identidade está inconsistente. "
                "A autorização foi negada."
            )
            return
        except Exception:
            self.campo_senha.clear()
            self.rotulo_mensagem.setText(
                "Não foi possível autorizar a operação."
            )
            return

        self.capacidade = capacidade
        self.campo_senha.clear()
        self.accept()
