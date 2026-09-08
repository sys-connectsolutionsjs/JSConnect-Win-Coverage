# ResumenDelDia.md — Historial del día

Fecha: 2026-09-08

## Estado al cierre

- **Rama `main` = `origin/main`** — todo pusheado. Sin cambios sin commitear
  (salvo este propio `ResumenDelDia.md`).
- **10 commits hoy** (`cae2702` → `76afb9d`, todos `2026-09-08`).
- **104 tests pasando, `ruff check .` limpio.**
- Esta PC: Python **3.14.7** (el repo ahora exige **≥ 3.12**).
- Plan **"Sesión WinForce robusta"**: **Fases 0, 1, 2A, 2.5, 3 y 4 COMPLETAS**.
  Falta solo la **Fase 5 (barrido final de docs)** para cerrarlo.
- El resumen del día **NO se ha rotado** todavía (no se creó `resumenes/2026-09-08.md`
  ni la entrada en `HistorialResumenes.md`). Hacerlo al cerrar sesión de verdad.

---

## Commits del día (en orden)

| SHA | Título | Qué |
|---|---|---|
| `cae2702` | docs: cerrar investigación de keepalive + hook de auto-sync | Sincroniza `PlanesAprobados.md` / `anotaciones.md` / `AGENTS.md` con el desenlace de la corrida keepalive v3 (investigación CERRADA); crea el hook `.claude/hooks/historial_sync.py`. Incluye la rotación pendiente del resumen 2026-09-05 → `HistorialResumenes.md`. |
| `b3aca38` | chore: cerrar deuda técnica previa a la Fase 2 | `httpx` → `requirements.txt`; `requires-python` → `>=3.12`; crea `resumenes/2026-09-04.md` y `2026-09-05.md` (recuperados de git). Sin cambios de código. |
| `b3adb38` | feat: keepalive del proxy ("latido perezoso") + fix guard idle | **Fase 2A.** `_keepalive_loop` + `ProxyValidatorAPI._keepalive_tick` en `server.py`; config `keepalive_*`; fix del guard idle de 120 s del cliente-core. `tests/test_proxy.py` NUEVO. |
| `28b7698` | feat: login asistido — renovar la sesión WinForce con doble clic | **Fase 2.5.** `login_asistido.py` NUEVO (Playwright); `rotate_creds.py` v2 (asistido / `--manual` / `--fresh`). `install_service.bat` descarga Chromium + crea el `.lnk` del Escritorio. `tests/test_login_asistido.py` NUEVO. |
| `c96de4c` | feat: rotate_creds --preview | **Fase 2.5b.** Abre la ventana de captura sin guardar nada ni necesitar `config.yaml`. |
| `cb085da` | feat: login asistido usa Chrome real (autofill de contraseñas) | **Fase 2.5c.** `_lanzar_navegador` abre el Chrome instalado (`channel="chrome"`) con la infobar de automatización desactivada. *(Se creó como `a4c14dd` con un flag `--extension`; se hizo **amend** para quitarlo — el gestor de Chrome basta.)* |
| `499ba5f` | feat: extensión de Chrome para renovar con un clic | **Fase 2.5d.** `validator_app/proxy/extension/` (MV3) + endpoints `/local/renovar` y `/local/estado` en `server.py` + `_instalar_extension.py` (empaqueta `.crx`, política force-install). |
| `e517a2b` | docs: guía para probar la extensión en desarrollo | Sección "Probar la extensión en desarrollo" en `README_PROXY.md`. |
| `5cf8e3f` | feat: Fase 3 — diálogo de cookie en la GUI (arregla standalone) | `validator_app/gui/session_config.py` NUEVO + menú "⚙ Configurar Sesión (standalone)" en `main_window.py`. `tests/test_session_config.py` NUEVO. |
| `76afb9d` | test: cubrir la capa FastAPI del proxy | **Fase 4.** 14 tests de `/api/*`, `/health`, `/admin/*`, middleware de auth y exception handlers en `tests/test_proxy.py`. |

---

