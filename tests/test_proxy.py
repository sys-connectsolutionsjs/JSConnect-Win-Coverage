"""Tests del proxy local (validator_app.proxy.server).

Cubre el keepalive "latido perezoso" de la Fase 2A, el fix del guard idle del
cliente-core, y los endpoints `/local/*` de la extension de Chrome (Fase 2.5d,
con FastAPI TestClient — adelanta parte de la Fase 4).
"""

import asyncio
import time
import types
from unittest import mock

import keyring
import pytest
from fastapi.testclient import TestClient

from validator_app.core import api as core_api
from validator_app.proxy import server
from validator_app.proxy.config import ProxyConfig


def _mk_proxy_api(**overrides) -> server.ProxyValidatorAPI:
    cfg = ProxyConfig(proxy_token="a" * 64, admin_key="b" * 64, **overrides)
    return server.ProxyValidatorAPI(cfg)


class FakeCore:
    """Cliente-core mínimo: cookies + validar_cobertura/score configurable."""

    def __init__(self, *, php="sess-1", resultado=None, excepcion=None):
        if php is None:
            self._sesion = None
        else:
            self._sesion = types.SimpleNamespace(cookies={"PHPSESSID": php})
        self._resultado = resultado or {"hay_cobertura": True, "cobertura": "SI"}
        self._excepcion = excepcion
        self.llamadas = 0

    def validar_cobertura(self, lat, lon):
        self.llamadas += 1
        if self._excepcion is not None:
            raise self._excepcion
        return self._resultado

    def validar_score(self, tipo, numero, lat, lon, cobertura="SI"):
        self.llamadas += 1
        if self._excepcion is not None:
            raise self._excepcion
        return {"valor": 1, "riesgo": "BAJO", "valido": True}

    def set_session_cookies(self, cookies):
        if self._sesion is None:
            self._sesion = types.SimpleNamespace(cookies={})
        self._sesion.cookies.update(cookies)


# --------------------------------------------------------------------------
# Prerrequisito: el cliente-core del proxy no debe tener el guard idle de 120s
# --------------------------------------------------------------------------

def test_proxy_client_sin_guard_idle_de_120s():
    """El proxy gestiona la frescura de sesión por su cuenta; el guard interno
    del cliente-core (auto_relogin_if_needed, _session_max_idle=120) lanzaría
    SessionError en cada hueco >120s. `_get_client()` debe neutralizarlo."""
    pa = _mk_proxy_api()
    client = pa._get_client()
    assert client._session_max_idle > 10**8

    # Simula un hueco largo: con el guard activo esto lanzaría SessionError.
    client._sesion = types.SimpleNamespace(cookies={"PHPSESSID": "x"})
    client._last_activity = time.time() - 6000
    client.auto_relogin_if_needed()  # no debe lanzar


# --------------------------------------------------------------------------
# _keepalive_tick — latido perezoso
# --------------------------------------------------------------------------

def test_keepalive_omitido_por_trafico_reciente():
    pa = _mk_proxy_api(keepalive_interval_seconds=900)
    pa._client = FakeCore()
    pa._last_activity = time.time()  # los agentes acaban de usar el proxy

    res = pa._keepalive_tick()

    assert res["accion"] == "omitido"
    assert res["motivo"] == "trafico_reciente"
    assert pa._client.llamadas == 0


def test_keepalive_omitido_sin_sesion():
    pa = _mk_proxy_api()
    pa._client = FakeCore(php=None)
    pa._last_activity = 0

    res = pa._keepalive_tick()

    assert res == {"accion": "omitido", "motivo": "sin_sesion"}


def test_keepalive_ping_viva_resetea_contadores():
    pa = _mk_proxy_api(keepalive_interval_seconds=900)
    pa._client = FakeCore()
    pa._last_activity = time.time() - 5000
    pa._keepalive_consecutive_failures = 3
    pa._session_dead_since = time.time() - 100

    res = pa._keepalive_tick()

    assert res["accion"] == "ping"
    assert res["resultado"] == "VIVA"
    assert pa._client.llamadas == 1
    assert pa._keepalive_last_ping_ok is True
    assert pa._keepalive_consecutive_failures == 0
    assert pa._session_dead_since is None
    # el ping cuenta como actividad → reinicia el reloj del latido perezoso
    assert time.time() - pa._last_activity < 5


