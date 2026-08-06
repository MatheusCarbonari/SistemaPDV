from models.produto import Produto


def test_criar_produto_com_dados_validos() -> None:
    produto = Produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINO",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto.codigo == "101"
    assert produto.nome == "Picanha"
    assert produto.categoria == "BOVINO"
    assert produto.forma_venda == "PESO"
    assert produto.preco_venda_centavos == 7990
    assert produto.origem == "COMPRADO"
    assert produto.ativo is True
    assert produto.id is None
    assert produto.criado_em is None
    assert produto.atualizado_em is None