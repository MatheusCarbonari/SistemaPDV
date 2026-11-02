from dataclasses import dataclass

from database.conexao import CAMINHO_BANCO
from models.produto import Produto
from services.etiqueta_balanca import EtiquetaBalanca, interpretar_etiqueta
from services.produto_service import consultar_produto_por_codigo


@dataclass(frozen=True)
class ProdutoEtiqueta:
    etiqueta: EtiquetaBalanca
    produto: Produto


def associar_etiqueta_ao_produto(
    codigo_barras: object,
    caminho_banco=CAMINHO_BANCO,
) -> tuple[ProdutoEtiqueta | None, list[str]]:
    """Associa a etiqueta ao código normalizado, sem tentar variantes com zeros."""
    try:
        etiqueta = interpretar_etiqueta(codigo_barras)
    except ValueError as erro:
        return None, [str(erro)]

    produto, erros = consultar_produto_por_codigo(
        etiqueta.codigo_produto,
        caminho_banco,
    )

    if erros:
        return None, erros

    if not produto.ativo:
        return None, ["O produto associado à etiqueta está inativo."]

    return ProdutoEtiqueta(etiqueta=etiqueta, produto=produto), []
