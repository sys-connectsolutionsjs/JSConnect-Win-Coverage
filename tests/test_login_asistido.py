"""Tests del login asistido (Fase 2.5).

La captura por navegador (Playwright) es interactiva y no se testea en CI; aquí
se cubre la lógica pura (`_php_sessid_de_cookies`, manejo de "sin playwright") y
el dispatch de `rotate_creds` (asistido vs `--manual`, con las piezas de red y
navegador monkeypatcheadas).
"""

import types
from unittest import mock

import httpx
import pytest

from validator_app.proxy import login_asistido, rotate_creds

_FAKE_CFG = types.SimpleNamespace(
    proxy_url="http://0.0.0.0:8080",
    proxy_local_url="http://127.0.0.1:8080",
    admin_key="k" * 64,
    win_keyring_service="JSWinProxy",
    win_keyring_user="credentials",
)


# --------------------------------------------------------------------------
# _php_sessid_de_cookies
# --------------------------------------------------------------------------

def test_php_sessid_de_cookies_encuentra():
    cookies = [
        {"name": "otra", "value": "x", "domain": "appwinforce.win.pe"},
        {"name": "PHPSESSID", "value": "abc123", "domain": ".appwinforce.win.pe"},
    ]
    assert login_asistido._php_sessid_de_cookies(cookies) == "abc123"


def test_php_sessid_de_cookies_ignora_otros_dominios():
    cookies = [
        {"name": "PHPSESSID", "value": "de-microsoft", "domain": "login.microsoftonline.com"},
    ]
    assert login_asistido._php_sessid_de_cookies(cookies) is None


def test_php_sessid_de_cookies_vacio():
    assert login_asistido._php_sessid_de_cookies([]) is None
    assert login_asistido._php_sessid_de_cookies(
        [{"name": "PHPSESSID", "value": "", "domain": "appwinforce.win.pe"}]
    ) is None


def test_capturar_sin_playwright_da_mensaje_util():
    with (
        mock.patch.object(
            login_asistido, "_import_sync_playwright", side_effect=ImportError("no module")
        ),
        pytest.raises(login_asistido.LoginAsistidoError) as exc,
    ):
        login_asistido.capturar_php_sessid_asistido()
    assert "--manual" in str(exc.value)


# --------------------------------------------------------------------------
# push_session_cookie — empuja la cookie al proxy por HTTP (Etapa 0.5)
#
# rotate_creds.py corre como el OWNER; el servicio del proxy corre como
# LocalSystem y tiene su propio Windows Keyring. Escribir la cookie
# directo al keyring de este proceso (como hacia antes) nunca la veria el
# servicio. Por eso se empuja por HTTP: /local/renovar si el proxy esta
# vivo en esta PC, /admin/rotar si no.
# --------------------------------------------------------------------------

def _mock_post(monkeypatch, respuestas):
    """Reemplaza httpx.post por un fake que devuelve `respuestas` en orden
    (una `httpx.Response` o una excepción a lanzar, por llamada)."""
    it = iter(respuestas)
    llamadas = []

    def fake_post(url, **kwargs):
        llamadas.append((url, kwargs))
        resultado = next(it)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    monkeypatch.setattr(httpx, "post", fake_post)
    return llamadas


def test_push_session_cookie_via_local_renovar(monkeypatch):
    monkeypatch.setattr(rotate_creds, "get_config", lambda: _FAKE_CFG)
    llamadas = _mock_post(monkeypatch, [httpx.Response(200, json={"ok": True})])

    ok, msg = rotate_creds.push_session_cookie("cookie-x")

    assert ok is True
    assert "local/renovar" in msg
    assert len(llamadas) == 1
    assert llamadas[0][0] == "http://127.0.0.1:8080/local/renovar"
    assert llamadas[0][1]["json"] == {"php_sessid": "cookie-x"}


