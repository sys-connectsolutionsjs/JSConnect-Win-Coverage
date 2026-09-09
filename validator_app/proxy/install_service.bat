@echo off
REM =====================================================================
REM Instalador del servicio JSConnect Win Proxy
REM Ejecutar como ADMINISTRADOR
REM =====================================================================

setlocal enabledelayedexpansion

title JSConnect Win Proxy - Instalador

echo.
echo =====================================================================
echo  JSCONNECT WIN PROXY - INSTALACION DEL SERVICIO
echo =====================================================================
echo.

REM Verificar permisos de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Debes ejecutar este script como ADMINISTRADOR.
    echo          Click derecho -> "Ejecutar como administrador"
    pause
    exit /b 1
)

REM Directorio base (donde está este script)
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
echo [INFO] Directorio base: %BASE_DIR%

REM Verificar Python
echo.
echo [1/11] Verificando Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python no encontrado en PATH.
    echo         Instala Python 3.12+ y asegurate de marcar "Add to PATH".
    pause
    exit /b 1
)

for /f "tokens=2 delims=. " %%a in ('python --version 2^>^&1') do set PY_VER=%%a
for /f "tokens=3 delims=. " %%b in ('python --version 2^>^&1') do set PY_MINOR=%%b

if %PY_VER% LSS 3 (
    echo [ERROR] Se requiere Python 3.12 o superior. Version detectada: %PY_VER%.%PY_MINOR%
    pause
    exit /b 1
)
if %PY_VER% EQU 3 if %PY_MINOR% LSS 12 (
    echo [ERROR] Se requiere Python 3.12 o superior. Version detectada: %PY_VER%.%PY_MINOR%
    pause
    exit /b 1
)
echo [OK] Python %PY_VER%.%PY_MINOR% detectado.

