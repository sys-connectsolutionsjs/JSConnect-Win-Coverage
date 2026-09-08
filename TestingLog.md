# TestingLog.md — Registro de pruebas y metodología

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Metodología preferida: TDD (semáforo)
- **TDD** = Test-Driven Development: escribir el test PRIMERO (rojo: falla),
  ver la necesidad del cambio en el fallo, implementar lo mínimo para que deje
  de fallar y, al final, refactorizar. El test ya no genera el error (verde).
- Este proyecto usa este flujo: 1) test rojo, 2) implementación, 3) test verde.
- Comando de tests: `pytest` (o `python -m pytest -q`).
- Comando de lint: `ruff check .` (config en pyproject.toml, target py314).
- Convención: cualquier cambio de comportamiento va acompañado de su test.

## Inventario de tests (40 en total)
| Archivo | Casos | Qué cubre |
|---|---|---|
| tests/test_fields.py | varios | parseo de coordenadas y detección DNI/RUC/CE |
| tests/test_captura_guard.py | 4 | guard de instancia única de captura.py |
| tests/test_api.py | 17 | núcleo: login, cobertura, score, su parser y `validar_cookie_sesion()` |
| tests/test_prueba_core.py | 6 | lógica del arnés gráfico (flujo, errores, mocks) |

Nota: `tests/test_proxy.py` (FastAPI `TestClient` para las rutas `/admin/*`
y `/health` del proxy) todavía no existe — queda para la Fase 4 del plan
"Sesión WinForce robusta" (`PlanesAprobados.md`).

Nota: `tools/probar_concurrencia.py` NO tiene tests automáticos a propósito (pide
credenciales y hace peticiones reales); se valida con `ruff` e import.

## Bitácora de la sesión de hoy (TDD aplicado)

### Sesión 2026-09-08 — Fase 3: diálogo de cookie en la GUI (arregla standalone)
- [TDD rojo] `tests/test_session_config.py` NUEVO (6 tests). Fake de `keyring`
  (dict) por `monkeypatch` + `core.api.validar_cookie_sesion` mockeado:
  roundtrip `guardar/cargar/borrar`; `validar_y_guardar` recorta espacios y
  guarda solo si la validación pasa; cookie mala (`LoginError`) → propaga y NO
  guarda; cookie vacía → `ValueError`; `cliente_standalone()` devuelve un
  `ValidatorAPI` con `PHPSESSID` inyectada y `_session_max_idle` grande, o `None`.
- [TDD verde] `validator_app/gui/session_config.py` + wiring en `main_window.py`
  (menú + `_abrir_config_sesion` + `_validar_en_hilo` usa `self._session_client`).
- [Verificación] 90 tests, ruff limpio. **Smoke headless**: `App()` arranca, el
  menú "⚙ Configuración" tiene "Configurar Sesión (standalone)", el diálogo abre,
  y sin sesión el estado dice "standalone SIN sesion". (El patrón thread +
  `self.after` es el mismo del diálogo de proxy; funciona con el mainloop real.)

### Sesión 2026-09-08 — Fase 2.5d: extensión de Chrome
- [TDD rojo] `tests/test_proxy.py` estrena **FastAPI `TestClient`** (adelanta parte
  de la Fase 4): `TestClient(server.app, client=("127.0.0.1", N))` para controlar
  `request.client.host`; `get_proxy_api` monkeypatcheado a un `Mock`.
  - `POST /local/renovar` desde `127.0.0.1` → 200, `set_session_cookie` llamado.
  - `POST /local/renovar` desde `10.0.0.9` → 403 (guardia `_es_local`).
  - `set_session_cookie` lanza `LoginError` → 401 (por el `exception_handler` que
    ya existe).
  - `GET /local/estado` → `{session_alive, session_dead_since}` de `get_status`.
- [TDD rojo] `tests/test_instalar_extension.py` NUEVO: `_crx_id` contra su
  definición (sha256 → 32 hex → 0-f a a-p), determinismo, y que cambie con la
  clave; `_render_updates_xml` contiene id/codebase/version.
- [TDD verde] `server.py` (`_es_local` + `/local/*`), `extension/` (manifest MV3 +
  `background.js` + `icon.png` generado con Python), `_instalar_extension.py`.
- [Verificación] 84 tests, ruff limpio. **Smoke real**: `_instalar_extension`
  empaquetó `extension.crx` (2741 B) con `chrome --pack-extension`, generó
  `extension.pem` y calculó un id estable en dos corridas
  (`oclimnkhjeeamemdkdkfdliadmkdafkl`); `updates.xml` correcto; el `winreg` a HKLM
  avisó "sin permisos" sin abortar (correcto sin admin).

