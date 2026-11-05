import re
import unicodedata

from database.conexao import CAMINHO_BANCO
from models.usuario import Usuario
from repositories.usuario_repository import (
    criar_administrador_inicial_repository,
    consultar_estado_identidade,
)
from services.senha_service import gerar_hash_senha


TAMANHO_MINIMO_SENHA = 12
TAMANHO_MAXIMO_SENHA = 128
PADRAO_IDENTIFICACAO = re.compile(r"^[a-z0-9._-]+$")


def criar_administrador_inicial(
    identificacao_acesso,
    senha,
    confirmacao_senha,
    caminho_banco=CAMINHO_BANCO,
) -> tuple[Usuario | None, list[str]]:
    identificacao = normalizar_identificacao(identificacao_acesso)
    erros = validar_identificacao(identificacao)
    erros.extend(validar_senha(senha))
    if senha != confirmacao_senha:
        erros.append("A confirmação da senha não confere.")
    if erros:
        return None, erros

    senha_hash = gerar_hash_senha(senha)
    usuario = criar_administrador_inicial_repository(
        identificacao,
        senha_hash,
        caminho_banco,
    )
    return usuario, []


def obter_estado_primeiro_acesso(caminho_banco=CAMINHO_BANCO) -> str:
    return consultar_estado_identidade(caminho_banco)


def normalizar_identificacao(valor) -> str:
    if not isinstance(valor, str):
        return ""
    return unicodedata.normalize("NFKC", valor).strip().lower()


def validar_identificacao(identificacao: str) -> list[str]:
    if not identificacao:
        return ["A identificação de acesso é obrigatória."]
    if not 3 <= len(identificacao) <= 64:
        return ["A identificação deve possuir entre 3 e 64 caracteres."]
    if PADRAO_IDENTIFICACAO.fullmatch(identificacao) is None:
        return [
            "A identificação permite apenas letras minúsculas, números, "
            "ponto, hífen e sublinhado."
        ]
    return []


def validar_senha(senha) -> list[str]:
    if not isinstance(senha, str):
        return ["A senha é obrigatória."]
    if len(senha) < TAMANHO_MINIMO_SENHA:
        return [
            f"A senha deve possuir ao menos {TAMANHO_MINIMO_SENHA} caracteres."
        ]
    if len(senha) > TAMANHO_MAXIMO_SENHA:
        return [
            f"A senha deve possuir no máximo {TAMANHO_MAXIMO_SENHA} caracteres."
        ]
    if not senha.strip():
        return ["A senha não pode conter somente espaços."]
    return []
