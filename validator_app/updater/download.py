"""Descarga y aplicacion de actualizaciones.

El .exe en ejecucion no puede sobrescribirse: se descarga a %TEMP%, se verifica
su SHA-256 y se lanza un updater.bat que espera, reemplaza y relanza la app.
"""

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

# Segundos que el .bat espera a que el PID actual desaparezca antes de darse
# por vencido (el .exe viejo puede tardar un poco en soltar el archivo tras
# cerrarse). Igual de tope para los reintentos de `move`.
ESPERA_MAXIMA_SEGUNDOS = 30
REINTENTOS_MOVE = 10

# Asset por defecto cuando `info` no trae "nombre_asset" (el agente).
NOMBRE_EXE_AGENTE = "JSConnect-Win-Coverage.exe"


def descargar(url: str, destino: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with open(destino, "wb") as f:
            f.writelines(resp.iter_content(1024 * 256))


def sha256_de(archivo: Path) -> str:
    digest = hashlib.sha256()
    with open(archivo, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def extraer_checksum(notas: str, nombre_archivo: str | None = None):
    """Busca un checksum SHA-256 en las notas del release.

    Si `nombre_archivo` se pasa (release con mas de un asset, cada uno con su
    propio bloque "## <nombre>\nSHA-256: ..."), recorta las notas a ese bloque
    primero - evita extraer el hash de OTRO archivo cuando el release trae
    varios (p.ej. agente + consola owner en el mismo release)."""
    texto = notas or ""
    if nombre_archivo:
        bloque = re.search(
            rf"(?i){re.escape(nombre_archivo)}.*?(?=\n##\s|\Z)", texto, re.DOTALL
        )
        texto = bloque.group(0) if bloque else ""
    match = re.search(r"(?i)(?:sha[- ]?256|checksum)[:=\s`]*([0-9a-f]{64})", texto)
    return match.group(1) if match else None


def _script_updater(nuevo: Path, exe_actual: Path, pid: int) -> str:
    """Bat que espera a que el proceso viejo (`pid`) termine de verdad antes
    de reemplazar el .exe.

    Reemplaza el `timeout /t 2` fijo que usaba la version anterior: con la
    app todavia corriendo (nada la cerraba), el .exe seguia bloqueado tras
    esos 2s, `move` fallaba EN SILENCIO (sin chequear `errorlevel`) y el
    `start` de despues igual se ejecutaba -- relanzando la version VIEJA y
    dejando dos procesos vivos (bug real, 2026-09-29). Ahora: espera activa
    por PID, reintenta el `move`, y solo relanza si el `move` funciono."""
    return (
        "@echo off\r\n"
        "setlocal enabledelayedexpansion\r\n"
        f'set "PID={pid}"\r\n'
        f'set "NUEVO={nuevo}"\r\n'
        f'set "DESTINO={exe_actual}"\r\n'
        "set /a ESPERA=0\r\n"
        ":esperar_cierre\r\n"
        'tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        f"    if !ESPERA! GEQ {ESPERA_MAXIMA_SEGUNDOS} goto fallo\r\n"
        "    set /a ESPERA+=1\r\n"
        "    timeout /t 1 /nobreak >nul\r\n"
        "    goto esperar_cierre\r\n"
        ")\r\n"
        "set /a INTENTOS=0\r\n"
        ":mover\r\n"
        'move /y "%NUEVO%" "%DESTINO%" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        f"    if !INTENTOS! GEQ {REINTENTOS_MOVE} goto fallo\r\n"
        "    set /a INTENTOS+=1\r\n"
        "    timeout /t 1 /nobreak >nul\r\n"
        "    goto mover\r\n"
        ")\r\n"
        'start "" "%DESTINO%"\r\n'
        'del "%~f0"\r\n'
        "exit /b 0\r\n"
        ":fallo\r\n"
        "rem no se pudo reemplazar el ejecutable (bloqueado demasiado tiempo)\r\n"
        'del "%~f0"\r\n'
        "exit /b 1\r\n"
    )


def aplicar_actualizacion(info: dict) -> bool:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Las actualizaciones solo se aplican al .exe compilado.")

    url = info.get("url_descarga")
    if not url:
        raise ValueError("El release no tiene un asset .exe.")

    # El agente y la consola owner comparten este flujo: cada uno pide su asset.
    nombre = info.get("nombre_asset") or NOMBRE_EXE_AGENTE
    temp_dir = Path(tempfile.gettempdir()) / "jsconnect_update"
    temp_dir.mkdir(parents=True, exist_ok=True)
    nuevo = temp_dir / nombre

    descargar(url, nuevo)

    checksum = extraer_checksum(info.get("notes", ""), nombre_archivo=nombre)
    if checksum and sha256_de(nuevo) != checksum:
        raise ValueError("Checksum no coincide: el archivo esta corrupto o fue manipulado.")

    exe_actual = Path(sys.executable)
    bat = temp_dir / "updater.bat"
    bat.write_text(_script_updater(nuevo, exe_actual, os.getpid()), encoding="utf-8")
    # CREATE_NO_WINDOW: en Windows 11 el .bat se abriria en una ventana de
    # Windows Terminal. Sigue teniendo consola (oculta), asi que `timeout` funciona.
    subprocess.Popen(
        ["cmd", "/c", str(bat)],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return True
