Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ExpectedModel = "gemma-4-26b-a4b-it"
$script:LmMetadataUri = "http://127.0.0.1:1234/api/v0/models"
$script:ApiHealthUri = "http://127.0.0.1:8040/api/v1/health"

function Get-PropertyValue {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Assert-StudyPilotModelMetadata {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Payload)

    $records = Get-PropertyValue $Payload "data"
    if ($null -eq $records -or $records -is [string]) {
        throw "LM Studio 预检失败：/api/v0/models 返回格式无效。"
    }
    $match = $null
    foreach ($candidate in @($records)) {
        $id = Get-PropertyValue $candidate "id"
        if ($id -is [string] -and [string]::Equals($id, $script:ExpectedModel, [StringComparison]::Ordinal)) {
            $match = $candidate
            break
        }
    }
    if ($null -eq $match) {
        throw "LM Studio 预检失败：未找到精确模型 gemma-4-26b-a4b-it。"
    }
    $state = Get-PropertyValue $match "state"
    if ($state -isnot [string] -or -not [string]::Equals($state, "loaded", [StringComparison]::Ordinal)) {
        throw "LM Studio 预检失败：gemma-4-26b-a4b-it 必须处于 loaded 状态。"
    }
    $capabilities = Get-PropertyValue $match "capabilities"
    if ($null -eq $capabilities -or @($capabilities) -cnotcontains "tool_use") {
        throw "LM Studio 预检失败：gemma-4-26b-a4b-it 缺少 tool_use 能力。"
    }
    return $match
}

