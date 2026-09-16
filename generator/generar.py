"""Generador de codigos de activacion - SOLO para el encargado autorizado.

Uso:
    python generator/generar.py --generar-llaves
    python generator/generar.py --codigo 7F3A-9C21-D04E-B5A8-1C77

La llave PRIVADA se guarda en generator/private_key.pem (NUNCA se sube al repo).
La llave PUBLICA se imprime por pantalla para pegarla en
validator_app/activation/signer.py (embebida en el .exe).

La app valida el codigo con la llave publica; solo esta herramienta puede firmar.
"""

import argparse
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def directorio_llaves(
    frozen: bool | None = None, executable: Path | None = None
) -> Path:
    if frozen is None:
        frozen = getattr(sys, "frozen", False)
    if frozen:
        return (executable or Path(sys.executable)).resolve().parent
    return Path(__file__).parent


PRIVATE_KEY_FILE = directorio_llaves() / "private_key.pem"


def generar_llaves():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    PRIVATE_KEY_FILE.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    print(f"Llave privada guardada en: {PRIVATE_KEY_FILE}")
    print("Llave publica (pegala en validator_app/activation/signer.py, campo PUBLIC_KEY_PEM):")
    print(public_pem.decode())


def cargar_llave_privada(private_key_file: Path = PRIVATE_KEY_FILE):
    if not private_key_file.exists():
        raise FileNotFoundError(f"No existe la llave privada: {private_key_file}")
    return serialization.load_pem_private_key(private_key_file.read_bytes(), password=None)


def firmar_codigo(huella: str, private_key_file: Path = PRIVATE_KEY_FILE) -> str:
    private_key = cargar_llave_privada(private_key_file)
    firma = private_key.sign(huella.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(firma).decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generar-llaves", action="store_true")
    parser.add_argument("--codigo", help="Huella de la maquina a activar")
    args = parser.parse_args()

    if args.generar_llaves:
        generar_llaves()
    elif args.codigo:
        huella = args.codigo.strip().upper()
        if len(huella) < 10:
            print("La huella parece invalida (formato XXXX-XXXX-XXXX-XXXX).")
            raise SystemExit(1)
        print(f"Codigo de activacion para {huella}:")
        try:
            print(firmar_codigo(huella))
        except FileNotFoundError:
            print("No existe la llave privada. Ejecuta primero: --generar-llaves")
            raise SystemExit(1) from None
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
