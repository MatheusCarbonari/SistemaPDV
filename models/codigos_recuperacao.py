from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConjuntoCodigosRecuperacao:
    """Códigos originais retornados somente pela operação de emissão."""

    codigos: tuple[str, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if not self.codigos or len(set(self.codigos)) != len(self.codigos):
            raise ValueError("O conjunto de códigos de recuperação é inválido.")