function Test-StudyPilotProcessRecord {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Process,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Listeners,
        [Parameter(Mandatory = $true)][int]$ExpectedPid,
        [Parameter(Mandatory = $true)][string]$ExpectedProcessName,
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string[]]$SignatureTokens,
        [Parameter(Mandatory = $true)][int]$ExpectedPort
    )

    $actualPid = Get-PropertyValue $Process "ProcessId"
    $name = Get-PropertyValue $Process "Name"
    $commandLine = Get-PropertyValue $Process "CommandLine"
    if ($null -eq $actualPid -or [int]$actualPid -ne $ExpectedPid) { return $false }
    if ($name -isnot [string] -or -not [string]::Equals($name, $ExpectedProcessName, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    if ($commandLine -isnot [string] -or [string]::IsNullOrWhiteSpace($commandLine)) { return $false }

    $root = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd([char[]]@('\', '/'))
    if ($commandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
    foreach ($token in $SignatureTokens) {
        if ($commandLine.IndexOf($token, [StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
    }
    foreach ($listener in $Listeners) {
        $address = Get-PropertyValue $listener "LocalAddress"
        $port = Get-PropertyValue $listener "LocalPort"
        $owner = Get-PropertyValue $listener "OwningProcess"
        if (($address -eq "127.0.0.1" -or $address -eq "::1") -and [int]$port -eq $ExpectedPort -and [int]$owner -eq $ExpectedPid) {
            return $true
        }
    }
    return $false
}

function Get-RequiredCommandPath {
    param([string]$Name, [string]$ChineseName)
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) { throw "启动失败：未找到 $ChineseName，请先运行安装依赖。" }
    return $command.Source
}

function Get-StudyPilotListeners {
    try {
        return @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Select-Object LocalAddress, LocalPort, OwningProcess)
    }
    catch {
        throw "进程检查失败：无法读取本机 TCP 监听信息。"
    }
}

function Read-TrackedPid {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $value = (Get-Content -Raw -LiteralPath $Path).Trim()
    $pidValue = 0
    if (-not [int]::TryParse($value, [ref]$pidValue) -or $pidValue -le 0) { return $null }
    return $pidValue
}

function Test-TrackedService {
    param([object]$Service, [object[]]$Listeners)
    $trackedPid = Read-TrackedPid $Service.PidPath
    if ($null -eq $trackedPid) { return $false }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$trackedPid" -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $false }
    return Test-StudyPilotProcessRecord -Process $process -Listeners $Listeners -ExpectedPid $trackedPid -ExpectedProcessName $Service.ProcessName -ProjectRoot $Service.ProjectRoot -SignatureTokens $Service.SignatureTokens -ExpectedPort $Service.Port
}

function Test-ProcessDescendsFrom {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][int]$DescendantPid,
        [Parameter(Mandatory = $true)][int]$AncestorPid
    )

    $seen = @{}
    $currentPid = $DescendantPid
    for ($depth = 0; $depth -lt 16; $depth += 1) {
        if ($currentPid -eq $AncestorPid) { return $true }
        if ($seen.ContainsKey($currentPid)) { return $false }
        $seen[$currentPid] = $true
        $record = Get-CimInstance Win32_Process -Filter "ProcessId=$currentPid" -ErrorAction SilentlyContinue
        if ($null -eq $record -or $null -eq $record.ParentProcessId) { return $false }
        $parentPid = [int]$record.ParentProcessId
        if ($parentPid -le 0 -or $parentPid -eq $currentPid) { return $false }
        $currentPid = $parentPid
    }
    return $false
}

function Get-ValidatedListeningProcess {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Service,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Listeners,
        [Parameter(Mandatory = $true)][int]$LaunchedPid
    )

    foreach ($listener in @($Listeners | Where-Object { $_.LocalPort -eq $Service.Port })) {
        $ownerPid = Get-PropertyValue $listener "OwningProcess"
        if ($null -eq $ownerPid) { continue }
        $ownerPid = [int]$ownerPid
        if ($ownerPid -ne $LaunchedPid -and -not (Test-ProcessDescendsFrom -DescendantPid $ownerPid -AncestorPid $LaunchedPid)) {
            continue
        }
        $record = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
        if ($null -eq $record) { continue }
        if (Test-StudyPilotProcessRecord -Process $record -Listeners @($Listeners) -ExpectedPid $ownerPid -ExpectedProcessName $Service.ProcessName -ProjectRoot $Service.ProjectRoot -SignatureTokens $Service.SignatureTokens -ExpectedPort $Service.Port) {
            return [pscustomobject]@{ Pid = $ownerPid; Process = $record }
        }
    }
    return $null
}

function New-ServiceDefinition {
    param(
        [string]$Name, [string]$DisplayName, [int]$Port, [string]$ProcessName,
        [string[]]$SignatureTokens, [string]$Executable, [string[]]$Arguments,
        [string]$WorkingDirectory, [string]$ProjectRoot, [string]$RuntimeRoot
    )
    return [pscustomobject]@{
        Name = $Name; DisplayName = $DisplayName; Port = $Port
        ProcessName = $ProcessName; SignatureTokens = $SignatureTokens
        Executable = $Executable; Arguments = $Arguments; WorkingDirectory = $WorkingDirectory
        ProjectRoot = $ProjectRoot; PidPath = (Join-Path $RuntimeRoot "$Name-$Port.pid")
    }
}

function Get-ServiceDefinitions {
    param([string]$ProjectRoot, [switch]$ForStart, [switch]$IncludeParent)
    $runtimeRoot = Join-Path $ProjectRoot ".runtime"
    $serviceScript = Join-Path $ProjectRoot "scripts\studypilot_service.py"
    $python = if ($ForStart) { Get-RequiredCommandPath "python.exe" "Python 3.13" } else { "python.exe" }
    $node = if ($ForStart) { Get-RequiredCommandPath "node.exe" "Node.js" } else { "node.exe" }
    $services = @(
        (New-ServiceDefinition "api" "API" 8040 ([IO.Path]::GetFileName($python)) @($serviceScript, " api") $python @("`"$serviceScript`"", "api") $ProjectRoot $ProjectRoot $runtimeRoot)
    )
    $kidVite = Join-Path $ProjectRoot "kid-frontend\node_modules\vite\bin\vite.js"
    $services += New-ServiceDefinition "kid" "孩子端" 8041 ([IO.Path]::GetFileName($node)) @($kidVite, "--port 8041") $node @("`"$kidVite`"", "--host", "127.0.0.1", "--port", "8041", "--strictPort") (Join-Path $ProjectRoot "kid-frontend") $ProjectRoot $runtimeRoot
    $parentPackage = Join-Path $ProjectRoot "parent-frontend\package.json"
    if ($IncludeParent -or (Test-Path -LiteralPath $parentPackage -PathType Leaf)) {
        $parentVite = Join-Path $ProjectRoot "parent-frontend\node_modules\vite\bin\vite.js"
        $services += New-ServiceDefinition "parent" "家长端" 8042 ([IO.Path]::GetFileName($node)) @($parentVite, "--port 8042") $node @("`"$parentVite`"", "--host", "127.0.0.1", "--port", "8042", "--strictPort") (Join-Path $ProjectRoot "parent-frontend") $ProjectRoot $runtimeRoot
    }
    return @($services)
}

function Invoke-WithRuntimeEnvironment {
    param([scriptblock]$Operation, [switch]$DemoMode)
    $demoValue = if ($DemoMode) { "true" } else { "false" }
    $databasePath = if ($DemoMode) { "data/local/studypilot_v14_demo.db" } else { "data/local/studypilot_v13.db" }
    $values = @{
        V13_LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
        V13_LM_STUDIO_MODEL = $script:ExpectedModel
        V13_BACKEND_PORT = "8040"; V13_CHILD_PORT = "8041"; V13_PARENT_PORT = "8042"
        V13_MOCK_ENABLED = "false"
        V13_DEMO_MODE = $demoValue
        V13_DB_PATH = $databasePath
        VITE_DEMO_MODE = $demoValue
    }
    $previous = @{}
    foreach ($name in $values.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
        [Environment]::SetEnvironmentVariable($name, $values[$name], "Process")
    }
    try { & $Operation }
    finally {
        foreach ($name in $values.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], "Process") }
    }
}

function Invoke-CheckedCommand {
    param([string]$Executable, [string[]]$Arguments, [string]$WorkingDirectory, [string]$FailureMessage)
    Push-Location $WorkingDirectory
    try {
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$FailureMessage（退出码 $LASTEXITCODE）。" }
    }
    finally { Pop-Location }
}

function Invoke-StudyPilotInstall {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)
    $python = Get-RequiredCommandPath "python.exe" "Python 3.13"
    $npm = Get-RequiredCommandPath "npm.cmd" "npm"
    Write-Host "[1/3] 安装 Python 项目及开发依赖..."
    Invoke-CheckedCommand $python @("-m", "pip", "install", "--disable-pip-version-check", "-e", ".[dev]") $ProjectRoot "Python 依赖安装失败"
    $frontends = @((Join-Path $ProjectRoot "kid-frontend"))
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "parent-frontend\package.json") -PathType Leaf) { $frontends += Join-Path $ProjectRoot "parent-frontend" }
    foreach ($frontend in $frontends) {
        $package = Join-Path $frontend "package.json"
        if (-not (Test-Path -LiteralPath $package -PathType Leaf)) { throw "依赖安装失败：缺少 $package。" }
        $command = if (Test-Path -LiteralPath (Join-Path $frontend "package-lock.json")) { "ci" } else { "install" }
        Write-Host "安装 $([IO.Path]::GetFileName($frontend)) npm 依赖..."
        Invoke-CheckedCommand $npm @($command) $frontend "npm 依赖安装失败"
    }
    Write-Host "依赖安装完成。"
}

function Invoke-ModelMetadataCheck {
    try { $payload = Invoke-RestMethod -Method Get -Uri $script:LmMetadataUri -TimeoutSec 10 }
    catch { throw "LM Studio 预检失败：无法访问 http://127.0.0.1:1234/api/v0/models。" }
    $null = Assert-StudyPilotModelMetadata -Payload $payload
}

function Assert-ApiHealth {
    param([object]$Health)
    $model = Get-PropertyValue $Health "model"
    $modelId = Get-PropertyValue $model "model_id"
    if ((Get-PropertyValue $Health "ready") -ne $true -or (Get-PropertyValue (Get-PropertyValue $Health "api") "status") -ne "ok" -or (Get-PropertyValue (Get-PropertyValue $Health "sqlite") "status") -ne "ok" -or -not [string]::Equals([string]$modelId, $script:ExpectedModel, [StringComparison]::Ordinal) -or (Get-PropertyValue $model "loaded") -ne $true -or (Get-PropertyValue $model "tool_use") -ne $true) {
        throw "API 预检失败：/api/v1/health 未报告完整就绪状态。"
    }
}

function Invoke-ApiHealthCheck {
    try { $health = Invoke-RestMethod -Method Get -Uri $script:ApiHealthUri -TimeoutSec 5 }
    catch { throw "API 预检失败：无法访问 http://127.0.0.1:8040/api/v1/health。" }
    Assert-ApiHealth $health
}

function Assert-LoopbackPort {
    param([int]$Port, [string]$DisplayName, [object[]]$Listeners)
    $matches = @($Listeners | Where-Object { $_.LocalPort -eq $Port })
    if ($matches.Count -eq 0) { throw "$DisplayName 预检失败：端口 $Port 未监听。" }
    if (@($matches | Where-Object { $_.LocalAddress -ne "127.0.0.1" -and $_.LocalAddress -ne "::1" }).Count -gt 0) { throw "$DisplayName 预检失败：端口 $Port 不是仅回环监听。" }
}

function Write-TrackedPid {
    param([string]$Path, [int]$ProcessId)
    $temporary = "$Path.tmp"
    [IO.File]::WriteAllText($temporary, "$ProcessId`r`n", [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Start-TrackedService {
    param([object]$Service)
    foreach ($requiredPath in @($Service.Executable, $Service.SignatureTokens[0])) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) { throw "启动失败：缺少 $requiredPath，请先运行安装依赖。" }
    }
    $stamp = (Get-Date -Format "yyyyMMdd-HHmmss-fff")
    $stdout = Join-Path (Split-Path -Parent $Service.PidPath) "$($Service.Name)-$($Service.Port)-$stamp.out.log"
    $stderr = Join-Path (Split-Path -Parent $Service.PidPath) "$($Service.Name)-$($Service.Port)-$stamp.err.log"
    $process = Start-Process -FilePath $Service.Executable -ArgumentList $Service.Arguments -WorkingDirectory $Service.WorkingDirectory -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    for ($attempt = 0; $attempt -lt 40; $attempt += 1) {
        Start-Sleep -Milliseconds 250
        $listeners = @(Get-StudyPilotListeners)
        $candidate = Get-ValidatedListeningProcess -Service $Service -Listeners $listeners -LaunchedPid $process.Id
        if ($null -ne $candidate) {
            Write-TrackedPid $Service.PidPath $candidate.Pid
            Write-Host "$($Service.DisplayName) 已启动：127.0.0.1:$($Service.Port) (PID $($candidate.Pid))"
            return
        }
        if ($process.HasExited) { throw "$($Service.DisplayName) 启动失败，请查看日志 $stderr。" }
    }
    throw "$($Service.DisplayName) 启动失败：PID 未在预期回环端口 $($Service.Port) 监听；未终止任何未验证进程。"
}

function Invoke-StudyPilotStart {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$ProjectRoot, [switch]$DemoMode)
    Invoke-ModelMetadataCheck
    $runtimeRoot = Join-Path $ProjectRoot ".runtime"
    $null = New-Item -ItemType Directory -Path $runtimeRoot -Force
    $requestedMode = if ($DemoMode) { "demo" } else { "real" }
    $modePath = Join-Path $runtimeRoot "launch-mode.txt"
    $services = Get-ServiceDefinitions -ProjectRoot $ProjectRoot -ForStart
    $listeners = Get-StudyPilotListeners
    $running = @{}
    foreach ($service in $services) {
        $running[$service.Name] = Test-TrackedService $service $listeners
        if (-not $running[$service.Name] -and @($listeners | Where-Object { $_.LocalPort -eq $service.Port }).Count -gt 0) {
            throw "启动失败：端口 $($service.Port) 已被未验证进程占用；未终止或接管该进程。"
        }
    }
    $runningCount = @($running.Values | Where-Object { $_ }).Count
    if ($runningCount -gt 0) {
        $activeMode = if (Test-Path -LiteralPath $modePath -PathType Leaf) { (Get-Content -Raw -LiteralPath $modePath).Trim() } else { "" }
        if (-not [string]::Equals($activeMode, $requestedMode, [StringComparison]::Ordinal)) {
            throw "启动失败：当前端口由另一运行模式占用，请先运行停止决赛Demo.bat，再启动 $requestedMode 模式。"
        }
    }
    elseif (Test-Path -LiteralPath $modePath -PathType Leaf) {
        Remove-Item -LiteralPath $modePath -Force
    }
    Invoke-WithRuntimeEnvironment -DemoMode:$DemoMode {
        $api = $services | Where-Object Name -eq "api"
        if (-not $running["api"]) {
            Invoke-CheckedCommand $api.Executable @("`"$(Join-Path $ProjectRoot 'scripts\studypilot_service.py')`"", "migrate") $ProjectRoot "数据库迁移失败"
            Start-TrackedService $api
        } else { Write-Host "API 已由本启动器运行，跳过重复启动。" }
        for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
            try { Invoke-ApiHealthCheck; break } catch { if ($attempt -eq 19) { throw }; Start-Sleep -Milliseconds 500 }
        }
        foreach ($service in @($services | Where-Object Name -ne "api")) {
            if ($running[$service.Name]) { Write-Host "$($service.DisplayName) 已由本启动器运行，跳过重复启动。" }
            else { Start-TrackedService $service }
        }
    }
    [IO.File]::WriteAllText($modePath, "$requestedMode`r`n", [Text.UTF8Encoding]::new($false))
    Start-Process "http://127.0.0.1:8041"
    Write-Host "StudyPilot $requestedMode 模式启动完成。"
}

function Invoke-StudyPilotStop {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)
    $services = Get-ServiceDefinitions -ProjectRoot $ProjectRoot -IncludeParent
    foreach ($service in @($services | Sort-Object @{ Expression = { if ($_.Name -eq 'api') { 1 } else { 0 } } })) {
        $trackedPid = Read-TrackedPid $service.PidPath
        if ($null -eq $trackedPid) { Write-Host "$($service.DisplayName)：没有有效 PID 文件，已忽略。"; continue }
        $listeners = Get-StudyPilotListeners
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$trackedPid" -ErrorAction SilentlyContinue
        if ($null -eq $process -or -not (Test-StudyPilotProcessRecord -Process $process -Listeners $listeners -ExpectedPid $trackedPid -ExpectedProcessName $service.ProcessName -ProjectRoot $ProjectRoot -SignatureTokens $service.SignatureTokens -ExpectedPort $service.Port)) {
            Write-Host "$($service.DisplayName)：PID 文件已过期或不属于预期服务，已忽略且未终止进程。"
            continue
        }
        Stop-Process -Id $trackedPid -ErrorAction Stop
        Wait-Process -Id $trackedPid -Timeout 10 -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $service.PidPath -Force
        Write-Host "$($service.DisplayName) 已停止 (PID $trackedPid)。"
    }
    $remainingPidFiles = @($services | Where-Object { Test-Path -LiteralPath $_.PidPath -PathType Leaf })
    if ($remainingPidFiles.Count -eq 0) {
        $modePath = Join-Path (Join-Path $ProjectRoot ".runtime") "launch-mode.txt"
        if (Test-Path -LiteralPath $modePath -PathType Leaf) { Remove-Item -LiteralPath $modePath -Force }
    }
}

function Invoke-StudyPilotPreflight {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)
    Invoke-ModelMetadataCheck
    Invoke-ApiHealthCheck
    $listeners = Get-StudyPilotListeners
    Assert-LoopbackPort 8041 "孩子端" $listeners
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot "parent-frontend\package.json") -PathType Leaf) { Assert-LoopbackPort 8042 "家长端" $listeners }
    else { Write-Host "家长端未安装，按目录现状跳过 8042。" }
    Write-Host "现场预检通过：模型、API 和现有前端均已就绪。"
}

Export-ModuleMember -Function Assert-StudyPilotModelMetadata, Test-StudyPilotProcessRecord, Invoke-StudyPilotInstall, Invoke-StudyPilotStart, Invoke-StudyPilotStop, Invoke-StudyPilotPreflight
