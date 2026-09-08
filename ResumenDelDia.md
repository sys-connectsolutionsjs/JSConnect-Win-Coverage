# ResumenDelDia.md — Historial del día

Fecha: 2026-09-08

## Qué se hizo hoy

### 2026-09-08 — Sesión — Actualizar el repo, cerrar la investigación de keepalive y rotar resúmenes

#### Inicio
- Repo local **6 commits por detrás** de `origin/main` (`1dcecc6` → `3c1baa5`).
  `git pull --ff-only` limpio, fast-forward, sin conflictos. Los 6 commits
  (`5506ed4`, `44d1132`, `3925dbf`, `26e7567`, `82f9a4c`, `3c1baa5`) son de la
  sesión 2026-09-05, hecha en la otra máquina y ya pusheada.
- Revisado el diff del proxy (`5506ed4`, único commit que toca
  `validator_app/proxy/server.py`): caché de `session_alive` 30s atada a la
  cookie + logging de cada fallo de sesión con remedio + `logging.basicConfig`
  en `__main__`. Sin cambio de contrato ni rutas nuevas.

#### Desenlace de la corrida keepalive v3 — investigación CERRADA
Llegó el reporte final del test (`tools/medir_keepalive.py` v3, corrida iniciada
2026-09-05 21:08, ping fijo cada 900s, 49 coords rotativas):
- **37 pings consecutivos VIVA**; última confirmación VIVA a los **33 370s de
  edad de sesión (556.2 min ≈ 9 h 16 m)**.
- Murió **limpia** a los **34 270s (571.2 min ≈ 9 h 31 m)**: categoría del ping
  `SESION_MUERTA`, patrón HTTP 200 + `text/html` (HTML de login), **confirmado de
  forma independiente** por `core.api.validar_cookie_sesion()`.

Lecturas:
- **Idle-timeout descartado como causa** de esta muerte — ping real cada 900s y
  última confirmación VIVA 900s antes de morir. El keepalive de 15 min resuelve
  el idle-timeout de Fase 0 (~1200s) con holgura enorme.
- **Anti-bot acumulativo descartado** — 37 pings con coords variadas en 9 h, 0 fallos.
- **"Tope absoluto a 40 min" descartado** — era el 404 ambiguo de v1.
- **Sí existe un tope absoluto de sesión ≈ 9.5 h desde el login**, independiente
  de la actividad. Queda por encima de la jornada de 8 h con ~1.5 h de margen →
  reinyectar la cookie al inicio del turno, no a media mañana.

Un dato limpio basta aquí (a diferencia del 404 ambiguo de v1): patrón de muerte
inequívoco, idle-timeout excluido por los pings activos, confirmación
independiente, anti-bot excluido. Una 2ª corrida solo afinaría el número exacto
y no cambia el diseño de la Fase 2.

#### Rotación de resúmenes
- La sesión **2026-09-05** se movió a `HistorialResumenes.md` (condensada, con el
  desenlace v3 incluido para que quede autocontenida). `ResumenDelDia.md`
  reabierto con la fecha de hoy.
- `resumenes/2026-09-05.md` (snapshot completo) **no se creó** — igual que
  `2026-09-04.md`; se deja como deuda menor.

#### Sincronización de documentación — HECHO
- **Investigación cerrada sincronizada** en los tres docs:
  - `PlanesAprobados.md`: addendum (ahora 2026-09-08), Fase 0 (act. 2026-09-08
    con el desenlace), Fase 2 → "[LISTA PARA IMPLEMENTAR]" + aviso al owner por el
    tope ≈ 9.5 h, "cola activa" (bullet de la corrida marcado CERRADO).
  - `anotaciones.md` (`## M`): "Dos límites de sesión" (recuadro de estado +
    "Implicación de diseño": el tope ≈ 9.5 h ya es un hecho medido) y "Revisión
    del método" (resultado final en vez de "en curso toda la noche").
  - `AGENTS.md`: ítems 15 ("[CERRADA]") y 16 ("[LISTA PARA IMPLEMENTAR]"), tree
    (`.claude/`, `HistorialResumenes.md`), nota del hook en la regla de
    auto-actualización, y `### Cierre de la sesión 2026-09-08`.
