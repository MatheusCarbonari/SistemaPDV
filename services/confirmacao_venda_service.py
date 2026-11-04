from models.pagamento import PagamentosEmAndamento
from models.venda_confirmada import VendaConfirmada
from models.venda_em_andamento import VendaEmAndamento
from services.pagamento_service import esta_integralmente_pago
from services.venda_em_andamento_service import calcular_total


def validar_confirmacao_venda(
    venda: VendaEmAndamento,
    pagamentos: PagamentosEmAndamento,
) -> None:
    """Valida a confirmação comercial sem alterar os objetos recebidos."""
    if not isinstance(venda, VendaEmAndamento):
        raise TypeError("A venda deve ser uma instância de VendaEmAndamento.")

    if not isinstance(pagamentos, PagamentosEmAndamento):
        raise TypeError(
            "Os pagamentos devem ser uma instância de PagamentosEmAndamento."
        )

    if not venda.itens:
        raise ValueError("A venda não pode estar vazia.")

    total_venda = calcular_total(venda)
    if total_venda <= 0:
        raise ValueError("O total da venda deve ser positivo.")

    if pagamentos.total_venda_centavos != total_venda:
        raise ValueError(
            "Os pagamentos não correspondem ao total atual da venda."
        )

    if not esta_integralmente_pago(pagamentos):
        raise ValueError("A venda deve estar integralmente paga.")


def confirmar_venda(
    venda: VendaEmAndamento,
    pagamentos: PagamentosEmAndamento,
) -> VendaConfirmada:
    """Produz o resultado validado que será persistido em ticket futuro."""
    validar_confirmacao_venda(venda, pagamentos)
    return VendaConfirmada(venda=venda, pagamentos=pagamentos)
