"""Pruebas del generador de codigos para el owner."""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from generator import generar
from validator_app.activation import signer


def test_directorio_llaves_empaquetado_usa_la_carpeta_del_exe(tmp_path):
    executable = tmp_path / "JSConnect-Win-Owner.exe"

    assert generar.directorio_llaves(frozen=True, executable=executable) == tmp_path


def test_firmar_codigo_usa_la_llave_indicada(tmp_path, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "private_key.pem"
    private_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(signer, "PUBLIC_KEY_PEM", public_pem)

    codigo = generar.firmar_codigo("7F3A-9C21-D04E-B5A8", private_path)

    assert signer.validar_codigo("7F3A-9C21-D04E-B5A8", codigo) is True


def test_cargar_llave_inexistente_da_error_claro(tmp_path):
    missing = tmp_path / "no-existe.pem"

    try:
        generar.cargar_llave_privada(missing)
    except FileNotFoundError as exc:
        assert str(missing) in str(exc)
    else:
        raise AssertionError("Se esperaba FileNotFoundError")