- **Hook de auto-actualización de docs creado**: `.claude/settings.json` +
  `.claude/hooks/historial_sync.py` (hook `PostToolUse`). Vigila
  `HistorialResumenes.md`: al agregar entradas recuerda sincronizar
  `anotaciones.md` / `PlanesAprobados.md` / `AGENTS.md`; cada 3 entradas nuevas,
  también `README.md`. Estado local en `historial_sync_state.local.json`
  (gitignored vía `.claude/hooks/*.local.json`).

#### Deuda técnica cerrada (antes de la Fase 2)
- **`httpx` → `requirements.txt`**: la GUI importa `ProxyClient`
  (`proxy/client.py` → `import httpx`) siempre, y `proxy/__init__.py` también;
  `pip install -r requirements.txt` + `python main.py` fallaba con
  `ModuleNotFoundError: httpx`. Quitado el duplicado y los comentarios falsos de
  `requirements-proxy.txt`.
- **`requires-python` → `>=3.12`**: piso real (tests en 3.12 desde 2026-08-27,
  cero sintaxis 3.13/3.14 en el código). `ruff target-version = "py312"`.
  Requisito de versión unificado en `3.12+`: `README.md` (ES+EN),
  `docs/proxy-deploy.md`, `docs/proxy-config.md`, `README_PROXY.md`,
  `install_service.bat`, `AGENTS.md`, `anotaciones.md`.
- **Snapshots faltantes creados**: `resumenes/2026-09-04.md` y
  `resumenes/2026-09-05.md`, recuperados verbatim de git
  (`44d1132~1` y `3c1baa5`).
- Sin cambios de código; **49 tests, ruff limpio**. Nota en `TestingLog.md`.

#### Fase 2A — Keepalive del proxy ("latido perezoso") — HECHO
- **`_keepalive_loop`** (`asyncio` en el `lifespan` de `server.py`) +
  **`ProxyValidatorAPI._keepalive_tick`** (síncrono, corre en `asyncio.to_thread`).
  Config `keepalive_enabled` / `keepalive_interval_seconds` (**900**) en `config.py`
  (+ `config.yaml.example`, `install_service.bat`).
- **Latido perezoso**: el tick no pinga si `now - _last_activity < intervalo`
  (los agentes ya mantienen la sesión viva); solo cubre los huecos. Ping =
  `validar_cobertura` con coord pública rotada al azar (`_KEEPALIVE_COORDS`, 12
  puntos embebidos; las 49 siguen en `tools/coords_prueba.txt`).
- **Aviso al owner**: ping fallido → se confirma con `validar_cookie_sesion()`.
  Endpoint caído → `TRANSITORIO` (warning). Sesión muerta → `log.error` (una vez)
  con el remedio + `session_dead_since` poblado en `/admin/status` (nuevo bloque
  `keepalive`). **No reintenta en silencio.**
- **Prerrequisito arreglado**: `_get_client()` pone `_session_max_idle = 10**9`
  en el cliente-core — su guard idle de 120 s lanzaba `SessionError` en cada hueco
  > 120 s (el proxy ya gestiona la frescura por su cuenta). Bug latente que el
  keepalive habría vuelto constante.
- **`tests/test_proxy.py` NUEVO** (12 tests: latido perezoso, clasificación de
  fallos, limpieza al renovar, regresión del guard, loop async). **61 tests, ruff
  limpio.**
- **Validado end-to-end contra WinForce real**: al arrancar en esta PC, el
  keepalive detectó la `PHPSESSID` muerta del keyring y disparó el `ERROR` de
  aviso al owner — exactamente lo diseñado.

#### Fase 2.5 — Login asistido (renovar la sesión sin F12) — HECHO
- **`validator_app/proxy/login_asistido.py` NUEVO**: `capturar_php_sessid_asistido()`
  abre Chromium con `launch_persistent_context` (perfil `.browser_profile/`,
  gitignored), el owner inicia sesión normalmente y el script sondea
  `context.cookies()` buscando la `PHPSESSID` de `appwinforce.win.pe` (ve las
  **HttpOnly**, a diferencia de `document.cookie`). Al encontrarla la valida con
  `validar_cookie_sesion()` y la devuelve. Overlay verde en la ventana al capturar.