## Cómo empezó la sesión

- Repo local **6 commits por detrás** de `origin/main` (`1dcecc6` → `3c1baa5`).
  `git pull --ff-only` limpio. Esos 6 commits son de la sesión 2026-09-05 (otra
  máquina).
- Revisado el diff del proxy (`5506ed4`): caché de `session_alive` 30 s + logging
  de cada fallo de sesión con remedio + `logging.basicConfig` en `__main__`.

---

## 1 · Investigación de keepalive — CERRADA (reporte final de la corrida v3)

`tools/medir_keepalive.py` v3, corrida iniciada 2026-09-05 21:08 (sesión a 70 s de
edad), ping fijo cada 900 s, 49 coords rotativas de `tools/coords_prueba.txt`.
Reporte final recibido hoy (`medir_keepalive.log` — **local, gitignored,
`*.log`**; no viaja a otra máquina, pero las conclusiones están en los docs):

- **37 pings consecutivos VIVA**; última confirmación VIVA a **33 370 s de edad de
  sesión (≈ 9 h 16 m)**.
- Murió **limpia** a **34 270 s (≈ 9 h 31 m)**: categoría `SESION_MUERTA`, patrón
  HTTP 200 + `text/html` (HTML de login), **confirmado por
  `core.api.validar_cookie_sesion()`** de forma independiente.

Lecturas:
- **Idle-timeout descartado** como causa de esta muerte (ping real cada 900 s;
  última confirmación VIVA 900 s antes de morir). El keepalive de 15 min resuelve
  el idle-timeout de Fase 0 (~1200 s) con holgura.
- **Anti-bot acumulativo descartado** (37 pings variados en 9 h, 0 fallos).
- **"Tope absoluto a 40 min" descartado** — era el 404 ambiguo de v1.
- **Sí existe un tope absoluto de sesión ≈ 9.5 h desde el login**, independiente
  de la actividad. Por encima de la jornada de 8 h con ~1.5 h de margen →
  reinyectar la cookie **al inicio del turno**.

Un dato limpio basta (patrón inequívoco + idle-timeout excluido + confirmación
independiente + anti-bot excluido). Una 2ª corrida solo afinaría el número.

**Sincronizado en**: `PlanesAprobados.md` (addendum + Fase 0 act. 2026-09-08 +
Fase 2 + cola activa), `anotaciones.md` `## M` ("Dos límites de sesión" +
"Revisión del método"), `AGENTS.md` (ítems 15–16 + cierre).

### Rotación de resúmenes
- La sesión 2026-09-05 se movió a `HistorialResumenes.md` (condensada, con el
  desenlace v3 incluido). `ResumenDelDia.md` reabierto hoy.
- `resumenes/2026-09-04.md` y `2026-09-05.md` se crearon **después** (commit
  `b3aca38`) recuperándolos de git.

---

## 2 · Hook de auto-actualización de docs

- **`.claude/settings.json`** (NUEVO, versionado) + **`.claude/hooks/historial_sync.py`**
  (NUEVO). Hook `PostToolUse` (matcher `Write|Edit`, forma exec `python
  ${CLAUDE_PROJECT_DIR}/.claude/hooks/historial_sync.py`).
- Al **agregar entradas** (`### YYYY-MM-DD`) a `HistorialResumenes.md`, inyecta un
  recordatorio (additionalContext, no bloqueante) para sincronizar
  `anotaciones.md` / `PlanesAprobados.md` / `AGENTS.md`. **Cada 3 entradas nuevas
  acumuladas**, además recuerda `README.md`.
- Estado local: `.claude/hooks/historial_sync_state.local.json`
  (`{last_entry_count, readme_baseline_count}`), gitignored vía
  `.claude/hooks/*.local.json`. Primera ejecución en una máquina nueva = siembra
  la línea base y no molesta.
- Cuenta hoy: 8 entradas en `HistorialResumenes.md`. Probado en vivo (sembrando
  el estado a 7 y editando el archivo → el recordatorio apareció).
