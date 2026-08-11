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
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$venvBin = Join-Path $venvRoot "Scripts"
$expectedModel = "gemma-4-26b-a4b-it"

function Get-SystemPython {
    $command = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "决赛 Demo 需要 Python 3.13 或更高版本，请先安装 Python。"
    }
    return $command.Source
}

function Use-LocalPython {
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "决赛 Demo 的本地 Python 依赖尚未安装，请先运行 安装决赛Demo依赖.bat。"
    }
    $env:PATH = "$venvBin;$env:PATH"
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments, [string]$WorkingDirectory)
    Push-Location $WorkingDirectory
    try {
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "命令失败：$Executable（退出码 $LASTEXITCODE）。"
        }
    }
    finally {
        Pop-Location
    }
}

function Assert-ModelMetadata {
    try {
        $payload = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:1234/api/v0/models" -TimeoutSec 10
    }
    catch {
        throw "LM Studio 预检失败：请先手动启动 LM Studio Server。"
    }
    $records = @($payload.data)
    $record = $records | Where-Object { [string]$_.id -ceq $expectedModel } | Select-Object -First 1
    if ($null -eq $record) {
        throw "LM Studio 预检失败：未找到精确模型 $expectedModel。"
    }
    if ([string]$record.state -cne "loaded") {
        throw "LM Studio 预检失败：$expectedModel 必须处于 loaded 状态。"
    }
    if (@($record.capabilities) -cnotcontains "tool_use") {
        throw "LM Studio 预检失败：$expectedModel 缺少 tool_use 能力。"
    }
    Write-Host "LM Studio 模型检查通过：$expectedModel / loaded / tool_use"
}

function Assert-PrestartFiles {
    $required = @(
        $venvPython,
        (Join-Path $projectRoot "scripts\studypilot_service.py"),
        (Join-Path $projectRoot "kid-frontend\node_modules\vite\bin\vite.js"),
        (Join-Path $projectRoot "parent-frontend\node_modules\vite\bin\vite.js")
    )
    foreach ($path in $required) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "决赛 Demo 依赖不完整：缺少 $path。"
        }
    }
}

function Get-ListeningPorts {
    try {
        return @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
            Where-Object { $_.LocalPort -in @(8040, 8041, 8042) })
    }
    catch {
        throw "无法检查 StudyPilot 现场端口状态：$($_.Exception.Message)"
    }
}

function Invoke-FinalPreflight {
    Assert-ModelMetadata
    Assert-PrestartFiles
    $listeners = @(Get-ListeningPorts)
    if ($listeners.Count -gt 0) {
        Write-Host "StudyPilot 服务已在现场端口监听；将继续检查现有健康状态。"
        Import-Module (Join-Path $PSScriptRoot "StudyPilotLauncher.psm1") -Force
        Invoke-StudyPilotPreflight -ProjectRoot $projectRoot
    }
    else {
        Write-Host "决赛 Demo 启动前检查通过：LM Studio、依赖和 8040/8041/8042 端口均可用。"
    }
}

if ($CheckOnly) {
    Write-Host "Finals launcher check: PASS ($Action)"
    exit 0
}

try {
    switch ($Action) {
        "Install" {
            $systemPython = Get-SystemPython
            $version = & $systemPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            if ($LASTEXITCODE -ne 0 -or [version]$version -lt [version]"3.13") {
                throw "决赛 Demo 需要 Python 3.13 或更高版本。"
            }
            if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
                Invoke-Checked $systemPython @("-m", "venv", $venvRoot) $projectRoot
            }
            Use-LocalPython
            Import-Module (Join-Path $PSScriptRoot "StudyPilotLauncher.psm1") -Force
            Invoke-StudyPilotInstall -ProjectRoot $projectRoot
            Write-Host "决赛 Demo 本地依赖安装完成。"
        }
        "Start" {
            Use-LocalPython
            Import-Module (Join-Path $PSScriptRoot "StudyPilotLauncher.psm1") -Force
            Invoke-StudyPilotStart -ProjectRoot $projectRoot -DemoMode:$true
            Start-Process "http://127.0.0.1:8042"
            Write-Host "决赛 Demo 已启动：孩子端 8041，家长端 8042。"
        }
        "Stop" {
            if (Test-Path -LiteralPath $venvPython -PathType Leaf) { Use-LocalPython }
            Import-Module (Join-Path $PSScriptRoot "StudyPilotLauncher.psm1") -Force
            Invoke-StudyPilotStop -ProjectRoot $projectRoot
            Write-Host "决赛 Demo 服务已停止；LM Studio 未被操作。"
        }
        "Preflight" {
            Invoke-FinalPreflight
        }
    }
}
catch {
    Write-Host "失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

exit 0
