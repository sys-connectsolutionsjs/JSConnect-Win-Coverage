"""Tests del proxy local (validator_app.proxy.server).

Cubre el keepalive "latido perezoso" de la Fase 2A y el fix del guard idle del
cliente-core. Son unit tests sobre `ProxyValidatorAPI` con `core.api`
monkeypatcheado (sin red, sin FastAPI TestClient — eso es Fase 4).
"""

import asyncio
import time
import types
from unittest import mock

from validator_app.core import api as core_api
from validator_app.proxy import server
from validator_app.proxy.config import ProxyConfig


def _mk_proxy_api(**overrides) -> server.ProxyValidatorAPI:
    cfg = ProxyConfig(proxy_token="a" * 64, admin_key="b" * 64, **overrides)
    return server.ProxyValidatorAPI(cfg)


class FakeCore:
    """Cliente-core mínimo: cookies + validar_cobertura configurable."""

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
