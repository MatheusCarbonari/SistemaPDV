import pytest

from models.estado_venda import EstadoVenda
from models.item_venda import ItemVenda
from models.venda_em_andamento import VendaEmAndamento
from services.estado_venda_service import (
    desfazer_ultima_remocao,
    remover_com_desfazer,
)
from services.venda_em_andamento_service import (
    adicionar_item,
    calcular_total,
    inserir_item,
    remover_item,
)


def criar_item_de_teste(subtotal_centavos=1000) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
    )


def test_calcular_total_de_venda_vazia_retorna_zero_inteiro() -> None:
    total = calcular_total(VendaEmAndamento())

    assert total == 0
    assert isinstance(total, int)


@pytest.mark.parametrize(
    ("subtotais", "total_esperado"),
    [
        ((1234,), 1234),
        ((1099, 205, 1), 1305),
    ],
)
def test_calcular_total_soma_um_ou_varios_subtotais_em_centavos(
    subtotais,
    total_esperado,
) -> None:
    venda = VendaEmAndamento(
        itens=tuple(criar_item_de_teste(subtotal) for subtotal in subtotais),
    )

    assert calcular_total(venda) == total_esperado


def test_calcular_total_conta_itens_iguais_e_mesma_instancia_repetida() -> None:
    item = criar_item_de_teste(1234)
    item_igual = criar_item_de_teste(1234)
    venda = VendaEmAndamento(itens=(item, item_igual, item))

    assert item == item_igual
    assert item is not item_igual
    assert calcular_total(venda) == 3702


def test_calcular_total_reflete_adicao_e_remocao() -> None:
    primeiro_item = criar_item_de_teste(1001)
    segundo_item = criar_item_de_teste(250)
    venda_original = VendaEmAndamento(itens=(primeiro_item,))

    venda_com_adicao = adicionar_item(venda_original, segundo_item)
    venda_apos_remocao = remover_item(venda_com_adicao, 0)

    assert calcular_total(venda_original) == 1001
    assert calcular_total(venda_com_adicao) == 1251
    assert calcular_total(venda_apos_remocao) == 250


def test_calcular_total_apos_desfazer_remocao() -> None:
    venda = VendaEmAndamento(
        itens=(criar_item_de_teste(1001), criar_item_de_teste(250)),
    )
    estado = EstadoVenda(venda=venda)

    estado_com_remocao = remover_com_desfazer(estado, 0)
    estado_restaurado = desfazer_ultima_remocao(estado_com_remocao)

    assert calcular_total(estado_com_remocao.venda) == 250
    assert calcular_total(estado_restaurado.venda) == 1251


@pytest.mark.parametrize("venda_invalida", [None, (), "venda", 1])
def test_calcular_total_rejeita_venda_invalida(venda_invalida) -> None:
    with pytest.raises(
        TypeError,
        match="A venda deve ser uma instância de VendaEmAndamento.",
    ):
        calcular_total(venda_invalida)


def test_calcular_total_nao_modifica_venda_ou_itens() -> None:
    primeiro_item = criar_item_de_teste(1001)
    segundo_item = criar_item_de_teste(250)
    itens = (primeiro_item, segundo_item)
    venda = VendaEmAndamento(itens=itens)

    calcular_total(venda)

    assert venda.itens is itens
    assert venda.itens[0] is primeiro_item
    assert venda.itens[1] is segundo_item
    assert primeiro_item.subtotal_centavos == 1001
    assert segundo_item.subtotal_centavos == 250


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


@pytest.mark.parametrize(
    ("indice", "ordem_esperada"),
    [
        (0, (2, 0, 1)),
        (1, (0, 2, 1)),
        (2, (0, 1, 2)),
    ],
)
def test_inserir_item_no_inicio_meio_ou_final(indice, ordem_esperada) -> None:
    primeiro_item = criar_item_de_teste(1000)
    segundo_item = criar_item_de_teste(2000)
    item_inserido = criar_item_de_teste(3000)
    itens = (primeiro_item, segundo_item, item_inserido)
    venda = VendaEmAndamento(itens=(primeiro_item, segundo_item))

    nova_venda = inserir_item(venda, indice, item_inserido)

    assert nova_venda.itens == tuple(itens[i] for i in ordem_esperada)
    assert all(
        item_resultante is itens[indice_original]
        for item_resultante, indice_original in zip(
            nova_venda.itens,
            ordem_esperada,
        )
    )


