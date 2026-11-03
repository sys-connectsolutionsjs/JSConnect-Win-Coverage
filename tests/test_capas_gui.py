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


def test_plan_score_sin_confirmar_no_pide_score():
    assert zonas.plan_score(_decision(geo.SIN_CONFIRMAR)) == "no"


# --- Tarjetas del resultado (pedido de los asesores 2026-11-03: "mucho texto") ---


def _d(estado, minimo=201, distancia=None, capas=(), en_fraude=False, fraude_m=None):
    return geo.Decision(
        estado, minimo, "m", distancia_m=distancia, capas=capas,
        en_fraude=en_fraude, fraude_m=fraude_m,
    )


@pytest.mark.parametrize(
    ("hay", "decision", "esperado"),
    [
        (True, _d(geo.VENDER), ("✔ Hay cobertura", "", "success")),
        (False, _d(geo.EXTENSIBLE, distancia=0),
         ("▲ Confirma con soporte", "el mapa lo cubre", "warning")),
        (False, _d(geo.EXTENSIBLE, distancia=120.4),
         ("▲ Posible extensión", "a 120 m", "warning")),
        (False, _d(geo.SIN_COBERTURA), ("✖ Sin cobertura", "", "danger")),
        (None, _d(geo.SIN_CONFIRMAR, distancia=0),
         ("▲ Reintenta", "el mapa lo cubre", "warning")),
        (None, _d(geo.SIN_CONFIRMAR, distancia=80),
         ("▲ Reintenta", "cobertura a 80 m", "warning")),
        (None, _d(geo.SIN_CONFIRMAR, distancia=None),
         ("▲ Reintenta", "el mapa no lo cubre", "warning")),
        (None, None, ("—", "sin coordenadas", "secondary")),
    ],
)
def test_tarjeta_cobertura(hay, decision, esperado):
    assert zonas.tarjeta_cobertura(hay, decision) == esperado


@pytest.mark.parametrize(
    ("decision", "esperado"),
    [
        (_d(geo.VENDER), ("Normal", "mín. 201", "info")),
        (_d(geo.VENDER, 401, capas=("PREFERENTE 2",)), ("Preferente 2", "mín. 401", "info")),
        (_d(geo.VENDER, capas=("FRAUDE",), en_fraude=True, fraude_m=0),
         ("Normal", "mín. 201\n⚠ zona de fraude", "warning")),
        (_d(geo.SIN_COBERTURA, fraude_m=150.2),
         ("Normal", "mín. 201\n⚠ fraude a 150 m", "warning")),
        (_d(geo.VENDER, 401, capas=("FRAUDE", "PREFERENTE 2"), en_fraude=True, fraude_m=0),
         ("Preferente 2", "mín. 401\n⚠ zona de fraude", "warning")),
        (_d(geo.BLOQUEADA, None), ("✖ Código bloqueado", "no vender", "danger")),
        (None, ("—", "sin coordenadas", "secondary")),
    ],
)
def test_tarjeta_zona(decision, esperado):
    assert zonas.tarjeta_zona(decision) == esperado


@pytest.mark.parametrize(
    ("kwargs", "esperado"),
    [
        (dict(valor=652, vendible=True, minimo=401),
         ("✔ VENDE", "652 (mín. 401)", "success")),
        (dict(valor=180, vendible=False, minimo=201),
         ("✖ NO VENDE", "rango no vendible", "danger")),
        (dict(valor=350, vendible=True, minimo=401),
         ("✖ NO VENDE", "350 (mín. 401)", "danger")),
        (dict(valor=652, vendible=True, minimo=None), ("✔ VENDE", "652", "success")),
        (dict(motivo="no_consultado", minimo=201),
         ("Necesita 201+", "no se consultó", "secondary")),
        (dict(motivo="pendiente", minimo=401),
         ("Necesita 401+", "pendiente de confirmar", "secondary")),
        (dict(motivo="error", minimo=201), ("▲ Sin score", "reintenta", "warning")),
        (dict(motivo="no_disponible", minimo=201),
         ("▲ Sin score", "puntaje no disponible", "warning")),
        (dict(motivo="bloqueada"), ("No se consulta", "código bloqueado", "secondary")),
        (dict(motivo="sin_documento", minimo=201), ("—", "ingresa un documento", "secondary")),
        (dict(motivo="listo", minimo=201),
         ("Necesita 201+", "pulsa CONSULTAR SCORE", "secondary")),
        (dict(motivo="consultando", minimo=401), ("Consultando…", "", "secondary")),
        (dict(motivo="no_consultado", minimo=None), ("—", "no se consultó", "secondary")),
    ],
)
def test_tarjeta_score(kwargs, esperado):
    assert zonas.tarjeta_score(**kwargs) == esperado


def test_linea_estado_resume_los_errores_en_una_linea():
    from validator_app.proxy.client import ProxySesionCaducadaError

    caducada = ProxySesionCaducadaError("x")
    assert zonas.linea_estado(None, None) == ""
    assert zonas.linea_estado(caducada, None) == (
        "Sesión del proxy caducada · reintenta en 2-3 min"
    )
    # La misma sesion caducada en cobertura y score es un solo aviso.
    assert zonas.linea_estado(caducada, caducada) == zonas.linea_estado(caducada, None)
    assert zonas.linea_estado(RuntimeError("t"), None) == "WinForce no respondió · reintenta"
    assert zonas.linea_estado(None, RuntimeError("t")) == (
        "No se pudo obtener el score · reintenta"
    )


def test_detalle_para_copiar_trae_el_error_exacto_sin_recortar():
    largo = "Respuesta inesperada del servidor " + "x" * 300
    d = _d(geo.SIN_CONFIRMAR, 401, distancia=0, capas=("COBERTURA", "PREFERENTE 2"),
           en_fraude=True, fraude_m=0)
    texto = zonas.detalle_para_copiar(
        fecha="2026-11-03 16:21", version="abc1234", lat=-12.05, lon=-77.04,
        tipo_doc="DNI", num_doc="10412031", hay_cobertura=None, decision=d,
        score_valor=None, rango=None, cobertura_exc=RuntimeError(largo), score_exc=None,
    )
    assert "2026-11-03 16:21" in texto
    assert "abc1234" in texto
    assert "-12.05, -77.04" in texto
    assert "DNI 10412031" in texto
    assert "sin respuesta" in texto
    assert "COBERTURA, PREFERENTE 2" in texto
    assert "zona de fraude" in texto
    assert f"RuntimeError: {largo}" in texto


def test_detalle_para_copiar_sin_errores_ni_coordenadas():
    texto = zonas.detalle_para_copiar(
        fecha="f", version="v", lat=None, lon=None, tipo_doc="RUC", num_doc="20123456789",
        hay_cobertura=None, decision=None, score_valor=652, rango="SCORE: 601 - 700",
        cobertura_exc=None, score_exc=None,
    )
    assert "RUC 20123456789" in texto
    assert "652 (SCORE: 601 - 700)" in texto
    assert "Error" not in texto
