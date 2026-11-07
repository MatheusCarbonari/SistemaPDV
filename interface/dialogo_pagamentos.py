from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from interface.formatacao import (
    centavos_para_texto,
    formatar_centavos,
    ler_centavos,
)
from models.pagamento import Pagamento, PagamentosEmAndamento
from services.pagamento_service import (
    adicionar_pagamento,
    calcular_saldo_restante,
    calcular_total_pago,
    dividir_valor_igualmente,
    editar_pagamento,
    esta_integralmente_pago,
    remover_pagamento,
)


MODALIDADES_EXIBIDAS = ("DINHEIRO", "CREDITO", "DEBITO", "PIX")
MAXIMO_INTEIRO_QT = 2_147_483_647
LARGURA_INICIAL = 900
ALTURA_INICIAL = 700
LARGURA_MINIMA = 640
ALTURA_MINIMA = 480


class DialogoPagamentos(QDialog):
    pagamentos_confirmados = Signal(object)

    def __init__(
        self,
        total_venda_centavos: int,
        parent=None,
        estado_inicial: PagamentosEmAndamento | None = None,
    ) -> None:
        super().__init__(parent)
        if estado_inicial is not None:
            if not isinstance(estado_inicial, PagamentosEmAndamento):
                raise TypeError(
                    "O estado inicial deve ser PagamentosEmAndamento ou None."
                )
            if estado_inicial.total_venda_centavos != total_venda_centavos:
                raise ValueError(
                    "O estado inicial não corresponde ao total da venda."
                )
            self.estado_pagamentos = estado_inicial
        else:
            self.estado_pagamentos = PagamentosEmAndamento(
                total_venda_centavos
            )
        self._indice_edicao: int | None = None
        self._resultado_confirmado = False
        self.sugestoes_divisao: tuple[int, ...] = ()
        self._proximo_indice_sugestao = 0
        self._pagamentos_sugeridos: dict[int, Pagamento] = {}
        self._divisao_automatica_ativa = False
        self._divisao_requer_recalculo = False
        self._base_divisao_centavos: int | None = None
        self._alterando_valor_programaticamente = False
        self._tamanho_inicial_ajustado = False
        self._layout_empilhado: bool | None = None
        self.setWindowTitle("Pagamentos")
        self.setObjectName("dialogo_pagamentos")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(LARGURA_MINIMA, ALTURA_MINIMA)
        self.resize(LARGURA_INICIAL, ALTURA_INICIAL)
        self._aplicar_tema_escuro()

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(12, 10, 12, 10)
        layout_raiz.setSpacing(8)

        self.area_rolagem = QScrollArea(self)
        self.area_rolagem.setObjectName("rolagem_pagamentos")
        self.area_rolagem.setWidgetResizable(True)
        self.area_rolagem.setFrameShape(QFrame.Shape.NoFrame)
        conteudo = QWidget(self.area_rolagem)
        conteudo.setObjectName("conteudo_pagamentos")
        conteudo.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored,
        )
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(2, 2, 4, 2)
        layout.setSpacing(10)

        grupo_resumo = QGroupBox("Resumo financeiro", conteudo)
        grupo_resumo.setObjectName("secao_resumo_financeiro")
        layout_resumo = QHBoxLayout(grupo_resumo)
        layout_resumo.setContentsMargins(10, 12, 10, 6)
        layout_resumo.setSpacing(10)

        self.rotulo_total = self._criar_cartao_resumo(
            layout_resumo,
            "Total da venda",
            formatar_centavos(total_venda_centavos),
            "total_pagamentos",
        )
        self.rotulo_total.setObjectName("total_pagamentos")
        self.rotulo_total_pago = self._criar_cartao_resumo(
            layout_resumo,
            "Já pago",
            formatar_centavos(0),
            "total_pago",
        )
        self.rotulo_saldo = self._criar_cartao_resumo(
            layout_resumo,
            "Saldo restante",
            formatar_centavos(total_venda_centavos),
            "saldo_restante",
        )
        layout.addWidget(grupo_resumo)

        self.layout_colunas = QGridLayout()
        self.layout_colunas.setHorizontalSpacing(12)
        self.layout_colunas.setVerticalSpacing(10)
        self.coluna_esquerda = QWidget(conteudo)
        self.coluna_esquerda.setObjectName("coluna_operacao_pagamentos")
        layout_esquerda = QVBoxLayout(self.coluna_esquerda)
        layout_esquerda.setContentsMargins(0, 0, 0, 0)
        layout_esquerda.setSpacing(12)

        self.grupo_lancamento = QGroupBox(
            "Novo pagamento ou edição",
            conteudo,
        )
        self.grupo_lancamento.setObjectName("secao_lancamento_pagamento")
        formulario = QGridLayout(self.grupo_lancamento)
        formulario.setContentsMargins(10, 12, 10, 6)
        formulario.setHorizontalSpacing(10)
        formulario.setVerticalSpacing(3)

        self.grupo_lancamento.setProperty("modoEdicao", False)
        formulario.addWidget(QLabel("Modalidade"), 0, 0, 1, 3)
        layout_modalidades = QGridLayout()
        layout_modalidades.setHorizontalSpacing(7)
        layout_modalidades.setVerticalSpacing(7)
        self.grupo_modalidades = QButtonGroup(self)
        self.grupo_modalidades.setExclusive(True)
        self.botoes_modalidade: dict[str, QPushButton] = {}
        nomes_modalidades = {
            "DINHEIRO": "DINHEIRO",
            "CREDITO": "CRÉDITO",
            "DEBITO": "DÉBITO",
            "PIX": "PIX",
        }
        for indice, modalidade in enumerate(MODALIDADES_EXIBIDAS):
            botao = QPushButton(nomes_modalidades[modalidade])
            botao.setObjectName(f"modalidade_{modalidade.lower()}")
            botao.setProperty("papelModalidade", True)
            botao.setProperty("modalidade", modalidade)
            botao.setCheckable(True)
            botao.setAutoDefault(False)
            self.grupo_modalidades.addButton(botao)
            self.botoes_modalidade[modalidade] = botao
            layout_modalidades.addWidget(botao, indice // 2, indice % 2)
        self.botoes_modalidade["DINHEIRO"].setChecked(True)
        formulario.addLayout(layout_modalidades, 1, 0, 1, 3)

        self.campo_valor = QLineEdit()
        self.campo_valor.setObjectName("valor_pagamento")
        self.campo_valor.setMaximumWidth(160)
        formulario.addWidget(QLabel("Valor (R$)"), 2, 0, 1, 3)

        self.botao_adicionar = QPushButton("Adicionar")
        self.botao_adicionar.setObjectName("adicionar_pagamento")
        self.botao_editar = QPushButton("Salvar edição")
        self.botao_editar.setObjectName("editar_pagamento")
        acoes_lancamento = QHBoxLayout()
        acoes_lancamento.setSpacing(8)
        acoes_lancamento.addWidget(self.campo_valor)
        acoes_lancamento.addWidget(self.botao_adicionar)
        acoes_lancamento.addWidget(self.botao_editar)
        acoes_lancamento.addStretch()
        formulario.addLayout(acoes_lancamento, 3, 0, 1, 3)
        formulario.setColumnStretch(2, 1)
        layout_esquerda.addWidget(self.grupo_lancamento)

        self.grupo_registrados = QGroupBox(
            "Pagamentos já registrados",
            conteudo,
        )
        self.grupo_registrados.setObjectName("secao_pagamentos_registrados")
        layout_registrados = QVBoxLayout(self.grupo_registrados)
        layout_registrados.setContentsMargins(10, 15, 10, 10)
        layout_registrados.setSpacing(6)

        self.tabela_pagamentos = QTableWidget(0, 2)
        self.tabela_pagamentos.setObjectName("lista_pagamentos")
        self.tabela_pagamentos.setHorizontalHeaderLabels(
            ["Modalidade", "Valor"]
        )
        self.tabela_pagamentos.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela_pagamentos.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela_pagamentos.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela_pagamentos.setAlternatingRowColors(True)
        self.tabela_pagamentos.verticalHeader().setVisible(False)
        self.tabela_pagamentos.verticalHeader().setDefaultSectionSize(32)
        self.tabela_pagamentos.setMinimumHeight(200)
        cabecalho_pagamentos = self.tabela_pagamentos.horizontalHeader()
        cabecalho_pagamentos.setStretchLastSection(False)
        cabecalho_pagamentos.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        cabecalho_pagamentos.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        layout_registrados.addWidget(self.tabela_pagamentos)

        layout_acoes = QHBoxLayout()
        self.rotulo_acao_tabela = QLabel(
            "Selecione uma linha para editar ou remover."
        )
        self.rotulo_acao_tabela.setWordWrap(True)
        self.botao_remover = QPushButton("Remover")
        self.botao_remover.setObjectName("remover_pagamento")
        layout_acoes.addWidget(self.rotulo_acao_tabela, 1)
        layout_acoes.addWidget(self.botao_remover)
        layout_registrados.addLayout(layout_acoes)
        self.layout_colunas.addWidget(self.grupo_registrados, 0, 1)

        self.grupo_divisao = QGroupBox("Sugestão de divisão", conteudo)
        self.grupo_divisao.setObjectName("secao_sugestao_divisao")
        layout_grupo_divisao = QVBoxLayout(self.grupo_divisao)
        layout_grupo_divisao.setContentsMargins(10, 12, 10, 6)
        layout_grupo_divisao.setSpacing(3)
        layout_divisao = QGridLayout()
        layout_divisao.setHorizontalSpacing(8)
        layout_divisao.setVerticalSpacing(5)
        layout_divisao.addWidget(
            QLabel("Dividir o saldo atual em"),
            0,
            0,
            1,
            3,
        )
        self.campo_partes = QSpinBox()
        self.campo_partes.setObjectName("quantidade_partes_pagamento")
        self.campo_partes.setRange(
            1,
            max(1, min(total_venda_centavos, MAXIMO_INTEIRO_QT)),
        )
        self.campo_partes.setValue(min(2, total_venda_centavos))
        layout_divisao.addWidget(self.campo_partes, 1, 0)
        self.botao_dividir = QPushButton("Sugerir divisão")
        self.botao_dividir.setObjectName("dividir_pagamento")
        layout_divisao.addWidget(self.botao_dividir, 1, 1)
        layout_divisao.setColumnStretch(2, 1)
        layout_grupo_divisao.addLayout(layout_divisao)

        metadados_divisao = QGridLayout()
        metadados_divisao.setHorizontalSpacing(10)
        metadados_divisao.setVerticalSpacing(4)
        self.rotulos_metadados_divisao: dict[str, QLabel] = {}
        for linha, (nome, texto) in enumerate(
            (
                ("base", "Base da última divisão:"),
                ("quantidade", "Quantidade de parcelas:"),
                ("situacao", "Situação:"),
            )
        ):
            legenda = QLabel(texto)
            legenda.setObjectName(f"legenda_{nome}_divisao")
            self.rotulos_metadados_divisao[nome] = legenda
            metadados_divisao.addWidget(legenda, linha, 0)
        self.rotulo_base_divisao = QLabel("—")
        self.rotulo_base_divisao.setObjectName("base_divisao_pagamento")
        self.rotulo_quantidade_divisao = QLabel("—")
        self.rotulo_quantidade_divisao.setObjectName(
            "quantidade_divisao_pagamento"
        )
        self.rotulo_estado_divisao = QLabel("Nenhuma sugestão")
        self.rotulo_estado_divisao.setObjectName("estado_divisao_pagamento")
        self.rotulo_estado_divisao.setProperty("estadoSugestao", "ausente")
        metadados_divisao.addWidget(self.rotulo_base_divisao, 0, 1)
        metadados_divisao.addWidget(self.rotulo_quantidade_divisao, 1, 1)
        metadados_divisao.addWidget(self.rotulo_estado_divisao, 2, 1)
        metadados_divisao.setColumnStretch(2, 1)
        layout_grupo_divisao.addLayout(metadados_divisao)

        self.tabela_sugestoes = QTableWidget(0, 3)
        self.tabela_sugestoes.setObjectName("parcelas_sugeridas_pagamento")
        self.tabela_sugestoes.setHorizontalHeaderLabels(
            ["Parcela", "Valor", "Situação"]
        )
        self.tabela_sugestoes.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela_sugestoes.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.tabela_sugestoes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tabela_sugestoes.setAlternatingRowColors(True)
        self.tabela_sugestoes.verticalHeader().setVisible(False)
        self.tabela_sugestoes.verticalHeader().setDefaultSectionSize(30)
        self.tabela_sugestoes.setMinimumHeight(80)
        self.tabela_sugestoes.setMaximumHeight(100)
        cabecalho_sugestoes = self.tabela_sugestoes.horizontalHeader()
        cabecalho_sugestoes.setStretchLastSection(False)
        cabecalho_sugestoes.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Fixed,
        )
        cabecalho_sugestoes.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Fixed,
        )
        cabecalho_sugestoes.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        self.tabela_sugestoes.setColumnWidth(0, 70)
        self.tabela_sugestoes.setColumnWidth(1, 105)
        layout_grupo_divisao.addWidget(self.tabela_sugestoes)

        self.rotulo_sugestao = QLabel("")
        self.rotulo_sugestao.setObjectName("sugestao_divisao_pagamento")
        self.rotulo_sugestao.setWordWrap(True)
        self.rotulo_sugestao.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.rotulo_sugestao.setMaximumHeight(44)
        layout_grupo_divisao.addWidget(self.rotulo_sugestao)
        layout_esquerda.addWidget(self.grupo_divisao, 1)

        self.layout_colunas.addWidget(self.coluna_esquerda, 0, 0)
        self.layout_colunas.setColumnStretch(0, 1)
        self.layout_colunas.setColumnStretch(1, 1)
        layout.addLayout(self.layout_colunas, 1)

        self.area_rolagem.setWidget(conteudo)
        layout_raiz.addWidget(self.area_rolagem, 1)

        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setObjectName("erro_pagamento")
        self.rotulo_erro.setWordWrap(True)
        self.rotulo_erro.setVisible(False)
        layout_raiz.addWidget(self.rotulo_erro)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_concluir = self.botoes.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.botao_concluir.setText("Concluir pagamentos")
        self.botao_concluir.setObjectName("concluir_pagamentos")
        self.botao_concluir.setToolTip("Atalho: Ctrl+Enter")
        self.botao_concluir.setAutoDefault(False)
        self.botao_concluir.setDefault(False)
        botao_cancelar = self.botoes.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        botao_cancelar.setText("Cancelar")
        botao_cancelar.setAutoDefault(False)
        for botao in (
            self.botao_adicionar,
            self.botao_editar,
            self.botao_remover,
            self.botao_dividir,
        ):
            botao.setAutoDefault(False)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout_raiz.addWidget(self.botoes)

        self.botao_adicionar.clicked.connect(self._adicionar_pagamento)
        self.botao_editar.clicked.connect(self._editar_pagamento)
        self.botao_remover.clicked.connect(self._remover_pagamento)
        self.botao_dividir.clicked.connect(self._sugerir_divisao)
        self.campo_valor.returnPressed.connect(self._confirmar_lancamento)
        self.campo_valor.textChanged.connect(
            self._registrar_alteracao_manual_do_valor
        )
        self.tabela_pagamentos.itemSelectionChanged.connect(
            self._carregar_pagamento_selecionado
        )
        self.atalho_concluir_retorno = QShortcut(
            QKeySequence("Ctrl+Return"),
            self,
        )
        self.atalho_concluir_enter = QShortcut(
            QKeySequence("Ctrl+Enter"),
            self,
        )
        for atalho in (
            self.atalho_concluir_retorno,
            self.atalho_concluir_enter,
        ):
            atalho.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            atalho.activated.connect(self.accept)

        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def _criar_cartao_resumo(
        self,
        layout: QHBoxLayout,
        legenda: str,
        valor: str,
        nome_valor: str,
    ) -> QLabel:
        cartao = QFrame(self)
        cartao.setObjectName("cartao_resumo")
        cartao.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout_cartao = QVBoxLayout(cartao)
        layout_cartao.setContentsMargins(12, 6, 12, 6)
        layout_cartao.setSpacing(3)
        rotulo_legenda = QLabel(legenda, cartao)
        rotulo_legenda.setObjectName("legenda_resumo")
        rotulo_legenda.setWordWrap(True)
        rotulo_legenda.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        rotulo_valor = QLabel(valor, cartao)
        rotulo_valor.setObjectName(nome_valor)
        rotulo_valor.setProperty("papelVisual", "valorResumo")
        rotulo_valor.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout_cartao.addWidget(rotulo_legenda)
        layout_cartao.addWidget(rotulo_valor)
        layout.addWidget(cartao)
        return rotulo_valor

    def _aplicar_tema_escuro(self) -> None:
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
            QDialog#dialogo_pagamentos,
            QDialog#dialogo_pagamentos QWidget#conteudo_pagamentos,
            QDialog#dialogo_pagamentos QScrollArea#rolagem_pagamentos,
            QDialog#dialogo_pagamentos QScrollArea#rolagem_pagamentos > QWidget > QWidget {
                background: #171a1f;
                color: #e8edf2;
            }
            QDialog#dialogo_pagamentos QGroupBox {
                color: #e8edf2;
                background: #1d2127;
                border: 1px solid #414a53;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: 700;
            }
            QDialog#dialogo_pagamentos QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QDialog#dialogo_pagamentos QLabel {
                color: #e3e8ed;
                background: transparent;
                font-weight: 400;
            }
            QDialog#dialogo_pagamentos QFrame#cartao_resumo {
                background: #1d3040;
                border: 1px solid #4d83aa;
                border-radius: 6px;
            }
            QDialog#dialogo_pagamentos QLabel#legenda_resumo {
                color: #b7c4cf;
                font-size: 12px;
            }
            QDialog#dialogo_pagamentos QLabel[papelVisual="valorResumo"] {
                color: #f7fbff;
                font-size: 21px;
                font-weight: 700;
            }
            QDialog#dialogo_pagamentos QLineEdit,
            QDialog#dialogo_pagamentos QSpinBox {
                color: #f5f7fa;
                background: #23272e;
                selection-color: #ffffff;
                selection-background-color: #2f75a6;
                border: 1px solid #5b6570;
                border-radius: 5px;
                min-height: 34px;
                padding: 3px 8px;
            }
            QDialog#dialogo_pagamentos QLineEdit:focus,
            QDialog#dialogo_pagamentos QSpinBox:focus {
                border: 2px solid #4aa3df;
                padding: 2px 7px;
            }
            QDialog#dialogo_pagamentos QTableWidget {
                color: #f1f4f7;
                background: #181b20;
                alternate-background-color: #22272e;
                selection-color: #ffffff;
                selection-background-color: #2f75a6;
                border: 1px solid #424a53;
                border-radius: 4px;
                gridline-color: #343b43;
            }
            QDialog#dialogo_pagamentos QTableWidget::item {
                color: #f1f4f7;
                padding: 4px 7px;
            }
            QDialog#dialogo_pagamentos QHeaderView::section {
                color: #f4f6f8;
                background: #2b3038;
                border: 0;
                border-right: 1px solid #424a53;
                border-bottom: 1px solid #4a535d;
                padding: 7px;
                font-weight: 700;
            }
            QDialog#dialogo_pagamentos QPushButton {
                color: #e8edf2;
                background: #2a2f36;
                border: 1px solid #525d68;
                border-radius: 5px;
                min-height: 34px;
                padding: 4px 12px;
            }
            QDialog#dialogo_pagamentos QPushButton:hover:enabled {
                background: #353c44;
                border-color: #687684;
            }
            QDialog#dialogo_pagamentos QPushButton[papelModalidade="true"] {
                min-height: 30px;
                padding: 3px 8px;
            }
            QDialog#dialogo_pagamentos QPushButton[papelModalidade="true"]:checked {
                color: #ffffff;
                background: #2474a6;
                border-color: #65b7eb;
                font-weight: 700;
            }
            QDialog#dialogo_pagamentos QPushButton:disabled {
                color: #aab3bc;
                background: #22262c;
                border-color: #3e464e;
            }
            QDialog#dialogo_pagamentos QPushButton#concluir_pagamentos {
                color: #ffffff;
                background: #2474a6;
                border-color: #4297cc;
                font-weight: 700;
                padding-left: 18px;
                padding-right: 18px;
            }
            QDialog#dialogo_pagamentos QPushButton#concluir_pagamentos:disabled {
                color: #b7c1c9;
                background: #314653;
                border-color: #435b69;
            }
            QDialog#dialogo_pagamentos QLabel#estado_divisao_pagamento[estadoSugestao="valida"] {
                color: #a8e6bd;
                font-weight: 700;
            }
            QDialog#dialogo_pagamentos QLabel#estado_divisao_pagamento[estadoSugestao="desatualizada"] {
                color: #f5d889;
                font-weight: 700;
            }
            QDialog#dialogo_pagamentos QGroupBox#secao_lancamento_pagamento[modoEdicao="true"] {
                color: #f5d889;
            }
            QDialog#dialogo_pagamentos QLabel#erro_pagamento {
                color: #ffb8b1;
                font-weight: 600;
            }
            """
        )

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        if not self._tamanho_inicial_ajustado:
            tela = self.screen()
            if tela is not None:
                disponivel = tela.availableGeometry().size()
                self.resize(
                    min(LARGURA_INICIAL, int(disponivel.width() * 0.9)),
                    min(ALTURA_INICIAL, int(disponivel.height() * 0.9)),
                )
            self._tamanho_inicial_ajustado = True
        self._ajustar_layout_colunas(self.width())
        QTimer.singleShot(
            0,
            self.botoes_modalidade["DINHEIRO"].setFocus,
        )

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        if hasattr(self, "layout_colunas"):
            self._ajustar_layout_colunas(evento.size().width())

    def _ajustar_layout_colunas(self, largura: int) -> None:
        empilhar = largura < 760
        if empilhar == self._layout_empilhado:
            return
        if empilhar:
            self.layout_colunas.addWidget(
                self.coluna_esquerda,
                0,
                0,
                1,
                2,
            )
            self.layout_colunas.addWidget(
                self.grupo_registrados,
                1,
                0,
                1,
                2,
            )
        else:
            self.layout_colunas.addWidget(self.coluna_esquerda, 0, 0)
            self.layout_colunas.addWidget(self.grupo_registrados, 0, 1)
        self._layout_empilhado = empilhar
        self.layout_colunas.invalidate()

    def keyPressEvent(self, evento) -> None:
        if (
            evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and evento.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.accept()
            evento.accept()
            return

        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            evento.accept()
            return

        if evento.key() == Qt.Key.Key_Escape and self._indice_edicao is not None:
            self._preparar_novo_lancamento()
            evento.accept()
            return

        super().keyPressEvent(evento)

    def accept(self) -> None:
        if self._resultado_confirmado:
            return

        if not esta_integralmente_pago(self.estado_pagamentos):
            self._mostrar_erro(
                ValueError("Informe pagamentos para cobrir todo o saldo.")
            )
            return

        self._resultado_confirmado = True
        self.pagamentos_confirmados.emit(self.estado_pagamentos)
        super().accept()

    def _criar_pagamento_do_formulario(self) -> Pagamento:
        valor_centavos = ler_centavos(self.campo_valor.text())
        botao_modalidade = self.grupo_modalidades.checkedButton()
        if botao_modalidade is None:
            raise ValueError("Selecione uma modalidade de pagamento.")
        return Pagamento(
            modalidade=botao_modalidade.property("modalidade"),
            valor_centavos=valor_centavos,
        )

    def _confirmar_lancamento(self) -> None:
        if self._indice_edicao is None:
            self._adicionar_pagamento()
        else:
            self._editar_pagamento()

    def _adicionar_pagamento(self) -> None:
        try:
            pagamento = self._criar_pagamento_do_formulario()
            indice_sugestao = self._indice_sugestao_automatica(pagamento)
            novo_estado = adicionar_pagamento(
                self.estado_pagamentos,
                pagamento,
            )
        except (TypeError, ValueError) as erro:
            self._mostrar_erro(erro)
            return

        self.estado_pagamentos = novo_estado
        if indice_sugestao is not None:
            self._pagamentos_sugeridos[indice_sugestao] = pagamento
            self._proximo_indice_sugestao += 1
            if self._proximo_indice_sugestao >= len(self.sugestoes_divisao):
                self._divisao_automatica_ativa = False
        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def _editar_pagamento(self) -> None:
        if self._indice_edicao is None:
            self._mostrar_erro(ValueError("Selecione um pagamento para editar."))
            return

        pagamento_anterior = self.estado_pagamentos.pagamentos[
            self._indice_edicao
        ]
        try:
            pagamento = self._criar_pagamento_do_formulario()
            novo_estado = editar_pagamento(
                self.estado_pagamentos,
                self._indice_edicao,
                pagamento,
            )
        except (TypeError, ValueError, IndexError) as erro:
            self._mostrar_erro(erro)
            return

        self.estado_pagamentos = novo_estado
        self._atualizar_pagamento_sugerido_editado(
            pagamento_anterior,
            pagamento,
        )
        self._validar_compatibilidade_divisao()
        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def _remover_pagamento(self) -> None:
        if self._indice_edicao is None:
            self._mostrar_erro(ValueError("Selecione um pagamento para remover."))
            return

        pagamento_removido = self.estado_pagamentos.pagamentos[
            self._indice_edicao
        ]
        try:
            novo_estado = remover_pagamento(
                self.estado_pagamentos,
                self._indice_edicao,
            )
        except (TypeError, ValueError, IndexError) as erro:
            self._mostrar_erro(erro)
            return

        self.estado_pagamentos = novo_estado
        self._remover_marcacao_pagamento_sugerido(pagamento_removido)
        self._validar_compatibilidade_divisao()
        self._atualizar_exibicao()
        self._preparar_novo_lancamento()

    def _carregar_pagamento_selecionado(self) -> None:
        linhas = self.tabela_pagamentos.selectionModel().selectedRows()
        if not linhas:
            self._indice_edicao = None
            self._atualizar_botoes_de_edicao()
            return

        self._indice_edicao = linhas[0].row()
        pagamento = self.estado_pagamentos.pagamentos[self._indice_edicao]
        self._selecionar_modalidade(pagamento.modalidade)
        self._definir_valor_programaticamente(
            centavos_para_texto(pagamento.valor_centavos)
        )
        self._definir_contexto_edicao(
            f"Editando pagamento {self._indice_edicao + 1}"
        )
        self._limpar_erro()
        self._atualizar_botoes_de_edicao()
        self.campo_valor.setFocus()
        self.campo_valor.selectAll()

    def _preparar_novo_lancamento(self) -> None:
        self._indice_edicao = None
        self.tabela_pagamentos.clearSelection()
        self._definir_contexto_edicao("Novo lançamento", editando=False)
        self._limpar_erro()
        self._validar_compatibilidade_divisao()
        saldo = calcular_saldo_restante(self.estado_pagamentos)
        proxima_sugestao = self._proxima_sugestao_automatica()
        valor = proxima_sugestao if proxima_sugestao is not None else saldo
        self._definir_valor_programaticamente(
            centavos_para_texto(valor) if valor > 0 else ""
        )
        self._atualizar_rotulo_sugestao()
        self._atualizar_botoes_de_edicao()
        self.grupo_modalidades.checkedButton().setFocus()

    def _sugerir_divisao(self) -> None:
        saldo = calcular_saldo_restante(self.estado_pagamentos)

        try:
            sugestoes = dividir_valor_igualmente(
                saldo,
                self.campo_partes.value(),
            )
        except (TypeError, ValueError) as erro:
            self._mostrar_erro(erro)
            return

        self.sugestoes_divisao = sugestoes
        self._base_divisao_centavos = saldo
        self._proximo_indice_sugestao = 0
        self._pagamentos_sugeridos.clear()
        self._divisao_automatica_ativa = True
        self._divisao_requer_recalculo = False
        self._atualizar_rotulo_sugestao()
        self._definir_valor_programaticamente(
            centavos_para_texto(sugestoes[0])
        )
        self._limpar_erro()
        self.campo_valor.setFocus()
        self.campo_valor.selectAll()

    def _atualizar_exibicao(self) -> None:
        pagamentos = self.estado_pagamentos.pagamentos
        self.tabela_pagamentos.setRowCount(len(pagamentos))

        for linha, pagamento in enumerate(pagamentos):
            item_modalidade = QTableWidgetItem(pagamento.modalidade)
            item_valor = QTableWidgetItem(
                formatar_centavos(pagamento.valor_centavos)
            )
            item_valor.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.tabela_pagamentos.setItem(linha, 0, item_modalidade)
            self.tabela_pagamentos.setItem(linha, 1, item_valor)

        total_pago = calcular_total_pago(self.estado_pagamentos)
        saldo = calcular_saldo_restante(self.estado_pagamentos)
        self.rotulo_total_pago.setText(formatar_centavos(total_pago))
        self.rotulo_saldo.setText(formatar_centavos(saldo))
        self.botao_concluir.setEnabled(
            esta_integralmente_pago(self.estado_pagamentos)
        )
        self.botao_dividir.setEnabled(saldo > 0)
        self.campo_partes.setMaximum(
            max(1, min(saldo, MAXIMO_INTEIRO_QT))
        )
        self.botao_adicionar.setEnabled(
            saldo > 0 and self._indice_edicao is None
        )

    def _atualizar_botoes_de_edicao(self) -> None:
        editando = self._indice_edicao is not None
        saldo = calcular_saldo_restante(self.estado_pagamentos)
        self.botao_adicionar.setEnabled(saldo > 0 and not editando)
        self.botao_editar.setEnabled(editando)
        self.botao_remover.setEnabled(editando)

    def _definir_valor_programaticamente(self, texto: str) -> None:
        self._alterando_valor_programaticamente = True
        try:
            self.campo_valor.setText(texto)
        finally:
            self._alterando_valor_programaticamente = False

    def _selecionar_modalidade(self, modalidade: str) -> None:
        try:
            botao = self.botoes_modalidade[modalidade]
        except KeyError as erro:
            raise ValueError("Modalidade de pagamento inválida.") from erro
        botao.setChecked(True)

    def _definir_contexto_edicao(
        self,
        texto: str,
        editando: bool = True,
    ) -> None:
        self.grupo_lancamento.setTitle(texto)
        self.grupo_lancamento.setProperty("modoEdicao", editando)
        estilo = self.grupo_lancamento.style()
        estilo.unpolish(self.grupo_lancamento)
        estilo.polish(self.grupo_lancamento)

    def _registrar_alteracao_manual_do_valor(self, _texto: str) -> None:
        if (
            self._alterando_valor_programaticamente
            or self._indice_edicao is not None
            or not self._divisao_automatica_ativa
        ):
            return

        proxima = self._proxima_sugestao_automatica()
        try:
            valor_atual = ler_centavos(self.campo_valor.text())
        except (TypeError, ValueError):
            valor_atual = None
        if valor_atual != proxima:
            self._divisao_automatica_ativa = False
            self._divisao_requer_recalculo = True
            self._atualizar_rotulo_sugestao()

    def _proxima_sugestao_automatica(self) -> int | None:
        if (
            not self._divisao_automatica_ativa
            or self._proximo_indice_sugestao >= len(self.sugestoes_divisao)
        ):
            return None
        return self.sugestoes_divisao[self._proximo_indice_sugestao]

    def _indice_sugestao_automatica(
        self,
        pagamento: Pagamento,
    ) -> int | None:
        sugestao = self._proxima_sugestao_automatica()
        if sugestao is None or pagamento.valor_centavos != sugestao:
            return None
        return self._proximo_indice_sugestao

    def _atualizar_pagamento_sugerido_editado(
        self,
        anterior: Pagamento,
        atual: Pagamento,
    ) -> None:
        for indice, pagamento in tuple(self._pagamentos_sugeridos.items()):
            if pagamento is anterior:
                if atual.valor_centavos == self.sugestoes_divisao[indice]:
                    self._pagamentos_sugeridos[indice] = atual
                else:
                    self._pagamentos_sugeridos.pop(indice)
                return

    def _remover_marcacao_pagamento_sugerido(
        self,
        removido: Pagamento,
    ) -> None:
        for indice, pagamento in tuple(self._pagamentos_sugeridos.items()):
            if pagamento is removido:
                self._pagamentos_sugeridos.pop(indice)
                return

    def _validar_compatibilidade_divisao(self) -> None:
        if not self.sugestoes_divisao:
            return
        saldo = calcular_saldo_restante(self.estado_pagamentos)
        saldo_sugerido = sum(
            self.sugestoes_divisao[self._proximo_indice_sugestao :]
        )
        if saldo != saldo_sugerido:
            self._divisao_automatica_ativa = False
            self._divisao_requer_recalculo = True

    def _atualizar_rotulo_sugestao(self) -> None:
        if not self.sugestoes_divisao:
            self.rotulo_base_divisao.setText("—")
            self.rotulo_quantidade_divisao.setText("—")
            self._definir_estado_visual_divisao(
                "Nenhuma sugestão",
                "ausente",
            )
            self.tabela_sugestoes.setRowCount(0)
            self.rotulo_sugestao.setText(
                "A divisão usa o saldo existente no momento da solicitação."
            )
            return

        base = self._base_divisao_centavos
        if base is None:
            base = sum(self.sugestoes_divisao)
        self.rotulo_base_divisao.setText(formatar_centavos(base))
        self.rotulo_quantidade_divisao.setText(
            str(len(self.sugestoes_divisao))
        )
        if self._divisao_requer_recalculo:
            self._definir_estado_visual_divisao(
                "Desatualizada",
                "desatualizada",
            )
        elif self._proximo_indice_sugestao >= len(self.sugestoes_divisao):
            self._definir_estado_visual_divisao(
                "Válida — todas adicionadas",
                "valida",
            )
        else:
            self._definir_estado_visual_divisao("Válida", "valida")

        pagamentos_atuais = self.estado_pagamentos.pagamentos
        self.tabela_sugestoes.setRowCount(len(self.sugestoes_divisao))
        for indice, valor in enumerate(self.sugestoes_divisao):
            pagamento = self._pagamentos_sugeridos.get(indice)
            utilizada = pagamento is not None and any(
                atual is pagamento for atual in pagamentos_atuais
            )
            if utilizada:
                situacao = "Usada"
            elif (
                self._divisao_automatica_ativa
                and indice == self._proximo_indice_sugestao
            ):
                situacao = "Próxima"
            else:
                situacao = "Pendente"
            situacao_tabela = (
                "Utilizada" if situacao == "Usada" else situacao
            )
            itens = (
                QTableWidgetItem(str(indice + 1)),
                QTableWidgetItem(formatar_centavos(valor)),
                QTableWidgetItem(situacao_tabela),
            )
            itens[0].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            itens[1].setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            for coluna, item in enumerate(itens):
                self.tabela_sugestoes.setItem(indice, coluna, item)

        if self._divisao_requer_recalculo:
            texto = (
                "Referência mantida e desatualizada. Solicite uma nova "
                "divisão para retomar o preenchimento automático."
            )
        elif self._proximo_indice_sugestao >= len(self.sugestoes_divisao):
            texto = "Todas as parcelas sugeridas foram adicionadas."
        else:
            texto = (
                "Sugestão válida; a próxima parcela está destacada na tabela."
            )
        self.rotulo_sugestao.setText(texto)

    def _definir_estado_visual_divisao(
        self,
        texto: str,
        estado: str,
    ) -> None:
        self.rotulo_estado_divisao.setText(texto)
        self.rotulo_estado_divisao.setProperty("estadoSugestao", estado)
        estilo = self.rotulo_estado_divisao.style()
        estilo.unpolish(self.rotulo_estado_divisao)
        estilo.polish(self.rotulo_estado_divisao)

    def _mostrar_erro(self, erro: Exception) -> None:
        self.rotulo_erro.setText(str(erro))
        self.rotulo_erro.setVisible(True)

    def _limpar_erro(self) -> None:
        self.rotulo_erro.clear()
        self.rotulo_erro.setVisible(False)
