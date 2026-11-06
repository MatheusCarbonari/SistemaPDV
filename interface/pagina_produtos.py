from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
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

        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.campo_codigo = QLineEdit()
        self.campo_codigo.setObjectName("produto_codigo")
        self.campo_nome = QLineEdit()
        self.campo_nome.setObjectName("produto_nome")
        self.campo_categoria = QComboBox()
        self.campo_categoria.setObjectName("produto_categoria")
        for categoria in categorias:
            rotulo = categoria.nome
            if not categoria.ativo:
                rotulo += " (inativa)"
            self.campo_categoria.addItem(rotulo, categoria)
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
        self.botao_historico_precos = QPushButton("Histórico de preços")
        self.botao_historico_precos.setObjectName("historico_precos_produto")
        self.botao_gerenciar_categorias = QPushButton("Gerenciar categorias")
        self.botao_gerenciar_categorias.setObjectName("gerenciar_categorias")
        acoes.addWidget(self.botao_cadastrar)
        acoes.addWidget(self.botao_editar)
        acoes.addWidget(self.botao_alterar_situacao)
        acoes.addWidget(self.botao_historico_precos)
        acoes.addWidget(self.botao_gerenciar_categorias)
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
                self.tabela_produtos.setItem(linha, coluna, item)

        self.rotulo_mensagem.setText(
            f"{len(produtos)} produto(s) encontrado(s)."
            if produtos
            else "Nenhum produto encontrado."
        )
        self._atualizar_acoes_selecao()

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
