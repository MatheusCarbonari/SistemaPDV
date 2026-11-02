from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from models.produto_snapshot import ProdutoSnapshot


OrigemItemVenda = Literal["ETIQUETA", "MANUAL"]
OrigemQuantidade = Literal["INFORMADA", "ESTIMADA", "NAO_INFORMADA"]

ORIGENS_VALIDAS = frozenset({"ETIQUETA", "MANUAL"})
ORIGENS_QUANTIDADE_VALIDAS = frozenset(
    {"INFORMADA", "ESTIMADA", "NAO_INFORMADA"}
)


@dataclass(frozen=True)
class ItemVenda:
    origem: OrigemItemVenda
    subtotal_centavos: int
    origem_quantidade: OrigemQuantidade
    produto: ProdutoSnapshot | None = None
    codigo_barras: str | None = None
    quantidade: Decimal | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.subtotal_centavos, int)
            or isinstance(self.subtotal_centavos, bool)
        ):
            raise ValueError("O subtotal deve ser um número inteiro em centavos.")

        if self.subtotal_centavos < 0:
            raise ValueError("O subtotal não pode ser negativo.")

        if not isinstance(self.origem, str) or self.origem not in ORIGENS_VALIDAS:
            raise ValueError("A origem deve ser ETIQUETA ou MANUAL.")

        if (
            not isinstance(self.origem_quantidade, str)
            or self.origem_quantidade not in ORIGENS_QUANTIDADE_VALIDAS
        ):
            raise ValueError(
                "A origem da quantidade deve ser INFORMADA, ESTIMADA "
                "ou NAO_INFORMADA."
            )

        if self.produto is not None and not isinstance(
            self.produto,
            ProdutoSnapshot,
        ):
            raise ValueError("O produto deve ser um ProdutoSnapshot ou None.")

        if self.quantidade is None:
            if self.origem_quantidade != "NAO_INFORMADA":
                raise ValueError(
                    "Quantidade ausente exige origem NAO_INFORMADA."
                )
        else:
            if not isinstance(self.quantidade, Decimal):
                raise ValueError("A quantidade deve ser informada como Decimal.")

            if not self.quantidade.is_finite() or self.quantidade <= 0:
                raise ValueError("A quantidade deve ser positiva e finita.")

            if self.origem_quantidade == "NAO_INFORMADA":
                raise ValueError(
                    "Quantidade presente exige origem INFORMADA ou ESTIMADA."
                )

        if self.origem == "ETIQUETA":
            if not isinstance(self.codigo_barras, str) or self.codigo_barras == "":
                raise ValueError(
                    "Item com origem ETIQUETA exige código de barras."
                )
        elif self.codigo_barras is not None:
            raise ValueError(
                "Item com origem MANUAL não deve possuir código de barras."
            )
