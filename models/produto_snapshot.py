from dataclasses import dataclass

from models.produto import Produto


@dataclass(frozen=True)
class ProdutoSnapshot:
    produto_id: int | None
    codigo: str
    nome: str
    forma_venda: str
    preco_referencia_centavos: int


def criar_snapshot_produto(produto: Produto) -> ProdutoSnapshot:
    """Copia os dados comerciais atuais do produto para um valor imutável."""
    return ProdutoSnapshot(
        produto_id=produto.id,
        codigo=produto.codigo,
        nome=produto.nome,
        forma_venda=produto.forma_venda,
        preco_referencia_centavos=produto.preco_venda_centavos,
    )
