# Collect install/app logs and environment into a bug report zip
param(
    [string]$OutputZip = ''
)

. "$PSScriptRoot\_common.ps1"

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$reportDir = Join-Path $env:TEMP "blivechat-bug-report-$stamp"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

function Copy-IfExists {
    param([string]$Path, [string]$DestName)
    if (Test-Path $Path) {
        Copy-Item -Force $Path (Join-Path $reportDir $DestName)
    }
}

$installLog = Join-Path $env:ProgramData 'blivechat\install.log'
$appLog = Join-Path $env:ProgramData 'blivechat\log\blivechat.log'

Copy-IfExists $installLog 'install.log'
Copy-IfExists $appLog 'blivechat.log'

@(
    "Time: $(Get-Date -Format o)",
    "OS: $([System.Environment]::OSVersion.VersionString)",
    "64bit OS: $([System.Environment]::Is64BitOperatingSystem)",
    "Computer: $env:COMPUTERNAME",
    "User: $env:USERNAME",
    "ProgramFiles: ${env:ProgramFiles}",
    "APPDATA: $env:APPDATA",
    "PATH: $env:PATH"
) | Set-Content -Path (Join-Path $reportDir 'environment.txt') -Encoding UTF8

foreach ($tool in @('python', 'cmake', 'ffmpeg', 'ffprobe', 'winget')) {
    $exe = Find-ExecutableOnPath $tool
    $line = if ($exe) { "$tool=$exe" } else { "$tool=(not found)" }
    Add-Content -Path (Join-Path $reportDir 'tools.txt') -Value $line
}

$obsPaths = @(
    "${env:ProgramFiles}\obs-studio\bin\64bit\obs64.exe",
    (Join-Path $env:APPDATA 'obs-studio\plugins\obs-blivechat-bridge\bin\64bit\obs-blivechat-bridge.dll')
)
$obsInfo = foreach ($p in $obsPaths) {
    if (Test-Path $p) { "FOUND $p" } else { "MISSING $p" }
}
$obsInfo | Set-Content -Path (Join-Path $reportDir 'obs-paths.txt') -Encoding UTF8

if ($OutputZip -eq '') {
    $OutputZip = Join-Path ([Environment]::GetFolderPath('Desktop')) "blivechat-bug-report-$stamp.zip"
}

if (Test-Path $OutputZip) { Remove-Item -Force $OutputZip }
Compress-Archive -Path (Join-Path $reportDir '*') -DestinationPath $OutputZip -Force
Remove-Item -Recurse -Force $reportDir

Write-Host "Bug report saved: $OutputZip"
exit 0
