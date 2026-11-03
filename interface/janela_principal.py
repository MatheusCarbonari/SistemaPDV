from PySide6.QtCore import QSignalBlocker, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
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
from interface.formatacao import formatar_centavos
from models.estado_venda import EstadoVenda
from models.item_venda import DESCRICAO_DIVERSOS, ItemVenda
from models.venda_em_andamento import VendaEmAndamento
from services.estado_venda_service import (
    adicionar_no_estado,
    desfazer_ultima_remocao,
    remover_com_desfazer,
)
from services.item_venda_service import criar_item_de_etiqueta_com_estimativa
from services.produto_etiqueta import associar_etiqueta_ao_produto
from services.produto_service import consultar_produto_por_codigo
from services.venda_em_andamento_service import calcular_total


class JanelaPrincipal(QMainWindow):
    """Janela principal com entrada única para códigos do PDV."""

    item_criado = Signal(object)

    def __init__(self, caminho_banco=CAMINHO_BANCO) -> None:
        super().__init__()
        self.caminho_banco = caminho_banco
        self.dialogo_atual: QDialog | None = None
        self.estado_venda = EstadoVenda(venda=VendaEmAndamento())
        self._processando_entrada = False
        self._ignorar_proximo_enter = False
        self.setWindowTitle("Sistema-PDV")
        self.resize(1024, 720)

        area_vendas = QWidget(self)
        area_vendas.setObjectName("area_vendas")

        layout = QVBoxLayout(area_vendas)
        titulo = QLabel("Área de vendas", area_vendas)
        titulo.setObjectName("titulo_area_vendas")
        layout.addWidget(titulo)

        self.campo_entrada = QLineEdit(area_vendas)
        self.campo_entrada.setObjectName("campo_entrada")
        self.campo_entrada.setPlaceholderText(
            "Leia a etiqueta ou digite o código do produto"
        )
        self.campo_entrada.textChanged.connect(
            self._processar_etiqueta_automaticamente
        )
        self.campo_entrada.returnPressed.connect(self._processar_enter)
        layout.addWidget(self.campo_entrada)

        self.rotulo_status = QLabel("", area_vendas)
        self.rotulo_status.setObjectName("status_entrada")
        layout.addWidget(self.rotulo_status)

        self.tabela_itens = QTableWidget(0, 4, area_vendas)
        self.tabela_itens.setObjectName("tabela_itens")
        self.tabela_itens.setHorizontalHeaderLabels(
            [
                "Produto/descrição",
                "Quantidade ou peso",
                "Preço unitário ou preço/kg",
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
        self.tabela_itens.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_itens)

        layout_acoes = QHBoxLayout()
        self.botao_remover = QPushButton("Remover", area_vendas)
        self.botao_remover.setObjectName("botao_remover")
        self.botao_desfazer = QPushButton("Desfazer", area_vendas)
        self.botao_desfazer.setObjectName("botao_desfazer")
        layout_acoes.addWidget(self.botao_remover)
        layout_acoes.addWidget(self.botao_desfazer)
        layout_acoes.addStretch()

        self.rotulo_total = QLabel("Total: R$ 0,00", area_vendas)
        self.rotulo_total.setObjectName("total_venda")
        layout_acoes.addWidget(self.rotulo_total)
        layout.addLayout(layout_acoes)

        self.setCentralWidget(area_vendas)
        self.item_criado.connect(self._adicionar_item_a_venda)
        self.botao_remover.clicked.connect(self.remover_item_selecionado)
        self.botao_desfazer.clicked.connect(self.desfazer_ultima_remocao)
        self._atualizar_venda_exibida()

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        QTimer.singleShot(
            0,
            self.campo_entrada,
            self.campo_entrada.setFocus,
        )

    def processar_entrada(self) -> None:
        if self.dialogo_atual is not None or self._processando_entrada:
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
        self.rotulo_status.setText("Item confirmado.")
        self.item_criado.emit(item)

    def _adicionar_item_a_venda(self, item: ItemVenda) -> None:
        self.estado_venda = adicionar_no_estado(self.estado_venda, item)
        self._atualizar_venda_exibida()

    def remover_item_selecionado(self) -> None:
        if not self.estado_venda.venda.itens:
            self._restaurar_foco_entrada()
            return

        linhas_selecionadas = self.tabela_itens.selectionModel().selectedRows()
        indice = (
            linhas_selecionadas[0].row()
            if linhas_selecionadas
            else len(self.estado_venda.venda.itens) - 1
        )
        self.estado_venda = remover_com_desfazer(self.estado_venda, indice)
        self._atualizar_venda_exibida()
        self._restaurar_foco_entrada()

    def desfazer_ultima_remocao(self) -> None:
        self.estado_venda = desfazer_ultima_remocao(self.estado_venda)
        self._atualizar_venda_exibida()
        self._restaurar_foco_entrada()

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
        self.botao_remover.setEnabled(bool(itens))
        self.botao_desfazer.setEnabled(
            self.estado_venda.ultima_remocao is not None
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
            self.rotulo_status.setText("Operação cancelada.")

        if self.dialogo_atual is dialogo:
            self.dialogo_atual = None

        dialogo.deleteLater()
        self._limpar_entrada_e_restaurar_foco()

    def _concluir_com_erro(self, erros: list[str]) -> None:
        self.rotulo_status.setText("\n".join(erros))
        self._limpar_entrada_e_restaurar_foco()

    def _limpar_entrada_e_restaurar_foco(self) -> None:
        with QSignalBlocker(self.campo_entrada):
            self.campo_entrada.clear()
        self._restaurar_foco_entrada()

    def _restaurar_foco_entrada(self) -> None:
        QTimer.singleShot(
            0,
            self.campo_entrada,
            self.campo_entrada.setFocus,
        )
