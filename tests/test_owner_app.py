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
