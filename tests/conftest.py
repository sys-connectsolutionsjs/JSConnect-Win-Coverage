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


@pytest.fixture(autouse=True)
def avisos_capturados(monkeypatch):
    """El aviso al owner (Etapa R) escribe en el Registro de Eventos de Windows
    (`eventcreate`) y hace POST a un webhook. En los tests eso es un efecto de
    sistema real -- el mismo tipo de fuga que motivó `keyring_en_memoria`.

    Este fixture autouse sustituye `_disparar_aviso` por un registrador
    síncrono: cada `(evento, detalle)` va a la lista que devuelve el fixture, sin
    hilos, sin subprocess, sin red. Los tests que quieran verificar el aviso
    piden `avisos_capturados` y assertan sobre la lista.
    """
    from validator_app.proxy import server

    eventos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        server.ProxyValidatorAPI,
        "_disparar_aviso",
        lambda self, evento, detalle="": eventos.append((evento, detalle)),
    )
    return eventos
