from dataclasses import FrozenInstanceError

import pytest

from models.estado_venda import EstadoVenda, RemocaoPendente
from models.item_venda import ItemVenda
from models.venda_em_andamento import VendaEmAndamento
from services.estado_venda_service import (
    adicionar_no_estado,
    desfazer_ultima_remocao,
    inserir_no_estado,
    remover_com_desfazer,
)


def criar_item_de_teste(subtotal_centavos=1000) -> ItemVenda:
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="NAO_INFORMADA",
    )


def criar_estado_com_tres_itens() -> tuple[EstadoVenda, tuple[ItemVenda, ...]]:
    itens = (
        criar_item_de_teste(1000),
        criar_item_de_teste(2000),
        criar_item_de_teste(3000),
    )
    return EstadoVenda(venda=VendaEmAndamento(itens=itens)), itens


def test_remover_com_desfazer_guarda_item_e_indice() -> None:
    estado, itens = criar_estado_com_tres_itens()

    novo_estado = remover_com_desfazer(estado, 1)

    assert novo_estado.venda.itens == (itens[0], itens[2])
    assert novo_estado.ultima_remocao == RemocaoPendente(
        item=itens[1],
        indice_original=1,
    )
    assert novo_estado.ultima_remocao.item is itens[1]
    assert estado.venda.itens == itens
    assert estado.ultima_remocao is None


def test_desfazer_restaura_item_na_posicao_original_e_consumo_registro() -> None:
    estado, itens = criar_estado_com_tres_itens()
    estado_com_remocao = remover_com_desfazer(estado, 1)

    estado_restaurado = desfazer_ultima_remocao(estado_com_remocao)

    assert estado_restaurado.venda.itens == itens
    assert all(
        item_restaurado is item_original
        for item_restaurado, item_original in zip(
            estado_restaurado.venda.itens,
            itens,
        )
    )
    assert estado_restaurado.ultima_remocao is None
    assert estado_com_remocao.venda.itens == (itens[0], itens[2])
    assert estado_com_remocao.ultima_remocao is not None


def test_desfazer_preserva_duplicatas_da_mesma_instancia() -> None:
    item = criar_item_de_teste()
    estado = EstadoVenda(
        venda=VendaEmAndamento(itens=(item, item, item)),
    )

    estado_com_remocao = remover_com_desfazer(estado, 1)
    estado_restaurado = desfazer_ultima_remocao(estado_com_remocao)

    assert len(estado_restaurado.venda.itens) == 3
    assert all(item_restaurado is item for item_restaurado in estado_restaurado.venda.itens)


def test_segunda_tentativa_de_desfazer_nao_altera_estado() -> None:
    estado, _ = criar_estado_com_tres_itens()
    estado_restaurado = desfazer_ultima_remocao(
        remover_com_desfazer(estado, 1)
    )

    segunda_tentativa = desfazer_ultima_remocao(estado_restaurado)

    assert segunda_tentativa is estado_restaurado


def test_remocoes_consecutivas_substituem_registro_anterior() -> None:
    estado, itens = criar_estado_com_tres_itens()
    estado_sem_segundo = remover_com_desfazer(estado, 1)

    estado_sem_primeiro = remover_com_desfazer(estado_sem_segundo, 0)
    estado_apos_desfazer = desfazer_ultima_remocao(estado_sem_primeiro)

    assert estado_sem_primeiro.venda.itens == (itens[2],)
    assert estado_sem_primeiro.ultima_remocao.item is itens[0]
    assert estado_apos_desfazer.venda.itens == (itens[0], itens[2])
    assert itens[1] not in estado_apos_desfazer.venda.itens
    assert estado_apos_desfazer.ultima_remocao is None


def test_adicionar_no_estado_descarta_remocao_pendente() -> None:
    estado, itens = criar_estado_com_tres_itens()
    estado_com_remocao = remover_com_desfazer(estado, 1)
    novo_item = criar_item_de_teste(4000)

    estado_com_adicao = adicionar_no_estado(estado_com_remocao, novo_item)

    assert estado_com_adicao.venda.itens == (itens[0], itens[2], novo_item)
    assert estado_com_adicao.ultima_remocao is None
    assert desfazer_ultima_remocao(estado_com_adicao) is estado_com_adicao


def test_inserir_no_estado_descarta_remocao_pendente() -> None:
    estado, itens = criar_estado_com_tres_itens()
    estado_com_remocao = remover_com_desfazer(estado, 1)
    novo_item = criar_item_de_teste(4000)

    estado_com_insercao = inserir_no_estado(
        estado_com_remocao,
        1,
        novo_item,
    )

    assert estado_com_insercao.venda.itens == (itens[0], novo_item, itens[2])
    assert estado_com_insercao.ultima_remocao is None
    assert desfazer_ultima_remocao(estado_com_insercao) is estado_com_insercao


