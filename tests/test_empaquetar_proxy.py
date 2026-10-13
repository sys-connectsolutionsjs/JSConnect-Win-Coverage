"""Guardas del paquete de actualizacion del proxy (sin secretos, solo codigo)."""

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "tools" / "empaquetar_actualizacion_proxy.ps1"

ARCHIVOS_PROHIBIDOS = {
    "config.yaml", "proxy_token.txt", "admin_key.txt", "updates.xml", "capas.json.gz",
    "activacion.dat",
}
EXTENSIONES_PROHIBIDAS = {".pem", ".crx"}
CARPETAS_PROHIBIDAS = {".browser_profile", ".extension_build"}


def test_el_script_existe_y_usa_la_lista_de_git():
    texto = SCRIPT.read_text(encoding="utf-8")
    assert "ls-files" in texto and "--exclude-standard" in texto
    assert "LEEME" in texto
    assert "geofinder_basic" in texto
    assert "JSWinProxy" in texto


def test_la_instruccion_robocopy_no_borra_nada():
    lineas = [
        linea.lower() for linea in SCRIPT.read_text(encoding="utf-8").splitlines()
        if linea.strip().lower().startswith("2. robocopy")
    ]
    assert len(lineas) == 1
    assert "/e" in lineas[0] and "/mir" not in lineas[0] and "/purge" not in lineas[0]


@pytest.mark.skipif(shutil.which("git") is None, reason="git no disponible")
def test_la_lista_de_archivos_no_trae_secretos():
    r = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "validator_app"],
        cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    archivos = [a for a in r.stdout.splitlines() if a.strip()]
    assert any(a.endswith("proxy/server.py") for a in archivos)
    assert any(a.endswith("config.yaml.example") for a in archivos)  # la plantilla si viaja
    for a in archivos:
        partes = Path(a).parts
        assert partes[-1] not in ARCHIVOS_PROHIBIDOS, f"{a} no debe viajar en el paquete"
        assert Path(a).suffix not in EXTENSIONES_PROHIBIDAS, f"{a} no debe viajar"
        assert not CARPETAS_PROHIBIDAS & set(partes), f"{a} no debe viajar"
