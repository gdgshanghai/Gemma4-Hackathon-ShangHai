# Resolve FFmpeg/OBS: bundled vendor first, winget second, manual download last
param(
    [Parameter(Mandatory = $true)]
    [string]$AppDir,
    [switch]$SkipFfmpeg,
    [switch]$SkipObs,
    [string]$ResultFile = ''
)

. "$PSScriptRoot\_common.ps1"

$results = @{
    ffmpeg     = @{ status = 'unknown'; source = ''; message = '' }
    obs_studio = @{ status = 'unknown'; source = ''; message = '' }
}

function Save-InstallResults {
    if ($ResultFile -eq '') { return }
    $dir = Split-Path $ResultFile -Parent
    if ($dir -ne '' -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $results | ConvertTo-Json -Depth 4 | Set-Content -Path $ResultFile -Encoding UTF8
}

function Test-FfmpegOnPath {
    return [bool](Find-ExecutableOnPath 'ffmpeg') -and [bool](Find-ExecutableOnPath 'ffprobe')
}

function Test-ObsInstalled {
    foreach ($p in @(
            "${env:ProgramFiles}\obs-studio\bin\64bit\obs64.exe",
            "${env:ProgramFiles(x86)}\obs-studio\bin\64bit\obs64.exe"
        )) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Install-BundledFfmpeg {
    param([string]$Root)
    $bundledBin = Join-Path $Root 'vendor\ffmpeg\bin'
    if (-not (Test-Path (Join-Path $bundledBin 'ffmpeg.exe'))) {
        return $false
    }
    $toolsDir = Join-Path $Root 'tools\ffmpeg'
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    Copy-Item -Path (Join-Path $bundledBin '*') -Destination $toolsDir -Recurse -Force
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath -notlike "*$toolsDir*") {
        if ($userPath -and -not $userPath.EndsWith(';')) { $userPath += ';' }
        [Environment]::SetEnvironmentVariable('Path', ($userPath + $toolsDir), 'User')
        $env:Path = "$toolsDir;$env:Path"
    }
    Write-BlivechatInstallLog "Bundled FFmpeg installed to: $toolsDir"
    return $true
}

function Try-WingetInstall {
    param([string]$Id, [string]$DisplayName)
    if (-not (Find-ExecutableOnPath 'winget')) {
        Write-BlivechatInstallLog "winget unavailable for $DisplayName" -Level WARN
        return $false
    }
    $list = winget list --id $Id -e 2>&1
    if ($LASTEXITCODE -eq 0 -and ($list -match [regex]::Escape($Id))) {
        return $true
    }
    Write-BlivechatInstallLog "winget installing $DisplayName ..."
    winget install --id $Id -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    return ($LASTEXITCODE -eq 0)
}

if (-not $SkipFfmpeg) {
    if (Test-FfmpegOnPath) {
        $results.ffmpeg.status = 'ok'
        $results.ffmpeg.source = 'system'
        $results.ffmpeg.message = 'FFmpeg already on PATH'
        Write-BlivechatInstallLog $results.ffmpeg.message
    } elseif (Install-BundledFfmpeg -Root $AppDir) {
        $results.ffmpeg.status = 'ok'
        $results.ffmpeg.source = 'bundled'
        $results.ffmpeg.message = 'Installed bundled FFmpeg from installer package'
    } elseif (Try-WingetInstall -Id 'Gyan.FFmpeg' -DisplayName 'FFmpeg') {
        if (Test-FfmpegOnPath) {
            $results.ffmpeg.status = 'ok'
            $results.ffmpeg.source = 'winget'
            $results.ffmpeg.message = 'FFmpeg installed via winget'
        } else {
            $results.ffmpeg.status = 'manual_required'
            $results.ffmpeg.source = 'none'
            $results.ffmpeg.message = 'FFmpeg winget install finished but ffmpeg not on PATH. Download: https://www.gyan.dev/ffmpeg/builds/'
        }
    } else {
        $results.ffmpeg.status = 'manual_required'
        $results.ffmpeg.source = 'none'
        $results.ffmpeg.message = 'FFmpeg not bundled and winget failed. Download: https://www.gyan.dev/ffmpeg/builds/ or run: winget install Gyan.FFmpeg'
        Write-BlivechatInstallLog $results.ffmpeg.message -Level WARN
    }
}

if (-not $SkipObs) {
    $obsPath = Test-ObsInstalled
    if ($obsPath) {
        $results.obs_studio.status = 'ok'
        $results.obs_studio.source = 'system'
        $results.obs_studio.message = "OBS Studio found: $obsPath"
        Write-BlivechatInstallLog $results.obs_studio.message
    } elseif (Try-WingetInstall -Id 'OBSProject.OBSStudio' -DisplayName 'OBS Studio') {
        $obsPath = Test-ObsInstalled
        if ($obsPath) {
            $results.obs_studio.status = 'ok'
            $results.obs_studio.source = 'winget'
            $results.obs_studio.message = "OBS Studio installed: $obsPath"
        } else {
            $results.obs_studio.status = 'manual_required'
            $results.obs_studio.source = 'none'
            $results.obs_studio.message = 'OBS installed via winget but obs64.exe not found. Download: https://obsproject.com/download'
        }
    } else {
        $results.obs_studio.status = 'manual_required'
        $results.obs_studio.source = 'none'
        $results.obs_studio.message = 'OBS Studio is not included in this installer. Download: https://obsproject.com/download'
        Write-BlivechatInstallLog $results.obs_studio.message -Level WARN
    }
}

Save-InstallResults

exit 0
