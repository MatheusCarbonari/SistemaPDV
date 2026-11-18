#ifndef AmbienteCodigo
  #define AmbienteCodigo "1"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\windows\Sistema-PDV"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist\installers"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define ProductId "62d747d5-49e6-47f8-9371-a8377c5857e2"

#if AmbienteCodigo == "1"
  #define Environment "PRODUCAO"
  #define EnvironmentId "58450fc4-001f-4ce0-b8d2-26c86f436322"
  #define EnvironmentDir "Producao"
  #define EnvironmentDisplay "Produção"
  #define StableAppId "Sistema-PDV-Producao"
#elif AmbienteCodigo == "2"
  #define Environment "HOMOLOGACAO"
  #define EnvironmentId "296d11ce-5363-45c1-8254-838b393b70e0"
  #define EnvironmentDir "Homologacao"
  #define EnvironmentDisplay "Homologação"
  #define StableAppId "Sistema-PDV-Homologacao"
#else
  #error AmbienteCodigo deve ser 1 (Produção) ou 2 (Homologação)
#endif

#define AppDisplayName "Sistema-PDV - " + EnvironmentDisplay
#define AppMutexName "Global\Sistema-PDV-" + ProductId + "-" + EnvironmentId

[Setup]
AppId={#StableAppId}
AppName={#AppDisplayName}
AppVersion={#AppVersion}
AppPublisher=Sistema-PDV
DefaultDirName={autopf}\Sistema-PDV\{#EnvironmentDir}
DefaultGroupName={#AppDisplayName}
DisableDirPage=yes
DisableProgramGroupPage=yes
UsePreviousAppDir=no
UsePreviousGroup=no
UsePreviousTasks=no
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename=Sistema-PDV-{#EnvironmentDir}-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
Uninstallable=yes
UninstallDisplayName={#AppDisplayName}
UninstallDisplayIcon={app}\Sistema-PDV.exe
CreateUninstallRegKey=yes
AppMutex={#AppMutexName}
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: unchecked

[Files]
Source: "provision_installation.ps1"; Flags: dontcopy noencryption
Source: "provision_installation.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKLM64; Subkey: "SOFTWARE\Sistema-PDV\Installations\{code:GetInstallationId}"; ValueType: string; ValueName: "ProductId"; ValueData: "{#ProductId}"; Flags: uninsdeletekey
Root: HKLM64; Subkey: "SOFTWARE\Sistema-PDV\Installations\{code:GetInstallationId}"; ValueType: string; ValueName: "Environment"; ValueData: "{#Environment}"
Root: HKLM64; Subkey: "SOFTWARE\Sistema-PDV\Installations\{code:GetInstallationId}"; ValueType: string; ValueName: "EnvironmentId"; ValueData: "{#EnvironmentId}"
Root: HKLM64; Subkey: "SOFTWARE\Sistema-PDV\Installations\{code:GetInstallationId}"; ValueType: string; ValueName: "InstallationId"; ValueData: "{code:GetInstallationId}"
Root: HKLM64; Subkey: "SOFTWARE\Sistema-PDV\Installations\{code:GetInstallationId}"; ValueType: string; ValueName: "InstallRoot"; ValueData: "{app}"
Root: HKLM64; Subkey: "SOFTWARE\Sistema-PDV\Installations\{code:GetInstallationId}"; ValueType: string; ValueName: "ExecutablePath"; ValueData: "{app}\Sistema-PDV.exe"

[Icons]
Name: "{commonprograms}\{#AppDisplayName}"; Filename: "{app}\Sistema-PDV.exe"; WorkingDir: "{app}"
Name: "{commondesktop}\{#AppDisplayName}"; Filename: "{app}\Sistema-PDV.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Code]
type
  TSecurityAttributes = record
    Length: LongWord;
    SecurityDescriptor: LongWord;
    InheritHandle: LongWord;
  end;

var
  InstallationId: String;
  ProvisioningStarted: Boolean;
  AdministrativeMutex: THandle;

const
  ERROR_ALREADY_EXISTS = 183;

function CreateMutex(
  var MutexAttributes: TSecurityAttributes;
  InitialOwner: Boolean;
  Name: String
): THandle;
  external 'CreateMutexW@kernel32.dll stdcall';
function ReleaseMutex(Mutex: THandle): Boolean;
  external 'ReleaseMutex@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';
function GetLastError(): LongWord;
  external 'GetLastError@kernel32.dll stdcall';
function ConvertStringSecurityDescriptorToSecurityDescriptor(
  StringSecurityDescriptor: String;
  StringSDRevision: LongWord;
  var SecurityDescriptor: LongWord;
  var SecurityDescriptorSize: LongWord
): Boolean;
  external 'ConvertStringSecurityDescriptorToSecurityDescriptorW@advapi32.dll stdcall';
function LocalFree(Memory: LongWord): LongWord;
  external 'LocalFree@kernel32.dll stdcall';

function QuoteArgument(const Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '"', '\"', True);
  Result := '"' + Result + '"';
end;

function PowerShellPath(): String;
begin
  Result := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
end;

function HelperPath(const Uninstalling: Boolean): String;
begin
  if Uninstalling then
    Result := ExpandConstant('{app}\installer\provision_installation.ps1')
  else
    Result := ExpandConstant('{tmp}\provision_installation.ps1');
end;

function CommonHelperArguments(const Mode: String; const Uninstalling: Boolean): String;
begin
  Result :=
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ' +
    QuoteArgument(HelperPath(Uninstalling)) +
    ' -Mode ' + QuoteArgument(Mode) +
    ' -Environment ' + QuoteArgument('{#Environment}') +
    ' -EnvironmentId ' + QuoteArgument('{#EnvironmentId}') +
    ' -InstallRoot ' + QuoteArgument(ExpandConstant('{app}')) +
    ' -ExecutablePath ' + QuoteArgument(ExpandConstant('{app}\Sistema-PDV.exe')) +
    ' -ProgramDataRoot ' +
      QuoteArgument(ExpandConstant('{commonappdata}\Sistema-PDV\{#EnvironmentDir}')) +
    ' -AppId ' + QuoteArgument('{#StableAppId}');
end;

function RunHelper(
  const Mode: String;
  const ExtraArguments: String;
  const Uninstalling: Boolean;
  var ResultCode: Integer
): Boolean;
var
  Arguments: String;
begin
  Arguments := CommonHelperArguments(Mode, Uninstalling);
  if ExtraArguments <> '' then
    Arguments := Arguments + ' ' + ExtraArguments;
  Result := Exec(
    PowerShellPath(),
    Arguments,
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Result := Result and (ResultCode = 0);
end;

function AcquireAdministrativeMutex(): Boolean;
var
  LastError: LongWord;
  SecurityAttributes: TSecurityAttributes;
  SecurityDescriptor: LongWord;
  SecurityDescriptorSize: LongWord;
begin
  Result := False;
  if AdministrativeMutex <> 0 then
  begin
    Result := True;
    Exit;
  end;
  SecurityDescriptor := 0;
  SecurityDescriptorSize := 0;
  if not ConvertStringSecurityDescriptorToSecurityDescriptor(
    'D:P(A;;GA;;;SY)(A;;GA;;;BA)',
    1,
    SecurityDescriptor,
    SecurityDescriptorSize
  ) then
    Exit;
  SecurityAttributes.Length := SizeOf(SecurityAttributes);
  SecurityAttributes.SecurityDescriptor := SecurityDescriptor;
  SecurityAttributes.InheritHandle := 0;
  AdministrativeMutex := CreateMutex(
    SecurityAttributes,
    True,
    '{#AppMutexName}'
  );
  LastError := GetLastError();
  LocalFree(SecurityDescriptor);
  if AdministrativeMutex = 0 then
    Exit;
  if LastError = ERROR_ALREADY_EXISTS then
  begin
    CloseHandle(AdministrativeMutex);
    AdministrativeMutex := 0;
    Exit;
  end;
  Result := True;
end;

procedure ReleaseAdministrativeMutex();
begin
  if AdministrativeMutex <> 0 then
  begin
    ReleaseMutex(AdministrativeMutex);
    CloseHandle(AdministrativeMutex);
    AdministrativeMutex := 0;
  end;
end;

function GetInstallationId(Param: String): String;
begin
  Result := InstallationId;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  IdFile: String;
  IdContent: AnsiString;
  ExpectedDir: String;
begin
  Result := '';
  ExpectedDir := ExpandConstant('{autopf}\Sistema-PDV\{#EnvironmentDir}');
  if CompareText(ExpandConstant('{app}'), ExpectedDir) <> 0 then
  begin
    Result := 'O diretório comercial é fixo e não pode ser redirecionado.';
    Exit;
  end;
  if ProvisioningStarted then
    Exit;

  ExtractTemporaryFile('provision_installation.ps1');
  if not RunHelper('preflight', '', False, ResultCode) then
  begin
    Result := 'A pré-validação recusou a instalação inicial. ' +
      'Nenhum dado existente será sobrescrito.';
    Exit;
  end;

  if not AcquireAdministrativeMutex() then
  begin
    Result := 'O ambiente ficou ocupado antes do provisionamento. ' +
      'Feche o Sistema-PDV e tente novamente.';
    Exit;
  end;

  IdFile := ExpandConstant('{tmp}\installation-id.txt');
  if not RunHelper(
    'begin',
    '-InstallationIdFile ' + QuoteArgument(IdFile) +
      ' -MutexOwnedByInstaller',
    False,
    ResultCode
  ) then
  begin
    Result := 'O provisionamento administrativo falhou. A instalação ' +
      'permanece bloqueada para manutenção.';
    Exit;
  end;
  if not LoadStringFromFile(IdFile, IdContent) then
  begin
    Result := 'O GUID da instalação não pôde ser recuperado.';
    Exit;
  end;
  InstallationId := Trim(String(IdContent));
  if Length(InstallationId) <> 36 then
  begin
    Result := 'O GUID da instalação possui formato inválido.';
    Exit;
  end;
  ProvisioningStarted := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not RunHelper(
      'finalize',
      '-InstallationId ' + QuoteArgument(InstallationId) +
        ' -MutexOwnedByInstaller',
      False,
      ResultCode
    ) then
      RaiseException(
        'A validação final falhou. O estado IDLE não foi publicado e a ' +
        'instalação exige manutenção.'
      );
  end;
end;

procedure DeinitializeSetup();
begin
  ReleaseAdministrativeMutex();
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if not FileExists(HelperPath(True)) then
  begin
    MsgBox(
      'O componente de validação da desinstalação está ausente. ' +
      'A remoção foi bloqueada.',
      mbError,
      MB_OK
    );
    Exit;
  end;
  if not AcquireAdministrativeMutex() then
  begin
    MsgBox(
      'O Sistema-PDV deste ambiente está em execução. Feche-o antes de ' +
      'desinstalar.',
      mbError,
      MB_OK
    );
    Exit;
  end;
  if not RunHelper(
    'check-running',
    '-MutexOwnedByInstaller',
    True,
    ResultCode
  ) then
  begin
    ReleaseAdministrativeMutex();
    MsgBox(
      'Feche o Sistema-PDV deste ambiente antes de desinstalar. ' +
      'Nenhum processo será encerrado à força.',
      mbError,
      MB_OK
    );
    Exit;
  end;
  Result := True;
end;

procedure DeinitializeUninstall();
begin
  ReleaseAdministrativeMutex();
end;
