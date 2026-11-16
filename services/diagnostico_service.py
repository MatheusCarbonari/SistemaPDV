"""Exportação local e limitada de diagnóstico técnico do Sistema-PDV."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import zipfile

from database.conexao import CAMINHO_BANCO
from models.sessao_usuario import SessaoUsuario
from services.autenticacao_service import autorizar_sessao
from services.logging_service import (
    NOME_ARQUIVO_LOG,
    obter_contrato_evento_tecnico,
    obter_diretorio_logs_autorizado,
    obter_estado_logging,
    registrar_evento,
)
from services.version_service import obter_identificacao_aplicativo


VERSAO_CONTRATO_DIAGNOSTICO = 1
MAX_ARQUIVOS_LOG = 6
MAX_BYTES_POR_ARQUIVO = 1024 * 1024
MAX_BYTES_LINHA = 16 * 1024
MAX_EVENTOS = 1000
MAX_BYTES_EVENTOS_EXPORTADOS = 1024 * 1024
PREFIXO_TEMPORARIO = ".sistema-pdv-diagnostico-"

_NOME_TECNICO = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
_BUILD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_COMMIT_GIT = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
_VERSAO = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_RESULTADOS = frozenset(
    {"bloqueado", "em_verificacao", "falha", "incerto", "nao_persistido", "sucesso"}
)

_CAMPOS_EXPORTAVEIS_POR_EVENTO: dict[str, frozenset[str]] = {
    "aplicacao_identificada": frozenset(
        {"build_id", "commit_git", "nome_aplicativo", "versao_aplicativo"}
    ),
    "inicializacao_iniciada": frozenset(),
    "preparacao_banco_falhou": frozenset({"erro_tipo", "resultado"}),
    "preparacao_banco_concluida": frozenset(
        {"backup_criado", "banco_novo", "resultado", "versao_final", "versao_inicial"}
    ),
    "identidade_inconsistente": frozenset({"erro_tipo", "resultado"}),
    "verificacao_identidade_falhou": frozenset({"erro_tipo", "resultado"}),
    "primeiro_acesso_cancelado": frozenset({"codigo_saida"}),
    "primeiro_acesso_incompleto": frozenset({"resultado"}),
    "primeiro_acesso_concluido": frozenset({"resultado"}),
    "inicializacao_cancelada": frozenset({"codigo_saida"}),
    "sessao_ausente_apos_login": frozenset({"resultado"}),
    "abertura_operacao_falhou": frozenset({"erro_tipo", "resultado"}),
    "operacao_iniciada": frozenset({"resultado"}),
    "aplicacao_encerrada": frozenset({"codigo_saida"}),
    "persistencia_venda_falhou": frozenset({"erro_tipo", "resultado"}),
    "commit_venda_exigiu_verificacao": frozenset({"erro_tipo", "resultado"}),
    "resultado_fechamento_incerto": frozenset({"erro_tipo", "resultado"}),
    "venda_nao_persistida_apos_falha": frozenset({"erro_tipo", "resultado"}),
    "commit_cancelamento_exigiu_verificacao": frozenset(
        {"erro_tipo", "resultado"}
    ),
    "resultado_cancelamento_incerto": frozenset({"erro_tipo", "resultado"}),
    "cancelamento_nao_persistido": frozenset({"erro_tipo", "resultado"}),
    "erro_nao_tratado": frozenset({"erro_tipo"}),
    "erro_thread_nao_tratado": frozenset({"erro_tipo"}),
    "diagnostico_exportado": frozenset({"resultado"}),
    "diagnostico_exportacao_falhou": frozenset({"erro_tipo", "resultado"}),
    "backup_externo_concluido": frozenset({"resultado", "status"}),
    "backup_externo_falhou": frozenset(
        {"erro_tipo", "resultado", "status"}
    ),
    "registro_nao_catalogado": frozenset(),
}


class DiagnosticoError(RuntimeError):
    pass


class DestinoDiagnosticoInvalidoError(DiagnosticoError):
    pass


class DiagnosticoJaExisteError(DiagnosticoError):
    pass


def exportar_diagnostico(
    diretorio_destino: str | Path,
    sessao: SessaoUsuario,
    caminho_banco: str | Path = CAMINHO_BANCO,
) -> Path:
    """Cria um ZIP técnico após revalidar uma sessão Administrador."""
    try:
        autorizar_sessao(sessao, ("ADMINISTRADOR",), caminho_banco)
        return _exportar_diagnostico_autorizado(diretorio_destino)
    except Exception as erro:
        registrar_evento(
            "diagnostico_exportacao_falhou",
            erro_tipo=type(erro).__name__,
            resultado="falha",
        )
        raise


def gerar_nome_arquivo_diagnostico(instante: datetime | None = None) -> str:
    agora = instante or datetime.now(UTC)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=UTC)
    utc = agora.astimezone(UTC)
    return f"sistema-pdv-diagnostico-{utc:%Y%m%dT%H%M%S%fZ}.zip"


def _exportar_diagnostico_autorizado(diretorio_destino: str | Path) -> Path:
    destino = _validar_diretorio_destino(diretorio_destino)
    instante = datetime.now(UTC)
    caminho_final = destino / gerar_nome_arquivo_diagnostico(instante)
    temporario: Path | None = None

    try:
        eventos, estatisticas = _coletar_eventos_validos()
        identificacao = obter_identificacao_aplicativo()
        manifesto = {
            "versao_contrato": VERSAO_CONTRATO_DIAGNOSTICO,
            "gerado_em": instante.isoformat(timespec="milliseconds"),
            "aplicativo": identificacao.dados_diagnostico(),
            "logging": {"status": obter_estado_logging().status},
            "eventos": estatisticas,
            "arquivos": ["manifesto.json", "eventos.jsonl"],
        }
        conteudo_eventos = "".join(
            f"{json.dumps(evento, ensure_ascii=False, separators=(',', ':'))}\n"
            for evento in eventos
        )

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destino,
            prefix=PREFIXO_TEMPORARIO,
            suffix=".tmp",
            delete=False,
        ) as arquivo_temporario:
            temporario = Path(arquivo_temporario.name)

        with zipfile.ZipFile(
            temporario,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as pacote:
            pacote.writestr(
                "manifesto.json",
                json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
            )
            pacote.writestr("eventos.jsonl", conteudo_eventos)

        _publicar_pacote_sem_sobrescrever(temporario, caminho_final)
        temporario = None
        registrar_evento("diagnostico_exportado", resultado="sucesso")
        return caminho_final
    except Exception:
        if temporario is not None:
            try:
                temporario.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def _publicar_pacote_sem_sobrescrever(
    temporario: Path,
    caminho_final: Path,
) -> None:
    try:
        # No Windows, alvo do produto, rename é atômico no mesmo volume e
        # recusa um destino existente, ao contrário de os.replace().
        os.rename(temporario, caminho_final)
    except FileExistsError as erro:
        raise DiagnosticoJaExisteError(
            "Já existe um pacote de diagnóstico com o mesmo nome."
        ) from erro


def _validar_diretorio_destino(diretorio: str | Path) -> Path:
    if not isinstance(diretorio, (str, Path)):
        raise DestinoDiagnosticoInvalidoError(
            "Selecione um diretório válido para o diagnóstico."
        )
    destino = Path(diretorio).expanduser()
    try:
        resolvido = destino.resolve(strict=True)
    except OSError as erro:
        raise DestinoDiagnosticoInvalidoError(
            "O diretório selecionado não está disponível."
        ) from erro
    if not resolvido.is_dir():
        raise DestinoDiagnosticoInvalidoError(
            "O destino do diagnóstico deve ser um diretório."
        )
    return resolvido


def _coletar_eventos_validos() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    diretorio = obter_diretorio_logs_autorizado().resolve(strict=False)
    eventos: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTOS)
    descartados = 0
    arquivos_lidos = 0
    arquivos_indisponiveis = 0
    truncado = False

    for caminho in _caminhos_logs_permitidos(diretorio):
        if not caminho.exists():
            continue
        documentos, invalidos, arquivo_truncado, disponivel = _ler_arquivo_log(
            caminho
        )
        if not disponivel:
            arquivos_indisponiveis += 1
            continue
        arquivos_lidos += 1
        descartados += invalidos
        truncado = truncado or arquivo_truncado
        for documento in documentos:
            if len(eventos) == MAX_EVENTOS:
                truncado = True
            eventos.append(documento)

    selecionados = list(eventos)
    linhas: deque[tuple[dict[str, Any], int]] = deque()
    tamanho = 0
    for documento in reversed(selecionados):
        serializado = json.dumps(
            documento, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        tamanho_linha = len(serializado) + 1
        if tamanho + tamanho_linha > MAX_BYTES_EVENTOS_EXPORTADOS:
            truncado = True
            break
        linhas.appendleft((documento, tamanho_linha))
        tamanho += tamanho_linha

    exportados = [documento for documento, _ in linhas]
    return exportados, {
        "arquivos_lidos": arquivos_lidos,
        "arquivos_indisponiveis": arquivos_indisponiveis,
        "registros_exportados": len(exportados),
        "registros_descartados": descartados,
        "truncado": truncado,
        "limite_registros": MAX_EVENTOS,
        "limite_bytes": MAX_BYTES_EVENTOS_EXPORTADOS,
    }


def _caminhos_logs_permitidos(diretorio: Path) -> list[Path]:
    nomes = [f"{NOME_ARQUIVO_LOG}.{indice}" for indice in range(5, 0, -1)]
    nomes.append(NOME_ARQUIVO_LOG)
    permitidos = []
    for nome in nomes[:MAX_ARQUIVOS_LOG]:
        candidato = diretorio / nome
        if candidato.is_symlink():
            continue
        try:
            resolvido = candidato.resolve(strict=False)
        except OSError:
            continue
        if resolvido.parent == diretorio and resolvido.name == nome:
            permitidos.append(resolvido)
    return permitidos


def _ler_arquivo_log(
    caminho: Path,
) -> tuple[list[dict[str, Any]], int, bool, bool]:
    documentos = []
    invalidos = 0
    truncado = False
    try:
        with caminho.open("rb") as arquivo:
            arquivo.seek(0, os.SEEK_END)
            tamanho = arquivo.tell()
            inicio = max(0, tamanho - MAX_BYTES_POR_ARQUIVO)
            truncado = inicio > 0
            arquivo.seek(inicio)
            if inicio:
                fragmento = arquivo.readline(MAX_BYTES_LINHA + 1)
                if fragmento and not fragmento.endswith(b"\n"):
                    _descartar_restante_linha(arquivo)

            while True:
                linha = arquivo.readline(MAX_BYTES_LINHA + 1)
                if not linha:
                    break
                if len(linha) > MAX_BYTES_LINHA and not linha.endswith(b"\n"):
                    invalidos += 1
                    truncado = True
                    _descartar_restante_linha(arquivo)
                    continue
                documento = _reconstruir_evento(linha)
                if documento is None:
                    invalidos += 1
                else:
                    documentos.append(documento)
    except OSError:
        return [], 0, False, False
    return documentos, invalidos, truncado, True


def _descartar_restante_linha(arquivo) -> None:
    while True:
        trecho = arquivo.readline(MAX_BYTES_LINHA + 1)
        if not trecho or trecho.endswith(b"\n"):
            return


def _reconstruir_evento(linha: bytes) -> dict[str, Any] | None:
    try:
        bruto = json.loads(linha.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(bruto, dict):
        return None

    evento = bruto.get("event")
    if (
        not isinstance(evento, str)
        or evento not in _CAMPOS_EXPORTAVEIS_POR_EVENTO
    ):
        return None
    contrato = obter_contrato_evento_tecnico(evento)
    if contrato is None:
        return None
    if (
        bruto.get("component") != contrato.componente
        or bruto.get("level") != contrato.nivel
        or bruto.get("message") != contrato.mensagem
    ):
        return None

    timestamp = _normalizar_timestamp(bruto.get("timestamp"))
    if timestamp is None:
        return None
    reconstruido: dict[str, Any] = {
        "timestamp": timestamp,
        "level": contrato.nivel,
        "component": contrato.componente,
        "event": evento,
        "message": contrato.mensagem,
    }
    campos = _CAMPOS_EXPORTAVEIS_POR_EVENTO[evento] & contrato.campos_admitidos
    for campo in campos:
        valor = bruto.get(campo)
        if _valor_exportavel(campo, valor):
            reconstruido[campo] = valor
    return reconstruido


def _normalizar_timestamp(valor: Any) -> str | None:
    if not isinstance(valor, str) or len(valor) > 64:
        return None
    try:
        instante = datetime.fromisoformat(valor)
    except ValueError:
        return None
    if instante.tzinfo is None:
        return None
    return instante.astimezone(UTC).isoformat(timespec="milliseconds")


def _valor_exportavel(campo: str, valor: Any) -> bool:
    if campo in {"backup_criado", "banco_novo"}:
        return isinstance(valor, bool)
    if campo == "codigo_saida":
        return isinstance(valor, int) and not isinstance(valor, bool)
    if campo in {"versao_final", "versao_inicial"}:
        return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0
    if campo in {"erro_tipo", "status"}:
        return isinstance(valor, str) and bool(_NOME_TECNICO.fullmatch(valor))
    if campo == "resultado":
        return isinstance(valor, str) and valor in _RESULTADOS
    if campo == "nome_aplicativo":
        return valor == "Sistema-PDV"
    if campo == "versao_aplicativo":
        return isinstance(valor, str) and bool(_VERSAO.fullmatch(valor))
    if campo == "build_id":
        return valor == "desconhecido" or (
            isinstance(valor, str) and bool(_BUILD_ID.fullmatch(valor))
        )
    if campo == "commit_git":
        return valor == "desconhecido" or (
            isinstance(valor, str) and bool(_COMMIT_GIT.fullmatch(valor))
        )
    return False
