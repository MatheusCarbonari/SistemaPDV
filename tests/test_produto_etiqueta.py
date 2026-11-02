from dataclasses import FrozenInstanceError

import pytest

from database.schema import criar_tabelas
from models.produto import Produto
from repositories.produto_repository import salvar_produto
from services.produto_etiqueta import associar_etiqueta_ao_produto
from services.produto_service import alterar_situacao_produto


def salvar_produto_de_teste(caminho_banco, codigo="234") -> Produto:
    return salvar_produto(
        Produto(
            codigo=codigo,
            nome="Picanha",
            categoria="BOVINOS",
            forma_venda="PESO",
            preco_venda_centavos=7990,
            origem="COMPRADO",
        ),
        caminho_banco,
    )


def test_associar_etiqueta_retorna_produto_ativo_e_preserva_etiqueta(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_produto_etiqueta.db"
    criar_tabelas(caminho_banco)
    produto_salvo = salvar_produto_de_teste(caminho_banco)

    associacao, erros = associar_etiqueta_ao_produto(
        "2023400053672",
        caminho_banco,
    )

    assert erros == []
    assert associacao is not None
    assert associacao.produto.id == produto_salvo.id
    assert associacao.produto.codigo == "234"
    assert associacao.etiqueta.codigo_barras == "2023400053672"
    assert associacao.etiqueta.valor_centavos == 5367


def test_associar_etiqueta_retorna_resultado_imutavel(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_etiqueta.db"
    criar_tabelas(caminho_banco)
    salvar_produto_de_teste(caminho_banco)

    associacao, erros = associar_etiqueta_ao_produto(
        "2023400053672",
        caminho_banco,
    )

    assert erros == []
    with pytest.raises(FrozenInstanceError):
        associacao.produto = None


def test_associar_etiqueta_rejeita_produto_inexistente(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_etiqueta.db"
    criar_tabelas(caminho_banco)

    associacao, erros = associar_etiqueta_ao_produto(
        "2023400053672",
        caminho_banco,
    )

    assert associacao is None
    assert erros == ["Produto não encontrado."]


def test_associar_etiqueta_rejeita_produto_inativo(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_etiqueta.db"
    criar_tabelas(caminho_banco)
    produto_salvo = salvar_produto_de_teste(caminho_banco)
    foi_atualizado, erros_situacao = alterar_situacao_produto(
        produto_salvo.id,
        False,
        caminho_banco,
    )

    associacao, erros = associar_etiqueta_ao_produto(
        "2023400053672",
        caminho_banco,
    )

    assert foi_atualizado is True
    assert erros_situacao == []
    assert associacao is None
    assert erros == ["O produto associado à etiqueta está inativo."]


def test_associar_etiqueta_rejeita_etiqueta_invalida(tmp_path) -> None:
    caminho_banco = tmp_path / "teste_produto_etiqueta.db"
    criar_tabelas(caminho_banco)
    salvar_produto_de_teste(caminho_banco)

    associacao, erros = associar_etiqueta_ao_produto(
        "2023400053673",
        caminho_banco,
    )

    assert associacao is None
    assert erros == ["O código informado não é um EAN-13 válido."]


def test_associar_etiqueta_nao_busca_variante_com_zeros_a_esquerda(
    tmp_path,
) -> None:
    caminho_banco = tmp_path / "teste_produto_etiqueta.db"
    criar_tabelas(caminho_banco)
    salvar_produto_de_teste(caminho_banco, codigo="0234")

    associacao, erros = associar_etiqueta_ao_produto(
        "2023400053672",
        caminho_banco,
    )

    assert associacao is None
    assert erros == ["Produto não encontrado."]
