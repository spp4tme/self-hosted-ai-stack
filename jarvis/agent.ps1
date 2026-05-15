# Jarvis Agent v3 — PC/Media + outils IA (fichiers, Python, web)
# Usage: powershell -ExecutionPolicy Bypass -File jarvis\agent.ps1
# Ports : http://localhost:9999/gesture  (gestes)
#         http://localhost:9999/tool/*   (agent IA)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class WinKey {
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte vk, byte sc, int fl, int ei);
    public static void Press(byte vk) {
        keybd_event(vk, 0, 0, 0);
        System.Threading.Thread.Sleep(30);
        keybd_event(vk, 0, 2, 0);
    }
    public static void Hold(byte vk)    { keybd_event(vk, 0, 0, 0); }
    public static void Release(byte vk) { keybd_event(vk, 0, 2, 0); }
    public static void Combo(byte mod, byte key) {
        keybd_event(mod, 0, 0, 0);
        System.Threading.Thread.Sleep(60);
        keybd_event(key, 0, 0, 0);
        System.Threading.Thread.Sleep(30);
        keybd_event(key, 0, 2, 0);
        System.Threading.Thread.Sleep(60);
        keybd_event(mod, 0, 2, 0);
    }
}
"@

$VK = @{
    PLAY_PAUSE = [byte]0xB3; NEXT = [byte]0xB0; PREV = [byte]0xB1
    VOL_UP     = [byte]0xAF; VOL_DOWN = [byte]0xAE; MUTE = [byte]0xAD
    WIN        = [byte]0x5B; ALT  = [byte]0x12; CTRL = [byte]0x11
    SHIFT      = [byte]0x10; TAB  = [byte]0x09; F4   = [byte]0x73
    D          = [byte]0x44; L    = [byte]0x4C; ESC  = [byte]0x1B
}

function Invoke-Gesture {
    param([string]$Mode, [string]$Gesture)
    switch ("${Mode}|${Gesture}") {
        "MEDIA|STOP"      { [WinKey]::Press($VK.PLAY_PAUSE);           return "Pause activee" }
        "MEDIA|NAVIGATE"  { [WinKey]::Press($VK.NEXT);                 return "Piste suivante" }
        "MEDIA|SELECT"    { [WinKey]::Press($VK.PREV);                 return "Piste precedente" }
        "MEDIA|VALIDATE"  { [WinKey]::Press($VK.VOL_UP);               return "Volume plus" }
        "MEDIA|SCROLL"    { [WinKey]::Press($VK.VOL_DOWN);             return "Volume moins" }
        "MEDIA|STOP_HOLD" { [WinKey]::Press($VK.MUTE);                 return "Muet" }
        "PC|STOP"         { [WinKey]::Combo($VK.WIN, $VK.D);           return "Bureau affiche" }
        "PC|NAVIGATE"     { [WinKey]::Combo($VK.ALT, $VK.TAB);        return "Fenetre suivante" }
        "PC|SELECT"       { [WinKey]::Combo($VK.ALT, $VK.F4);         return "Fenetre fermee" }
        "PC|VALIDATE"     { [WinKey]::Press($VK.WIN);                  return "Menu Demarrer" }
        "PC|SCROLL"       { [WinKey]::Combo($VK.WIN, $VK.TAB);        return "Vue des taches" }
        "PC|STOP_HOLD"    { [WinKey]::Combo($VK.WIN, $VK.L);          return "Ecran verrouille" }
        default           { return "OK" }
    }
}

function Invoke-Tool {
    param([string]$Tool, [System.Net.HttpListenerRequest]$Req)

    $BASE = "C:\Users\antho\Documents\mon-ia"

    # ── list_files (GET) ──────────────────────────────────────────────────────
    if ($Tool -eq "list_files") {
        $dirPath  = if ($Req.QueryString["path"]) { $Req.QueryString["path"] } else { $BASE }
        $resolved = [System.IO.Path]::GetFullPath($dirPath)
        $items = Get-ChildItem -Path $resolved -ErrorAction Stop | ForEach-Object {
            [ordered]@{
                name = $_.Name
                type = if ($_.PSIsContainer) { "dir" } else { "file" }
                size = if ($_.PSIsContainer) { 0 } else { $_.Length }
                modified = $_.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
            }
        }
        return [ordered]@{ ok = $true; path = $resolved; items = @($items) } |
               ConvertTo-Json -Depth 4 -Compress
    }

    # Lire le body JSON (outils POST)
    $reader  = [System.IO.StreamReader]::new($Req.InputStream, [System.Text.Encoding]::UTF8)
    $rawBody = $reader.ReadToEnd()
    $body    = $rawBody | ConvertFrom-Json

    # ── read_file (POST) ──────────────────────────────────────────────────────
    if ($Tool -eq "read_file") {
        $resolved = [System.IO.Path]::GetFullPath($body.path)
        if (-not $resolved.StartsWith($BASE)) { throw "Acces refuse: chemin hors de mon-ia" }
        $content = Get-Content -Path $resolved -Raw -Encoding UTF8 -ErrorAction Stop
        if ($content.Length -gt 51200) { $content = $content.Substring(0, 51200) + "`n...[tronque]" }
        return [ordered]@{ ok = $true; path = $resolved; content = $content } |
               ConvertTo-Json -Depth 2 -Compress
    }

    # ── write_file (POST) ─────────────────────────────────────────────────────
    if ($Tool -eq "write_file") {
        $resolved = [System.IO.Path]::GetFullPath($body.path)
        if (-not $resolved.StartsWith($BASE)) { throw "Acces refuse: chemin hors de mon-ia" }
        $dir = [System.IO.Path]::GetDirectoryName($resolved)
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Set-Content -Path $resolved -Value $body.content -Encoding UTF8 -ErrorAction Stop
        return [ordered]@{ ok = $true; path = $resolved; bytes_written = $body.content.Length } |
               ConvertTo-Json -Compress
    }

    # ── run_python (POST) ─────────────────────────────────────────────────────
    if ($Tool -eq "run_python") {
        $guid = [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
        $tmp  = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "jarvis_$guid.py")
        Set-Content -Path $tmp -Value $body.code -Encoding UTF8
        $output = & python $tmp 2>&1
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        $outStr = ($output -join "`n")
        if ($outStr.Length -gt 8192) { $outStr = $outStr.Substring(0, 8192) + "`n...[tronque]" }
        return [ordered]@{ ok = $true; output = $outStr } | ConvertTo-Json -Compress
    }

    throw "Outil inconnu: $Tool"
}

