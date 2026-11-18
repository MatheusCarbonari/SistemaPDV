"""Identidade e caminhos confiáveis da instalação Windows do Sistema-PDV."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
import json
import os
from pathlib import Path
import sys
from typing import Protocol
from uuid import UUID


PRODUTO_ID = "62d747d5-49e6-47f8-9371-a8377c5857e2"
AMBIENTE_PRODUCAO_ID = "58450fc4-001f-4ce0-b8d2-26c86f436322"
AMBIENTE_HOMOLOGACAO_ID = "296d11ce-5363-45c1-8254-838b393b70e0"
GRUPO_OPERADORES = "Sistema-PDV-Operadores"
CONTRATO_IDENTIDADE_VERSAO = 1
CONTRATO_MANUTENCAO_VERSAO = 1
STATUS_MANUTENCAO_LIVRE = "IDLE"
CHAVE_REGISTRO_INSTALACOES = r"SOFTWARE\Sistema-PDV\Installations"
NOME_ARQUIVO_BANCO = "sistema_acougue.db"
NOME_ARQUIVO_IDENTIDADE = "installation.json"
NOME_ARQUIVO_ESTADO_MANUTENCAO = "state.json"
TAMANHO_MAXIMO_DESCRITOR = 32 * 1024
RAIZ_REPOSITORIO = Path(__file__).resolve().parent.parent


class ContextoInstalacaoError(RuntimeError):
    pass


class IdentidadeInstalacaoAusenteError(ContextoInstalacaoError):
    pass


class IdentidadeInstalacaoDivergenteError(ContextoInstalacaoError):
    pass


class EstadoManutencaoInvalidoError(ContextoInstalacaoError):
    pass


class AmbienteInstalacao(str, Enum):
    DESENVOLVIMENTO = "DESENVOLVIMENTO"
    PRODUCAO = "PRODUCAO"
    HOMOLOGACAO = "HOMOLOGACAO"


_IDENTIDADES_AMBIENTE = {
    AmbienteInstalacao.PRODUCAO: AMBIENTE_PRODUCAO_ID,
    AmbienteInstalacao.HOMOLOGACAO: AMBIENTE_HOMOLOGACAO_ID,
}
_DIRETORIOS_AMBIENTE = {
    AmbienteInstalacao.PRODUCAO: "Producao",
    AmbienteInstalacao.HOMOLOGACAO: "Homologacao",
}


@dataclass(frozen=True, slots=True)
class CaminhosInstalacao:
    raiz_ambiente: Path
    dados: Path
    banco: Path
    logs: Path
    configuracao: Path
    administrativo: Path
    descritor_identidade: Path
    manifestos: Path
    manutencao: Path
    estado_manutencao: Path


@dataclass(frozen=True, slots=True)
class ContextoInstalacao:
    produto_id: str
    ambiente: AmbienteInstalacao
    ambiente_id: str
    instalacao_id: str | None
    comercial: bool
    caminho_executavel: Path
    raiz_instalacao: Path
    caminhos: CaminhosInstalacao


@dataclass(frozen=True, slots=True)
class ContratoAclInstalacao:
    grupo_operadores: str
    gravacao_operacional: tuple[Path, ...]
    leitura_operacional: tuple[Path, ...]
    controle_administrativo: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class RegistroInstalacao:
    produto_id: str
    ambiente: str
    ambiente_id: str
    instalacao_id: str
    raiz_instalacao: str
    caminho_executavel: str


class ProvedorRegistroInstalacao(Protocol):
    def listar_instalacoes(self) -> tuple[RegistroInstalacao, ...]: ...


class ProvedorRegistroWindows:
    """Lê somente a identidade administrativa em HKLM, visão de 64 bits."""

    def listar_instalacoes(self) -> tuple[RegistroInstalacao, ...]:
        if sys.platform != "win32":
            return ()
        import winreg

        acesso = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        try:
            raiz = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                CHAVE_REGISTRO_INSTALACOES,
                0,
                acesso,
            )
        except FileNotFoundError:
            return ()
        except OSError as erro:
            raise IdentidadeInstalacaoAusenteError(
                "A identidade administrativa da instalação não está acessível."
            ) from erro

        registros = []
        with raiz:
            indice = 0
            while True:
                try:
                    nome_subchave = winreg.EnumKey(raiz, indice)
                except OSError:
                    break
                indice += 1
                try:
                    with winreg.OpenKey(raiz, nome_subchave, 0, acesso) as chave:
                        registros.append(
                            RegistroInstalacao(
                                produto_id=_ler_valor_registro(chave, "ProductId"),
                                ambiente=_ler_valor_registro(chave, "Environment"),
                                ambiente_id=_ler_valor_registro(
                                    chave, "EnvironmentId"
                                ),
                                instalacao_id=_ler_valor_registro(
                                    chave, "InstallationId"
                                ),
                                raiz_instalacao=_ler_valor_registro(
                                    chave, "InstallRoot"
                                ),
                                caminho_executavel=_ler_valor_registro(
                                    chave, "ExecutablePath"
                                ),
                            )
                        )
                except (FileNotFoundError, OSError, TypeError):
                    continue
        return tuple(registros)


def _ler_valor_registro(chave, nome: str) -> str:
    import winreg

    valor, tipo = winreg.QueryValueEx(chave, nome)
    if tipo != winreg.REG_SZ or not isinstance(valor, str):
        raise TypeError("Valor de registro inválido.")
    return valor


def execucao_empacotada() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


@lru_cache(maxsize=1)
def obter_contexto_instalacao() -> ContextoInstalacao:
    return resolver_contexto_instalacao()


def obter_local_app_data_confiavel() -> Path:
    """Resolve LocalAppData pela Known Folder API, sem aceitar redirecionamento."""
    return _obter_pasta_conhecida(
        "f1b32785-6fba-4fcf-9d55-7b8e7f157091",
        "LocalAppData",
    )


def resolver_contexto_instalacao(
    *,
    empacotado: bool | None = None,
    caminho_executavel: str | Path | None = None,
    provedor_registro: ProvedorRegistroInstalacao | None = None,
    program_data: str | Path | None = None,
    program_files: str | Path | None = None,
    raiz_repositorio: str | Path = RAIZ_REPOSITORIO,
) -> ContextoInstalacao:
    congelado = execucao_empacotada() if empacotado is None else empacotado
    executavel = Path(caminho_executavel or sys.executable).resolve(strict=False)
    if not congelado:
        return _criar_contexto_desenvolvimento(
            Path(raiz_repositorio).resolve(strict=False),
            executavel,
        )

    if sys.platform != "win32":
        raise IdentidadeInstalacaoAusenteError(
            "A instalação comercial exige o contrato de identidade do Windows."
        )
    provedor = provedor_registro or ProvedorRegistroWindows()
    registros = tuple(
        registro
        for registro in provedor.listar_instalacoes()
        if _caminhos_equivalentes(registro.caminho_executavel, executavel)
    )
    if len(registros) != 1:
        raise IdentidadeInstalacaoAusenteError(
            "A execução comercial não possui uma identidade administrativa única."
        )
    return _validar_contexto_comercial(
        registros[0],
        executavel,
        (
            Path(program_data)
            if program_data is not None
            else _obter_pasta_conhecida(
                "62ab5d82-fdc1-4dc3-a9dd-070d1d495d97",
                "ProgramData",
            )
        ),
        (
            Path(program_files)
            if program_files is not None
            else _obter_pasta_conhecida(
                "905e63b6-c1bf-494e-b29c-65b732d3d21a",
                "Program Files",
            )
        ),
    )


def _criar_contexto_desenvolvimento(
    raiz: Path,
    executavel: Path,
) -> ContextoInstalacao:
    dados = raiz / "data"
    local_app_data = os.environ.get("LOCALAPPDATA")
    logs = (
        Path(local_app_data) / "Sistema-PDV" / "logs"
        if local_app_data
        else Path.home() / ".local" / "state" / "Sistema-PDV" / "logs"
    )
    caminhos = CaminhosInstalacao(
        raiz_ambiente=raiz,
        dados=dados,
        banco=dados / NOME_ARQUIVO_BANCO,
        logs=logs,
        configuracao=raiz / "config",
        administrativo=raiz,
        descritor_identidade=raiz / NOME_ARQUIVO_IDENTIDADE,
        manifestos=raiz / "packaging",
        manutencao=raiz / "build" / "maintenance",
        estado_manutencao=raiz / "build" / "maintenance" / NOME_ARQUIVO_ESTADO_MANUTENCAO,
    )
    return ContextoInstalacao(
        produto_id=PRODUTO_ID,
        ambiente=AmbienteInstalacao.DESENVOLVIMENTO,
        ambiente_id="DESENVOLVIMENTO",
        instalacao_id=None,
        comercial=False,
        caminho_executavel=executavel,
        raiz_instalacao=raiz,
        caminhos=caminhos,
    )


def _validar_contexto_comercial(
    registro: RegistroInstalacao,
    executavel: Path,
    program_data: Path,
    program_files: Path,
) -> ContextoInstalacao:
    try:
        ambiente = AmbienteInstalacao(registro.ambiente)
    except ValueError as erro:
        raise IdentidadeInstalacaoDivergenteError(
            "O ambiente registrado para a instalação é inválido."
        ) from erro
    if ambiente not in _IDENTIDADES_AMBIENTE:
        raise IdentidadeInstalacaoDivergenteError(
            "A execução comercial não pode usar o contexto de desenvolvimento."
        )
    esperado_ambiente_id = _IDENTIDADES_AMBIENTE[ambiente]
    if registro.produto_id != PRODUTO_ID or registro.ambiente_id != esperado_ambiente_id:
        raise IdentidadeInstalacaoDivergenteError(
            "A identidade do produto ou do ambiente é divergente."
        )
    instalacao_id = _normalizar_uuid(registro.instalacao_id, "instalação")
    raiz_instalacao = Path(registro.raiz_instalacao).resolve(strict=False)
    if (
        not raiz_instalacao.is_absolute()
        or not _esta_sob_raiz(executavel, raiz_instalacao)
        or not _esta_sob_raiz(
            raiz_instalacao,
            program_files.resolve(strict=False),
        )
    ):
        raise IdentidadeInstalacaoDivergenteError(
            "O executável não pertence à raiz comercial registrada."
        )

    raiz_ambiente = (
        program_data.resolve(strict=False)
        / "Sistema-PDV"
        / _DIRETORIOS_AMBIENTE[ambiente]
    )
    administrativo = raiz_ambiente / "administrative"
    manutencao = raiz_ambiente / "maintenance"
    dados = raiz_ambiente / "data"
    caminhos = CaminhosInstalacao(
        raiz_ambiente=raiz_ambiente,
        dados=dados,
        banco=dados / NOME_ARQUIVO_BANCO,
        logs=raiz_ambiente / "logs",
        configuracao=raiz_ambiente / "config",
        administrativo=administrativo,
        descritor_identidade=administrativo / NOME_ARQUIVO_IDENTIDADE,
        manifestos=administrativo / "manifests",
        manutencao=manutencao,
        estado_manutencao=manutencao / NOME_ARQUIVO_ESTADO_MANUTENCAO,
    )
    contexto = ContextoInstalacao(
        produto_id=PRODUTO_ID,
        ambiente=ambiente,
        ambiente_id=esperado_ambiente_id,
        instalacao_id=instalacao_id,
        comercial=True,
        caminho_executavel=executavel,
        raiz_instalacao=raiz_instalacao,
        caminhos=caminhos,
    )
    _validar_descritor_identidade(contexto)
    return contexto


def _validar_descritor_identidade(contexto: ContextoInstalacao) -> None:
    documento = _ler_json_administrativo(
        contexto.caminhos.descritor_identidade,
        "descritor de instalação",
    )
    campos = {
        "contract_version",
        "product_id",
        "environment",
        "environment_id",
        "installation_id",
        "install_root",
        "executable_path",
    }
    identidade_divergente = (
        set(documento) != campos
        or documento.get("contract_version") != CONTRATO_IDENTIDADE_VERSAO
        or documento.get("product_id") != contexto.produto_id
        or documento.get("environment") != contexto.ambiente.value
        or documento.get("environment_id") != contexto.ambiente_id
        or documento.get("installation_id") != contexto.instalacao_id
        or not _caminhos_equivalentes(
            documento.get("install_root", ""),
            contexto.raiz_instalacao,
        )
        or not _caminhos_equivalentes(
            documento.get("executable_path", ""),
            contexto.caminho_executavel,
        )
    )
    if identidade_divergente:
        raise IdentidadeInstalacaoDivergenteError(
            "O registro e o descritor administrativo da instalação divergem."
        )


def verificar_estado_manutencao(contexto: ContextoInstalacao) -> None:
    if not contexto.comercial:
        return
    try:
        documento = _ler_json_administrativo(
            contexto.caminhos.estado_manutencao,
            "estado de manutenção",
        )
    except ContextoInstalacaoError as erro:
        raise EstadoManutencaoInvalidoError(
            "A instalação não possui um estado de manutenção confiável."
        ) from erro
    if (
        documento.get("contract_version") != CONTRATO_MANUTENCAO_VERSAO
        or documento.get("product_id") != contexto.produto_id
        or documento.get("environment_id") != contexto.ambiente_id
        or documento.get("installation_id") != contexto.instalacao_id
        or documento.get("status") != STATUS_MANUTENCAO_LIVRE
    ):
        raise EstadoManutencaoInvalidoError(
            "A instalação possui estado de manutenção ausente, desconhecido ou incompleto."
        )


def obter_contrato_acl(contexto: ContextoInstalacao) -> ContratoAclInstalacao:
    if not contexto.comercial:
        return ContratoAclInstalacao(GRUPO_OPERADORES, (), (), ())
    return ContratoAclInstalacao(
        grupo_operadores=GRUPO_OPERADORES,
        gravacao_operacional=(contexto.caminhos.dados, contexto.caminhos.logs),
        leitura_operacional=(
            contexto.caminhos.configuracao,
            contexto.caminhos.administrativo,
            contexto.caminhos.manutencao,
        ),
        controle_administrativo=(
            contexto.caminhos.configuracao,
            contexto.caminhos.administrativo,
            contexto.caminhos.manutencao,
        ),
    )


def _ler_json_administrativo(caminho: Path, descricao: str) -> dict:
    try:
        if caminho.is_symlink() or not caminho.is_file():
            raise OSError
        if caminho.stat().st_size > TAMANHO_MAXIMO_DESCRITOR:
            raise OSError
        documento = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as erro:
        raise IdentidadeInstalacaoAusenteError(
            f"O {descricao} não está disponível ou é inválido."
        ) from erro
    if not isinstance(documento, dict):
        raise IdentidadeInstalacaoDivergenteError(
            f"O {descricao} não possui um objeto JSON válido."
        )
    return documento


def _normalizar_uuid(valor: str, descricao: str) -> str:
    try:
        normalizado = str(UUID(valor))
    except (ValueError, TypeError, AttributeError) as erro:
        raise IdentidadeInstalacaoDivergenteError(
            f"O identificador da {descricao} é inválido."
        ) from erro
    if valor != normalizado:
        raise IdentidadeInstalacaoDivergenteError(
            f"O identificador da {descricao} não está normalizado."
        )
    return normalizado


def _caminhos_equivalentes(caminho_a: str | Path, caminho_b: str | Path) -> bool:
    try:
        a = Path(caminho_a).resolve(strict=False)
        b = Path(caminho_b).resolve(strict=False)
    except (OSError, RuntimeError, TypeError):
        return False
    if os.path.normcase(str(a)) == os.path.normcase(str(b)):
        return True
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _esta_sob_raiz(caminho: Path, raiz: Path) -> bool:
    try:
        caminho.relative_to(raiz)
        return True
    except ValueError:
        return False


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _obter_pasta_conhecida(identificador_textual: str, descricao: str) -> Path:
    if sys.platform != "win32":
        raise IdentidadeInstalacaoAusenteError(
            f"A pasta conhecida {descricao} não está disponível."
        )
    identificador = UUID(identificador_textual)
    guid = _GUID(
        identificador.time_low,
        identificador.time_mid,
        identificador.time_hi_version,
        (ctypes.c_ubyte * 8)(*identificador.bytes[8:]),
    )
    caminho = ctypes.c_wchar_p()
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    shell32.SHGetKnownFolderPath.argtypes = (
        ctypes.POINTER(_GUID),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    )
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = (wintypes.LPVOID,)
    ole32.CoTaskMemFree.restype = None
    resultado = shell32.SHGetKnownFolderPath(
        ctypes.byref(guid),
        0,
        None,
        ctypes.byref(caminho),
    )
    if resultado != 0 or not caminho.value:
        raise IdentidadeInstalacaoAusenteError(
            f"A pasta conhecida {descricao} não pôde ser resolvida."
        )
    try:
        return Path(caminho.value).resolve(strict=False)
    finally:
        ole32.CoTaskMemFree(ctypes.cast(caminho, wintypes.LPVOID))