### Sesión 2026-09-08 — Fase 2.5: login asistido
- [TDD rojo] `tests/test_login_asistido.py` NUEVO (10 tests). Playwright
  interactivo no se testea en CI → se cubre la lógica pura:
  - `_php_sessid_de_cookies`: filtra la lista de cookies de Playwright por
    nombre + dominio `appwinforce.win.pe`; ignora la `PHPSESSID` de
    `login.microsoftonline.com`; devuelve None si vacía o sin valor.
  - `capturar_php_sessid_asistido` sin Playwright (`_import_sync_playwright`
    monkeypatcheado a `ImportError`) → `LoginAsistidoError` con "--manual".
  - Dispatch de `rotate_creds.main`: `--manual` usa `extract_php_sessid_from_input`
    y NO abre navegador; asistido captura → valida → guarda → `_avisar(ok=True)`;
    fallo de captura o cookie inválida → `_avisar(ok=False)`, exit 1, keyring
    intacto; `--fresh` propaga `fresh=True`; `_avisar` sin tkinter cae a stdout.
- [TDD verde] `login_asistido.py` (perfil persistente, poll de `context.cookies()`,
  overlay), `rotate_creds.py` v2 (dispatch, `_avisar` con `tkinter.messagebox`,
  `_verificar_proxy` extraído).
- [Verificación] 71 tests pasando, ruff limpio. **Smoke real**:
  `capturar_php_sessid_asistido(timeout_min=0)` abre y cierra Chromium sin error y
  lanza `LoginAsistidoError` (esperado sin completar login). `.lnk` de prueba
  creado OK con el one-liner de PowerShell.
- [Añadido] `rotate_creds --preview`: 3 tests (no guarda ni verifica, gana sobre
  `--manual`, fallo de captura avisa). 74 tests, ruff limpio. Abre la ventana sin
  tocar keyring ni `config.yaml` — para probar la UX en desarrollo.
- [Añadido] Chrome real + autofill: `_lanzar_navegador` con `channel="chrome"` y
  fallback a Chromium (2 tests: prefiere Chrome, fallback tras excepción). Se
  probó un flag `--extension` (Bitwarden) y se descartó — el gestor de Chrome
  basta. 76 tests, ruff limpio. Smoke: `_lanzar_navegador` abre Chrome 152 (el
  instalado, no el Chromium empaquetado); UA normal.

### Sesión 2026-09-08 — Fase 2A: keepalive del proxy
- [TDD rojo] `tests/test_proxy.py` NUEVO (abre el archivo de la Fase 4). 12 tests
  sobre `ProxyValidatorAPI` con `core.api` monkeypatcheado (sin red, sin FastAPI
  TestClient todavía): latido perezoso (omitir por tráfico reciente / sin sesión),
  clasificación de un ping fallido (VIVA / TRANSITORIO / SESION_MUERTA /
  INDETERMINADO vía `validar_cookie_sesion()`), `set_session_cookie` limpia
  `session_dead_since`, bloque `keepalive` en `get_status()`, loop async que para
  limpio y sobrevive a un tick que lanza.
- [Prerrequisito] `test_proxy_client_sin_guard_idle_de_120s`: el cliente-core del
  proxy tenía el guard `auto_relogin_if_needed` (`_session_max_idle=120`) que
  lanza `SessionError` en cada hueco > 120 s **antes de tocar la red**; el
  reintento del wrapper volvía a lanzar (nadie resetea `_last_activity`) y
  propagaba. `_get_client()` ahora pone `_session_max_idle = 10**9` (el proxy ya
  gestiona la frescura). Igual que `tools/medir_keepalive.py`, que usa instancia
  nueva por ping para esquivar ese guard.
- [TDD verde] `_keepalive_loop` (`asyncio` en `lifespan`) + `_keepalive_tick`
  (sync, `asyncio.to_thread`), `KeepaliveStatus`, config `keepalive_*`.
- [Verificación] 61 tests pasando, ruff limpio. **Prueba real**: al arrancar el
  proxy en esta PC, el keepalive pingó WinForce con la `PHPSESSID` (muerta) del
  keyring, confirmó la muerte con `validar_cookie_sesion()` y logueó el `ERROR` de
  aviso al owner — el camino de "sesión muerta" quedó ejercitado contra el
  servidor real.

### Sesión 2026-09-08 — Deuda técnica previa a la Fase 2 (sin cambios de código)
- [Problema] `pip install -r requirements.txt` + `python main.py` fallaba con
  `ModuleNotFoundError: httpx`: la GUI (`gui/main_window.py`) importa
  `ProxyClient` (`proxy/client.py`, que hace `import httpx`) siempre, y
  `proxy/__init__.py` también. `httpx` solo estaba en `requirements-proxy.txt`.
  El build no lo notaba porque `requirements-dev.txt` arrastra el de proxy.
  → **Solución**: `httpx>=0.27` movido a `requirements.txt`; quitado el duplicado
  y los comentarios falsos de `requirements-proxy.txt`.
