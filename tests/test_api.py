"""Tests del nucleo (validator_app.core.api)."""

import json
from unittest import mock

import pytest

from validator_app.core import api


class FakeResponse:
    def __init__(self, datos=None, status=200):
        self.datos = datos
        self.status_code = status

    def json(self):
        return self.datos


class FakeResponseConBOM:
    """Simula una respuesta cruda (como requests) cuyo texto trae un BOM UTF-8.

    A diferencia de FakeResponse, aqui .json() falla como lo haria requests
    de verdad al toparse con el BOM, y .text expone el texto crudo.
    """

    def __init__(self, texto: str, status=200):
        self.texto = texto
        self.status_code = status
        self.headers = {"Content-Type": "text/html; charset=UTF-8"}

    @property
    def text(self):
        return self.texto

    def json(self):
        raise json.JSONDecodeError("Expecting value", self.texto, 0)


class FakeSesion:
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = []
        self.cookies = {"PHPSESSID": "abc123"}

    def _responder(self, metodo, url, **kwargs):
        self.llamadas.append((metodo, url, kwargs))
        for patron, m, resp in self.respuestas:
            if m == metodo and patron in url:
                return resp
        raise AssertionError(f"no hay respuesta fake para {metodo} {url}")

    def post(self, url, **kwargs):
        return self._responder("post", url, **kwargs)

    def get(self, url, **kwargs):
        return self._responder("get", url, **kwargs)


def _reporte_equifax():
    return {
        "soapBody": {
            "ns3GetReporteOnlineResponse": {
                "ns2ReporteCrediticio": {
                    "Nombre": "REPORTE UNIFICADO DE EQUIFAX",
                    "DatosPrincipales": {
                        "TipoDocumento": "1",
                        "NumeroDocumento": "75020496",
                        "Nombre": "SANCHEZ CHANAME ANGEL HUMBERTO",
                    },
                    "Modulos": {
                        "Modulo": [
                            {
                                "Codigo": "865",
                                "Nombre": "Resumen Flag",
                                "Data": {
                                    "flag": True,
                                    "ns3ResumenFlags": {
                                        "ResumenComportamiento": {
                                            "ResumenDeuda": {
                                                "Periodo": "Junio 2026",
                                                "DeudaTotal": 0,
                                            },
                                            "ResumenScoreHistorico": {
                                                "ScoreActual": {
                                                    "Periodo": "Agosto 2026",
                                                    "Riesgo": "MUY ALTO",
                                                    "MotivoSinScore": None,
                                                },
                                            },
                                        }
                                    },
                                },
                            },
                            {
                                "Codigo": "0",
                                "Nombre": "Score RP3",
                                "Data": {
                                    "ns3ResumenScoreRP3": {
                                        "Puntaje": "423",
                                        "NivelRiesgo": "MUY ALTO",
                                        "Conclusion": "De cada 1000 personas se esperan 4 impagos.",
                                    }
                                },
                            },
                        ]
                    },
                }
            }
        }
    }


def _respuesta_score():
    return {"response": "success", "data": json.dumps(_reporte_equifax())}


def test_tipos_documento():
    assert api.TIPOS_DOCUMENTO["DNI"] == "1"
    assert api.TIPOS_DOCUMENTO["CE"] == "2"
    assert api.TIPOS_DOCUMENTO["RUC"] == "3"


def test_formato_coordenada():
    assert api._formato_coordenada(-11.938907461158038) == "-11.938907461158038"


def test_login_ok():
    sesion = FakeSesion(
        [
            ("acceso.php", "post", FakeResponse([{"response": "success"}])),
            ("operador.php", "get", FakeResponse([{"response": "success"}])),
        ]
    )
    cliente = api.ValidatorAPI()
    with mock.patch("validator_app.core.session.crear_sesion", return_value=sesion):
        cliente.login("usuario@x.pe", "clave")
    metodo, url, kwargs = sesion.llamadas[0]
    assert metodo == "post"
    assert "acceso.php" in url
    assert kwargs["data"]["accion"] == "iniciar_sesion"
    assert kwargs["data"]["username"] == "usuario@x.pe"
    assert kwargs["data"]["password"] == "clave"


def test_login_credenciales_incorrectas():
    sesion = FakeSesion(
        [
            (
                "acceso.php",
                "post",
                FakeResponse([{"response": "warning", "comment": "Credenciales invalidas"}]),
            )
        ]
    )
    cliente = api.ValidatorAPI()
    with (
        mock.patch("validator_app.core.session.crear_sesion", return_value=sesion),
        pytest.raises(api.LoginError),
    ):
        cliente.login("usuario@x.pe", "clave-incorrecta")


