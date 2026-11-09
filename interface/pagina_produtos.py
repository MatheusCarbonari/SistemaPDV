from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.conexao import CAMINHO_BANCO
from interface.dialogo_categorias import DialogoCategorias
from interface.dialogo_historico_precos import DialogoHistoricoPrecos
from interface.dialogo_autorizacao_administrativa import (
    DialogoAutorizacaoAdministrativa,
)
from interface.formatacao import centavos_para_texto, formatar_centavos, ler_centavos
from models.produto import Produto
from models.comando_produto import (
    ComandoCadastroProduto,
    ComandoEdicaoProduto,
)
from models.sessao_usuario import SessaoUsuario
from services.produto_service import (
    alterar_situacao_produto,
    executar_cadastro_produto,
    executar_edicao_produto,
    listar_produtos,
    preparar_comando_cadastro_produto,
    preparar_comando_edicao_produto,
)
from services.autorizacao_pontual_service import (
    AutorizacaoPontualExpiradaError,
    AutorizacaoPontualInvalidaError,
    GERENCIADOR_AUTORIZACOES,
)
from services.categoria_service import listar_categorias


MENSAGEM_RESTRICAO_ATENDIMENTO = (
    "Finalize ou esvazie a venda em andamento antes de editar, ativar ou "
    "desativar produtos. Novos cadastros continuam permitidos."
)
MENSAGEM_FECHAMENTO_PENDENTE = (
    "Resolva o fechamento pendente antes de administrar produtos."
)


