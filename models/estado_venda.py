from dataclasses import dataclass

from models.item_venda import ItemVenda
from models.venda_em_andamento import VendaEmAndamento


@dataclass(frozen=True)
class RemocaoPendente:
    item: ItemVenda
    indice_original: int

    def __post_init__(self) -> None:
        if not isinstance(self.item, ItemVenda):
            raise ValueError("O item removido deve ser uma instância de ItemVenda.")

        if (
            not isinstance(self.indice_original, int)
            or isinstance(self.indice_original, bool)
        ):
            raise ValueError("O índice original deve ser um número inteiro.")

        if self.indice_original < 0:
            raise ValueError("O índice original não pode ser negativo.")


@dataclass(frozen=True)
class EstadoVenda:
    venda: VendaEmAndamento
    ultima_remocao: RemocaoPendente | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.venda, VendaEmAndamento):
            raise ValueError("A venda deve ser uma instância de VendaEmAndamento.")

        if self.ultima_remocao is not None and not isinstance(
            self.ultima_remocao,
            RemocaoPendente,
        ):
            raise ValueError(
                "A última remoção deve ser uma RemocaoPendente ou None."
            )

        if (
            self.ultima_remocao is not None
            and self.ultima_remocao.indice_original > len(self.venda.itens)
        ):
            raise ValueError(
                "O índice original da remoção não pode ultrapassar "
                "o tamanho atual da venda."
            )
