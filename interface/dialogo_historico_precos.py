from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.conexao import CAMINHO_BANCO
from interface.formatacao import formatar_centavos
from models.produto import Produto
from models.sessao_usuario import SessaoUsuario
from services.historico_preco_service import consultar_historico_precos


FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class DialogoHistoricoPrecos(QDialog):
    """Consulta somente leitura do histórico persistido pelo T44."""

    def __init__(
        self,
        sessao_administrativa: SessaoUsuario,
        produto: Produto,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.sessao_administrativa = sessao_administrativa
        self.produto = produto
        self.caminho_banco = caminho_banco
        self.setWindowTitle("Histórico de preços")
        self.setObjectName("dialogo_historico_precos")
        self.setModal(True)
        self.resize(720, 480)
        self.setMinimumSize(560, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        rotulo_produto = QLabel(f"{produto.codigo} — {produto.nome}")
        rotulo_produto.setObjectName("produto_historico_precos")
        layout.addWidget(rotulo_produto)
        linha_periodo = QHBoxLayout()
        linha_periodo.addWidget(QLabel("Período:"))
        self.combo_periodo = QComboBox()
        self.combo_periodo.setObjectName("periodo_historico_precos")
        self.combo_periodo.setMaximumWidth(220)
        self.combo_periodo.addItem("Últimos 12 meses", 12)
        self.combo_periodo.addItem("Todo o histórico", None)
        linha_periodo.addWidget(self.combo_periodo)
        linha_periodo.addStretch()
        layout.addLayout(linha_periodo)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_historico_precos")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.tabela = QTableWidget(0, 3)
        self.tabela.setObjectName("tabela_historico_precos")
        self.tabela.setHorizontalHeaderLabels(
            ("Data/hora", "Preço anterior", "Preço novo")
        )
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
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
        cabecalho.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        layout.addWidget(self.tabela)
        layout.addWidget(
            QLabel("Responsável não registrado pela estrutura do T44.")
        )

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botoes.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)
        self.combo_periodo.currentIndexChanged.connect(self.carregar)
        self._aplicar_tema_escuro()
        self.carregar()

    def carregar(self) -> None:
        try:
            registros = consultar_historico_precos(
                self.sessao_administrativa,
                self.produto.id,
                self.caminho_banco,
                meses=self.combo_periodo.currentData(),
            )
        except Exception:
            self.tabela.setRowCount(0)
            self.rotulo_mensagem.setText(
                "Não foi possível consultar o histórico de preços. "
                "Confirme a sessão administrativa e tente novamente."
            )
            return

        self.tabela.setRowCount(len(registros))
        for linha, registro in enumerate(registros):
            valores = (
                registro.alterado_em.astimezone(FUSO_SAO_PAULO).strftime(
                    "%d/%m/%Y %H:%M:%S"
                ),
                formatar_centavos(registro.preco_anterior_centavos),
                formatar_centavos(registro.preco_novo_centavos),
            )
            for coluna, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if coluna in (1, 2):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.tabela.setItem(linha, coluna, item)
        self.rotulo_mensagem.setText(
            f"{len(registros)} alteração(ões) encontrada(s)."
            if registros
            else "Nenhuma alteração de preço encontrada no período."
        )

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
            QDialog#dialogo_historico_precos { background: #171a1f; color: #e8edf2; }
            QLabel { color: #e3e8ed; }
            QLabel#produto_historico_precos {
                color: #f7fbff; font-size: 16px; font-weight: 700;
                background: #1d3040; border: 1px solid #4d83aa;
                border-radius: 5px; padding: 8px 10px;
            }
            QLabel#mensagem_historico_precos { color: #c7d0d8; }
            QComboBox {
                color: #f5f7fa; background: #23272e; border: 1px solid #5b6570;
                border-radius: 5px; min-height: 32px; padding: 2px 8px;
            }
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
                border-radius: 5px; min-height: 32px; padding: 3px 12px;
            }
            QPushButton:hover:enabled { background: #353c44; border-color: #687684; }
            """
        )
