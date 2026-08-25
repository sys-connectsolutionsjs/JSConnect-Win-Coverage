"""Prueba de concurrencia (Fase 1.5): simula uso simultaneo de la cuenta de Win.

Objetivo: comprobar si Win (la ISP) bloquea o avisa cuando varias maquinas usan la
misma cuenta a la vez. Se ejecuta en 4-5 maquinas simultaneamente.

Uso:
    python tools/probar_concurrencia.py [--ciclos N] [--intervalo S] [--log FILE]

    --ciclos      numero de ciclos login->cobertura->score (por defecto 5)
    --intervalo   segundos de espera entre ciclos (por defecto 0)
    --log         archivo de salida con marcas de tiempo (defecto concurrencia.log)
"""

import argparse
import getpass
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

from validator_app.core import api
from validator_app.gui import fields

COORDENADAS_PRUEBA = "-12.087718994493725, -76.98571219979543"  # San Borja (cobertura SI)
DOCUMENTO_PRUEBA = "75020496"  # DNI real de la captura (cobertura SI)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba de concurrencia de la cuenta Win.")
    parser.add_argument("--ciclos", type=int, default=5)
    parser.add_argument("--intervalo", type=float, default=0.0)
    parser.add_argument("--log", default="concurrencia.log")
    args = parser.parse_args()

    usuario = input("Usuario (email): ").strip()
    contrasena = getpass.getpass("Contrasena: ")
    if not usuario or not contrasena:
        print("[ERROR] Usuario y contrasena son obligatorios.")
        return 1

    lat, lon = fields.parse_coordenadas(COORDENADAS_PRUEBA)
    tipo = fields.detectar_tipo_documento(DOCUMENTO_PRUEBA)

    maquina = socket.gethostname()
    log = Path(args.log)
    fallos_seguidos = 0

    print(f"Maquina: {maquina} | ciclos: {args.ciclos} | cuenta: {usuario}")
    print(f"Prueba: login -> cobertura({lat},{lon}) -> score({tipo} {DOCUMENTO_PRUEBA})")
    print("=" * 66)

    for ciclo in range(1, args.ciclos + 1):
        marca = datetime.now().isoformat(timespec="seconds")
        resultado = "OK"
        detalle = ""
        try:
            cliente = api.obtener_cliente().login(usuario, contrasena)
            cobertura = cliente.validar_cobertura(lat, lon)
            if cobertura["hay_cobertura"]:
                score = cliente.validar_score(
                    tipo, DOCUMENTO_PRUEBA, lat, lon, cobertura=cobertura["cobertura"]
                )
                detalle = f"cobertura={cobertura['cobertura']} score={score['valor']}"
            else:
                detalle = f"cobertura={cobertura['cobertura']} (sin score)"
        except Exception as exc:
            resultado = "FALLO"
            detalle = f"{type(exc).__name__}: {exc}"
            fallos_seguidos += 1
        else:
            fallos_seguidos = 0

        linea = f"{marca}\t{maquina}\t{ciclo}\t{resultado}\t{detalle}"
        print(f"[{ciclo:02}] {resultado}: {detalle}")
        with log.open("a", encoding="utf-8") as fh:
            fh.write(linea + "\n")

        if fallos_seguidos >= 3:
            print("3 fallos seguidos: probable bloqueo o sesion invalida. Deteniendo.")
            break
        if args.intervalo:
            time.sleep(args.intervalo)

    print("=" * 66)
    print(f"Detalle guardado en: {log.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
