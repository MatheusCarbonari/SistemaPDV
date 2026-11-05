from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
import time

from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from repositories.usuario_repository import (
    buscar_usuario_para_autenticacao,
    buscar_usuario_por_id,
)
from services.administrador_inicial_service import normalizar_identificacao
from services.senha_service import verificar_senha


MENSAGEM_CREDENCIAIS_INVALIDAS = "Identificação ou senha inválida."
# Hash scrypt v1 válido usado somente para igualar o custo de usuário inexistente.
HASH_SIMULADO = (
    "scrypt$v=1$n=16384,r=8,p=5,dklen=32$"
    "AAAAAAAAAAAAAAAAAAAAAA==$"
    "txD9r3RC1/S8WEr6Xfa4bR0FJqUyX9CBQGpIn+DVqec="
)


class CredenciaisInvalidasError(RuntimeError):
    pass


class TentativasLoginExcedidasError(RuntimeError):
    def __init__(self, segundos_restantes: int) -> None:
        self.segundos_restantes = max(1, segundos_restantes)
        super().__init__(
            "Muitas tentativas de acesso. Aguarde "
            f"{self.segundos_restantes} segundo(s) e tente novamente."
        )


class SessaoInvalidaError(PermissionError):
    pass


class PermissaoNegadaError(PermissionError):
    pass


@dataclass
class _EstadoTentativas:
    falhas: deque[float]
    bloqueado_ate: float = 0.0


class LimitadorTentativasLogin:
    """Limite temporário em memória; não cria bloqueio durável explorável."""

    def __init__(
        self,
        *,
        maximo_falhas: int = 5,
        janela_segundos: float = 60.0,
        espera_segundos: float = 30.0,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.maximo_falhas = maximo_falhas
        self.janela_segundos = janela_segundos
        self.espera_segundos = espera_segundos
        self._relogio = relogio
        self._estados: dict[str, _EstadoTentativas] = defaultdict(
            lambda: _EstadoTentativas(deque())
        )

    def verificar(self, chave: str) -> None:
        agora = self._relogio()
        estado = self._estados[chave]
        if estado.bloqueado_ate > agora:
            restante = int(estado.bloqueado_ate - agora) + 1
            raise TentativasLoginExcedidasError(restante)
        if estado.bloqueado_ate:
            self._estados.pop(chave, None)

    def registrar_falha(self, chave: str) -> None:
        agora = self._relogio()
        estado = self._estados[chave]
        limite = agora - self.janela_segundos
        while estado.falhas and estado.falhas[0] <= limite:
            estado.falhas.popleft()
        estado.falhas.append(agora)
        if len(estado.falhas) >= self.maximo_falhas:
            estado.bloqueado_ate = agora + self.espera_segundos

    def registrar_sucesso(self, chave: str) -> None:
        self._estados.pop(chave, None)


LIMITADOR_LOGIN_PADRAO = LimitadorTentativasLogin()


def autenticar_usuario(
    identificacao_acesso,
    senha,
    caminho_banco=CAMINHO_BANCO,
    *,
    limitador: LimitadorTentativasLogin | None = None,
) -> SessaoUsuario:
    limitador = limitador or LIMITADOR_LOGIN_PADRAO
    identificacao = normalizar_identificacao(identificacao_acesso)
    chave = identificacao or "<invalida>"
    limitador.verificar(chave)

    linha = buscar_usuario_para_autenticacao(identificacao, caminho_banco)
    hash_armazenado = linha["senha_hash"] if linha is not None else HASH_SIMULADO
    senha_textual = senha if isinstance(senha, str) else ""
    senha_confere = verificar_senha(senha_textual, hash_armazenado)
    conta_valida = linha is not None and linha["ativo"] == 1
    if not senha_confere or not conta_valida:
        limitador.registrar_falha(chave)
        raise CredenciaisInvalidasError(MENSAGEM_CREDENCIAIS_INVALIDAS)

    if linha["perfil"] not in ("ADMINISTRADOR", "CAIXA"):
        limitador.registrar_falha(chave)
        raise CredenciaisInvalidasError(MENSAGEM_CREDENCIAIS_INVALIDAS)

    limitador.registrar_sucesso(chave)
    return SessaoUsuario(
        usuario_id=linha["id"],
        identificacao_acesso=linha["identificacao_acesso"],
        perfil=linha["perfil"],
    )


def autorizar_sessao(
    sessao: SessaoUsuario,
    perfis_permitidos: Iterable[str],
    caminho_banco=CAMINHO_BANCO,
):
    if not isinstance(sessao, SessaoUsuario) or not sessao.autenticada:
        raise SessaoInvalidaError("A sessão não está autenticada.")

    usuario = buscar_usuario_por_id(sessao.usuario_id, caminho_banco)
    if (
        usuario is None
        or not usuario.ativo
        or usuario.identificacao_acesso != sessao.identificacao_acesso
        or usuario.perfil != sessao.perfil
    ):
        sessao.encerrar()
        raise SessaoInvalidaError(
            "A conta não está mais habilitada para esta sessão."
        )
    if usuario.perfil not in tuple(perfis_permitidos):
        raise PermissaoNegadaError("O perfil autenticado não possui permissão.")
    return usuario


def encerrar_sessao(sessao: SessaoUsuario) -> None:
    sessao.encerrar()
