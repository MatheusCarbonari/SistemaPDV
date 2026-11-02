import pytest

from services.ean13 import validar_ean13


@pytest.mark.parametrize(
    "codigo",
    [
        "0000000000017",
        "0000000000000",
        "9999999999994",
    ],
)
def test_validar_ean13_aceita_codigos_validos(codigo) -> None:
    assert validar_ean13(codigo) is True


@pytest.mark.parametrize(
    "codigo",
    [
        "2023400053673",
        "0000000000001",
        "9999999999995",
    ],
)
def test_validar_ean13_rejeita_digito_verificador_incorreto(codigo) -> None:
    assert validar_ean13(codigo) is False


@pytest.mark.parametrize(
    "codigo",
    [
        "",
        "202340005367",
        "20234000536722",
    ],
)
def test_validar_ean13_rejeita_comprimento_invalido(codigo) -> None:
    assert validar_ean13(codigo) is False


@pytest.mark.parametrize(
    "codigo",
    [
        "202340005367A",
        "20234-0053672",
        "２０２３４０００５３６７２",
    ],
)
def test_validar_ean13_rejeita_caracteres_que_nao_sao_digitos_ascii(codigo) -> None:
    assert validar_ean13(codigo) is False


@pytest.mark.parametrize(
    "codigo",
    [
        None,
        2023400053672,
        2023400053672.0,
        b"2023400053672",
        [],
        {},
    ],
)
def test_validar_ean13_rejeita_tipos_inesperados(codigo) -> None:
    assert validar_ean13(codigo) is False
