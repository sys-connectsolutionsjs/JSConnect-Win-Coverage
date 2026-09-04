"""CLI para rotar credenciales WinForce (ejecutar via RDP en PC proxy).

Uso:
    python -m validator_app.proxy.rotate_creds

Flujo v1 (hibrido - necesario por Microsoft 2FA):
1. Owner hace login MANUAL en navegador en la PC proxy (incluye 2FA Microsoft)
2. Owner copia cookie PHPSESSID del navegador (F12 -> Application -> Cookies)
3. Script pide la cookie y la valida contra WinForce
4. Si valida, guarda en keyring para que el proxy la use
"""

from __future__ import annotations

import getpass
import json
import sys
from datetime import datetime

import keyring

from validator_app.core import api as core_api
from validator_app.proxy.config import get_config


def extract_php_sessid_from_input() -> str:
    """Pide al usuario que pegue la cookie PHPSESSID."""
    print("\n" + "=" * 60)
    print("ROTACION DE CREDENCIALES WINFORCE (v1 - Hibrido)")
    print("=" * 60)
    print("""
PASO 1: Abre Chrome/Edge en ESTA PC (la del proxy)
PASO 2: Ve a https://appwinforce.win.pe/login
PASO 3: Inicia sesion con las NUEVAS credenciales (incluye 2FA Microsoft)
PASO 4: Cuando estes en el dashboard (menu principal), abre DevTools (F12)
PASO 5: Ve a Application -> Cookies -> https://appwinforce.win.pe
PASO 6: Busca 'PHPSESSID', copia su Value (string largo alfanumerico)
PASO 7: Pegalo abajo cuando se solicite
""")
    print("=" * 60)
    php_sessid = getpass.getpass("Pega el valor de cookie PHPSESSID: ").strip()
    return php_sessid


def validate_session_cookie(php_sessid: str) -> tuple[bool, str]:
    """Valida que la cookie PHPSESSID funciona haciendo una peticion autenticada.

    Delega en el helper compartido `core.api.validar_cookie_sesion()` (usado
    tambien por el proxy) para no duplicar la logica de `operador.php`.
    """
    try:
        core_api.validar_cookie_sesion(php_sessid)
    except core_api.LoginError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error validando sesion: {e}"
    return True, "Sesion valida - operador autenticado"


def save_session_to_keyring(php_sessid: str) -> None:
    """Guarda la cookie de sesion en Windows Keyring."""
    config = get_config()
    cookies = {"PHPSESSID": php_sessid}
    keyring.set_password(
        config.win_keyring_service,
        config.win_keyring_user + "_cookies",
        json.dumps(cookies),
    )
    # Tambien guardar timestamp de actualizacion
    keyring.set_password(
        config.win_keyring_service,
        config.win_keyring_user + "_updated",
        datetime.now().isoformat(timespec="seconds"),
    )


def main() -> int:
    print("\n" + "=" * 60)
    print("  JSCONNECT WIN PROXY - ROTACION DE CREDENCIALES")
    print("=" * 60)

    # Verificar que estamos en la PC correcta (donde corre el proxy)
    config = get_config()
    print(f"\nProxy detectado: {config.proxy_url}")
    print(f"Keyring servicio: {config.win_keyring_service}")
    print(f"Keyring usuario: {config.win_keyring_user}")

    # Pedir cookie PHPSESSID
    php_sessid = extract_php_sessid_from_input()
    if not php_sessid:
        print("[ERROR] PHPSESSID vacio. Cancelado.")
        return 1

    # Validar cookie
    print("\nValidando cookie contra WinForce...")
    ok, msg = validate_session_cookie(php_sessid)
    if not ok:
        print(f"[ERROR] {msg}")
        print("\nPosibles causas:")
        print("  - Cookie copiada incorrectamente (incluye solo el Value)")
        print("  - Sesion ya expiro (haz login fresco y copia rapido)")
        print("  - No completaste el 2FA de Microsoft")
        return 1

    print(f"[OK] {msg}")

    # Guardar en keyring
    print("Guardando en Windows Keyring...")
    save_session_to_keyring(php_sessid)
    print("[OK] Cookie guardada en keyring.")

    # Verificar que el proxy la detecta
    print("\nVerificando estado del proxy...")
    try:
        import httpx

        url = f"{config.proxy_url}/admin/status"
        headers = {"X-Admin-Key": config.admin_key}
        resp = httpx.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            logged = data.get("logged_in")
            age = data.get("session_age")
            print(f"[OK] Proxy status: logged_in={logged}, session_age={age}s")
        else:
            print(f"[WARN] Proxy respondio HTTP {resp.status_code}")
    except Exception as e:
        print(f"[WARN] No se pudo verificar proxy: {e}")

    print("\n" + "=" * 60)
    print("  ROTACION COMPLETADA EXITOSAMENTE")
    print("=" * 60)
    print("Los agentes ya pueden validar con las nuevas credenciales.")
    print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