- Documentado en `AGENTS.md` → "Regla de auto-actualización de la documentación".

---

## 3 · Deuda técnica cerrada (commit `b3aca38`)

- **`httpx` → `requirements.txt`**: la GUI importa `ProxyClient`
  (`proxy/client.py` → `import httpx`) siempre, y `proxy/__init__.py` también; un
  `pip install -r requirements.txt` + `python main.py` fallaba con
  `ModuleNotFoundError: httpx`. Movido a `requirements.txt`; quitado el duplicado
  y los comentarios falsos de `requirements-proxy.txt`.
- **`requires-python` → `>=3.12`** (era `>=3.14`): piso real — los tests corren en
  3.12 desde 2026-08-27 y no hay sintaxis 3.13/3.14 en el código.
  `ruff target-version = "py312"`. Requisito de versión **unificado en `3.12+`**:
  `README.md` (ES+EN), `docs/proxy-deploy.md`, `docs/proxy-config.md`,
  `README_PROXY.md`, `install_service.bat`, `AGENTS.md`, `anotaciones.md`.
- **Snapshots faltantes creados**: `resumenes/2026-09-04.md`
  (`git show 44d1132~1:ResumenDelDia.md`) y `resumenes/2026-09-05.md`
  (`git show 3c1baa5:ResumenDelDia.md`), verbatim, con el H1 ajustado.
- La deuda quedó **marcada resuelta con rastro** (no borrada) en `PlanesAprobados.md`
  (tachado + "RESUELTO"), `AGENTS.md` (ítem 21 `[COMPLETADO]`), `ResumenDelDia.md`,
  `TestingLog.md`.

---

## 4 · Fase 2A — Keepalive del proxy ("latido perezoso") — commit `b3adb38`

- **`_keepalive_loop`** (`asyncio` en el `lifespan` de `server.py`) —
  arranca/para con el servicio; cada tick corre en `asyncio.to_thread` (el
  cliente-core es síncrono). Un tick que lanza no mata el loop.
- **`ProxyValidatorAPI._keepalive_tick`** (síncrono, 100 % testeable):
  1. **Latido perezoso**: si `now - _last_activity < keepalive_interval_seconds`
     → `omitido/trafico_reciente` (los agentes ya mantienen la sesión viva).
  2. Sin `PHPSESSID` → `omitido/sin_sesion`.
  3. Ping = `validar_cobertura` con coord de `_KEEPALIVE_COORDS` (12 puntos
     públicos de Lima embebidos en `server.py`; las 49 completas siguen en
     `tools/coords_prueba.txt`), elegida con `random.choice`.
  4. Ping fallido → `_keepalive_registrar_fallo`: confirma con
     `validar_cookie_sesion()`. Endpoint caído → `TRANSITORIO` (warning). Sesión
     muerta → `SESION_MUERTA`: `log.error` **una vez** con el remedio (renovar la
     cookie), pone `_session_dead_since`, y en ciclos siguientes solo `warning`.
     Indeterminado (no se pudo confirmar) → warning. **Nunca reintenta en
     silencio.**
- **Config nueva** (`config.py` + `config.yaml.example` + `install_service.bat`):
  `keepalive_enabled: bool = True`, `keepalive_interval_seconds: int = 900`.
- **`/admin/status`**: bloque `keepalive` nuevo
  (`{enabled, last_ping_at, last_ping_ok, consecutive_failures, session_dead_since}`).
  `set_session_cookie()` limpia `_session_dead_since` y los contadores.
- **PRERREQUISITO — bug latente arreglado**: el cliente-core cacheado del proxy
  tenía el guard `auto_relogin_if_needed` (`_session_max_idle = 120`) que lanza
  `SessionError` en **cada hueco de tráfico > 120 s** *antes de tocar la red*, y
  el reintento del wrapper volvía a lanzar (nadie resetea `_last_activity`) →
  propagaba. El keepalive (huecos de 900 s) lo habría vuelto constante.
  **Fix**: `ProxyValidatorAPI._get_client()` pone `self._client._session_max_idle
  = 10**9` (el proxy ya gestiona la frescura). Igual que hace `medir_keepalive.py`
  con instancia nueva por ping.
