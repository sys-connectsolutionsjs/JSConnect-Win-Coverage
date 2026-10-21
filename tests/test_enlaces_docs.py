"""Guardas de los enlaces entre documentos .md (grafo de Obsidian / GitHub).

Los .md se citan entre si con enlaces markdown relativos. Al mover texto entre
carpetas (cierre de AGENTS.md -> docs/historial-agents.md, ResumenDelDia.md ->
resumenes/) las rutas relativas cambian: este test falla si alguna queda rota.
Los snapshots de resumenes/ son inmutables y no se revisan.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXCLUIDAS = {"build", "dist", "dist-nuevo", "node_modules", "venv"}

_ENLACE = re.compile(r"\]\(([^)\s]+?\.md)(?:#[^)]*)?\)")


def _documentos():
    for archivo in sorted(_REPO_ROOT.rglob("*.md")):
        partes = archivo.relative_to(_REPO_ROOT).parts[:-1]
        if any(p.startswith(".") or p in _EXCLUIDAS for p in partes):
            continue
        yield archivo


def test_hay_documentos():
    assert any(_documentos())


def test_enlaces_relativos_a_md_existen():
    rotos = []
    for archivo in _documentos():
        if archivo.parent.name == "resumenes":
            continue
        texto = archivo.read_text(encoding="utf-8")
        for destino in _ENLACE.findall(texto):
            if destino.startswith(("http://", "https://")):
                continue
            if not (archivo.parent / destino).resolve().is_file():
                rotos.append(f"{archivo.relative_to(_REPO_ROOT).as_posix()} -> {destino}")
    assert not rotos, "enlaces rotos:\n" + "\n".join(rotos)


def test_historial_enlaza_cada_snapshot():
    texto = (_REPO_ROOT / "HistorialResumenes.md").read_text(encoding="utf-8")
    enlazados = set(_ENLACE.findall(texto))
    faltan = [
        s.name
        for s in sorted((_REPO_ROOT / "resumenes").glob("*.md"))
        if f"resumenes/{s.name}" not in enlazados
    ]
    assert not faltan, f"HistorialResumenes.md no enlaza: {faltan}"
