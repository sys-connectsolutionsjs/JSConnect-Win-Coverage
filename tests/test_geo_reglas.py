"""Capas embebidas (KMZ, zonas.txt, json.gz) y reglas completas de venta por zona."""

import gzip
import io
import json
import time
import zipfile

import pytest

from validator_app.core import geo


def cuadro(lat, lon, lado=0.01, nombre=""):
    anillo = (
        (lat, lon),
        (lat + lado, lon),
        (lat + lado, lon + lado),
        (lat, lon + lado),
        (lat, lon),
    )
    return geo.Poligono(anillo, (), nombre)


KML_FOLDER = """<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Folder><name>cobertura_win_2</name>
<Placemark><name>15034-5-1</name><MultiGeometry><Polygon><outerBoundaryIs><LinearRing><coordinates>
-77.10,-12.00,0 -77.10,-11.90,0 -77.00,-11.90,0 -77.00,-12.00,0 -77.10,-12.00,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></MultiGeometry></Placemark>
</Folder></Document></kml>"""

KML_SUELTO = """<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Fraude</name>
<Placemark><name>VMT</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
-77.10,-12.00,0 -77.10,-11.90,0 -77.00,-11.90,0 -77.00,-12.00,0 -77.10,-12.00,0
</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
<Placemark><name>PUNTO</name><Point><coordinates>-77.05,-11.95,0</coordinates></Point></Placemark>
</Document></kml>"""

ZONAS_JS = """
    // === INICIO ===
    var ZONA_F_POLYGONS_DATA = [
        [ // Poligono 0
            [-12.16, -76.94],[-12.17, -76.94],[-12.17, -76.93],[-12.16, -76.94]],
    ];
    var ZONA_PREFERENTE_2_POLYGONS_DATA = [
        [[-12.0, -77.1],[-11.9, -77.1],[-11.9, -77.0],[-12.0, -77.1]],
        [[-12.5, -77.1],[-12.4, -77.1],[-12.4, -77.0],[-12.5, -77.1]]
    ];
    var ZONA_CODIGOS_BLOQUEADOS_POLYGONS_DATA = [
        [[-13.0, -77.1],[-12.9, -77.1],[-12.9, -77.0],[-13.0, -77.1]]
    ];
    function algo() { var lat = 1; }
"""


def test_poligono_calcula_bbox():
    p = cuadro(-12.0, -77.0, 0.01)
    assert p.bbox == (-12.0, -77.0, -11.99, -76.99)


def test_parse_kml_guarda_nombre_del_placemark():
    capas = geo.parse_kml(KML_FOLDER)
    assert capas["cobertura_win_2"][0].nombre == "15034-5-1"


def test_parse_kml_placemarks_sueltos_van_a_la_capa_por_defecto():
    capas = geo.parse_kml(KML_SUELTO, capa_por_defecto="FRAUDE")
    assert list(capas) == ["FRAUDE"]
    assert len(capas["FRAUDE"]) == 1
    assert capas["FRAUDE"][0].nombre == "VMT"


def test_parse_kmz_lee_doc_kml():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("doc.kml", KML_FOLDER)
    capas = geo.parse_kmz(buf.getvalue(), capa_por_defecto="COBERTURA")
    assert len(capas["cobertura_win_2"]) == 1


def test_parse_kmz_sin_kml_lanza_error():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("otro.txt", "x")
    with pytest.raises(ValueError):
        geo.parse_kmz(buf.getvalue())


def test_parse_zonas_js_extrae_las_tres_capas():
    capas = geo.parse_zonas_js(ZONAS_JS)
    assert len(capas["ZONA F"]) == 1
    assert len(capas["PREFERENTE 2"]) == 2
    assert len(capas["CODIGOS BLOQUEADOS"]) == 1
    assert capas["ZONA F"][0].anillo[0] == (-12.16, -76.94)


def test_parse_zonas_js_sin_datos_devuelve_vacio():
    assert geo.parse_zonas_js("var otra = 1;") == {}


def test_guardar_y_cargar_capas_embebidas(tmp_path):
    ruta = tmp_path / "capas.json.gz"
    capas = {"COBERTURA": [cuadro(-12.0, -77.0, 0.01, "P1")]}
    geo.guardar_capas_embebidas(capas, ruta)
    assert geo.cargar_capas_embebidas(ruta) == capas


def test_guardar_redondea_coordenadas(tmp_path):
    ruta = tmp_path / "capas.json.gz"
    p = geo.Poligono(((-12.123456789, -77.987654321), (-12.1, -77.9), (-12.2, -77.8)))
    geo.guardar_capas_embebidas({"X": [p]}, ruta, decimales=6)
    cargado = geo.cargar_capas_embebidas(ruta)
    assert cargado["X"][0].anillo[0] == (-12.123457, -77.987654)