def test_login_sin_sesion_activa():
    sesion = FakeSesion(
        [
            ("acceso.php", "post", FakeResponse([{"response": "success"}])),
            ("operador.php", "get", FakeResponse({"response": "error", "comment": "no sesion"})),
        ]
    )
    cliente = api.ValidatorAPI()
    with (
        mock.patch("validator_app.core.session.crear_sesion", return_value=sesion),
        pytest.raises(api.LoginError),
    ):
        cliente.login("usuario@x.pe", "clave")


class FakeHtmlResponse:
    """Respuesta con body HTML (json() falla), como un WAF o pagina de error."""

    def __init__(self, texto="<html>Access denied</html>", status=200):
        self.texto = texto
        self.status_code = status
        self.headers = {"Content-Type": "text/html; charset=UTF-8"}

    def json(self):
        raise ValueError("no JSON")

    @property
    def text(self):
        return self.texto


def _login_html():
    return [
        ("acceso.php", "post", FakeHtmlResponse()),
        ("operador.php", "get", FakeHtmlResponse("<html>blocked</html>")),
    ]


def test_sesion_no_activa_html_incluye_diagnostico():
    sesion = FakeSesion(_login_html())
    cliente = api.ValidatorAPI()
    with (
        mock.patch("validator_app.core.session.crear_sesion", return_value=sesion),
        pytest.raises(api.LoginError) as captura,
    ):
        cliente.login("usuario@x.pe", "clave")
    mensaje = str(captura.value)
    assert "la sesion no quedo activa" in mensaje
    assert "text/html" in mensaje
    assert "200" in mensaje
    assert "<html>" in mensaje


def test_sesion_no_activa_json_incluye_comment():
    sesion = FakeSesion(
        [
            ("acceso.php", "post", FakeResponse([{"response": "success"}])),
            (
                "operador.php",
                "get",
                FakeResponse({"response": "error", "comment": "sesion expirada"}),
            ),
        ]
    )
    cliente = api.ValidatorAPI()
    with (
        mock.patch("validator_app.core.session.crear_sesion", return_value=sesion),
        pytest.raises(api.LoginError) as captura,
    ):
        cliente.login("usuario@x.pe", "clave")
    assert "sesion expirada" in str(captura.value)


def test_verificar_login_http_error_incluye_status():
    resp = FakeHtmlResponse(status=503)
    with pytest.raises(api.LoginError) as captura:
        api.ValidatorAPI._verificar_login(resp)
    assert "503" in str(captura.value)


def test_requiere_sesion():
    cliente = api.ValidatorAPI()
    with pytest.raises(api.APIError):
        cliente.validar_cobertura(-11.95, -77.04)


def test_cobertura_si():
    sesion = FakeSesion(
        [
            (
                "coordenada.php",
                "get",
                FakeResponse(
                    {
                        "response": "success",
                        "cobertura": "SI",
                        "tipo": "HORIZONTAL",
                        "id_celda": "9754",
                        "comment": "Resultado exitoso",
                    }
                ),
            )
        ]
    )
    cliente = api.ValidatorAPI()
    cliente._sesion = sesion
    resultado = cliente.validar_cobertura(-12.087718994493725, -76.98571219979543)
    assert resultado["hay_cobertura"] is True
    assert resultado["cobertura"] == "SI"
    assert resultado["id_celda"] == "9754"
    _, url, kwargs = sesion.llamadas[0]
    assert "coordenada.php" in url
    assert kwargs["params"]["accion"] == "validar_cobertura"
    assert kwargs["params"]["data[latitud]"] == "-12.087718994493725"


def test_cobertura_si_con_bom():
    """Regresion: coordenada.php puede anteponer un BOM UTF-8 al JSON (visto en
    prueba real contra el servidor). requests.json() falla con eso; _json()
    debe recuperarse quitando el BOM antes de rendirse."""
    texto = (
        "﻿"
        '{"response":"success","cobertura":"SI","tipo":"HORIZONTAL",'
        '"id_celda":"8764","comment":"Resultado exitoso"}'
    )
    sesion = FakeSesion([("coordenada.php", "get", FakeResponseConBOM(texto))])
    cliente = api.ValidatorAPI()
    cliente._sesion = sesion
    resultado = cliente.validar_cobertura(-11.956037627741102, -77.04065381800075)
    assert resultado["hay_cobertura"] is True
    assert resultado["id_celda"] == "8764"


