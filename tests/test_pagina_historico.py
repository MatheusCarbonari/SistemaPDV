from datetime import date
from decimal import Decimal
import sqlite3

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHeaderView

from database.conexao import conectar
from database.schema import criar_tabelas
from tests.helpers_identidade import (
    criar_ambiente_autorizacao_teste,
    criar_janela_autenticada,
    emitir_cancelamento_teste,
)
from interface.pagina_historico import PaginaHistorico
import interface.pagina_historico as pagina_historico_module
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_em_andamento import VendaEmAndamento
from services.cancelamento_venda_service import cancelar_venda
from services.confirmacao_venda_service import confirmar_venda
from services.persistencia_venda_service import (
    gerar_identificador_tentativa,
    persistir_venda_confirmada_idempotente,
)


def criar_item_produto(
    subtotal: int,
    *,
    codigo="ANTIGO",
    nome="Produto histórico",
    forma="PESO",
    preco=7990,
    quantidade=Decimal("0.625"),
    origem_quantidade="ESTIMADA",
) -> ItemVenda:
    return ItemVenda(
        origem="ETIQUETA",
        subtotal_centavos=subtotal,
        origem_quantidade=origem_quantidade,
        produto=ProdutoSnapshot(None, codigo, nome, forma, preco),
        codigo_barras="2000100005000",
        quantidade=quantidade,
    )


def criar_diversos(subtotal: int) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal,
        origem_quantidade="NAO_INFORMADA",
        tipo_item="DIVERSOS",
    )


def persistir_venda_rica(caminho_banco) -> int:
    itens = (criar_item_produto(5000), criar_diversos(500))
    pagamentos = (
        Pagamento("PIX", 2500),
        Pagamento("PIX", 1000),
        Pagamento("DINHEIRO", 2000),
    )
    confirmacao = confirmar_venda(
        VendaEmAndamento(itens=itens),
        PagamentosEmAndamento(5500, pagamentos),
    )
    venda_id = persistir_venda_confirmada_idempotente(
        confirmacao,
        gerar_identificador_tentativa(),
        caminho_banco,
    )
    conexao = conectar(caminho_banco)
    try:
        conexao.execute(
            "UPDATE vendas SET registrada_em = ? WHERE id = ?",
            ("2026-11-04 15:30:00", venda_id),
        )
        conexao.commit()
    finally:
        conexao.close()
    return venda_id


def persistir_venda_com_muitos_pagamentos(caminho_banco) -> int:
    pagamentos = tuple(Pagamento("PIX", 500) for _ in range(11))
    confirmacao = confirmar_venda(
        VendaEmAndamento(itens=(criar_item_produto(5500),)),
        PagamentosEmAndamento(5500, pagamentos),
    )
    return persistir_venda_confirmada_idempotente(
        confirmacao,
        gerar_identificador_tentativa(),
        caminho_banco,
    )


def contar_registros(caminho_banco) -> tuple[int, int, int]:
    conexao = conectar(caminho_banco)
    try:
        return tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("vendas", "itens_venda", "pagamentos")
        )
    finally:
        conexao.close()


