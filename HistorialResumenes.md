# HistorialResumenes.md — Archivo histórico de resúmenes

Fecha de creación: 2026-08-21 · Proyecto: JSConnect-Win-Coverage

## Qué es este archivo
Índice cronológico CONDENSADO de las sesiones pasadas. Existe para ubicar rápido
qué ocurrió y enlazar el snapshot completo en `resumenes/<fecha>.md`, mientras
`ResumenDelDia.md` conserva únicamente el estado de la jornada en curso.

**Regla de rotación**: al cerrar una jornada, el contenido íntegro se copia a
`resumenes/<fecha>.md` y aquí se agrega solo una entrada condensada, con lo más
nuevo arriba. Este archivo nunca se borra; solo crece.

---

### 2026-09-25 — Sesión — "URL para los agentes" en la consola owner (fix WinError 10061) + release v2026.09.25
- **Snapshot completo**: `resumenes/2026-09-25.md`.
- **Origen**: primer despliegue real con agente y owner en PC distintas. Al
  configurar el agente con `http://localhost:8080` falló con
  `[WinError 10061] ... denegó expresamente dicha conexión`, porque `localhost`
  en la PC del agente apunta al propio agente, no a la PC del proxy.
- **Fix**: `generator/owner_app.py` gana `detectar_ip_lan()` (socket UDP a
  `8.8.8.8:80` + `getsockname()`, respaldo `getaddrinfo` sin ruta por defecto,
  descarta loopback/APIPA), `puerto_proxy_local()` y `url_para_agentes()`. La UI
  muestra "URL para los agentes" (`http://<ip-detectada>:<puerto>`) lista para
  copiar en el recuadro de estado del proxy.
- **Verificado**: en esta PC detecta `192.168.18.49`, coincide con `ipconfig`.
- **Calidad**: 193 → **201 tests** (8 nuevos en `test_owner_app.py`, TDD
  rojo→verde), ruff limpio.
- **Documentación**: `docs/proxy-deploy.md` (aviso de no usar `localhost` +
  fila en troubleshooting), `README.md` (es/en), `TestingLog.md`.
- **Release**: `v2026.09.25` publicado con ambos `.exe` reconstruidos,
  reemplazando `v2026.09.22`.
- **Segunda parte de la sesión — fix del chequeo de actualización**: la
  observación de arriba sobre `target_commitish` se revisó el mismo día.
  Confirmado (`gh release view ... --json targetCommitish` → `"main"`) que ese
  campo es la rama del tag, nunca un SHA, así que `hay_actualizacion()` siempre
  creía que había una versión nueva. Fix: `_commit_de_tag()` (NUEVO) resuelve el
  SHA real vía `GET /commits/{tag}`. Verificado en vivo:
  `_commit_de_tag("v2026.09.25")` devolvió el commit exacto embebido en ese
  Release. 8 tests nuevos, 201 → **206 tests**, ruff limpio. **Decisión de
  proceso**: un Release ya no se publica por cada commit, solo a pedido
  explícito — este fix quedó comiteado y pusheado sin Release nuevo.
- **Tercera parte de la sesión — el instalador no abría el puerto en el
  Firewall**: con la IP ya corregida, el mismo agente pasó de `WinError 10061` a
  `Timeout` — firma de un firewall que descarta el paquete en silencio en vez de
  rechazarlo (confirma que IP/puerto ya estaban bien). `install_service.bat`
  solo imprimía el comando `New-NetFirewallRule`, nunca lo ejecutaba (gap
  anotado desde 2026-09-18). Fix: nuevo paso `[11/13]` (instalador renumerado de
  12 a 13 pasos), idempotente, con fallback manual si el firewall es de dominio;
  `uninstall_service.bat` quita la regla. Guarda genérica nueva
  (`test_los_pasos_numerados_son_consistentes`) contra volver a olvidar
  renumerar un paso. Se le dio al usuario el comando manual para desbloquearse
  ya mismo. 206 → **209 tests**, ruff limpio. Sin Release (el `.bat` no se
  empaqueta).
- **Cuarta parte de la sesión — validar cobertura o score por separado**: con el
  proxy conectando de punta a punta, pedido nuevo: el botón VALIDAR exigía
  coordenadas Y documento siempre. Fix: `validar_score()` acepta `lat`/`lon` en
  `None` (en blanco en el payload, mismo patrón que la geodata opcional);
  propagado por `server.py`/`client.py`; la GUI detecta qué campo(s) llenó el
  agente (solo coords → cobertura; solo documento → score directo; ambos → sin
  cambios). Helper `_a_dict()` normaliza dataclass (proxy) vs dict (standalone).
  **Verificado en vivo**: no se pudo leer la cookie del keyring (vive en
  LocalSystem, aislado); el usuario dio el `PROXY_TOKEN` y reinició el servicio;
  `POST /api/score` con coordenadas `null` para el DNI de prueba **10412031**
  devolvió `Score 862/BAJO riesgo` (HTTP 200) — confirma que WinForce no
  requiere coordenadas para el score. `10412031` queda como DNI de prueba fijo
  del proyecto. 209 → **212 tests**, ruff limpio.
- **Cierre técnico**: reconstruido el `.exe` del agente (commit `513a2f7`);
  owner reutilizado sin cambios. Release **`v2026.09.25.1`** publicado (tag
  nuevo, no reemplaza `v2026.09.25` de la mañana). Los 4 casos de validación
  parcial se confirmaron con una instancia REAL de `App` (`mainloop()` de
  verdad, no solo el smoke headless) a pedido del usuario.
- **Quinta parte — rediseño visual, Etapa 1/3 (iconos)**: pedido de iconos
  distintos agente/owner/extensión + navegación extensible en el agente.
  Investigación (WebSearch): **CustomTkinter no soporta `--onefile`**
  (documentación oficial exige `--onedir`, rompería el `.exe` portable) →
  decisión **ttkbootstrap** (sí soporta `--onefile`). Plan en 3 etapas: iconos
  → tema (agente claro `cosmo` / owner oscuro `superhero`) → barra lateral de
  navegación. **Etapa 1 completada**: `tools/generar_iconos.py` (NUEVO,
  Pillow) genera `assets/icons/agent.ico`/`owner.ico` (pin azul / llave ámbar)
  y el icono real de la extensión (antes un cuadrado verde liso). Bug real
  encontrado: Pillow instalado en el venv hacía que un hook de PyInstaller lo
  arrastrara al `.exe` sin uso real (+7 MB); fix `--exclude-module PIL` en
  ambos scripts de build, verificado con el tamaño normal y extrayendo el
  icono real de cada `.exe` compilado. 212 tests, ruff limpio. Sin Release
  (pendiente completar las 3 etapas).
