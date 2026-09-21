# build_installer.ps1
# 一键构建 THzAnalyzer 安装包，并生成发布所需的 version.json
# 依赖：
#   1. Python 3.13 + uv（项目依赖已通过 uv sync 安装）
#   2. Inno Setup 6（安装：winget install JRSoftware.InnoSetup）
#
# 产物（均在 installer-output\ 下）：
#   1. install.exe    —— 安装程序
#   2. version.json   —— GitHub Releases 更新源文件（含版本号、下载地址、SHA256）
#
# 用法：
#   .\build_installer.ps1
#   .\build_installer.ps1 -Changelog "- 新增 xxx;- 修复 xxx"
# 不传 -Changelog 时，会沿用上一次 version.json 中同版本的更新说明（若有）。
#
# 版本号唯一来源：config\release.json（会同步写入 pyproject.toml）

param(
    [string]$Changelog = ""
)

$ErrorActionPreference = "Stop"

# 切换到脚本所在目录，保证 main.py / installer.iss 等相对路径始终正确
Set-Location $PSScriptRoot

$AppName = "THzAnalyzer"
$OutputDir = "output"          # PyInstaller onedir 输出目录
$InstallerDir = "installer-output"
$ReleaseConfigPath = "config\release.json"

Write-Host "=== 1/5 读取发布配置并同步版本号 ===" -ForegroundColor Cyan
if (-not (Test-Path $ReleaseConfigPath)) {
    throw "未找到发布配置: $ReleaseConfigPath"
}
$releaseConfig = Get-Content $ReleaseConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$appVersion = [string]$releaseConfig.version
if (-not $appVersion) { throw "config/release.json 缺少 version 字段" }
if ($appVersion -notmatch '^\d+\.\d+\.\d+') {
    throw "config/release.json 的 version 必须为 X.Y.Z 格式，当前: $appVersion"
}

