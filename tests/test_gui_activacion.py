"""Comprobacion de activacion usada por la ventana principal (sin instanciar Tk)."""

import pytest

from validator_app.gui import main_window

HUELLA = "3A05-5810-F921-AE0C"


def _guardado(monkeypatch, valor):
    monkeypatch.setattr(main_window.activation_state, "leer", lambda: valor)


def _legacy_prohibido():
    raise AssertionError("no debe calcular huellas legacy si la guardada es la actual")


def test_activacion_vigente_con_codigo_valido(monkeypatch):
    _guardado(monkeypatch, {"huella": HUELLA, "codigo": "abc"})
    monkeypatch.setattr(main_window.signer, "validar_codigo", lambda h, c: True)
    assert main_window.activacion_vigente(HUELLA, _legacy_prohibido) == "vigente"


def test_activacion_no_vigente_sin_estado_guardado(monkeypatch):
    _guardado(monkeypatch, None)
    assert main_window.activacion_vigente(HUELLA) is None


def test_activacion_no_vigente_si_la_huella_guardada_es_de_otra_pc(monkeypatch):
    _guardado(monkeypatch, {"huella": "0000-0000-0000-0000", "codigo": "abc"})
    monkeypatch.setattr(main_window.signer, "validar_codigo", lambda h, c: True)
    assert main_window.activacion_vigente(HUELLA, lambda: {"1111-2222-3333-4444"}) is None


def test_activacion_en_transicion_con_huella_legacy_de_la_misma_pc(monkeypatch):
    """Activacion hecha con la huella de versiones anteriores: sigue valida (en
    transicion) y la firma se verifica contra la huella GUARDADA."""
    _guardado(monkeypatch, {"huella": "1111-2222-3333-4444", "codigo": "abc"})
    verificadas = []
    monkeypatch.setattr(
        main_window.signer, "validar_codigo", lambda h, c: verificadas.append(h) or True
    )
    assert (
        main_window.activacion_vigente(HUELLA, lambda: {"1111-2222-3333-4444"}) == "transicion"
    )
    assert verificadas == ["1111-2222-3333-4444"]


def test_activacion_no_vigente_con_codigo_invalido(monkeypatch):
    _guardado(monkeypatch, {"huella": HUELLA, "codigo": "malo"})
    monkeypatch.setattr(main_window.signer, "validar_codigo", lambda h, c: False)
    assert main_window.activacion_vigente(HUELLA, lambda: {HUELLA}) is None


def test_activacion_legacy_con_codigo_invalido_no_vale(monkeypatch):
    _guardado(monkeypatch, {"huella": "1111-2222-3333-4444", "codigo": "malo"})
    monkeypatch.setattr(main_window.signer, "validar_codigo", lambda h, c: False)
    assert main_window.activacion_vigente(HUELLA, lambda: {"1111-2222-3333-4444"}) is None


@pytest.mark.parametrize(
    "escrito, esperado",
    [
        ("192.168.1.50:8080", "http://192.168.1.50:8080"),
        ("  192.168.1.50:8080  ", "http://192.168.1.50:8080"),
        ("http://192.168.1.50:8080", "http://192.168.1.50:8080"),
        ("https://proxy.local:8443/", "https://proxy.local:8443"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalizar_url_proxy(escrito, esperado):
    assert main_window.normalizar_url_proxy(escrito) == esperado


def test_normalizar_url_proxy_acepta_none():
    assert main_window.normalizar_url_proxy(None) == ""


def test_resumir_error_deja_una_sola_linea():
    exc = RuntimeError("fallo\n  de   conexion\r\ncon espacios")
    assert main_window.resumir_error(exc) == "fallo de conexion con espacios"


def test_resumir_error_recorta_los_mensajes_largos():
    resumen = main_window.resumir_error(RuntimeError("x" * 500), limite=40)
    assert len(resumen) == 40 and resumen.endswith("…")


def test_resumir_error_sin_mensaje_usa_el_nombre_de_la_excepcion():
    assert main_window.resumir_error(TimeoutError()) == "TimeoutError"


@pytest.mark.parametrize(
    "valor, rango, riesgo, categoria",
    [
        (0, "SCORE: 0 - 200", "MUY ALTO", "MUY MALO"),
        (200, "SCORE: 0 - 200", "MUY ALTO", "MUY MALO"),
        (201, "SCORE: 201 - 300", "ALTO", "MALO"),
        (300, "SCORE: 201 - 300", "ALTO", "MALO"),
        (301, "SCORE: 301 - 400", "ALTO", "MALO"),
        (400, "SCORE: 301 - 400", "ALTO", "MALO"),
        (401, "SCORE: 401 - 500", "REGULAR", "BUENO"),
        (423, "SCORE: 401 - 500", "REGULAR", "BUENO"),
        (600, "SCORE: 501 - 600", "REGULAR", "BUENO"),
        (601, "SCORE: 601 - 700", "BAJO", "MUY BUENO"),
        (800, "SCORE: 701 - 800", "BAJO", "MUY BUENO"),
        (801, "SCORE: 801 - 900", "MUY BAJO", "EXCELENTE"),
        (862, "SCORE: 801 - 900", "MUY BAJO", "EXCELENTE"),
        (900, "SCORE: 801 - 900", "MUY BAJO", "EXCELENTE"),
        (901, "SCORE: 901 - 999", "MUY BAJO", "EXCELENTE"),
        (999, "SCORE: 901 - 999", "MUY BAJO", "EXCELENTE"),
    ],
)
def test_clasificar_score_bordes(valor, rango, riesgo, categoria):
    r = main_window.clasificar_score(valor)
    assert (r["rango"], r["riesgo"], r["categoria"]) == (rango, riesgo, categoria)


def test_clasificar_score_vendible_solo_por_encima_de_200():
    assert main_window.clasificar_score(200)["vendible"] is False
    assert main_window.clasificar_score(201)["vendible"] is True


def test_clasificar_score_colores_por_nivel():
    c = lambda v: main_window.clasificar_score(v)["color"]  # noqa: E731
    assert c(100) == "#C8102E"
    assert c(250) == c(350) == "#D9480F"
    assert c(450) == c(550) == "#B8860B"
    assert c(650) == c(750) == "#2B8A3E"
    assert c(850) == c(950) == "#1A237E"


@pytest.mark.parametrize("valor", [None, -1, 1000, "abc", 4.5, True])
def test_clasificar_score_invalido_devuelve_none(valor):
    assert main_window.clasificar_score(valor) is None


def test_clasificar_score_acepta_entero_como_texto():
    assert main_window.clasificar_score("423")["rango"] == "SCORE: 401 - 500"


def test_ruta_recurso_en_el_repo():
    assert main_window._ruta_recurso("assets/LogoJSConnectSolutionsLogo.png").exists()
    assert main_window._ruta_recurso("assets/icons/borrador.png").exists()


def test_recortar_margen_blanco_deja_solo_el_dibujo():
    from PIL import Image

    img = Image.new("RGB", (100, 100), (255, 255, 255))
    img.paste((200, 0, 0), (20, 40, 80, 60))
    assert main_window._recortar_margen(img).size == (60, 20)


def test_recortar_margen_imagen_toda_blanca_no_falla():
    from PIL import Image

    img = Image.new("RGB", (50, 50), (255, 255, 255))
    assert main_window._recortar_margen(img).size == (50, 50)


def test_ruta_recurso_empaquetado_usa_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(main_window.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert main_window._ruta_recurso("assets/x.png") == tmp_path / "assets" / "x.png"
