"""Tests del clasificador de fallos de tools/medir_keepalive.py.

La logica que importa aqui es _clasificar(): decide si un ping fallido apunta a
una sesion muerta o a un hipo transitorio. Clasificar mal es justo lo que hizo
inservibles las corridas v1/v2 (un HTTP 404 se conto como muerte de sesion sin
prueba). Es logica pura, sin red.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import medir_keepalive as mk

from validator_app.core import api


def _err(mensaje, code):
    return api.APIError(mensaje, code)


def test_login_session_es_sesion_muerta():
    exc = api.LoginError("la sesion no quedo activa", "ERR_LOGIN_SESSION")
    assert mk._clasificar(exc) == mk.SESION_MUERTA


def test_html_200_es_sesion_muerta():
    # coordenada.php devolvio la pagina de login en vez de JSON (patron de v2).
    exc = _err(
        "Respuesta inesperada al consultar cobertura. "
        "[HTTP 200 text/html; charset=UTF-8 body='<!DOCTYPE html><html>...login...']",
        "ERR_NETWORK",
    )
    assert mk._clasificar(exc) == mk.SESION_MUERTA


def test_http_404_es_transitorio():
    # El 404 estilo Apache con el que murio v1: NO es prueba de sesion muerta.
    exc = _err(
        "Respuesta inesperada al consultar cobertura. "
        "[HTTP 404 text/html; charset=iso-8859-1 body='<html>Not Found</html>']",
        "ERR_NETWORK",
    )
    assert mk._clasificar(exc) == mk.TRANSITORIO


def test_error_red_es_transitorio():
    exc = _err("timeout", "ERR_NETWORK_TIMEOUT")
    assert mk._clasificar(exc) == mk.TRANSITORIO


def test_5xx_es_transitorio():
    exc = _err("fallo servidor [HTTP 503 text/html]", "ERR_NETWORK")
    assert mk._clasificar(exc) == mk.TRANSITORIO


def test_desconocido_es_otro():
    exc = _err("algo raro sin status", "ERR_UNKNOWN")
    assert mk._clasificar(exc) == mk.OTRO


def test_extraer_status():
    assert mk._extraer_status("cosas [HTTP 404 text/html]") == 404
    assert mk._extraer_status("sin nada") is None


def test_edad_desde_hora_futuro_falla():
    import pytest

    with pytest.raises(ValueError, match="futuro"):
        mk._edad_desde_hora("23:59")


def test_edad_desde_hora_formato_malo():
    import pytest

    with pytest.raises(ValueError, match="HH:MM"):
        mk._edad_desde_hora("nueve y media")
