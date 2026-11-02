from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from models.item_venda import ItemVenda
from models.produto_snapshot import ProdutoSnapshot


def criar_snapshot_de_teste() -> ProdutoSnapshot:
    return ProdutoSnapshot(
        produto_id=42,
        codigo="234",
        nome="Picanha",
        forma_venda="PESO",
        preco_referencia_centavos=7990,
    )


def test_item_venda_de_etiqueta_preserva_dados_recebidos() -> None:
    produto = criar_snapshot_de_teste()

    item = ItemVenda(
        produto=produto,
        origem="ETIQUETA",
        subtotal_centavos=5367,
        codigo_barras="2023400053672",
        quantidade=Decimal("0.6717146433"),
        origem_quantidade="ESTIMADA",
    )

    assert item.produto is produto
    assert item.subtotal_centavos == 5367
    assert item.codigo_barras == "2023400053672"
    assert item.quantidade == Decimal("0.6717146433")
    assert item.origem_quantidade == "ESTIMADA"


def test_item_venda_manual_aceita_produto_e_quantidade_ausentes() -> None:
    item = ItemVenda(
        origem="MANUAL",
        subtotal_centavos=1000,
        origem_quantidade="NAO_INFORMADA",
    )

    assert item.produto is None
    assert item.codigo_barras is None
    assert item.quantidade is None


def test_item_venda_manual_aceita_quantidade_decimal_informada() -> None:
    item = ItemVenda(
        produto=criar_snapshot_de_teste(),
        origem="MANUAL",
        subtotal_centavos=15980,
        quantidade=Decimal("2"),
        origem_quantidade="INFORMADA",
    )

    assert item.quantidade == Decimal("2")
    assert item.origem_quantidade == "INFORMADA"


@pytest.mark.parametrize("subtotal", [-1, True, 10.5, Decimal("10")])
def test_item_venda_rejeita_subtotal_invalido(subtotal) -> None:
    with pytest.raises(ValueError):
        ItemVenda(
            origem="MANUAL",
            subtotal_centavos=subtotal,
            origem_quantidade="NAO_INFORMADA",
        )


@pytest.mark.parametrize("origem", ["OUTRA", None, []])
def test_item_venda_rejeita_origem_invalida(origem) -> None:
    with pytest.raises(ValueError, match="A origem deve ser ETIQUETA ou MANUAL."):
        ItemVenda(
            origem=origem,
            subtotal_centavos=1000,
            origem_quantidade="NAO_INFORMADA",
        )


@pytest.mark.parametrize("origem_quantidade", ["OUTRA", None, []])
def test_item_venda_rejeita_origem_da_quantidade_invalida(
    origem_quantidade,
) -> None:
    with pytest.raises(ValueError, match="A origem da quantidade deve ser"):
        ItemVenda(
            origem="MANUAL",
            subtotal_centavos=1000,
            origem_quantidade=origem_quantidade,
        )


@pytest.mark.parametrize(
    "quantidade",
    [1, Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_item_venda_rejeita_quantidade_invalida(quantidade) -> None:
    with pytest.raises(ValueError):
        ItemVenda(
            origem="MANUAL",
            subtotal_centavos=1000,
            quantidade=quantidade,
            origem_quantidade="INFORMADA",
        )


@pytest.mark.parametrize("origem_quantidade", ["INFORMADA", "ESTIMADA"])
def test_item_venda_rejeita_origem_para_quantidade_ausente(
    origem_quantidade,
) -> None:
    with pytest.raises(
        ValueError,
        match="Quantidade ausente exige origem NAO_INFORMADA.",
    ):
        ItemVenda(
            origem="MANUAL",
            subtotal_centavos=1000,
            origem_quantidade=origem_quantidade,
        )


def test_item_venda_rejeita_quantidade_presente_com_origem_nao_informada() -> None:
    with pytest.raises(
        ValueError,
        match="Quantidade presente exige origem INFORMADA ou ESTIMADA.",
    ):
        ItemVenda(
            origem="MANUAL",
            subtotal_centavos=1000,
            quantidade=Decimal("1"),
            origem_quantidade="NAO_INFORMADA",
        )


@pytest.mark.parametrize("codigo_barras", [None, ""])
def test_item_venda_de_etiqueta_exige_codigo_de_barras(codigo_barras) -> None:
    with pytest.raises(
        ValueError,
        match="Item com origem ETIQUETA exige código de barras.",
    ):
        ItemVenda(
            origem="ETIQUETA",
            subtotal_centavos=1000,
            codigo_barras=codigo_barras,
            origem_quantidade="NAO_INFORMADA",
        )


def test_item_venda_manual_rejeita_codigo_de_barras() -> None:
    with pytest.raises(
        ValueError,
        match="Item com origem MANUAL não deve possuir código de barras.",
    ):
        ItemVenda(
            origem="MANUAL",
            subtotal_centavos=1000,
            codigo_barras="2023400053672",
            origem_quantidade="NAO_INFORMADA",
        )


def test_item_venda_rejeita_produto_que_nao_e_snapshot() -> None:
    with pytest.raises(ValueError, match="O produto deve ser um ProdutoSnapshot"):
        ItemVenda(
            produto="234",
            origem="MANUAL",
            subtotal_centavos=1000,
            origem_quantidade="NAO_INFORMADA",
        )


def test_item_venda_e_imutavel() -> None:
    item = ItemVenda(
        origem="MANUAL",
        subtotal_centavos=1000,
        origem_quantidade="NAO_INFORMADA",
    )

    with pytest.raises(FrozenInstanceError):
        item.subtotal_centavos = 2000
