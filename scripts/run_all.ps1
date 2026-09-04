# ==============================================================================
# Razorpay Return-Risk Intelligence Engine - Windows PowerShell Runner
# ==============================================================================

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "Starting Razorpay Return-Risk Intelligence Engine" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan

$processes = @()

# 1. Scoring API
Write-Host "Starting Scoring API on http://127.0.0.1:8000 (Metrics: /metrics)..." -ForegroundColor Green
$apiProc = Start-Process -FilePath "venv\Scripts\python.exe" -ArgumentList "-m uvicorn src.app:app --host 0.0.0.0 --port 8000" -PassThru -NoNewWindow
$processes += $apiProc

# 2. Dashboard BFF
Write-Host "Starting Dashboard BFF on http://127.0.0.1:8001 (Metrics: /metrics)..." -ForegroundColor Green
$bffProc = Start-Process -FilePath "venv\Scripts\python.exe" -ArgumentList "-m uvicorn src.dashboard.api:app --host 0.0.0.0 --port 8001" -PassThru -NoNewWindow
$processes += $bffProc

# 3. SHAP Worker
Write-Host "Starting TreeSHAP Worker daemon..." -ForegroundColor Green
$shapProc = Start-Process -FilePath "venv\Scripts\python.exe" -ArgumentList "scripts\run_shap_worker.py --poll-interval 0.5" -PassThru -NoNewWindow
$processes += $shapProc

Write-Host "`nAll background Python services started!" -ForegroundColor Cyan
Write-Host "  - Scoring API:    http://localhost:8000" -ForegroundColor Yellow
Write-Host "  - Dashboard BFF:  http://localhost:8001" -ForegroundColor Yellow
Write-Host "To start the frontend, open another terminal and run: cd frontend; npm run dev" -ForegroundColor Gray
Write-Host "Press Ctrl+C to terminate services." -ForegroundColor White

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`nStopping services..." -ForegroundColor Red
    foreach ($p in $processes) {
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "All services stopped." -ForegroundColor Red
}
