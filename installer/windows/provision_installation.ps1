[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("preflight", "begin", "finalize", "check-running")]
    [string]$Mode,
    [Parameter(Mandatory = $true)]
    [ValidateSet("PRODUCAO", "HOMOLOGACAO")]
    [string]$Environment,
    [Parameter(Mandatory = $true)]
    [string]$EnvironmentId,
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,
    [Parameter(Mandatory = $true)]
    [string]$ProgramDataRoot,
    [Parameter(Mandatory = $true)]
    [string]$AppId,
    [string]$InstallationId,
    [string]$InstallationIdFile,
    [switch]$MutexOwnedByInstaller
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$ProductId = "62d747d5-49e6-47f8-9371-a8377c5857e2"
$ProductionId = "58450fc4-001f-4ce0-b8d2-26c86f436322"
$HomologationId = "296d11ce-5363-45c1-8254-838b393b70e0"
$OperatorsGroup = "Sistema-PDV-Operadores"
$RegistryBase = "SOFTWARE\Sistema-PDV\Installations"
$Utf8NoBom = [Text.UTF8Encoding]::new($false)

function Assert-ContractArguments {
    $expected = if ($Environment -eq "PRODUCAO") {
        $ProductionId
    }
    else {
        $HomologationId
    }
    if ($EnvironmentId -ne $expected) {
        throw "O identificador do ambiente não corresponde ao contrato T60-B."
    }
    foreach ($path in @($InstallRoot, $ExecutablePath, $ProgramDataRoot)) {
        if ($path -notmatch '^(?:[A-Za-z]:\\|\\\\[^\\]+\\[^\\]+\\)') {
            throw "Os caminhos administrativos devem ser absolutos."
        }
    }
}

function Open-LocalMachine64([bool]$writable) {
    return [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        [Microsoft.Win32.RegistryView]::Registry64
    )
}

