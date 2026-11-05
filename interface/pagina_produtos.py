from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.conexao import CAMINHO_BANCO
from interface.formatacao import centavos_para_texto, formatar_centavos, ler_centavos
from models.produto import Produto
from services.produto_service import (
    alterar_situacao_produto,
    atualizar_produto,
    cadastrar_produto,
    listar_produtos,
)


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

    def __init__(self, produto: Produto | None = None, parent=None) -> None:
        super().__init__(parent)
        self.produto = produto
        self.setModal(True)
        self.setWindowTitle("Editar produto" if produto else "Cadastrar produto")

        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.campo_codigo = QLineEdit()
        self.campo_codigo.setObjectName("produto_codigo")
        self.campo_nome = QLineEdit()
        self.campo_nome.setObjectName("produto_nome")
        self.campo_categoria = QLineEdit()
        self.campo_categoria.setObjectName("produto_categoria")
        self.combo_forma_venda = QComboBox()
        self.combo_forma_venda.setObjectName("produto_forma_venda")
        self.combo_forma_venda.addItems(("PESO", "UNIDADE"))
        self.campo_preco = QLineEdit()
        self.campo_preco.setObjectName("produto_preco")
        self.campo_preco.setPlaceholderText("0,00")
        self.combo_origem = QComboBox()
        self.combo_origem.setObjectName("produto_origem")
        self.combo_origem.addItems(("COMPRADO", "PRODUZIDO"))
        formulario.addRow("Código:", self.campo_codigo)
        formulario.addRow("Nome:", self.campo_nome)
        formulario.addRow("Categoria:", self.campo_categoria)
        formulario.addRow("Forma de venda:", self.combo_forma_venda)
        formulario.addRow("Preço de venda (R$):", self.campo_preco)
        formulario.addRow("Origem:", self.combo_origem)
        layout.addLayout(formulario)

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

        if produto is not None:
            self.campo_codigo.setText(produto.codigo)
            self.campo_codigo.setReadOnly(True)
            self.campo_nome.setText(produto.nome)
            self.campo_categoria.setText(produto.categoria)
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

        self.dados_confirmados.emit(
            {
                "codigo": self.campo_codigo.text(),
                "nome": self.campo_nome.text(),
                "categoria": self.campo_categoria.text(),
                "forma_venda": self.combo_forma_venda.currentText(),
                "preco_venda_centavos": preco_centavos,
                "origem": self.combo_origem.currentText(),
            }
        )

    def mostrar_erros(self, erros) -> None:
        self.rotulo_mensagem.setText("\n".join(str(erro) for erro in erros))


