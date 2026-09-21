; installer.iss
; Inno Setup 脚本：将 PyInstaller 生成的 onedir 程序封装为 install.exe
; 编译前请先运行 build_installer.ps1 生成 output\THzAnalyzer\*
; 使用方式：用 Inno Setup Compiler 打开本文件编译，或直接运行 build_installer.ps1

#define MyAppName "Thz Analyzer"
; 版本号由 build_installer.ps1 从 config/release.json 读取并以 /D 参数注入
#ifndef MyAppVersion
#define MyAppVersion "1.1.0"
#endif
#define MyAppPublisher "THz"
#define MyAppExeName "THzAnalyzer.exe"
#define MyAppIcon "app.ico"
#define SourceDir "output\THzAnalyzer"

[Setup]
; 卸载标识（GUID 固定，升级时保持不变即可）
AppId={{8F3A2C51-7B9E-4D6E-9A1C-2E5F8B0D3A77}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; 安装到用户目录，无需管理员权限，程序可正常写入 thz_config.json 与 logs/
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer-output
OutputBaseFilename=install
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
; 覆盖前自动关闭正在运行的程序（配合在线更新流程，升级更顺畅）
CloseApplications=yes
RestartApplications=no

[Languages]
; 简体中文语言文件需要单独下载（Inno Setup 6 默认不附带）。
; 若未安装该文件，此段自动跳过，安装向导回退为英文界面。
; 下载地址：https://jrsoftware.org/files/istrans/ChineseSimplified.isl
;   放到 Inno Setup 安装目录的 Languages\ 下即可。
#ifexist "compiler:Languages\ChineseSimplified.isl"
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif

[Files]
; Excludes 兜底排除运行时产物（即使未通过 build_installer.ps1 清理也安全）
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "logs\*,thz_config.json"

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent
