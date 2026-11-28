# Build a local Windows x64 installer. No publishing or update metadata.
[CmdletBinding()]
param(
    [string]$IsccPath = $env:ISCC_PATH,
    [string]$DependencyNotices,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'

if (-not $IsccPath) {
    $iscc = Get-Command ISCC.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($iscc) { $IsccPath = $iscc.Path }
}
if (-not $IsccPath) {
    $bases = @(${env:ProgramFiles(x86)}, $env:ProgramFiles, "$env:LOCALAPPDATA\Programs")
    foreach ($base in $bases | Where-Object { $_ }) {
        foreach ($edition in @('Inno Setup 7', 'Inno Setup 6')) {
            $candidate = Join-Path $base "$edition\ISCC.exe"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { $IsccPath = $candidate; break }
        }
        if ($IsccPath) { break }
    }
}
if (-not $IsccPath) {
    $uninstall = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    foreach ($entry in (Get-ItemProperty -Path $uninstall -ErrorAction SilentlyContinue)) {
        if ($entry.DisplayName -like 'Inno Setup*' -and $entry.InstallLocation) {
            $candidate = Join-Path $entry.InstallLocation 'ISCC.exe'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { $IsccPath = $candidate; break }
        }
    }
}
if (-not $IsccPath -or -not (Test-Path -LiteralPath $IsccPath -PathType Leaf)) {
    throw 'Inno Setup compiler not found. Install Inno Setup 6.3+ or pass -IsccPath.'
}
$IsccPath = (Resolve-Path -LiteralPath $IsccPath).ProviderPath
if ($DependencyNotices) {
    if (-not (Test-Path -LiteralPath $DependencyNotices -PathType Leaf)) {
        throw "Rust dependency notice file not found: $DependencyNotices"
    }
    $DependencyNotices = (Resolve-Path -LiteralPath $DependencyNotices).ProviderPath
}

$cargo = Get-Command cargo.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$cargoPath = if ($cargo) { $cargo.Path } else { Join-Path $HOME '.cargo\bin\cargo.exe' }
if (-not (Test-Path -LiteralPath $cargoPath -PathType Leaf)) { throw 'Cargo not found. Install Rust with rustup.' }

Push-Location -LiteralPath $PSScriptRoot
try {
    $metadataJson = & $cargoPath metadata --no-deps --format-version 1 --locked
    if ($LASTEXITCODE -ne 0) { throw "Cargo metadata failed: $LASTEXITCODE" }
    $metadata = $metadataJson | ConvertFrom-Json
    $package = $metadata.packages | Where-Object name -EQ 'thz-analyzer-rust' | Select-Object -First 1
    $version = $package.version
    if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Expected a numeric Cargo package version: $version" }

    if (-not $SkipBuild) {
        # Link the MSVC C runtime statically so the installer only needs the app exe.
        $savedRustFlags = $env:RUSTFLAGS
        $savedEncodedFlags = $env:CARGO_ENCODED_RUSTFLAGS
        try {
            if ($savedEncodedFlags) {
                $env:CARGO_ENCODED_RUSTFLAGS = $savedEncodedFlags + [char]31 + '-C' + [char]31 + 'target-feature=+crt-static'
            } else {
                $env:RUSTFLAGS = "$savedRustFlags -C target-feature=+crt-static".Trim()
            }
            & $cargoPath build --release --locked --bin thz-analyzer-rust
            if ($LASTEXITCODE -ne 0) { throw "Cargo release build failed: $LASTEXITCODE" }
        } finally {
            $env:RUSTFLAGS = $savedRustFlags
            $env:CARGO_ENCODED_RUSTFLAGS = $savedEncodedFlags
        }
    }
    $exe = Join-Path $metadata.target_directory 'release\thz-analyzer-rust.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Release executable not found: $exe" }

    # Match the installer's architecture rather than packaging an x86/ARM64 executable by mistake.
    $reader = [System.IO.BinaryReader]::new([System.IO.File]::OpenRead($exe))
    try {
        if ($reader.ReadUInt16() -ne 0x5a4d) { throw "Not a Windows PE executable: $exe" }
        $reader.BaseStream.Position = 0x3c
        $reader.BaseStream.Position = $reader.ReadInt32()
        if ($reader.ReadUInt32() -ne 0x00004550 -or $reader.ReadUInt16() -ne 0x8664) {
            throw "Expected an x64 Windows executable: $exe"
        }
    } finally {
        $reader.Dispose()
    }

    $compilerArgs = @("/DRustVersion=$version", "/DRustExePath=$exe")
    if ($DependencyNotices) { $compilerArgs += "/DRustNoticesPath=$DependencyNotices" }
    $compilerArgs += 'installer.iss'
    & $IsccPath @compilerArgs
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed: $LASTEXITCODE" }
    $installer = Join-Path $PSScriptRoot "dist\THzAnalyzer-Rust-$version-Setup.exe"
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw "Installer not found: $installer" }
    $sizeMiB = (Get-Item -LiteralPath $installer).Length / 1MB
    Write-Host ('Installer: {0} ({1:N2} MiB)' -f $installer, $sizeMiB)
} finally {
    Pop-Location
}
