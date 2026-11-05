import hashlib
import secrets
import unicodedata
import uuid

from database.conexao import CAMINHO_BANCO
from models.codigos_recuperacao import ConjuntoCodigosRecuperacao
from models.sessao_usuario import SessaoUsuario
from repositories.recuperacao_acesso_repository import (
    consumir_codigo_e_atualizar_senha,
    rotacionar_codigos_recuperacao,
)
from services.administrador_inicial_service import (
    normalizar_identificacao,
    validar_senha,
)
from services.autenticacao_service import (
    GERENCIADOR_SESSOES,
    CredenciaisInvalidasError,
    GerenciadorSessoes,
    LimitadorTentativasLogin,
    autorizar_sessao,
    validar_credenciais_usuario,
)
from services.autorizacao_pontual_service import (
    GERENCIADOR_AUTORIZACOES,
    GerenciadorAutorizacoesPontuais,
)
from services.senha_service import gerar_hash_senha


QUANTIDADE_CODIGOS = 10
CARACTERES_POR_CODIGO = 32
TAMANHO_GRUPO = 8
ALFABETO_CODIGO = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
MENSAGEM_RECUPERACAO_INVALIDA = (
    "Não foi possível validar os dados de recuperação."
)


class RecuperacaoAcessoInvalidaError(PermissionError):
    pass


class NovaSenhaInvalidaError(ValueError):
    def __init__(self, erros: list[str]) -> None:
        self.erros = tuple(erros)
        super().__init__("\n".join(erros))


LIMITADOR_RECUPERACAO_PADRAO = LimitadorTentativasLogin(
    maximo_falhas=5,
    janela_segundos=300.0,
    espera_segundos=60.0,
)


def emitir_ou_rotacionar_codigos(
    sessao_administrativa: SessaoUsuario,
    senha_atual,
    caminho_banco=CAMINHO_BANCO,
    *,
    gerenciador_sessoes: GerenciadorSessoes = GERENCIADOR_SESSOES,
    limitador: LimitadorTentativasLogin | None = None,
) -> ConjuntoCodigosRecuperacao:
    administrador = autorizar_sessao(
        sessao_administrativa,
        ("ADMINISTRADOR",),
        caminho_banco,
        gerenciador_sessoes=gerenciador_sessoes,
    )
    confirmado = validar_credenciais_usuario(
        administrador.identificacao_acesso,
        senha_atual,
        caminho_banco,
        limitador=limitador,
    )
    if confirmado.id != administrador.id or confirmado.perfil != "ADMINISTRADOR":
        raise CredenciaisInvalidasError(
            "Identificação ou senha administrativa inválida."
        )

    codigos = _gerar_codigos()
    verificadores = tuple(_calcular_verificador(codigo) for codigo in codigos)
    rotacionar_codigos_recuperacao(
        administrador.id,
        str(uuid.uuid4()),
        verificadores,
        caminho_banco,
    )
    return ConjuntoCodigosRecuperacao(codigos)


def recuperar_acesso_administrativo(
    identificacao_acesso,
    codigo,
    nova_senha,
    confirmacao_senha,
    caminho_banco=CAMINHO_BANCO,
    *,
    limitador: LimitadorTentativasLogin | None = None,
    gerenciador_sessoes: GerenciadorSessoes = GERENCIADOR_SESSOES,
    gerenciador_autorizacoes: GerenciadorAutorizacoesPontuais = (
        GERENCIADOR_AUTORIZACOES
    ),
) -> None:
    identificacao = normalizar_identificacao(identificacao_acesso)
    chave_limite = identificacao or "<invalida>"
    limitador = limitador or LIMITADOR_RECUPERACAO_PADRAO
    limitador.verificar(chave_limite)

    erros = validar_senha(nova_senha)
    if nova_senha != confirmacao_senha:
        erros.append("A confirmação da senha não confere.")
    if erros:
        raise NovaSenhaInvalidaError(erros)

    codigo_normalizado = _normalizar_codigo(codigo)
    verificador = _calcular_verificador(codigo_normalizado)
    nova_senha_hash = gerar_hash_senha(nova_senha)
    usuario_id = consumir_codigo_e_atualizar_senha(
        identificacao,
        verificador,
        nova_senha_hash,
        caminho_banco,
    )
    if usuario_id is None:
        limitador.registrar_falha(chave_limite)
        raise RecuperacaoAcessoInvalidaError(MENSAGEM_RECUPERACAO_INVALIDA)

    limitador.registrar_sucesso(chave_limite)
    gerenciador_autorizacoes.invalidar_usuario(usuario_id)
    gerenciador_sessoes.invalidar_usuario(usuario_id)


def _gerar_codigos() -> tuple[str, ...]:
    codigos: set[str] = set()
    while len(codigos) < QUANTIDADE_CODIGOS:
        bruto = "".join(
            secrets.choice(ALFABETO_CODIGO)
            for _ in range(CARACTERES_POR_CODIGO)
        )
        codigos.add(
            "-".join(
                bruto[inicio : inicio + TAMANHO_GRUPO]
                for inicio in range(0, CARACTERES_POR_CODIGO, TAMANHO_GRUPO)
            )
        )
    return tuple(codigos)


def _normalizar_codigo(codigo) -> str:
    if not isinstance(codigo, str):
        return ""
    normalizado = unicodedata.normalize("NFKC", codigo).upper()
    return "".join(caractere for caractere in normalizado if caractere not in "- ")


def _calcular_verificador(codigo) -> str:
    normalizado = _normalizar_codigo(codigo)
    return hashlib.sha256(normalizado.encode("ascii", errors="ignore")).hexdigest()