# ── Serveur HTTP ──────────────────────────────────────────────────────────────
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add("http://localhost:9999/")
$listener.Start()

Write-Host ""
Write-Host "  Jarvis Agent v3 -- Port 9999" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  POST /gesture              : controle PC/Media" -ForegroundColor Green
Write-Host "  GET  /tool/list_files      : liste un dossier" -ForegroundColor Magenta
Write-Host "  POST /tool/read_file       : lit un fichier" -ForegroundColor Magenta
Write-Host "  POST /tool/write_file      : ecrit un fichier" -ForegroundColor Magenta
Write-Host "  POST /tool/run_python      : execute du Python" -ForegroundColor Magenta
Write-Host "  GET  /health               : statut" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Ctrl+C pour arreter`n"

try {
    while ($listener.IsListening) {
        $ctx = $listener.GetContext()
        $req = $ctx.Request
        $res = $ctx.Response

        $res.Headers.Add("Access-Control-Allow-Origin",  "*")
        $res.Headers.Add("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        $res.Headers.Add("Access-Control-Allow-Headers", "Content-Type")

        if ($req.HttpMethod -eq "OPTIONS") {
            $res.StatusCode = 204; $res.Close(); continue
        }

        $responseBody = '{"ok":true}'
        $statusCode   = 200

        try {
            $path = $req.Url.LocalPath

            # ── /gesture ──────────────────────────────────────────────────────
            if ($req.HttpMethod -eq "POST" -and $path -eq "/gesture") {
                $reader  = [System.IO.StreamReader]::new($req.InputStream, [System.Text.Encoding]::UTF8)
                $body    = $reader.ReadToEnd() | ConvertFrom-Json
                $mode    = ($body.mode    -replace '[^A-Za-z]',   '').ToUpper()
                $gesture = ($body.gesture -replace '[^A-Za-z_]',  '').ToUpper()
                $gesture = $gesture -replace 'NAVIGUER','NAVIGATE' `
                                    -replace 'SELECTIONNER','SELECT' `
                                    -replace 'VALIDER','VALIDATE'
                $action  = Invoke-Gesture -Mode $mode -Gesture $gesture
                $ts      = Get-Date -Format "HH:mm:ss"
                $color   = switch ($mode) { "MEDIA"{"Green"} "PC"{"Cyan"} "IA"{"Magenta"} default{"White"} }
                Write-Host "  [$ts]  " -NoNewline
                Write-Host "$mode" -ForegroundColor $color -NoNewline
                Write-Host "  |  $gesture  ->  $action"
                $responseBody = "{`"ok`":true,`"action`":`"$action`"}"

            # ── /tool/* ───────────────────────────────────────────────────────
            } elseif ($path -like "/tool/*") {
                $toolName     = $path.Substring(6)   # retire "/tool/"
                $responseBody = Invoke-Tool -Tool $toolName -Req $req
                $ts = Get-Date -Format "HH:mm:ss"
                Write-Host "  [$ts]  " -NoNewline
                Write-Host "TOOL" -ForegroundColor Magenta -NoNewline
                Write-Host "  |  $($req.HttpMethod) $toolName"

            # ── /health ───────────────────────────────────────────────────────
            } elseif ($path -eq "/health") {
                $responseBody = '{"ok":true,"service":"jarvis-agent","version":"3","tools":["list_files","read_file","write_file","run_python"]}'

            } else {
                $responseBody = '{"ok":false,"error":"Not found"}'
                $statusCode   = 404
            }

        } catch {
            Write-Host "  [ERREUR] $_" -ForegroundColor Red
            $errMsg = ($_.ToString() -replace '"', "'") -replace '\\', '\\\\'
            $responseBody = "{`"ok`":false,`"error`":`"$errMsg`"}"
            $statusCode   = 500
        }

        $bytes = [System.Text.Encoding]::UTF8.GetBytes($responseBody)
        $res.ContentType     = "application/json; charset=utf-8"
        $res.StatusCode      = $statusCode
        $res.ContentLength64 = $bytes.Length
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
        $res.Close()
    }
} finally {
    $listener.Stop()
    Write-Host "`n  Agent arrete." -ForegroundColor Yellow
}
