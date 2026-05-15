# Jarvis Agent — Controle PC et Media depuis les gestes
# Usage: powershell -ExecutionPolicy Bypass -File scripts\jarvis_agent.ps1

Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public class WinKey {
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte vk, byte sc, int fl, int ei);
    public static void Press(byte vk) {
        keybd_event(vk, 0, 0, 0);
        keybd_event(vk, 0, 2, 0);
    }
    public static void Hold(byte vk)    { keybd_event(vk, 0, 0, 0); }
    public static void Release(byte vk) { keybd_event(vk, 0, 2, 0); }
}
"@

# Virtual key codes Windows
$VK = @{
    PLAY_PAUSE = [byte]0xB3
    NEXT       = [byte]0xB0
    PREV       = [byte]0xB1
    STOP       = [byte]0xB2
    VOL_UP     = [byte]0xAF
    VOL_DOWN   = [byte]0xAE
    MUTE       = [byte]0xAD
    WIN        = [byte]0x5B
    ALT        = [byte]0x12
    CTRL       = [byte]0x11
    SHIFT      = [byte]0x10
    TAB        = [byte]0x09
    F4         = [byte]0x73
    D          = [byte]0x44
    ESC        = [byte]0x1B
}

function Invoke-Action($mode, $gesture) {
    switch ("${mode}|${gesture}") {

        # --- MEDIA ---
        # paume  = pause/play  (geste stop universel)
        "MEDIA|STOP"         { [WinKey]::Press($VK.PLAY_PAUSE) }
        # index  = suivant     (pointer en avant)
        "MEDIA|NAVIGUER"     { [WinKey]::Press($VK.NEXT) }
        # poing  = precedent   (reculer)
        "MEDIA|SELECTIONNER" { [WinKey]::Press($VK.PREV) }
        # pouce  = volume +    (pouce en haut = plus)
        "MEDIA|VALIDER"      { [WinKey]::Press($VK.VOL_UP) }
        # 2 doigts = volume -  (doux/moderer)
        "MEDIA|SCROLL"       { [WinKey]::Press($VK.VOL_DOWN) }

        # --- PC ---
        # paume  = bureau      (main vide = ecran vide)
        "PC|STOP" {
            [WinKey]::Hold($VK.WIN)
            [WinKey]::Press($VK.D)
            [WinKey]::Release($VK.WIN)
        }
        # index  = Alt+Tab     (naviguer entre les apps)
        "PC|NAVIGUER" {
            [WinKey]::Hold($VK.ALT)
            Start-Sleep -Milliseconds 60
            [WinKey]::Press($VK.TAB)
            Start-Sleep -Milliseconds 60
            [WinKey]::Release($VK.ALT)
        }
        # poing  = Alt+F4      (fermer de force)
        "PC|SELECTIONNER" {
            [WinKey]::Hold($VK.ALT)
            [WinKey]::Press($VK.F4)
            [WinKey]::Release($VK.ALT)
        }
        # pouce  = Demarrer    (le bouton principal de Windows)
        "PC|VALIDER" {
            [WinKey]::Press($VK.WIN)
        }
        # 2 doigts = Win+Tab   (vue d'ensemble des taches)
        "PC|SCROLL" {
            [WinKey]::Hold($VK.WIN)
            [WinKey]::Press($VK.TAB)
            [WinKey]::Release($VK.WIN)
        }
    }
}

# Demarrage du serveur HTTP
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add("http://localhost:9999/")
$listener.Start()

Write-Host ""
Write-Host "  Jarvis Agent actif sur http://localhost:9999" -ForegroundColor Green
Write-Host "  Modes supportes : MEDIA, PC" -ForegroundColor Cyan
Write-Host "  Ctrl+C pour arreter`n"

try {
    while ($listener.IsListening) {
        $ctx = $listener.GetContext()
        $req = $ctx.Request
        $res = $ctx.Response

        # CORS — autoriser appels depuis le navigateur
        $res.Headers.Add("Access-Control-Allow-Origin",  "*")
        $res.Headers.Add("Access-Control-Allow-Methods", "POST, OPTIONS")
        $res.Headers.Add("Access-Control-Allow-Headers", "Content-Type")

        if ($req.HttpMethod -eq "OPTIONS") {
            $res.StatusCode = 204
            $res.Close()
            continue
        }

        if ($req.HttpMethod -eq "POST" -and $req.Url.LocalPath -eq "/gesture") {
            try {
                $reader = [System.IO.StreamReader]::new($req.InputStream)
                $body   = $reader.ReadToEnd() | ConvertFrom-Json

                $mode    = ($body.mode).ToUpper()
                $gesture = ($body.gesture).ToUpper() -replace 'É','E' -replace 'È','E' -replace 'Ê','E'

                Invoke-Action $mode $gesture

                $ts = Get-Date -Format "HH:mm:ss"
                Write-Host "  [$ts]  $mode  ·  $($body.gesture)" -ForegroundColor Cyan
            } catch {
                Write-Host "  Erreur: $_" -ForegroundColor Red
            }
        }

        $bytes = [System.Text.Encoding]::UTF8.GetBytes('{"ok":true}')
        $res.ContentType = "application/json"
        $res.StatusCode  = 200
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
        $res.Close()
    }
} finally {
    $listener.Stop()
    Write-Host "`n  Agent arrete." -ForegroundColor Yellow
}
