# ResumenDelDia.md — Historial del día

Fecha: 2026-08-26

## Qué se hizo hoy

### 2026-08-26 — Sesión (mañana) — Setup de acceso + sincronización de documentación

#### Setup del entorno (nueva máquina)
- Clonado el repositorio en `C:\Users\Angel\Documents\JSCONECTSOLUTIONS\JS-REPOS\JSConnect-Win-Coverage`
- Configurado `git config user.name "AngelSanchezDev"` / `user.email` local para firmar commits
- Resuelto acceso de escritura: la cuenta `AngelSanchezDev` no tenía permisos en `sys-connectsolutionsjs/JSConnect-Win-Coverage` (403) → se agregó como colaborador con permiso de escritura desde la organización, credencial de Windows Credential Manager renovada, push verificado OK

#### Auditoría de inicio de sesión (detectó desfase de documentación)
- Al revisar el estado del proyecto se encontró que el archivo de reglas (`AGENTS.md`, tracked en git, pero presente en disco como `Claude.md`) tenía las "Tareas pendientes" y el cierre de sesión 2026-08-25 desactualizados: daban por pendientes las FASES 1–5 del proxy, pero el código **ya estaba implementado** en commits posteriores del mismo día (`877689f`, `801ce05`, `f63660b`, `7cf7ea1`)
- Verificado en el árbol real: `validator_app/proxy/` completo (server.py 7 rutas, config.py, client.py, rotate_creds.py, winsw.xml, instaladores), `core/api.py` con `auto_relogin_if_needed()` y persistencia de cookies, GUI con menú "⚙️ Configuración" conectado a keyring
- `python -m pytest -q` → 35 passed. `python -m ruff check .` → All checks passed.

#### Corrección de nombre de archivo
- `Claude.md` (disco) renombrado a `AGENTS.md` — coincide con el nombre ya tracked en git y con el título interno (`# AGENTS.md — Proyecto JSConnect-Win-Coverage`). Verificado que ningún archivo del proyecto referenciaba "Claude.md" por nombre; todos ya decían "AGENTS.md", así que no hubo referencias que corregir.

#### Documentación sincronizada
- `AGENTS.md`:
  - Tareas pendientes 1–6 y 11 marcadas `[COMPLETADO]` con evidencia (file:line), dejadas visibles para trazabilidad
  - Añadida sección de Historial `### Fase Proxy — Implementación [COMPLETADA]` con el detalle verificado
  - Corregido el cierre de sesión 2026-08-25 (nota de corrección) y añadido este cierre 2026-08-26
  - Nueva **regla de auto-actualización de la documentación** en 3 momentos: inicio de sesión (ojeada de verificación), durante la sesión (registro narrativo), cierre de sesión (actualización auditada contra el código)
  - Nueva **regla de rotación de resúmenes**: `resumenes/<fecha>.md` = snapshot completo; `HistorialResumenes.md` = índice condensado
  - Registrados `HistorialResumenes.md` y `resumenes/` en el mapa de conocimiento
- Creado `resumenes/2026-08-25.md` (snapshot faltante de la sesión anterior, que no se había archivado)
- Actualizado `HistorialResumenes.md` con entrada condensada de 2026-08-25
- Actualizado `PlanesAprobados.md` (estado real, cola limpiada de lo ya implementado)

### 2026-08-26 — Sesión (tarde) — Diagnóstico de 2FA y prueba real del core

#### Contexto del diagnóstico
- Contradicción encontrada en la doc: Fase 0 decía que el login programático no necesita 2FA;
  Fase 1.5 decía que WinForce siempre redirige a 2FA Microsoft; `rotate_creds.py` asume 2FA
  obligatorio y usa flujo híbrido (cookie manual). `tools/probar_core.py` nunca se actualizó
  tras la decisión de Fase 1.5 y sigue intentando login directo.
- Dato del usuario: el 2FA solo aparece la PRIMERA vez; luego no vuelve a pedirse (posible
  token "recordar dispositivo"). Hipótesis a probar: ¿ese recordatorio es por cuenta
  (server-side, login programático viable) o por dispositivo (cookie local del navegador,
  y entonces `requests` sí chocará con 2FA)?
- Ejecutando `tools/probar_core.py` (arnés existente, sin modificar) con credenciales reales
  tecleadas por el usuario vía getpass (nunca compartidas en el chat).

#### Resultado del login — CONFIRMADO: 2FA bloquea la sesión `requests` limpia
- Ejecutado `tools/probar_core.py` con credenciales reales (usuario
  `ventaslimasb2@alivtelecom.pe`) vía `PYTHONPATH=.` (workaround del bug de entorno, ver
  hallazgos).
- `acceso.php` respondió `{"response":"success","comment":"Redireccionar"}` — el servidor
  acepta las credenciales pero indica que hay que "Redireccionar" (al 2FA de Microsoft).
- La verificación posterior (`operador.php?accion=get_operador`) devolvió HTML (una página
  de login/redirect), NO el JSON esperado de operador autenticado → `LoginError
  ERR_LOGIN_SESSION`: "No se pudo iniciar sesion (la sesion no quedo activa)".
- **Conclusión**: el recordatorio de 2FA es **por dispositivo/navegador**, no por cuenta.
  Una sesión `requests` nueva (sin ese estado del navegador) siempre choca con 2FA. El
  login programático de `ValidatorAPI.login()` **NO es viable** tal como está — confirma
  que la arquitectura de Proxy Local + flujo de cookie (`rotate_creds.py`) es la decisión
  correcta, no una sobre-ingeniería.
