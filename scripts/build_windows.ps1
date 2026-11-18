[CmdletBinding()]
param(
    [string]$BuildId = $env:SISTEMA_PDV_BUILD_ID,
    [string]$CommitGit = $env:SISTEMA_PDV_COMMIT_GIT,
    [string]$ConfiguracaoManifesto,
    [string]$ChavePrivadaManifesto,
    [string]$ChaveIdManifesto,
    [switch]$PularSmokeTest
)

$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") {
    throw "O build T59 deve ser executado no Windows."
}

$RaizProjeto = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonComando = Get-Command python -CommandType Application |
    Select-Object -First 1
if (-not $PythonComando) {
    throw "Python não foi encontrado no PATH do ambiente de build."
}
$PythonExecutavel = $PythonComando.Source
$PythonPathAnterior = $env:PYTHONPATH
$PythonNoUserSiteAnterior = $env:PYTHONNOUSERSITE
$BuildStageAnterior = $env:SISTEMA_PDV_BUILD_STAGE
$env:PYTHONPATH = $RaizProjeto
$env:PYTHONNOUSERSITE = "1"
$DiretorioExecucao = $null
try {
$DiretorioBuild = Join-Path $RaizProjeto "build"
$IdExecucao = [guid]::NewGuid().ToString("N")
$DiretorioExecucao = Join-Path $DiretorioBuild "t59-$IdExecucao"
$DiretorioStage = Join-Path $DiretorioExecucao "staging"
$DiretorioWork = Join-Path $DiretorioExecucao "pyinstaller-work"
$DiretorioDistTemporario = Join-Path $DiretorioExecucao "distribuicao"
$DiretorioAplicacaoTemporaria = Join-Path `
    $DiretorioDistTemporario "Sistema-PDV"
$DiretorioDistPublicado = Join-Path $RaizProjeto "dist\windows"
$DiretorioAplicacaoPublicada = Join-Path `
    $DiretorioDistPublicado "Sistema-PDV"
$Spec = Join-Path $RaizProjeto "packaging\windows\Sistema-PDV.spec"
$RequisitosBuild = Join-Path $RaizProjeto "requirements-build.txt"

& $PythonExecutavel -m tools.empacotamento_windows validar-ambiente `
    --requisitos $RequisitosBuild
if ($LASTEXITCODE -ne 0) {
    throw "O interpretador ou as dependências de build são incompatíveis."
}
& $PythonExecutavel -m pip check
if ($LASTEXITCODE -ne 0) {
    throw "As dependências instaladas possuem conflitos."
}

if (-not $CommitGit) {
    try {
        $EstadoGit = @(& git -C $RaizProjeto status --porcelain 2>$null)
        if (
            $LASTEXITCODE -eq 0 -and
            [string]::IsNullOrWhiteSpace(($EstadoGit -join ""))
        ) {
            $CommitGit = (& git -C $RaizProjeto rev-parse HEAD 2>$null).Trim()
        }
        else {
            $CommitGit = $null
        }
    }
    catch {
        $CommitGit = $null
    }
}
if (-not $BuildId -and $CommitGit) {
    $BuildId = "win-$($CommitGit.Substring(0, 12))"
}

$CaminhoExecucaoCompleto = [IO.Path]::GetFullPath($DiretorioExecucao)
if (-not $CaminhoExecucaoCompleto.StartsWith(
    ([IO.Path]::GetFullPath($DiretorioBuild)) +
        [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Diretório temporário fora da raiz de build."
}
New-Item -ItemType Directory -Path $DiretorioStage -Force | Out-Null

$Preparar = @(
    "-m", "tools.empacotamento_windows", "preparar",
    "--origem", $RaizProjeto,
    "--destino", $DiretorioStage
)
if ($BuildId) {
    $Preparar += @("--build-id", $BuildId)
}
if ($CommitGit) {
    $Preparar += @("--commit", $CommitGit)
}
& $PythonExecutavel @Preparar
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao preparar a cópia temporária do build."
}

$env:SISTEMA_PDV_BUILD_STAGE = $DiretorioStage
& $PythonExecutavel -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $DiretorioDistTemporario `
    --workpath $DiretorioWork `
    $Spec
if ($LASTEXITCODE -ne 0) {
    throw "O PyInstaller não concluiu o empacotamento."
}

& $PythonExecutavel -m tools.empacotamento_windows validar `
    --diretorio $DiretorioAplicacaoTemporaria
if ($LASTEXITCODE -ne 0) {
    throw "A distribuição contém arquivos proibidos."
}

$Executavel = Join-Path $DiretorioAplicacaoTemporaria "Sistema-PDV.exe"
if (-not (Test-Path -LiteralPath $Executavel -PathType Leaf)) {
    throw "Sistema-PDV.exe não foi produzido."
}

if (-not $PularSmokeTest) {
    $RaizSmoke = Join-Path ([IO.Path]::GetTempPath()) (
        "Sistema-PDV-T59-" + [guid]::NewGuid().ToString("N")
    )
    New-Item -ItemType Directory -Path $RaizSmoke | Out-Null
    $LocalAppDataAnterior = $env:LOCALAPPDATA
    $QtAnterior = $env:QT_QPA_PLATFORM
    $SmokeBuildAnterior = $env:SISTEMA_PDV_SMOKE_BUILD_ID
    $SmokeCommitAnterior = $env:SISTEMA_PDV_SMOKE_COMMIT_GIT
    try {
        $env:LOCALAPPDATA = $RaizSmoke
        $env:QT_QPA_PLATFORM = "offscreen"
        $env:SISTEMA_PDV_SMOKE_BUILD_ID = $BuildId
        $env:SISTEMA_PDV_SMOKE_COMMIT_GIT = $CommitGit
        $ProcessoSmoke = Start-Process `
            -FilePath $Executavel `
            -ArgumentList "--t59-smoke-test" `
            -Wait `
            -PassThru `
            -WindowStyle Hidden
        if ($ProcessoSmoke.ExitCode -ne 0) {
            throw (
                "Smoke test do executável falhou com código " +
                "$($ProcessoSmoke.ExitCode)."
            )
        }
        $DadosCriados = Get-ChildItem -LiteralPath $RaizSmoke -Recurse -File
        if ($DadosCriados) {
            throw "O smoke test criou dados persistentes indevidamente."
        }
    }
    finally {
        $env:LOCALAPPDATA = $LocalAppDataAnterior
        $env:QT_QPA_PLATFORM = $QtAnterior
        Remove-Item -LiteralPath $RaizSmoke -Recurse -Force
        $env:SISTEMA_PDV_SMOKE_BUILD_ID = $SmokeBuildAnterior
        $env:SISTEMA_PDV_SMOKE_COMMIT_GIT = $SmokeCommitAnterior
    }
}

$Hash = (Get-FileHash -LiteralPath $Executavel -Algorithm SHA256).Hash.ToLower()
$VersaoAplicativo = (& $PythonExecutavel -c (
    "from services.version_service import VERSAO_APLICATIVO; " +
    "print(VERSAO_APLICATIVO)"
)).Trim()
$Relatorio = [ordered]@{
    aplicativo = "Sistema-PDV"
    versao_aplicativo = $VersaoAplicativo
    build_id = $(if ($BuildId) { $BuildId } else { $null })
    commit_git = $(if ($CommitGit) { $CommitGit } else { $null })
    executavel_sha256 = $Hash
    distribuicao = "Sistema-PDV"
}
$CaminhoRelatorio = Join-Path $DiretorioDistTemporario "build-report.json"
$ConteudoRelatorio = ($Relatorio | ConvertTo-Json) + [Environment]::NewLine
$Utf8SemBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($CaminhoRelatorio, $ConteudoRelatorio, $Utf8SemBom)

if ($ConfiguracaoManifesto) {
    $ConfiguracaoManifesto = (Resolve-Path `
        -LiteralPath $ConfiguracaoManifesto).Path
    & $PythonExecutavel -m tools.manifesto_pacote gerar `
        --raiz $DiretorioDistTemporario `
        --configuracao $ConfiguracaoManifesto
    if ($LASTEXITCODE -ne 0) {
        throw "O manifesto do pacote não pôde ser gerado ou auditado."
    }
    if ([bool]$ChavePrivadaManifesto -ne [bool]$ChaveIdManifesto) {
        throw "Chave privada e identificador da chave devem ser informados juntos."
    }
    if ($ChavePrivadaManifesto) {
        $ChavePrivadaManifesto = (Resolve-Path `
            -LiteralPath $ChavePrivadaManifesto).Path
        & $PythonExecutavel -m tools.manifesto_pacote assinar `
            --raiz $DiretorioDistTemporario `
            --chave-privada $ChavePrivadaManifesto `
            --chave-id $ChaveIdManifesto
        if ($LASTEXITCODE -ne 0) {
            throw "O manifesto do pacote não pôde ser assinado."
        }
    }
}
elseif ($ChavePrivadaManifesto -or $ChaveIdManifesto) {
    throw "A assinatura exige uma configuração explícita de manifesto."
}

& $PythonExecutavel -m tools.empacotamento_windows publicar `
    --origem $DiretorioDistTemporario `
    --destino $DiretorioDistPublicado
if ($LASTEXITCODE -ne 0) {
    throw "Não foi possível publicar a distribuição validada."
}
Write-Output "Distribuição criada em: $DiretorioAplicacaoPublicada"
}
finally {
    $env:PYTHONPATH = $PythonPathAnterior
    $env:PYTHONNOUSERSITE = $PythonNoUserSiteAnterior
    $env:SISTEMA_PDV_BUILD_STAGE = $BuildStageAnterior
    if ($DiretorioExecucao -and (Test-Path -LiteralPath $DiretorioExecucao)) {
        try {
            Remove-Item -LiteralPath $DiretorioExecucao -Recurse -Force
        }
        catch {
            Write-Warning (
                "Não foi possível limpar o diretório intermediário: $_"
            )
        }
    }
}
