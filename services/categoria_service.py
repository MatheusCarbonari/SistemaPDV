from database.conexao import CAMINHO_BANCO
from models.categoria import validar_nome_categoria
from models.sessao_usuario import SessaoUsuario
from repositories.categoria_repository import (
    alterar_situacao_categoria_repository,
    criar_categoria_repository,
    listar_categorias_repository,
    renomear_categoria_repository,
)
from services.autenticacao_service import autorizar_sessao


def listar_categorias(
    sessao_administrativa: SessaoUsuario,
    caminho_banco=CAMINHO_BANCO,
    *,
    ativo: bool | None = None,
):
    autorizar_sessao(
        sessao_administrativa,
        ("ADMINISTRADOR", "CAIXA"),
        caminho_banco,
    )
    if ativo is not None and not isinstance(ativo, bool):
        raise TypeError("A situação da categoria deve ser booleana.")
    return listar_categorias_repository(caminho_banco, ativo=ativo)


def criar_categoria(
    sessao_administrativa: SessaoUsuario,
    nome,
    caminho_banco=CAMINHO_BANCO,
):
    autorizar_sessao(sessao_administrativa, ("ADMINISTRADOR",), caminho_banco)
    nome_normalizado, chave, erros = validar_nome_categoria(nome)
    if erros:
        return None, list(erros)
    return criar_categoria_repository(
        nome_normalizado,
        chave,
        caminho_banco,
    ), []


def renomear_categoria(
    sessao_administrativa: SessaoUsuario,
    categoria_id,
    nome,
    caminho_banco=CAMINHO_BANCO,
):
    autorizar_sessao(sessao_administrativa, ("ADMINISTRADOR",), caminho_banco)
    _validar_categoria_id(categoria_id)
    nome_normalizado, chave, erros = validar_nome_categoria(nome)
    if erros:
        return None, list(erros)
    categoria = renomear_categoria_repository(
        categoria_id,
        nome_normalizado,
        chave,
        caminho_banco,
    )
    if categoria is None:
        raise LookupError("A categoria não foi encontrada.")
    return categoria, []


def alterar_situacao_categoria(
    sessao_administrativa: SessaoUsuario,
    categoria_id,
    ativo,
    caminho_banco=CAMINHO_BANCO,
):
    autorizar_sessao(sessao_administrativa, ("ADMINISTRADOR",), caminho_banco)
    _validar_categoria_id(categoria_id)
    if not isinstance(ativo, bool):
        raise TypeError("A situação da categoria deve ser booleana.")
    categoria = alterar_situacao_categoria_repository(
        categoria_id,
        ativo,
        caminho_banco,
    )
    if categoria is None:
        raise LookupError("A categoria não foi encontrada.")
    return categoria


def _validar_categoria_id(categoria_id) -> None:
    if not isinstance(categoria_id, int) or isinstance(categoria_id, bool):
        raise TypeError("O ID da categoria deve ser um inteiro.")
    if categoria_id <= 0:
        raise ValueError("O ID da categoria deve ser positivo.")
