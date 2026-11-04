from decimal import Decimal

import pytest

from services.pagamento_service import dividir_valor_igualmente


def test_divisao_exata_sem_resto() -> None:
    partes = dividir_valor_igualmente(900, 3)

    assert partes == (300, 300, 300)


def test_divisao_com_resto_de_um_centavo() -> None:
    partes = dividir_valor_igualmente(1000, 3)

    assert partes == (334, 333, 333)


def test_divisao_distribui_varios_centavos_restantes_no_inicio() -> None:
    partes = dividir_valor_igualmente(1003, 4)

    assert partes == (251, 251, 251, 250)


def test_cem_reais_divididos_em_tres_partes() -> None:
    partes = dividir_valor_igualmente(10000, 3)

    assert partes == (3334, 3333, 3333)
    assert sum(partes) == 10000


def test_divisao_em_uma_unica_parte() -> None:
    assert dividir_valor_igualmente(12345, 1) == (12345,)


def test_valor_minimo_de_um_centavo() -> None:
    assert dividir_valor_igualmente(1, 1) == (1,)


def test_quantidade_de_partes_igual_ao_total_em_centavos() -> None:
    partes = dividir_valor_igualmente(5, 5)

    assert partes == (1, 1, 1, 1, 1)


def test_rejeita_mais_partes_que_centavos_disponiveis() -> None:
    with pytest.raises(
        ValueError,
        match="A quantidade de partes não pode ultrapassar o valor em centavos.",
    ):
        dividir_valor_igualmente(2, 3)


@pytest.mark.parametrize(
    "valor_invalido",
    [None, True, False, 10.0, "10", Decimal("10")],
)
def test_rejeita_tipo_invalido_para_valor_total(valor_invalido) -> None:
    with pytest.raises(
        TypeError,
        match="O valor total deve ser um número inteiro em centavos.",
    ):
        dividir_valor_igualmente(valor_invalido, 2)


@pytest.mark.parametrize("valor_invalido", [0, -1, -100])
def test_rejeita_valor_total_nao_positivo(valor_invalido) -> None:
    with pytest.raises(ValueError, match="O valor total deve ser positivo."):
        dividir_valor_igualmente(valor_invalido, 1)


@pytest.mark.parametrize(
    "quantidade_invalida",
    [None, True, False, 2.0, "2", Decimal("2")],
)
def test_rejeita_tipo_invalido_para_quantidade_de_partes(
    quantidade_invalida,
) -> None:
    with pytest.raises(
        TypeError,
        match="A quantidade de partes deve ser um número inteiro.",
    ):
        dividir_valor_igualmente(100, quantidade_invalida)


@pytest.mark.parametrize("quantidade_invalida", [0, -1, -100])
def test_rejeita_quantidade_de_partes_nao_positiva(
    quantidade_invalida,
) -> None:
    with pytest.raises(
        ValueError,
        match="A quantidade de partes deve ser positiva.",
    ):
        dividir_valor_igualmente(100, quantidade_invalida)


@pytest.mark.parametrize(
    ("valor_total", "quantidade_partes"),
    [
        (2, 2),
        (7, 3),
        (10, 6),
        (100, 9),
        (999, 17),
        (10000, 3),
        (999999, 97),
    ],
)
def test_preserva_soma_e_diferenca_maxima_de_um_centavo(
    valor_total,
    quantidade_partes,
) -> None:
    partes = dividir_valor_igualmente(valor_total, quantidade_partes)

    assert len(partes) == quantidade_partes
    assert all(isinstance(parte, int) and parte > 0 for parte in partes)
    assert sum(partes) == valor_total
    assert max(partes) - min(partes) <= 1


def test_retorno_e_imutavel_e_deterministico() -> None:
    primeiro_resultado = dividir_valor_igualmente(1003, 4)
    segundo_resultado = dividir_valor_igualmente(1003, 4)

    assert isinstance(primeiro_resultado, tuple)
    assert primeiro_resultado == segundo_resultado

    with pytest.raises(TypeError):
        primeiro_resultado[0] = 250
