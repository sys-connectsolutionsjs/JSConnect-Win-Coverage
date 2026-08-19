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

# TODO(Fase 3): pegar aqui la llave publica PEM que imprime --generar-llaves
PUBLIC_KEY_PEM = PLACEHOLDER


def activacion_disponible() -> bool:
    return PUBLIC_KEY_PEM != PLACEHOLDER


def validar_codigo(huella: str, codigo: str) -> bool:
    if not activacion_disponible():
        return False
    try:
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        firma = base64.b64decode(codigo.strip())
        public_key.verify(firma, huella.encode(), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False
