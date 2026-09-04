# PlanesAprobados.md — Planes de trabajo aprobados

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Contexto
App de escritorio (Python/Tkinter) para un call center que valida COBERTURA
(coordenadas) y SCORE crediticio (DNI/RUC/CE) replicando la API interna de
appwinforce.win.pe (sin scrapear HTML). Repo:
https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Estado del proyecto (verificado 2026-08-26)
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
  probabilístico de PHP. **Conclusión para Fase 2 SUPERADA por hallazgos
  posteriores** (ver `tools/medir_keepalive.py` y `anotaciones.md` "Dos
  límites de sesión" / hallazgos 2026-09-04 tarde): un keepalive de pings
  reales no se comporta como un simple idle-timeout evitable con cualquier
  intervalo fijo — hay indicios de detección anti-bot (query idéntico
  repetido + actividad automatizada acumulada). La decisión final de
  `keepalive_interval_seconds` queda **pendiente** hasta cerrar esa
  investigación (test con `--coords-lista` programado, requiere lista de
  coordenadas reales del usuario).
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
- **Fase 2 (B) — keepalive en el proxy. [BLOQUEADA, pendiente de investigación]**
  Loop `asyncio` en `lifespan` que pinga WinForce periódicamente (config
  `keepalive_enabled` / `keepalive_interval_seconds`) — diseño original asumía
  `operador.php` (solo lectura) cada ~90s, pero eso ya no aplica: ver
  investigación en curso (`tools/medir_keepalive.py`, `anotaciones.md`). Antes
  de implementar esta fase falta cerrar: (1) qué endpoint usar como ping real
  (`validar_cobertura` funcionó mejor que el chequeo pasivo, pero no es
  gratis — cuenta como consulta real de negocio), (2) si hace falta rotar
  coordenadas/variar el patrón para evitar detección anti-bot, y (3) qué
  intervalo es seguro dado que el "tope" observado varió entre 1100s y 2400s
  según la corrida.
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

### Código muerto confirmado a eliminar/reemplazar (Fase 1)

- `server.py:_relogin_silent()` (`:111`): lee `usuario`/`password` del keyring y llama
  `client.login()` → **imposible con 2FA**, nunca tuvo éxito en producción.
- `server.py:login_winforce(usuario, password)` (`:195`), `AdminLoginRequest`,
  `/admin/login`, `/admin/rotar`: asumen credenciales; pasan a cookie.
- `server.py:ProxyValidatorAPI.auto_relogin_if_needed()` (`:104`): solo llamaba a
  `_relogin_silent`; se renombra a `ensure_session_fresh()` y recarga cookie.
- `core/api.py:ValidatorAPI.auto_relogin_if_needed(credentials)` (`:267`): el path con
  `credentials` no se ejercita en producción; se conserva solo el early-return por
  `_last_activity == 0` (que es justo lo que necesita un cliente con cookie inyectada).

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
- `pyproject.toml` exige `Python>=3.14`. La máquina de la sesión 2026-08-27 solo tenía
  3.12.2 (workaround `PYTHONPATH=.`); la máquina actual (2026-08-28) sí tiene 3.14.7, así
  que no bloquea hoy. Decidir si se relaja el requisito o se documenta como obligatorio.

## Notas de seguridad
- Credenciales de Win rotan cada 1-2 meses; nunca hardcodear; en proxy solo viven en keyring PC proxy.
- NO subir a GitHub: `config.yaml`, `proxy_token.txt`, `admin_key.txt`, `tools/captura.json`, `tools/js/`, `generator/private_key.pem`, credenciales reales.
- Token proxy = secreto LAN (binding IP); admin key = solo owner.