- **Sexta parte — rediseño visual, Etapas 2 y 3 (cierre)**: `App`/`OwnerApp`
  pasan a `ttkbootstrap.Window` (`cosmo` claro / `superhero` oscuro).
  Descubierto en el camino: esta versión de ttkbootstrap NO retema los widgets
  `ttk.*` planos como la 1.x investigada — hace falta `bootstyle=` explícito.
  **Etapa 2.1** (feedback al ver las ventanas reales): indicadores de
  cobertura/score coloreados por el riesgo real de WinForce (verde/ámbar/rojo);
  contraste del owner corregido con la fórmula WCAG (rojo daba 2.78:1 sobre el
  fondo oscuro, bajo el mínimo 4.5:1 — cambiado a ámbar, 5.66:1); botón nuevo
  "Instalar extensión en Chrome" con diálogo de los 4 pasos + ruta real.
  **Etapa 3**: barra lateral de navegación en el agente
  (`self._paginas`/`_mostrar_pagina()`, lista para funciones futuras) — dos
  rondas de feedback ("parece un botón enorme", "el uso de los colores no me
  convence") llevaron a un ítem de navegación plano (barra de acento de color
  real del tema, sin caja de botón, sin fondo gris en la barra). Un bug de
  coordenadas en un script de captura de pantalla capturó por error contenido
  ajeno de la pantalla del usuario — se borró de inmediato, no se repitió.
  **Con esto se cierran las 3 etapas.** 219 tests, ruff limpio. Reconstruido
  `JSConnect-Win-Coverage.exe` (owner reutilizado sin cambios). Release
  **`v2026.09.25.2`** publicado.

### 2026-09-22 — Sesión — UAC falso-cancelado + `sc qc` en español, y release v2026.09.22
- **Snapshot completo**: `resumenes/2026-09-22.md`.
- **Origen**: al probar en vivo (PC de casa, proxy de desarrollo instalado) el panel de
  credenciales agregado ayer, el botón **Mostrar** fallaba con "UAC cancelado"
  **sin que apareciera ningún diálogo real**, incluso corriendo la consola como
  Administrador.
- **Bug 1**: `_ejecutar_elevado()` combinaba `-Verb RunAs` con
  `-RedirectStandardOutput` en el mismo `Start-Process` — combinación inválida en
  PowerShell (una exige `UseShellExecute=true`, la otra `false`), rechazada antes de
  mostrar ningún UAC. Fix: la ruta de salida se pasa como argumento posicional; el
  subcomando elevado escribe el JSON directo al archivo en vez de usar stdout.
- **Confirmaciones**: **Mostrar** ahora pide confirmación propia antes del UAC (no
  tenía ninguna); **Rotar** menciona que pedirá UAC y su mensaje final indica dónde
  colocar el valor nuevo (proxy_token → reconfigurar agentes; admin_key → solo local).
- **Bug 2** (destapado al verificar el fix del Bug 1 en vivo): `ruta_instalacion()`
  buscaba la etiqueta en inglés `BINARY_PATH_NAME` en la salida de `sc qc`, pero
  Windows en español (como toda la oficina) la traduce a `NOMBRE_RUTA_BINARIO` —
  nunca matcheaba, caía a un fallback inválido en el `.exe` empaquetado y fallaba
  aunque el servicio y `config.yaml` sí existían. Habría afectado a cualquier PC de
  la oficina. Fix (decisión del owner: detectar idioma, no cambiar de comando):
  reconoce ambas etiquetas, inglés primero, español como segunda opción.
- **Verificado en vivo end-to-end** en esta PC (servicio real instalado): Mostrar y
  Rotar completos, para `proxy_token` y `admin_key`.
- **Calidad**: 191 → **193 tests** (`test_owner_app.py` 21→22, `test_secretos.py`
  11→12), suite completa en verde, ruff limpio.
- **Release**: `v2026.09.22` publicado con ambos `.exe` corregidos, reemplazando
  `v2026.09.21` (que tenía los dos bugs sin detectar).
- **Pendiente**: repetir la verificación del flujo elevado en la PC oficial de la
  oficina (esta PC es solo de desarrollo/pruebas). Resto de pendientes del
  2026-09-21 sigue abierto.

### 2026-09-21 — Sesión — credenciales en la consola owner, `/admin/*` loopback-only, y releases de owner+agente
- **Snapshot completo**: `resumenes/2026-09-21.md`.
- **Origen**: el owner propuso exponer `proxy_token`/`admin_key` en la consola owner
  bajo la premisa de un `key.pem` generado por el instalador — premisa incorrecta (el
  instalador solo genera los dos tokens; la llave crítica es `private_key.pem`, de otro
  instalador y no rotable). La conclusión se sostuvo igual: la consola ya convive con esa
  llave, así que exponer tokens rotables ahí no aumenta el riesgo marginal.
- **Hallazgos**: `admin_key` era superconjunto de `proxy_token` (`/admin/config` lo
  devolvía en claro) y `verify_admin_key` no validaba IP con el server en `0.0.0.0`;
  `proxy_token` abre `/api/score` (datos personales por DNI, Ley 29733).
- **Implementado**: `/admin/*` restringido a loopback (no configurable, a diferencia de
  `allowed_networks`); comparación de tokens en tiempo constante; `secretos.py` nuevo
  (lectura/rotación preservando el resto de `config.yaml` + ACL + reinicio del servicio);
  panel "Credenciales del proxy" en `owner_app.py` (Mostrar/Copiar/Rotar vía relanzo
  elevado con UAC, sin debilitar la ACL). `private_key.pem` nunca aparece en la GUI.
- **Traspaso futuro**: `TraspasoInmediato.md` nuevo (plan sin implementar) para el día que
  el proxy tenga que moverse de PC — por qué no usar una semilla compartida para los
  tokens, sincronizar `config.yaml` en su lugar, y que el problema real es la IP fija de
  cada agente, no los tokens.
