"""Configuração central de logs locais seguros do Sistema-PDV."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
import threading
from threading import RLock
from types import TracebackType
from typing import Any

from services.contexto_instalacao_service import obter_contexto_instalacao


NOME_LOGGER = "sistema_pdv"
NOME_ARQUIVO_LOG = "sistema-pdv.log"
TAMANHO_MAXIMO_PADRAO = 5 * 1024 * 1024
BACKUPS_PADRAO = 5
VARIAVEL_DIRETORIO_LOG = "SISTEMA_PDV_LOG_DIR"

LOGGING_DESCONHECIDO = "DESCONHECIDO"
LOGGING_DISPONIVEL = "DISPONIVEL"
LOGGING_FALHA_INICIALIZACAO = "FALHA_INICIALIZACAO"
LOGGING_FALHA_ESCRITA = "FALHA_ESCRITA"

_CAMPOS_PERMITIDOS = frozenset(
    {
        "backup_criado",
        "banco_novo",
        "build_id",
        "codigo_saida",
        "commit_git",
        "erro_tipo",
        "nome_aplicativo",
        "resultado",
        "status",
        "venda_id",
        "versao_aplicativo",
        "versao_final",
        "versao_inicial",
    }
)
_RESULTADOS_PERMITIDOS = frozenset(
    {"bloqueado", "em_verificacao", "falha", "incerto", "nao_persistido", "sucesso"}
)
_NOME_TECNICO_SEGURO = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")
_VERSAO_APLICATIVO_SEGURA = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_BUILD_ID_SEGURO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_COMMIT_GIT_SEGURO = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
_CHAVES_SENSIVEIS = re.compile(
    r"senha|password|hash|salt|token|capacidade|credencial|recupera(?:cao|ção)",
    re.IGNORECASE,
)
_VALORES_ROTULADOS_SENSIVEIS = re.compile(
    r"(?i)(senha|password|hash|salt|token|capacidade|credencial|"
    r"codigo[_ -]?de[_ -]?recupera(?:cao|ção))"
    r"(\s*[=:]\s*)([^\s,;]+)",
)
_UUID_SEGURO = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_VENDA_ID_SEGURO = re.compile(r"^venda:[1-9][0-9]*$")
_EVENTOS_COM_UUID = frozenset(
    {
        "commit_venda_exigiu_verificacao",
        "resultado_fechamento_incerto",
        "venda_nao_persistida_apos_falha",
    }
)
_EVENTOS_COM_VENDA_ID = frozenset(
    {
        "cancelamento_nao_persistido",
        "commit_cancelamento_exigiu_verificacao",
        "resultado_cancelamento_incerto",
    }
)

# evento: (componente, nivel, mensagem tecnica, campos admitidos)
_CATALOGO_EVENTOS: dict[str, tuple[str, int, str, frozenset[str]]] = {
    "aplicacao_identificada": (
        "aplicacao",
        logging.INFO,
        "A versão e a origem do build foram identificadas.",
        frozenset(
            {"build_id", "commit_git", "nome_aplicativo", "versao_aplicativo"}
        ),
    ),
    "inicializacao_iniciada": (
        "aplicacao",
        logging.INFO,
        "A inicialização do Sistema-PDV foi iniciada.",
        frozenset(),
    ),
    "preparacao_banco_falhou": (
        "banco",
        logging.CRITICAL,
        "A preparação do banco falhou e a operação foi bloqueada.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "preparacao_banco_concluida": (
        "banco",
        logging.INFO,
        "A preparação técnica do banco foi concluída.",
        frozenset(
            {
                "backup_criado",
                "banco_novo",
                "resultado",
                "versao_final",
                "versao_inicial",
            }
        ),
    ),
    "identidade_inconsistente": (
        "identidade",
        logging.CRITICAL,
        "A configuração de identidade está inconsistente.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "verificacao_identidade_falhou": (
        "identidade",
        logging.ERROR,
        "A verificação da configuração de identidade falhou.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "primeiro_acesso_cancelado": (
        "aplicacao",
        logging.INFO,
        "A configuração do primeiro acesso foi cancelada.",
        frozenset({"codigo_saida"}),
    ),
    "primeiro_acesso_incompleto": (
        "identidade",
        logging.CRITICAL,
        "A configuração inicial não pôde ser comprovada.",
        frozenset({"resultado"}),
    ),
    "primeiro_acesso_concluido": (
        "identidade",
        logging.INFO,
        "A configuração administrativa inicial foi concluída.",
        frozenset({"resultado"}),
    ),
    "inicializacao_cancelada": (
        "aplicacao",
        logging.INFO,
        "A inicialização foi encerrada antes da abertura da operação.",
        frozenset({"codigo_saida"}),
    ),
    "sessao_ausente_apos_login": (
        "identidade",
        logging.CRITICAL,
        "O login terminou sem uma sessão operacional válida.",
        frozenset({"resultado"}),
    ),
    "abertura_operacao_falhou": (
        "aplicacao",
        logging.CRITICAL,
        "A janela operacional não pôde ser aberta.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "operacao_iniciada": (
        "aplicacao",
        logging.INFO,
        "A janela operacional foi iniciada.",
        frozenset({"resultado"}),
    ),
    "aplicacao_encerrada": (
        "aplicacao",
        logging.INFO,
        "O Sistema-PDV foi encerrado.",
        frozenset({"codigo_saida"}),
    ),
    "persistencia_venda_falhou": (
        "persistencia_venda",
        logging.ERROR,
        "A persistência da venda falhou antes de um resultado confirmado.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "commit_venda_exigiu_verificacao": (
        "persistencia_venda",
        logging.WARNING,
        "O commit da venda falhou e exige verificação independente.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "resultado_fechamento_incerto": (
        "persistencia_venda",
        logging.ERROR,
        "Não foi possível determinar o resultado da tentativa de fechamento.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "venda_nao_persistida_apos_falha": (
        "persistencia_venda",
        logging.ERROR,
        "A verificação confirmou ausência da venda após a falha.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "commit_cancelamento_exigiu_verificacao": (
        "cancelamento_venda",
        logging.WARNING,
        "O commit do cancelamento falhou e exige verificação independente.",
        frozenset({"erro_tipo", "resultado", "venda_id"}),
    ),
    "resultado_cancelamento_incerto": (
        "cancelamento_venda",
        logging.ERROR,
        "Não foi possível confirmar o resultado do cancelamento.",
        frozenset({"erro_tipo", "resultado", "venda_id"}),
    ),
    "cancelamento_nao_persistido": (
        "cancelamento_venda",
        logging.WARNING,
        "A verificação confirmou que o cancelamento não foi persistido.",
        frozenset({"erro_tipo", "resultado", "venda_id"}),
    ),
    "erro_nao_tratado": (
        "runtime",
        logging.CRITICAL,
        "A aplicação encontrou um erro não tratado.",
        frozenset({"erro_tipo"}),
    ),
    "erro_thread_nao_tratado": (
        "runtime",
        logging.CRITICAL,
        "Uma thread Python encontrou um erro não tratado.",
        frozenset({"erro_tipo"}),
    ),
    "diagnostico_exportado": (
        "diagnostico",
        logging.INFO,
        "O pacote de diagnóstico foi exportado.",
        frozenset({"resultado"}),
    ),
    "diagnostico_exportacao_falhou": (
        "diagnostico",
        logging.ERROR,
        "A exportação do diagnóstico falhou.",
        frozenset({"erro_tipo", "resultado"}),
    ),
    "backup_externo_concluido": (
        "backup_externo",
        logging.INFO,
        "O backup externo foi transportado e validado.",
        frozenset({"resultado", "status"}),
    ),
    "backup_externo_falhou": (
        "backup_externo",
        logging.ERROR,
        "A tentativa de backup externo falhou sem afetar a operação comercial.",
        frozenset({"erro_tipo", "resultado", "status"}),
    ),
    "restauracao_teste_concluida": (
        "restauracao",
        logging.INFO,
        "Uma base de teste foi restaurada e validada.",
        frozenset({"resultado"}),
    ),
    "restauracao_teste_falhou": (
        "restauracao",
        logging.ERROR,
        "A restauração isolada não foi concluída.",
        frozenset({"erro_tipo", "resultado"}),
    ),
}
_REGISTRO_NAO_CATALOGADO = (
    "logging",
    logging.WARNING,
    "Uma tentativa de registro fora do catálogo foi neutralizada.",
)
_ORIGEM_REGISTRO_API = object()

_BLOQUEIO = RLock()
_LOGGER_RAIZ = logging.getLogger(NOME_LOGGER)
_LOGGER_RAIZ.setLevel(logging.DEBUG)
_LOGGER_RAIZ.propagate = False
_LOGGER_RAIZ.addHandler(logging.NullHandler())
_HOOK_ANTERIOR = None
_HOOK_THREAD_ANTERIOR = None
_ESTADO_LOGGING = LOGGING_DESCONHECIDO
_DIRETORIO_LOG_ATUAL: Path | None = None


@dataclass(frozen=True, slots=True)
class EstadoLogging:
    """Estado técnico observável sem expor caminho ou conteúdo dos logs."""

    status: str


@dataclass(frozen=True, slots=True)
class ContratoEventoTecnico:
    """Descrição imutável usada para validar logs tratados como não confiáveis."""

    componente: str
    nivel: str
    mensagem: str
    campos_admitidos: frozenset[str]


class _FormatadorJsonSeguro(logging.Formatter):
    """Serializa somente os campos explicitamente admitidos pelo contrato."""

    def format(self, record: logging.LogRecord) -> str:
        evento_solicitado = getattr(record, "evento_catalogado", None)
        contrato = (
            _CATALOGO_EVENTOS.get(evento_solicitado)
            if (
                getattr(record, "origem_registro_api", None)
                is _ORIGEM_REGISTRO_API
                and isinstance(evento_solicitado, str)
            )
            else None
        )
        if contrato is not None:
            componente, nivel, mensagem, campos_admitidos = contrato
            evento = evento_solicitado
            levelname = logging.getLevelName(nivel)
        else:
            componente, nivel, mensagem = _REGISTRO_NAO_CATALOGADO
            evento = "registro_nao_catalogado"
            levelname = logging.getLevelName(nivel)
            campos_admitidos = frozenset()

        documento: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": levelname,
            "component": componente,
            "event": evento,
            "message": _sanitizar_texto(mensagem),
        }

        identificador = getattr(record, "identificador_operacao", None)
        if _identificador_operacao_valido(evento, identificador):
            documento["operation_id"] = identificador

        campos = getattr(record, "campos_seguros", {})
        if isinstance(campos, dict):
            for chave, valor in campos.items():
                if (
                    chave in campos_admitidos
                    and chave in _CAMPOS_PERMITIDOS
                    and _valor_campo_valido(chave, valor)
                ):
                    documento[chave] = _normalizar_valor_seguro(valor)

        return json.dumps(documento, ensure_ascii=False, separators=(",", ":"))


class _RotatingFileHandlerTolerante(RotatingFileHandler):
    """Impede que uma falha do arquivo altere o fluxo comercial."""

    _sistema_pdv_handler = True

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        # O logging é auxiliar. Os canais de erro da interface e as exceções
        # comerciais conservam precedência quando o arquivo fica indisponível.
        _marcar_falha_escrita()
        return None


def resolver_diretorio_logs() -> Path:
    """Resolve o diretório local sem acoplá-lo ao caminho do banco SQLite."""
    contexto = obter_contexto_instalacao()
    if contexto.comercial:
        return contexto.caminhos.logs

    configurado = os.environ.get(VARIAVEL_DIRETORIO_LOG)
    if configurado:
        return Path(configurado).expanduser()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Sistema-PDV" / "logs"

    return Path.home() / ".local" / "state" / "Sistema-PDV" / "logs"


def configurar_logging(
    diretorio: str | Path | None = None,
    *,
    max_bytes: int = TAMANHO_MAXIMO_PADRAO,
    backup_count: int = BACKUPS_PADRAO,
) -> Path | None:
    """Configura um único handler rotativo; falhas degradam com segurança."""
    global _ESTADO_LOGGING, _DIRETORIO_LOG_ATUAL

    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ValueError("O tamanho máximo do log deve ser um inteiro positivo.")
    if (
        not isinstance(backup_count, int)
        or isinstance(backup_count, bool)
        or backup_count <= 0
    ):
        raise ValueError("A quantidade de backups do log deve ser inteira e positiva.")

    destino = Path(diretorio) if diretorio is not None else resolver_diretorio_logs()
    caminho_log = destino / NOME_ARQUIVO_LOG

    try:
        destino.mkdir(parents=True, exist_ok=True)
        novo_handler = _RotatingFileHandlerTolerante(
            caminho_log,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
        )
        novo_handler.setLevel(logging.DEBUG)
        novo_handler.setFormatter(_FormatadorJsonSeguro())
    except (OSError, ValueError):
        _atualizar_estado_logging(LOGGING_FALHA_INICIALIZACAO, None)
        return None

    with _BLOQUEIO:
        _remover_handlers_gerenciados()
        _LOGGER_RAIZ.addHandler(novo_handler)
        _LOGGER_RAIZ.setLevel(logging.DEBUG)
        _LOGGER_RAIZ.propagate = False
        _ESTADO_LOGGING = LOGGING_DISPONIVEL
        _DIRETORIO_LOG_ATUAL = destino.resolve(strict=False)
    return caminho_log


def registrar_evento(
    evento: str,
    *,
    identificador_operacao: str | None = None,
    **campos: Any,
) -> None:
    """Registra somente eventos catalogados, sem mensagens ou objetos livres."""
    contrato = _CATALOGO_EVENTOS.get(evento) if isinstance(evento, str) else None
    if contrato is None:
        componente, nivel, mensagem = _REGISTRO_NAO_CATALOGADO
        evento_seguro = "registro_nao_catalogado"
        campos_seguros = {}
        identificador_seguro = None
    else:
        componente, nivel, mensagem, campos_admitidos = contrato
        evento_seguro = evento
        campos_seguros = {
            chave: valor
            for chave, valor in campos.items()
            if chave in campos_admitidos
            and chave in _CAMPOS_PERMITIDOS
            and not _CHAVES_SENSIVEIS.search(chave)
            and _valor_campo_valido(chave, valor)
        }
        identificador_seguro = (
            identificador_operacao
            if _identificador_operacao_valido(evento, identificador_operacao)
            else None
        )
    logging.getLogger(f"{NOME_LOGGER}.{componente}").log(
        nivel,
        mensagem,
        extra={
            "origem_registro_api": _ORIGEM_REGISTRO_API,
            "evento_catalogado": evento_seguro,
            "identificador_operacao": identificador_seguro,
            "campos_seguros": campos_seguros,
        },
    )


def instalar_tratamento_erros_nao_tratados() -> None:
    """Instala uma vez o registro seguro de exceções que chegam ao Python."""
    global _HOOK_ANTERIOR, _HOOK_THREAD_ANTERIOR
    with _BLOQUEIO:
        if sys.excepthook is not _tratar_erro_nao_tratado:
            _HOOK_ANTERIOR = sys.excepthook
            sys.excepthook = _tratar_erro_nao_tratado
        if threading.excepthook is not _tratar_erro_thread_nao_tratado:
            _HOOK_THREAD_ANTERIOR = threading.excepthook
            threading.excepthook = _tratar_erro_thread_nao_tratado


def encerrar_logging() -> None:
    """Fecha handlers do projeto, permitindo flush e reconfiguração segura."""
    global _ESTADO_LOGGING, _DIRETORIO_LOG_ATUAL

    with _BLOQUEIO:
        _remover_handlers_gerenciados()
        _ESTADO_LOGGING = LOGGING_DESCONHECIDO
        _DIRETORIO_LOG_ATUAL = None


def obter_estado_logging() -> EstadoLogging:
    """Retorna um snapshot seguro do estado conhecido do mecanismo de logging."""
    with _BLOQUEIO:
        return EstadoLogging(_ESTADO_LOGGING)


def obter_diretorio_logs_autorizado() -> Path:
    """Retorna somente o diretório configurado pelo T49 ou seu padrão oficial."""
    with _BLOQUEIO:
        if _DIRETORIO_LOG_ATUAL is not None:
            return _DIRETORIO_LOG_ATUAL
    return resolver_diretorio_logs().resolve(strict=False)


def obter_contrato_evento_tecnico(
    evento: str,
) -> ContratoEventoTecnico | None:
    """Expõe uma cópia somente leitura do contrato, sem permitir registrá-lo."""
    if evento == "registro_nao_catalogado":
        componente, nivel, mensagem = _REGISTRO_NAO_CATALOGADO
        return ContratoEventoTecnico(
            componente,
            logging.getLevelName(nivel),
            mensagem,
            frozenset(),
        )
    contrato = _CATALOGO_EVENTOS.get(evento)
    if contrato is None:
        return None
    componente, nivel, mensagem, campos = contrato
    return ContratoEventoTecnico(
        componente,
        logging.getLevelName(nivel),
        mensagem,
        campos,
    )


def _tratar_erro_nao_tratado(
    tipo_excecao: type[BaseException],
    excecao: BaseException,
    traceback: TracebackType | None,
) -> None:
    registrar_evento(
        "erro_nao_tratado",
        erro_tipo=tipo_excecao.__name__,
    )
    hook_anterior = _HOOK_ANTERIOR
    if hook_anterior is not None and hook_anterior is not _tratar_erro_nao_tratado:
        hook_anterior(tipo_excecao, excecao, traceback)


def _tratar_erro_thread_nao_tratado(
    argumentos: threading.ExceptHookArgs,
) -> None:
    tipo_excecao = getattr(argumentos, "exc_type", None)
    if tipo_excecao is not SystemExit:
        registrar_evento(
            "erro_thread_nao_tratado",
            erro_tipo=(
                tipo_excecao.__name__
                if isinstance(tipo_excecao, type)
                else "Exception"
            ),
        )
    hook_anterior = _HOOK_THREAD_ANTERIOR
    if (
        hook_anterior is not None
        and hook_anterior is not _tratar_erro_thread_nao_tratado
    ):
        hook_anterior(argumentos)


def _remover_handlers_gerenciados() -> None:
    for handler in tuple(_LOGGER_RAIZ.handlers):
        if getattr(handler, "_sistema_pdv_handler", False):
            _LOGGER_RAIZ.removeHandler(handler)
            handler.close()


def _atualizar_estado_logging(status: str, diretorio: Path | None) -> None:
    global _ESTADO_LOGGING, _DIRETORIO_LOG_ATUAL
    with _BLOQUEIO:
        _ESTADO_LOGGING = status
        _DIRETORIO_LOG_ATUAL = diretorio


def _marcar_falha_escrita() -> None:
    global _ESTADO_LOGGING
    with _BLOQUEIO:
        _ESTADO_LOGGING = LOGGING_FALHA_ESCRITA


def _sanitizar_texto(texto: str) -> str:
    return _VALORES_ROTULADOS_SENSIVEIS.sub(r"\1\2[REDACTED]", texto)


def _normalizar_valor_seguro(valor: Any) -> str | int | float | bool | None:
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return _sanitizar_texto(valor) if isinstance(valor, str) else valor
    return type(valor).__name__


def _valor_campo_valido(chave: str, valor: Any) -> bool:
    if chave in {"backup_criado", "banco_novo"}:
        return isinstance(valor, bool)
    if chave == "codigo_saida":
        return isinstance(valor, int) and not isinstance(valor, bool)
    if chave == "venda_id":
        return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0
    if chave in {"versao_final", "versao_inicial"}:
        return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0
    if chave == "erro_tipo":
        return isinstance(valor, str) and bool(_NOME_TECNICO_SEGURO.fullmatch(valor))
    if chave == "resultado":
        return isinstance(valor, str) and valor in _RESULTADOS_PERMITIDOS
    if chave == "nome_aplicativo":
        return valor == "Sistema-PDV"
    if chave == "versao_aplicativo":
        return isinstance(valor, str) and bool(
            _VERSAO_APLICATIVO_SEGURA.fullmatch(valor)
        )
    if chave == "build_id":
        return valor == "desconhecido" or (
            isinstance(valor, str) and bool(_BUILD_ID_SEGURO.fullmatch(valor))
        )
    if chave == "commit_git":
        return valor == "desconhecido" or (
            isinstance(valor, str) and bool(_COMMIT_GIT_SEGURO.fullmatch(valor))
        )
    if chave == "status":
        return isinstance(valor, str) and bool(_NOME_TECNICO_SEGURO.fullmatch(valor))
    return False


def _identificador_operacao_valido(evento: str, identificador: Any) -> bool:
    if not isinstance(identificador, str):
        return False
    if evento in _EVENTOS_COM_UUID:
        return bool(_UUID_SEGURO.fullmatch(identificador))
    if evento in _EVENTOS_COM_VENDA_ID:
        return bool(_VENDA_ID_SEGURO.fullmatch(identificador))
    return False
