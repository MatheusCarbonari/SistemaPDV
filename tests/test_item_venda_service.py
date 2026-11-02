from dataclasses import FrozenInstanceError

import pytest

from models.produto import Produto
from services.etiqueta_balanca import EtiquetaBalanca
from services.item_venda_service import criar_item_de_etiqueta
from services.produto_etiqueta import ProdutoEtiqueta


def criar_produto_etiqueta_de_teste() -> ProdutoEtiqueta:
    return ProdutoEtiqueta(
        etiqueta=EtiquetaBalanca(
            codigo_barras="2023400053672",
            codigo_produto="234",
            valor_centavos=5367,
        ),
        produto=Produto(
            id=42,
            codigo="234",
            nome="Picanha",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=7990,
            origem="COMPRADO",
        ),
    )


def test_criar_item_de_etiqueta_copia_valores_exatos() -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste()

    item = criar_item_de_etiqueta(produto_etiqueta)

    assert item.origem == "ETIQUETA"
    assert item.subtotal_centavos == 5367
    assert item.codigo_barras == "2023400053672"
    assert item.quantidade is None
    assert item.origem_quantidade == "NAO_INFORMADA"
    assert item.produto.produto_id == 42
    assert item.produto.codigo == "234"
    assert item.produto.nome == "Picanha"
    assert item.produto.forma_venda == "PESO"
    assert item.produto.preco_referencia_centavos == 7990


def test_item_criado_nao_mantem_referencia_mutavel_ao_produto() -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste()
    item = criar_item_de_etiqueta(produto_etiqueta)

    produto_etiqueta.produto.id = 99
    produto_etiqueta.produto.codigo = "999"
    produto_etiqueta.produto.nome = "Alcatra"
    produto_etiqueta.produto.forma_venda = "UNIDADE"
    produto_etiqueta.produto.preco_venda_centavos = 12345

    assert item.produto.produto_id == 42
    assert item.produto.codigo == "234"
    assert item.produto.nome == "Picanha"
    assert item.produto.forma_venda == "PESO"
    assert item.produto.preco_referencia_centavos == 7990


def test_criar_item_de_etiqueta_retorna_item_imutavel() -> None:
    item = criar_item_de_etiqueta(criar_produto_etiqueta_de_teste())

    with pytest.raises(FrozenInstanceError):
        item.subtotal_centavos = 100


def test_criar_item_de_etiqueta_nao_altera_objetos_de_entrada() -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste()
    produto_original = criar_produto_etiqueta_de_teste().produto
    etiqueta_original = criar_produto_etiqueta_de_teste().etiqueta

    criar_item_de_etiqueta(produto_etiqueta)

    assert produto_etiqueta.produto == produto_original
    assert produto_etiqueta.etiqueta == etiqueta_original