REM Instalar dependencias
echo.
echo [2/11] Instalando dependencias (requirements-proxy.txt)...
REM requirements-proxy.txt vive en la RAIZ del repo (dos niveles arriba), y su
REM "-r requirements.txt" interno se resuelve relativo a ese archivo.
set "REPO_ROOT=%BASE_DIR%\..\.."
if not exist "%REPO_ROOT%\requirements-proxy.txt" (
    echo [ERROR] No se encuentra requirements-proxy.txt en %REPO_ROOT%
    pause
    exit /b 1
)
pip install -r "%REPO_ROOT%\requirements-proxy.txt" --quiet
if %errorLevel% neq 0 (
    echo [ERROR] Fallo al instalar dependencias. Revisa tu conexion a internet.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

REM Descargar el navegador para el login asistido (rotate_creds sin --manual)
echo.
echo [3/11] Descargando el navegador para "Renovar sesion" (Chromium, ~150 MB)...
python -m playwright install chromium
if %errorLevel% neq 0 (
    echo [WARN] No se pudo descargar Chromium. El icono "Renovar sesion WinForce"
    echo        no funcionara hasta que corras: python -m playwright install chromium
    echo        (mientras tanto: python -m validator_app.proxy.rotate_creds --manual)
)

REM Descargar winsw.exe
echo.
echo [4/11] Descargando winsw.exe (Windows Service Wrapper)...
set "WINSW_URL=https://github.com/winsw/winsw/releases/download/v3.0.0/WinSW.NET4.exe"
set "WINSW_PATH=%BASE_DIR%\winsw.exe"
powershell -Command "Invoke-WebRequest -Uri '%WINSW_URL%' -OutFile '%WINSW_PATH%' -UseBasicParsing" 2>nul
if %errorLevel% neq 0 (
    echo [WARN] Descarga automatica fallo. Intentando URL alternativa...
    set "WINSW_URL=https://github.com/winsw/winsw/releases/latest/download/WinSW.NET4.exe"
    powershell -Command "Invoke-WebRequest -Uri '%WINSW_URL%' -OutFile '%WINSW_PATH%' -UseBasicParsing" 2>nul
    if %errorLevel% neq 0 (
        echo [ERROR] No se pudo descargar winsw.exe. Descargalo manualmente de:
        echo         https://github.com/winsw/winsw/releases
        echo         y colocalo en: %WINSW_PATH%
        pause
        exit /b 1
    )
)
echo [OK] winsw.exe descargado en %WINSW_PATH%

REM Generar / reutilizar tokens
echo.
echo [5/11] Tokens de seguridad...
set "CONFIG_YAML=%BASE_DIR%\config.yaml"
if exist "%CONFIG_YAML%" (
    echo [INFO] config.yaml ya existe: se reutilizan sus tokens y puerto.
    echo        Para regenerar, borra config.yaml y vuelve a ejecutar.
    for /f "usebackq tokens=1,* delims=: " %%a in (`findstr /R "^proxy_token:" "%CONFIG_YAML%"`) do call :trim_quotes PROXY_TOKEN %%b
    for /f "usebackq tokens=1,* delims=: " %%a in (`findstr /R "^admin_key:" "%CONFIG_YAML%"`) do call :trim_quotes ADMIN_KEY %%b
    for /f "usebackq tokens=1,* delims=: " %%a in (`findstr /R "^proxy_port:" "%CONFIG_YAML%"`) do set "PROXY_PORT=%%b"
    if "!PROXY_TOKEN!"=="" (
        echo [ERROR] No pude leer proxy_token de config.yaml. Revisalo o borralo.
        pause
        exit /b 1
    )
    if "!PROXY_PORT!"=="" set "PROXY_PORT=8080"
    echo [OK] Tokens y puerto (!PROXY_PORT!) leidos de config.yaml.
) else (
    REM Una sola linea: cmd.exe no soporta cadenas multilinea en python -c.
    python -c "import secrets,pathlib; d=pathlib.Path(r'%BASE_DIR%'); (d/'proxy_token.txt').write_text(secrets.token_hex(32)); (d/'admin_key.txt').write_text(secrets.token_hex(32))"
    if errorlevel 1 (
        echo [ERROR] Fallo al generar los tokens.
        pause
        exit /b 1
    )
    set /p PROXY_TOKEN=<"%BASE_DIR%\proxy_token.txt"
    set /p ADMIN_KEY=<"%BASE_DIR%\admin_key.txt"
    if "!PROXY_TOKEN!"=="" (
        echo [ERROR] proxy_token.txt quedo vacio.
        pause
        exit /b 1
    )
    echo [OK] Tokens generados (64 chars hex cada uno^).
)

REM Verificar/crear config.yaml
echo.
echo [6/11] Configurando config.yaml...
if exist "%CONFIG_YAML%" (
    echo [INFO] Se mantiene el config.yaml existente.
) else (
    echo [INFO] Creando config.yaml nuevo con tokens generados...
    set "PROXY_PORT=8080"
    echo Verificando puerto !PROXY_PORT!...
    netstat -an | findstr ":!PROXY_PORT! " >nul
    if not errorlevel 1 (
        echo [WARN] Puerto !PROXY_PORT! ya esta en uso.
        set /p PROXY_PORT="Ingresa otro puerto (ej: 8081, 9000): "
        if "!PROXY_PORT!"=="" set PROXY_PORT=8081
        netstat -an | findstr ":!PROXY_PORT! " >nul
        if not errorlevel 1 (
            echo [ERROR] Puerto !PROXY_PORT! tambien esta en uso. Elige otro.
            pause
            exit /b 1
        )
    )
    (
        echo # Configuracion del Proxy Local JSConnect Win Coverage
        echo # Generado automaticamente por install_service.bat - %DATE% %TIME%
        echo.
        echo proxy_host: "0.0.0.0"
        echo proxy_port: !PROXY_PORT!
        echo.
        echo proxy_token: "!PROXY_TOKEN!"
        echo admin_key: "!ADMIN_KEY!"
        echo.
        echo win_keyring_service: "JSWinProxy"
        echo win_keyring_user: "credentials"
        echo.
        echo session_max_idle_seconds: 120
        echo request_timeout: 30
        echo winforce_login_timeout: 30
        echo winforce_cobertura_timeout: 30
        echo winforce_score_timeout: 90
        echo.
        echo keepalive_enabled: true
        echo keepalive_interval_seconds: 900
        echo.
        echo allowed_networks:
        echo   - "192.168.0.0/16"
        echo   - "10.0.0.0/8"
        echo   - "172.16.0.0/12"
        echo   - "100.64.0.0/10"
        echo.
        echo winforce_base_url: "https://appwinforce.win.pe"
        echo winforce_controllers: "https://appwinforce.win.pe/controllers"
    ) > "%CONFIG_YAML%"
    echo [OK] config.yaml creado en %CONFIG_YAML%
)

REM Restringir config.yaml: contiene proxy_token + admin_key en texto plano.
REM .gitignore protege de GitHub; esta ACL protege de otros usuarios de la PC.
echo [INFO] Restringiendo permisos de config.yaml (SYSTEM + Administradores)...
icacls "%CONFIG_YAML%" /inheritance:r /grant:r "SYSTEM:F" "BUILTIN\Administradores:F" >nul 2>&1
if errorlevel 1 icacls "%CONFIG_YAML%" /inheritance:r /grant:r "SYSTEM:F" "BUILTIN\Administrators:F" >nul 2>&1
icacls "%BASE_DIR%\proxy_token.txt" /inheritance:r /grant:r "SYSTEM:F" "BUILTIN\Administradores:F" >nul 2>&1
icacls "%BASE_DIR%\admin_key.txt" /inheritance:r /grant:r "SYSTEM:F" "BUILTIN\Administradores:F" >nul 2>&1
echo [OK] Permisos aplicados (si fallo, revisa que corres como Administrador).

REM Instalar la extension de Chrome "Renovar sesion WinForce" (force-install por politica)
echo.
echo [7/11] Instalando la extension de Chrome "Renovar sesion WinForce"...
cd /d "%BASE_DIR%\..\.."
python -m validator_app.proxy._instalar_extension
cd /d "%BASE_DIR%"

REM Generar winsw.xml con paths absolutos
echo.
echo [8/11] Generando winsw.xml con paths absolutos...
REM El interprete REAL que corre ahora (no el primero del PATH, que puede ser el
REM stub de Microsoft Store).
for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] No se pudo resolver el ejecutable de Python (%PYTHON_EXE%).
    pause
    exit /b 1
)
echo [INFO] Usando Python: %PYTHON_EXE%

