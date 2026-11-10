import sqlite3

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QDialog, QHeaderView

from database.schema import criar_tabelas
from tests.helpers_identidade import (
    criar_janela_autenticada,
    criar_sessao_admin_teste,
)
from interface.pagina_produtos import (
    AVISO_ALTERACAO_CODIGO,
    DialogoConfirmacaoSituacaoProduto,
    PaginaProdutos,
)
import interface.pagina_produtos as pagina_produtos_module
from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.produto import Produto
from repositories.produto_repository import (
    alterar_situacao_produto_repository,
    buscar_produto_por_codigo,
    salvar_produto,
)
from services.produto_service import atualizar_produto
from tests.helpers_categorias import garantir_categoria_teste


@pytest.fixture
def banco_produtos(tmp_path):
    caminho = tmp_path / "produtos_interface.db"
    criar_tabelas(caminho)
    garantir_categoria_teste(caminho)
    return caminho


def cadastrar(
    caminho,
    codigo="101",
    nome="Picanha",
    forma="PESO",
    preco=7990,
    ativo=True,
):
    categoria = garantir_categoria_teste(caminho)
    produto = salvar_produto(
        Produto(
            codigo,
            nome,
            categoria.nome,
            forma,
            preco,
            "COMPRADO",
            categoria_id=categoria.id,
        ),
        caminho,
    )
    if not ativo:
        alterar_situacao_produto_repository(produto.id, False, caminho)
    return produto


@pytest.fixture
def pagina(qtbot, banco_produtos):
    sessao = criar_sessao_admin_teste(banco_produtos)
    widget = PaginaProdutos(
        banco_produtos,
        sessao_administrativa=sessao,
    )
    qtbot.addWidget(widget)
    widget.show()
    widget.ativar()
    qtbot.waitUntil(widget.isVisible)
    return widget


def preencher_dialogo(
    dialogo,
    *,
    codigo="101",
    nome="Picanha",
    categoria="Bovinos",
    forma="PESO",
    preco="79,90",
    origem="COMPRADO",
):
    dialogo.campo_codigo.setText(codigo)
    dialogo.campo_nome.setText(nome)
    for indice in range(dialogo.campo_categoria.count()):
        item = dialogo.campo_categoria.itemData(indice)
        if item.nome.casefold() == categoria.casefold():
            dialogo.campo_categoria.setCurrentIndex(indice)
            break
    dialogo.combo_forma_venda.setCurrentText(forma)
    dialogo.campo_preco.setText(preco)
    dialogo.combo_origem.setCurrentText(origem)


@pytest.mark.parametrize(
    ("codigo", "forma", "preco", "centavos"),
    (("101", "PESO", "79,90", 7990), ("102", "UNIDADE", "12,34", 1234)),
)
def test_cadastro_pela_pagina_persiste_valor_exato(
    pagina,
    codigo,
    forma,
    preco,
    centavos,
) -> None:
    pagina.abrir_cadastro()
    dialogo = pagina.dialogo_atual
    preencher_dialogo(dialogo, codigo=codigo, forma=forma, preco=preco)

    dialogo.confirmar()

    salvo = buscar_produto_por_codigo(codigo, pagina.caminho_banco)
    assert salvo is not None
    assert salvo.forma_venda == forma
    assert salvo.preco_venda_centavos == centavos
    assert pagina.tabela_produtos.rowCount() == 1


def test_cadastro_duplicado_e_campos_invalidos_mantem_formulario_aberto(
    pagina,
) -> None:
    cadastrar(pagina.caminho_banco)
    pagina.abrir_cadastro()
    dialogo = pagina.dialogo_atual
    preencher_dialogo(dialogo, preco="0")
    dialogo.confirmar()
    assert "maior que zero" in dialogo.rotulo_mensagem.text()
    assert dialogo.isVisible()

    dialogo.campo_preco.setText("79,90")
    dialogo.confirmar()
    assert "Já existe" in dialogo.rotulo_mensagem.text()
    assert dialogo.isVisible()


def test_preco_com_mais_de_duas_casas_e_rejeitado_no_formulario(pagina) -> None:
    pagina.abrir_cadastro()
    dialogo = pagina.dialogo_atual
    preencher_dialogo(dialogo, preco="10,001")

    dialogo.confirmar()

    assert "no máximo duas casas" in dialogo.rotulo_mensagem.text()
    assert buscar_produto_por_codigo("101", pagina.caminho_banco) is None


