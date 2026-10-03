"""Huella de la maquina para la activacion."""

import hashlib
import os
import shutil
import subprocess
import uuid
import winreg

# Windows 11 lanza las consolas en Windows Terminal: sin este flag, cada
# subprocess de la app con ventana abre una ventana visible que roba el foco.
_SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Windows 11 24H2+ ya no trae `wmic`. Sin el, se leen los MISMOS valores de WMI
# por PowerShell/CIM (mismo proveedor y mismo orden que `wmic`), asi que una PC
# de Windows 10 que pasa a Windows 11 conserva su huella y su activacion.
_PS_CIM = (
    "$c = Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty ProcessorId; "
    "$v = Get-CimInstance Win32_Volume | Where-Object { $_.DriveLetter -and "
    "$null -ne $_.SerialNumber } | Select-Object -First 1 -ExpandProperty SerialNumber; "
    "Write-Output \"$c|$v\""
)
_cim_cache: tuple[str, str] | None = None


def _machine_guid():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            return winreg.QueryValueEx(key, "MachineGuid")[0]
    except Exception:
        return ""


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
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_CIM],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                creationflags=_SIN_VENTANA,
            )
            lineas = [line.strip() for line in out.stdout.splitlines() if line.strip()]
            cpu, _, vol = (lineas[-1] if lineas else "|").partition("|")
            _cim_cache = (cpu.strip(), vol.strip())
        except Exception:
            _cim_cache = ("", "")
    return _cim_cache


def _cpu():
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
            creationflags=_SIN_VENTANA,
        )
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        return lines[1] if len(lines) > 1 else ""
    except Exception:
        return os.environ.get("PROCESSOR_IDENTIFIER", "")


def _volume_serial():
    if not _hay_wmic():
        return _cim()[1]
    try:
        out = subprocess.run(
            ["wmic", "volume", "get", "DriveLetter,SerialNumber"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=_SIN_VENTANA,
        )
        for line in out.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].endswith(":"):
                return parts[1]
    except Exception:
        pass
    return ""


def _formatear(material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16].upper()
    return "-".join(digest[i : i + 4] for i in range(0, 16, 4))


def obtener_huella() -> str:
    return _formatear("|".join([_machine_guid(), _mac(), _cpu(), _volume_serial()]))


def _huella_legacy_sin_wmic() -> str:
    """La huella que calculaban las versiones anteriores en una PC SIN `wmic`
    (Windows 11 24H2+): CPU = PROCESSOR_IDENTIFIER y volumen vacio."""
    return _formatear(
        "|".join([_machine_guid(), _mac(), os.environ.get("PROCESSOR_IDENTIFIER", ""), ""])
    )


def huellas_compatibles() -> set[str]:
    """Huellas que se aceptan para una activacion ya guardada: la actual y, en
    una PC sin `wmic`, la que calculaban las versiones anteriores (asi no se
    pierden las activaciones hechas antes de este cambio)."""
    huellas = {obtener_huella()}
    if not _hay_wmic():
        huellas.add(_huella_legacy_sin_wmic())
    return huellas
