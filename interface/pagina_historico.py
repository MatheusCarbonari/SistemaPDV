from collections.abc import Callable
from datetime import datetime
import sqlite3

from PySide6.QtCore import QDate, QPoint, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
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
from interface.dialogo_autorizacao_administrativa import (
    DialogoAutorizacaoAdministrativa,
)
from interface.formatacao import formatar_centavos
from interface.dialogo_solicitacao_cancelamento import (
    DialogoSolicitacaoCancelamento,
)
from models.item_venda import DESCRICAO_DIVERSOS
from models.sessao_usuario import SessaoUsuario
from models.venda_detalhada import VendaDetalhada
from models.venda_resumo import VendaResumo
import services.cancelamento_venda_service as cancelamento_venda_service
from services.autorizacao_pontual_service import (
    GERENCIADOR_AUTORIZACOES,
    OPERACAO_CANCELAR_VENDA,
    AutorizacaoPontualExpiradaError,
    AutorizacaoPontualInvalidaError,
    GerenciadorAutorizacoesPontuais,
)
from services.historico_venda_service import (
    FUSO_SAO_PAULO,
    buscar_venda_detalhada_por_id,
    buscar_venda_resumida_por_id,
    listar_vendas_resumidas_por_data,
)


class CampoDataHistorico(QDateEdit):
    """Campo compacto que abre o calendário ao receber um clique."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.calendarWidget().clicked.connect(self._selecionar_data)

    def mousePressEvent(self, evento) -> None:
        super().mousePressEvent(evento)
        if evento.button() == Qt.MouseButton.LeftButton:
            QTimer.singleShot(0, self._mostrar_calendario)

    def _mostrar_calendario(self) -> None:
        calendario = self.calendarWidget()
        calendario.setWindowFlags(Qt.WindowType.Popup)
        calendario.adjustSize()
        calendario.move(self.mapToGlobal(QPoint(0, self.height())))
        calendario.show()
        calendario.raise_()

    def _selecionar_data(self, data: QDate) -> None:
        self.setDate(data)
        self.calendarWidget().hide()


class PaginaHistorico(QWidget):
    """Página interna somente leitura para consulta de vendas persistidas."""

    def __init__(
        self,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
        *,
        operacao_bloqueada: Callable[[], bool] | None = None,
        sessao_solicitante: SessaoUsuario | None = None,
        gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
            GERENCIADOR_AUTORIZACOES
        ),
    ) -> None:
        super().__init__(parent)
        self.caminho_banco = caminho_banco
        self._operacao_bloqueada = operacao_bloqueada or (lambda: False)
        self.sessao_solicitante = sessao_solicitante
        self.gerenciador_autorizacoes = gerenciador_autorizacoes
        self.detalhe_selecionado: VendaDetalhada | None = None
        self.dialogo_cancelamento: DialogoSolicitacaoCancelamento | None = None
        self.dialogo_autorizacao: DialogoAutorizacaoAdministrativa | None = None
        self._cancelamento_em_processamento = False
        self._cancelamentos_incertos: set[int] = set()
        self._layout_detalhe_empilhado: bool | None = None
        self._layout_filtros_empilhado: bool | None = None
        self.setObjectName("pagina_historico")
        self._aplicar_tema_escuro()

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        self.area_rolagem = QScrollArea(self)
        self.area_rolagem.setObjectName("rolagem_historico")
        self.area_rolagem.setWidgetResizable(True)
        self.area_rolagem.setFrameShape(QFrame.Shape.NoFrame)
        self.area_rolagem.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.conteudo = QWidget(self.area_rolagem)
        self.conteudo.setObjectName("conteudo_historico")
        self.conteudo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored,
        )
        layout = QVBoxLayout(self.conteudo)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(9)

        titulo = QLabel("Histórico de vendas", self.conteudo)
        titulo.setObjectName("titulo_historico")
        layout.addWidget(titulo)

        grupo_filtros = QGroupBox("Consulta", self.conteudo)
        grupo_filtros.setObjectName("secao_filtros_historico")
        self.layout_filtros = QGridLayout(grupo_filtros)
        self.layout_filtros.setContentsMargins(10, 14, 10, 8)
        self.layout_filtros.setHorizontalSpacing(8)
        self.layout_filtros.setVerticalSpacing(6)
        self.rotulo_filtro_data = QLabel("Data (São Paulo)")
        self.campo_data = CampoDataHistorico()
        self.campo_data.setObjectName("data_historico")
        self.campo_data.setDisplayFormat("dd/MM/yyyy")
        largura_data = (
            self.campo_data.fontMetrics().horizontalAdvance("88/88/8888")
            + 58
        )
        self.campo_data.setFixedWidth(max(150, largura_data))
        hoje = datetime.now(FUSO_SAO_PAULO).date()
        self.campo_data.setDate(QDate(hoje.year, hoje.month, hoje.day))
        self.botao_pesquisar_data = QPushButton("Pesquisar data")
        self.botao_pesquisar_data.setObjectName("pesquisar_historico_data")

        self.rotulo_filtro_id = QLabel("Número da venda")
        self.campo_id = QLineEdit()
        self.campo_id.setObjectName("id_historico")
        self.campo_id.setPlaceholderText("Número da venda")
        self.campo_id.setMaximumWidth(160)
        self.botao_pesquisar_id = QPushButton("Pesquisar ID")
        self.botao_pesquisar_id.setObjectName("pesquisar_historico_id")
        layout.addWidget(grupo_filtros)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_historico")
        self.rotulo_mensagem.setWordWrap(True)
        self.rotulo_mensagem.setMinimumHeight(18)
        layout.addWidget(self.rotulo_mensagem)

        self.grupo_vendas = QGroupBox("Vendas encontradas", self.conteudo)
        self.grupo_vendas.setObjectName("secao_lista_vendas")
        layout_vendas = QVBoxLayout(self.grupo_vendas)
        layout_vendas.setContentsMargins(10, 14, 10, 9)
        self.tabela_vendas = QTableWidget(0, 4)
        self.tabela_vendas.setObjectName("lista_historico_vendas")
        self.tabela_vendas.setHorizontalHeaderLabels(
            ["Venda", "Data/hora local", "Total", "Situação"]
        )
        self._configurar_tabela_somente_leitura(self.tabela_vendas)
        self.tabela_vendas.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela_vendas.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._preparar_tabela_visual(self.tabela_vendas, altura_linha=30)
        cabecalho_vendas = self.tabela_vendas.horizontalHeader()
        cabecalho_vendas.setStretchLastSection(False)
        for coluna in range(4):
            cabecalho_vendas.setSectionResizeMode(
                coluna,
                QHeaderView.ResizeMode.Fixed,
            )
        self.tabela_vendas.setMinimumHeight(150)
        self.tabela_vendas.setMaximumHeight(240)
        layout_vendas.addWidget(self.tabela_vendas)

        self.grupo_detalhe = QWidget(self.conteudo)
        self.grupo_detalhe.setObjectName("secao_detalhe_venda")
        layout_detalhe = QVBoxLayout(self.grupo_detalhe)
        layout_detalhe.setContentsMargins(0, 0, 0, 0)
        layout_detalhe.setSpacing(7)
        self.rotulo_detalhe = QLabel("Selecione uma venda para ver os detalhes.")
        self.rotulo_detalhe.setObjectName("resumo_detalhe_historico")
        self.rotulo_detalhe.setWordWrap(True)
        layout_detalhe.addWidget(self.rotulo_detalhe)

        self.layout_detalhes_principais = QGridLayout()
        self.layout_detalhes_principais.setHorizontalSpacing(10)
        self.layout_detalhes_principais.setVerticalSpacing(8)

        self.grupo_itens = QGroupBox(
            "Produtos e itens vendidos",
            self.grupo_detalhe,
        )
        self.grupo_itens.setObjectName("secao_itens_historico")
        layout_itens = QVBoxLayout(self.grupo_itens)
        layout_itens.setContentsMargins(8, 13, 8, 8)
        layout_itens.setSpacing(6)
        self.tabela_itens = QTableWidget(0, 4)
        self.tabela_itens.setObjectName("itens_historico_venda")
        self.tabela_itens.setHorizontalHeaderLabels(
            [
                "Produto / descrição",
                "Quantidade / peso",
                "Preço de referência",
                "Subtotal",
            ]
        )
        self._configurar_tabela_somente_leitura(self.tabela_itens)
        self._preparar_tabela_visual(self.tabela_itens, altura_linha=30)
        cabecalho_itens = self.tabela_itens.horizontalHeader()
        cabecalho_itens.setStretchLastSection(False)
        for coluna in range(4):
            cabecalho_itens.setSectionResizeMode(
                coluna,
                QHeaderView.ResizeMode.Fixed,
            )
        self.tabela_itens.setMinimumHeight(85)
        self.tabela_itens.setMaximumHeight(85)
        layout_itens.addWidget(self.tabela_itens, 1)

        self.painel_lateral_detalhe = QWidget(self.grupo_detalhe)
        self.painel_lateral_detalhe.setObjectName("painel_lateral_historico")
        layout_lateral = QVBoxLayout(self.painel_lateral_detalhe)
        layout_lateral.setContentsMargins(0, 0, 0, 0)
        layout_lateral.setSpacing(8)

        grupo_pagamentos = QGroupBox(
            "Pagamentos originais",
            self.painel_lateral_detalhe,
        )
        grupo_pagamentos.setObjectName("secao_pagamentos_historico")
        layout_pagamentos = QVBoxLayout(grupo_pagamentos)
        layout_pagamentos.setContentsMargins(8, 13, 8, 8)
        self.tabela_pagamentos = QTableWidget(0, 3)
        self.tabela_pagamentos.setObjectName("pagamentos_historico_venda")
        self.tabela_pagamentos.setHorizontalHeaderLabels(
            ["Nº", "Modalidade", "Valor"]
        )
        self._configurar_tabela_somente_leitura(self.tabela_pagamentos)
        self._preparar_tabela_visual(self.tabela_pagamentos, altura_linha=29)
        cabecalho_pagamentos = self.tabela_pagamentos.horizontalHeader()
        cabecalho_pagamentos.setStretchLastSection(False)
        cabecalho_pagamentos.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        cabecalho_pagamentos.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        cabecalho_pagamentos.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        self.tabela_pagamentos.setMinimumHeight(125)
        self.tabela_pagamentos.setMaximumHeight(160)
        layout_pagamentos.addWidget(self.tabela_pagamentos)
        layout_lateral.addWidget(grupo_pagamentos, 1)

        grupo_cancelamento = QGroupBox(
            "Situação e cancelamento",
            self.painel_lateral_detalhe,
        )
        grupo_cancelamento.setObjectName("secao_cancelamento_historico")
        cancelamento = QGridLayout(grupo_cancelamento)
        cancelamento.setContentsMargins(8, 13, 8, 8)
        cancelamento.setHorizontalSpacing(8)
        cancelamento.setVerticalSpacing(4)
        self.rotulo_status_cancelamento = QLabel("—")
        self.rotulo_status_cancelamento.setObjectName(
            "status_cancelamento_historico"
        )
        self.rotulo_motivo_cancelamento = QLabel("—")
        self.rotulo_motivo_cancelamento.setObjectName(
            "motivo_cancelamento_historico"
        )
        self.rotulo_data_cancelamento = QLabel("—")
        self.rotulo_data_cancelamento.setObjectName(
            "data_cancelamento_historico"
        )
        self.rotulo_autorizador_cancelamento = QLabel("—")
        self.rotulo_autorizador_cancelamento.setObjectName(
            "autorizador_cancelamento_historico"
        )
        for rotulo in (
            self.rotulo_motivo_cancelamento,
            self.rotulo_data_cancelamento,
            self.rotulo_autorizador_cancelamento,
        ):
            rotulo.setWordWrap(True)
        campos_cancelamento = (
            ("Situação:", self.rotulo_status_cancelamento),
            ("Motivo:", self.rotulo_motivo_cancelamento),
            ("Cancelada em:", self.rotulo_data_cancelamento),
            ("Autorizador:", self.rotulo_autorizador_cancelamento),
        )
        for linha, (legenda, valor) in enumerate(campos_cancelamento):
            cancelamento.addWidget(QLabel(legenda), linha, 0)
            cancelamento.addWidget(valor, linha, 1)
        cancelamento.setColumnStretch(1, 1)

        self.botao_solicitar_cancelamento = QPushButton(
            "Solicitar cancelamento"
        )
        self.botao_solicitar_cancelamento.setObjectName(
            "solicitar_cancelamento"
        )
        self.botao_solicitar_cancelamento.setEnabled(False)
        self.botao_solicitar_cancelamento.setProperty("papelAcao", "alerta")
        self.botao_solicitar_cancelamento.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        cancelamento.addWidget(
            self.botao_solicitar_cancelamento,
            len(campos_cancelamento),
            0,
            1,
            2,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout_lateral.addWidget(grupo_cancelamento)

        self.layout_detalhes_principais.addWidget(self.grupo_vendas, 0, 0)
        self.layout_detalhes_principais.addWidget(
            self.painel_lateral_detalhe,
            0,
            1,
        )
        self.layout_detalhes_principais.addWidget(
            self.grupo_itens,
            1,
            0,
            1,
            2,
        )
        self.layout_detalhes_principais.setColumnStretch(0, 1)
        self.layout_detalhes_principais.setColumnStretch(1, 1)
        self.layout_detalhes_principais.setRowStretch(0, 1)
        layout_detalhe.addLayout(self.layout_detalhes_principais, 1)
        layout.addWidget(self.grupo_detalhe, 1)

        self.area_rolagem.setWidget(self.conteudo)
        layout_raiz.addWidget(self.area_rolagem)

        self.botao_pesquisar_data.clicked.connect(self.pesquisar_por_data)
        self.botao_pesquisar_id.clicked.connect(self.pesquisar_por_id)
        self.campo_id.returnPressed.connect(self.pesquisar_por_id)
        self.tabela_vendas.itemSelectionChanged.connect(
            self._carregar_venda_selecionada
        )
        self.botao_solicitar_cancelamento.clicked.connect(
            self.abrir_solicitacao_cancelamento
        )
        self._ajustar_layout_responsivo(self.width())

    def _aplicar_tema_escuro(self) -> None:
        self.setAutoFillBackground(True)
        paleta = self.palette()
        paleta.setColor(QPalette.ColorRole.Window, QColor("#171a1f"))
        paleta.setColor(QPalette.ColorRole.WindowText, QColor("#e8edf2"))
        paleta.setColor(QPalette.ColorRole.Base, QColor("#181b20"))
        paleta.setColor(QPalette.ColorRole.AlternateBase, QColor("#22272e"))
        paleta.setColor(QPalette.ColorRole.Text, QColor("#f1f4f7"))
        paleta.setColor(QPalette.ColorRole.Button, QColor("#2a2f36"))
        paleta.setColor(QPalette.ColorRole.ButtonText, QColor("#e8edf2"))
        paleta.setColor(QPalette.ColorRole.Highlight, QColor("#2f75a6"))
        paleta.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(paleta)
        self.setStyleSheet(
            """
            QWidget#pagina_historico,
            QWidget#conteudo_historico,
            QScrollArea#rolagem_historico,
            QScrollArea#rolagem_historico > QWidget > QWidget {
                color: #e8edf2;
                background: #171a1f;
            }
            QLabel#titulo_historico {
                color: #f7fbff;
                font-size: 20px;
                font-weight: 700;
            }
            QGroupBox {
                color: #e8edf2;
                background: #1d2127;
                border: 1px solid #414a53;
                border-radius: 6px;
                margin-top: 9px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLabel {
                color: #e3e8ed;
                background: transparent;
                font-weight: 400;
            }
            QLabel#resumo_detalhe_historico {
                color: #f7fbff;
                background: #1d3040;
                border: 1px solid #4d83aa;
                border-radius: 5px;
                padding: 7px 10px;
                font-weight: 700;
            }
            QLabel#mensagem_historico {
                color: #c7d0d8;
                padding: 2px 4px;
            }
            QLineEdit,
            QDateEdit {
                color: #f5f7fa;
                background: #23272e;
                selection-color: #ffffff;
                selection-background-color: #2f75a6;
                border: 1px solid #5b6570;
                border-radius: 5px;
                min-height: 32px;
                padding: 2px 8px;
            }
            QLineEdit:focus,
            QDateEdit:focus {
                border: 2px solid #4aa3df;
                padding: 1px 7px;
            }
            QDateEdit {
                padding-right: 30px;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #5b6570;
            }
            QTableWidget {
                color: #f1f4f7;
                background: #181b20;
                alternate-background-color: #22272e;
                selection-color: #ffffff;
                selection-background-color: #2f75a6;
                border: 1px solid #424a53;
                border-radius: 4px;
                gridline-color: #343b43;
            }
            QTableWidget::item {
                color: #f1f4f7;
                padding: 4px 6px;
            }
            QTableWidget QScrollBar:vertical {
                background: #20252b;
                width: 14px;
                margin: 0;
            }
            QTableWidget QScrollBar::handle:vertical {
                background: #5b6570;
                min-height: 28px;
                border-radius: 6px;
                margin: 2px;
            }
            QTableWidget QScrollBar::handle:vertical:hover {
                background: #687684;
            }
            QHeaderView::section {
                color: #f4f6f8;
                background: #2b3038;
                border: 0;
                border-right: 1px solid #424a53;
                border-bottom: 1px solid #4a535d;
                padding: 6px;
                font-weight: 700;
            }
            QPushButton {
                color: #e8edf2;
                background: #2a2f36;
                border: 1px solid #525d68;
                border-radius: 5px;
                min-height: 32px;
                padding: 3px 11px;
            }
            QPushButton:hover:enabled {
                background: #353c44;
                border-color: #687684;
            }
            QPushButton:disabled {
                color: #aab3bc;
                background: #22262c;
                border-color: #3e464e;
            }
            QPushButton[papelAcao="alerta"]:enabled {
                color: #ffe6a6;
                background: #46391f;
                border-color: #b58a2b;
                font-weight: 700;
            }
            QLabel#status_cancelamento_historico[statusVenda="ATIVA"] {
                color: #a8e6bd;
                font-weight: 700;
            }
            QLabel#status_cancelamento_historico[statusVenda="CANCELADA"] {
                color: #ffb8b1;
                font-weight: 700;
            }
            """
        )

    @staticmethod
    def _preparar_tabela_visual(
        tabela: QTableWidget,
        *,
        altura_linha: int,
    ) -> None:
        tabela.setAlternatingRowColors(True)
        tabela.verticalHeader().setVisible(False)
        tabela.verticalHeader().setDefaultSectionSize(altura_linha)

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        if hasattr(self, "layout_detalhes_principais"):
            self._ajustar_layout_responsivo(evento.size().width())
            QTimer.singleShot(0, self._ajustar_larguras_tabelas)

    def _ajustar_layout_responsivo(self, largura: int) -> None:
        empilhar_detalhe = largura < 850
        if empilhar_detalhe != self._layout_detalhe_empilhado:
            if empilhar_detalhe:
                self.layout_detalhes_principais.addWidget(
                    self.grupo_vendas,
                    0,
                    0,
                    1,
                    2,
                )
                self.layout_detalhes_principais.addWidget(
                    self.painel_lateral_detalhe,
                    1,
                    0,
                    1,
                    2,
                )
                self.layout_detalhes_principais.addWidget(
                    self.grupo_itens,
                    2,
                    0,
                    1,
                    2,
                )
            else:
                self.layout_detalhes_principais.addWidget(
                    self.grupo_vendas,
                    0,
                    0,
                )
                self.layout_detalhes_principais.addWidget(
                    self.painel_lateral_detalhe,
                    0,
                    1,
                )
                self.layout_detalhes_principais.addWidget(
                    self.grupo_itens,
                    1,
                    0,
                    1,
                    2,
                )
            self._layout_detalhe_empilhado = empilhar_detalhe
            self.layout_detalhes_principais.invalidate()

        empilhar_filtros = largura < 760
        if empilhar_filtros != self._layout_filtros_empilhado:
            if empilhar_filtros:
                posicoes = (
                    (self.rotulo_filtro_data, 0, 0),
                    (self.campo_data, 0, 1),
                    (self.botao_pesquisar_data, 0, 2),
                    (self.rotulo_filtro_id, 1, 0),
                    (self.campo_id, 1, 1),
                    (self.botao_pesquisar_id, 1, 2),
                )
            else:
                posicoes = (
                    (self.rotulo_filtro_data, 0, 0),
                    (self.campo_data, 0, 1),
                    (self.botao_pesquisar_data, 0, 2),
                    (self.rotulo_filtro_id, 0, 3),
                    (self.campo_id, 0, 4),
                    (self.botao_pesquisar_id, 0, 5),
                )
            for widget, linha, coluna in posicoes:
                self.layout_filtros.addWidget(widget, linha, coluna)
            self.layout_filtros.setColumnStretch(6, 1)
            self._layout_filtros_empilhado = empilhar_filtros
            self.layout_filtros.invalidate()
        self.conteudo.updateGeometry()
        QTimer.singleShot(0, self._sincronizar_area_rolagem)

    def _ajustar_larguras_tabelas(self) -> None:
        largura_vendas = self.tabela_vendas.viewport().width()
        if largura_vendas >= 360:
            proporcoes_vendas = (0.23, 0.34, 0.20)
            usadas = 0
            for coluna, proporcao in enumerate(proporcoes_vendas):
                largura_coluna = int(largura_vendas * proporcao)
                self.tabela_vendas.setColumnWidth(coluna, largura_coluna)
                usadas += largura_coluna
            self.tabela_vendas.setColumnWidth(3, largura_vendas - usadas)

        largura_itens = self.tabela_itens.viewport().width()
        if largura_itens >= 500:
            proporcoes_itens = (0.46, 0.20, 0.20)
            usadas = 0
            for coluna, proporcao in enumerate(proporcoes_itens):
                largura_coluna = int(largura_itens * proporcao)
                self.tabela_itens.setColumnWidth(coluna, largura_coluna)
                usadas += largura_coluna
            self.tabela_itens.setColumnWidth(3, largura_itens - usadas)

    def _sincronizar_area_rolagem(self) -> None:
        viewport = self.area_rolagem.viewport().size()
        minimo = self.conteudo.minimumSizeHint()
        self.conteudo.resize(
            max(viewport.width(), minimo.width()),
            max(viewport.height(), minimo.height()),
        )

    def restaurar_foco(self) -> None:
        QTimer.singleShot(0, self.campo_id.setFocus)

    def pesquisar_por_data(self) -> None:
        data_qt = self.campo_data.date()
        data_local = data_qt.toPython()
        try:
            vendas = listar_vendas_resumidas_por_data(
                data_local,
                self.caminho_banco,
            )
        except Exception as erro:
            self._mostrar_erro(erro)
            return

        self._preencher_vendas(vendas)
        self._cancelamentos_incertos.difference_update(
            venda.venda_id for venda in vendas
        )
        if vendas:
            self.rotulo_mensagem.setText(
                f"{len(vendas)} venda(s) encontrada(s)."
            )
        else:
            self.rotulo_mensagem.setText(
                "Nenhuma venda encontrada para a data informada."
            )

    def pesquisar_por_id(self) -> None:
        texto = self.campo_id.text().strip()
        if not texto.isascii() or not texto.isdigit() or int(texto) <= 0:
            self._mostrar_erro(
                ValueError("Informe um ID de venda inteiro e positivo.")
            )
            return

        try:
            resumo = buscar_venda_resumida_por_id(
                int(texto),
                self.caminho_banco,
            )
        except Exception as erro:
            self._mostrar_erro(erro)
            return

        if resumo is None:
            self._preencher_vendas(())
            self.rotulo_mensagem.setText("Venda não encontrada.")
            return

        self._cancelamentos_incertos.discard(resumo.venda_id)
        self._preencher_vendas((resumo,))
        self.rotulo_mensagem.setText("Venda encontrada.")
        self.tabela_vendas.selectRow(0)

    def _preencher_vendas(self, vendas: tuple[VendaResumo, ...]) -> None:
        self.tabela_vendas.clearSelection()
        self.tabela_vendas.setRowCount(len(vendas))
        for linha, venda in enumerate(vendas):
            numero = QTableWidgetItem(f"Venda nº {venda.venda_id}")
            numero.setData(Qt.ItemDataRole.UserRole, venda.venda_id)
            data_local = QTableWidgetItem(
                self._formatar_data_local(venda.registrada_em)
            )
            data_local.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            total = QTableWidgetItem(formatar_centavos(venda.total_centavos))
            total.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            valores = (
                numero,
                data_local,
                total,
                self._criar_item_status(venda.status),
            )
            for coluna, item in enumerate(valores):
                self.tabela_vendas.setItem(linha, coluna, item)
        self._limpar_detalhe()
        QTimer.singleShot(0, self._ajustar_larguras_tabelas)

    def _carregar_venda_selecionada(self) -> None:
        linhas = self.tabela_vendas.selectionModel().selectedRows()
        if not linhas:
            return
        item_id = self.tabela_vendas.item(linhas[0].row(), 0)
        venda_id = item_id.data(Qt.ItemDataRole.UserRole)
        try:
            detalhe = buscar_venda_detalhada_por_id(
                venda_id,
                self.caminho_banco,
            )
        except Exception as erro:
            self._mostrar_erro(erro, limpar_lista=False)
            return

        if detalhe is None:
            self.rotulo_mensagem.setText(
                "A venda selecionada não está mais disponível."
            )
            self._limpar_detalhe()
            return

        self._preencher_detalhe(detalhe)

    def _preencher_detalhe(self, detalhe: VendaDetalhada) -> None:
        self.detalhe_selecionado = detalhe
        resumo = detalhe.resumo
        self.rotulo_detalhe.setText(
            f"Venda nº {resumo.venda_id} — "
            f"{self._formatar_data_local(resumo.registrada_em)} — "
            f"{formatar_centavos(resumo.total_centavos)} — {resumo.status}"
        )
        self.tabela_itens.setRowCount(len(detalhe.itens))
        for linha, detalhado in enumerate(detalhe.itens):
            item = detalhado.item
            snapshot = item.produto
            descricao = (
                snapshot.nome
                if snapshot is not None
                else (
                    DESCRICAO_DIVERSOS
                    if item.tipo_item == "DIVERSOS"
                    else "Item sem descrição"
                )
            )
            valores = (
                descricao,
                self._formatar_quantidade(item),
                (
                    formatar_centavos(snapshot.preco_referencia_centavos)
                    if snapshot is not None
                    else "—"
                ),
                formatar_centavos(item.subtotal_centavos),
            )
            for coluna, valor in enumerate(valores):
                item_tabela = QTableWidgetItem(valor)
                if coluna in (2, 3):
                    item_tabela.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                elif coluna == 1:
                    item_tabela.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )
                self.tabela_itens.setItem(linha, coluna, item_tabela)

        altura_itens = max(
            85,
            min(160, 34 + len(detalhe.itens) * 30),
        )
        self.tabela_itens.setMinimumHeight(altura_itens)
        self.tabela_itens.setMaximumHeight(altura_itens)

        self.tabela_pagamentos.setRowCount(len(detalhe.pagamentos))
        for linha, pagamento in enumerate(detalhe.pagamentos):
            numero_pagamento = QTableWidgetItem(str(linha + 1))
            numero_pagamento.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabela_pagamentos.setItem(
                linha,
                0,
                numero_pagamento,
            )
            self.tabela_pagamentos.setItem(
                linha,
                1,
                QTableWidgetItem(pagamento.modalidade),
            )
            valor_pagamento = QTableWidgetItem(
                formatar_centavos(pagamento.valor_centavos)
            )
            valor_pagamento.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.tabela_pagamentos.setItem(linha, 2, valor_pagamento)

        self._definir_status_cancelamento(resumo.status)
        self.rotulo_motivo_cancelamento.setText(
            resumo.motivo_cancelamento or "—"
        )
        self.rotulo_data_cancelamento.setText(
            self._formatar_data_local(resumo.cancelada_em)
            if resumo.cancelada_em is not None
            else "—"
        )
        self.rotulo_autorizador_cancelamento.setText(
            resumo.autorizador_identidade or "—"
        )
        self.botao_solicitar_cancelamento.setEnabled(
            resumo.status == "ATIVA"
            and self.sessao_solicitante is not None
            and not self._operacao_bloqueada()
            and not self._cancelamento_em_processamento
            and resumo.venda_id not in self._cancelamentos_incertos
        )
        QTimer.singleShot(0, self._sincronizar_area_rolagem)
        QTimer.singleShot(0, self._ajustar_larguras_tabelas)

    def _definir_status_cancelamento(self, status: str) -> None:
        self.rotulo_status_cancelamento.setText(status)
        self.rotulo_status_cancelamento.setProperty("statusVenda", status)
        estilo = self.rotulo_status_cancelamento.style()
        estilo.unpolish(self.rotulo_status_cancelamento)
        estilo.polish(self.rotulo_status_cancelamento)

    def abrir_solicitacao_cancelamento(self) -> None:
        if self._operacao_bloqueada():
            self.rotulo_mensagem.setText(
                "Resolva o fechamento pendente antes de solicitar cancelamento."
            )
            return
        detalhe = self.detalhe_selecionado
        if detalhe is None:
            self.rotulo_mensagem.setText(
                "Selecione uma venda ativa para solicitar cancelamento."
            )
            return
        if detalhe.status != "ATIVA":
            self.rotulo_mensagem.setText(
                "A venda selecionada já está cancelada."
            )
            return

        dialogo = DialogoSolicitacaoCancelamento(detalhe, self)
        self.dialogo_cancelamento = dialogo
        dialogo.autorizacao_requerida.connect(
            lambda venda_id, motivo: self._iniciar_autorizacao(
                dialogo,
                venda_id,
                motivo,
            )
        )
        dialogo.finished.connect(
            lambda: self._finalizar_dialogo_cancelamento(dialogo)
        )
        dialogo.open()

    def _iniciar_autorizacao(
        self,
        dialogo_solicitacao: DialogoSolicitacaoCancelamento,
        venda_id: int,
        motivo: str,
    ) -> None:
        if self._cancelamento_em_processamento:
            return
        if self._operacao_bloqueada():
            dialogo_solicitacao.permitir_nova_tentativa(
                "O cancelamento foi bloqueado por um fechamento pendente."
            )
            return
        if self.sessao_solicitante is None:
            dialogo_solicitacao.permitir_nova_tentativa(
                "A sessão solicitante não está autenticada."
            )
            return

        self._cancelamento_em_processamento = True
        dialogo = DialogoAutorizacaoAdministrativa(
            self.sessao_solicitante,
            OPERACAO_CANCELAR_VENDA,
            venda_id,
            f"Autorizar cancelamento da venda #{venda_id:06d}",
            self.caminho_banco,
            dialogo_solicitacao,
            gerenciador=self.gerenciador_autorizacoes,
        )
        self.dialogo_autorizacao = dialogo
        dialogo.finished.connect(
            lambda resultado: self._finalizar_autorizacao(
                dialogo_solicitacao,
                dialogo,
                venda_id,
                motivo,
                resultado,
            )
        )
        dialogo.open()

    def _finalizar_autorizacao(
        self,
        dialogo_solicitacao: DialogoSolicitacaoCancelamento,
        dialogo_autorizacao: DialogoAutorizacaoAdministrativa,
        venda_id: int,
        motivo: str,
        resultado: int,
    ) -> None:
        if self.dialogo_autorizacao is dialogo_autorizacao:
            self.dialogo_autorizacao = None
        dialogo_autorizacao.deleteLater()

        if resultado != QDialog.DialogCode.Accepted:
            self._cancelamento_em_processamento = False
            dialogo_solicitacao.permitir_nova_tentativa(
                "Autorização cancelada. A venda permanece ativa."
            )
            return
        if dialogo_autorizacao.capacidade is None:
            self._cancelamento_em_processamento = False
            dialogo_solicitacao.permitir_nova_tentativa(
                "A autorização não produziu uma capacidade válida."
            )
            return
        if self._operacao_bloqueada():
            self._invalidar_capacidade_nao_utilizada(
                dialogo_autorizacao.capacidade,
                venda_id,
            )
            self._cancelamento_em_processamento = False
            dialogo_solicitacao.permitir_nova_tentativa(
                "O cancelamento foi bloqueado por um fechamento pendente. "
                "Solicite uma nova autorização após resolvê-lo."
            )
            return

        try:
            cancelamento_venda_service.cancelar_venda(
                venda_id,
                motivo,
                dialogo_autorizacao.capacidade,
                self.sessao_solicitante,
                self.caminho_banco,
                gerenciador_autorizacoes=self.gerenciador_autorizacoes,
            )
        except AutorizacaoPontualExpiradaError:
            self._permitir_nova_autorizacao(
                dialogo_solicitacao,
                "A autorização expirou. Solicite uma nova autorização.",
            )
            return
        except AutorizacaoPontualInvalidaError:
            self._permitir_nova_autorizacao(
                dialogo_solicitacao,
                "A autorização não é mais válida. Solicite uma nova autorização.",
            )
            return
        except cancelamento_venda_service.VendaNaoEncontradaError:
            self._cancelamento_em_processamento = False
            dialogo_solicitacao.reject()
            self.rotulo_mensagem.setText(
                "A venda não foi encontrada e não pôde ser cancelada."
            )
            return
        except cancelamento_venda_service.VendaJaCanceladaError:
            self._cancelamento_em_processamento = False
            dialogo_solicitacao.reject()
            self._atualizar_venda_apos_cancelamento(venda_id)
            self.rotulo_mensagem.setText("A venda já estava cancelada.")
            return
        except cancelamento_venda_service.CancelamentoVendaIncertoError:
            self._registrar_resultado_incerto(
                dialogo_solicitacao,
                venda_id,
            )
            return
        except cancelamento_venda_service.CancelamentoVendaNaoPersistidoError:
            self._permitir_nova_autorizacao(
                dialogo_solicitacao,
                "A falha foi confirmada e o cancelamento não foi concluído. "
                "Solicite uma nova autorização para tentar novamente.",
            )
            return
        except sqlite3.Error:
            self._permitir_nova_autorizacao(
                dialogo_solicitacao,
                "Falha no banco de dados confirmada. O cancelamento não foi "
                "concluído; solicite nova autorização para tentar novamente.",
            )
            return
        except Exception:
            self._registrar_resultado_incerto(
                dialogo_solicitacao,
                venda_id,
            )
            return

        self._cancelamento_em_processamento = False
        dialogo_solicitacao.accept()
        self._atualizar_venda_apos_cancelamento(venda_id)
        self.rotulo_mensagem.setText(
            f"Venda #{venda_id:06d} cancelada com sucesso."
        )

    def _permitir_nova_autorizacao(
        self,
        dialogo: DialogoSolicitacaoCancelamento,
        mensagem: str,
    ) -> None:
        self._cancelamento_em_processamento = False
        dialogo.permitir_nova_tentativa(mensagem)

    def _registrar_resultado_incerto(
        self,
        dialogo: DialogoSolicitacaoCancelamento,
        venda_id: int,
    ) -> None:
        self._cancelamento_em_processamento = False
        self._cancelamentos_incertos.add(venda_id)
        dialogo.reject()
        try:
            self._atualizar_venda_apos_cancelamento(venda_id)
        except Exception:
            # A atualização é apenas uma consulta auxiliar e não pode substituir
            # nem ocultar o resultado incerto informado pelo serviço.
            pass
        self.rotulo_mensagem.setText(
            "O resultado do cancelamento não pôde ser confirmado. Consulte ou "
            "atualize o Histórico antes de qualquer nova ação; a autorização "
            "já foi consumida."
        )

    def _invalidar_capacidade_nao_utilizada(
        self,
        capacidade,
        venda_id: int,
    ) -> None:
        try:
            self.gerenciador_autorizacoes.consumir(
                capacidade,
                self.sessao_solicitante,
                OPERACAO_CANCELAR_VENDA,
                venda_id,
                self.caminho_banco,
            )
        except Exception:
            # O gerenciador remove a capacidade antes das demais validações.
            pass

    def _atualizar_venda_apos_cancelamento(self, venda_id: int) -> None:
        resumo = buscar_venda_resumida_por_id(venda_id, self.caminho_banco)
        if resumo is None:
            self._limpar_detalhe()
            return

        for linha in range(self.tabela_vendas.rowCount()):
            item_id = self.tabela_vendas.item(linha, 0)
            if item_id.data(Qt.ItemDataRole.UserRole) == venda_id:
                self.tabela_vendas.setItem(
                    linha,
                    3,
                    self._criar_item_status(resumo.status),
                )
                break

        detalhe = buscar_venda_detalhada_por_id(venda_id, self.caminho_banco)
        if detalhe is not None:
            self._preencher_detalhe(detalhe)

    def _finalizar_dialogo_cancelamento(
        self,
        dialogo: DialogoSolicitacaoCancelamento,
    ) -> None:
        if self.dialogo_cancelamento is dialogo:
            self.dialogo_cancelamento = None
        if self.dialogo_autorizacao is not None:
            self.dialogo_autorizacao.reject()
        dialogo.deleteLater()
        self.restaurar_foco()

    def _limpar_detalhe(self) -> None:
        self.detalhe_selecionado = None
        self.rotulo_detalhe.setText(
            "Selecione uma venda para ver os detalhes."
        )
        self.tabela_itens.setRowCount(0)
        self.tabela_itens.setMinimumHeight(85)
        self.tabela_itens.setMaximumHeight(85)
        self.tabela_pagamentos.setRowCount(0)
        self._definir_status_cancelamento("—")
        self.rotulo_motivo_cancelamento.setText("—")
        self.rotulo_data_cancelamento.setText("—")
        self.rotulo_autorizador_cancelamento.setText("—")
        self.botao_solicitar_cancelamento.setEnabled(False)
        QTimer.singleShot(0, self._sincronizar_area_rolagem)

    def _mostrar_erro(
        self,
        erro: Exception,
        *,
        limpar_lista: bool = True,
    ) -> None:
        self.rotulo_mensagem.setText(str(erro))
        if limpar_lista:
            self._preencher_vendas(())
        else:
            self._limpar_detalhe()

    @staticmethod
    def _configurar_tabela_somente_leitura(tabela: QTableWidget) -> None:
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabela.setSortingEnabled(False)

    @staticmethod
    def _criar_item_status(status: str) -> QTableWidgetItem:
        item = QTableWidgetItem(status)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        fonte = item.font()
        fonte.setBold(True)
        item.setFont(fonte)
        cor = "#a8e6bd" if status == "ATIVA" else "#ffb8b1"
        item.setForeground(QBrush(QColor(cor)))
        return item

    @staticmethod
    def _formatar_data_local(data: datetime) -> str:
        return data.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M:%S")

    @staticmethod
    def _formatar_quantidade(item) -> str:
        if item.quantidade is None:
            return "Não informada"
        sufixo = ""
        if item.produto is not None:
            if item.produto.forma_venda == "PESO":
                sufixo = " kg"
            elif item.produto.forma_venda == "UNIDADE":
                sufixo = " un."
        estimativa = (
            " (estimada)" if item.origem_quantidade == "ESTIMADA" else ""
        )
        return f"{format(item.quantidade, 'f')}{sufixo}{estimativa}"
