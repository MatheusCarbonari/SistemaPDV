from zoneinfo import ZoneInfo

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{produto.codigo} — {produto.nome}"))
        linha_periodo = QHBoxLayout()
        linha_periodo.addWidget(QLabel("Período:"))
        self.combo_periodo = QComboBox()
        self.combo_periodo.setObjectName("periodo_historico_precos")
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
        self.tabela.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela)
        layout.addWidget(
            QLabel("Responsável não registrado pela estrutura do T44.")
        )

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)
        self.combo_periodo.currentIndexChanged.connect(self.carregar)
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
                self.tabela.setItem(linha, coluna, QTableWidgetItem(valor))
        self.rotulo_mensagem.setText(
            f"{len(registros)} alteração(ões) encontrada(s)."
            if registros
            else "Nenhuma alteração de preço encontrada no período."
        )
