# TestingLog.md — Registro de pruebas y metodología

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Metodología preferida: TDD (semáforo)
- **TDD** = Test-Driven Development: escribir el test PRIMERO (rojo: falla),
  ver la necesidad del cambio en el fallo, implementar lo mínimo para que deje
  de fallar y, al final, refactorizar. El test ya no genera el error (verde).
- Este proyecto usa este flujo: 1) test rojo, 2) implementación, 3) test verde.
- Comando de tests: `pytest` (o `python -m pytest -q`).
- Comando de lint: `ruff check .` (config en pyproject.toml, `target-version = "py312"`).
- Convención: cualquier cambio de comportamiento va acompañado de su test.

## Inventario de tests (201 en total, a 2026-09-25)
| Archivo | Casos | Qué cubre |
|---|---|---|
| tests/conftest.py | (fixtures) | autouse: `keyring_en_memoria` (aísla el Credential Manager) + `avisos_capturados` (aísla el Event Log / webhook de la Etapa R) + `sin_config_yaml_real` (aísla el `config.yaml` de la PC; sin él la suite fallaba sin elevar en una PC con el proxy instalado) |
| tests/test_fields.py | 7 | parseo de coordenadas y detección DNI/RUC/CE |
| tests/test_captura_guard.py | 4 | guard de instancia única de captura.py |
| tests/test_api.py | 22 | núcleo: login, cobertura, score, su parser, `validar_cookie_sesion()`, BOM/doble-encoding |
| tests/test_prueba_core.py | 7 | lógica del arnés gráfico (flujo, errores, mocks) |
| tests/test_proxy.py | 46 | proxy: keepalive "latido perezoso", `/local/*`, capa FastAPI (`/api/*`, `/health`, `/admin/*`), auth (token+IP, admin key **loopback-only desde 2026-09-21**), exception handlers, y la **Etapa R** (bug de `_last_activity`, validación al arrancar, fail-fast 503, `_marcar_sesion_muerta/viva`) |
| tests/test_client.py | 3 | `ProxyClient`: 503 terminal → `ProxySesionCaducadaError` sin reintentos; `HealthResult.session_alive` (usa `httpx.MockTransport`) |
| tests/test_config.py | 6 | `ProxyConfig` lee `config.yaml`; precedencia y `proxy_local_url` |
| tests/test_session_config.py | 6 | modo standalone: keyring `JSWinCoverage/session_cookie`, `validar_y_guardar`, `cliente_standalone` |
| tests/test_login_asistido.py | 19 | captura asistida y envío HTTP al proceso LocalSystem |
| tests/test_instalar_extension.py | 3 | empaquetado del `.crx`, id estable |
| tests/test_medir_keepalive.py | 9 | clasificación muerte/transitorio/indeterminado del medidor |
| tests/test_activation.py | 4 | llave pública real, firma por huella y diagnóstico de código incompleto |
| tests/test_generator.py | 3 | firma con PEM, error claro y ruta junto al `.exe` owner |
| tests/test_owner_app.py | 30 | formato de huella, estado del servicio, `consultar_proxy` con `config.yaml` ilegible/inexistente (PermissionError, ValidationError), reinicio elevado del servicio (`comando_reinicio`, `reiniciar_servicio`: ok, UAC cancelado, fallo, sin PowerShell), el relanzo elevado para credenciales (`_comando_propio`, `_ejecutar_elevado`: ok, UAC cancelado, error propagado, temporal borrado — la ruta de salida va como argumento posicional, ya no por `-RedirectStandardOutput`, incompatible con `-Verb RunAs`; subcomandos `--leer-secretos`/`--rotar-secretos` de `main()` escriben a archivo) y **detección de IP de LAN para la "URL para los agentes"** (`detectar_ip_lan`: socket UDP, respaldo con `getaddrinfo`, descarte de loopback/APIPA, sin candidatas; `url_para_agentes`; `puerto_proxy_local`) |
| tests/test_gui_activacion.py | 4 | `activacion_vigente()` del agente: código válido, sin estado, huella de otra PC, código inválido |
| tests/test_install_bat.py | 3 | guardas estáticas de `install_service.bat`: sin `)` sin escapar en `echo` dentro de bloques, ventana persistente + pregunta de tokens, y carga manual de la extensión sin `exit`/`pause` en el paso 7 |
| tests/test_secretos.py | 12 | `validator_app/proxy/secretos.py`: lectura de `proxy_token`/`admin_key`, rotación preserva el resto de `config.yaml` y no toca el otro secreto, fallback de `icacls` a `Administrators`, `ruta_instalacion` vía `sc qc` con sus dos caminos de fallback y reconociendo la etiqueta del binPath tanto en inglés (`BINARY_PATH_NAME`) como en español (`NOMBRE_RUTA_BINARIO`) |
| tests/test_updater.py | 13 | `validator_app/updater/`: `hay_actualizacion()` elige el asset del agente por nombre exacto aunque el release traiga tambien el `.exe` del owner (y en cualquier orden), `None` si mismo commit o sin release; `extraer_checksum()` no cruza el hash del owner con el del agente cuando el release trae ambos; `aplicar_actualizacion()` feliz, checksum no coincide, sin exe congelado |

