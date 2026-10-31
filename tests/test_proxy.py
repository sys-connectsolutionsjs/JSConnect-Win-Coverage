"""Tests del proxy local (validator_app.proxy.server).

Cubre el keepalive "latido perezoso" de la Fase 2A, el fix del guard idle del
cliente-core, y los endpoints `/local/*` de la extension de Chrome (Fase 2.5d,
con FastAPI TestClient — adelanta parte de la Fase 4).
"""

import asyncio
import json
import re
import threading
import time
import types
from pathlib import Path
from unittest import mock

import keyring
import pytest
from fastapi.testclient import TestClient

from validator_app.core import api as core_api
from validator_app.proxy import autologin, server
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

    def get_session_cookies(self):
        return dict(self._sesion.cookies) if self._sesion else {}


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


class _FakeFn:
    """Función de DLL falsa: admite restype/argtypes y registra las llamadas."""

    def __init__(self, retorno):
        self.retorno = retorno
        self.llamadas = []

    def __call__(self, *args):
        self.llamadas.append(args)
        return self.retorno


@pytest.mark.parametrize(("tipo", "tipo_win"), [("ERROR", 1), ("INFORMATION", 4)])
def test_aviso_event_log_usa_reportevent_con_origen_jswinproxy(monkeypatch, tipo, tipo_win):
    """Regresión 2026-10-02: con `eventcreate` el evento nunca se escribía (rechaza
    orígenes registrados con New-EventLog) y la tarea del popup no se disparaba.
    Ahora va por ReportEventW, que acepta cualquier origen registrado."""
    import ctypes

    dll = types.SimpleNamespace(
        RegisterEventSourceW=_FakeFn(1234),
        ReportEventW=_FakeFn(1),
        DeregisterEventSource=_FakeFn(1),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: dll, raising=False)

    server.ProxyValidatorAPI._aviso_event_log(101, tipo, "sesion caducada")

    assert dll.RegisterEventSourceW.llamadas == [(None, "JSWinProxy")]
    (args,) = dll.ReportEventW.llamadas
    assert args[0] == 1234
    assert args[1] == tipo_win
    assert args[3] == 101
    assert args[7][0] == "sesion caducada"
    assert dll.DeregisterEventSource.llamadas == [(1234,)]


def test_aviso_event_log_falla_si_reportevent_falla(monkeypatch):
    """Si ReportEventW falla, se lanza (el caller lo suprime) y el handle se libera."""
    import ctypes

    dll = types.SimpleNamespace(
        RegisterEventSourceW=_FakeFn(1234),
        ReportEventW=_FakeFn(0),
        DeregisterEventSource=_FakeFn(1),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: dll, raising=False)

    with pytest.raises(OSError):
        server.ProxyValidatorAPI._aviso_event_log(101, "ERROR", "x")
    assert dll.DeregisterEventSource.llamadas == [(1234,)]


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
# Reconfirmacion antes de declarar muerte (falso positivo real 2026-09-29:
# `/health` marco MUERTA una sesion viva tras un solo ReadTimeout de WinForce)
# --------------------------------------------------------------------------

def test_confirmar_muerte_viva_si_el_segundo_intento_pasa():
    pa = _mk_proxy_api()
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        estado, detalle = pa._confirmar_muerte("sess-1")
    assert estado == "VIVA"
    assert detalle == ""


def test_confirmar_muerte_muerta_si_el_segundo_intento_tambien_falla():
    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    pa = _mk_proxy_api()
    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err):
        estado, detalle = pa._confirmar_muerte("sess-1")
    assert estado == "MUERTA"
    assert "sesion no activa" in detalle


def test_confirmar_muerte_indeterminado_si_el_segundo_intento_es_error_de_red():
    pa = _mk_proxy_api()
    with mock.patch.object(
        core_api, "validar_cookie_sesion", side_effect=OSError("red caida")
    ):
        estado, detalle = pa._confirmar_muerte("sess-1")
    assert estado == "INDETERMINADO"
    assert "red caida" in detalle


def test_is_session_alive_no_marca_muerta_con_un_solo_fallo_puntual():
    """Regresion del falso positivo real: un timeout aislado de WinForce en
    `_verificar_sesion_activa` no debe bastar para declarar la sesion muerta
    si, reconfirmando, la cookie sigue activa."""
    pa = _mk_proxy_api()
    err = core_api.LoginError("HTTP 200 text/html", "ERR_LOGIN_SESSION")
    with mock.patch.object(
        core_api, "validar_cookie_sesion", side_effect=[err, None]
    ):
        alive = pa._is_session_alive("sess-1")

    assert alive is True
    assert pa._session_dead_since is None


def test_is_session_alive_marca_muerta_si_el_segundo_intento_confirma(avisos_capturados):
    pa = _mk_proxy_api()
    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err):
        alive = pa._is_session_alive("sess-1")

    assert alive is False
    assert pa._session_dead_since is not None
    assert avisos_capturados == [
        ("sesion_caducada", "verificación de estado (/health · /admin/status)")
    ]


def test_is_session_alive_indeterminado_no_marca_ni_cachea():
    pa = _mk_proxy_api()
    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with mock.patch.object(
        core_api, "validar_cookie_sesion", side_effect=[err, OSError("red caida")]
    ):
        alive = pa._is_session_alive("sess-1")

    assert alive is False
    assert pa._session_dead_since is None
    assert pa._session_alive_checked_at == 0.0  # no se cacheo


