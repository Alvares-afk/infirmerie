# Enregistre ou retire le nom "infirmerie" dans le fichier hosts de Windows.
# Usage : nom.ps1 -action ajouter   |   nom.ps1 -action retirer
param([string]$action = "ajouter")

$nom = "infirmerie"
$marqueur = "# infirmerie-locale"
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"

$lignes = Get-Content $hosts -ErrorAction SilentlyContinue
if ($null -eq $lignes) { $lignes = @() }

$present = $false
foreach ($l in $lignes) {
    if ($l -match [regex]::Escape($marqueur)) { $present = $true }
}

if ($action -eq "ajouter") {
    if ($present) {
        Write-Host "  Le nom '$nom' est deja enregistre."
    } else {
        Add-Content $hosts "`r`n127.0.0.1`t$nom`t$marqueur"
        Write-Host "  Nom '$nom' enregistre."
    }
} elseif ($action -eq "retirer") {
    if ($present) {
        $garde = $lignes | Where-Object { $_ -notmatch [regex]::Escape($marqueur) }
        Set-Content $hosts $garde
        Write-Host "  Nom '$nom' retire."
    } else {
        Write-Host "  Le nom '$nom' n'etait pas enregistre."
    }
} else {
    Write-Host "  Action inconnue : $action (ajouter ou retirer)"
    exit 1
}

ipconfig /flushdns | Out-Null
