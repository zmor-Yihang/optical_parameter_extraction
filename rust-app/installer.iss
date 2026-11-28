; Rust edition: independent from the legacy Python edition and its update channel.
#define MyAppName "THzLab"
#define MyAppExeName "thz-analyzer-rust.exe"
#ifndef RustVersion
  #define RustVersion "1.3.3"
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
