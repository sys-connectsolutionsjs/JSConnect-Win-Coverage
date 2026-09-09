# ResumenDelDia.md — Historial del día

Fecha: 2026-09-09

> **Estado al cierre**: todo pusheado a `origin/main` (hasta `f93e5c0` +
> el commit de sincronización de docs). Working tree limpio, 124 tests, ruff
> limpio. **Se continúa en otra PC. Lo siguiente: Etapa 0.5** — spec completa en
> `PlanesAprobados.md` ("Puesta en marcha del proxy"). La sesión del proxy quedó
> muerta a propósito (se renueva por la extensión / `/admin/rotar` al retomar).

## Objetivo del día — HECHO

**Poner en marcha todo lo construido: activar el proxy end-to-end.** Hasta hoy
cada pieza (keepalive, login asistido, extensión de Chrome, diálogo de la GUI) se
había validado por separado con mocks y smoke tests; el sistema completo nunca
había corrido contra una sesión WinForce viva y el instalador nunca se había
ejecutado de verdad.

Lo que se hizo, en orden (detalle abajo; vista de conjunto en `Roadmap.md`):
1. Rotar el resumen 2026-09-08 → `resumenes/2026-09-08.md`.
2. **Etapa 0** — desbloquear el arranque (`config.yaml` no se leía;
   `install_service.bat` con 3 bugs; `winsw.xml` trackeado).
3. **Etapa A** — proxy en primer plano + auth.
4. **Etapa B** — sesión WinForce viva + primera validación real cobertura/score.
5. **Etapa C** — GUI (Tkinter) contra el proxy.
6. **Etapa R** (no estaba en el plan original; nació del hallazgo C.2) —
   robustez de la detección de sesión muerta + aviso al owner.
7. `Roadmap.md` nuevo + registro del plan en `PlanesAprobados.md`.

Pendiente del plan original (no se tocó hoy): **0.5 → C.12 → D → E → Fase 5**.

---

## Estado al arranque (2026-09-09)

- Rama `main` = `origin/main` (`e13a778`), working tree limpio.
- Entorno esta PC: Python **3.14.7**; `fastapi` / `uvicorn` / `httpx` / `keyring` /
  `playwright` importan; Chrome en `C:\Program Files\Google\Chrome\Application\`;
  puerto 8080 libre.
- **104 tests** (pendiente re-verificar en verde tras la Etapa 0).

### Decisión sobre la versión de Python (aclarada hoy)
Nada corre en 3.12. `requires-python = ">=3.12"` es un **piso mínimo**, no una
versión fijada; el 3.12 entró ayer solo como compatibilidad hacia atrás para una
máquina ajena que no podía hacer `pip install -e .`. **No se toca `pyproject.toml`**
(el piso bajo es un seguro para la PC de oficina). La instalación de producción se
**estandariza en Python 3.14.7**, igual que desarrollo. Cabos para la Fase 5:
`TestingLog.md:11` y `SkillsPropuestas.md:53` aún dicen `py314`; `>=3.12` es hoy
una promesa sin verificar (última corrida en 3.12: 2026-08-27, ~40 tests).

---

## Trabajo del día

### Rotación del resumen 2026-09-08 — HECHO
- `resumenes/2026-09-08.md` creado (copia verbatim del `ResumenDelDia.md` anterior,
  cabecera ajustada a `# Resumen — 2026-09-08`).
- Entrada condensada añadida arriba del todo en `HistorialResumenes.md` (total: 9
  entradas; el hook `historial_sync.py` disparó el recordatorio de doc-sync, sin
  README porque necesita 3 acumuladas).
- `ResumenDelDia.md` reabierto con fecha 2026-09-09.
- Pendiente en esta rotación: sincronizar `AGENTS.md` (Historial + Tareas
  pendientes + Cierre) y `PlanesAprobados.md` (sacar de la cola lo ya implementado).

---

