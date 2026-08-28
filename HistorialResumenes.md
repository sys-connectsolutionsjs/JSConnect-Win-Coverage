# HistorialResumenes.md — Archivo histórico de resúmenes

Fecha de creación: 2026-08-21 · Proyecto: JSConnect-Win-Coverage

## Qué es este archivo
Depósito COMPLETO y cronológico de los resúmenes de días pasados. Existe para
que `ResumenDelDia.md` (que se lee con regularidad) se mantenga lo más LIGERO
posible: solo contiene la sesión del día en curso.

**Regla de rotación**: al iniciar una sesión de un día nuevo, lo que quede en
`ResumenDelDia.md` se MUEVE aquí (en orden cronológico, lo más nuevo arriba),
y el archivo del día empieza limpio. Este archivo nunca se borra; solo crece.

---

### 2026-08-27 — Sesión (primera prueba real end-to-end del core)
- [Confirmado] **Login programático inviable**: `acceso.php` acepta credenciales pero
  responde `"Redireccionar"` (al 2FA de Microsoft) y `operador.php` devuelve HTML →
  `ERR_LOGIN_SESSION`. El "recordar dispositivo" del 2FA es **por navegador, no por
  cuenta**. Valida definitivamente la arquitectura Proxy Local + cookie manual.
- [Bug real 1 — corregido] `coordenada.php` antepone un **BOM UTF-8** al JSON;
  `requests.json()` fallaba y `_json()` lo ocultaba. Fix: reintento `json.loads(texto[1:])`
  + test `test_cobertura_si_con_bom` (nueva clase `FakeResponseConBOM`).
- [Bug real 2 — corregido] Score **doble-encodificado** (2 `json.loads`, documentado desde
  Fase 0 pero nunca implementado — solo hacía uno). Fix: `_parsear_score` decodifica
  tolerante a profundidad + test `test_score_parsea_reporte_doble_encodificado`.
- [Verificado con datos reales] Flujo completo: cookie (login manual+2FA) → cobertura
  (SI, HORIZONTAL, celda 8764) → score (423, MUY ALTO). **37 tests, ruff limpio.**
- [Decisión] **Geodata del score = opción C (payload mínimo)**: funciona enviando solo
  coordenadas + documento, sin replicar la geoapi de Equifax.
- [Nuevo] `tools/probar_con_cookie.py` (herramienta de diagnóstico contra el servidor real,
  con `_diagnosticar_score` para inspeccionar la profundidad del encoding).
- [Seguridad] `.gitignore` no cubría `config.yaml` / `proxy_token.txt` / `admin_key.txt`
  del proxy — corregido antes de que se generen en la PC del proxy.
- [Entorno] En una máquina con Python 3.12.2 `pip install -e .` falla (pyproject exige
  ≥3.14); workaround `PYTHONPATH=.`. Snapshot: `resumenes/2026-08-27.md`.
- Commits: `c72188c`, `7bc6550`.

### 2026-08-26 — Sesión (setup máquina nueva + sincronización de documentación)
- [Entorno] Repo clonado en máquina nueva; `git user.name=AngelSanchezDev`. Acceso de
  escritura resuelto: `AngelSanchezDev` se agregó como colaborador con permiso de escritura
  en `sys-connectsolutionsjs/JSConnect-Win-Coverage` (antes daba 403).
- [Auditoría] Detectado desfase doc↔código: `AGENTS.md` (en disco como `Claude.md`) daba
  por pendientes las FASES 1–5 del proxy, pero ya estaban implementadas en commits
  posteriores del 2026-08-25 (`877689f`, `801ce05`, `f63660b`, `7cf7ea1`).
- [Corregido] `Claude.md` → `AGENTS.md` en disco (coincide con el tracked de git). Tareas
  1–6 y 11 marcadas `[COMPLETADO]` con evidencia file:line. Añadidas la regla de
  auto-actualización de docs (3 momentos) y la regla de rotación de resúmenes.
- [Docs] Creado `resumenes/2026-08-25.md` (snapshot faltante); `HistorialResumenes.md` y
  `PlanesAprobados.md` sincronizados con el estado real.
- [Verificado] 35 tests pasando, ruff limpio. Snapshot: `resumenes/2026-08-26.md`.

### 2026-08-25 — Sesión (tarde + noche)
- [Hallazgo crítico] Login WinForce redirige a 2FA Microsoft → inviable simular 4-5
  máquinas concurrentes con la misma cuenta.
- [Decisión arquitectónica] **Proxy Local (Opción B) APROBADA**: 20 agentes LAN → 1
  proxy (PC oficina) → 1-2 sesiones WinForce desde una sola IP. Stack: FastAPI +
  uvicorn, token compartido + IP LAN, admin key separada, winsw service, config.yaml
  gitignored.
- [Avance] FASE 0 Documentación completada: `docs/` (5 archivos), `Escalabilidad.md`,
  `anotaciones.md`, `resumenes/2026-08-19.md`.
- [Avance] FASES 1–5 del Proxy implementadas: `validator_app/proxy/` completo
  (server.py con 7 rutas, config.py, client.py, rotate_creds.py, winsw.xml,
  install/uninstall .bat), `auto_relogin_if_needed()` + persistencia de cookies en
  `core/api.py`, GUI con menú "⚙️ Configuración" y diálogo de proxy conectado a keyring.
- [Avance] Sistema de códigos de error: excepciones tipadas con `code` + diccionario
  `ERROR_CODES` (32 códigos) en `api.py`.
