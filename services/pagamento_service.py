from models.pagamento import Pagamento, PagamentosEmAndamento


def dividir_valor_igualmente(
    valor_total_centavos: int,
    quantidade_partes: int,
) -> tuple[int, ...]:
    """Divide um valor em partes inteiras e distribui o resto no início."""
    if (
        not isinstance(valor_total_centavos, int)
        or isinstance(valor_total_centavos, bool)
    ):
        raise TypeError("O valor total deve ser um número inteiro em centavos.")

    if (
        not isinstance(quantidade_partes, int)
        or isinstance(quantidade_partes, bool)
    ):
        raise TypeError("A quantidade de partes deve ser um número inteiro.")

    if valor_total_centavos <= 0:
        raise ValueError("O valor total deve ser positivo.")

    if quantidade_partes <= 0:
        raise ValueError("A quantidade de partes deve ser positiva.")

    if quantidade_partes > valor_total_centavos:
        raise ValueError(
            "A quantidade de partes não pode ultrapassar o valor em centavos."
        )

    valor_base, resto = divmod(valor_total_centavos, quantidade_partes)

    return tuple(
        valor_base + (1 if indice < resto else 0)
        for indice in range(quantidade_partes)
    )


def adicionar_pagamento(
    pagamentos: PagamentosEmAndamento,
    pagamento: Pagamento,
) -> PagamentosEmAndamento:
    """Retorna um novo estado com o pagamento acrescentado ao final."""
    _validar_pagamentos(pagamentos)

    if not isinstance(pagamento, Pagamento):
        raise TypeError("O pagamento deve ser uma instância de Pagamento.")

    if pagamento.valor_centavos > calcular_saldo_restante(pagamentos):
        raise ValueError("O pagamento não pode ultrapassar o saldo restante.")

    return PagamentosEmAndamento(
        total_venda_centavos=pagamentos.total_venda_centavos,
        pagamentos=pagamentos.pagamentos + (pagamento,),
    )


def editar_pagamento(
    pagamentos: PagamentosEmAndamento,
    indice: int,
    pagamento: Pagamento,
) -> PagamentosEmAndamento:
    """Substitui o pagamento indicado sem modificar o estado recebido."""
    _validar_pagamentos(pagamentos)
    _validar_indice(pagamentos, indice)

    if not isinstance(pagamento, Pagamento):
        raise TypeError("O pagamento deve ser uma instância de Pagamento.")

    novos_pagamentos = (
        pagamentos.pagamentos[:indice]
        + (pagamento,)
        + pagamentos.pagamentos[indice + 1 :]
    )

    return PagamentosEmAndamento(
        total_venda_centavos=pagamentos.total_venda_centavos,
        pagamentos=novos_pagamentos,
    )


def remover_pagamento(
    pagamentos: PagamentosEmAndamento,
    indice: int,
) -> PagamentosEmAndamento:
    """Remove o pagamento indicado preservando a ordem dos demais."""
    _validar_pagamentos(pagamentos)
    _validar_indice(pagamentos, indice)

    novos_pagamentos = (
        pagamentos.pagamentos[:indice]
        + pagamentos.pagamentos[indice + 1 :]
    )

    return PagamentosEmAndamento(
        total_venda_centavos=pagamentos.total_venda_centavos,
        pagamentos=novos_pagamentos,
    )


def calcular_total_pago(pagamentos: PagamentosEmAndamento) -> int:
    """Soma os pagamentos registrados em centavos."""
    _validar_pagamentos(pagamentos)
    return sum(
        pagamento.valor_centavos for pagamento in pagamentos.pagamentos
    )


def calcular_saldo_restante(pagamentos: PagamentosEmAndamento) -> int:
    """Calcula quanto ainda falta para cobrir o total da venda."""
    _validar_pagamentos(pagamentos)
    return pagamentos.total_venda_centavos - calcular_total_pago(pagamentos)


def esta_integralmente_pago(pagamentos: PagamentosEmAndamento) -> bool:
    """Informa se os pagamentos cobrem exatamente o total da venda."""
    _validar_pagamentos(pagamentos)
    return calcular_saldo_restante(pagamentos) == 0


def _validar_pagamentos(pagamentos: PagamentosEmAndamento) -> None:
    if not isinstance(pagamentos, PagamentosEmAndamento):
        raise TypeError(
            "Os pagamentos devem ser uma instância de PagamentosEmAndamento."
        )


def _validar_indice(
    pagamentos: PagamentosEmAndamento,
    indice: int,
) -> None:
    if not isinstance(indice, int) or isinstance(indice, bool):
        raise TypeError("O índice deve ser um número inteiro.")

    if indice < 0 or indice >= len(pagamentos.pagamentos):
        raise IndexError("O índice do pagamento está fora da faixa.")
