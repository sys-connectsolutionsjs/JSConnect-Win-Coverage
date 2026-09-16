"""Verificacion RSA de codigos de activacion.

La llave PUBLICA va embebida aqui. Se genera con:
    python generator/generar.py --generar-llaves

Si PUBLIC_KEY_PEM es el valor por defecto, la activacion queda desactivada
(modo desarrollo).
"""

import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

PLACEHOLDER = b""

PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0xQRUZJqaS5ZQNOPtgvG
FmMc9kafOFL6fdZ4LRXO+h+U225wpU+EXsszcfS7MUoDrHCSRB7PX/WHCu2kmDp2
seevzukWhOJhAPkMDXCb5vQgmqedt7rA7nqe1TAfP4qXzM/3wALYmaCxyH1pw7Cp
dgMU8fbUIJ1uBGFtWCFFygBRE8KMGkYs44QhUNefbGAbZyP3GvWjhjbe317Qgjxt
Kn1WquYMy7sJCa2wdn/+Mgs3GheoerZsrrrnh9xqN9xdRr1NOLm+lLQOxArE3jrA
fgak++6eMGqb5RF2mf+UfNreHAYpQaMUkRLZlAqAdEmkuaafCsIcZJTkEQo+f+AT
ywIDAQAB
-----END PUBLIC KEY-----
"""


def activacion_disponible() -> bool:
    return PUBLIC_KEY_PEM != PLACEHOLDER


def verificar_codigo(huella: str, codigo: str) -> tuple[bool, str]:
    if not activacion_disponible():
        return False, "La activacion no esta configurada en esta version."
    codigo = codigo.strip()
    if not codigo:
        return False, "Pega el codigo de activacion completo."
    try:
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        firma = base64.b64decode(codigo, validate=True)
    except Exception:
        return False, "El codigo esta incompleto o tiene un formato invalido."
    if len(firma) != public_key.key_size // 8:
        return False, "El codigo esta incompleto. Usa el boton Copiar del generador."
    try:
        public_key.verify(firma, huella.encode(), padding.PKCS1v15(), hashes.SHA256())
        return True, "Codigo valido."
    except Exception:
        return False, "El codigo no corresponde a la huella de esta PC."


def validar_codigo(huella: str, codigo: str) -> bool:
    return verificar_codigo(huella, codigo)[0]