def test_cargar_capas_embebidas_inexistente_o_corrupta_devuelve_vacio(tmp_path):
    assert geo.cargar_capas_embebidas(tmp_path / "no_existe.json.gz") == {}
    mala = tmp_path / "mala.json.gz"
    mala.write_bytes(b"no es gzip")
    assert geo.cargar_capas_embebidas(mala) == {}
    rota = tmp_path / "rota.json.gz"
    rota.write_bytes(gzip.compress(b"{no json"))
    assert geo.cargar_capas_embebidas(rota) == {}


def test_cargar_capas_embebidas_ignora_version_desconocida(tmp_path):
    ruta = tmp_path / "v.json.gz"
    ruta.write_bytes(gzip.compress(json.dumps({"version": 99, "capas": {}}).encode()))
    assert geo.cargar_capas_embebidas(ruta) == {}


def test_combinar_capas_reemplaza_solo_las_reglas_del_my_maps():
    base = {
        "COBERTURA": [cuadro(0, 0)],
        "PREFERENTE 2": [cuadro(1, 1)],
        "CODIGOS BLOQUEADOS": [cuadro(2, 2)],
    }
    remotas = {"PREFERENTE 2": [cuadro(5, 5), cuadro(6, 6)], "COBERTURA": [cuadro(9, 9)]}
    r = geo.combinar_capas(base, remotas)
    assert r["COBERTURA"] == base["COBERTURA"]
    assert len(r["PREFERENTE 2"]) == 2
    assert r["CODIGOS BLOQUEADOS"] == base["CODIGOS BLOQUEADOS"]


def test_combinar_capas_remota_vacia_no_borra_la_base():
    base = {"PREFERENTE 2": [cuadro(1, 1)]}
    assert geo.combinar_capas(base, {"PREFERENTE 2": []}) == base


@pytest.fixture
def capas():
    return {
        "COBERTURA": [cuadro(-12.00, -77.00, 0.01, "15034-5-1")],
        "FRAUDE": [cuadro(-12.20, -77.20, 0.01, "VMT")],
        "CODIGOS BLOQUEADOS": [cuadro(-12.40, -77.40, 0.01)],
        "PREFERENTE 2": [cuadro(-11.90, -77.00, 0.01)],
        "ZONA F": [cuadro(-12.60, -77.60, 0.01)],
    }


def test_dentro_de_fraude_bloquea_aunque_haya_cobertura(capas):
    r = geo.decidir_venta(-12.195, -77.195, True, capas)
    assert r.estado == geo.BLOQUEADA
    assert r.score_minimo is None


def test_dentro_de_codigos_bloqueados_bloquea(capas):
    assert geo.decidir_venta(-12.395, -77.395, True, capas).estado == geo.BLOQUEADA


def test_fraude_cercana_solo_avisa(capas):
    # a ~100 m al sur del borde del cuadro de fraude (-12.20)
    r = geo.decidir_venta(-12.2009, -77.195, True, capas)
    assert r.estado == geo.VENDER
    assert any("fraude" in a.lower() for a in r.avisos)


def test_fraude_lejana_no_avisa(capas):
    r = geo.decidir_venta(-12.205, -77.195, True, capas)
    assert not any("fraude" in a.lower() for a in r.avisos)


def test_si_winforce_dice_no_nunca_es_vender_aunque_el_mapa_lo_cubra(capas):
    r = geo.decidir_venta(-11.995, -76.995, False, capas)
    assert r.estado == geo.EXTENSIBLE
    assert r.distancia_m == 0
    assert r.proyecto == "15034-5-1"
    assert any("winforce" in a.lower() for a in r.avisos)


def test_si_winforce_dice_si_vende_aunque_el_mapa_no_lo_cubra(capas):
    r = geo.decidir_venta(-11.50, -76.50, True, capas)
    assert r.estado == geo.VENDER


def test_extensible_a_150_m_trae_distancia_y_proyecto(capas):
    # borde sur de la cobertura en -12.00; 0.00135 grados ~ 150 m
    r = geo.decidir_venta(-12.00135, -76.995, False, capas)
    assert r.estado == geo.EXTENSIBLE
    assert r.distancia_m == pytest.approx(150, abs=5)
    assert r.proyecto == "15034-5-1"
    assert any("doble v" in a.lower() for a in r.avisos)


def test_a_400_m_ya_no_es_extensible(capas):
    r = geo.decidir_venta(-12.0036, -76.995, False, capas)
    assert r.estado == geo.SIN_COBERTURA
    assert r.distancia_m is None


