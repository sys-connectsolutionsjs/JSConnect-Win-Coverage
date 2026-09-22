"""Lectura y rotacion de proxy_token / admin_key desde config.yaml.

Funciones puras (reciben la ruta, no dependen de un proceso corriendo elevado
ni de tkinter) para que la consola del owner (generator/owner_app.py) las
invoque desde un subproceso relanzado con permisos de administrador -
config.yaml tiene ACL de SYSTEM+Administradores, igual que la aplica
install_service.bat.
"""

from __future__ import annotations

import contextlib
import re
import secrets
import subprocess
from pathlib import Path

NOMBRE_SERVICIO = "JSWinProxy"
CUALES_VALIDOS = ("proxy_token", "admin_key")

_LINEA_CLAVE = re.compile(r'^(?P<clave>proxy_token|admin_key):\s*"(?P<valor>[^"]*)"\s*$')

# BASE_DIR relativo a este modulo: sirve como fallback en desarrollo, cuando
# el servicio de Windows no esta instalado (config.py:20-22 usa la misma ruta).
_BASE_DIR_DESARROLLO = Path(__file__).resolve().parent

# Etiqueta de "BINARY_PATH_NAME" en la salida de `sc qc`: varia con el idioma
# de Windows. Ingles primero (mas comun en instalaciones corporativas base),
# espanol como segunda opcion (idioma real de las PC de la oficina).
_ETIQUETAS_BINARY_PATH = ("BINARY_PATH_NAME", "NOMBRE_RUTA_BINARIO")


class SecretosError(Exception):
    """Error legible por el owner (se muestra tal cual en la GUI)."""


def ruta_instalacion(runner=subprocess.run) -> Path:
    """Directorio real donde vive config.yaml en la PC instalada.

    config.py:22 resuelve config.yaml junto al modulo, pero en el .exe onefile
    ese "modulo" vive en el directorio temporal de PyInstaller (el mismo
    problema resuelto para la consola owner en 63ca477). El WinSW que instala
    install_service.bat registra el servicio con el binPath apuntando a
    validator_app\\proxy dentro de la instalacion real, asi que se deriva de
    ahi via `sc qc`.

    La etiqueta de `sc qc` para el binPath cambia con el idioma de Windows
    ("BINARY_PATH_NAME" en ingles, "NOMBRE_RUTA_BINARIO" en espanol) -
    _ETIQUETAS_BINARY_PATH prueba ambas, ingles primero.
    """
    try:
        resultado = runner(
            ["sc", "qc", NOMBRE_SERVICIO], capture_output=True, text=True, timeout=10, check=False
        )
    except OSError as exc:
        raise SecretosError(f"No se pudo consultar el servicio {NOMBRE_SERVICIO}: {exc}") from exc

    if resultado.returncode == 0:
        for linea in resultado.stdout.splitlines():
            linea_mayus = linea.upper()
            if not any(etq in linea_mayus for etq in _ETIQUETAS_BINARY_PATH):
                continue
            bin_path = linea.split(":", 1)[1].strip()
            # El binPath es el .exe de WinSW dentro de validator_app\proxy; a veces
            # viene entre comillas si la ruta tiene espacios.
            bin_path = bin_path.strip('"')
            carpeta = Path(bin_path).resolve().parent
            if (carpeta / "config.yaml").exists():
                return carpeta

    if (_BASE_DIR_DESARROLLO / "config.yaml").exists():
        return _BASE_DIR_DESARROLLO

    raise SecretosError(
        f"No se encontro config.yaml (servicio {NOMBRE_SERVICIO} no instalado "
        "o config.yaml ausente)."
    )


def leer_secretos(base_dir: Path) -> dict[str, str]:
    """Lee proxy_token y admin_key de config.yaml. Requiere permisos de lectura
    (ACL de SYSTEM+Administradores: hace falta correr elevado)."""
    config_yaml = base_dir / "config.yaml"
    try:
        texto = config_yaml.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SecretosError(f"No existe {config_yaml}") from exc
    except PermissionError as exc:
        raise SecretosError(
            f"Sin permiso para leer {config_yaml}. ¿Esta corriendo elevado?"
        ) from exc

    valores: dict[str, str] = {}
    for linea in texto.splitlines():
        m = _LINEA_CLAVE.match(linea.strip())
        if m:
            valores[m.group("clave")] = m.group("valor")

    faltantes = [c for c in CUALES_VALIDOS if c not in valores]
    if faltantes:
        raise SecretosError(f"config.yaml no tiene: {', '.join(faltantes)}")
    return valores


def _reescribir_linea(texto: str, cual: str, valor_nuevo: str) -> str:
    """Reemplaza solo la linea `cual: "..."`, preservando el resto del archivo
    (comentarios, puerto, allowed_networks, timeouts) tal cual esta."""
    patron = re.compile(rf'^({re.escape(cual)}:\s*)"[^"]*"(\s*)$', re.MULTILINE)
    nuevo_texto, n = patron.subn(rf'\g<1>"{valor_nuevo}"\g<2>', texto)
    if n != 1:
        raise SecretosError(f"No se encontro (o hay duplicada) la linea '{cual}:' en config.yaml")
    return nuevo_texto


def _aplicar_acl(ruta: Path, runner=subprocess.run) -> None:
    """Misma restriccion que install_service.bat:273-276: SYSTEM + Administradores
    (o Administrators en Windows en ingles), sin heredar del padre."""
    args_base = ["icacls", str(ruta), "/inheritance:r", "/grant:r", "SYSTEM:F"]
    resultado = runner(
        [*args_base, "BUILTIN\\Administradores:F"], capture_output=True, check=False
    )
    if resultado.returncode != 0:
        runner([*args_base, "BUILTIN\\Administrators:F"], capture_output=True, check=False)


def rotar(base_dir: Path, cual: str, runner=subprocess.run) -> str:
    """Genera un valor nuevo para `cual` ('proxy_token' o 'admin_key'), lo
    escribe en config.yaml y en el .txt correspondiente, reaplica la ACL y
    reinicia el servicio para que tome el cambio. Devuelve el valor nuevo."""
    if cual not in CUALES_VALIDOS:
        raise SecretosError(f"'{cual}' invalido: debe ser uno de {CUALES_VALIDOS}")

    config_yaml = base_dir / "config.yaml"
    try:
        texto = config_yaml.read_text(encoding="utf-8")
    except OSError as exc:
        raise SecretosError(f"No se pudo leer {config_yaml}: {exc}") from exc

    valor_nuevo = secrets.token_hex(32)
    texto_nuevo = _reescribir_linea(texto, cual, valor_nuevo)

    try:
        config_yaml.write_text(texto_nuevo, encoding="utf-8")
    except OSError as exc:
        raise SecretosError(f"No se pudo escribir {config_yaml}: {exc}") from exc

    archivo_txt = base_dir / f"{cual}.txt"
    # config.yaml es la fuente de verdad; el .txt es solo de referencia.
    with contextlib.suppress(OSError):
        archivo_txt.write_text(valor_nuevo, encoding="utf-8")

    _aplicar_acl(config_yaml, runner)
    _aplicar_acl(archivo_txt, runner)

    try:
        runner(
            ["powershell", "-NoProfile", "-Command", f"Restart-Service {NOMBRE_SERVICIO}"],
            capture_output=True, timeout=120, check=False,
        )
    except OSError as exc:
        raise SecretosError(
            f"{cual} rotado, pero no se pudo reiniciar el servicio: {exc}. "
            "Reinicialo desde la consola para que tome el cambio."
        ) from exc

    return valor_nuevo