def test_push_session_cookie_cae_a_admin_rotar_si_local_no_conecta(monkeypatch):
    monkeypatch.setattr(rotate_creds, "get_config", lambda: _FAKE_CFG)
    llamadas = _mock_post(
        monkeypatch,
        [
            httpx.ConnectError("proxy no esta corriendo en esta PC"),
            httpx.Response(200, json={"ok": True}),
        ],
    )

    ok, msg = rotate_creds.push_session_cookie("cookie-x")

    assert ok is True
    assert "admin/rotar" in msg
    assert len(llamadas) == 2
    assert llamadas[1][0] == "http://127.0.0.1:8080/admin/rotar"
    assert llamadas[1][1]["headers"] == {"X-Admin-Key": _FAKE_CFG.admin_key}


def test_push_session_cookie_no_reintenta_si_local_renovar_rechaza(monkeypatch):
    """Un 401 de /local/renovar significa 'te alcancé, la cookie es mala' -- muy
    distinto de no poder conectar. Reintentar por /admin/rotar con la misma
    cookie mala no serviria de nada."""
    monkeypatch.setattr(rotate_creds, "get_config", lambda: _FAKE_CFG)
    llamadas = _mock_post(
        monkeypatch, [httpx.Response(401, text="sesion no activa")]
    )

    ok, msg = rotate_creds.push_session_cookie("cookie-mala")

    assert ok is False
    assert "local/renovar" in msg and "401" in msg
    assert len(llamadas) == 1  # sin fallback


def test_push_session_cookie_falla_si_nada_responde(monkeypatch):
    monkeypatch.setattr(rotate_creds, "get_config", lambda: _FAKE_CFG)
    _mock_post(
        monkeypatch,
        [
            httpx.ConnectError("caido"),
            httpx.ConnectError("caido tambien"),
        ],
    )

    ok, msg = rotate_creds.push_session_cookie("cookie-x")

    assert ok is False
    assert "no se pudo contactar" in msg.lower()


def _config_ilegible():
    raise PermissionError(13, "Acceso denegado", "config.yaml")


def test_push_session_cookie_no_lee_config_yaml_si_local_renovar_responde(monkeypatch):
    """El icono del Escritorio corre SIN elevar y config.yaml tiene ACL de
    SYSTEM+Administradores: antes get_config() reventaba con PermissionError
    antes de enviar nada (2026-10-02)."""
    monkeypatch.setattr(rotate_creds, "get_config", _config_ilegible)
    monkeypatch.setattr(rotate_creds, "proxy_local_url_seguro", lambda: "http://127.0.0.1:8080")
    llamadas = _mock_post(monkeypatch, [httpx.Response(200, json={"ok": True})])

    ok, _msg = rotate_creds.push_session_cookie("cookie-x")

    assert ok is True
    assert llamadas[0][0] == "http://127.0.0.1:8080/local/renovar"


def test_push_session_cookie_sin_config_y_proxy_caido_da_error_claro(monkeypatch):
    monkeypatch.setattr(rotate_creds, "get_config", _config_ilegible)
    monkeypatch.setattr(rotate_creds, "proxy_local_url_seguro", lambda: "http://127.0.0.1:8080")
    _mock_post(monkeypatch, [httpx.ConnectError("caido")])

    ok, msg = rotate_creds.push_session_cookie("cookie-x")

    assert ok is False
    assert "JSWinProxy" in msg


def test_verificar_proxy_usa_local_estado_sin_admin_key(monkeypatch):
    monkeypatch.setattr(rotate_creds, "get_config", _config_ilegible)
    monkeypatch.setattr(rotate_creds, "proxy_local_url_seguro", lambda: "http://127.0.0.1:8080")
    pedidas = []

    def fake_get(url, **kwargs):
        pedidas.append((url, kwargs))
        return httpx.Response(200, json={"session_alive": True})

    monkeypatch.setattr(httpx, "get", fake_get)

    rotate_creds._verificar_proxy()

    assert pedidas == [("http://127.0.0.1:8080/local/estado", {"timeout": 5})]


# --------------------------------------------------------------------------
# rotate_creds — dispatch
# --------------------------------------------------------------------------

