"""Aislamiento global de la suite.

Sin esto, cualquier test que ejerza codigo con `keyring.set_password` escribe en
el almacen de credenciales real del sistema. En concreto
`test_set_session_cookie_limpia_session_dead_since` guardaba
`{"PHPSESSID": "cookie-nueva"}` en `JSWinProxy/credentials_cookies` -- la misma
clave que el proxy lee al arrancar (`server._load_session_cookies`) -- y dejaba
la sesion del proxy envenenada: al reiniciar restauraba esa cookie de pega,
reportaba `logged_in: true` y todo `/api/*` fallaba con el HTML de login.

El fixture es autouse: cada test corre contra un keyring en memoria y el estado
no cruza de un test a otro ni sale al sistema.
"""

import keyring
import pytest


@pytest.fixture(autouse=True)
def keyring_en_memoria(monkeypatch):
    """Reemplaza las funciones de modulo de `keyring` por un dict por test."""
    store: dict[tuple[str, str], str] = {}

    monkeypatch.setattr(keyring, "get_password", lambda s, u: store.get((s, u)))
    monkeypatch.setattr(
        keyring, "set_password", lambda s, u, p: store.__setitem__((s, u), p)
    )
    monkeypatch.setattr(
        keyring, "delete_password", lambda s, u: store.pop((s, u), None)
    )

    return store
