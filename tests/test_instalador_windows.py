from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

from services.contexto_instalacao_service import (
    AMBIENTE_HOMOLOGACAO_ID,
    AMBIENTE_PRODUCAO_ID,
    PRODUTO_ID,
)
from tools.empacotamento_windows import EmpacotamentoInvalidoError
from tools.instalador_windows import (
    validar_fonte_instalador,
    validar_saida_instalador,
)


RAIZ_PROJETO = Path(__file__).resolve().parent.parent
SCRIPT_INNO = RAIZ_PROJETO / "installer" / "windows" / "Sistema-PDV.iss"
HELPER = (
    RAIZ_PROJETO / "installer" / "windows" / "provision_installation.ps1"
)


def _criar_distribuicao_t59(raiz: Path) -> Path:
    distribuicao = raiz / "Sistema-PDV"
    (distribuicao / "_internal").mkdir(parents=True)
    (distribuicao / "Sistema-PDV.exe").write_bytes(b"executavel de teste")
    (distribuicao / "_internal" / "python314.dll").write_bytes(b"runtime")
    return distribuicao


def test_fonte_do_instalador_aceita_distribuicao_t59_sem_dados(tmp_path) -> None:
    distribuicao = _criar_distribuicao_t59(tmp_path)

    validar_fonte_instalador(distribuicao, SCRIPT_INNO, HELPER)


@pytest.mark.parametrize(
    "relativo",
    [
        "data/sistema_acougue.db",
        "logs/sistema-pdv.log",
        "backup/copia.db",
        "_internal/.env.production",
        "_internal/segredo.pfx",
    ],
)
def test_fonte_do_instalador_recusa_dados_operacionais(
    tmp_path,
    relativo,
) -> None:
    distribuicao = _criar_distribuicao_t59(tmp_path)
    proibido = distribuicao / relativo
    proibido.parent.mkdir(parents=True, exist_ok=True)
    proibido.write_bytes(b"nao incluir")

    with pytest.raises(EmpacotamentoInvalidoError):
        validar_fonte_instalador(distribuicao, SCRIPT_INNO, HELPER)


def test_script_inno_define_instalacoes_isoladas_e_sem_atualizacao() -> None:
    texto = SCRIPT_INNO.read_text(encoding="utf-8")

    assert '#define StableAppId "Sistema-PDV-Producao"' in texto
    assert '#define StableAppId "Sistema-PDV-Homologacao"' in texto
    assert "DefaultDirName={autopf}\\Sistema-PDV\\{#EnvironmentDir}" in texto
    assert "{commonappdata}\\Sistema-PDV\\{#EnvironmentDir}" in texto
    assert "UsePreviousAppDir=no" in texto
    assert "DisableDirPage=yes" in texto
    assert "PrivilegesRequired=admin" in texto
    assert "ArchitecturesAllowed=x64compatible" in texto
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in texto
    assert "Root: HKLM64" in texto
    assert "uninsdeletekey" in texto


def test_atalhos_e_desinstalacao_preservam_dados() -> None:
    texto = SCRIPT_INNO.read_text(encoding="utf-8")

    assert "{commonprograms}\\{#AppDisplayName}" in texto
    assert "{commondesktop}\\{#AppDisplayName}" in texto
    assert "Flags: unchecked" in texto
    assert "[UninstallDelete]" not in texto
    assert "[Run]" not in texto
    assert "CloseApplications=no" in texto
    assert "RestartApplications=no" in texto
    assert "InitializeUninstall" in texto


def test_provisionamento_publica_idle_somente_na_finalizacao() -> None:
    texto = HELPER.read_text(encoding="utf-8")
    inicio = texto.index('New-MaintenanceDocument $newId "INSTALLING"')
    descritor = texto.index("Write-NewUtf8Json $descriptorPath $descriptor")
    idle = texto.index('New-MaintenanceDocument $InstallationId "IDLE"')

    assert inicio < descritor < idle
    assert "RegistryView]::Registry64" in texto
    assert "Assert-NoExistingRegistry" in texto
    assert "Assert-NewInstallation" in texto
    assert "Assert-DirectoryContract" in texto
    assert "Get-CimInstance Win32_Process" in texto
    assert "OpenExisting($mutexName)" in texto
    assert "MutexOwnedByInstaller" in texto
    assert "Add-LocalGroupMember" not in texto
    assert "taskkill" not in texto.casefold()
    assert "Stop-Process" not in texto

    script_inno = SCRIPT_INNO.read_text(encoding="utf-8")
    assert "AcquireAdministrativeMutex" in script_inno
    assert "DeinitializeSetup" in script_inno
    assert "DeinitializeUninstall" in script_inno


