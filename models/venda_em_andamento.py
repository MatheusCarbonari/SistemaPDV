from dataclasses import dataclass

from models.item_venda import ItemVenda


@dataclass(frozen=True)
class VendaEmAndamento:
    itens: tuple[ItemVenda, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.itens, tuple):
            raise ValueError("Os itens da venda devem ser informados em uma tuple.")

        for indice, item in enumerate(self.itens):
            if not isinstance(item, ItemVenda):
                raise ValueError(
                    f"O item na posição {indice} deve ser uma instância "
                    "de ItemVenda."
                )
