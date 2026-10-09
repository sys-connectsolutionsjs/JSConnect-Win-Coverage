"""Capas de reglas de venta: cache del proxy, endpoint /api/capas y cliente."""

from unittest import mock

import httpx
import pytest
from fastapi.testclient import TestClient

from validator_app.core import geo
from validator_app.proxy import capas as capas_mod
from validator_app.proxy import client as pc
from validator_app.proxy import server
from validator_app.proxy.config import ProxyConfig

KML_A = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Folder><name>PREFERENTE 2</name><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
-77.10,-12.00,0 -77.10,-11.90,0 -77.00,-11.90,0 -77.00,-12.00,0 -77.10,-12.00,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Folder>
</Document></kml>"""
KML_B = KML_A.replace("-77.10", "-77.20")


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _cache(tmp_path, descargar, reloj=None, ttl_s=100):
    return capas_mod.CapasCache(
        "http://kml.test/x.kml",
        tmp_path / "capas.kml",
        ttl_s=ttl_s,
        descargar=descargar,
        reloj=reloj or Reloj(),
    )


def test_roundtrip_json_de_capas():
    capas = geo.parse_kml(KML_A)
    assert geo.capas_de_json(geo.capas_a_json(capas)) == capas


def test_primera_llamada_descarga_y_guarda_en_disco(tmp_path):
    descargar = mock.Mock(return_value=KML_A)
    c = _cache(tmp_path, descargar)
    r = c.obtener()
    assert len(r.capas["PREFERENTE 2"]) == 1
    assert r.version
    assert (tmp_path / "capas.kml").read_text(encoding="utf-8") == KML_A
    descargar.assert_called_once_with("http://kml.test/x.kml")


def test_dentro_del_ttl_no_vuelve_a_descargar(tmp_path):
    descargar = mock.Mock(return_value=KML_A)
    c = _cache(tmp_path, descargar)
    c.obtener()
    c.obtener()
    assert descargar.call_count == 1


def test_pasado_el_ttl_redescarga_y_cambia_la_version(tmp_path):
    reloj = Reloj()
    descargar = mock.Mock(side_effect=[KML_A, KML_B])
    c = _cache(tmp_path, descargar, reloj)
    v1 = c.obtener().version
    reloj.t += 101
    v2 = c.obtener().version
    assert descargar.call_count == 2
    assert v1 != v2


def test_mismo_contenido_misma_version(tmp_path):
    reloj = Reloj()
    c = _cache(tmp_path, mock.Mock(return_value=KML_A), reloj)
    v1 = c.obtener().version
    reloj.t += 101
    assert c.obtener().version == v1


def test_si_la_descarga_falla_usa_la_copia_en_disco(tmp_path):
    (tmp_path / "capas.kml").write_text(KML_A, encoding="utf-8")
    c = _cache(tmp_path, mock.Mock(side_effect=OSError("sin red")))
    assert len(c.obtener().capas["PREFERENTE 2"]) == 1


def test_si_falla_y_no_hay_copia_lanza_error(tmp_path):
    c = _cache(tmp_path, mock.Mock(side_effect=OSError("sin red")))
    with pytest.raises(capas_mod.CapasNoDisponiblesError):
        c.obtener()


def test_kml_invalido_no_pisa_la_copia_buena(tmp_path):
    reloj = Reloj()
    c = _cache(tmp_path, mock.Mock(side_effect=[KML_A, "<html>login</html"]), reloj)
    v1 = c.obtener().version
    reloj.t += 101
    assert c.obtener().version == v1
    assert (tmp_path / "capas.kml").read_text(encoding="utf-8") == KML_A


def test_respuesta_sin_carpetas_se_trata_como_invalida(tmp_path):
    c = _cache(tmp_path, mock.Mock(return_value="<kml></kml>"))
    with pytest.raises(capas_mod.CapasNoDisponiblesError):
        c.obtener()


_TOKEN = "t" * 64


@pytest.fixture
def api(monkeypatch, tmp_path):
    cfg = ProxyConfig(proxy_token=_TOKEN, admin_key="k" * 64, allowed_networks=["10.0.0.0/8"])
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    cache = _cache(tmp_path, mock.Mock(return_value=KML_A))
    monkeypatch.setattr(server, "get_capas_cache", lambda: cache)
    return TestClient(server.app, client=("10.0.0.5", 5000)), cache


def test_endpoint_exige_token(api):
    tc, _ = api
    assert tc.get("/api/capas").status_code == 401


def test_endpoint_devuelve_version_y_capas(api):
    tc, _ = api
    r = tc.get("/api/capas", headers={"X-Proxy-Token": _TOKEN})
    assert r.status_code == 200
    body = r.json()
    assert body["actualizado"] is True
    assert body["version"]
    assert len(body["capas"]["PREFERENTE 2"]) == 1


def test_endpoint_misma_version_no_reenvia_capas(api):
    tc, _ = api
    h = {"X-Proxy-Token": _TOKEN}
    version = tc.get("/api/capas", headers=h).json()["version"]
    r = tc.get("/api/capas", params={"version": version}, headers=h)
    assert r.json() == {"version": version, "actualizado": False, "capas": None}


def test_endpoint_503_si_no_hay_capas(monkeypatch, tmp_path):
    cfg = ProxyConfig(proxy_token=_TOKEN, admin_key="k" * 64, allowed_networks=["10.0.0.0/8"])
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    cache = _cache(tmp_path, mock.Mock(side_effect=OSError("sin red")))
    monkeypatch.setattr(server, "get_capas_cache", lambda: cache)
    tc = TestClient(server.app, client=("10.0.0.5", 5000))
    r = tc.get("/api/capas", headers={"X-Proxy-Token": _TOKEN})
    assert r.status_code == 503


def _client_con(respuesta: httpx.Response):
    vistas = []

    def handler(request):
        vistas.append(request)
        return respuesta

    c = pc.ProxyClient(base_url="http://proxy.test", token=_TOKEN, max_retries=1)
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    return c, vistas


def test_cliente_obtener_capas_convierte_a_poligonos():
    capas = geo.parse_kml(KML_A)
    body = {"version": "v1", "actualizado": True, "capas": geo.capas_a_json(capas)}
    c, vistas = _client_con(httpx.Response(200, json=body))
    r = c.obtener_capas()
    assert r.version == "v1"
    assert r.actualizado is True
    assert r.capas == capas
    assert "version" not in vistas[0].url.params


def test_cliente_obtener_capas_envia_version_local_y_acepta_sin_cambios():
    body = {"version": "v1", "actualizado": False, "capas": None}
    c, vistas = _client_con(httpx.Response(200, json=body))
    r = c.obtener_capas("v1")
    assert r.actualizado is False
    assert r.capas is None
    assert vistas[0].url.params["version"] == "v1"


def test_sin_url_configurada_no_se_descarga_nada_y_no_hay_capas(tmp_path):
    descargar = mock.Mock()
    c = capas_mod.CapasCache("", tmp_path / "capas.kml", descargar=descargar, reloj=Reloj())
    with pytest.raises(capas_mod.CapasNoDisponiblesError):
        c.obtener()
    descargar.assert_not_called()


def test_sin_url_pero_con_copia_en_disco_se_usa_la_copia(tmp_path):
    (tmp_path / "capas.kml").write_text(KML_A, encoding="utf-8")
    descargar = mock.Mock()
    c = capas_mod.CapasCache("", tmp_path / "capas.kml", descargar=descargar, reloj=Reloj())
    assert len(c.obtener().capas["PREFERENTE 2"]) == 1
    descargar.assert_not_called()


def test_la_url_del_my_maps_no_viene_escrita_en_el_codigo_publico():
    cfg = ProxyConfig(proxy_token="a" * 64, admin_key="b" * 64)
    assert cfg.capas_kml_url == ""
