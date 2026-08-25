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
echo [1/8] Verificando Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python no encontrado en PATH.
    echo         Instala Python 3.13+ y asegurate de marcar "Add to PATH".
    pause
    exit /b 1
)

for /f "tokens=2 delims=. " %%a in ('python --version 2^>^&1') do set PY_VER=%%a
for /f "tokens=3 delims=. " %%b in ('python --version 2^>^&1') do set PY_MINOR=%%b

if %PY_VER% LSS 3 (
    echo [ERROR] Se requiere Python 3.13 o superior. Version detectada: %PY_VER%.%PY_MINOR%
    pause
    exit /b 1
)
if %PY_VER% EQU 3 if %PY_MINOR% LSS 13 (
    echo [ERROR] Se requiere Python 3.13 o superior. Version detectada: %PY_VER%.%PY_MINOR%
    pause
    exit /b 1
)
echo [OK] Python %PY_VER%.%PY_MINOR% detectado.

REM Instalar dependencias
echo.
echo [2/8] Instalando dependencias (requirements-proxy.txt)...
cd /d "%BASE_DIR%"
if not exist "requirements-proxy.txt" (
    echo [ERROR] No se encuentra requirements-proxy.txt en %BASE_DIR%
    pause
    exit /b 1
)
pip install -r requirements-proxy.txt --quiet
if %errorLevel% neq 0 (
    echo [ERROR] Fallo al instalar dependencias. Revisa tu conexion a internet.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

REM Descargar winsw.exe
echo.
echo [3/8] Descargando winsw.exe (Windows Service Wrapper)...
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

REM Generar tokens seguros
echo.
echo [4/8] Generando tokens de seguridad...
python -c "
import secrets, sys
proxy_token = secrets.token_hex(32)
admin_key = secrets.token_hex(32)
with open('%BASE_DIR%\\proxy_token.txt', 'w') as f: f.write(proxy_token)
with open('%BASE_DIR%\\admin_key.txt', 'w') as f: f.write(admin_key)
print('PROXY_TOKEN=' + proxy_token)
print('ADMIN_KEY=' + admin_key)
" > tokens_gen.tmp
for /f "tokens=1* delims==" %%a in (tokens_gen.tmp) do set "%%a=%%b"
del tokens_gen.tmp
echo [OK] Tokens generados (64 chars hex cada uno).

REM Verificar/crear config.yaml
echo.
echo [5/8] Configurando config.yaml...
set "CONFIG_YAML=%BASE_DIR%\config.yaml"
if exist "%CONFIG_YAML%" (
    echo [INFO] config.yaml ya existe. Se mantendra el existente.
    echo        Si quieres regenerar tokens, borra config.yaml y vuelve a ejecutar.
    REM Leer tokens existentes del config.yaml
    for /f "tokens=2 delims=: " %%a in ('findstr /R "^proxy_token:" "%CONFIG_YAML%"') do set PROXY_TOKEN=%%a
    for /f "tokens=2 delims=: " %%a in ('findstr /R "^admin_key:" "%CONFIG_YAML%"') do set ADMIN_KEY=%%a
) else (
    echo [INFO] Creando config.yaml nuevo con tokens generados...
    set "PROXY_PORT=8080"
    echo Verificando puerto %PROXY_PORT%...
    netstat -an | findstr ":%PROXY_PORT% " >nul
    if not errorlevel 1 (
        echo [WARN] Puerto %PROXY_PORT% ya esta en uso.
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

REM Generar winsw.xml con paths absolutos
echo.
echo [6/8] Generando winsw.xml con paths absolutos...
set "PYTHON_EXE=%BASE_DIR%\..\..\python.exe"
if not exist "%PYTHON_EXE%" (
    where python >nul 2>&1
    for /f "delims=" %%i in ('where python') do set "PYTHON_EXE=%%i"
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
echo [7/8] Instalando servicio Windows...
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
echo [8/8] Iniciando servicio...
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
echo   Ver logs:       Visor de Eventos -> Applications and Services Logs -> JSWinProxy
echo   Detener:        %BASE_DIR%\winsw.exe stop
echo   Reiniciar:      %BASE_DIR%\winsw.exe restart
echo   Desinstalar:    %BASE_DIR%\uninstall_service.bat
echo   Rotar creds:    python -m validator_app.proxy.rotate_creds
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