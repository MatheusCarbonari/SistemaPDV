from decimal import Decimal, ROUND_HALF_UP


UNIDADE_INTEIRA = Decimal("1")


def estimar_unidades(
    subtotal_centavos: int,
    preco_unitario_centavos: int,
) -> int:
    """Sugere uma quantidade inteira de unidades.

    Para subtotal positivo, o retorno mínimo é uma unidade.

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
        not isinstance(preco_unitario_centavos, int)
        or isinstance(preco_unitario_centavos, bool)
    ):
        raise TypeError(
            "O preço unitário deve ser um número inteiro em centavos."
        )

    if subtotal_centavos < 0:
        raise ValueError("O subtotal não pode ser negativo.")

    if preco_unitario_centavos <= 0:
        raise ValueError("O preço unitário deve ser maior que zero.")

    if subtotal_centavos == 0:
        return 0

    quantidade = Decimal(subtotal_centavos) / Decimal(preco_unitario_centavos)
    quantidade_arredondada = quantidade.quantize(
        UNIDADE_INTEIRA,
        rounding=ROUND_HALF_UP,
    )

    return max(1, int(quantidade_arredondada))
