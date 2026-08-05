# build_installer.ps1
# 一键构建 THzAnalyzer 安装包 (install.exe)
# 依赖：
#   1. Python 3.13 + uv（项目依赖已通过 uv sync 安装）
#   2. Inno Setup 6（安装：winget install JRSoftware.InnoSetup）
#
# 产物：installer-output\install.exe

$ErrorActionPreference = "Stop"

# 切换到脚本所在目录，保证 main.py / installer.iss 等相对路径始终正确
Set-Location $PSScriptRoot

$AppName = "THzAnalyzer"
$OutputDir = "output"          # PyInstaller onedir 输出目录
$InstallerDir = "installer-output"

Write-Host "=== 1/3 清理旧构建产物 ===" -ForegroundColor Cyan
if (Test-Path $OutputDir) { Remove-Item $OutputDir -Recurse -Force }
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path $InstallerDir) { Remove-Item $InstallerDir -Recurse -Force }

Write-Host "=== 2/3 PyInstaller 打包 (onedir, 无控制台) ===" -ForegroundColor Cyan
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
    main.py

$exePath = Join-Path $OutputDir "$AppName\$AppName.exe"
if (-not (Test-Path $exePath)) { throw "打包失败: 未找到 $exePath" }

# 清理用户运行时生成的产物（避免把 logs/ 与 thz_config.json 打进安装包）
$buildDir = Join-Path $OutputDir $AppName
Get-ChildItem -Path $buildDir -Force -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -eq 'logs' -or $_.Name -eq 'thz_config.json'
} | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "已清理运行时产物 (logs/, thz_config.json)" -ForegroundColor DarkGray

Write-Host "=== 3/3 Inno Setup 编译安装程序 ===" -ForegroundColor Cyan
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

& $isccPath "installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败" }

$installer = Join-Path $InstallerDir "install.exe"
Write-Host ""
Write-Host "构建完成!" -ForegroundColor Green
Write-Host "安装包位置: $PWD\$installer"
