from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from models.pagamento import Pagamento, PagamentosEmAndamento


@pytest.mark.parametrize(
    "modalidade",
    ["DINHEIRO", "CREDITO", "DEBITO", "PIX"],
)
def test_pagamento_aceita_modalidades_aprovadas(modalidade) -> None:
    pagamento = Pagamento(modalidade=modalidade, valor_centavos=1000)

    assert pagamento.modalidade == modalidade
    assert pagamento.valor_centavos == 1000


@pytest.mark.parametrize(
    "modalidade_invalida",
    [None, "", "CARTAO", "credito", "CRÉDITO", 1, True],
)
def test_pagamento_rejeita_modalidade_invalida(modalidade_invalida) -> None:
    with pytest.raises(
        ValueError,
        match="A modalidade deve ser DINHEIRO, CREDITO, DEBITO ou PIX.",
    ):
        Pagamento(
            modalidade=modalidade_invalida,
            valor_centavos=1000,
        )


@pytest.mark.parametrize(
    "valor_invalido",
    [None, 0, -1, True, False, 1.5, "100", Decimal("100")],
)
def test_pagamento_rejeita_valor_invalido(valor_invalido) -> None:
    with pytest.raises(ValueError, match="valor do pagamento"):
        Pagamento(
            modalidade="DINHEIRO",
            valor_centavos=valor_invalido,
        )


def test_pagamento_e_imutavel() -> None:
    pagamento = Pagamento(modalidade="PIX", valor_centavos=1000)

    with pytest.raises(FrozenInstanceError):
        pagamento.valor_centavos = 2000

    with pytest.raises(FrozenInstanceError):
        pagamento.modalidade = "DINHEIRO"


def test_pagamentos_em_andamento_inicia_vazio() -> None:
    pagamentos = PagamentosEmAndamento(total_venda_centavos=1000)

    assert pagamentos.total_venda_centavos == 1000
    assert pagamentos.pagamentos == ()


def test_pagamentos_em_andamento_preserva_ordem_e_repeticoes() -> None:
    primeiro = Pagamento("PIX", 300)
    segundo = Pagamento("DINHEIRO", 400)
    terceiro = Pagamento("PIX", 300)

    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=1000,
        pagamentos=(primeiro, segundo, terceiro),
    )

    assert pagamentos.pagamentos == (primeiro, segundo, terceiro)
    assert pagamentos.pagamentos[0] is primeiro
    assert pagamentos.pagamentos[2] is terceiro
    assert primeiro == terceiro
    assert primeiro is not terceiro


@pytest.mark.parametrize(
    "total_invalido",
    [None, 0, -1, True, False, 1.5, "1000", Decimal("1000")],
)
def test_pagamentos_em_andamento_rejeita_total_invalido(
    total_invalido,
) -> None:
    with pytest.raises(ValueError, match="total da venda"):
        PagamentosEmAndamento(total_venda_centavos=total_invalido)


def test_pagamentos_em_andamento_rejeita_lista_mutavel() -> None:
    with pytest.raises(
        ValueError,
        match="Os pagamentos devem ser informados em uma tuple.",
    ):
        PagamentosEmAndamento(
            total_venda_centavos=1000,
            pagamentos=[Pagamento("PIX", 1000)],
        )


@pytest.mark.parametrize("pagamento_invalido", [None, "pagamento", 1, ()])
def test_pagamentos_em_andamento_rejeita_elemento_invalido(
    pagamento_invalido,
) -> None:
    with pytest.raises(
        ValueError,
        match="O pagamento na posição 1 deve ser uma instância de Pagamento.",
    ):
        PagamentosEmAndamento(
            total_venda_centavos=1000,
            pagamentos=(Pagamento("PIX", 500), pagamento_invalido),
        )


def test_pagamentos_em_andamento_rejeita_total_pago_excedente() -> None:
    with pytest.raises(
        ValueError,
        match="O total pago não pode ultrapassar o total da venda.",
    ):
        PagamentosEmAndamento(
            total_venda_centavos=1000,
            pagamentos=(
                Pagamento("PIX", 600),
                Pagamento("DINHEIRO", 401),
            ),
        )


def test_pagamentos_em_andamento_aceita_cobertura_exata() -> None:
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=1000,
        pagamentos=(
            Pagamento("PIX", 999),
            Pagamento("DINHEIRO", 1),
        ),
    )

    assert pagamentos.total_venda_centavos == 1000
    assert len(pagamentos.pagamentos) == 2


def test_pagamentos_em_andamento_e_imutavel() -> None:
    pagamento = Pagamento("PIX", 500)
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=1000,
        pagamentos=(pagamento,),
    )

    with pytest.raises(FrozenInstanceError):
        pagamentos.total_venda_centavos = 2000

    with pytest.raises(FrozenInstanceError):
        pagamentos.pagamentos = ()

    with pytest.raises(TypeError):
        pagamentos.pagamentos[0] = Pagamento("DINHEIRO", 500)