# --------------------------------------------------------------------------
# Bitacora persistente de eventos de sesion (logs/sesion_eventos.jsonl)
# --------------------------------------------------------------------------

def test_set_session_cookie_registra_evento_renovada():
    pa = _mk_proxy_api()
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa.set_session_cookie("cookie-nueva", origen="extension")

    eventos = server._leer_eventos_sesion()
    assert len(eventos) == 1
    assert eventos[0]["evento"] == "renovada"
    assert eventos[0]["origen"] == "extension"
    assert eventos[0]["cookie_id"] == server._cookie_id("cookie-nueva")
    # cookie_id no permite recuperar la cookie original
    assert "cookie-nueva" not in json.dumps(eventos[0])


def test_marcar_sesion_muerta_registra_evento_con_edad_de_la_cookie():
    """La edad de la cookie al morir se calcula releyendo la bitacora (no un
    estado en memoria): asi sobrevive a un reinicio del proceso proxy."""
    pa = _mk_proxy_api()
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa.set_session_cookie("cookie-x", origen="admin_rotar")

    # "reinicio": instancia nueva, misma bitacora en disco (EVENTOS_LOG_PATH
    # esta aislado por test, no por instancia de ProxyValidatorAPI).
    pa2 = _mk_proxy_api()
    pa2._marcar_sesion_muerta("motivo de prueba", "detalle de prueba", "cookie-x")

    eventos = server._leer_eventos_sesion()
    assert [e["evento"] for e in eventos] == ["renovada", "muerta"]
    muerta = eventos[1]
    assert muerta["origen"] == "motivo de prueba"
    assert muerta["detalle"] == "detalle de prueba"
    assert muerta["cookie_id"] == server._cookie_id("cookie-x")
    assert muerta["edad_cookie_s"] is not None
    assert muerta["edad_cookie_s"] >= 0


def test_marcar_sesion_muerta_sin_cookie_no_calcula_edad():
    pa = _mk_proxy_api()
    pa._marcar_sesion_muerta("motivo sin cookie")

    eventos = server._leer_eventos_sesion()
    assert eventos[0]["cookie_id"] is None
    assert eventos[0]["edad_cookie_s"] is None


def test_bitacora_es_best_effort_no_tumba_si_no_se_puede_escribir(monkeypatch):
    """Un fallo de disco al escribir la bitacora no debe propagar: es
    diagnostico, no una funcion critica."""
    monkeypatch.setattr(
        server, "EVENTOS_LOG_PATH", Path("Z:/ruta-que-no-existe/eventos.jsonl")
    )
    pa = _mk_proxy_api()
    pa._marcar_sesion_muerta("motivo")  # no debe lanzar


def test_admin_status_incluye_eventos_de_sesion(admin_client):
    tc, fake = admin_client
    fake.get_status.return_value = _STATUS
    server._registrar_evento_sesion("renovada", "extension", "cookie-real")

    r = tc.get("/admin/status", headers={"X-Admin-Key": _ADMIN})

    assert r.status_code == 200
    eventos = r.json()["sesion_eventos"]
    assert len(eventos) == 1
    assert eventos[0]["evento"] == "renovada"
    assert eventos[0]["cookie_id"] == server._cookie_id("cookie-real")


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
    fake.set_session_cookie.assert_called_once_with("cookie-nav", origen="extension")


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


@pytest.fixture
def admin_client(monkeypatch):
    """TestClient desde 127.0.0.1: /admin/* solo acepta la PC del proxy."""
    cfg = ProxyConfig(
        proxy_token=_TOKEN, admin_key=_ADMIN,
        allowed_networks=["127.0.0.0/8", "10.0.0.0/8"],
    )
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    fake = mock.Mock()
    fake.get_status.return_value = _STATUS
    monkeypatch.setattr(server, "get_proxy_api", lambda: fake)
    return TestClient(server.app, client=("127.0.0.1", 5000)), fake


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


