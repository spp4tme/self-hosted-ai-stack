$root = Split-Path $PSScriptRoot -Parent

Write-Host ""
Write-Host "  +----------------------------------+" -ForegroundColor DarkYellow
Write-Host "  |    JARVIS  --  DEMARRAGE STACK   |" -ForegroundColor DarkYellow
Write-Host "  +----------------------------------+" -ForegroundColor DarkYellow
Write-Host ""

# ── 1. dashboard_api.py ───────────────────────────────────────────────────
$existing = Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*dashboard_api.py*' }
if ($existing) {
    Write-Host "  [OK] dashboard_api.py  deja actif (port 9200)" -ForegroundColor Green
} else {
    Start-Process python `
        -ArgumentList "$root\scripts\dashboard_api.py" `
        -WorkingDirectory $root `
        -WindowStyle Hidden
    Write-Host "  [>>] dashboard_api.py  lance en arriere-plan (port 9200)" -ForegroundColor Cyan
}

# ── 2. Docker Compose ─────────────────────────────────────────────────────
Write-Host "  [>>] docker compose up -d ..." -ForegroundColor Cyan
Push-Location $root
$out = docker compose up -d 2>&1
Pop-Location
$out | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
Write-Host "  [OK] Stack Docker demarree" -ForegroundColor Green

# ── 3. Ouvrir le navigateur ───────────────────────────────────────────────
Write-Host "  [>>] Ouverture de dashboard.local ..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
Start-Process "https://dashboard.local"

Write-Host ""
Write-Host "  Tout est pret. Bonne session !" -ForegroundColor DarkYellow
Write-Host ""
Start-Sleep -Seconds 3
