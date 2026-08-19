# build.ps1 - empaqueta la app con PyInstaller y embebe el commit SHA actual
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 1. Commit y tag actuales
$commit = (git rev-parse HEAD 2>$null).Trim()
if (-not $commit) { $commit = "unknown" }
$tag = (git describe --tags --always 2>$null).Trim()
if (-not $tag) { $tag = "unknown" }

Write-Host "Commit: $commit"
Write-Host "Tag:    $tag"

# 2. Generar validator_app/version.py
$content = @"
# Autogenerado por build.ps1 - NO editar a mano.
BUILD_COMMIT = "$commit"
BUILD_TAG = "$tag"
REPO_OWNER = "sys-connectsolutionsjs"
REPO_NAME = "JSConnect-Win-Coverage"
"@
Set-Content -Path "$root\validator_app\version.py" -Value $content -Encoding UTF8

# 3. Empaquetar con PyInstaller (un solo .exe, sin consola)
python -m PyInstaller --onefile --windowed --name "JSConnect-Win-Coverage" main.py

Write-Host ""
Write-Host "Listo: dist\JSConnect-Win-Coverage.exe"
Write-Host "Publica la version con publish-release.ps1"