"""Guardas estaticas de install_service.bat.

CMD parsea un bloque `( ... )` completo antes de ejecutarlo: un `)` sin escapar
dentro de un `echo` indentado cierra el bloque y el script aborta con "No se
esperaba ... en este momento" (paso 5 del instalador, 2026-09-18).
"""

import re
from pathlib import Path

_PROXY_DIR = Path(__file__).resolve().parents[1] / "validator_app" / "proxy"
BAT = _PROXY_DIR / "install_service.bat"
UNINSTALL_BAT = _PROXY_DIR / "uninstall_service.bat"


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
    paso7 = texto.split("[7/13]")[1].split("[8/13]")[0]
    assert "exit /b" not in paso7 and "pause" not in paso7


def test_los_pasos_numerados_son_consistentes():
    """Guarda generica contra el bug que motivo este archivo de tests: al
    insertar/quitar un paso hay que renumerar TODOS los `echo [N/TOTAL]`, y es
    facil olvidar uno. `re.MULTILINE` con `^echo \\[` evita falsos positivos
    como el CIDR "172.16.0.0/12" de allowed_networks, que no es un marcador de
    paso."""
    texto = BAT.read_text(encoding="utf-8")
    marcadores = re.findall(r"^echo \[(\d+)/(\d+)\]", texto, re.MULTILINE)
    assert marcadores, "no se encontraron marcadores de paso"
    totales = {total for _, total in marcadores}
    assert len(totales) == 1, f"denominadores de paso inconsistentes: {totales}"
    total = int(totales.pop())
    numeros = sorted(int(n) for n, _ in marcadores)
    assert numeros == list(range(1, total + 1)), f"pasos no consecutivos: {numeros}"


def test_regla_de_firewall_se_crea_automaticamente_con_fallback_manual():
    """Bug real (2026-09-25): el instalador solo IMPRIMIA el comando de
    New-NetFirewallRule como nota manual al final, nunca lo ejecutaba. Un
    agente en otra PC fallaba con timeout (el firewall descarta el paquete en
    silencio) en vez de "conexion rechazada"."""
    texto = BAT.read_text(encoding="utf-8")
    assert "Get-NetFirewallRule -DisplayName 'JSWinProxy API'" in texto  # idempotencia
    assert "New-NetFirewallRule" in texto
    assert "-LocalPort !PROXY_PORT!" in texto  # el puerto real, no uno fijo
    # Fallback si el firewall esta gobernado por Directiva de Grupo/dominio.
    assert "Directiva de" in texto


def test_uninstall_quita_la_regla_de_firewall():
    texto = UNINSTALL_BAT.read_text(encoding="utf-8")
    assert "Remove-NetFirewallRule -DisplayName 'JSWinProxy API'" in texto
