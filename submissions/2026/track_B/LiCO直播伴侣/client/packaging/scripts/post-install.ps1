# Inno Setup post-install: bundled files first, optional winget, GUI summary
param(
    [string]$AppDir,
    [switch]$SkipDependencies,
    [switch]$SkipObsPlugin,
    [switch]$ForceCompilePlugin
)

$ErrorActionPreference = 'Continue'
. "$PSScriptRoot\_common.ps1"
Initialize-BlivechatInstallLog

$resultFile = Join-Path $env:ProgramData 'blivechat\install-result.json'
$allResults = @{
    obs_plugin = @{ status = 'unknown'; source = ''; message = '' }
    ffmpeg     = @{ status = 'unknown'; source = ''; message = '' }
    obs_studio = @{ status = 'unknown'; source = ''; message = '' }
}

Write-BlivechatInstallLog "post-install AppDir=$AppDir"

try {
    & "$PSScriptRoot\ensure-app-data.ps1" -AppDir $AppDir
} catch {
    Write-BlivechatInstallLog $_.Exception.Message -Level ERROR
}

if (-not $SkipObsPlugin) {
    $args = @{ AppDir = $AppDir }
    if ($ForceCompilePlugin) { $args['ForceCompile'] = $true }
    try {
        & "$PSScriptRoot\install-obs-plugin-bundled.ps1" @args
        if ($LASTEXITCODE -eq 0) {
            $allResults.obs_plugin.status = 'ok'
            $allResults.obs_plugin.source = if ($ForceCompilePlugin) { 'compiled' } else { 'bundled' }
            $allResults.obs_plugin.message = 'obs-blivechat-bridge installed to OBS plugins folder'
        } else {
            $allResults.obs_plugin.status = 'failed'
            $allResults.obs_plugin.message = 'Bundled OBS plugin DLL missing or copy failed'
        }
    } catch {
        $allResults.obs_plugin.status = 'failed'
        $allResults.obs_plugin.message = $_.Exception.Message
        Write-BlivechatInstallLog $_.Exception.Message -Level ERROR
    }
}

if (-not $SkipDependencies) {
    try {
        & "$PSScriptRoot\install-dependencies.ps1" -AppDir $AppDir -ResultFile $resultFile
        if (Test-Path $resultFile) {
            $dep = Get-Content $resultFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($dep.ffmpeg) { $allResults.ffmpeg = $dep.ffmpeg }
            if ($dep.obs_studio) { $allResults.obs_studio = $dep.obs_studio }
        }
    } catch {
        Write-BlivechatInstallLog $_.Exception.Message -Level ERROR
    }
}

$allResults | ConvertTo-Json -Depth 4 | Set-Content -Path $resultFile -Encoding UTF8

& "$PSScriptRoot\show-install-result.ps1" -ResultFile $resultFile

if ($allResults.obs_plugin.status -eq 'failed') {
    Write-BlivechatInstallLog 'OBS plugin install failed' -Level ERROR
    exit 2
}

Write-BlivechatInstallLog 'Post-install completed successfully'
exit 0
