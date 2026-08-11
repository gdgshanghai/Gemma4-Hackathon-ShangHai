[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceWrapperRoot = Join-Path $projectRoot "final-competition\wrappers"
$wrapperRoot = if (Test-Path -LiteralPath $sourceWrapperRoot -PathType Container) {
    $sourceWrapperRoot
}
elseif (Test-Path -LiteralPath (Join-Path $projectRoot "启动决赛Demo.bat") -PathType Leaf) {
    $projectRoot
}
else {
    Split-Path -Parent $projectRoot
}
$checks = 0

function Assert-True {
    param([bool]$Condition, [string]$Message)
    $script:checks += 1
    if (-not $Condition) { throw "CHECK FAILED: $Message" }
}

$wrappers = @{
    "安装决赛Demo依赖.bat" = "Install"
    "启动决赛Demo.bat" = "Start"
    "停止决赛Demo.bat" = "Stop"
    "决赛现场预检.bat" = "Preflight"
}
foreach ($entry in $wrappers.GetEnumerator()) {
    $path = Join-Path $wrapperRoot $entry.Key
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "$($entry.Key) exists"
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $path
    Assert-True ($content -match ("-Action\s+" + $entry.Value)) "$($entry.Key) maps to $($entry.Value)"
    Assert-True ($content -notmatch "V13|半决赛|taskkill|rmdir|rd\s+/s") "$($entry.Key) uses finals-safe copy"
}

$openPpt = Join-Path $wrapperRoot "打开决赛PPT.bat"
Assert-True (Test-Path -LiteralPath $openPpt -PathType Leaf) "打开决赛PPT.bat exists"
$openPptContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $openPpt
Assert-True ($openPptContent -match "\*V11\*\.pptx") "PPT wrapper locates V11 without locale-dependent batch text"
Assert-True ($openPptContent -notmatch "V13|半决赛") "PPT wrapper uses finals-safe copy"

$previousNoPause = $env:STUDYPILOT_NO_PAUSE
$env:STUDYPILOT_NO_PAUSE = "1"
try {
    foreach ($entry in $wrappers.GetEnumerator()) {
        $path = Join-Path $wrapperRoot $entry.Key
        & $env:ComSpec /d /c call $path --check
        Assert-True ($LASTEXITCODE -eq 0) "$($entry.Key) executes through cmd.exe check mode"
    }
    & $env:ComSpec /d /c call $openPpt --check
    Assert-True ($LASTEXITCODE -eq 0) "打开决赛PPT.bat executes through cmd.exe check mode"
}
finally {
    $env:STUDYPILOT_NO_PAUSE = $previousNoPause
}

$launcher = Join-Path $PSScriptRoot "final_competition_launcher.ps1"
Assert-True (Test-Path -LiteralPath $launcher -PathType Leaf) "final launcher exists"
foreach ($action in @("Install", "Start", "Stop", "Preflight")) {
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $launcher -Action $action -CheckOnly
    Assert-True ($LASTEXITCODE -eq 0) "final launcher CheckOnly passes for $action"
}

$moduleSource = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot "StudyPilotLauncher.psm1")
Assert-True ($moduleSource -notmatch "停止V13\.bat") "runtime errors do not direct the presenter to an old wrapper"
Assert-True ($moduleSource -match "停止决赛Demo\.bat") "runtime errors direct the presenter to the finals wrapper"

$demoRoute = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "backend\api\routes\demo.py")
$kidPreset = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "kid-frontend\src\views\IntakeView.tsx")
$parentBrief = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "parent-frontend\src\views\BriefView.tsx")
$parentCalibration = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot "parent-frontend\src\views\CalibrationView.tsx")
Assert-True ($demoRoute -match "/scenario") "demo scenario API is present"
Assert-True ($demoRoute -match "/evenings/today/reset") "demo reset API is present"
Assert-True ($kidPreset -match "一键代入预设作业") "kid preset button is present"
Assert-True ($parentBrief -match "载入示例作业单") "parent brief preset is present"
Assert-True ($parentCalibration -match "载入示例观察") "parent calibration preset is present"

Write-Host "Final competition launcher checks: PASS ($checks checks)"
