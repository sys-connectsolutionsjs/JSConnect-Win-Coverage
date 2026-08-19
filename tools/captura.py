"""Herramienta de captura (Fase 0): descubre la API interna del sistema de validacion.

Uso:
    python tools/captura.py [--minutos N]

Pasos:
    1. Se abre UNA ventana de Chromium (maximizada) con la URL de SISTEMA_URL.
    2. Haz TODO dentro de ESA ventana (NO en tu Chrome):
       - Inicia sesion manualmente (usa el portapapeles para credenciales).
       - Ve a "Anadir nuevo lead" y valida UN cliente con coordenadas.
       - Haz una validacion de score (elige el tipo de documento).
    3. Al terminar, haz clic en el BOTON VERDE "TERMINAR CAPTURA" (o cierra la
       ventana con la X, o espera el auto-cierre).

Al terminar, SIEMPRE genera tools/captura.json con las llamadas de red
relevantes (solo peticiones tipo API), con los campos sensibles redactados,
aunque el navegador se cierre de forma forzada.

IMPORTANTE: revisa captura.json antes de compartirlo y borralo cuando termine
la Fase 1. Puede contener datos de clientes.
"""

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from playwright.sync_api import sync_playwright

# TODO: reemplazar por la URL real del sistema (pantalla de inicio de sesion)
SISTEMA_URL = "https://appwinforce.win.pe/login"

# Minutos de espera antes de cerrar el navegador solo (anti-hang)
TIEMPO_MAX_MINUTOS = 10

# Campos cuyo VALOR se redacta en los payloads y respuestas
SENSITIVE_FIELDS = (
    "password",
    "pass",
    "pwd",
    "clave",
    "secret",
    "authorization",
    "token",
    "jwt",
)

# Headers cuyo valor se redacta por completo
REDACT_HEADERS = (
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
)

# URLs de recursos estaticos/mapas que no aportan a la API
SKIP_URL_PATTERNS = (
    r"\.(png|jpg|jpeg|gif|svg|css|js|woff2?|ico|webp|map|mp4)(\?|$)",
    r"/tile",
    r"tiles?\.",
    r"openstreetmap",
    r"google-analytics",
    r"gtm\.js",
)

MAX_BODY_CHARS = 200000
OUTPUT_FILE = Path(__file__).parent / "captura.json"
SCREENSHOT_FILE = Path(__file__).parent / "captura_inicio.png"


def _obtener_procesos():
    """Devuelve [{ProcessId, ParentProcessId, CommandLine}] de todos los procesos."""
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    try:
        data = json.loads(out.stdout)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    return data


def _construir_arbol(procesos):
    """Mapa pid -> pid del padre."""
    arbol = {}
    for proc in procesos:
        pid = proc.get("ProcessId")
        padre = proc.get("ParentProcessId")
        if pid:
            arbol[int(pid)] = int(padre) if padre else 0
    return arbol


def _es_ancestro(arbol, pid_candidato, mi_pid):
    """True si pid_candidato es padre (directo o indirecto) de mi_pid."""
    actual = int(mi_pid)
    for _ in range(10):
        padre = arbol.get(actual, 0)
        if not padre or padre == actual:
            return False
        if padre == pid_candidato:
            return True
        actual = padre
    return False


def _buscar_otra_instancia(procesos, mi_pid):
    """True si hay otra instancia de captura.py que NO sea un ancestro mio.

    El stub de Python de Microsoft Store lanza el python real, y ambos procesos
    llevan "tools/captura.py" en su linea de comandos. Los ancestros se excluyen
    para no confundir al propio lanzador con una segunda instancia.
    """
    mi_pid = int(mi_pid)
    arbol = _construir_arbol(procesos)
    for proc in procesos:
        comando = proc.get("CommandLine") or ""
        pid = proc.get("ProcessId")
        if "tools/captura.py" not in comando or not pid:
            continue
        pid = int(pid)
        if pid == mi_pid:
            continue
        if _es_ancestro(arbol, pid, mi_pid):
            continue
        return True
    return False


