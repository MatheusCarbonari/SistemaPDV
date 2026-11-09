from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QTableWidget

from database.conexao import conectar
from database.schema import criar_tabelas
from tests.helpers_identidade import (
    criar_ambiente_autorizacao_teste,
    criar_janela_autenticada,
    emitir_cancelamento_teste,
)
from interface.pagina_historico import PaginaHistorico
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_em_andamento import VendaEmAndamento
from services.cancelamento_venda_service import cancelar_venda
import services.cancelamento_venda_service as cancelamento_service
from services.confirmacao_venda_service import confirmar_venda
from services.persistencia_venda_service import (
    gerar_identificador_tentativa,
    persistir_venda_confirmada_idempotente,
)


@pytest.fixture
def banco_cancelamento_visual(tmp_path):
    caminho = tmp_path / "cancelamento_visual.db"
    criar_tabelas(caminho)
    return caminho


def persistir_venda(caminho) -> int:
    item = ItemVenda(
        origem="ETIQUETA",
        subtotal_centavos=5000,
        origem_quantidade="ESTIMADA",
        produto=ProdutoSnapshot(
            None,
            "101",
            "Picanha histórica",
            "PESO",
            7990,
        ),
        quantidade=Decimal("0.625"),
        codigo_barras="2000100005000",
    )
    pagamentos = PagamentosEmAndamento(
        5000,
        (Pagamento("PIX", 3000), Pagamento("DINHEIRO", 2000)),
    )
    confirmada = confirmar_venda(
        VendaEmAndamento(itens=(item,)),
        pagamentos,
    )
    venda_id = persistir_venda_confirmada_idempotente(
        confirmada,
        gerar_identificador_tentativa(),
        caminho,
    )
    conexao = conectar(caminho)
    try:
        conexao.execute(
            "UPDATE vendas SET registrada_em = ? WHERE id = ?",
            ("2026-11-05 15:30:00", venda_id),
        )
        conexao.commit()
    finally:
        conexao.close()
    return venda_id


def estado_persistido(caminho, venda_id):
    conexao = conectar(caminho)
    try:
        venda = tuple(
            conexao.execute(
                """
                SELECT status, motivo_cancelamento, cancelada_em,
                       autorizador_identidade
                FROM vendas
                WHERE id = ?
                """,
                (venda_id,),
            ).fetchone()
        )
        quantidades = tuple(
            conexao.execute(
                f"SELECT COUNT(*) FROM {tabela} WHERE venda_id = ?",
                (venda_id,),
            ).fetchone()[0]
            for tabela in ("itens_venda", "pagamentos")
        )
        return venda, quantidades
    finally:
        conexao.close()


def selecionar_venda(pagina, venda_id) -> None:
    pagina.campo_id.setText(str(venda_id))
    pagina.pesquisar_por_id()
    assert pagina.detalhe_selecionado is not None


@pytest.fixture
def pagina(qtbot, banco_cancelamento_visual):
    sessao, gerenciador = criar_ambiente_autorizacao_teste(
        banco_cancelamento_visual
    )
    widget = PaginaHistorico(
        banco_cancelamento_visual,
        sessao_solicitante=sessao,
        gerenciador_autorizacoes=gerenciador,
    )
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(widget.isVisible)
    return widget


