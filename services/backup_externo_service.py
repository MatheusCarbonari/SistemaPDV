"""Transporte e agendamento processual de backups externos do T56."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import Event, Lock, Thread, current_thread
from typing import BinaryIO, Protocol, runtime_checkable
from uuid import uuid4
from zoneinfo import ZoneInfo

from database.conexao import CAMINHO_BANCO
from services.backup_local_service import (
    ResultadoBackupLocal,
    abrir_backup_local_para_transporte,
    coordenar_diretorio_backup,
    criar_backup_local,
    validar_backup_sqlite,
)
from services.estado_operacional_service import ControladorEstadoOperacional
from services.logging_service import registrar_evento


INTERVALO_BACKUP_EXTERNO_SEGUNDOS = 2 * 60 * 60
DIAS_RETENCAO_EXTERNA = 30
VARIAVEL_DESTINO_BACKUP_EXTERNO = "SISTEMA_PDV_BACKUP_EXTERNO_DIR"
FUSO_ESTABELECIMENTO = ZoneInfo("America/Sao_Paulo")
_PREFIXO_EXTERNO = "sistema-pdv-externo-v1"
_PADRAO_EXTERNO = re.compile(
    rf"^{re.escape(_PREFIXO_EXTERNO)}\."
    r"(?P<origem>[0-9a-f]{16})\."
    r"(?P<instante>\d{8}T\d{12}Z)\."
    r"(?P<unico>[0-9a-f]{32})\.sqlite3$"
)


class EstadoBackupExterno(str, Enum):
    NAO_CONFIGURADO = "NAO_CONFIGURADO"
    PENDENTE = "PENDENTE"
    EM_EXECUCAO = "EM_EXECUCAO"
    SUCESSO = "SUCESSO"
    FALHA = "FALHA"


class BackupExternoError(RuntimeError):
    pass


class DestinoExternoInvalidoError(BackupExternoError):
    pass


class IntegridadeTransporteError(BackupExternoError):
    pass


class PublicacaoExternaError(BackupExternoError):
    pass


@dataclass(frozen=True, slots=True)
class EstadoBackupExternoSnapshot:
    status: EstadoBackupExterno
    ultima_tentativa: datetime | None
    ultimo_sucesso: datetime | None
    erro_tipo: str | None


@dataclass(frozen=True, slots=True)
class ResultadoTransporteExterno:
    caminho_backup: Path
    sha256: str
    backups_removidos: int
    falhas_retencao: int


@runtime_checkable
class DestinoBackupExterno(Protocol):
    def enviar(
        self,
        fonte: BinaryIO,
        backup_local: ResultadoBackupLocal,
        sha256_esperado: str,
    ) -> ResultadoTransporteExterno: ...


@dataclass(frozen=True, slots=True)
class _CopiaExternaReconhecida:
    caminho: Path
    instante_utc: datetime


class DestinoDiretorio:
    """Destino explícito para unidade, compartilhamento ou teste simulado."""

    def __init__(self, diretorio_raiz: str | Path) -> None:
        if not isinstance(diretorio_raiz, (str, Path)):
            raise DestinoExternoInvalidoError(
                "O destino externo deve ser um diretório explícito."
            )
        self._diretorio_raiz = Path(diretorio_raiz).expanduser()

    def enviar(
        self,
        fonte: BinaryIO,
        backup_local: ResultadoBackupLocal,
        sha256_esperado: str,
    ) -> ResultadoTransporteExterno:
        diretorio = self._preparar_diretorio(backup_local)
        nome_lock = (
            f".{_PREFIXO_EXTERNO}."
            f"{backup_local.identificador_origem}.lock"
        )
        with coordenar_diretorio_backup(diretorio, nome_lock):
            return self._enviar_coordenado(
                fonte,
                backup_local,
                sha256_esperado,
                diretorio,
            )

    def _preparar_diretorio(
        self,
        backup_local: ResultadoBackupLocal,
    ) -> Path:
        raiz = self._diretorio_raiz
        try:
            if raiz.is_symlink():
                raise DestinoExternoInvalidoError(
                    "Links simbólicos não são aceitos como destino externo."
                )
            if raiz.exists() and not raiz.is_dir():
                raise DestinoExternoInvalidoError(
                    "O destino externo deve ser um diretório."
                )
            raiz.mkdir(parents=True, exist_ok=True)
            resolvida = raiz.resolve(strict=True)
            area_local = backup_local.caminho_backup.parent.parent.resolve(
                strict=True
            )
            areas_proibidas = [area_local]
            if (
                area_local.name.casefold() == "local"
                and area_local.parent.name.casefold() == "backups"
            ):
                areas_proibidas.append(area_local.parent)
            if any(
                resolvida == area
                or resolvida.is_relative_to(area)
                or area.is_relative_to(resolvida)
                for area in areas_proibidas
            ):
                raise DestinoExternoInvalidoError(
                    "O destino externo não pode reutilizar a área de backup local."
                )
            diretorio = resolvida / backup_local.identificador_origem
            if diretorio.is_symlink():
                raise DestinoExternoInvalidoError(
                    "Links simbólicos não são aceitos como destino externo."
                )
            if diretorio.exists() and not diretorio.is_dir():
                raise DestinoExternoInvalidoError(
                    "O destino externo deve ser um diretório."
                )
            diretorio.mkdir(exist_ok=True)
            return diretorio.resolve(strict=True)
        except DestinoExternoInvalidoError:
            raise
        except (OSError, RuntimeError) as erro:
            raise DestinoExternoInvalidoError(
                "O destino externo não está acessível."
            ) from erro

    def _enviar_coordenado(
        self,
        fonte: BinaryIO,
        backup_local: ResultadoBackupLocal,
        sha256_esperado: str,
        diretorio: Path,
    ) -> ResultadoTransporteExterno:
        descritor, nome_temporario = tempfile.mkstemp(
            prefix=f".{_PREFIXO_EXTERNO}.",
            suffix=".tmp",
            dir=diretorio,
        )
        os.close(descritor)
        temporario = Path(nome_temporario)
        definitivo = diretorio / _criar_nome_externo(
            backup_local.identificador_origem,
            datetime.now(UTC),
            uuid4().hex,
        )
        try:
            fonte.seek(0)
            _copiar_stream(fonte, temporario)
            recebido = _calcular_sha256_caminho(temporario)
            if recebido != sha256_esperado:
                raise IntegridadeTransporteError(
                    "A cópia recebida não corresponde ao backup local."
                )
            validar_backup_sqlite(temporario)
            _publicar_externo_sem_sobrescrever(temporario, definitivo)
            removidos, falhas = _aplicar_retencao_externa(
                diretorio,
                backup_local.identificador_origem,
                preservar=definitivo,
            )
            if not definitivo.is_file():
                raise PublicacaoExternaError(
                    "A cópia externa publicada deixou de estar disponível."
                )
            return ResultadoTransporteExterno(
                definitivo,
                recebido,
                removidos,
                falhas,
            )
        finally:
            try:
                temporario.unlink(missing_ok=True)
            except OSError:
                pass


class ServicoBackupExterno:
    def __init__(
        self,
        caminho_banco: str | Path = CAMINHO_BANCO,
        *,
        destino: DestinoBackupExterno | None = None,
        diretorio_backup_local: str | Path | None = None,
        controlador_estado: ControladorEstadoOperacional | None = None,
    ) -> None:
        self._caminho_banco = caminho_banco
        self._diretorio_backup_local = diretorio_backup_local
        self._controlador_estado = controlador_estado
        self._bloqueio = Lock()
        self._destino = None
        self._status = EstadoBackupExterno.NAO_CONFIGURADO
        self._ultima_tentativa = None
        self._ultimo_sucesso = None
        self._erro_tipo = None
        self._ultimo_resultado: ResultadoTransporteExterno | None = None
        self._em_execucao = False
        if destino is not None:
            self.configurar_destino(destino)

    def configurar_destino(
        self,
        destino: DestinoBackupExterno | None,
    ) -> None:
        if destino is not None and not isinstance(
            destino,
            DestinoBackupExterno,
        ):
            raise TypeError("O destino de backup externo é inváido.")
        with self._bloqueio:
            if self._em_execucao:
                raise BackupExternoError(
                    "O destino não pode mudar durante uma execução."
                )
            self._destino = destino
            self._status = (
                EstadoBackupExterno.PENDENTE
                if destino is not None
                else EstadoBackupExterno.NAO_CONFIGURADO
            )
            self._erro_tipo = None

    def obter_estado(self) -> EstadoBackupExternoSnapshot:
        with self._bloqueio:
            return self._snapshot_sem_bloquear()

    def obter_ultimo_resultado(self) -> ResultadoTransporteExterno | None:
        with self._bloqueio:
            return self._ultimo_resultado

    def executar(self) -> EstadoBackupExternoSnapshot:
        with self._bloqueio:
            if self._destino is None:
                self._status = EstadoBackupExterno.NAO_CONFIGURADO
                return self._snapshot_sem_bloquear()
            if self._em_execucao:
                return self._snapshot_sem_bloquear()
            destino = self._destino
            self._em_execucao = True
            self._status = EstadoBackupExterno.EM_EXECUCAO
            self._ultima_tentativa = datetime.now(UTC)
            self._erro_tipo = None

        try:
            local = criar_backup_local(
                self._caminho_banco,
                self._diretorio_backup_local,
                controlador_estado=self._controlador_estado,
            )
            with abrir_backup_local_para_transporte(local) as fonte:
                sha256 = _calcular_sha256_stream(fonte)
                fonte.seek(0)
                resultado = destino.enviar(fonte, local, sha256)
        except Exception as erro:
            with self._bloqueio:
                self._status = EstadoBackupExterno.FALHA
                self._erro_tipo = type(erro).__name__
                self._em_execucao = False
                snapshot = self._snapshot_sem_bloquear()
            registrar_evento(
                "backup_externo_falhou",
                erro_tipo=type(erro).__name__,
                resultado="falha",
                status=snapshot.status.value,
            )
            return snapshot

        with self._bloqueio:
            self._ultimo_resultado = resultado
            self._ultimo_sucesso = datetime.now(UTC)
            self._status = EstadoBackupExterno.SUCESSO
            self._erro_tipo = None
            self._em_execucao = False
            snapshot = self._snapshot_sem_bloquear()
        registrar_evento(
            "backup_externo_concluido",
            resultado="sucesso",
            status=snapshot.status.value,
        )
        return snapshot

    def marcar_pendente(self) -> None:
        with self._bloqueio:
            if self._destino is not None and not self._em_execucao:
                self._status = EstadoBackupExterno.PENDENTE

    def _snapshot_sem_bloquear(self) -> EstadoBackupExternoSnapshot:
        return EstadoBackupExternoSnapshot(
            self._status,
            self._ultima_tentativa,
            self._ultimo_sucesso,
            self._erro_tipo,
        )


class AgendadorBackupExterno:
    def __init__(
        self,
        servico: ServicoBackupExterno,
        *,
        intervalo_segundos: float = INTERVALO_BACKUP_EXTERNO_SEGUNDOS,
    ) -> None:
        if not isinstance(servico, ServicoBackupExterno):
            raise TypeError("O serviço de backup externo é inválido.")
        if (
            not isinstance(intervalo_segundos, (int, float))
            or isinstance(intervalo_segundos, bool)
            or intervalo_segundos <= 0
        ):
            raise ValueError("O intervalo do backup externo deve ser positivo.")
        self._servico = servico
        self._intervalo = float(intervalo_segundos)
        self._parar = Event()
        self._bloqueio = Lock()
        self._thread: Thread | None = None

    def iniciar(self) -> bool:
        with self._bloqueio:
            if (
                self._servico.obter_estado().status
                is EstadoBackupExterno.NAO_CONFIGURADO
            ):
                return False
            if self._thread is not None and self._thread.is_alive():
                return False
            self._parar.clear()
            self._thread = Thread(
                target=self._executar_ciclo,
                name="sistema-pdv-backup-externo",
                daemon=True,
            )
            self._thread.start()
            return True

    def parar(self, timeout: float = 5.0) -> None:
        self._parar.set()
        with self._bloqueio:
            thread = self._thread
        if thread is not None and thread is not current_thread():
            thread.join(timeout)

    def _executar_ciclo(self) -> None:
        while not self._parar.is_set():
            self._servico.marcar_pendente()
            self._servico.executar()
            if self._parar.wait(self._intervalo):
                return


def destino_externo_configurado_no_ambiente() -> DestinoDiretorio | None:
    configurado = os.environ.get(VARIAVEL_DESTINO_BACKUP_EXTERNO)
    if not configurado or not configurado.strip():
        return None
    return DestinoDiretorio(configurado)


def _calcular_sha256_stream(fonte: BinaryIO) -> str:
    fonte.seek(0)
    resumo = hashlib.sha256()
    while bloco := fonte.read(1024 * 1024):
        resumo.update(bloco)
    return resumo.hexdigest()


def _calcular_sha256_caminho(caminho: Path) -> str:
    with caminho.open("rb") as arquivo:
        return _calcular_sha256_stream(arquivo)


def _copiar_stream(fonte: BinaryIO, destino: Path) -> None:
    with destino.open("wb") as arquivo_destino:
        shutil.copyfileobj(fonte, arquivo_destino, length=1024 * 1024)
        arquivo_destino.flush()
        os.fsync(arquivo_destino.fileno())


def _publicar_externo_sem_sobrescrever(
    temporario: Path,
    definitivo: Path,
) -> None:
    try:
        if os.name == "nt":
            os.rename(temporario, definitivo)
        else:
            os.link(temporario, definitivo)
            temporario.unlink()
    except FileExistsError as erro:
        raise PublicacaoExternaError(
            "Já existe uma cópia externa com o nome calculado."
        ) from erro
    except OSError as erro:
        raise PublicacaoExternaError(
            "A cópia externa não pôde ser publicada com segurança."
        ) from erro


def _criar_nome_externo(
    identificador_origem: str,
    instante_utc: datetime,
    sufixo: str,
) -> str:
    return (
        f"{_PREFIXO_EXTERNO}.{identificador_origem}."
        f"{instante_utc.astimezone(UTC).strftime('%Y%m%dT%H%M%S%fZ')}."
        f"{sufixo}.sqlite3"
    )


def _aplicar_retencao_externa(
    diretorio: Path,
    identificador_origem: str,
    *,
    preservar: Path,
) -> tuple[int, int]:
    reconhecidos = _listar_copias_externas(diretorio, identificador_origem)
    if preservar not in {item.caminho for item in reconhecidos}:
        raise PublicacaoExternaError(
            "A retenção exige a nova cópia externa validada."
        )
    ordenados = sorted(
        reconhecidos,
        key=lambda item: (item.instante_utc, item.caminho.name),
        reverse=True,
    )
    manter = {preservar, ordenados[0].caminho}
    datas = set()
    for item in ordenados:
        data_local = item.instante_utc.astimezone(FUSO_ESTABELECIMENTO).date()
        if data_local in datas or len(datas) >= DIAS_RETENCAO_EXTERNA:
            continue
        datas.add(data_local)
        manter.add(item.caminho)
    removidos = 0
    falhas = 0
    for item in ordenados:
        if item.caminho in manter:
            continue
        try:
            item.caminho.unlink()
        except OSError:
            falhas += 1
        else:
            removidos += 1
    return removidos, falhas


def _listar_copias_externas(
    diretorio: Path,
    identificador_origem: str,
) -> list[_CopiaExternaReconhecida]:
    reconhecidas = []
    try:
        entradas = tuple(diretorio.iterdir())
    except OSError:
        return reconhecidas
    for caminho in entradas:
        if caminho.is_symlink() or not caminho.is_file():
            continue
        correspondencia = _PADRAO_EXTERNO.fullmatch(caminho.name)
        if (
            correspondencia is None
            or correspondencia.group("origem") != identificador_origem
        ):
            continue
        try:
            instante = datetime.strptime(
                correspondencia.group("instante"),
                "%Y%m%dT%H%M%S%fZ",
            ).replace(tzinfo=UTC)
        except ValueError:
            continue
        reconhecidas.append(_CopiaExternaReconhecida(caminho, instante))
    return reconhecidas