def test_api_score_sin_coordenadas_pasa_none(client):
    """Validar solo por documento (sin coordenadas, 2026-09-25): lat/lon en
    null deben llegar como None a ProxyValidatorAPI.validar_score, no
    rechazarse con 422 por los limites geograficos de CoberturaRequest/ScoreRequest."""
    tc, fake = client
    fake.validar_score.return_value = _SCORE
    r = tc.post(
        "/api/score",
        json={"tipo_doc": "DNI", "num_doc": "75020496", "lat": None, "lon": None},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 200
    assert r.json()["valor"] == 423
    _args, kwargs = fake.validar_score.call_args
    assert kwargs["lat"] is None
    assert kwargs["lon"] is None


def test_api_score_documento_invalido_422(client):
    tc, _fake = client
    r = tc.post(
        "/api/score",
        json={"tipo_doc": "PASAPORTE", "num_doc": "1", "lat": -12.05, "lon": -77.03},
        headers={"X-Proxy-Token": _TOKEN},
    )
    assert r.status_code == 422


def test_admin_config_requiere_key(admin_client):
    tc, _fake = admin_client
    assert tc.get("/admin/config").status_code == 401
    r = tc.get("/admin/config", headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 200
    assert r.json()["token"] == _TOKEN


def test_admin_config_rechaza_ip_no_local_403(client):
    """El admin key expone el proxy_token via /admin/config: nunca viaja por LAN,
    aunque la IP este en allowed_networks (eso solo aplica a /api/*)."""
    tc, _fake = client  # IP 10.0.0.5, dentro de allowed_networks pero no loopback
    r = tc.get("/admin/config", headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 403


def test_admin_login_inyecta_cookie(admin_client):
    tc, fake = admin_client
    r = tc.post("/admin/login", json={"php_sessid": "abc"}, headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 200
    fake.set_session_cookie.assert_called_once_with("abc", origen="admin_login")


def test_admin_rotar_inyecta_cookie(admin_client):
    tc, fake = admin_client
    r = tc.post("/admin/rotar", json={"php_sessid": "xyz"}, headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 200
    fake.set_session_cookie.assert_called_once_with("xyz", origen="admin_rotar")


def test_admin_status_ok(admin_client):
    tc, _fake = admin_client
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


def test_ip_in_allowed_networks_loopback_siempre_permitido():
    # La PC del proxy usada como agente llega como 127.0.0.1 / ::1.
    for redes in (["192.168.0.0/16"], []):
        assert server._ip_in_allowed_networks("127.0.0.1", redes) is True
        assert server._ip_in_allowed_networks("::1", redes) is True


def test_ip_in_allowed_networks_ip_publica_del_router_no_se_permite():
    # La salida NAT del router (IP publica) no esta en la whitelist ni debe estarlo.
    redes = ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12", "100.64.0.0/10"]
    for publica in ("162.120.185.241", "38.253.147.12", "72.14.201.203"):
        assert server._ip_in_allowed_networks(publica, redes) is False


# --------------------------------------------------------------------------
# Autologin desatendido (plan Proxy 24/7, 2026-10-28)
# --------------------------------------------------------------------------


class _RelojFreno:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.t += s


def _pa_con_credencial(**overrides) -> server.ProxyValidatorAPI:
    """Credencial escrita directo en el keyring (en memoria): `guardar_credencial_login`
    ademas lanza el autologin, que aqui no interesa."""
    pa = _mk_proxy_api(**overrides)
    keyring.set_password(
        "JSWinProxy",
        "credentials_login",
        json.dumps({"usuario": "proxy@empresa.pe", "password": "secreta"}),
    )
    return pa


def _pa_reloj_falso(pa: server.ProxyValidatorAPI, **kw) -> _RelojFreno:
    reloj = _RelojFreno()
    pa._freno = autologin.FrenoAutologin(reloj=reloj, **kw)
    pa._dormir = reloj.dormir
    return reloj


def _eventos() -> list[dict]:
    return server._leer_eventos_sesion(limite=100)


def test_config_autologin_por_defecto():
    cfg = ProxyConfig(proxy_token="a" * 64, admin_key="b" * 64)
    assert cfg.autologin_enabled is True
    assert cfg.autologin_muerte_rapida_s == 600
    # El tope por hora ya no es config: sale del frenado elegido (consola owner).
    assert not hasattr(cfg, "autologin_max_por_hora")


def test_guardar_credencial_login_va_al_keyring_y_se_lee(keyring_en_memoria):
    pa = _mk_proxy_api()
    assert pa._leer_credencial_login() is None
    pa.guardar_credencial_login("proxy@empresa.pe", "secreta")
    assert pa._leer_credencial_login() == ("proxy@empresa.pe", "secreta")
    assert ("JSWinProxy", "credentials_login") in keyring_en_memoria


def test_guardar_credencial_login_rechaza_vacios():
    pa = _mk_proxy_api()
    with pytest.raises(ValueError):
        pa.guardar_credencial_login("", "x")
    with pytest.raises(ValueError):
        pa.guardar_credencial_login("u", "")


def test_leer_credencial_login_corrupta_es_none():
    pa = _mk_proxy_api()
    keyring.set_password("JSWinProxy", "credentials_login", "no-es-json")
    assert pa._leer_credencial_login() is None


def test_guardar_credencial_reactiva_el_freno_tras_credencial_invalida():
    pa = _mk_proxy_api()
    pa._freno.registrar_credencial_invalida()
    pa.guardar_credencial_login("u@x.pe", "nueva")
    assert pa._freno.puede_intentar() == (True, "")


def test_guardar_credencial_con_sesion_muerta_lanza_autologin(autologin_capturado):
    pa = _mk_proxy_api()
    pa._client = FakeCore(php=None)
    pa.guardar_credencial_login("u@x.pe", "p")
    assert len(autologin_capturado) == 1


def test_guardar_credencial_con_sesion_viva_no_lanza_autologin(autologin_capturado):
    pa = _mk_proxy_api()
    pa._client = FakeCore(php="viva")
    pa.guardar_credencial_login("u@x.pe", "p")
    assert autologin_capturado == []


def test_get_status_informa_login_configurado_y_bloque_autologin():
    pa = _mk_proxy_api()
    st = pa.get_status()
    assert st["login_configurado"] is False
    assert st["autologin"]["habilitado"] is False

    pa.guardar_credencial_login("u@x.pe", "secreta")
    st = pa.get_status()
    assert st["login_configurado"] is True
    assert st["autologin"]["habilitado"] is True
    assert st["autologin"]["en_curso"] is True  # sin sesion: guardar la lanza
    assert "secreta" not in json.dumps(st)


def test_get_status_autologin_deshabilitado_por_config():
    pa = _pa_con_credencial(autologin_enabled=False)
    assert pa.get_status()["autologin"]["habilitado"] is False


def test_muerte_con_credencial_lanza_autologin_y_no_avisa(
    avisos_capturados, autologin_capturado
):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="vieja")
    pa._marcar_sesion_muerta("prueba", php_sessid="vieja")
    assert len(autologin_capturado) == 1
    assert avisos_capturados == []
    assert [e["evento"] for e in _eventos()] == ["muerta"]


def test_muerte_sin_credencial_avisa_como_antes(avisos_capturados, autologin_capturado):
    pa = _mk_proxy_api()
    pa._marcar_sesion_muerta("prueba")
    assert autologin_capturado == []
    assert avisos_capturados == [("sesion_caducada", "prueba")]


def test_muerte_con_autologin_apagado_en_config_avisa(avisos_capturados, autologin_capturado):
    pa = _pa_con_credencial(autologin_enabled=False)
    pa._marcar_sesion_muerta("prueba")
    assert autologin_capturado == []
    assert avisos_capturados == [("sesion_caducada", "prueba")]


def test_programar_autologin_es_single_flight(autologin_capturado):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php=None)
    autologin_capturado.clear()
    assert pa._programar_autologin("a") is True
    assert pa._programar_autologin("b") is False
    assert len(autologin_capturado) == 1


def test_ejecutar_autologin_ok_renueva_y_hace_ping(monkeypatch, avisos_capturados):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="vieja")
    pa._session_dead_since = time.time() - 30
    llamadas = []
    monkeypatch.setattr(
        autologin, "login_automatico", lambda u, p: llamadas.append((u, p)) or "php-nueva"
    )

    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._ejecutar_autologin()

    assert llamadas == [("proxy@empresa.pe", "secreta")]
    assert pa._session_dead_since is None
    assert pa._client._sesion.cookies["PHPSESSID"] == "php-nueva"
    assert pa._client.llamadas == 1  # el ping de cobertura
    ultimo = _eventos()[-1]
    assert (ultimo["evento"], ultimo["origen"]) == ("renovada", "autologin")
    assert pa._freno.estado()["ultimo_resultado"] == "ok"
    assert pa._autologin_corriendo is False


def test_ejecutar_autologin_credencial_invalida_no_reintenta_y_avisa(
    monkeypatch, avisos_capturados
):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php=None)
    _pa_reloj_falso(pa)
    llamadas = []

    def falla(u, p):
        llamadas.append(1)
        raise autologin.CredencialInvalidaError("rechazada por Microsoft")

    monkeypatch.setattr(autologin, "login_automatico", falla)
    pa._ejecutar_autologin()

    assert llamadas == [1]
    assert pa._freno.puede_intentar() == (False, "credencial_invalida")
    assert _eventos()[-1]["evento"] == "autologin_fallido"
    assert [e for e, _ in avisos_capturados] == ["autologin_credencial_invalida"]


def test_ejecutar_autologin_navegador_rechazado_no_reintenta_y_avisa(
    monkeypatch, avisos_capturados
):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php=None)
    _pa_reloj_falso(pa)
    llamadas = []

    def falla(u, p):
        llamadas.append(1)
        raise autologin.NavegadorRechazadoError("HTTP 410")

    monkeypatch.setattr(autologin, "login_automatico", falla)
    pa._ejecutar_autologin()

    assert llamadas == [1]
    assert pa._freno.puede_intentar() == (False, "navegador_rechazado")
    assert pa._autologin_disponible() is False
    assert _eventos()[-1]["evento"] == "autologin_fallido"
    assert [e for e, _ in avisos_capturados] == ["autologin_navegador_rechazado"]