Nota: `tools/probar_concurrencia.py` y `tools/probar_con_cookie.py` NO tienen
tests automáticos a propósito (piden credenciales y hacen peticiones reales); se
validan con `ruff` e import.

## Bitácora de la sesión de hoy (TDD aplicado)

### Sesión 2026-09-25 — "URL para los agentes" en la consola owner (fix WinError 10061)

- **Origen**: primer despliegue real con agente y owner en PC distintas. Al
  configurar el agente con `http://localhost:8080`, falló con
  `[WinError 10061] ... denegó expresamente dicha conexión`. Causa:
  `localhost`/`127.0.0.1` en la PC del agente apunta al propio agente, no a la
  PC del proxy — nunca se había probado antes con agente y proxy separados.
- **Rojo**: se escribieron 8 tests en `tests/test_owner_app.py` contra funciones
  que todavía no existían (`detectar_ip_lan`, `url_para_agentes`,
  `puerto_proxy_local`) → `AttributeError` confirmado en las 8, resto de la suite
  intacta (22 pasando).
- **Verde**: `detectar_ip_lan(socket_factory=..., resolver=...)` — método
  principal con un socket UDP conectado a `8.8.8.8:80` (no envía nada; UDP
  `connect()` solo fija la ruta) y `getsockname()[0]`; respaldo con
  `socket.getaddrinfo(gethostname(), ...)` si no hay ruta por defecto (`OSError`,
  por ejemplo sin red); ambos caminos descartan loopback y APIPA
  (`ipaddress.ip_address(...).is_loopback/.is_link_local`). `url_para_agentes()` y
  `puerto_proxy_local()` (reutiliza `_url_proxy_local()` ya existente) son
  triviales. Los 4 parámetros de fábrica (`socket_factory`/`resolver`) siguen el
  mismo patrón de inyección que `runner=subprocess.run` en el resto del archivo,
  para no depender de la red real en los tests.
- **UI**: campo de solo lectura + botón Copiar en el recuadro "Proxy y sesion
  WinForce", relleno desde el mismo hilo de `actualizar_estado()` que ya consulta
  `/health`. `_copiar_de_entry` gana un parámetro `limpiar: bool = True` porque
  la URL no es secreta (no debe borrarse del portapapeles a los 60s como los
  tokens).
- **Verificación manual** (no automatizable: depende de la red real de esta PC):
  `detectar_ip_lan()` devolvió `192.168.18.49`, coincide con `ipconfig`.
- **Ruff**: dos líneas >100 columnas (el `Entry` nuevo y un test) — cortadas.
- 193 → **201 tests**, ruff limpio.

### Sesión 2026-09-21 — Credenciales en la consola owner y `/admin/*` loopback-only

