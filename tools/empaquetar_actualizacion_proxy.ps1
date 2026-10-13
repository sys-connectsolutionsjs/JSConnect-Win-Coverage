# empaquetar_actualizacion_proxy.ps1 - prepara la carpeta que se lleva en el pendrive para
# ACTUALIZAR el proxy de la PC owner SIN reinstalar. Copia solo el codigo de validator_app
# (archivos versionados + nuevos; gitignore deja fuera config.yaml, tokens, llaves, perfiles
# del navegador y datos de terceros). Nunca borra nada en el destino.
#
# Uso:  powershell -ExecutionPolicy Bypass -File tools\empaquetar_actualizacion_proxy.ps1
#       [-Destino C:\ruta\proxy-update]
param(
    [string]$Destino = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
if (-not $Destino) { $Destino = Join-Path $root "proxy-update" }

$lista = git ls-files --cached --others --exclude-standard validator_app
if ($LASTEXITCODE -ne 0 -or -not $lista) { throw "No se pudo listar validator_app con git." }

if (Test-Path $Destino) { Remove-Item -Recurse -Force $Destino }
New-Item -ItemType Directory -Force $Destino | Out-Null
# Nombres exactos de archivo (config.yaml.example SI viaja: es la plantilla) y carpetas.
$archivosProhibidos = @("config.yaml", "proxy_token.txt", "admin_key.txt", "updates.xml",
                        "capas.json.gz", "activacion.dat")
$extensionesProhibidas = @(".pem", ".crx")
$carpetasProhibidas = @(".browser_profile", ".extension_build")
$copiados = 0
foreach ($rel in $lista) {
    $relWin = $rel -replace "/", "\"
    $hoja = Split-Path -Leaf $relWin
    $segmentos = $relWin -split "\\"
    if ($archivosProhibidos -contains $hoja) { continue }
    if ($extensionesProhibidas -contains [System.IO.Path]::GetExtension($hoja)) { continue }
    if ($segmentos | Where-Object { $carpetasProhibidas -contains $_ }) { continue }
    $origen = Join-Path $root $relWin
    if (-not (Test-Path $origen -PathType Leaf)) { continue }
    $salida = Join-Path $Destino $relWin
    New-Item -ItemType Directory -Force (Split-Path -Parent $salida) | Out-Null
    Copy-Item $origen $salida
    $copiados++
}

$commit = (git rev-parse --short HEAD 2>$null).Trim()
$leeme = @"
ACTUALIZAR EL PROXY (sin reinstalar) - paquete generado desde el commit $commit

Contenido: solo la carpeta validator_app (codigo). NO trae config.yaml, tokens, llaves ni
perfiles: lo que ya existe en esta PC no se toca.

En la PC owner, PowerShell COMO ADMINISTRADOR (el repo suele estar en C:\jsconnect):

  1. sc stop JSWinProxy
  2. robocopy "<unidad>:\proxy-update\validator_app" "C:\jsconnect\validator_app" /E
     (sin /MIR ni /PURGE: no borra nada)
  3. Editar C:\jsconnect\validator_app\proxy\config.yaml y agregar al final:
         geofinder_basic: "<lo que sigue a Authorization: Basic>"
     (F12 en WinForce -> Network -> filtro "oauth" -> peticion api.latam.equifax.com/v2/oauth/token
      -> Headers -> Authorization. Pegarlo a mano; no compartirlo por chat ni correo.)
  4. sc start JSWinProxy
  5. curl http://localhost:8080/health   -> debe decir "geofinder":true
  6. Si el servicio no arranca por un paquete faltante: ejecutar
     C:\jsconnect\validator_app\proxy\install_service.bat como Administrador y elegir C
     (conserva los tokens; los agentes no se reconfiguran).
"@
Set-Content -Path (Join-Path $Destino "LEEME.txt") -Value $leeme -Encoding UTF8

Write-Host "Listo: $Destino ($copiados archivos + LEEME.txt)"
Write-Host "Lleva la carpeta proxy-update al pendrive y sigue LEEME.txt en la PC owner."