- **Tests**: `tests/test_proxy.py` NUEVO — 12 tests (latido perezoso, clasificación
  de fallos, limpieza al renovar, **regresión del guard**, loop async que para
  limpio / sobrevive a un tick que lanza).
- **Validado end-to-end contra WinForce real**: al arrancar el proxy en esta PC,
  el keepalive pingó con la `PHPSESSID` muerta del keyring, la detectó (HTTP 200 +
  HTML), la confirmó con `validar_cookie_sesion()` y disparó el `ERROR` de aviso
  al owner — exactamente lo diseñado.

---

## 5 · Fase 2.5 — Renovación de la sesión sin F12

Por el tope absoluto ≈ 9.5 h, el owner renueva la cookie ~1 vez por jornada. El
flujo viejo (`rotate_creds.py` original) pedía F12 + copiar/pegar — inviable para
alguien sin conocimientos técnicos. Se rehízo en varias capas:

### 2.5 — Login asistido (`28b7698`) — ahora es el FALLBACK
- **`validator_app/proxy/login_asistido.py`** NUEVO. `capturar_php_sessid_asistido()`
  abre un navegador, el owner inicia sesión normalmente, el script sondea
  `context.cookies()` buscando la `PHPSESSID` de `appwinforce.win.pe` (**la API de
  Playwright ve las cookies HttpOnly, `document.cookie` no**), la valida con
  `validar_cookie_sesion()` y la devuelve. Overlay flotante en la ventana
  (patrón de `tools/captura.py`); `page.on("close")`; timeout.
- **`rotate_creds.py` → v2**: sin args = asistido, resultado por
  `tkinter.messagebox`; corre bajo `pythonw.exe` (sin consola). `--manual` = el
  copiar/pegar de antes (fallback sin Playwright). `--fresh` borra el perfil.
- **Perfil persistente** `validator_app/proxy/.browser_profile/` (gitignored):
  mantiene la sesión de Microsoft → **el SSO salta el 2FA solo dentro de la misma
  jornada** (a la siguiente jornada lo pide otra vez — política de Microsoft; el
  perfil persistente no lo empeora).
- `install_service.bat`: paso `python -m playwright install chromium` + paso que
  crea el `.lnk` **"Renovar sesion WinForce"** en el Escritorio (PowerShell
  WScript.Shell, target `pythonw.exe`). `playwright>=1.45` → `requirements-proxy.txt`
  (quitado el suelto de `requirements-dev.txt`).
- `tests/test_login_asistido.py` NUEVO (13 tests al final).
- Smoke: `capturar_php_sessid_asistido(timeout_min=0)` abre/cierra Chrome limpio y
  lanza `LoginAsistidoError`.

### 2.5b — `--preview` (`c96de4c`)
`rotate_creds --preview` abre la ventana, imprime la `PHPSESSID` en la terminal y
muestra un `messagebox`, **sin guardar nada ni necesitar `config.yaml`**. Para
inspeccionar la UX.

### 2.5c — Chrome real + autofill (`cb085da`)
- `_lanzar_navegador()` abre el **Google Chrome instalado** (`channel="chrome"`)
  con `ignore_default_args=["--enable-automation"]` +
  `--disable-blink-features=AutomationControlled` → el gestor de contraseñas de
  Chrome autocompleta. Fallback automático a Chromium empaquetado si no hay Chrome.
- El owner, **una vez**, inicia sesión en Chrome (cuenta de Google) o guarda la
  contraseña de Microsoft en esa ventana (perfil dedicado) → desde entonces se
  autocompleta y solo queda aprobar el 2FA.
- Se creó como `a4c14dd` con un flag `--extension <ruta>` (cargar Bitwarden
  desempaquetado); el usuario pidió quitarlo → **amend** → `cb085da` sin ese flag.