- Próximo paso (Fase 2 del plan): repetir el flujo pero inyectando la cookie `PHPSESSID`
  capturada tras un login manual en el navegador, para validar cobertura y score.

#### Fase 2 — Cobertura/score con cookie del navegador: causa real encontrada (corrige hipótesis)
- Capturada la cookie `PHPSESSID` tras login manual en el navegador (2FA superado ahí) e
  inyectada en una sesión `requests` limpia vía `tools/probar_con_cookie.py` (script nuevo,
  creado esta sesión).
- Primer intento falló: `[FALLO] Respuesta inesperada del servidor al consultar cobertura.`
  Se investigaron dos hipótesis en orden:
  1. **Descartada**: que la cookie no autenticara (2FA/expiración). `operador.php` con esa
     misma cookie devolvió JSON completo y válido (`"response":"success"`, lista de
     operadores) → la sesión SÍ está autenticada.
  2. **Descartada**: que el servidor atara la sesión al `User-Agent`. Se probó la misma
     cookie con el UA hardcodeado del core y con el UA real del navegador
     (`navigator.userAgent`) — **resultado idéntico en ambos casos**. El UA no influye.
- **Causa real encontrada**: `coordenada.php` antepone un **BOM UTF-8** (`﻿`) a su
  respuesta JSON (`'﻿response":"success","cobertura":"SI",...'`). `resp.json()` de
  `requests` no tolera ese carácter y lanza `ValueError`; `_json()` (`core/api.py:453`)
  lo capturaba y lo convertía en un mensaje genérico sin mostrar el cuerpo real. El
  servidor **siempre respondió correctamente** — el bug era 100% del lado del cliente.
- **Fix aplicado**: `_json()` ahora intenta `json.loads(texto[1:])` si el texto empieza con
  BOM, antes de rendirse. Añadido test de regresión `test_cobertura_si_con_bom` en
  `tests/test_api.py` (con nueva clase `FakeResponseConBOM` que simula el fallo real de
  `requests.json()`, no solo el retorno de datos ya parseados). **36 tests pasando, ruff
  limpio.**
- **Confirmado con datos reales**: cobertura SI, tipo HORIZONTAL, id_celda 8764 en las
  coordenadas de prueba del README.

#### Score — segundo bug encontrado y corregido: doble-encodificado real
- Al probar score con el documento 75020496 (mismo dato de prueba ya usado en
  `tests/test_api.py` y `tools/probar_core_gui.py`, no un cliente nuevo), apareció
  `[ERROR SCORE] 'str' object has no attribute 'get'`.
- Diagnóstico añadido a `tools/probar_con_cookie.py` (`_diagnosticar_score`) confirmó la
  causa exacta: el campo `data` de la respuesta necesita **2 pasadas de `json.loads`**
  (profundidad 0: string de 23702 chars; profundidad 1: string de 20876 chars; profundidad
  final: dict). Esto es exactamente lo que la Fase 0 (2026-08-18) ya había documentado
  como "JSON doble-encodificado" (`AGENTS.md`, `PlanesAprobados.md`) pero que la
  implementación de Fase 1 nunca hizo — solo llamaba `json.loads()` una vez
  (`core/api.py:383`, código anterior).
- **Fix aplicado**: `_parsear_score` ahora decodifica de forma tolerante a profundidad
  (hasta 3 iteraciones de `json.loads` mientras el resultado siga siendo `str`, con tope de
  seguridad) en vez de asumir un número fijo de capas.
- Test de regresión `test_score_parsea_reporte_doble_encodificado` en `tests/test_api.py`
  (doble `json.dumps` real, no solo uno). **37 tests pasando, ruff limpio.**
- **Confirmado con datos reales**: `Score: valor=423 riesgo=MUY ALTO valido=True`.

#### Prueba end-to-end COMPLETA (cobertura + score) — decisión de geodata resuelta
- Flujo completo verificado contra el servidor real: cookie de sesión (login manual con
  2FA) → cobertura (SI, HORIZONTAL, celda 8764) → score (423, MUY ALTO).
- **Decisión de geodata (A/B/C, pendiente desde Fase 0) resuelta a favor de la opción C
  (payload mínimo)**: el score respondió correctamente enviando solo coordenadas +
  documento, con todos los campos de geodata (`distrito`, `ubigeo`, `direccion_instalacion`,
  etc.) vacíos en el payload. No hace falta replicar la geoapi de Equifax (opción A) ni
  pedir datos manuales al agente (opción B).

#### Hallazgos de entorno (bugs, no del flujo de negocio)
- `python tools/probar_core.py` fallaba con `ModuleNotFoundError: No module named
  'validator_app'` — el paquete no está instalado editable en esta máquina.
  `pip install -e .` falla porque `pyproject.toml` exige `Python>=3.14` y la máquina solo
  tiene Python 3.12.2 instalado — pese a que los 35 tests corren bien en 3.12. Workaround
  usado: `$env:PYTHONPATH="."` antes de correr el script. Pendiente decidir si se relaja el
  requisito de versión en `pyproject.toml` o se documenta la instalación real requerida.
- Prueba real del core con credenciales (login → cobertura → score)
- Decidir si llamar a `actualizar_score_cliente`
- Conectar GUI ↔ core end-to-end (más allá de la config de proxy)
- Evaluar creación del lead final (`POST controllers/newsearch.php`)
- Resolver la decisión de geodata del score (opciones A/B/C, ver `AGENTS.md`)
