"""Smoke-test v2: pings de interaccion REAL con intervalos VARIABLES (y,
opcionalmente, coordenadas rotativas), intentando sostener la sesion
indefinidamente durante el horario laboral.

Historial de corridas (detalle completo en anotaciones.md, "Dos limites de
sesion" / hallazgos del 2026-09-04):
- **v1** (pings de validar_cobertura cada 300s EXACTOS, 1 sola coordenada,
  45 min): sobrevivio hasta los 2100s, murio a los 2400s (40 min) con un
  HTTP 404 generico (no el patron de "HTML de login").
- **v2 primera corrida** (intervalos variables 180-420s, la MISMA
  coordenada de siempre): murio a los 1100s (18 min) -- **antes** que el
  idle-timeout pasivo de Fase 0 (~1155-1350s sin ningun ping) y muy antes
  que v1. Que morir haciendo MAS actividad tome MENOS tiempo que no hacer
  nada es la senal mas fuerte hasta ahora de que no es un timeout mecanico
  simple.

Con 4 sesiones automatizadas seguidas en un par de horas, todas contra la
MISMA coordenada (`-12.073802720229136, -77.03793556536581`), la hipotesis
de trabajo actual es que hay deteccion anti-bot por **query identico
repetido** y/o **actividad automatizada acumulada reciente** -- no solo por
la regularidad del intervalo (que ya se corrigio en v2 y no alcanzo).

**Proxima corrida (pendiente, con lista de coordenadas del usuario)**: usar
`--coords-lista` para rotar entre varias coordenadas reales distintas en vez
de repetir siempre la misma, y dejar pasar tiempo (no encadenar sesiones de
prueba una tras otra) antes de correrla, para no seguir alimentando una
posible deteccion acumulativa.

IMPORTANTE (detalle tecnico no obvio, heredado de la v1): cada ping usa una
instancia NUEVA de ValidatorAPI (no se reutiliza la misma entre pings).
ValidatorAPI tiene su propio guard interno `_session_max_idle = 120`
(segundos, hardcodeado en __init__) que, si se reutiliza la misma instancia y
pasan mas de 120s entre llamadas, lanza un SessionError("Sesion expirada...")
del lado del CLIENTE antes siquiera de tocar el servidor (ver
auto_relogin_if_needed en validator_app/core/api.py). Usar una instancia
nueva por ping (con _last_activity=0 siempre) evita ese falso positivo y mide
el estado REAL de la sesion en el servidor.

No pide usuario/contrasena: se asume que ya iniciaste sesion manualmente en
el navegador (incluyendo el 2FA de Microsoft) y copiaste el valor de la
cookie PHPSESSID (F12 -> Application -> Cookies -> https://appwinforce.win.pe).

Uso (requiere PYTHONPATH=. si validator_app no esta instalado editable):
    python tools/medir_keepalive.py [opciones]

    --intervalo-min S   segundos minimos entre pings (por defecto 180 = 3 min)
    --intervalo-max S   segundos maximos entre pings (por defecto 420 = 7 min)
    --intervalo S       atajo: fija min=max=S (intervalo constante, como la v1)
    --duracion S        segundos totales a sostener la prueba; 0 = sin limite,
                         corre hasta que muera o se corte con Ctrl+C (por
                         defecto 0)
    --coords "lat,lon"      una sola coordenada fija (salta el prompt)
    --coords-lista "lat1,lon1;lat2,lon2;..."  rota entre varias coordenadas al
                         azar en cada ping, en vez de usar siempre la misma
    --log FILE          archivo TSV de salida (por defecto medir_keepalive.log)
"""

import argparse
import getpass
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from validator_app.core import api
from validator_app.gui import fields


def _ping(php_sessid: str, lat: float, lon: float) -> tuple[bool, str]:
    """Un ping de actividad real con una instancia nueva de ValidatorAPI
    (evita el guard interno de 120s idle de una instancia reutilizada)."""
    cliente = api.ValidatorAPI()
    cliente.set_session_cookies({"PHPSESSID": php_sessid})
    try:
        cobertura = cliente.validar_cobertura(lat, lon)
    except api.APIError as e:
        return False, f"{e.code}: {e}"
    return True, f"cobertura={cobertura.get('cobertura')}"