### 2.5d — Extensión de Chrome (`499ba5f`) — VÍA PRINCIPAL
El owner **no quiere ventana aparte**: quiere renovar desde su Chrome de siempre,
ya logueado. **No se puede adjuntar Playwright a ese Chrome** — Chrome 136+ (2025)
bloquea `--remote-debugging-port` cuando se usa el perfil por defecto
(anti-robo-de-cookies). → **extensión**.

- **`validator_app/proxy/extension/`** NUEVO: `manifest.json` (MV3, permisos
  `cookies` / `alarms` / `notifications`, host_permissions
  `https://appwinforce.win.pe/*` + `http://127.0.0.1:8080/*`), `background.js`
  (~50 líneas), `icon.png` (128×128 verde, generado con Python).
  - Badge rojo `!` cuando la sesión murió (poll `GET /local/estado` cada 5 min +
    `onStartup`/`onInstalled`).
  - Clic → `chrome.cookies.get({url: "https://appwinforce.win.pe", name:
    "PHPSESSID"})` → `POST http://127.0.0.1:8080/local/renovar {php_sessid}` →
    `chrome.notifications` con el resultado.
  - El puerto `8080` es fijo en la plantilla; `_instalar_extension.py` lo
    sustituye por el real al construir.
- **`server.py`** — endpoints locales (`_es_local`: solo `127.0.0.1`/`::1`, sin
  admin key — petición local ya es de confianza + el proxy valida la cookie contra
  WinForce igual): `POST /local/renovar` (reusa `set_session_cookie`),
  `GET /local/estado` (reusa `get_status`).
- **`validator_app/proxy/_instalar_extension.py`** NUEVO (lo llama
  `install_service.bat`, paso `[7/11]`). Idempotente:
  1. Copia `extension/` → `.extension_build/`, sustituye el puerto.
  2. Empaqueta un `.crx` firmado: `chrome --pack-extension` (genera `extension.pem`
     la 1ª vez → **id de extensión estable**).
  3. Calcula el id (`_crx_id`: SHA-256 de la clave pública DER, 32 hex, 0-f→a-p),
     escribe `updates.xml` (`_render_updates_xml`).
  4. Escribe la política `HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionSettings\<id>`
     = `{"installation_mode": "force_installed", "update_url": "file:///…/updates.xml"}`
     (`winreg`) → Chrome la instala sola al reabrir, **sin modo desarrollador**,
     sin poder quitarla por error.
  - `--uninstall` (lo llama `uninstall_service.bat`) borra la clave.
- **`.gitignore`**: `.extension_build/`, `extension.pem`, `extension.crx`,
  `updates.xml`.
- **Tests**: `tests/test_proxy.py` estrena **FastAPI `TestClient`** (5 tests de
  `/local/*`); `tests/test_instalar_extension.py` NUEVO (`_crx_id`,
  `_render_updates_xml`).
- **Smoke real**: `_instalar_extension` empaquetó `extension.crx` (2741 B), generó
  `extension.pem` y calculó un id **estable en dos corridas**
  (`oclimnkhjeeamemdkdkfdliadmkdafkl`); `updates.xml` correcto; la escritura HKLM
  avisó "sin permisos" sin abortar (correcto sin admin).

### 2.5 — Guía de prueba (`e517a2b`)
Sección "Probar la extensión en desarrollo" en `README_PROXY.md` (cargar
descomprimida + proxy local + `revisarEstado()` en la consola del service worker +
`/local/*` + clic real + limpieza). Puntero en `docs/rotacion-credenciales.md`.

---

## 6 · Fase 3 — Diálogo de cookie en la GUI (arregla el modo standalone) — `5cf8e3f`

- **El bug**: la rama standalone de `main_window.py:_validar_en_hilo` llamaba
  `api.obtener_cliente().validar(...)` sobre un `ValidatorAPI` **sin sesión**
  (`_sesion is None`) → siempre `SessionError`. Standalone estaba roto de raíz.
