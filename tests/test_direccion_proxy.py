"""Direccion por coordenadas: endpoint /api/direccion, ProxyClient y respaldo OSM."""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from validator_app.core import direccion
from validator_app.proxy import client as pc
from validator_app.proxy import server
from validator_app.proxy.config import ProxyConfig

_TOKEN = "t" * 64
_ADMIN = "a" * 64
GEO = {
    "direccion": "JIRON CARLOS AUGUSTO SALAVERRY 489 BOCANEGRA SECTOR 3",
    "departamento": "CALLAO", "provincia": "CALLAO", "distrito": "CALLAO",
    "fuente": "geofinder", "aproximada": False,
}
OSM = {**GEO, "direccion": "Jirón Salaverry 489", "fuente": "osm", "aproximada": True}


@pytest.fixture
def api(monkeypatch):
    cfg = ProxyConfig(
        proxy_token=_TOKEN, admin_key=_ADMIN, geofinder_basic="QUJD",
        allowed_networks=["10.0.0.0/8"],
    )
    monkeypatch.setattr(server, "get_config", lambda: cfg)
    geo = mock.Mock()
    monkeypatch.setattr(server, "get_geofinder", lambda: geo)
    return TestClient(server.app, client=("10.0.0.5", 5000)), geo


def test_config_geofinder_basic_vacio_por_defecto():
    cfg = ProxyConfig(proxy_token=_TOKEN, admin_key=_ADMIN)
    assert cfg.geofinder_basic == ""


def test_health_informa_si_geofinder_esta_configurado(monkeypatch):
    for basic, esperado in (("QUJD", True), ("", False)):
        cfg = ProxyConfig(
            proxy_token=_TOKEN, admin_key=_ADMIN, geofinder_basic=basic,
            allowed_networks=["10.0.0.0/8"],
        )
        monkeypatch.setattr(server, "get_config", lambda cfg=cfg: cfg)
        fake = mock.Mock()
        fake.get_status.return_value = {"session_age": 1, "logged_in": True, "session_alive": True}
        monkeypatch.setattr(server, "get_proxy_api", lambda fake=fake: fake)
        tc = TestClient(server.app, client=("10.0.0.5", 5000))
        assert tc.get("/health").json()["geofinder"] is esperado


def test_endpoint_exige_token(api):
    tc, _ = api
    assert tc.get("/api/direccion", params={"lat": -12, "lon": -77}).status_code == 401


def test_endpoint_devuelve_direccion(api):
    tc, geo = api
    geo.consultar.return_value = GEO
    r = tc.get(
        "/api/direccion", params={"lat": -12.03, "lon": -77.09}, headers={"X-Proxy-Token": _TOKEN}
    )
    assert r.status_code == 200
    assert r.json() == {"disponible": True, "motivo": "", "direccion": GEO}
    geo.consultar.assert_called_once_with(-12.03, -77.09)