def test_inserir_item_em_venda_vazia() -> None:
    item = criar_item_de_teste()

    nova_venda = inserir_item(VendaEmAndamento(), 0, item)

    assert nova_venda.itens == (item,)
    assert nova_venda.itens[0] is item


def test_inserir_item_reconstroi_ordem_apos_remocao() -> None:
    primeiro_item = criar_item_de_teste(1000)
    item_removido = criar_item_de_teste(2000)
    terceiro_item = criar_item_de_teste(3000)
    venda_original = VendaEmAndamento(
        itens=(primeiro_item, item_removido, terceiro_item),
    )
    venda_sem_item = remover_item(venda_original, 1)

    venda_reconstruida = inserir_item(venda_sem_item, 1, item_removido)

    assert venda_reconstruida.itens == venda_original.itens
    assert all(
        item_reconstruido is item_original
        for item_reconstruido, item_original in zip(
            venda_reconstruida.itens,
            venda_original.itens,
        )
    )


def test_inserir_item_permite_mesma_instancia_em_varias_posicoes() -> None:
    item = criar_item_de_teste()
    venda = VendaEmAndamento(itens=(item, item))

    nova_venda = inserir_item(venda, 1, item)

    assert nova_venda.itens == (item, item, item)
    assert all(item_resultante is item for item_resultante in nova_venda.itens)


@pytest.mark.parametrize(
    ("venda", "indice"),
    [
        (VendaEmAndamento(), -1),
        (VendaEmAndamento(), 1),
        (VendaEmAndamento(itens=(criar_item_de_teste(),)), -1),
        (VendaEmAndamento(itens=(criar_item_de_teste(),)), 2),
        (VendaEmAndamento(itens=(criar_item_de_teste(),)), 999),
    ],
)
def test_inserir_item_rejeita_indice_fora_da_faixa(venda, indice) -> None:
    with pytest.raises(
        IndexError,
        match="O índice de inserção está fora da faixa da venda.",
    ):
        inserir_item(venda, indice, criar_item_de_teste())


@pytest.mark.parametrize("indice_invalido", [True, False, 0.0, "0", None])
def test_inserir_item_rejeita_tipo_de_indice_invalido(indice_invalido) -> None:
    with pytest.raises(TypeError, match="O índice deve ser um número inteiro."):
        inserir_item(
            VendaEmAndamento(),
            indice_invalido,
            criar_item_de_teste(),
        )


@pytest.mark.parametrize("venda_invalida", [None, (), "venda", 1])
def test_inserir_item_rejeita_venda_invalida(venda_invalida) -> None:
    with pytest.raises(
        TypeError,
        match="A venda deve ser uma instância de VendaEmAndamento.",
    ):
        inserir_item(venda_invalida, 0, criar_item_de_teste())


@pytest.mark.parametrize("item_invalido", [None, (), "item", 1])
def test_inserir_item_rejeita_item_invalido(item_invalido) -> None:
    with pytest.raises(
        TypeError,
        match="O item deve ser uma instância de ItemVenda.",
    ):
        inserir_item(VendaEmAndamento(), 0, item_invalido)


def test_inserir_item_preserva_venda_original_e_versoes_independentes() -> None:
    primeiro_item = criar_item_de_teste(1000)
    segundo_item = criar_item_de_teste(2000)
    item_inserido = criar_item_de_teste(3000)
    venda_original = VendaEmAndamento(itens=(primeiro_item, segundo_item))

    insercao_no_inicio = inserir_item(venda_original, 0, item_inserido)
    insercao_no_final = inserir_item(venda_original, 2, item_inserido)

    assert venda_original.itens == (primeiro_item, segundo_item)
    assert insercao_no_inicio.itens == (
        item_inserido,
        primeiro_item,
        segundo_item,
    )
    assert insercao_no_final.itens == (
        primeiro_item,
        segundo_item,
        item_inserido,
    )
    assert insercao_no_inicio.itens[1] is primeiro_item
    assert insercao_no_final.itens[1] is segundo_item