def bloquear_instancia_unica():
    """Sale si ya hay otra instancia de captura.py corriendo."""
    if getattr(sys, "frozen", False):
        return
    procesos = _obtener_procesos()
    if not procesos:
        return
    if _buscar_otra_instancia(procesos, os.getpid()):
        print("Ya hay otra instancia de captura.py corriendo.")
        print("Cierra ESA ventana (o espera a que termine) antes de volver a ejecutar.")
        sys.exit(1)


def redact_dict(data):
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            key_low = str(key).lower()
            if any(s in key_low for s in SENSITIVE_FIELDS):
                out[key] = "********"
            else:
                out[key] = redact_dict(value)
        return out
    if isinstance(data, list):
        return [redact_dict(item) for item in data]
    return data


def parse_body(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def redact_form(text):
    """Redacta valores de campos sensibles en un formulario URL-encoded."""
    try:
        pares = parse_qsl(text, keep_blank_values=True)
        redactados = [
            (clave, "********") if any(s in clave.lower() for s in SENSITIVE_FIELDS)
            else (clave, valor)
            for clave, valor in pares
        ]
        return urlencode(redactados)
    except Exception:
        return "********"


def es_multipart(text):
    return bool(text) and "WebKitFormBoundary" in text


def es_relevante(response):
    url = response.url
    for pattern in SKIP_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    content_type = response.headers.get("content-type", "")
    resource_type = response.request.resource_type
    return "json" in content_type or resource_type in ("xhr", "fetch")


def guardar_archivo(url_inicial, records, cookies):
    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "meta": {
                    "creado": datetime.now().isoformat(timespec="seconds"),
                    "url_inicial": url_inicial,
                    "total_registros": len(records),
                },
                "cookies": [
                    {"name": c["name"], "domain": c["domain"], "secure": c["secure"]}
                    for c in cookies
                ],
                "registros": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nCaptura guardada: {OUTPUT_FILE} ({len(records)} registros)")
    print("Revisa el archivo (puede tener datos sensibles) y borralo tras la Fase 1.")


def main():
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(line_buffering=True)

    if SISTEMA_URL.startswith("https://SISTEMA-DEL-ISP"):
        print("Pon la URL real del sistema en SISTEMA_URL (tools/captura.py) y vuelve a ejecutar.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Captura la API interna del sistema de validacion."
    )
    parser.add_argument(
        "--minutos",
        type=int,
        default=TIEMPO_MAX_MINUTOS,
        help="Minutos de espera antes del auto-cierre del navegador.",
    )
    parser.add_argument(
        "--guardar-js",
        action="store_true",
        help="Guarda los archivos JS cargados en tools/js/ (para buscar credenciales).",
    )
    args = parser.parse_args()
    tiempo_max_seg = args.minutos * 60

    bloquear_instancia_unica()

    records = []
    cookies = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--start-maximized"])
            context = browser.new_context(no_viewport=True)
            page = context.new_page()

            def on_response(response):
                try:
                    if not es_relevante(response):
                        return
                    request = response.request
                    body = ""
                    with contextlib.suppress(Exception):
                        body = response.text()

                    payload = None
                    if request.post_data:
                        if es_multipart(request.post_data):
                            payload = "(multipart/form-data - contenido no capturado)"
                        else:
                            payload = redact_dict(parse_body(request.post_data))
                            if payload is None:
                                payload = redact_form(request.post_data)

                    response_body = None
                    with contextlib.suppress(Exception):
                        raw = body[:MAX_BODY_CHARS]
                        parsed = parse_body(raw)
                        if parsed is not None:
                            response_body = redact_dict(parsed)
                        else:
                            content_type = response.headers.get("content-type", "")
                            if any(
                                t in content_type
                                for t in ("text", "json", "xml")
                            ):
                                response_body = raw

                    record = {
                        "id": len(records) + 1,
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "url": response.url,
                        "metodo": request.method,
                        "headers": {
                            key: ("********" if key.lower() in REDACT_HEADERS else value)
                            for key, value in request.headers.items()
                        },
                        "payload": payload,
                        "respuesta": {
                            "status": response.status,
                            "content_type": response.headers.get("content-type", ""),
                            "body": response_body,
                        },
                    }
                    records.append(record)
                    print(f"[{record['id']:3}] {record['metodo']:6} {record['url']}")
                except Exception as exc:
                    print(f"Error capturando {response.url}: {exc}")

            page.on("response", on_response)

            if args.guardar_js:
                carpeta_js = Path(__file__).parent / "js"
                carpeta_js.mkdir(exist_ok=True)
                guardados = []

                def guardar_js(response):
                    try:
                        content_type = response.headers.get("content-type", "")
                        if "javascript" not in content_type:
                            return
                        cuerpo = response.text()
                        nombre = Path(response.url).name[:60] or "script.js"
                        destino = carpeta_js / f"{len(guardados) + 1:03d}_{nombre}"
                        destino.write_text(cuerpo, encoding="utf-8", errors="replace")
                        guardados.append(destino)
                        print(f"JS guardado: {destino.name} ({len(cuerpo)} chars)")
                    except Exception:
                        pass

                page.on("response", guardar_js)

            terminar = threading.Event()

            def marcar_fin(*_args):
                terminar.set()

            page.on("close", marcar_fin)

            def inyectar_boton():
                """Inserta un boton verde flotante que finaliza la captura al hacer clic."""
                with contextlib.suppress(Exception):
                    page.evaluate(
                        """
                        if (!document.getElementById('btn-terminar-captura')) {
                            const b = document.createElement('div');
                            b.id = 'btn-terminar-captura';
                            b.textContent = 'TERMINAR CAPTURA  ✓';
                            b.style.cssText = 'position:fixed;top:16px;right:16px;' +
                                'z-index:2147483647;background:#0a7d2c;color:#fff;' +
                                'font:bold 16px/1.4 sans-serif;padding:12px 18px;' +
                                'border-radius:8px;cursor:pointer;' +
                                'box-shadow:0 4px 12px rgba(0,0,0,.45);user-select:none;';
                            b.onclick = () => {
                                window.__captura_fin = true;
                                b.textContent = 'GUARDANDO...';
                            };
                            document.body.appendChild(b);
                        }
                        """
                    )

            print("=" * 66)
            print("LA VENTANA DEL SCRIPT ESTA ABIERTA AHORA (maximizada).")
            print("Es la ventana que tiene el BOTON VERDE 'TERMINAR CAPTURA'.")
            print("Haz TODO dentro de ESA ventana (NO en tu Chrome):")
            print("  1) Inicia sesion manualmente (usa el portapapeles).")
            print("  2) Ve a 'Anadir nuevo lead' y valida UN cliente (coordenadas).")
            print("  3) Haz una validacion de score (elige el tipo de documento).")
            print("  4) Al terminar, haz clic en el BOTON VERDE 'TERMINAR CAPTURA'.")
            print("     (Tambien puedes cerrar la ventana con la X, o esperar el auto-cierre.)")
            print(f"  Auto-cierre en {args.minutos} minutos por si acaso.")
            print("=" * 66)

            page.goto(SISTEMA_URL)
            with contextlib.suppress(Exception):
                page.bring_to_front()
            time.sleep(3)
            with contextlib.suppress(Exception):
                page.screenshot(path=str(SCREENSHOT_FILE))
                print(f"Screenshot inicial: {SCREENSHOT_FILE}")
            inyectar_boton()

            inicio = time.monotonic()
            ultima_inyeccion = 0.0
            try:
                while not terminar.is_set():
                    if time.monotonic() - inicio > tiempo_max_seg:
                        print("Tiempo maximo alcanzado. Cerrando el navegador.")
                        break
                    ahora = time.monotonic()
                    if ahora - ultima_inyeccion >= 2:
                        inyectar_boton()
                        ultima_inyeccion = ahora
                    with contextlib.suppress(Exception):
                        if page.evaluate("window.__captura_fin === true"):
                            print("Boton TERMINAR pulsado. Guardando...")
                            break
                    time.sleep(0.5)
            except Exception:
                pass

            with contextlib.suppress(Exception):
                cookies = context.cookies()

            with contextlib.suppress(Exception):
                browser.close()
    finally:
        guardar_archivo(SISTEMA_URL, records, cookies)


if __name__ == "__main__":
    main()
