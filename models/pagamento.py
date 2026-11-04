from dataclasses import dataclass
from typing import Literal


ModalidadePagamento = Literal["DINHEIRO", "CREDITO", "DEBITO", "PIX"]

MODALIDADES_PAGAMENTO_VALIDAS = frozenset(
    {"DINHEIRO", "CREDITO", "DEBITO", "PIX"}
)


@dataclass(frozen=True)
class Pagamento:
    modalidade: ModalidadePagamento
    valor_centavos: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.modalidade, str)
            or self.modalidade not in MODALIDADES_PAGAMENTO_VALIDAS
        ):
            raise ValueError(
                "A modalidade deve ser DINHEIRO, CREDITO, DEBITO ou PIX."
            )

        if (
            not isinstance(self.valor_centavos, int)
            or isinstance(self.valor_centavos, bool)
        ):
            raise ValueError(
                "O valor do pagamento deve ser um número inteiro em centavos."
            )

        if self.valor_centavos <= 0:
            raise ValueError("O valor do pagamento deve ser positivo.")


@dataclass(frozen=True)
class PagamentosEmAndamento:
    total_venda_centavos: int
    pagamentos: tuple[Pagamento, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.total_venda_centavos, int)
            or isinstance(self.total_venda_centavos, bool)
        ):
            raise ValueError(
                "O total da venda deve ser um número inteiro em centavos."
            )

        if self.total_venda_centavos <= 0:
            raise ValueError("O total da venda deve ser positivo.")

        if not isinstance(self.pagamentos, tuple):
            raise ValueError("Os pagamentos devem ser informados em uma tuple.")

        for indice, pagamento in enumerate(self.pagamentos):
            if not isinstance(pagamento, Pagamento):
                raise ValueError(
                    f"O pagamento na posição {indice} deve ser uma "
                    "instância de Pagamento."
                )

        total_pago = sum(
            pagamento.valor_centavos for pagamento in self.pagamentos
        )
        if total_pago > self.total_venda_centavos:
            raise ValueError("O total pago não pode ultrapassar o total da venda.")
