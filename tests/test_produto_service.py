from services.produto_service import criar_produto


# Cenário válido e normalização dos dados.
def test_criar_produto() -> None:

    produto, erros = criar_produto(
        codigo=" 101 ",
        nome=" picanha ",
        categoria=" bovinos ",
        forma_venda=" peso ",
        preco_venda_centavos=7990,
        origem=" comprado "
    )

    assert erros == []
    assert produto.codigo == "101"
    assert produto.nome == "Picanha"
    assert produto.categoria == "BOVINOS"
    assert produto.forma_venda == "PESO"
    assert produto.preco_venda_centavos == 7990
    assert produto.origem == "COMPRADO"


# Validações do código.
def test_criar_produto_com_codigo_vazio() -> None:
    produto, erros = criar_produto(
        codigo="",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O código é obrigatório." in erros


def test_criar_produto_com_codigo_nao_numerico() -> None:
    produto, erros = criar_produto(
        codigo="ABC",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O código deve conter apenas números." in erros


# Validações do nome.
def test_criar_produto_com_nome_vazio() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O nome é obrigatório." in erros


# Confirma que a limpeza transforma espaços em código vazio.
def test_criar_produto_com_codigo_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="   ",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O código é obrigatório." in erros


# Validações adicionais do nome após a limpeza.
def test_criar_produto_com_nome_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="   ",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O nome é obrigatório." in erros


def test_criar_produto_com_nome_apenas_numeros() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="123",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O nome não pode conter apenas números." in erros


# Validações da categoria.
def test_criar_produto_com_categoria_vazia() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A categoria é obrigatória." in erros


def test_criar_produto_com_categoria_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="   ",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A categoria é obrigatória." in erros


def test_criar_produto_com_categoria_apenas_numeros() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="123",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A categoria não pode conter apenas números." in erros


# Validações da forma de venda.
def test_criar_produto_com_forma_venda_vazia() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A forma de venda é obrigatória." in erros


def test_criar_produto_com_forma_venda_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="   ",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A forma de venda é obrigatória." in erros


def test_criar_produto_com_forma_venda_contendo_numero() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO2",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "A forma de venda não permite números." in erros


def test_criar_produto_com_forma_venda_invalida() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="CAIXA",
        preco_venda_centavos=7990,
        origem="COMPRADO",
    )

    assert produto is None
    assert "Forma de venda permite apenas 'PESO' e 'UNIDADE'." in erros


# Validações do preço em centavos.
def test_criar_produto_com_preco_none() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=None,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda é obrigatório." in erros


def test_criar_produto_com_preco_texto() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos="7990",
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser um número inteiro em centavos." in erros


def test_criar_produto_com_preco_decimal() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=79.90,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser um número inteiro em centavos." in erros


def test_criar_produto_com_preco_zero() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=0,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser maior que zero." in erros


def test_criar_produto_com_preco_negativo() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=-100,
        origem="COMPRADO",
    )

    assert produto is None
    assert "O preço de venda deve ser maior que zero." in erros


# Validações da origem do produto.
def test_criar_produto_com_origem_vazia() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="",
    )

    assert produto is None
    assert "A origem do produto é obrigatória." in erros


def test_criar_produto_com_origem_apenas_espacos() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="   ",
    )

    assert produto is None
    assert "A origem do produto é obrigatória." in erros


def test_criar_produto_com_origem_contendo_numero() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="COMPRADO2",
    )

    assert produto is None
    assert "A origem do produto não permite números." in erros


def test_criar_produto_com_origem_invalida() -> None:
    produto, erros = criar_produto(
        codigo="101",
        nome="Picanha",
        categoria="BOVINOS",
        forma_venda="PESO",
        preco_venda_centavos=7990,
        origem="IMPORTADO",
    )

    assert produto is None
    assert "A origem do produto permite apenas 'COMPRADO' e 'PRODUZIDO'." in erros
