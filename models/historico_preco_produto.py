from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HistoricoPrecoProduto:
    id: int
    produto_id: int
    preco_anterior_centavos: int
    preco_novo_centavos: int
    alterado_em: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, int) or isinstance(self.id, bool) or self.id <= 0:
            raise ValueError("O ID do histórico deve ser um inteiro positivo.")
        if (
            not isinstance(self.produto_id, int)
            or isinstance(self.produto_id, bool)
            or self.produto_id <= 0
        ):
            raise ValueError("O ID do produto deve ser um inteiro positivo.")
        for valor in (
            self.preco_anterior_centavos,
            self.preco_novo_centavos,
        ):
            if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
                raise ValueError("Os preços históricos devem ser positivos.")
        if self.preco_anterior_centavos == self.preco_novo_centavos:
            raise ValueError("A alteração deve possuir preços diferentes.")
        if not isinstance(self.alterado_em, datetime) or self.alterado_em.tzinfo is None:
            raise ValueError("O instante da alteração deve possuir fuso horário.")