def test_guardar_credencial_reactiva_el_freno_tras_navegador_rechazado():
    pa = _mk_proxy_api()
    pa._freno.registrar_navegador_rechazado()
    pa.guardar_credencial_login("u@x.pe", "nueva")
    assert pa._freno.puede_intentar() == (True, "")


def test_ejecutar_autologin_reintenta_con_espera_tras_un_fallo(monkeypatch):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php=None)
    reloj = _pa_reloj_falso(pa)
    inicio = reloj.t
    respuestas = [autologin.AutologinError("timeout"), "php-nueva"]

    def login(u, p):
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(autologin, "login_automatico", login)
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._ejecutar_autologin()

    assert respuestas == []
    assert reloj.t - inicio == 60  # frenado recomendado: 2.o intento al minuto
    assert pa._client._sesion.cookies["PHPSESSID"] == "php-nueva"
    assert [e["evento"] for e in _eventos()][-2:] == ["autologin_fallido", "renovada"]


def test_ejecutar_autologin_se_rinde_al_tope_por_hora_y_avisa(monkeypatch, avisos_capturados):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php=None)
    _pa_reloj_falso(pa, max_por_hora=3)
    llamadas = []

    def falla(u, p):
        llamadas.append(1)
        raise autologin.AutologinError("timeout")

    monkeypatch.setattr(autologin, "login_automatico", falla)
    pa._ejecutar_autologin()

    assert len(llamadas) == 3
    assert avisos_capturados == [("autologin_detenido", "tope_por_hora")]
    assert pa._autologin_corriendo is False


def test_ejecutar_autologin_para_si_la_sesion_ya_volvio(monkeypatch):
    """El owner renovo a mano mientras el autologin esperaba: no se re-loguea."""
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="renovada-a-mano")
    pa._session_dead_since = None
    monkeypatch.setattr(
        autologin, "login_automatico", lambda u, p: pytest.fail("no debia loguear")
    )
    pa._ejecutar_autologin()