def test_mutex_de_manutencao_tem_contrato_compartilhado_e_acl_administrativa(
) -> None:
    script_inno = SCRIPT_INNO.read_text(encoding="utf-8")

    assert f'#define ProductId "{PRODUTO_ID}"' in script_inno
    assert f'#define EnvironmentId "{AMBIENTE_PRODUCAO_ID}"' in script_inno
    assert f'#define EnvironmentId "{AMBIENTE_HOMOLOGACAO_ID}"' in script_inno
    assert (
        '#define AppMutexName "Global\\Sistema-PDV-" + ProductId + "-" + '
        "EnvironmentId"
    ) in script_inno
    assert "D:P(A;;GA;;;SY)(A;;GA;;;BA)" in script_inno
    assert script_inno.index("AcquireAdministrativeMutex") < script_inno.index(
        "RunHelper(\n    'begin'"
    )
    assert "AppMutex={#AppMutexName}" in script_inno
    assert "ReleaseAdministrativeMutex" in script_inno


def test_acls_protegem_manifestos_e_rejeitam_escrita_inesperada() -> None:
    texto = HELPER.read_text(encoding="utf-8")

    assert '@{ Path = $manifests; Rights = "ReadAndExecute" }' in texto
    assert texto.count(") $operatorsSid \"ReadAndExecute\" $false") >= 4
    assert texto.count('"manifests"') >= 2
    assert "Uma identidade não autorizada recebeu escrita em $path." in texto
    assert "Operadores receberam controle administrativo em $path." in texto
    assert '$sid -ne "S-1-5-18"' in texto
    assert '$sid -ne "S-1-5-32-544"' in texto
    assert "$sid -ne $operatorsSid.Value" in texto


def test_falha_apos_inicio_mantem_estado_restritivo() -> None:
    texto = HELPER.read_text(encoding="utf-8")
    installing = texto.index('New-MaintenanceDocument $newId "INSTALLING"')
    demais_diretorios = texto.index("foreach ($directoryContract")
    retorno_identidade = texto.index(
        "[IO.File]::WriteAllText($InstallationIdFile, $newId"
    )
    idle = texto.index('New-MaintenanceDocument $InstallationId "IDLE"')

    assert installing < demais_diretorios < retorno_identidade < idle


def test_auditoria_recusa_helper_sem_protecao_dos_manifestos(tmp_path) -> None:
    distribuicao = _criar_distribuicao_t59(tmp_path / "fonte")
    helper_incompleto = tmp_path / "provision_installation.ps1"
    helper_incompleto.write_text(
        HELPER.read_text(encoding="utf-8").replace(
            '@{ Path = $manifests; Rights = "ReadAndExecute" }',
            "",
        ),
        encoding="utf-8",
    )

    with pytest.raises(EmpacotamentoInvalidoError, match="incompleto"):
        validar_fonte_instalador(distribuicao, SCRIPT_INNO, helper_incompleto)


def test_auditoria_recusa_helper_sem_rejeicao_de_escrita_inesperada(
    tmp_path,
) -> None:
    distribuicao = _criar_distribuicao_t59(tmp_path / "fonte")
    helper_inseguro = tmp_path / "provision_installation.ps1"
    helper_inseguro.write_text(
        HELPER.read_text(encoding="utf-8").replace(
            "Uma identidade não autorizada recebeu escrita",
            "Permissão aceita",
        ),
        encoding="utf-8",
    )

    with pytest.raises(EmpacotamentoInvalidoError, match="incompleto"):
        validar_fonte_instalador(distribuicao, SCRIPT_INNO, helper_inseguro)


