import pytest

from validator_app.core import geo

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>PARAMETROS VENTAS</name>
<Folder><name>PREFERENTE 2</name>
<Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
-77.10,-12.00,0 -77.10,-11.90,0 -77.00,-11.90,0 -77.00,-12.00,0 -77.10,-12.00,0
</coordinates></LinearRing></outerBoundaryIs>
<innerBoundaryIs><LinearRing><coordinates>
-77.06,-11.96,0 -77.06,-11.94,0 -77.04,-11.94,0 -77.04,-11.96,0 -77.06,-11.96,0
</coordinates></LinearRing></innerBoundaryIs></Polygon></Placemark>
</Folder>
<Folder><name>CODIGOS BLOQUEADOS</name>
<Placemark><MultiGeometry>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
-77.30,-12.10,0 -77.30,-12.05,0 -77.25,-12.05,0 -77.25,-12.10,0 -77.30,-12.10,0
</coordinates></LinearRing></outerBoundaryIs></Polygon>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
-77.20,-12.10,0 -77.20,-12.05,0 -77.15,-12.05,0 -77.15,-12.10,0 -77.20,-12.10,0
</coordinates></LinearRing></outerBoundaryIs></Polygon>
</MultiGeometry></Placemark>
</Folder>
</Document></kml>"""


@pytest.fixture
def capas():
    return geo.parse_kml(KML)


def test_parse_kml_agrupa_por_carpeta(capas):
    assert set(capas) == {"PREFERENTE 2", "CODIGOS BLOQUEADOS"}
    assert len(capas["PREFERENTE 2"]) == 1
    assert len(capas["CODIGOS BLOQUEADOS"]) == 2


def test_parse_kml_invierte_lon_lat_a_lat_lon(capas):
    lat, lon = capas["PREFERENTE 2"][0].anillo[0]
    assert (lat, lon) == (-12.00, -77.10)


def test_parse_kml_lee_huecos(capas):
    assert len(capas["PREFERENTE 2"][0].huecos) == 1


def test_parse_kml_invalido_lanza_error():
    with pytest.raises(ValueError):
        geo.parse_kml("<no es kml")


def test_punto_dentro_y_fuera(capas):
    poli = capas["PREFERENTE 2"][0]
    assert geo.punto_en_poligono(-11.92, -77.08, poli)
    assert not geo.punto_en_poligono(-11.80, -77.08, poli)


def test_punto_en_hueco_queda_fuera(capas):
    poli = capas["PREFERENTE 2"][0]
    assert not geo.punto_en_poligono(-11.95, -77.05, poli)


def test_distancia_a_poligono_cero_si_esta_dentro(capas):
    assert geo.distancia_a_poligono_m(-11.92, -77.08, capas["PREFERENTE 2"][0]) == 0


def test_distancia_a_poligono_en_metros(capas):
    # 0.001 grados de longitud al este del borde -77.00, a latitud ~ -11.95 -> ~108.9 m
    d = geo.distancia_a_poligono_m(-11.95, -76.999, capas["PREFERENTE 2"][0])
    assert d == pytest.approx(108.9, abs=2)


def test_decidir_venta_bloqueada_gana_a_todo(capas):
    r = geo.decidir_venta(-12.07, -77.27, True, capas)
    assert r.estado == geo.BLOQUEADA
    assert r.score_minimo is None


def test_decidir_venta_bloqueada_en_segundo_poligono_del_multi(capas):
    assert geo.decidir_venta(-12.07, -77.17, True, capas).estado == geo.BLOQUEADA


def test_decidir_venta_preferente_exige_401(capas):
    r = geo.decidir_venta(-11.92, -77.08, True, capas)
    assert r.estado == geo.VENDER
    assert r.score_minimo == 401


def test_decidir_venta_zona_normal_exige_201(capas):
    r = geo.decidir_venta(-11.50, -77.08, True, capas)
    assert r.estado == geo.VENDER
    assert r.score_minimo == 201


def test_decidir_venta_sin_cobertura_no_vende_pero_informa_minimo(capas):
    r = geo.decidir_venta(-11.92, -77.08, False, capas)
    assert r.estado == geo.SIN_COBERTURA
    assert r.score_minimo == 401


def test_decidir_venta_sin_capas_asume_201():
    r = geo.decidir_venta(-11.92, -77.08, True, {})
    assert r.estado == geo.VENDER
    assert r.score_minimo == 201


def test_decision_trae_mensaje_en_espanol(capas):
    assert "no vender" in geo.decidir_venta(-12.07, -77.27, True, capas).mensaje.lower()