- **Rojo (falso, hallado a mano)**: `test_ruta_instalacion_servicio_no_instalado_cae_a_
  desarrollo` asumía que `validator_app/proxy/config.yaml` no existía en el repo para
  probar el fallback de `ruta_instalacion`. Falló porque ese archivo **sí existe** en
  esta PC (gitignored, de un ensayo previo): el test dependía del filesystem real, no
  de un estado controlado. **Verde**: se monkeypatcheó `Path.exists` en vez de asumir
  el estado de la PC — mismo principio que `conftest.py` aplica desde el 2026-09-18.
- **Efecto colateral del cambio a loopback**: la fixture `client` de `test_proxy.py`
  (IP `10.0.0.5`, dentro de `allowed_networks` pero no loopback) se usaba también para
  los tests de `/admin/*`. Al restringir `/admin/*` a `127.0.0.1`, esos tests pasaron
  a una fixture nueva `admin_client` (IP `127.0.0.1`); se agregó
  `test_admin_config_rechaza_ip_no_local_403` para cubrir el caso que antes no existía:
  una IP en la whitelist de LAN pero no loopback debe seguir dando 403 en `/admin/*`.
- **Calidad**: **178 tests**, suite completa en verde.

**Segunda mitad de la sesión — releases de owner + agente**

- **Bug real, no en el plan original**: al implementar la publicación conjunta de
  ambos `.exe` en un mismo Release de GitHub, se encontró que
  `validator_app/updater/check.py::hay_actualizacion()` elegía el asset por
  `nombre.lower().endswith(".exe")` — con dos `.exe` en el release (agente +
  owner), podía devolver el equivocado y el agente intentaría autoactualizarse
  con el binario del owner. Mismo problema en
  `download.py::extraer_checksum()`: un solo `re.search` sobre todas las notas
  del release podía extraer el hash del owner y compararlo contra el `.exe` del
  agente descargado, lo que habría hecho fallar la verificación de integridad
  siempre (checksum nunca coincide).
- **Verde**: `check.py` compara por nombre exacto (`NOMBRE_ASSET_AGENTE`);
  `extraer_checksum(notas, nombre_archivo)` recorta las notas al bloque de ese
  archivo antes de buscar el hash. No existía cobertura de `validator_app/
  updater/` — se agregó `tests/test_updater.py` (13 casos), incluyendo un caso
  específico que reproduce el bug (release con los dos assets, el del owner
  primero en la lista) para que no regrese.
- **Verificación en vivo, no solo unitaria**: tras publicar el Release real
  (`v2026.09.21`), se simuló un `.exe` viejo contra la API real de GitHub y se
  confirmó que detecta la actualización, elige el asset del agente (con el del
  owner presente en el mismo release) y extrae el checksum correcto.
- **Calidad**: **191 tests**, suite completa en verde, ruff limpio.

### Sesión 2026-09-18 — Ensayo del instalador y del proxy en la PC de desarrollo

- **Bug del paso 5 (rojo encontrado a mano)**: la primera corrida elevada de
  `install_service.bat` abortaba en el paso 5. Causa (reproducida con `cmd /c`): un `)`
  sin escapar dentro de un `echo` en un bloque `( ... )` cierra el bloque y CMD aborta
  al parsearlo entero. **Verde**: se escaparon 7 líneas y `tests/test_install_bat.py`
  falla si vuelve a aparecer un `)` sin escapar en un `echo` indentado (probado contra la
  versión anterior: detecta esas 7 líneas).
- **Trampa**: dentro de `set "VAR=..."` (entre comillas) los `^(`/`^)` se imprimen
  literales; ahí los paréntesis van sin escapar.
- **Aislamiento (incidente)**: con `config.yaml` instalado (ACL SYSTEM/Administradores)
  37 casos de `test_proxy.py` fallaban con `PermissionError` al correr sin elevar.
  `conftest.py` gana `sin_config_yaml_real` (apunta `yaml_file` a un archivo inexistente,
  mismo patrón que `test_config.py`). Regla: ningún test depende de archivos reales de la PC.