def _luminancia_relativa(cor: QColor) -> float:
    canais = []
    for canal in (cor.redF(), cor.greenF(), cor.blueF()):
        canais.append(
            canal / 12.92
            if canal <= 0.04045
            else ((canal + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def _contraste(cor_a: QColor, cor_b: QColor) -> float:
    mais_clara, mais_escura = sorted(
        (_luminancia_relativa(cor_a), _luminancia_relativa(cor_b)),
        reverse=True,
    )
    return (mais_clara + 0.05) / (mais_escura + 0.05)


@pytest.fixture
def banco_historico(tmp_path):
    caminho = tmp_path / "historico_interface.db"
    criar_tabelas(caminho)
    return caminho


@pytest.fixture
def pagina(qtbot, banco_historico):
    widget = PaginaHistorico(banco_historico)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(widget.isVisible)
    return widget


def test_navegacao_preserva_venda_pagamentos_e_foco(qtbot, banco_historico) -> None:
    janela = criar_janela_autenticada(banco_historico)
    qtbot.addWidget(janela)
    janela.show()
    qtbot.waitUntil(janela.campo_entrada.hasFocus)
    item = criar_diversos(1000)
    pagamentos = PagamentosEmAndamento(
        1000,
        (Pagamento("PIX", 1000),),
    )
    janela.item_criado.emit(item)
    janela._emitir_pagamentos_confirmados(pagamentos)
    estado = janela.estado_venda

    qtbot.mouseClick(
        janela.botao_navegar_historico,
        Qt.MouseButton.LeftButton,
    )

    assert janela.paginas.currentWidget() is janela.pagina_historico
    assert janela.estado_venda is estado
    assert janela.composicao_pagamentos is pagamentos
    assert janela.botao_navegar_produtos.isVisible()
    assert janela.botao_navegar_produtos.isEnabled()
    qtbot.waitUntil(janela.pagina_historico.campo_id.hasFocus)

    qtbot.mouseClick(
        janela.botao_navegar_caixa,
        Qt.MouseButton.LeftButton,
    )

    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
    assert janela.estado_venda is estado
    assert janela.composicao_pagamentos is pagamentos
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_commit_incerto_impede_navegacao_para_historico(
    qtbot,
    banco_historico,
) -> None:
    janela = criar_janela_autenticada(banco_historico)
    qtbot.addWidget(janela)
    janela.show()
    janela.item_criado.emit(criar_diversos(1000))
    janela._fechamento_incerto = True
    janela._atualizar_venda_exibida()

    janela.mostrar_historico()

    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
    assert not janela.botao_navegar_historico.isEnabled()
    assert "fechamento pendente" in janela.rotulo_status.text()


def test_pesquisa_por_data_civil_de_sao_paulo(
    pagina,
    qtbot,
    banco_historico,
) -> None:
    venda_id = persistir_venda_rica(banco_historico)
    pagina.campo_data.setDate(QDate(2026, 11, 4))

    qtbot.mouseClick(
        pagina.botao_pesquisar_data,
        Qt.MouseButton.LeftButton,
    )

    assert pagina.tabela_vendas.rowCount() == 1
    assert pagina.tabela_vendas.item(0, 0).text() == f"Venda nº {venda_id}"
    assert pagina.tabela_vendas.item(0, 0).data(
        Qt.ItemDataRole.UserRole
    ) == venda_id
    assert pagina.tabela_vendas.item(0, 1).text() == "04/11/2026 12:30:00"
    assert pagina.tabela_vendas.item(0, 2).text() == "R$ 55,00"
    assert pagina.tabela_vendas.item(0, 3).text() == "ATIVA"


def test_pesquisa_por_id_exibe_snapshots_quantidades_e_pagamentos(
    pagina,
    qtbot,
    banco_historico,
) -> None:
    venda_id = persistir_venda_rica(banco_historico)
    antes = contar_registros(banco_historico)
    pagina.campo_id.setText(str(venda_id))

    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )

    assert pagina.tabela_vendas.rowCount() == 1
    assert pagina.tabela_itens.rowCount() == 2
    assert pagina.tabela_itens.item(0, 0).text() == "Produto histórico"
    assert pagina.tabela_itens.item(0, 1).text() == "0.625 kg (estimada)"
    assert pagina.tabela_itens.item(0, 2).text() == "R$ 79,90"
    assert pagina.tabela_itens.item(0, 3).text() == "R$ 50,00"
    assert pagina.tabela_itens.item(1, 0).text() == "Diversos"
    assert pagina.tabela_itens.item(1, 1).text() == "Não informada"
    assert not hasattr(pagina, "rotulo_detalhes_tecnicos")
    assert pagina.findChild(QFrame, "detalhes_tecnicos_item") is None
    assert pagina.tabela_pagamentos.rowCount() == 3
    assert [
        pagina.tabela_pagamentos.item(linha, 0).text()
        for linha in range(3)
    ] == ["1", "2", "3"]
    assert pagina.tabela_pagamentos.item(0, 1).text() == "PIX"
    assert pagina.tabela_pagamentos.item(1, 1).text() == "PIX"
    assert pagina.tabela_pagamentos.item(2, 1).text() == "DINHEIRO"
    assert pagina.tabela_pagamentos.item(0, 2).text() == "R$ 25,00"
    assert pagina.tabela_pagamentos.item(0, 2).textAlignment() & int(
        Qt.AlignmentFlag.AlignRight
    )
    assert pagina.tabela_itens.editTriggers() == (
        QAbstractItemView.EditTrigger.NoEditTriggers
    )
    assert pagina.tabela_pagamentos.editTriggers() == (
        QAbstractItemView.EditTrigger.NoEditTriggers
    )
    assert contar_registros(banco_historico) == antes


def test_venda_cancelada_exibe_metadados(
    pagina,
    qtbot,
    banco_historico,
) -> None:
    venda_id = persistir_venda_rica(banco_historico)
    sessao, gerenciador = criar_ambiente_autorizacao_teste(banco_historico)
    capacidade = emitir_cancelamento_teste(
        banco_historico,
        venda_id,
        sessao,
        gerenciador,
    )
    cancelar_venda(
        venda_id,
        "Erro operacional",
        capacidade,
        sessao,
        banco_historico,
        gerenciador_autorizacoes=gerenciador,
    )
    pagina.campo_id.setText(str(venda_id))

    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )

    assert pagina.tabela_vendas.item(0, 3).text() == "CANCELADA"
    assert pagina.rotulo_status_cancelamento.text() == "CANCELADA"
    assert (
        pagina.rotulo_status_cancelamento.property("statusVenda")
        == "CANCELADA"
    )
    assert pagina.rotulo_motivo_cancelamento.text() == "Erro operacional"
    assert pagina.rotulo_data_cancelamento.text() != "—"
    assert pagina.rotulo_autorizador_cancelamento.text() == "administrador"


@pytest.mark.parametrize("largura,altura", [(1024, 720), (1280, 800)])
def test_layout_usual_preserva_colunas_e_acoes_sem_cortes(
    pagina,
    qtbot,
    banco_historico,
    largura,
    altura,
) -> None:
    venda_id = persistir_venda_rica(banco_historico)
    pagina.campo_id.setText(str(venda_id))
    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )
    pagina.resize(largura, altura)
    qtbot.wait(30)

    assert not pagina._layout_detalhe_empilhado
    assert not pagina.area_rolagem.horizontalScrollBar().isVisible()
    qtbot.waitUntil(
        lambda: not pagina.area_rolagem.verticalScrollBar().isVisible()
    )
    assert not pagina.tabela_itens.horizontalScrollBar().isVisible()

    cabecalho_vendas = pagina.tabela_vendas.horizontalHeader()
    assert cabecalho_vendas.sectionResizeMode(0) == (
        QHeaderView.ResizeMode.Fixed
    )
    assert cabecalho_vendas.sectionResizeMode(1) == (
        QHeaderView.ResizeMode.Fixed
    )
    assert cabecalho_vendas.sectionResizeMode(3) == (
        QHeaderView.ResizeMode.Fixed
    )
    texto_data = pagina.tabela_vendas.item(0, 1).text()
    assert pagina.tabela_vendas.columnWidth(1) >= (
        pagina.tabela_vendas.fontMetrics().horizontalAdvance(texto_data) + 16
    )
    assert pagina.tabela_vendas.columnWidth(3) < (
        pagina.tabela_vendas.columnWidth(1)
    )
    assert pagina.tabela_vendas.item(0, 1).textAlignment() & int(
        Qt.AlignmentFlag.AlignHCenter
    )
    largura_vendas = pagina.tabela_vendas.viewport().width()
    assert abs(
        sum(pagina.tabela_vendas.columnWidth(coluna) for coluna in range(4))
        - largura_vendas
    ) <= 4
    assert 0.30 <= (
        pagina.tabela_vendas.columnWidth(1) / largura_vendas
    ) <= 0.38

    grade = pagina.layout_detalhes_principais
    assert grade.getItemPosition(grade.indexOf(pagina.grupo_vendas)) == (
        0,
        0,
        1,
        1,
    )
    assert grade.getItemPosition(
        grade.indexOf(pagina.painel_lateral_detalhe)
    ) == (0, 1, 1, 1)
    assert grade.getItemPosition(grade.indexOf(pagina.grupo_itens)) == (
        1,
        0,
        1,
        2,
    )
    proporcao_colunas = (
        pagina.grupo_vendas.width() / pagina.painel_lateral_detalhe.width()
    )
    assert 0.85 <= proporcao_colunas <= 1.15
    assert pagina.grupo_itens.width() > pagina.grupo_vendas.width() * 1.8

    assert [
        pagina.tabela_itens.horizontalHeaderItem(coluna).text()
        for coluna in range(4)
    ] == [
        "Produto / descrição",
        "Quantidade / peso",
        "Preço de referência",
        "Subtotal",
    ]
    assert pagina.tabela_itens.columnWidth(0) > (
        pagina.tabela_itens.columnWidth(3)
    )
    assert pagina.botao_solicitar_cancelamento.width() == (
        pagina.botao_solicitar_cancelamento.sizeHint().width()
    )


