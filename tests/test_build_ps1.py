"""Guardas estaticas de build.ps1 y del .gitignore de las capas de terceros."""

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BUILD = RAIZ / "build.ps1"


def test_build_embebe_las_capas_solo_si_existen_y_avisa_si_faltan():
    texto = BUILD.read_text(encoding="utf-8")
    assert r"validator_app\data\capas.json.gz" in texto
    assert "Test-Path $capas" in texto
    assert "Write-Warning" in texto
    assert r"validator_app\data" in texto  # destino dentro del .exe (ver geo._ruta_embebida)


def test_build_empaqueta_los_datos_de_la_libreria_del_mapa():
    texto = BUILD.read_text(encoding="utf-8")
    assert "--collect-data tkintermapview" in texto
    assert "--collect-data customtkinter" in texto


def test_capas_de_terceros_estan_ignoradas_por_git():
    for ruta in ("datos_capas/zonas.txt", "validator_app/data/capas.json.gz"):
        r = subprocess.run(
            ["git", "check-ignore", "-q", ruta], cwd=RAIZ, capture_output=True, check=False
        )
        assert r.returncode == 0, f"{ruta} NO esta en .gitignore (el repo es publico)"