### Etapa 0 — desbloquear el arranque — HECHO (0.5 pospuesta)
- **0.1 `config.py`** (commit `d9c1ef7`): `settings_customise_sources` con
  `YamlConfigSettingsSource` + `yaml_file` a ruta absoluta (`_CONFIG_YAML`, junto
  al módulo) + `pyyaml` → `requirements-proxy.txt`. `tests/test_config.py` NUEVO
  (5 tests). El warning de pydantic-settings desapareció. 109 tests, ruff limpio.
- **0.2/0.3/0.4 `install_service.bat` + `winsw.xml`** (commit `ffa213a`):
  - `[2/11]` buscaba `requirements-proxy.txt` en `validator_app\proxy\` (está en la
    raíz) → `%REPO_ROOT%`.
  - `[5/11]` `python -c` multilínea (cmd.exe lo rompía → tokens vacíos) → una línea.
  - `[6/11]` `%PROXY_PORT%` se expandía vacío dentro del bloque `( )` → delayed
    expansion `!PROXY_PORT!`; la rama "config.yaml ya existe" relee puerto y tokens
    sin comillas (subrutina `:trim_quotes`).
  - `[8/11]` `where python` podía coger el stub de Store → `sys.executable`.
  - **`winsw.xml` sacado del control de versiones** → `winsw.xml.example` (plantilla);
    `winsw.xml` y `winsw.exe` gitignored. Elimina el "repo sucio tras instalar".
  - **ACL de `config.yaml`**: nuevo paso `icacls /inheritance:r` + grant solo a
    SYSTEM + Administradores (también `proxy_token.txt` / `admin_key.txt`).
  - Ayuda corregida: los logs van a `<repo>\logs\`, no al Visor de Eventos.
- **0.5 (coherencia del almacén de la cookie con LocalSystem)** → **POSPUESTA a
  después de la Etapa C** (no bloquea A–C; queda mejor informada tras ver
  `/local/renovar` con cookie real; se hace antes de la Etapa D).
- **0.6 versión de Python**: decidido no tocar `pyproject.toml` (piso `>=3.12` es
  un seguro); producción se estandariza en 3.14.7. Nota para `docs/proxy-deploy.md`
  y las 2 refs a `py314` → Fase 5.

### Etapa A — proxy en primer plano en esta PC — HECHO
- `config.yaml` local creado (gitignored, puerto **8090** ≠ default 8080 a
  propósito). El proxy arranca y escucha en 8090 → **prueba en vivo de que
  `config.yaml` se lee**. Sin el warning `yaml_file ... ignored`.
- `GET /health` → `{"status":"ok", ...}`. Keepalive loop iniciado (intervalo 900s).
- Auth verificada: `/api/cobertura` sin token → 401, token malo → 401;
  `/admin/status` sin `X-Admin-Key` → 401, con key → 200 (con bloque `keepalive`).
- Token válido → la petición llega a WinForce; con la `PHPSESSID` muerta del
  keyring devuelve 502 + error claro con remedio. Pipeline OK, falta sesión viva.
- El proxy quedó corriendo en segundo plano para la Etapa B.

### Etapa B — sesión viva + validación real end-to-end — HECHO
- **Login asistido**: el flujo `rotate_creds --preview` con `capturar_php_sessid_asistido`
  **no capturó** (el owner cerró la ventana justo en el redirect de OAuth, antes de
  que WinForce activara la sesión PHP). Recuperado reabriendo el perfil persistente
  `.browser_profile/` (el SSO de Microsoft ya estaba guardado → sin 2FA) y dejando
  que completara el redirect: la `PHPSESSID` se activó en la 1ª/2ª iteración.
  → **Bug de UX a anotar**: el poller de `login_asistido` no detecta "ventana
  cerrada" de forma fiable (siguió sondeando 15 min tras cerrarla); y si el owner
  cierra antes de tiempo, no hay recuperación automática. Candidato para Fase 5 /
  mejora del login asistido.
- Cookie inyectada vía `POST /admin/login` (`X-Admin-Key`) → `{"ok":true}`;
  `/health` → `session_alive:true`.
- **Validación real contra WinForce** (documento `75020496`, coords del README):
  - `/api/cobertura` → `hay_cobertura:true, SI, HORIZONTAL, id_celda 8764`
    (idéntico a la prueba de 2026-08-27).
  - `/api/score` → **primero HTTP 500** (bug real): `ScoreResponse.deuda_total:
    str|None` reventaba porque WinForce manda `DeudaTotal: 0` (int) cuando no hay
    deuda. **Arreglado** (commit `3f63e8f`): `_parsear_score` normaliza a str +
    `ScoreResponse` con `coerce_numbers_to_str`. Tras el fix: `valor:423,
    riesgo:MUY ALTO, deuda_total:"0", valido:true` (idéntico a 2026-08-27).
- **Descubrimiento operativo**: reabrir el login asistido / el perfil persistente
  **mientras el proxy tiene sesión viva** puede invalidar la sesión inyectada
  (WinForce rota / re-autentica). Anotar en el runbook: renovar cuando el proxy
  reporta la sesión muerta, no "por si acaso".
- Keepalive: se bajó el intervalo a 120s en `config.yaml` (temporal) para observar
  ciclos reales. Resultado: `/health` reportó `session_alive:true` de forma
  sostenida durante toda la sesión con ciclos de 120s. Evidencia suficiente →
  restaurado a **900** al cerrar la Etapa C.

### Etapa C — GUI (Tkinter) contra el proxy — HECHO (pasos 10-11; 12 no aplica)

- **Paso 10 — configurar el proxy en la GUI.** ⚙ → Configurar Proxy con
  `http://127.0.0.1:8090` + el token de `proxy_token.txt`. "Probar conexión"
  verde, "Guardar" OK, barra de estado → `listo (proxy: http://127.0.0.1:8090)`.
  Verificado: keyring `JSWinClient` con `proxy_url` (sin barra final) y
  `proxy_token` idénticos al `config.yaml` del proxy.