def test_endpoint_no_disponible_es_200_con_motivo(api):
    tc, geo = api
    geo.consultar.side_effect = direccion.DireccionNoDisponible("Geofinder no esta configurado")
    r = tc.get(
        "/api/direccion", params={"lat": -12.03, "lon": -77.09}, headers={"X-Proxy-Token": _TOKEN}
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["disponible"] is False
    assert "no esta configurado" in cuerpo["motivo"]
    assert cuerpo["direccion"] is None


def test_endpoint_valida_rango_de_coordenadas(api):
    tc, _ = api
    r = tc.get("/api/direccion", params={"lat": 200, "lon": 0}, headers={"X-Proxy-Token": _TOKEN})
    assert r.status_code == 422


def _cliente_con(respuesta_json):
    c = pc.ProxyClient("http://p", "tok")
    resp = mock.Mock()
    resp.json.return_value = respuesta_json
    c._request_with_retry = mock.Mock(return_value=resp)
    return c


def test_proxyclient_obtener_direccion_ok():
    c = _cliente_con({"disponible": True, "motivo": "", "direccion": GEO})
    assert c.obtener_direccion(-12.0, -77.0) == GEO
    args, kwargs = c._request_with_retry.call_args
    assert args == ("GET", "/api/direccion")
    assert kwargs["params"] == {"lat": -12.0, "lon": -77.0}
    assert kwargs["max_retries"] == 1


def test_proxyclient_404_es_proxy_desactualizado():
    c = pc.ProxyClient("http://p", "tok")
    c._request_with_retry = mock.Mock(side_effect=pc.ProxyEndpointNoExisteError("404"))
    with pytest.raises(direccion.DireccionNoDisponible, match="anterior"):
        c.obtener_direccion(-12.0, -77.0)


def test_request_404_no_se_reintenta_y_es_tipado():
    c = pc.ProxyClient("http://p", "tok", max_retries=3)
    resp = mock.Mock(status_code=404, text="Not Found")
    c._client = mock.Mock()
    c._client.request.return_value = resp
    with pytest.raises(pc.ProxyEndpointNoExisteError):
        c._request_with_retry("GET", "/api/direccion")
    assert c._client.request.call_count == 1


def test_proxyclient_no_disponible_lanza():
    c = _cliente_con({"disponible": False, "motivo": "sin credencial", "direccion": None})
    with pytest.raises(direccion.DireccionNoDisponible, match="sin credencial"):
        c.obtener_direccion(-12.0, -77.0)


class _ClienteGeofinder:
    def __init__(self, resultado=None, error=None):
        self.resultado, self.error = resultado, error

    def obtener_direccion(self, lat, lon):
        if self.error:
            raise self.error
        return self.resultado


def test_obtener_usa_geofinder_del_proxy_sin_aviso():
    osm = mock.Mock()
    d, aviso = direccion.obtener(_ClienteGeofinder(GEO), -12.0, -77.0, osm=osm)
    assert d == GEO and aviso is None
    osm.assert_not_called()


def test_obtener_respalda_con_osm_y_avisa_si_falla_el_proxy():
    osm = mock.Mock(return_value=OSM)
    cliente = _ClienteGeofinder(error=direccion.DireccionNoDisponible("x"))
    d, aviso = direccion.obtener(cliente, -12.0, -77.0, osm=osm)
    assert d == OSM
    assert "OpenStreetMap" in aviso and "reactivar" in aviso


def test_aviso_incluye_el_motivo_del_proxy_viejo():
    osm = mock.Mock(return_value=OSM)
    cliente = _ClienteGeofinder(
        error=direccion.DireccionNoDisponible("El proxy es de una version anterior")
    )
    _d, aviso = direccion.obtener(cliente, -12.0, -77.0, osm=osm)
    assert "NO es la de WinForce" in aviso
    assert "version anterior" in aviso


def test_obtener_sin_cliente_o_standalone_usa_osm_con_aviso():
    osm = mock.Mock(return_value=OSM)
    d, aviso = direccion.obtener(None, -12.0, -77.0, osm=osm)
    assert d == OSM and aviso
    d, aviso = direccion.obtener(object(), -12.0, -77.0, osm=osm)
    assert d == OSM and aviso


def test_obtener_si_todo_falla_devuelve_none_y_aviso():
    osm = mock.Mock(side_effect=direccion.DireccionNoDisponible("sin red"))
    d, aviso = direccion.obtener(None, -12.0, -77.0, osm=osm)
    assert d is None
    assert "no se pudo" in aviso.lower()


def test_obtener_trata_cualquier_error_del_proxy_como_respaldo():
    osm = mock.Mock(return_value=OSM)
    cliente = _ClienteGeofinder(error=pc.ProxyConnectionError("caido"))
    d, aviso = direccion.obtener(cliente, -12.0, -77.0, osm=osm)
    assert d == OSM and aviso
