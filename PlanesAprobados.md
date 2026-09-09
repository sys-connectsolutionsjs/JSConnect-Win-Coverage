# PlanesAprobados.md — Planes de trabajo aprobados

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Contexto
App de escritorio (Python/Tkinter) para un call center que valida COBERTURA
(coordenadas) y SCORE crediticio (DNI/RUC/CE) replicando la API interna de
appwinforce.win.pe (sin scrapear HTML). Repo:
https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Estado del proyecto (verificado 2026-08-26; addendum 2026-09-08)

**Addendum 2026-09-08**: del plan "Sesión WinForce robusta" — Fase 1 (limpiar
login muerto) COMPLETA y con la visibilidad de fallos añadida encima (`5506ed4`);
Fase 0 (medir vida de sesión) COMPLETA. **Investigación de keepalive CERRADA**
(reporte final de la corrida v3 recibido 2026-09-08): el keepalive de 15 min
funciona (37 pings VIVA hasta ≈ 9 h 16 m de edad de sesión) y **existe un tope
absoluto de sesión ≈ 9.5 h desde el login** (muerte limpia a ≈ 9 h 31 m,
confirmada por `validar_cookie_sesion()`); idle-timeout, anti-bot acumulativo y
"tope a 40 min" quedan **descartados**. **Fases 2A (keepalive) y 2.5 (renovación de
sesión) COMPLETADAS 2026-09-08** — el proxy mantiene la sesión viva y el owner la
renueva con **un clic en una extensión de su Chrome de siempre** (fallbacks:
ventana asistida `.lnk` / `--manual`). ~35 tests nuevos, 84 pasando, ruff limpio.
Pendiente: Fases 3–5.

- Fase 0 (captura de la API): COMPLETA.
- Fase 1 (núcleo core): COMPLETA — 35 tests, ruff limpio.
- Fase 1.5 (decisión de autenticación): **DECIDIDA — Opción B (Proxy Local)**.
- Fase 0 Documentación: COMPLETA — `docs/`, `Escalabilidad.md`, `anotaciones.md`, `resumenes/`.
- **Proxy Local (FASES 1.1–1.5) IMPLEMENTADO**: `validator_app/proxy/` completo
  (server.py, config.py, client.py, rotate_creds.py, winsw.xml, install/uninstall .bat),
  core adaptado (`auto_relogin_if_needed`, persistencia cookies), GUI conectada
  (menú "⚙️ Configuración"). Detalle en `AGENTS.md` (Historial → Fase Proxy —
  Implementación).
- ~~**Gap: sin tests del proxy**~~ → **CERRADO 2026-09-08 (Fase 4)**:
  `tests/test_proxy.py` cubre el keepalive (2A), `/local/*` (2.5d) y toda la capa
  FastAPI — `/api/*`, `/health`, `/admin/*`, middleware de auth y exception
  handlers. 31 tests en ese archivo.
- **Prueba real del core**: COMPLETADA 2026-08-27 (ver sección abajo).
- **Próxima fase (en ejecución, 2026-08-28)**: plan "Sesión WinForce robusta" — keepalive
  del proxy + limpieza del login muerto (el proxy asumía login programático, imposible con
  2FA) + diálogo de cookie en la GUI para arreglar el modo standalone. Ver sección abajo.

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

### Hallazgo crítico 2026-08-25
**Login WinForce redirige a `login.microsoftonline.com` para 2FA Microsoft** con la misma cuenta.
Esto hace **inviable la prueba de concurrencia** planificada (4-5 máquinas simultáneas requerirían 2FA manual cada una).

### Decisión aprobada (2026-08-25)
**Opción B (Proxy Local) APROBADA** definitivamente. No se realiza prueba de concurrencia.
Razones documentadas en `AGENTS.md` (Historial 2026-08-25) y `ResumenDelDia.md`.

## Plan Proxy Local — IMPLEMENTADO (sacado de la cola 2026-08-26)
El plan completo de FASES 1.1–1.5 (stack, acuerdos, pasos de implementación) se
ejecutó íntegramente. El detalle verificado vive en `AGENTS.md` (Historial → Fase
Proxy — Implementación), no se duplica aquí. Único cabo suelto: **no se creó
`tests/test_proxy.py`** (ver "Gap detectado" arriba) — si se retoma, es cola nueva,
no parte de este plan ya cerrado.