@pytest.mark.skipif(sys.platform != "win32", reason="contrato Windows")
def test_preflight_preserva_dados_existentes(tmp_path) -> None:
    powershell = Path(
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    )
    dados = tmp_path / "ProgramData" / "Sistema-PDV" / "Producao"
    dados.mkdir(parents=True)
    marcador = dados / "preservar.txt"
    marcador.write_text("dados existentes", encoding="utf-8")
    instalacao = tmp_path / "ProgramFiles" / "Sistema-PDV" / "Producao"
    executavel = instalacao / "Sistema-PDV.exe"

    resultado = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(HELPER),
            "-Mode",
            "preflight",
            "-Environment",
            "PRODUCAO",
            "-EnvironmentId",
            "58450fc4-001f-4ce0-b8d2-26c86f436322",
            "-InstallRoot",
            str(instalacao),
            "-ExecutablePath",
            str(executavel),
            "-ProgramDataRoot",
            str(dados),
            "-AppId",
            "Sistema-PDV-Producao",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resultado.returncode != 0
    assert marcador.read_text(encoding="utf-8") == "dados existentes"
    assert not instalacao.exists()


def test_roteiro_compila_em_diretorio_isolado_e_publica_ao_final() -> None:
    texto = (
        RAIZ_PROJETO / "scripts" / "build_installer_windows.ps1"
    ).read_text(encoding="utf-8")

    assert '"t60-" + [guid]::NewGuid()' in texto
    assert "validar-fonte" in texto
    assert "validar-saida" in texto
    assert "Inno Setup 7" in texto
    assert "tools.empacotamento_windows publicar" in texto
    assert texto.index("validar-saida") < texto.index(
        "tools.empacotamento_windows publicar"
    )


def test_saida_exige_os_dois_instaladores_e_nenhum_extra(tmp_path) -> None:
    for ambiente in ("Producao", "Homologacao"):
        (tmp_path / f"Sistema-PDV-{ambiente}-0.1.0-Setup.exe").write_bytes(
            b"setup"
        )

    saida = validar_saida_instalador(tmp_path)

    assert len(saida) == 2
    (tmp_path / "inesperado.txt").write_text("x", encoding="utf-8")
    with pytest.raises(EmpacotamentoInvalidoError):
        validar_saida_instalador(tmp_path)


@pytest.mark.skipif(sys.platform != "win32", reason="contrato Windows")
def test_helper_powershell_possui_sintaxe_valida() -> None:
    powershell = Path(
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    )
    comando = (
        "$tokens=$null;$errors=$null;"
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{HELPER}',[ref]$tokens,[ref]$errors)|Out-Null;"
        "if($errors.Count){$errors|ForEach-Object{Write-Error $_.Message};exit 1}"
    )

    resultado = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", comando],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resultado.returncode == 0, resultado.stderr


def _localizar_iscc_7() -> Path | None:
    localizado = shutil.which("ISCC.exe")
    candidatos = [
        Path(os.environ["INNO_SETUP_ISCC"])
        if os.environ.get("INNO_SETUP_ISCC")
        else None,
        Path(localizado) if localizado else None,
        Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe"),
    ]
    return next((item for item in candidatos if item and item.is_file()), None)


@pytest.mark.skipif(_localizar_iscc_7() is None, reason="Inno Setup 7 ausente")
def test_script_inno_compila_para_os_dois_ambientes(tmp_path) -> None:
    distribuicao = _criar_distribuicao_t59(tmp_path / "fonte")
    saida = tmp_path / "saida"
    saida.mkdir()
    iscc = _localizar_iscc_7()
    assert iscc is not None

    for codigo in (1, 2):
        resultado = subprocess.run(
            [
                str(iscc),
                "/Qp",
                f"-DAmbienteCodigo={codigo}",
                f"-DSourceDir={distribuicao}",
                f"-DOutputDir={saida}",
                "-DAppVersion=0.1.0",
                str(SCRIPT_INNO),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert resultado.returncode == 0, resultado.stdout + resultado.stderr

    validar_saida_instalador(saida)
