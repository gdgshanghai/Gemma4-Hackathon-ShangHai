[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Push-Location -LiteralPath $ProjectRoot
try {
    python scripts/lm_studio_preflight.py
    if ($LASTEXITCODE -ne 0) {
        throw "LM Studio Native Function Calling preflight failed."
    }

    python -m pytest `
        "tests/real_lm/test_evening_intake_fc.py::test_real_gemma_saves_chinese_evening_intake_draft" `
        -q -m real_lm
    if ($LASTEXITCODE -ne 0) {
        throw "The real Gemma multi-subject scenario failed."
    }

    python -m pytest `
        "tests/integration/api/test_evenings.py::test_second_intake_turn_sends_cumulative_child_report_to_model" `
        "tests/integration/api/test_evenings.py::test_capacity_conflict_offers_child_adjustment_and_replans_without_parent" `
        "tests/unit/storage/test_evening_history.py::test_completed_deviation_changes_the_next_matching_task_estimate" `
        -q
    if ($LASTEXITCODE -ne 0) {
        throw "One or more deterministic V14 scenarios failed."
    }

    Write-Host "V14 demo checks: PASS (4/4 synthetic functional scenarios)"
}
finally {
    Pop-Location
}
