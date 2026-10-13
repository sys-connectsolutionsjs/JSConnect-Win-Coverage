import pytest

from validator_app.core import direccion
from validator_app.proxy import geofinder

GEOFINDER = {
    "cod_via": "225081", "nom_via": "66", "tipo_via": "PASAJE", "via": "PASAJE 66",
    "numero": "189", "manzana": None, "lt_muni": None, "ubigeo": "CALLAO / CALLAO / CALLAO",
    "distrito": "CALLAO", "provincia": "CALLAO", "departamen": "CALLAO",
    "nom_hu": "BOCANEGRA SECTOR 2", "hhuu": "ASENTAMIENTO HUMANO BOCANEGRA SECTOR 2",
    "lon_x": "-77.0932923097382", "lat_y": "-12.02501332161986", "zonas": [],
}

NOMINATIM = {
    "display_name": "Jirón Salaverry 489, Bocanegra, Callao, Perú",
    "address": {
        "road": "Jirón Salaverry", "house_number": "489", "neighbourhood": "Bocanegra",
        "city_district": "Callao", "county": "Provincia de Callao", "state": "Callao",
        "country": "Perú",
    },
}


def test_de_geofinder_arma_direccion_detallada():
    r = direccion.de_geofinder(GEOFINDER)
    assert r == {
        "direccion": "PASAJE 66 189 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)",
        "departamento": "CALLAO",
        "provincia": "CALLAO",
        "distrito": "CALLAO",
        "fuente": "geofinder",
        "aproximada": False,
    }


def test_de_geofinder_sin_numero_usa_manzana_y_lote():
    datos = {**GEOFINDER, "numero": None, "manzana": "K", "lt_muni": "12"}
    assert direccion.de_geofinder(datos)["direccion"] == (
        "PASAJE 66 MZ K LT 12 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)"
    )


def test_de_geofinder_sin_datos_devuelve_none():
    assert direccion.de_geofinder({}) is None
    assert direccion.de_geofinder(None) is None
    assert direccion.de_geofinder({"via": None, "nom_hu": None, "distrito": None}) is None


def test_de_nominatim_es_aproximada():
    r = direccion.de_nominatim(NOMINATIM)
    assert r["direccion"] == "Jirón Salaverry 489, Bocanegra (Callao, Callao, Callao)"
    assert r["distrito"] == "Callao"
    assert r["provincia"] == "Callao"
    assert r["departamento"] == "Callao"
    assert r["fuente"] == "osm"
    assert r["aproximada"] is True


def test_de_nominatim_sin_calle_cae_al_nombre_completo():
    datos = {"display_name": "Bocanegra, Callao, Perú", "address": {"state": "Callao"}}
    assert direccion.de_nominatim(datos)["direccion"] == "Bocanegra, Callao, Perú"


def test_de_nominatim_vacio_devuelve_none():
    assert direccion.de_nominatim({}) is None
    assert direccion.de_nominatim({"error": "Unable to geocode"}) is None


class _Resp:
    def __init__(self, estado=200, cuerpo=None):
        self.status_code = estado
        self._cuerpo = cuerpo

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo

    @property
    def text(self):
        return str(self._cuerpo)


