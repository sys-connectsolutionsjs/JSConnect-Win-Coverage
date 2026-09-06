"""Prueba rapida del nucleo contra la API real (Fase 1).

Uso:
    python tools/probar_core.py

Pide usuario y contrasena (no se muestran), coordenadas y un documento de
prueba; ejecuta login -> cobertura -> score e imprime los resultados.
"""

import getpass
import sys
from pathlib import Path

# Permite `python tools/probar_core.py` desde la raiz del repo sin tener
# `validator_app` instalado editable ni exportar PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validator_app.core import api
from validator_app.gui import fields


def main() -> int:
    usuario = input("Usuario (email): ").strip()
    contrasena = getpass.getpass("Contrasena: ")
    if not usuario or not contrasena:
        print("[ERROR] Usuario y contrasena son obligatorios.")
        return 1

    try:
        cliente = api.obtener_cliente().login(usuario, contrasena)
    except api.LoginError as exc:
        print(f"[ERROR LOGIN] {exc}")
        return 1

    print("Login OK (sesion activa).")

    try:
        lat, lon = fields.parse_coordenadas(input("Coordenadas (lat, lon): ").strip())
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"Consultando cobertura en {lat}, {lon} ...")
    cobertura = cliente.validar_cobertura(lat, lon)
    print(
        f"Cobertura: {cobertura['cobertura']} | "
        f"tipo={cobertura['tipo']} | id_celda={cobertura['id_celda']}"
    )
    if not cobertura["hay_cobertura"]:
        print("Sin cobertura: no se valida score.")
        return 0

    numero = input("Documento (DNI/RUC/CE): ").strip()
    try:
        tipo = fields.detectar_tipo_documento(numero)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"Consultando score para {tipo} {numero} ...")
    score = cliente.validar_score(
        tipo, numero, lat, lon, cobertura=cobertura["cobertura"]
    )
    print(f"Score: {score['valor']} | riesgo: {score['riesgo']}")
    if score["nombre"]:
        print(f"Titular: {score['nombre']} ({score['documento']})")
    if score["deuda_total"] is not None:
        print(f"Deuda total: {score['deuda_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
