"""Preparação e auditoria reproduzível do empacotamento Windows T59."""

from __future__ import annotations

import argparse
from importlib import import_module
from importlib import metadata
from pathlib import Path
import re
import shutil
import sys
import time
from uuid import uuid4

from services.version_service import validar_metadados_build


DIRETORIOS_RUNTIME = (
    "database",
    "interface",
    "models",
    "repositories",
    "services",
    "utils",
)
COMPONENTES_PROIBIDOS = frozenset(
    {
        ".git",
        ".pytest_cache",
        "__pycache__",
        "backups",
        "data",
        "docs",
        "logs",
        "tests",
    }
)
SUFIXOS_PROIBIDOS = frozenset(
    {
        ".db",
        ".db-backup",
        ".db-bak",
        ".db-journal",
        ".db-shm",
        ".db-wal",
        ".env",
        ".key",
        ".log",
        ".p12",
        ".pem",
        ".pfx",
        ".pyc",
        ".sqlite",
        ".sqlite3",
        ".temp",
        ".tmp",
    }
)
DISTRIBUICOES_QT_RUNTIME = frozenset(
    {"pyside6-essentials", "shiboken6"}
)
MODULOS_QT_RUNTIME = (
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "shiboken6",
)


class EmpacotamentoInvalidoError(RuntimeError):
    pass


def validar_ambiente_build(caminho_requisitos: Path) -> None:
    """Valida o ambiente Windows usado pelo roteiro reproduzível do T59."""
    if sys.platform != "win32":
        raise EmpacotamentoInvalidoError("O build T59 exige Windows.")
    if sys.version_info[:2] != (3, 14):
        raise EmpacotamentoInvalidoError("O build T59 exige Python 3.14.")
    if sys.maxsize <= 2**32:
        raise EmpacotamentoInvalidoError(
            "O build T59 exige um interpretador Windows de 64 bits."
        )

    requisitos = caminho_requisitos.resolve(strict=True)
    divergencias = []
    versoes_fixadas = {}
    for numero, linha in enumerate(
        requisitos.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        conteudo = linha.strip()
        if not conteudo or conteudo.startswith("#"):
            continue
        if conteudo.count("==") != 1:
            raise EmpacotamentoInvalidoError(
                f"Requisito sem versão exata na linha {numero}."
            )
        nome, versao_esperada = (
            parte.strip() for parte in conteudo.split("==", maxsplit=1)
        )
        nome_normalizado = nome.casefold().replace("_", "-")
        versoes_fixadas[nome_normalizado] = versao_esperada
        try:
            versao_instalada = metadata.version(nome)
        except metadata.PackageNotFoundError:
            divergencias.append(f"{nome} ausente")
            continue
        if versao_instalada != versao_esperada:
            divergencias.append(
                f"{nome}={versao_instalada} (esperado {versao_esperada})"
            )
    if divergencias:
        raise EmpacotamentoInvalidoError(
            "Dependências de build divergentes: " + ", ".join(divergencias)
        )

    qt_ausentes = DISTRIBUICOES_QT_RUNTIME - versoes_fixadas.keys()
    if qt_ausentes:
        raise EmpacotamentoInvalidoError(
            "Contrato Qt incompleto em requirements-build.txt: "
            + ", ".join(sorted(qt_ausentes))
        )
    if (
        versoes_fixadas["pyside6-essentials"]
        != versoes_fixadas["shiboken6"]
    ):
        raise EmpacotamentoInvalidoError(
            "PySide6_Essentials e shiboken6 devem usar a mesma versão."
        )

    modulos_ausentes = []
    for nome_modulo in MODULOS_QT_RUNTIME:
        try:
            import_module(nome_modulo)
        except (ImportError, OSError):
            modulos_ausentes.append(nome_modulo)
    if modulos_ausentes:
        raise EmpacotamentoInvalidoError(
            "Módulos Qt indisponíveis: " + ", ".join(modulos_ausentes)
        )


def publicar_distribuicao(
    diretorio_candidato: Path,
    diretorio_publicado: Path,
) -> None:
    """Publica a candidata validada sem perder a distribuição anterior."""
    candidato = diretorio_candidato.resolve(strict=True)
    publicado = diretorio_publicado.absolute()
    if not candidato.is_dir():
        raise EmpacotamentoInvalidoError(
            "A distribuição candidata não é um diretório."
        )
    if candidato == publicado:
        raise EmpacotamentoInvalidoError(
            "A distribuição candidata deve estar isolada da publicada."
        )
    publicado.parent.mkdir(parents=True, exist_ok=True)
    anterior = publicado.with_name(
        f".{publicado.name}.anterior-{uuid4().hex}"
    )
    havia_anterior = publicado.exists()

    if havia_anterior:
        _substituir_diretorio(publicado, anterior)
    try:
        _substituir_diretorio(candidato, publicado)
    except BaseException:
        if havia_anterior and anterior.exists() and not publicado.exists():
            _substituir_diretorio(anterior, publicado)
        raise
    else:
        if anterior.exists():
            shutil.rmtree(anterior)


def _substituir_diretorio(origem: Path, destino: Path) -> None:
    tentativas = 10
    for tentativa in range(tentativas):
        try:
            origem.replace(destino)
            return
        except PermissionError:
            if tentativa == tentativas - 1:
                raise
            time.sleep(0.5)


def listar_fontes_runtime(raiz_projeto: Path) -> tuple[Path, ...]:
    raiz = raiz_projeto.resolve(strict=True)
    arquivos = [raiz / "main.py"]
    for nome_diretorio in DIRETORIOS_RUNTIME:
        diretorio = raiz / nome_diretorio
        if not diretorio.is_dir():
            raise EmpacotamentoInvalidoError(
                f"Diretório de runtime ausente: {nome_diretorio}."
            )
        arquivos.extend(diretorio.rglob("*.py"))
    fontes = tuple(sorted((item for item in arquivos if item.is_file())))
    if raiz / "main.py" not in fontes:
        raise EmpacotamentoInvalidoError("Ponto de entrada main.py ausente.")
    return fontes


def preparar_fontes_build(
    raiz_projeto: Path,
    diretorio_destino: Path,
    *,
    identificador_build: str | None,
    commit_git: str | None,
) -> tuple[Path, ...]:
    raiz = raiz_projeto.resolve(strict=True)
    destino = diretorio_destino.resolve(strict=True)
    if any(destino.iterdir()):
        raise EmpacotamentoInvalidoError(
            "O diretório temporário do build deve estar vazio."
        )
    build_id, commit = validar_metadados_build(
        identificador_build,
        commit_git,
    )
    copiados = []
    for origem in listar_fontes_runtime(raiz):
        relativo = origem.relative_to(raiz)
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)
        copiados.append(alvo)

    _incorporar_metadados(
        destino / "services" / "version_service.py",
        identificador_build=build_id,
        commit_git=commit,
    )
    validar_arvore_sem_dados(destino)
    return tuple(copiados)


