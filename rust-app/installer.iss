; THzLab uses its own install directory and replaces registered legacy Python installations.
#define LegacyUninstallKey "Software\Microsoft\Windows\CurrentVersion\Uninstall\{8F3A2C51-7B9E-4D6E-9A1C-2E5F8B0D3A77}_is1"
#define MyAppName "THzLab"
#define MyAppExeName "thz-analyzer-rust.exe"
#ifndef RustVersion
  #define RustVersion "1.3.4"
#endif
#ifndef RustExePath
  #define RustExePath "target\release\" + MyAppExeName
#endif

[Setup]
AppId={{9D2C61B8-D128-47F5-84C1-DB7A5FF711B0}
AppName={#MyAppName}
AppVersion={#RustVersion}
VersionInfoVersion={#RustVersion}.0
AppPublisher=NUAA THz Group
DefaultDirName={localappdata}\THz Analyzer Rust
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=dist
OutputBaseFilename=THzAnalyzer-Rust-{#RustVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#ifexist "compiler:Languages\ChineseSimplified.isl"
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"

[Files]
Source: "{#RustExePath}"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion
; Covers the inherited icon assets. A Rust dependency notice manifest can be
; supplied independently before external distribution.
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
#ifdef RustNoticesPath
Source: "{#RustNoticesPath}"; DestDir: "{app}"; DestName: "RUST_DEPENDENCY_NOTICES.txt"; Flags: ignoreversion
#endif

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[CustomMessages]
LegacyUninstallFailed=THzLab is installed, but the previous Python version could not be removed automatically. You can uninstall Thz Analyzer from Windows Settings.
#ifexist "compiler:Languages\ChineseSimplified.isl"
chinesesimp.LegacyUninstallFailed=THzLab 已安装，但未能自动卸载旧 Python 版。可在 Windows 设置中手动卸载 Thz Analyzer。
#endif

[Code]
function RemoveLegacyInstall: Boolean;
var
  LegacyDir, Uninstaller, Name, NewDir: String;
  ExitCode, I: Integer;
begin
  Result := True;
  { The legacy installer is per-user and uses Inno Setup's 32-bit registry view. }
  if not RegKeyExists(HKCU32, '{#LegacyUninstallKey}') then
    Exit;

  Result := False;
  if not RegQueryStringValue(HKCU32, '{#LegacyUninstallKey}', 'InstallLocation', LegacyDir) or
     not RegQueryStringValue(HKCU32, '{#LegacyUninstallKey}', 'UninstallString', Uninstaller) then
    Exit;
  Uninstaller := RemoveQuotes(Trim(Uninstaller));
  LegacyDir := AddBackslash(LegacyDir);
  NewDir := AddBackslash(ExpandConstant('{app}'));
  Name := Lowercase(ExtractFileName(Uninstaller));

  { Run only the registered Inno uninstaller, never a shell command or arbitrary arguments. }
  if (CompareText(AddBackslash(ExtractFileDir(Uninstaller)), LegacyDir) <> 0) or
     (Length(Name) <> 12) or (Copy(Name, 1, 5) <> 'unins') or
     (Copy(Name, 9, 4) <> '.exe') or
     (CompareText(Copy(NewDir, 1, Length(LegacyDir)), LegacyDir) = 0) or
     not FileExists(Uninstaller) then
    Exit;
  for I := 6 to 8 do
    if (Name[I] < '0') or (Name[I] > '9') then
      Exit;

  Log('Removing registered legacy Python installation: ' + LegacyDir);
  if Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', LegacyDir,
          SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    Result := (ExitCode = 0) and not RegKeyExists(HKCU32, '{#LegacyUninstallKey}');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if not RemoveLegacyInstall then
    begin
      Log(CustomMessage('LegacyUninstallFailed'));
      if not WizardSilent then
        MsgBox(CustomMessage('LegacyUninstallFailed'), mbInformation, MB_OK);
    end;
end;
