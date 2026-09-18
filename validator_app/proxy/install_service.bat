@echo off
REM =====================================================================
REM Instalador del servicio JSConnect Win Proxy
REM Ejecutar como ADMINISTRADOR
REM =====================================================================

setlocal enabledelayedexpansion

title JSConnect Win Proxy - Instalador

REM Ventana persistente: si no llega el argumento _run, el script se relanza dentro
REM de "cmd /k" para que la consola NO se cierre nunca (doble clic, error
REM inesperado, etc.). Cada paso verifica si ya esta hecho y lo salta.
if /i not "%~1"=="_run" (
    cmd /k ""%~f0" _run"
    exit /b
)

echo.
echo =====================================================================
echo  JSCONNECT WIN PROXY - INSTALACION DEL SERVICIO
echo =====================================================================
echo.

REM Verificar permisos de administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Debes ejecutar este script como ADMINISTRADOR.
    echo          Click derecho -^> "Ejecutar como administrador"
    pause
    exit /b 1
)

REM Directorio base (donde está este script)
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
echo [INFO] Directorio base: %BASE_DIR%

REM Verificar Python
echo.
echo [1/12] Verificando Python...
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
echo [2/12] Instalando dependencias (requirements-proxy.txt)...
REM requirements-proxy.txt vive en la RAIZ del repo (dos niveles arriba), y su
REM "-r requirements.txt" interno se resuelve relativo a ese archivo.
set "REPO_ROOT=%BASE_DIR%\..\.."
if not exist "%REPO_ROOT%\requirements-proxy.txt" (
    echo [ERROR] No se encuentra requirements-proxy.txt en %REPO_ROOT%
    pause
    exit /b 1
)
python -c "import fastapi, uvicorn, pydantic, pydantic_settings, yaml, playwright, httpx, keyring, cryptography, requests" >nul 2>&1
if !errorLevel! equ 0 (
    echo [OK] Dependencias ya instaladas - nada que hacer.
    set "R2=ya estaba"
) else (
    pip install -r "%REPO_ROOT%\requirements-proxy.txt" --quiet
    if errorlevel 1 (
        echo [ERROR] Fallo al instalar dependencias. Revisa tu conexion a internet.
        pause
        exit /b 1
    )
    echo [OK] Dependencias instaladas.
    set "R2=hecho ahora"
)

REM Descargar el navegador para el login asistido (rotate_creds sin --manual)
echo.
echo [3/12] Descargando el navegador para "Renovar sesion" (Chromium, ~150 MB)...
set "PW_OK="
for /d %%d in ("%LOCALAPPDATA%\ms-playwright\chromium-*") do set "PW_OK=1"
if defined PW_OK (
    echo [OK] Chromium ya estaba descargado - nada que hacer.
    set "R3=ya estaba"
) else (
    python -m playwright install chromium
    if errorlevel 1 (
        echo [WARN] No se pudo descargar Chromium. El icono "Renovar sesion WinForce"
        echo        no funcionara hasta que corras: python -m playwright install chromium
        echo        ^(mientras tanto: python -m validator_app.proxy.rotate_creds --manual^)
        set "R3=FALLO - ver aviso"
    ) else (
        set "R3=hecho ahora"
    )
)

REM Descargar winsw.exe
REM NOTA (2026-09-15): la URL anterior apuntaba a v3.0.0, que NUNCA existio como
REM release estable de winsw/winsw (solo hay v3.0.0-alpha.N) -> 404 siempre.
REM La ultima release real es v2.12.0. Ademas Invoke-WebRequest fallaba aqui en
REM Windows PowerShell 5.1 (no siempre negocia TLS 1.2 con GitHub por defecto,
REM aunque la URL sea correcta) -> se prueba primero con curl.exe (viene con
REM Windows 10 1803+/11, y el propio script ya lo usa mas abajo para el health
REM check), y solo si no esta se cae a PowerShell forzando TLS 1.2 a mano.
echo.
echo [4/12] Descargando winsw.exe (Windows Service Wrapper)...
set "WINSW_URL=https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW.NET4.exe"
set "WINSW_PATH=%BASE_DIR%\winsw.exe"

