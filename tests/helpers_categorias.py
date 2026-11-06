from models.categoria import normalizar_identidade_categoria
from repositories.categoria_repository import (
    alterar_situacao_categoria_repository,
    buscar_categoria_por_chave_repository,
    criar_categoria_repository,
)


def garantir_categoria_teste(caminho_banco, nome="BOVINOS", *, ativo=True):
    nome_normalizado, chave = normalizar_identidade_categoria(nome)
    categoria = buscar_categoria_por_chave_repository(chave, caminho_banco)
    if categoria is None:
        categoria = criar_categoria_repository(
            nome_normalizado,
            chave,
            caminho_banco,
        )
    if categoria.ativo != ativo:
        categoria = alterar_situacao_categoria_repository(
            categoria.id,
            ativo,
            caminho_banco,
        )
    return categoria
