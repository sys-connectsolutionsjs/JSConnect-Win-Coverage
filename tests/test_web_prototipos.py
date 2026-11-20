"""Prototipos de interfaz web (HTML/CSS/JS): estructura, accesibilidad y fidelidad con la app.

Los datos de ejemplo de la galeria se comparan con lo que calculan `gui/zonas.py`,
`gui/ficha.py` y `gui/main_window.py`, para que los prototipos no se alejen de los
textos reales de la aplicacion.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from validator_app.core import geo
from validator_app.gui import ficha, main_window, zonas

RAIZ = Path(__file__).resolve().parents[1] / "validator_app" / "web" / "prototipos"
VARIANTES = ("bento", "panel", "pasos", "compacta", "protagonista")
COMUN = ("tokens.css", "base.css", "datos.js", "nucleo.js")
PAGINAS = ("index.html", *(f"{v}/index.html" for v in VARIANTES))
CON_TRANSICIONES_DE_VISTA = ("bento", "panel", "pasos", "protagonista")

FECHA = "2026-11-20 10:30"
VERSION = "prototipo"


def _leer(relativa: str) -> str:
    return (RAIZ / relativa).read_text(encoding="utf-8")


def _decision(estado, minimo, mensaje, **extra):
    return geo.Decision(estado=estado, score_minimo=minimo, mensaje=mensaje, **extra)


def _detalle(decision, hay_cobertura, valor, cobertura_exc=None):
    rango = main_window.clasificar_score(valor)["rango"] if valor is not None else None
    return zonas.detalle_para_copiar(
        fecha=FECHA, version=VERSION, lat=-12.0, lon=-77.0, tipo_doc="DNI", num_doc="00000001",
        hay_cobertura=hay_cobertura, decision=decision, score_valor=valor, rango=rango,
        cobertura_exc=cobertura_exc, score_exc=None,
    )


def _vendible(valor):
    return main_window.clasificar_score(valor)["vendible"]


def esperado() -> dict:
    """Lo que la app muestra para cada caso de ejemplo de `comun/datos.js`."""
    normal = _decision(geo.VENDER, 201, "Con cobertura. Score minimo para vender: 201.")
    preferente = _decision(
        geo.VENDER, 401, "Con cobertura. Score minimo para vender: 401.",
        capas=(geo.CAPA_PREFERENTE,), en_fraude=True,
    )
    extensible = _decision(
        geo.EXTENSIBLE, 201,
        "Sin cobertura en el punto, pero hay cobertura a 120 m (proyecto PROYECTO EJEMPLO). "
        "Se puede extender el servicio desde ahi. Score minimo en la zona: 201.",
        distancia_m=120.0, proyecto="PROYECTO EJEMPLO",
    )
    bloqueado = _decision(
        geo.BLOQUEADA, None, "Codigo bloqueado: no vender, no consultar el score.",
        capas=(geo.CAPA_BLOQUEADOS,),
    )
    sin_confirmar = _decision(
        geo.SIN_CONFIRMAR, 201,
        "No se pudo confirmar la cobertura con WinForce. Score minimo en la zona: 201.",
        distancia_m=0,
    )
    timeout = TimeoutError("Timeout tras 5.0s conect / 30.0s lectura")
    return {
        "inicial": {
            "cobertura": zonas.tarjeta_cobertura(None, None),
            "zona": zonas.tarjeta_zona(None),
            "score": zonas.tarjeta_score(motivo="sin_documento"),
        },
        "vende": {
            "cobertura": zonas.tarjeta_cobertura(True, normal),
            "zona": zonas.tarjeta_zona(normal),
            "score": zonas.tarjeta_score(612, _vendible(612), 201),
            "detalle": _detalle(normal, True, 612),
        },
        "no_vende": {
            "cobertura": zonas.tarjeta_cobertura(True, preferente),
            "zona": zonas.tarjeta_zona(preferente),
            "score": zonas.tarjeta_score(380, _vendible(380), 401),
            "detalle": _detalle(preferente, True, 380),
        },
        "extensible": {
            "cobertura": zonas.tarjeta_cobertura(False, extensible),
            "zona": zonas.tarjeta_zona(extensible),
            "score": zonas.tarjeta_score(None, None, 201, "pendiente"),
            "detalle": _detalle(extensible, False, None),
            "mensaje": extensible.mensaje,
            "score_confirmado": zonas.tarjeta_score(534, _vendible(534), 201),
            "detalle_confirmado": _detalle(extensible, False, 534),
        },
        "bloqueado": {
            "cobertura": zonas.tarjeta_cobertura(True, bloqueado),
            "zona": zonas.tarjeta_zona(bloqueado),
            "score": zonas.tarjeta_score(motivo="bloqueada"),
            "detalle": _detalle(bloqueado, True, None),
        },
        "error_cobertura": {
            "cobertura": zonas.tarjeta_cobertura(None, sin_confirmar),
            "zona": zonas.tarjeta_zona(sin_confirmar),
            "score": zonas.tarjeta_score(None, None, 201, "no_consultado"),
            "detalle": _detalle(sin_confirmar, None, None, cobertura_exc=timeout),
            "aviso": zonas.linea_estado(timeout, None),
        },
    }


def _literal(tarjeta: tuple) -> str:
    titulo, nota, estilo = tarjeta
    texto = lambda valor: json.dumps(valor, ensure_ascii=False)  # noqa: E731
    return f"{{ titulo: {texto(titulo)}, nota: {texto(nota)}, estilo: {texto(estilo)} }}"


def _pares_de_tarjetas() -> list[tuple[str, str]]:
    pares = []
    for caso, datos in esperado().items():
        for campo in ("cobertura", "zona", "score", "score_confirmado"):
            if campo in datos:
                pares.append((f"{caso}/{campo}", _literal(datos[campo])))
    return pares


def _pares_de_textos() -> list[tuple[str, str]]:
    pares = []
    for caso, datos in esperado().items():
        for campo in ("detalle", "detalle_confirmado", "mensaje", "aviso"):
            if campo in datos:
                pares.append((f"{caso}/{campo}", json.dumps(datos[campo], ensure_ascii=False)))
    return pares


def _fuentes() -> list[Path]:
    return [p for p in RAIZ.rglob("*") if p.suffix in {".html", ".css", ".js"}]


# --- estructura --------------------------------------------------------------


def test_hay_fuentes_web():
    assert _fuentes(), f"no hay HTML/CSS/JS en {RAIZ}"


@pytest.mark.parametrize(
    "relativa",
    [
        "README.md",
        "index.html",
        "galeria.css",
        *(f"comun/{nombre}" for nombre in COMUN),
        *(f"{v}/{archivo}" for v in VARIANTES for archivo in ("index.html", f"{v}.css", f"{v}.js")),
    ],
)
def test_existe_el_archivo(relativa):
    assert (RAIZ / relativa).is_file(), relativa


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_html_basica(pagina):
    html = _leer(pagina)
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert '<html lang="es"' in html
    assert '<meta charset="utf-8">' in html.lower()
    assert 'name="viewport"' in html
    assert '<meta name="color-scheme" content="light dark">' in html
    assert re.search(r"<title>[^<]+</title>", html)


def test_la_galeria_enlaza_las_cinco_variantes():
    galeria = _leer("index.html")
    for variante in VARIANTES:
        assert f'href="{variante}/index.html"' in galeria, variante


def test_sin_recursos_externos():
    for fuente in _fuentes():
        assert not re.search(r"https?://", fuente.read_text(encoding="utf-8")), fuente.name


def test_sin_manejadores_de_eventos_en_linea():
    for pagina in PAGINAS:
        assert not re.search(r"\son[a-z]+\s*=", _leer(pagina)), pagina


@pytest.mark.parametrize("variante", VARIANTES)
def test_la_variante_carga_lo_comun_y_lo_propio_en_orden(variante):
    html = _leer(f"{variante}/index.html")
    orden = [
        "../comun/tokens.css",
        "../comun/base.css",
        f"{variante}.css",
        "../comun/datos.js",
        "../comun/nucleo.js",
        f"{variante}.js",
    ]
    posiciones = [html.find(recurso) for recurso in orden]
    assert all(p >= 0 for p in posiciones), dict(zip(orden, posiciones, strict=True))
    assert posiciones[3:] == sorted(posiciones[3:])


# --- accesibilidad y textos de la app ------------------------------------------


@pytest.mark.parametrize("variante", VARIANTES)
def test_la_variante_tiene_el_formulario_de_la_app_accesible(variante):
    html = _leer(f"{variante}/index.html")
    for fragmento in (
        "<main",
        "<h1",
        "<form",
        'id="formulario"',
        'id="coordenadas"',
        'for="coordenadas"',
        'id="documento"',
        'for="documento"',
        "Coordenadas (latitud, longitud):",
        "Documento (DNI/RUC/CE):",
        "VALIDAR",
        'type="submit"',
        'role="status"',
        'id="barra-prueba"',
        "data-tipo-documento",
    ):
        assert fragmento in html, f"{variante}: falta {fragmento}"


@pytest.mark.parametrize("variante", VARIANTES)
def test_la_variante_muestra_las_tarjetas_y_la_ficha(variante):
    html = _leer(f"{variante}/index.html")
    for texto in ("Cobertura", "Zona", "Score", "Datos del cliente", "Ver detalle"):
        assert texto in html, f"{variante}: falta {texto}"


def test_los_dialogos_comparten_los_textos_de_la_app():
    nucleo = _leer("comun/nucleo.js")
    for texto in (
        "Detalle de la validación",
        "Copiar para WhatsApp",
        "Consultar score",
        "El score gasta una consulta de Equifax. ¿Consultarlo de todas formas?",
        "Ingresa coordenadas y/o un documento.",
    ):
        assert texto in nucleo, texto
    assert 'closedby="any"' in nucleo
    assert "role=\"dialog\"" not in nucleo
    assert "aria-modal" not in nucleo


def test_los_niveles_del_score_coinciden_con_la_app():
    datos = _leer("comun/datos.js")
    for tope, riesgo, categoria, color in main_window._TABLA_SCORE:
        patron = (
            rf'tope:\s*{tope},\s*riesgo:\s*"{re.escape(riesgo)}",\s*'
            rf'categoria:\s*"{re.escape(categoria)}",\s*color:\s*"{re.escape(color)}"'
        )
        assert re.search(patron, datos), (tope, riesgo, categoria, color)
    assert main_window._COLOR_INACTIVO in datos


def test_los_colores_del_score_estan_en_los_tokens():
    tokens = _leer("comun/tokens.css").lower()
    for *_, color in main_window._TABLA_SCORE:
        assert color.lower() in tokens, color


def test_las_etiquetas_de_la_ficha_coinciden_con_la_app():
    datos = _leer("comun/datos.js")
    for etiqueta in ficha.ETIQUETAS:
        assert json.dumps(etiqueta, ensure_ascii=False) in datos, etiqueta


@pytest.mark.parametrize(("nombre", "literal"), _pares_de_tarjetas())
def test_las_tarjetas_de_ejemplo_coinciden_con_zonas_py(nombre, literal):
    assert literal in _leer("comun/datos.js"), nombre


@pytest.mark.parametrize(("nombre", "texto"), _pares_de_textos())
def test_los_textos_de_ejemplo_coinciden_con_la_app(nombre, texto):
    assert texto in _leer("comun/datos.js"), nombre


def test_los_documentos_de_ejemplo_son_ficticios():
    documentos = re.findall(r'(?:documento:|DOCUMENTO =)\s*"([^"]*)"', _leer("comun/datos.js"))
    assert documentos
    assert all(re.fullmatch(r"(0{7}\d)?", d) for d in documentos), documentos


# --- estilos y movimiento -------------------------------------------------------


def test_los_tokens_declaran_esquemas_de_color_y_oklch():
    tokens = _leer("comun/tokens.css")
    assert "color-scheme: light dark" in tokens
    assert "light-dark(" in tokens
    assert "oklch(" in tokens


@pytest.mark.parametrize("css", [f"{v}/{v}.css" for v in VARIANTES] + ["comun/base.css"])
def test_el_css_respeta_el_movimiento_reducido(css):
    texto = _leer(css)
    assert "prefers-reduced-motion" in texto, css
    assert "0.01ms" not in texto, css


def test_la_base_anima_la_capa_superior_y_la_entrada_de_elementos():
    base = _leer("comun/base.css")
    for fragmento in (
        "@starting-style",
        "transition-behavior: allow-discrete",
        "overlay",
        "dialog::backdrop",
        "overscroll-behavior: contain",
        ":focus-visible",
    ):
        assert fragmento in base, fragmento


@pytest.mark.parametrize("variante", CON_TRANSICIONES_DE_VISTA)
def test_las_variantes_con_transiciones_de_vista_las_declaran(variante):
    css = _leer(f"{variante}/{variante}.css")
    assert "view-transition-name" in css
    assert "::view-transition-group" in css


def test_pasos_distingue_la_direccion_de_la_navegacion():
    css = _leer("pasos/pasos.css")
    assert ":active-view-transition-type(forward)" in css
    assert ":active-view-transition-type(backward)" in css
    assert "translate" in css


def test_bento_se_adapta_con_container_queries():
    css = _leer("bento/bento.css")
    assert "container-type: inline-size" in css
    assert "@container" in css
    assert "grid-template-areas" in css


def test_compacta_anima_el_desplegable_con_details_content():
    css = _leer("compacta/compacta.css")
    assert "::details-content" in css
    assert "interpolate-size: allow-keywords" in css


def test_el_nucleo_detecta_las_transiciones_de_vista_antes_de_usarlas():
    nucleo = _leer("comun/nucleo.js")
    assert "startViewTransition" in nucleo
    assert re.search(r"!\s*\w+\.startViewTransition", nucleo)


def test_la_politica_de_navegadores_esta_documentada():
    readme = _leer("README.md")
    assert "Browser Support" in readme
    assert "WebView2" in readme