(
    echo ^<service^>
    echo   ^<id^>JSWinProxy^</id^>
    echo   ^<name^>JSConnect Win Proxy^</name^>
    echo   ^<description^>Proxy local para validacion de cobertura y score crediticio (JSConnect Win Coverage). Recibe peticiones de agentes LAN y las reenvia a WinForce/Equifax usando una sola sesion.^</description^>
    echo   ^<executable^>%PYTHON_EXE%^</executable^>
    echo   ^<arguments^>-m validator_app.proxy.server^</arguments^>
    echo   ^<workingdirectory^>%BASE_DIR%\..\..^</workingdirectory^>
    echo   ^<logmode^>rotate^</logmode^>
    echo   ^<logpath^>%BASE_DIR%\..\..\logs^</logpath^>
    echo   ^<log level="info" /^>
    echo   ^<onfailure action="restart" delay="10 sec" /^>
    echo   ^<onfailure action="restart" delay="30 sec" /^>
    echo   ^<onfailure action="restart" delay="60 sec" /^>
    echo   ^<env name="PYTHONUTF8" value="1" /^>
    echo   ^<env name="PYTHONIOENCODING" value="utf-8" /^>
    echo ^</service^>
) > "%BASE_DIR%\winsw.xml"
echo [OK] winsw.xml generado.

REM Instalar servicio
echo.
echo [9/11] Instalando servicio Windows...
cd /d "%BASE_DIR%"
"%WINSW_PATH%" install
if %errorLevel% neq 0 (
    echo [ERROR] Fallo al instalar el servicio.
    pause
    exit /b 1
)
echo [OK] Servicio instalado.

REM Iniciar servicio
echo.
echo [10/11] Iniciando servicio...
"%WINSW_PATH%" start
if %errorLevel% neq 0 (
    echo [ERROR] Fallo al iniciar el servicio. Revisa logs en Visor de Eventos -> JSWinProxy
    pause
    exit /b 1
)
echo [OK] Servicio iniciado.

REM Esperar un momento y verificar health
echo.
echo [VERIFICACION] Esperando 3 segundos para health check...
timeout /t 3 /nobreak >nul

set "HEALTH_URL=http://localhost:%PROXY_PORT%/health"
echo Probando %HEALTH_URL% ...
curl -s -m 5 "%HEALTH_URL%" > health_check.tmp 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Health check fallo (curl no disponible o servicio no listo).
    echo         Verifica manualmente: curl %HEALTH_URL%
) else (
    type health_check.tmp
    findstr /C:"\"status\":\"ok\"" health_check.tmp >nul
    if %errorLevel% equ 0 (
        echo.
        echo [EXITO] Health check OK - Proxy funcionando correctamente!
    ) else (
        echo.
        echo [WARN] Health check respondio pero status no es 'ok'.
    )
)
del health_check.tmp 2>nul