function Get-RegistryText($key, [string]$name) {
    $value = $key.GetValue(
        $name,
        $null,
        [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
    )
    if ($null -eq $value -or $value -isnot [string] -or $value.Length -eq 0) {
        throw "O registro administrativo existente está parcialmente provisionado."
    }
    return $value
}

function Assert-NoExistingRegistry {
    $hklm = Open-LocalMachine64 $false
    try {
        $base = $hklm.OpenSubKey($RegistryBase, $false)
        if ($null -ne $base) {
            try {
                foreach ($name in $base.GetSubKeyNames()) {
                    $key = $base.OpenSubKey($name, $false)
                    try {
                        $product = Get-RegistryText $key "ProductId"
                        $environmentFound = Get-RegistryText $key "Environment"
                        $environmentIdFound = Get-RegistryText $key "EnvironmentId"
                        $installationFound = Get-RegistryText $key "InstallationId"
                        $null = Get-RegistryText $key "InstallRoot"
                        $null = Get-RegistryText $key "ExecutablePath"
                        $expectedOther = if ($environmentFound -eq "PRODUCAO") {
                            $ProductionId
                        }
                        elseif ($environmentFound -eq "HOMOLOGACAO") {
                            $HomologationId
                        }
                        else {
                            throw "Existe um registro administrativo de ambiente desconhecido."
                        }
                        if (
                            $product -ne $ProductId -or
                            $environmentIdFound -ne $expectedOther -or
                            ([guid]::ParseExact($installationFound, "D").ToString("D") -ne
                                $installationFound)
                        ) {
                            throw "Existe um registro administrativo divergente."
                        }
                        if ($environmentFound -eq $Environment) {
                            throw "Já existe uma instalação registrada para este ambiente."
                        }
                    }
                    finally {
                        if ($null -ne $key) { $key.Dispose() }
                    }
                }
            }
            finally {
                $base.Dispose()
            }
        }

        $uninstallPath = (
            "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\" +
            $AppId + "_is1"
        )
        $uninstallKey = $hklm.OpenSubKey($uninstallPath, $false)
        if ($null -ne $uninstallKey) {
            $uninstallKey.Dispose()
            throw "O Windows já registra este ambiente como instalado."
        }
    }
    finally {
        $hklm.Dispose()
    }
}

function Assert-NoProcessRunning {
    try {
        $processes = Get-CimInstance Win32_Process -Filter "Name='Sistema-PDV.exe'"
    }
    catch {
        throw "Não foi possível verificar os processos do Sistema-PDV."
    }
    foreach ($process in $processes) {
        if (
            $process.ExecutablePath -and
            [string]::Equals(
                [IO.Path]::GetFullPath($process.ExecutablePath),
                [IO.Path]::GetFullPath($ExecutablePath),
                [StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw "O executável desta instalação ainda está em execução."
        }
    }
}

function Assert-NotRunning {
    if (-not $MutexOwnedByInstaller) {
        $mutexName = "Global\Sistema-PDV-$ProductId-$EnvironmentId"
        $mutex = $null
        try {
            $mutex = [Threading.Mutex]::OpenExisting($mutexName)
        }
        catch [Threading.WaitHandleCannotBeOpenedException] {
            $mutex = $null
        }
        catch {
            throw "Não foi possível validar o mutex do ambiente com segurança."
        }
        if ($null -ne $mutex) {
            $mutex.Dispose()
            throw "O Sistema-PDV deste ambiente está em execução."
        }
    }
    Assert-NoProcessRunning
}

function Assert-NewInstallation {
    Assert-NoExistingRegistry
    Assert-NotRunning
    if (Test-Path -LiteralPath $InstallRoot) {
        throw "O diretório comercial do aplicativo já existe."
    }
    if (Test-Path -LiteralPath $ProgramDataRoot) {
        throw "O diretório comercial de dados já existe e exige manutenção."
    }
}

function Get-OperatorsSid([bool]$create) {
    $groupPath = "WinNT://$env:COMPUTERNAME/$OperatorsGroup,group"
    try {
        $group = [ADSI]$groupPath
        $null = $group.psbase.NativeObject
    }
    catch {
        if (-not $create) {
            throw "O grupo local de operadores não está disponível."
        }
        $computer = [ADSI]("WinNT://$env:COMPUTERNAME,computer")
        $group = $computer.Create("group", $OperatorsGroup)
        $group.SetInfo()
        $group.Description = "Contas autorizadas a operar o Sistema-PDV"
        $group.SetInfo()
    }
    return [Security.Principal.NTAccount]::new(
        $env:COMPUTERNAME,
        $OperatorsGroup
    ).Translate([Security.Principal.SecurityIdentifier])
}

function New-AccessRule(
    [Security.Principal.IdentityReference]$identity,
    [Security.AccessControl.FileSystemRights]$rights
) {
    return [Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        $rights,
        (
            [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
            [Security.AccessControl.InheritanceFlags]::ObjectInherit
        ),
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-DirectoryContract(
    [string]$path,
    [Security.Principal.SecurityIdentifier]$operatorsSid,
    [Security.AccessControl.FileSystemRights]$operatorRights
) {
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $systemSid = [Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $acl.AddAccessRule((New-AccessRule $systemSid "FullControl"))
    $acl.AddAccessRule((New-AccessRule $adminsSid "FullControl"))
    $acl.AddAccessRule((New-AccessRule $operatorsSid $operatorRights))
    Set-Acl -LiteralPath $path -AclObject $acl
}

function Assert-DirectoryContract(
    [string]$path,
    [Security.Principal.SecurityIdentifier]$operatorsSid,
    [Security.AccessControl.FileSystemRights]$requiredRights,
    [bool]$allowOperatorWrite
) {
    $acl = Get-Acl -LiteralPath $path
    if (-not $acl.AreAccessRulesProtected) {
        throw "A ACL obrigatória não está protegida em $path."
    }
    $operatorRule = $false
    $systemRule = $false
    $administratorsRule = $false
    $writeMask = (
        [Security.AccessControl.FileSystemRights]::WriteData -bor
        [Security.AccessControl.FileSystemRights]::AppendData -bor
        [Security.AccessControl.FileSystemRights]::WriteAttributes -bor
        [Security.AccessControl.FileSystemRights]::WriteExtendedAttributes -bor
        [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
        [Security.AccessControl.FileSystemRights]::Delete -bor
        [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [Security.AccessControl.FileSystemRights]::TakeOwnership
    )
    $operatorForbiddenMask = (
        [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [Security.AccessControl.FileSystemRights]::TakeOwnership
    )
    foreach ($rule in $acl.Access) {
        $sid = $rule.IdentityReference.Translate(
            [Security.Principal.SecurityIdentifier]
        ).Value
        if (
            $rule.AccessControlType -eq
                [Security.AccessControl.AccessControlType]::Allow -and
            $sid -eq $operatorsSid.Value -and
            (($rule.FileSystemRights -band $requiredRights) -eq $requiredRights)
        ) {
            $operatorRule = $true
            if (
                -not $allowOperatorWrite -and
                (($rule.FileSystemRights -band $writeMask) -ne 0)
            ) {
                throw "Operadores receberam escrita administrativa indevida."
            }
        }
        if (
            $rule.AccessControlType -eq
                [Security.AccessControl.AccessControlType]::Allow -and
            $sid -eq "S-1-5-18" -and
            (($rule.FileSystemRights -band
                [Security.AccessControl.FileSystemRights]::FullControl) -eq
                [Security.AccessControl.FileSystemRights]::FullControl)
        ) {
            $systemRule = $true
        }
        if (
            $rule.AccessControlType -eq
                [Security.AccessControl.AccessControlType]::Allow -and
            $sid -eq "S-1-5-32-544" -and
            (($rule.FileSystemRights -band
                [Security.AccessControl.FileSystemRights]::FullControl) -eq
                [Security.AccessControl.FileSystemRights]::FullControl)
        ) {
            $administratorsRule = $true
        }
        if (
            $rule.AccessControlType -eq
                [Security.AccessControl.AccessControlType]::Allow -and
            (($rule.FileSystemRights -band $writeMask) -ne 0) -and
            $sid -ne "S-1-5-18" -and
            $sid -ne "S-1-5-32-544" -and
            ($sid -ne $operatorsSid.Value -or -not $allowOperatorWrite)
        ) {
            throw "Uma identidade não autorizada recebeu escrita em $path."
        }
        if (
            $rule.AccessControlType -eq
                [Security.AccessControl.AccessControlType]::Allow -and
            $sid -eq $operatorsSid.Value -and
            (($rule.FileSystemRights -band $operatorForbiddenMask) -ne 0)
        ) {
            throw "Operadores receberam controle administrativo em $path."
        }
    }
    if (-not $operatorRule) {
        throw "A ACL obrigatória dos operadores não foi comprovada em $path."
    }
    if (-not $systemRule -or -not $administratorsRule) {
        throw "A ACL administrativa obrigatória não foi comprovada em $path."
    }
}

function Write-NewUtf8Json([string]$path, $document) {
    $temporary = "$path.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        [IO.File]::WriteAllText(
            $temporary,
            ($document | ConvertTo-Json -Compress),
            $Utf8NoBom
        )
        [IO.File]::Move($temporary, $path)
    }
    finally {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
    }
}

function Replace-Utf8Json([string]$path, $document) {
    $temporary = "$path.$([guid]::NewGuid().ToString('N')).tmp"
    try {
        [IO.File]::WriteAllText(
            $temporary,
            ($document | ConvertTo-Json -Compress),
            $Utf8NoBom
        )
        [IO.File]::Replace($temporary, $path, $null)
    }
    finally {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
    }
}

function New-MaintenanceDocument([string]$installation, [string]$status) {
    return [ordered]@{
        contract_version = 1
        product_id = $ProductId
        environment_id = $EnvironmentId
        installation_id = $installation
        status = $status
    }
}

function Start-Provisioning {
    Assert-NewInstallation
    if (-not $InstallationIdFile) {
        throw "O instalador não informou o arquivo de retorno da identidade."
    }
    $newId = [guid]::NewGuid().ToString("D")
    $operatorsSid = Get-OperatorsSid $true
    $data = Join-Path $ProgramDataRoot "data"
    $logs = Join-Path $ProgramDataRoot "logs"
    $config = Join-Path $ProgramDataRoot "config"
    $administrative = Join-Path $ProgramDataRoot "administrative"
    $manifests = Join-Path $administrative "manifests"
    $maintenance = Join-Path $ProgramDataRoot "maintenance"
    New-Item -ItemType Directory -Path $ProgramDataRoot -ErrorAction Stop |
        Out-Null
    Set-DirectoryContract $ProgramDataRoot $operatorsSid "ReadAndExecute"
    New-Item -ItemType Directory -Path $maintenance -ErrorAction Stop |
        Out-Null
    Set-DirectoryContract $maintenance $operatorsSid "ReadAndExecute"
    Write-NewUtf8Json (
        Join-Path $maintenance "state.json"
    ) (New-MaintenanceDocument $newId "INSTALLING")

    foreach ($directoryContract in @(
        [pscustomobject]@{ Path = $data; Rights = "Modify" },
        [pscustomobject]@{ Path = $logs; Rights = "Modify" },
        [pscustomobject]@{ Path = $config; Rights = "ReadAndExecute" },
        [pscustomobject]@{ Path = $administrative; Rights = "ReadAndExecute" },
        [pscustomobject]@{ Path = $manifests; Rights = "ReadAndExecute" }
    )) {
        $directory = $directoryContract.Path
        $rights = $directoryContract.Rights
        New-Item -ItemType Directory -Path $directory -ErrorAction Stop |
            Out-Null
        Set-DirectoryContract $directory $operatorsSid $rights
    }
    Assert-DirectoryContract $data $operatorsSid "Modify" $true
    Assert-DirectoryContract $logs $operatorsSid "Modify" $true
    Assert-DirectoryContract $ProgramDataRoot $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract $config $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract $administrative $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract $manifests $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract $maintenance $operatorsSid "ReadAndExecute" $false
    [IO.File]::WriteAllText($InstallationIdFile, $newId, $Utf8NoBom)
}

function Assert-RegistryIdentity([string]$installation) {
    $hklm = Open-LocalMachine64 $false
    try {
        $key = $hklm.OpenSubKey("$RegistryBase\$installation", $false)
        if ($null -eq $key) {
            throw "A identidade HKLM não foi publicada."
        }
        try {
            $expected = [ordered]@{
                ProductId = $ProductId
                Environment = $Environment
                EnvironmentId = $EnvironmentId
                InstallationId = $installation
                InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
                ExecutablePath = [IO.Path]::GetFullPath($ExecutablePath)
            }
            foreach ($item in $expected.GetEnumerator()) {
                if ((Get-RegistryText $key $item.Key) -ne $item.Value) {
                    throw "A identidade HKLM diverge do provisionamento."
                }
            }
        }
        finally {
            $key.Dispose()
        }
    }
    finally {
        $hklm.Dispose()
    }
}

function Complete-Provisioning {
    $normalizedId = [guid]::ParseExact($InstallationId, "D").ToString("D")
    if ($normalizedId -ne $InstallationId) {
        throw "O GUID da instalação não está normalizado."
    }
    Assert-NotRunning
    if (-not (Test-Path -LiteralPath $ExecutablePath -PathType Leaf)) {
        throw "O executável principal não foi instalado."
    }
    Assert-RegistryIdentity $InstallationId
    $operatorsSid = Get-OperatorsSid $false
    Assert-DirectoryContract (
        Join-Path $ProgramDataRoot "data"
    ) $operatorsSid "Modify" $true
    Assert-DirectoryContract (
        Join-Path $ProgramDataRoot "logs"
    ) $operatorsSid "Modify" $true
    Assert-DirectoryContract $ProgramDataRoot $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract (
        Join-Path $ProgramDataRoot "config"
    ) $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract (
        Join-Path $ProgramDataRoot "administrative"
    ) $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract (
        Join-Path (
            Join-Path $ProgramDataRoot "administrative"
        ) "manifests"
    ) $operatorsSid "ReadAndExecute" $false
    Assert-DirectoryContract (
        Join-Path $ProgramDataRoot "maintenance"
    ) $operatorsSid "ReadAndExecute" $false

    $descriptorPath = Join-Path (
        Join-Path $ProgramDataRoot "administrative"
    ) "installation.json"
    $descriptor = [ordered]@{
        contract_version = 1
        product_id = $ProductId
        environment = $Environment
        environment_id = $EnvironmentId
        installation_id = $InstallationId
        install_root = [IO.Path]::GetFullPath($InstallRoot)
        executable_path = [IO.Path]::GetFullPath($ExecutablePath)
    }
    Write-NewUtf8Json $descriptorPath $descriptor

    $statePath = Join-Path (
        Join-Path $ProgramDataRoot "maintenance"
    ) "state.json"
    $currentState = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    if (
        $currentState.installation_id -ne $InstallationId -or
        $currentState.status -ne "INSTALLING"
    ) {
        throw "O estado de provisionamento não permite publicar IDLE."
    }
    Replace-Utf8Json $statePath (
        New-MaintenanceDocument $InstallationId "IDLE"
    )
}

Assert-ContractArguments
switch ($Mode) {
    "preflight" { Assert-NewInstallation }
    "begin" { Start-Provisioning }
    "finalize" { Complete-Provisioning }
    "check-running" { Assert-NotRunning }
}
