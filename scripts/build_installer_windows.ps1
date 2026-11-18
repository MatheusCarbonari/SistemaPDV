[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") {
    throw "O instalador T60 deve ser compilado no Windows."
}

$RaizProjeto = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonComando = Get-Command python -CommandType Application |
    Select-Object -First 1
if (-not $PythonComando) {
    throw "Python não foi encontrado no PATH do ambiente de build."
}
$PythonExecutavel = $PythonComando.Source
$Distribuicao = Join-Path $RaizProjeto "dist\windows\Sistema-PDV"
$ScriptInno = Join-Path $RaizProjeto "installer\windows\Sistema-PDV.iss"
$Helper = Join-Path $RaizProjeto "installer\windows\provision_installation.ps1"
$DestinoPublicado = Join-Path $RaizProjeto "dist\installers"
$DiretorioBuild = Join-Path $RaizProjeto "build"
$DiretorioExecucao = Join-Path $DiretorioBuild (
    "t60-" + [guid]::NewGuid().ToString("N")
)
$Candidata = Join-Path $DiretorioExecucao "candidata"
$PythonPathAnterior = $env:PYTHONPATH
$PythonNoUserSiteAnterior = $env:PYTHONNOUSERSITE

function Resolve-InnoCompiler {
    $candidatos = @()
    if ($env:INNO_SETUP_ISCC) {
        $candidatos += $env:INNO_SETUP_ISCC
    }
    $comando = Get-Command ISCC.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($comando) {
        $candidatos += $comando.Source
    }
    $candidatos += @(
        (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe")
    )
    foreach ($candidato in $candidatos) {
        if ($candidato -and (Test-Path -LiteralPath $candidato -PathType Leaf)) {
            $versao = ((& $candidato --version 2>&1) | Out-String).Trim()
            if ($LASTEXITCODE -ne 0 -or $versao -notmatch '^7\.') {
                throw "O build exige Inno Setup 7 ou posterior."
            }
            return (Resolve-Path -LiteralPath $candidato).Path
        }
    }
    throw "ISCC.exe do Inno Setup 7 não foi encontrado."
}

try {
    $env:PYTHONPATH = $RaizProjeto
    $env:PYTHONNOUSERSITE = "1"
    & $PythonExecutavel -m tools.instalador_windows validar-fonte `
        --distribuicao $Distribuicao `
        --script $ScriptInno `
        --helper $Helper
    if ($LASTEXITCODE -ne 0) {
        throw "A distribuição T59 ou o contrato do instalador é inválido."
    }

    $ISCC = Resolve-InnoCompiler
    New-Item -ItemType Directory -Path $Candidata -Force | Out-Null
    $VersaoAplicativo = (& $PythonExecutavel -c (
        "from services.version_service import VERSAO_APLICATIVO; " +
        "print(VERSAO_APLICATIVO)"
    )).Trim()
    foreach ($AmbienteCodigo in @(1, 2)) {
        $Argumentos = @(
            "/Qp",
            "-DAmbienteCodigo=$AmbienteCodigo",
            ("-DSourceDir=" + $Distribuicao),
            ("-DOutputDir=" + $Candidata),
            ("-DAppVersion=" + $VersaoAplicativo),
            $ScriptInno
        )
        & $ISCC @Argumentos
        if ($LASTEXITCODE -ne 0) {
            throw "O Inno Setup não compilou o ambiente $AmbienteCodigo."
        }
    }

    & $PythonExecutavel -m tools.instalador_windows validar-saida `
        --diretorio $Candidata `
        --versao $VersaoAplicativo
    if ($LASTEXITCODE -ne 0) {
        throw "A saída compilada do instalador é inválida."
    }

    $Instaladores = Get-ChildItem -LiteralPath $Candidata -Filter "*.exe"
    $Relatorio = [ordered]@{
        aplicativo = "Sistema-PDV"
        versao_aplicativo = $VersaoAplicativo
        compilador = $ISCC
        instaladores = @(
            $Instaladores | ForEach-Object {
                [ordered]@{
                    arquivo = $_.Name
                    sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
                }
            }
        )
    }
    $Relatorio | ConvertTo-Json -Depth 4 | Set-Content `
        -LiteralPath (Join-Path $Candidata "installer-build-report.json") `
        -Encoding UTF8

    & $PythonExecutavel -m tools.empacotamento_windows publicar `
        --origem $Candidata `
        --destino $DestinoPublicado
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível publicar os instaladores validados."
    }
    Write-Output "Instaladores criados em: $DestinoPublicado"
}
finally {
    $env:PYTHONPATH = $PythonPathAnterior
    $env:PYTHONNOUSERSITE = $PythonNoUserSiteAnterior
    if (Test-Path -LiteralPath $DiretorioExecucao) {
        Remove-Item -LiteralPath $DiretorioExecucao -Recurse -Force
    }
}