def test_ping_tras_autologin_con_sesion_rechazada_cuenta_como_fallo(monkeypatch):
    pa = _pa_con_credencial()
    reloj = _pa_reloj_falso(pa, max_por_hora=2)
    pa._client = FakeCore(
        php=None, excepcion=core_api.LoginError("no activa", "ERR_LOGIN_SESSION")
    )
    llamadas = []
    monkeypatch.setattr(
        autologin, "login_automatico", lambda u, p: llamadas.append(1) or "php"
    )
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._ejecutar_autologin()
    assert len(llamadas) == 2
    assert reloj.t > 1_000_000.0


def test_dos_muertes_rapidas_pausan_el_autologin_y_avisan(
    avisos_capturados, autologin_capturado
):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="x")
    reloj = _pa_reloj_falso(pa, muerte_rapida_s=600)

    pa._freno.registrar_intento()
    pa._freno.registrar_exito()
    reloj.t += 100
    pa._marcar_sesion_muerta("muere 1", php_sessid="x")
    assert len(autologin_capturado) == 1

    pa._autologin_corriendo = False
    pa._marcar_sesion_viva()
    avisos_capturados.clear()
    pa._freno.registrar_intento()
    pa._freno.registrar_exito()
    reloj.t += 100
    pa._marcar_sesion_muerta("muere 2", php_sessid="x")

    assert len(autologin_capturado) == 1
    assert [e for e, _ in avisos_capturados] == ["autologin_pausado"]
    assert _eventos()[-1]["evento"] == "autologin_pausado"


def test_keepalive_sin_sesion_lanza_autologin_si_hay_credencial(autologin_capturado):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php=None)
    autologin_capturado.clear()
    res = pa._keepalive_tick()
    assert res["motivo"] == "sin_sesion"
    assert len(autologin_capturado) == 1


def test_keepalive_sin_sesion_y_sin_credencial_no_lanza_nada(autologin_capturado):
    pa = _mk_proxy_api()
    pa._client = FakeCore(php=None)
    pa._keepalive_tick()
    assert autologin_capturado == []


def test_keepalive_con_sesion_ya_muerta_vuelve_a_lanzar_autologin(autologin_capturado):
    pa = _pa_con_credencial()
    pa._client = FakeCore(excepcion=core_api.APIError("HTTP 200 text/html", "ERR_NETWORK"))
    pa._session_dead_since = time.time() - 600
    pa._last_activity = time.time() - 5000
    err = core_api.LoginError("sesion no activa", "ERR_LOGIN_SESSION")
    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=err):
        res = pa._keepalive_tick()
    assert res["resultado"] == "SESION_MUERTA"
    assert len(autologin_capturado) == 1


def test_enviar_avisos_tiene_mensaje_para_cada_evento_de_autologin(monkeypatch):
    pa = _mk_proxy_api()
    escritos = []
    monkeypatch.setattr(
        server.ProxyValidatorAPI,
        "_aviso_event_log",
        staticmethod(lambda event_id, tipo, mensaje: escritos.append((event_id, tipo, mensaje))),
    )
    for evento in (
        "autologin_credencial_invalida",
        "autologin_pausado",
        "autologin_detenido",
        "autologin_navegador_rechazado",
    ):
        pa._enviar_avisos(evento, "detalle")
    assert [e[0] for e in escritos] == [server.EVENTO_SESION_CADUCADA] * 4
    assert all(e[1] == "ERROR" for e in escritos)
    assert "rotate_creds --guardar-login" in escritos[0][2]
    assert "WinForce o Microsoft" in escritos[0][2]
    assert "otra persona" in escritos[1][2]
    assert "no es la contrasena" in escritos[3][2]


# --- endpoint /local/credenciales --------------------------------------------

def test_local_credenciales_guarda_sin_eco(admin_client):
    tc, fake = admin_client
    r = tc.post(
        "/local/credenciales",
        json={"usuario": "proxy@empresa.pe", "password": "secreta"},
        headers={"X-Admin-Key": _ADMIN},
    )
    assert r.status_code == 200
    assert "secreta" not in r.text
    fake.guardar_credencial_login.assert_called_once_with("proxy@empresa.pe", "secreta")


def test_local_credenciales_exige_admin_key(admin_client):
    tc, fake = admin_client
    r = tc.post("/local/credenciales", json={"usuario": "u", "password": "p"})
    assert r.status_code == 401
    fake.guardar_credencial_login.assert_not_called()


def test_local_credenciales_solo_desde_la_pc_del_proxy(client):
    tc, fake = client
    r = tc.post(
        "/local/credenciales",
        json={"usuario": "u", "password": "p"},
        headers={"X-Admin-Key": _ADMIN},
    )
    assert r.status_code == 403
    fake.guardar_credencial_login.assert_not_called()


def test_local_credenciales_vacias_da_422(admin_client):
    tc, fake = admin_client
    fake.guardar_credencial_login.side_effect = ValueError("vacio")
    r = tc.post(
        "/local/credenciales",
        json={"usuario": "", "password": ""},
        headers={"X-Admin-Key": _ADMIN},
    )
    assert r.status_code == 422


def test_health_y_admin_status_incluyen_autologin(admin_client):
    tc, fake = admin_client
    fake.get_status.return_value = {
        **_STATUS,
        "login_configurado": True,
        "autologin": {
            "habilitado": True, "en_curso": False, "ultimo_intento": None,
            "ultimo_resultado": "ok", "pausado_hasta": None, "motivo": "",
        },
    }
    h = tc.get("/health").json()
    assert h["login_configurado"] is True
    assert h["autologin"]["ultimo_resultado"] == "ok"
    s = tc.get("/admin/status", headers={"X-Admin-Key": _ADMIN}).json()
    assert s["login_configurado"] is True
    assert s["autologin"]["habilitado"] is True


