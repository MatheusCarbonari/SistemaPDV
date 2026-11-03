from decimal import Decimal, InvalidOperation


def formatar_centavos(valor_centavos: int) -> str:
    """Formata centavos inteiros para apresentação em reais."""
    reais, centavos = divmod(valor_centavos, 100)
    return f"R$ {reais},{centavos:02d}"


def centavos_para_texto(valor_centavos: int) -> str:
    """Converte centavos para texto editável sem símbolo monetário."""
    reais, centavos = divmod(valor_centavos, 100)
    return f"{reais},{centavos:02d}"


def ler_decimal(texto: str) -> Decimal:
    """Converte texto decimal com vírgula ou ponto, sem usar float."""
    texto_normalizado = texto.strip().replace(",", ".")

    if texto_normalizado == "":
        raise ValueError("Informe um valor.")

    try:
        return Decimal(texto_normalizado)
    except InvalidOperation as erro:
        raise ValueError("Informe um número válido.") from erro


def ler_centavos(texto: str) -> int:
    """Converte valor em reais com até duas casas para centavos inteiros."""
    valor = ler_decimal(texto)

    if not valor.is_finite():
        raise ValueError("Informe um valor finito.")

    if valor.as_tuple().exponent < -2:
        raise ValueError("O valor deve possuir no máximo duas casas decimais.")

    return int(valor * 100)
