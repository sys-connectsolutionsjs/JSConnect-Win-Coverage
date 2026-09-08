"""CLI para rotar / renovar la sesion WinForce del proxy (PC de oficina).

Uso:
    python -m validator_app.proxy.rotate_creds            # asistido (navegador)
    python -m validator_app.proxy.rotate_creds --manual   # pegar la cookie a mano
    python -m validator_app.proxy.rotate_creds --fresh     # asistido, perfil limpio

Por el 2FA de Microsoft el login programatico es inviable: la cookie PHPSESSID
sale siempre de un login manual en navegador.

- **Asistido** (por defecto, lo que lanza el icono "Renovar sesion WinForce" del
  Escritorio): abre Chromium, el owner inicia sesion normalmente y el script
  captura la PHPSESSID solo, la valida y la guarda. Resultado por cuadro de
  dialogo (sin consola).
- **--manual**: el owner/tecnico pega la PHPSESSID (F12 -> Application -> Cookies)
  en la consola. Fallback si Playwright se rompe.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime

import keyring

from validator_app.core import api as core_api
from validator_app.proxy.config import get_config
from validator_app.proxy.login_asistido import (
    LoginAsistidoError,
    capturar_php_sessid_asistido,
)

_TITULO = "Renovar sesion WinForce"


def extract_php_sessid_from_input() -> str:
    """Pide al usuario que pegue la cookie PHPSESSID (flujo --manual)."""
    print("\n" + "=" * 60)
    print("ROTACION DE CREDENCIALES WINFORCE (--manual)")
    print("=" * 60)
    print("""
PASO 1: Abre Chrome/Edge en ESTA PC (la del proxy)
PASO 2: Ve a https://appwinforce.win.pe/login
PASO 3: Inicia sesion con las credenciales (incluye 2FA Microsoft)
PASO 4: Cuando estes en el dashboard, abre DevTools (F12)
PASO 5: Ve a Application -> Cookies -> https://appwinforce.win.pe
PASO 6: Busca 'PHPSESSID', copia su Value (string largo alfanumerico)
PASO 7: Pegalo abajo cuando se solicite
""")
    print("=" * 60)
    return getpass.getpass("Pega el valor de cookie PHPSESSID: ").strip()


def validate_session_cookie(php_sessid: str) -> tuple[bool, str]:
    """Valida que la cookie PHPSESSID funciona con una peticion autenticada.

    Delega en el helper compartido `core.api.validar_cookie_sesion()`.
    """
    try:
        core_api.validar_cookie_sesion(php_sessid)
    except core_api.LoginError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error validando sesion: {e}"
    return True, "Sesion valida - operador autenticado"


def save_session_to_keyring(php_sessid: str) -> None:
    """Guarda la cookie de sesion + timestamp en Windows Keyring."""
    config = get_config()
    keyring.set_password(
        config.win_keyring_service,
        config.win_keyring_user + "_cookies",
        json.dumps({"PHPSESSID": php_sessid}),
    )
    keyring.set_password(
        config.win_keyring_service,
        config.win_keyring_user + "_updated",
        datetime.now().isoformat(timespec="seconds"),
    )


def _verificar_proxy(quiet: bool = False) -> None:
    """Comprueba que el proxy en marcha ya ve la sesion nueva (best-effort)."""
    config = get_config()
    try:
        import httpx

        resp = httpx.get(
            f"{config.proxy_url}/admin/status",
            headers={"X-Admin-Key": config.admin_key},
            timeout=5,
        )
        if not quiet:
            if resp.status_code == 200:
                data = resp.json()
                print(f"[OK] Proxy: logged_in={data.get('logged_in')}, "
                      f"session_age={data.get('session_age')}s")
            else:
                print(f"[WARN] Proxy respondio HTTP {resp.status_code}")
    except Exception as e:
        if not quiet:
            print(f"[WARN] No se pudo verificar el proxy: {e}")


def _avisar(ok: bool, titulo: str, mensaje: str) -> None:
    """Muestra el resultado en un cuadro de dialogo (sin consola). Si tkinter no
    esta disponible, cae a stdout."""
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        (messagebox.showinfo if ok else messagebox.showerror)(titulo, mensaje)
        root.destroy()
    except Exception:
        print(f"[{'OK' if ok else 'ERROR'}] {titulo}: {mensaje}")


def _main_manual() -> int:
    print("\n" + "=" * 60)
    print("  JSCONNECT WIN PROXY - ROTACION DE CREDENCIALES (--manual)")
    print("=" * 60)
    config = get_config()
    print(f"\nProxy detectado: {config.proxy_url}")
    print(f"Keyring: {config.win_keyring_service}/{config.win_keyring_user}")

    php_sessid = extract_php_sessid_from_input()
    if not php_sessid:
        print("[ERROR] PHPSESSID vacio. Cancelado.")
        return 1

    print("\nValidando cookie contra WinForce...")
    ok, msg = validate_session_cookie(php_sessid)
    if not ok:
        print(f"[ERROR] {msg}")
        print("\nPosibles causas: cookie mal copiada / sesion ya expirada / "
              "2FA de Microsoft sin completar.")
        return 1
    print(f"[OK] {msg}")

    print("Guardando en Windows Keyring...")
    save_session_to_keyring(php_sessid)
    print("[OK] Cookie guardada.")

    print("\nVerificando estado del proxy...")
    _verificar_proxy()

    print("\n" + "=" * 60)
    print("  ROTACION COMPLETADA")
    print("=" * 60 + "\n")
    return 0


def _main_asistido(args: argparse.Namespace) -> int:
    try:
        php_sessid = capturar_php_sessid_asistido(
            timeout_min=args.timeout, fresh=args.fresh
        )
    except LoginAsistidoError as e:
        _avisar(False, _TITULO, str(e))
        return 1

    ok, msg = validate_session_cookie(php_sessid)
    if not ok:
        _avisar(
            False,
            _TITULO,
            f"La sesion capturada no quedo valida ({msg}). "
            "Vuelve a abrir 'Renovar sesion WinForce' e intentalo de nuevo.",
        )
        return 1

    save_session_to_keyring(php_sessid)
    _verificar_proxy(quiet=True)
    _avisar(True, _TITULO, "Sesion renovada correctamente. Ya puedes cerrar todo.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Renueva la sesion WinForce del proxy (cookie PHPSESSID)."
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Pegar la PHPSESSID a mano en la consola (fallback sin navegador).",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Asistido: borra el perfil del navegador antes de abrirlo.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Asistido: minutos de espera antes de rendirse (por defecto 10).",
    )
    args = parser.parse_args(argv)

    if args.manual:
        return _main_manual()
    return _main_asistido(args)


if __name__ == "__main__":
    sys.exit(main())
