# Set bundled plugin.json enabled=false for packaged installs (no per-plugin exe yet).
param(
    [Parameter(Mandatory = $true)]
    [string]$PluginsDir
)

if (-not (Test-Path $PluginsDir)) {
    Write-Warning "Plugins dir not found: $PluginsDir"
    exit 0
}

Get-ChildItem -Path $PluginsDir -Directory | ForEach-Object {
    $jsonPath = Join-Path $_.FullName 'plugin.json'
    if (-not (Test-Path $jsonPath)) { return }
    $raw = Get-Content -Path $jsonPath -Raw -Encoding UTF8
    try {
        $cfg = $raw | ConvertFrom-Json
    } catch {
        Write-Warning "Skip invalid plugin.json: $jsonPath"
        return
    }
    if ($cfg.enabled -eq $true) {
        $cfg.enabled = $false
        $json = ($cfg | ConvertTo-Json -Depth 10)
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($jsonPath, $json, $utf8NoBom)
        Write-Host "Disabled bundled plugin by default: $($_.Name)"
    }
}

exit 0
