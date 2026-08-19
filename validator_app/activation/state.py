"""Estado de activacion guardado en %APPDATA% (fuera del .exe)."""

import json
from pathlib import Path

APP_DIR = Path.home() / "AppData" / "Roaming" / "JSConnectWinCoverage"
STATE_FILE = APP_DIR / "activacion.dat"


def guardar(huella: str, codigo: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"huella": huella, "codigo": codigo}), encoding="utf-8")


def leer():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
