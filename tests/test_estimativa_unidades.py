from decimal import Decimal

import pytest

from services.estimativa_unidades import estimar_unidades


@pytest.mark.parametrize(
    ("subtotal_centavos", "preco_unitario_centavos", "esperado"),
    [
        (7000, 3000, 2),
        (7500, 3000, 3),
        (9000, 3000, 3),
        (500, 3000, 1),
    ],
)
def test_estimar_unidades_retorna_exemplos_solicitados(
    subtotal_centavos,
    preco_unitario_centavos,
    esperado,
) -> None:
    assert (
        estimar_unidades(subtotal_centavos, preco_unitario_centavos)
        == esperado
    )


def test_estimar_unidades_retorna_zero_para_subtotal_zero() -> None:
    assert estimar_unidades(0, 3000) == 0


@pytest.mark.parametrize(
    ("subtotal_centavos", "preco_unitario_centavos", "esperado"),
    [
        (4499, 3000, 1),
        (4500, 3000, 2),
        (1, 3000, 1),
    ],
)
def test_estimar_unidades_aplica_round_half_up_e_minimo_positivo(
    subtotal_centavos,
    preco_unitario_centavos,
    esperado,
) -> None:
    assert (
        estimar_unidades(subtotal_centavos, preco_unitario_centavos)
        == esperado
    )


def test_estimar_unidades_rejeita_subtotal_negativo() -> None:
    with pytest.raises(ValueError, match="O subtotal não pode ser negativo."):
        estimar_unidades(-1, 3000)


@pytest.mark.parametrize("preco_unitario_centavos", [0, -1])
def test_estimar_unidades_rejeita_preco_nao_positivo(
    preco_unitario_centavos,
) -> None:
    with pytest.raises(
        ValueError,
        match="O preço unitário deve ser maior que zero.",
    ):
        estimar_unidades(7000, preco_unitario_centavos)


@pytest.mark.parametrize(
    ("subtotal_centavos", "preco_unitario_centavos"),
    [
        (True, 3000),
        (7000, False),
        (7000.0, 3000),
        (7000, 3000.0),
        (Decimal("7000"), 3000),
        (7000, Decimal("3000")),
        ("7000", 3000),
        (7000, None),
    ],
)
def test_estimar_unidades_rejeita_tipos_invalidos(
    subtotal_centavos,
    preco_unitario_centavos,
) -> None:
    with pytest.raises(TypeError):
        estimar_unidades(subtotal_centavos, preco_unitario_centavos)
