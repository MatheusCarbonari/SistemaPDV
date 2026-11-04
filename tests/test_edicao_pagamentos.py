import pytest

from models.pagamento import Pagamento, PagamentosEmAndamento
from services.pagamento_service import (
    calcular_saldo_restante,
    calcular_total_pago,
    editar_pagamento,
    remover_pagamento,
)


def criar_estado() -> tuple[
    PagamentosEmAndamento,
    tuple[Pagamento, Pagamento, Pagamento],
]:
    pagamentos = (
        Pagamento("DINHEIRO", 300),
        Pagamento("PIX", 400),
        Pagamento("CREDITO", 200),
    )
    estado = PagamentosEmAndamento(
        total_venda_centavos=1000,
        pagamentos=pagamentos,
    )
    return estado, pagamentos


def test_remover_pagamento_preserva_ordem_e_demais_registros() -> None:
    estado, pagamentos = criar_estado()

    novo_estado = remover_pagamento(estado, 1)

    assert novo_estado.pagamentos == (pagamentos[0], pagamentos[2])
    assert novo_estado.pagamentos[0] is pagamentos[0]
    assert novo_estado.pagamentos[1] is pagamentos[2]
    assert calcular_total_pago(novo_estado) == 500
    assert calcular_saldo_restante(novo_estado) == 500


def test_editar_pagamento_substitui_modalidade_e_valor_na_mesma_posicao() -> None:
    estado, pagamentos = criar_estado()
    substituto = Pagamento("DEBITO", 500)

    novo_estado = editar_pagamento(estado, 1, substituto)

    assert novo_estado.pagamentos == (
        pagamentos[0],
        substituto,
        pagamentos[2],
    )
    assert novo_estado.pagamentos[0] is pagamentos[0]
    assert novo_estado.pagamentos[1] is substituto
    assert novo_estado.pagamentos[2] is pagamentos[2]
    assert calcular_total_pago(novo_estado) == 1000
    assert calcular_saldo_restante(novo_estado) == 0


def test_editar_apenas_modalidade_preserva_valor() -> None:
    estado, pagamentos = criar_estado()
    substituto = Pagamento("DEBITO", pagamentos[1].valor_centavos)

    novo_estado = editar_pagamento(estado, 1, substituto)

    assert novo_estado.pagamentos[1].modalidade == "DEBITO"
    assert novo_estado.pagamentos[1].valor_centavos == 400


def test_editar_apenas_valor_preserva_modalidade() -> None:
    estado, pagamentos = criar_estado()
    substituto = Pagamento(pagamentos[1].modalidade, 300)

    novo_estado = editar_pagamento(estado, 1, substituto)

    assert novo_estado.pagamentos[1].modalidade == "PIX"
    assert novo_estado.pagamentos[1].valor_centavos == 300
    assert calcular_saldo_restante(novo_estado) == 200


def test_edicao_que_ultrapassa_total_preserva_estado_original() -> None:
    estado, pagamentos = criar_estado()
    registros_originais = estado.pagamentos

    with pytest.raises(
        ValueError,
        match="O total pago não pode ultrapassar o total da venda.",
    ):
        editar_pagamento(estado, 1, Pagamento("PIX", 501))

    assert estado.pagamentos is registros_originais
    assert estado.pagamentos == pagamentos
    assert calcular_total_pago(estado) == 900


@pytest.mark.parametrize("indice_invalido", [None, True, False, 1.0, "1"])
def test_editar_e_remover_rejeitam_tipo_de_indice_invalido(
    indice_invalido,
) -> None:
    estado, _ = criar_estado()

    with pytest.raises(TypeError, match="O índice deve ser um número inteiro."):
        editar_pagamento(
            estado,
            indice_invalido,
            Pagamento("PIX", 100),
        )

    with pytest.raises(TypeError, match="O índice deve ser um número inteiro."):
        remover_pagamento(estado, indice_invalido)


@pytest.mark.parametrize("indice_invalido", [-1, 3, 999])
def test_editar_e_remover_rejeitam_indice_fora_da_faixa(
    indice_invalido,
) -> None:
    estado, _ = criar_estado()

    with pytest.raises(IndexError, match="fora da faixa"):
        editar_pagamento(
            estado,
            indice_invalido,
            Pagamento("PIX", 100),
        )

    with pytest.raises(IndexError, match="fora da faixa"):
        remover_pagamento(estado, indice_invalido)


@pytest.mark.parametrize("pagamento_invalido", [None, (), "pagamento", 1])
def test_editar_rejeita_pagamento_invalido_sem_modificar_estado(
    pagamento_invalido,
) -> None:
    estado, pagamentos = criar_estado()

    with pytest.raises(
        TypeError,
        match="O pagamento deve ser uma instância de Pagamento.",
    ):
        editar_pagamento(estado, 1, pagamento_invalido)

    assert estado.pagamentos == pagamentos


@pytest.mark.parametrize("estado_invalido", [None, (), "pagamentos", 1])
def test_editar_e_remover_rejeitam_estado_invalido(estado_invalido) -> None:
    with pytest.raises(TypeError):
        editar_pagamento(
            estado_invalido,
            0,
            Pagamento("PIX", 100),
        )

    with pytest.raises(TypeError):
        remover_pagamento(estado_invalido, 0)
