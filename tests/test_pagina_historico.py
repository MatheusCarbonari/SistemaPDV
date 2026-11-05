from datetime import date
from decimal import Decimal
import sqlite3

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QAbstractItemView

from database.conexao import conectar
from database.schema import criar_tabelas
from interface.janela_principal import JanelaPrincipal
from interface.pagina_historico import PaginaHistorico
import interface.pagina_historico as pagina_historico_module
from models.cancelamento_venda import ContextoAutorizacaoCancelamento
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


def contar_registros(caminho_banco) -> tuple[int, int, int]:
    conexao = conectar(caminho_banco)
    try:
        return tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("vendas", "itens_venda", "pagamentos")
        )
    finally:
        conexao.close()


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
    janela = JanelaPrincipal(banco_historico)
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
    janela = JanelaPrincipal(banco_historico)
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
    assert pagina.tabela_vendas.item(0, 0).text() == f"{venda_id:06d}"
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
    assert pagina.tabela_itens.item(0, 1).text() == "PRODUTO"
    assert pagina.tabela_itens.item(0, 2).text() == "ANTIGO"
    assert pagina.tabela_itens.item(0, 3).text() == "Produto histórico"
    assert pagina.tabela_itens.item(0, 5).text() == "ETIQUETA"
    assert pagina.tabela_itens.item(0, 6).text() == "0.625 kg (estimada)"
    assert pagina.tabela_itens.item(0, 7).text() == "ESTIMADA"
    assert pagina.tabela_itens.item(0, 8).text() == "R$ 79,90"
    assert pagina.tabela_itens.item(0, 9).text() == "R$ 50,00"
    assert pagina.tabela_itens.item(1, 1).text() == "DIVERSOS"
    assert pagina.tabela_itens.item(1, 3).text() == "Diversos"
    assert pagina.tabela_pagamentos.rowCount() == 3
    assert pagina.tabela_pagamentos.item(0, 0).text() == "PIX"
    assert pagina.tabela_pagamentos.item(1, 0).text() == "PIX"
    assert pagina.tabela_pagamentos.item(2, 0).text() == "DINHEIRO"
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
    cancelar_venda(
        venda_id,
        "Erro operacional",
        ContextoAutorizacaoCancelamento("administrador-1"),
        banco_historico,
    )
    pagina.campo_id.setText(str(venda_id))

    qtbot.mouseClick(
        pagina.botao_pesquisar_id,
        Qt.MouseButton.LeftButton,
    )

    assert pagina.tabela_vendas.item(0, 3).text() == "CANCELADA"
    assert pagina.rotulo_motivo_cancelamento.text() == "Erro operacional"
    assert pagina.rotulo_data_cancelamento.text() != "—"
    assert pagina.rotulo_autorizador_cancelamento.text() == "administrador-1"


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
