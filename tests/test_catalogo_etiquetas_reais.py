import pytest

from services.ean13 import validar_ean13
from services.etiqueta_balanca import EtiquetaBalanca, interpretar_etiqueta


# Amostras fornecidas como etiquetas reais no T07. A forma de venda não está
# documentada na origem e, por isso, não é inferida neste catálogo.
@pytest.mark.parametrize(
    ("codigo", "codigo_produto", "valor_centavos"),
    [
        pytest.param("2023400053672", "234", 5367, id="produto-0234"),
        pytest.param("2001100137083", "11", 13708, id="produto-0011"),
        pytest.param("2014700015903", "147", 1590, id="produto-0147"),
    ],
)
def test_catalogo_de_etiquetas_reais(
    codigo: str,
    codigo_produto: str,
    valor_centavos: int,
) -> None:
    assert validar_ean13(codigo) is True
    assert interpretar_etiqueta(codigo) == EtiquetaBalanca(
        codigo_barras=codigo,
        codigo_produto=codigo_produto,
        valor_centavos=valor_centavos,
    )
