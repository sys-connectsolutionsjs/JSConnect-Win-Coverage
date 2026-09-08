r"""Instala la extensión "Renovar sesión WinForce" en el Chrome de la PC del proxy.

Lo llama `install_service.bat` (como administrador). Idempotente.

Qué hace:
  1. Copia `extension/` (plantilla, puerto 8080) a `.extension_build/` y sustituye
     el puerto por el real de `config.yaml`.
  2. Empaqueta un `.crx` firmado con `chrome --pack-extension` (genera
     `extension.pem` la primera vez; se reutiliza → id de extensión estable).
  3. Escribe `updates.xml` (update manifest local) y `id.txt`.
  4. Escribe la política de Chrome
     `HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionSettings\<id>` = force_installed
     → Chrome la instala sola al reabrir, sin modo desarrollador y sin que el owner
     la pueda quitar por error.

`_desinstalar()` (lo llama `uninstall_service.bat`) borra esa clave.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

_PROXY_DIR = Path(__file__).resolve().parent
_TEMPLATE = _PROXY_DIR / "extension"
_BUILD = _PROXY_DIR / ".extension_build"
_PEM = _PROXY_DIR / "extension.pem"
_CRX = _PROXY_DIR / "extension.crx"
_UPDATES = _PROXY_DIR / "updates.xml"
_ID_FILE = _PROXY_DIR / ".extension_build" / "id.txt"

_POLICY_KEY = r"SOFTWARE\Policies\Google\Chrome\ExtensionSettings"


def _crx_id(pubkey_der: bytes) -> str:
    """Id de una extensión de Chrome: SHA-256 de la clave pública DER, primeros
    16 bytes (32 hex), con cada dígito hex 0-f mapeado a la letra a-p."""
    digest = hashlib.sha256(pubkey_der).hexdigest()[:32]
    return "".join(chr(ord("a") + int(ch, 16)) for ch in digest)


def _render_updates_xml(ext_id: str, crx_uri: str, version: str) -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>\n"
        f"  <app appid='{ext_id}'>\n"
        f'    <updatecheck codebase="{crx_uri}" version="{version}" />\n'
        "  </app>\n"
        "</gupdate>\n"
    )


def _localizar_chrome() -> str | None:
    candidatos = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidatos:
        if os.path.isfile(c):
            return c
    return shutil.which("chrome")


def _puerto_proxy() -> int:
    try:
        from validator_app.proxy.config import get_config

        return get_config().proxy_port
    except Exception:
        return 8080


def _version_extension() -> str:
    import json

    try:
        return json.loads((_TEMPLATE / "manifest.json").read_text(encoding="utf-8"))["version"]
    except Exception:
        return "1.0.0"


def _construir_build(puerto: int) -> None:
    if _BUILD.exists():
        shutil.rmtree(_BUILD)
    shutil.copytree(_TEMPLATE, _BUILD)
    for nombre in ("manifest.json", "background.js"):
        f = _BUILD / nombre
        f.write_text(f.read_text(encoding="utf-8").replace("8080", str(puerto)), encoding="utf-8")


def _empaquetar_crx(chrome: str) -> None:
    """chrome --pack-extension deja `<dir>.crx` y (la 1ª vez) `<dir>.pem` como
    hermanos del directorio."""
    cmd = [chrome, f"--pack-extension={_BUILD}"]
    if _PEM.exists():
        cmd.append(f"--pack-extension-key={_PEM}")
    subprocess.run(cmd, check=True, timeout=120)

    crx_generado = _PROXY_DIR / ".extension_build.crx"
    pem_generado = _PROXY_DIR / ".extension_build.pem"
    if crx_generado.exists():
        crx_generado.replace(_CRX)
    if pem_generado.exists() and not _PEM.exists():
        pem_generado.replace(_PEM)
    elif pem_generado.exists():
        pem_generado.unlink()


def _id_desde_pem() -> str:
    from cryptography.hazmat.primitives import serialization

    key = serialization.load_pem_private_key(_PEM.read_bytes(), password=None)
    der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return _crx_id(der)


def _escribir_politica(ext_id: str) -> bool:
    try:
        import winreg
    except ImportError:
        print("[WARN] winreg no disponible (no es Windows). Politica no escrita.")
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, f"{_POLICY_KEY}\\{ext_id}") as k:
            winreg.SetValueEx(k, "installation_mode", 0, winreg.REG_SZ, "force_installed")
            winreg.SetValueEx(k, "update_url", 0, winreg.REG_SZ, _UPDATES.as_uri())
        return True
    except PermissionError:
        print("[WARN] Sin permisos para HKLM. Ejecuta install_service.bat como Administrador.")
        return False


def _desinstalar() -> int:
    try:
        import winreg
    except ImportError:
        return 0
    if not _ID_FILE.exists():
        print("[INFO] No hay id.txt; nada que quitar.")
        return 0
    ext_id = _ID_FILE.read_text(encoding="utf-8").strip()
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, f"{_POLICY_KEY}\\{ext_id}")
        print(f"[OK] Politica de la extension {ext_id} eliminada.")
    except FileNotFoundError:
        print("[INFO] La politica ya no estaba.")
    except PermissionError:
        print("[WARN] Sin permisos para HKLM (ejecuta como Administrador).")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--uninstall" in argv:
        return _desinstalar()

    chrome = _localizar_chrome()
    if not chrome:
        print(
            "[WARN] Google Chrome no encontrado. La extension 'Renovar sesion WinForce'\n"
            "       no se instalo. Instala Chrome y vuelve a correr:\n"
            "       python -m validator_app.proxy._instalar_extension"
        )
        return 0  # no abortar la instalacion del servicio

    puerto = _puerto_proxy()
    version = _version_extension()
    print(f"[INFO] Construyendo la extension (puerto {puerto}, v{version})...")
    _construir_build(puerto)

    try:
        _empaquetar_crx(chrome)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"[WARN] No se pudo empaquetar el .crx ({e}). Extension no instalada.")
        return 0

    ext_id = _id_desde_pem()
    _UPDATES.write_text(_render_updates_xml(ext_id, _CRX.as_uri(), version), encoding="utf-8")
    _ID_FILE.write_text(ext_id, encoding="utf-8")

    if _escribir_politica(ext_id):
        print(
            f"[OK] Extension '{ext_id}' fuerza-instalada. Reabre Chrome: aparecera\n"
            "     'Renovar sesion WinForce' (icono en la barra)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
