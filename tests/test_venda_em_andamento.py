from dataclasses import FrozenInstanceError

import pytest

from models.item_venda import ItemVenda
from models.venda_em_andamento import VendaEmAndamento


def criar_item_de_teste(subtotal_centavos=1000) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
    )


def test_venda_em_andamento_inicia_vazia() -> None:
    venda = VendaEmAndamento()

    assert venda.itens == ()


def test_venda_em_andamento_aceita_um_item() -> None:
    item = criar_item_de_teste()

    venda = VendaEmAndamento(itens=(item,))

    assert venda.itens == (item,)


def test_venda_em_andamento_preserva_varios_itens_na_ordem() -> None:
    primeiro_item = criar_item_de_teste(1000)
    segundo_item = criar_item_de_teste(2000)
    terceiro_item = criar_item_de_teste(3000)

    venda = VendaEmAndamento(
        itens=(primeiro_item, segundo_item, terceiro_item),
    )

    assert venda.itens == (primeiro_item, segundo_item, terceiro_item)


def test_venda_em_andamento_rejeita_lista_de_itens() -> None:
    with pytest.raises(
        ValueError,
        match="Os itens da venda devem ser informados em uma tuple.",
    ):
        VendaEmAndamento(itens=[criar_item_de_teste()])


@pytest.mark.parametrize("item_invalido", [None, "item", 1])
def test_venda_em_andamento_rejeita_elemento_de_tipo_incorreto(
    item_invalido,
) -> None:
    with pytest.raises(
        ValueError,
        match="O item na posição 1 deve ser uma instância de ItemVenda.",
    ):
        VendaEmAndamento(
            itens=(criar_item_de_teste(), item_invalido),
        )


def test_venda_em_andamento_e_imutavel() -> None:
    venda = VendaEmAndamento()

    with pytest.raises(FrozenInstanceError):
        venda.itens = (criar_item_de_teste(),)


def test_colecao_de_itens_e_imutavel() -> None:
    venda = VendaEmAndamento(itens=(criar_item_de_teste(),))

    with pytest.raises(TypeError):
        venda.itens[0] = criar_item_de_teste(2000)


def test_vendas_em_andamento_sao_independentes() -> None:
    item = criar_item_de_teste()

    venda_com_item = VendaEmAndamento(itens=(item,))
    venda_vazia = VendaEmAndamento()

    assert venda_com_item.itens == (item,)
    assert venda_vazia.itens == ()


def test_item_imutavel_pode_ser_compartilhado_entre_vendas() -> None:
    item = criar_item_de_teste()

    primeira_venda = VendaEmAndamento(itens=(item,))
    segunda_venda = VendaEmAndamento(itens=(item,))

    assert primeira_venda.itens[0] is item
    assert segunda_venda.itens[0] is item

    with pytest.raises(FrozenInstanceError):
        item.subtotal_centavos = 2000
