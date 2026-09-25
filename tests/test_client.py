"""Tests del cliente HTTP de los agentes (validator_app.proxy.client).

Se centra en el contrato que la Etapa R fija: un 503 del proxy (sesion con
WinForce caducada) es TERMINAL -> ProxySesionCaducadaError sin reintentos.
"""

import json

import httpx
import pytest

from validator_app.proxy import client as pc


def _client_con_respuestas(respuestas: list[httpx.Response]) -> tuple[pc.ProxyClient, list]:
    """ProxyClient cuyo transporte devuelve `respuestas` en orden. La lista que
    tambien se devuelve registra cada peticion vista (para contar reintentos)."""
    vistas: list[httpx.Request] = []
    it = iter(respuestas)

    def handler(request: httpx.Request) -> httpx.Response:
        vistas.append(request)
        return next(it)

    c = pc.ProxyClient(base_url="http://proxy.test", token="t" * 64, max_retries=3)
    c._client = httpx.Client(transport=httpx.MockTransport(handler))
    return c, vistas


def test_503_lanza_sesion_caducada_con_mensaje_accionable():
    body = {"detail": "La sesion del proxy con WinForce caduco. Reintenta en unos minutos.",
            "codigo": "ERR_SESION_CADUCADA", "owner_avisado": True}
    c, vistas = _client_con_respuestas([httpx.Response(503, json=body)])

    with pytest.raises(pc.ProxySesionCaducadaError) as exc:
        c.validar_cobertura(-12.05, -77.03)

    assert "caduc" in str(exc.value).lower()
    assert len(vistas) == 1  # terminal, no reintenta


def test_503_es_ProxyError_pero_no_ProxyServerError():
    """El 503 de sesion caducada NO debe confundirse con un 5xx generico: la GUI
    lo distingue por el tipo para mostrar el mensaje suave, no el dialogo rojo."""
    c, _ = _client_con_respuestas([httpx.Response(503, json={"detail": "x"})])
    with pytest.raises(pc.ProxySesionCaducadaError):
        c.validar_cobertura(-12.05, -77.03)
    assert issubclass(pc.ProxySesionCaducadaError, pc.ProxyError)
    assert not issubclass(pc.ProxySesionCaducadaError, pc.ProxyServerError)


def test_validar_score_sin_coordenadas_manda_null():
    """Validar solo por documento (2026-09-25): lat/lon en None deben viajar
    como null en el body JSON, no reventar armando la peticion."""
    payload = {
        "valor": 423, "riesgo": "MUY ALTO", "conclusion": None, "deuda_total": "0",
        "nombre": "X", "documento": "75020496", "valido": True,
    }
    c, vistas = _client_con_respuestas([httpx.Response(200, json=payload)])

    resultado = c.validar_score("DNI", "75020496", None, None, cobertura="NO")

    assert resultado.valor == 423
    cuerpo = json.loads(vistas[0].content)
    assert cuerpo["lat"] is None
    assert cuerpo["lon"] is None
    assert cuerpo["cobertura"] == "NO"


def test_health_check_parsea_session_alive():
    payload = {"status": "ok", "version": "dev", "session_age": 12,
               "logged_in": True, "session_alive": False}
    c, _ = _client_con_respuestas([httpx.Response(200, json=payload)])

    health = c.health_check()

    assert health.logged_in is True
    assert health.session_alive is False
