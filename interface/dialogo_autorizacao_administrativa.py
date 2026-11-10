from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
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
        aplicar_padrao_dialogo(
            self,
            nome="dialogo_autorizacao_administrativa",
            tamanho=(660, 520),
            minimo=(560, 440),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        titulo = QLabel("Autorização administrativa")
        titulo.setProperty("papelVisual", "titulo")
        layout.addWidget(titulo)
        instrucao = QLabel(
            "Revise a operação e informe as credenciais de um Administrador. "
            "A autorização vale somente para esta ação."
        )
        instrucao.setWordWrap(True)
        instrucao.setProperty("papelVisual", "instrucao")
        layout.addWidget(instrucao)

        grupo_resumo = QGroupBox("Operação solicitada")
        resumo = QVBoxLayout(grupo_resumo)
        resumo.setContentsMargins(14, 18, 14, 12)
        resumo.setSpacing(7)
        descricao = QLabel(descricao_operacao)
        descricao.setObjectName("descricao_operacao_critica")
        descricao.setWordWrap(True)
        descricao.setVisible(False)
        resumo.addWidget(descricao)
        linhas_descricao = descricao_operacao.splitlines()
        self.rotulo_operacao = QLabel(
            linhas_descricao[0] if linhas_descricao else "Operação crítica"
        )
        self.rotulo_operacao.setObjectName("titulo_operacao_critica")
        self.rotulo_operacao.setProperty("papelVisual", "destaque")
        self.rotulo_operacao.setWordWrap(True)
        resumo.addWidget(self.rotulo_operacao)
        self.grade_resumo = QGridLayout()
        self.grade_resumo.setHorizontalSpacing(12)
        self.grade_resumo.setVerticalSpacing(6)
        linha_grade = 0
        for linha in linhas_descricao[1:]:
            texto = linha.strip()
            if not texto:
                continue
            legenda, separador, valor = texto.partition(":")
            if not separador:
                legenda, valor = "Detalhe", texto
            rotulo_legenda = QLabel(f"{legenda.strip()}:")
            rotulo_valor = QLabel(valor.strip())
            rotulo_valor.setWordWrap(True)
            if legenda.strip().casefold() in {"preço", "categoria"}:
                rotulo_valor.setProperty("dadoAlterado", True)
            self.grade_resumo.addWidget(rotulo_legenda, linha_grade, 0)
            self.grade_resumo.addWidget(rotulo_valor, linha_grade, 1)
            linha_grade += 1
        self.grade_resumo.setColumnStretch(1, 1)
        resumo.addLayout(self.grade_resumo)
        layout.addWidget(grupo_resumo)

        grupo_credenciais = QGroupBox("Credenciais do Administrador")
        formulario = QFormLayout(grupo_credenciais)
        formulario.setContentsMargins(14, 18, 14, 12)
        formulario.setHorizontalSpacing(16)
        formulario.setVerticalSpacing(9)
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_autorizador")
        configurar_campo_texto(self.campo_identificacao)
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_autorizador")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        configurar_campo_texto(self.campo_senha)
        self.campo_senha.returnPressed.connect(self.autorizar)
        formulario.addRow("Administrador:", self.campo_identificacao)
        formulario.addRow("Senha:", self.campo_senha)
        layout.addWidget(grupo_credenciais)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_autorizacao")
        self.rotulo_mensagem.setWordWrap(True)
        self.rotulo_mensagem.setProperty("papelVisual", "mensagem")
        self.rotulo_mensagem.setProperty("semMensagem", True)
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
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setProperty(
            "papelVisual", "principal"
        )
        linha_botoes = QHBoxLayout()
        linha_botoes.addStretch()
        linha_botoes.addWidget(self.botoes)
        layout.addLayout(linha_botoes)

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
            atualizar_apresentacao_mensagem(self.rotulo_mensagem, str(erro))
            return
        except EstadoIdentidadeInconsistenteError:
            self.campo_senha.clear()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "A configuração de identidade está inconsistente. "
                "A autorização foi negada."
            )
            return
        except Exception:
            self.campo_senha.clear()
            atualizar_apresentacao_mensagem(self.rotulo_mensagem,
                "Não foi possível autorizar a operação."
            )
            return

        self.capacidade = capacidade
        self.campo_senha.clear()
        self.accept()
