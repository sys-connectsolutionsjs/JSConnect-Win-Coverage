"""Huella de la maquina para la activacion.

La huella actual usa solo dos datos que no cambian con la red, los discos USB ni la
version de Windows: el MachineGuid y el identificador del CPU, ambos leidos del
registro (sin `wmic`, sin PowerShell, sin lanzar procesos).

La huella de versiones anteriores (MachineGuid|MAC|CPU|volumen) cambiaba con una VPN,
un USB o la falta de `wmic`, y por eso se perdia el estado "activado". Sigue
disponible en `huellas_legacy()` solo para que las activaciones ya hechas funcionen
mientras el agente se reactiva.
"""

import hashlib
import os
import shutil
import subprocess
import uuid
import winreg

_CPU_REG = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"


def _machine_guid():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            return winreg.QueryValueEx(key, "MachineGuid")[0]
    except Exception:
        return ""


def _cpu_registro():
    """Identifier + nombre del primer CPU segun el registro. Windows lo arma al
    arrancar; no depende de `wmic` ni de PowerShell."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _CPU_REG) as key:
            ident = winreg.QueryValueEx(key, "Identifier")[0]
            nombre = winreg.QueryValueEx(key, "ProcessorNameString")[0]
        return f"{ident}|{nombre}".strip()
    except Exception:
        return os.environ.get("PROCESSOR_IDENTIFIER", "")


def _formatear(material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16].upper()
    return "-".join(digest[i : i + 4] for i in range(0, 16, 4))


def obtener_huella() -> str:
    return _formatear("|".join([_machine_guid(), _cpu_registro()]))


# --- Huella de versiones anteriores ------------------------------------------------
# NO BORRAR esto (ni el uso de `huellas_legacy` en la ventana principal) salvo que el
# usuario lo pida expresamente: el actualizador salta directo al ultimo Release, y un
# agente que se salte la transicion perderia su activacion (ver AGENTS.md).

# Windows 11 lanza las consolas en Windows Terminal: sin este flag, cada
# subprocess de la app con ventana abre una ventana visible que roba el foco.
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Windows 11 24H2+ ya no trae `wmic`. Sin el, se leen los MISMOS valores de WMI
# por PowerShell/CIM (mismo proveedor y mismo orden que `wmic`).
_PS_CIM = (
    "$c = Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty ProcessorId; "
    "$v = Get-CimInstance Win32_Volume | Where-Object { $_.DriveLetter -and "
    "$null -ne $_.SerialNumber } | Select-Object -First 1 -ExpandProperty SerialNumber; "
    "Write-Output \"$c|$v\""
)
_cim_cache: tuple[str, str] | None = None


def _mac():
    try:
        mac = uuid.getnode()
        if (mac >> 40) & 1:
            return ""
        return ":".join(f"{(mac >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1))
    except Exception:
        return ""


def _hay_wmic() -> bool:
    return shutil.which("wmic") is not None


def _cim() -> tuple[str, str]:
    """(ProcessorId, SerialNumber del primer volumen con letra) via CIM. Una sola
    llamada a PowerShell para ambos valores, cacheada por proceso."""
    global _cim_cache
    if _cim_cache is None:
        try:
            out = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    _PS_CIM,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                stdin=subprocess.DEVNULL,
                creationflags=_SIN_VENTANA,
            )
            lineas = [line.strip() for line in out.stdout.splitlines() if line.strip()]
            cpu, _, vol = (lineas[-1] if lineas else "|").partition("|")
            _cim_cache = (cpu.strip(), vol.strip())
        except Exception:
            _cim_cache = ("", "")
    return _cim_cache


def _cpu_legacy():
    if not _hay_wmic():
        cpu = _cim()[0]
        return cpu or os.environ.get("PROCESSOR_IDENTIFIER", "")
    try:
        out = subprocess.run(
            ["wmic", "cpu", "get", "ProcessorId"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
            creationflags=_SIN_VENTANA,
        )
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        return lines[1] if len(lines) > 1 else ""
    except Exception:
        return os.environ.get("PROCESSOR_IDENTIFIER", "")


def _volume_serial_legacy():
    if not _hay_wmic():
        return _cim()[1]
    try:
        out = subprocess.run(
            ["wmic", "volume", "get", "DriveLetter,SerialNumber"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            stdin=subprocess.DEVNULL,
            creationflags=_SIN_VENTANA,
        )
        for line in out.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].endswith(":"):
                return parts[1]
    except Exception:
        pass
    return ""


def huellas_legacy() -> set[str]:
    """Huellas (MachineGuid|MAC|CPU|volumen) que calculaban las versiones anteriores
    en ESTA PC: la leida con `wmic` o CIM, y la que salia en una PC sin `wmic`
    (CPU = PROCESSOR_IDENTIFIER y volumen vacio)."""
    guid, mac = _machine_guid(), _mac()
    return {
        _formatear("|".join([guid, mac, _cpu_legacy(), _volume_serial_legacy()])),
        _formatear("|".join([guid, mac, os.environ.get("PROCESSOR_IDENTIFIER", ""), ""])),
    }
