# PlanesAprobados.md — Planes de trabajo aprobados

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Contexto
App de escritorio (Python/Tkinter) para un call center que valida COBERTURA
(coordenadas) y SCORE crediticio (DNI/RUC/CE) replicando la API interna de
appwinforce.win.pe (sin scrapear HTML). Repo:
https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Estado del proyecto (verificado 2026-08-26; addendum 2026-09-05)

**Addendum 2026-09-05**: del plan "Sesión WinForce robusta" — Fase 1 (limpiar
login muerto) COMPLETA y con la visibilidad de fallos añadida encima (`5506ed4`);
Fase 0 (medir vida de sesión) COMPLETA pero su conclusión quedó **superada**: la
investigación de keepalive se reabrió con método corregido (`medir_keepalive.py`
v3) y hay una **corrida final en curso** (2h+ con la sesión viva, ver Fase 0 más
abajo). **49 tests, ruff limpio.** Fase 2 en desbloqueo; Fases 3–5 pendientes.

- Fase 0 (captura de la API): COMPLETA.
- Fase 1 (núcleo core): COMPLETA — 35 tests, ruff limpio.
- Fase 1.5 (decisión de autenticación): **DECIDIDA — Opción B (Proxy Local)**.
- Fase 0 Documentación: COMPLETA — `docs/`, `Escalabilidad.md`, `anotaciones.md`, `resumenes/`.
- **Proxy Local (FASES 1.1–1.5) IMPLEMENTADO**: `validator_app/proxy/` completo
  (server.py, config.py, client.py, rotate_creds.py, winsw.xml, install/uninstall .bat),
  core adaptado (`auto_relogin_if_needed`, persistencia cookies), GUI conectada
  (menú "⚙️ Configuración"). Detalle en `AGENTS.md` (Historial → Fase Proxy —
  Implementación).
- **Gap detectado**: no existe `tests/test_proxy.py` — el plan original (FASE 1.1,
  paso 5 abajo) lo pedía y no se hizo. El proxy no tiene tests unitarios propios;
  los 37 tests actuales cubren core/activation/GUI fields, no `validator_app/proxy/`.
  (En camino de cerrarse: Fase 4 del plan "Sesión WinForce robusta".)
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
  **Actualización 2026-09-05 — la investigación de keepalive se rehízo con
  método corregido.** Los datos de v1/v2 (que sugerían un "tope absoluto a 40
  min" y posible anti-bot) resultaron **inservibles**: v1/v2 medían tiempo de
  test, no edad de sesión, y trataban cualquier error como muerte. `medir_keepalive.py`
  **v3** mide `edad_sesion_s`, clasifica el fallo y lo confirma con
  `validar_cookie_sesion()` antes de cortar. La corrida v3 (intervalo 900s, 49
  coords rotativas de `coords_prueba.txt`) lleva **2h+ con la sesión viva** →
  el keepalive de 15 min funciona; "tope a 40 min" y "anti-bot" quedan muy
  debilitados. **Falta el desenlace de la corrida nocturna** (`medir_keepalive.log`);
  con él se fija `keepalive_interval_seconds`.
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
- **Fase 2 (B) — keepalive en el proxy. [DESBLOQUEO EN CURSO]**
  Loop `asyncio` en `lifespan` que pinga WinForce (config `keepalive_enabled` /
  `keepalive_interval_seconds`). Las 3 preguntas que la bloqueaban están casi
  resueltas por la corrida v3:
  1. **Endpoint** → `validar_cobertura` confirmado como ping válido (resetea el
     reloj de expiración; el chequeo pasivo de `operador.php` no).
  2. **Rotar coordenadas** → sí; `tools/coords_prueba.txt` tiene 49 y la corrida
     de 2h+ no muestra ningún problema por variar el query.
  3. **Intervalo** → 900s (15 min) en prueba, 2h+ sin fallo. El número final
     sale del desenlace de la corrida nocturna.
  **Diseño acordado: "latido perezoso"** — el loop no pinga cada N s a secas,
  sino solo si pasaron N min **sin tráfico real de los agentes** (comparar
  contra `ProxyValidatorAPI._last_activity`, que ya existe). Con 20 agentes el
  trabajo normal ya mantiene la sesión; el ping solo cubre huecos (almuerzo,
  primera hora). Reduce las consultas fantasma contra la cuenta de Win ~95%.
  Además manejar con gracia la muerte pese al keepalive (avisar al owner, no
  reintentar en silencio) por si hay un tope de sesión de varias horas.
- **Fase 3 (D) — cookie en la GUI (arregla standalone).** `validator_app/gui/session_config.py`
  (NUEVO) + diálogo `⚙️ Configurar Sesión` en `main_window.py`; la rama standalone deja de
  usar `api.obtener_cliente()` y usa un `ValidatorAPI` con la cookie inyectada.
- **Fase 4 — tests.** `tests/test_proxy.py` (NUEVO, cierra el gap de abajo),
  `tests/test_session_config.py` (NUEVO), tests del helper en `tests/test_api.py`.
- **Fase 5 — docs.** `docs/proxy-config.md`, `docs/proxy-deploy.md`, `README_PROXY.md`.

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

## Fuera de alcance de la sesión actual — próxima fase

- **Login asistido con Playwright en la PC del proxy**: un script abre Chrome real, el
  encargado hace login + 2FA en esa ventana, y el script **extrae la `PHPSESSID`
  automáticamente** del contexto del navegador y la empuja a `/admin/login`. Elimina el
  copiar/pegar de F12. Reusa el patrón del proyecto hermano "Captura de API". `playwright`
  ya está en `requirements-dev.txt`; habría que decidir si entra en `requirements-proxy.txt`.
  El plan actual deja `/admin/login` listo para recibir el `php_sessid` que este script
  enviaría.

## Pendientes adicionales (cola activa)
- Decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`.
- ~~Conectar GUI a core end-to-end~~ → **absorbido por el plan "Sesión WinForce robusta"
  (Fase 3)**.
- ~~Escribir `tests/test_proxy.py`~~ → **absorbido por el plan "Sesión WinForce robusta"
  (Fase 4)**.
- `requirements.txt` no incluye `httpx`, que sí necesita el `.exe` del agente al empaquetar
  `proxy/client.py`. (`httpx` sí está en `requirements-proxy.txt`, pero ese archivo es solo
  para la PC del proxy, no para el build del agente.)
- `pyproject.toml` exige `Python>=3.14`. Algunas máquinas del proyecto tienen 3.12.
  El workaround `PYTHONPATH=.` para los scripts de `tools/` **ya no hace falta**
  (`82f9a4c`: los scripts insertan la raíz en `sys.path` solos). Sigue pendiente
  decidir si se relaja el requisito de `pyproject.toml` o se documenta como
  obligatorio.
- **Corrida de keepalive v3 en curso (2026-09-05)**: leer `medir_keepalive.log`
  al retomar; con el resultado, fijar `keepalive_interval_seconds` (Fase 2).

## Notas de seguridad
- Credenciales de Win rotan cada 1-2 meses; nunca hardcodear; en proxy solo viven en keyring PC proxy.
- NO subir a GitHub: `config.yaml`, `proxy_token.txt`, `admin_key.txt`, `tools/captura.json`, `tools/js/`, `generator/private_key.pem`, credenciales reales.
- Token proxy = secreto LAN (binding IP); admin key = solo owner.