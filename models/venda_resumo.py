from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VendaResumo:
    """Projeção resumida e imutável de uma venda persistida."""

    venda_id: int
    total_centavos: int
    registrada_em: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.venda_id, int)
            or isinstance(self.venda_id, bool)
            or self.venda_id <= 0
        ):
            raise ValueError("O ID da venda deve ser um inteiro positivo.")

        if (
            not isinstance(self.total_centavos, int)
            or isinstance(self.total_centavos, bool)
            or self.total_centavos <= 0
        ):
            raise ValueError("O total da venda deve ser positivo em centavos.")

        if (
            not isinstance(self.registrada_em, datetime)
            or self.registrada_em.tzinfo is None
            or self.registrada_em.utcoffset() is None
        ):
            raise ValueError("A data de registro deve conter fuso horário.")
