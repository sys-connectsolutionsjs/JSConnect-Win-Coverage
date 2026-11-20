"""Version mas reciente via proxy: cache del proxy, endpoint /api/version y cliente."""

from unittest import mock

import httpx
import pytest
from fastapi.testclient import TestClient

from validator_app.proxy import client as pc
from validator_app.proxy import server
from validator_app.proxy.config import ProxyConfig
from validator_app.proxy.version_cache import VersionCache

_TOKEN = "t" * 64
_RELEASE = {
    "tag": "v2026.11.20",
    "commit": "abc123",
    "notes": "",
    "asset": None,
    "url_descarga": "https://github.com/o/r/releases/download/v2026.11.20/JSConnect-Win-Coverage.exe",
    "nombre_asset": "JSConnect-Win-Coverage.exe",
}


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_cache_consulta_github_una_sola_vez_dentro_del_ttl():
    consultar = mock.Mock(return_value=_RELEASE)
    reloj = Reloj()
    cache = VersionCache(consultar, ttl_s=600, reloj=reloj)

    assert cache.obtener() == _RELEASE
    reloj.t += 599
    assert cache.obtener() == _RELEASE

    assert consultar.call_count == 1


def test_cache_vuelve_a_consultar_pasado_el_ttl():
    consultar = mock.Mock(return_value=_RELEASE)
    reloj = Reloj()
    cache = VersionCache(consultar, ttl_s=600, reloj=reloj)

    cache.obtener()
    reloj.t += 601
    cache.obtener()

    assert consultar.call_count == 2


def test_cache_recuerda_tambien_que_no_hay_release():
    consultar = mock.Mock(return_value=None)
    cache = VersionCache(consultar, ttl_s=600, reloj=Reloj())

    assert cache.obtener() is None
    assert cache.obtener() is None

    assert consultar.call_count == 1


def test_cache_sirve_la_ultima_version_buena_si_github_falla_despues():
    consultar = mock.Mock(side_effect=[_RELEASE, OSError("sin red")])
    reloj = Reloj()
    cache = VersionCache(consultar, ttl_s=600, reloj=reloj)

    cache.obtener()
    reloj.t += 700

    assert cache.obtener() == _RELEASE


def test_cache_lanza_si_github_falla_y_nunca_hubo_dato():
    cache = VersionCache(mock.Mock(side_effect=OSError("sin red")), ttl_s=600, reloj=Reloj())
    with pytest.raises(OSError):
        cache.obtener()


def test_cache_tras_un_fallo_no_martilla_a_github_en_cada_consulta():
    consultar = mock.Mock(side_effect=[_RELEASE, OSError("a"), OSError("b")])
    reloj = Reloj()
    cache = VersionCache(consultar, ttl_s=600, reloj=reloj, reintento_s=60)

    cache.obtener()
    reloj.t += 700
    cache.obtener()
    cache.obtener()

    assert consultar.call_count == 2


@pytest.fixture
def api(monkeypatch):
    cfg = ProxyConfig(proxy_token=_TOKEN, admin_key="k" * 64, allowed_networks=["10.0.0.0/8"])
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    cache = VersionCache(mock.Mock(return_value=_RELEASE), ttl_s=600, reloj=Reloj())
    monkeypatch.setattr(server, "get_version_cache", lambda: cache)
    return TestClient(server.app, client=("10.0.0.5", 5000)), cache


def test_endpoint_exige_token(api):
    tc, _ = api
    assert tc.get("/api/version").status_code == 401


def test_endpoint_devuelve_el_release(api):
    tc, _ = api
    r = tc.get("/api/version", headers={"X-Proxy-Token": _TOKEN})
    assert r.status_code == 200
    assert r.json() == {"release": _RELEASE}


def test_endpoint_dos_llamadas_consultan_github_una_vez(api):
    tc, cache = api
    h = {"X-Proxy-Token": _TOKEN}
    tc.get("/api/version", headers=h)
    tc.get("/api/version", headers=h)
    assert cache._consultar.call_count == 1


def test_endpoint_sin_release_responde_release_none(monkeypatch):
    cfg = ProxyConfig(proxy_token=_TOKEN, admin_key="k" * 64, allowed_networks=["10.0.0.0/8"])
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    cache = VersionCache(mock.Mock(return_value=None), ttl_s=600, reloj=Reloj())
    monkeypatch.setattr(server, "get_version_cache", lambda: cache)
    tc = TestClient(server.app, client=("10.0.0.5", 5000))

    r = tc.get("/api/version", headers={"X-Proxy-Token": _TOKEN})

    assert r.status_code == 200
    assert r.json() == {"release": None}


def test_endpoint_503_si_github_falla_y_no_hay_cache(monkeypatch):
    cfg = ProxyConfig(proxy_token=_TOKEN, admin_key="k" * 64, allowed_networks=["10.0.0.0/8"])
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    cache = VersionCache(mock.Mock(side_effect=OSError("sin red")), ttl_s=600, reloj=Reloj())
    monkeypatch.setattr(server, "get_version_cache", lambda: cache)
    tc = TestClient(server.app, client=("10.0.0.5", 5000))

    r = tc.get("/api/version", headers={"X-Proxy-Token": _TOKEN})

    assert r.status_code == 503


def _client_con(respuesta: httpx.Response):
    vistas = []

    def handler(request):
        vistas.append(request)
        return respuesta

    c = pc.ProxyClient(base_url="http://proxy.test", token=_TOKEN, max_retries=3)
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    return c, vistas


def test_cliente_obtener_version_devuelve_el_cuerpo():
    c, vistas = _client_con(httpx.Response(200, json={"release": _RELEASE}))
    assert c.obtener_version() == {"release": _RELEASE}
    assert vistas[0].url.path == "/api/version"


@pytest.mark.parametrize("estado", [404, 503, 500])
def test_cliente_obtener_version_devuelve_none_sin_reintentar_ni_dormir(estado, monkeypatch):
    dormidas = []
    monkeypatch.setattr(pc.time, "sleep", lambda s: dormidas.append(s))
    c, vistas = _client_con(httpx.Response(estado, json={"detail": "x"}))

    assert c.obtener_version() is None
    assert len(vistas) == 1
    assert dormidas == []


def test_cliente_obtener_version_none_si_no_conecta():
    def handler(request):
        raise httpx.ConnectError("sin proxy")

    c = pc.ProxyClient(base_url="http://proxy.test", token=_TOKEN)
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    assert c.obtener_version() is None