class PaginaProdutos(QWidget):
    """Página interna para administração do catálogo de produtos."""

    def __init__(
        self,
        caminho_banco=CAMINHO_BANCO,
        *,
        tem_venda_em_andamento: Callable[[], bool] | None = None,
        operacao_bloqueada: Callable[[], bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.caminho_banco = caminho_banco
        self._tem_venda_em_andamento = tem_venda_em_andamento or (lambda: False)
        self._operacao_bloqueada = operacao_bloqueada or (lambda: False)
        self.dialogo_atual: DialogoProduto | None = None
        self.setObjectName("pagina_produtos")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Produtos"))

        filtros = QHBoxLayout()
        self.campo_pesquisa = QLineEdit()
        self.campo_pesquisa.setObjectName("pesquisa_produtos")
        self.campo_pesquisa.setPlaceholderText("Código ou nome")
        self.combo_situacao = QComboBox()
        self.combo_situacao.setObjectName("situacao_produtos")
        self.combo_situacao.addItem("Todos", None)
        self.combo_situacao.addItem("Ativos", True)
        self.combo_situacao.addItem("Inativos", False)
        self.botao_pesquisar = QPushButton("Pesquisar")
        self.botao_pesquisar.setObjectName("pesquisar_produtos")
        filtros.addWidget(QLabel("Pesquisa:"))
        filtros.addWidget(self.campo_pesquisa)
        filtros.addWidget(QLabel("Situação:"))
        filtros.addWidget(self.combo_situacao)
        filtros.addWidget(self.botao_pesquisar)
        layout.addLayout(filtros)

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
        self.tabela_produtos.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_produtos)

        acoes = QHBoxLayout()
        self.botao_cadastrar = QPushButton("Cadastrar")
        self.botao_cadastrar.setObjectName("cadastrar_produto")
        self.botao_editar = QPushButton("Editar")
        self.botao_editar.setObjectName("editar_produto")
        self.botao_alterar_situacao = QPushButton("Ativar/desativar")
        self.botao_alterar_situacao.setObjectName("alterar_situacao_produto")
        acoes.addWidget(self.botao_cadastrar)
        acoes.addWidget(self.botao_editar)
        acoes.addWidget(self.botao_alterar_situacao)
        acoes.addStretch()
        layout.addLayout(acoes)

        self.botao_pesquisar.clicked.connect(self.carregar_produtos)
        self.campo_pesquisa.returnPressed.connect(self.carregar_produtos)
        self.combo_situacao.currentIndexChanged.connect(self.carregar_produtos)
        self.botao_cadastrar.clicked.connect(self.abrir_cadastro)
        self.botao_editar.clicked.connect(self.abrir_edicao)
        self.botao_alterar_situacao.clicked.connect(
            self.alterar_situacao_selecionada
        )
        self.tabela_produtos.itemSelectionChanged.connect(
            self._atualizar_acoes_selecao
        )
        self._atualizar_acoes_selecao()

    def ativar(self) -> None:
        self.carregar_produtos()
        self.restaurar_foco()

    def restaurar_foco(self) -> None:
        QTimer.singleShot(0, self.campo_pesquisa.setFocus)

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
                self.tabela_produtos.setItem(linha, coluna, item)

        self.rotulo_mensagem.setText(
            f"{len(produtos)} produto(s) encontrado(s)."
            if produtos
            else "Nenhum produto encontrado."
        )
        self._atualizar_acoes_selecao()

    def abrir_cadastro(self) -> None:
        if self._bloqueado_por_fechamento():
            return
        dialogo = DialogoProduto(parent=self)
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
        dialogo = DialogoProduto(produto, self)
        dialogo.dados_confirmados.connect(
            lambda dados: self._editar(dialogo, produto, dados)
        )
        self._abrir_dialogo(dialogo)

    def alterar_situacao_selecionada(self) -> None:
        if not self._pode_alterar_produto_existente():
            return
        produto = self.produto_selecionado()
        if produto is None:
            self.rotulo_mensagem.setText(
                "Selecione um produto para ativar ou desativar."
            )
            return
        nova_situacao = not produto.ativo
        acao = "ativar" if nova_situacao else "desativar"
        resposta = QMessageBox.question(
            self,
            f"Confirmar {acao}",
            f"Deseja {acao} o produto {produto.codigo} — {produto.nome}?",
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return

        try:
            atualizado, erros = alterar_situacao_produto(
                produto.id,
                nova_situacao,
                self.caminho_banco,
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

    def produto_selecionado(self) -> Produto | None:
        linhas = self.tabela_produtos.selectionModel().selectedRows()
        if not linhas:
            return None
        return self.tabela_produtos.item(linhas[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )

    def _cadastrar(self, dialogo: DialogoProduto, dados: dict) -> None:
        if self._bloqueado_por_fechamento():
            dialogo.mostrar_erros((MENSAGEM_FECHAMENTO_PENDENTE,))
            return
        try:
            produto, erros = cadastrar_produto(
                **dados,
                caminho_banco=self.caminho_banco,
            )
        except Exception as erro:
            dialogo.mostrar_erros((str(erro),))
            return
        if erros:
            dialogo.mostrar_erros(erros)
            return
        dialogo.accept()
        self.carregar_produtos()
        self.rotulo_mensagem.setText(
            f"Produto {produto.codigo} cadastrado com sucesso."
        )

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
            atualizado, erros = atualizar_produto(
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
        dialogo.accept()
        self.carregar_produtos()
        self.rotulo_mensagem.setText(
            f"Produto {atualizado.codigo} atualizado com sucesso."
        )

    def _abrir_dialogo(self, dialogo: DialogoProduto) -> None:
        self.dialogo_atual = dialogo
        dialogo.finished.connect(lambda: self._finalizar_dialogo(dialogo))
        dialogo.open()

    def _finalizar_dialogo(self, dialogo: DialogoProduto) -> None:
        if self.dialogo_atual is dialogo:
            self.dialogo_atual = None
        dialogo.deleteLater()
        self.restaurar_foco()

    def _pode_alterar_produto_existente(self) -> bool:
        if self._bloqueado_por_fechamento():
            return False
        if self._tem_venda_em_andamento():
            self.rotulo_mensagem.setText(MENSAGEM_RESTRICAO_ATENDIMENTO)
            return False
        return True

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
        self.botao_editar.setEnabled(selecionado)
        self.botao_alterar_situacao.setEnabled(selecionado)
