"""Logica sin interfaz de la consola grafica del owner."""

import pytest

from generator import owner_app


def test_normalizar_huella_acepta_formato_valido():
    assert owner_app.normalizar_huella(" 7f3a-9c21-d04e-b5a8 ") == "7F3A-9C21-D04E-B5A8"


def test_normalizar_huella_rechaza_valor_corto():
    with pytest.raises(ValueError, match="Huella"):
        owner_app.normalizar_huella("corta")


def test_normalizar_huella_rechaza_formato_largo_incorrecto():
    with pytest.raises(ValueError, match="Huella"):
        owner_app.normalizar_huella("ESTA-HUELLA-NO-ES-VALIDA")


def test_estado_servicio_interpreta_running():
    assert owner_app.estado_servicio("STATE              : 4  RUNNING") == "Servicio proxy: activo"


def test_estado_servicio_interpreta_stop():
    assert owner_app.estado_servicio("STATE              : 1  STOPPED") == (
        "Servicio proxy: detenido"
    )


def test_consultar_proxy_sin_permiso_sobre_config_usa_puerto_por_defecto(monkeypatch):
    import validator_app.proxy.config as config

    def sin_permiso(*args, **kwargs):
        raise PermissionError("config.yaml")

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"logged_in": True, "session_alive": True}

    visitadas = []
    monkeypatch.setattr(config, "ProxyConfig", sin_permiso)
    monkeypatch.setattr(
        owner_app.httpx, "get", lambda url, timeout: visitadas.append(url) or Respuesta()
    )

    assert owner_app.consultar_proxy() == "Proxy: operativo; sesion WinForce viva"
    assert visitadas == ["http://127.0.0.1:8080/health"]


def test_consultar_proxy_config_invalida_usa_puerto_por_defecto(monkeypatch):
    """En el .exe empaquetado config.yaml no existe: ProxyConfig() lanza
    ValidationError. La consola debe consultar /health igualmente."""
    import validator_app.proxy.config as config

    def sin_tokens(*args, **kwargs):
        raise ValueError("proxy_token y admin_key son obligatorios")

    visitadas = []

    def sin_respuesta(url, timeout):
        visitadas.append(url)
        raise OSError("sin conexion")

    monkeypatch.setattr(config, "ProxyConfig", sin_tokens)
    monkeypatch.setattr(owner_app.httpx, "get", sin_respuesta)

    assert owner_app.consultar_proxy() == "Proxy: no responde localmente"
    assert visitadas == ["http://127.0.0.1:8080/health"]