- **Paso 11 — validación real desde la GUI.** Cobertura **SI**; score **valor
  423, riesgo MUY ALTO** — idéntico al baseline de 2026-08-27 y a la Etapa B por
  `curl`. El owner probó además un **segundo DNI** distinto → también OK.
  `/health` con `session_alive:true` antes y después: la GUI no tumbó la sesión.
  Es la **confirmación por GUI** del fix `3f63e8f` (score / `DeudaTotal: 0` int).
- **Paso 12 (modo standalone) — NO aplica ya.** El modo proxy siempre gana y no
  hay forma de deshacerlo desde la UI: `_load_proxy_config()` (`main_window.py:75-77`)
  y `_validar_en_hilo()` (`main_window.py:175`) prueban `from_keyring()` primero
  y hacen `return`; el diálogo de proxy no tiene botón de borrar (el de standalone
  sí). Con la config de proxy guardada, probar standalone exige borrar a mano
  `JSWinClient/proxy_url` y `JSWinClient/proxy_token`. Se pospone; no bloquea nada.

#### Hallazgos de la Etapa C

1. **[CRÍTICO — corregido] La suite de tests envenenaba la sesión del proxy.**
   `test_set_session_cookie_limpia_session_dead_since` (`tests/test_proxy.py:169`)
   llamaba a `set_session_cookie("cookie-nueva")` sin mockear keyring →
   `_save_session_cookies()` escribía `{"PHPSESSID": "cookie-nueva"}` en el
   Credential Manager real bajo `JSWinProxy/credentials_cookies`, la misma clave
   que `server._load_session_cookies()` lee al arrancar. Efecto: tras cualquier
   `pytest`, un reinicio del proxy restauraba esa cookie de pega, `/health` decía
   `logged_in:true` y todo `/api/*` devolvía el HTML de login. **Esto es lo que
   pasó** al reiniciar el proxy para tomar el `keepalive_interval: 900`.
   → Arreglado en `ffc5296`: `tests/conftest.py` nuevo con fixture autouse que
   aísla `keyring.{get,set,delete}_password` en un dict por test. Entrada real
   `JSWinProxy/credentials_cookies` borrada a mano (estaba con `cookie-nueva`).
   La sesión viva del proxy se perdió en el proceso — **se deja muerta a
   propósito** (la Etapa C ya se validó end-to-end antes); se renueva por
   `/admin/login` cuando haga falta.
