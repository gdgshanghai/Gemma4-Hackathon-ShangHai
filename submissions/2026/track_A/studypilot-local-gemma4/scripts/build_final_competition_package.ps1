[CmdletBinding()]
param(
    [string]$DesktopOutput,
    [string]$SubmissionOutput
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$desktopRoot = [Environment]::GetFolderPath("Desktop")
if ([string]::IsNullOrWhiteSpace($DesktopOutput)) {
    $DesktopOutput = Join-Path $desktopRoot "StudyPilot_2026决赛参赛包_V14Demo_V11PPT"
}
if ([string]::IsNullOrWhiteSpace($SubmissionOutput)) {
    $SubmissionOutput = Join-Path $projectRoot ".runtime\final-submission-staging"
}
$python = (Get-Command "python.exe" -ErrorAction Stop).Source
$builder = Join-Path $PSScriptRoot "final_competition_package.py"

& $python $builder build --source-root $projectRoot --desktop-output $DesktopOutput --submission-output $SubmissionOutput
if ($LASTEXITCODE -ne 0) {
    throw "决赛参赛包构建失败（退出码 $LASTEXITCODE）。"
}

Write-Host "决赛参赛包已生成："
Write-Host "  桌面包：$DesktopOutput"
Write-Host "  赛事 staging：$SubmissionOutput"