- **`validator_app/gui/session_config.py`** NUEVO (lógica pura, testeable):
  - `guardar_cookie` / `cargar_cookie` / `borrar_cookie` — keyring
    `JSWinCoverage` / `session_cookie`.
  - `validar_y_guardar(php_sessid)` — recorta espacios, valida con
    `core.api.validar_cookie_sesion` y guarda. `ValueError` si vacío, `LoginError`
    si la sesión no está activa.
  - `cliente_standalone()` — `ValidatorAPI` con `set_session_cookies({"PHPSESSID":
    ck})`, `_session_max_idle = 10**9` (el usuario re-pega la cookie a mano; sin
    re-login automático). `None` si no hay cookie.
- **`main_window.py`**:
  - Menú "⚙ Configuración → **Configurar Sesión (standalone)**" +
    `_abrir_config_sesion()` (diálogo modal clonado del de proxy: campo `show="•"`,
    "Mostrar", "Probar y guardar" en hilo, "Quitar sesión guardada").
  - `_load_proxy_config` carga también `cliente_standalone()`;
    `_actualizar_estado_standalone()` pone el label: "standalone, sesión
    configurada" o "standalone SIN sesión — menú ⚙…".
  - `_validar_en_hilo` usa `self._session_client`; sin sesión → `SessionError` con
    el remedio.
- **`api.obtener_cliente()` se CONSERVA** — lo usan `tools/probar_core.py`,
  `tools/probar_concurrencia.py`, `validator_app/gui/prueba_core.py` (y tests).
  Solo la rama standalone de `main_window` deja de usarlo.
- **`tests/test_session_config.py`** NUEVO (6 tests). Smoke headless: `App()`
  arranca, el menú tiene el ítem, el diálogo abre, sin sesión el estado es el
  correcto. (El patrón thread + `self.after` es el mismo del diálogo de proxy;
  "main thread is not in main loop" en el smoke es artefacto de no tener mainloop,
  en la app real funciona.)

---

## 7 · Fase 4 — Cubrir la capa FastAPI del proxy con tests — `76afb9d`

- Fixture `client` en `tests/test_proxy.py`: `ProxyConfig(proxy_token="t"*64,
  admin_key="k"*64, allowed_networks=["127.0.0.0/8", "10.0.0.0/8"])`;
  `server.get_config` y `server.get_proxy_api` monkeypatcheados;
  `TestClient(server.app, client=("10.0.0.5", 5000))`.
- **14 tests**: `/health` (público); `/api/cobertura` y `/api/score` (OK con
  `X-Proxy-Token` + proxy mockeado; token malo → 401; IP fuera de
  `allowed_networks` → 403; documento inválido → 422); `/admin/config` (sin key →
  401, con key → 200); `/admin/login` + `/admin/rotar` (→ `set_session_cookie`);
  `/admin/status` (bloque keepalive); exception handlers (`LoginError`→401,
  `ScoreError`→502, `APIError`→502); `_ip_in_allowed_networks` directo.
- **104 tests, ruff limpio. Ningún bug en `server.py`** — la capa HTTP del proxy
  quedó cubierta sin cambios de código. Cierra el gap histórico "no hay tests del
  proxy".
- `tests/test_proxy.py` = **31 tests** en total (keepalive 2A + `/local/*` 2.5d +
  capa FastAPI 4).

---

## Decisiones y descubrimientos clave (para el próximo dev)

- **Tope absoluto de sesión WinForce ≈ 9.5 h desde el login** (medido con v3,
  independiente de la actividad). El keepalive NO lo evita → aviso al owner +
  reinyección de cookie al inicio del turno. Re-login programado inviable por 2FA.
- **Chrome 136+ (mayo 2025) bloquea `--remote-debugging-port` con el perfil por
  defecto** — medida anti-robo-de-cookies de Google. Por eso NO se puede
  adjuntar Playwright al Chrome cotidiano del owner; hubo que hacer una extensión.
- **`chrome.cookies` (API de extensión) y `context.cookies()` (Playwright) SÍ leen
  cookies HttpOnly.** `document.cookie` (JS de página / bookmarklet) NO — por eso
  un bookmarklet no serviría.
