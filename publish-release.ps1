# publish-release.ps1 - prepara y publica un Release en GitHub
# Requiere: build.ps1 ejecutado antes y la CLI 'gh' instalada (o publicar a mano).
param(
    [string]$Tag
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not $Tag) { $Tag = "v" + (Get-Date -Format "yyyy.MM.dd") }

$exe = "$root\dist\JSConnect-Win-Coverage.exe"
if (-not (Test-Path $exe)) {
    throw "No se encontro $exe. Ejecuta build.ps1 primero."
}

$hash = Get-FileHash -Path $exe -Algorithm SHA256
$notas = "Checksum SHA-256:`n`n$($hash.Hash)`n$exe"

Write-Host "Tag:     $Tag"
Write-Host "SHA-256: $($hash.Hash)"
Write-Host ""
Write-Host "Para publicar:"
Write-Host "  gh release create `"$Tag`" `"$exe`" --title `"$Tag`" --notes `"$($notas -replace "`n", " ")`""
Write-Host ""
Write-Host "Si no tienes gh, publica a mano desde GitHub > Releases > Draft."