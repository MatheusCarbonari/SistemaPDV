import pytest

from models.item_venda import ItemVenda
from models.venda_em_andamento import VendaEmAndamento
from services.venda_em_andamento_service import adicionar_item, remover_item


def criar_item_de_teste(subtotal_centavos=1000) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
    )


def test_adicionar_item_em_venda_vazia() -> None:
    venda = VendaEmAndamento()
    item = criar_item_de_teste()

    nova_venda = adicionar_item(venda, item)

    assert nova_venda.itens == (item,)
    assert nova_venda.itens[0] is item


def test_adicionar_item_preserva_itens_existentes_e_ordem() -> None:
    primeiro_item = criar_item_de_teste(1000)
    segundo_item = criar_item_de_teste(2000)
    venda = VendaEmAndamento(itens=(primeiro_item,))

    nova_venda = adicionar_item(venda, segundo_item)

    assert nova_venda.itens == (primeiro_item, segundo_item)
    assert nova_venda.itens[0] is primeiro_item
    assert nova_venda.itens[1] is segundo_item


def test_adicionar_mesma_instancia_mais_de_uma_vez() -> None:
    item = criar_item_de_teste()

    primeira_versao = adicionar_item(VendaEmAndamento(), item)
    segunda_versao = adicionar_item(primeira_versao, item)

    assert segunda_versao.itens == (item, item)
    assert segunda_versao.itens[0] is item
    assert segunda_versao.itens[1] is item


def test_adicionar_item_nao_modifica_venda_ou_item_recebidos() -> None:
    item_existente = criar_item_de_teste(1000)
    novo_item = criar_item_de_teste(2000)
    venda = VendaEmAndamento(itens=(item_existente,))

    nova_venda = adicionar_item(venda, novo_item)

    assert venda.itens == (item_existente,)
    assert novo_item.subtotal_centavos == 2000
    assert nova_venda is not venda


@pytest.mark.parametrize("venda_invalida", [None, (), "venda", 1])
def test_adicionar_item_rejeita_venda_invalida(venda_invalida) -> None:
    with pytest.raises(
        TypeError,
        match="A venda deve ser uma instância de VendaEmAndamento.",
    ):
        adicionar_item(venda_invalida, criar_item_de_teste())


@pytest.mark.parametrize("item_invalido", [None, (), "item", 1])
def test_adicionar_item_rejeita_item_invalido(item_invalido) -> None:
    with pytest.raises(
        TypeError,
        match="O item deve ser uma instância de ItemVenda.",
    ):
        adicionar_item(VendaEmAndamento(), item_invalido)


def test_versoes_da_venda_permanecem_independentes() -> None:
    primeiro_item = criar_item_de_teste(1000)
    segundo_item = criar_item_de_teste(2000)
    terceiro_item = criar_item_de_teste(3000)
    venda_inicial = VendaEmAndamento()

    venda_com_primeiro = adicionar_item(venda_inicial, primeiro_item)
    venda_com_dois = adicionar_item(venda_com_primeiro, segundo_item)
    venda_alternativa = adicionar_item(venda_inicial, terceiro_item)

    assert venda_inicial.itens == ()
    assert venda_com_primeiro.itens == (primeiro_item,)
    assert venda_com_dois.itens == (primeiro_item, segundo_item)
    assert venda_alternativa.itens == (terceiro_item,)


@pytest.mark.parametrize(
    ("indice", "indices_restantes"),
    [
        (0, (1, 2)),
        (1, (0, 2)),
        (2, (0, 1)),
    ],
)
def test_remover_item_remove_primeiro_intermediario_ou_ultimo(
    indice,
    indices_restantes,
) -> None:
    itens = (
        criar_item_de_teste(1000),
        criar_item_de_teste(2000),
        criar_item_de_teste(3000),
    )
    venda = VendaEmAndamento(itens=itens)

    nova_venda = remover_item(venda, indice)

    assert nova_venda.itens == tuple(itens[i] for i in indices_restantes)
    assert all(
        item_restante is itens[indice_original]
        for item_restante, indice_original in zip(
            nova_venda.itens,
            indices_restantes,
        )
    )


def test_remover_item_unico_retorna_venda_vazia() -> None:
    item = criar_item_de_teste()
    venda = VendaEmAndamento(itens=(item,))

    nova_venda = remover_item(venda, 0)

    assert nova_venda.itens == ()
    assert venda.itens == (item,)


def test_remover_item_elimina_apenas_uma_ocorrencia_da_mesma_instancia() -> None:
    item = criar_item_de_teste()
    venda = VendaEmAndamento(itens=(item, item, item))

    nova_venda = remover_item(venda, 1)

    assert len(nova_venda.itens) == 2
    assert nova_venda.itens[0] is item
    assert nova_venda.itens[1] is item


def test_remover_item_distingue_objetos_iguais_pela_posicao() -> None:
    primeiro_item = criar_item_de_teste()
    segundo_item = criar_item_de_teste()
    assert primeiro_item == segundo_item
    assert primeiro_item is not segundo_item
    venda = VendaEmAndamento(itens=(primeiro_item, segundo_item))

    nova_venda = remover_item(venda, 0)

    assert nova_venda.itens == (segundo_item,)
    assert nova_venda.itens[0] is segundo_item


@pytest.mark.parametrize(
    ("venda", "indice"),
    [
        (VendaEmAndamento(), 0),
        (VendaEmAndamento(), -1),
        (VendaEmAndamento(itens=(criar_item_de_teste(),)), -1),
        (VendaEmAndamento(itens=(criar_item_de_teste(),)), 1),
        (VendaEmAndamento(itens=(criar_item_de_teste(),)), 999),
    ],
)
def test_remover_item_rejeita_indice_fora_da_faixa(venda, indice) -> None:
    with pytest.raises(
        IndexError,
        match="O índice do item está fora da faixa da venda.",
    ):
        remover_item(venda, indice)


@pytest.mark.parametrize("indice_invalido", [True, False, 0.0, "0", None])
def test_remover_item_rejeita_tipo_de_indice_invalido(indice_invalido) -> None:
    venda = VendaEmAndamento(itens=(criar_item_de_teste(),))

    with pytest.raises(TypeError, match="O índice deve ser um número inteiro."):
        remover_item(venda, indice_invalido)


@pytest.mark.parametrize("venda_invalida", [None, (), "venda", 1])
def test_remover_item_rejeita_venda_invalida(venda_invalida) -> None:
    with pytest.raises(
        TypeError,
        match="A venda deve ser uma instância de VendaEmAndamento.",
    ):
        remover_item(venda_invalida, 0)


def test_remover_item_preserva_venda_original_e_versoes_independentes() -> None:
    primeiro_item = criar_item_de_teste(1000)
    segundo_item = criar_item_de_teste(2000)
    terceiro_item = criar_item_de_teste(3000)
    venda_original = VendaEmAndamento(
        itens=(primeiro_item, segundo_item, terceiro_item),
    )

    sem_primeiro = remover_item(venda_original, 0)
    sem_ultimo = remover_item(venda_original, 2)

    assert venda_original.itens == (primeiro_item, segundo_item, terceiro_item)
    assert sem_primeiro.itens == (segundo_item, terceiro_item)
    assert sem_ultimo.itens == (primeiro_item, segundo_item)
    assert sem_primeiro.itens[0] is segundo_item
    assert sem_ultimo.itens[1] is segundo_item