@pytest.fixture
def _stub_tail():
    """Neutraliza la cola compartida (validar + push al proxy + verificar proxy)."""
    with (
        mock.patch.object(
            rotate_creds, "push_session_cookie", return_value=(True, "ok")
        ) as save,
        mock.patch.object(rotate_creds, "_verificar_proxy", return_value=None),
        mock.patch.object(rotate_creds, "get_config", return_value=_FAKE_CFG),
        mock.patch.object(rotate_creds, "_avisar") as avisar,
    ):
        yield {"save": save, "avisar": avisar}


def test_manual_usa_input_y_no_navegador(_stub_tail):
    with (
        mock.patch.object(
            rotate_creds, "extract_php_sessid_from_input", return_value="cookie-manual"
        ),
        mock.patch.object(rotate_creds, "validate_session_cookie", return_value=(True, "ok")),
        mock.patch.object(rotate_creds, "capturar_php_sessid_asistido") as cap,
    ):
        rc = rotate_creds.main(["--manual"])
    assert rc == 0
    cap.assert_not_called()
    _stub_tail["save"].assert_called_once_with("cookie-manual")


def test_asistido_captura_valida_y_guarda(_stub_tail):
    with (
        mock.patch.object(rotate_creds, "capturar_php_sessid_asistido", return_value="cookie-nav"),
        mock.patch.object(rotate_creds, "validate_session_cookie", return_value=(True, "ok")),
    ):
        rc = rotate_creds.main([])
    assert rc == 0
    _stub_tail["save"].assert_called_once_with("cookie-nav")
    ok_arg = _stub_tail["avisar"].call_args[0][0]
    assert ok_arg is True


def test_asistido_fallo_captura_avisa_y_no_guarda(_stub_tail):
    with mock.patch.object(
        rotate_creds,
        "capturar_php_sessid_asistido",
        side_effect=login_asistido.LoginAsistidoError("no se capturo"),
    ):
        rc = rotate_creds.main([])
    assert rc == 1
    _stub_tail["save"].assert_not_called()
    assert _stub_tail["avisar"].call_args[0][0] is False


def test_asistido_cookie_invalida_avisa_y_no_guarda(_stub_tail):
    with (
        mock.patch.object(rotate_creds, "capturar_php_sessid_asistido", return_value="cookie-mala"),
        mock.patch.object(
            rotate_creds, "validate_session_cookie", return_value=(False, "sesion expirada")
        ),
    ):
        rc = rotate_creds.main([])
    assert rc == 1
    _stub_tail["save"].assert_not_called()
    assert _stub_tail["avisar"].call_args[0][0] is False


def test_fresh_se_propaga_a_captura(_stub_tail):
    with (
        mock.patch.object(rotate_creds, "capturar_php_sessid_asistido", return_value="c") as cap,
        mock.patch.object(rotate_creds, "validate_session_cookie", return_value=(True, "ok")),
    ):
        rotate_creds.main(["--fresh"])
    assert cap.call_args.kwargs.get("fresh") is True


def test_avisar_sin_tkinter_no_revienta(capsys):
    with mock.patch.dict("sys.modules", {"tkinter": None}):
        rotate_creds._avisar(True, "t", "m")  # no debe lanzar
    assert "t" in capsys.readouterr().out


# --------------------------------------------------------------------------
# --preview: ver la ventana sin guardar ni tocar config del proxy
# --------------------------------------------------------------------------

def test_preview_no_guarda_ni_verifica():
    with (
        mock.patch.object(rotate_creds, "capturar_php_sessid_asistido", return_value="cookie-x"),
        mock.patch.object(rotate_creds, "push_session_cookie") as save,
        mock.patch.object(rotate_creds, "_verificar_proxy") as verif,
        mock.patch.object(rotate_creds, "_avisar") as avisar,
    ):
        rc = rotate_creds.main(["--preview"])
    assert rc == 0
    save.assert_not_called()
    verif.assert_not_called()
    assert avisar.call_args[0][0] is True


