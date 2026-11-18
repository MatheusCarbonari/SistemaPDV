"""Transferência administrativa, explícita e não destrutiva de dados T59."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import ctypes
import csv
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Callable
from uuid import UUID, uuid4

from database.migracoes import MigracaoError, inspecionar_migracao
from database.schema import VERSAO_ESQUEMA
from services.backup_local_service import (
    BackupLocalError,
    criar_copia_sqlite_consistente,
)
from services.contexto_instalacao_service import (
    AMBIENTE_HOMOLOGACAO_ID,
    AMBIENTE_PRODUCAO_ID,
    CONTRATO_IDENTIDADE_VERSAO,
    CONTRATO_MANUTENCAO_VERSAO,
    NOME_ARQUIVO_BANCO,
    PRODUTO_ID,
    STATUS_MANUTENCAO_LIVRE,
    AmbienteInstalacao,
    ContextoInstalacao,
    ContextoInstalacaoError,
    obter_local_app_data_confiavel,
    verificar_estado_manutencao,
)
from services.instancia_unica_service import (
    BackendMutex,
    InstanciaUnicaError,
    adquirir_manutencao_exclusiva,
)


CONTRATO_HISTORICO_VERSAO = 1
STATUS_MIGRACAO_DADOS = "MIGRATING_LEGACY_DATA"
NOME_DIRETORIO_HISTORICO = "data-migrations"
FRASES_CONFIRMACAO = {
    AmbienteInstalacao.PRODUCAO: "MIGRAR DADOS LEGADOS PARA PRODUCAO",
    AmbienteInstalacao.HOMOLOGACAO: "MIGRAR DADOS LEGADOS PARA HOMOLOGACAO",
}
_AMBIENTES_IDS = {
    AmbienteInstalacao.PRODUCAO: AMBIENTE_PRODUCAO_ID,
    AmbienteInstalacao.HOMOLOGACAO: AMBIENTE_HOMOLOGACAO_ID,
}
_LIMITE_JSON = 32 * 1024


class MigracaoDadosLegadosError(RuntimeError):
    pass


class AutorizacaoMigracaoLegadaError(MigracaoDadosLegadosError):
    pass


class OrigemLegadaInvalidaError(MigracaoDadosLegadosError):
    pass


class DestinoComercialInvalidoError(MigracaoDadosLegadosError):
    pass


class VersaoLegadaIncompativelError(MigracaoDadosLegadosError):
    pass


class EstadoMigracaoDadosError(MigracaoDadosLegadosError):
    pass


class CopiaDadosLegadosError(MigracaoDadosLegadosError):
    pass


class HistoricoMigracaoError(MigracaoDadosLegadosError):
    pass


@dataclass(frozen=True, slots=True)
class ResultadoMigracaoDadosLegados:
    operacao_id: str
    caminho_destino: Path
    versao_schema: int
    diretorio_historico: Path


@dataclass(frozen=True, slots=True)
class _OrigemLegadaValidada:
    caminho: Path
    raiz_local_app_data: Path
    identidade_arquivo: tuple[int, int, int, int, int]


def migrar_dados_legados(
    origem_selecionada: str | Path,
    contexto_destino: ContextoInstalacao,
    *,
    confirmacao: str,
    raiz_local_app_data: str | Path | None = None,
    verificar_administrador: Callable[[], bool] | None = None,
    verificar_aplicativos_encerrados: Callable[[], bool] | None = None,
    backend_mutex: BackendMutex | None = None,
) -> ResultadoMigracaoDadosLegados:
    """Copia uma base T59 atual para um destino comercial vazio e validado."""
    _exigir_autorizacao(
        contexto_destino,
        confirmacao,
        verificar_administrador or _processo_windows_elevado,
    )
    origem_validada = _resolver_origem_legada(
        origem_selecionada,
        raiz_local_app_data,
    )
    try:
        origem_id = calcular_identificador_origem(origem_validada.caminho)
    except OSError as erro:
        raise OrigemLegadaInvalidaError(
            "A origem legada deixou de estar disponível."
        ) from erro
    operacao_id = str(uuid4())
    sequencia = 0
    historico = None
    manutencao_iniciada = False

    try:
        with adquirir_manutencao_exclusiva(
            contexto_destino,
            backend=backend_mutex,
        ):
            _validar_contexto_destino(contexto_destino)
            historico = _criar_historico(contexto_destino, operacao_id)
            sequencia = _registrar_evento(
                historico,
                contexto_destino,
                operacao_id,
                sequencia,
                "STARTED",
                origem_id=origem_id,
            )
            origem = _revalidar_origem_legada(origem_validada)
            _exigir_aplicativos_encerrados(
                verificar_aplicativos_encerrados
                or _nenhum_sistema_pdv_em_execucao
            )
            destino = _validar_destino_vazio(contexto_destino)
            versao = _validar_schema_atual(origem)
            origem = _revalidar_origem_legada(origem_validada)
            sequencia = _registrar_evento(
                historico,
                contexto_destino,
                operacao_id,
                sequencia,
                "SOURCE_VALIDATED",
                versao_schema=versao,
                origem_id=origem_id,
            )
            _publicar_estado_migracao(contexto_destino, operacao_id)
            manutencao_iniciada = True
            criar_copia_sqlite_consistente(
                origem,
                destino,
                validador=_validar_copia_schema_atual,
            )
            _revalidar_origem_legada(origem_validada)
            sequencia = _registrar_evento(
                historico,
                contexto_destino,
                operacao_id,
                sequencia,
                "COPY_VALIDATED",
                versao_schema=versao,
                origem_id=origem_id,
            )
            _registrar_evento(
                historico,
                contexto_destino,
                operacao_id,
                sequencia,
                "SUCCESS_VALIDATED",
                versao_schema=versao,
                origem_id=origem_id,
            )
            _publicar_estado_livre(contexto_destino)
            return ResultadoMigracaoDadosLegados(
                operacao_id,
                destino,
                versao,
                historico,
            )
    except BaseException as erro:
        if historico is not None:
            try:
                _registrar_evento(
                    historico,
                    contexto_destino,
                    operacao_id,
                    sequencia,
                    "FAILED_AFTER_START" if manutencao_iniciada else "REJECTED",
                    codigo_erro=type(erro).__name__,
                    origem_id=origem_id,
                )
            except Exception:
                pass
        if isinstance(erro, MigracaoDadosLegadosError):
            raise
        if isinstance(erro, (InstanciaUnicaError, ContextoInstalacaoError)):
            raise EstadoMigracaoDadosError(
                "A instalação comercial não está livre para manutenção."
            ) from erro
        if isinstance(erro, MigracaoError):
            raise VersaoLegadaIncompativelError(
                "A origem exige atualização coordenada e não foi copiada."
            ) from erro
        if isinstance(erro, BackupLocalError):
            raise CopiaDadosLegadosError(
                "A cópia consistente falhou e a manutenção permanece restrita."
            ) from erro
        if isinstance(erro, Exception):
            if manutencao_iniciada:
                raise CopiaDadosLegadosError(
                    "A operação falhou e a manutenção permanece restrita."
                ) from erro
            raise EstadoMigracaoDadosError(
                "A operação administrativa foi recusada com segurança."
            ) from erro
        raise


def _exigir_autorizacao(
    contexto: ContextoInstalacao,
    confirmacao: str,
    verificador: Callable[[], bool],
) -> None:
    if contexto.ambiente not in FRASES_CONFIRMACAO:
        raise AutorizacaoMigracaoLegadaError(
            "O destino deve ser Produção ou Homologação."
        )
    if confirmacao != FRASES_CONFIRMACAO[contexto.ambiente]:
        raise AutorizacaoMigracaoLegadaError(
            "A confirmação explícita do ambiente não confere."
        )
    try:
        autorizado = verificador()
    except Exception as erro:
        raise AutorizacaoMigracaoLegadaError(
            "A autorização administrativa não pôde ser comprovada."
        ) from erro
    if autorizado is not True:
        raise AutorizacaoMigracaoLegadaError(
            "A migração exige um Administrador Windows elevado."
        )


def _resolver_origem_legada(
    origem_selecionada: str | Path,
    raiz_local_app_data: str | Path | None,
) -> _OrigemLegadaValidada:
    if not isinstance(origem_selecionada, (str, Path)):
        raise OrigemLegadaInvalidaError("A origem legada não foi selecionada.")
    try:
        raiz = _absoluto_sem_resolver(Path(
            raiz_local_app_data
            if raiz_local_app_data is not None
            else obter_local_app_data_confiavel()
        ))
        esperada = _absoluto_sem_resolver(
            raiz / "Sistema-PDV" / "data" / NOME_ARQUIVO_BANCO
        )
        selecionada = _absoluto_sem_resolver(Path(origem_selecionada))
        if os.path.normcase(str(selecionada)) != os.path.normcase(str(esperada)):
            raise OSError
        _exigir_caminho_sem_redirecionamentos(raiz, selecionada)
        estado = os.lstat(selecionada)
        if not stat.S_ISREG(estado.st_mode) or estado.st_nlink != 1:
            raise OSError
    except (OSError, RuntimeError) as erro:
        raise OrigemLegadaInvalidaError(
            "A origem selecionada não corresponde à instalação legada T59."
        ) from erro
    return _OrigemLegadaValidada(
        selecionada,
        raiz,
        _identidade_arquivo(estado),
    )


def _revalidar_origem_legada(origem: _OrigemLegadaValidada) -> Path:
    observada = _resolver_origem_legada(
        origem.caminho,
        origem.raiz_local_app_data,
    )
    if observada.identidade_arquivo != origem.identidade_arquivo:
        raise OrigemLegadaInvalidaError(
            "A origem legada foi substituída após a seleção."
        )
    return observada.caminho


def _absoluto_sem_resolver(caminho: Path) -> Path:
    return Path(os.path.abspath(os.fspath(caminho.expanduser())))


def _exigir_caminho_sem_redirecionamentos(
    raiz: Path,
    caminho: Path,
) -> None:
    try:
        relativo = caminho.relative_to(raiz)
    except ValueError as erro:
        raise OSError("A origem está fora de LocalAppData.") from erro
    atual = raiz
    for componente in (None, *relativo.parts):
        if componente is not None:
            atual = atual / componente
        estado = os.lstat(atual)
        atributos = getattr(estado, "st_file_attributes", 0)
        if (
            stat.S_ISLNK(estado.st_mode)
            or bool(
                atributos
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            )
            or (
                hasattr(atual, "is_junction")
                and atual.is_junction()
            )
        ):
            raise OSError("A origem contém um redirecionamento de caminho.")


def _identidade_arquivo(
    estado: os.stat_result,
) -> tuple[int, int, int, int, int]:
    return (
        estado.st_dev,
        estado.st_ino,
        estado.st_size,
        estado.st_mtime_ns,
        estado.st_ctime_ns,
    )


def _validar_contexto_destino(contexto: ContextoInstalacao) -> None:
    if (
        not contexto.comercial
        or contexto.ambiente not in _AMBIENTES_IDS
        or contexto.produto_id != PRODUTO_ID
        or contexto.ambiente_id != _AMBIENTES_IDS.get(contexto.ambiente)
        or contexto.instalacao_id is None
    ):
        raise DestinoComercialInvalidoError(
            "A identidade do destino comercial é incompatível."
        )
    try:
        if str(UUID(contexto.instalacao_id)) != contexto.instalacao_id:
            raise ValueError
        _validar_caminhos_contexto(contexto)
        documento = _ler_json(contexto.caminhos.descritor_identidade)
        esperado = {
            "contract_version": CONTRATO_IDENTIDADE_VERSAO,
            "product_id": contexto.produto_id,
            "environment": contexto.ambiente.value,
            "environment_id": contexto.ambiente_id,
            "installation_id": contexto.instalacao_id,
            "install_root": str(contexto.raiz_instalacao.resolve(strict=False)),
            "executable_path": str(
                contexto.caminho_executavel.resolve(strict=False)
            ),
        }
        if set(documento) != set(esperado):
            raise ValueError
        for campo, valor in esperado.items():
            observado = documento.get(campo)
            if campo in {"install_root", "executable_path"}:
                if not _caminhos_equivalentes(observado, valor):
                    raise ValueError
            elif observado != valor:
                raise ValueError
        verificar_estado_manutencao(contexto)
    except (ValueError, OSError, ContextoInstalacaoError) as erro:
        raise DestinoComercialInvalidoError(
            "A identidade ou o estado do destino comercial diverge."
        ) from erro


def _validar_caminhos_contexto(contexto: ContextoInstalacao) -> None:
    raiz = contexto.caminhos.raiz_ambiente
    esperados = (
        (contexto.caminhos.dados, raiz / "data"),
        (contexto.caminhos.banco, raiz / "data" / NOME_ARQUIVO_BANCO),
        (contexto.caminhos.logs, raiz / "logs"),
        (contexto.caminhos.configuracao, raiz / "config"),
        (contexto.caminhos.administrativo, raiz / "administrative"),
        (
            contexto.caminhos.descritor_identidade,
            raiz / "administrative" / "installation.json",
        ),
        (
            contexto.caminhos.manifestos,
            raiz / "administrative" / "manifests",
        ),
        (contexto.caminhos.manutencao, raiz / "maintenance"),
        (
            contexto.caminhos.estado_manutencao,
            raiz / "maintenance" / "state.json",
        ),
    )
    if any(
        not _caminhos_equivalentes(observado, esperado)
        for observado, esperado in esperados
    ):
        raise ValueError("Os caminhos comerciais internos divergem.")


def _validar_destino_vazio(contexto: ContextoInstalacao) -> Path:
    destino = contexto.caminhos.banco
    dados_informados = contexto.caminhos.dados
    try:
        if dados_informados.is_symlink():
            raise OSError
        dados = dados_informados.resolve(strict=True)
    except OSError as erro:
        raise DestinoComercialInvalidoError(
            "O diretório comercial de dados não está disponível."
        ) from erro
    if dados.is_symlink() or destino.parent.resolve(strict=True) != dados:
        raise DestinoComercialInvalidoError(
            "O destino não pertence ao diretório comercial esperado."
        )
    try:
        entradas = tuple(dados_informados.iterdir())
    except OSError as erro:
        raise DestinoComercialInvalidoError(
            "O diretório comercial de dados não pôde ser inspecionado."
        ) from erro
    if entradas:
        raise DestinoComercialInvalidoError(
            "O diretório comercial de dados não está integralmente vazio."
        )
    return destino


def _validar_schema_atual(caminho: Path) -> int:
    try:
        plano = inspecionar_migracao(caminho)
    except MigracaoError as erro:
        raise VersaoLegadaIncompativelError(
            "A origem exige atualização coordenada e não foi copiada."
        ) from erro
    if plano.versao_inicial != VERSAO_ESQUEMA or plano.migracoes:
        raise VersaoLegadaIncompativelError(
            "A origem exige atualização coordenada e não foi copiada."
        )
    return plano.versao_inicial


def _validar_copia_schema_atual(caminho: Path) -> None:
    if _validar_schema_atual(caminho) != VERSAO_ESQUEMA:
        raise VersaoLegadaIncompativelError(
            "A cópia não corresponde ao schema comercial esperado."
        )


def _criar_historico(
    contexto: ContextoInstalacao,
    operacao_id: str,
) -> Path:
    manifestos = contexto.caminhos.manifestos
    raiz = manifestos / NOME_DIRETORIO_HISTORICO
    try:
        if manifestos.is_symlink() or not manifestos.is_dir():
            raise OSError
        if raiz.is_symlink():
            raise OSError
        raiz.mkdir(parents=False, exist_ok=True)
        diretorio = raiz / operacao_id
        diretorio.mkdir(parents=False, exist_ok=False)
        return diretorio
    except OSError as erro:
        raise HistoricoMigracaoError(
            "O histórico administrativo não pôde ser iniciado."
        ) from erro


def _registrar_evento(
    diretorio: Path,
    contexto: ContextoInstalacao,
    operacao_id: str,
    sequencia_anterior: int,
    evento: str,
    *,
    versao_schema: int | None = None,
    codigo_erro: str | None = None,
    origem_id: str | None = None,
) -> int:
    sequencia = sequencia_anterior + 1
    documento = {
        "contract_version": CONTRATO_HISTORICO_VERSAO,
        "operation_id": operacao_id,
        "sequence": sequencia,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "event": evento,
        "product_id": contexto.produto_id,
        "environment": contexto.ambiente.value,
        "environment_id": contexto.ambiente_id,
        "installation_id": contexto.instalacao_id,
        "authorization": "ELEVATED_WINDOWS_ADMIN",
    }
    if versao_schema is not None:
        documento["schema_version"] = versao_schema
    if codigo_erro is not None:
        documento["error_code"] = codigo_erro[:120]
    if origem_id is not None:
        documento["source_id"] = origem_id
    nome = f"{sequencia:03d}-{evento.casefold().replace('_', '-')}.json"
    _publicar_json_novo(diretorio / nome, documento)
    return sequencia


def _publicar_estado_migracao(
    contexto: ContextoInstalacao,
    operacao_id: str,
) -> None:
    documento = _documento_estado(contexto, STATUS_MIGRACAO_DADOS)
    documento["operation_id"] = operacao_id
    _substituir_json(contexto.caminhos.estado_manutencao, documento)


def _publicar_estado_livre(contexto: ContextoInstalacao) -> None:
    _substituir_json(
        contexto.caminhos.estado_manutencao,
        _documento_estado(contexto, STATUS_MANUTENCAO_LIVRE),
    )


def _documento_estado(contexto: ContextoInstalacao, status: str) -> dict:
    return {
        "contract_version": CONTRATO_MANUTENCAO_VERSAO,
        "product_id": contexto.produto_id,
        "environment_id": contexto.ambiente_id,
        "installation_id": contexto.instalacao_id,
        "status": status,
    }


def _publicar_json_novo(caminho: Path, documento: dict) -> None:
    temporario = caminho.with_name(f".{caminho.name}.{uuid4().hex}.tmp")
    conteudo = json.dumps(
        documento,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    try:
        with temporario.open("xb") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.link(temporario, caminho)
    except FileExistsError as erro:
        raise HistoricoMigracaoError(
            "Um evento administrativo já existe para esta operação."
        ) from erro
    except OSError as erro:
        raise HistoricoMigracaoError(
            "Um evento administrativo não pôde ser registrado."
        ) from erro
    finally:
        try:
            temporario.unlink(missing_ok=True)
        except OSError:
            pass


def _substituir_json(caminho: Path, documento: dict) -> None:
    temporario = caminho.with_name(f".{caminho.name}.{uuid4().hex}.tmp")
    conteudo = json.dumps(
        documento,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    try:
        with temporario.open("xb") as arquivo:
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    except OSError as erro:
        raise EstadoMigracaoDadosError(
            "O estado administrativo não pôde ser publicado."
        ) from erro
    finally:
        try:
            temporario.unlink(missing_ok=True)
        except OSError:
            pass


def _ler_json(caminho: Path) -> dict:
    if caminho.is_symlink() or not caminho.is_file():
        raise OSError
    if caminho.stat().st_size > _LIMITE_JSON:
        raise OSError
    documento = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(documento, dict):
        raise ValueError
    return documento


def _caminhos_equivalentes(caminho_a: object, caminho_b: object) -> bool:
    if not isinstance(caminho_a, (str, Path)):
        return False
    try:
        a = Path(caminho_a).resolve(strict=False)
        b = Path(caminho_b).resolve(strict=False)
        if os.path.normcase(str(a)) == os.path.normcase(str(b)):
            return True
        return os.path.samefile(a, b)
    except (OSError, RuntimeError, TypeError):
        return False


def _exigir_aplicativos_encerrados(verificador: Callable[[], bool]) -> None:
    try:
        encerrados = verificador()
    except Exception as erro:
        raise EstadoMigracaoDadosError(
            "Não foi possível comprovar que o Sistema-PDV está fechado."
        ) from erro
    if encerrados is not True:
        raise EstadoMigracaoDadosError(
            "Feche todas as instâncias do Sistema-PDV antes da migração."
        )


def _processo_windows_elevado() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _nenhum_sistema_pdv_em_execucao() -> bool:
    """Enumera processos Windows como defesa adicional ao mutex comercial."""
    if sys.platform != "win32":
        return False
    import subprocess

    resultado = subprocess.run(
        [
            "tasklist.exe",
            "/FI",
            "IMAGENAME eq Sistema-PDV.exe",
            "/FO",
            "CSV",
            "/NH",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if resultado.returncode != 0:
        raise OSError("A enumeração de processos falhou.")
    processos = csv.reader(resultado.stdout.splitlines())
    atual = os.getpid()
    for colunas in processos:
        if len(colunas) < 2 or colunas[0].casefold() != "sistema-pdv.exe":
            continue
        try:
            pid = int(colunas[1])
        except ValueError as erro:
            raise OSError(
                "A enumeração de processos retornou dados inválidos."
            ) from erro
        if pid != atual:
            return False
    return True


def calcular_identificador_origem(caminho: str | Path) -> str:
    """Identificador técnico sem expor o caminho legado no histórico."""
    resolvido = Path(caminho).resolve(strict=True)
    estado = resolvido.stat()
    material = "|".join(
        (os.path.normcase(str(resolvido)), str(estado.st_dev), str(estado.st_ino))
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]
