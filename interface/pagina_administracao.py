from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
        self._blocos_empilhados: bool | None = None
        self.setObjectName("pagina_administracao")
        self._aplicar_tema_escuro()

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        self.area_rolagem = QScrollArea(self)
        self.area_rolagem.setFrameShape(QFrame.Shape.NoFrame)
        self.area_rolagem.setWidgetResizable(True)
        self.area_rolagem.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.conteudo = QWidget(self.area_rolagem)
        layout = QVBoxLayout(self.conteudo)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(9)
        titulo = QLabel("Administração de operadores Caixa")
        titulo.setObjectName("titulo_administracao")
        layout.addWidget(titulo)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_administracao")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.grupo_operadores = QGroupBox("Operadores cadastrados")
        layout_operadores = QVBoxLayout(self.grupo_operadores)
        layout_operadores.setContentsMargins(10, 14, 10, 9)
        layout_operadores.setSpacing(7)

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
        self.tabela_operadores.setAlternatingRowColors(True)
        self.tabela_operadores.verticalHeader().setVisible(False)
        self.tabela_operadores.verticalHeader().setDefaultSectionSize(30)
        cabecalho = self.tabela_operadores.horizontalHeader()
        cabecalho.setStretchLastSection(False)
        for coluna in range(3):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.Fixed)
        self.tabela_operadores.itemSelectionChanged.connect(
            self._atualizar_acao_situacao
        )
        layout_operadores.addWidget(self.tabela_operadores)

        linha_acoes = QHBoxLayout()
        self.botao_atualizar = QPushButton("Atualizar lista")
        self.botao_atualizar.setObjectName("atualizar_operadores")
        self.botao_situacao = QPushButton("Alterar situação")
        self.botao_situacao.setObjectName("alterar_situacao_operador")
        self.botao_situacao.setEnabled(False)
        self.botao_redefinir_senha = QPushButton("Redefinir senha")
        self.botao_redefinir_senha.setObjectName("redefinir_senha_operador")
        self.botao_redefinir_senha.setEnabled(False)
        for botao in (
            self.botao_atualizar,
            self.botao_situacao,
            self.botao_redefinir_senha,
        ):
            botao.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        linha_acoes.addWidget(self.botao_atualizar)
        linha_acoes.addWidget(self.botao_situacao)
        linha_acoes.addWidget(self.botao_redefinir_senha)
        linha_acoes.addStretch()
        layout_operadores.addLayout(linha_acoes)

        self.grupo_cadastro = QGroupBox("Cadastrar operador")
        layout_cadastro = QVBoxLayout(self.grupo_cadastro)
        layout_cadastro.setContentsMargins(10, 14, 10, 9)
        layout_cadastro.setSpacing(8)
        formulario = QGridLayout()
        formulario.setHorizontalSpacing(8)
        formulario.setVerticalSpacing(4)
        self.campo_identificacao = QLineEdit()
        self.campo_identificacao.setObjectName("identificacao_novo_caixa")
        self.campo_identificacao.setFixedSize(320, 30)
        self.campo_senha = QLineEdit()
        self.campo_senha.setObjectName("senha_inicial_novo_caixa")
        self.campo_senha.setFixedSize(320, 30)
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao = QLineEdit()
        self.campo_confirmacao.setObjectName("confirmacao_senha_novo_caixa")
        self.campo_confirmacao.setFixedSize(320, 30)
        self.campo_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao.returnPressed.connect(self.cadastrar_operador)
        campos = (
            ("Identificação", self.campo_identificacao),
            ("Senha inicial", self.campo_senha),
            ("Confirmar senha", self.campo_confirmacao),
        )
        for linha, (rotulo, campo) in enumerate(campos):
            formulario.addWidget(QLabel(rotulo), linha * 2, 0)
            formulario.addWidget(campo, linha * 2 + 1, 0)
        formulario.setColumnStretch(1, 1)
        layout_cadastro.addLayout(formulario)

        self.botao_cadastrar = QPushButton("Cadastrar operador Caixa")
        self.botao_cadastrar.setObjectName("cadastrar_operador_caixa")
        self.botao_cadastrar.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        linha_cadastrar = QHBoxLayout()
        linha_cadastrar.addWidget(self.botao_cadastrar)
        linha_cadastrar.addStretch()
        layout_cadastro.addLayout(linha_cadastrar)
        self.grupo_cadastro.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.layout_blocos = QGridLayout()
        self.layout_blocos.setHorizontalSpacing(10)
        self.layout_blocos.setVerticalSpacing(8)
        self.layout_blocos.setColumnStretch(0, 1)
        self.layout_blocos.setColumnStretch(1, 1)
        layout.addLayout(self.layout_blocos, 1)
        self.area_rolagem.setWidget(self.conteudo)
        layout_raiz.addWidget(self.area_rolagem)

        self.botao_atualizar.clicked.connect(self.atualizar_lista)
        self.botao_situacao.clicked.connect(self.alterar_situacao_selecionada)
        self.botao_redefinir_senha.clicked.connect(
            self.redefinir_senha_selecionada
        )
        self.botao_cadastrar.clicked.connect(self.cadastrar_operador)
        self._ajustar_layout_responsivo(self.width())

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        if hasattr(self, "layout_blocos"):
            self._ajustar_layout_responsivo(evento.size().width())
            QTimer.singleShot(0, self._ajustar_larguras_tabela)

    def _ajustar_layout_responsivo(self, largura: int) -> None:
        empilhar = largura < 850
        if empilhar == self._blocos_empilhados:
            return
        if empilhar:
            self.layout_blocos.addWidget(
                self.grupo_operadores,
                0,
                0,
                1,
                2,
            )
            self.layout_blocos.addWidget(
                self.grupo_cadastro,
                1,
                0,
                1,
                2,
                Qt.AlignmentFlag.AlignTop,
            )
        else:
            self.layout_blocos.addWidget(self.grupo_operadores, 0, 0)
            self.layout_blocos.addWidget(
                self.grupo_cadastro,
                0,
                1,
                Qt.AlignmentFlag.AlignTop,
            )
        self._blocos_empilhados = empilhar

    def _ajustar_larguras_tabela(self) -> None:
        largura = self.tabela_operadores.viewport().width()
        if largura < 280:
            return
        identificacao = int(largura * 0.54)
        perfil = int(largura * 0.22)
        self.tabela_operadores.setColumnWidth(0, identificacao)
        self.tabela_operadores.setColumnWidth(1, perfil)
        self.tabela_operadores.setColumnWidth(
            2,
            largura - identificacao - perfil,
        )

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
                if coluna in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabela_operadores.setItem(linha, coluna, item)
        self.botao_situacao.setEnabled(False)
        self.botao_redefinir_senha.setEnabled(False)
        self.rotulo_mensagem.setText(
            f"{len(operadores)} operador(es) Caixa cadastrado(s)."
        )
        QTimer.singleShot(0, self._ajustar_larguras_tabela)

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

    def _aplicar_tema_escuro(self) -> None:
        self.setAutoFillBackground(True)
        paleta = self.palette()
        paleta.setColor(QPalette.ColorRole.Window, QColor("#171a1f"))
        paleta.setColor(QPalette.ColorRole.Base, QColor("#181b20"))
        paleta.setColor(QPalette.ColorRole.AlternateBase, QColor("#22272e"))
        paleta.setColor(QPalette.ColorRole.Text, QColor("#f1f4f7"))
        paleta.setColor(QPalette.ColorRole.Highlight, QColor("#2f75a6"))
        paleta.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(paleta)
        self.setStyleSheet(
            """
            QWidget#pagina_administracao { background: #171a1f; color: #e8edf2; }
            QLabel { color: #e3e8ed; background: transparent; }
            QLabel#titulo_administracao { color: #f7fbff; font-size: 20px; font-weight: 700; }
            QLabel#mensagem_administracao { color: #c7d0d8; padding: 2px 4px; }
            QGroupBox {
                color: #dce4ea; border: 1px solid #404850;
                border-radius: 6px; margin-top: 9px; font-weight: 700;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit {
                color: #f5f7fa; background: #23272e; border: 1px solid #5b6570;
                border-radius: 5px; min-height: 26px; max-height: 26px;
                padding: 1px 7px;
            }
            QLineEdit:focus { border: 2px solid #4aa3df; }
            QTableWidget {
                color: #f1f4f7; background: #181b20;
                alternate-background-color: #22272e;
                selection-color: #ffffff; selection-background-color: #2f75a6;
                border: 1px solid #424a53; gridline-color: #343b43;
            }
            QHeaderView::section {
                color: #f4f6f8; background: #2b3038; border: 0;
                border-right: 1px solid #424a53; border-bottom: 1px solid #4a535d;
                padding: 6px; font-weight: 700;
            }
            QPushButton {
                color: #e8edf2; background: #2a2f36; border: 1px solid #525d68;
                border-radius: 5px; min-height: 32px; padding: 3px 11px;
            }
            QPushButton:hover:enabled { background: #353c44; border-color: #687684; }
            QPushButton:disabled { color: #929ba4; background: #22262c; }
            QPushButton#cadastrar_operador_caixa {
                color: #e8f4ff; background: #245477; border-color: #4d8fbd;
                font-weight: 700;
            }
            """
        )