def test_health_sin_bloque_autologin_sigue_respondiendo(client):
    tc, fake = client
    fake.get_status.return_value = _STATUS
    body = tc.get("/health").json()
    assert body["login_configurado"] is False
    assert body["autologin"] is None


# --- frenado configurable (perfiles) -----------------------------------------

def test_freno_por_defecto_es_el_recomendado_sin_archivo():
    pa = _mk_proxy_api()
    st = pa.get_status()["autologin"]["freno"]
    assert st == {
        "perfil": "recomendado",
        "nombre": "Rango de relogin recomendado",
        "minutos": [0, 1, 2, 3, 5],
        "pausa_min": 5,
    }
    assert pa._freno.esperas == (0, 60, 120, 180, 300)


def test_configurar_freno_aplica_en_vivo_y_persiste(autologin_freno_path):
    pa = _mk_proxy_api()
    pa.configurar_freno("personalizado", [2, 3, 4, 7])
    assert pa._freno.esperas == (0, 120, 180, 240, 420)
    assert pa._freno.pausa_s == 420
    guardado = json.loads(autologin_freno_path.read_text(encoding="utf-8"))
    assert guardado == {"perfil": "personalizado", "minutos": [2, 3, 4, 7]}

    otra = _mk_proxy_api()  # reinicio del servicio
    assert otra._freno.esperas == (0, 120, 180, 240, 420)
    assert otra.get_status()["autologin"]["freno"]["perfil"] == "personalizado"
    assert _eventos()[-1]["evento"] == "freno_cambiado"


def test_configurar_freno_perfil_con_nombre_usa_sus_minutos():
    pa = _mk_proxy_api()
    pa.configurar_freno("lento", [1, 1, 1, 1])
    assert pa.get_status()["autologin"]["freno"]["minutos"] == [0, 3, 6, 10, 15]


def test_configurar_freno_invalido_no_cambia_nada(autologin_freno_path):
    pa = _mk_proxy_api()
    with pytest.raises(ValueError):
        pa.configurar_freno("personalizado", [9, 9, 9, 9])
    assert pa._freno.esperas == (0, 60, 120, 180, 300)
    assert not autologin_freno_path.exists()


@pytest.mark.parametrize("contenido", ["no-es-json", '{"perfil": "personalizado", "minutos": [9]}'])
def test_freno_guardado_corrupto_vuelve_al_recomendado(autologin_freno_path, contenido):
    autologin_freno_path.write_text(contenido, encoding="utf-8")
    pa = _mk_proxy_api()
    assert pa._freno.esperas == (0, 60, 120, 180, 300)


def test_local_freno_aplica_sin_eco_de_secretos(admin_client):
    tc, fake = admin_client
    r = tc.post(
        "/local/freno",
        json={"perfil": "personalizado", "minutos": [2, 3, 4, 7]},
        headers={"X-Admin-Key": _ADMIN},
    )
    assert r.status_code == 200
    fake.configurar_freno.assert_called_once_with("personalizado", [2, 3, 4, 7])


def test_local_freno_exige_admin_key_y_loopback(admin_client, client):
    tc, fake = admin_client
    assert tc.post("/local/freno", json={"perfil": "lento"}).status_code == 401
    tc_lan, fake_lan = client
    r = tc_lan.post("/local/freno", json={"perfil": "lento"}, headers={"X-Admin-Key": _ADMIN})
    assert r.status_code == 403
    fake.configurar_freno.assert_not_called()
    fake_lan.configurar_freno.assert_not_called()


def test_local_freno_invalido_da_422(admin_client):
    tc, fake = admin_client
    fake.configurar_freno.side_effect = ValueError("El 2.o va de 1 a 5")
    r = tc.post(
        "/local/freno",
        json={"perfil": "personalizado", "minutos": [9, 9, 9, 9]},
        headers={"X-Admin-Key": _ADMIN},
    )
    assert r.status_code == 422
    assert "1 a 5" in r.text


def test_mensaje_de_pausa_dice_los_minutos_del_frenado(monkeypatch):
    pa = _mk_proxy_api()
    pa.configurar_freno("lento_optimo")
    escritos = []
    monkeypatch.setattr(
        server.ProxyValidatorAPI,
        "_aviso_event_log",
        staticmethod(lambda event_id, tipo, mensaje: escritos.append(mensaje)),
    )
    pa._enviar_avisos("autologin_pausado", "")
    assert "10 min" in escritos[0]


# --------------------------------------------------------------------------
# La consulta espera al autologin y se reintenta (2026-10-30: el asesor que
# descubrio la muerte recibia 502 aunque el autologin la renovaba en 12 s)
# --------------------------------------------------------------------------

def _autologin_en_hilo_real(monkeypatch, login):
    """Corre el autologin en un hilo de verdad (el fixture autouse lo captura) con
    `login_automatico` falso: asi la consulta realmente espera a otro hilo."""
    hilos = []

    def lanzar(self, target):
        h = threading.Thread(target=target, daemon=True)
        hilos.append(h)
        h.start()

    monkeypatch.setattr(server.ProxyValidatorAPI, "_lanzar_hilo", lanzar)
    monkeypatch.setattr(autologin, "login_automatico", login)
    return hilos


