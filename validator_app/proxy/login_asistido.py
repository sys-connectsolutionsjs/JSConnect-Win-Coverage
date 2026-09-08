"""Login asistido: recolecta la cookie PHPSESSID de WinForce con un navegador real.

El owner hace login normal (incluye el 2FA de Microsoft el primer login de cada
jornada) en una ventana de Chromium que abre este modulo; el script lee la
`PHPSESSID` del contexto del navegador (`context.cookies()` ve las cookies
HttpOnly, a diferencia de `document.cookie`), la valida contra WinForce y la
devuelve. Sin F12, sin copiar/pegar.

El perfil del navegador es PERSISTENTE (`.browser_profile/`, gitignored): dentro
de la misma jornada el SSO de Microsoft se salta el 2FA en renovaciones
sucesivas. `fresh=True` lo borra si algo se atasca.

Lo usa `rotate_creds.py` (sin argumentos). Playwright se importa de forma
perezosa: si no esta instalado, `--manual` sigue funcionando.
"""

from __future__ import annotations

import contextlib
import shutil
import time
from pathlib import Path

from validator_app.core import api as core_api

LOGIN_URL = "https://appwinforce.win.pe/login"
_PROFILE_DIR = Path(__file__).parent / ".browser_profile"
_POLL_SECONDS = 3

_OVERLAY_JS = """
(args) => {
  let b = document.getElementById('js-login-asistido');
  if (!b) {
    b = document.createElement('div');
    b.id = 'js-login-asistido';
    b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;' +
      'font:bold 16px/1.5 sans-serif;color:#fff;padding:12px 18px;text-align:center;' +
      'box-shadow:0 2px 10px rgba(0,0,0,.4);';
    document.body.appendChild(b);
  }
  b.textContent = args.mensaje;
  b.style.background = args.color;
}
"""


class LoginAsistidoError(Exception):
    """La captura por navegador no pudo completarse."""


def _import_sync_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright


def _php_sessid_de_cookies(cookies: list[dict]) -> str | None:
    """Saca la PHPSESSID de WinForce de la lista de cookies de Playwright."""
    for c in cookies:
        if c.get("name") == "PHPSESSID" and "appwinforce.win.pe" in (c.get("domain") or ""):
            return c.get("value") or None
    return None


def _overlay(page, mensaje: str, color: str = "#0a3d91") -> None:
    with contextlib.suppress(Exception):
        page.evaluate(_OVERLAY_JS, {"mensaje": mensaje, "color": color})


def capturar_php_sessid_asistido(timeout_min: int = 10, fresh: bool = False) -> str:
    """Abre el navegador, espera a que el owner inicie sesion y devuelve una
    PHPSESSID ya validada contra WinForce. Lanza LoginAsistidoError si no se
    logra (timeout, ventana cerrada antes de tiempo, sin Playwright)."""
    try:
        sync_playwright = _import_sync_playwright()
    except ImportError as e:
        raise LoginAsistidoError(
            "Playwright no esta instalado en esta PC. Ejecuta install_service.bat, "
            "o usa `python -m validator_app.proxy.rotate_creds --manual` para "
            "pegar la cookie a mano."
        ) from e

    if fresh:
        shutil.rmtree(_PROFILE_DIR, ignore_errors=True)
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    limite = time.monotonic() + timeout_min * 60
    php: str | None = None

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(_PROFILE_DIR),
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        with contextlib.suppress(Exception):
            page.goto(LOGIN_URL)

        while time.monotonic() < limite:
            try:
                cookies = context.cookies()
            except Exception:
                break  # navegador cerrado por el owner

            _overlay(
                page,
                "Inicia sesion en WinForce normalmente. Esta ventana se cerrara "
                "sola cuando la sesion quede lista.",
            )

            candidato = _php_sessid_de_cookies(cookies)
            if candidato:
                try:
                    core_api.validar_cookie_sesion(candidato)
                    php = candidato
                    break
                except core_api.LoginError:
                    pass  # cookie aun no autenticada (falta el 2FA)
                except Exception:
                    pass  # red/WinForce: reintentar

            time.sleep(_POLL_SECONDS)

        if php:
            _overlay(page, "Sesion capturada. Ya puedes cerrar esta ventana.", color="#0a7d2c")
            time.sleep(2)
        with contextlib.suppress(Exception):
            context.close()

    if not php:
        raise LoginAsistidoError(
            "No se capturo la sesion. Vuelve a abrir 'Renovar sesion WinForce' e "
            "inicia sesion por completo (incluye el paso de Microsoft) antes de "
            "cerrar la ventana."
        )
    return php
