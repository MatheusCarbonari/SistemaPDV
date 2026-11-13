"""Estado processual para degradação controlada do PDV."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import os
import sqlite3
from threading import RLock

from services.catalogo_memoria_service import (
    CATALOGO_DISPONIVEL,
    CatalogoBancoDivergenteError,
    CatalogoProdutosMemoria,
)


class ModoOperacional(str, Enum):
    NORMAL = "NORMAL"
    CALCULO_DEGRADADO = "CALCULO_DEGRADADO"
    INDISPONIVEL = "INDISPONIVEL"


class OperacaoProibidaNoModoAtualError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EstadoOperacional:
    modo: ModoOperacional
    motivo: str | None = None


class ControladorEstadoOperacional:
    """Mantém uma transição conservadora, sem retorno automático."""

    def __init__(self) -> None:
        self._bloqueio = RLock()
        self._estado = EstadoOperacional(ModoOperacional.NORMAL)
        self._catalogo_degradado: CatalogoProdutosMemoria | None = None

    def obter_estado(self) -> EstadoOperacional:
        with self._bloqueio:
            self._revalidar_catalogo_sem_bloquear()
            return self._estado

    def tentar_ativar_calculo_degradado(
        self,
        erro: BaseException,
        catalogo: CatalogoProdutosMemoria,
        caminho_banco: str | Path,
    ) -> bool:
        """Ativa somente diante de falha SQLite de acesso e snapshot confiável."""
        if not falha_sqlite_permite_degradacao(erro):
            return False
        if not isinstance(catalogo, CatalogoProdutosMemoria):
            raise TypeError("O catálogo em memória informado é inválido.")

        with self._bloqueio:
            self._revalidar_catalogo_sem_bloquear()
            if self._estado.modo is ModoOperacional.CALCULO_DEGRADADO:
                return True
            if self._estado.modo is ModoOperacional.INDISPONIVEL:
                return False
            try:
                catalogo.vincular_ou_validar_banco(caminho_banco)
            except CatalogoBancoDivergenteError:
                self._estado = EstadoOperacional(
                    ModoOperacional.INDISPONIVEL,
                    "ORIGEM_CATALOGO_DIVERGENTE",
                )
                return False
            if catalogo.obter_estado().status != CATALOGO_DISPONIVEL:
                self._estado = EstadoOperacional(
                    ModoOperacional.INDISPONIVEL,
                    "CATALOGO_INDISPONIVEL",
                )
                return False
            self._estado = EstadoOperacional(
                ModoOperacional.CALCULO_DEGRADADO,
                "FALHA_ACESSO_SQLITE",
            )
            self._catalogo_degradado = catalogo
            return True

    def exige_modo_normal(self) -> None:
        with self._bloqueio:
            self._exigir_modo_normal_sem_bloquear()

    def _exigir_modo_normal_sem_bloquear(self) -> None:
        self._revalidar_catalogo_sem_bloquear()
        if self._estado.modo is not ModoOperacional.NORMAL:
            raise OperacaoProibidaNoModoAtualError(
                "A operação exige o modo normal com persistência disponível."
            )

    def permite_calculo(self) -> bool:
        return self.obter_estado().modo in {
            ModoOperacional.NORMAL,
            ModoOperacional.CALCULO_DEGRADADO,
        }

    def _revalidar_catalogo_sem_bloquear(self) -> None:
        if self._estado.modo is not ModoOperacional.CALCULO_DEGRADADO:
            return
        catalogo = self._catalogo_degradado
        if (
            catalogo is None
            or catalogo.obter_estado().status != CATALOGO_DISPONIVEL
        ):
            self._estado = EstadoOperacional(
                ModoOperacional.INDISPONIVEL,
                "CATALOGO_INVALIDADO_DURANTE_DEGRADACAO",
            )
            self._catalogo_degradado = None


@dataclass(frozen=True, slots=True)
class _VinculoBanco:
    caminho_resolvido: Path
    chave_normalizada: str
    controlador: ControladorEstadoOperacional

    def corresponde(self, caminho_resolvido: Path, chave: str) -> bool:
        if self.chave_normalizada == chave:
            return True
        try:
            return os.path.samefile(self.caminho_resolvido, caminho_resolvido)
        except OSError:
            return False


_BLOQUEIO_VINCULOS = RLock()
_VINCULOS_BANCO: list[_VinculoBanco] = []


def vincular_controlador_ao_banco(
    caminho_banco: str | Path,
    controlador: ControladorEstadoOperacional,
) -> ControladorEstadoOperacional:
    """Vincula a primeira autoridade do banco e impede sua substituição."""
    if not isinstance(controlador, ControladorEstadoOperacional):
        raise TypeError("O controlador de estado operacional é inválido.")
    caminho_resolvido, chave = _identificar_caminho_banco(caminho_banco)
    with _BLOQUEIO_VINCULOS:
        existente = _buscar_vinculo_sem_bloquear(caminho_resolvido, chave)
        if existente is not None:
            return existente.controlador
        _VINCULOS_BANCO.append(
            _VinculoBanco(caminho_resolvido, chave, controlador)
        )
        return controlador


def exigir_modo_normal(
    caminho_banco: str | Path,
    controlador: ControladorEstadoOperacional | None,
) -> None:
    """Executa a verificação pontual preservada para integrações existentes."""
    with operacao_comercial_em_modo_normal(caminho_banco, controlador):
        pass


@contextmanager
def operacao_comercial_em_modo_normal(
    caminho_banco: str | Path,
    controlador: ControladorEstadoOperacional | None = None,
):
    """Protege uma operação inteira contra transição operacional concorrente."""
    controlador_efetivo = _resolver_controlador_operacional(
        caminho_banco,
        controlador,
    )
    if controlador_efetivo is None:
        # Compatibilidade explícita: integrações sem vínculo continuam normais.
        yield
        return

    with controlador_efetivo._bloqueio:
        controlador_efetivo._exigir_modo_normal_sem_bloquear()
        yield


def _resolver_controlador_operacional(
    caminho_banco: str | Path,
    controlador: ControladorEstadoOperacional | None,
) -> ControladorEstadoOperacional | None:
    caminho_resolvido, chave = _identificar_caminho_banco(caminho_banco)
    with _BLOQUEIO_VINCULOS:
        vinculo = _buscar_vinculo_sem_bloquear(caminho_resolvido, chave)
    controlador_canonico = vinculo.controlador if vinculo is not None else None

    # O argumento preserva integrações e protege chamadas isoladas, mas nunca
    # substitui uma autoridade processual que já esteja vinculada ao banco.
    if controlador_canonico is not None:
        return controlador_canonico
    if controlador is not None:
        if not isinstance(controlador, ControladorEstadoOperacional):
            raise TypeError("O controlador de estado operacional é inválido.")
        return controlador
    return None


def _buscar_vinculo_sem_bloquear(
    caminho_resolvido: Path,
    chave: str,
) -> _VinculoBanco | None:
    for vinculo in _VINCULOS_BANCO:
        if vinculo.corresponde(caminho_resolvido, chave):
            return vinculo
    return None


def _identificar_caminho_banco(
    caminho_banco: str | Path,
) -> tuple[Path, str]:
    if not isinstance(caminho_banco, (str, Path)):
        raise TypeError("O caminho do banco deve ser texto ou Path.")
    try:
        resolvido = Path(caminho_banco).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as erro:
        raise ValueError("O caminho do banco não pôde ser identificado.") from erro
    return resolvido, os.path.normcase(str(resolvido))


def falha_sqlite_permite_degradacao(erro: BaseException) -> bool:
    if not isinstance(erro, sqlite3.Error):
        return False

    codigo = getattr(erro, "sqlite_errorcode", None)
    if isinstance(codigo, int):
        codigo_base = codigo & 0xFF
        permitidos = {
            sqlite3.SQLITE_BUSY,
            sqlite3.SQLITE_LOCKED,
            sqlite3.SQLITE_IOERR,
            sqlite3.SQLITE_CANTOPEN,
        }
        if codigo_base in permitidos:
            return True

    mensagem = str(erro).strip().lower()
    return any(
        trecho in mensagem
        for trecho in (
            "database is locked",
            "database table is locked",
            "unable to open database file",
            "disk i/o error",
        )
    )