- **Releases**: se publicó por primera vez el `.exe` del owner junto al del agente en el
  mismo Release de GitHub (`v2026.09.21`, commit `3af91f6`). Al implementar se encontró un
  bug real no planeado: el chequeo de actualizaciones elegía el asset `.exe` por sufijo
  (cualquiera que terminara en `.exe`), y el checksum se extraía con un solo `re.search`
  sobre todas las notas — con dos `.exe` en el mismo release, el agente podía
  autoactualizarse con el binario equivocado o fallar la verificación de integridad
  siempre. Corregido (`check.py` por nombre exacto, `download.py` por bloque de notas) y
  verificado en vivo contra la API real de GitHub, no solo con tests.
- **Calidad**: 157 → **191 tests** (`test_secretos.py`, `test_updater.py` nuevos;
  `test_owner_app.py`/`test_proxy.py` ampliados), suite completa en verde.
- **Pendiente**: el flujo elevado de credenciales no se ha probado en la PC oficial con el
  servicio instalado (UAC real, `sc qc` contra un binPath real, rotación end-to-end). La
  ruta completa de descarga+reemplazo del updater está cubierta por tests unitarios pero
  no en vivo (necesita una segunda versión futura). Sigue abierto todo lo pendiente del
  2026-09-18.

### 2026-09-18 — Sesión — ensayo del proxy en la PC dev: instalador re-ejecutable, consola owner y control de acceso
- **Snapshot completo**: `resumenes/2026-09-18.md`.
- **Decisión**: ensayo completo del proxy en la PC de desarrollo antes de la PC owner
  oficial (sin coexistir con el proxy de la oficina). La oficina tiene 15 PC hoy; meta
  35; piloto de 2 agentes primero.
- **Instalador**: `install_service.bat` re-ejecutable (ventana `cmd /k`, cada paso
  verifica "ya estaba"/"hecho ahora", resumen final) y pregunta Conservar/Regenerar
  tokens. Bug del paso 5 (`)` sin escapar en `echo` dentro de bloques) corregido con
  guarda `tests/test_install_bat.py`. Paso 7: aviso (sin bloquear) y carga manual de la
  extensión cuando la PC no está gestionada (Windows Home/WORKGROUP).
- **Consola owner**: ya no dice "falta configurar el servicio" (usa `127.0.0.1:8080`
  ante `config.yaml` ilegible o inexistente en el `.exe`); botón **Reiniciar servicio**
  (UAC). **Agente**: menú **Activación / Huella de la PC**.
- **Control de acceso**: `localhost` daba 403; loopback siempre permitido. Decisión
  documentada: las IP públicas del router no se agregan; VPN futura cubierta (Tailscale)
  o se añade su rango. Docs: arquitectura, Escalabilidad, glosario, runbook de pendrive.
- **Calidad**: 157 tests, ruff limpio; `conftest.py` aísla el `config.yaml` real.
- **Semana decisiva**: ensayo de construcción de ambos `.exe` desde un clon limpio (≈3
  min; rutas cortas por WinError 206; `version.py` a restaurar; sin `gh`). Runbook en
  `docs/proxy-deploy.md`; el usuario lleva `private_key.pem` a la PC oficial.
- **Pendiente al cierre**: sesión WinForce que murió 3 veces (hipótesis: dos logins en
  paralelo, sin confirmar); persistencia tras reinicio, firewall desde otra PC, carga,
  desinstalar el ensayo; luego Etapa D/E en la PC oficial y Fase 5.

### 2026-09-16 — Sesión — activación RSA real y consola del owner
- **Snapshot completo**: `resumenes/2026-09-16.md`.
- **Activación habilitada**: se derivó e incorporó la llave pública del PEM
  privado del owner; el agente verifica firmas RSA ligadas a su huella. La llave
  privada sigue fuera de Git, con ACL restringida.
- **Consola owner**: `generator/owner_app.py` y `build-owner.ps1` generan códigos,
  consultan el proxy/servicio y abren la renovación asistida de WinForce. En modo
  empaquetado el PEM vive junto a `JSConnect-Win-Owner.exe`.
- **UX corregida y validada**: botones para copiar la huella y pegar el código,
  validación estricta y errores específicos. La prueba manual completa terminó
  con activación correcta.
- **Calidad y entrega**: 141 tests, Ruff y diff-check en verde; builds de agente y
  owner correctos y ejecutados en secuencia. Se deja la Etapa D para la PC owner
  oficial, con transferencia privada del PEM y prueba del servicio LocalSystem.

### 2026-09-15 — Sesión — ensayo de la Etapa D y corrección del instalador
- **Rotación**: se preserva el snapshot completo en `resumenes/2026-09-15.md`.
- **Ensayo del servicio**: `install_service.bat` llegó correctamente a los pasos
  de Python, dependencias y Chromium, pero falló al descargar WinSW.
- **Bug corregido** (`abff2e4`): la URL de WinSW apuntaba a la inexistente
  `v3.0.0`; se actualizó a `v2.12.0`, con `curl.exe` como descarga principal y
  fallback PowerShell con TLS 1.2. También se escaparon flechas `->` que CMD
  interpretaba como redirecciones y podían crear archivos accidentales.
- **Pendiente al cierre**: repetir la instalación elevada desde cero y completar
  la Etapa D.

