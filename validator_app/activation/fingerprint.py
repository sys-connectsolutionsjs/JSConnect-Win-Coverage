"""Huella de la maquina para la activacion."""

import hashlib
import os
import subprocess
import uuid
import winreg


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


def _cpu():
    try:
        out = subprocess.run(
            ["wmic", "cpu", "get", "ProcessorId"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        return lines[1] if len(lines) > 1 else ""
    except Exception:
        return os.environ.get("PROCESSOR_IDENTIFIER", "")


def _volume_serial():
    try:
        out = subprocess.run(
            ["wmic", "volume", "get", "DriveLetter,SerialNumber"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        for line in out.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].endswith(":"):
                return parts[1]
    except Exception:
        pass
    return ""


def obtener_huella() -> str:
    material = "|".join([_machine_guid(), _mac(), _cpu(), _volume_serial()])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16].upper()
    return "-".join(digest[i : i + 4] for i in range(0, 16, 4))
