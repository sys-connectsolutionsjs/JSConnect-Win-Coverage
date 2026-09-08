"""Sesión de WinForce para el modo standalone (sin proxy).

El modo standalone es para desarrollo / pruebas / el owner — NO para los 20
agentes (esos van por el proxy). Como el login programático es inviable por el
2FA de Microsoft, el usuario pega una vez su cookie `PHPSESSID` (obtenida de un
login manual en el navegador) en el diálogo "⚙ Configurar Sesión"; se valida
contra WinForce y se guarda en el keyring local.

`main_window.py` construye el `ValidatorAPI` standalone con `cliente_standalone()`.
"""

from __future__ import annotations

import contextlib

import keyring

from validator_app.core import api

_SERVICE = "JSWinCoverage"
_USER = "session_cookie"


def guardar_cookie(php_sessid: str) -> None:
    keyring.set_password(_SERVICE, _USER, php_sessid)


def cargar_cookie() -> str | None:
    return keyring.get_password(_SERVICE, _USER) or None


def borrar_cookie() -> None:
    with contextlib.suppress(Exception):
        keyring.delete_password(_SERVICE, _USER)  # ignora "no estaba guardada"


def validar_y_guardar(php_sessid: str) -> None:
    """Valida la cookie contra WinForce y, si sirve, la guarda.

    Lanza ValueError si viene vacía, o core.api.LoginError si la sesión no está
    activa en WinForce.
    """
    php_sessid = (php_sessid or "").strip()
    if not php_sessid:
        raise ValueError("La cookie PHPSESSID está vacía.")
    api.validar_cookie_sesion(php_sessid)
    guardar_cookie(php_sessid)


def cliente_standalone() -> api.ValidatorAPI | None:
    """`ValidatorAPI` con la cookie del keyring inyectada, o None si no hay."""
    ck = cargar_cookie()
    if not ck:
        return None
    cliente = api.ValidatorAPI()
    cliente.set_session_cookies({"PHPSESSID": ck})
    # El usuario gestiona la cookie a mano (la re-pega cuando expira); el guard
    # idle de 120s del core solo estorba aquí — igual que en el proxy.
    cliente._session_max_idle = 10**9
    return cliente