def _parse_coords_lista(texto: str) -> list[tuple[float, float]]:
    coords = []
    for parte in texto.split(";"):
        parte = parte.strip()
        if not parte:
            continue
        coords.append(fields.parse_coordenadas(parte))
    if not coords:
        raise ValueError("--coords-lista no tenia ninguna coordenada valida")
    return coords


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prueba si pings de actividad real con intervalos variables "
        "evitan que muera la sesion, intentando superar el tope absoluto medido en v1."
    )
    parser.add_argument("--intervalo-min", type=float, default=180.0)
    parser.add_argument("--intervalo-max", type=float, default=420.0)
    parser.add_argument("--intervalo", type=float, default=None, help="atajo: min=max=S")
    parser.add_argument("--duracion", type=float, default=0.0, help="0 = sin limite")
    parser.add_argument("--coords", default=None)
    parser.add_argument("--coords-lista", default=None)
    parser.add_argument("--log", default="medir_keepalive.log")
    args = parser.parse_args()

    intervalo_min = args.intervalo_min
    intervalo_max = args.intervalo_max
    if args.intervalo is not None:
        intervalo_min = intervalo_max = args.intervalo
    if intervalo_min > intervalo_max:
        print("[ERROR] --intervalo-min no puede ser mayor que --intervalo-max.")
        return 1

    php_sessid = getpass.getpass("Pega el valor de la cookie PHPSESSID: ").strip()
    if not php_sessid:
        print("[ERROR] Cookie vacia. Cancelado.")
        return 1

    coords_lista: list[tuple[float, float]]
    if args.coords_lista:
        try:
            coords_lista = _parse_coords_lista(args.coords_lista)
        except Exception as e:
            print(f"[ERROR] --coords-lista invalida: {e}")
            return 1
    else:
        coords_texto = args.coords or input("Coordenadas (lat, lon): ").strip()
        try:
            coords_lista = [fields.parse_coordenadas(coords_texto)]
        except Exception as e:
            print(f"[ERROR] Coordenadas invalidas: {e}")
            return 1

    log = Path(args.log)
    print(f"Log: {log.resolve()}")
    print(
        f"Ping cada {intervalo_min:.0f}-{intervalo_max:.0f}s (variable), "
        f"con {len(coords_lista)} coordenada(s), "
        + (
            f"durante {args.duracion:.0f}s ({args.duracion / 60:.1f} min)."
            if args.duracion > 0
            else "sin limite de duracion (Ctrl+C para cortar)."
        )
    )
    print("=" * 66)

    def elegir_coord() -> tuple[float, float]:
        return random.choice(coords_lista)

    lat, lon = elegir_coord()
    ok, detalle = _ping(php_sessid, lat, lon)
    if not ok:
        print(f"[ERROR] La cookie no esta activa desde el primer ping: {detalle}")
        return 1
    print(f"[OK] Ping inicial (0s). coords=({lat},{lon}) {detalle}")
    with log.open("a", encoding="utf-8") as fh:
        marca = datetime.now().isoformat(timespec="seconds")
        fh.write(f"{marca}\t0\t0\tVIVA\t{lat},{lon}\t{detalle}\n")

    transcurrido = 0.0
    while args.duracion <= 0 or transcurrido < args.duracion:
        espera = random.uniform(intervalo_min, intervalo_max)
        time.sleep(espera)
        transcurrido += espera

        lat, lon = elegir_coord()
        ok, detalle = _ping(php_sessid, lat, lon)
        marca = datetime.now().isoformat(timespec="seconds")
        estado = "VIVA" if ok else "MUERTA"
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{marca}\t{transcurrido:.0f}\t{espera:.0f}\t{estado}\t{lat},{lon}\t{detalle}\n")

        if not ok:
            print(
                f"\n[RESULTADO] La sesion murio a los {transcurrido:.0f}s "
                f"({transcurrido / 60:.1f} min) pese a los pings variables."
            )
            print(
                "Conclusion: ni un ping real ni variar el intervalo evitaron la "
                "expiracion. Siguiente paso: repetir con --coords-lista si no se "
                "uso, para descartar deteccion anti-bot por query identico."
            )
            return 0

        print(
            f"[OK] Sesion viva a los {transcurrido:.0f}s "
            f"(espera usada: {espera:.0f}s). coords=({lat},{lon}) {detalle}"
        )

    print(
        f"\n[RESULTADO] La sesion sobrevivio {transcurrido:.0f}s "
        f"({transcurrido / 60:.1f} min) con pings variables ({intervalo_min:.0f}-"
        f"{intervalo_max:.0f}s / {len(coords_lista)} coordenada(s)), superando "
        "tanto los ~1100s de la corrida anterior como los ~2400s de v1."
    )
    print(
        "Conclusion: con este patron (intervalo variable"
        + (" + coordenadas rotativas" if len(coords_lista) > 1 else "")
        + ") SI se puede sostener la sesion mas alla de los topes vistos antes "
        "-- sugiere que esos topes eran deteccion de patron, no un limite duro "
        "de PHP/WinForce."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