class _Http:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def _siguiente(self, metodo, url, kwargs):
        self.llamadas.append((metodo, url, kwargs))
        return self.respuestas.pop(0)

    def get(self, url, **kwargs):
        return self._siguiente("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._siguiente("POST", url, kwargs)


def test_consultar_osm_manda_user_agent_y_parsea():
    http = _Http([_Resp(200, NOMINATIM)])
    r = direccion.consultar_osm(-12.03, -77.09, http=http)
    assert r["fuente"] == "osm"
    _metodo, url, kw = http.llamadas[0]
    assert "nominatim" in url
    assert kw["headers"]["User-Agent"]
    assert kw["params"]["lat"] == -12.03 and kw["params"]["lon"] == -77.09


def test_consultar_osm_sin_resultado_lanza():
    http = _Http([_Resp(200, {"error": "Unable to geocode"})])
    with pytest.raises(direccion.DireccionNoDisponible):
        direccion.consultar_osm(0.0, 0.0, http=http)


def test_consultar_osm_error_http_lanza():
    http = _Http([_Resp(429, {})])
    with pytest.raises(direccion.DireccionNoDisponible):
        direccion.consultar_osm(0.0, 0.0, http=http)


TOKEN = {"access_token": "tok-1", "token_type": "Bearer", "expires_in": 1439}

REF = {
    "tipo_geo": "invertref",
    "direccion": "PASAJE 66 189 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)",
    "lon_x": "-77.0932923097382", "lat_y": "-12.02501332161986",
    "via": "PASAJE 66", "nom_hu": "BOCANEGRA SECTOR 2", "manzana": None,
}


def test_con_ubicacion_arma_el_formato_de_geofinder():
    detalle = "AVENIDA PERU 4298 BOCANEGRA SECTOR 3"
    assert direccion.con_ubicacion(detalle, "CALLAO", "CALLAO", "CALLAO") == (
        "AVENIDA PERU 4298 BOCANEGRA SECTOR 3 (CALLAO, CALLAO, CALLAO)"
    )
    assert direccion.con_ubicacion("CALLE 1 20", "", "LIMA", "LIMA") == "CALLE 1 20"
    assert direccion.con_ubicacion("", "A", "B", "C") == ""


def test_de_geofinder_ref_conserva_el_formato_completo_y_da_el_punto_ajustado():
    r = direccion.de_geofinder_ref(REF)
    assert r["direccion"] == "PASAJE 66 189 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)"
    assert r["detalle"] == "PASAJE 66 189 BOCANEGRA SECTOR 2"
    assert (r["distrito"], r["provincia"], r["departamento"]) == ("CALLAO", "CALLAO", "CALLAO")
    assert r["punto"] == (-12.02501332161986, -77.0932923097382)
    assert r["fuente"] == "geofinder" and r["aproximada"] is False


def test_de_geofinder_ref_orden_distrito_provincia_departamento():
    datos = {**REF, "direccion": "AV LARCO 345 MIRAFLORES (MIRAFLORES, LIMA, LIMA)"}
    r = direccion.de_geofinder_ref(datos)
    assert r["direccion"] == "AV LARCO 345 MIRAFLORES (MIRAFLORES, LIMA, LIMA)"
    assert (r["distrito"], r["provincia"], r["departamento"]) == ("MIRAFLORES", "LIMA", "LIMA")


def test_de_geofinder_ref_sin_parentesis_ni_punto():
    r = direccion.de_geofinder_ref({"direccion": "CALLE 1 20"})
    assert r["direccion"] == "CALLE 1 20"
    assert r["distrito"] == "" and r["punto"] is None
    assert direccion.de_geofinder_ref({}) is None
    assert direccion.de_geofinder_ref({"direccion": ""}) is None


def _flujo_ok():
    return [_Resp(200, TOKEN), _Resp(200, REF), _Resp(200, GEOFINDER)]


def test_geofinder_sin_credencial_lanza_sin_llamar():
    http = _Http([])
    g = geofinder.GeofinderEquifax("", http=http)
    with pytest.raises(direccion.DireccionNoDisponible):
        g.consultar(-12.0, -77.0)
    assert http.llamadas == []


def test_geofinder_sigue_el_flujo_de_winforce():
    http = _Http(_flujo_ok())
    g = geofinder.GeofinderEquifax("QUJD", http=http)
    r = g.consultar(-12.0296812519999, -77.09398235286045)
    assert r["direccion"] == "PASAJE 66 189 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)"
    assert r["fuente"] == "geofinder" and "punto" not in r and "detalle" not in r
    (m1, u1, k1), (m2, u2, k2), (_m3, u3, k3) = http.llamadas
    assert m1 == "POST" and u1.endswith("/v2/oauth/token")
    assert k1["headers"]["Authorization"] == "Basic QUJD"
    assert k1["data"]["grant_type"] == "client_credentials"
    assert k1["data"]["scope"].endswith("/geoapi/nyg/pe")
    # 1.o: coordenadas tal cual, endpoint coordinates-ref (la direccion que ve el asesor)
    assert m2 == "GET" and "/geoapi/nyg/pe/coordinates-ref/v1" in u2
    assert k2["headers"]["Authorization"] == "Bearer tok-1"
    assert k2["params"]["x"] == -77.09398235286045 and k2["params"]["y"] == -12.0296812519999
    # 2.o: el punto AJUSTADO que devolvio el 1.o, endpoint coordinates (distrito, etc.)
    assert "/geoapi/nyg/pe/coordinates/v1" in u3
    assert k3["params"]["x"] == -77.0932923097382 and k3["params"]["y"] == -12.02501332161986


def test_geofinder_usa_el_distrito_del_segundo_endpoint():
    detalle = {**GEOFINDER, "distrito": "LA PERLA", "provincia": "CALLAO", "departamen": "CALLAO"}
    http = _Http([_Resp(200, TOKEN), _Resp(200, REF), _Resp(200, detalle)])
    r = geofinder.GeofinderEquifax("QUJD", http=http).consultar(-12.0, -77.0)
    assert r["distrito"] == "LA PERLA"
    assert r["direccion"] == "PASAJE 66 189 BOCANEGRA SECTOR 2 (LA PERLA, CALLAO, CALLAO)"


def test_geofinder_si_falla_el_segundo_usa_el_parentesis():
    ref = {**REF, "direccion": "AV LARCO 345 MIRAFLORES (MIRAFLORES, LIMA, LIMA)"}
    http = _Http([_Resp(200, TOKEN), _Resp(200, ref), _Resp(500, {})])
    r = geofinder.GeofinderEquifax("QUJD", http=http).consultar(-12.0, -77.0)
    assert r["direccion"] == "AV LARCO 345 MIRAFLORES (MIRAFLORES, LIMA, LIMA)"
    assert (r["distrito"], r["provincia"], r["departamento"]) == ("MIRAFLORES", "LIMA", "LIMA")


def test_geofinder_sin_punto_ajustado_reutiliza_las_coordenadas_originales():
    ref = {"direccion": "CALLE 1 20 (CALLAO, CALLAO, CALLAO)"}
    http = _Http([_Resp(200, TOKEN), _Resp(200, ref), _Resp(200, GEOFINDER)])
    geofinder.GeofinderEquifax("QUJD", http=http).consultar(-12.5, -77.5)
    assert http.llamadas[2][2]["params"]["x"] == -77.5
    assert http.llamadas[2][2]["params"]["y"] == -12.5


def test_geofinder_acepta_el_valor_con_prefijo_basic():
    http = _Http(_flujo_ok())
    geofinder.GeofinderEquifax("Basic QUJD", http=http).consultar(-12.0, -77.0)
    assert http.llamadas[0][2]["headers"]["Authorization"] == "Basic QUJD"


def test_geofinder_reutiliza_el_token_hasta_que_vence():
    ahora = [1000.0]
    http = _Http([*_flujo_ok(), _Resp(200, REF), _Resp(200, GEOFINDER)])
    g = geofinder.GeofinderEquifax("QUJD", http=http, reloj=lambda: ahora[0])
    g.consultar(-12.0, -77.0)
    ahora[0] += 600
    g.consultar(-12.0, -77.0)
    assert [m for m, _u, _k in http.llamadas] == ["POST", "GET", "GET", "GET", "GET"]


def test_geofinder_renueva_el_token_vencido():
    ahora = [1000.0]
    http = _Http([
        *_flujo_ok(),
        _Resp(200, {**TOKEN, "access_token": "tok-2"}), _Resp(200, REF), _Resp(200, GEOFINDER),
    ])
    g = geofinder.GeofinderEquifax("QUJD", http=http, reloj=lambda: ahora[0])
    g.consultar(-12.0, -77.0)
    ahora[0] += 1439
    g.consultar(-12.0, -77.0)
    assert http.llamadas[4][2]["headers"]["Authorization"] == "Bearer tok-2"


def test_geofinder_reintenta_con_token_nuevo_ante_401():
    http = _Http([
        _Resp(200, TOKEN), _Resp(401, {}),
        _Resp(200, {**TOKEN, "access_token": "tok-2"}), _Resp(200, REF), _Resp(200, GEOFINDER),
    ])
    r = geofinder.GeofinderEquifax("QUJD", http=http).consultar(-12.0, -77.0)
    assert r["distrito"] == "CALLAO"
    assert http.llamadas[3][2]["headers"]["Authorization"] == "Bearer tok-2"


def test_geofinder_token_rechazado_lanza():
    http = _Http([_Resp(401, {})])
    with pytest.raises(direccion.DireccionNoDisponible):
        geofinder.GeofinderEquifax("MALA", http=http).consultar(-12.0, -77.0)


def test_geofinder_sin_direccion_en_la_respuesta_lanza():
    http = _Http([_Resp(200, TOKEN), _Resp(200, {})])
    with pytest.raises(direccion.DireccionNoDisponible):
        geofinder.GeofinderEquifax("QUJD", http=http).consultar(-12.0, -77.0)