2. **[revisar antes de Etapa D] El arranque restaura la cookie sin validarla.**
   `_load_session_cookies()` (`server.py:269-321`) inyecta la cookie del keyring y
   loguea "Sesión restaurada" sin comprobar que siga viva → `logged_in:true`
   aunque esté muerta (solo `session_alive` lo delata, y requiere pegarle a
   WinForce). Con winsw en `onfailure restart`, un servicio que se reinicia solo
   puede quedar "logueado" con una cookie muerta y sin avisar. Relacionado:
   `_save_session_cookies()` solo corre en `/admin/login` y `/admin/rotar`
   (`server.py:359`), nunca tras un request normal; si WinForce llegara a rotar
   la `PHPSESSID` en caliente, el keyring quedaría desactualizado. Arreglo a
   evaluar antes de la D: validar al restaurar (y degradar el log a warning si
   falla) + re-persistir tras cada validación/keepalive OK.
3. **[producto — v1.1] La GUI exige coordenadas Y documento** para habilitar
   VALIDAR. El owner quiere poder consultar solo cobertura sin DNI. Backlog v1.1.
4. **No hay `logs/` y es correcto.** winsw crea `logs/` solo con el proxy como
   servicio (`winsw.xml.example:21`); en primer plano `server.py:771-774` loguea
   a stdout.
