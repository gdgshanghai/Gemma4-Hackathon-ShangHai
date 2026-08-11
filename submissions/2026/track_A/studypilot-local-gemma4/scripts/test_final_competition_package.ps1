[CmdletBinding()]
param(
    [string]$DesktopOutput,
    [string]$SubmissionOutput
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$desktopRoot = [Environment]::GetFolderPath("Desktop")
$verifyDesktop = -not [string]::IsNullOrWhiteSpace($DesktopOutput)
$verifySubmission = -not [string]::IsNullOrWhiteSpace($SubmissionOutput)
$packagedSubmissionManifest = Join-Path $projectRoot "final-package-manifest.json"
$packagedDesktopRoot = Split-Path -Parent $projectRoot
$packagedDesktopManifest = Join-Path $packagedDesktopRoot "04_启动说明\final-package-manifest.json"

if (-not $verifyDesktop -and -not $verifySubmission) {
    if (Test-Path -LiteralPath $packagedSubmissionManifest -PathType Leaf) {
        $SubmissionOutput = $projectRoot
        $verifySubmission = $true
        Write-Host "Detected delivered submission package; verifying this package only."
    }
    elseif (Test-Path -LiteralPath $packagedDesktopManifest -PathType Leaf) {
        $DesktopOutput = $packagedDesktopRoot
        $verifyDesktop = $true
        Write-Host "Detected delivered desktop package; verifying this package only."
    }
    else {
        $DesktopOutput = Join-Path $desktopRoot "StudyPilot_2026决赛参赛包_V14Demo_V11PPT"
        $SubmissionOutput = Join-Path $projectRoot ".runtime\final-submission-staging"
        $verifyDesktop = $true
        $verifySubmission = $true
    }
}
$python = (Get-Command "python.exe" -ErrorAction Stop).Source
$builder = Join-Path $PSScriptRoot "final_competition_package.py"
$contractTest = Join-Path $projectRoot "tests/unit/release/test_final_competition_package.py"

Push-Location -LiteralPath $projectRoot
try {
    if (Test-Path -LiteralPath $contractTest -PathType Leaf) {
        & $python -m pytest $contractTest -q
        if ($LASTEXITCODE -ne 0) { throw "决赛包合同测试失败。" }
    }
    else {
        Write-Host "source-only contract test not present; running packaged checks."
    }

    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File scripts/check_final_competition_launchers.ps1
    if ($LASTEXITCODE -ne 0) { throw "决赛 launcher 检查失败。" }

    if ($verifyDesktop) {
        & $python $builder verify --package $DesktopOutput --kind desktop
        if ($LASTEXITCODE -ne 0) { throw "桌面决赛包校验失败。" }
    }

    if ($verifySubmission) {
        & $python $builder verify --package $SubmissionOutput --kind submission
        if ($LASTEXITCODE -ne 0) { throw "赛事 staging 校验失败。" }
    }
}
finally {
    Pop-Location
}

Write-Host "Final competition package checks: PASS"
