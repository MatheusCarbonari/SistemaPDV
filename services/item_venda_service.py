from models.item_venda import ItemVenda
from models.produto_snapshot import criar_snapshot_produto
from services.produto_etiqueta import ProdutoEtiqueta


def criar_item_de_etiqueta(produto_etiqueta: ProdutoEtiqueta) -> ItemVenda:
    """Cria um item imutável a partir de uma etiqueta já associada ao produto."""
    produto_snapshot = criar_snapshot_produto(produto_etiqueta.produto)

    return ItemVenda(
        produto=produto_snapshot,
        origem="ETIQUETA",
        subtotal_centavos=produto_etiqueta.etiqueta.valor_centavos,
        codigo_barras=produto_etiqueta.etiqueta.codigo_barras,
        quantidade=None,
        origem_quantidade="NAO_INFORMADA",
    )