def test_keepalive_transitorio_no_marca_muerte():
    pa = _mk_proxy_api()
    pa._client = FakeCore(excepcion=core_api.APIError("coordenada.php 503", "ERR_NETWORK"))
    pa._last_activity = time.time() - 5000

    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        res = pa._keepalive_tick()

    assert res["resultado"] == "TRANSITORIO"
    assert pa._keepalive_consecutive_failures == 1
    assert pa._keepalive_last_ping_ok is False
    assert pa._session_dead_since is None


def test_keepalive_sesion_muerta_marca_y_loguea(caplog):
    pa = _mk_proxy_api()
    pa._client = FakeCore(excepcion=core_api.APIError("HTTP 200 text/html", "ERR_NETWORK"))
    pa._last_activity = time.time() - 5000

    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with (
        mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err),
        caplog.at_level("ERROR"),
    ):
        res = pa._keepalive_tick()

    assert res["resultado"] == "SESION_MUERTA"
    assert pa._session_dead_since is not None
    assert pa._keepalive_consecutive_failures == 1
    texto = caplog.text.lower()
    assert "owner" in texto
    assert "renov" in texto


def test_keepalive_sesion_muerta_no_reescribe_session_dead_since():
    pa = _mk_proxy_api()
    pa._client = FakeCore(excepcion=core_api.APIError("boom", "ERR_NETWORK"))
    pa._last_activity = time.time() - 5000
    momento_original = time.time() - 500
    pa._session_dead_since = momento_original

    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err):
        pa._keepalive_tick()

    assert pa._session_dead_since == momento_original


def test_keepalive_indeterminado_cuando_no_se_puede_confirmar():
    pa = _mk_proxy_api()
    pa._client = FakeCore(excepcion=core_api.APIError("boom", "ERR_NETWORK"))
    pa._last_activity = time.time() - 5000

    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=OSError("red caida")):
        res = pa._keepalive_tick()

    assert res["resultado"] == "INDETERMINADO"
    assert pa._session_dead_since is None
    assert pa._keepalive_consecutive_failures == 1


def test_set_session_cookie_limpia_session_dead_since():
    pa = _mk_proxy_api()
    pa._session_dead_since = time.time() - 100
    pa._keepalive_consecutive_failures = 5

    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa.set_session_cookie("cookie-nueva")

    assert pa._session_dead_since is None
    assert pa._keepalive_consecutive_failures == 0


def test_get_status_incluye_bloque_keepalive():
    pa = _mk_proxy_api()
    status = pa.get_status()
    assert "keepalive" in status
    ka = status["keepalive"]
    assert ka["enabled"] is True
    assert ka["session_dead_since"] is None
    assert ka["consecutive_failures"] == 0


# --------------------------------------------------------------------------
# Etapa R — robustez de la deteccion de sesion muerta
# --------------------------------------------------------------------------

def test_last_activity_no_se_refresca_en_peticion_fallida():
    """El bug que cegaba la alarma: si `_last_activity` se refresca en TODA
    peticion (incluso las que fallan), 20 agentes reintentando contra una
    sesion muerta lo mantienen fresco para siempre y el keepalive nunca pincha."""
    pa = _mk_proxy_api()
    pa._client = FakeCore(excepcion=core_api.APIError("HTTP 200 text/html", "ERR_NETWORK"))
    pa._last_activity = 0

    with pytest.raises(core_api.APIError):
        pa.validar_cobertura(-12.05, -77.03)

    assert pa._last_activity == 0  # la peticion fallo -> no cuenta como actividad


def test_last_activity_se_refresca_en_peticion_exitosa():
    pa = _mk_proxy_api()
    pa._client = FakeCore()
    pa._last_activity = 0

    pa.validar_cobertura(-12.05, -77.03)

    assert time.time() - pa._last_activity < 5