- [Metadatos] `pyproject.toml` `requires-python` bajado de `>=3.14` a `>=3.12`
  (piso real: los tests corren en 3.12 desde 2026-08-27, cero sintaxis 3.13/3.14
  en el código); `ruff target-version = "py312"`. Requisito de versión unificado
  en `>=3.12` en README, `docs/proxy-*.md`, `README_PROXY.md`, `install_service.bat`.
- [Docs] Creados los snapshots faltantes `resumenes/2026-09-04.md` y
  `resumenes/2026-09-05.md` (recuperados verbatim de git).
- [Verificación] 49 tests pasando, ruff limpio (sin cambios respecto a antes).

### Sesión 2026-09-04 — Fase 1 (limpiar login muerto del proxy) + helper compartido
- [TDD rojo] 3 tests nuevos en `tests/test_api.py` para el helper nuevo
  `validar_cookie_sesion()`: cookie válida (no lanza), cookie inválida/
  expirada (`LoginError`), respuesta HTML en vez de JSON (`LoginError`,
  reusa `FakeHtmlResponse`). Se agregó `FakeCookieJar` (dict con `.set()`
  al estilo `requests.cookies.RequestsCookieJar`) a `FakeSesion.cookies`,
  que antes era un dict plano sin ese método.
- [TDD verde] `core/api.py`: nuevo `validar_cookie_sesion(php_sessid)`
  (reutiliza `ValidatorAPI._verificar_sesion_activa`, no duplica el parseo
  de `operador.php`). `rotate_creds.validate_session_cookie()` reescrito
  para delegar en el helper. `server.py`: `/admin/login`/`/admin/rotar`
  pasan a `{php_sessid}`; `_relogin_silent()` reescrito (recarga+revalida
  cookie del keyring en vez de login programático inviable); `session_alive`
  agregado a `/health`/`/admin/status`.
- [Verificación] 40 tests pasando, ruff limpio.
- Detalle completo en `PlanesAprobados.md` (Fase 1) y `ResumenDelDia.md`.

### Sesión 2026-08-21 — Primer intento real + diagnóstico de login
- [Prueba real] El usuario ejecutó `probar_core_gui.py` con sus credenciales
  (pegadas del portapapeles) → `[ERROR LOGIN] No se pudo iniciar sesion (la sesion
  no quedo activa).` Las mismas credenciales SÍ funcionan en el navegador.
- [Hipótesis] 1) Espacios/saltos de línea invisibles al pegar (el navegador los
  recorta; el script los enviaba tal cual). 2) `operador.php` devolviendo HTML
  (WAF/headers) — indistinguible porque el mensaje no daba detalles.
- [TDD rojo] Tests nuevos: `test_espacios_de_portapapeles_se_recortan` (strip de
  usuario/contrasena/coords/documento) y diagnóstico de login: HTML en operador
  debe incluir status/content-type/body en el mensaje (`FakeHtmlResponse`), JSON
  sin éxito debe incluir el `comment`. Nota: `resp.headers.get("content-type")`
  es case-sensitive en dicts comunes (requests usa CaseInsensitiveDict); el
  diagnostico ahora recorre headers comparando en minúsculas.
- [TDD verde] `prueba_core.ejecutar_prueba` hace `.strip()` de las 4 entradas;
  `api._diagnostico(resp)` resume respuestas (HTTP, content-type, body 80 chars,
  SIN datos sensibles); `_verificar_login`/`_verificar_sesion_activa` incluyen el
  diagnóstico en sus mensajes.
- [Estado] Pendiente que el usuario re-ejecute la GUI: si vuelve a fallar, el
  nuevo mensaje mostrará exactamente qué respondió cada endpoint.
- [Verificación] 35 tests pasando, ruff limpio.

### Sesión 2026-08-21 — Arnés gráfico de prueba core
- [Dato] El usuario intentó `probar_core.py` en consola y le confundió que la
  contraseña no apareciera al escribirla (comportamiento NORMAL de `getpass`).
  → Decisión: crear versión gráfica (Tkinter), coherente con que los usuarios
  finales no usan consola.
- [TDD rojo] Creados 6 tests (`tests/test_prueba_core.py`) para la lógica
  reutilizable `validator_app/gui/prueba_core.ejecutar_prueba()` (mockea
  `api.obtener_cliente`; flujo OK, sin cobertura, login inválido, coordenadas
  malas, documento malo, campos vacíos). Fallaban: módulo inexistente.
- [TDD verde] Implementado `prueba_core.py`: devuelve líneas de salida; los
  errores van como líneas `[ERROR ...]` (login/cobertura/score separados).
- [GUI] Creado `tools/probar_core_gui.py` (Tkinter): contrasena oculta con
  `show="*"`, validación en hilo aparte (`threading`) + `after()` para pintar,
  botón deshabilitado mientras valida. Smoke test OK (ventana instancia).
