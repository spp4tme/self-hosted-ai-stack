# Ajoute les domaines .local manquants au fichier hosts
# Lancer ce script avec : Clic droit -> Exécuter avec PowerShell (en tant qu'administrateur)

$hostsFile = "C:\Windows\System32\drivers\etc\hosts"

$domains = @(
    "127.0.0.1 crewai.local",
    "127.0.0.1 comfyui.local"
)

$content = Get-Content $hostsFile -Raw

foreach ($line in $domains) {
    $domain = $line.Split(" ")[1]
    if ($content -notmatch [regex]::Escape($domain)) {
        "`n$line" | Out-File -FilePath $hostsFile -Append -Encoding ascii
        Write-Host "Ajouté : $line" -ForegroundColor Green
    } else {
        Write-Host "Déjà présent : $domain" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Fichier hosts mis à jour. Vérification :" -ForegroundColor Cyan
Get-Content $hostsFile | Select-String "127.0.0.1.*\.local"