def test_keepalive_pincha_aunque_haya_trafico_si_la_sesion_esta_muerta():
    """Con la sesion ya marcada muerta, las peticiones de los agentes fallan y NO
    refrescan `_last_activity`, asi que el keepalive deja de saltarse el ping."""
    pa = _mk_proxy_api(keepalive_interval_seconds=900)
    pa._client = FakeCore(excepcion=core_api.APIError("HTTP 200 text/html", "ERR_NETWORK"))
    pa._session_dead_since = time.time() - 10
    pa._last_activity = time.time() - 5000  # nadie lo refresco: las peticiones abortan antes

    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err):
        res = pa._keepalive_tick()

    assert res["accion"] == "ping"
    assert res["resultado"] == "SESION_MUERTA"


def test_marcar_sesion_muerta_es_idempotente_y_avisa_una_vez(avisos_capturados):
    pa = _mk_proxy_api()

    pa._marcar_sesion_muerta("motivo 1")
    primera = pa._session_dead_since
    pa._marcar_sesion_muerta("motivo 2")  # ya estaba muerta

    assert pa._session_dead_since == primera
    assert avisos_capturados == [("sesion_caducada", "motivo 1")]


def test_marcar_sesion_viva_avisa_solo_si_venia_de_muerta(avisos_capturados):
    pa = _mk_proxy_api()

    pa._marcar_sesion_viva()  # ya estaba viva -> nada
    assert avisos_capturados == []

    pa._session_dead_since = time.time() - 100
    pa._marcar_sesion_viva()
    assert pa._session_dead_since is None
    assert avisos_capturados == [("sesion_renovada", "")]


def test_validar_cobertura_aborta_rapido_si_sesion_muerta():
    pa = _mk_proxy_api()
    pa._client = FakeCore()
    pa._session_dead_since = time.time() - 10

    with pytest.raises(server.SesionCaducadaError):
        pa.validar_cobertura(-12.05, -77.03)

    assert pa._client.llamadas == 0  # no se tocó WinForce


def test_validar_score_aborta_rapido_si_sesion_muerta():
    pa = _mk_proxy_api()
    pa._client = FakeCore()
    pa._session_dead_since = time.time() - 10

    with pytest.raises(server.SesionCaducadaError):
        pa.validar_score("DNI", "75020496", -12.05, -77.03)

    assert pa._client.llamadas == 0


def test_load_session_cookies_marca_muerta_si_la_cookie_del_keyring_ya_no_vale(
    avisos_capturados,
):
    pa = _mk_proxy_api()
    pa._client = FakeCore(php=None)
    keyring.set_password(
        pa.config.win_keyring_service,
        pa.config.win_keyring_user + "_cookies",
        '{"PHPSESSID": "vieja"}',
    )

    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err):
        pa._load_session_cookies()  # no debe propagar

    assert pa._session_dead_since is not None
    assert avisos_capturados == [
        ("sesion_caducada", "cookie del keyring caducada al arrancar")
    ]


def test_load_session_cookies_verifica_y_marca_actividad_si_la_cookie_vale():
    pa = _mk_proxy_api()
    pa._client = FakeCore(php=None)
    keyring.set_password(
        pa.config.win_keyring_service,
        pa.config.win_keyring_user + "_cookies",
        '{"PHPSESSID": "buena"}',
    )

    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._load_session_cookies()

    assert pa._session_dead_since is None
    assert time.time() - pa._last_activity < 5


def test_load_session_cookies_no_marca_muerta_si_es_fallo_de_red(avisos_capturados):
    pa = _mk_proxy_api()
    pa._client = FakeCore(php=None)
    keyring.set_password(
        pa.config.win_keyring_service,
        pa.config.win_keyring_user + "_cookies",
        '{"PHPSESSID": "quiza-buena"}',
    )

    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=OSError("red caida")):
        pa._load_session_cookies()

    assert pa._session_dead_since is None  # indeterminado, no muerto
    assert avisos_capturados == []


# --------------------------------------------------------------------------
# Loop async
# --------------------------------------------------------------------------

def test_keepalive_loop_para_limpio_en_shutdown():
    """El loop corre al menos un tick y termina en cuanto se activa el Event
    (sin depender de tiempos de pared)."""
    pa = _mk_proxy_api()
    stop = asyncio.Event()

    def tick():
        stop.set()  # tras el primer tick, pedir parada
        return {"accion": "omitido"}

    pa._keepalive_tick = mock.Mock(side_effect=tick)

    async def run():
        task = asyncio.create_task(server._keepalive_loop(pa, 0.001, stop))
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(run())
    assert pa._keepalive_tick.call_count == 1


