[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Install", "Start", "Stop", "Preflight")]
    [string]$Action,

    [switch]$CheckOnly,

    [switch]$DemoMode
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $PSScriptRoot "StudyPilotLauncher.psm1") -Force

if ($CheckOnly) {
    Write-Host "Launcher wrapper check: PASS ($Action)"
    exit 0
}

try {
    switch ($Action) {
        "Install" { Invoke-StudyPilotInstall -ProjectRoot $projectRoot }
        "Start" { Invoke-StudyPilotStart -ProjectRoot $projectRoot -DemoMode:$DemoMode }
        "Stop" { Invoke-StudyPilotStop -ProjectRoot $projectRoot }
        "Preflight" { Invoke-StudyPilotPreflight -ProjectRoot $projectRoot }
    }
}
catch {
    Write-Host "失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
