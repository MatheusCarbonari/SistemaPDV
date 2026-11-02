from decimal import Decimal

from models.item_venda import ItemVenda
from models.produto_snapshot import criar_snapshot_produto
from services.estimativa_peso import estimar_peso
from services.estimativa_unidades import estimar_unidades
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


def criar_item_de_etiqueta_com_estimativa(
    produto_etiqueta: ProdutoEtiqueta,
) -> ItemVenda:
    """Cria um item de etiqueta com quantidade estimada quando possível."""
    produto_snapshot = criar_snapshot_produto(produto_etiqueta.produto)
    subtotal_centavos = produto_etiqueta.etiqueta.valor_centavos
    preco_referencia_centavos = produto_snapshot.preco_referencia_centavos

    if produto_snapshot.forma_venda not in {"PESO", "UNIDADE"}:
        raise ValueError("A forma de venda deve ser PESO ou UNIDADE.")

    quantidade = None
    origem_quantidade = "NAO_INFORMADA"

    if subtotal_centavos != 0 and preco_referencia_centavos != 0:
        if produto_snapshot.forma_venda == "PESO":
            peso_estimado = estimar_peso(
                subtotal_centavos,
                preco_referencia_centavos,
            )

            if peso_estimado > 0:
                quantidade = peso_estimado
                origem_quantidade = "ESTIMADA"
        else:
            unidades_estimadas = estimar_unidades(
                subtotal_centavos,
                preco_referencia_centavos,
            )
            quantidade = Decimal(unidades_estimadas)
            origem_quantidade = "ESTIMADA"

    return ItemVenda(
        produto=produto_snapshot,
        origem="ETIQUETA",
        subtotal_centavos=subtotal_centavos,
        codigo_barras=produto_etiqueta.etiqueta.codigo_barras,
        quantidade=quantidade,
        origem_quantidade=origem_quantidade,
    )
