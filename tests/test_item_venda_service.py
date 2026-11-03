from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from models.produto import Produto
from services.etiqueta_balanca import EtiquetaBalanca
from services.item_venda_service import (
    criar_item_de_etiqueta,
    criar_item_de_etiqueta_com_estimativa,
    criar_item_manual_unidade,
)
from services.produto_etiqueta import ProdutoEtiqueta


def criar_produto_etiqueta_de_teste(
    forma_venda="PESO",
    preco_venda_centavos=7990,
    valor_centavos=5367,
    codigo_barras="2023400053672",
) -> ProdutoEtiqueta:
    return ProdutoEtiqueta(
        etiqueta=EtiquetaBalanca(
            codigo_barras=codigo_barras,
            codigo_produto="234",
            valor_centavos=valor_centavos,
        ),
        produto=Produto(
            id=42,
            codigo="234",
            nome="Picanha",
            categoria="BOVINOS",
            forma_venda=forma_venda,
            preco_venda_centavos=preco_venda_centavos,
            origem="COMPRADO",
        ),
    )


def criar_produto_unidade_de_teste(
    preco_venda_centavos=1500,
    forma_venda="UNIDADE",
    ativo=True,
) -> Produto:
    return Produto(
        id=42,
        codigo="11",
        nome="Espetinho",
        categoria="ESPETINHOS",
        forma_venda=forma_venda,
        preco_venda_centavos=preco_venda_centavos,
        origem="PRODUZIDO",
        ativo=ativo,
    )


@pytest.mark.parametrize(
    ("quantidade", "subtotal_esperado"),
    [
        (Decimal("2"), 3000),
        (Decimal("2.000"), 3000),
        (Decimal("2.333"), 3500),
    ],
)
def test_criar_item_manual_unidade_com_quantidade_valida(
    quantidade,
    subtotal_esperado,
) -> None:
    produto = criar_produto_unidade_de_teste()

    item = criar_item_manual_unidade(produto, quantidade)

    assert item.origem == "MANUAL"
    assert item.origem_quantidade == "INFORMADA"
    assert item.quantidade is quantidade
    assert item.subtotal_centavos == subtotal_esperado
    assert item.codigo_barras is None
    assert item.produto.produto_id == 42
    assert item.produto.codigo == "11"
    assert item.produto.nome == "Espetinho"
    assert item.produto.forma_venda == "UNIDADE"
    assert item.produto.preco_referencia_centavos == 1500


@pytest.mark.parametrize(
    ("quantidade", "subtotal_esperado"),
    [
        (Decimal("1.499"), 1),
        (Decimal("1.500"), 2),
    ],
)
def test_criar_item_manual_unidade_arredonda_fracao_de_centavo_com_half_up(
    quantidade,
    subtotal_esperado,
) -> None:
    produto = criar_produto_unidade_de_teste(preco_venda_centavos=1)

    item = criar_item_manual_unidade(produto, quantidade)

    assert item.subtotal_centavos == subtotal_esperado


