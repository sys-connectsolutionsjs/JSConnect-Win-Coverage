"""Pruebas de la activacion RSA offline."""

import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from validator_app.activation import signer


def test_clave_publica_de_produccion_configurada():
    assert signer.activacion_disponible() is True
    public_key = serialization.load_pem_public_key(signer.PUBLIC_KEY_PEM)
    assert public_key.key_size >= 2048


def test_validar_codigo_acepta_firma_correspondiente(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(signer, "PUBLIC_KEY_PEM", public_pem)

    huella = "7F3A-9C21-D04E-B5A8"
    firma = private_key.sign(huella.encode(), padding.PKCS1v15(), hashes.SHA256())

    assert signer.validar_codigo(huella, base64.b64encode(firma).decode()) is True


def test_validar_codigo_rechaza_otra_huella(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(signer, "PUBLIC_KEY_PEM", public_pem)
    firma = private_key.sign(
        b"7F3A-9C21-D04E-B5A8", padding.PKCS1v15(), hashes.SHA256()
    )

    assert signer.validar_codigo("OTRA-HUELLA", base64.b64encode(firma).decode()) is False


def test_diagnostico_detecta_codigo_incompleto():
    ok, mensaje = signer.verificar_codigo("7F3A-9C21-D04E-B5A8", "abc")

    assert ok is False
    assert "incompleto" in mensaje.lower() or "formato" in mensaje.lower()
