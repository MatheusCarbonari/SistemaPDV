from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from models.usuario import Usuario
from repositories.usuario_repository import (
    alterar_situacao_usuario_caixa_repository,
    criar_usuario_caixa_repository,
    listar_usuarios_caixa_repository,
)
from services.administrador_inicial_service import (
    normalizar_identificacao,
    validar_identificacao,
    validar_senha,
)
from services.autenticacao_service import (
    GERENCIADOR_SESSOES,
    GerenciadorSessoes,
    autorizar_sessao,
)
from services.autorizacao_pontual_service import (
    GERENCIADOR_AUTORIZACOES,
    GerenciadorAutorizacoesPontuais,
)
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


def listar_contas_caixa(
    sessao_administrativa: SessaoUsuario,
    caminho_banco=CAMINHO_BANCO,
) -> tuple[Usuario, ...]:
    autorizar_sessao(
        sessao_administrativa,
        ("ADMINISTRADOR",),
        caminho_banco,
    )
    return listar_usuarios_caixa_repository(caminho_banco)


def alterar_situacao_conta_caixa(
    sessao_administrativa: SessaoUsuario,
    usuario_id,
    ativo,
    caminho_banco=CAMINHO_BANCO,
    *,
    gerenciador_sessoes: GerenciadorSessoes = GERENCIADOR_SESSOES,
    gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
        GERENCIADOR_AUTORIZACOES
    ),
):
    autorizar_sessao(
        sessao_administrativa,
        ("ADMINISTRADOR",),
        caminho_banco,
    )
    if not isinstance(usuario_id, int) or isinstance(usuario_id, bool):
        raise TypeError("O ID do operador deve ser um inteiro.")
    if usuario_id <= 0:
        raise ValueError("O ID do operador deve ser positivo.")
    if not isinstance(ativo, bool):
        raise TypeError("A situação do operador deve ser booleana.")

    usuario = alterar_situacao_usuario_caixa_repository(
        usuario_id,
        ativo,
        caminho_banco,
    )
    if usuario is None:
        raise LookupError("A conta Caixa não foi encontrada.")
    if not ativo:
        gerenciador_autorizacoes.invalidar_usuario(usuario.id)
        gerenciador_sessoes.invalidar_usuario(usuario.id)
    return usuario