class DialogoProduto(QDialog):
    """Formulário auxiliar para cadastrar ou editar um produto."""

    dados_confirmados = Signal(object)

    def __init__(
        self,
        produto: Produto | None = None,
        categorias=(),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.produto = produto
        self.setModal(True)
        self.setWindowTitle("Editar produto" if produto else "Cadastrar produto")
        self.setObjectName("dialogo_produto")
        self.resize(600, 450)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        self.rotulo_estado = QLabel(
            f"Editando produto {produto.codigo}" if produto else "Novo produto"
        )
        self.rotulo_estado.setObjectName("estado_formulario_produto")
        layout.addWidget(self.rotulo_estado)

        self.grupo_identificacao = QGroupBox("Identificação")
        formulario_identificacao = QGridLayout(self.grupo_identificacao)
        formulario_identificacao.setContentsMargins(12, 18, 12, 12)
        formulario_identificacao.setHorizontalSpacing(10)
        formulario_identificacao.setVerticalSpacing(10)
        self.campo_codigo = QLineEdit()
        self.campo_codigo.setObjectName("produto_codigo")
        self.campo_codigo.setFixedSize(140, 30)
        self.campo_nome = QLineEdit()
        self.campo_nome.setObjectName("produto_nome")
        self.campo_nome.setFixedSize(320, 30)
        self.bloco_codigo = self._criar_bloco_campo(
            "Código",
            self.campo_codigo,
        )
        self.bloco_nome = self._criar_bloco_campo("Nome", self.campo_nome)
        formulario_identificacao.addWidget(self.bloco_codigo, 0, 0)
        formulario_identificacao.addWidget(self.bloco_nome, 0, 1)
        formulario_identificacao.setColumnStretch(2, 1)
        layout.addWidget(self.grupo_identificacao)

        self.grupo_comercial = QGroupBox("Classificação e venda")
        formulario = QGridLayout(self.grupo_comercial)
        formulario.setContentsMargins(12, 18, 12, 12)
        formulario.setHorizontalSpacing(10)
        formulario.setVerticalSpacing(12)
        self.campo_categoria = QComboBox()
        self.campo_categoria.setObjectName("produto_categoria")
        self.campo_categoria.setFixedSize(210, 30)
        for categoria in categorias:
            rotulo = categoria.nome
            if not categoria.ativo:
                rotulo += " (inativa)"
            self.campo_categoria.addItem(rotulo, categoria)
        self.combo_forma_venda = QComboBox()
        self.combo_forma_venda.setObjectName("produto_forma_venda")
        self.combo_forma_venda.setFixedSize(130, 30)
        self.combo_forma_venda.addItems(("PESO", "UNIDADE"))
        self.campo_preco = QLineEdit()
        self.campo_preco.setObjectName("produto_preco")
        self.campo_preco.setFixedSize(130, 30)
        self.campo_preco.setPlaceholderText("0,00")
        self.combo_origem = QComboBox()
        self.combo_origem.setObjectName("produto_origem")
        self.combo_origem.setFixedSize(150, 30)
        self.combo_origem.addItems(("COMPRADO", "PRODUZIDO"))
        self.bloco_categoria = self._criar_bloco_campo(
            "Categoria",
            self.campo_categoria,
        )
        self.bloco_forma_venda = self._criar_bloco_campo(
            "Forma de venda",
            self.combo_forma_venda,
        )
        self.bloco_preco = self._criar_bloco_campo(
            "Preço de venda (R$)",
            self.campo_preco,
        )
        self.bloco_origem = self._criar_bloco_campo(
            "Origem",
            self.combo_origem,
        )
        formulario.addWidget(self.bloco_categoria, 0, 0)
        formulario.addWidget(self.bloco_forma_venda, 0, 1)
        formulario.addWidget(self.bloco_preco, 1, 0)
        formulario.addWidget(self.bloco_origem, 1, 1)
        formulario.setColumnStretch(0, 1)
        formulario.setColumnStretch(1, 1)
        formulario.setColumnStretch(2, 1)
        layout.addWidget(self.grupo_comercial)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_formulario_produto")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        self.botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.botoes.accepted.connect(self.confirmar)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)
        self._aplicar_tema_escuro()

        if produto is not None:
            self.campo_codigo.setText(produto.codigo)
            self.campo_codigo.setReadOnly(True)
            self.campo_nome.setText(produto.nome)
            for indice in range(self.campo_categoria.count()):
                categoria = self.campo_categoria.itemData(indice)
                if categoria.id == produto.categoria_id:
                    self.campo_categoria.setCurrentIndex(indice)
                    break
            self.combo_forma_venda.setCurrentText(produto.forma_venda)
            self.campo_preco.setText(
                centavos_para_texto(produto.preco_venda_centavos)
            )
            self.combo_origem.setCurrentText(produto.origem)

    def confirmar(self) -> None:
        try:
            preco_centavos = ler_centavos(self.campo_preco.text())
        except ValueError as erro:
            self.mostrar_erros((str(erro),))
            return

        categoria = self.campo_categoria.currentData()
        self.dados_confirmados.emit(
            {
                "codigo": self.campo_codigo.text(),
                "nome": self.campo_nome.text(),
                "categoria": categoria.nome if categoria is not None else "",
                "categoria_id": categoria.id if categoria is not None else None,
                "forma_venda": self.combo_forma_venda.currentText(),
                "preco_venda_centavos": preco_centavos,
                "origem": self.combo_origem.currentText(),
            }
        )

    def mostrar_erros(self, erros) -> None:
        self.rotulo_mensagem.setText("\n".join(str(erro) for erro in erros))

    @staticmethod
    def _criar_bloco_campo(rotulo: str, campo: QWidget) -> QWidget:
        bloco = QWidget()
        layout = QVBoxLayout(bloco)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        legenda = QLabel(rotulo)
        legenda.setObjectName("rotulo_campo_produto")
        layout.addWidget(legenda)
        layout.addWidget(campo, 0, Qt.AlignmentFlag.AlignLeft)
        return bloco

    def _aplicar_tema_escuro(self) -> None:
        self.setStyleSheet(
            """
            QDialog#dialogo_produto { background: #171a1f; color: #e8edf2; }
            QLabel { color: #e3e8ed; }
            QLabel#estado_formulario_produto {
                color: #f7fbff; font-size: 16px; font-weight: 700;
                background: #1d3040; border: 1px solid #4d83aa;
                border-radius: 5px; padding: 8px 10px;
            }
            QLabel#mensagem_formulario_produto { color: #ffb8b1; }
            QGroupBox {
                color: #dce4ea; border: 1px solid #404850;
                border-radius: 6px; margin-top: 9px; font-weight: 700;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit, QComboBox {
                color: #f5f7fa; background: #23272e; border: 1px solid #5b6570;
                border-radius: 5px; min-height: 26px; max-height: 26px;
                padding: 1px 7px;
            }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #4aa3df; }
            QPushButton {
                color: #e8edf2; background: #2a2f36; border: 1px solid #525d68;
                border-radius: 5px; min-height: 32px; padding: 3px 12px;
            }
            QPushButton:hover:enabled { background: #353c44; border-color: #687684; }
            """
        )


class DialogoConfirmacaoSituacaoProduto(QDialog):
    """Confirma a mudança de situação com botões proporcionais."""

    def __init__(self, produto: Produto, nova_situacao: bool, parent=None) -> None:
        super().__init__(parent)
        acao = "ativar" if nova_situacao else "desativar"
        self.setObjectName("confirmacao_situacao_produto")
        self.setWindowTitle(f"Confirmar {acao}")
        self.setModal(True)
        self.resize(440, 150)
        self.setMinimumSize(380, 140)
        self.setMaximumSize(500, 190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(12)
        self.rotulo_pergunta = QLabel(
            f"Deseja {acao} o produto {produto.codigo} — {produto.nome}?"
        )
        self.rotulo_pergunta.setObjectName("pergunta_situacao_produto")
        self.rotulo_pergunta.setWordWrap(True)
        layout.addWidget(self.rotulo_pergunta)

        self.botao_sim = QPushButton("Sim")
        self.botao_nao = QPushButton("Não")
        for botao in (self.botao_sim, self.botao_nao):
            botao.setFixedSize(96, 30)
        self.botao_nao.setDefault(True)
        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        botoes.addStretch()
        botoes.addWidget(self.botao_sim)
        botoes.addWidget(self.botao_nao)
        botoes.addStretch()
        layout.addLayout(botoes)
        self.botao_sim.clicked.connect(self.accept)
        self.botao_nao.clicked.connect(self.reject)
        self.setStyleSheet(
            """
            QDialog#confirmacao_situacao_produto {
                background: #171a1f; color: #e8edf2;
            }
            QLabel#pergunta_situacao_produto { color: #e3e8ed; font-size: 14px; }
            QPushButton {
                color: #e8edf2; background: #2a2f36; border: 1px solid #525d68;
                border-radius: 5px; min-width: 96px; min-height: 30px;
                max-height: 30px; padding: 0 10px;
            }
            QPushButton:hover { background: #353c44; border-color: #687684; }
            """
        )


class PaginaProdutos(QWidget):
    """Página interna para administração do catálogo de produtos."""

    def __init__(
        self,
        caminho_banco=CAMINHO_BANCO,
        *,
        tem_venda_em_andamento: Callable[[], bool] | None = None,
        operacao_bloqueada: Callable[[], bool] | None = None,
        alteracao_permitida: Callable[[], bool] | None = None,
        sessao_administrativa: SessaoUsuario | None = None,
        parent=None,
        gerenciador_autorizacoes=GERENCIADOR_AUTORIZACOES,
    ) -> None:
        super().__init__(parent)
        self.caminho_banco = caminho_banco
        self._tem_venda_em_andamento = tem_venda_em_andamento or (lambda: False)
        self._operacao_bloqueada = operacao_bloqueada or (lambda: False)
        self._alteracao_permitida = alteracao_permitida or (lambda: True)
        self.sessao_administrativa = sessao_administrativa
        self.gerenciador_autorizacoes = gerenciador_autorizacoes
        self._autorizacao_produto_em_processamento = False
        self.dialogo_autorizacao_produto = None
        self.dialogo_atual: QDialog | None = None
        self._filtros_empilhados: bool | None = None
        self._acoes_empilhadas: bool | None = None
        self.setObjectName("pagina_produtos")
        self._aplicar_tema_escuro()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(9)
        titulo = QLabel("Produtos")
        titulo.setObjectName("titulo_produtos")
        layout.addWidget(titulo)

        grupo_filtros = QGroupBox("Filtros")
        self.layout_filtros = QGridLayout(grupo_filtros)
        self.layout_filtros.setContentsMargins(10, 14, 10, 8)
        self.campo_pesquisa = QLineEdit()
        self.campo_pesquisa.setObjectName("pesquisa_produtos")
        self.campo_pesquisa.setPlaceholderText("Código ou nome")
        self.campo_pesquisa.setMaximumWidth(420)
        self.combo_situacao = QComboBox()
        self.combo_situacao.setObjectName("situacao_produtos")
        self.combo_situacao.addItem("Todos", None)
        self.combo_situacao.addItem("Ativos", True)
        self.combo_situacao.addItem("Inativos", False)
        self.combo_situacao.setMaximumWidth(180)
        self.botao_pesquisar = QPushButton("Pesquisar")
        self.botao_pesquisar.setObjectName("pesquisar_produtos")
        self.rotulo_pesquisa = QLabel("Pesquisa:")
        self.rotulo_situacao = QLabel("Situação:")
        layout.addWidget(grupo_filtros)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_produtos")
        self.rotulo_mensagem.setWordWrap(True)
        layout.addWidget(self.rotulo_mensagem)

        self.tabela_produtos = QTableWidget(0, 6)
        self.tabela_produtos.setObjectName("lista_produtos")
        self.tabela_produtos.setHorizontalHeaderLabels(
            ("Código", "Nome", "Categoria", "Forma", "Preço", "Situação")
        )
        self.tabela_produtos.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.tabela_produtos.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela_produtos.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela_produtos.setAlternatingRowColors(True)
        self.tabela_produtos.verticalHeader().setVisible(False)
        self.tabela_produtos.verticalHeader().setDefaultSectionSize(30)
        cabecalho = self.tabela_produtos.horizontalHeader()
        cabecalho.setStretchLastSection(False)
        for coluna in range(6):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeMode.Fixed)
        layout.addWidget(self.tabela_produtos)

        self.layout_acoes = QGridLayout()
        self.layout_acoes.setHorizontalSpacing(8)
        self.layout_acoes.setVerticalSpacing(6)
        self.botao_cadastrar = QPushButton("Cadastrar")
        self.botao_cadastrar.setObjectName("cadastrar_produto")
        self.botao_editar = QPushButton("Editar")
        self.botao_editar.setObjectName("editar_produto")
        self.botao_alterar_situacao = QPushButton("Ativar/desativar")
        self.botao_alterar_situacao.setObjectName("alterar_situacao_produto")
        self.botao_historico_precos = QPushButton("Histórico de preços")
        self.botao_historico_precos.setObjectName("historico_precos_produto")
        self.botao_gerenciar_categorias = QPushButton("Gerenciar categorias")
        self.botao_gerenciar_categorias.setObjectName("gerenciar_categorias")
        self._botoes_acoes = (
            self.botao_cadastrar,
            self.botao_editar,
            self.botao_alterar_situacao,
            self.botao_historico_precos,
            self.botao_gerenciar_categorias,
        )
        for botao in self._botoes_acoes:
            botao.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addLayout(self.layout_acoes)

        self.botao_pesquisar.clicked.connect(self.carregar_produtos)
        self.campo_pesquisa.returnPressed.connect(self.carregar_produtos)
        self.combo_situacao.currentIndexChanged.connect(self.carregar_produtos)
        self.botao_cadastrar.clicked.connect(self.abrir_cadastro)
        self.botao_editar.clicked.connect(self.abrir_edicao)
        self.botao_alterar_situacao.clicked.connect(
            self.alterar_situacao_selecionada
        )
        self.botao_historico_precos.clicked.connect(
            self.abrir_historico_precos
        )
        self.botao_gerenciar_categorias.clicked.connect(
            self.abrir_gerenciamento_categorias
        )
        self.tabela_produtos.itemSelectionChanged.connect(
            self._atualizar_acoes_selecao
        )
        self._atualizar_acoes_selecao()
        self._ajustar_layout_responsivo(self.width())

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
            QWidget#pagina_produtos { background: #171a1f; color: #e8edf2; }
            QLabel { color: #e3e8ed; background: transparent; }
            QLabel#titulo_produtos { color: #f7fbff; font-size: 20px; font-weight: 700; }
            QLabel#mensagem_produtos { color: #c7d0d8; padding: 2px 4px; }
            QGroupBox {
                color: #dce4ea; border: 1px solid #404850;
                border-radius: 6px; margin-top: 9px; font-weight: 700;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLineEdit, QComboBox {
                color: #f5f7fa; background: #23272e; border: 1px solid #5b6570;
                border-radius: 5px; min-height: 32px; padding: 2px 8px;
            }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #4aa3df; }
            QTableWidget {
                color: #f1f4f7; background: #181b20;
                alternate-background-color: #22272e;
                selection-color: #ffffff; selection-background-color: #2f75a6;
                border: 1px solid #424a53; border-radius: 4px;
                gridline-color: #343b43;
            }
            QTableWidget::item { padding: 4px 6px; }
            QHeaderView::section {
                color: #f4f6f8; background: #2b3038;
                border: 0; border-right: 1px solid #424a53;
                border-bottom: 1px solid #4a535d; padding: 6px; font-weight: 700;
            }
            QPushButton {
                color: #e8edf2; background: #2a2f36; border: 1px solid #525d68;
                border-radius: 5px; min-height: 32px; padding: 3px 11px;
            }
            QPushButton:hover:enabled { background: #353c44; border-color: #687684; }
            QPushButton:disabled { color: #929ba4; background: #22262c; border-color: #3e464e; }
            QPushButton#cadastrar_produto {
                color: #e8f4ff; background: #245477; border-color: #4d8fbd;
                font-weight: 700;
            }
            """
        )

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        if hasattr(self, "layout_filtros"):
            self._ajustar_layout_responsivo(evento.size().width())
            QTimer.singleShot(0, self._ajustar_larguras_tabela)

    def _ajustar_layout_responsivo(self, largura: int) -> None:
        filtros_empilhados = largura < 720
        if filtros_empilhados != self._filtros_empilhados:
            if filtros_empilhados:
                posicoes = (
                    (self.rotulo_pesquisa, 0, 0),
                    (self.campo_pesquisa, 0, 1),
                    (self.botao_pesquisar, 0, 2),
                    (self.rotulo_situacao, 1, 0),
                    (self.combo_situacao, 1, 1),
                )
            else:
                posicoes = (
                    (self.rotulo_pesquisa, 0, 0),
                    (self.campo_pesquisa, 0, 1),
                    (self.rotulo_situacao, 0, 2),
                    (self.combo_situacao, 0, 3),
                    (self.botao_pesquisar, 0, 4),
                )
            for widget, linha, coluna in posicoes:
                self.layout_filtros.addWidget(widget, linha, coluna)
            self.layout_filtros.setColumnStretch(1, 1)
            self._filtros_empilhados = filtros_empilhados

        acoes_empilhadas = largura < 900
        if acoes_empilhadas != self._acoes_empilhadas:
            for indice, botao in enumerate(self._botoes_acoes):
                if acoes_empilhadas:
                    linha = 0 if indice < 3 else 1
                    coluna = indice if indice < 3 else indice - 3
                else:
                    linha, coluna = 0, indice
                self.layout_acoes.addWidget(botao, linha, coluna)
            self.layout_acoes.setColumnStretch(5, 1)
            self._acoes_empilhadas = acoes_empilhadas

    def _ajustar_larguras_tabela(self) -> None:
        largura = self.tabela_produtos.viewport().width()
        if largura < 480:
            return
        proporcoes = (0.12, 0.30, 0.18, 0.13, 0.14)
        usadas = 0
        for coluna, proporcao in enumerate(proporcoes):
            largura_coluna = int(largura * proporcao)
            self.tabela_produtos.setColumnWidth(coluna, largura_coluna)
            usadas += largura_coluna
        self.tabela_produtos.setColumnWidth(5, largura - usadas)

    def ativar(self) -> None:
        self.carregar_produtos()
        self.restaurar_foco()

    def restaurar_foco(self) -> None:
        self.campo_pesquisa.setFocus()

    def carregar_produtos(self) -> None:
        try:
            produtos, erros = listar_produtos(
                ativo=self.combo_situacao.currentData(),
                termo=self.campo_pesquisa.text(),
                caminho_banco=self.caminho_banco,
            )
        except Exception as erro:
            self._mostrar_erro(erro)
            return

        if erros:
            self._mostrar_erro("\n".join(erros))
            return

        self.tabela_produtos.clearSelection()
        self.tabela_produtos.setRowCount(len(produtos))
        for linha, produto in enumerate(produtos):
            codigo = QTableWidgetItem(produto.codigo)
            codigo.setData(Qt.ItemDataRole.UserRole, produto)
            valores = (
                codigo,
                QTableWidgetItem(produto.nome),
                QTableWidgetItem(produto.categoria),
                QTableWidgetItem(produto.forma_venda),
                QTableWidgetItem(
                    formatar_centavos(produto.preco_venda_centavos)
                ),
                QTableWidgetItem("Ativo" if produto.ativo else "Inativo"),
            )
            for coluna, item in enumerate(valores):
                if coluna == 4:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                elif coluna in (0, 3, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabela_produtos.setItem(linha, coluna, item)

        self.rotulo_mensagem.setText(
            f"{len(produtos)} produto(s) encontrado(s)."
            if produtos
            else "Nenhum produto encontrado."
        )
        self._atualizar_acoes_selecao()
        QTimer.singleShot(0, self._ajustar_larguras_tabela)

    def abrir_cadastro(self) -> None:
        if not self._pode_operar() or self._bloqueado_por_fechamento():
            return
        categorias = self._categorias_para_formulario()
        if not categorias:
            self.rotulo_mensagem.setText(
                "Cadastre uma categoria ativa antes de cadastrar produtos."
            )
            return
        dialogo = DialogoProduto(categorias=categorias, parent=self)
        dialogo.dados_confirmados.connect(
            lambda dados: self._cadastrar(dialogo, dados)
        )
        self._abrir_dialogo(dialogo)

    def abrir_edicao(self) -> None:
        if not self._pode_alterar_produto_existente():
            return
        produto = self.produto_selecionado()
        if produto is None:
            self.rotulo_mensagem.setText("Selecione um produto para editar.")
            return
        categorias = self._categorias_para_formulario(produto)
        if not categorias:
            return
        dialogo = DialogoProduto(produto, categorias, self)
        dialogo.dados_confirmados.connect(
            lambda dados: self._editar(dialogo, produto, dados)
        )
        self._abrir_dialogo(dialogo)

    def alterar_situacao_selecionada(self) -> None:
        if not self._pode_administrar():
            return
        if not self._pode_alterar_produto_existente():
            return
        produto = self.produto_selecionado()
        if produto is None:
            self.rotulo_mensagem.setText(
                "Selecione um produto para ativar ou desativar."
            )
            return
        nova_situacao = not produto.ativo
        dialogo = DialogoConfirmacaoSituacaoProduto(
            produto,
            nova_situacao,
            self,
        )
        self.dialogo_confirmacao_situacao = dialogo
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            atualizado, erros = alterar_situacao_produto(
                produto.id,
                nova_situacao,
                self.caminho_banco,
                sessao_solicitante=self.sessao_administrativa,
            )
        except Exception as erro:
            self._mostrar_erro(erro)
            return
        if not atualizado:
            self._mostrar_erro("\n".join(erros))
            return
        self.carregar_produtos()
        self.rotulo_mensagem.setText(
            f"Produto {'ativado' if nova_situacao else 'desativado'} com sucesso."
        )

    def abrir_historico_precos(self) -> None:
        if not self._pode_administrar():
            return
        produto = self.produto_selecionado()
        if produto is None:
            self.rotulo_mensagem.setText(
                "Selecione um produto para consultar o histórico de preços."
            )
            return
        dialogo = DialogoHistoricoPrecos(
            self.sessao_administrativa,
            produto,
            self.caminho_banco,
            self,
        )
        self._abrir_dialogo(dialogo)

    def abrir_gerenciamento_categorias(self) -> None:
        if not self._pode_administrar() or self._bloqueado_por_fechamento():
            return
        dialogo = DialogoCategorias(
            self.sessao_administrativa,
            self.caminho_banco,
            self,
        )
        self._abrir_dialogo(dialogo)

    def _categorias_para_formulario(self, produto=None):
        try:
            categorias = listar_categorias(
                self.sessao_administrativa,
                self.caminho_banco,
            )
        except Exception:
            self.rotulo_mensagem.setText(
                "Não foi possível consultar as categorias. "
                "Confirme a sessão administrativa."
            )
            return ()
        return tuple(
            categoria
            for categoria in categorias
            if categoria.ativo
            or (
                produto is not None
                and categoria.id == produto.categoria_id
            )
        )

    def produto_selecionado(self) -> Produto | None:
        linhas = self.tabela_produtos.selectionModel().selectedRows()
        if not linhas:
            return None
        return self.tabela_produtos.item(linhas[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )

    def _cadastrar(self, dialogo: DialogoProduto, dados: dict) -> None:
        if not self._pode_operar():
            dialogo.mostrar_erros((self.rotulo_mensagem.text(),))
            return
        if self._bloqueado_por_fechamento():
            dialogo.mostrar_erros((MENSAGEM_FECHAMENTO_PENDENTE,))
            return
        try:
            comando, erros = preparar_comando_cadastro_produto(
                **dados,
                caminho_banco=self.caminho_banco,
            )
        except Exception as erro:
            dialogo.mostrar_erros((str(erro),))
            return
        if erros:
            dialogo.mostrar_erros(erros)
            return
        self._autorizar_ou_executar(dialogo, comando)

    def _editar(
        self,
        dialogo: DialogoProduto,
        produto: Produto,
        dados: dict,
    ) -> None:
        if not self._pode_alterar_produto_existente():
            dialogo.mostrar_erros((self.rotulo_mensagem.text(),))
            return
        try:
            dados = {**dados, "codigo": produto.codigo}
            comando, erros = preparar_comando_edicao_produto(
                produto.id,
                **dados,
                caminho_banco=self.caminho_banco,
            )
        except Exception as erro:
            dialogo.mostrar_erros((str(erro),))
            return
        if erros:
            dialogo.mostrar_erros(erros)
            return
        self._autorizar_ou_executar(dialogo, comando)

    def _autorizar_ou_executar(self, dialogo, comando) -> None:
        if self.sessao_administrativa.perfil == "ADMINISTRADOR":
            self._executar_comando(dialogo, comando)
            return
        if self._autorizacao_produto_em_processamento:
            return
        self._autorizacao_produto_em_processamento = True
        dialogo.botoes.setEnabled(False)
        autorizacao = DialogoAutorizacaoAdministrativa(
            self.sessao_administrativa,
            comando.operacao,
            comando.recurso_id,
            self._resumo_comando(comando),
            self.caminho_banco,
            dialogo,
            dados_autorizados_hash=comando.dados_autorizados_hash,
            gerenciador=self.gerenciador_autorizacoes,
        )
        self.dialogo_autorizacao_produto = autorizacao
        autorizacao.finished.connect(
            lambda resultado: self._finalizar_autorizacao_produto(
                dialogo,
                autorizacao,
                comando,
                resultado,
            )
        )
        autorizacao.open()

    def _finalizar_autorizacao_produto(
        self,
        dialogo,
        autorizacao,
        comando,
        resultado,
    ) -> None:
        if self.dialogo_autorizacao_produto is autorizacao:
            self.dialogo_autorizacao_produto = None
        capacidade = autorizacao.capacidade
        autorizacao.deleteLater()
        self._autorizacao_produto_em_processamento = False
        dialogo.botoes.setEnabled(True)
        if resultado != QDialog.DialogCode.Accepted or capacidade is None:
            dialogo.mostrar_erros(
                ("Autorização cancelada. Nenhuma alteração foi gravada.",)
            )
            return
        if self._operacao_bloqueada() or (
            isinstance(comando, ComandoEdicaoProduto)
            and self._tem_venda_em_andamento()
        ):
            try:
                self.gerenciador_autorizacoes.consumir(
                    capacidade,
                    self.sessao_administrativa,
                    comando.operacao,
                    comando.recurso_id,
                    self.caminho_banco,
                    dados_autorizados_hash=comando.dados_autorizados_hash,
                )
            except Exception:
                pass
            dialogo.mostrar_erros(
                (
                    "A operação foi bloqueada após a autorização. "
                    "Solicite uma nova autorização quando o bloqueio terminar.",
                )
            )
            return
        self._executar_comando(dialogo, comando, capacidade=capacidade)

    def _executar_comando(self, dialogo, comando, *, capacidade=None) -> None:
        try:
            if isinstance(comando, ComandoCadastroProduto):
                produto = executar_cadastro_produto(
                    comando,
                    self.sessao_administrativa,
                    self.caminho_banco,
                    capacidade=capacidade,
                    gerenciador_autorizacoes=self.gerenciador_autorizacoes,
                )
                mensagem = f"Produto {produto.codigo} cadastrado com sucesso."
            else:
                produto = executar_edicao_produto(
                    comando,
                    self.sessao_administrativa,
                    self.caminho_banco,
                    capacidade=capacidade,
                    gerenciador_autorizacoes=self.gerenciador_autorizacoes,
                )
                mensagem = f"Produto {produto.codigo} atualizado com sucesso."
        except AutorizacaoPontualExpiradaError:
            dialogo.mostrar_erros(
                ("A autorização expirou. Solicite uma nova autorização.",)
            )
            return
        except AutorizacaoPontualInvalidaError:
            dialogo.mostrar_erros(
                ("A autorização não corresponde mais aos dados aprovados.",)
            )
            return
        except Exception as erro:
            dialogo.mostrar_erros((str(erro),))
            return
        dialogo.accept()
        self.carregar_produtos()
        self.rotulo_mensagem.setText(mensagem)

    def _resumo_comando(self, comando) -> str:
        if isinstance(comando, ComandoCadastroProduto):
            return (
                "Autorizar cadastro de produto\n\n"
                f"Código: {comando.codigo}\n"
                f"Nome: {comando.nome}\n"
                f"Categoria: {comando.categoria.nome}\n"
                f"Forma de venda: {comando.forma_venda}\n"
                f"Preço: {formatar_centavos(comando.preco_venda_centavos)}\n"
                f"Origem: {comando.origem}"
            )
        base = comando.estado_base
        return (
            f"Autorizar edição do produto {base.codigo}\n\n"
            f"Nome: {base.nome} → {comando.nome}\n"
            f"Categoria: {base.categoria.nome} → {comando.categoria.nome}\n"
            f"Forma de venda: {base.forma_venda} → {comando.forma_venda}\n"
            f"Preço: {formatar_centavos(base.preco_venda_centavos)} → "
            f"{formatar_centavos(comando.preco_venda_centavos)}\n"
            f"Origem: {base.origem} → {comando.origem}"
        )

    def _abrir_dialogo(self, dialogo: QDialog) -> None:
        self.dialogo_atual = dialogo
        dialogo.finished.connect(lambda: self._finalizar_dialogo(dialogo))
        dialogo.open()

    def _finalizar_dialogo(self, dialogo: QDialog) -> None:
        if self.dialogo_atual is dialogo:
            self.dialogo_atual = None
        dialogo.deleteLater()
        self.restaurar_foco()

    def _pode_alterar_produto_existente(self) -> bool:
        if not self._pode_operar():
            return False
        if self._bloqueado_por_fechamento():
            return False
        if self._tem_venda_em_andamento():
            self.rotulo_mensagem.setText(MENSAGEM_RESTRICAO_ATENDIMENTO)
            return False
        return True

    def _pode_administrar(self) -> bool:
        if (
            self.sessao_administrativa is not None
            and self.sessao_administrativa.perfil == "ADMINISTRADOR"
            and self._alteracao_permitida()
        ):
            return True
        self.rotulo_mensagem.setText(
            "A administração de produtos exige perfil Administrador ativo."
        )
        return False

    def _pode_operar(self) -> bool:
        if (
            self.sessao_administrativa is not None
            and self._alteracao_permitida()
        ):
            return True
        self.rotulo_mensagem.setText(
            "A sessão não está habilitada para operar Produtos."
        )
        return False

    def _bloqueado_por_fechamento(self) -> bool:
        if not self._operacao_bloqueada():
            return False
        self.rotulo_mensagem.setText(MENSAGEM_FECHAMENTO_PENDENTE)
        return True

    def _mostrar_erro(self, erro) -> None:
        self.rotulo_mensagem.setText(str(erro))
        self.tabela_produtos.setRowCount(0)
        self._atualizar_acoes_selecao()

    def _atualizar_acoes_selecao(self) -> None:
        selecionado = self.produto_selecionado() is not None
        permitido = (
            self.sessao_administrativa is not None
            and self._alteracao_permitida()
        )
        administrador = (
            self.sessao_administrativa is not None
            and self.sessao_administrativa.perfil == "ADMINISTRADOR"
        )
        self.botao_cadastrar.setEnabled(permitido)
        self.botao_editar.setEnabled(selecionado and permitido)
        self.botao_alterar_situacao.setEnabled(
            selecionado and permitido and administrador
        )
        self.botao_historico_precos.setEnabled(
            selecionado
            and permitido
            and administrador
        )
        self.botao_gerenciar_categorias.setEnabled(
            permitido and administrador
        )