def test_preview_gana_sobre_manual():
    with (
        mock.patch.object(rotate_creds, "capturar_php_sessid_asistido", return_value="c") as cap,
        mock.patch.object(rotate_creds, "extract_php_sessid_from_input") as inp,
        mock.patch.object(rotate_creds, "push_session_cookie"),
        mock.patch.object(rotate_creds, "_avisar"),
    ):
        rotate_creds.main(["--preview", "--manual"])
    cap.assert_called_once()
    inp.assert_not_called()


def test_preview_fallo_captura_avisa():
    with (
        mock.patch.object(
            rotate_creds,
            "capturar_php_sessid_asistido",
            side_effect=login_asistido.LoginAsistidoError("no se capturo"),
        ),
        mock.patch.object(rotate_creds, "push_session_cookie") as save,
        mock.patch.object(rotate_creds, "_avisar") as avisar,
    ):
        rc = rotate_creds.main(["--preview"])
    assert rc == 1
    save.assert_not_called()
    assert avisar.call_args[0][0] is False


# --------------------------------------------------------------------------
# _lanzar_navegador: Chrome real (autofill) con fallback a Chromium
# --------------------------------------------------------------------------

def test_lanzar_navegador_prefiere_chrome():
    ctx = object()
    p = mock.Mock()
    p.chromium.launch_persistent_context.return_value = ctx
    assert login_asistido._lanzar_navegador(p) is ctx
    assert p.chromium.launch_persistent_context.call_args.kwargs.get("channel") == "chrome"


def test_lanzar_navegador_fallback_a_chromium():
    ctx = object()
    p = mock.Mock()
    p.chromium.launch_persistent_context.side_effect = [RuntimeError("no chrome"), ctx]
    assert login_asistido._lanzar_navegador(p) is ctx
    calls = p.chromium.launch_persistent_context.call_args_list
    assert calls[0].kwargs.get("channel") == "chrome"
    assert "channel" not in calls[1].kwargs


# --------------------------------------------------------------------------
# --guardar-login (credencial del autologin, plan Proxy 24/7)
# --------------------------------------------------------------------------

def test_push_credencial_login_envia_con_admin_key():
    resp = mock.Mock(status_code=200, text='{"ok": true}')
    with (
        mock.patch.object(rotate_creds, "get_config", return_value=_FAKE_CFG),
        mock.patch.object(httpx, "post", return_value=resp) as post,
    ):
        ok, msg = rotate_creds.push_credencial_login("proxy@empresa.pe", "secreta")
    assert ok is True
    url = post.call_args.args[0]
    assert url == "http://127.0.0.1:8080/local/credenciales"
    assert post.call_args.kwargs["headers"] == {"X-Admin-Key": "k" * 64}
    assert post.call_args.kwargs["json"] == {"usuario": "proxy@empresa.pe", "password": "secreta"}
    assert "secreta" not in msg


def test_push_credencial_login_sin_permiso_pide_consola_de_administrador():
    with mock.patch.object(rotate_creds, "get_config", side_effect=PermissionError("denegado")):
        ok, msg = rotate_creds.push_credencial_login("u", "p")
    assert ok is False
    assert "Administrador" in msg


def test_push_credencial_login_proxy_apagado():
    with (
        mock.patch.object(rotate_creds, "get_config", return_value=_FAKE_CFG),
        mock.patch.object(httpx, "post", side_effect=httpx.ConnectError("x")),
    ):
        ok, msg = rotate_creds.push_credencial_login("u", "p")
    assert ok is False
    assert "JSWinProxy" in msg


def test_push_credencial_login_http_error():
    resp = mock.Mock(status_code=401, text="Admin key invalida")
    with (
        mock.patch.object(rotate_creds, "get_config", return_value=_FAKE_CFG),
        mock.patch.object(httpx, "post", return_value=resp),
    ):
        ok, msg = rotate_creds.push_credencial_login("u", "p")
    assert ok is False
    assert "401" in msg


def test_main_guardar_login_despacha(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _m: "proxy@empresa.pe")
    monkeypatch.setattr(rotate_creds.getpass, "getpass", lambda _m: "secreta")
    with mock.patch.object(
        rotate_creds, "push_credencial_login", return_value=(True, "ok")
    ) as push:
        assert rotate_creds.main(["--guardar-login"]) == 0
    push.assert_called_once_with("proxy@empresa.pe", "secreta")


