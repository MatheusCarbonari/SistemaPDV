from services.produto_service import consultar_produto_por_codigo


def consultar_produto_interface():
    codigo = input("Digite o código do produto: ")

    produto, erros = consultar_produto_por_codigo(codigo)

    if erros:
        for erro in erros:
            print(erro)
        return

    print("Produto encontrado:")
    print(f"Código: {produto.codigo}")
    print(f"Nome: {produto.nome}")
    print(f"Categoria: {produto.categoria}")
    print(f"Forma de venda: {produto.forma_venda}")
    print(f"Preço: {formatar_preco(produto.preco_venda_centavos)}")
    print(f"Origem: {produto.origem}")


def formatar_preco(preco_centavos: int) -> str:
    valor = preco_centavos / 100
    return f"R$ {valor:.2f}".replace("." , ",")