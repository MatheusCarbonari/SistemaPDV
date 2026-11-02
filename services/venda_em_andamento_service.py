from models.item_venda import ItemVenda
from models.venda_em_andamento import VendaEmAndamento


def adicionar_item(
    venda: VendaEmAndamento,
    item: ItemVenda,
) -> VendaEmAndamento:
    """Retorna uma nova venda com o item acrescentado ao final."""
    if not isinstance(venda, VendaEmAndamento):
        raise TypeError("A venda deve ser uma instância de VendaEmAndamento.")

    if not isinstance(item, ItemVenda):
        raise TypeError("O item deve ser uma instância de ItemVenda.")

    return VendaEmAndamento(itens=venda.itens + (item,))


def remover_item(
    venda: VendaEmAndamento,
    indice: int,
) -> VendaEmAndamento:
    """Retorna uma nova venda sem o item da posição indicada."""
    if not isinstance(venda, VendaEmAndamento):
        raise TypeError("A venda deve ser uma instância de VendaEmAndamento.")

    if not isinstance(indice, int) or isinstance(indice, bool):
        raise TypeError("O índice deve ser um número inteiro.")

    if indice < 0 or indice >= len(venda.itens):
        raise IndexError("O índice do item está fora da faixa da venda.")

    itens_restantes = venda.itens[:indice] + venda.itens[indice + 1:]

    return VendaEmAndamento(itens=itens_restantes)


def inserir_item(
    venda: VendaEmAndamento,
    indice: int,
    item: ItemVenda,
) -> VendaEmAndamento:
    """Retorna uma nova venda com o item inserido na posição indicada."""
    if not isinstance(venda, VendaEmAndamento):
        raise TypeError("A venda deve ser uma instância de VendaEmAndamento.")

    if not isinstance(indice, int) or isinstance(indice, bool):
        raise TypeError("O índice deve ser um número inteiro.")

    if not isinstance(item, ItemVenda):
        raise TypeError("O item deve ser uma instância de ItemVenda.")

    if indice < 0 or indice > len(venda.itens):
        raise IndexError("O índice de inserção está fora da faixa da venda.")

    novos_itens = venda.itens[:indice] + (item,) + venda.itens[indice:]

    return VendaEmAndamento(itens=novos_itens)
