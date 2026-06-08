# Build frontend + PyInstaller bundle + optional OBS plugin + Inno installer
param(
    [switch]$SkipFrontend,
    [switch]$SkipPlugin,
    [switch]$SkipInstaller,
    [string]$InnoSetupCompiler = ''
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_common.ps1"

$projectRoot = Get-BlivechatProjectRoot -StartDir $PSScriptRoot
$packagingDir = Join-Path $projectRoot 'packaging'
$distApp = Join-Path $packagingDir 'dist\blivechat'
$vendorDir = Join-Path $packagingDir 'vendor'

Write-Host "Project root: $projectRoot"

if (-not $SkipFrontend) {
    Push-Location (Join-Path $projectRoot 'frontend')
    if (-not (Test-Path 'node_modules')) { npm install }
    npm run build
    Pop-Location
}

Write-Host 'Installing Python build deps...'
python -m pip install -r (Join-Path $projectRoot 'requirements.txt')
python -m pip install -r (Join-Path $packagingDir 'requirements-build.txt')

Push-Location $packagingDir
python -m PyInstaller --noconfirm --clean blivechat.spec
Pop-Location

$bundledPlugins = Join-Path $distApp '_internal\plugins'
if (-not (Test-Path $bundledPlugins)) {
    $bundledPlugins = Join-Path $distApp 'plugins'
}
& "$PSScriptRoot\set-bundled-plugins-defaults.ps1" -PluginsDir $bundledPlugins

if (-not $SkipPlugin) {
    $builtDllInTree = Join-Path $projectRoot 'obs-plugintemplate\build_x64\RelWithDebInfo\obs-blivechat-bridge.dll'
    if (-not (Test-Path $builtDllInTree)) {
        & "$PSScriptRoot\build-obs-plugin.ps1" -ProjectRoot $projectRoot
    }
    if (Test-Path $builtDllInTree) {
        New-Item -ItemType Directory -Force -Path $vendorDir | Out-Null
        Copy-Item -Force $builtDllInTree (Join-Path $vendorDir 'obs-blivechat-bridge.dll')
        $builtPdb = Join-Path $projectRoot 'obs-plugintemplate\build_x64\RelWithDebInfo\obs-blivechat-bridge.pdb'
        if (Test-Path $builtPdb) {
            Copy-Item -Force $builtPdb (Join-Path $vendorDir 'obs-blivechat-bridge.pdb')
        }
        $srcCpp = Get-FileHash (Join-Path $projectRoot 'obs-blivechat-bridge\src\obs-blivechat-bridge.cpp') -Algorithm SHA256
        @(
            "built_at=$(Get-Date -Format o)",
            "source=obs-blivechat-bridge/src/obs-blivechat-bridge.cpp",
            "source_sha256=$($srcCpp.Hash)",
            "cmake_preset=windows-x64",
            "configuration=RelWithDebInfo"
        ) | Set-Content -Path (Join-Path $vendorDir 'BUILD_INFO.txt') -Encoding UTF8
        Write-Host "Prebuilt plugin copied to $vendorDir"
    } else {
        Write-Warning 'OBS plugin DLL not found; packaging without vendor fallback.'
    }
}

$appVendor = Join-Path $distApp 'vendor'
if (Test-Path $appVendor) { Remove-Item -Recurse -Force $appVendor }
if (Test-Path $vendorDir) {
    Copy-Item -Recurse $vendorDir $appVendor
    Remove-Item -Force (Join-Path $appVendor 'obs-blivechat-bridge.pdb') -ErrorAction SilentlyContinue
    Write-Host "Vendor bundle copied to $appVendor"
}

$templateDest = Join-Path $distApp 'obs-plugintemplate'
if (Test-Path $templateDest) { Remove-Item -Recurse -Force $templateDest }
Copy-Item -Recurse (Join-Path $projectRoot 'obs-plugintemplate') $templateDest
Remove-Item -Recurse -Force (Join-Path $templateDest 'build_x64') -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $templateDest '.deps') -ErrorAction SilentlyContinue
$bridgeDest = Join-Path $distApp 'obs-blivechat-bridge'
if (Test-Path $bridgeDest) { Remove-Item -Recurse -Force $bridgeDest }
Copy-Item -Recurse (Join-Path $projectRoot 'obs-blivechat-bridge') $bridgeDest
Remove-Item -Recurse -Force (Join-Path $bridgeDest 'build') -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $bridgeDest 'build-macos') -ErrorAction SilentlyContinue

if (-not $SkipInstaller) {
    if ($InnoSetupCompiler -eq '') {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
            "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
        )
        foreach ($c in $candidates) {
            if (Test-Path $c) { $InnoSetupCompiler = $c; break }
        }
    }
    if ($InnoSetupCompiler -eq '' -or -not (Test-Path $InnoSetupCompiler)) {
        Write-Warning 'Inno Setup ISCC.exe not found. Install Inno Setup 6 and re-run with -SkipFrontend -SkipPlugin'
    } else {
        & $InnoSetupCompiler (Join-Path $packagingDir 'installer\setup.iss')
        Write-Host "Installer output: $(Join-Path $packagingDir 'installer\output')"
    }
}

Write-Host "Application bundle: $distApp"