def test_layout_reduzido_empilha_detalhes_sem_rolagem_horizontal(
    pagina,
    qtbot,
) -> None:
    pagina.resize(700, 600)
    qtbot.wait(30)

    assert pagina._layout_detalhe_empilhado
    assert pagina._layout_filtros_empilhado
    assert pagina.area_rolagem.verticalScrollBar().isVisible()
    assert not pagina.area_rolagem.horizontalScrollBar().isVisible()
    assert pagina.botao_solicitar_cancelamento.isVisible()
    grade = pagina.layout_detalhes_principais
    assert grade.getItemPosition(grade.indexOf(pagina.grupo_vendas))[0] == 0
    assert grade.getItemPosition(
        grade.indexOf(pagina.painel_lateral_detalhe)
    )[0] == 1
    assert grade.getItemPosition(grade.indexOf(pagina.grupo_itens))[0] == 2


def test_tabelas_historicas_usam_proporcoes_contraste_e_somente_leitura(
    pagina,
    qtbot,
    banco_historico,
) -> None:
    venda_id = persistir_venda_rica(banco_historico)
    pagina.campo_id.setText(str(venda_id))
    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )
    pagina.resize(1024, 720)
    qtbot.wait(30)

    cabecalho_pagamentos = pagina.tabela_pagamentos.horizontalHeader()
    assert cabecalho_pagamentos.sectionResizeMode(0) == (
        QHeaderView.ResizeMode.ResizeToContents
    )
    assert cabecalho_pagamentos.sectionResizeMode(1) == (
        QHeaderView.ResizeMode.Stretch
    )
    assert abs(
        pagina.tabela_pagamentos.columnWidth(1)
        - pagina.tabela_pagamentos.columnWidth(2)
    ) <= 2
    assert pagina.tabela_pagamentos.columnWidth(0) < (
        pagina.tabela_pagamentos.columnWidth(1)
    )

    for tabela in (
        pagina.tabela_vendas,
        pagina.tabela_itens,
        pagina.tabela_pagamentos,
    ):
        assert tabela.editTriggers() == (
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        paleta = tabela.palette()
        assert _contraste(
            paleta.color(QPalette.ColorRole.Text),
            paleta.color(QPalette.ColorRole.Base),
        ) >= 4.5
        assert _contraste(
            paleta.color(QPalette.ColorRole.HighlightedText),
            paleta.color(QPalette.ColorRole.Highlight),
        ) >= 4.5

    assert pagina.tabela_vendas.item(0, 3).foreground().color().name() == (
        "#a8e6bd"
    )


def test_data_reserva_espaco_para_texto_e_seletor(pagina) -> None:
    largura_texto = pagina.campo_data.fontMetrics().horizontalAdvance(
        "88/88/8888"
    )

    assert pagina.campo_data.width() >= largura_texto + 50
    assert "padding-right: 30px" in pagina.styleSheet()
    assert "QDateEdit::drop-down" in pagina.styleSheet()


def test_clique_no_campo_de_data_abre_calendario(pagina, qtbot) -> None:
    qtbot.mouseClick(
        pagina.campo_data,
        Qt.MouseButton.LeftButton,
        pos=pagina.campo_data.rect().center(),
    )

    qtbot.waitUntil(pagina.campo_data.calendarWidget().isVisible)
    pagina.campo_data.calendarWidget().hide()


def test_muitas_vendas_usam_rolagem_interna_sem_ampliar_pagina(
    pagina,
    qtbot,
    banco_historico,
) -> None:
    for _ in range(9):
        persistir_venda_rica(banco_historico)
    pagina.campo_data.setDate(QDate(2026, 11, 4))
    qtbot.mouseClick(
        pagina.botao_pesquisar_data,
        Qt.MouseButton.LeftButton,
    )
    pagina.resize(1024, 720)
    qtbot.wait(30)

    assert pagina.tabela_vendas.rowCount() == 9
    assert pagina.tabela_vendas.verticalScrollBar().maximum() > 0
    assert pagina.tabela_vendas.verticalScrollBar().isVisible()
    assert not pagina.area_rolagem.verticalScrollBar().isVisible()


def test_muitos_pagamentos_permanecem_separados_numerados_e_rolaveis(
    pagina,
    qtbot,
    banco_historico,
) -> None:
    venda_id = persistir_venda_com_muitos_pagamentos(banco_historico)
    pagina.campo_id.setText(str(venda_id))
    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )
    qtbot.wait(30)

    assert pagina.tabela_pagamentos.rowCount() == 11
    assert [
        pagina.tabela_pagamentos.item(linha, 0).text()
        for linha in range(11)
    ] == [str(numero) for numero in range(1, 12)]
    assert all(
        pagina.tabela_pagamentos.item(linha, 1).text() == "PIX"
        for linha in range(11)
    )
    assert pagina.tabela_pagamentos.verticalScrollBar().maximum() > 0
    assert pagina.tabela_pagamentos.verticalScrollBar().isVisible()


