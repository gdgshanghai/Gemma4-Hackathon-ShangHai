# Sync obs-blivechat-bridge source, build with obs-plugintemplate, install OBS plugin
param(
    [string]$ProjectRoot = '',
    [string]$InstallPrefix = '',
    [switch]$AllowPrebuiltFallback,
    [string]$PrebuiltDll = ''
)

. "$PSScriptRoot\_common.ps1"
Initialize-BlivechatInstallLog

if ($ProjectRoot -eq '') {
    $ProjectRoot = Get-BlivechatProjectRoot
}
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$bridgeSrc = Join-Path $ProjectRoot 'obs-blivechat-bridge\src\obs-blivechat-bridge.cpp'
$templateDir = Join-Path $ProjectRoot 'obs-plugintemplate'
$templateSrc = Join-Path $templateDir 'src\obs-blivechat-bridge.cpp'

if (-not (Test-Path $bridgeSrc)) {
    Write-BlivechatInstallLog "Missing plugin source: $bridgeSrc" -Level ERROR
    exit 1
}

if ($InstallPrefix -eq '') {
    $InstallPrefix = Join-Path $env:APPDATA 'obs-studio\plugins'
}

function Copy-PrebuiltPlugin {
    param([string]$DllPath, [string]$DestRoot)
    if (-not (Test-Path $DllPath)) { return $false }
    $destDir = Join-Path $DestRoot 'obs-blivechat-bridge\bin\64bit'
    $localeDir = Join-Path $DestRoot 'obs-blivechat-bridge\data\locale'
    New-Item -ItemType Directory -Force -Path $destDir, $localeDir | Out-Null
    Copy-Item -Force $DllPath (Join-Path $destDir 'obs-blivechat-bridge.dll')
    $vendorRoot = Split-Path $DllPath -Parent
    $pdb = Join-Path $vendorRoot 'obs-blivechat-bridge.pdb'
    if (Test-Path $pdb) {
        Copy-Item -Force $pdb (Join-Path $destDir 'obs-blivechat-bridge.pdb')
    }
    $locale = Join-Path $vendorRoot 'locale\en-US.ini'
    if (Test-Path $locale) {
        Copy-Item -Force $locale (Join-Path $localeDir 'en-US.ini')
    }
    Write-BlivechatInstallLog "Using prebuilt plugin: $DllPath -> $destDir"
    return $true
}

function Invoke-CmakeBuildWithVcVars {
    param(
        [string]$TemplateDir,
        [string]$CmakeExe,
        [string]$InstallPrefix
    )
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) {
        throw 'vswhere.exe not found; install VS 2022 or Build Tools with C++ workload'
    }
    $installPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installPath) {
        throw 'Visual Studio with VC++ tools not found'
    }
    $vcvars = Join-Path $installPath 'VC\Auxiliary\Build\vcvars64.bat'
    if (-not (Test-Path $vcvars)) {
        throw "vcvars64.bat not found: $vcvars"
    }
    $batFile = Join-Path $env:TEMP 'blivechat-build-plugin.bat'
    @"
@echo off
call "$vcvars" >nul 2>&1
cd /d "$TemplateDir"
"$CmakeExe" --preset windows-x64
if errorlevel 1 exit /b 1
"$CmakeExe" --build --preset windows-x64
if errorlevel 1 exit /b 1
"$CmakeExe" --install build_x64 --config RelWithDebInfo --prefix "$InstallPrefix"
exit /b %ERRORLEVEL%
"@ | Set-Content -Path $batFile -Encoding ASCII
    cmd /c $batFile
    if ($LASTEXITCODE -ne 0) { throw "Build failed, exit $LASTEXITCODE" }
}

New-Item -ItemType Directory -Force -Path (Split-Path $templateSrc) | Out-Null
Copy-Item -Force $bridgeSrc $templateSrc
Write-BlivechatInstallLog "Synced plugin source -> $templateSrc"

$cmake = Find-ExecutableOnPath 'cmake'
if (-not $cmake) {
    Write-BlivechatInstallLog 'cmake not found; trying winget Kitware.CMake' -Level WARN
    if (Find-ExecutableOnPath 'winget') {
        winget install --id Kitware.CMake -e --accept-package-agreements --accept-source-agreements --disable-interactivity
        $cmake = Find-ExecutableOnPath 'cmake'
    }
}
if (-not $cmake) {
    Write-BlivechatInstallLog 'cmake unavailable; cannot compile OBS plugin' -Level ERROR
    if ($AllowPrebuiltFallback -and $PrebuiltDll -ne '') {
        if (Copy-PrebuiltPlugin -DllPath $PrebuiltDll -DestRoot $InstallPrefix) { exit 0 }
    }
    exit 1
}

try {
    Invoke-CmakeBuildWithVcVars -TemplateDir $templateDir -CmakeExe $cmake -InstallPrefix $InstallPrefix
    Write-BlivechatInstallLog "OBS plugin installed to: $InstallPrefix"
} catch {
    Write-BlivechatInstallLog $_.Exception.Message -Level ERROR
    if ($AllowPrebuiltFallback -and $PrebuiltDll -ne '' -and (Copy-PrebuiltPlugin -DllPath $PrebuiltDll -DestRoot $InstallPrefix)) {
        exit 0
    }
    exit 1
}

$systemPluginDir = "${env:ProgramFiles}\obs-studio\obs-plugins\64bit"
if ((Test-Path $systemPluginDir) -and ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $builtDll = Join-Path $InstallPrefix 'obs-blivechat-bridge\bin\64bit\obs-blivechat-bridge.dll'
    if (Test-Path $builtDll) {
        Copy-Item -Force $builtDll (Join-Path $systemPluginDir 'obs-blivechat-bridge.dll')
        Write-BlivechatInstallLog "Copied plugin to: $systemPluginDir"
    }
}

exit 0