## Prueba real del core — COMPLETADA (2026-08-27)
Login manual (2FA) + cookie inyectada vía `tools/probar_con_cookie.py` (nuevo, conservar
como herramienta de diagnóstico) → cobertura (SI, HORIZONTAL, celda 8764) → score (423,
MUY ALTO). Dos bugs reales encontrados y corregidos: BOM UTF-8 en `_json()` (cobertura) y
doble-encodificado no implementado en `_parsear_score` (score, ya documentado desde Fase 0
pero nunca hecho). 37 tests pasando, ruff limpio. Detalle completo en `AGENTS.md`
(Historial → "Prueba real end-to-end (2026-08-27)") y `ResumenDelDia.md`.

**Geodata del score — RESUELTA: opción C (payload mínimo)**. El score respondió bien
enviando solo coordenadas + documento, sin geodata. No hace falta replicar Equifax (A) ni
pedir datos manuales (B).

## Plan aprobado — Sesión WinForce robusta (2026-08-28)

**En ejecución.** Keepalive del proxy + limpieza del login muerto + cookie en la GUI.
El detalle completo (fases, verificación, archivos) vive en el plan aprobado
`~/.claude/plans/perfecto-ahora-tenemos-acceso-vivid-cake.md`. Resumen de la cola:

- **Fase 0 — medir vida de la `PHPSESSID`** (`tools/medir_sesion.py`, NUEVO).
  **[COMPLETADA 2026-09-04]**. 4 corridas (`medir_sesion.log`): dos con `--max` por
  defecto (600s) llegaron VIVA hasta 525s sin morir; una corrida corta murió entre
  135s y 210s (anómala — coincide con una recarga del navegador que reemplazó la
  `PHPSESSID`, ver `anotaciones.md` "Reuse de PHPSESSID..."; no representa el
  idle-timeout real); la corrida `--max 3600` (la buena, sin interferencia) dio el
  rango real: **VIVA a 1155s, MUERTA a 1350s** (entre 19.25 y 22.5 min de
  inactividad) — algo por debajo del `session.gc_maxlifetime` default de PHP
  (1440s/24min), probablemente por un timeout propio de la app o el GC
  probabilístico de PHP.
  **Actualización 2026-09-08 — la investigación de keepalive se rehízo con
  método corregido y quedó CERRADA.** Los datos de v1/v2 (que sugerían un "tope
  absoluto a 40 min" y posible anti-bot) resultaron **inservibles**: v1/v2 medían
  tiempo de test, no edad de sesión, y trataban cualquier error como muerte.
  `medir_keepalive.py` **v3** mide `edad_sesion_s`, clasifica el fallo y lo
  confirma con `validar_cookie_sesion()` antes de cortar. Corrida v3 (arrancó
  2026-09-05 21:08, intervalo fijo 900s, 49 coords rotativas de
  `coords_prueba.txt`; reporte final 2026-09-08): **37 pings consecutivos VIVA**,
  última confirmación a 33 370s (≈ 9 h 16 m de edad de sesión); murió **limpia** a
  34 270s (≈ 9 h 31 m) con patrón HTTP 200 + HTML de login, confirmado por
  `validar_cookie_sesion()`. Lecturas: idle-timeout **descartado** como causa
  (ping real cada 900s), anti-bot acumulativo **descartado** (37 pings variados,
  0 fallos), "tope a 40 min" **descartado** (era el 404 ambiguo de v1); **sí
  existe un tope absoluto de sesión ≈ 9.5 h desde el login**, por encima de la
  jornada de 8 h con ~1.5 h de margen. `keepalive_interval_seconds` fijado en
  **900** para la Fase 2.
- **Fase 1 (C) — limpiar login muerto del proxy. [COMPLETADA 2026-09-04]** Helper
  compartido `core.api.validar_cookie_sesion()` (usado también por
  `rotate_creds.py`, eliminando la duplicación); `/admin/login` y `/admin/rotar`
  reciben `{php_sessid}` en vez de `{usuario, password}` (ambos hacen lo mismo,
  intercambiables); `_relogin_silent()` reescrito para recargar+revalidar la
  cookie del keyring (antes intentaba login programático inviable, código muerto
  en dos capas); `session_alive` agregado a `/health` y `/admin/status`
  (valida la cookie actual contra WinForce en vivo). `docs/rotacion-credenciales.md`
  actualizado. 3 tests nuevos en `tests/test_api.py` (40 pasando, ruff limpio).
  `tests/test_proxy.py` (FastAPI TestClient) queda para la Fase 4, como estaba
  planeado.
  **Añadido 2026-09-05 (`5506ed4`)** — extensión natural de esta fase:
  `_relogin_silent()` y `_load_session_cookies()` dejan de tener `except
  Exception: pass` (cada fallo se loguea con causa + error + remedio, distingue
  cookie expirada de fallo de red); `/health` cachea `session_alive` 30s en vez
  de validar contra WinForce en cada request; `logging.basicConfig` en el
  `__main__` de `server.py`. `docs/arquitectura.md` sincronizado.
- **Fase 2A (B) — keepalive en el proxy. [COMPLETADA 2026-09-08]**
  `_keepalive_loop` (`asyncio` en el `lifespan`) + `ProxyValidatorAPI._keepalive_tick`
  en `server.py`. Config `keepalive_enabled` / `keepalive_interval_seconds` (**900s**)
  en `config.py`. Diseño "latido perezoso": pinga `validar_cobertura` (coordenada
  pública rotada de `_KEEPALIVE_COORDS`) solo si pasaron ≥ N s **sin tráfico real
  de los agentes** (`_last_activity`). Ping fallido → se confirma con
  `validar_cookie_sesion()`: endpoint caído = transitorio; **sesión muerta =
  `log.error` con aviso al owner + `session_dead_since` en `/admin/status`, sin
  reintentar en silencio** (tope absoluto ≈ 9.5 h; re-login programado inviable
  por 2FA → el owner renueva la cookie ~1 vez por jornada). Fix de prerrequisito:
  `_get_client()` neutraliza el guard idle de 120 s del cliente-core (el proxy ya
  gestiona la frescura). **12 tests nuevos en `tests/test_proxy.py`** (abre el
  archivo de la Fase 4); 61 pasando, ruff limpio. Validado end-to-end contra
  WinForce real (detectó una sesión muerta y disparó el aviso).
- **Fase 2.5 (B) — renovación de sesión sin F12. [COMPLETADA 2026-09-08]**
  - **2.5d (vía principal) — extensión de Chrome**: MV3 en el navegador cotidiano
    del owner; badge rojo cuando la sesión muere → 1 clic → `chrome.cookies` (lee
    HttpOnly) → `POST 127.0.0.1/local/renovar`. Endpoints `/local/*` en `server.py`
    (solo localhost, sin admin key). `_instalar_extension.py` empaqueta el `.crx` y
    la fuerza-instala por política (`ExtensionSettings\<id>` = `force_installed`).
    Adjuntarse al Chrome del owner con Playwright NO se puede (Chrome 136+ bloquea
    el debug port en el perfil por defecto).
  - **2.5 (fallback) — login asistido**: `login_asistido.py` (Playwright abre el
    Chrome instalado, perfil dedicado; captura la `PHPSESSID` de `context.cookies()`).
    `rotate_creds.py` v2: sin args = asistido + `messagebox`; `--manual` =
    copiar/pegar; `--fresh` / `--preview`. `.lnk` en el Escritorio.
  - `playwright>=1.45` → `requirements-proxy.txt`. Gitignored: `.browser_profile/`,
    `.extension_build/`, `extension.pem/.crx`, `updates.xml`.
  - **20 tests** (`tests/test_login_asistido.py` + `tests/test_proxy.py`
    `/local/*` con FastAPI TestClient + `tests/test_instalar_extension.py`).
    84 pasando, ruff limpio.
- **Fase 3 (D) — cookie en la GUI (arregla standalone). [COMPLETADA 2026-09-08]**
  `validator_app/gui/session_config.py` NUEVO (keyring `JSWinCoverage`/`session_cookie`,
  `validar_y_guardar()`, `cliente_standalone()`); menú "⚙ Configurar Sesión
  (standalone)" + `_abrir_config_sesion()` en `main_window.py`. La rama standalone
  usa `cliente_standalone()` en vez del `ValidatorAPI` sin sesión de
  `api.obtener_cliente()`. 6 tests en `tests/test_session_config.py`. 90 pasando,
  ruff limpio.
- **Fase 4 — tests. [COMPLETADA 2026-09-08]** `tests/test_proxy.py` cubre
  keepalive (2A) + `/local/*` (2.5d) + toda la capa FastAPI (`/api/*`, `/health`,
  `/admin/*`, middleware token/IP/admin-key, exception handlers). 14 tests nuevos,
  104 pasando, ruff limpio. `tests/test_session_config.py` (Fase 3) y
  `tests/test_login_asistido.py` / `tests/test_instalar_extension.py` (Fase 2.5).
- **Fase 5 — barrido final de la documentación. [LA ÚLTIMA del plan]** Coherencia
  general (extensión = vía principal, login asistido + `--manual` = fallback) y
  las **19 incoherencias doc↔código** verificadas el 2026-09-09, cada una con
  `archivo:línea`. **No se ejecuta hasta cerrar R / 0.5 / C.12 / D / E.**

  _Las 11 previas (todas vigentes):_
  1. Rotación por usuario/contraseña inexistente — `docs/rotacion-credenciales.md:3,10,190`,
     `anotaciones.md:319,322` vs `server.py:120-121,686,692-694` (`server.py:12`).
  2. `version="dev"` vs commit SHA — `server.py:655,681,506` (y `:604` dice `1.0.0`)
     vs `docs/proxy-deploy.md:78`, `anotaciones.md:122`, `docs/rotacion-credenciales.md:139,146`,
     `docs/proxy-config.md:156`, `Escalabilidad.md:36`, `docs/escalabilidad-remota.md:62`,
     `README_PROXY.md:54`.
  3. Ejemplos de `/admin/status` sin `X-Admin-Key` — `docs/rotacion-credenciales.md:133-134`,
     `README_PROXY.md:121` vs `server.py:700-703,539-544`.
  4. `session_age_seconds` vs `session_age` — `docs/rotacion-credenciales.md:137`
     vs `server.py:134,504,709`.
  5. "IP:puerto" sin esquema vs la GUI que exige `http://` — `docs/proxy-config.md:25-26`,
     `README_PROXY.md:71`, `docs/proxy-deploy.md:95`, `README.md:51`,
     `docs/arquitectura.md:40`, `AGENTS.md:270,412` vs `main_window.py:337-341` (etiqueta `:240`).
  6. Keyring standalone — `docs/proxy-config.md:104` (`JSWinCoverage/credentials`)
     vs `session_config.py:20-21` (`JSWinCoverage/session_cookie`, una PHPSESSID).
  7. "Logs en el Visor de Eventos" — `README_PROXY.md:169,219`, `docs/proxy-deploy.md:83-84,165`,
     `docs/arquitectura.md:158`, `anotaciones.md:399`, `Escalabilidad.md:54` vs
     `winsw.xml.example:21` + stdout (`server.py:766-777`). Ojo: la Etapa R (Capa B)
     hace que parte de esto pase a ser verdad — coordinar el texto.
  8. `/admin/config` "público" — `docs/proxy-config.md:163`,
     `docs/escalabilidad-remota.md:78,189`, `Escalabilidad.md:38`, `anotaciones.md:45`,
     `docs/arquitectura.md:51` vs `server.py:663-667` (`Depends(verify_admin_key)`,
     y devuelve el token en claro).
  9. "`config.yaml` no se lee" — **invertida**: el código ya lo lee
     (`config.py:13-18,22,74-89`, `d9c1ef7`, `tests/test_config.py`); ahora mienten
     `AGENTS.md:584,589-593`, `HistorialResumenes.md:26,28`.
  10-12. Tres refs a `py314` — `TestingLog.md:11,257`, `SkillsPropuestas.md:53`
     vs `pyproject.toml:10` (`py312`).

  _Las 8 de la Etapa C (todas vigentes):_
  13. `192.168.1.50:8080` sin esquema — `docs/proxy-config.md:26`, `README_PROXY.md:71`,
      `docs/proxy-deploy.md:95` (+ `README.md:51`, `docs/arquitectura.md:40`) vs `main_window.py:337-341`.
  14. Etiqueta "IP:puerto del proxy" no normaliza — `main_window.py:240`.
  15. "Conexión OK (45 ms)" — `docs/proxy-config.md:35`, `README_PROXY.md:73`,
      `docs/proxy-deploy.md:97` vs `main_window.py:308` (muestra `session_age`, no latencia).
  16. `PlanesAprobados.md:219` `win_sessid` vs `session_config.py:21` `session_cookie`
      (y `:197` de este archivo ya dice `session_cookie` — se contradice a sí mismo).
  17. `docs/proxy-config.md:100-106` no menciona el diálogo "Configurar Sesión (standalone)".
  18. `main_window.py:362-363` hace `.base_url` sobre `from_keyring()` sin comprobar `None`.
  19. "Probar conexión" traga la excepción real — `main_window.py:316-317` (`"Error de conexion"`).

  Notas de edición: `docs/rotacion-credenciales.md:51` y `:53` son dos encabezados
  casi idénticos; `resumenes/*.md` son snapshots inmutables (`AGENTS.md:249-252`) —
  **no tocar**.

### Análisis de lo ya hecho (piezas reutilizables — NO reimplementar)

| Necesita el plan | Ya existe | Uso |
|---|---|---|
| Inyectar cookie en el core | `ValidatorAPI.set_session_cookies()` / `get_session_cookies()` (`core/api.py:282`/`:288`) | Se usa tal cual en Fases 1 y 3 |
| Validar una `PHPSESSID` contra WinForce | `ValidatorAPI._verificar_sesion_activa()` (`core/api.py:233`) y su copia `validate_session_cookie()` (`rotate_creds.py:45`) | Se extrae a `validar_cookie_sesion()` y se deduplica |
| Persistir la cookie del proxy en keyring | `_load_session_cookies()` / `_save_session_cookies()` (`server.py:148`/`:133`, clave `credentials_cookies`) | `set_session_cookie` reusa `_save_session_cookies` |
| Flujo de cookie manual en la PC del proxy | `rotate_creds.py` completo (pega → valida → keyring → verifica `/admin/status`) | Sigue siendo el camino oficial; solo cambia su validador interno |
| Diálogo modal de configuración en la GUI | `_abrir_config_proxy()` (`main_window.py:206`) — Entry con `show`, checkbox "Mostrar", "Probar" en hilo, guardar en keyring | Plantilla exacta para `_abrir_config_sesion()` |
| Keyring del lado cliente | `ProxyClient.from_keyring()` / `save_to_keyring()` (servicio `JSWinClient`) | Mismo patrón para `session_config.py` (usuario `win_sessid`) |
| Códigos de error de sesión | `ERR_SESSION_EXPIRED`, `ERR_SESSION_COOKIES` ya en `ERROR_CODES` | Se reutilizan, no se crean nuevos |
| Prueba end-to-end cookie→cobertura→score | `tools/probar_con_cookie.py` (`_diagnosticar_score` incluido) | Base para `tools/medir_sesion.py` |

### Código muerto de la Fase 1 — ELIMINADO (`1dcecc6`, 2026-09-04)

Ya hecho, se deja como referencia de qué se tocó:
- `server.py:_relogin_silent()`: ya no intenta `client.login()` con
  `usuario`/`password` (imposible con 2FA); recarga y revalida la cookie del
  keyring. En `5506ed4` se le añadió logging de cada fallo.
- `server.py`: `login_winforce()` → `set_session_cookie()`; `AdminLoginRequest`
  → `AdminCookieRequest` (`{php_sessid}`); `/admin/login` y `/admin/rotar`
  intercambiables.
- `auto_relogin_if_needed()` se conservó con ese nombre (no se renombró a
  `ensure_session_fresh` como decía el plan); el early-return por
  `_last_activity == 0` sigue siendo lo que necesita un cliente con cookie
  inyectada.

## Plan aprobado — Puesta en marcha del proxy (2026-09-09)

Activar end-to-end todo lo construido. Detalle en `~/.claude/plans/shimmying-skipping-mochi.md`
y en `~/.claude/plans/steady-crunching-music.md` (Etapa R). Vista de conjunto en
`Roadmap.md`. Estado:

- **Etapa 0 — desbloquear el arranque. [COMPLETADA 2026-09-09]** `config.yaml` se
  lee (`d9c1ef7`); 3 bugs de `install_service.bat` + `winsw.xml` fuera de git
  (`ffa213a`); `install_service.bat:262` (`b70dacf`). 0.5 pospuesta.
- **Etapa A — proxy en primer plano + auth. [COMPLETADA 2026-09-09]** (`7992e01`).
- **Etapa B — sesión viva + validación real end-to-end. [COMPLETADA 2026-09-09]**
  cobertura SI / score 423 MUY ALTO contra WinForce real; fix `deuda_total` int
  (`3f63e8f`, `898b9ab`).
- **Etapa C — GUI (Tkinter) contra el proxy. [COMPLETADA 2026-09-09]** pasos 10-11
  validados; la suite envenenaba el keyring del proxy → `tests/conftest.py`
  (`ffc5296`); paso 12 (standalone) no aplica ya (el modo proxy siempre gana).
  Ver `ResumenDelDia.md`.
- **Etapa R — robustez de sesión del proxy. [EN COLA]** El proxy puede quedarse
  sin sesión WinForce sin avisar. R1 detección fiable · R2 fail-fast HTTP 503 ·
  R3 aviso al owner por 3 vías (GUI del agente · Evento Windows + Tarea programada
  · toast de la extensión · webhook opcional) · R4 `/health` honesto. Plan:
  `~/.claude/plans/steady-crunching-music.md`. **Desbloquea la D.**
- **Etapa 0.5 — almacén de la cookie con LocalSystem. [EN COLA]** `rotate_creds.py`
  debe empujar la cookie por HTTP, no escribir el keyring del owner.
  `~/.claude/plans/shimmying-skipping-mochi.md:145-158`. **Bloquea la D.**
- **Etapa C.12 — modo standalone en la GUI. [EN COLA, opcional]** Exige borrar a
  mano el keyring de proxy (`main_window.py:75-77`).
- **Etapa D — servicio de Windows en la PC de oficina. [EN COLA]** Los 11 pasos de
  `install_service.bat`, sobrevive a reinicio, firewall LAN, Tarea programada de
  aviso de la Etapa R. **Bloqueada por R y 0.5.**
- **Etapa E — runbook de la oficina. [EN COLA]** El procedimiento verificado en la
  D, en `docs/proxy-deploy.md`. **Bloqueada por acceso físico.**
- Luego: **Fase 5 — barrido de docs** (arriba en este archivo).

## Fuera de alcance de la sesión actual — próxima fase

- ~~**Login asistido con Playwright**~~ → **IMPLEMENTADO 2026-09-08** (Fase 2.5, ver
  arriba). `login_asistido.py` extrae la `PHPSESSID` de `context.cookies()` y
  `rotate_creds.py` la guarda directo en keyring (no vía `/admin/login`, para que
  funcione aunque el proxy esté caído).

## Pendientes adicionales (cola activa)
- Decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`.
- ~~Conectar GUI a core end-to-end~~ → **absorbido por el plan "Sesión WinForce robusta"
  (Fase 3)**.
- ~~Escribir `tests/test_proxy.py`~~ → **absorbido por el plan "Sesión WinForce robusta"
  (Fase 4)**.
- ~~`requirements.txt` no incluye `httpx`~~ → **RESUELTO 2026-09-08**: `httpx>=0.27`
  movido a `requirements.txt` (la GUI importa `ProxyClient` siempre); quitado el
  duplicado de `requirements-proxy.txt`.
- ~~`pyproject.toml` exige `Python>=3.14`~~ → **RESUELTO 2026-09-08**:
  `requires-python = ">=3.12"` (piso real probado; cero sintaxis 3.13/3.14 en el
  código), `ruff target-version = "py312"`, requisito de versión unificado en
  `3.12+` en todo el repo. El workaround `PYTHONPATH=.` para `tools/` tampoco hace
  falta desde `82f9a4c`.
- ~~`resumenes/2026-09-04.md` y `2026-09-05.md` sin crear~~ → **RESUELTO
  2026-09-08**: recuperados verbatim de git.
- ~~Corrida de keepalive v3~~ → **CERRADA 2026-09-08**: `keepalive_interval_seconds
  = 900` fijado; tope absoluto de sesión ≈ 9.5 h confirmado. Ver Fase 0 (act.
  2026-09-08) y `anotaciones.md`.

## Notas de seguridad
- Credenciales de Win rotan cada 1-2 meses; nunca hardcodear; en proxy solo viven en keyring PC proxy.
- NO subir a GitHub: `config.yaml`, `proxy_token.txt`, `admin_key.txt`, `tools/captura.json`, `tools/js/`, `generator/private_key.pem`, credenciales reales.
- Token proxy = secreto LAN (binding IP); admin key = solo owner.