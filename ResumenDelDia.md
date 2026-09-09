# ResumenDelDia.md — Historial del día

Fecha: 2026-09-09

## Objetivo del día

**Poner en marcha todo lo construido: activar el proxy end-to-end.** Hasta ahora
cada pieza (keepalive, login asistido, extensión de Chrome, diálogo de la GUI) se
validó por separado con mocks y smoke tests; el sistema completo nunca ha corrido
contra una sesión WinForce viva y el instalador nunca se ha ejecutado de verdad.

Plan aprobado: `~/.claude/plans/shimmying-skipping-mochi.md`. Orden:
1. Rotar el resumen 2026-09-08 (hecho, ver abajo).
2. **Etapa 0** — desbloquear el arranque: `config.yaml` no se lee (`config.py`
   sin `settings_customise_sources`), `install_service.bat` tiene 3 bugs que lo
   detienen, `winsw.xml` está trackeado, incoherencia del almacén de la cookie.
3. **Etapa A** — proxy en primer plano en esta PC + auth.
4. **Etapa B** — sesión WinForce viva (2FA disponible ahora) + renovación por
   extensión + primera validación real de cobertura/score + keepalive real.
5. **Etapa C** — GUI contra el proxy + modo standalone.
6. **Etapa D** — servicio de Windows en esta PC (sobrevive a reinicio).
7. **Etapa E** — runbook para la PC de oficina (hoy NO accesible → solo se
   documenta, no se ejecuta).
8. **Fase 5** (barrido de docs) — solo si sobra tiempo; hay 11 incoherencias
   doc↔código ya localizadas.

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

## Pendiente

### De la puesta en marcha
- **0.5** (coherencia del almacén de la cookie con LocalSystem — antes de la D),
  **C.12** (standalone — solo si se necesita, exige borrar keyring de proxy),
  **D** (servicio Windows — bloqueada por el hallazgo C.2), **E** = runbook
  oficina (no accesible hoy).
- **Renovar la sesión del proxy** por `/admin/login` cuando se vaya a retomar
  trabajo que la necesite (hoy está muerta a propósito).

### Fase 5 — Barrido final de docs (última del plan "Sesión WinForce robusta")
- `docs/proxy-config.md`, `docs/proxy-deploy.md`, `docs/rotacion-credenciales.md`,
  `docs/arquitectura.md` — coherencia general (extensión = principal, login
  asistido + `--manual` = fallback).
- 11 incoherencias doc↔código localizadas antes (rotación por usuario/contraseña
  inexistente, `version` = `"dev"` vs commit SHA, ejemplos de `/admin/status` sin
  `X-Admin-Key`, `session_age_seconds` vs `session_age`, "IP:puerto" sin esquema
  vs la GUI que exige `http://`, keyring standalone, "logs en el Visor de
  Eventos", `/admin/config` "público", `config.yaml` no se lee, dos referencias a
  `py314`).
- **+8 de la Etapa C** (config de la GUI contra el proxy):
  1. `docs/proxy-config.md:26`, `README_PROXY.md:69`, `docs/proxy-deploy.md:95`
     muestran `192.168.1.50:8080` sin esquema; el código lo rechaza
     (`main_window.py:337-341`).
  2. La etiqueta "IP:puerto del proxy" espera una URL completa y no normaliza
     (`main_window.py:240`).
  3. Los docs prometen *"Conexión OK (45 ms)"*; el código nunca mide latencia
     (`docs/proxy-config.md:35` vs `main_window.py:310-312`).
  4. `docs/proxy-config.md:104` dice que standalone usa `JSWinCoverage/credentials`
     (credenciales); el código usa `JSWinCoverage/session_cookie` (una PHPSESSID).
  5. `PlanesAprobados.md:219` planificó el usuario de keyring `win_sessid`; se
     implementó `session_cookie` (`session_config.py:21`).
  6. `docs/proxy-config.md:100-106` no menciona el diálogo "Configurar Sesión
     (standalone)" añadido en la Fase 3.
  7. Bug latente: `main_window.py:362-363` hace `.base_url` sobre el retorno de
     `from_keyring()` sin comprobar `None` → `AttributeError` si el keyring falla.
  8. "Probar conexión" traga la excepción real (`main_window.py:316-317`); el
     usuario final no distingue 401 / 403 / timeout / DNS.

### Deuda vieja (no de hoy)
- Decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`
  (Tareas pendientes 8 y 10 de `AGENTS.md`).