- **`rotate_creds.py` → v2**: sin argumentos = asistido, resultado por
  `tkinter.messagebox` ("✓ Sesión renovada"), corre bajo `pythonw.exe` (sin
  consola). `--manual` = el copiar/pegar de antes (fallback si Playwright se
  rompe). `--fresh` borra el perfil del navegador. `--preview` (añadido después)
  abre la ventana para inspeccionarla sin guardar nada ni necesitar `config.yaml`.
- **Chrome real + autofill (añadido después)**: `_lanzar_navegador` abre el
  **Google Chrome instalado** (`channel="chrome"`) con
  `ignore_default_args=["--enable-automation"]` +
  `--disable-blink-features=AutomationControlled` → el gestor de contraseñas de
  Chrome autocompleta. El owner inicia sesión en Chrome (Google) o guarda la
  contraseña una vez y luego solo aprueba el 2FA. Fallback a Chromium si no hay
  Chrome. (Se descartó un flag `--extension` para cargar Bitwarden — el gestor de
  Chrome basta.) 76 tests, ruff limpio.

#### Fase 2.5d — Extensión de Chrome (renovar con un clic desde el navegador del owner) — HECHO
- El owner **no quiere** ventana aparte ni re-login: quiere renovar desde su
  Chrome de siempre. Adjuntarse a ese Chrome con Playwright **no se puede** (Chrome
  136+ bloquea `--remote-debugging-port` en el perfil por defecto). → **extensión**.
- **`validator_app/proxy/extension/`** (NUEVO): `manifest.json` MV3 + `background.js`
  + `icon.png`. Badge rojo cuando la sesión muere (poll `GET /local/estado` cada
  5 min); clic → `chrome.cookies.get({url: WINFORCE, name: "PHPSESSID"})` (lee
  HttpOnly) → `POST 127.0.0.1:<puerto>/local/renovar` → notificación.
- **`server.py`**: `_es_local` (dependency 127.0.0.1) + `POST /local/renovar`
  (reusa `set_session_cookie`) + `GET /local/estado` (reusa `get_status`). Sin
  admin key — petición local + el proxy valida la cookie igual.
- **`_instalar_extension.py`** (NUEVO): copia la plantilla → `.extension_build/`,
  sustituye el puerto, empaqueta `.crx` firmado (`chrome --pack-extension`,
  `extension.pem` estable), escribe `updates.xml` y la política
  `HKLM\...\Chrome\ExtensionSettings\<id>` = `force_installed` (winreg).
  `--uninstall` la borra. `install_service.bat` lo llama en el paso `[7/11]`;
  `uninstall_service.bat` lo llama con `--uninstall`.
- **`.gitignore`**: `.extension_build/`, `extension.pem`, `extension.crx`,
  `updates.xml`.
- **Tests**: `tests/test_proxy.py` estrena **FastAPI `TestClient`** (5 tests de
  `/local/*`: 127.0.0.1 OK, IP externa 403, cookie inválida 401, `/local/estado`);
  `tests/test_instalar_extension.py` NUEVO (`_crx_id` contra la definición,
  `_render_updates_xml`). **84 tests, ruff limpio.**
- **Smoke real**: `_instalar_extension` empaquetó el `.crx` (2741 B) y calculó un
  id de extensión estable (`oclimnkhjeeamemdkdkfdliadmkdafkl`); el `updates.xml`
  quedó bien; la escritura de HKLM avisó "sin permisos" (correcto sin admin).
- El login asistido (`.lnk` del Escritorio) y `--manual` pasan a **fallback**.
- **`install_service.bat`**: paso nuevo `python -m playwright install chromium` +
  paso nuevo que crea el `.lnk` **"Renovar sesion WinForce"** en el Escritorio
  (PowerShell/WScript.Shell, target `pythonw.exe`). Renumerados los pasos a `/10`.
- `playwright>=1.45` → `requirements-proxy.txt` (quitado el suelto de
  `requirements-dev.txt`). `.browser_profile/` → `.gitignore`.
- **`tests/test_login_asistido.py` NUEVO** (10 tests: `_php_sessid_de_cookies`,
  "sin playwright" → mensaje útil, dispatch asistido/`--manual`/`--fresh`, fallo de
  captura y cookie inválida → avisa y no toca keyring, `_avisar` sin tkinter).
  **71 tests, ruff limpio.**
