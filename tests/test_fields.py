import pytest

from validator_app.gui import fields


def test_parse_coordenadas():
    assert fields.parse_coordenadas("-11.956037627741102, -77.04065381800075") == (
        -11.956037627741102,
        -77.04065381800075,
    )


def test_parse_coordenadas_con_espacios():
    assert fields.parse_coordenadas("-11.956 , -77.040") == (-11.956, -77.040)


def test_parse_coordenadas_invalidas():
    with pytest.raises(ValueError):
        fields.parse_coordenadas("solo-una-coordenada")
    with pytest.raises(ValueError):
        fields.parse_coordenadas("-91.0, -77.0")
    with pytest.raises(ValueError):
        fields.parse_coordenadas("-11.0, -181.0")


def test_detectar_dni():
    assert fields.detectar_tipo_documento("12345678") == "DNI"


def test_detectar_ruc():
    assert fields.detectar_tipo_documento("12345678901") == "RUC"


def test_detectar_carnet_extranjeria():
    assert fields.detectar_tipo_documento("123456789") == "CE"
    assert fields.detectar_tipo_documento("E12345678") == "CE"


def test_detectar_documento_invalido():
    with pytest.raises(ValueError):
        fields.detectar_tipo_documento("1234")
    with pytest.raises(ValueError):
        fields.detectar_tipo_documento("123456789012")