- [Verificado] 35 tests pasando, ruff limpio.
- [Nota] El cierre de esta sesión en `AGENTS.md` quedó desactualizado (decía "listo
  para FASE 1 Proxy Implementation" pese a que ya se implementó todo el mismo día);
  corregido en la sesión 2026-08-26. Ver `resumenes/2026-08-25.md` para el detalle
  completo.

### 2026-08-19 — Sesión (tarde)
- [Entorno] Nueva máquina: clonado el repo en
  `C:\Users\Connect Solutions 10\Documents\JS-REPOS\JSConnect-Win-Coverage`.
- [Entorno] Python 3.14.7 instalado (winget) + agregado al PATH del usuario.
- [Entorno] Dependencias instaladas (prod + dev) y Playwright Chromium descargado.
- [Entorno] `pyproject.toml`: añadido `[project]` + `[tool.setuptools.packages.find]`
  (solo `validator_app*`) para permitir `pip install -e .`; el paquete se instala
  en modo editable.
- [Git] Configurado user.name=AngelSanchezDev / user.email=sistemasconnectsolutionsjs@gmail.com.
- [Verificación] 25 tests pasando y ruff limpio en la máquina nueva.
- [Seguridad] Escaneo del proyecto y del historial de git por credenciales: NO se
  encontraron secretos (ni en código ni en commits); solo variable de runtime en
  api.py. Confirmado que `private_key.pem` y `tools/js/` nunca estuvieron en el repo.
- [Decisión] `tools/captura.json` y `tools/captura_inicio.png` NO son necesarios de
  transferir (info ya replicada en código; el primero además contiene datos de
  clientes).
- [Plan] Aprobada y registrada la **Fase 2 — Gestión visual de activación** en
  PlanesAprobados.md: `GeneradorActividad.exe` portable (PyInstaller onefile) para
  gerente/sistemas, con `private_key.pem` junto al .exe; flujo huella -> código por
  chat; se implementa DESPUÉS de la prueba de concurrencia.
- [Avance] Fase 1.5 **Paso 1 implementado**: creado `tools/probar_concurrencia.py`
  con el diseño aprobado (login->cobertura->score en N ciclos con log TSV).
  Ruff limpio, import OK, 25 tests pasando. Pendiente solo de ejecutarse en 4-5
  máquinas (Paso 2).
- [Herramienta] Creado el proyecto independiente **Captura de API** (Playwright) en
  `C:\Users\Connect Solutions 10\Documents\JS-REPOS\Captura de API` con `git init`,
  propio `captura.py` + `test_captura_guard.py` (adaptado: sys.path a la raíz y
  guarda de instancia única ahora busca `captura.py`), requirements/pyproject/
  .gitignore y los 6 MD propios (AGENTS, PlanesAprobados, ResumenDelDia, TestingLog,
  README, SkillsPropuestas). Verificado: 4 tests + ruff limpio.
- [Docs] `AGENTS.md` raíz: regla explícita de automantenimiento, `SkillsPropuestas.md`
  registrado en el mapa de conocimiento, sección "Proyectos relacionados" con la
  herramienta Captura de API, y historial de la sesión.
- [Docs] Creado `SkillsPropuestas.md` (cola/historial de skills) en el repo raíz.
- [Error→Solución] `pip`/`python` no reconocidos: Python no estaba instalado
  (solo stub de Microsoft Store). → Instalar Python 3.14.7 con winget y añadir al
  PATH de usuario.
- [Error→Solución] `pip install -e .` fallaba con "Multiple top-level packages
  discovered in a flat-layout". → Añadir `[project]` + `[tool.setuptools.packages.find]`
  (include `validator_app*`) en `pyproject.toml`.
- [Error→Solución] `tests/test_captura_guard.py` no encontraba `playwright` al
  importar captura.py. → Instalar playwright y su navegador (`python -m playwright
  install chromium`).
- [Error→Solución] `W292` (sin newline al final) en `probar_concurrencia.py`.
  → `ruff check . --fix`.
- [Pospuesto] **PRUEBA DE CONCURRENCIA** (Fase 1.5, Paso 2) pospuesta para OTRO DÍA:
  la herramienta ya está lista; solo falta ejecutarla en 4-5 máquinas.

### 2026-08-19 — Sesión (mañana)
- [Push] Primer commit del proyecto subido a GitHub (commit `e837681`, rama `main`)
  en https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage (32 archivos).
- [Contexto] Revisión de los .md de conocimiento (AGENTS.md, PlanesAprobados.md,
  TestingLog.md, README.md) para retomar dónde se quedó la sesión anterior.
- [Reglas] Definidas las reglas de trabajo del proyecto y reflejadas en `AGENTS.md`:
  - `ResumenDelDia.md` = historial del día (ese archivo), se actualiza a medida
    que se trabaja y sirve de base para el resumen de cierre de sesión.
  - `PlanesAprobados.md` = COLA de trabajo (no historial): lo implementado se saca
    de ahí.
  - `README.md` se actualiza con avances cuando el plan lo amerita (seguridad,
    funciones nuevas, etc.).
  - Al terminar la sesión se actualiza `AGENTS.md` con el resumen del día; luego se
    pregunta al usuario si quiere ver el resumen del día desde ese archivo.
- [Docs] Creado `ResumenDelDia.md` y actualizados `AGENTS.md` y `PlanesAprobados.md`
  con las reglas y el estado de la cola.
- [Git] Commit + push de los cambios de la mañana a GitHub (rama `main`).
- [Pospuesto] Prueba de concurrencia (Fase 1.5, Paso 1 — `tools/probar_concurrencia.py`)
  se pospone; queda agendado para retomarse en cuanto se vuelva (probablemente hoy).