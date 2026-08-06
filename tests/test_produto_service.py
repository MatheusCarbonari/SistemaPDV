from services.produto_service import criar_produto

def test_criar_produto() -> None:

    resultado = criar_produto(
        codigo=" 101 ",
        nome=" picanha ",
        categoria=" bovinos ",
        forma_venda=" peso ",
        preco_venda_centavos=7990,
        origem=" comprado "
    )

    assert resultado.codigo == "101"
    assert resultado.nome == "Picanha"
    assert resultado.categoria == "BOVINOS"
    assert resultado.forma_venda == "PESO"
    assert resultado.preco_venda_centavos == 7990
    assert resultado.origem == "COMPRADO"