REM Un winsw.exe de 0 bytes (descarga cortada) se descarta y se vuelve a bajar.
if exist "%WINSW_PATH%" for %%f in ("%WINSW_PATH%") do if %%~zf equ 0 del "%WINSW_PATH%"
if exist "%WINSW_PATH%" (
    echo [OK] winsw.exe ya estaba descargado - nada que hacer.
    set "R4=ya estaba"
    goto :winsw_listo
)

where curl >nul 2>&1
if %errorLevel% equ 0 (
    curl.exe -sS -L -f -o "%WINSW_PATH%" "%WINSW_URL%"
) else (
    echo [INFO] curl.exe no encontrado en PATH, se prueba con PowerShell...
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%WINSW_URL%' -OutFile '%WINSW_PATH%' -UseBasicParsing"
)

if not exist "%WINSW_PATH%" (
    echo [WARN] Descarga con curl fallo, reintentando con PowerShell forzando TLS 1.2...
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%WINSW_URL%' -OutFile '%WINSW_PATH%' -UseBasicParsing"
)

if not exist "%WINSW_PATH%" (
    echo [ERROR] No se pudo descargar winsw.exe desde %WINSW_URL%
    echo         Descargalo manualmente de:
    echo         https://github.com/winsw/winsw/releases
    echo         y colocalo en: %WINSW_PATH%
    pause
    exit /b 1
)
echo [OK] winsw.exe descargado en %WINSW_PATH%
set "R4=hecho ahora"
:winsw_listo

REM Generar / reutilizar tokens
echo.
echo [5/12] Tokens de seguridad...
set "CONFIG_YAML=%BASE_DIR%\config.yaml"
set "REGEN=0"
set "OLD_PORT="
if exist "%CONFIG_YAML%" (
    echo [INFO] Ya hay tokens generados en config.yaml.
    echo        CONSERVARLOS mantiene validos los tokens ya entregados a los agentes.
    echo        REGENERARLOS crea tokens nuevos: hay que reconfigurar cada agente.
    choice /c CR /t 20 /d C /n /m "Presiona C para CONSERVAR o R para REGENERAR (C por defecto en 20 s): "
    if errorlevel 2 (
        for /f "usebackq tokens=1,* delims=: " %%a in (`findstr /R "^proxy_port:" "%CONFIG_YAML%"`) do set "OLD_PORT=%%b"
        set "REGEN=1"
        del "%CONFIG_YAML%" "%BASE_DIR%\proxy_token.txt" "%BASE_DIR%\admin_key.txt" >nul 2>&1
        echo [INFO] Tokens anteriores borrados: se generan nuevos.
    )
)
if exist "%CONFIG_YAML%" (
    echo [INFO] Se conservan los tokens y el puerto de config.yaml.
    for /f "usebackq tokens=1,* delims=: " %%a in (`findstr /R "^proxy_token:" "%CONFIG_YAML%"`) do call :trim_quotes PROXY_TOKEN %%b
    for /f "usebackq tokens=1,* delims=: " %%a in (`findstr /R "^admin_key:" "%CONFIG_YAML%"`) do call :trim_quotes ADMIN_KEY %%b
    for /f "usebackq tokens=1,* delims=: " %%a in (`findstr /R "^proxy_port:" "%CONFIG_YAML%"`) do set "PROXY_PORT=%%b"
    if "!PROXY_TOKEN!"=="" (
        echo [ERROR] No pude leer proxy_token de config.yaml. Revisalo o borralo.
        pause
        exit /b 1
    )
    if "!PROXY_PORT!"=="" set "PROXY_PORT=8080"
    echo [OK] Tokens y puerto ^(!PROXY_PORT!^) leidos de config.yaml.
    set "R5=ya estaba"
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
    set "R5=hecho ahora"
)