- **Smoke real**: `capturar_php_sessid_asistido(timeout_min=0)` abre/cierra
  Chromium limpio y lanza `LoginAsistidoError` (esperado sin login).
- **Perfil persistente + 2FA (según el usuario)**: el SSO de Microsoft se salta el
  2FA solo **dentro de la misma jornada**; a la siguiente jornada pide 2FA otra
  vez. El perfil persistente es ganancia neta (renovaciones repetidas del mismo
  día son instantáneas) y no empeora la del día siguiente.

#### Fase 3 — Diálogo de cookie en la GUI (arregla el modo standalone) — HECHO
- **El bug**: la rama standalone de `main_window.py:_validar_en_hilo` llamaba
  `api.obtener_cliente().validar(...)` sobre un `ValidatorAPI` **sin sesión** →
  siempre `SessionError`. Standalone estaba roto de raíz.
- **`validator_app/gui/session_config.py` NUEVO** (lógica pura, testeable):
  `guardar_cookie` / `cargar_cookie` / `borrar_cookie` (keyring
  `JSWinCoverage`/`session_cookie`), `validar_y_guardar(php_sessid)` (valida con
  `core.api.validar_cookie_sesion` y guarda), `cliente_standalone()` (arma un
  `ValidatorAPI` con la cookie inyectada; `_session_max_idle = 10**9` porque el
  usuario re-pega la cookie a mano, sin re-login automático).
- **`main_window.py`**: menú "⚙ Configuración → **Configurar Sesión (standalone)**"
  + `_abrir_config_sesion()` (diálogo modal clonado del de proxy: un campo
  `show="•"`, "Mostrar", "Probar y guardar" en hilo, "Quitar sesión guardada").
  `_load_proxy_config` carga también `cliente_standalone()`; el estado dice
  "standalone, sesión configurada" o "standalone SIN sesión — menú ⚙…".
  `_validar_en_hilo` usa `self._session_client`; sin sesión → `SessionError` con
  el remedio (ir al menú).
- **`api.obtener_cliente()` se conserva** — lo usan `tools/probar_core.py`,
  `probar_concurrencia.py`, `gui/prueba_core.py`; solo la rama standalone de
  `main_window` deja de usarlo.
- **`tests/test_session_config.py` NUEVO** (6 tests: roundtrip keyring, validar y
  guardar OK / cookie mala / vacía, `cliente_standalone` con y sin cookie).
  **90 tests, ruff limpio.** Smoke: la GUI arranca headless, el menú y el diálogo
  aparecen, el estado sin sesión es el correcto.

#### Fase 4 — Cubrir la capa FastAPI del proxy con tests — HECHO
- `tests/test_proxy.py` estrena un fixture `client` (config con token/admin_key
  conocidos + `allowed_networks` con `10.0.0.0/8`; `get_config` / `get_proxy_api`
  monkeypatcheados; `TestClient(client=("10.0.0.5", 5000))`).
- **14 tests nuevos**: `/health`; `/api/cobertura` y `/api/score` (OK, token malo
  → 401, IP externa → 403, doc inválido → 422); `/admin/config` (sin key → 401,
  con key → 200); `/admin/login` + `/admin/rotar` (→ `set_session_cookie`);
  `/admin/status` (bloque keepalive); los 3 exception handlers (`LoginError`→401,
  `ScoreError`→502, `APIError`→502); `_ip_in_allowed_networks` directo.
- **104 tests, ruff limpio.** Ningún bug en `server.py` — la capa HTTP del proxy
  quedó cubierta sin cambios de código. Cierra el gap histórico "no hay tests del
  proxy".

#### Pendiente
- Fase 5 — barrido final de docs (`docs/proxy-config.md`, `docs/proxy-deploy.md`,
  coherencia general del repo).
- Prueba manual de la GUI standalone y de la extensión con una cookie real.
- Menor: `config.yaml` no se está leyendo (pydantic-settings sin
  `YamlConfigSettingsSource`); el proxy va por defaults + env `PROXY_*`.
- Deuda vieja: decidir `actualizar_score_cliente` / `newsearch.php`.
- Deuda restante: `tests/test_proxy.py` inexistente (= Fase 4); decidir
  `actualizar_score_cliente` / `newsearch.php`.
