# Show graphical summary after setup (Chinese UI)
param(
    [string]$ResultFile = '',
    [string]$LogFile = ''
)

if ($ResultFile -eq '') {
    $ResultFile = Join-Path $env:ProgramData 'blivechat\install-result.json'
}
if ($LogFile -eq '') {
    $LogFile = Join-Path $env:ProgramData 'blivechat\install.log'
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('blivechat 安装完成')
$lines.Add('')

if (Test-Path $ResultFile) {
    try {
        $data = Get-Content $ResultFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($data.obs_plugin) {
            $p = $data.obs_plugin
            $lines.Add(("OBS 插件: {0} ({1})" -f $p.status, $p.source))
            if ($p.message) { $lines.Add("  " + $p.message) }
        }
        if ($data.ffmpeg) {
            $f = $data.ffmpeg
            $lines.Add(("FFmpeg: {0} ({1})" -f $f.status, $f.source))
            if ($f.message) { $lines.Add("  " + $f.message) }
        }
        if ($data.obs_studio) {
            $o = $data.obs_studio
            $lines.Add(("OBS Studio: {0} ({1})" -f $o.status, $o.source))
            if ($o.message) { $lines.Add("  " + $o.message) }
        }
    } catch {
        $lines.Add('无法读取安装结果文件。')
    }
} else {
    $lines.Add('核心文件已安装。')
}

$manual = $lines | Where-Object { $_ -match 'manual_required|Download:|下载' }
if ($manual.Count -gt 0) {
    $lines.Add('')
    $lines.Add('部分组件需您手动安装（见上方说明或打开下载链接）。')
}

$lines.Add('')
$lines.Add("详细日志: $LogFile")

$text = $lines -join "`r`n"
$icon = [System.Windows.Forms.MessageBoxIcon]::Information
if ($text -match 'manual_required|需您手动') {
    $icon = [System.Windows.Forms.MessageBoxIcon]::Warning
}

try {
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show(
        $text,
        'blivechat 安装向导',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        $icon
    )
} catch {
    Write-Host $text
}