- **Bug latente arreglado**: el guard idle de 120 s del cliente-core
  (`auto_relogin_if_needed`) rompía el proxy en cada hueco de tráfico > 120 s.
  `ProxyValidatorAPI._get_client()` y `session_config.cliente_standalone()` ambos
  ponen `_session_max_idle = 10**9`.
- **`config.yaml` NO se está leyendo** — pydantic-settings avisa "Config key
  `yaml_file` is set … but will be ignored, no YamlConfigSettingsSource source is
  configured". El proxy funciona por defaults + variables `PROXY_*`.
  `install_service.bat` genera `config.yaml` pero el server no lo lee. **Sin
  arreglar** (out of scope hoy; anotado). Fix: `settings_customise_sources` con
  `YamlConfigSettingsSource` en `config.py`.
- **Modo standalone estaba roto de raíz** desde siempre (`api.obtener_cliente()`
  devuelve un `ValidatorAPI` sin sesión). Arreglado en la Fase 3.
- **Perfil de navegador persistente**: el SSO de Microsoft salta el 2FA **solo
  dentro de la misma jornada**; a la siguiente jornada lo pide otra vez.

---

## Archivos nuevos hoy (con propósito)

| Archivo | Propósito |
|---|---|
| `.claude/settings.json` | Registra el hook `PostToolUse` de doc-sync (versionado). |
| `.claude/hooks/historial_sync.py` | Hook: recuerda sincronizar docs al crecer `HistorialResumenes.md`. |
| `validator_app/proxy/login_asistido.py` | Captura de `PHPSESSID` con navegador (Playwright, Chrome real). |
| `validator_app/proxy/_instalar_extension.py` | Empaqueta el `.crx` + fuerza-instala la extensión por política. |
| `validator_app/proxy/extension/manifest.json` · `background.js` · `icon.png` | Extensión MV3 "Renovar sesion WinForce". |
| `validator_app/gui/session_config.py` | Cookie del modo standalone (keyring + validación + cliente). |
| `resumenes/2026-09-04.md` · `resumenes/2026-09-05.md` | Snapshots recuperados de git. |
| `tests/test_proxy.py` | Keepalive + `/local/*` + capa FastAPI del proxy (31 tests). |
| `tests/test_login_asistido.py` | Login asistido + dispatch de `rotate_creds` (13 tests). |
| `tests/test_instalar_extension.py` | `_crx_id` + `_render_updates_xml` (3 tests). |
| `tests/test_session_config.py` | Cookie standalone (6 tests). |

Modificados clave: `validator_app/proxy/server.py` (keepalive + `/local/*`),
`validator_app/proxy/rotate_creds.py` (v2), `validator_app/proxy/config.py`
(`keepalive_*`), `validator_app/gui/main_window.py` (menú + diálogo + standalone),
`validator_app/proxy/install_service.bat` / `uninstall_service.bat`,
`requirements.txt` / `requirements-proxy.txt` / `requirements-dev.txt`,
`pyproject.toml`, `.gitignore`, y los docs (`AGENTS.md`, `PlanesAprobados.md`,
`anotaciones.md`, `README.md`, `README_PROXY.md`, `docs/rotacion-credenciales.md`,
`docs/arquitectura.md`, `TestingLog.md`).

---

## Pendiente

### Fase 5 — Barrido final de docs (última del plan "Sesión WinForce robusta")
- `docs/proxy-config.md`, `docs/proxy-deploy.md` — revisar coherencia (versión de
  Python ya unificada hoy; falta repasar el flujo de renovación de sesión, que
  ahora es la extensión).
- `docs/rotacion-credenciales.md` — tiene todavía secciones antiguas:
  "Procedimiento Futuro (v2 — Remoto via VPN)" y una tabla de troubleshooting que
  se solapa con la nueva. Consolidar.