def test_listagem_pesquisa_codigo_nome_e_exibe_inativos(pagina) -> None:
    cadastrar(pagina.caminho_banco, "101", "Picanha")
    cadastrar(pagina.caminho_banco, "202", "Alcatra", ativo=False)
    pagina.combo_situacao.setCurrentIndex(0)

    pagina.campo_pesquisa.setText("202")
    pagina.carregar_produtos()
    assert pagina.tabela_produtos.rowCount() == 1
    assert pagina.tabela_produtos.item(0, 1).text() == "Alcatra"
    assert pagina.tabela_produtos.item(0, 5).text() == "Inativo"

    pagina.campo_pesquisa.setText("pica")
    pagina.carregar_produtos()
    assert pagina.tabela_produtos.rowCount() == 1
    assert pagina.tabela_produtos.item(0, 0).text() == "101"


def test_edicao_permite_alterar_codigo_e_atualiza_lista(pagina) -> None:
    cadastrar(pagina.caminho_banco)
    pagina.carregar_produtos()
    pagina.tabela_produtos.selectRow(0)
    pagina.abrir_edicao()
    dialogo = pagina.dialogo_atual
    assert not dialogo.campo_codigo.isReadOnly()
    assert not dialogo.rotulo_aviso_codigo.isVisible()
    dialogo.campo_codigo.setText("202")
    assert dialogo.rotulo_aviso_codigo.isVisible()
    assert dialogo.rotulo_aviso_codigo.text() == AVISO_ALTERACAO_CODIGO
    dialogo.campo_nome.setText("Picanha premium")
    dialogo.campo_preco.setText("84,90")

    dialogo.confirmar()

    assert buscar_produto_por_codigo("101", pagina.caminho_banco) is None
    salvo = buscar_produto_por_codigo("202", pagina.caminho_banco)
    assert salvo.nome == "Picanha premium"
    assert salvo.preco_venda_centavos == 8490
    assert pagina.tabela_produtos.item(0, 0).text() == "202"


def test_aviso_de_codigo_some_quando_valor_original_e_restaurado(pagina) -> None:
    cadastrar(pagina.caminho_banco)
    pagina.carregar_produtos()
    pagina.tabela_produtos.selectRow(0)
    pagina.abrir_edicao()
    dialogo = pagina.dialogo_atual

    dialogo.campo_codigo.setText("202")
    assert dialogo.rotulo_aviso_codigo.isVisible()
    dialogo.campo_codigo.setText("101")
    assert not dialogo.rotulo_aviso_codigo.isVisible()


def test_ativacao_e_desativacao_atualizam_lista(
    pagina,
    monkeypatch,
) -> None:
    cadastrar(pagina.caminho_banco)
    pagina.carregar_produtos()
    pagina.tabela_produtos.selectRow(0)
    monkeypatch.setattr(
        DialogoConfirmacaoSituacaoProduto,
        "exec",
        lambda self: int(QDialog.DialogCode.Accepted),
    )

    pagina.alterar_situacao_selecionada()

    assert buscar_produto_por_codigo("101", pagina.caminho_banco).ativo is False
    assert pagina.tabela_produtos.item(0, 5).text() == "Inativo"
    pagina.tabela_produtos.selectRow(0)
    pagina.alterar_situacao_selecionada()
    assert buscar_produto_por_codigo("101", pagina.caminho_banco).ativo is True


def test_venda_em_andamento_bloqueia_edicao_e_situacao_mas_permite_cadastro(
    qtbot,
    banco_produtos,
) -> None:
    em_atendimento = True
    pagina = PaginaProdutos(
        banco_produtos,
        tem_venda_em_andamento=lambda: em_atendimento,
        sessao_administrativa=criar_sessao_admin_teste(banco_produtos),
    )
    qtbot.addWidget(pagina)
    pagina.show()
    cadastrar(banco_produtos)
    pagina.carregar_produtos()
    pagina.tabela_produtos.selectRow(0)

    pagina.abrir_edicao()
    assert pagina.dialogo_atual is None
    assert "venda em andamento" in pagina.rotulo_mensagem.text()

    pagina.alterar_situacao_selecionada()
    assert buscar_produto_por_codigo("101", banco_produtos).ativo is True

    pagina.abrir_cadastro()
    assert pagina.dialogo_atual is not None


def test_bloqueio_de_fechamento_impede_todas_as_operacoes(
    qtbot,
    banco_produtos,
) -> None:
    pagina = PaginaProdutos(
        banco_produtos,
        operacao_bloqueada=lambda: True,
        sessao_administrativa=criar_sessao_admin_teste(banco_produtos),
    )
    qtbot.addWidget(pagina)
    pagina.show()
    pagina.abrir_cadastro()
    assert pagina.dialogo_atual is None
    assert "fechamento pendente" in pagina.rotulo_mensagem.text()


