def validar_ean13(codigo: object) -> bool:
    """Retorna se o código possui formato e dígito verificador EAN-13 válidos."""
    if not isinstance(codigo, str) or len(codigo) != 13:
        return False

    if any(caractere < "0" or caractere > "9" for caractere in codigo):
        return False

    digitos = [int(caractere) for caractere in codigo]
    soma = sum(
        digito * (1 if indice % 2 == 0 else 3)
        for indice, digito in enumerate(digitos[:12])
    )
    digito_verificador = (10 - soma % 10) % 10

    return digito_verificador == digitos[12]