- [Problema] `W292` sin newline final (3 archivos nuevos) → `ruff check . --fix`.
- [Verificación] 31 tests pasando, ruff limpio.

### Sesión 2026-08-19 (tarde) — Retoma desde otra máquina
- [Entorno] Python 3.14.7 instalado (winget) y añadido al PATH de usuario; tras la
  instalación los comandos `python`/`pip` seguían sin resolver hasta abrir una
  terminal nueva o usar la ruta completa
  (`C:\Users\<user>\AppData\Local\Programs\Python\Python314\python.exe`).
- [Entorno] `pip install -e .` fallaba: "Multiple top-level packages discovered in
  a flat-layout: ['generator', 'validator_app']". → Añadir `[project]` +
  `[tool.setuptools.packages.find]` (`include = ["validator_app*"]`) a
  `pyproject.toml`.
- [Problema] `tests/test_captura_guard.py` no colectaba: `ModuleNotFoundError:
  No module named 'playwright'`. → Instalar dependencias dev (`playwright`,
  `pytest`, `ruff`, `pyinstaller`) + `python -m playwright install chromium`.
- [Problema] `W292` (sin newline al final) en `tools/probar_concurrencia.py`.
  → `ruff check . --fix`.
- [Verificación] 25 tests pasando y ruff limpio en la máquina nueva.

### tests/test_api.py — núcleo (nuevo, 14 casos)
Proceso seguido para cada caso:
1. **Rojo**: se escribió el test primero (responde simuladas con FakeResponse/FakeSesion).
2. **Fallo esperado**: `NotImplementedError` del stub de `api.py` (los tests no podían
   pasar porque el core no existía).
3. **Verde**: se construyó `validator_app/core/api.py` + `core/session.py`.
4. **Refactor**: ajustes de estilo/typing por ruff.

### Problemas encontrados y soluciones
| Problema | Causa | Solución |
|---|---|---|
| `test_login_ok` lanzaba `LoginError` y hacia peticiones HTTP reales | `login()` crea la sesión con `session.crear_sesion()` (sesión real), ignorando el `FakeSesion` que el test asignaba a `_sesion` | Mockear `validator_app.core.session.crear_sesion` con `unittest.mock.patch(..., return_value=FakeSesion)` |
| `test_score_parsea_reporte` fallaba con `AttributeError: 'str' object has no attribute 'get'` | El test codificaba el reporte Equifax con DOBLE `json.dumps`, pero la respuesta real es de UNA sola capa: `data` = `json.dumps(reporte)` (el `json.loads` de `data` ya devuelve el dict) | Verificar la codificación real leyendo el body crudo de `tools/captura.json`; corregir el fixture a una sola codificación |
| Mismos `AttributeError` en `test_score_payload_incluye_documento` y `test_validar_flow_con_cobertura` | Misma causa: fixture doble-codificado | Misma solución (fixture corregido) |
| `E501` líneas >100 | Test muy largo | Partir la línea / extraer variable |
| `RUF059` variable desempaquetada sin uso | `metodo, url, kwargs = ...` sin usar `metodo`/`url` en algunos asserts | Usar `_` (dummy) en el desempaquetado |
| `W292` sin salto de línea al final | Write sin newline final | `ruff check . --fix` |
| `SIM117` `with` anidados | Dos `with` consecutivos | Combinar en un solo `with (...)` con paréntesis |
| `UP006/UP035/UP045/UP037` | ruff target py314 exige typing moderno: `dict` en vez de `Dict`, `X \| None` en vez de `Optional`, sin comillas en anotaciones | `from __future__ import annotations` + `dict[str, ...]` + `Any \| None` |
| `B904` | `raise` dentro de `except` sin encadenar | Añadir `from None` |

### Descubrimiento técnico clave (parser del score)
- La respuesta de `score_cliente` es `{"response":"success","data":"<JSON-string>"}`
  donde `<JSON-string>` es el reporte SOAP de Equifax. Tras `json.loads(respuesta)["data"]`,
  un único `json.loads(...)` ya devuelve el dict (NO doble-codificado).
- Puntaje en `ns3ResumenScoreRP3.Puntaje` (ej: 423), `NivelRiesgo`, y deuda en
  `ResumenDeuda.DeudaTotal`. El parser usa una búsqueda recursiva robusta.

## Cómo probar manualmente contra la API real
- `python tools/probar_core.py` → pide usuario/contraseña, coordenadas y documento;
  ejecuta login → cobertura → score. NO muestra la contraseña (getpass).

## Pendiente de pruebas
- Prueba de concurrencia (4-5 máquinas, misma cuenta): ver `PlanesAprobados.md`.
- Prueba real del core con credenciales del responsable (probar_core.py).