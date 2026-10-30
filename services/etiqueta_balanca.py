from dataclasses import dataclass

from services.ean13 import validar_ean13


@dataclass(frozen=True)
class EtiquetaBalanca:
    codigo_barras: str
    codigo_produto: str
    valor_centavos: int


def interpretar_etiqueta(codigo: object) -> EtiquetaBalanca:
    """Interpreta uma etiqueta de balança no formato inicial do Sistema-PDV."""
    if not validar_ean13(codigo):
        raise ValueError("O código informado não é um EAN-13 válido.")

    if codigo[0] != "2":
        raise ValueError("A etiqueta da balança deve começar com o prefixo 2.")

    if codigo[5:7] != "00":
        raise ValueError(
            "A etiqueta da balança deve conter 00 no campo intermediário."
        )

    codigo_produto = codigo[1:5].lstrip("0") or "0"
    valor_centavos = int(codigo[7:12])

    return EtiquetaBalanca(
        codigo_barras=codigo,
        codigo_produto=codigo_produto,
        valor_centavos=valor_centavos,
    )