- **Consola owner**: "Proxy: falta configurar el servicio" no era Chrome ni la sesión.
  Primero `PermissionError` (ACL) y, en el `.exe`, `ValidationError` (no existe
  `config.yaml` en el bundle). `_url_proxy_local()` cae al puerto por defecto ante
  cualquier fallo; el estado real lo da `/health`. Botón **Reiniciar servicio** con
  runner inyectable para testear sin PowerShell ni UAC.
- **Whitelist**: `localhost` daba 403 (`127.0.0.1` fuera de `allowed_networks`). Fix +
  tests: loopback permitido (v4 y v6) y las tres IP públicas del router bloqueadas.
- **Lección operativa**: un fix del servidor no cuenta hasta reiniciar el servicio; los
  logs (`winsw.wrapper.log`, `winsw.out.log`) delataron que corría el código viejo.
- **Calidad**: **157 tests**, `ruff check .` limpio. Los `ruff format` pendientes son
  previos (`main_window.py`, `generar.py`) y no se tocaron.

### Sesión 2026-09-16 — Activación RSA real y consola del owner

- **Rojo**: no existían pruebas de activación y `PUBLIC_KEY_PEM` era un
  placeholder, por lo que `activacion_disponible()` devolvía `False`.
- **Verde**: `tests/test_activation.py` valida que la clave pública de producción
  está configurada y que una firma RSA correcta se acepta mientras que una huella
  distinta se rechaza. La clave pública se derivó del PEM local sin imprimir la
  privada; una comprobación independiente firmó una huella temporal y la verificó.
- **Generador/UI**: `generar.py` expone carga y firma reutilizables; tests cubren
  llave indicada, PEM ausente y ruta al lado del `.exe` empaquetado. Se creó
  `generator/owner_app.py` con generación de códigos, estado del proxy/servicio y
  renovación asistida. Sus tests cubren normalización de huella y lectura del
  estado del servicio.
- **UX encontrada en prueba real**: el primer intento falló por una copia
  incompleta/incorrecta. Se añadieron **Copiar huella** y **Pegar código**,
  validación estricta `XXXX-XXXX-XXXX-XXXX` y diagnósticos distintos para código
  incompleto, formato inválido y código de otra PC.
- **Prueba manual**: el owner generó el código con `private_key.pem`, el agente lo
  pegó y la activación terminó correctamente en esta PC.
- **Calidad**: **141 tests** de la suite completa, Ruff y `git diff --check` en
  verde; se construyeron en secuencia los ejecutables de agente y owner. Los
  builds PyInstaller no deben correr en paralelo porque comparten caché temporal.

### Sesión 2026-09-09 — Incidente: la suite envenenaba el keyring real

- **Problema**: `test_proxy.py::test_set_session_cookie_limpia_session_dead_since`
  llamaba a `pa.set_session_cookie("cookie-nueva")` sin mockear `keyring`.
  `set_session_cookie` → `_save_session_cookies()` → `keyring.set_password(...)`
  escribía `{"PHPSESSID": "cookie-nueva"}` en el **Credential Manager real** bajo
  `JSWinProxy/credentials_cookies` — exactamente la clave que
  `server._load_session_cookies()` lee al arrancar el proxy.
- **Síntoma**: tras cualquier `pytest`, reiniciar el proxy restauraba esa cookie
  de pega, `/health` decía `logged_in:true` y todo `/api/*` devolvía el HTML de
  login de WinForce. Se descubrió al restaurar `keepalive_interval` a 900.
- **Fix**: `tests/conftest.py` NUEVO — fixture **autouse** `keyring_en_memoria`
  que sustituye `keyring.{get,set,delete}_password` por un dict por test. Nadie
  más tocaba el keyring real (`test_session_config` ya lo mockeaba;
  `test_login_asistido` mockea `save_session_to_keyring`). Bonus: la suite bajó
  de 5.3s a 2.1s (las llamadas reales al Credential Manager de Windows son lentas).

### Sesión 2026-09-09 — Patrón: aislar los efectos de sistema de la Etapa R

