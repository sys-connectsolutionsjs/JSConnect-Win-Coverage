"""Piezas puras que usa la GUI del mapa: geometria de apoyo, carga de capas y textos."""

import json
from unittest import mock

import pytest

from validator_app.core import capas_local, geo
from validator_app.gui import zonas
from validator_app.proxy.client import CapasResult


def cuadro(lat, lon, lado=0.01, nombre=""):
    anillo = (
        (lat, lon),
        (lat + lado, lon),
        (lat + lado, lon + lado),
        (lat, lon + lado),
        (lat, lon),
    )
    return geo.Poligono(anillo, (), nombre)


def test_poligonos_cercanos_solo_devuelve_los_que_cruzan_el_area():
    capas = {
        "COBERTURA": [
            cuadro(-12.00, -77.00, 0.001, "cerca"),
            cuadro(-12.50, -77.50, 0.001, "lejos"),
        ],
        "FRAUDE": [],
    }
    r = geo.poligonos_cercanos(capas, -12.0005, -76.9995, 1000)
    assert [p.nombre for p in r["COBERTURA"]] == ["cerca"]
    assert r["FRAUDE"] == []


def test_circulo_tiene_n_puntos_a_la_distancia_pedida():
    pts = geo.circulo(-12.0, -77.0, 300, n=36)
    assert len(pts) == 36
    d = geo.distancia_a_poligono_m(-12.0, -77.0, geo.Poligono(tuple(pts)))
    assert d == 0
    # el punto mas al norte esta ~300 m del centro
    norte = max(pts, key=lambda p: p[0])
    assert (norte[0] - -12.0) * 111194.9 == pytest.approx(300, abs=2)


CAPAS_JSON = geo.capas_a_json({"PREFERENTE 2": [cuadro(-12.0, -77.0)]})


def test_cargar_capas_sin_proxy_ni_cache_usa_solo_las_embebidas(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {"COBERTURA": [cuadro(0, 0)]})
    r = capas_local.cargar_capas(None, tmp_path / "reglas.json")
    assert list(r) == ["COBERTURA"]


def test_cargar_capas_con_proxy_reemplaza_reglas_y_guarda_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {"PREFERENTE 2": [cuadro(5, 5)]})
    cliente = mock.Mock()
    cliente.obtener_capas.return_value = CapasResult(
        "v1", True, {"PREFERENTE 2": [cuadro(-12.0, -77.0, 0.01, "nueva")]}
    )
    ruta = tmp_path / "reglas.json"
    r = capas_local.cargar_capas(cliente, ruta)
    assert r["PREFERENTE 2"][0].nombre == "nueva"
    assert json.loads(ruta.read_text(encoding="utf-8"))["version"] == "v1"
    cliente.obtener_capas.assert_called_once_with(None)


def test_cargar_capas_sin_cambios_usa_la_cache_local(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {})
    ruta = tmp_path / "reglas.json"
    ruta.write_text(json.dumps({"version": "v1", "capas": CAPAS_JSON}), encoding="utf-8")
    cliente = mock.Mock()
    cliente.obtener_capas.return_value = CapasResult("v1", False, None)
    r = capas_local.cargar_capas(cliente, ruta)
    assert len(r["PREFERENTE 2"]) == 1
    cliente.obtener_capas.assert_called_once_with("v1")


def test_cargar_capas_si_el_proxy_falla_usa_la_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {})
    ruta = tmp_path / "reglas.json"
    ruta.write_text(json.dumps({"version": "v1", "capas": CAPAS_JSON}), encoding="utf-8")
    cliente = mock.Mock()
    cliente.obtener_capas.side_effect = OSError("proxy caido")
    assert len(capas_local.cargar_capas(cliente, ruta)["PREFERENTE 2"]) == 1


def test_cargar_capas_cache_corrupta_se_ignora(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {"COBERTURA": [cuadro(0, 0)]})
    ruta = tmp_path / "reglas.json"
    ruta.write_text("{no json", encoding="utf-8")
    assert list(capas_local.cargar_capas(None, ruta)) == ["COBERTURA"]


def test_cargar_capas_standalone_no_rompe_si_el_cliente_no_tiene_capas(tmp_path, monkeypatch):
    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {"COBERTURA": [cuadro(0, 0)]})
    cliente = object()
    assert list(capas_local.cargar_capas(cliente, tmp_path / "r.json")) == ["COBERTURA"]


def _decision(estado, minimo=201, distancia=None, avisos=()):
    return geo.Decision(estado, minimo, "mensaje", distancia_m=distancia, avisos=avisos)


@pytest.mark.parametrize(
    ("estado", "etiqueta", "estilo"),
    [
        (geo.VENDER, "CON COBERTURA", "success"),
        (geo.EXTENSIBLE, "EXTENSIBLE", "warning"),
        (geo.SIN_COBERTURA, "SIN COBERTURA", "danger"),
        (geo.BLOQUEADA, "ZONA BLOQUEADA", "danger"),
    ],
)
def test_resumen_decision_etiqueta_y_estilo(estado, etiqueta, estilo):
    texto, est = zonas.resumen_decision(_decision(estado, None if estado == geo.BLOQUEADA else 201))
    assert texto.startswith(etiqueta)
    assert est == estilo


def test_resumen_decision_incluye_distancia_y_avisos():
    texto, _ = zonas.resumen_decision(_decision(geo.EXTENSIBLE, 401, 150, ("Aviso uno",)))
    assert "150 m" in texto
    assert "401" in texto
    assert "Aviso uno" in texto


