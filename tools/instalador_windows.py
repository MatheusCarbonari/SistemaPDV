"""Auditoria reproduzível das entradas e saídas do instalador Windows T60."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.empacotamento_windows import (
    EmpacotamentoInvalidoError,
    validar_arvore_sem_dados,
)


AMBIENTES = ("Producao", "Homologacao")


def validar_fonte_instalador(
    distribuicao: Path,
    script_inno: Path,
    helper: Path,
) -> None:
    distribuicao = distribuicao.resolve(strict=True)
    validar_arvore_sem_dados(distribuicao)
    executavel = distribuicao / "Sistema-PDV.exe"
    if not executavel.is_file():
        raise EmpacotamentoInvalidoError(
            "A distribuição T59 não contém Sistema-PDV.exe."
        )
    if any(item.is_symlink() for item in distribuicao.rglob("*")):
        raise EmpacotamentoInvalidoError(
            "A distribuição T59 contém links não permitidos."
        )
    texto_inno = script_inno.resolve(strict=True).read_text(encoding="utf-8")
    texto_helper = helper.resolve(strict=True).read_text(encoding="utf-8")
    exigidos_inno = (
        "PrivilegesRequired=admin",
        "ArchitecturesAllowed=x64compatible",
        "AppMutex={#AppMutexName}",
        "CloseApplications=no",
        "Root: HKLM64",
        "uninsdeletekey",
        "InitializeUninstall",
        "PrepareToInstall",
        "CurStepChanged",
        "D:P(A;;GA;;;SY)(A;;GA;;;BA)",
        "AcquireAdministrativeMutex",
        "ReleaseAdministrativeMutex",
    )
    exigidos_helper = (
        '"preflight", "begin", "finalize", "check-running"',
        "RegistryView]::Registry64",
        'New-MaintenanceDocument $newId "INSTALLING"',
        'New-MaintenanceDocument $InstallationId "IDLE"',
        "Assert-DirectoryContract",
        "Assert-NotRunning",
        '@{ Path = $manifests; Rights = "ReadAndExecute" }',
        "Uma identidade não autorizada recebeu escrita",
        "Operadores receberam controle administrativo",
    )
    ausentes = [item for item in exigidos_inno if item not in texto_inno]
    ausentes += [item for item in exigidos_helper if item not in texto_helper]
    if ausentes:
        raise EmpacotamentoInvalidoError(
            "O contrato do instalador está incompleto: " + ", ".join(ausentes)
        )
    marcos_helper = (
        'New-MaintenanceDocument $newId "INSTALLING"',
        "foreach ($directoryContract",
        "[IO.File]::WriteAllText($InstallationIdFile, $newId",
        'New-MaintenanceDocument $InstallationId "IDLE"',
    )
    if [texto_helper.index(item) for item in marcos_helper] != sorted(
        texto_helper.index(item) for item in marcos_helper
    ):
        raise EmpacotamentoInvalidoError(
            "O estado restritivo não precede as demais etapas do provisionamento."
        )
    aquisicao = texto_inno.index("if not AcquireAdministrativeMutex() then")
    inicio = texto_inno.index("RunHelper(\n    'begin'")
    if aquisicao >= inicio:
        raise EmpacotamentoInvalidoError(
            "O mutex de manutenção deve preceder o provisionamento."
        )
    proibidos = (
        "taskkill",
        "Stop-Process",
        "runascurrentuser",
    )
    combinado = f"{texto_inno}\n{texto_helper}".casefold()
    encontrados = [item for item in proibidos if item.casefold() in combinado]
    if encontrados:
        raise EmpacotamentoInvalidoError(
            "O instalador contém operações proibidas: " + ", ".join(encontrados)
        )


def validar_saida_instalador(
    diretorio: Path,
    versao_aplicativo: str = "0.1.0",
) -> tuple[Path, ...]:
    raiz = diretorio.resolve(strict=True)
    instaladores = tuple(sorted(raiz.glob("Sistema-PDV-*-Setup.exe")))
    if not instaladores:
        raise EmpacotamentoInvalidoError("Nenhum instalador foi produzido.")
    nomes_esperados = {
        f"Sistema-PDV-{ambiente}-{versao_aplicativo}-Setup.exe"
        for ambiente in AMBIENTES
    }
    if {item.name for item in instaladores} != nomes_esperados:
        raise EmpacotamentoInvalidoError(
            "A saída não contém exatamente os instaladores dos dois ambientes."
        )
    for item in raiz.iterdir():
        if item not in instaladores or not item.is_file() or item.stat().st_size == 0:
            raise EmpacotamentoInvalidoError(
                "A saída temporária do instalador contém artefatos inesperados."
            )
    return instaladores


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    comandos = parser.add_subparsers(dest="comando", required=True)
    fonte = comandos.add_parser("validar-fonte")
    fonte.add_argument("--distribuicao", type=Path, required=True)
    fonte.add_argument("--script", type=Path, required=True)
    fonte.add_argument("--helper", type=Path, required=True)
    saida = comandos.add_parser("validar-saida")
    saida.add_argument("--diretorio", type=Path, required=True)
    saida.add_argument("--versao", required=True)
    return parser


def main() -> int:
    argumentos = _criar_parser().parse_args()
    if argumentos.comando == "validar-fonte":
        validar_fonte_instalador(
            argumentos.distribuicao,
            argumentos.script,
            argumentos.helper,
        )
    else:
        validar_saida_instalador(argumentos.diretorio, argumentos.versao)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
