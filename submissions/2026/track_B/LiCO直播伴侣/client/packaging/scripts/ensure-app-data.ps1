# Initialize %ProgramData%\blivechat data and config
param(
    [string]$AppDir = '',
    [string]$ConfigExample = ''
)

. "$PSScriptRoot\_common.ps1"
Initialize-BlivechatInstallLog

$dataRoot = Join-Path $env:ProgramData 'blivechat'
$dataDir = Join-Path $dataRoot 'data'
$logDir = Join-Path $dataRoot 'log'
$configPath = Join-Path $dataDir 'config.ini'

New-Item -ItemType Directory -Force -Path $dataDir, $logDir | Out-Null

if (-not (Test-Path $configPath)) {
    if ($ConfigExample -eq '' -and $AppDir -ne '') {
        $candidates = @(
            (Join-Path $AppDir 'data\config.example.ini'),
            (Join-Path $AppDir '_internal\data\config.example.ini')
        )
        foreach ($c in $candidates) {
            if (Test-Path $c) { $ConfigExample = $c; break }
        }
    }
    $pluginsDir = Join-Path $dataDir 'plugins'
    New-Item -ItemType Directory -Force -Path $pluginsDir | Out-Null
    if ($ConfigExample -ne '' -and (Test-Path $ConfigExample)) {
        Copy-Item -Force $ConfigExample $configPath
        $dbPath = Join-Path $dataDir 'database.db'
        $dbUrl = 'sqlite:///' + ($dbPath -replace '\\', '/')
        $lines = Get-Content -Path $configPath -Encoding UTF8
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^\s*database_url\s*=') {
                $lines[$i] = "database_url = $dbUrl"
                break
            }
        }
        [System.IO.File]::WriteAllLines($configPath, $lines, [System.Text.UTF8Encoding]::new($false))
        Write-BlivechatInstallLog "Created default config: $configPath (database_url=$dbUrl)"
    } else {
        Write-BlivechatInstallLog 'config.example.ini not found; skipped config init' -Level WARN
    }
} else {
    Write-BlivechatInstallLog "Keeping existing config: $configPath"
}

exit 0
