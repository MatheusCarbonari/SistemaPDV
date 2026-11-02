from dataclasses import FrozenInstanceError

import pytest

from models.produto import Produto
from models.produto_snapshot import ProdutoSnapshot, criar_snapshot_produto


def criar_produto_de_teste(produto_id=42) -> Produto:
    return Produto(
        id=produto_id,
        codigo="234",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )


def test_criar_snapshot_produto_copia_dados_comerciais() -> None:
    produto = criar_produto_de_teste()

    snapshot = criar_snapshot_produto(produto)

    assert snapshot == ProdutoSnapshot(
        produto_id=42,
        codigo="234",
        nome="Picanha",
        forma_venda="PESO",
        preco_referencia_centavos=7990,
    )


def test_snapshot_permanece_independente_apos_mutacao_do_produto() -> None:
    produto = criar_produto_de_teste()
    snapshot = criar_snapshot_produto(produto)

    produto.id = 99
    produto.codigo = "999"
    produto.nome = "Alcatra"
    produto.forma_venda = "UNIDADE"
    produto.preco_venda_centavos = 12345

    assert snapshot == ProdutoSnapshot(
        produto_id=42,
        codigo="234",
        nome="Picanha",
        forma_venda="PESO",
        preco_referencia_centavos=7990,
    )


def test_snapshot_produto_e_imutavel() -> None:
    snapshot = criar_snapshot_produto(criar_produto_de_teste())

    with pytest.raises(FrozenInstanceError):
        snapshot.preco_referencia_centavos = 100


def test_criar_snapshot_produto_preserva_id_ausente() -> None:
    produto = criar_produto_de_teste(produto_id=None)

    snapshot = criar_snapshot_produto(produto)

    assert snapshot.produto_id is None


def test_criar_snapshot_produto_nao_altera_objeto_original() -> None:
    produto = criar_produto_de_teste()
    produto_original = criar_produto_de_teste()

    criar_snapshot_produto(produto)

    assert produto == produto_original
