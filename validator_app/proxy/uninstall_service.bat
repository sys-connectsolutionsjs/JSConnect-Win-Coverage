@echo off
REM =====================================================================
REM Desinstalador del servicio JSConnect Win Proxy
REM Ejecutar como ADMINISTRADOR
REM =====================================================================

setlocal enabledelayedexpansion

title JSConnect Win Proxy - Desinstalador

echo.
echo =====================================================================
echo  JSCONNECT WIN PROXY - DESINSTALACION DEL SERVICIO
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

set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
cd /d "%BASE_DIR%"

set "WINSW_PATH=%BASE_DIR%\winsw.exe"

if not exist "%WINSW_PATH%" (
    echo [ERROR] No se encuentra winsw.exe en %BASE_DIR%
    echo         Ejecuta install_service.bat primero o descarga winsw.exe manualmente.
    pause
    exit /b 1
)

echo [INFO] Deteniendo servicio...
"%WINSW_PATH%" stop 2>nul
timeout /t 2 /nobreak >nul

echo [INFO] Desinstalando servicio...
"%WINSW_PATH%" uninstall
if %errorLevel% neq 0 (
    echo [WARN] El servicio ya estaba desinstalado o hubo un error.
) else (
    echo [OK] Servicio desinstalado.
)

echo [INFO] Limpiando archivos generados...
del "%BASE_DIR%\winsw.exe" 2>nul
del "%BASE_DIR%\winsw.xml" 2>nul
echo [OK] winsw.exe y winsw.xml eliminados.

echo.
echo =====================================================================
echo  DESINSTALACION COMPLETADA
echo =====================================================================
echo.
echo El servicio JSWinProxy ha sido detenido y desinstalado.
echo.
echo ARCHIVOS PRESERVADOS (configuracion y tokens - NO se borran automaticamente):
echo   %BASE_DIR%\config.yaml
echo   %BASE_DIR%\proxy_token.txt
echo   %BASE_DIR%\admin_key.txt
echo.
echo Si quieres borrar completamente la configuracion:
echo   del "%BASE_DIR%\config.yaml"
echo   del "%BASE_DIR%\proxy_token.txt"
echo   del "%BASE_DIR%\admin_key.txt"
echo.
echo Para reinstalar: ejecuta install_service.bat (usara config.yaml existente)
echo.
pause