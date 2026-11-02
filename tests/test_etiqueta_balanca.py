from dataclasses import FrozenInstanceError

import pytest

from services.etiqueta_balanca import interpretar_etiqueta


def test_interpretar_etiqueta_retorna_resultado_imutavel() -> None:
    etiqueta = interpretar_etiqueta("2000000000008")

    with pytest.raises(FrozenInstanceError):
        etiqueta.valor_centavos = 100


@pytest.mark.parametrize(
    "codigo",
    [
        "2023400053673",
        "",
        None,
        2023400053672,
    ],
)
def test_interpretar_etiqueta_rejeita_ean13_invalido(codigo) -> None:
    with pytest.raises(
        ValueError,
        match="O código informado não é um EAN-13 válido.",
    ):
        interpretar_etiqueta(codigo)


def test_interpretar_etiqueta_rejeita_prefixo_incorreto() -> None:
    with pytest.raises(
        ValueError,
        match="A etiqueta da balança deve começar com o prefixo 2.",
    ):
        interpretar_etiqueta("1023400053673")


def test_interpretar_etiqueta_rejeita_campo_intermediario_incorreto() -> None:
    with pytest.raises(
        ValueError,
        match="A etiqueta da balança deve conter 00 no campo intermediário.",
    ):
        interpretar_etiqueta("2023401053671")


@pytest.mark.parametrize(
    ("codigo", "codigo_produto", "valor_centavos"),
    [
        ("2000000000008", "0", 0),
        ("2999900999997", "9999", 99999),
    ],
)
def test_interpretar_etiqueta_aceita_valores_limite_e_zeros_a_esquerda(
    codigo,
    codigo_produto,
    valor_centavos,
) -> None:
    etiqueta = interpretar_etiqueta(codigo)

    assert etiqueta.codigo_barras == codigo
    assert etiqueta.codigo_produto == codigo_produto
    assert etiqueta.valor_centavos == valor_centavos
