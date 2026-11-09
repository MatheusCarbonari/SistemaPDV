from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from repositories.categoria_repository import NomeCategoriaEmUsoError
from services.categoria_service import (
    alterar_situacao_categoria,
    criar_categoria,
    listar_categorias,
    renomear_categoria,
)


class DialogoCategorias(QDialog):
    categorias_alteradas = Signal()

    def __init__(
        self,
        sessao_administrativa: SessaoUsuario,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.sessao_administrativa = sessao_administrativa
        self.caminho_banco = caminho_banco
        self.setWindowTitle("Gerenciar categorias")
        self.setObjectName("dialogo_categorias")
        self.setModal(True)
        self.resize(620, 460)
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setWordWrap(True)
        self.rotulo_mensagem.setObjectName("mensagem_categorias")
        layout.addWidget(self.rotulo_mensagem)

        self.tabela = QTableWidget(0, 2)
        self.tabela.setObjectName("lista_categorias")
        self.tabela.setHorizontalHeaderLabels(("Nome", "Situação"))
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela.setAlternatingRowColors(True)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.verticalHeader().setDefaultSectionSize(30)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setStretchLastSection(False)
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        layout.addWidget(self.tabela)

        self.campo_nome = QLineEdit()
        self.campo_nome.setObjectName("nome_categoria")
        self.campo_nome.setPlaceholderText("Nome da categoria")
        self.campo_nome.setMaximumWidth(360)
        self.campo_nome.returnPressed.connect(self.cadastrar)
        linha_nome = QHBoxLayout()
        linha_nome.addWidget(QLabel("Nome:"))
        linha_nome.addWidget(self.campo_nome)
        linha_nome.addStretch()
        layout.addLayout(linha_nome)

        acoes = QHBoxLayout()
        self.botao_cadastrar = QPushButton("Cadastrar")
        self.botao_renomear = QPushButton("Renomear")
        self.botao_situacao = QPushButton("Ativar/desativar")
        self.botao_fechar = QPushButton("Fechar")
        self.botao_renomear.setEnabled(False)
        self.botao_situacao.setEnabled(False)
        for botao in (
            self.botao_cadastrar,
            self.botao_renomear,
            self.botao_situacao,
            self.botao_fechar,
        ):
            botao.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        acoes.addWidget(self.botao_cadastrar)
        acoes.addWidget(self.botao_renomear)
        acoes.addWidget(self.botao_situacao)
        acoes.addStretch()
        acoes.addWidget(self.botao_fechar)
        layout.addLayout(acoes)

        self.botao_cadastrar.clicked.connect(self.cadastrar)
        self.botao_renomear.clicked.connect(self.renomear)
        self.botao_situacao.clicked.connect(self.alterar_situacao)
        self.botao_fechar.clicked.connect(self.accept)
        self.tabela.itemSelectionChanged.connect(self._selecionar)
        self._aplicar_tema_escuro()
        self.carregar()

    def carregar(self) -> None:
        try:
            categorias = listar_categorias(
                self.sessao_administrativa,
                self.caminho_banco,
            )
        except Exception:
            self._bloquear(
                "Não foi possível consultar as categorias. "
                "Confirme a sessão administrativa."
            )
            return
        self.tabela.setEnabled(True)
        self.botao_cadastrar.setEnabled(True)
        self.tabela.clearSelection()
        self.tabela.setRowCount(len(categorias))
        for linha, categoria in enumerate(categorias):
            nome = QTableWidgetItem(categoria.nome)
            nome.setData(Qt.ItemDataRole.UserRole, categoria)
            self.tabela.setItem(linha, 0, nome)
            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem("Ativa" if categoria.ativo else "Inativa"),
            )
            self.tabela.item(linha, 1).setTextAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
        self.rotulo_mensagem.setText(
            f"{len(categorias)} categoria(s) cadastrada(s)."
            if categorias
            else "Nenhuma categoria cadastrada. Cadastre a primeira categoria."
        )
        self._selecionar()

    def cadastrar(self) -> None:
        try:
            categoria, erros = criar_categoria(
                self.sessao_administrativa,
                self.campo_nome.text(),
                self.caminho_banco,
            )
        except NomeCategoriaEmUsoError as erro:
            self.rotulo_mensagem.setText(str(erro))
            return
        except Exception:
            self._bloquear("Não foi possível cadastrar a categoria.")
            return
        if erros:
            self.rotulo_mensagem.setText("\n".join(erros))
            return
        self.campo_nome.clear()
        self.carregar()
        self.rotulo_mensagem.setText(
            f"Categoria {categoria.nome} cadastrada com sucesso."
        )
        self.categorias_alteradas.emit()

    def renomear(self) -> None:
        categoria = self._categoria_selecionada()
        if categoria is None:
            return
        try:
            atualizada, erros = renomear_categoria(
                self.sessao_administrativa,
                categoria.id,
                self.campo_nome.text(),
                self.caminho_banco,
            )
        except NomeCategoriaEmUsoError as erro:
            self.rotulo_mensagem.setText(str(erro))
            return
        except Exception:
            self._bloquear("Não foi possível renomear a categoria.")
            return
        if erros:
            self.rotulo_mensagem.setText("\n".join(erros))
            return
        self.campo_nome.clear()
        self.carregar()
        self.rotulo_mensagem.setText(
            f"Categoria renomeada para {atualizada.nome}."
        )
        self.categorias_alteradas.emit()

    def alterar_situacao(self) -> None:
        categoria = self._categoria_selecionada()
        if categoria is None:
            return
        try:
            atualizada = alterar_situacao_categoria(
                self.sessao_administrativa,
                categoria.id,
                not categoria.ativo,
                self.caminho_banco,
            )
        except Exception:
            self._bloquear("Não foi possível alterar a categoria.")
            return
        self.campo_nome.clear()
        self.carregar()
        self.rotulo_mensagem.setText(
            f"Categoria {'ativada' if atualizada.ativo else 'desativada'}."
        )
        self.categorias_alteradas.emit()

    def _selecionar(self) -> None:
        categoria = self._categoria_selecionada()
        selecionada = categoria is not None
        self.botao_renomear.setEnabled(selecionada)
        self.botao_situacao.setEnabled(selecionada)
        if categoria is not None:
            self.campo_nome.setText(categoria.nome)
            self.botao_situacao.setText(
                "Desativar" if categoria.ativo else "Ativar"
            )

    def _categoria_selecionada(self):
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        return self.tabela.item(linhas[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )

    def _bloquear(self, mensagem: str) -> None:
        self.rotulo_mensagem.setText(mensagem)
        self.tabela.setEnabled(False)
        self.botao_cadastrar.setEnabled(False)
        self.botao_renomear.setEnabled(False)
        self.botao_situacao.setEnabled(False)

    def _aplicar_tema_escuro(self) -> None:
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
            QDialog#dialogo_categorias { background: #171a1f; color: #e8edf2; }
            QLabel { color: #e3e8ed; }
            QLabel#mensagem_categorias { color: #c7d0d8; }
            QLineEdit {
                color: #f5f7fa; background: #23272e; border: 1px solid #5b6570;
                border-radius: 5px; min-height: 32px; padding: 2px 8px;
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
            """
        )