REM Crear el acceso directo "Renovar sesion WinForce" en el Escritorio
echo.
echo [11/11] Creando el icono "Renovar sesion WinForce" en el Escritorio...
for /f "delims=" %%p in ('where pythonw.exe 2^>nul') do set "PYTHONW_EXE=%%p"
if not defined PYTHONW_EXE set "PYTHONW_EXE=pythonw.exe"
set "REPO_ROOT=%BASE_DIR%\..\.."
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $l=$w.CreateShortcut((Join-Path $w.SpecialFolders('Desktop') 'Renovar sesion WinForce.lnk')); $l.TargetPath='%PYTHONW_EXE%'; $l.Arguments='-m validator_app.proxy.rotate_creds'; $l.WorkingDirectory=(Resolve-Path '%REPO_ROOT%').Path; $l.IconLocation='shell32.dll,44'; $l.Description='Renueva la sesion de WinForce del proxy'; $l.Save()" 2>nul
if %errorLevel% equ 0 (
    echo [OK] Icono creado. El owner solo tiene que hacer doble clic e iniciar sesion.
) else (
    echo [WARN] No se pudo crear el icono. Crea a mano un acceso directo a:
    echo        %PYTHONW_EXE% -m validator_app.proxy.rotate_creds  (en %BASE_DIR%\..\..)
)

REM Resumen final
echo.
echo =====================================================================
echo  INSTALACION COMPLETADA
echo =====================================================================
echo.
echo Servicio:     JSWinProxy (JSConnect Win Proxy)
echo Puerto:       %PROXY_PORT%
echo Health:       http://localhost:%PROXY_PORT%/health
echo Docs (Swagger): http://localhost:%PROXY_PORT%/docs
echo.
echo =====================================================================
echo  TOKEN PROXY (distribuir a los 20 agentes via keyring o GUI):
echo =====================================================================
echo !PROXY_TOKEN!
echo.
echo =====================================================================
echo  ADMIN KEY (guardar seguro - SOLO owner, para /admin/*):
echo =====================================================================
echo !ADMIN_KEY!
echo.
echo =====================================================================
echo  ARCHIVOS GENERADOS (gitignored - NO subir a GitHub):
echo =====================================================================
echo %BASE_DIR%\config.yaml
echo %BASE_DIR%\proxy_token.txt
echo %BASE_DIR%\admin_key.txt
echo %BASE_DIR%\winsw.exe
echo %BASE_DIR%\winsw.xml
echo.
echo COMANDOS UTILES:
echo   Ver estado:     sc query JSWinProxy
echo   Ver logs:       %BASE_DIR%\..\..\logs\  (archivos rotados de winsw)
echo   Detener:        %BASE_DIR%\winsw.exe stop
echo   Reiniciar:      %BASE_DIR%\winsw.exe restart
echo   Desinstalar:    %BASE_DIR%\uninstall_service.bat
echo   Renovar sesion: la EXTENSION de Chrome pone un badge rojo y el owner
echo                   hace 1 clic (reabre Chrome tras instalar para que aparezca).
echo                   Fallback: icono "Renovar sesion WinForce" del Escritorio,
echo                   o python -m validator_app.proxy.rotate_creds [--manual]
echo.
echo CONFIGURACION AGENTES (en cada una de las 20 maquinas):
echo   1. Ejecutar JSConnect-Win-Coverage.exe
echo   2. Menu [Configuracion] -> [Configurar Proxy]
echo   3. IP:puerto:   [IP_DE_ESTA_PC]:%PROXY_PORT%
echo   4. Token:       !PROXY_TOKEN!
echo   5. [Probar conexion] -> [Guardar]
echo.
echo FIREWALL (si agentes no conectan):
echo   New-NetFirewallRule -DisplayName "JSWinProxy API" -Direction Inbound -LocalPort %PROXY_PORT% -Protocol TCP -Action Allow -Profile Domain,Private
echo.
pause
exit /b 0

REM ---------------------------------------------------------------------
REM Subrutinas
REM ---------------------------------------------------------------------
:trim_quotes
REM %1 = nombre de variable a setear; %2 = valor (posiblemente entre comillas)
set "_tq_val=%~2"
set "%1=%_tq_val%"
set "_tq_val="
goto :eof