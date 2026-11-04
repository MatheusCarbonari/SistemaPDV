from dataclasses import dataclass

from models.pagamento import PagamentosEmAndamento
from models.venda_em_andamento import VendaEmAndamento


@dataclass(frozen=True)
class VendaConfirmada:
    """Resultado comercial validado, ainda sem identidade persistente."""

    venda: VendaEmAndamento
    pagamentos: PagamentosEmAndamento

    def __post_init__(self) -> None:
        if not isinstance(self.venda, VendaEmAndamento):
            raise ValueError(
                "A venda confirmada deve conter uma VendaEmAndamento."
            )

        if not isinstance(self.pagamentos, PagamentosEmAndamento):
            raise ValueError(
                "A venda confirmada deve conter PagamentosEmAndamento."
            )
