# PlanesAprobados.md — Planes de trabajo aprobados

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Contexto
App de escritorio (Python/Tkinter) para un call center que valida COBERTURA
(coordenadas) y SCORE crediticio (DNI/RUC/CE) replicando la API interna de
appwinforce.win.pe (sin scrapear HTML). Repo:
https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Estado del proyecto (2026-08-18)
- Fase 0 (captura de la API): COMPLETA.
- Fase 1 (núcleo core): construida; pendiente prueba real con credenciales.
- Fase 1.5 (decisión de autenticación): EN CURSO (plan aprobado abajo).

## Descubrimientos técnicos (Fase 0)
- Login: POST /controllers/acceso.php (accion=iniciar_sesion) -> cookie PHPSESSID.
- Cobertura: GET /controllers/coordenada.php?accion=validar_cobertura
  &data[latitud]=..&data[longitud]=.. -> {cobertura: SI/NO, tipo, id_celda}.
- Score: POST /controllers/cliente.php accion=score_cliente (payload data[...]).
  Respuesta: JSON doble-encodificado con reporte SOAP Equifax; puntaje en
  ns3ResumenScoreRP3.Puntaje (ej: 423) y DeudaTotal en ResumenDeuda.
- Tipos de doc: 1=DNI, 2=Carnet extranjería, 3=RUC, 4=Pasaporte.
- Geodata (distrito/ubigeo/cod_postal/segmentación): la calcula el navegador
  llamando a la geoapi de Equifax (oauth client_credentials). Credenciales en
  el header Authorization (embebidas en el JS del sitio).

## Fase 1 — Núcleo (construida)
- validator_app/core/session.py: sesión requests con headers de navegador.
- validator_app/core/api.py: login(), validar_cobertura(), validar_score()
  (parser del reporte Equifax), validar(). Errores: APIError/LoginError/ScoreError.
- tools/probar_core.py: arnés de prueba en consola (login->cobertura->score).
- tools/captura.py mejorada: redacción de formularios, guarda HTML,
  MAX_BODY_CHARS=200000, --guardar-js (JS en tools/js/), salida sin buffer.
- Tests: tests/test_api.py (14 casos). Total: 25 tests, ruff limpio.

## Decisión de autenticación — análisis
### Restricciones del negocio
- Los agentes NO tienen cuenta de WinForce (solo el responsable).
- La app debe ser OFFLINE y de mínimo costo.
- ~20 máquinas con internet constante.
- Win (la ISP) permite 2-3 personas simultáneas por cuenta; cierra la sesión
  a los 3 minutos sin uso.
- Win ROTA las credenciales cada 1-2 meses (desactiva la cuenta anterior y
  entrega usuario/contraseña nuevos al responsable).
- Hay una PC fija disponible en la oficina (encendida en horario laboral).

### Opciones analizadas
A) Credenciales por máquina (keyring) + auto-relogin.
   + Simple, $0, sin dependencias.
   - Hasta 20 sesiones concurrentes de la misma cuenta -> riesgo de bloqueo.
   - Cada rotación (1-2 meses) = actualizar keyring en las 20 máquinas.
B) Proxy local en la PC de la oficina (LAN).
   + 1-2 sesiones de WinForce desde UNA IP -> sin riesgo de bloqueo.
   + Credenciales SOLO en el proxy; rotación = actualizar 1 sola PC.
   + Sigue siendo offline (solo LAN, sin VPS), costo ~$0.
   - Punto único de falla (mitigable con una 2ª PC de respaldo).
C) Cuentas propias por agente: DESCARTADA (no tienen cuentas).
D) Sesión en caché por máquina: DESCARTADA (expiraciones + misma cuenta).

### Decisión aprobada (2026-08-18)
1. PRIMERO: prueba de concurrencia en 4-5 máquinas con la misma cuenta para
   comprobar si Win bloquea. Registro de resultados en AGENTS.md.
2. LUEGO: elegir arquitectura según los datos:
   - Sensibilidad/bloqueo -> B (proxy local).
   - Pasa limpia con 5+ simultáneas -> evaluar A.
3. Recomendación técnica del plan: B (proxy local), incluso si la prueba pasa,
   por la rotación mensual y el límite de 2-3 sesiones.

## Pasos del plan aprobado
### Paso 0 — Continuidad
- Crear este archivo (PlanesAprobados.md).
- AGENTS.md: tarea de concurrencia al TOPE de Tareas pendientes + historial de
  hoy + dato de rotación de credenciales.

### Paso 1 — Herramienta de prueba de concurrencia
- tools/probar_concurrencia.py: bucle login -> cobertura -> score (N veces),
  con marcas de tiempo; registra errores/bloqueos para detectar el límite de Win.
- Alternativa manual previa: abrir appwinforce.win.pe en 5 navegadores con el
  mismo usuario y validar a la vez (prueba más fiel del límite real).
- **Diseño acordado (código listo, NO creado aún)**: al construirla, usar el
  siguiente borrador aprobado:

