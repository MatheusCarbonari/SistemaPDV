from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.conexao import CAMINHO_BANCO
from interface.formatacao import formatar_centavos
from interface.dialogo_solicitacao_cancelamento import (
    DialogoSolicitacaoCancelamento,
)
from models.item_venda import DESCRICAO_DIVERSOS
from models.venda_detalhada import VendaDetalhada
from models.venda_resumo import VendaResumo
from services.historico_venda_service import (
    FUSO_SAO_PAULO,
    buscar_venda_detalhada_por_id,
    buscar_venda_resumida_por_id,
    listar_vendas_resumidas_por_data,
)


class PaginaHistorico(QWidget):
    """Página interna somente leitura para consulta de vendas persistidas."""

    def __init__(
        self,
        caminho_banco=CAMINHO_BANCO,
        parent=None,
        *,
        operacao_bloqueada: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.caminho_banco = caminho_banco
        self._operacao_bloqueada = operacao_bloqueada or (lambda: False)
        self.detalhe_selecionado: VendaDetalhada | None = None
        self.dialogo_cancelamento: DialogoSolicitacaoCancelamento | None = None
        self.setObjectName("pagina_historico")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Histórico de vendas"))

        filtros = QHBoxLayout()
        self.campo_data = QDateEdit()
        self.campo_data.setObjectName("data_historico")
        self.campo_data.setCalendarPopup(True)
        self.campo_data.setDisplayFormat("dd/MM/yyyy")
        hoje = datetime.now(FUSO_SAO_PAULO).date()
        self.campo_data.setDate(QDate(hoje.year, hoje.month, hoje.day))
        filtros.addWidget(QLabel("Data (São Paulo):"))
        filtros.addWidget(self.campo_data)
        self.botao_pesquisar_data = QPushButton("Pesquisar data")
        self.botao_pesquisar_data.setObjectName("pesquisar_historico_data")
        filtros.addWidget(self.botao_pesquisar_data)

        self.campo_id = QLineEdit()
        self.campo_id.setObjectName("id_historico")
        self.campo_id.setPlaceholderText("Número da venda")
        filtros.addWidget(QLabel("ID:"))
        filtros.addWidget(self.campo_id)
        self.botao_pesquisar_id = QPushButton("Pesquisar ID")
        self.botao_pesquisar_id.setObjectName("pesquisar_historico_id")
        filtros.addWidget(self.botao_pesquisar_id)
        filtros.addStretch()
        layout.addLayout(filtros)

        self.rotulo_mensagem = QLabel("")
        self.rotulo_mensagem.setObjectName("mensagem_historico")
        layout.addWidget(self.rotulo_mensagem)

        self.tabela_vendas = QTableWidget(0, 4)
        self.tabela_vendas.setObjectName("lista_historico_vendas")
        self.tabela_vendas.setHorizontalHeaderLabels(
            ["Número", "Data/hora local", "Total", "Status"]
        )
        self._configurar_tabela_somente_leitura(self.tabela_vendas)
        self.tabela_vendas.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.tabela_vendas.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tabela_vendas.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_vendas)

        self.rotulo_detalhe = QLabel("Selecione uma venda para ver os detalhes.")
        self.rotulo_detalhe.setObjectName("resumo_detalhe_historico")
        layout.addWidget(self.rotulo_detalhe)

        self.tabela_itens = QTableWidget(0, 11)
        self.tabela_itens.setObjectName("itens_historico_venda")
        self.tabela_itens.setHorizontalHeaderLabels(
            [
                "Posição",
                "Tipo",
                "Código",
                "Descrição",
                "Forma",
                "Origem",
                "Quantidade",
                "Origem qtd.",
                "Preço ref.",
                "Subtotal",
                "Código de barras",
            ]
        )
        self._configurar_tabela_somente_leitura(self.tabela_itens)
        self.tabela_itens.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_itens)

        self.tabela_pagamentos = QTableWidget(0, 2)
        self.tabela_pagamentos.setObjectName("pagamentos_historico_venda")
        self.tabela_pagamentos.setHorizontalHeaderLabels(
            ["Modalidade", "Valor"]
        )
        self._configurar_tabela_somente_leitura(self.tabela_pagamentos)
        self.tabela_pagamentos.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabela_pagamentos)

        cancelamento = QFormLayout()
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
        cancelamento.addRow("Motivo do cancelamento:", self.rotulo_motivo_cancelamento)
        cancelamento.addRow("Cancelada em:", self.rotulo_data_cancelamento)
        cancelamento.addRow(
            "Autorizador:",
            self.rotulo_autorizador_cancelamento,
        )
        layout.addLayout(cancelamento)

        self.botao_solicitar_cancelamento = QPushButton(
            "Solicitar cancelamento"
        )
        self.botao_solicitar_cancelamento.setObjectName(
            "solicitar_cancelamento"
        )
        self.botao_solicitar_cancelamento.setEnabled(False)
        layout.addWidget(self.botao_solicitar_cancelamento)

        self.botao_pesquisar_data.clicked.connect(self.pesquisar_por_data)
        self.botao_pesquisar_id.clicked.connect(self.pesquisar_por_id)
        self.campo_id.returnPressed.connect(self.pesquisar_por_id)
        self.tabela_vendas.itemSelectionChanged.connect(
            self._carregar_venda_selecionada
        )
        self.botao_solicitar_cancelamento.clicked.connect(
            self.abrir_solicitacao_cancelamento
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

        self._preencher_vendas((resumo,))
        self.rotulo_mensagem.setText("Venda encontrada.")
        self.tabela_vendas.selectRow(0)

    def _preencher_vendas(self, vendas: tuple[VendaResumo, ...]) -> None:
        self.tabela_vendas.clearSelection()
        self.tabela_vendas.setRowCount(len(vendas))
        for linha, venda in enumerate(vendas):
            numero = QTableWidgetItem(f"{venda.venda_id:06d}")
            numero.setData(Qt.ItemDataRole.UserRole, venda.venda_id)
            valores = (
                numero,
                QTableWidgetItem(self._formatar_data_local(venda.registrada_em)),
                QTableWidgetItem(formatar_centavos(venda.total_centavos)),
                QTableWidgetItem(venda.status),
            )
            for coluna, item in enumerate(valores):
                self.tabela_vendas.setItem(linha, coluna, item)
        self._limpar_detalhe()

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
            f"Venda #{resumo.venda_id:06d} — "
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
                str(detalhado.posicao + 1),
                item.tipo_item or "LEGADO",
                snapshot.codigo if snapshot is not None else "—",
                descricao,
                snapshot.forma_venda if snapshot is not None else "—",
                item.origem,
                self._formatar_quantidade(item),
                item.origem_quantidade,
                (
                    formatar_centavos(snapshot.preco_referencia_centavos)
                    if snapshot is not None
                    else "—"
                ),
                formatar_centavos(item.subtotal_centavos),
                item.codigo_barras or "—",
            )
            for coluna, valor in enumerate(valores):
                self.tabela_itens.setItem(
                    linha,
                    coluna,
                    QTableWidgetItem(valor),
                )

        self.tabela_pagamentos.setRowCount(len(detalhe.pagamentos))
        for linha, pagamento in enumerate(detalhe.pagamentos):
            self.tabela_pagamentos.setItem(
                linha,
                0,
                QTableWidgetItem(pagamento.modalidade),
            )
            self.tabela_pagamentos.setItem(
                linha,
                1,
                QTableWidgetItem(formatar_centavos(pagamento.valor_centavos)),
            )

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
            resumo.status == "ATIVA" and not self._operacao_bloqueada()
        )

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
            self._registrar_preparacao_visual
        )
        dialogo.finished.connect(
            lambda: self._finalizar_dialogo_cancelamento(dialogo)
        )
        dialogo.open()

    def _registrar_preparacao_visual(self, venda_id: int, motivo: str) -> None:
        self.rotulo_mensagem.setText(
            f"Solicitação da venda #{venda_id:06d} preparada visualmente; "
            "nenhum cancelamento foi executado."
        )

    def _finalizar_dialogo_cancelamento(
        self,
        dialogo: DialogoSolicitacaoCancelamento,
    ) -> None:
        if self.dialogo_cancelamento is dialogo:
            self.dialogo_cancelamento = None
        dialogo.deleteLater()
        self.restaurar_foco()

    def _limpar_detalhe(self) -> None:
        self.detalhe_selecionado = None
        self.rotulo_detalhe.setText(
            "Selecione uma venda para ver os detalhes."
        )
        self.tabela_itens.setRowCount(0)
        self.tabela_pagamentos.setRowCount(0)
        self.rotulo_motivo_cancelamento.setText("—")
        self.rotulo_data_cancelamento.setText("—")
        self.rotulo_autorizador_cancelamento.setText("—")
        self.botao_solicitar_cancelamento.setEnabled(False)

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