def test_cobertura_no():
    sesion = FakeSesion(
        [
            (
                "coordenada.php",
                "get",
                FakeResponse(
                    {
                        "response": "success",
                        "cobertura": "NO",
                        "tipo": "",
                        "id_celda": "",
                        "comment": "Resultado exitoso",
                    }
                ),
            )
        ]
    )
    cliente = api.ValidatorAPI()
    cliente._sesion = sesion
    resultado = cliente.validar_cobertura(-11.93, -77.09)
    assert resultado["hay_cobertura"] is False


def test_score_parsea_reporte():
    resp = FakeResponse(_respuesta_score())
    cliente = api.ValidatorAPI()
    resultado = cliente._parsear_score(resp)
    assert resultado["valor"] == 423
    assert resultado["riesgo"] == "MUY ALTO"
    assert resultado["deuda_total"] == 0
    assert resultado["nombre"] == "SANCHEZ CHANAME ANGEL HUMBERTO"
    assert resultado["documento"] == "75020496"
    assert resultado["valido"] is True


def test_score_parsea_reporte_doble_encodificado():
    """Regresion: el servidor real envia 'data' con DOS capas de json.loads
    (confirmado con diagnostico real, ver ResumenDelDia.md), no una sola como
    asumia el codigo original. _parsear_score debe tolerar la profundidad real
    sin asumir un numero fijo de capas."""
    doble = json.dumps(json.dumps(_reporte_equifax()))
    resp = FakeResponse({"response": "success", "data": doble})
    cliente = api.ValidatorAPI()
    resultado = cliente._parsear_score(resp)
    assert resultado["valor"] == 423
    assert resultado["riesgo"] == "MUY ALTO"
    assert resultado["valido"] is True


def test_score_payload_incluye_documento():
    sesion = FakeSesion([("cliente.php", "post", FakeResponse(_respuesta_score()))])
    cliente = api.ValidatorAPI()
    cliente._sesion = sesion
    resultado = cliente.validar_score("DNI", "75020496", -12.08, -76.98, cobertura="SI")
    assert resultado["valor"] == 423
    _, url, kwargs = sesion.llamadas[0]
    assert "cliente.php" in url
    assert kwargs["data"]["accion"] == "score_cliente"
    assert kwargs["data"]["data[tipo_doc]"] == "1"
    assert kwargs["data"]["data[documento_identidad]"] == "75020496"
    assert kwargs["data"]["data[serv_cobertura]"] == "SI"
    assert kwargs["data"]["data[latitud]"] == "-12.08"
    assert kwargs["data"]["data[distrito]"] == ""


def test_score_error_del_servidor():
    resp = FakeResponse({"response": "error", "comment": "Documento no encontrado"})
    cliente = api.ValidatorAPI()
    with pytest.raises(api.ScoreError):
        cliente._parsear_score(resp)


def test_score_sin_puntaje_es_no_valido():
    reporte = _reporte_equifax()
    credit = reporte["soapBody"]["ns3GetReporteOnlineResponse"]["ns2ReporteCrediticio"]
    for modulo in credit["Modulos"]["Modulo"]:
        modulo["Data"] = {}
    resp = FakeResponse({"response": "success", "data": json.dumps(reporte)})
    cliente = api.ValidatorAPI()
    resultado = cliente._parsear_score(resp)
    assert resultado["valido"] is False
    assert resultado["valor"] is None


def test_validar_flow_con_cobertura():
    sesion = FakeSesion(
        [
            (
                "coordenada.php",
                "get",
                FakeResponse(
                    {
                        "response": "success",
                        "cobertura": "SI",
                        "tipo": "HORIZONTAL",
                        "id_celda": "9754",
                    }
                ),
            ),
            ("cliente.php", "post", FakeResponse(_respuesta_score())),
        ]
    )
    cliente = api.ValidatorAPI()
    cliente._sesion = sesion
    resultado = cliente.validar(-12.08, -76.98, "DNI", "75020496")
    assert resultado["cobertura"]["hay_cobertura"] is True
    assert resultado["score"]["valor"] == 423


def test_validar_sin_cobertura_no_llama_score():
    sesion = FakeSesion(
        [
            (
                "coordenada.php",
                "get",
                FakeResponse(
                    {
                        "response": "success",
                        "cobertura": "NO",
                        "tipo": "",
                        "id_celda": "",
                    }
                ),
            )
        ]
    )
    cliente = api.ValidatorAPI()
    cliente._sesion = sesion
    resultado = cliente.validar(-11.93, -77.09, "DNI", "75020496")
    assert resultado["score"] is None
    assert len(sesion.llamadas) == 1