def test_main_guardar_login_vacio_no_envia(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _m: "")
    monkeypatch.setattr(rotate_creds.getpass, "getpass", lambda _m: "")
    with mock.patch.object(rotate_creds, "push_credencial_login") as push:
        assert rotate_creds.main(["--guardar-login"]) == 1
    push.assert_not_called()


# --------------------------------------------------------------------------
# Navegadores compartidos con el servicio (plan Proxy 24/7)
# --------------------------------------------------------------------------

def test_usar_navegadores_compartidos_fija_la_ruta_si_existe(monkeypatch, tmp_path):
    monkeypatch.setattr(login_asistido, "NAVEGADORES_DIR", tmp_path)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    login_asistido.usar_navegadores_compartidos()
    import os

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path)


def test_usar_navegadores_compartidos_no_pisa_una_ruta_ya_definida(monkeypatch, tmp_path):
    monkeypatch.setattr(login_asistido, "NAVEGADORES_DIR", tmp_path)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "C:/otra")
    login_asistido.usar_navegadores_compartidos()
    import os

    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == "C:/otra"


def test_usar_navegadores_compartidos_sin_carpeta_no_toca_nada(monkeypatch, tmp_path):
    monkeypatch.setattr(login_asistido, "NAVEGADORES_DIR", tmp_path / "no-existe")
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    login_asistido.usar_navegadores_compartidos()
    import os

    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ


def test_import_de_playwright_usa_los_navegadores_compartidos(monkeypatch):
    from validator_app.proxy import autologin

    llamadas = []
    monkeypatch.setattr(
        login_asistido, "usar_navegadores_compartidos", lambda: llamadas.append("asistido")
    )
    with mock.patch.dict("sys.modules", {"playwright.sync_api": types.SimpleNamespace(
        sync_playwright="sp"
    )}):
        assert login_asistido._import_sync_playwright() == "sp"
        assert autologin._import_sync_playwright() == "sp"
    assert llamadas == ["asistido", "asistido"]


def test_push_credencial_login_con_admin_key_explicita_no_lee_config():
    resp = mock.Mock(status_code=200, text='{"ok": true}')
    with (
        mock.patch.object(rotate_creds, "get_config", side_effect=AssertionError("no")),
        mock.patch.object(httpx, "post", return_value=resp) as post,
    ):
        ok, _msg = rotate_creds.push_credencial_login(
            "u@x.pe", "p", admin_key="z" * 64, url="http://127.0.0.1:9000"
        )
    assert ok is True
    assert post.call_args.args[0] == "http://127.0.0.1:9000/local/credenciales"
    assert post.call_args.kwargs["headers"] == {"X-Admin-Key": "z" * 64}


def test_push_freno_autologin_envia_perfil_y_minutos_con_admin_key():
    resp = mock.Mock(status_code=200, text='{"ok": true}')
    with mock.patch.object(httpx, "post", return_value=resp) as post:
        ok, msg = rotate_creds.push_freno_autologin(
            "personalizado", [2, 3, 4, 7], admin_key="z" * 64, url="http://127.0.0.1:8080"
        )
    assert ok is True
    assert post.call_args.args[0] == "http://127.0.0.1:8080/local/freno"
    assert post.call_args.kwargs["json"] == {"perfil": "personalizado", "minutos": [2, 3, 4, 7]}
    assert post.call_args.kwargs["headers"] == {"X-Admin-Key": "z" * 64}
    assert "Frenado" in msg


def test_push_freno_autologin_422_devuelve_el_motivo():
    resp = mock.Mock(
        status_code=422, text='{"detail":"La espera antes del 2.o intento va de 1 a 5 min."}'
    )
    with mock.patch.object(httpx, "post", return_value=resp):
        ok, msg = rotate_creds.push_freno_autologin("personalizado", [9, 9, 9, 9], "z" * 64, "u")
    assert ok is False
    assert "1 a 5" in msg