def test_extensible_respeta_el_radio_configurable(capas):
    r = geo.decidir_venta(-12.0036, -76.995, False, capas, radio_m=500)
    assert r.estado == geo.EXTENSIBLE


def test_score_minimo_401_en_preferente_tambien_en_extensible(capas):
    zona = {
        **capas,
        "COBERTURA": [cuadro(-11.9, -77.0)],
        "PREFERENTE 2": [cuadro(-11.92, -77.02, 0.05)],
    }
    r = geo.decidir_venta(-11.90135, -76.995, False, zona)
    assert r.estado == geo.EXTENSIBLE
    assert r.score_minimo == 401


def test_zona_f_es_informativa(capas):
    r = geo.decidir_venta(-12.595, -77.595, True, capas)
    assert r.estado == geo.VENDER
    assert r.score_minimo == 201
    assert any("zona f" in a.lower() for a in r.avisos)


def test_decidir_venta_con_miles_de_poligonos_es_rapido():
    polis = [cuadro(-12.5 + (i % 60) * 0.01, -77.5 + (i // 60) * 0.01, 0.005) for i in range(3400)]
    capas = {"COBERTURA": polis}
    t = time.perf_counter()
    for _ in range(5):
        geo.decidir_venta(-12.2, -77.2, False, capas)
    assert (time.perf_counter() - t) / 5 < 0.25


def test_cargar_capas_embebidas_encuentra_el_archivo_dentro_del_exe(tmp_path, monkeypatch):
    destino = tmp_path / "validator_app" / "data"
    capas = {"COBERTURA": [cuadro(-12.0, -77.0, 0.01, "P1")]}
    geo.guardar_capas_embebidas(capas, destino / "capas.json.gz")
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
    cargadas = geo.cargar_capas_embebidas()
    assert cargadas["COBERTURA"][0].nombre == "P1"


def test_capas_en_punto_lista_todas_las_capas_que_lo_contienen(capas):
    zona = {
        **capas,
        "ZONA F": [cuadro(-12.20, -77.20, 0.01)],  # igual que FRAUDE, como en los datos reales
    }
    assert geo.capas_en_punto(-12.195, -77.195, zona) == ("FRAUDE", "ZONA F")
    assert geo.capas_en_punto(-11.995, -76.995, zona) == ("COBERTURA",)
    assert geo.capas_en_punto(-10.0, -70.0, zona) == ()


def test_capas_visibles_solo_filtra_el_dibujo_y_no_toca_el_original(capas):
    copia = dict(capas)
    r = geo.capas_visibles(capas, {"FRAUDE", "ZONA F"})
    assert set(r) == {"FRAUDE", "ZONA F"}
    assert capas == copia
    assert geo.capas_visibles(capas, set()) == {}


def test_la_decision_no_depende_de_que_capas_se_vean(capas):
    completa = geo.decidir_venta(-12.195, -77.195, True, capas)
    solo_zona_f = geo.decidir_venta(-12.195, -77.195, True, capas)  # la decision nunca filtra
    assert completa == solo_zona_f
    assert completa.estado == geo.BLOQUEADA


def test_sin_respuesta_de_winforce_la_zona_bloqueada_sigue_bloqueada(capas):
    r = geo.decidir_venta(-12.195, -77.195, None, capas)
    assert r.estado == geo.BLOQUEADA
    assert "FRAUDE" in r.capas


def test_sin_respuesta_de_winforce_se_dan_las_condiciones_de_venta(capas):
    r = geo.decidir_venta(-11.50, -77.08, None, capas)
    assert r.estado == geo.SIN_CONFIRMAR
    assert r.score_minimo == 201
    assert any("sin confirmar" in a.lower() for a in r.avisos)


def test_sin_respuesta_de_winforce_preferente_2_exige_401(capas):
    r = geo.decidir_venta(-11.895, -76.995, None, capas)
    assert r.estado == geo.SIN_CONFIRMAR
    assert r.score_minimo == 401
    assert "PREFERENTE 2" in r.capas


def test_sin_respuesta_de_winforce_referencia_del_mapa_de_cobertura(capas):
    dentro = geo.decidir_venta(-11.995, -76.995, None, capas)
    assert any("cubierto" in a.lower() for a in dentro.avisos)
    cerca = geo.decidir_venta(-12.00135, -76.995, None, capas)
    assert cerca.distancia_m == pytest.approx(150, abs=5)
    assert any("150 m" in a for a in cerca.avisos)
    lejos = geo.decidir_venta(-12.0036, -76.995, None, capas)
    assert lejos.distancia_m is None
    assert any("no muestra cobertura" in a.lower() for a in lejos.avisos)
