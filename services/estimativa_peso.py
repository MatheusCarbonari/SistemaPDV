from decimal import Decimal, ROUND_HALF_UP


CASAS_DECIMAIS_PESO = Decimal("0.001")


def estimar_peso(
    subtotal_centavos: int,
    preco_kg_centavos: int,
) -> Decimal:
    """Estima o peso em kg com três casas decimais.

    Raises:
        TypeError: se os argumentos não forem inteiros reais ou forem bool.
        ValueError: se o subtotal for negativo ou o preço não for positivo.
    """
    if (
        not isinstance(subtotal_centavos, int)
        or isinstance(subtotal_centavos, bool)
    ):
        raise TypeError("O subtotal deve ser um número inteiro em centavos.")

    if (
        not isinstance(preco_kg_centavos, int)
        or isinstance(preco_kg_centavos, bool)
    ):
        raise TypeError("O preço por kg deve ser um número inteiro em centavos.")

    if subtotal_centavos < 0:
        raise ValueError("O subtotal não pode ser negativo.")

    if preco_kg_centavos <= 0:
        raise ValueError("O preço por kg deve ser maior que zero.")

    peso = Decimal(subtotal_centavos) / Decimal(preco_kg_centavos)

    return peso.quantize(CASAS_DECIMAIS_PESO, rounding=ROUND_HALF_UP)