```python
"""Prueba de concurrencia (Fase 1.5): simula uso simultaneo de la cuenta de Win.

Objetivo: comprobar si Win (la ISP) bloquea o avisa cuando varias maquinas usan la
misma cuenta a la vez. Se ejecuta en 4-5 maquinas simultaneamente.

Uso:
    python tools/probar_concurrencia.py [--ciclos N] [--intervalo S] [--log FILE]

    --ciclos      numero de ciclos login->cobertura->score (por defecto 5)
    --intervalo   segundos de espera entre ciclos (por defecto 0)
    --log         archivo de salida con marcas de tiempo (defecto concurrencia.log)
"""

import argparse
import getpass
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

from validator_app.core import api
from validator_app.gui import fields

COORDENADAS_PRUEBA = "-12.087718994493725, -76.98571219979543"  # San Borja (cobertura SI)
DOCUMENTO_PRUEBA = "75020496"  # DNI real de la captura (cobertura SI)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba de concurrencia de la cuenta Win.")
    parser.add_argument("--ciclos", type=int, default=5)
    parser.add_argument("--intervalo", type=float, default=0.0)
    parser.add_argument("--log", default="concurrencia.log")
    args = parser.parse_args()

    usuario = input("Usuario (email): ").strip()
    contrasena = getpass.getpass("Contrasena: ")
    if not usuario or not contrasena:
        print("[ERROR] Usuario y contrasena son obligatorios.")
        return 1

    lat, lon = fields.parse_coordenadas(COORDENADAS_PRUEBA)
    tipo = fields.detectar_tipo_documento(DOCUMENTO_PRUEBA)

    maquina = socket.gethostname()
    log = Path(args.log)
    fallos_seguidos = 0

    print(f"Maquina: {maquina} | ciclos: {args.ciclos} | cuenta: {usuario}")
    print(f"Prueba: login -> cobertura({lat},{lon}) -> score({tipo} {DOCUMENTO_PRUEBA})")
    print("=" * 66)

    for ciclo in range(1, args.ciclos + 1):
        marca = datetime.now().isoformat(timespec="seconds")
        resultado = "OK"
        detalle = ""
        try:
            cliente = api.obtener_cliente().login(usuario, contrasena)
            cobertura = cliente.validar_cobertura(lat, lon)
            if cobertura["hay_cobertura"]:
                score = cliente.validar_score(
                    tipo, DOCUMENTO_PRUEBA, lat, lon, cobertura=cobertura["cobertura"]
                )
                detalle = f"cobertura={cobertura['cobertura']} score={score['valor']}"
            else:
                detalle = f"cobertura={cobertura['cobertura']} (sin score)"
        except Exception as exc:
            resultado = "FALLO"
            detalle = f"{type(exc).__name__}: {exc}"
            fallos_seguidos += 1
        else:
            fallos_seguidos = 0

        linea = f"{marca}\t{maquina}\t{ciclo}\t{resultado}\t{detalle}"
        print(f"[{ciclo:02}] {resultado}: {detalle}")
        with log.open("a", encoding="utf-8") as fh:
            fh.write(linea + "\n")

        if fallos_seguidos >= 3:
            print("3 fallos seguidos: probable bloqueo o sesion invalida. Deteniendo.")
            break
        if args.intervalo:
            time.sleep(args.intervalo)

    print("=" * 66)
    print(f"Detalle guardado en: {log.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- **Uso previsto**: en 4-5 máquinas a la vez: `python tools/probar_concurrencia.py
  --ciclos 5 --log concurrencia.log`. Cada máquina genera un log TSV
  (fecha, máquina, ciclo, OK/FALLO, detalle) para correlacionar.
- **Seguridad**: el log solo contiene cobertura/score (sin documento ni
  contraseña); aun así, borrarlo al terminar y no subirlo a GitHub.
- **Lint esperado**: debe pasar `ruff check .` y `python -c "import
  tools.probar_concurrencia"` (no se ejecuta en pruebas automáticas porque pide
  credenciales y hace peticiones reales).

### Paso 2 — Ejecutar la prueba
- En 4-5 máquinas simultáneas con la misma cuenta.
- Observar: ¿bloquea? ¿avisa? ¿fuerza cierres? ¿3 min de inactividad?
- Registrar resultados en AGENTS.md.

### Paso 3 — Decidir arquitectura y registrar la decisión.

### Paso 4 — Implementar lo elegido
- TRABAJO COMÚN (ambas opciones): auto-relogin en core/api.py:
  * Si la sesión tiene >~120 s sin uso, re-loguear en silencio antes de validar.
  * Si una respuesta indica sesión expirada, re-loguear y reintentar 1 vez.
- Si B (proxy): proxy/server.py (FastAPI o stdlib http.server) que reusa
  ValidatorAPI y expone /cobertura y /score por LAN con token compartido.
  El cliente de las 20 máquinas apunta al proxy (sin credenciales).
- Si A (por máquina): keyring por máquina configurado UNA vez por el
  responsable; GUI sin pantalla de login; modo "actualizar credenciales".

## Pendientes adicionales (no bloquean la decisión)
- Prueba real del core (tools/probar_core.py) con credenciales del responsable.
- Decidir geodata del score (A: replicar Equifax / B: manual / C: mínimo)
  según el resultado de la prueba real.
- Decidir si la app llama a actualizar_score_cliente y/o newsearch.php.
- Conectar GUI a core (keyring) + ajustar resultados + README.

## Checklist próxima sesión
1. Leer AGENTS.md (Archivos de documentación) + PlanesAprobados.md (Paso 1) para
   retomar contexto completo sin depender de memoria.
2. Crear tools/probar_concurrencia.py a partir del diseño aprobado en el Paso 1.
3. Coordinar la prueba en 4-5 máquinas.
4. Registrar resultados en AGENTS.md y decidir arquitectura.
5. Implementar lo elegido (Paso 4) + pendientes adicionales.

## Notas de seguridad
- Credenciales de Win rotan cada 1-2 meses; nunca hardcodear; en B solo viven
  en la PC del proxy; en A en keyring por máquina (nunca en el repo).
- NO subir a GitHub: tools/captura.json, tools/js/, generator/private_key.pem,
  credenciales reales.