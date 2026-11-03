from decimal import Decimal

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from interface.formatacao import (
    centavos_para_texto,
    formatar_centavos,
    ler_centavos,
    ler_decimal,
)
from models.item_venda import DESCRICAO_DIVERSOS, ItemVenda
from models.produto import Produto
from services.item_venda_service import (
    criar_item_diversos,
    criar_item_manual_peso_por_quantidade,
    criar_item_manual_peso_por_valor,
    criar_item_manual_unidade,
)


class DialogoUnidade(QDialog):
    item_confirmado = Signal(object)

    def __init__(self, produto: Produto, parent=None) -> None:
        super().__init__(parent)
        self.produto = produto
        self.item_previa: ItemVenda | None = None
        self.setWindowTitle("Produto por unidade")
        self.setModal(True)

        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        formulario.addRow("Produto:", QLabel(produto.nome))
        formulario.addRow(
            "Preço unitário:",
            QLabel(formatar_centavos(produto.preco_venda_centavos)),
        )

        self.campo_quantidade = QLineEdit()
        self.campo_quantidade.setObjectName("campo_quantidade")
        formulario.addRow("Quantidade:", self.campo_quantidade)

        self.rotulo_subtotal = QLabel("—")
        self.rotulo_subtotal.setObjectName("subtotal_unidade")
        formulario.addRow("Subtotal:", self.rotulo_subtotal)
        layout.addLayout(formulario)

        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setObjectName("erro_dialogo_unidade")
        layout.addWidget(self.rotulo_erro)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

        self.campo_quantidade.textChanged.connect(self._atualizar_previa)
        self.campo_quantidade.returnPressed.connect(self.accept)

    def _atualizar_previa(self, texto: str) -> None:
        try:
            quantidade = ler_decimal(texto)
            self.item_previa = criar_item_manual_unidade(
                self.produto,
                quantidade,
            )
        except (TypeError, ValueError) as erro:
            self.item_previa = None
            self.rotulo_subtotal.setText("—")
            self.rotulo_erro.setText(str(erro))
            self.botoes.button(
                QDialogButtonBox.StandardButton.Ok
            ).setEnabled(False)
            return

        self.rotulo_subtotal.setText(
            formatar_centavos(self.item_previa.subtotal_centavos)
        )
        self.rotulo_erro.clear()
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def accept(self) -> None:
        if self.item_previa is None:
            return

        self.item_confirmado.emit(self.item_previa)
        super().accept()


class DialogoPeso(QDialog):
    item_confirmado = Signal(object)

    def __init__(self, produto: Produto, parent=None) -> None:
        super().__init__(parent)
        self.produto = produto
        self.item_previa: ItemVenda | None = None
        self.campo_principal: str | None = None
        self.setWindowTitle("Produto por peso")
        self.setModal(True)

        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        formulario.addRow("Produto:", QLabel(produto.nome))
        formulario.addRow(
            "Preço/kg:",
            QLabel(formatar_centavos(produto.preco_venda_centavos)),
        )

        self.campo_peso = QLineEdit()
        self.campo_peso.setObjectName("campo_peso")
        formulario.addRow("Peso (kg):", self.campo_peso)

        self.campo_valor = QLineEdit()
        self.campo_valor.setObjectName("campo_valor_peso")
        formulario.addRow("Valor total (R$):", self.campo_valor)

        self.rotulo_subtotal = QLabel("—")
        self.rotulo_subtotal.setObjectName("subtotal_peso")
        formulario.addRow("Subtotal:", self.rotulo_subtotal)
        layout.addLayout(formulario)

        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setObjectName("erro_dialogo_peso")
        layout.addWidget(self.rotulo_erro)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

        self.campo_peso.textChanged.connect(self._atualizar_por_peso)
        self.campo_valor.textChanged.connect(self._atualizar_por_valor)
        self.campo_peso.returnPressed.connect(self.accept)
        self.campo_valor.returnPressed.connect(self.accept)

    def _atualizar_por_peso(self, texto: str) -> None:
        self.campo_principal = "PESO"

        try:
            quantidade = ler_decimal(texto)
            item = criar_item_manual_peso_por_quantidade(
                self.produto,
                quantidade,
            )
        except (TypeError, ValueError) as erro:
            self._mostrar_erro(erro)
            return

        self.item_previa = item
        with QSignalBlocker(self.campo_valor):
            self.campo_valor.setText(
                centavos_para_texto(item.subtotal_centavos)
            )
        self._mostrar_item_valido(item)

    def _atualizar_por_valor(self, texto: str) -> None:
        self.campo_principal = "VALOR"

        try:
            subtotal_centavos = ler_centavos(texto)
            item = criar_item_manual_peso_por_valor(
                self.produto,
                subtotal_centavos,
            )
        except (TypeError, ValueError) as erro:
            self._mostrar_erro(erro)
            return

        self.item_previa = item
        with QSignalBlocker(self.campo_peso):
            self.campo_peso.setText(format(item.quantidade, "f"))
        self._mostrar_item_valido(item)

    def _mostrar_erro(self, erro: Exception) -> None:
        self.item_previa = None
        self.rotulo_subtotal.setText("—")
        self.rotulo_erro.setText(str(erro))
        self.botoes.button(
            QDialogButtonBox.StandardButton.Ok
        ).setEnabled(False)

    def _mostrar_item_valido(self, item: ItemVenda) -> None:
        self.rotulo_subtotal.setText(
            formatar_centavos(item.subtotal_centavos)
        )
        self.rotulo_erro.clear()
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def accept(self) -> None:
        if self.item_previa is None:
            return

        self.item_confirmado.emit(self.item_previa)
        super().accept()


class DialogoDiversos(QDialog):
    item_confirmado = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.item_previa: ItemVenda | None = None
        self.setWindowTitle(DESCRICAO_DIVERSOS)
        self.setModal(True)

        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        formulario.addRow("Descrição:", QLabel(DESCRICAO_DIVERSOS))

        self.campo_valor = QLineEdit()
        self.campo_valor.setObjectName("campo_valor_diversos")
        formulario.addRow("Valor (R$):", self.campo_valor)

        self.rotulo_subtotal = QLabel("—")
        self.rotulo_subtotal.setObjectName("subtotal_diversos")
        formulario.addRow("Subtotal:", self.rotulo_subtotal)
        layout.addLayout(formulario)

        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setObjectName("erro_dialogo_diversos")
        layout.addWidget(self.rotulo_erro)

        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

        self.campo_valor.textChanged.connect(self._atualizar_previa)
        self.campo_valor.returnPressed.connect(self.accept)

    def _atualizar_previa(self, texto: str) -> None:
        try:
            valor_centavos = ler_centavos(texto)
            self.item_previa = criar_item_diversos(valor_centavos)
        except (TypeError, ValueError) as erro:
            self.item_previa = None
            self.rotulo_subtotal.setText("—")
            self.rotulo_erro.setText(str(erro))
            self.botoes.button(
                QDialogButtonBox.StandardButton.Ok
            ).setEnabled(False)
            return

        self.rotulo_subtotal.setText(
            formatar_centavos(self.item_previa.subtotal_centavos)
        )
        self.rotulo_erro.clear()
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def accept(self) -> None:
        if self.item_previa is None:
            return

        self.item_confirmado.emit(self.item_previa)
        super().accept()
