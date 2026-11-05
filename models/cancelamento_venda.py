from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class CancelamentoVenda:
    venda_id: int
    motivo: str
    cancelada_em: datetime
    identidade_autorizador: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.venda_id, int)
            or isinstance(self.venda_id, bool)
            or self.venda_id <= 0
        ):
            raise ValueError("O ID da venda deve ser um inteiro positivo.")
        if not isinstance(self.motivo, str) or not self.motivo.strip():
            raise ValueError("O motivo do cancelamento não pode estar vazio.")
        if (
            not isinstance(self.cancelada_em, datetime)
            or self.cancelada_em.tzinfo is None
            or self.cancelada_em.utcoffset() != UTC.utcoffset(None)
        ):
            raise ValueError("A data do cancelamento deve estar em UTC.")
        if (
            not isinstance(self.identidade_autorizador, str)
            or not self.identidade_autorizador.strip()
        ):
            raise ValueError("A identidade do autorizador não pode estar vazia.")