- `docs/arquitectura.md` — ya se actualizó (keepalive, decisión #9); repasar que
  mencione los endpoints `/local/*` y la extensión.
- Coherencia general: que todos los docs cuenten la misma historia (extensión =
  principal, login asistido + `--manual` = fallback).

### Deuda / verificaciones manuales (necesitan cookie real + 2FA)
- Probar la **GUI en modo standalone** con una `PHPSESSID` real (menú → Configurar
  Sesión → pegar → validar → validar cobertura/score).
- Probar la **extensión** end-to-end (cargar descomprimida, proxy corriendo,
  login en WinForce, clic → renovado). Guía en `README_PROXY.md`.
- Probar el **login asistido** (`.lnk` del Escritorio / `rotate_creds`).

### Deuda vieja (no de hoy)
- `config.yaml` no se lee (ver "Decisiones y descubrimientos").
- Decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`.
- `pyproject.toml` exige `Python>=3.12` — ya no bloquea 3.12; nada más que hacer.

---

## Para continuar en OTRA MÁQUINA

1. **`git pull --ff-only`** — todo está en `origin/main` (hasta `76afb9d`).
2. **`pip install -r requirements-dev.txt`** (arrastra `requirements-proxy.txt`,
   que ahora incluye `playwright`).
3. **`python -m playwright install chromium`** (para `login_asistido.py` y
   `tools/captura.py`).
4. **Verificar**: `python -m pytest -q` → **104 passed**; `python -m ruff check .`
   → clean.

### Qué NO viaja (solo vive en esta PC — gitignored o keyring)
- **Keyring de esta PC**: `JSWinProxy/credentials_cookies` tiene **una `PHPSESSID`
  muerta** que usé para el smoke del keepalive y de la extensión (por eso
  `session_alive` da `false` sin más). En la máquina nueva el keyring está vacío →
  el proxy arranca "sin sesión" (correcto). `JSWinClient/*` y
  `JSWinCoverage/session_cookie` **no están** ni aquí ni allá.
- **Gitignored (se regeneran)**: `validator_app/proxy/.browser_profile/`,
  `.extension_build/`, `extension.pem`, `extension.crx`, `updates.xml`,
  `.claude/hooks/historial_sync_state.local.json`, `medir_keepalive.log` y demás
  `*.log`, `config.yaml` (lo genera `install_service.bat`, pero **el server no lo
  lee** — ver Decisiones).
- **`extension.pem`** NO viaja → al re-empaquetar la extensión en otra PC el id
  será **distinto** (`oclimnkhjeeamemdkdkfdliadmkdafkl` es el de esta PC). Es
  irrelevante salvo que quieras el mismo id en dos sitios (no hace falta).

### El proxy de prueba está PARADO
Durante la sesión levanté `python -m validator_app.proxy.server` en segundo plano
para una demo de la extensión; **ya está parado** (`taskkill` sobre el PID que
escuchaba en 8080). Los tokens de esa corrida quedaron en el scratchpad de la
sesión — **no reutilizar**, generar nuevos.

### Incidente a recordar
Al limpiar un Chrome zombie de una prueba usé `taskkill /F /IM chrome.exe /T`, que
**cerró TODO Chrome de la máquina** (no solo el de la prueba). Si había pestañas
abiertas, Chrome las ofrece restaurar. **No repetir** — matar solo el proceso hijo
del perfil de prueba.

### El hook de doc-sync en la máquina nueva
`.claude/settings.json` viaja (versionado). En la primera edición de
`HistorialResumenes.md` allí, el hook siembra su línea base
(`historial_sync_state.local.json`) y no molesta; a partir de la 2ª entrada nueva
empieza a recordar. Si no se carga, abrir `/hooks` una vez o reiniciar Claude Code
(el watcher solo vigila `.claude/` si el archivo existía al arrancar).

### Cierre de sesión real (cuando el usuario diga que cierra)
- Crear `resumenes/2026-09-08.md` = copia de este archivo (H1 → `# Resumen — 2026-09-08`).
- Añadir la entrada condensada arriba del todo en `HistorialResumenes.md`
  (dispara el hook — normal).
- Reabrir `ResumenDelDia.md` con la fecha nueva.
- Actualizar `AGENTS.md` (Historial) si falta algo.
