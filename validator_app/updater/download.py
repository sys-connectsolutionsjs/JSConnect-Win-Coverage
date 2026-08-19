"""Descarga y aplicacion de actualizaciones.

El .exe en ejecucion no puede sobrescribirse: se descarga a %TEMP%, se verifica
su SHA-256 y se lanza un updater.bat que espera, reemplaza y relanza la app.
"""

import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests


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


def extraer_checksum(notas: str):
    match = re.search(r"(?i)(?:sha[- ]?256|checksum)[:=\s]*([0-9a-f]{64})", notas or "")
    return match.group(1) if match else None


def aplicar_actualizacion(info: dict) -> bool:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Las actualizaciones solo se aplican al .exe compilado.")

    url = info.get("url_descarga")
    if not url:
        raise ValueError("El release no tiene un asset .exe.")

    temp_dir = Path(tempfile.gettempdir()) / "jsconnect_update"
    temp_dir.mkdir(parents=True, exist_ok=True)
    nuevo = temp_dir / "JSConnect-Win-Coverage.exe"

    descargar(url, nuevo)

    checksum = extraer_checksum(info.get("notes", ""))
    if checksum and sha256_de(nuevo) != checksum:
        raise ValueError("Checksum no coincide: el archivo esta corrupto o fue manipulado.")

    exe_actual = Path(sys.executable)
    bat = temp_dir / "updater.bat"
    bat.write_text(
        "@echo off\r\n"
        f"timeout /t 2 /nobreak >nul\r\n"
        f'move /y "{nuevo}" "{exe_actual}"\r\n'
        f'start "" "{exe_actual}"\r\n'
        f'del "%~f0"\r\n',
        encoding="utf-8",
    )
    subprocess.Popen(["cmd", "/c", str(bat)], close_fds=True)
    return True