### 2026-09-11 — Sesión — Etapa 0.5 (cookie por HTTP, no keyring) + planificación de la D
- **Arranque**: la sesión anterior había dejado la Etapa 0.5 a medio hacer y sin commitear (código cambiado, tests rotos, `ruff` con un import sin usar). Se detectó al preguntar "¿ya hicimos la Fase 0.5?" y correr `git status`/`pytest`.
- **Etapa 0.5 — HECHA** (`f5eb257`, `a6e90da`): `rotate_creds.py` deja de escribir la `PHPSESSID` directo en el keyring del owner (`save_session_to_keyring()`, código muerto — el servicio LocalSystem nunca la veía) → `push_session_cookie()` la empuja por HTTP (`/local/renovar` primero, `/admin/rotar` de fallback si no conecta, sin reintento si el local la rechaza). Bug latente arreglado de paso: `config.proxy_local_url` nueva, ignora `proxy_host=0.0.0.0` de producción. 4 tests nuevos con `httpx.post` monkeypatcheado + smoke en vivo contra el proxy real (cookie falsa → 401 real). Docs sincronizados (`anotaciones.md`, `docs/rotacion-credenciales.md`, `PlanesAprobados.md`, `Roadmap.md`) — ya no describen el mecanismo viejo.
- **Calidad**: 129 tests pasando, ruff limpio.
- **Etapa D planificada** (más tarde el mismo día): con R y 0.5 hechas, nada la bloquea. Se decidió con el owner: ensayo en esta PC (no producción real), `config.yaml` de pruebas (puerto 8090) con backup y borrado para forzar la rama de generación fresca del instalador, y se acepta que fuerce la extensión de Chrome por política HKLM. **No se llegó a ejecutar** `install_service.bat`.
- **Trabajo suelto sin relación**: 6 diagramas UML de análisis en `diagramas-locales/` (no versionados a propósito).
- **Pendiente al cierre**: Etapa D (instalar el servicio, nada la bloquea) → E (runbook oficina, bloqueada por acceso físico) → Fase 5 (19 incoherencias doc↔código). Snapshot completo: `resumenes/2026-09-11.md`.

### 2026-09-09 — Sesión — Puesta en marcha end-to-end del proxy (Etapas 0/A/B/C/R)
- **Objetivo del día — HECHO**: activar todo lo construido contra WinForce real por primera vez (hasta entonces cada pieza se había validado por separado con mocks/smoke tests). Rotación previa: `resumenes/2026-09-08.md` creado, entrada condensada agregada aquí.
- **Etapa 0 — desbloquear el arranque** (`d9c1ef7`, `ffa213a`): `config.yaml` no se leía (`settings_customise_sources` faltante) → corregido; 3 bugs de `install_service.bat` (ruta de `requirements-proxy.txt`, `python -c` multilínea roto por cmd.exe, `%PROXY_PORT%` sin expansión retrasada, `where python` cogía el stub de Store); `winsw.xml` sacado de git (`winsw.xml.example` como plantilla) + ACL `icacls` para `config.yaml`/tokens. Etapa 0.5 (coherencia del keyring bajo LocalSystem) pospuesta a después de la C.
- **Etapa A — proxy en primer plano + auth** (`7992e01`): `config.yaml` local en puerto 8090 confirma que se lee de verdad; auth de `/api/*` y `/admin/*` verificada (401 sin token/key, 200 con); pipeline OK, sesión aún muerta.
- **Etapa B — sesión viva + validación real** (`3f63e8f`, `898b9ab`): login asistido recuperado reabriendo el perfil persistente tras un fallo de captura; cobertura SI / score 423 MUY ALTO contra WinForce real (idéntico al baseline 2026-08-27). Bug real corregido: `ScoreResponse.deuda_total` reventaba con `DeudaTotal: 0` (int) de WinForce. Hallazgo operativo: reabrir el login asistido con sesión viva puede invalidarla — renovar solo cuando el proxy reporta sesión muerta.
- **Etapa C — GUI (Tkinter) contra el proxy** (`b70dacf`, `ffc5296`, `f91b9fb`): validación real desde la GUI (cobertura + score, dos DNIs); paso 12 (standalone) no aplica, el modo proxy siempre gana. **Hallazgo crítico corregido**: la suite de tests envenenaba el keyring real del proxy (`tests/test_proxy.py` escribía `credentials_cookies` sin mockear) → `tests/conftest.py` con fixture autouse que aísla keyring por test. `install_service.bat:262` seguía mandando al Visor de Eventos en la rama de error — corregido.
- **Etapa R — robustez de detección de sesión muerta** (`82f3604`→`67ec0e4`, no estaba en el plan original, nació del hallazgo C.2): fix del bug que cegaba la alarma (`auto_relogin_if_needed()` ya no refresca `_last_activity`, solo lo hace una llamada real exitosa); validación de la cookie al arrancar; fail-fast HTTP 503 + `Retry-After` antes de tocar WinForce; aviso al owner por 3 capas (GUI · Evento de Windows + tarea programada · toast de la extensión · webhook opcional). `Roadmap.md` nuevo (vista única del proyecto); plan de puesta en marcha registrado en `PlanesAprobados.md`.
- **Calidad**: 124 tests pasando, ruff limpio.
- **Pendiente al cierre**: Etapa 0.5 (coherencia del keyring con LocalSystem — bloquea la D) → C.12 (standalone, opcional) → D (servicio de Windows en la PC de oficina) → E (runbook, bloqueada por acceso físico) → Fase 5 (barrido final de 19 incoherencias doc↔código). Sesión del proxy dejada muerta a propósito. Snapshot completo: `resumenes/2026-09-09.md`.

