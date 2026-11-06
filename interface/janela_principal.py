import services.persistencia_venda_service as persistencia_venda_service

from PySide6.QtCore import Qt, QSignalBlocker, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.conexao import CAMINHO_BANCO
from interface.dialogos_entrada import (
    DialogoDiversos,
    DialogoPeso,
    DialogoUnidade,
)
from interface.dialogo_confirmacao_venda import DialogoConfirmacaoVenda
from interface.dialogo_codigos_recuperacao import DialogoCodigosRecuperacao
from interface.dialogo_pagamentos import DialogoPagamentos
from interface.formatacao import formatar_centavos
from interface.pagina_historico import PaginaHistorico
from interface.pagina_administracao import PaginaAdministracao
from interface.pagina_produtos import PaginaProdutos
from models.estado_venda import EstadoVenda
from models.item_venda import DESCRICAO_DIVERSOS, ItemVenda
from models.pagamento import PagamentosEmAndamento
from models.sessao_usuario import SessaoUsuario
from models.venda_confirmada import VendaConfirmada
from models.venda_em_andamento import VendaEmAndamento
from services.estado_venda_service import (
    adicionar_no_estado,
    desfazer_ultima_remocao,
    remover_com_desfazer,
)
from services.autenticacao_service import (
    PermissaoNegadaError,
    autorizar_sessao,
    encerrar_sessao,
)
from services.item_venda_service import criar_item_de_etiqueta_com_estimativa
from services.produto_etiqueta import associar_etiqueta_ao_produto
from services.produto_service import consultar_produto_por_codigo
from services.venda_em_andamento_service import calcular_total


