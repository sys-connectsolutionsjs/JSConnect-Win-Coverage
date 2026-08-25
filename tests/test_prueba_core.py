"""Tests de la logica del arnes grafico de prueba core (validator_app.gui.prueba_core)."""

from unittest import mock

from validator_app.core import api
from validator_app.gui import prueba_core


class FakeCliente:
    def __init__(self, cobertura=None, score=None, error_login=None):
        self.cobertura = cobertura
        self.score = score
        self.error_login = error_login
        self.logueado = False
        self.usuario_recibido = None
        self.contrasena_recibida = None

    def login(self, usuario, contrasena):
        if self.error_login:
            raise self.error_login
        self.logueado = True
        self.usuario_recibido = usuario
        self.contrasena_recibida = contrasena
        return self

    def validar_cobertura(self, lat, lon):
        return self.cobertura

    def validar_score(self, tipo, numero, lat, lon, cobertura="NO"):
        return self.score


COBERTURA_SI = {
    "hay_cobertura": True,
    "cobertura": "SI",
    "tipo": "HORIZONTAL",
    "id_celda": "9754",
    "comment": "",
}

SCORE_OK = {
    "valor": 423,
    "riesgo": "MUY ALTO",
    "conclusion": None,
    "deuda_total": 0,
    "nombre": "SANCHEZ CHANAME ANGEL HUMBERTO",
    "documento": "75020496",
    "valido": True,
}

COORDS = "-12.087718994493725, -76.98571219979543"


def _ejecutar(cliente, coords=COORDS, documento="75020496"):
    with mock.patch.object(prueba_core.api, "obtener_cliente", return_value=cliente):
        return prueba_core.ejecutar_prueba("usuario@x.pe", "clave", coords, documento)


def test_flujo_ok_con_cobertura():
    lineas = _ejecutar(FakeCliente(cobertura=COBERTURA_SI, score=SCORE_OK))
    texto = "\n".join(lineas)
    assert "Login OK" in texto
    assert "Cobertura: SI | tipo=HORIZONTAL | id_celda=9754" in texto
    assert "Score: 423 | riesgo: MUY ALTO" in texto
    assert "Titular: SANCHEZ CHANAME ANGEL HUMBERTO (75020496)" in texto
    assert "Deuda total: 0" in texto


def test_sin_cobertura_no_consulta_score():
    cliente = FakeCliente(
        cobertura={
            "hay_cobertura": False,
            "cobertura": "NO",
            "tipo": "",
            "id_celda": "",
            "comment": "",
        }
    )
    lineas = _ejecutar(cliente)
    texto = "\n".join(lineas)
    assert "Cobertura: NO" in texto
    assert "Sin cobertura: no se valida score." in texto
    assert "Score:" not in texto


def test_login_incorrecto():
    cliente = FakeCliente(error_login=api.LoginError("Credenciales invalidas"))
    lineas = _ejecutar(cliente)
    texto = "\n".join(lineas)
    assert "[ERROR LOGIN] Credenciales invalidas" in texto
    assert "Login OK" not in texto


def test_coordenadas_invalidas():
    lineas = _ejecutar(FakeCliente(), coords="abc, xyz")
    assert any("[ERROR]" in linea and "coordenadas" in linea.lower() for linea in lineas)


def test_documento_invalido():
    lineas = _ejecutar(FakeCliente(cobertura=COBERTURA_SI), documento="12345")
    assert any("[ERROR]" in linea and "Documento no reconocido" in linea for linea in lineas)


def test_campos_obligatorios():
    with mock.patch.object(prueba_core.api, "obtener_cliente") as _mock:
        lineas = prueba_core.ejecutar_prueba("", "", COORDS, "75020496")
    texto = "\n".join(lineas)
    assert "[ERROR] Usuario y contrasena son obligatorios." in texto


def test_espacios_de_portapapeles_se_recortan():
    cliente = FakeCliente(cobertura=COBERTURA_SI, score=SCORE_OK)
    with mock.patch.object(prueba_core.api, "obtener_cliente", return_value=cliente):
        lineas = prueba_core.ejecutar_prueba(
            " usuario@x.pe ", " clave\n", f" {COORDS} ", " 75020496\n"
        )
    texto = "\n".join(lineas)
    assert "[ERROR" not in texto
    assert cliente.usuario_recibido == "usuario@x.pe"
    assert cliente.contrasena_recibida == "clave"
    assert "Score: 423" in texto
