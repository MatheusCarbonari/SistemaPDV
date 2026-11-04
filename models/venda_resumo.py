from dataclasses import dataclass
from datetime import datetime
from typing import Literal


StatusVenda = Literal["ATIVA", "CANCELADA"]


@dataclass(frozen=True)
class VendaResumo:
    """Projeção resumida e imutável de uma venda persistida."""

    venda_id: int
    total_centavos: int
    registrada_em: datetime
    status: StatusVenda = "ATIVA"
    motivo_cancelamento: str | None = None
    cancelada_em: datetime | None = None
    autorizador_identidade: str | None = None

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

        if self.status not in ("ATIVA", "CANCELADA"):
            raise ValueError("O status da venda deve ser ATIVA ou CANCELADA.")

        metadados = (
            self.motivo_cancelamento,
            self.cancelada_em,
            self.autorizador_identidade,
        )
        if self.status == "ATIVA" and any(valor is not None for valor in metadados):
            raise ValueError("Venda ativa não deve conter dados de cancelamento.")

        if self.status == "CANCELADA":
            if (
                not isinstance(self.motivo_cancelamento, str)
                or not self.motivo_cancelamento.strip()
            ):
                raise ValueError("Venda cancelada exige motivo.")
            if (
                not isinstance(self.cancelada_em, datetime)
                or self.cancelada_em.tzinfo is None
                or self.cancelada_em.utcoffset() is None
            ):
                raise ValueError("Venda cancelada exige data com fuso horário.")
            if (
                not isinstance(self.autorizador_identidade, str)
                or not self.autorizador_identidade.strip()
            ):
                raise ValueError("Venda cancelada exige autorizador.")
