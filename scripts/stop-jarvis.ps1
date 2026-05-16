$root = Split-Path $PSScriptRoot -Parent

Write-Host ""
Write-Host "  +----------------------------------+" -ForegroundColor Red
Write-Host "  |     JARVIS  --  ARRET STACK      |" -ForegroundColor Red
Write-Host "  +----------------------------------+" -ForegroundColor Red
Write-Host ""

# ── 1. Docker Compose ─────────────────────────────────────────────────────
Write-Host "  [>>] docker compose down ..." -ForegroundColor Cyan
Push-Location $root
$out = docker compose down 2>&1
Pop-Location
$out | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
Write-Host "  [OK] Stack Docker arretee" -ForegroundColor Green

# ── 2. Tuer dashboard_api.py ──────────────────────────────────────────────
$procs = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*dashboard_api.py*' }
if ($procs) {
    $procs | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  [OK] dashboard_api.py arrete" -ForegroundColor Green
} else {
    Write-Host "  [--] dashboard_api.py non actif" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  Stack Jarvis eteinte." -ForegroundColor Red
Write-Host ""
Start-Sleep -Seconds 3
