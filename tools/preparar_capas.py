"""Convierte las fuentes privadas de capas en el archivo que se embebe en el .exe.

Entrada (carpeta `datos_capas/`, GITIGNORED - el repo es publico):
  COBERTURA_JUNIO.kmz  poligonos de cobertura
  zona_fraude.kml      zonas de fraude
  zonas.txt            PREFERENTE 2, CODIGOS BLOQUEADOS y ZONA F

Salida: validator_app/data/capas.json.gz (tambien GITIGNORED).

Uso:  python tools/preparar_capas.py [--datos datos_capas] [--salida RUTA]
"""

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from validator_app.core import geo  # noqa: E402

SALIDA_POR_DEFECTO = RAIZ / "validator_app" / "data" / "capas.json.gz"
ARCHIVOS = ("COBERTURA_JUNIO.kmz", "zona_fraude.kml", "zonas.txt")


def _aplanar(capas: dict) -> list:
    return [poli for polis in capas.values() for poli in polis]


def preparar(datos: Path, salida: Path) -> dict:
    datos = Path(datos)
    faltan = [a for a in ARCHIVOS if not (datos / a).exists()]
    if faltan:
        raise FileNotFoundError(f"Faltan en {datos}: {', '.join(faltan)}")

    capas = {
        geo.CAPA_COBERTURA: _aplanar(geo.parse_kmz((datos / ARCHIVOS[0]).read_bytes())),
        geo.CAPA_FRAUDE: _aplanar(
            geo.parse_kml((datos / ARCHIVOS[1]).read_text(encoding="utf-8"))
        ),
    }
    zonas = geo.parse_zonas_js((datos / ARCHIVOS[2]).read_text(encoding="utf-8", errors="replace"))
    for nombre in (geo.CAPA_PREFERENTE, geo.CAPA_BLOQUEADOS, geo.CAPA_ZONA_F):
        capas[nombre] = zonas.get(nombre, [])

    vacias = [n for n, polis in capas.items() if not polis]
    if vacias:
        raise ValueError(f"Sin poligonos en {', '.join(vacias)}: revisa {', '.join(ARCHIVOS)}")
    geo.guardar_capas_embebidas(capas, salida)
    return {nombre: len(polis) for nombre, polis in capas.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--datos", type=Path, default=RAIZ / "datos_capas")
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO)
    args = parser.parse_args()
    try:
        conteo = preparar(args.datos, args.salida)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    for nombre, cantidad in conteo.items():
        print(f"{nombre:<20} {cantidad:>6} poligonos")
    print(f"Escrito {args.salida} ({args.salida.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