def _login_lento(usuario, password):
    """Como el real (~6 s), pero corto: la consulta alcanza a quedarse esperando."""
    time.sleep(0.2)
    return "php-nueva"


def _esperar_hilos(hilos):
    for h in hilos:
        h.join(5)


def test_config_espera_de_la_consulta_por_defecto():
    cfg = ProxyConfig(proxy_token="a" * 64, admin_key="b" * 64)
    assert cfg.autologin_espera_consulta_s == 15


def test_consulta_con_sesion_muerta_espera_al_autologin_y_responde(monkeypatch):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="vieja")
    hilos = _autologin_en_hilo_real(monkeypatch, _login_lento)
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._marcar_sesion_muerta("prueba", php_sessid="vieja")
        pa._last_activity = time.time()
        resultado = pa.validar_cobertura(-12.05, -77.03)
        _esperar_hilos(hilos)

    assert resultado["cobertura"] == "SI"
    assert pa._client._sesion.cookies["PHPSESSID"] == "php-nueva"
    reintento = [e for e in _eventos() if e["evento"] == "consulta_reintentada"]
    assert len(reintento) == 1
    assert reintento[0]["origen"] == "cobertura"
    detalle = reintento[0]["detalle"]
    for fase in ("deteccion", "autologin", "consulta", "total"):
        assert re.search(rf"{fase} \d+\.\d s", detalle), detalle
    assert "-12.05" not in json.dumps(reintento)


def test_score_tambien_espera_al_autologin(monkeypatch):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="vieja")
    hilos = _autologin_en_hilo_real(monkeypatch, _login_lento)
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._marcar_sesion_muerta("prueba", php_sessid="vieja")
        pa._last_activity = time.time()
        resultado = pa.validar_score("DNI", "10412031", -12.05, -77.03)
        _esperar_hilos(hilos)

    assert resultado["valido"] is True
    reintento = [e for e in _eventos() if e["evento"] == "consulta_reintentada"]
    assert [e["origen"] for e in reintento] == ["score"]
    assert "10412031" not in json.dumps(_eventos())


def test_consulta_da_503_si_el_autologin_no_termina_a_tiempo(monkeypatch):
    pa = _pa_con_credencial(autologin_espera_consulta_s=0.3)
    pa._client = FakeCore(php="vieja")
    soltar = threading.Event()
    hilos = _autologin_en_hilo_real(monkeypatch, lambda u, p: (soltar.wait(5), "php-nueva")[1])
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._marcar_sesion_muerta("prueba", php_sessid="vieja")
        inicio = time.monotonic()
        try:
            with pytest.raises(server.SesionCaducadaError):
                pa.validar_cobertura(-12.05, -77.03)
            assert time.monotonic() - inicio < 2
            assert pa._client.llamadas == 0
        finally:
            soltar.set()
            for h in hilos:
                h.join(5)
    sin_sesion = [e for e in _eventos() if e["evento"] == "consulta_sin_sesion"]
    assert len(sin_sesion) == 1
    assert re.search(r"autologin \d+\.\d s", sin_sesion[0]["detalle"])


def test_consulta_no_espera_si_el_autologin_falla(monkeypatch):
    """Si el intento falla, el autologin queda esperando su frenado (minutos): la
    consulta no se queda colgada el plazo entero."""
    pa = _pa_con_credencial(autologin_espera_consulta_s=5)
    pa._client = FakeCore(php="vieja")

    def falla(u, p):
        time.sleep(0.1)
        raise autologin.AutologinError("no termino")

    hilos = _autologin_en_hilo_real(monkeypatch, falla)
    pa._freno = autologin.FrenoAutologin(esperas=(0, 600))
    with mock.patch.object(core_api, "validar_cookie_sesion", return_value=None):
        pa._marcar_sesion_muerta("prueba", php_sessid="vieja")
        inicio = time.monotonic()
        with pytest.raises(server.SesionCaducadaError):
            pa.validar_cobertura(-12.05, -77.03)
        assert time.monotonic() - inicio < 3
    # el hilo queda dormido en su frenado de 600 s (daemon, sin red)
    assert all(h.is_alive() for h in hilos)


def test_consulta_no_espera_si_el_autologin_esta_en_frenado(autologin_capturado):
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="vieja")
    pa._freno.registrar_fallo()  # proximo intento en minutos
    pa._session_dead_since = time.time() - 10
    inicio = time.monotonic()
    with pytest.raises(server.SesionCaducadaError):
        pa.validar_cobertura(-12.05, -77.03)
    assert time.monotonic() - inicio < 1
    assert pa._client.llamadas == 0


def test_relogin_que_descubre_la_muerte_no_consulta_con_la_cookie_muerta(monkeypatch):
    """Lo que paso a las 19:00: la consulta llego tras >120 s sin actividad, el
    relogin vio la cookie del keyring muerta y lanzo el autologin, pero la consulta
    seguia con la cookie muerta y el asesor recibia 502."""
    pa = _pa_con_credencial()
    pa._client = FakeCore(php="vieja")
    pa._save_session_cookies()
    pa._last_activity = time.time() - 5000
    hilos = _autologin_en_hilo_real(monkeypatch, _login_lento)

    def validar(php):
        if php == "vieja":
            raise core_api.LoginError("la sesion no quedo activa")

    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=validar):
        resultado = pa.validar_cobertura(-12.05, -77.03)
        _esperar_hilos(hilos)

    assert resultado["cobertura"] == "SI"
    assert pa._client._sesion.cookies["PHPSESSID"] == "php-nueva"
    reintento = [e for e in _eventos() if e["evento"] == "consulta_reintentada"]
    assert len(reintento) == 1
    # la deteccion (validar la cookie del keyring y confirmar) es una fase propia
    assert re.search(r"deteccion \d+\.\d s", reintento[0]["detalle"])


