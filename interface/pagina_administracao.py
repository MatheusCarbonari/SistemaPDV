from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.conexao import CAMINHO_BANCO
from interface.dialogo_redefinicao_senha import DialogoRedefinicaoSenha
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import IdentificacaoUsuarioEmUsoError
from services.usuario_service import (
    alterar_situacao_conta_caixa,
    criar_conta_caixa,
    listar_contas_caixa,
)


class PaginaAdministracao(QWidget):
    """Gestão mínima de contas Caixa, protegida pelos serviços de identidade."""

    def __init__(
        self,
        sessao_administrativa: SessaoUsuario,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.sessao_administrativa = sessao_administrativa
        self.caminho_banco = caminho_banco
        self.setObjectName("pagina_administracao")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Administração de operadores Caixa"))

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_administracao")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.tabela_operadores = QTableWidget(0, 3)
        self.tabela_operadores.setObjectName("lista_operadores_caixa")
        self.tabela_operadores.setHorizontalHeaderLabels(
            ["Identificação", "Perfil", "Situação"]
        )
        self.tabela_operadores.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela_operadores.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela_operadores.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela_operadores.setSortingEnabled(False)
        self.tabela_operadores.horizontalHeader().setStretchLastSection(True)
        self.tabela_operadores.itemSelectionChanged.connect(
            self._atualizar_acao_situacao
        )
        layout.addWidget(self.tabela_operadores)

        linha_acoes = QHBoxLayout()
        self.botao_atualizar = QPushButton("Atualizar lista")
        self.botao_atualizar.setObjectName("atualizar_operadores")
        self.botao_situacao = QPushButton("Alterar situação")
        self.botao_situacao.setObjectName("alterar_situacao_operador")
        self.botao_situacao.setEnabled(False)
        self.botao_redefinir_senha = QPushButton("Redefinir senha")
        self.botao_redefinir_senha.setObjectName("redefinir_senha_operador")
        self.botao_redefinir_senha.setEnabled(False)
        linha_acoes.addWidget(self.botao_atualizar)
        linha_acoes.addWidget(self.botao_situacao)
        linha_acoes.addWidget(self.botao_redefinir_senha)
        linha_acoes.addStretch()
        layout.addLayout(linha_acoes)

        formulario = QFormLayout()
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_novo_caixa")
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_inicial_novo_caixa")
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao = QLineEdit()
        self.campo_confirmacao.setObjectName("confirmacao_senha_novo_caixa")
        self.campo_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao.returnPressed.connect(self.cadastrar_operador)
        formulario.addRow("Identificação:", self.campo_identificacao)
        formulario.addRow("Senha inicial:", self.campo_senha)
        formulario.addRow("Confirmar senha:", self.campo_confirmacao)
        layout.addLayout(formulario)

        self.botao_cadastrar = QPushButton("Cadastrar operador Caixa")
        self.botao_cadastrar.setObjectName("cadastrar_operador_caixa")
        layout.addWidget(self.botao_cadastrar)

        self.botao_atualizar.clicked.connect(self.atualizar_lista)
        self.botao_situacao.clicked.connect(self.alterar_situacao_selecionada)
        self.botao_redefinir_senha.clicked.connect(
            self.redefinir_senha_selecionada
        )
        self.botao_cadastrar.clicked.connect(self.cadastrar_operador)

    def ativar(self) -> None:
        self.atualizar_lista()
        self.campo_identificacao.setFocus()

    def atualizar_lista(self) -> None:
        try:
            operadores = listar_contas_caixa(
                self.sessao_administrativa,
                self.caminho_banco,
            )
        except Exception:
            self._bloquear_por_falha(
                "Não foi possível consultar os operadores. "
                "Confirme a sessão administrativa e tente novamente."
            )
            return

        self.tabela_operadores.setEnabled(True)
        self.botao_cadastrar.setEnabled(True)
        self.tabela_operadores.clearSelection()
        self.tabela_operadores.setRowCount(len(operadores))
        for linha, usuario in enumerate(operadores):
            identificacao = QTableWidgetItem(usuario.identificacao_acesso)
            identificacao.setData(Qt.ItemDataRole.UserRole, usuario.id)
            identificacao.setData(Qt.ItemDataRole.UserRole + 1, usuario.ativo)
            valores = (
                identificacao,
                QTableWidgetItem(usuario.perfil),
                QTableWidgetItem("Ativa" if usuario.ativo else "Inativa"),
            )
            for coluna, item in enumerate(valores):
                self.tabela_operadores.setItem(linha, coluna, item)
        self.botao_situacao.setEnabled(False)
        self.botao_redefinir_senha.setEnabled(False)
        self.rotulo_mensagem.setText(
            f"{len(operadores)} operador(es) Caixa cadastrado(s)."
        )

    def cadastrar_operador(self) -> None:
        try:
            usuario, erros = criar_conta_caixa(
                self.sessao_administrativa,
                self.campo_identificacao.text(),
                self.campo_senha.text(),
                self.campo_confirmacao.text(),
                self.caminho_banco,
            )
        except IdentificacaoUsuarioEmUsoError:
            self.rotulo_mensagem.setText(
                "A identificação informada já está em uso."
            )
            return
        except Exception:
            self._bloquear_por_falha(
                "Não foi possível cadastrar o operador. "
                "Confirme a sessão administrativa e os dados informados."
            )
            return
        finally:
            self._limpar_senhas()

        if erros:
            self.rotulo_mensagem.setText("\n".join(erros))
            return

        self.campo_identificacao.clear()
        self.atualizar_lista()
        self.rotulo_mensagem.setText(
            f"Operador {usuario.identificacao_acesso} cadastrado com sucesso."
        )

    def alterar_situacao_selecionada(self) -> None:
        selecionado = self._operador_selecionado()
        if selecionado is None:
            return
        usuario_id, ativo_atual, _ = selecionado
        try:
            usuario = alterar_situacao_conta_caixa(
                self.sessao_administrativa,
                usuario_id,
                not ativo_atual,
                self.caminho_banco,
            )
        except Exception:
            self._bloquear_por_falha(
                "Não foi possível alterar a situação do operador. "
                "Confirme a sessão administrativa e tente novamente."
            )
            return

        self.atualizar_lista()
        situacao = "ativada" if usuario.ativo else "desativada"
        self.rotulo_mensagem.setText(
            f"Conta {usuario.identificacao_acesso} {situacao} com sucesso."
        )

    def redefinir_senha_selecionada(self) -> None:
        selecionado = self._operador_selecionado()
        if selecionado is None:
            return
        usuario_id, _, identificacao = selecionado
        dialogo = DialogoRedefinicaoSenha(
            self.sessao_administrativa,
            usuario_id,
            identificacao,
            self.caminho_banco,
            self,
        )
        self.dialogo_redefinicao_senha = dialogo
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        self.atualizar_lista()
        self.rotulo_mensagem.setText(
            f"Senha do operador {identificacao} redefinida com sucesso."
        )

    def _atualizar_acao_situacao(self) -> None:
        selecionado = self._operador_selecionado()
        self.botao_situacao.setEnabled(selecionado is not None)
        self.botao_redefinir_senha.setEnabled(selecionado is not None)
        if selecionado is not None:
            _, ativo, _ = selecionado
            self.botao_situacao.setText("Desativar" if ativo else "Ativar")

    def _operador_selecionado(self) -> tuple[int, bool, str] | None:
        linhas = self.tabela_operadores.selectionModel().selectedRows()
        if not linhas:
            return None
        item = self.tabela_operadores.item(linhas[0].row(), 0)
        return (
            item.data(Qt.ItemDataRole.UserRole),
            item.data(Qt.ItemDataRole.UserRole + 1),
            item.text(),
        )

    def _bloquear_por_falha(self, mensagem: str) -> None:
        self.rotulo_mensagem.setText(mensagem)
        self.tabela_operadores.setEnabled(False)
        self.botao_situacao.setEnabled(False)
        self.botao_redefinir_senha.setEnabled(False)
        self.botao_cadastrar.setEnabled(False)
        self._limpar_senhas()

    def _limpar_senhas(self) -> None:
        self.campo_senha.clear()
        self.campo_confirmacao.clear()
