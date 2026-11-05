from dataclasses import dataclass
import secrets
from threading import Lock
import time

from database.conexao import CAMINHO_BANCO
from models.autorizacao_pontual import CapacidadeAutorizacao
from models.sessao_usuario import SessaoUsuario
from services.autenticacao_service import (
    GERENCIADOR_SESSOES,
    LIMITADOR_LOGIN_PADRAO,
    CredenciaisInvalidasError,
    GerenciadorSessoes,
    LimitadorTentativasLogin,
    SessaoInvalidaError,
    autorizar_sessao,
    validar_credenciais_usuario,
)


OPERACAO_CANCELAR_VENDA = "CANCELAR_VENDA"
OPERACOES_SUPORTADAS = frozenset((OPERACAO_CANCELAR_VENDA,))


class AutorizacaoPontualInvalidaError(PermissionError):
    pass


class AutorizacaoPontualExpiradaError(AutorizacaoPontualInvalidaError):
    pass


class AutorizacaoPontualConsumidaError(AutorizacaoPontualInvalidaError):
    pass


@dataclass(frozen=True)
class _EstadoAutorizacao:
    capacidade: CapacidadeAutorizacao
    sessao_solicitante: SessaoUsuario
    operacao: str
    recurso_id: int
    identidade_administrador: str
    expira_em: float


class GerenciadorAutorizacoesPontuais:
    def __init__(
        self,
        *,
        gerenciador_sessoes: GerenciadorSessoes = GERENCIADOR_SESSOES,
        validade_segundos: float = 60.0,
        relogio=time.monotonic,
    ) -> None:
        if validade_segundos <= 0:
            raise ValueError("A validade da autorização deve ser positiva.")
        self.gerenciador_sessoes = gerenciador_sessoes
        self.validade_segundos = validade_segundos
        self._relogio = relogio
        self._autorizacoes: dict[str, _EstadoAutorizacao] = {}
        self._consumidas: set[str] = set()
        self._bloqueio = Lock()

    def emitir(
        self,
        sessao_solicitante: SessaoUsuario,
        operacao: str,
        recurso_id: int,
        identificacao_administrador,
        senha_administrador,
        caminho_banco=CAMINHO_BANCO,
        *,
        limitador: LimitadorTentativasLogin | None = None,
    ) -> CapacidadeAutorizacao:
        _validar_vinculo(operacao, recurso_id)
        autorizar_sessao(
            sessao_solicitante,
            ("ADMINISTRADOR", "CAIXA"),
            caminho_banco,
            gerenciador_sessoes=self.gerenciador_sessoes,
        )
        administrador = validar_credenciais_usuario(
            identificacao_administrador,
            senha_administrador,
            caminho_banco,
            limitador=limitador or LIMITADOR_LOGIN_PADRAO,
        )
        if administrador.perfil != "ADMINISTRADOR":
            raise CredenciaisInvalidasError(
                "Identificação ou senha administrativa inválida."
            )

        capacidade = CapacidadeAutorizacao(secrets.token_urlsafe(32))
        estado = _EstadoAutorizacao(
            capacidade=capacidade,
            sessao_solicitante=sessao_solicitante,
            operacao=operacao,
            recurso_id=recurso_id,
            identidade_administrador=administrador.identificacao_acesso,
            expira_em=self._relogio() + self.validade_segundos,
        )
        with self._bloqueio:
            self._autorizacoes[capacidade.identificador] = estado
        return capacidade

    def consumir(
        self,
        capacidade: CapacidadeAutorizacao,
        sessao_solicitante: SessaoUsuario,
        operacao: str,
        recurso_id: int,
        caminho_banco=CAMINHO_BANCO,
    ) -> str:
        if not isinstance(capacidade, CapacidadeAutorizacao):
            raise AutorizacaoPontualInvalidaError(
                "A operação exige uma capacidade de autorização válida."
            )

        with self._bloqueio:
            identificador = capacidade.identificador
            estado = self._autorizacoes.pop(identificador, None)
            if estado is None:
                if identificador in self._consumidas:
                    raise AutorizacaoPontualConsumidaError(
                        "A autorização pontual já foi consumida."
                    )
                raise AutorizacaoPontualInvalidaError(
                    "A capacidade não foi emitida pelo gerenciador confiável."
                )
            self._consumidas.add(identificador)

            if self._relogio() >= estado.expira_em:
                raise AutorizacaoPontualExpiradaError(
                    "A autorização pontual expirou."
                )
            if estado.sessao_solicitante is not sessao_solicitante:
                raise AutorizacaoPontualInvalidaError(
                    "A autorização pertence a outra sessão."
                )
            if estado.operacao != operacao or estado.recurso_id != recurso_id:
                raise AutorizacaoPontualInvalidaError(
                    "A autorização não corresponde à operação solicitada."
                )
            identidade_administrador = estado.identidade_administrador

        try:
            autorizar_sessao(
                sessao_solicitante,
                ("ADMINISTRADOR", "CAIXA"),
                caminho_banco,
                gerenciador_sessoes=self.gerenciador_sessoes,
            )
        except SessaoInvalidaError as erro:
            raise AutorizacaoPontualInvalidaError(
                "A sessão solicitante não está mais válida."
            ) from erro
        return identidade_administrador


def _validar_vinculo(operacao: str, recurso_id: int) -> None:
    if operacao not in OPERACOES_SUPORTADAS:
        raise ValueError("O tipo de operação crítica é inválido.")
    if not isinstance(recurso_id, int) or isinstance(recurso_id, bool):
        raise TypeError("O ID do recurso deve ser um inteiro.")
    if recurso_id <= 0:
        raise ValueError("O ID do recurso deve ser positivo.")


GERENCIADOR_AUTORIZACOES = GerenciadorAutorizacoesPontuais()
