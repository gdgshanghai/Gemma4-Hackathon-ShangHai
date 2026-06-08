# Shared helpers for install/build scripts
$ErrorActionPreference = 'Stop'

$script:BlivechatInstallLogRoot = Join-Path $env:ProgramData 'blivechat'
$script:BlivechatInstallLogFile = Join-Path $BlivechatInstallLogRoot 'install.log'

function Initialize-BlivechatInstallLog {
    New-Item -ItemType Directory -Force -Path $BlivechatInstallLogRoot | Out-Null
    $header = @"
================================================================================
blivechat install log
Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Computer: $env:COMPUTERNAME
User: $env:USERNAME
IsAdmin: $(
        try {
            ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
                [Security.Principal.WindowsBuiltInRole]::Administrator
            )
        } catch { 'unknown' }
    )
================================================================================
"@
    Set-Content -Path $BlivechatInstallLogFile -Value $header -Encoding UTF8
}

function Write-BlivechatInstallLog {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR')]
        [string]$Level = 'INFO'
    )
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [$Level] $Message"
    Add-Content -Path $BlivechatInstallLogFile -Value $line -Encoding UTF8
    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN' { Write-Host $line -ForegroundColor Yellow }
        default { Write-Host $line }
    }
}

function Invoke-BlivechatLoggedCommand {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-BlivechatInstallLog "BEGIN $Name"
    try {
        & $Command
        Write-BlivechatInstallLog "OK $Name"
        return $true
    } catch {
        Write-BlivechatInstallLog "FAIL $Name : $($_.Exception.Message)" -Level ERROR
        if ($_.ScriptStackTrace) {
            Write-BlivechatInstallLog $_.ScriptStackTrace -Level ERROR
        }
        return $false
    }
}

function Get-BlivechatProjectRoot {
    param([string]$StartDir = $PSScriptRoot)
    $dir = (Resolve-Path $StartDir).Path
    for ($i = 0; $i -lt 8; $i++) {
        if ((Test-Path (Join-Path $dir 'main.py')) -or (Test-Path (Join-Path $dir 'blivechat.exe'))) {
            return $dir
        }
        if (Test-Path (Join-Path $dir 'obs-plugintemplate\CMakePresets.json')) {
            return $dir
        }
        $parent = Split-Path $dir -Parent
        if ($parent -eq $dir) { break }
        $dir = $parent
    }
    throw "Cannot locate project root from $StartDir"
}

function Find-ExecutableOnPath {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}