class JanelaPrincipal(QMainWindow):
    """Janela principal com entrada única para códigos do PDV."""

    item_criado = Signal(object)
    pagamentos_confirmados = Signal(object)
    venda_confirmada = Signal(object)
    venda_persistida = Signal(int)
    logout_realizado = Signal()

    def __init__(
        self,
        caminho_banco=CAMINHO_BANCO,
        sessao: SessaoUsuario | None = None,
    ) -> None:
        super().__init__()
        self.caminho_banco = caminho_banco
        autorizar_sessao(
            sessao,
            ("ADMINISTRADOR", "CAIXA"),
            self.caminho_banco,
        )
        self.sessao = sessao
        self.dialogo_atual: QDialog | None = None
        self.estado_venda = EstadoVenda(venda=VendaEmAndamento())
        self.composicao_pagamentos: PagamentosEmAndamento | None = None
        self.resultado_confirmacao: VendaConfirmada | None = None
        self.identificador_tentativa_fechamento: str | None = None
        self.confirmacao_pendente: VendaConfirmada | None = None
        self.ultimo_id_venda_persistida: int | None = None
        self._fechamento_em_processamento = False
        self._fechamento_incerto = False
        self._processando_entrada = False
        self._ignorar_proximo_enter = False
        self._encerramento_autorizado = False
        self.setWindowTitle("Sistema-PDV")
        self.resize(1024, 720)

        estrutura_principal = QWidget(self)
        estrutura_principal.setObjectName("estrutura_principal")
        estrutura_principal.setAutoFillBackground(True)
        paleta_estrutura = estrutura_principal.palette()
        paleta_estrutura.setColor(
            QPalette.ColorRole.Window,
            QColor("#171a1f"),
        )
        estrutura_principal.setPalette(paleta_estrutura)
        layout_principal = QVBoxLayout(estrutura_principal)

        menu_superior = QWidget(estrutura_principal)
        menu_superior.setObjectName("menu_superior")
        menu_superior.setAutoFillBackground(True)
        paleta_menu = menu_superior.palette()
        paleta_menu.setColor(QPalette.ColorRole.Window, QColor("#171a1f"))
        menu_superior.setPalette(paleta_menu)
        menu_superior.setStyleSheet(
            """
            QWidget#menu_superior {
                background: #171a1f;
            }
            QWidget#menu_superior QLabel#usuario_autenticado {
                color: #e3e8ed;
                font-weight: 600;
                padding: 0 4px;
            }
            QWidget#menu_superior QPushButton {
                color: #e8edf2;
                background: #2a2f36;
                border: 1px solid #525d68;
                border-radius: 5px;
                min-height: 34px;
                padding: 5px 14px;
            }
            QWidget#menu_superior QPushButton:hover:enabled {
                background: #353c44;
                border-color: #687684;
            }
            QWidget#menu_superior QPushButton:checked {
                color: #ffffff;
                background: #2474a6;
                border-color: #4297cc;
                font-weight: 700;
            }
            QWidget#menu_superior QPushButton:disabled {
                color: #aab3bc;
                background: #22262c;
                border-color: #3e464e;
            }
            """
        )
        layout_menu = QHBoxLayout(menu_superior)
        layout_menu.setContentsMargins(8, 7, 8, 7)
        layout_menu.setSpacing(8)
        self.botao_navegar_caixa = QPushButton("Frente de Caixa")
        self.botao_navegar_caixa.setObjectName("navegar_frente_caixa")
        self.botao_navegar_historico = QPushButton("Histórico")
        self.botao_navegar_historico.setObjectName("navegar_historico")
        self.botao_navegar_produtos = QPushButton("Produtos")
        self.botao_navegar_produtos.setObjectName("navegar_produtos")
        self.botao_navegar_administracao = QPushButton("Administração")
        self.botao_navegar_administracao.setObjectName(
            "navegar_administracao"
        )
        for botao in (
            self.botao_navegar_caixa,
            self.botao_navegar_historico,
            self.botao_navegar_produtos,
            self.botao_navegar_administracao,
        ):
            botao.setCheckable(True)
            fonte_selecionada = botao.font()
            fonte_selecionada.setBold(True)
            largura_texto_selecionado = QFontMetrics(
                fonte_selecionada
            ).horizontalAdvance(botao.text())
            botao.setMinimumWidth(
                max(botao.sizeHint().width(), largura_texto_selecionado + 40)
            )
            botao.setMinimumHeight(44)
        self.grupo_navegacao = QButtonGroup(self)
        self.grupo_navegacao.setExclusive(True)
        self.grupo_navegacao.addButton(self.botao_navegar_caixa)
        self.grupo_navegacao.addButton(self.botao_navegar_historico)
        self.grupo_navegacao.addButton(self.botao_navegar_produtos)
        self.grupo_navegacao.addButton(self.botao_navegar_administracao)
        self.botao_navegar_caixa.setChecked(True)
        layout_menu.addWidget(self.botao_navegar_caixa)
        layout_menu.addWidget(self.botao_navegar_historico)
        layout_menu.addWidget(self.botao_navegar_produtos)
        layout_menu.addWidget(self.botao_navegar_administracao)
        layout_menu.addStretch()
        self.rotulo_usuario = QLabel(
            f"{self.sessao.identificacao_acesso} ({self.sessao.perfil})"
        )
        self.rotulo_usuario.setObjectName("usuario_autenticado")
        self.botao_logout = QPushButton("Trocar operador")
        self.botao_logout.setObjectName("encerrar_sessao")
        self.botao_codigos_recuperacao = QPushButton("Códigos de recuperação")
        self.botao_codigos_recuperacao.setObjectName(
            "abrir_codigos_recuperacao"
        )
        self.botao_codigos_recuperacao.setVisible(
            self.sessao.perfil == "ADMINISTRADOR"
        )
        layout_menu.addWidget(self.rotulo_usuario)
        layout_menu.addWidget(self.botao_codigos_recuperacao)
        layout_menu.addWidget(self.botao_logout)
        layout_principal.addWidget(menu_superior)

        self.paginas = QStackedWidget(estrutura_principal)
        self.paginas.setObjectName("paginas_principais")
        layout_principal.addWidget(self.paginas)

        area_vendas = QWidget(self.paginas)
        area_vendas.setObjectName("area_vendas")
        area_vendas.setAutoFillBackground(True)
        paleta_area_vendas = area_vendas.palette()
        paleta_area_vendas.setColor(
            QPalette.ColorRole.Window,
            QColor("#171a1f"),
        )
        area_vendas.setPalette(paleta_area_vendas)
        self.pagina_frente_caixa = area_vendas

        layout = QVBoxLayout(area_vendas)
        layout.setContentsMargins(24, 16, 24, 20)
        layout.setSpacing(12)
        area_vendas.setStyleSheet(
            """
            QWidget#area_vendas {
                background: #171a1f;
            }
            QWidget#area_vendas QLabel#rotulo_leitura_codigo {
                color: #e3e8ed;
                font-size: 13px;
                font-weight: 600;
            }
            QWidget#area_vendas QLineEdit#campo_entrada {
                color: #f5f7fa;
                background: #23272e;
                selection-color: #ffffff;
                selection-background-color: #2f75a6;
                border: 1px solid #5b6570;
                border-radius: 5px;
                padding: 7px 10px;
                font-size: 15px;
            }
            QWidget#area_vendas QLineEdit#campo_entrada:focus {
                border: 2px solid #4aa3df;
                padding: 6px 9px;
            }
            QWidget#area_vendas QLineEdit#campo_entrada:disabled {
                color: #aab3bc;
                background: #20242a;
                border-color: #414a53;
            }
            QWidget#area_vendas QLabel#status_entrada {
                border: 1px solid #46515c;
                border-radius: 5px;
                padding: 9px 12px;
                color: #e1e7ec;
                background: #22272d;
                font-size: 14px;
                font-weight: 600;
            }
            QWidget#area_vendas QLabel#status_entrada[tipoStatus="sucesso"] {
                border-color: #3f8f65;
                color: #a8e6bd;
                background: #183426;
            }
            QWidget#area_vendas QLabel#status_entrada[tipoStatus="erro"] {
                border-color: #b85c5c;
                color: #ffb8b1;
                background: #412326;
            }
            QWidget#area_vendas QLabel#status_entrada[tipoStatus="alerta"] {
                border-color: #a98228;
                color: #f5d889;
                background: #3b321d;
            }
            QWidget#area_vendas QTableWidget#tabela_itens {
                color: #f1f4f7;
                background: #181b20;
                alternate-background-color: #22272e;
                selection-color: #ffffff;
                selection-background-color: #2f75a6;
                border: 1px solid #424a53;
                border-radius: 4px;
                gridline-color: #343b43;
            }
            QWidget#area_vendas QTableWidget#tabela_itens::item {
                color: #f1f4f7;
                padding: 5px 7px;
            }
            QWidget#area_vendas QTableWidget#tabela_itens::item:selected {
                color: #ffffff;
                background: #2f75a6;
            }
            QWidget#area_vendas QHeaderView::section {
                background: #2b3038;
                color: #f4f6f8;
                border: 0;
                border-right: 1px solid #424a53;
                border-bottom: 1px solid #4a535d;
                padding: 8px 7px;
                font-weight: 700;
            }
            QWidget#area_vendas QLabel#total_venda {
                color: #f7fbff;
                background: #1d3040;
                border: 1px solid #4d83aa;
                border-radius: 6px;
                padding: 9px 14px;
                font-size: 22px;
                font-weight: 700;
            }
            QWidget#area_vendas QPushButton {
                color: #e8edf2;
                background: #2a2f36;
                border: 1px solid #525d68;
                border-radius: 5px;
                min-height: 34px;
                padding: 4px 12px;
            }
            QWidget#area_vendas QPushButton:hover:enabled {
                background: #353c44;
                border-color: #687684;
            }
            QWidget#area_vendas QPushButton:disabled {
                color: #aab3bc;
                background: #22262c;
                border-color: #3e464e;
            }
            QWidget#area_vendas QPushButton[papelAcao="principal"] {
                color: #ffffff;
                background: #2474a6;
                border: 1px solid #4297cc;
                border-radius: 5px;
                font-weight: 700;
                padding-left: 18px;
                padding-right: 18px;
            }
            QWidget#area_vendas QPushButton[papelAcao="principal"]:disabled {
                color: #b7c1c9;
                background: #314653;
                border-color: #435b69;
            }
            QWidget#area_vendas QPushButton[papelAcao="comercial"] {
                color: #dff3ff;
                background: #233b4b;
                border: 1px solid #4f8db5;
                border-radius: 5px;
                font-weight: 700;
            }
            QWidget#area_vendas QPushButton[papelAcao="alerta"]:enabled {
                color: #ffe6a6;
                background: #46391f;
                border: 1px solid #b58a2b;
                border-radius: 5px;
                font-weight: 700;
            }
            """
        )

        layout_operacao = QHBoxLayout()
        layout_operacao.setSpacing(12)
        rotulo_leitura = QLabel("Leitura de código", area_vendas)
        rotulo_leitura.setObjectName("rotulo_leitura_codigo")
        layout_operacao.addWidget(rotulo_leitura)

        self.campo_entrada = QLineEdit(area_vendas)
        self.campo_entrada.setObjectName("campo_entrada")
        self.campo_entrada.setPlaceholderText(
            "Leia a etiqueta ou digite o código do produto"
        )
        paleta_entrada = self.campo_entrada.palette()
        paleta_entrada.setColor(QPalette.ColorRole.Base, QColor("#23272e"))
        paleta_entrada.setColor(QPalette.ColorRole.Text, QColor("#f5f7fa"))
        paleta_entrada.setColor(
            QPalette.ColorRole.PlaceholderText,
            QColor("#b5bec7"),
        )
        paleta_entrada.setColor(
            QPalette.ColorRole.Highlight,
            QColor("#2f75a6"),
        )
        paleta_entrada.setColor(
            QPalette.ColorRole.HighlightedText,
            QColor("#ffffff"),
        )
        self.campo_entrada.setPalette(paleta_entrada)
        self.campo_entrada.setMinimumWidth(320)
        self.campo_entrada.setMaximumWidth(520)
        self.campo_entrada.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.campo_entrada.textChanged.connect(
            self._processar_etiqueta_automaticamente
        )
        self.campo_entrada.returnPressed.connect(self._processar_enter)
        layout_operacao.addWidget(self.campo_entrada)

        self.rotulo_status = QLabel("Pronto para leitura.", area_vendas)
        self.rotulo_status.setObjectName("status_entrada")
        self.rotulo_status.setProperty("tipoStatus", "neutro")
        self.rotulo_status.setWordWrap(True)
        self.rotulo_status.setMinimumHeight(42)
        self.rotulo_status.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.rotulo_status.setMinimumWidth(300)
        self.rotulo_status.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        layout_operacao.addWidget(self.rotulo_status, 1)
        layout.addLayout(layout_operacao)

        self.tabela_itens = QTableWidget(0, 4, area_vendas)
        self.tabela_itens.setObjectName("tabela_itens")
        self.tabela_itens.setHorizontalHeaderLabels(
            [
                "Produto / descrição",
                "Quantidade / peso",
                "Preço unitário / kg",
                "Subtotal",
            ]
        )
        self.tabela_itens.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela_itens.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela_itens.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela_itens.setSortingEnabled(False)
        self.tabela_itens.setAlternatingRowColors(True)
        paleta_tabela = self.tabela_itens.palette()
        paleta_tabela.setColor(QPalette.ColorRole.Base, QColor("#181b20"))
        paleta_tabela.setColor(
            QPalette.ColorRole.AlternateBase,
            QColor("#22272e"),
        )
        paleta_tabela.setColor(QPalette.ColorRole.Text, QColor("#f1f4f7"))
        paleta_tabela.setColor(
            QPalette.ColorRole.Highlight,
            QColor("#2f75a6"),
        )
        paleta_tabela.setColor(
            QPalette.ColorRole.HighlightedText,
            QColor("#ffffff"),
        )
        self.tabela_itens.setPalette(paleta_tabela)
        self.tabela_itens.verticalHeader().setVisible(False)
        self.tabela_itens.verticalHeader().setDefaultSectionSize(34)
        cabecalho = self.tabela_itens.horizontalHeader()
        cabecalho.setStretchLastSection(False)
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tabela_itens.setColumnWidth(1, 170)
        self.tabela_itens.setColumnWidth(2, 180)
        self.tabela_itens.setColumnWidth(3, 120)
        layout.addWidget(self.tabela_itens, 1)

        layout_acoes = QHBoxLayout()
        layout_acoes.setSpacing(8)
        self.botao_remover = QPushButton("Remover item", area_vendas)
        self.botao_remover.setObjectName("botao_remover")
        self.botao_desfazer = QPushButton("Desfazer remoção", area_vendas)
        self.botao_desfazer.setObjectName("botao_desfazer")
        self.botao_pagamento = QPushButton("Pagamentos", area_vendas)
        self.botao_pagamento.setObjectName("botao_pagamento")
        self.botao_pagamento.setProperty("papelAcao", "comercial")
        self.botao_confirmar_venda = QPushButton(
            "Confirmar venda",
            area_vendas,
        )
        self.botao_confirmar_venda.setObjectName("botao_confirmar_venda")
        self.botao_confirmar_venda.setProperty("papelAcao", "principal")
        self.botao_verificar_fechamento = QPushButton(
            "Verificar fechamento",
            area_vendas,
        )
        self.botao_verificar_fechamento.setObjectName(
            "botao_verificar_fechamento"
        )
        self.botao_verificar_fechamento.setProperty("papelAcao", "alerta")
        layout_acoes.addWidget(self.botao_remover)
        layout_acoes.addWidget(self.botao_desfazer)
        layout_acoes.addWidget(self.botao_verificar_fechamento)
        layout_acoes.addStretch()

        layout_total = QHBoxLayout()
        layout_total.addStretch()
        self.rotulo_total = QLabel("Total: R$ 0,00", area_vendas)
        self.rotulo_total.setObjectName("total_venda")
        self.rotulo_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotulo_total.setMinimumWidth(205)
        layout_total.addWidget(self.rotulo_total)
        layout.addLayout(layout_total)

        layout_acoes.addWidget(self.botao_pagamento)
        layout_acoes.addWidget(self.botao_confirmar_venda)
        layout.addLayout(layout_acoes)

        self.pagina_historico = PaginaHistorico(
            self.caminho_banco,
            self.paginas,
            operacao_bloqueada=self._fechamento_bloqueia_operacao,
            sessao_solicitante=self.sessao,
        )
        self.pagina_produtos = PaginaProdutos(
            self.caminho_banco,
            tem_venda_em_andamento=lambda: bool(
                self.estado_venda.venda.itens
            ),
            operacao_bloqueada=self._fechamento_bloqueia_operacao,
            alteracao_permitida=self._usuario_pode_operar,
            sessao_administrativa=self.sessao,
            parent=self.paginas,
        )
        self.pagina_administracao = PaginaAdministracao(
            self.sessao,
            self.caminho_banco,
            self.paginas,
        )
        self.paginas.addWidget(self.pagina_frente_caixa)
        self.paginas.addWidget(self.pagina_historico)
        self.paginas.addWidget(self.pagina_produtos)
        self.paginas.addWidget(self.pagina_administracao)
        self.setCentralWidget(estrutura_principal)
        self.item_criado.connect(self._adicionar_item_a_venda)
        self.botao_navegar_caixa.clicked.connect(self.mostrar_frente_caixa)
        self.botao_navegar_historico.clicked.connect(self.mostrar_historico)
        self.botao_navegar_produtos.clicked.connect(self.mostrar_produtos)
        self.botao_navegar_administracao.clicked.connect(
            self.mostrar_administracao
        )
        self.botao_logout.clicked.connect(self.solicitar_logout)
        self.botao_codigos_recuperacao.clicked.connect(
            self.abrir_codigos_recuperacao
        )
        self.botao_remover.clicked.connect(self.remover_item_selecionado)
        self.botao_desfazer.clicked.connect(self.desfazer_ultima_remocao)
        self.botao_pagamento.clicked.connect(self.abrir_dialogo_pagamentos)
        self.botao_confirmar_venda.clicked.connect(
            self.abrir_dialogo_confirmacao
        )
        self.botao_verificar_fechamento.clicked.connect(
            self.verificar_fechamento_pendente
        )
        self._atualizar_venda_exibida()

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        if self.paginas.currentWidget() is self.pagina_frente_caixa:
            self._restaurar_foco_entrada()

    def mostrar_frente_caixa(self) -> None:
        if not self._usuario_pode_operar():
            return
        self.paginas.setCurrentWidget(self.pagina_frente_caixa)
        self.botao_navegar_caixa.setChecked(True)
        self._restaurar_foco_entrada()

    def mostrar_historico(self) -> None:
        if not self._usuario_pode_operar():
            return
        if self.dialogo_atual is not None:
            self.botao_navegar_caixa.setChecked(True)
            return
        if self._fechamento_bloqueia_operacao():
            self._definir_status(
                "Resolva o fechamento pendente antes de sair da Frente de Caixa.",
                "alerta",
            )
            self.botao_navegar_caixa.setChecked(True)
            self._restaurar_foco_entrada()
            return

        self.paginas.setCurrentWidget(self.pagina_historico)
        self.botao_navegar_historico.setChecked(True)
        self.pagina_historico.restaurar_foco()

    def mostrar_produtos(self) -> None:
        if not self._usuario_pode_operar():
            self._definir_status(
                "A página Produtos exige uma sessão operacional válida.",
                "erro",
            )
            self.botao_navegar_caixa.setChecked(True)
            return
        if self.dialogo_atual is not None:
            self.botao_navegar_caixa.setChecked(True)
            return
        if self._fechamento_bloqueia_operacao():
            self._definir_status(
                "Resolva o fechamento pendente antes de sair da Frente de Caixa.",
                "alerta",
            )
            self.botao_navegar_caixa.setChecked(True)
            self._restaurar_foco_entrada()
            return

        self.paginas.setCurrentWidget(self.pagina_produtos)
        self.botao_navegar_produtos.setChecked(True)
        self.pagina_produtos.ativar()

    def mostrar_administracao(self) -> None:
        if not self._usuario_pode_administrar_produtos():
            self._definir_status(
                "A página Administração exige perfil Administrador.",
                "erro",
            )
            self.botao_navegar_caixa.setChecked(True)
            return
        if self.dialogo_atual is not None:
            self.botao_navegar_caixa.setChecked(True)
            return
        if self._fechamento_bloqueia_operacao():
            self._definir_status(
                "Resolva o fechamento pendente antes de sair da Frente de Caixa.",
                "alerta",
            )
            self.botao_navegar_caixa.setChecked(True)
            self._restaurar_foco_entrada()
            return

        self.paginas.setCurrentWidget(self.pagina_administracao)
        self.botao_navegar_administracao.setChecked(True)
        self.pagina_administracao.ativar()

    def processar_entrada(self) -> None:
        if not self._usuario_pode_operar():
            return
        if (
            self.dialogo_atual is not None
            or self._processando_entrada
            or self._fechamento_bloqueia_operacao()
        ):
            return

        self._processando_entrada = True

        try:
            codigo = self.campo_entrada.text().strip()
            self.rotulo_status.clear()

            if codigo == "9999":
                self._abrir_dialogo(DialogoDiversos(self))
                return

            if len(codigo) == 13:
                self._processar_etiqueta(codigo)
                return

            self._processar_codigo_produto(codigo)
        finally:
            self._processando_entrada = False

    def _processar_enter(self) -> None:
        if self._ignorar_proximo_enter:
            self._ignorar_proximo_enter = False
            return

        self.processar_entrada()

    def _processar_etiqueta_automaticamente(self, texto: str) -> None:
        if self._processando_entrada or self.dialogo_atual is not None:
            return

        if texto and self._ignorar_proximo_enter:
            self._ignorar_proximo_enter = False

        codigo = texto.strip()
        if len(codigo) != 13 or not codigo.isascii() or not codigo.isdigit():
            return

        self._ignorar_proximo_enter = True
        self.processar_entrada()

    def _processar_etiqueta(self, codigo: str) -> None:
        produto_etiqueta, erros = associar_etiqueta_ao_produto(
            codigo,
            self.caminho_banco,
        )

        if erros:
            self._concluir_com_erro(erros)
            return

        try:
            item = criar_item_de_etiqueta_com_estimativa(produto_etiqueta)
        except (TypeError, ValueError) as erro:
            self._concluir_com_erro([str(erro)])
            return

        self._emitir_item(item)
        self._limpar_entrada_e_restaurar_foco()

    def _processar_codigo_produto(self, codigo: str) -> None:
        produto, erros = consultar_produto_por_codigo(
            codigo,
            self.caminho_banco,
        )

        if erros:
            self._concluir_com_erro(erros)
            return

        if produto.ativo is not True:
            self._concluir_com_erro(["O produto está inativo."])
            return

        if produto.forma_venda == "UNIDADE":
            self._abrir_dialogo(DialogoUnidade(produto, self))
        elif produto.forma_venda == "PESO":
            self._abrir_dialogo(DialogoPeso(produto, self))
        else:
            self._concluir_com_erro(
                ["A forma de venda do produto não é suportada."]
            )

    def _abrir_dialogo(self, dialogo: QDialog) -> None:
        self.dialogo_atual = dialogo
        dialogo.item_confirmado.connect(self._emitir_item)
        dialogo.finished.connect(
            lambda resultado: self._finalizar_dialogo(dialogo, resultado)
        )
        dialogo.open()

    def _emitir_item(self, item) -> None:
        self._definir_status("Item confirmado.", "sucesso")
        self.item_criado.emit(item)

    def _adicionar_item_a_venda(self, item: ItemVenda) -> None:
        if not self._usuario_pode_operar() or self._fechamento_bloqueia_operacao():
            return
        havia_pagamentos = self.composicao_pagamentos is not None
        self.estado_venda = adicionar_no_estado(self.estado_venda, item)
        self._invalidar_pagamentos_apos_alteracao(havia_pagamentos)
        self._atualizar_venda_exibida()

    def remover_item_selecionado(self) -> None:
        if not self._usuario_pode_operar() or self._fechamento_bloqueia_operacao():
            return
        if not self.estado_venda.venda.itens:
            self._restaurar_foco_entrada()
            return

        linhas_selecionadas = self.tabela_itens.selectionModel().selectedRows()
        indice = (
            linhas_selecionadas[0].row()
            if linhas_selecionadas
            else len(self.estado_venda.venda.itens) - 1
        )
        havia_pagamentos = self.composicao_pagamentos is not None
        self.estado_venda = remover_com_desfazer(self.estado_venda, indice)
        self._invalidar_pagamentos_apos_alteracao(havia_pagamentos)
        self._atualizar_venda_exibida()
        self._restaurar_foco_entrada()

    def desfazer_ultima_remocao(self) -> None:
        if not self._usuario_pode_operar() or self._fechamento_bloqueia_operacao():
            return
        estado_anterior = self.estado_venda
        havia_pagamentos = self.composicao_pagamentos is not None
        self.estado_venda = desfazer_ultima_remocao(self.estado_venda)
        if self.estado_venda is not estado_anterior:
            self._invalidar_pagamentos_apos_alteracao(havia_pagamentos)
        self._atualizar_venda_exibida()
        self._restaurar_foco_entrada()

    def abrir_dialogo_pagamentos(self) -> None:
        if not self._usuario_pode_operar():
            return
        if (
            self.dialogo_atual is not None
            or self._fechamento_bloqueia_operacao()
        ):
            return

        total_venda = calcular_total(self.estado_venda.venda)
        if total_venda <= 0:
            self._definir_status(
                "Adicione ao menos um item com valor antes do pagamento.",
                "alerta",
            )
            self._restaurar_foco_entrada()
            return

        dialogo = DialogoPagamentos(
            total_venda,
            self,
            estado_inicial=self.composicao_pagamentos,
        )
        self.dialogo_atual = dialogo
        dialogo.pagamentos_confirmados.connect(
            self._emitir_pagamentos_confirmados
        )
        dialogo.finished.connect(
            lambda resultado: self._finalizar_dialogo(dialogo, resultado)
        )
        dialogo.open()

    def _emitir_pagamentos_confirmados(self, pagamentos) -> None:
        if not self._usuario_pode_operar() or self._fechamento_bloqueia_operacao():
            return
        composicao_alterada = pagamentos != self.composicao_pagamentos
        self.composicao_pagamentos = pagamentos
        self.resultado_confirmacao = None
        if composicao_alterada:
            self._reiniciar_tentativa_fechamento()
        self._definir_status("Pagamentos compostos.", "sucesso")
        self.pagamentos_confirmados.emit(pagamentos)
        self._atualizar_venda_exibida()

    def abrir_dialogo_confirmacao(self) -> None:
        if not self._usuario_pode_operar():
            return
        if (
            self.dialogo_atual is not None
            or self._fechamento_bloqueia_operacao()
        ):
            return

        if self.composicao_pagamentos is None:
            self._definir_status(
                "Conclua a composição dos pagamentos antes de confirmar.",
                "alerta",
            )
            self._restaurar_foco_entrada()
            return

        try:
            dialogo = DialogoConfirmacaoVenda(
                self.estado_venda.venda,
                self.composicao_pagamentos,
                self,
            )
        except (TypeError, ValueError) as erro:
            self._definir_status(str(erro), "erro")
            self._restaurar_foco_entrada()
            return

        self.dialogo_atual = dialogo
        dialogo.venda_confirmada.connect(self._receber_venda_confirmada)
        dialogo.finished.connect(
            lambda resultado: self._finalizar_dialogo(dialogo, resultado)
        )
        dialogo.open()

    def _receber_venda_confirmada(self, resultado: VendaConfirmada) -> None:
        if not self._usuario_pode_operar() or self._fechamento_bloqueia_operacao():
            return
        self.resultado_confirmacao = resultado
        self.confirmacao_pendente = resultado
        self.venda_confirmada.emit(resultado)
        self._persistir_fechamento_pendente()

    def verificar_fechamento_pendente(self) -> None:
        if not self._usuario_pode_operar():
            return
        if (
            not self._fechamento_incerto
            or self.confirmacao_pendente is None
            or self.identificador_tentativa_fechamento is None
            or self._fechamento_em_processamento
        ):
            return

        self._fechamento_incerto = False
        self._persistir_fechamento_pendente()

    def _persistir_fechamento_pendente(self) -> None:
        if self._fechamento_em_processamento:
            return
        if self.confirmacao_pendente is None:
            return

        if self.identificador_tentativa_fechamento is None:
            self.identificador_tentativa_fechamento = (
                persistencia_venda_service.gerar_identificador_tentativa()
            )

        self._fechamento_em_processamento = True
        self._definir_status("Registrando venda...")
        self._atualizar_venda_exibida()
        try:
            venda_id = (
                persistencia_venda_service
                .persistir_venda_confirmada_idempotente(
                    self.confirmacao_pendente,
                    self.identificador_tentativa_fechamento,
                    self.caminho_banco,
                )
            )
        except persistencia_venda_service.CommitVendaIncertoError:
            self._fechamento_incerto = True
            self._definir_status(
                "O resultado do fechamento é incerto. A venda foi preservada. "
                "Use Verificar fechamento antes de continuar.",
                "alerta",
            )
        except Exception as erro:
            self._fechamento_incerto = False
            self._definir_status(
                "A venda não foi registrada. Os dados foram preservados: "
                f"{erro}",
                "erro",
            )
        else:
            self._concluir_fechamento_com_sucesso(venda_id)
        finally:
            self._fechamento_em_processamento = False
            self._atualizar_venda_exibida()
            self._restaurar_foco_entrada()

    def _concluir_fechamento_com_sucesso(self, venda_id: int) -> None:
        self.ultimo_id_venda_persistida = venda_id
        self.estado_venda = EstadoVenda(venda=VendaEmAndamento())
        self.composicao_pagamentos = None
        self.resultado_confirmacao = None
        self.confirmacao_pendente = None
        self.identificador_tentativa_fechamento = None
        self._fechamento_incerto = False
        self._definir_status(
            f"Venda #{venda_id:06d} registrada com sucesso.",
            "sucesso",
        )
        self.venda_persistida.emit(venda_id)

    def _invalidar_pagamentos_apos_alteracao(
        self,
        havia_pagamentos: bool,
    ) -> None:
        self.composicao_pagamentos = None
        self.resultado_confirmacao = None
        self._reiniciar_tentativa_fechamento()
        if havia_pagamentos:
            self._definir_status(
                "Os pagamentos foram invalidados porque a venda foi alterada.",
                "alerta",
            )

    def _atualizar_venda_exibida(self) -> None:
        itens = self.estado_venda.venda.itens
        self.tabela_itens.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            valores = (
                self._descricao_item(item),
                self._quantidade_item(item),
                self._preco_item(item),
                formatar_centavos(item.subtotal_centavos),
            )
            for coluna, valor in enumerate(valores):
                self.tabela_itens.setItem(
                    linha,
                    coluna,
                    QTableWidgetItem(valor),
                )

        self.tabela_itens.clearSelection()
        total = calcular_total(self.estado_venda.venda)
        self.rotulo_total.setText(f"Total: {formatar_centavos(total)}")
        sessao_valida = self._usuario_pode_operar(mostrar_mensagem=False)
        operacao_bloqueada = self._fechamento_bloqueia_operacao()
        if (
            operacao_bloqueada
            and self.paginas.currentWidget() is not self.pagina_frente_caixa
        ):
            self.paginas.setCurrentWidget(self.pagina_frente_caixa)
            self.botao_navegar_caixa.setChecked(True)
        self.botao_navegar_caixa.setEnabled(sessao_valida)
        self.botao_navegar_historico.setEnabled(sessao_valida and not operacao_bloqueada)
        self.botao_navegar_produtos.setEnabled(
            sessao_valida
            and not operacao_bloqueada
        )
        self.botao_navegar_administracao.setEnabled(
            sessao_valida
            and self.sessao.perfil == "ADMINISTRADOR"
            and not operacao_bloqueada
        )
        self.botao_logout.setEnabled(sessao_valida and not operacao_bloqueada)
        self.botao_codigos_recuperacao.setEnabled(
            sessao_valida
            and self.sessao.perfil == "ADMINISTRADOR"
            and not operacao_bloqueada
        )
        self.campo_entrada.setEnabled(sessao_valida and not operacao_bloqueada)
        self.tabela_itens.setEnabled(sessao_valida and not operacao_bloqueada)
        self.botao_remover.setEnabled(bool(itens) and sessao_valida and not operacao_bloqueada)
        self.botao_desfazer.setEnabled(
            self.estado_venda.ultima_remocao is not None
            and sessao_valida
            and not operacao_bloqueada
        )
        self.botao_pagamento.setEnabled(total > 0 and sessao_valida and not operacao_bloqueada)
        self.botao_confirmar_venda.setEnabled(
            self.composicao_pagamentos is not None
            and sessao_valida
            and not operacao_bloqueada
        )
        self.botao_verificar_fechamento.setEnabled(
            sessao_valida
            and self._fechamento_incerto
            and not self._fechamento_em_processamento
        )

    def solicitar_logout(self) -> None:
        if self._fechamento_bloqueia_operacao():
            self._definir_status(
                "Resolva o fechamento pendente antes de encerrar a sessão.",
                "alerta",
            )
            return
        if self._atendimento_impede_logout():
            self._definir_status(
                "Finalize ou esvazie o atendimento antes de trocar o operador.",
                "alerta",
            )
            return
        self._encerramento_autorizado = True
        encerrar_sessao(self.sessao)
        self.logout_realizado.emit()
        self.close()

    def closeEvent(self, evento) -> None:
        if self._encerramento_autorizado:
            evento.accept()
            return
        if self._fechamento_bloqueia_operacao() or self._atendimento_impede_logout():
            self._definir_status(
                "Finalize ou esvazie o atendimento antes de encerrar o sistema.",
                "alerta",
            )
            evento.ignore()
            return
        encerrar_sessao(self.sessao)
        evento.accept()

    def abrir_codigos_recuperacao(self) -> None:
        if not self._usuario_pode_administrar_produtos():
            self._definir_status(
                "A emissão de códigos exige perfil Administrador.",
                "erro",
            )
            return
        if self.dialogo_atual is not None or self._fechamento_bloqueia_operacao():
            return

        dialogo = DialogoCodigosRecuperacao(
            self.sessao,
            self.caminho_banco,
            self,
        )
        self.dialogo_atual = dialogo
        dialogo.finished.connect(
            lambda resultado: self._finalizar_dialogo(dialogo, resultado)
        )
        dialogo.open()

    def _usuario_pode_operar(self, *, mostrar_mensagem: bool = True) -> bool:
        return self._sessao_permite(
            ("ADMINISTRADOR", "CAIXA"),
            mostrar_mensagem=mostrar_mensagem,
        )

    def _usuario_pode_administrar_produtos(self) -> bool:
        return self._sessao_permite(("ADMINISTRADOR",))

    def _sessao_permite(
        self,
        perfis: tuple[str, ...],
        *,
        mostrar_mensagem: bool = True,
    ) -> bool:
        try:
            autorizar_sessao(self.sessao, perfis, self.caminho_banco)
        except PermissaoNegadaError:
            if mostrar_mensagem:
                self._definir_status(
                    "O perfil autenticado não possui permissão para esta operação.",
                    "erro",
                )
            return False
        except Exception:
            if mostrar_mensagem:
                self._definir_status(
                    "A sessão não é mais válida. Reinicie e autentique-se novamente.",
                    "erro",
                )
            return False
        return True

    def _reiniciar_tentativa_fechamento(self) -> None:
        self.identificador_tentativa_fechamento = None
        self.confirmacao_pendente = None
        self._fechamento_incerto = False

    def _fechamento_bloqueia_operacao(self) -> bool:
        return self._fechamento_em_processamento or self._fechamento_incerto

    def _atendimento_impede_logout(self) -> bool:
        return bool(
            self.estado_venda.venda.itens
            or self.composicao_pagamentos is not None
            or self.confirmacao_pendente is not None
            or self.dialogo_atual is not None
        )

    @staticmethod
    def _descricao_item(item: ItemVenda) -> str:
        if item.tipo_item == "DIVERSOS":
            return DESCRICAO_DIVERSOS
        if item.produto is not None:
            return item.produto.nome
        return "Item sem descrição"

    @staticmethod
    def _quantidade_item(item: ItemVenda) -> str:
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

    @staticmethod
    def _preco_item(item: ItemVenda) -> str:
        if item.produto is None:
            return "—"

        preco = formatar_centavos(item.produto.preco_referencia_centavos)
        if item.produto.forma_venda == "PESO":
            return f"{preco}/kg"
        if item.produto.forma_venda == "UNIDADE":
            return f"{preco}/un."
        return preco

    def _finalizar_dialogo(self, dialogo: QDialog, resultado: int) -> None:
        if resultado == QDialog.DialogCode.Rejected:
            self._definir_status("Operação cancelada.")

        if self.dialogo_atual is dialogo:
            self.dialogo_atual = None

        dialogo.deleteLater()
        self._limpar_entrada_e_restaurar_foco()

    def _definir_status(self, texto: str, tipo: str = "neutro") -> None:
        self.rotulo_status.setProperty("tipoStatus", tipo)
        self.rotulo_status.setText(texto)
        estilo = self.rotulo_status.style()
        estilo.unpolish(self.rotulo_status)
        estilo.polish(self.rotulo_status)

    def _concluir_com_erro(self, erros: list[str]) -> None:
        self._definir_status("\n".join(erros), "erro")
        self._limpar_entrada_e_restaurar_foco()

    def _limpar_entrada_e_restaurar_foco(self) -> None:
        with QSignalBlocker(self.campo_entrada):
            self.campo_entrada.clear()
        self._restaurar_foco_entrada()

    def _restaurar_foco_entrada(self) -> None:
        QTimer.singleShot(0, self._aplicar_foco_entrada)

    def _aplicar_foco_entrada(self) -> None:
        if (
            self.paginas.currentWidget() is self.pagina_frente_caixa
            and self.campo_entrada.isEnabled()
        ):
            self.campo_entrada.setFocus()
