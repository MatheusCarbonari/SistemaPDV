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