@pytest.mark.parametrize(
    "quantidade",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_criar_item_manual_unidade_rejeita_quantidade_fora_do_dominio(
    quantidade,
) -> None:
    with pytest.raises(ValueError, match="positiva e finita"):
        criar_item_manual_unidade(criar_produto_unidade_de_teste(), quantidade)


@pytest.mark.parametrize(
    "quantidade",
    [Decimal("0.0001"), Decimal("1.0000"), Decimal("2.3330")],
)
def test_criar_item_manual_unidade_rejeita_mais_de_tres_casas_decimais(
    quantidade,
) -> None:
    with pytest.raises(ValueError, match="no máximo três casas decimais"):
        criar_item_manual_unidade(criar_produto_unidade_de_teste(), quantidade)


@pytest.mark.parametrize("quantidade", [2, 2.0, "2", True, None])
def test_criar_item_manual_unidade_rejeita_quantidade_que_nao_e_decimal(
    quantidade,
) -> None:
    with pytest.raises(TypeError, match="informada como Decimal"):
        criar_item_manual_unidade(criar_produto_unidade_de_teste(), quantidade)


@pytest.mark.parametrize("produto_invalido", [None, "produto", 1, object()])
def test_criar_item_manual_unidade_rejeita_produto_invalido(
    produto_invalido,
) -> None:
    with pytest.raises(TypeError, match="instância de Produto"):
        criar_item_manual_unidade(produto_invalido, Decimal("1"))


def test_criar_item_manual_unidade_rejeita_produto_vendido_por_peso() -> None:
    produto = criar_produto_unidade_de_teste(forma_venda="PESO")

    with pytest.raises(ValueError, match="forma de venda UNIDADE"):
        criar_item_manual_unidade(produto, Decimal("1"))


def test_criar_item_manual_unidade_rejeita_produto_inativo() -> None:
    produto = criar_produto_unidade_de_teste(ativo=False)

    with pytest.raises(ValueError, match="produto deve estar ativo"):
        criar_item_manual_unidade(produto, Decimal("1"))


@pytest.mark.parametrize("preco_venda_centavos", [0, -1])
def test_criar_item_manual_unidade_rejeita_preco_nao_positivo(
    preco_venda_centavos,
) -> None:
    produto = criar_produto_unidade_de_teste(
        preco_venda_centavos=preco_venda_centavos,
    )

    with pytest.raises(
        ValueError,
        match="preço unitário deve ser maior que zero",
    ):
        criar_item_manual_unidade(produto, Decimal("1"))


@pytest.mark.parametrize("preco_venda_centavos", [True, 15.0, Decimal("15")])
def test_criar_item_manual_unidade_rejeita_tipo_de_preco_invalido(
    preco_venda_centavos,
) -> None:
    produto = criar_produto_unidade_de_teste(
        preco_venda_centavos=preco_venda_centavos,
    )

    with pytest.raises(TypeError, match="número inteiro em centavos"):
        criar_item_manual_unidade(produto, Decimal("1"))


def test_item_manual_unidade_possui_snapshot_independente_e_e_imutavel() -> None:
    produto = criar_produto_unidade_de_teste()
    produto_original = criar_produto_unidade_de_teste()
    item = criar_item_manual_unidade(produto, Decimal("2.000"))

    assert produto == produto_original

    produto.id = 99
    produto.codigo = "999"
    produto.nome = "Outro produto"
    produto.forma_venda = "PESO"
    produto.preco_venda_centavos = 9999
    produto.ativo = False

    assert item.produto.produto_id == 42
    assert item.produto.codigo == "11"
    assert item.produto.nome == "Espetinho"
    assert item.produto.forma_venda == "UNIDADE"
    assert item.produto.preco_referencia_centavos == 1500

    with pytest.raises(FrozenInstanceError):
        item.subtotal_centavos = 1

    with pytest.raises(FrozenInstanceError):
        item.produto.preco_referencia_centavos = 1


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


def test_criar_item_de_etiqueta_com_estimativa_para_peso() -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste(
        preco_venda_centavos=5990,
    )

    item = criar_item_de_etiqueta_com_estimativa(produto_etiqueta)

    assert item.quantidade == Decimal("0.896")
    assert item.origem_quantidade == "ESTIMADA"


def test_criar_item_de_etiqueta_com_estimativa_para_unidade() -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste(
        forma_venda="UNIDADE",
        preco_venda_centavos=3000,
        valor_centavos=7000,
        codigo_barras="2023400070006",
    )

    item = criar_item_de_etiqueta_com_estimativa(produto_etiqueta)

    assert item.quantidade == Decimal("2")
    assert isinstance(item.quantidade, Decimal)
    assert item.origem_quantidade == "ESTIMADA"


@pytest.mark.parametrize(
    ("preco_venda_centavos", "valor_centavos", "codigo_barras"),
    [
        (0, 5367, "2023400053672"),
        (5990, 0, "2023400000003"),
        (3000, 1, "2023400000010"),
    ],
)
def test_criar_item_de_etiqueta_sem_estimativa_quando_indisponivel(
    preco_venda_centavos,
    valor_centavos,
    codigo_barras,
) -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste(
        preco_venda_centavos=preco_venda_centavos,
        valor_centavos=valor_centavos,
        codigo_barras=codigo_barras,
    )

    item = criar_item_de_etiqueta_com_estimativa(produto_etiqueta)

    assert item.quantidade is None
    assert item.origem_quantidade == "NAO_INFORMADA"


def test_criar_item_de_etiqueta_com_estimativa_rejeita_forma_desconhecida() -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste(
        forma_venda="OUTRA",
    )

    with pytest.raises(
        ValueError,
        match="A forma de venda deve ser PESO ou UNIDADE.",
    ):
        criar_item_de_etiqueta_com_estimativa(produto_etiqueta)


def test_item_com_estimativa_preserva_dados_e_snapshot_independente() -> None:
    produto_etiqueta = criar_produto_etiqueta_de_teste(
        preco_venda_centavos=5990,
    )

    item = criar_item_de_etiqueta_com_estimativa(produto_etiqueta)
    produto_etiqueta.produto.nome = "Alcatra"
    produto_etiqueta.produto.preco_venda_centavos = 12345

    assert item.origem == "ETIQUETA"
    assert item.subtotal_centavos == 5367
    assert item.codigo_barras == "2023400053672"
    assert item.produto.nome == "Picanha"
    assert item.produto.preco_referencia_centavos == 5990
