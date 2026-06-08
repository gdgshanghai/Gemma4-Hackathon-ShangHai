# Install OBS bridge plugin from bundled vendor files (no compile unless -ForceCompile)
param(
    [Parameter(Mandatory = $true)]
    [string]$AppDir,
    [switch]$ForceCompile
)

. "$PSScriptRoot\_common.ps1"

$vendorDll = Join-Path $AppDir 'vendor\obs-blivechat-bridge.dll'
$installPrefix = Join-Path $env:APPDATA 'obs-studio\plugins'

if ($ForceCompile) {
    Write-BlivechatInstallLog 'ForceCompile: trying source build'
    & "$PSScriptRoot\build-obs-plugin.ps1" -ProjectRoot $AppDir -AllowPrebuiltFallback -PrebuiltDll $vendorDll
    exit $LASTEXITCODE
}

function Install-BundledPluginOnly {
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
    Write-BlivechatInstallLog "Bundled OBS plugin installed: $destDir"
    return $true
}

if (-not (Install-BundledPluginOnly -DllPath $vendorDll -DestRoot $installPrefix)) {
    Write-BlivechatInstallLog "Bundled plugin missing: $vendorDll" -Level ERROR
    exit 1
}

$systemPluginDir = "${env:ProgramFiles}\obs-studio\obs-plugins\64bit"
if ((Test-Path $systemPluginDir) -and (
        [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Copy-Item -Force $vendorDll (Join-Path $systemPluginDir 'obs-blivechat-bridge.dll') -ErrorAction SilentlyContinue
    Write-BlivechatInstallLog "Also copied plugin to: $systemPluginDir"
}

exit 0
