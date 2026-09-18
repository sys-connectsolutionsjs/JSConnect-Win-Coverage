"""Guardas estaticas de install_service.bat.

CMD parsea un bloque `( ... )` completo antes de ejecutarlo: un `)` sin escapar
dentro de un `echo` indentado cierra el bloque y el script aborta con "No se
esperaba ... en este momento" (paso 5 del instalador, 2026-09-18).
"""

import re
from pathlib import Path

BAT = Path(__file__).resolve().parents[1] / "validator_app" / "proxy" / "install_service.bat"


def test_echo_dentro_de_bloques_no_tiene_parentesis_sin_escapar():
    malas = []
    for n, linea in enumerate(BAT.read_text(encoding="utf-8").splitlines(), start=1):
        m = re.match(r"^\s+echo\b(.*)$", linea)
        if m and re.search(r"(?<!\^)\)", m.group(1)):
            malas.append(f"{n}: {linea.strip()}")
    assert not malas, "`)` sin escapar (usar ^) dentro de bloques:\n" + "\n".join(malas)


def test_el_instalador_sigue_pidiendo_confirmacion_de_tokens_y_no_se_cierra():
    texto = BAT.read_text(encoding="utf-8")
    assert "choice /c CR" in texto  # conservar / regenerar tokens
    assert 'cmd /k ""%~f0" _run"' in texto  # ventana persistente


def test_extension_manual_se_explica_al_final_sin_detener_el_instalador():
    texto = BAT.read_text(encoding="utf-8")
    assert "Cargar descomprimida" in texto
    assert r"%BASE_DIR%\.extension_build" in texto
    # El paso 7 solo informa: ningun exit/pause entre su inicio y el paso 8.
    paso7 = texto.split("[7/12]")[1].split("[8/12]")[0]
    assert "exit /b" not in paso7 and "pause" not in paso7