REM Verificar/crear config.yaml
echo.
echo [6/12] Configurando config.yaml...
if exist "%CONFIG_YAML%" (
    echo [INFO] Se mantiene el config.yaml existente.
    set "R6=ya estaba"
) else (
    echo [INFO] Creando config.yaml nuevo con tokens generados...
    set "PROXY_PORT=8080"
    if defined OLD_PORT set "PROXY_PORT=!OLD_PORT!"
    echo Verificando puerto !PROXY_PORT!...
    if defined OLD_PORT (
        echo [INFO] Se reutiliza el puerto anterior: lo ocupa el propio servicio.
        ver >nul
    ) else (
        netstat -an | findstr ":!PROXY_PORT! " >nul
    )
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
    set "R6=hecho ahora"
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
echo [7/12] Instalando la extension de Chrome "Renovar sesion WinForce"...
cd /d "%BASE_DIR%\..\.."
python -m validator_app.proxy._instalar_extension
set "EXT_RC=!errorLevel!"
cd /d "%BASE_DIR%"

REM Chrome solo aplica la politica de fuerza-instalacion en PCs gestionadas
REM (dominio o Azure AD). En una PC sin gestionar (p. ej. Windows Home) la ignora.
REM Esto solo INFORMA: nunca detiene el instalador.
set "PC_GESTIONADA=0"
powershell -NoProfile -Command "if ((Get-CimInstance Win32_ComputerSystem).PartOfDomain) { exit 0 } else { exit 1 }" >nul 2>&1
if !errorLevel! equ 0 set "PC_GESTIONADA=1"
if "!PC_GESTIONADA!"=="0" (
    dsregcmd /status 2>nul | findstr /R /C:"AzureAdJoined *: *YES" >nul
    if !errorLevel! equ 0 set "PC_GESTIONADA=1"
)
if not "!EXT_RC!"=="0" (
    echo [WARN] No se pudo registrar la politica de la extension de Chrome.
    echo        El instalador continua: al final se explica como instalarla a mano.
    set "R7=FALLO - instalar a mano (ver al final)"
) else if "!PC_GESTIONADA!"=="1" (
    echo [OK] Politica registrada. Chrome instalara la extension al reabrirse.
    set "R7=politica registrada - verificar en Chrome"
) else (
    echo [AVISO] Politica registrada, pero esta PC no es de dominio ni Azure AD:
    echo         Chrome probablemente NO cargue la extension solo.
    echo         El instalador continua: al final se explica como instalarla a mano.
    set "R7=politica registrada - instalar a mano (ver al final)"
)

REM Generar winsw.xml con paths absolutos
echo.
echo [8/12] Generando winsw.xml con paths absolutos...
REM El interprete REAL que corre ahora (no el primero del PATH, que puede ser el
REM stub de Microsoft Store).
for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%i"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] No se pudo resolver el ejecutable de Python ^(!PYTHON_EXE!^).
    pause
    exit /b 1
)
echo [INFO] Usando Python: %PYTHON_EXE%

