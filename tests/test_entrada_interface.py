from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit

from database.schema import criar_tabelas
from interface.dialogos_entrada import (
    DialogoDiversos,
    DialogoPeso,
    DialogoUnidade,
)
from tests.helpers_identidade import criar_janela_autenticada
from models.produto import Produto
from repositories.produto_repository import salvar_produto


@pytest.fixture
def caminho_banco(tmp_path):
    caminho = tmp_path / "teste_entrada_interface.db"
    criar_tabelas(caminho)

    salvar_produto(
        Produto(
            codigo="11",
            nome="Espetinho",
            categoria="ESPETINHOS",
            forma_venda="UNIDADE",
            preco_venda_centavos=1500,
            origem="PRODUZIDO",
        ),
        caminho,
    )
    salvar_produto(
        Produto(
            codigo="234",
            nome="Picanha",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=9900,
            origem="COMPRADO",
        ),
        caminho,
    )

    return caminho


@pytest.fixture
def janela(qtbot, caminho_banco):
    janela_principal = criar_janela_autenticada(caminho_banco)
    qtbot.addWidget(janela_principal)
    janela_principal.show()
    qtbot.waitUntil(janela_principal.isVisible)
    qtbot.waitUntil(janela_principal.campo_entrada.hasFocus)
    return janela_principal


def processar_codigo(janela, qtbot, codigo: str) -> None:
    janela.campo_entrada.setText(codigo)
    qtbot.keyPress(janela.campo_entrada, Qt.Key.Key_Return)


def test_janela_possui_um_unico_campo_principal(janela) -> None:
    campos = janela.pagina_frente_caixa.findChildren(QLineEdit)

    assert campos == [janela.campo_entrada]
    assert janela.campo_entrada.objectName() == "campo_entrada"


@pytest.mark.parametrize(
    ("codigo", "classe_dialogo"),
    [
        ("11", DialogoUnidade),
        ("234", DialogoPeso),
        ("9999", DialogoDiversos),
    ],
)
def test_enter_reconhece_codigo_e_abre_dialogo_correto(
    janela,
    qtbot,
    codigo,
    classe_dialogo,
) -> None:
    processar_codigo(janela, qtbot, codigo)

    qtbot.waitUntil(lambda: isinstance(janela.dialogo_atual, classe_dialogo))
    assert janela.dialogo_atual.isVisible()


def test_etiqueta_valida_emite_item_preservando_subtotal(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)

    processar_codigo(janela, qtbot, "2023400053672")

    assert len(itens) == 1
    assert itens[0].origem == "ETIQUETA"
    assert itens[0].subtotal_centavos == 5367
    assert itens[0].codigo_barras == "2023400053672"
    assert itens[0].produto.codigo == "234"
    assert janela.campo_entrada.text() == ""
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_etiqueta_completa_e_processada_sem_enter(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)

    janela.campo_entrada.setText("2023400053672")

    assert len(itens) == 1
    assert itens[0].codigo_barras == "2023400053672"
    assert janela.campo_entrada.text() == ""
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_leituras_automaticas_consecutivas_emitem_uma_vez_cada(
    janela,
    qtbot,
) -> None:
    itens = []
    janela.item_criado.connect(itens.append)

    janela.campo_entrada.setText("2023400053672")
    janela.campo_entrada.setText("2023400053672")

    assert [item.codigo_barras for item in itens] == [
        "2023400053672",
        "2023400053672",
    ]
    assert janela.campo_entrada.text() == ""


def test_enter_adicional_do_leitor_nao_duplica_etiqueta(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)

    janela.campo_entrada.setText("2023400053672")
    qtbot.keyPress(janela.campo_entrada, Qt.Key.Key_Return)

    assert len(itens) == 1
    assert janela.rotulo_status.text() == "Item confirmado."
    assert janela.dialogo_atual is None


@pytest.mark.parametrize(
    ("codigo", "classe_dialogo"),
    [("11", DialogoUnidade), ("9999", DialogoDiversos)],
)
def test_codigo_curto_continua_exigindo_enter(
    janela,
    qtbot,
    codigo,
    classe_dialogo,
) -> None:
    janela.campo_entrada.setText(codigo)

    assert janela.dialogo_atual is None

    qtbot.keyPress(janela.campo_entrada, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: isinstance(janela.dialogo_atual, classe_dialogo))


@pytest.mark.parametrize(
    ("codigo", "mensagem"),
    [
        ("2023400053673", "EAN-13 válido"),
        ("2014700015903", "Produto não encontrado"),
    ],
)
def test_etiqueta_invalida_ou_sem_produto_nao_emite_item(
    janela,
    codigo,
    mensagem,
) -> None:
    itens = []
    janela.item_criado.connect(itens.append)

    janela.campo_entrada.setText(codigo)

    assert itens == []
    assert mensagem in janela.rotulo_status.text()
    assert janela.campo_entrada.text() == ""


