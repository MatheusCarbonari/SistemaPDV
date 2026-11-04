from decimal import Decimal

import pytest

from models.item_venda import ItemVenda
from models.pagamento import Pagamento, PagamentosEmAndamento
from models.produto_snapshot import ProdutoSnapshot
from models.venda_em_andamento import VendaEmAndamento
from services.confirmacao_venda_service import confirmar_venda


def criar_item_produto(
    nome: str,
    subtotal_centavos: int,
    quantidade: str,
) -> ItemVenda:
    snapshot = ProdutoSnapshot(
        produto_id=1,
        codigo=f"COD-{nome}",
        nome=nome,
        forma_venda="UNIDADE",
        preco_referencia_centavos=subtotal_centavos,
    )
    return ItemVenda(
        origem="MANUAL",
        subtotal_centavos=subtotal_centavos,
        origem_quantidade="INFORMADA",
        produto=snapshot,
        quantidade=Decimal(quantidade),
    )


def test_confirmar_venda_valida_preserva_itens_snapshots_ordem_e_centavos(
) -> None:
    primeiro = criar_item_produto("Primeiro", 1234, "2")
    segundo = criar_item_produto("Segundo", 567, "1")
    venda = VendaEmAndamento(itens=(primeiro, segundo))
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=1801,
        pagamentos=(
            Pagamento("PIX", 1000),
            Pagamento("DINHEIRO", 801),
        ),
    )

    resultado = confirmar_venda(venda, pagamentos)

    assert resultado.venda is venda
    assert resultado.pagamentos is pagamentos
    assert resultado.venda.itens == (primeiro, segundo)
    assert resultado.venda.itens[0] is primeiro
    assert resultado.venda.itens[1] is segundo
    assert resultado.venda.itens[0].produto is primeiro.produto
    assert resultado.venda.itens[1].produto is segundo.produto
    assert tuple(
        item.subtotal_centavos for item in resultado.venda.itens
    ) == (1234, 567)


def test_confirmar_venda_rejeita_venda_vazia() -> None:
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=100,
        pagamentos=(Pagamento("PIX", 100),),
    )

    with pytest.raises(ValueError, match="não pode estar vazia"):
        confirmar_venda(VendaEmAndamento(), pagamentos)


def test_confirmar_venda_rejeita_total_nao_positivo() -> None:
    venda = VendaEmAndamento(
        itens=(criar_item_produto("Sem valor", 0, "1"),)
    )
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=100,
        pagamentos=(Pagamento("PIX", 100),),
    )

    with pytest.raises(ValueError, match="total da venda deve ser positivo"):
        confirmar_venda(venda, pagamentos)


def test_confirmar_venda_rejeita_pagamentos_incompletos() -> None:
    venda = VendaEmAndamento(
        itens=(criar_item_produto("Produto", 1000, "1"),)
    )
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=1000,
        pagamentos=(Pagamento("DINHEIRO", 600),),
    )

    with pytest.raises(ValueError, match="integralmente paga"):
        confirmar_venda(venda, pagamentos)


def test_confirmar_venda_rejeita_pagamentos_de_outro_total() -> None:
    venda = VendaEmAndamento(
        itens=(criar_item_produto("Produto", 1000, "1"),)
    )
    pagamentos = PagamentosEmAndamento(
        total_venda_centavos=900,
        pagamentos=(Pagamento("PIX", 900),),
    )

    with pytest.raises(ValueError, match="não correspondem ao total atual"):
        confirmar_venda(venda, pagamentos)