def test_venda_ativa_disponibiliza_solicitacao_com_resumo_correto(
    pagina,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    selecionar_venda(pagina, venda_id)

    assert pagina.botao_solicitar_cancelamento.isEnabled()
    pagina.abrir_solicitacao_cancelamento()
    dialogo = pagina.dialogo_cancelamento

    assert dialogo.rotulo_id.text() == f"Venda nº {venda_id}"
    assert dialogo.rotulo_data.text() == "05/11/2026 12:30:00"
    assert dialogo.rotulo_total.text() == "R$ 50,00"
    assert dialogo.rotulo_status.text() == "ATIVA"
    assert dialogo.rotulo_itens.text() == "1"
    assert dialogo.rotulo_pagamentos.text() == "2"


def test_dialogo_compacto_resume_quantidades_sem_tabelas(
    pagina,
    qtbot,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    dialogo = pagina.dialogo_cancelamento

    assert dialogo.findChildren(QTableWidget) == []
    assert dialogo.rotulo_itens.text() == "1"
    assert dialogo.rotulo_pagamentos.text() == "2"
    assert dialogo.minimumWidth() <= 480
    assert dialogo.minimumHeight() <= 360
    assert dialogo.botao_fechar.height() < 50
    assert dialogo.botao_prosseguir.height() < 50
    assert dialogo.botao_prosseguir.width() < dialogo.width()
    dialogo.resize(480, 360)
    qtbot.wait(20)
    assert dialogo.rect().contains(
        dialogo.botao_fechar.mapTo(dialogo, dialogo.botao_fechar.rect().topLeft())
    )
    assert dialogo.rect().contains(
        dialogo.botao_prosseguir.mapTo(
            dialogo,
            dialogo.botao_prosseguir.rect().bottomRight(),
        )
    )
    textos = [rotulo.text() for rotulo in dialogo.findChildren(QLabel)]
    assert any("Informe o motivo" in texto for texto in textos)
    assert any("autorização administrativa" in texto for texto in textos)


def test_venda_cancelada_permanece_consultavel_sem_nova_solicitacao(
    pagina,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    sessao = pagina.sessao_solicitante
    gerenciador = pagina.gerenciador_autorizacoes
    capacidade = emitir_cancelamento_teste(
        banco_cancelamento_visual,
        venda_id,
        sessao,
        gerenciador,
    )
    cancelar_venda(
        venda_id,
        "Erro operacional",
        capacidade,
        sessao,
        banco_cancelamento_visual,
        gerenciador_autorizacoes=gerenciador,
    )
    selecionar_venda(pagina, venda_id)

    assert pagina.detalhe_selecionado.status == "CANCELADA"
    assert not pagina.botao_solicitar_cancelamento.isEnabled()
    assert pagina.rotulo_motivo_cancelamento.text() == "Erro operacional"

    pagina.abrir_solicitacao_cancelamento()
    assert pagina.dialogo_cancelamento is None
    assert "já está cancelada" in pagina.rotulo_mensagem.text()


def test_motivo_e_obrigatorio_e_nao_emite_autorizacao(
    pagina,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    dialogo = pagina.dialogo_cancelamento
    sinais = QSignalSpy(dialogo.autorizacao_requerida)

    dialogo.campo_motivo.setPlainText("   ")
    dialogo.preparar_solicitacao()

    assert sinais.count() == 0
    assert "Informe o motivo" in dialogo.rotulo_mensagem.text()
    assert estado_persistido(banco_cancelamento_visual, venda_id)[0] == (
        "ATIVA",
        None,
        None,
        None,
    )


def test_desistencia_fecha_dialogo_sem_efeito(
    pagina,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    antes = estado_persistido(banco_cancelamento_visual, venda_id)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    dialogo = pagina.dialogo_cancelamento
    dialogo.campo_motivo.setPlainText("Venda lançada incorretamente")

    dialogo.reject()

    assert estado_persistido(banco_cancelamento_visual, venda_id) == antes


def test_preparacao_abre_autorizacao_sem_cancelar_nem_criar_identidade(
    pagina,
    banco_cancelamento_visual,
    monkeypatch,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    antes = estado_persistido(banco_cancelamento_visual, venda_id)
    chamadas = []
    monkeypatch.setattr(
        cancelamento_service,
        "cancelar_venda",
        lambda *args, **kwargs: chamadas.append((args, kwargs)),
    )
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    dialogo = pagina.dialogo_cancelamento
    sinais = QSignalSpy(dialogo.autorizacao_requerida)
    dialogo.campo_motivo.setPlainText("  Duplicidade de lançamento  ")

    dialogo.preparar_solicitacao()

    assert sinais.count() == 1
    assert sinais.at(0) == [venda_id, "Duplicidade de lançamento"]
    assert chamadas == []
    assert estado_persistido(banco_cancelamento_visual, venda_id) == antes
    assert not hasattr(dialogo, "identidade_autorizador")
    assert pagina.dialogo_autorizacao is not None
    assert "Aguardando autorização" in dialogo.rotulo_mensagem.text()
    assert not dialogo.botao_prosseguir.isEnabled()


def test_historico_permanece_intacto_apos_preparacao_visual(
    pagina,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    selecionar_venda(pagina, venda_id)
    pagina.abrir_solicitacao_cancelamento()
    dialogo = pagina.dialogo_cancelamento
    dialogo.campo_motivo.setPlainText("Correção operacional")
    dialogo.preparar_solicitacao()
    dialogo.reject()

    selecionar_venda(pagina, venda_id)

    assert pagina.detalhe_selecionado.status == "ATIVA"
    assert pagina.tabela_itens.rowCount() == 1
    assert pagina.tabela_pagamentos.rowCount() == 2
    assert pagina.tabela_itens.item(0, 0).text() == "Picanha histórica"


def test_atendimento_e_pagamentos_sao_preservados_durante_solicitacao(
    qtbot,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    janela = criar_janela_autenticada(banco_cancelamento_visual)
    qtbot.addWidget(janela)
    janela.show()
    item_aberto = ItemVenda(
        origem="MANUAL",
        subtotal_centavos=1000,
        origem_quantidade="NAO_INFORMADA",
        tipo_item="DIVERSOS",
    )
    pagamentos = PagamentosEmAndamento(1000, (Pagamento("PIX", 1000),))
    janela.item_criado.emit(item_aberto)
    janela._emitir_pagamentos_confirmados(pagamentos)
    estado = janela.estado_venda

    janela.mostrar_historico()
    selecionar_venda(janela.pagina_historico, venda_id)
    janela.pagina_historico.abrir_solicitacao_cancelamento()
    dialogo = janela.pagina_historico.dialogo_cancelamento
    dialogo.campo_motivo.setPlainText("Teste sem efeito comercial")
    dialogo.preparar_solicitacao()

    assert janela.estado_venda is estado
    assert janela.composicao_pagamentos is pagamentos
    assert estado_persistido(banco_cancelamento_visual, venda_id)[0][0] == "ATIVA"


def test_commit_incerto_bloqueia_solicitacao_e_navegacao(
    qtbot,
    banco_cancelamento_visual,
) -> None:
    venda_id = persistir_venda(banco_cancelamento_visual)
    bloqueada = PaginaHistorico(
        banco_cancelamento_visual,
        operacao_bloqueada=lambda: True,
    )
    qtbot.addWidget(bloqueada)
    bloqueada.show()
    selecionar_venda(bloqueada, venda_id)

    assert not bloqueada.botao_solicitar_cancelamento.isEnabled()
    bloqueada.abrir_solicitacao_cancelamento()
    assert bloqueada.dialogo_cancelamento is None
    assert "fechamento pendente" in bloqueada.rotulo_mensagem.text()

    janela = criar_janela_autenticada(banco_cancelamento_visual)
    qtbot.addWidget(janela)
    janela.show()
    janela._fechamento_incerto = True
    janela._atualizar_venda_exibida()
    janela.mostrar_historico()
    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
    assert not janela.botao_navegar_historico.isEnabled()


def test_regressao_navegacao_mantem_paginas_existentes(
    qtbot,
    banco_cancelamento_visual,
) -> None:
    janela = criar_janela_autenticada(banco_cancelamento_visual)
    qtbot.addWidget(janela)
    janela.show()

    qtbot.mouseClick(janela.botao_navegar_produtos, Qt.MouseButton.LeftButton)
    assert janela.paginas.currentWidget() is janela.pagina_produtos
    qtbot.mouseClick(janela.botao_navegar_historico, Qt.MouseButton.LeftButton)
    assert janela.paginas.currentWidget() is janela.pagina_historico
    qtbot.mouseClick(janela.botao_navegar_caixa, Qt.MouseButton.LeftButton)
    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