def test_error_de_sesion_de_winforce_se_reintenta_una_sola_vez(monkeypatch):
    pa = _pa_con_credencial()
    pa._last_activity = time.time()

    class CoreQueCaduca(FakeCore):
        def validar_cobertura(self, lat, lon):
            self.llamadas += 1
            if self._sesion.cookies.get("PHPSESSID") == "vieja":
                raise core_api.APIError("Sesion expirada", "ERR_SESSION")
            return self._resultado

    pa._client = CoreQueCaduca(php="vieja")
    pa._save_session_cookies()
    hilos = _autologin_en_hilo_real(monkeypatch, _login_lento)

    def validar(php):
        if php == "vieja":
            raise core_api.LoginError("la sesion no quedo activa")

    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=validar):
        resultado = pa.validar_cobertura(-12.05, -77.03)
        _esperar_hilos(hilos)

    assert resultado["cobertura"] == "SI"
    # la fallida + el ping del autologin + el unico reintento
    assert pa._client.llamadas == 3


def test_endpoints_de_consulta_no_bloquean_el_bucle_del_servidor():
    """Async + codigo bloqueante congelaba todo el proxy (y /health) mientras una
    consulta esperaba; como `def`, FastAPI las corre en su pool de hilos."""
    import inspect

    assert not inspect.iscoroutinefunction(server.api_cobertura)
    assert not inspect.iscoroutinefunction(server.api_score)


# 2026-10-30 ~20:00: la cookie paso la validacion y murio segundos despues;
# coordenada.php devolvio la pagina de login (HTML) y el asesor recibio 502 sin
# que el proxy marcara la muerte ni lanzara el autologin.
_HTML_INESPERADO = (
    "Respuesta inesperada del servidor al consultar {}. "
    "[HTTP 200 text/html; charset=UTF-8 body='<!DOCTYPE html>']"
)


class CoreConLoginHTML(FakeCore):
    """Con la cookie muerta, WinForce responde su pagina de login en vez de JSON."""

    def validar_cobertura(self, lat, lon):
        self.llamadas += 1
        if self._sesion.cookies.get("PHPSESSID") == "vieja":
            raise core_api.APIError(_HTML_INESPERADO.format("cobertura"), "ERR_NETWORK")
        return self._resultado

    def validar_score(self, tipo, numero, lat, lon, cobertura="SI"):
        self.llamadas += 1
        if self._sesion.cookies.get("PHPSESSID") == "vieja":
            raise core_api.APIError(_HTML_INESPERADO.format("score"), "ERR_NETWORK")
        return {"valor": 1, "riesgo": "BAJO", "valido": True}


def _vieja_muerta(php):
    if php == "vieja":
        raise core_api.LoginError("la sesion no quedo activa")


@pytest.mark.parametrize("nombre", ["cobertura", "score"])
def test_respuesta_html_con_cookie_muerta_lanza_autologin_y_reintenta(monkeypatch, nombre):
    pa = _pa_con_credencial()
    pa._last_activity = time.time()
    pa._client = CoreConLoginHTML(php="vieja")
    pa._save_session_cookies()
    hilos = _autologin_en_hilo_real(monkeypatch, _login_lento)

    with mock.patch.object(core_api, "validar_cookie_sesion", side_effect=_vieja_muerta):
        if nombre == "cobertura":
            resultado = pa.validar_cobertura(-12.05, -77.03)
            assert resultado["cobertura"] == "SI"
        else:
            resultado = pa.validar_score("DNI", "10412031", -12.05, -77.03)
            assert resultado["valido"] is True
        _esperar_hilos(hilos)

    eventos = [e["evento"] for e in _eventos()]
    assert "muerta" in eventos and "consulta_reintentada" in eventos


def test_respuesta_inesperada_con_cookie_viva_da_el_error_real_sin_reintentar():
    pa = _pa_con_credencial()
    pa._last_activity = time.time()
    pa._client = FakeCore(
        php="viva",
        excepcion=core_api.APIError(_HTML_INESPERADO.format("cobertura"), "ERR_NETWORK"),
    )
    pa._save_session_cookies()

    with (
        mock.patch.object(core_api, "validar_cookie_sesion", return_value=None),
        pytest.raises(core_api.APIError, match="Respuesta inesperada"),
    ):
        pa.validar_cobertura(-12.05, -77.03)

    assert pa._client.llamadas == 1
    assert pa._session_dead_since is None


def test_el_502_deja_el_detalle_en_el_log(client, caplog):
    tc, fake = client
    fake.validar_cobertura.side_effect = core_api.APIError(
        _HTML_INESPERADO.format("cobertura"), "ERR_NETWORK"
    )
    with caplog.at_level("WARNING"):
        r = tc.post(
            "/api/cobertura", json={"lat": -12.05, "lon": -77.03},
            headers={"X-Proxy-Token": _TOKEN},
        )
    assert r.status_code == 502
    assert "Respuesta inesperada" in caplog.text
    assert "/api/cobertura" in caplog.text
