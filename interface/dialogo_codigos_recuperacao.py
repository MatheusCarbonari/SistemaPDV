from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from interface.estilo_dialogos import (
    aplicar_padrao_dialogo,
    configurar_campo_texto,
    atualizar_apresentacao_mensagem,
)
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import EstadoIdentidadeInconsistenteError
from services.autenticacao_service import (
    GERENCIADOR_SESSOES,
    LIMITADOR_LOGIN_PADRAO,
    CredenciaisInvalidasError,
    GerenciadorSessoes,
    TentativasLoginExcedidasError,
)
from services.recuperacao_acesso_service import emitir_ou_rotacionar_codigos


class DialogoCodigosRecuperacao(QDialog):
    def __init__(
        self,
        sessao_administrativa: SessaoUsuario,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
        *,
        gerenciador_sessoes: GerenciadorSessoes = GERENCIADOR_SESSOES,
        limitador=LIMITADOR_LOGIN_PADRAO,
    ) -> None:
        super().__init__(parent)
        self.sessao_administrativa = sessao_administrativa
        self.caminho_banco = caminho_banco
        self.gerenciador_sessoes = gerenciador_sessoes
        self.limitador = limitador
        self.setModal(True)
        self.setWindowTitle("Códigos de recuperação")
        aplicar_padrao_dialogo(
            self,
            nome="dialogo_codigos_recuperacao",
            tamanho=(640, 520),
            minimo=(540, 450),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        titulo = QLabel("Códigos de recuperação")
        titulo.setProperty("papelVisual", "titulo")
        layout.addWidget(titulo)
        aviso = QLabel(
            "Confirme sua senha para gerar um novo conjunto. A emissão invalida "
            "os códigos anteriores. Guarde os novos códigos fora do computador; "
            "eles não poderão ser exibidos novamente."
        )
        aviso.setWordWrap(True)
        aviso.setProperty("papelVisual", "instrucao")
        layout.addWidget(aviso)

        grupo_emissao = QGroupBox("Confirmar identidade")
        layout_emissao = QVBoxLayout(grupo_emissao)
        layout_emissao.setContentsMargins(14, 18, 14, 12)
        layout_emissao.setSpacing(9)
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_emissao_codigos")
        self.campo_senha.setPlaceholderText("Senha administrativa atual")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        configurar_campo_texto(self.campo_senha)
        self.campo_senha.returnPressed.connect(self.emitir)
        layout_emissao.addWidget(self.campo_senha, 0, Qt.AlignmentFlag.AlignLeft)

        self.botao_emitir = QPushButton("Gerar ou rotacionar códigos")
        self.botao_emitir.setObjectName("emitir_codigos_recuperacao")
        self.botao_emitir.clicked.connect(self.emitir)
        layout_emissao.addWidget(self.botao_emitir, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(grupo_emissao)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_emissao_codigos")
        self.rotulo_mensagem.setWordWrap(True)
        self.rotulo_mensagem.setProperty("papelVisual", "mensagem")
        self.rotulo_mensagem.setProperty("semMensagem", True)
        layout.addWidget(self.rotulo_mensagem)

        self.grupo_codigos = QGroupBox("Novo conjunto — guarde em local seguro")
        layout_codigos = QVBoxLayout(self.grupo_codigos)
        layout_codigos.setContentsMargins(14, 18, 14, 12)
        self.campo_codigos = QPlainTextEdit()
        self.campo_codigos.setObjectName("codigos_recuperacao_emitidos")
        self.campo_codigos.setReadOnly(True)
        self.campo_codigos.setVisible(False)
        layout_codigos.addWidget(self.campo_codigos)
        self.grupo_codigos.setVisible(False)
        layout.addWidget(self.grupo_codigos, 1)

        self.botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.botoes.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        self.botoes.rejected.connect(self.reject)
        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch()
        linha_botoes.addWidget(self.botoes)
        layout.addLayout(linha_botoes)

    def emitir(self) -> None:
        if not self.botao_emitir.isEnabled():
            return
        try:
            conjunto = emitir_ou_rotacionar_codigos(
                self.sessao_administrativa,
                self.campo_senha.text(),
                self.caminho_banco,
                gerenciador_sessoes=self.gerenciador_sessoes,
                limitador=self.limitador,
            )
        except (CredenciaisInvalidasError, TentativasLoginExcedidasError) as erro:
            self.campo_senha.clear()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem, str(erro))
            return
        except EstadoIdentidadeInconsistenteError:
            self.campo_senha.clear()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "A configuração de identidade está inconsistente. "
                "Nenhum código foi emitido."
            )
            return
        except Exception:
            self.campo_senha.clear()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "Não foi possível gerar os códigos de recuperação."
            )
            return

        self.campo_senha.clear()
        self.campo_senha.setEnabled(False)
        self.botao_emitir.setEnabled(False)
        self.campo_codigos.setPlainText("\n".join(conjunto.codigos))
        self.campo_codigos.setVisible(True)
        self.grupo_codigos.setVisible(True)
        atualizar_apresentacao_mensagem(self.rotulo_mensagem,
            "Novo conjunto criado. Esta é a única apresentação dos códigos."
        )

    def done(self, resultado: int) -> None:
        self.campo_senha.clear()
        self.campo_codigos.clear()
        super().done(resultado)
