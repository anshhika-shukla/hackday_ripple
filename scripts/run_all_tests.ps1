# PowerShell test runner for all RIPPLE acceptance test suites
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🌊 Running RIPPLE Complete Acceptance Test Suite (Phases 1-6)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$suites = @(
    "tests/test_diffmap.py",
    "tests/test_impact.py",
    "tests/test_triage.py",
    "tests/test_eval_harness.py",
    "tests/test_cli_e2e.py",
    "tests/test_ripplemap.py",
    "tests/test_draft.py"
)

$passedAll = $true

foreach ($suite in $suites) {
    Write-Host "`n>>> Running $suite..." -ForegroundColor Yellow
    python -m pytest $suite -v
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Suite failed: $suite" -ForegroundColor Red
        $passedAll = $false
    } else {
        Write-Host "✅ Passed: $suite" -ForegroundColor Green
    }
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
if ($passedAll) {
    Write-Host "🎉 ALL 38 ACCEPTANCE TESTS PASSED! RIPPLE IS READY!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Some tests failed. Please inspect the output above." -ForegroundColor Red
}
Write-Host "==========================================================" -ForegroundColor Cyan
