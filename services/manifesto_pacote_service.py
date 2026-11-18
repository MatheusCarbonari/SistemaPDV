"""Manifestos assinados e inspeção inerte de pacotes comerciais T60."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
from types import MappingProxyType
from typing import Iterable, Mapping
import unicodedata
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from services.contexto_instalacao_service import (
    AMBIENTE_HOMOLOGACAO_ID,
    AMBIENTE_PRODUCAO_ID,
    PRODUTO_ID,
    AmbienteInstalacao,
    ContextoInstalacao,
)


CONTRATO_MANIFESTO_VERSAO = 1
CONTRATO_ASSINATURA_VERSAO = 1
ALGORITMO_ASSINATURA = "Ed25519"
NOME_MANIFESTO = "package-manifest.json"
NOME_ASSINATURA = "package-manifest.sig"
NOME_RELATORIO_BUILD = "build-report.json"
PLATAFORMA_WINDOWS = "windows"
ARQUITETURA_X64 = "x86_64"
TAMANHO_MAXIMO_MANIFESTO = 8 * 1024 * 1024
TAMANHO_MAXIMO_ASSINATURA = 16 * 1024
MAXIMO_ARQUIVOS = 20_000
TAMANHO_BLOCO_HASH = 1024 * 1024

# Nenhuma chave comercial foi autorizada nesta etapa. Releases permanecem
# bloqueadas até uma chave pública ser incorporada por processo controlado.
CHAVES_PUBLICAS_COMERCIAIS: Mapping[str, bytes] = MappingProxyType({})

_AMBIENTES_IDS = {
    AmbienteInstalacao.PRODUCAO.value: AMBIENTE_PRODUCAO_ID,
    AmbienteInstalacao.HOMOLOGACAO.value: AMBIENTE_HOMOLOGACAO_ID,
}
_VERSAO = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_IDENTIFICADOR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HASH_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
_METADADOS_RESERVADOS = frozenset({NOME_MANIFESTO, NOME_ASSINATURA})
_CARACTERES_PROIBIDOS_WINDOWS = frozenset('<>:"\\|?*')
_NOMES_DISPOSITIVOS_WINDOWS = frozenset(
    {
        "aux",
        "clock$",
        "con",
        "conin$",
        "conout$",
        "nul",
        "prn",
        *(f"com{numero}" for numero in "123456789¹²³"),
        *(f"lpt{numero}" for numero in "123456789¹²³"),
    }
)
_SUFIXOS_SENSIVEIS = (
    ".db",
    ".db-backup",
    ".db-bak",
    ".db-journal",
    ".db-shm",
    ".db-wal",
    ".key",
    ".log",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
)


class ManifestoPacoteError(RuntimeError):
    pass


class ManifestoInvalidoError(ManifestoPacoteError):
    pass


class AssinaturaPacoteInvalidaError(ManifestoPacoteError):
    pass


class IntegridadePacoteError(ManifestoPacoteError):
    pass


class CompatibilidadePacoteError(ManifestoPacoteError):
    pass


@dataclass(frozen=True, slots=True)
class OrigemCompativel:
    versao_aplicativo: str
    versao_schema: int


@dataclass(frozen=True, slots=True)
class ResultadoVerificacaoPacote:
    pacote_id: str
    versao_pacote: str
    versao_aplicativo_destino: str
    build_id: str
    chave_id: str
    migracoes_schema_presentes: bool
    integridade_comprovada: bool
    compatibilidade_declarada: bool
    atualizacao_coordenada_autorizada: bool


def serializar_json_canonico(documento: object) -> bytes:
    """Serializa sem espaços, NaN ou ordenação dependente do produtor."""
    try:
        texto = json.dumps(
            documento,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError, RecursionError) as erro:
        raise ManifestoInvalidoError(
            "O documento não admite serialização JSON canônica."
        ) from erro
    return texto.encode("utf-8")


def gerar_manifesto(
    raiz_pacote: str | Path,
    *,
    ambiente: str,
    pacote_id: str,
    versao_pacote: str,
    versao_aplicativo: str,
    build_id: str,
    commit_git: str | None,
    origens_permitidas: Iterable[OrigemCompativel],
    versao_schema_exigida: int,
    politica_atualizacao_id: str,
    compatibilidade_anterior_declarada: bool,
    referencia_homologacao: str,
    migracoes_schema: Iterable[str] = (),
) -> dict:
    """Gera conteúdo determinístico; não assina nem concede confiança."""
    raiz = _validar_raiz(raiz_pacote)
    ambiente_id = _AMBIENTES_IDS.get(ambiente)
    if ambiente_id is None:
        raise ManifestoInvalidoError("O ambiente comercial do pacote é inválido.")
    origens = sorted(
        (
            {
                "application_version": item.versao_aplicativo,
                "schema_version": item.versao_schema,
            }
            for item in origens_permitidas
        ),
        key=lambda item: (item["application_version"], item["schema_version"]),
    )
    migracoes = sorted(migracoes_schema)
    manifesto = {
        "contract_version": CONTRATO_MANIFESTO_VERSAO,
        "product": {
            "product_id": PRODUTO_ID,
            "environment": ambiente,
            "environment_id": ambiente_id,
        },
        "package": {
            "package_id": pacote_id,
            "package_version": versao_pacote,
        },
        "application": {
            "name": "Sistema-PDV",
            "version": versao_aplicativo,
            "build_id": build_id,
            "commit_git": commit_git,
        },
        "target": {
            "platform": PLATAFORMA_WINDOWS,
            "architecture": ARQUITETURA_X64,
        },
        "compatibility": {
            "allowed_sources": origens,
            "required_schema_version": versao_schema_exigida,
            "update_policy_id": politica_atualizacao_id,
            "previous_application_compatibility": {
                "declared": compatibilidade_anterior_declarada,
                "homologation_reference": referencia_homologacao,
            },
            "schema_migrations": {
                "present": bool(migracoes),
                "identifiers": migracoes,
            },
        },
        "files": _inventariar_arquivos(raiz),
    }
    _validar_contrato_manifesto(manifesto)
    _validar_relatorio_build(raiz, manifesto)
    return manifesto


def gravar_manifesto(raiz_pacote: str | Path, manifesto: dict) -> Path:
    raiz = _validar_raiz(raiz_pacote)
    _validar_contrato_manifesto(manifesto)
    destino = raiz / NOME_MANIFESTO
    if destino.exists():
        raise ManifestoInvalidoError("O manifesto existente não será sobrescrito.")
    destino.write_bytes(serializar_json_canonico(manifesto) + b"\n")
    return destino


def validar_conteudo_manifesto_nao_confiavel(
    raiz_pacote: str | Path,
) -> dict:
    """Audita estrutura/inventário, mas deliberadamente não prova confiança."""
    raiz = _validar_raiz(raiz_pacote)
    manifesto = _ler_json_canonico(
        raiz / NOME_MANIFESTO,
        TAMANHO_MAXIMO_MANIFESTO,
        ManifestoInvalidoError,
    )
    _validar_contrato_manifesto(manifesto)
    _validar_inventario(raiz, manifesto)
    _validar_relatorio_build(raiz, manifesto)
    return manifesto


def verificar_pacote_assinado(
    raiz_pacote: str | Path,
    *,
    contexto: ContextoInstalacao,
    versao_aplicativo_origem: str,
    versao_schema_origem: int,
    plataforma_atual: str | None = None,
    arquitetura_atual: str | None = None,
) -> ResultadoVerificacaoPacote:
    """Autentica antes de interpretar e nunca executa conteúdo do pacote."""
    raiz = _validar_raiz(raiz_pacote)
    manifesto = _ler_json_canonico(
        raiz / NOME_MANIFESTO,
        TAMANHO_MAXIMO_MANIFESTO,
        ManifestoInvalidoError,
    )
    assinatura = _ler_json_canonico(
        raiz / NOME_ASSINATURA,
        TAMANHO_MAXIMO_ASSINATURA,
        AssinaturaPacoteInvalidaError,
    )
    chave_id = _verificar_assinatura(
        manifesto,
        assinatura,
        CHAVES_PUBLICAS_COMERCIAIS,
    )
    _validar_contrato_manifesto(manifesto)
    _validar_inventario(raiz, manifesto)
    _validar_relatorio_build(raiz, manifesto)
    _validar_compatibilidade(
        manifesto,
        contexto,
        versao_aplicativo_origem,
        versao_schema_origem,
        plataforma_atual or _plataforma_atual(),
        arquitetura_atual or _arquitetura_atual(),
    )
    compatibilidade = manifesto["compatibility"]
    declaracao = compatibilidade["previous_application_compatibility"]
    return ResultadoVerificacaoPacote(
        pacote_id=manifesto["package"]["package_id"],
        versao_pacote=manifesto["package"]["package_version"],
        versao_aplicativo_destino=manifesto["application"]["version"],
        build_id=manifesto["application"]["build_id"],
        chave_id=chave_id,
        migracoes_schema_presentes=compatibilidade["schema_migrations"]["present"],
        integridade_comprovada=True,
        compatibilidade_declarada=declaracao["declared"],
        atualizacao_coordenada_autorizada=False,
    )


def _verificar_assinatura(
    manifesto: dict,
    assinatura: dict,
    chaves_confiaveis: Mapping[str, bytes],
) -> str:
    if not isinstance(assinatura, dict) or set(assinatura) != {
        "contract_version",
        "algorithm",
        "key_id",
        "signature",
    }:
        raise AssinaturaPacoteInvalidaError("O contrato da assinatura é inválido.")
    if (
        assinatura["contract_version"] != CONTRATO_ASSINATURA_VERSAO
        or assinatura["algorithm"] != ALGORITMO_ASSINATURA
        or not _texto_valido(assinatura["key_id"], _IDENTIFICADOR)
        or not isinstance(assinatura["signature"], str)
    ):
        raise AssinaturaPacoteInvalidaError("A assinatura é inválida.")
    chave_id = assinatura["key_id"]
    material = chaves_confiaveis.get(chave_id)
    if not isinstance(material, bytes) or len(material) != 32:
        raise AssinaturaPacoteInvalidaError("A chave de assinatura não é confiável.")
    try:
        valor = base64.b64decode(assinatura["signature"], validate=True)
        if len(valor) != 64:
            raise ValueError
        Ed25519PublicKey.from_public_bytes(material).verify(
            valor,
            serializar_json_canonico(manifesto),
        )
    except (InvalidSignature, ValueError, TypeError) as erro:
        raise AssinaturaPacoteInvalidaError(
            "A assinatura do manifesto não pôde ser comprovada."
        ) from erro
    return chave_id


def _validar_contrato_manifesto(manifesto: object) -> None:
    try:
        if not isinstance(manifesto, dict) or set(manifesto) != {
            "contract_version",
            "product",
            "package",
            "application",
            "target",
            "compatibility",
            "files",
        }:
            raise ValueError
        if manifesto["contract_version"] != CONTRATO_MANIFESTO_VERSAO:
            raise ValueError
        produto = manifesto["product"]
        pacote = manifesto["package"]
        aplicativo = manifesto["application"]
        alvo = manifesto["target"]
        compatibilidade = manifesto["compatibility"]
        if set(produto) != {"product_id", "environment", "environment_id"}:
            raise ValueError
        if (
            produto["product_id"] != PRODUTO_ID
            or produto["environment"] not in _AMBIENTES_IDS
            or produto["environment_id"]
            != _AMBIENTES_IDS[produto["environment"]]
        ):
            raise ValueError
        if set(pacote) != {"package_id", "package_version"}:
            raise ValueError
        if not _texto_valido(pacote["package_id"], _IDENTIFICADOR):
            raise ValueError
        if not _texto_valido(pacote["package_version"], _VERSAO):
            raise ValueError
        if set(aplicativo) != {"name", "version", "build_id", "commit_git"}:
            raise ValueError
        if (
            aplicativo["name"] != "Sistema-PDV"
            or not _texto_valido(aplicativo["version"], _VERSAO)
            or not _texto_valido(aplicativo["build_id"], _IDENTIFICADOR)
            or (
                aplicativo["commit_git"] is not None
                and not _texto_valido(aplicativo["commit_git"], _COMMIT)
            )
        ):
            raise ValueError
        if alvo != {
            "platform": PLATAFORMA_WINDOWS,
            "architecture": ARQUITETURA_X64,
        }:
            raise ValueError
        _validar_compatibilidade_declarada(compatibilidade)
        _validar_lista_arquivos(manifesto["files"])
        UUID(produto["product_id"])
        UUID(produto["environment_id"])
    except (KeyError, TypeError, ValueError) as erro:
        raise ManifestoInvalidoError(
            "O contrato do manifesto é desconhecido, incompleto ou inválido."
        ) from erro


def _validar_compatibilidade_declarada(compatibilidade: object) -> None:
    if not isinstance(compatibilidade, dict) or set(compatibilidade) != {
        "allowed_sources",
        "required_schema_version",
        "update_policy_id",
        "previous_application_compatibility",
        "schema_migrations",
    }:
        raise ValueError
    if (
        not isinstance(compatibilidade["required_schema_version"], int)
        or isinstance(compatibilidade["required_schema_version"], bool)
        or compatibilidade["required_schema_version"] < 0
        or not _texto_valido(compatibilidade["update_policy_id"], _IDENTIFICADOR)
    ):
        raise ValueError
    origens = compatibilidade["allowed_sources"]
    if not isinstance(origens, list) or not origens:
        raise ValueError
    identidades = set()
    for origem in origens:
        if not isinstance(origem, dict) or set(origem) != {
            "application_version",
            "schema_version",
        }:
            raise ValueError
        if (
            not _texto_valido(origem["application_version"], _VERSAO)
            or not isinstance(origem["schema_version"], int)
            or isinstance(origem["schema_version"], bool)
            or origem["schema_version"] < 0
        ):
            raise ValueError
        identidade = (origem["application_version"], origem["schema_version"])
        if identidade in identidades:
            raise ValueError
        identidades.add(identidade)
    declaracao = compatibilidade["previous_application_compatibility"]
    if (
        not isinstance(declaracao, dict)
        or set(declaracao) != {"declared", "homologation_reference"}
        or declaracao["declared"] is not True
        or not _texto_valido(declaracao["homologation_reference"], _IDENTIFICADOR)
    ):
        raise ValueError
    migracoes = compatibilidade["schema_migrations"]
    if (
        not isinstance(migracoes, dict)
        or set(migracoes) != {"present", "identifiers"}
        or not isinstance(migracoes["present"], bool)
        or not isinstance(migracoes["identifiers"], list)
        or migracoes["present"] != bool(migracoes["identifiers"])
        or any(not _texto_valido(item, _IDENTIFICADOR) for item in migracoes["identifiers"])
        or len(set(migracoes["identifiers"])) != len(migracoes["identifiers"])
    ):
        raise ValueError


def _validar_lista_arquivos(arquivos: object) -> None:
    if not isinstance(arquivos, list) or not arquivos or len(arquivos) > MAXIMO_ARQUIVOS:
        raise ValueError
    anteriores = set()
    for arquivo in arquivos:
        if not isinstance(arquivo, dict) or set(arquivo) != {"path", "size", "sha256"}:
            raise ValueError
        caminho = _normalizar_caminho_relativo(arquivo["path"])
        identidade = caminho.casefold()
        if identidade in anteriores or caminho in _METADADOS_RESERVADOS:
            raise ValueError
        anteriores.add(identidade)
        if (
            not isinstance(arquivo["size"], int)
            or isinstance(arquivo["size"], bool)
            or arquivo["size"] < 0
            or not _texto_valido(arquivo["sha256"], _HASH_SHA256)
        ):
            raise ValueError


def _validar_inventario(raiz: Path, manifesto: dict) -> None:
    declarados = {
        item["path"].casefold(): item
        for item in manifesto["files"]
    }
    observados = {
        item["path"].casefold(): item
        for item in _inventariar_arquivos(raiz)
    }
    if declarados.keys() != observados.keys():
        raise IntegridadePacoteError(
            "O pacote contém arquivos ausentes ou inesperados."
        )
    for identidade, declarado in declarados.items():
        observado = observados[identidade]
        if (
            declarado["path"] != observado["path"]
            or declarado["size"] != observado["size"]
            or declarado["sha256"] != observado["sha256"]
        ):
            raise IntegridadePacoteError(
                "O tamanho, caminho ou hash de um arquivo diverge."
            )


def _validar_relatorio_build(raiz: Path, manifesto: dict) -> None:
    relatorio = _ler_json_limitado(
        raiz / NOME_RELATORIO_BUILD,
        64 * 1024,
        ManifestoInvalidoError,
    )
    aplicativo = manifesto["application"]
    esperado = {
        "aplicativo": aplicativo["name"],
        "versao_aplicativo": aplicativo["version"],
        "build_id": aplicativo["build_id"],
        "commit_git": aplicativo["commit_git"],
    }
    if not isinstance(relatorio, dict) or any(
        relatorio.get(campo) != valor for campo, valor in esperado.items()
    ):
        raise ManifestoInvalidoError(
            "O identificador do build diverge do relatório T59 autenticado."
        )


def _validar_compatibilidade(
    manifesto: dict,
    contexto: ContextoInstalacao,
    versao_aplicativo_origem: str,
    versao_schema_origem: int,
    plataforma_atual: str,
    arquitetura_atual: str,
) -> None:
    produto = manifesto["product"]
    if (
        not contexto.comercial
        or contexto.produto_id != produto["product_id"]
        or contexto.ambiente.value != produto["environment"]
        or contexto.ambiente_id != produto["environment_id"]
    ):
        raise CompatibilidadePacoteError(
            "O produto ou ambiente do pacote diverge da instalação."
        )
    alvo = manifesto["target"]
    if (
        plataforma_atual != alvo["platform"]
        or arquitetura_atual != alvo["architecture"]
    ):
        raise CompatibilidadePacoteError(
            "A plataforma ou arquitetura do pacote é incompatível."
        )
    compatibilidade = manifesto["compatibility"]
    origem = {
        "application_version": versao_aplicativo_origem,
        "schema_version": versao_schema_origem,
    }
    if origem not in compatibilidade["allowed_sources"]:
        raise CompatibilidadePacoteError(
            "A combinação de versão e schema de origem não foi homologada."
        )
    migracoes = compatibilidade["schema_migrations"]
    if not migracoes["present"] and (
        versao_schema_origem != compatibilidade["required_schema_version"]
    ):
        raise CompatibilidadePacoteError(
            "O schema exige migração não declarada pelo pacote."
        )


def _inventariar_arquivos(raiz: Path) -> list[dict]:
    itens = []
    identidades = set()
    for caminho in _percorrer_sem_redirecionamentos(raiz):
        relativo = caminho.relative_to(raiz).as_posix()
        if relativo in _METADADOS_RESERVADOS:
            continue
        normalizado = _normalizar_caminho_relativo(relativo)
        identidade = normalizado.casefold()
        if identidade in identidades:
            raise IntegridadePacoteError(
                "O pacote contém caminhos duplicados no Windows."
            )
        identidades.add(identidade)
        estado = os.lstat(caminho)
        itens.append(
            {
                "path": normalizado,
                "size": estado.st_size,
                "sha256": _calcular_sha256(caminho),
            }
        )
        if len(itens) > MAXIMO_ARQUIVOS:
            raise IntegridadePacoteError("O pacote excede o limite de arquivos.")
    if not itens:
        raise IntegridadePacoteError("O pacote não contém arquivos distribuídos.")
    return sorted(itens, key=lambda item: item["path"].casefold())


def _percorrer_sem_redirecionamentos(raiz: Path):
    pendentes = [raiz]
    while pendentes:
        diretorio = pendentes.pop()
        _exigir_entrada_regular(diretorio, diretorio=True)
        try:
            entradas = sorted(os.scandir(diretorio), key=lambda item: item.name.casefold())
        except OSError as erro:
            raise IntegridadePacoteError("O pacote não pôde ser inspecionado.") from erro
        for entrada in entradas:
            caminho = Path(entrada.path)
            estado = _exigir_entrada_regular(caminho, diretorio=entrada.is_dir(follow_symlinks=False))
            if stat.S_ISDIR(estado.st_mode):
                pendentes.append(caminho)
            elif stat.S_ISREG(estado.st_mode):
                yield caminho
            else:
                raise IntegridadePacoteError("O pacote contém uma entrada especial.")


def _exigir_entrada_regular(caminho: Path, *, diretorio: bool) -> os.stat_result:
    try:
        estado = os.lstat(caminho)
        atributos = getattr(estado, "st_file_attributes", 0)
        if (
            stat.S_ISLNK(estado.st_mode)
            or bool(atributos & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
            or (hasattr(caminho, "is_junction") and caminho.is_junction())
            or (not diretorio and estado.st_nlink != 1)
        ):
            raise OSError
    except OSError as erro:
        raise IntegridadePacoteError(
            "O pacote contém link ou redirecionamento não permitido."
        ) from erro
    return estado


def _normalizar_caminho_relativo(valor: object) -> str:
    if not isinstance(valor, str) or not valor or "\\" in valor or ":" in valor:
        raise ValueError
    caminho = PurePosixPath(valor)
    if caminho.is_absolute() or any(parte in {"", ".", ".."} for parte in caminho.parts):
        raise ValueError
    normalizado = caminho.as_posix()
    if normalizado != valor:
        raise ValueError
    for componente in caminho.parts:
        if (
            componente.endswith((".", " "))
            or unicodedata.normalize("NFC", componente) != componente
            or len(componente.encode("utf-16-le")) // 2 > 255
            or any(
                caractere in _CARACTERES_PROIBIDOS_WINDOWS
                or unicodedata.category(caractere) == "Cc"
                for caractere in componente
            )
            or componente.split(".", maxsplit=1)[0].rstrip(" ").casefold()
            in _NOMES_DISPOSITIVOS_WINDOWS
        ):
            raise ValueError
    nome = caminho.name.casefold()
    if (
        nome == ".env"
        or nome.startswith(".env.")
        or nome.startswith("credentials.local.")
        or nome.startswith("secrets.local.")
        or nome.endswith(_SUFIXOS_SENSIVEIS)
    ):
        raise ValueError
    return normalizado


def _ler_json_canonico(caminho: Path, limite: int, erro_tipo: type[ManifestoPacoteError]) -> dict:
    documento, conteudo = _ler_json_com_bytes(caminho, limite, erro_tipo)
    if conteudo != serializar_json_canonico(documento) + b"\n":
        raise erro_tipo("O documento não usa a serialização canônica exigida.")
    return documento


def _ler_json_limitado(caminho: Path, limite: int, erro_tipo: type[ManifestoPacoteError]) -> dict:
    documento, _ = _ler_json_com_bytes(caminho, limite, erro_tipo)
    return documento


def _ler_json_com_bytes(caminho: Path, limite: int, erro_tipo: type[ManifestoPacoteError]):
    try:
        os.lstat(caminho)
    except OSError as erro:
        raise erro_tipo("O documento do pacote está ausente ou é inválido.") from erro
    try:
        estado = _exigir_entrada_regular(caminho, diretorio=False)
        if not stat.S_ISREG(estado.st_mode) or estado.st_size > limite:
            raise OSError
        conteudo = caminho.read_bytes()
        estado_final = _exigir_entrada_regular(caminho, diretorio=False)
        if _identidade_entrada(estado) != _identidade_entrada(estado_final):
            raise OSError
        documento = json.loads(conteudo, object_pairs_hook=_objeto_sem_duplicatas)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as erro:
        raise erro_tipo("O documento do pacote está ausente ou é inválido.") from erro
    return documento, conteudo


def _identidade_entrada(estado: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        estado.st_dev,
        estado.st_ino,
        estado.st_size,
        estado.st_mtime_ns,
        estado.st_ctime_ns,
    )


def _objeto_sem_duplicatas(pares):
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError("Campo JSON duplicado.")
        resultado[chave] = valor
    return resultado


def _validar_raiz(raiz_pacote: str | Path) -> Path:
    try:
        informada = Path(os.path.abspath(os.fspath(Path(raiz_pacote).expanduser())))
        _exigir_entrada_regular(informada, diretorio=True)
        raiz = informada.resolve(strict=True)
        if not raiz.is_dir():
            raise OSError
    except (OSError, RuntimeError) as erro:
        raise IntegridadePacoteError("A raiz do pacote é inválida.") from erro
    return raiz


def _calcular_sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    try:
        with caminho.open("rb") as arquivo:
            while bloco := arquivo.read(TAMANHO_BLOCO_HASH):
                resumo.update(bloco)
    except OSError as erro:
        raise IntegridadePacoteError("Um arquivo do pacote não pôde ser lido.") from erro
    return resumo.hexdigest()


def _texto_valido(valor: object, padrao: re.Pattern[str]) -> bool:
    return isinstance(valor, str) and bool(padrao.fullmatch(valor))


def _plataforma_atual() -> str:
    return PLATAFORMA_WINDOWS if os.name == "nt" else os.name


def _arquitetura_atual() -> str:
    observada = platform.machine().casefold()
    return ARQUITETURA_X64 if observada in {"amd64", "x86_64"} else observada
