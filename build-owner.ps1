# build-owner.ps1 - empaqueta la consola grafica del owner.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m PyInstaller --clean --noconfirm --onefile --windowed `
    --name "JSConnect-Win-Owner" generator\owner_app.py
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo construir la consola del owner."
}

Write-Host "Listo: dist\JSConnect-Win-Owner.exe"
Write-Host "Conserva private_key.pem fuera de Git y junto al programa del owner."