def validar_arvore_sem_dados(raiz: Path) -> None:
    raiz_resolvida = raiz.resolve(strict=True)
    violacoes = []
    for caminho in raiz_resolvida.rglob("*"):
        relativo = caminho.relative_to(raiz_resolvida)
        componentes = {parte.casefold() for parte in relativo.parts}
        if componentes & COMPONENTES_PROIBIDOS:
            violacoes.append(str(relativo))
            continue
        if caminho.is_file() and _arquivo_proibido(caminho):
            violacoes.append(str(relativo))
    if violacoes:
        detalhe = ", ".join(sorted(violacoes)[:10])
        raise EmpacotamentoInvalidoError(
            f"A árvore contém arquivos proibidos: {detalhe}."
        )


def _arquivo_proibido(caminho: Path) -> bool:
    nome = caminho.name.casefold()
    return (
        nome == ".env"
        or nome.startswith(".env.")
        or nome.startswith("credentials.local.")
        or nome.startswith("secrets.local.")
        or any(nome.endswith(sufixo) for sufixo in SUFIXOS_PROIBIDOS)
    )


def _incorporar_metadados(
    caminho_version_service: Path,
    *,
    identificador_build: str | None,
    commit_git: str | None,
) -> None:
    conteudo = caminho_version_service.read_text(encoding="utf-8")
    substituicoes = (
        (
            r"^IDENTIFICADOR_BUILD_EMBUTIDO: str \| None = None$",
            "IDENTIFICADOR_BUILD_EMBUTIDO: str | None = "
            f"{identificador_build!r}",
        ),
        (
            r"^COMMIT_GIT_EMBUTIDO: str \| None = None$",
            f"COMMIT_GIT_EMBUTIDO: str | None = {commit_git!r}",
        ),
    )
    for padrao, substituto in substituicoes:
        conteudo, quantidade = re.subn(
            padrao,
            substituto,
            conteudo,
            count=1,
            flags=re.MULTILINE,
        )
        if quantidade != 1:
            raise EmpacotamentoInvalidoError(
                "O contrato de metadados T50 não pôde ser preparado."
            )
    caminho_version_service.write_text(conteudo, encoding="utf-8")


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    preparar = subcomandos.add_parser("preparar")
    preparar.add_argument("--origem", required=True, type=Path)
    preparar.add_argument("--destino", required=True, type=Path)
    preparar.add_argument("--build-id")
    preparar.add_argument("--commit")
    validar = subcomandos.add_parser("validar")
    validar.add_argument("--diretorio", required=True, type=Path)
    ambiente = subcomandos.add_parser("validar-ambiente")
    ambiente.add_argument("--requisitos", required=True, type=Path)
    publicar = subcomandos.add_parser("publicar")
    publicar.add_argument("--origem", required=True, type=Path)
    publicar.add_argument("--destino", required=True, type=Path)
    return parser


def main() -> int:
    argumentos = _criar_parser().parse_args()
    if argumentos.comando == "preparar":
        preparar_fontes_build(
            argumentos.origem,
            argumentos.destino,
            identificador_build=argumentos.build_id,
            commit_git=argumentos.commit,
        )
    elif argumentos.comando == "validar":
        validar_arvore_sem_dados(argumentos.diretorio)
    elif argumentos.comando == "validar-ambiente":
        validar_ambiente_build(argumentos.requisitos)
    else:
        publicar_distribuicao(argumentos.origem, argumentos.destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
