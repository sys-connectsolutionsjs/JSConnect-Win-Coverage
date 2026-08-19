# ResumenDelDia.md — Historial del día

Fecha: 2026-08-19

## Qué se hizo hoy

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
  - `ResumenDelDia.md` = historial del día (este archivo), se actualiza a medida
    que se trabaja y sirve de base para el resumen de cierre de sesión.
  - `PlanesAprobados.md` = COLA de trabajo (no historial): lo implementado se saca
    de ahí.
  - `README.md` se actualiza con avances cuando el plan lo amerita (seguridad,
    funciones nuevas, etc.).
  - Al terminar la sesión se actualiza `AGENTS.md` con el resumen del día; luego se
    pregunta al usuario si quiere ver el resumen del día desde este archivo.
- [Docs] Creado `ResumenDelDia.md` (este archivo) y actualizados `AGENTS.md` y
  `PlanesAprobados.md` con las reglas y el estado de la cola.
- [Git] Commit + push de los cambios de la mañana a GitHub (rama `main`).
- [Pospuesto] Prueba de concurrencia (Fase 1.5, Paso 1 — `tools/probar_concurrencia.py`)
  se pospone; queda agendado para retomarse en cuanto se vuelva (probablemente hoy).

## Pendiente al volver
- **EJECUTAR la prueba de concurrencia** (Fase 1.5, Paso 2): en 4-5 máquinas a la vez
  con `python tools/probar_concurrencia.py --ciclos 5 --log concurrencia.log`.
  Observar si Win bloquea/avisa/fuerza cierres; registrar resultados en AGENTS.md y
  decidir arquitectura A/B (Paso 3). La herramienta YA está creada (Paso 1 hecho).
  Coordenadas de prueba: `-12.087718994493725, -76.98571219979543` (San Borja,
  cobertura SI) · DNI de prueba: `75020496`. El log TSV es fecha/máquina/ciclo/
  OK|FALLO/detalle. NO subir el log a GitHub (borrarlo al terminar).
- Luego implementar lo elegido (Paso 4) y, posteriormente, la **Fase 2** (gestión
  visual de activación: `GeneradorActividad.exe`).
- Revisar el estado de la herramienta **Captura de API** (traer `captura.json` desde
  la otra PC; ver sus propios MD).
- Ver PlanesAprobados.md y AGENTS.md para el resto de pendientes.