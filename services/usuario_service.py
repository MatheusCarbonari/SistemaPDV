from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import criar_usuario_caixa_repository
from services.administrador_inicial_service import (
    normalizar_identificacao,
    validar_identificacao,
    validar_senha,
)
from services.autenticacao_service import autorizar_sessao
from services.senha_service import gerar_hash_senha


def criar_conta_caixa(
    sessao_administrativa: SessaoUsuario,
    identificacao_acesso,
    senha,
    confirmacao_senha,
    caminho_banco=CAMINHO_BANCO,
):
    autorizar_sessao(
        sessao_administrativa,
        ("ADMINISTRADOR",),
        caminho_banco,
    )
    identificacao = normalizar_identificacao(identificacao_acesso)
    erros = validar_identificacao(identificacao)
    erros.extend(validar_senha(senha))
    if senha != confirmacao_senha:
        erros.append("A confirmação da senha não confere.")
    if erros:
        return None, erros

    usuario = criar_usuario_caixa_repository(
        identificacao,
        gerar_hash_senha(senha),
        caminho_banco,
    )
    return usuario, []