- El aviso de "sesión muerta" escribe en el **Registro de Eventos de Windows**
  (`eventcreate`) y hace un POST a un webhook — efectos de sistema reales, la
  misma clase de fuga que el keyring.
- `conftest.py` gana un 2º fixture autouse: `avisos_capturados` sustituye
  `ProxyValidatorAPI._disparar_aviso` por un registrador síncrono
  (`list[(evento, detalle)]`, sin hilos, sin subprocess, sin red). Los tests que
  verifican el aviso piden el fixture y assertan sobre la lista.
- `tests/test_client.py` NUEVO: usa `httpx.MockTransport` para simular respuestas
  del proxy sin servidor. Contrato clave verificado: **un 503 es terminal**
  (`ProxySesionCaducadaError`, 1 sola petición, sin reintentos).
- Regla reforzada: **cualquier test que ejerza código con efectos de sistema
  (keyring, Event Log, red, ficheros fuera de tmp) se aísla en `conftest.py`,
  no test por test.**

### Sesión 2026-09-08 — Incidente: `taskkill` cerró todo Chrome de la máquina
- **Problema**: al limpiar un Chrome zombie de un smoke test del login asistido /
  la extensión, se usó `taskkill /F /IM chrome.exe /T` → cerró **todos** los
  procesos `chrome.exe` de la máquina (incluido el navegador normal del usuario,
  con sus pestañas). Chrome ofreció restaurar al reabrir; sin pérdida real, pero
  disruptivo.
- **Causa**: `/IM chrome.exe` matchea por nombre de imagen, no por el árbol de
  procesos del test. Playwright con `channel="chrome"` / `launch_persistent_context`
  deja procesos hijo que a veces sobreviven al script si se mató Python antes de
  tiempo (`timeout`).
- **Lección** (para futuros smoke tests con navegador):
  - Matar **solo el PID** del navegador del test. Si escucha un puerto (proxy):
    `netstat -ano | findstr :8080` → `taskkill /F /T /PID <pid>`.
  - Nunca `/IM chrome.exe`.
  - Los perfiles de prueba (`validator_app/proxy/.browser_profile/`,
    `.extension_build/`) se borran aparte con `rmdir /s /q` **después** de cerrar
    ese proceso (si no, "Device or resource busy").
  - Mejor: dar a `capturar_php_sessid_asistido()` / los smoke un `timeout_min`
    pequeño y dejar que cierre el contexto por su cuenta (`context.close()`), en
    vez de matar Python con `timeout`.

### Sesión 2026-09-08 — Fase 4: cubrir la capa FastAPI del proxy
- Fixture `client` en `tests/test_proxy.py`: `ProxyConfig` con `proxy_token` /
  `admin_key` conocidos y `allowed_networks=["127.0.0.0/8","10.0.0.0/8"]`;
  `server.get_config` y `server.get_proxy_api` monkeypatcheados;
  `TestClient(server.app, client=("10.0.0.5", 5000))`.
- 14 tests: `/health` (público); `/api/cobertura` y `/api/score` OK con
  `X-Proxy-Token` (proxy mockeado), token malo → 401, IP fuera de
  `allowed_networks` → 403, documento inválido → 422; `/admin/config` sin key →
  401 / con key → 200; `/admin/login` y `/admin/rotar` → `set_session_cookie`;
  `/admin/status` → bloque `keepalive`; los 3 exception handlers
  (`LoginError`→401, `ScoreError`→502, `APIError`→502); `_ip_in_allowed_networks`
  (unit directo).
- **104 tests, ruff limpio.** Ninguno destapó un bug en `server.py` — la capa HTTP
  del proxy quedó cubierta sin cambios de código.

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
| `UP006/UP035/UP045/UP037` | ruff (`target-version = "py312"`) exige typing moderno: `dict` en vez de `Dict`, `X \| None` en vez de `Optional`, sin comillas en anotaciones | `from __future__ import annotations` + `dict[str, ...]` + `Any \| None` |
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