def test_veredicto_score_alcanza_o_no_el_minimo():
    assert zonas.veredicto_score(450, 401) == ("Alcanza el minimo de la zona (401).", True)
    assert zonas.veredicto_score(300, 401) == ("NO alcanza el minimo de la zona (401).", False)
    assert zonas.veredicto_score(201, 201)[1] is True
    assert zonas.veredicto_score(None, 201) is None
    assert zonas.veredicto_score(450, None) is None


@pytest.mark.parametrize(
    ("estado", "plan"),
    [
        (geo.VENDER, "pedir"),
        (geo.EXTENSIBLE, "confirmar"),
        (geo.SIN_COBERTURA, "no"),
        (geo.BLOQUEADA, "no"),
    ],
)
def test_plan_score_segun_la_decision(estado, plan):
    assert zonas.plan_score(_decision(estado)) == plan


def test_capas_cargadas_obtener_espera_a_que_terminen_las_capas_locales(monkeypatch, tmp_path):
    import threading
    import time

    def lenta():
        time.sleep(0.3)
        return {"COBERTURA": [cuadro(0, 0)]}

    monkeypatch.setattr(geo, "cargar_capas_embebidas", lenta)
    carga = capas_local.CapasCargadas()
    threading.Thread(target=carga.cargar, args=(None, tmp_path / "r.json"), daemon=True).start()
    assert carga.listo is False
    assert list(carga.obtener(espera_s=5)) == ["COBERTURA"]
    assert carga.listo is True


def test_capas_cargadas_si_falla_igual_se_libera_con_vacio(monkeypatch, tmp_path):
    def rota():
        raise RuntimeError("disco roto")

    monkeypatch.setattr(geo, "cargar_capas_embebidas", rota)
    carga = capas_local.CapasCargadas()
    carga.cargar(None, tmp_path / "r.json")
    assert carga.listo is True
    assert carga.obtener(espera_s=1) == {}


def test_capas_cargadas_no_espera_a_un_proxy_lento(monkeypatch, tmp_path):
    import threading
    import time

    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {"COBERTURA": [cuadro(0, 0)]})
    proxy_lento = mock.Mock()

    def tarda(version):
        time.sleep(1.0)
        return CapasResult("v2", True, {"PREFERENTE 2": [cuadro(-12.0, -77.0, 0.01, "nueva")]})

    proxy_lento.obtener_capas.side_effect = tarda
    carga = capas_local.CapasCargadas()
    hilo = threading.Thread(
        target=carga.cargar, args=(proxy_lento, tmp_path / "r.json"), daemon=True
    )
    inicio = time.perf_counter()
    hilo.start()
    capas = carga.obtener(espera_s=0.6)
    assert time.perf_counter() - inicio < 0.9  # no espero al proxy
    assert list(capas) == ["COBERTURA"]  # las locales ya estaban
    hilo.join(5)
    assert carga.obtener(0)["PREFERENTE 2"][0].nombre == "nueva"  # luego llegan las reglas


def test_capas_cargadas_si_el_proxy_cae_quedan_las_locales(monkeypatch, tmp_path):
    monkeypatch.setattr(geo, "cargar_capas_embebidas", lambda: {"COBERTURA": [cuadro(0, 0)]})
    proxy = mock.Mock()
    proxy.obtener_capas.side_effect = OSError("proxy caido")
    carga = capas_local.CapasCargadas()
    carga.cargar(proxy, tmp_path / "r.json")
    assert list(carga.obtener(0)) == ["COBERTURA"]


def test_capas_cargadas_si_vence_la_espera_devuelve_vacio_sin_colgarse():
    carga = capas_local.CapasCargadas()
    assert carga.obtener(espera_s=0.05) == {}
    assert carga.listo is False


def test_resumen_decision_sin_confirmar_indica_las_capas_del_punto():
    d = geo.Decision(
        geo.SIN_CONFIRMAR, 401, "m", avisos=("Mapa sin confirmar",), capas=("PREFERENTE 2",)
    )
    texto, estilo = zonas.resumen_decision(d)
    assert texto.startswith("COBERTURA SIN CONFIRMAR")
    assert estilo == "warning"
    assert "Este punto est\u00e1 en: PREFERENTE 2" in texto


def test_plan_score_sin_confirmar_no_pide_score():
    assert zonas.plan_score(_decision(geo.SIN_CONFIRMAR)) == "no"


@pytest.mark.parametrize(
    ("decision", "esperado"),
    [
        (geo.Decision(geo.BLOQUEADA, None, "m"), "No se vende"),
        (geo.Decision(geo.SIN_CONFIRMAR, 401, "m", capas=("PREFERENTE 2",)), "score 401"),
        (geo.Decision(geo.SIN_CONFIRMAR, 201, "m"), "score 201"),
        (
            geo.Decision(geo.VENDER, 201, "m", avisos=("Zona de fraude cercana (a 120 m): x",)),
            "120 m",
        ),
    ],
)
def test_condiciones_de_venta(decision, esperado):
    assert esperado in zonas.condiciones_de_venta(decision)


def test_mensaje_cobertura_no_disponible_incluye_motivo_y_condiciones():
    d = geo.Decision(geo.SIN_CONFIRMAR, 201, "m")
    texto = zonas.mensaje_sin_cobertura("sesion caducada", d)
    assert "No se pudo obtener la informaci\u00f3n de cobertura" in texto
    assert "sesion caducada" in texto
    assert "Del resto de los datos s\u00ed" in texto
    assert "score 201" in texto


def test_motivo_cobertura_distingue_sesion_caducada_de_otros_errores():
    from validator_app.gui import main_window as mw
    from validator_app.proxy.client import ProxySesionCaducadaError

    caducada = mw.motivo_cobertura(ProxySesionCaducadaError("x"))
    assert "caducada" in caducada
    assert "administrador" in caducada
    assert mw.motivo_cobertura(OSError("sin red")) == "sin red"
