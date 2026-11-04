from dataclasses import dataclass
from datetime import datetime

from models.item_venda import ItemVenda
from models.pagamento import Pagamento
from models.venda_resumo import VendaResumo


@dataclass(frozen=True)
class ItemVendaDetalhado:
    posicao: int
    item: ItemVenda

    def __post_init__(self) -> None:
        if (
            not isinstance(self.posicao, int)
            or isinstance(self.posicao, bool)
            or self.posicao < 0
        ):
            raise ValueError("A posição do item deve ser um inteiro não negativo.")
        if not isinstance(self.item, ItemVenda):
            raise ValueError("O detalhe deve conter um ItemVenda.")


@dataclass(frozen=True)
class VendaDetalhada:
    resumo: VendaResumo
    itens: tuple[ItemVendaDetalhado, ...]
    pagamentos: tuple[Pagamento, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.resumo, VendaResumo):
            raise ValueError("O detalhe deve conter um VendaResumo.")
        if not isinstance(self.itens, tuple) or not all(
            isinstance(item, ItemVendaDetalhado) for item in self.itens
        ):
            raise ValueError("Os itens detalhados devem ser informados em tuple.")
        if not isinstance(self.pagamentos, tuple) or not all(
            isinstance(pagamento, Pagamento) for pagamento in self.pagamentos
        ):
            raise ValueError("Os pagamentos devem ser informados em tuple.")

    @property
    def venda_id(self) -> int:
        return self.resumo.venda_id

    @property
    def total_centavos(self) -> int:
        return self.resumo.total_centavos

    @property
    def registrada_em(self) -> datetime:
        return self.resumo.registrada_em
