from decimal import Decimal

import pytest
from PySide6.QtCore import Qt

from database.schema import criar_tabelas
from interface.janela_principal import JanelaPrincipal
from models.produto import Produto
from repositories.produto_repository import salvar_produto


ETIQUETA_PRODUTO_234 = "2023400053672"
ETIQUETA_PRODUTO_11 = "2001100137083"
ETIQUETA_PRODUTO_147 = "2014700015903"


@pytest.fixture
def caminho_banco(tmp_path):
    caminho = tmp_path / "fluxo_leitura_etiquetas.db"
    criar_tabelas(caminho)

    salvar_produto(
        Produto(
            codigo="234",
            nome="Produto 234",
            categoria="TESTE",
            forma_venda="PESO",
            preco_venda_centavos=5990,
            origem="COMPRADO",
        ),
        caminho,
    )
    salvar_produto(
        Produto(
            codigo="11",
            nome="Produto 11",
            categoria="TESTE",
            forma_venda="UNIDADE",
            preco_venda_centavos=3000,
            origem="COMPRADO",
        ),
        caminho,
    )
    return caminho


@pytest.fixture
def janela(qtbot, caminho_banco):
    janela_principal = JanelaPrincipal(caminho_banco)
    qtbot.addWidget(janela_principal)
    janela_principal.show()
    qtbot.waitUntil(janela_principal.isVisible)
    qtbot.waitUntil(janela_principal.campo_entrada.hasFocus)
    return janela_principal


def digitar_etiqueta(janela, qtbot, codigo, quantidade_esperada):
    qtbot.keyClicks(janela.campo_entrada, codigo)
    qtbot.waitUntil(
        lambda: len(janela.estado_venda.venda.itens) == quantidade_esperada
    )
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


@pytest.mark.parametrize(
    ("codigo", "subtotal_esperado"),
    [
        (ETIQUETA_PRODUTO_234, 5367),
        (ETIQUETA_PRODUTO_11, 13708),
    ],
)
def test_digitacao_de_etiqueta_real_inclui_automaticamente_na_venda(
    janela,
    qtbot,
    codigo,
    subtotal_esperado,
) -> None:
    digitar_etiqueta(janela, qtbot, codigo, 1)

    item = janela.estado_venda.venda.itens[0]
    assert item.codigo_barras == codigo
    assert item.subtotal_centavos == subtotal_esperado
    assert janela.tabela_itens.item(0, 3).text() == (
        f"R$ {subtotal_esperado // 100},{subtotal_esperado % 100:02d}"
    )
    assert janela.campo_entrada.text() == ""


def test_sequencia_com_repeticao_e_enter_adicional_nao_duplica_itens(
    janela,
    qtbot,
) -> None:
    leituras = [
        (ETIQUETA_PRODUTO_234, 5367),
        (ETIQUETA_PRODUTO_234, 5367),
        (ETIQUETA_PRODUTO_11, 13708),
    ]

    for quantidade, (codigo, _) in enumerate(leituras, start=1):
        digitar_etiqueta(janela, qtbot, codigo, quantidade)
        qtbot.keyPress(janela.campo_entrada, Qt.Key.Key_Return)

    itens = janela.estado_venda.venda.itens
    assert len(itens) == len(leituras)
    assert [item.codigo_barras for item in itens] == [
        codigo for codigo, _ in leituras
    ]
    assert [item.subtotal_centavos for item in itens] == [
        subtotal for _, subtotal in leituras
    ]
    assert itens[0] is not itens[1]
    assert janela.tabela_itens.rowCount() == len(leituras)
    assert janela.rotulo_total.text() == "Total: R$ 244,42"


def test_entradas_invalidas_e_incompletas_nao_alteram_venda(
    janela,
    qtbot,
) -> None:
    qtbot.keyClicks(janela.campo_entrada, ETIQUETA_PRODUTO_234[:-1])

    assert janela.estado_venda.venda.itens == ()
    assert janela.campo_entrada.text() == ETIQUETA_PRODUTO_234[:-1]
    assert janela.campo_entrada.hasFocus()

    qtbot.keyClick(janela.campo_entrada, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qtbot.keyClicks(janela.campo_entrada, "2023400053673")

    assert janela.estado_venda.venda.itens == ()
    assert "EAN-13 válido" in janela.rotulo_status.text()
    assert janela.campo_entrada.text() == ""
    qtbot.waitUntil(janela.campo_entrada.hasFocus)

    qtbot.keyClicks(janela.campo_entrada, ETIQUETA_PRODUTO_147)

    assert janela.estado_venda.venda.itens == ()
    assert "Produto não encontrado" in janela.rotulo_status.text()
    assert janela.campo_entrada.text() == ""
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_fluxo_continua_apos_etiqueta_invalida(janela, qtbot) -> None:
    qtbot.keyClicks(janela.campo_entrada, "2023400053673")
    qtbot.waitUntil(janela.campo_entrada.hasFocus)

    digitar_etiqueta(janela, qtbot, ETIQUETA_PRODUTO_234, 1)

    assert len(janela.estado_venda.venda.itens) == 1
    assert janela.estado_venda.venda.itens[0].subtotal_centavos == 5367
    assert janela.tabela_itens.rowCount() == 1


def test_alterna_codigo_manual_com_enter_e_etiqueta_automatica(
    janela,
    qtbot,
) -> None:
    qtbot.keyClicks(janela.campo_entrada, "11")
    assert janela.dialogo_atual is None
    qtbot.keyPress(janela.campo_entrada, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: janela.dialogo_atual is not None)

    dialogo = janela.dialogo_atual
    qtbot.keyClicks(dialogo.campo_quantidade, "2")
    qtbot.keyPress(dialogo.campo_quantidade, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: janela.dialogo_atual is None)
    qtbot.waitUntil(janela.campo_entrada.hasFocus)

    digitar_etiqueta(janela, qtbot, ETIQUETA_PRODUTO_234, 2)

    manual, etiqueta = janela.estado_venda.venda.itens
    assert manual.origem == "MANUAL"
    assert manual.quantidade == Decimal("2")
    assert etiqueta.origem == "ETIQUETA"
    assert etiqueta.codigo_barras == ETIQUETA_PRODUTO_234
    assert janela.tabela_itens.rowCount() == 2
    assert janela.rotulo_total.text() == "Total: R$ 113,67"
