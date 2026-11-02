from models.estado_venda import EstadoVenda, RemocaoPendente
from models.item_venda import ItemVenda
from models.venda_em_andamento import VendaEmAndamento
from services.venda_em_andamento_service import (
    adicionar_item,
    inserir_item,
    remover_item,
)


def remover_com_desfazer(estado: EstadoVenda, indice: int) -> EstadoVenda:
    """Remove um item e guarda somente essa remoção para possível restauração."""
    _validar_estado(estado)
    nova_venda = remover_item(estado.venda, indice)
    remocao = RemocaoPendente(
        item=estado.venda.itens[indice],
        indice_original=indice,
    )

    return EstadoVenda(venda=nova_venda, ultima_remocao=remocao)


def desfazer_ultima_remocao(estado: EstadoVenda) -> EstadoVenda:
    """Restaura e consome a última remoção, quando ela existir."""
    _validar_estado(estado)

    if estado.ultima_remocao is None:
        return estado

    venda_restaurada = inserir_item(
        estado.venda,
        estado.ultima_remocao.indice_original,
        estado.ultima_remocao.item,
    )

    return EstadoVenda(venda=venda_restaurada)


def adicionar_no_estado(
    estado: EstadoVenda,
    item: ItemVenda,
) -> EstadoVenda:
    """Adiciona um item e descarta eventual remoção pendente."""
    _validar_estado(estado)
    nova_venda = adicionar_item(estado.venda, item)

    return EstadoVenda(venda=nova_venda)


def inserir_no_estado(
    estado: EstadoVenda,
    indice: int,
    item: ItemVenda,
) -> EstadoVenda:
    """Insere um item e descarta eventual remoção pendente."""
    _validar_estado(estado)
    nova_venda = inserir_item(estado.venda, indice, item)

    return EstadoVenda(venda=nova_venda)


def _validar_estado(estado: EstadoVenda) -> None:
    if not isinstance(estado, EstadoVenda):
        raise TypeError("O estado deve ser uma instância de EstadoVenda.")