def test_falha_de_banco_e_apresentada_sem_encerrar_pagina(
    pagina,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        pagina_produtos_module,
        "listar_produtos",
        lambda **kwargs: (_ for _ in ()).throw(
            sqlite3.OperationalError("banco indisponível")
        ),
    )

    pagina.carregar_produtos()

    assert pagina.rotulo_mensagem.text() == "banco indisponível"
    assert pagina.isVisible()
    assert pagina.tabela_produtos.rowCount() == 0


def test_navegacao_preserva_venda_pagamentos_e_restaura_foco(
    qtbot,
    banco_produtos,
) -> None:
    janela = criar_janela_autenticada(banco_produtos)
    qtbot.addWidget(janela)
    janela.show()
    item = ItemVenda(
        origem="MANUAL",
        subtotal_centavos=1000,
        origem_quantidade="NAO_INFORMADA",
        tipo_item="DIVERSOS",
    )
    pagamentos = PagamentosEmAndamento(1000, (Pagamento("PIX", 1000),))
    janela.item_criado.emit(item)
    janela._emitir_pagamentos_confirmados(pagamentos)
    estado = janela.estado_venda

    qtbot.mouseClick(
        janela.botao_navegar_produtos,
        Qt.MouseButton.LeftButton,
    )
    assert janela.paginas.currentWidget() is janela.pagina_produtos
    assert janela.estado_venda is estado
    assert janela.composicao_pagamentos is pagamentos

    qtbot.mouseClick(janela.botao_navegar_caixa, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(janela.campo_entrada.hasFocus)
    assert janela.estado_venda is estado
    assert janela.composicao_pagamentos is pagamentos


def test_commit_incerto_impede_navegacao_para_produtos(
    qtbot,
    banco_produtos,
) -> None:
    janela = criar_janela_autenticada(banco_produtos)
    qtbot.addWidget(janela)
    janela.show()
    janela._fechamento_incerto = True
    janela._atualizar_venda_exibida()

    janela.mostrar_produtos()

    assert janela.paginas.currentWidget() is janela.pagina_frente_caixa
    assert not janela.botao_navegar_produtos.isEnabled()
    assert "fechamento pendente" in janela.rotulo_status.text()


def test_produto_novo_fica_disponivel_no_caixa_sem_reiniciar(
    qtbot,
    banco_produtos,
) -> None:
    janela = criar_janela_autenticada(banco_produtos)
    qtbot.addWidget(janela)
    janela.show()
    cadastrar(banco_produtos, "303", "Hambúrguer", "UNIDADE", 1500)

    janela.campo_entrada.setText("303")
    janela.processar_entrada()

    assert janela.dialogo_atual is not None
    assert janela.dialogo_atual.produto.codigo == "303"
    assert janela.dialogo_atual.produto.forma_venda == "UNIDADE"


def test_edicao_nao_altera_snapshot_ja_lancado(banco_produtos) -> None:
    produto = cadastrar(banco_produtos)
    snapshot = ProdutoSnapshot(
        produto.id,
        produto.codigo,
        produto.nome,
        produto.forma_venda,
        produto.preco_venda_centavos,
    )

    atualizado, erros = atualizar_produto(
        produto.id,
        produto.codigo,
        "Picanha premium",
        produto.categoria,
        produto.forma_venda,
        8990,
        produto.origem,
        banco_produtos,
        sessao_solicitante=criar_sessao_admin_teste(banco_produtos),
    )

    assert erros == []
    assert atualizado.nome == "Picanha premium"
    assert snapshot.nome == "Picanha"
    assert snapshot.preco_referencia_centavos == 7990


@pytest.mark.parametrize("largura,altura", [(1024, 720), (1280, 800)])
def test_layout_produtos_distribui_colunas_sem_cortes(
    pagina,
    qtbot,
    largura,
    altura,
) -> None:
    cadastrar(pagina.caminho_banco, "101", "Picanha premium maturada")
    cadastrar(pagina.caminho_banco, "202", "Alcatra")
    pagina.carregar_produtos()
    pagina.resize(largura, altura)
    qtbot.wait(30)

    cabecalho = pagina.tabela_produtos.horizontalHeader()
    assert all(
        cabecalho.sectionResizeMode(coluna) == QHeaderView.ResizeMode.Fixed
        for coluna in range(6)
    )
    largura_tabela = pagina.tabela_produtos.viewport().width()
    assert abs(
        sum(pagina.tabela_produtos.columnWidth(coluna) for coluna in range(6))
        - largura_tabela
    ) <= 5
    assert pagina.tabela_produtos.columnWidth(1) > (
        pagina.tabela_produtos.columnWidth(0) * 2
    )
    assert pagina.tabela_produtos.columnWidth(1) > (
        pagina.tabela_produtos.columnWidth(5) * 2
    )
    assert pagina.tabela_produtos.item(0, 4).textAlignment() & int(
        Qt.AlignmentFlag.AlignRight
    )
    assert not pagina.tabela_produtos.horizontalScrollBar().isVisible()
    assert not pagina._filtros_empilhados
    assert not pagina._acoes_empilhadas


def test_layout_produtos_reduzido_empilha_filtros_e_acoes(
    pagina,
    qtbot,
) -> None:
    pagina.resize(680, 520)
    qtbot.wait(30)

    assert pagina._filtros_empilhados
    assert pagina._acoes_empilhadas
    assert pagina.layout_filtros.getItemPosition(
        pagina.layout_filtros.indexOf(pagina.combo_situacao)
    )[0] == 1
    assert pagina.layout_acoes.getItemPosition(
        pagina.layout_acoes.indexOf(pagina.botao_historico_precos)
    )[0] == 1


def test_formulario_produto_usa_campos_compactos_e_destaca_edicao(
    pagina,
    qtbot,
) -> None:
    produto = cadastrar(pagina.caminho_banco)
    pagina.carregar_produtos()
    pagina.tabela_produtos.selectRow(0)
    pagina.abrir_edicao()
    dialogo = pagina.dialogo_atual
    dialogo.resize(500, 400)
    qtbot.wait(20)

    assert dialogo.rotulo_estado.text() == f"Editando produto {produto.codigo}"
    assert dialogo.campo_codigo.size().toTuple() == (140, 30)
    assert dialogo.campo_nome.size().toTuple() == (320, 30)
    assert dialogo.campo_preco.size().toTuple() == (130, 30)
    assert dialogo.campo_categoria.size().toTuple() == (210, 30)
    assert dialogo.combo_forma_venda.size().toTuple() == (130, 30)
    assert dialogo.combo_origem.size().toTuple() == (150, 30)
    assert not dialogo.campo_categoria.isEditable()
    assert dialogo.botoes.width() < dialogo.width()
    assert "QDialog#dialogo_produto" in dialogo.styleSheet()


@pytest.mark.parametrize("editar", [False, True])
@pytest.mark.parametrize("escala_fonte", [1.0, 1.25])
def test_formulario_produto_nao_sobrepoe_campos(
    pagina,
    qtbot,
    editar,
    escala_fonte,
) -> None:
    if editar:
        cadastrar(pagina.caminho_banco)
        pagina.carregar_produtos()
        pagina.tabela_produtos.selectRow(0)
        pagina.abrir_edicao()
    else:
        pagina.abrir_cadastro()
    dialogo = pagina.dialogo_atual
    fonte = dialogo.font()
    fonte.setPointSizeF(fonte.pointSizeF() * escala_fonte)
    dialogo.setFont(fonte)
    dialogo.show()
    dialogo.resize(600, 450)
    qtbot.wait(20)

    campos_comerciais = (
        dialogo.campo_categoria,
        dialogo.combo_forma_venda,
        dialogo.campo_preco,
        dialogo.combo_origem,
    )
    retangulos = []
    for campo in campos_comerciais:
        origem = campo.mapTo(dialogo.grupo_comercial, QPoint(0, 0))
        retangulos.append(QRect(origem, campo.size()))
    for indice, retangulo in enumerate(retangulos):
        for outro in retangulos[indice + 1:]:
            assert not retangulo.intersects(outro)
    assert dialogo.grupo_comercial.height() >= 115


def test_confirmacao_situacao_usa_botoes_largos_e_baixos(
    pagina,
    qtbot,
) -> None:
    produto = cadastrar(pagina.caminho_banco)
    dialogo = DialogoConfirmacaoSituacaoProduto(produto, False, pagina)
    qtbot.addWidget(dialogo)
    dialogo.show()
    qtbot.wait(20)

    assert dialogo.botao_sim.text() == "Sim"
    assert dialogo.botao_nao.text() == "Não"
    assert dialogo.width() <= 500
    assert dialogo.height() <= 190
    assert "Deseja desativar" in dialogo.rotulo_pergunta.text()
    for botao in (dialogo.botao_sim, dialogo.botao_nao):
        assert 110 <= botao.width() <= 125
        assert 30 <= botao.height() <= 34
        assert botao.width() > botao.height() * 3