def test_keepalive_loop_sobrevive_a_un_tick_que_lanza():
    """Un tick que lanza no mata el loop: el 2º tick igual corre."""
    pa = _mk_proxy_api()
    stop = asyncio.Event()
    llamadas = []

    def tick():
        llamadas.append(1)
        if len(llamadas) == 1:
            raise RuntimeError("boom")
        stop.set()
        return {"accion": "omitido"}

    pa._keepalive_tick = mock.Mock(side_effect=tick)

    async def run():
        task = asyncio.create_task(server._keepalive_loop(pa, 0.001, stop))
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(run())
    assert pa._keepalive_tick.call_count == 2  # siguió pese al error del 1º


# --------------------------------------------------------------------------
# Endpoints /local/* de la extensión de Chrome (Fase 2.5d)
# --------------------------------------------------------------------------

@pytest.fixture
def client_local(monkeypatch):
    """TestClient con IP de cliente 127.0.0.1 y get_proxy_api mockeado."""
    fake = mock.Mock()
    monkeypatch.setattr(server, "get_proxy_api", lambda: fake)
    return TestClient(server.app, client=("127.0.0.1", 51000)), fake


def test_local_renovar_desde_localhost(client_local):
    client, fake = client_local
    r = client.post("/local/renovar", json={"php_sessid": "cookie-nav"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    fake.set_session_cookie.assert_called_once_with("cookie-nav")


def test_local_renovar_rechaza_ip_externa(monkeypatch):
    fake = mock.Mock()
    monkeypatch.setattr(server, "get_proxy_api", lambda: fake)
    client = TestClient(server.app, client=("10.0.0.9", 1))
    r = client.post("/local/renovar", json={"php_sessid": "x"})
    assert r.status_code == 403
    fake.set_session_cookie.assert_not_called()


def test_local_renovar_cookie_invalida_401(client_local):
    client, fake = client_local
    fake.set_session_cookie.side_effect = core_api.LoginError("sesion muerta", "ERR_LOGIN_SESSION")
    r = client.post("/local/renovar", json={"php_sessid": "x"})
    assert r.status_code == 401


def test_local_estado(client_local):
    client, fake = client_local
    fake.get_status.return_value = {
        "session_alive": True,
        "keepalive": {"session_dead_since": None},
    }
    r = client.get("/local/estado")
    assert r.status_code == 200
    assert r.json() == {"session_alive": True, "session_dead_since": None}


def test_local_estado_rechaza_ip_externa():
    client = TestClient(server.app, client=("192.168.1.5", 1))
    assert client.get("/local/estado").status_code == 403


# --------------------------------------------------------------------------
# Capa FastAPI: /api/*, /health, /admin/* + auth + exception handlers (Fase 4)
# --------------------------------------------------------------------------

_TOKEN = "t" * 64
_ADMIN = "k" * 64
_COBERTURA = {
    "hay_cobertura": True, "cobertura": "SI", "tipo": "HORIZONTAL",
    "id_celda": "8764", "comment": "",
}
_SCORE = {
    "valor": 423, "riesgo": "MUY ALTO", "conclusion": "NO APTO",
    "deuda_total": "0", "nombre": "X Y", "documento": "75020496", "valido": True,
}
_STATUS = {
    "logged_in": True, "session_age": 10, "creds_updated": None,
    "proxy_version": "dev", "session_alive": True,
    "keepalive": {
        "enabled": True, "last_ping_at": None, "last_ping_ok": None,
        "consecutive_failures": 0, "session_dead_since": None,
    },
}


@pytest.fixture
def client(monkeypatch):
    """TestClient con config conocida (token/admin_key) y proxy mockeado.
    IP del cliente en 10.0.0.0/8 (permitida)."""
    cfg = ProxyConfig(
        proxy_token=_TOKEN, admin_key=_ADMIN,
        allowed_networks=["127.0.0.0/8", "10.0.0.0/8"],
    )
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    fake = mock.Mock()
    fake.get_status.return_value = _STATUS
    monkeypatch.setattr(server, "get_proxy_api", lambda: fake)
    return TestClient(server.app, client=("10.0.0.5", 5000)), fake


def test_health_publico(client):
    tc, _fake = client
    r = tc.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["session_alive"] is True


def test_api_cobertura_ok(client):
    tc, fake = client
    fake.validar_cobertura.return_value = _COBERTURA
    r = tc.post(
        "/api/cobertura", json={"lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 200
    assert r.json()["hay_cobertura"] is True
    fake.validar_cobertura.assert_called_once_with(-12.05, -77.03)


def test_api_cobertura_token_malo_401(client):
    tc, fake = client
    r = tc.post(
        "/api/cobertura", json={"lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": "malo"},
    )
    assert r.status_code == 401
    fake.validar_cobertura.assert_not_called()


def test_api_cobertura_ip_no_permitida_403(client, monkeypatch):
    tc_externo = TestClient(server.app, client=("8.8.8.8", 1))
    r = tc_externo.post(
        "/api/cobertura", json={"lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 403


def test_api_score_ok(client):
    tc, fake = client
    fake.validar_score.return_value = _SCORE
    r = tc.post(
        "/api/score",
        json={"tipo_doc": "DNI", "num_doc": "75020496", "lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 200
    assert r.json()["valor"] == 423


def test_api_score_tolera_deuda_total_int(client):
    """Regresion (2026-09-09, hallado en la puesta en marcha end-to-end):
    WinForce manda deuda_total = 0 (int) cuando no hay deuda; ScoreResponse
    declaraba str | None y reventaba con HTTP 500 pydantic ValidationError."""
    tc, fake = client
    fake.validar_score.return_value = {**_SCORE, "deuda_total": 0}
    r = tc.post(
        "/api/score",
        json={"tipo_doc": "DNI", "num_doc": "75020496", "lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 200
    assert r.json()["deuda_total"] == "0"


def test_api_score_documento_invalido_422(client):
    tc, _fake = client
    r = tc.post(
        "/api/score",
        json={"tipo_doc": "PASAPORTE", "num_doc": "1", "lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 422


def test_admin_config_requiere_key(client):
    tc, _fake = client
    assert tc.get("/admin/config").status_code == 401
    r = tc.get("/admin/config", headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 200
    assert r.json()["token"] == _TOKEN


def test_admin_login_inyecta_cookie(client):
    tc, fake = client
    r = tc.post("/admin/login", json={"php_sessid": "abc"}, headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 200
    fake.set_session_cookie.assert_called_once_with("abc")


def test_admin_rotar_inyecta_cookie(client):
    tc, fake = client
    r = tc.post("/admin/rotar", json={"php_sessid": "xyz"}, headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 200
    fake.set_session_cookie.assert_called_once_with("xyz")


def test_admin_status_ok(client):
    tc, _fake = client
    r = tc.get("/admin/status", headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 200
    assert r.json()["keepalive"]["enabled"] is True


def test_login_error_da_401(client):
    tc, fake = client
    fake.validar_cobertura.side_effect = core_api.LoginError("expirada", "ERR_LOGIN_SESSION")
    r = tc.post(
        "/api/cobertura", json={"lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 401


def test_score_error_da_502(client):
    tc, fake = client
    fake.validar_score.side_effect = core_api.ScoreError("reporte roto")
    r = tc.post(
        "/api/score",
        json={"tipo_doc": "DNI", "num_doc": "75020496", "lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 502


def test_api_error_generico_da_502(client):
    tc, fake = client
    fake.validar_cobertura.side_effect = core_api.APIError("winforce raro")
    r = tc.post(
        "/api/cobertura", json={"lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 502


def test_sesion_caducada_da_503_con_retry_after(client):
    tc, fake = client
    fake.validar_cobertura.side_effect = server.SesionCaducadaError()
    r = tc.post(
        "/api/cobertura", json={"lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 503
    assert r.headers["Retry-After"] == "120"
    body = r.json()
    assert body["codigo"] == "ERR_SESION_CADUCADA"
    assert body["owner_avisado"] is True


def test_ip_in_allowed_networks():
    redes = ["10.0.0.0/8", "192.168.0.0/16"]
    assert server._ip_in_allowed_networks("10.1.2.3", redes) is True
    assert server._ip_in_allowed_networks("192.168.5.5", redes) is True
    assert server._ip_in_allowed_networks("8.8.8.8", redes) is False
    assert server._ip_in_allowed_networks("no-es-ip", redes) is False