(
    echo ^<service^>
    echo   ^<id^>JSWinProxy^</id^>
    echo   ^<name^>JSConnect Win Proxy^</name^>
    echo   ^<description^>Proxy local para validacion de cobertura y score crediticio ^(JSConnect Win Coverage^). Recibe peticiones de agentes LAN y las reenvia a WinForce/Equifax usando una sola sesion.^</description^>
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
set "R8=actualizado"

REM Instalar servicio
echo.
echo [9/12] Instalando servicio Windows...
cd /d "%BASE_DIR%"
sc query JSWinProxy >nul 2>&1
if !errorLevel! equ 0 (
    echo [OK] El servicio JSWinProxy ya estaba instalado - nada que hacer.
    set "R9=ya estaba"
) else (
    "%WINSW_PATH%" install
    if errorlevel 1 (
        echo [ERROR] Fallo al instalar el servicio.
        pause
        exit /b 1
    )
    echo [OK] Servicio instalado.
    set "R9=hecho ahora"
)

REM Iniciar servicio
echo.
echo [10/12] Iniciando servicio...
sc query JSWinProxy | findstr /C:"RUNNING" >nul
if !errorLevel! equ 0 (
    if "!REGEN!"=="1" (
        echo [INFO] Tokens regenerados: se reinicia el servicio para que los cargue.
        "%WINSW_PATH%" restart
        set "R10=reiniciado con tokens nuevos"
    ) else (
        echo [OK] El servicio ya estaba en ejecucion - nada que hacer.
        set "R10=ya estaba"
    )
) else (
    "%WINSW_PATH%" start
    if errorlevel 1 (
        echo [ERROR] Fallo al iniciar el servicio. Revisa los logs en %BASE_DIR%\..\..\logs\ ^(archivos rotados de winsw^)
        pause
        exit /b 1
    )
    echo [OK] Servicio iniciado.
    set "R10=hecho ahora"
)

REM Esperar un momento y verificar health
echo.
echo [VERIFICACION] Esperando 3 segundos para health check...
timeout /t 3 /nobreak >nul

set "HEALTH_URL=http://localhost:%PROXY_PORT%/health"
echo Probando %HEALTH_URL% ...
curl -s -m 5 "%HEALTH_URL%" > health_check.tmp 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Health check fallo ^(curl no disponible o servicio no listo^).
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

REM Tarea programada: popup al owner cuando el proxy avise que la sesion murio.
REM El servicio corre como LocalSystem (sesion 0, sin escritorio) y escribe un
REM evento de Windows (origen JSWinProxy, ID 101); esta tarea lo convierte en un
REM aviso visible en la sesion interactiva del owner.
echo.
echo [11/12] Registrando la tarea de aviso "sesion caducada"...
REM Registrar la fuente de eventos (una vez, elevado) para que el servicio
REM LocalSystem pueda escribir en el Registro de Windows sin "Acceso denegado".
powershell -NoProfile -Command "if (-not [System.Diagnostics.EventLog]::SourceExists('JSWinProxy')) { New-EventLog -LogName Application -Source JSWinProxy }" 2>nul
schtasks /query /tn "JSWinProxy-AvisoSesion" >nul 2>&1
if !errorLevel! equ 0 (
    echo [OK] La tarea de aviso ya estaba registrada - nada que hacer.
    set "R11=ya estaba"
    goto :tarea_lista
)
schtasks /create /tn "JSWinProxy-AvisoSesion" /f /ru INTERACTIVE ^
  /sc ONEVENT /ec Application ^
  /mo "*[System[Provider[@Name='JSWinProxy'] and EventID=101]]" ^
  /tr "msg * La sesion de WinForce del proxy caduco. Abre Chrome y pulsa el icono 'Renovar sesion' (badge rojo)." 2>nul
if %errorLevel% equ 0 (
    echo [OK] Tarea de aviso registrada. El owner vera un popup cuando la sesion caduque.
    set "R11=hecho ahora"
) else (
    set "R11=FALLO - ver aviso"
    echo [WARN] No se pudo registrar la tarea de aviso. El badge de la extension
    echo        y el Visor de Eventos siguen funcionando; registra la tarea a mano si quieres el popup.
)
:tarea_lista

REM Crear el acceso directo "Renovar sesion WinForce" en el Escritorio
echo.
echo [12/12] Creando el icono "Renovar sesion WinForce" en el Escritorio...
powershell -NoProfile -Command "if (Test-Path (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Renovar sesion WinForce.lnk')) { exit 0 } else { exit 1 }" >nul 2>&1
if !errorLevel! equ 0 (
    echo [OK] El icono ya estaba en el Escritorio - nada que hacer.
    set "R12=ya estaba"
    goto :icono_listo
)
for /f "delims=" %%p in ('where pythonw.exe 2^>nul') do set "PYTHONW_EXE=%%p"
if not defined PYTHONW_EXE set "PYTHONW_EXE=pythonw.exe"
set "REPO_ROOT=%BASE_DIR%\..\.."
powershell -NoProfile -Command "$w=New-Object -ComObject WScript.Shell; $l=$w.CreateShortcut((Join-Path $w.SpecialFolders('Desktop') 'Renovar sesion WinForce.lnk')); $l.TargetPath='%PYTHONW_EXE%'; $l.Arguments='-m validator_app.proxy.rotate_creds'; $l.WorkingDirectory=(Resolve-Path '%REPO_ROOT%').Path; $l.IconLocation='shell32.dll,44'; $l.Description='Renueva la sesion de WinForce del proxy'; $l.Save()" 2>nul
if %errorLevel% equ 0 (
    echo [OK] Icono creado. El owner solo tiene que hacer doble clic e iniciar sesion.
    set "R12=hecho ahora"
) else (
    set "R12=FALLO - ver aviso"
    echo [WARN] No se pudo crear el icono. Crea a mano un acceso directo a:
    echo        %PYTHONW_EXE% -m validator_app.proxy.rotate_creds  ^(en %BASE_DIR%\..\..^)
)

:icono_listo

REM Resumen final
echo.
echo =====================================================================
echo  INSTALACION COMPLETADA
echo =====================================================================
echo.
echo RESUMEN DE PASOS (hecho ahora / ya estaba de antes^):
echo   [2/12]  Dependencias Python ........ !R2!
echo   [3/12]  Chromium ................... !R3!
echo   [4/12]  winsw.exe .................. !R4!
echo   [5/12]  Tokens ..................... !R5!
echo   [6/12]  config.yaml ................ !R6!
echo   [7/12]  Extension de Chrome ........ !R7!
echo   [8/12]  winsw.xml .................. !R8!
echo   [9/12]  Servicio instalado ......... !R9!
echo   [10/12] Servicio en ejecucion ...... !R10!
echo   [11/12] Tarea de aviso ............. !R11!
echo   [12/12] Icono del Escritorio ....... !R12!
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
echo   Renovar sesion: cuando la sesion caduca sale un POPUP automatico (tarea
echo                   JSWinProxy-AvisoSesion) y la EXTENSION de Chrome pone un
echo                   badge rojo -^> el owner hace 1 clic (reabre Chrome tras
echo                   instalar para que aparezca).
echo                   Fallback: icono "Renovar sesion WinForce" del Escritorio,
echo                   o python -m validator_app.proxy.rotate_creds [--manual]
echo   Ver avisos:     Visor de Eventos -^> Registros de Windows -^> Aplicacion,
echo                   origen "JSWinProxy" (ID 101 = caduco, 102 = renovada)
echo.
echo =====================================================================
echo  EXTENSION DE CHROME - si en chrome://extensions NO aparece
echo  "Renovar sesion WinForce", instalala a mano ^(una sola vez^):
echo =====================================================================
echo   1. Abre Chrome y escribe en la barra de direcciones: chrome://extensions
echo   2. Activa "Modo de desarrollador" ^(arriba a la derecha^).
echo   3. Pulsa "Cargar descomprimida" y elige esta carpeta:
echo      %BASE_DIR%\.extension_build
echo   4. Fija el icono con el puzzle y el pin, en la barra de Chrome.
echo   Chrome mostrara un aviso por el modo desarrollador: es normal.
echo   Sin extension tambien puedes renovar la sesion con el icono
echo   "Renovar sesion WinForce" del Escritorio.
echo.
echo CONFIGURACION AGENTES (en cada una de las 20 maquinas):
echo   1. Ejecutar JSConnect-Win-Coverage.exe
echo   2. Menu [Configuracion] -^> [Configurar Proxy]
echo   3. IP:puerto:   [IP_DE_ESTA_PC]:%PROXY_PORT%
echo   4. Token:       !PROXY_TOKEN!
echo   5. [Probar conexion] -^> [Guardar]
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