@pytest.mark.parametrize("texto", ["", "abc", "0", "-1", "1.5"])
def test_id_invalido_exibe_erro_sem_consultar(pagina, qtbot, texto) -> None:
    pagina.campo_id.setText(texto)

    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )

    assert "inteiro e positivo" in pagina.rotulo_mensagem.text()
    assert pagina.tabela_vendas.rowCount() == 0


def test_consultas_vazias_e_erros_sao_apresentados(
    pagina,
    qtbot,
    monkeypatch,
) -> None:
    pagina.campo_id.setText("999999")
    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )
    assert pagina.rotulo_mensagem.text() == "Venda não encontrada."

    monkeypatch.setattr(
        pagina_historico_module,
        "listar_vendas_resumidas_por_data",
        lambda data_local, caminho: (_ for _ in ()).throw(
            sqlite3.OperationalError("consulta indisponível")
        ),
    )
    qtbot.mouseClick(
        pagina.botao_pesquisar_data,
        Qt.MouseButton.LeftButton,
    )
    assert pagina.rotulo_mensagem.text() == "consulta indisponível"
    assert pagina.tabela_vendas.rowCount() == 0


def test_data_sem_vendas_mostra_estado_vazio(pagina, qtbot) -> None:
    pagina.campo_data.setDate(QDate(date(2026, 11, 10)))

    qtbot.mouseClick(
        pagina.botao_pesquisar_data,
        Qt.MouseButton.LeftButton,
    )

    assert pagina.tabela_vendas.rowCount() == 0
    assert "Nenhuma venda" in pagina.rotulo_mensagem.text()
