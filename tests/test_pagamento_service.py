import pytest

from models.pagamento import Pagamento, PagamentosEmAndamento
from services.pagamento_service import (
    adicionar_pagamento,
    calcular_saldo_restante,
    calcular_total_pago,
    esta_integralmente_pago,
)


def test_adicionar_pagamento_unico() -> None:
    estado_inicial = PagamentosEmAndamento(total_venda_centavos=1000)
    pagamento = Pagamento("DINHEIRO", 1000)

    novo_estado = adicionar_pagamento(estado_inicial, pagamento)

    assert novo_estado.pagamentos == (pagamento,)
    assert novo_estado.pagamentos[0] is pagamento
    assert calcular_total_pago(novo_estado) == 1000
    assert calcular_saldo_restante(novo_estado) == 0
    assert esta_integralmente_pago(novo_estado) is True


def test_pagamento_dividido_entre_modalidades_diferentes() -> None:
    pagamentos = PagamentosEmAndamento(total_venda_centavos=10000)

    pagamentos = adicionar_pagamento(
        pagamentos,
        Pagamento("DINHEIRO", 2500),
    )
    pagamentos = adicionar_pagamento(
        pagamentos,
        Pagamento("CREDITO", 3000),
    )
    pagamentos = adicionar_pagamento(
        pagamentos,
        Pagamento("DEBITO", 2000),
    )
    pagamentos = adicionar_pagamento(
        pagamentos,
        Pagamento("PIX", 2500),
    )

    assert [pagamento.modalidade for pagamento in pagamentos.pagamentos] == [
        "DINHEIRO",
        "CREDITO",
        "DEBITO",
        "PIX",
    ]
    assert calcular_total_pago(pagamentos) == 10000
    assert esta_integralmente_pago(pagamentos) is True


def test_modalidade_repetida_preserva_registros_independentes() -> None:
    primeiro = Pagamento("PIX", 1000)
    segundo = Pagamento("PIX", 2000)
    terceiro = Pagamento("PIX", 3000)
    pagamentos = PagamentosEmAndamento(total_venda_centavos=6000)

    pagamentos = adicionar_pagamento(pagamentos, primeiro)
    pagamentos = adicionar_pagamento(pagamentos, segundo)
    pagamentos = adicionar_pagamento(pagamentos, terceiro)

    assert pagamentos.pagamentos == (primeiro, segundo, terceiro)
    assert pagamentos.pagamentos[0] is primeiro
    assert pagamentos.pagamentos[1] is segundo
    assert pagamentos.pagamentos[2] is terceiro
    assert calcular_total_pago(pagamentos) == 6000


def test_pagamento_parcial_calcula_saldo_e_nao_finaliza() -> None:
    pagamentos = PagamentosEmAndamento(total_venda_centavos=1000)

    pagamentos = adicionar_pagamento(
        pagamentos,
        Pagamento("DINHEIRO", 400),
    )

    assert calcular_total_pago(pagamentos) == 400
    assert calcular_saldo_restante(pagamentos) == 600
    assert esta_integralmente_pago(pagamentos) is False


def test_pagamento_integral_exige_saldo_zero() -> None:
    pagamentos = PagamentosEmAndamento(total_venda_centavos=1000)
    pagamentos = adicionar_pagamento(pagamentos, Pagamento("PIX", 999))

    assert calcular_saldo_restante(pagamentos) == 1
    assert esta_integralmente_pago(pagamentos) is False

    pagamentos = adicionar_pagamento(
        pagamentos,
        Pagamento("DINHEIRO", 1),
    )

    assert calcular_saldo_restante(pagamentos) == 0
    assert esta_integralmente_pago(pagamentos) is True


def test_pagamento_que_ultrapassa_total_e_rejeitado_sem_mudar_estado() -> None:
    primeiro = Pagamento("DINHEIRO", 600)
    estado_inicial = PagamentosEmAndamento(total_venda_centavos=1000)
    estado_parcial = adicionar_pagamento(estado_inicial, primeiro)
    pagamentos_antes_da_falha = estado_parcial.pagamentos

    with pytest.raises(
        ValueError,
        match="O pagamento não pode ultrapassar o saldo restante.",
    ):
        adicionar_pagamento(estado_parcial, Pagamento("PIX", 401))

    assert estado_inicial.pagamentos == ()
    assert estado_parcial.pagamentos is pagamentos_antes_da_falha
    assert estado_parcial.pagamentos == (primeiro,)
    assert calcular_total_pago(estado_parcial) == 600
    assert calcular_saldo_restante(estado_parcial) == 400


def test_pagamento_nao_pode_ser_adicionado_apos_cobertura_integral() -> None:
    estado = PagamentosEmAndamento(
        total_venda_centavos=1000,
        pagamentos=(Pagamento("PIX", 1000),),
    )

    with pytest.raises(
        ValueError,
        match="O pagamento não pode ultrapassar o saldo restante.",
    ):
        adicionar_pagamento(estado, Pagamento("DINHEIRO", 1))

    assert calcular_total_pago(estado) == 1000
    assert esta_integralmente_pago(estado) is True


def test_adicionar_pagamento_cria_novo_estado_sem_modificar_anterior() -> None:
    primeiro = Pagamento("PIX", 300)
    segundo = Pagamento("DINHEIRO", 700)
    estado_inicial = PagamentosEmAndamento(total_venda_centavos=1000)

    estado_com_primeiro = adicionar_pagamento(estado_inicial, primeiro)
    estado_completo = adicionar_pagamento(estado_com_primeiro, segundo)

    assert estado_inicial.pagamentos == ()
    assert estado_com_primeiro.pagamentos == (primeiro,)
    assert estado_completo.pagamentos == (primeiro, segundo)
    assert estado_completo.pagamentos[0] is primeiro
    assert estado_completo.pagamentos[1] is segundo


@pytest.mark.parametrize("estado_invalido", [None, (), "pagamentos", 1])
def test_funcoes_rejeitam_estado_invalido(estado_invalido) -> None:
    with pytest.raises(
        TypeError,
        match="Os pagamentos devem ser uma instância de PagamentosEmAndamento.",
    ):
        calcular_total_pago(estado_invalido)

    with pytest.raises(TypeError):
        calcular_saldo_restante(estado_invalido)

    with pytest.raises(TypeError):
        esta_integralmente_pago(estado_invalido)


@pytest.mark.parametrize("pagamento_invalido", [None, (), "pagamento", 1])
def test_adicionar_rejeita_objeto_que_nao_e_pagamento(
    pagamento_invalido,
) -> None:
    estado = PagamentosEmAndamento(total_venda_centavos=1000)

    with pytest.raises(
        TypeError,
        match="O pagamento deve ser uma instância de Pagamento.",
    ):
        adicionar_pagamento(estado, pagamento_invalido)

    assert estado.pagamentos == ()


def test_calculos_nao_modificam_pagamentos() -> None:
    primeiro = Pagamento("PIX", 400)
    segundo = Pagamento("DINHEIRO", 500)
    registros = (primeiro, segundo)
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=1000,
        pagamentos=registros,
    )

    assert calcular_total_pago(pagamentos) == 900
    assert calcular_saldo_restante(pagamentos) == 100
    assert esta_integralmente_pago(pagamentos) is False
    assert pagamentos.pagamentos is registros
    assert pagamentos.pagamentos[0] is primeiro
    assert pagamentos.pagamentos[1] is segundo
