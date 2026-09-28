"""Guardas estaticas de los diagramas PlantUML (docs/diagramas/).

No validan el contenido semantico (eso se revisa a mano al cambiar un flujo
importante), solo que no se rompan en silencio: sintaxis minima, que incluyan
el tema compartido y que los nombres de clase citados sigan existiendo en el
codigo real -- un rename futuro debe romper este test, no pudrir el diagrama.
"""

import re
from pathlib import Path

_DIAGRAMAS_DIR = Path(__file__).resolve().parents[1] / "docs" / "diagramas"
_REPO_ROOT = Path(__file__).resolve().parents[1]

_PUML = sorted(_DIAGRAMAS_DIR.glob("*.puml"))
_PUML_CON_STARTUML = [p for p in _PUML if p.name != "_comun.puml"]

_CLASES_CITADAS = {
    "ValidatorAPI": "validator_app/core/api.py",
    "ProxyValidatorAPI": "validator_app/proxy/server.py",
    "ProxyClient": "validator_app/proxy/client.py",
    "OwnerApp": "generator/owner_app.py",
}


def test_hay_al_menos_un_diagrama():
    assert _PUML_CON_STARTUML, "no se encontraron .puml en docs/diagramas/"


def test_cada_diagrama_abre_y_cierra_startuml():
    malos = []
    for archivo in _PUML_CON_STARTUML:
        texto = archivo.read_text(encoding="utf-8")
        if "@startuml" not in texto or "@enduml" not in texto:
            malos.append(archivo.name)
    assert not malos, f"faltan @startuml/@enduml en: {malos}"


def test_cada_diagrama_incluye_el_tema_comun():
    malos = [
        a.name
        for a in _PUML_CON_STARTUML
        if "!include _comun.puml" not in a.read_text(encoding="utf-8")
    ]
    assert not malos, f"falta '!include _comun.puml' en: {malos}"


def test_cada_diagrama_tiene_footer_de_verificacion():
    malos = [
        a.name
        for a in _PUML_CON_STARTUML
        if not re.search(r"^footer .+$", a.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    assert not malos, f"falta 'footer Verificado contra <sha> — <fecha>' en: {malos}"


def test_las_clases_citadas_siguen_existiendo_en_el_codigo():
    faltantes = []
    for clase, ruta_relativa in _CLASES_CITADAS.items():
        ruta = _REPO_ROOT / ruta_relativa
        if not ruta.exists():
            faltantes.append(f"{clase}: no existe {ruta_relativa}")
            continue
        texto = ruta.read_text(encoding="utf-8")
        if not re.search(rf"class {clase}\b", texto):
            faltantes.append(f"{clase}: no se encontro 'class {clase}' en {ruta_relativa}")
    assert not faltantes, "\n".join(faltantes)
