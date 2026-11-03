from PySide6.QtCore import QSignalBlocker, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from database.conexao import CAMINHO_BANCO
from interface.dialogos_entrada import (
    DialogoDiversos,
    DialogoPeso,
    DialogoUnidade,
)
from services.item_venda_service import criar_item_de_etiqueta_com_estimativa
from services.produto_etiqueta import associar_etiqueta_ao_produto
from services.produto_service import consultar_produto_por_codigo


class JanelaPrincipal(QMainWindow):
    """Janela principal com entrada única para códigos do PDV."""

    item_criado = Signal(object)

    def __init__(self, caminho_banco=CAMINHO_BANCO) -> None:
        super().__init__()
        self.caminho_banco = caminho_banco
        self.dialogo_atual: QDialog | None = None
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
        layout.addStretch()

        self.setCentralWidget(area_vendas)

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
        QTimer.singleShot(
            0,
            self.campo_entrada,
            self.campo_entrada.setFocus,
        )
