from decimal import Decimal

import pytest

from services.estimativa_peso import estimar_peso


def test_estimar_peso_retorna_exemplo_observado() -> None:
    resultado = estimar_peso(5367, 5990)

    assert resultado == Decimal("0.896")
    assert resultado.as_tuple().exponent == -3


def test_estimar_peso_retorna_zero_com_tres_casas_decimais() -> None:
    resultado = estimar_peso(0, 5990)

    assert resultado == Decimal("0.000")
    assert resultado.as_tuple().exponent == -3


@pytest.mark.parametrize(
    ("subtotal_centavos", "preco_kg_centavos", "esperado"),
    [
        (1, 2000, Decimal("0.001")),
        (1, 4000, Decimal("0.000")),
        (14995, 10000, Decimal("1.500")),
    ],
)
def test_estimar_peso_aplica_round_half_up(
    subtotal_centavos,
    preco_kg_centavos,
    esperado,
) -> None:
    resultado = estimar_peso(subtotal_centavos, preco_kg_centavos)

    assert resultado == esperado
    assert resultado.as_tuple().exponent == -3


def test_estimar_peso_rejeita_subtotal_negativo() -> None:
    with pytest.raises(ValueError, match="O subtotal não pode ser negativo."):
        estimar_peso(-1, 5990)


@pytest.mark.parametrize("preco_kg_centavos", [0, -1])
def test_estimar_peso_rejeita_preco_nao_positivo(preco_kg_centavos) -> None:
    with pytest.raises(
        ValueError,
        match="O preço por kg deve ser maior que zero.",
    ):
        estimar_peso(5367, preco_kg_centavos)


@pytest.mark.parametrize(
    ("subtotal_centavos", "preco_kg_centavos"),
    [
        (True, 5990),
        (5367, False),
        (5367.0, 5990),
        (5367, 5990.0),
        (Decimal("5367"), 5990),
        (5367, Decimal("5990")),
        ("5367", 5990),
        (5367, None),
    ],
)
def test_estimar_peso_rejeita_tipos_invalidos(
    subtotal_centavos,
    preco_kg_centavos,
) -> None:
    with pytest.raises(TypeError):
        estimar_peso(subtotal_centavos, preco_kg_centavos)
