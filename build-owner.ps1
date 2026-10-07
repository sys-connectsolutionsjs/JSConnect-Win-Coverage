# build-owner.ps1 - empaqueta la consola grafica del owner y embebe el commit SHA actual
# (la consola busca sus actualizaciones en GitHub, igual que el agente; ver build.ps1).
# -RepoName: repo de GitHub donde busca Releases (solo cambiarlo en un fork de pruebas).
param(
    [string]$RepoName = "JSConnect-Win-Coverage"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

# Commit y tag actuales -> validator_app/version.py (mismo archivo que escribe build.ps1)
$commit = (git rev-parse HEAD 2>$null).Trim()
if (-not $commit) { $commit = "unknown" }
$tag = (git describe --tags --always 2>$null).Trim()
if (-not $tag) { $tag = "unknown" }

Write-Host "Commit: $commit"
Write-Host "Tag:    $tag"
Write-Host "Repo de actualizaciones: sys-connectsolutionsjs/$RepoName"

$content = @"
# Autogenerado por build.ps1 / build-owner.ps1 - NO editar a mano.
BUILD_COMMIT = "$commit"
BUILD_TAG = "$tag"
REPO_OWNER = "sys-connectsolutionsjs"
REPO_NAME = "$RepoName"
"@
Set-Content -Path "$root\validator_app\version.py" -Value $content -Encoding UTF8

# Nota (2026-09-25): ver build.ps1 -- Pillow viaja en el .exe via ttkbootstrap.
& $python -m PyInstaller --clean --noconfirm --onefile --windowed `
    --icon "$root\assets\icons\owner.ico" `
    --name "JSConnect-Win-Owner" generator\owner_app.py
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo construir la consola del owner."
}

Write-Host "Listo: dist\JSConnect-Win-Owner.exe"
Write-Host "Conserva private_key.pem fuera de Git y junto al programa del owner."