### 2026-09-08 — Sesión — Fases 2A/2.5/3/4: keepalive, renovación sin F12 y tests del proxy
- **Arranque**: repo 6 commits por detrás (sesión 2026-09-05, otra máquina); `git pull --ff-only` limpio. **10 commits hoy** (`cae2702` → `76afb9d`), **104 tests pasando, `ruff` limpio**. Esta PC en Python 3.14.7.
- **Investigación de keepalive CERRADA** (reporte final de la corrida v3 recibido hoy): 37 pings consecutivos VIVA hasta ~9 h 16 m de edad de sesión; muerte limpia a ~9 h 31 m (HTTP 200 + HTML de login, confirmada por `validar_cookie_sesion()`). Idle-timeout, anti-bot acumulativo y "tope a 40 min" **descartados**; **sí existe un tope absoluto de sesión ≈ 9.5 h desde el login**, independiente de la actividad → reinyectar la cookie al inicio del turno. Sincronizado en `PlanesAprobados.md` / `anotaciones.md` / `AGENTS.md`.
- **Fase 2A — keepalive del proxy "latido perezoso" (`b3adb38`)**: `_keepalive_loop` (asyncio en el `lifespan`) + `ProxyValidatorAPI._keepalive_tick` (síncrono, testeable); omite el ping si hubo tráfico de agentes en el intervalo; ping = `validar_cobertura` con coord aleatoria de 12 puntos de Lima embebidos; fallo → confirma con `validar_cookie_sesion()` y clasifica `TRANSITORIO` / `SESION_MUERTA` (log.error una vez con remedio) / indeterminado, nunca reintenta en silencio. Config `keepalive_enabled` / `keepalive_interval_seconds=900`; bloque `keepalive` en `/admin/status`. **Bug latente arreglado**: el guard idle de 120 s del cliente-core (`auto_relogin_if_needed`) lanzaba `SessionError` en cada hueco de tráfico > 120 s antes de tocar la red → `_get_client()` pone `_session_max_idle = 10**9`.
- **Fase 2.5 — renovación de la sesión sin F12** (por el tope ≈ 9.5 h el owner renueva ~1 vez por jornada): **login asistido** `login_asistido.py` NUEVO (`28b7698`) abre un navegador, el owner inicia sesión, el script sondea `context.cookies()` (ve la `PHPSESSID` HttpOnly), la valida y la guarda directo en keyring; `rotate_creds.py` → v2 (sin args = asistido bajo `pythonw`, `--manual` = copiar/pegar, `--fresh`, `--preview` `c96de4c`). `cb085da`: abre el **Chrome instalado** (`channel="chrome"`) para el autofill de contraseñas.
- **Fase 2.5d — extensión de Chrome (`499ba5f`) — VÍA PRINCIPAL**: Chrome 136+ bloquea `--remote-debugging-port` con el perfil por defecto → no se puede adjuntar Playwright al Chrome cotidiano. `validator_app/proxy/extension/` MV3 (permisos `cookies`/`alarms`/`notifications`); badge rojo cuando la sesión murió (poll `GET /local/estado` cada 5 min); clic → `chrome.cookies.get` → `POST /local/renovar`. Endpoints locales nuevos en `server.py` (`_es_local`: solo 127.0.0.1, sin admin key). `_instalar_extension.py` NUEVO empaqueta un `.crx` firmado (id estable vía `extension.pem`) y fuerza-instala por política `HKLM\...\ExtensionSettings`. Guía de prueba en `README_PROXY.md` (`e517a2b`).
- **Fase 3 — diálogo de cookie en la GUI (`5cf8e3f`)**: el modo standalone estaba **roto de raíz** (llamaba `api.obtener_cliente().validar(...)` sobre un `ValidatorAPI` sin sesión → siempre `SessionError`). `validator_app/gui/session_config.py` NUEVO (keyring `JSWinCoverage`/`session_cookie` + validación + `cliente_standalone()` con `_session_max_idle = 10**9`); menú "⚙ Configurar Sesión (standalone)" + diálogo modal en `main_window.py`. `api.obtener_cliente()` se conserva (lo usan `tools/`).
- **Fase 4 — cubrir la capa FastAPI del proxy (`76afb9d`)**: 14 tests de `/api/*`, `/health`, `/admin/*`, middleware de auth y exception handlers. `tests/test_proxy.py` estrena `TestClient`. **Ningún bug en `server.py`** — la capa HTTP quedó cubierta sin cambios de código.
- **Deuda técnica cerrada (`b3aca38`)**: `httpx>=0.27` → `requirements.txt` (la GUI importa `ProxyClient` siempre); `requires-python` `>=3.14` → **`>=3.12`** (piso real; cero sintaxis 3.13/3.14), `ruff target-version = "py312"`, versión unificada en `3.12+` en todo el repo; `resumenes/2026-09-04.md` y `2026-09-05.md` creados (recuperados de git).
- **Hook de auto-sync de docs (`cae2702`)**: `.claude/settings.json` + `.claude/hooks/historial_sync.py` (`PostToolUse` sobre `Write|Edit`) — al agregar entradas `### YYYY-MM-DD` a este archivo, recuerda sincronizar `anotaciones.md` / `PlanesAprobados.md` / `AGENTS.md`; cada 3 entradas nuevas, además `README.md`. Solo avisa, no edita. Estado local gitignored.
- **Descubrimientos clave para el próximo dev**: tope absoluto de sesión ≈ 9.5 h desde el login (re-login programado inviable por 2FA); Chrome 136+ bloquea el remote-debugging con el perfil por defecto (anti-robo-de-cookies); `chrome.cookies` y `context.cookies()` SÍ leen HttpOnly, `document.cookie` NO (un bookmarklet no serviría); **`config.yaml` NO se está leyendo** — `SettingsConfigDict` declara `yaml_file` pero falta `settings_customise_sources` con `YamlConfigSettingsSource`; el proxy funciona por defaults + variables `PROXY_*`.
- **Validado end-to-end contra WinForce real**: al arrancar el proxy en esta PC el keepalive pingó con la `PHPSESSID` muerta del keyring, la detectó (HTTP 200 + HTML), la confirmó y disparó el `ERROR` de aviso al owner — exactamente lo diseñado. El proxy de la demo quedó **parado** (`taskkill` — incidente en `TestingLog.md`).
- **Pendiente al cierre**: **Fase 5** (barrido final de docs — `docs/proxy-config.md`, `docs/proxy-deploy.md`, `docs/rotacion-credenciales.md`, coherencia general: extensión = principal, login asistido + `--manual` = fallback). Verificaciones manuales con cookie real: GUI standalone, extensión end-to-end, login asistido (`.lnk` del Escritorio). Deuda vieja: `config.yaml` no se lee; decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`.
- Snapshot completo: `resumenes/2026-09-08.md`.

### 2026-09-05 — Sesión — Visibilidad de fallos del proxy, método de keepalive v3 y corrida final
- **Fix `5506ed4` — el proxy deja de fallar en silencio**: `_relogin_silent()` y `_load_session_cookies()` tenían `except Exception: pass`; ahora cada fallo se loguea con causa + error concreto + remedio (sin cookies en keyring / JSON corrupto / sin `PHPSESSID` / cookie expirada / fallo de red / éxito). Se mantiene el contrato (`_relogin_silent()` no propaga). Los 6 caminos se ejercitaron en la sesión.
- **Fix `5506ed4` — `/health` deja de pegar a WinForce en cada request**: nuevo `_is_session_alive()` cachea `session_alive` 30s (`SESSION_ALIVE_TTL_SECONDS`), atado al valor de la cookie; los fallos de red no se cachean. `logging.basicConfig(level=INFO)` en el `__main__` de `server.py` para que los mensajes se vean. `docs/arquitectura.md` sincronizado (arranque real `python -m`, endpoints admin por cookie `PHPSESSID`, clave de keyring `credentials_cookies`); árbol de `tools/` completado en `AGENTS.md`.
- **`medir_keepalive.py` v3 (`3925dbf`)** — reescritura del método porque v1/v2 no permitían concluir nada: medían tiempo de test y no la edad real de la sesión (el cronómetro arrancaba con el script, no con el login; `acceso.php` no regenera la `PHPSESSID`), y trataban cualquier error como muerte. v3: `--login-hora`/`--edad-inicial` obligatorios, columna `edad_sesion_s`, `_clasificar()` (`SESION_MUERTA`/`TRANSITORIO`/`OTRO` según `code` + status HTTP), `_confirmar_muerte()` revalida con `validar_cookie_sesion()` antes de cortar, `--coords-archivo`. 9 tests del clasificador (`tests/test_medir_keepalive.py`).
- **`coords_prueba.txt` a 49 puntos (`26e7567`)**: 10 del usuario + 39 generados con rejilla + jitter dentro de su polígono (Jesús María / Lince / San Isidro, ubicaciones públicas, no domicilios) para no repetir el mismo query en una corrida larga.
- **`82f9a4c`**: los 6 scripts de `tools/` que importan `validator_app` insertan la raíz del repo en `sys.path` antes del import → `python tools/X.py` funciona desde la raíz sin `PYTHONPATH` ni `pip install -e .`. Cierra el workaround que arrastraban los cierres 2026-08-27 y 2026-09-04.
- **Corrida keepalive v3 — desenlace (reporte final recibido 2026-09-08)**: arrancó 21:08 con la sesión a 70s de edad, ping fijo cada 900s, 49 coords rotativas. **37 pings consecutivos VIVA** (última confirmación a los 33 370s / 9 h 16 m de edad de sesión); murió **limpia** a los 34 270s (9 h 31 m) con patrón HTTP 200 + HTML de login, confirmado de forma independiente por `validar_cookie_sesion()`. Lecturas: idle-timeout **descartado como causa** (ping real cada 900s); anti-bot acumulativo **descartado** (37 pings variados, 0 fallos); "tope a 40 min" **descartado** (era el 404 ambiguo de v1). **Sí existe un tope absoluto de sesión ≈ 9.5 h desde el login**, por encima de la jornada de 8 h con ~1.5 h de margen (reinyectar la cookie al inicio del turno). **Investigación de keepalive CERRADA.**
- **Calidad**: 49 tests pasando, ruff limpio (eran 40; +9 del clasificador). Commits: `5506ed4`, `44d1132` (rotación 09-04 → historial), `3925dbf`, `26e7567`, `82f9a4c` — todos en `origin/main`.
- **Pendiente al cierre**: Fase 2 (keepalive en el proxy) desbloqueada — `keepalive_interval_seconds = 900`, diseño "latido perezoso" (pinguear solo tras N min sin tráfico real de los agentes) + **aviso al owner** cuando la sesión muera por el tope absoluto (re-login programado inviable por el 2FA); sincronizar `PlanesAprobados.md` / `anotaciones.md` / `AGENTS.md` con la investigación cerrada; luego Fase 3 (diálogo de cookie en la GUI), Fase 4 (`tests/test_proxy.py`), Fase 5 (docs). Deuda vieja: `resumenes/2026-09-04.md` y `resumenes/2026-09-05.md` nunca se crearon (solo la entrada condensada); `requirements.txt` sin `httpx`; `pyproject.toml` exige Python≥3.14.

### 2026-09-04 — Sesión — Medición de vida de PHPSESSID y limpieza del login muerto del proxy
- **Fix de entorno**: `tools/medir_sesion.py` fallaba con `ModuleNotFoundError: validator_app` con `C:\Python314\python.exe` directo (paquete no instalado en modo editable en ese intérprete). Resuelto con `python -m pip install -e .`.
- **Fase 0 completada** (`tools/medir_sesion.py`, 4 corridas): la corrida limpia `--max 3600` dio el dato bueno — **VIVA a 1155s, MUERTA a 1350s** (~19–22 min de inactividad real). Las de `--max 600` llegaron a 525s sin morir; una muerte a 135–210s fue anómala (coincidió con recarga que reemplazó la `PHPSESSID`). El idle-timeout real queda algo por debajo del `gc_maxlifetime` default de PHP (1440s) pero en el mismo orden; el `keepalive_interval` planeado da margen amplio.
- **Hallazgo de autenticación**: `acceso.php` **no regenera el PHPSESSID** al loguear (reusa la cookie anónima ya presente); el 2FA de Microsoft pasa por SSO silencioso de Azure AD si ya hay sesión de Microsoft. Documentado en `anotaciones.md`.
- **Keepalive en investigación** (`tools/medir_keepalive.py`, pings de interacción real): v1 (intervalo fijo 5 min) sobrevivió hasta 2100s y murió a 2400s; v2 (intervalos variables 180–420s) murió antes, a **1100s** — más rápido haciendo *más* actividad. Esto rompe el modelo "idle-timeout + tope absoluto de 40 min" (que queda como hipótesis sin confirmar) y apunta a **detección anti-bot acumulativa**: ~4 sesiones automatizadas en ~2 h, todas contra la misma coordenada exacta repetida decenas de veces.
- **Decisión**: pausar pruebas automatizadas; reanudar con `--coords-lista` (coordenadas rotativas que dará el usuario) dejando tiempo entre sesiones. Guard interno de 120s en `ValidatorAPI` (`core/api.py:197`) da falso "sesión expirada" si se reutiliza la instancia entre pings — el script usa instancia nueva por ping.
- **Fase 1 (C) — limpiar login muerto del proxy** (commit `1dcecc6`): `core/api.py` nuevo helper compartido `validar_cookie_sesion()` (reutiliza `_verificar_sesion_activa`); `rotate_creds.py` delega en él (elimina duplicación); `server.py` `AdminLoginRequest` → `AdminCookieRequest` (`{php_sessid}`), `/admin/login` y `/admin/rotar` intercambiables, `_relogin_silent()` recarga+revalida la cookie del keyring en vez del login programático inviable (código muerto en dos capas), `session_alive` añadido a `/health` y `/admin/status`; `docs/rotacion-credenciales.md` actualizado; 3 tests nuevos.
- **Calidad**: 40 tests pasando, ruff limpio. Detalle en `PlanesAprobados.md` (Fases 0 y 1) y `anotaciones.md`. Commits: `1dcecc6`.
- **Pendiente al cierre**: correr keepalive con `--coords-lista`; registrar `keepalive_interval_seconds` final en `PlanesAprobados.md`; Fase 2 (keepalive) bloqueada hasta cerrar la investigación; Fases 3 (diálogo cookie GUI), 4 (tests), 5 (docs).

### 2026-08-28 — Sesión (mañana) — Retomar contexto + planificar sesión WinForce robusta
- [Inicio] Repo al día con `origin/main` (`7bc6550`), GitHub CLI conectado, Python 3.14.7
  cumple el requisito de `pyproject.toml`. Baseline: 37 tests pasando, ruff limpio.
- [Docs] Rotación de resúmenes ejecutada: `resumenes/2026-08-26.md` y `resumenes/2026-08-27.md`
  creados como snapshots completos; entradas condensadas agregadas a este archivo;
  `ResumenDelDia.md` reiniciado.
- [Hallazgo] Código muerto en el proxy: `_relogin_silent()`, `login_winforce()` y
  `/admin/login` siguen llamando a `client.login()`, que es inviable por 2FA — aparentan
  un mecanismo de recuperación que no existe.
- [Aclarado] Modelo real de la cookie: los 20 agentes LAN nunca tocan `PHPSESSID` (solo
  `X-Proxy-Token`); solo la PC del proxy necesita la cookie, puesta a mano con
  `rotate_creds.py`.
- [Problema real] El proxy se cae solo: WinForce cierra la sesión tras ~3 min de
  inactividad y no hay keepalive.
- [Plan aprobado] "Sesión WinForce robusta" (`PlanesAprobados.md`): Fase 0 medir vida de
  sesión, Fase 1 limpiar login muerto del proxy, Fase 2 keepalive, Fase 3 diálogo
  `⚙️ Configurar Sesión` en la GUI, Fase 4 tests, Fase 5 docs.
- [Pendiente] Ejecutar Fase 0 (requiere login manual + 2FA del usuario) e implementar
  Fases 1–5. Snapshot: `resumenes/2026-08-28.md`.
- Commits: `fc81da8`.

### 2026-08-27 — Sesión (primera prueba real end-to-end del core)
- [Confirmado] **Login programático inviable**: `acceso.php` acepta credenciales pero
  responde `"Redireccionar"` (al 2FA de Microsoft) y `operador.php` devuelve HTML →
  `ERR_LOGIN_SESSION`. El "recordar dispositivo" del 2FA es **por navegador, no por
  cuenta**. Valida definitivamente la arquitectura Proxy Local + cookie manual.
- [Bug real 1 — corregido] `coordenada.php` antepone un **BOM UTF-8** al JSON;
  `requests.json()` fallaba y `_json()` lo ocultaba. Fix: reintento `json.loads(texto[1:])`
  + test `test_cobertura_si_con_bom` (nueva clase `FakeResponseConBOM`).
- [Bug real 2 — corregido] Score **doble-encodificado** (2 `json.loads`, documentado desde
  Fase 0 pero nunca implementado — solo hacía uno). Fix: `_parsear_score` decodifica
  tolerante a profundidad + test `test_score_parsea_reporte_doble_encodificado`.
- [Verificado con datos reales] Flujo completo: cookie (login manual+2FA) → cobertura
  (SI, HORIZONTAL, celda 8764) → score (423, MUY ALTO). **37 tests, ruff limpio.**
- [Decisión] **Geodata del score = opción C (payload mínimo)**: funciona enviando solo
  coordenadas + documento, sin replicar la geoapi de Equifax.
- [Nuevo] `tools/probar_con_cookie.py` (herramienta de diagnóstico contra el servidor real,
  con `_diagnosticar_score` para inspeccionar la profundidad del encoding).
- [Seguridad] `.gitignore` no cubría `config.yaml` / `proxy_token.txt` / `admin_key.txt`
  del proxy — corregido antes de que se generen en la PC del proxy.
- [Entorno] En una máquina con Python 3.12.2 `pip install -e .` falla (pyproject exige
  ≥3.14); workaround `PYTHONPATH=.`. Snapshot: `resumenes/2026-08-27.md`.
- Commits: `c72188c`, `7bc6550`.

### 2026-08-26 — Sesión (setup máquina nueva + sincronización de documentación)
- [Entorno] Repo clonado en máquina nueva; `git user.name=AngelSanchezDev`. Acceso de
  escritura resuelto: `AngelSanchezDev` se agregó como colaborador con permiso de escritura
  en `sys-connectsolutionsjs/JSConnect-Win-Coverage` (antes daba 403).
- [Auditoría] Detectado desfase doc↔código: `AGENTS.md` (en disco como `Claude.md`) daba
  por pendientes las FASES 1–5 del proxy, pero ya estaban implementadas en commits
  posteriores del 2026-08-25 (`877689f`, `801ce05`, `f63660b`, `7cf7ea1`).
- [Corregido] `Claude.md` → `AGENTS.md` en disco (coincide con el tracked de git). Tareas
  1–6 y 11 marcadas `[COMPLETADO]` con evidencia file:line. Añadidas la regla de
  auto-actualización de docs (3 momentos) y la regla de rotación de resúmenes.
- [Docs] Creado `resumenes/2026-08-25.md` (snapshot faltante); `HistorialResumenes.md` y
  `PlanesAprobados.md` sincronizados con el estado real.
- [Verificado] 35 tests pasando, ruff limpio. Snapshot: `resumenes/2026-08-26.md`.

### 2026-08-25 — Sesión (tarde + noche)
- [Hallazgo crítico] Login WinForce redirige a 2FA Microsoft → inviable simular 4-5
  máquinas concurrentes con la misma cuenta.
- [Decisión arquitectónica] **Proxy Local (Opción B) APROBADA**: 20 agentes LAN → 1
  proxy (PC oficina) → 1-2 sesiones WinForce desde una sola IP. Stack: FastAPI +
  uvicorn, token compartido + IP LAN, admin key separada, winsw service, config.yaml
  gitignored.
- [Avance] FASE 0 Documentación completada: `docs/` (5 archivos), `Escalabilidad.md`,
  `anotaciones.md`, `resumenes/2026-08-19.md`.
- [Avance] FASES 1–5 del Proxy implementadas: `validator_app/proxy/` completo
  (server.py con 7 rutas, config.py, client.py, rotate_creds.py, winsw.xml,
  install/uninstall .bat), `auto_relogin_if_needed()` + persistencia de cookies en
  `core/api.py`, GUI con menú "⚙️ Configuración" y diálogo de proxy conectado a keyring.
- [Avance] Sistema de códigos de error: excepciones tipadas con `code` + diccionario
  `ERROR_CODES` (32 códigos) en `api.py`.
- [Verificado] 35 tests pasando, ruff limpio.
- [Nota] El cierre de esta sesión en `AGENTS.md` quedó desactualizado (decía "listo
  para FASE 1 Proxy Implementation" pese a que ya se implementó todo el mismo día);
  corregido en la sesión 2026-08-26. Ver `resumenes/2026-08-25.md` para el detalle
  completo.

### 2026-08-19 — Sesión (tarde)
- [Entorno] Nueva máquina: clonado el repo en
  `C:\Users\Connect Solutions 10\Documents\JS-REPOS\JSConnect-Win-Coverage`.
- [Entorno] Python 3.14.7 instalado (winget) + agregado al PATH del usuario.
- [Entorno] Dependencias instaladas (prod + dev) y Playwright Chromium descargado.
- [Entorno] `pyproject.toml`: añadido `[project]` + `[tool.setuptools.packages.find]`
  (solo `validator_app*`) para permitir `pip install -e .`; el paquete se instala
  en modo editable.
- [Git] Configurado user.name=AngelSanchezDev / user.email=sistemasconnectsolutionsjs@gmail.com.
- [Verificación] 25 tests pasando y ruff limpio en la máquina nueva.
- [Seguridad] Escaneo del proyecto y del historial de git por credenciales: NO se
  encontraron secretos (ni en código ni en commits); solo variable de runtime en
  api.py. Confirmado que `private_key.pem` y `tools/js/` nunca estuvieron en el repo.
- [Decisión] `tools/captura.json` y `tools/captura_inicio.png` NO son necesarios de
  transferir (info ya replicada en código; el primero además contiene datos de
  clientes).
- [Plan] Aprobada y registrada la **Fase 2 — Gestión visual de activación** en
  PlanesAprobados.md: `GeneradorActividad.exe` portable (PyInstaller onefile) para
  gerente/sistemas, con `private_key.pem` junto al .exe; flujo huella -> código por
  chat; se implementa DESPUÉS de la prueba de concurrencia.
- [Avance] Fase 1.5 **Paso 1 implementado**: creado `tools/probar_concurrencia.py`
  con el diseño aprobado (login->cobertura->score en N ciclos con log TSV).
  Ruff limpio, import OK, 25 tests pasando. Pendiente solo de ejecutarse en 4-5
  máquinas (Paso 2).
- [Herramienta] Creado el proyecto independiente **Captura de API** (Playwright) en
  `C:\Users\Connect Solutions 10\Documents\JS-REPOS\Captura de API` con `git init`,
  propio `captura.py` + `test_captura_guard.py` (adaptado: sys.path a la raíz y
  guarda de instancia única ahora busca `captura.py`), requirements/pyproject/
  .gitignore y los 6 MD propios (AGENTS, PlanesAprobados, ResumenDelDia, TestingLog,
  README, SkillsPropuestas). Verificado: 4 tests + ruff limpio.
- [Docs] `AGENTS.md` raíz: regla explícita de automantenimiento, `SkillsPropuestas.md`
  registrado en el mapa de conocimiento, sección "Proyectos relacionados" con la
  herramienta Captura de API, y historial de la sesión.
- [Docs] Creado `SkillsPropuestas.md` (cola/historial de skills) en el repo raíz.
- [Error→Solución] `pip`/`python` no reconocidos: Python no estaba instalado
  (solo stub de Microsoft Store). → Instalar Python 3.14.7 con winget y añadir al
  PATH de usuario.
- [Error→Solución] `pip install -e .` fallaba con "Multiple top-level packages
  discovered in a flat-layout". → Añadir `[project]` + `[tool.setuptools.packages.find]`
  (include `validator_app*`) en `pyproject.toml`.
- [Error→Solución] `tests/test_captura_guard.py` no encontraba `playwright` al
  importar captura.py. → Instalar playwright y su navegador (`python -m playwright
  install chromium`).
- [Error→Solución] `W292` (sin newline al final) en `probar_concurrencia.py`.
  → `ruff check . --fix`.
- [Pospuesto] **PRUEBA DE CONCURRENCIA** (Fase 1.5, Paso 2) pospuesta para OTRO DÍA:
  la herramienta ya está lista; solo falta ejecutarla en 4-5 máquinas.

### 2026-08-19 — Sesión (mañana)
- [Push] Primer commit del proyecto subido a GitHub (commit `e837681`, rama `main`)
  en https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage (32 archivos).
- [Contexto] Revisión de los .md de conocimiento (AGENTS.md, PlanesAprobados.md,
  TestingLog.md, README.md) para retomar dónde se quedó la sesión anterior.
- [Reglas] Definidas las reglas de trabajo del proyecto y reflejadas en `AGENTS.md`:
  - `ResumenDelDia.md` = historial del día (ese archivo), se actualiza a medida
    que se trabaja y sirve de base para el resumen de cierre de sesión.
  - `PlanesAprobados.md` = COLA de trabajo (no historial): lo implementado se saca
    de ahí.
  - `README.md` se actualiza con avances cuando el plan lo amerita (seguridad,
    funciones nuevas, etc.).
  - Al terminar la sesión se actualiza `AGENTS.md` con el resumen del día; luego se
    pregunta al usuario si quiere ver el resumen del día desde ese archivo.
- [Docs] Creado `ResumenDelDia.md` y actualizados `AGENTS.md` y `PlanesAprobados.md`
  con las reglas y el estado de la cola.
- [Git] Commit + push de los cambios de la mañana a GitHub (rama `main`).
- [Pospuesto] Prueba de concurrencia (Fase 1.5, Paso 1 — `tools/probar_concurrencia.py`)
  se pospone; queda agendado para retomarse en cuanto se vuelva (probablemente hoy).