$pyprojectPath = Join-Path $PSScriptRoot "pyproject.toml"
$pyproject = [System.IO.File]::ReadAllText($pyprojectPath)
$updatedPyproject = [regex]::Replace(
    $pyproject,
    '(?m)^version\s*=\s*"[^"]+"',
    "version = `"$appVersion`""
)
if ($updatedPyproject -eq $pyproject -and $pyproject -notmatch ('(?m)^version\s*=\s*"' + [regex]::Escape($appVersion) + '"')) {
    throw "无法在 pyproject.toml 中定位 version 字段"
}
if ($updatedPyproject -ne $pyproject) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($pyprojectPath, $updatedPyproject, $utf8NoBom)
    Write-Host "已同步 pyproject.toml version = $appVersion" -ForegroundColor DarkGray
}
Write-Host "安装包版本: v$appVersion" -ForegroundColor Cyan

Write-Host "=== 2/5 清理旧构建产物 ===" -ForegroundColor Cyan
if (Test-Path $OutputDir) { Remove-Item $OutputDir -Recurse -Force }
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path $InstallerDir) {
    # 保留 version.json：其中可能已写好 changelog，第 5 步会复用它
    Get-ChildItem -Path $InstallerDir -Force |
        Where-Object { $_.Name -ne 'version.json' } |
        Remove-Item -Recurse -Force
}

Write-Host "=== 3/5 PyInstaller 打包 (onedir, 无控制台) ===" -ForegroundColor Cyan
# 确保 pyinstaller 可用（项目通过 auto-py-to-exe 间接依赖它）
uv run pyinstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller 不可用，尝试安装..." -ForegroundColor Yellow
    uv run pip install pyinstaller
}
uv run pyinstaller --noconfirm --clean --onedir --windowed `
    --name $AppName `
    --distpath $OutputDir `
    --icon "app.ico" `
    --add-data "config\release.json;config" `
    --add-data "app.ico;." `
    main.py

$exePath = Join-Path $OutputDir "$AppName\$AppName.exe"
if (-not (Test-Path $exePath)) { throw "打包失败: 未找到 $exePath" }

# 清理用户运行时生成的产物（避免把 logs/ 与 thz_config.json 打进安装包）
$buildDir = Join-Path $OutputDir $AppName
Get-ChildItem -Path $buildDir -Force -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq 'logs' -or $_.Name -eq 'thz_config.json'
} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "已清理运行时产物 (logs/, thz_config.json)" -ForegroundColor DarkGray

# 校验 release.json 已打入产物且版本一致。
# 程序运行时从该文件读取版本号；若缺失会回退到代码里的后备版本，
# 导致升级后仍显示旧版本并反复提示更新。
$packedRelease = Join-Path $buildDir "_internal\config\release.json"
if (-not (Test-Path $packedRelease)) {
    throw "打包产物缺少 config\release.json: $packedRelease"
}
# app.ico 用于运行时的窗口/任务栏图标（界面左上角图标），缺失会退回默认图标
if (-not (Test-Path (Join-Path $buildDir "_internal\app.ico"))) {
    throw "打包产物缺少 app.ico: 窗口图标将无法显示"
}
$packedVersion = (Get-Content $packedRelease -Raw -Encoding UTF8 | ConvertFrom-Json).version
if ($packedVersion -ne $appVersion) {
    throw "打包产物版本不一致：release.json=$appVersion，产物=$packedVersion"
}
Write-Host "已校验产物版本: v$packedVersion" -ForegroundColor DarkGray

Write-Host "=== 4/5 Inno Setup 编译安装程序 ===" -ForegroundColor Cyan
# 定位 ISCC.exe：PATH -> 常见安装目录 -> 注册表卸载信息
$iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if ($iscc) {
    $isccPath = $iscc.Source
} else {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 5\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    $isccPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    # 注册表查找实际安装位置
    if (-not $isccPath) {
        $regPaths = @(
            "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
            "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
            "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
        )
        $installDir = Get-ItemProperty $regPaths -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -like "*Inno Setup*" } |
            Select-Object -First 1 -ExpandProperty InstallLocation
        if ($installDir) {
            $candidate = Join-Path $installDir "ISCC.exe"
            if (Test-Path $candidate) { $isccPath = $candidate }
        }
    }
}
if (-not $isccPath) {
    Write-Host "未自动找到 Inno Setup (ISCC.exe)。" -ForegroundColor Yellow
    Write-Host "可手动指定路径后重新运行：`$env:ISCC_PATH = 'C:\...\ISCC.exe'" -ForegroundColor Yellow
    $manual = Read-Host "请输入 ISCC.exe 的完整路径（回车跳过）"
    if ($manual -and (Test-Path $manual)) { $isccPath = $manual }
}
if (-not $isccPath) {
    throw "未找到 Inno Setup 编译器 (ISCC.exe)。请先安装: winget install JRSoftware.InnoSetup"
}

& $isccPath "/DMyAppVersion=$appVersion" "installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败" }

$installer = Join-Path $InstallerDir "install.exe"
if (-not (Test-Path $installer)) { throw "Inno Setup 未生成安装包: $installer" }

Write-Host "=== 5/5 生成更新源 version.json ===" -ForegroundColor Cyan
# 用项目自带脚本生成，保证 version / download_url / sha256 与安装包一致
$makeVersionArgs = @("run", "python", "scripts\make_version_json.py")
if ($Changelog) { $makeVersionArgs += @("--changelog", $Changelog) }
& uv @makeVersionArgs
if ($LASTEXITCODE -ne 0) { throw "生成 version.json 失败" }

$versionJsonPath = Join-Path $InstallerDir "version.json"
if (-not (Test-Path $versionJsonPath)) { throw "未生成 version.json: $versionJsonPath" }
$versionInfo = Get-Content $versionJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($versionInfo.version -ne $appVersion) {
    throw "version.json 版本不一致：release.json=$appVersion，version.json=$($versionInfo.version)"
}

Write-Host ""
Write-Host "构建完成!" -ForegroundColor Green
Write-Host "安装包:   $PWD\$installer"
Write-Host "更新源:   $PWD\$versionJsonPath"
Write-Host ""
Write-Host "下一步：到 GitHub 仓库 Release 页面（Tag 建议 v$appVersion）上传上面两个文件。" -ForegroundColor Cyan
if ($versionInfo.changelog -eq "请填写本次更新的内容说明（每条一行）") {
    Write-Host "提示：本次未提供更新说明，请编辑 version.json 的 changelog，或用 -Changelog 参数重新运行。" -ForegroundColor Yellow
}
