from dataclasses import dataclass


@dataclass(frozen=True)
class CapacidadeAutorizacao:
    """Nonce opaco; os dados da autorização ficam somente no emissor."""

    identificador: str

    def __post_init__(self) -> None:
        if not isinstance(self.identificador, str) or len(self.identificador) < 32:
            raise ValueError("A capacidade de autorização é inválida.")