5. **[corregido] `install_service.bat:262`** (rama de error de "[10/11] Iniciando
   servicio") seguía mandando al "Visor de Eventos"; el commit `ffa213a` había
   arreglado solo la ayuda final (`:338`). Fix en `b70dacf`.

### Etapa R — robustez de la detección de sesión muerta — HECHA (código; instalador se verifica en la D)

Nace del hallazgo C.2. La exploración encontró que el problema tenía 4 capas.
(El plan de trabajo quedó archivado localmente; lo vigente está aquí y en
`PlanesAprobados.md`.)

- **Roadmap** (`82f3604`): `Roadmap.md` nuevo (línea de tiempo + cola aprobada
  C→R→0.5→C.12→D→E→Fase 5), registrado en `AGENTS.md` (mapa de conocimiento +
  orden de lectura) y en `historial_sync.py`. `PlanesAprobados.md` recibió el
  plan de puesta en marcha (antes solo vivía en `~/.claude/plans/`) y el
  checklist completo de las 19 incoherencias con `archivo:línea`.
- **R1 detección** (`3c8c7bd`):
  - `auto_relogin_if_needed()` ya NO refresca `_last_activity`: eso solo lo hace
    una llamada real y exitosa a WinForce. **Ese era el bug que cegaba la
    alarma**: 20 agentes reintentando contra una sesión muerta mantenían
    `_last_activity` fresco y el keepalive nunca pinchaba → el `log.error` "AVISO
    AL OWNER" no se emitía jamás.
  - `_load_session_cookies()` verifica la cookie contra WinForce al arrancar; si
    no vale, marca la sesión muerta y avisa (antes: `logged_in:true` mentiroso
    hasta que un agente fallara). Verificado en vivo: `session_dead_since` queda
    fijado desde el segundo 0.
  - Primer tick del keepalive a los 60s, no a los 900.
  - `_marcar_sesion_muerta()` / `_marcar_sesion_viva()`: único sitio que toca
    `_session_dead_since`, idempotente, dispara el aviso una sola vez.
- **R2 fail-fast** (`3c8c7bd`, `6ee6cb6`): `SesionCaducadaError` → **HTTP 503** +
  `Retry-After: 120` + `{codigo, owner_avisado}`, lanzada **antes** de tocar
  WinForce. Verificado: `POST /api/cobertura` con sesión muerta → 503 en **5 ms**.
  `ProxyClient` trata el 503 como terminal (`ProxySesionCaducadaError`, sin
  reintentos). La GUI lo muestra con un `showinfo` suave, no el diálogo rojo.
  `HealthResult.session_alive` ahora se parsea; "Probar conexión" pinta ámbar si
  el proxy está vivo pero sin sesión.
  - Corrección a la exploración: el cliente **no** reintentaba 3× los 5xx
    (`except ProxyError: raise` los re-lanza). El "60 golpes por oleada" era
    ~20. El fail-fast sigue valiendo (0 golpes, instantáneo, mensaje claro).
- **R3 aviso al owner, 3 capas** (`3c8c7bd`, `4924e70`, `9f49b8e`, `67ec0e4`):
  - **A) GUI del agente** — el 503 con mensaje accionable. Siempre funciona.
  - **B) Evento de Windows + Tarea programada** — el proxy escribe un evento
    (`eventcreate`, origen JSWinProxy, ID 101/102); `install_service.bat` (paso
    11/12 nuevo) registra la fuente y una tarea `schtasks /sc ONEVENT` que le
    saca un `msg *` al owner. Es la vía nativa para que un servicio LocalSystem
    alcance un escritorio. **En modo desarrollo (foreground sin elevar)
    `eventcreate` da "Acceso denegado"** — esperado; bajo LocalSystem funciona.
    Se verifica end-to-end en la Etapa D.
  - **C) Toast de la extensión** — `background.js` dispara `chrome.notifications`
    en la transición (no cada 5 min); estado previo en `chrome.storage.session`
    (permiso `storage` nuevo).
  - **D) Webhook opcional** — `config.alert_webhook_url`, POST `{"text": ...}`
    (Teams/Slack/Discord). Vacío por defecto. Verificado contra un listener local.
- **Tests**: `tests/conftest.py` gana `avisos_capturados` (autouse — el aviso
  toca el Event Log real, se aísla como el keyring). `tests/test_client.py`
  NUEVO (el cliente no tenía tests). **124 pasando**, ruff limpio.

## Pendiente

### De la puesta en marcha (ver `Roadmap.md` para la vista completa)
- **0.5** (almacén de la cookie con LocalSystem — antes de la D), **C.12**
  (standalone — solo si se necesita), **D** (servicio Windows — ya no bloqueada
  por C.2; la Etapa R lo cerró; sí verifica el instalador de R), **E** = runbook
  oficina (no accesible hoy).
- **Renovar la sesión del proxy** por `/admin/login` / la extensión cuando se
  retome trabajo que la necesite (hoy está muerta a propósito).
- **Pendiente menor**: `eventcreate` en modo desarrollo da "Acceso denegado";
  bajo LocalSystem (Etapa D) funciona. Confirmar el popup end-to-end en la D.

### Fase 5 — Barrido final de docs (la última del plan)
Las **19 incoherencias** (11 previas + 8 de la Etapa C) están ahora en
`PlanesAprobados.md` ("Fase 5 — barrido final de la documentación"), cada una con
`archivo:línea` del doc y del código. Ojo: la Capa B de la Etapa R vuelve
**verdad** parte de la incoherencia #7 ("logs en el Visor de Eventos") — el
evento de aviso sí va ahí, aunque los logs de operación siguen en `<repo>\logs\`.

### Deuda vieja (no de hoy)
- Decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`
  (Tareas pendientes 8 y 10 de `AGENTS.md`).
