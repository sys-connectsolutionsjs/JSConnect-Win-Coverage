"""Tests de validator_app.gui.session_config (Fase 3 — sesión del modo standalone).

El diálogo Tkinter no se testea; sí la lógica pura (keyring + validación +
construcción del cliente).
"""

from unittest import mock

import pytest

from validator_app.core import api as core_api
from validator_app.gui import session_config


@pytest.fixture
def _fake_keyring(monkeypatch):
    store: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        session_config.keyring, "set_password",
        lambda s, u, v: store.__setitem__((s, u), v),
    )
    monkeypatch.setattr(
        session_config.keyring, "get_password", lambda s, u: store.get((s, u))
    )
    monkeypatch.setattr(
        session_config.keyring, "delete_password",
        lambda s, u: store.pop((s, u), None),
    )
    return store


def test_guardar_cargar_borrar(_fake_keyring):
    assert session_config.cargar_cookie() is None
    session_config.guardar_cookie("sess-abc")
    assert session_config.cargar_cookie() == "sess-abc"
    session_config.borrar_cookie()
    assert session_config.cargar_cookie() is None


def test_validar_y_guardar_ok(_fake_keyring):
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None) as v:
        session_config.validar_y_guardar("  sess-xyz  ")
    v.assert_called_once_with("sess-xyz")  # recorta espacios
    assert session_config.cargar_cookie() == "sess-xyz"


def test_validar_y_guardar_rechaza_cookie_mala(_fake_keyring):
    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with (
        mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err),
        pytest.raises(core_api.LoginError),
    ):
        session_config.validar_y_guardar("sess-mala")
    assert session_config.cargar_cookie() is None  # no se guardó


def test_validar_y_guardar_vacio(_fake_keyring):
    with pytest.raises(ValueError):
        session_config.validar_y_guardar("   ")


def test_cliente_standalone_con_cookie(_fake_keyring):
    session_config.guardar_cookie("sess-live")
    cliente = session_config.cliente_standalone()
    assert isinstance(cliente, core_api.ValidatorAPI)
    assert cliente._sesion.cookies.get("PHPSESSID") == "sess-live"
    assert cliente._session_max_idle > 10**8  # sin guard idle; el usuario gestiona la cookie


def test_cliente_standalone_sin_cookie(_fake_keyring):
    assert session_config.cliente_standalone() is None
