# EatOrNot Claude Code Skill Installer (PowerShell)
# Usage: .\scripts\claude-setup\install.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SetupDir = Join-Path $ProjectRoot ".claude"
$SkillsDir = Join-Path $SetupDir "skills"

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  EatOrNot Claude Code Installer" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 1. Create .claude directories
if (-not (Test-Path $SkillsDir)) {
    New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null
    Write-Host "[OK] Created $SkillsDir" -ForegroundColor Green
} else {
    Write-Host "[--] Skills dir already exists" -ForegroundColor Gray
}

# 2. Copy skill directory (each skill is a subdirectory with SKILL.md)
$SkillSrcDir = Join-Path $PSScriptRoot "skills\meal-order"
$SkillDstDir = Join-Path $SkillsDir "meal-order"
if (Test-Path $SkillSrcDir) {
    # Remove old flat-file skill if it exists (migration from old format)
    if (Test-Path (Join-Path $SkillsDir "meal-order.md")) {
        Remove-Item (Join-Path $SkillsDir "meal-order.md") -Force
        Write-Host "[..] Removed old flat-file skill format" -ForegroundColor Yellow
    }
    # Copy entire skill directory
    if (Test-Path $SkillDstDir) {
        Remove-Item $SkillDstDir -Recurse -Force
    }
    Copy-Item -Path $SkillSrcDir -Destination $SkillDstDir -Recurse -Force
    Write-Host "[OK] Installed skill: meal-order" -ForegroundColor Green
} else {
    Write-Host "[ERR] Skill source not found: $SkillSrcDir" -ForegroundColor Red
    exit 1
}

# 3. Auto-merge settings.local.json permissions
$SettingsTemplate = Join-Path $PSScriptRoot "settings.local.json.template"
$SettingsDst = Join-Path $SetupDir "settings.local.json"

if (Test-Path $SettingsDst) {
    Write-Host "[--] Found existing settings.local.json, merging permissions..." -ForegroundColor Yellow

    # Read existing settings
    $existing = Get-Content -Path $SettingsDst -Raw -Encoding UTF8 | ConvertFrom-Json
    $template = Get-Content -Path $SettingsTemplate -Raw -Encoding UTF8 | ConvertFrom-Json

    # Collect existing allows into a HashSet
    $existingAllows = [System.Collections.Generic.HashSet[string]]::new()
    if ($existing.permissions.allow) {
        foreach ($a in $existing.permissions.allow) {
            $existingAllows.Add($a) | Out-Null
        }
    }

    # Add template allows that aren't already present
    $added = 0
    if ($template.permissions.allow) {
        foreach ($a in $template.permissions.allow) {
            if ($existingAllows.Add($a)) {
                $added++
            }
        }
    }

    # Write back merged settings
    $merged = @{
        permissions = @{
            allow = @($existingAllows | Sort-Object)
        }
    }
    $merged | ConvertTo-Json -Depth 10 | Set-Content -Path $SettingsDst -Encoding UTF8
    Write-Host "[OK] Merged $added new permissions into settings.local.json" -ForegroundColor Green
} else {
    Copy-Item -Path $SettingsTemplate -Destination $SettingsDst -Force
    Write-Host "[OK] Created settings.local.json from template" -ForegroundColor Green
}

# 4. Configure McDonald's MCP server
Write-Host ""
Write-Host "--- McDonald's MCP 配置 ---" -ForegroundColor Cyan
Write-Host ""

# Check if mcd-mcp is already configured
$mcpCheck = claude mcp list 2>$null | Select-String "mcd-mcp"

if ($mcpCheck) {
    Write-Host "[--] mcd-mcp already configured (user scope)" -ForegroundColor Gray
    Write-Host "     $mcpCheck" -ForegroundColor Gray
} else {
    Write-Host "麦当劳 MCP 用于终端点餐功能（查菜单、下单、领券等）。" -ForegroundColor White
    Write-Host "需要你自己的麦当劳 MCP Token。" -ForegroundColor White
    Write-Host ""
    Write-Host "获取方式：" -ForegroundColor Yellow
    Write-Host "  1. 访问 https://mcp.mcd.cn 或联系麦当劳 MCP 服务获取 Token"
    Write-Host "  2. 如果暂时没有 Token，可以跳过（将使用 Mock 数据）"
    Write-Host ""

    $token = Read-Host "请输入你的麦当劳 MCP Token（留空跳过）"

    if ($token.Trim() -ne "") {
        Write-Host "[..] Configuring mcd-mcp..." -ForegroundColor Yellow
        claude mcp add -t http -s user mcd-mcp https://mcp.mcd.cn -H "Authorization: Bearer $($token.Trim())"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] mcd-mcp configured successfully" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Failed to configure mcd-mcp. You can run manually:" -ForegroundColor Yellow
            Write-Host '       claude mcp add -t http -s user mcd-mcp https://mcp.mcd.cn -H "Authorization: Bearer YOUR_TOKEN"' -ForegroundColor Yellow
        }
    } else {
        Write-Host "[SKIP] mcd-mcp not configured. Terminal ordering will use mock data." -ForegroundColor Yellow
        Write-Host "       To configure later:" -ForegroundColor Yellow
        Write-Host '       claude mcp add -t http -s user mcd-mcp https://mcp.mcd.cn -H "Authorization: Bearer YOUR_TOKEN"' -ForegroundColor Yellow
    }
}

# 5. Summary
Write-Host ""
Write-Host "-------------------------------------" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "-------------------------------------" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Skills:   $(@('meal-order').Length) installed"
Write-Host "  Config:   $SettingsDst"
$skillCount = (Get-ChildItem $SkillsDir -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') } | Measure-Object).Count
Write-Host "  Total:    $skillCount skill(s) in .claude/skills/"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Restart Claude Code (or /reload session)"
Write-Host "  2. Say: '帮我点午餐' to test the meal-order skill"
Write-Host "  3. Say: '开启饭点提醒' to enable cron reminders"
Write-Host ""
