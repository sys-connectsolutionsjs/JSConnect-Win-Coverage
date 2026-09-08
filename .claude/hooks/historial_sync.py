#!/usr/bin/env python3
"""Hook PostToolUse: mantiene la documentacion sincronizada con HistorialResumenes.md.

Se dispara tras cada Edit/Write. Si el archivo tocado es HistorialResumenes.md y
aumento el numero de entradas (`### YYYY-MM-DD`), inyecta un recordatorio para
sincronizar anotaciones.md / PlanesAprobados.md / AGENTS.md (paso 3 de la "Regla
de auto-actualizacion de la documentacion" en AGENTS.md). Cada 3 entradas nuevas
acumuladas, ademas recuerda actualizar README.md.

Es solo un recordatorio (additionalContext): no bloquea el turno ni edita nada.
Cualquier fallo interno termina en exit 0 para no romper la sesion.
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORIAL = ROOT / "HistorialResumenes.md"
STATE = Path(__file__).resolve().parent / "historial_sync_state.local.json"
ENTRY_RE = re.compile(r"^### \d{4}-\d{2}-\d{2}", re.MULTILINE)
DOCS = "anotaciones.md, PlanesAprobados.md y AGENTS.md"


def _read_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(state: dict) -> None:
    with contextlib.suppress(OSError):
        STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _emit(context: str, notice: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        },
        "systemMessage": notice,
    }))


def _touched_historial(payload: dict) -> bool:
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        return False
    try:
        return Path(file_path).resolve() == HISTORIAL.resolve()
    except OSError:
        return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict) or not _touched_historial(payload):
        return 0

    try:
        count = len(ENTRY_RE.findall(HISTORIAL.read_text(encoding="utf-8")))
    except OSError:
        return 0

    state = _read_state()
    last = state.get("last_entry_count")
    readme_base = state.get("readme_baseline_count")

    # Primera ejecucion: sembrar la linea base y no molestar.
    if not isinstance(last, int) or not isinstance(readme_base, int):
        _write_state({"last_entry_count": count, "readme_baseline_count": count})
        return 0

    # Edicion sin entradas nuevas (o se quitaron): solo re-sincronizar la base.
    if count <= last:
        if count != last:
            state["last_entry_count"] = count
            _write_state(state)
        return 0

    nuevas = count - last

    # README: un aviso por cada bloque de 3 entradas nuevas acumuladas.
    readme_due = False
    while count - readme_base >= 3:
        readme_base += 3
        readme_due = True

    _write_state({"last_entry_count": count, "readme_baseline_count": readme_base})

    partes = [
        f"HistorialResumenes.md gano {nuevas} entrada(s) nueva(s) (total {count}). "
        f"Regla de auto-actualizacion de la documentacion (AGENTS.md): revisa y "
        f"sincroniza con esas entradas {DOCS}. En PlanesAprobados.md saca de la "
        f"cola lo ya implementado; en AGENTS.md actualiza Historial, Tareas "
        f"pendientes y el Cierre de sesion. Verifica contra el codigo antes de "
        f"marcar algo como completado."
    ]
    if readme_due:
        partes.append(
            "Ademas se acumularon >=3 entradas nuevas desde la ultima "
            "actualizacion de README.md: revisa README.md y refleja los avances "
            "relevantes (seguridad, funciones, estructura, comandos)."
        )

    notice = f"Doc-sync: {nuevas} entrada(s) nueva(s) en HistorialResumenes.md"
    if readme_due:
        notice += " + toca actualizar README.md"

    _emit(" ".join(partes), notice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
