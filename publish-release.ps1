# publish-release.ps1 - prepara y publica un Release en GitHub
# Requiere: build.ps1 ejecutado antes y la CLI 'gh' instalada (o publicar a mano).
# Si dist\JSConnect-Win-Owner.exe existe (build-owner.ps1 ya corrido), se incluye
# como segundo asset del mismo release; si no, publica solo el agente como antes.
param(
    [string]$Tag
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not $Tag) { $Tag = "v" + (Get-Date -Format "yyyy.MM.dd") }

$exeAgente = "$root\dist\JSConnect-Win-Coverage.exe"
if (-not (Test-Path $exeAgente)) {
    throw "No se encontro $exeAgente. Ejecuta build.ps1 primero."
}
$exeOwner = "$root\dist\JSConnect-Win-Owner.exe"
$incluyeOwner = Test-Path $exeOwner

$hashAgente = Get-FileHash -Path $exeAgente -Algorithm SHA256

# Notas estructuradas en bloques "## <nombre>\nSHA-256: <hash>" - es el
# formato que validator_app/updater/download.py::extraer_checksum() sabe leer
# por archivo cuando el release trae mas de un asset (no confundir hashes).
$notas = "## JSConnect-Win-Coverage.exe`nSHA-256: $($hashAgente.Hash)`n"
$archivos = @($exeAgente)

if ($incluyeOwner) {
    $hashOwner = Get-FileHash -Path $exeOwner -Algorithm SHA256
    $notas += "`n## JSConnect-Win-Owner.exe`nSHA-256: $($hashOwner.Hash)`n"
    $archivos += $exeOwner
}

Write-Host "Tag:            $Tag"
Write-Host "Agente SHA-256: $($hashAgente.Hash)"
if ($incluyeOwner) {
    Write-Host "Owner SHA-256:  $($hashOwner.Hash)"
} else {
    Write-Host "(dist\JSConnect-Win-Owner.exe no encontrado - se publica solo el agente)"
}
Write-Host ""

$notasFile = New-TemporaryFile
Set-Content -Path $notasFile -Value $notas -Encoding UTF8

$archivosStr = ($archivos | ForEach-Object { "`"$_`"" }) -join " "
Write-Host "Para publicar:"
Write-Host "  gh release create `"$Tag`" $archivosStr --title `"$Tag`" --notes-file `"$notasFile`""
Write-Host ""
Write-Host "Notas del release (guardadas en $notasFile):"
Write-Host $notas
Write-Host "Si no tienes gh, publica a mano desde GitHub > Releases > Draft (sube los"
Write-Host "mismos archivos y pega el contenido de arriba como notas)."