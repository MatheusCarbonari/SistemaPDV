from decimal import Decimal, ROUND_HALF_UP

from models.item_venda import ItemVenda
from models.produto import Produto
from models.produto_snapshot import criar_snapshot_produto
from services.estimativa_peso import estimar_peso
from services.estimativa_unidades import estimar_unidades
from services.produto_etiqueta import ProdutoEtiqueta


CENTAVO_INTEIRO = Decimal("1")


def criar_item_diversos(valor_centavos: int) -> ItemVenda:
    """Cria um item Diversos manual, sem vínculo com produto cadastrado."""
    if not isinstance(valor_centavos, int) or isinstance(valor_centavos, bool):
        raise TypeError("O valor deve ser um número inteiro em centavos.")

    if valor_centavos <= 0:
        raise ValueError("O valor deve ser maior que zero.")

    return ItemVenda(
        produto=None,
        origem="MANUAL",
        subtotal_centavos=valor_centavos,
        codigo_barras=None,
        quantidade=None,
        origem_quantidade="NAO_INFORMADA",
        tipo_item="DIVERSOS",
    )


def criar_item_manual_unidade(
    produto: Produto,
    quantidade: Decimal,
) -> ItemVenda:
    """Cria um item manual por unidade com quantidade informada."""
    _validar_produto_manual(produto, "UNIDADE", "unitário")
    _validar_quantidade_manual(quantidade)

    subtotal_decimal = quantidade * Decimal(produto.preco_venda_centavos)
    subtotal_centavos = _arredondar_centavos(subtotal_decimal)

    return _criar_item_manual(
        produto=produto,
        quantidade=quantidade,
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="INFORMADA",
    )


def criar_item_manual_peso_por_quantidade(
    produto: Produto,
    quantidade: Decimal,
) -> ItemVenda:
    """Cria item de PESO usando os quilogramas como informação principal."""
    _validar_produto_manual(produto, "PESO", "por kg")
    _validar_quantidade_manual(quantidade)

    subtotal_decimal = quantidade * Decimal(produto.preco_venda_centavos)
    subtotal_centavos = _arredondar_centavos(subtotal_decimal)

    if subtotal_centavos == 0:
        raise ValueError("O subtotal calculado deve ser maior que zero.")

    return _criar_item_manual(
        produto=produto,
        quantidade=quantidade,
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="INFORMADA",
    )


def criar_item_manual_peso_por_valor(
    produto: Produto,
    subtotal_centavos: int,
) -> ItemVenda:
    """Cria item de PESO preservando o subtotal como informação principal."""
    _validar_produto_manual(produto, "PESO", "por kg")

    if (
        not isinstance(subtotal_centavos, int)
        or isinstance(subtotal_centavos, bool)
    ):
        raise TypeError("O subtotal deve ser um número inteiro em centavos.")

    if subtotal_centavos <= 0:
        raise ValueError("O subtotal deve ser maior que zero.")

    quantidade = estimar_peso(
        subtotal_centavos,
        produto.preco_venda_centavos,
    )

    if quantidade == 0:
        raise ValueError("O peso estimado deve ser maior que zero.")

    return _criar_item_manual(
        produto=produto,
        quantidade=quantidade,
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="ESTIMADA",
    )


def _validar_produto_manual(
    produto: Produto,
    forma_venda: str,
    descricao_preco: str,
) -> None:
    if not isinstance(produto, Produto):
        raise TypeError("O produto deve ser uma instância de Produto.")

    if produto.ativo is not True:
        raise ValueError("O produto deve estar ativo.")

    if produto.forma_venda != forma_venda:
        raise ValueError(
            f"O produto deve possuir forma de venda {forma_venda}."
        )

    if (
        not isinstance(produto.preco_venda_centavos, int)
        or isinstance(produto.preco_venda_centavos, bool)
    ):
        raise TypeError(
            f"O preço {descricao_preco} deve ser um número inteiro em centavos."
        )

    if produto.preco_venda_centavos <= 0:
        raise ValueError(f"O preço {descricao_preco} deve ser maior que zero.")


def _validar_quantidade_manual(quantidade: Decimal) -> None:
    """Valida quantidade ou peso informado com até três casas decimais."""

    if not isinstance(quantidade, Decimal):
        raise TypeError("A quantidade deve ser informada como Decimal.")

    if not quantidade.is_finite() or quantidade <= 0:
        raise ValueError("A quantidade deve ser positiva e finita.")

    if quantidade.as_tuple().exponent < -3:
        raise ValueError(
            "A quantidade deve possuir no máximo três casas decimais."
        )


def _arredondar_centavos(valor_centavos: Decimal) -> int:
    return int(
        valor_centavos.quantize(CENTAVO_INTEIRO, rounding=ROUND_HALF_UP)
    )


def _criar_item_manual(
    produto: Produto,
    quantidade: Decimal,
    subtotal_centavos: int,
    origem_quantidade: str,
) -> ItemVenda:
    return ItemVenda(
        produto=criar_snapshot_produto(produto),
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        codigo_barras=None,
        quantidade=quantidade,
        origem_quantidade=origem_quantidade,
    )


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