def test_estado_e_remocao_pendente_sao_imutaveis() -> None:
    estado, _ = criar_estado_com_tres_itens()
    estado_com_remocao = remover_com_desfazer(estado, 1)

    with pytest.raises(FrozenInstanceError):
        estado_com_remocao.venda = VendaEmAndamento()

    with pytest.raises(FrozenInstanceError):
        estado_com_remocao.ultima_remocao.indice_original = 0


@pytest.mark.parametrize("estado_invalido", [None, "estado", (), 1])
@pytest.mark.parametrize(
    "operacao",
    [
        lambda estado: remover_com_desfazer(estado, 0),
        desfazer_ultima_remocao,
        lambda estado: adicionar_no_estado(estado, criar_item_de_teste()),
        lambda estado: inserir_no_estado(estado, 0, criar_item_de_teste()),
    ],
)
def test_operacoes_rejeitam_estado_invalido(operacao, estado_invalido) -> None:
    with pytest.raises(
        TypeError,
        match="O estado deve ser uma instância de EstadoVenda.",
    ):
        operacao(estado_invalido)


@pytest.mark.parametrize("indice_invalido", [True, 0.0, "0", None])
def test_remover_com_desfazer_rejeita_tipo_de_indice(indice_invalido) -> None:
    estado, _ = criar_estado_com_tres_itens()

    with pytest.raises(TypeError):
        remover_com_desfazer(estado, indice_invalido)


@pytest.mark.parametrize("indice_invalido", [-1, 3, 999])
def test_remover_com_desfazer_rejeita_indice_fora_da_faixa(
    indice_invalido,
) -> None:
    estado, _ = criar_estado_com_tres_itens()

    with pytest.raises(IndexError):
        remover_com_desfazer(estado, indice_invalido)


def test_remover_com_desfazer_rejeita_venda_vazia() -> None:
    with pytest.raises(IndexError):
        remover_com_desfazer(EstadoVenda(venda=VendaEmAndamento()), 0)


@pytest.mark.parametrize("item_invalido", [None, "item", (), 1])
def test_adicionar_no_estado_rejeita_item_invalido(item_invalido) -> None:
    with pytest.raises(TypeError):
        adicionar_no_estado(
            EstadoVenda(venda=VendaEmAndamento()),
            item_invalido,
        )


@pytest.mark.parametrize("indice_invalido", [True, -1, 1, "0"])
def test_inserir_no_estado_rejeita_indice_invalido(indice_invalido) -> None:
    estado = EstadoVenda(venda=VendaEmAndamento())
    excecao = TypeError if isinstance(indice_invalido, (bool, str)) else IndexError

    with pytest.raises(excecao):
        inserir_no_estado(estado, indice_invalido, criar_item_de_teste())


@pytest.mark.parametrize("item_invalido", [None, "item", (), 1])
def test_inserir_no_estado_rejeita_item_invalido(item_invalido) -> None:
    with pytest.raises(TypeError):
        inserir_no_estado(
            EstadoVenda(venda=VendaEmAndamento()),
            0,
            item_invalido,
        )


@pytest.mark.parametrize("item_invalido", [None, "item", (), 1])
def test_remocao_pendente_rejeita_item_invalido(item_invalido) -> None:
    with pytest.raises(ValueError):
        RemocaoPendente(item=item_invalido, indice_original=0)


@pytest.mark.parametrize("indice_invalido", [True, 0.0, "0", None, -1])
def test_remocao_pendente_rejeita_indice_invalido(indice_invalido) -> None:
    with pytest.raises(ValueError):
        RemocaoPendente(
            item=criar_item_de_teste(),
            indice_original=indice_invalido,
        )


@pytest.mark.parametrize("venda_invalida", [None, "venda", (), 1])
def test_estado_venda_rejeita_venda_invalida(venda_invalida) -> None:
    with pytest.raises(ValueError):
        EstadoVenda(venda=venda_invalida)


@pytest.mark.parametrize("remocao_invalida", ["remocao", (), 1])
def test_estado_venda_rejeita_remocao_invalida(remocao_invalida) -> None:
    with pytest.raises(ValueError):
        EstadoVenda(
            venda=VendaEmAndamento(),
            ultima_remocao=remocao_invalida,
        )


def test_estado_venda_rejeita_indice_de_restauracao_fora_da_faixa() -> None:
    with pytest.raises(ValueError):
        EstadoVenda(
            venda=VendaEmAndamento(),
            ultima_remocao=RemocaoPendente(
                item=criar_item_de_teste(),
                indice_original=1,
            ),
        )
