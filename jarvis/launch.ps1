# Jarvis Launcher v2 — lance l'agent + la detection en une commande
# Usage: powershell -ExecutionPolicy Bypass -File jarvis\launch.ps1

$JARVIS_DIR = $PSScriptRoot

Write-Host ""
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host "      JARVIS DESKTOP v2  -  Launcher    " -ForegroundColor Cyan
Write-Host "  ======================================" -ForegroundColor Cyan
Write-Host ""

# -- Verification Python --
Write-Host "  Verification de l'environnement..." -ForegroundColor Gray

$pythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    $ver = ""
    try { $ver = (& $candidate --version 2>&1).ToString() } catch { $ver = "" }
    if ($ver -match "Python 3") {
        $pythonCmd = $candidate
        Write-Host "  Python : $ver" -ForegroundColor Green
        break
    }
}

if ($null -eq $pythonCmd) {
    Write-Host "  [ERREUR] Python 3 introuvable." -ForegroundColor Red
    Write-Host "  Installez Python 3.10+ depuis https://python.org"
    pause
    exit 1
}

# -- Verification dependances --
$required = @("mediapipe", "cv2", "requests")
$missing  = @()
foreach ($mod in $required) {
    $out = & $pythonCmd -c "import $mod; print('ok')" 2>&1
    if ($out -notmatch "ok") { $missing += $mod }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  [ATTENTION] Modules manquants : $($missing -join ', ')" -ForegroundColor Yellow
    Write-Host "  Lancez : pip install mediapipe>=0.10 opencv-python requests" -ForegroundColor Yellow
    Write-Host "  Optionnel : pip install pystray Pillow win10toast" -ForegroundColor Gray
    Write-Host ""
    $rep = Read-Host "  Continuer quand meme ? (O/N)"
    if ($rep -notmatch "^[Oo]") { exit 1 }
}

# -- Lancement agent PowerShell (port 9999) --
Write-Host ""
Write-Host "  Demarrage agent HTTP (port 9999)..." -ForegroundColor Cyan

$agentPath = Join-Path $JARVIS_DIR "agent.ps1"
if (-not (Test-Path $agentPath)) {
    Write-Host "  [ERREUR] agent.ps1 introuvable : $agentPath" -ForegroundColor Red
    exit 1
}

$agentProc = Start-Process powershell `
    -ArgumentList "-ExecutionPolicy Bypass -WindowStyle Minimized -File `"$agentPath`"" `
    -PassThru

Write-Host "  Agent demarre (PID $($agentProc.Id))" -ForegroundColor Green
Start-Sleep -Milliseconds 800

# -- Lancement desktop.py --
Write-Host "  Demarrage Jarvis Desktop..." -ForegroundColor Cyan
Write-Host "  [ Q ] dans la fenetre camera pour tout arreter" -ForegroundColor Gray
Write-Host ""
Write-Host "  --------------------------------------" -ForegroundColor DarkGray

$desktopPath = Join-Path $JARVIS_DIR "desktop.py"
if (-not (Test-Path $desktopPath)) {
    Write-Host "  [ERREUR] desktop.py introuvable : $desktopPath" -ForegroundColor Red
    Stop-Process -Id $agentProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

try {
    & $pythonCmd $desktopPath
} finally {
    Write-Host ""
    Write-Host "  Arret de l'agent..." -ForegroundColor Yellow
    Stop-Process -Id $agentProc.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  Jarvis arrete. A bientot !" -ForegroundColor Cyan
    Write-Host ""
}
