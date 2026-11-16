"""Backup SQLite local consistente, validado e com retenção conservadora."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from threading import Lock, RLock
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

from database.conexao import CAMINHO_BANCO
from database.schema import TABELAS_ESSENCIAIS, VERSAO_ESQUEMA
from services.estado_operacional_service import (
    ControladorEstadoOperacional,
    operacao_comercial_em_modo_normal,
)


DIAS_RETENCAO_LOCAL = 7
SEMANAS_RETENCAO_LOCAL = 4
FUSO_ESTABELECIMENTO = ZoneInfo("America/Sao_Paulo")
_PREFIXO_BACKUP = "sistema-pdv-local-v1"
_PADRAO_BACKUP = re.compile(
    rf"^{re.escape(_PREFIXO_BACKUP)}\."
    r"(?P<origem>[0-9a-f]{16})\."
    r"(?P<instante>\d{8}T\d{12}Z)\."
    r"(?P<unico>[0-9a-f]{32})\.sqlite3$"
)
_TIMEOUT_LOCK_SEGUNDOS = 60.0
_INTERVALO_LOCK_SEGUNDOS = 0.05
_BLOQUEIO_REGISTRO = Lock()
_BLOQUEIOS_DIRETORIO: dict[str, RLock] = {}


class BackupLocalError(RuntimeError):
    pass


class OrigemBackupInvalidaError(BackupLocalError):
    pass


class DestinoBackupInvalidoError(BackupLocalError):
    pass


class ValidacaoBackupError(BackupLocalError):
    pass


class PublicacaoBackupError(BackupLocalError):
    pass


class CoordenacaoBackupError(BackupLocalError):
    pass


@dataclass(frozen=True, slots=True)
class ResultadoBackupLocal:
    caminho_backup: Path
    identificador_origem: str
    backups_removidos: int
    falhas_retencao: int


@dataclass(frozen=True, slots=True)
class _BackupReconhecido:
    caminho: Path
    instante_utc: datetime


def criar_backup_local(
    caminho_banco: str | Path = CAMINHO_BANCO,
    diretorio_raiz: str | Path | None = None,
    *,
    controlador_estado: ControladorEstadoOperacional | None = None,
) -> ResultadoBackupLocal:
    """Cria e publica uma cópia validada antes de aplicar a retenção."""
    origem, identificador = _identificar_origem(caminho_banco)

    with operacao_comercial_em_modo_normal(
        origem,
        controlador_estado,
    ):
        diretorio = _preparar_diretorio_destino(
            origem,
            diretorio_raiz,
            identificador,
        )
        with _backup_local_coordenado(diretorio, identificador):
            caminho_backup = _criar_e_publicar_backup(
                origem,
                diretorio,
                identificador,
            )
            removidos, falhas = _aplicar_retencao_local(
                diretorio,
                identificador,
                preservar=caminho_backup,
            )
            resultado = ResultadoBackupLocal(
                caminho_backup=caminho_backup,
                identificador_origem=identificador,
                backups_removidos=removidos,
                falhas_retencao=falhas,
            )
            if not caminho_backup.is_file():
                raise CoordenacaoBackupError(
                    "O backup publicado deixou de estar disponível."
                )
            return resultado


@contextmanager
def _backup_local_coordenado(
    diretorio: Path,
    identificador_origem: str,
):
    chave = os.path.normcase(os.fspath(diretorio.resolve(strict=True)))
    with _BLOQUEIO_REGISTRO:
        bloqueio_local = _BLOQUEIOS_DIRETORIO.setdefault(chave, RLock())

    with bloqueio_local:
        caminho_lock = diretorio / (
            f".{_PREFIXO_BACKUP}.{identificador_origem}.lock"
        )
        try:
            with caminho_lock.open("a+b", buffering=0) as arquivo_lock:
                if arquivo_lock.seek(0, os.SEEK_END) == 0:
                    arquivo_lock.write(b"\0")
                arquivo_lock.seek(0)
                _adquirir_lock_arquivo(arquivo_lock)
                try:
                    yield
                finally:
                    _liberar_lock_arquivo(arquivo_lock)
        except CoordenacaoBackupError:
            raise
        except OSError as erro:
            raise CoordenacaoBackupError(
                "Não foi possível coordenar o backup local."
            ) from erro


def _adquirir_lock_arquivo(arquivo_lock) -> None:
    limite = time.monotonic() + _TIMEOUT_LOCK_SEGUNDOS
    while True:
        try:
            if os.name == "nt":
                import msvcrt

                arquivo_lock.seek(0)
                msvcrt.locking(arquivo_lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(
                    arquivo_lock.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            return
        except (BlockingIOError, PermissionError) as erro:
            if time.monotonic() >= limite:
                raise CoordenacaoBackupError(
                    "Outra execução de backup não terminou no tempo esperado."
                ) from erro
            time.sleep(_INTERVALO_LOCK_SEGUNDOS)


def _liberar_lock_arquivo(arquivo_lock) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            arquivo_lock.seek(0)
            msvcrt.locking(arquivo_lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(arquivo_lock.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def _aplicar_retencao_local(
    diretorio: str | Path,
    identificador_origem: str,
    *,
    preservar: Path,
) -> tuple[int, int]:
    """Mantém 7 pontos diários e 4 semanais anteriores, por origem."""
    if not re.fullmatch(r"[0-9a-f]{16}", identificador_origem):
        raise ValueError("O identificador da origem é inválido.")
    raiz = Path(diretorio)
    reconhecidos = _listar_backups_reconhecidos(
        raiz,
        identificador_origem,
    )
    if not reconhecidos:
        return 0, 0

    caminho_preservado = Path(preservar)
    if caminho_preservado not in {
        backup.caminho for backup in reconhecidos
    }:
        raise ValueError(
            "A retenção exige um novo backup reconhecido e validado."
        )

    ordenados = sorted(
        reconhecidos,
        key=lambda item: (item.instante_utc, item.caminho.name),
        reverse=True,
    )
    manter: set[Path] = {ordenados[0].caminho}
    manter.add(caminho_preservado)

    datas_mantidas = []
    for backup in ordenados:
        data_local = backup.instante_utc.astimezone(
            FUSO_ESTABELECIMENTO
        ).date()
        if data_local in datas_mantidas:
            continue
        if len(datas_mantidas) >= DIAS_RETENCAO_LOCAL:
            continue
        datas_mantidas.append(data_local)
        manter.add(backup.caminho)

    limite_diario = min(datas_mantidas) if datas_mantidas else None
    semanas_mantidas: set[tuple[int, int]] = set()
    for backup in ordenados:
        instante_local = backup.instante_utc.astimezone(FUSO_ESTABELECIMENTO)
        if limite_diario is not None and instante_local.date() >= limite_diario:
            continue
        iso = instante_local.isocalendar()
        semana = (iso.year, iso.week)
        if semana in semanas_mantidas:
            continue
        if len(semanas_mantidas) >= SEMANAS_RETENCAO_LOCAL:
            continue
        semanas_mantidas.add(semana)
        manter.add(backup.caminho)

    removidos = 0
    falhas = 0
    for backup in ordenados:
        if backup.caminho in manter:
            continue
        try:
            backup.caminho.unlink()
        except OSError:
            falhas += 1
        else:
            removidos += 1
    return removidos, falhas


def _identificar_origem(
    caminho_banco: str | Path,
) -> tuple[Path, str]:
    if not isinstance(caminho_banco, (str, Path)):
        raise OrigemBackupInvalidaError(
            "O caminho do banco de origem é inválido."
        )
    try:
        origem = Path(caminho_banco).expanduser().resolve(strict=True)
        estado = origem.stat()
    except (OSError, RuntimeError) as erro:
        raise OrigemBackupInvalidaError(
            "O banco de origem não está disponível."
        ) from erro
    if not origem.is_file():
        raise OrigemBackupInvalidaError(
            "A origem do backup deve ser um arquivo SQLite existente."
        )

    material = "|".join(
        (
            os.path.normcase(os.fspath(origem)),
            str(estado.st_dev),
            str(estado.st_ino),
        )
    ).encode("utf-8")
    identificador = hashlib.sha256(material).hexdigest()[:16]
    return origem, identificador


def _preparar_diretorio_destino(
    origem: Path,
    diretorio_raiz: str | Path | None,
    identificador_origem: str,
) -> Path:
    if diretorio_raiz is None:
        raiz = origem.parent / "backups" / "local"
    elif isinstance(diretorio_raiz, (str, Path)):
        raiz = Path(diretorio_raiz).expanduser()
    else:
        raise DestinoBackupInvalidoError(
            "O diretório de backup local é inválido."
        )

    try:
        if raiz.exists() and not raiz.is_dir():
            raise DestinoBackupInvalidoError(
                "O destino do backup local deve ser um diretório."
            )
        raiz.mkdir(parents=True, exist_ok=True)
        raiz_resolvida = raiz.resolve(strict=True)
        if os.path.samefile(origem, raiz_resolvida):
            raise DestinoBackupInvalidoError(
                "O destino do backup não pode ser o banco de origem."
            )
        diretorio = raiz_resolvida / identificador_origem
        diretorio.mkdir(parents=False, exist_ok=True)
        return diretorio.resolve(strict=True)
    except DestinoBackupInvalidoError:
        raise
    except (OSError, RuntimeError) as erro:
        raise DestinoBackupInvalidoError(
            "Não foi possível preparar o destino do backup local."
        ) from erro


def _criar_e_publicar_backup(
    origem: Path,
    diretorio: Path,
    identificador_origem: str,
) -> Path:
    descritor, nome_temporario = tempfile.mkstemp(
        prefix=f".{_PREFIXO_BACKUP}.",
        suffix=".tmp",
        dir=diretorio,
    )
    os.close(descritor)
    temporario = Path(nome_temporario)
    instante = datetime.now(UTC)
    definitivo = diretorio / _criar_nome_backup(
        identificador_origem,
        instante,
        uuid4().hex,
    )
    try:
        _executar_backup_sqlite(origem, temporario)
        _validar_backup(temporario)
        _publicar_sem_sobrescrever(temporario, definitivo)
        return definitivo
    except BackupLocalError:
        raise
    except Exception as erro:
        raise BackupLocalError(
            "Não foi possível criar e validar o backup local."
        ) from erro
    finally:
        try:
            temporario.unlink(missing_ok=True)
        except OSError:
            pass


def _executar_backup_sqlite(origem: Path, temporario: Path) -> None:
    conexao_origem = None
    conexao_destino = None
    try:
        conexao_origem = sqlite3.connect(
            f"{origem.as_uri()}?mode=ro",
            uri=True,
        )
        conexao_destino = sqlite3.connect(temporario)
        conexao_origem.backup(conexao_destino)
        conexao_destino.commit()
    finally:
        if conexao_destino is not None:
            conexao_destino.close()
        if conexao_origem is not None:
            conexao_origem.close()


def _validar_backup(caminho_backup: Path) -> None:
    conexao = None
    try:
        conexao = sqlite3.connect(
            f"{caminho_backup.as_uri()}?mode=ro",
            uri=True,
        )
        integridade = tuple(
            linha[0]
            for linha in conexao.execute("PRAGMA integrity_check").fetchall()
        )
        if integridade != ("ok",):
            raise ValidacaoBackupError(
                "A integridade da cópia local não foi confirmada."
            )
        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        if versao != VERSAO_ESQUEMA:
            raise ValidacaoBackupError(
                "A versão do backup não é compatível com a aplicação."
            )
        tabelas = {
            linha[0]
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if not TABELAS_ESSENCIAIS.issubset(tabelas):
            raise ValidacaoBackupError(
                "A estrutura essencial do backup está incompleta."
            )
        for tabela in TABELAS_ESSENCIAIS:
            conexao.execute(f'SELECT 1 FROM "{tabela}" LIMIT 1').fetchone()
        if conexao.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValidacaoBackupError(
                "Os relacionamentos do backup não puderam ser confirmados."
            )
    except ValidacaoBackupError:
        raise
    except (OSError, sqlite3.Error) as erro:
        raise ValidacaoBackupError(
            "O backup local não pôde ser validado."
        ) from erro
    finally:
        if conexao is not None:
            conexao.close()


def _publicar_sem_sobrescrever(
    temporario: Path,
    definitivo: Path,
) -> None:
    try:
        os.link(temporario, definitivo)
    except FileExistsError as erro:
        raise PublicacaoBackupError(
            "Já existe um backup com o nome calculado."
        ) from erro
    except OSError as erro:
        raise PublicacaoBackupError(
            "Não foi possível publicar o backup local com segurança."
        ) from erro


def _criar_nome_backup(
    identificador_origem: str,
    instante_utc: datetime,
    sufixo_unico: str,
) -> str:
    return (
        f"{_PREFIXO_BACKUP}.{identificador_origem}."
        f"{instante_utc.astimezone(UTC).strftime('%Y%m%dT%H%M%S%fZ')}."
        f"{sufixo_unico}.sqlite3"
    )


def _listar_backups_reconhecidos(
    diretorio: Path,
    identificador_origem: str,
) -> list[_BackupReconhecido]:
    if not diretorio.is_dir():
        return []
    reconhecidos = []
    try:
        entradas = tuple(diretorio.iterdir())
    except OSError:
        return []
    for caminho in entradas:
        if caminho.is_symlink() or not caminho.is_file():
            continue
        correspondencia = _PADRAO_BACKUP.fullmatch(caminho.name)
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
        reconhecidos.append(_BackupReconhecido(caminho, instante))
    return reconhecidos
