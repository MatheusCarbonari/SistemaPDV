from models.pagamento import Pagamento, PagamentosEmAndamento


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