def test_entrada_invalida_exibe_erro_sem_travar(janela, qtbot) -> None:
    processar_codigo(janela, qtbot, "ABC")

    assert "apenas números" in janela.rotulo_status.text()
    assert janela.dialogo_atual is None
    assert janela.campo_entrada.text() == ""
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_dialogo_unidade_atualiza_previa_e_enter_confirma(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)
    processar_codigo(janela, qtbot, "11")
    dialogo = janela.dialogo_atual

    dialogo.campo_quantidade.setText("2,333")

    assert dialogo.item_previa.subtotal_centavos == 3500
    assert dialogo.item_previa.quantidade == Decimal("2.333")
    assert dialogo.item_previa.origem_quantidade == "INFORMADA"
    assert dialogo.rotulo_subtotal.text() == "R$ 35,00"

    qtbot.keyPress(dialogo.campo_quantidade, Qt.Key.Key_Return)

    qtbot.waitUntil(lambda: janela.dialogo_atual is None)
    assert itens == [dialogo.item_previa]
    assert janela.campo_entrada.text() == ""
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_dialogo_unidade_nao_confirma_quantidade_invalida(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)
    processar_codigo(janela, qtbot, "11")
    dialogo = janela.dialogo_atual

    dialogo.campo_quantidade.setText("2,3333")
    qtbot.keyPress(dialogo.campo_quantidade, Qt.Key.Key_Return)

    assert dialogo.item_previa is None
    assert dialogo.isVisible()
    assert itens == []


def test_dialogo_peso_alterna_campo_principal_sem_ciclo(janela, qtbot) -> None:
    processar_codigo(janela, qtbot, "234")
    dialogo = janela.dialogo_atual

    dialogo.campo_peso.setText("1,250")

    assert dialogo.campo_principal == "PESO"
    assert dialogo.campo_valor.text() == "123,75"
    assert dialogo.item_previa.quantidade == Decimal("1.250")
    assert dialogo.item_previa.subtotal_centavos == 12375
    assert dialogo.item_previa.origem_quantidade == "INFORMADA"

    dialogo.campo_valor.setText("5,00")

    assert dialogo.campo_principal == "VALOR"
    assert dialogo.campo_peso.text() == "0.051"
    assert dialogo.item_previa.quantidade == Decimal("0.051")
    assert dialogo.item_previa.subtotal_centavos == 500
    assert dialogo.item_previa.origem_quantidade == "ESTIMADA"


def test_dialogo_peso_preserva_valor_ao_confirmar(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)
    processar_codigo(janela, qtbot, "234")
    dialogo = janela.dialogo_atual
    dialogo.campo_valor.setText("123,75")

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    qtbot.waitUntil(lambda: janela.dialogo_atual is None)
    assert itens[0].subtotal_centavos == 12375
    assert itens[0].quantidade == Decimal("1.250")
    assert itens[0].origem_quantidade == "ESTIMADA"


def test_dialogo_peso_mantem_confirmacao_desabilitada_para_dado_incompleto(
    janela,
    qtbot,
) -> None:
    processar_codigo(janela, qtbot, "234")
    dialogo = janela.dialogo_atual

    dialogo.campo_peso.setText("-")

    assert dialogo.item_previa is None
    assert dialogo.rotulo_erro.text() != ""
    assert dialogo.isVisible()


def test_dialogo_diversos_exibe_descricao_e_confirma_valor(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)
    processar_codigo(janela, qtbot, "9999")
    dialogo = janela.dialogo_atual

    assert dialogo.windowTitle() == "Diversos"
    dialogo.campo_valor.setText("12,34")
    assert dialogo.rotulo_subtotal.text() == "R$ 12,34"

    qtbot.keyPress(dialogo.campo_valor, Qt.Key.Key_Return)

    qtbot.waitUntil(lambda: janela.dialogo_atual is None)
    assert itens[0].tipo_item == "DIVERSOS"
    assert itens[0].subtotal_centavos == 1234
    assert itens[0].produto is None


def test_escape_cancela_sem_emitir_item_e_restaura_foco(janela, qtbot) -> None:
    itens = []
    janela.item_criado.connect(itens.append)
    processar_codigo(janela, qtbot, "11")
    dialogo = janela.dialogo_atual
    dialogo.campo_quantidade.setText("2")

    qtbot.keyPress(dialogo, Qt.Key.Key_Escape)

    qtbot.waitUntil(lambda: janela.dialogo_atual is None)
    assert itens == []
    assert janela.rotulo_status.text() == "Operação cancelada."
    assert janela.campo_entrada.text() == ""
    qtbot.waitUntil(janela.campo_entrada.hasFocus)


def test_atualizar_previa_nao_emite_item_antes_da_confirmacao(
    janela,
    qtbot,
) -> None:
    itens = []
    janela.item_criado.connect(itens.append)
    processar_codigo(janela, qtbot, "9999")
    dialogo = janela.dialogo_atual

    dialogo.campo_valor.setText("10,00")

    assert dialogo.item_previa is not None
    assert itens == []
    assert dialogo.result() == QDialog.DialogCode.Rejected
