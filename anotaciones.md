# Anotaciones Técnicas - Glosario del Proyecto

> **Para futuros programadores**: Términos, conceptos y decisiones que no son obvios al leer el código.
> Si no entiendes algo, busca aquí. Si no está, agrégalo.

---

## A

### Activación RSA offline y consola del owner
Cada agente muestra una huella `XXXX-XXXX-XXXX-XXXX`. La consola separada
`generator/owner_app.py` firma esa huella con `private_key.pem` y devuelve un
código Base64; el agente lo verifica con la llave pública embebida en
`validator_app/activation/signer.py`.
- La llave **pública** puede estar en Git y en todos los agentes.
- La llave **privada** nunca se sube, nunca entra al `.exe` del agente y se
  transfiere a la PC owner por un canal privado con ACL NTFS restringida.
- En desarrollo vive en `generator/private_key.pem`; empaquetada, la consola
  owner la busca como `private_key.pem` junto a `JSConnect-Win-Owner.exe`.
- El código solo sirve para la huella firmada. La GUI ofrece **Copiar huella** y
  **Pegar código** para evitar truncar la cadena.
- **Desde el agente**: menú ⚙ Configuración → **Activación / Huella de la PC** abre el
  diálogo en cualquier momento (estado ACTIVADA/PENDIENTE, huella, pegar código y
  reactivar). Estado guardado en `%APPDATA%\JSConnectWinCoverage\activacion.dat`
  (borrarlo = "resetear" la activación de esa PC; el owner puede volver a firmar).
- **Consola owner** (`JSConnect-Win-Owner.exe`): además de firmar códigos muestra el
  estado del servicio/proxy, abre la renovación de WinForce y tiene el botón
  **Reiniciar servicio** (ver "Reiniciar servicio" abajo). En el `.exe` empaquetado no
  hay `config.yaml`: consulta `http://127.0.0.1:8080/health` (puerto por defecto).

### allowed_networks (whitelist de IP del proxy)
Lista de redes CIDR en `validator_app/proxy/config.yaml`. `/api/*` solo responde si la
**IP de origen que ve el proxy** está en la lista **y** llega `X-Proxy-Token`.
`/admin/*` exige además `X-Admin-Key`; `/health` es público (solo estado).
- Por defecto: `192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, `100.64.0.0/10`
  (Tailscale). **Loopback** (127.0.0.1 / ::1) siempre se permite.
- Error `IP no permitida: <ip>` (HTTP 403): esa `<ip>` es la que ve el proxy. Si es
  legítima, añadir su CIDR y reiniciar el servicio.
- **No se agregan las IP públicas del router** (p. ej. `162.120.185.241`): en la LAN
  el proxy ve la IP privada; la pública es la salida NAT que solo ven
  WinForce/Equifax. Ver "NAT / IP pública" y `docs/arquitectura.md`.

### API Interna (WinForce)
El sistema del ISP (`appwinforce.win.pe`) expone una API JSON interna en `/controllers/*.php` que el navegador usa vía AJAX. **No es pública documentada**, pero no requiere scraping: replicamos las llamadas HTTP directas.
- Endpoints: `acceso.php` (login), `coordenada.php` (cobertura), `cliente.php` (score), `operador.php` (verificar sesión), `document.php` (tipos doc), `newsearch.php` (crear lead)

### Auto-relogin Silencioso
Mecanismo en `ValidatorAPI` (proxy y standalone) que detecta sesión expirada o >120s sin uso → hace login automático en background → reintenta la petición original. El agente/cliente no ve error.
- **Ojo (Etapa R, 2026-09-09)**: en el proxy, `auto_relogin_if_needed()` ya NO refresca `_last_activity` — solo lo hace una llamada real y exitosa a WinForce. Antes lo refrescaba en toda petición (incluso las fallidas), y con 20 agentes reintentando contra una sesión muerta el keepalive nunca pinchaba → nadie se enteraba de la muerte.

### Aviso de sesión muerta (Etapa R, 3 capas)
Cuando el proxy confirma que la sesión WinForce murió (`_marcar_sesion_muerta()`), avisa por tres vías independientes, cada una degrada sola:
1. **HTTP 503 al agente** — ver "Sesión caducada (HTTP 503)".
2. **Evento de Windows + tarea programada** — el proxy escribe un evento (origen `JSWinProxy`, ID **101** = caducó / **102** = renovada) en el Registro de Aplicación con la API Win32 **`ReportEventW`** (ctypes, `server._aviso_event_log`); `install_service.bat` registra la tarea `JSWinProxy-AvisoSesion` (`schtasks /sc ONEVENT`) que le saca un `msg *` al owner en su escritorio. Es la vía nativa para que un servicio **LocalSystem** (sesión 0, sin escritorio) alcance a un humano.
   - **Lección (2026-10-02)**: antes se usaba `eventcreate.exe`, y **nunca funcionó en una instalación limpia**: `eventcreate` solo escribe en orígenes creados por él mismo (valor `CustomSource=1` en el registro), y `install_service.bat` registra `JSWinProxy` con `New-EventLog` (.NET). Respondía *"El parámetro de origen se usa para identificar solo las aplicaciones/scripts"* incluso como LocalSystem, y como se llamaba con `check=False` el error se perdía. `ReportEventW` acepta cualquier origen registrado (y, si no lo está, igual escribe el ID, que es lo que filtra la tarea).
3. **Toast de la extensión de Chrome** — `background.js` dispara `chrome.notifications` solo en la transición viva↔muerta (estado previo en `chrome.storage.session`), no cada sondeo.
4. **Webhook opcional** — `config.alert_webhook_url` (vacío = desactivado): POST `{"text": ...}`, forma que aceptan Teams/Slack/Discord. Para owner remoto o varias oficinas.

---

## B

### Bitácora de eventos de sesión (`logs/sesion_eventos.jsonl`, 2026-09-29)
Registro persistente (sobrevive reinicios del proceso) de cada cambio de estado
de la sesión WinForce del proxy, para diagnosticar "¿por qué se cerró la
sesión?" sin adivinar. Escrito por `_registrar_evento_sesion()` en
`validator_app/proxy/server.py`, `logs/sesion_eventos.jsonl` (una línea JSON
por evento, junto a `logs/winsw.*.log`).
- Campos: `ts`, `evento` (`renovada` / `muerta` / `falso_positivo_evitado`),
  `origen` (extensión, `admin_rotar`, `admin_login`, `/health`, `keepalive`,
  arranque), `cookie_id` (`sha256(PHPSESSID)[:8]` — identifica si cambió la
  cookie sin guardar el secreto), `edad_cookie_s` (segundos desde el último
  `renovada` con el mismo `cookie_id`, recalculado releyendo la bitácora — no
  un contador en memoria), `detalle` (el mensaje de `LoginError`, recortado).
- Best-effort: un fallo de disco al escribir nunca propaga (`contextlib.suppress`).
- Se lee con `Get-Content logs\sesion_eventos.jsonl -Tail 20` o vía
  `/admin/status` (campo `sesion_eventos`, últimos 10). Guía de lectura por
  patrón en `docs/rotacion-credenciales.md` → "¿Por qué se cerró la sesión?".
- Ver también "Reconfirmación antes de declarar sesión muerta" (abajo) y
  "Dos límites de sesión" (sección M).

### Reconfirmación antes de declarar sesión muerta (`_confirmar_muerte`, 2026-09-29)
Una sola respuesta fallida de `validar_cookie_sesion()` (timeout, error
puntual de WinForce) ya no basta para marcar `_session_dead_since`. Falso
positivo real que motivó el fix: 2026-09-29, `/health` recibió un
`ReadTimeout` de 30s y marcó "MUERTA" una sesión que, tras reiniciar el
servicio, resultó seguir viva (la cookie del keyring se validó sin problema).
- `_confirmar_muerte(php_sessid)` espera `SESSION_CONFIRM_DELAY_SECONDS` (3s
  en producción, 0 en tests vía fixture autouse) y reintenta una vez. Solo si
  el segundo intento **también** da `LoginError` se declara "MUERTA"; si pasa,
  "VIVA" (se anota `falso_positivo_evitado` en la bitácora); si da otro error
  (red/WinForce caído), "INDETERMINADO" — no se marca ni se cachea, igual que
  ya hacía el proxy ante un fallo de red en el primer intento.
- Aplicado en los 4 sitios que antes marcaban muerte con un solo chequeo:
  `_is_session_alive` (`/health`, `/admin/status`), `_keepalive_registrar_fallo`,
  `_load_session_cookies` (arranque) y `_relogin_silent`.

---

## C

### Cobertura (Validación de)
Consulta a `GET /controllers/coordenada.php?accion=validar_cobertura&data[latitud]=...&data[longitud]=...`.
Respuesta: `{"response":"success","cobertura":"SI|NO","tipo":"HORIZONTAL|VERTICAL|...","id_celda":"9754","comment":"..."}`.
- `cobertura: "SI"` → hay servicio disponible
- `tipo` → tecnología (HORIZONTAL = fibra/radio, VERTICAL = satelital, etc.)
- `id_celda` → identificador interno de la celda de cobertura

### Configuración (config.yaml / config.yaml.example)
- `config.yaml` = **archivo real con secretos** (gitignored, solo en PC proxy)
- `config.yaml.example` = **plantilla en repo** con placeholders y comentarios
- Leída por `config.py` via Pydantic Settings (precedencia: env vars > yaml > defaults)

### Credenciales WinForce
Usuario/contraseña del sistema del ISP. **Rotan cada 1-2 meses** (desactivan cuenta anterior + entregan nuevas al responsable).
- **NUNCA** en repo, **NUNCA** en agentes
- El proxy no guarda usuario/contraseña: conserva solo la `PHPSESSID` en
  `JSWinProxy`/`credentials_cookies` bajo LocalSystem
- Renovación: extensión de Chrome como vía principal; consola owner/login
  asistido y `--manual` como fallback

---

## D

### DNS Interno (Tailnet)
En Tailscale: nombre `proxy.oficina.local` → IP Tailscale del proxy (ej. `100.64.12.34`).
Idea de auto-discovery (hoy **no funciona**: `/admin/config` exige `X-Admin-Key` y solo responde desde la propia PC del proxy, así que un agente no puede usarlo para auto-configurarse; ver `docs/escalabilidad-remota.md`).

---

## E

### Equifax (API Externa Crediticia)
API de bureo de crédito (`api.latam.equifax.com`). WinForce la usa para score.
- OAuth: `client_credentials` (credenciales embebidas en JS del sitio WinForce)
- Endpoints geodata: `coordinates`, `coordinates-ref`, `intersectz`, `capas`
- Reporte SOAP: respuesta `score_cliente` viene doble-encodificada (JSON string dentro de JSON)
- **Proxy NO replica geocoding Equifax**; envía campos geodata vacíos en `score_cliente`

### Extensión de renovación (`validator_app/proxy/extension/`)
Extensión de Chrome (MV3) que renueva la sesión del proxy **desde el navegador
cotidiano del owner**, ya logueado en WinForce. Vía principal de renovación
(el login asistido y `--manual` quedan de fallback).
- **Por qué extensión y no CDP**: Chrome 136+ **bloquea `--remote-debugging-port`
  con el perfil por defecto** (anti-robo-de-cookies), así que Playwright no puede
  "entrar" al Chrome normal del owner.
- **`background.js`**: `chrome.action.onClicked` → `chrome.cookies.get({url:
  "https://appwinforce.win.pe", name: "PHPSESSID"})` (**`chrome.cookies` sí lee
  cookies HttpOnly**) → `POST http://127.0.0.1:<puerto>/local/renovar`.
  `chrome.alarms` cada 5 min → `GET /local/estado` → badge rojo `!` si la sesión
  murió.
- **Endpoints `/local/*`** (`server.py`): solo `127.0.0.1`, **sin admin key** (una
  petición local ya es de confianza; el proxy igual valida la cookie contra
  WinForce). `POST /local/renovar` reusa `set_session_cookie`; `GET /local/estado`
  reusa `get_status`.
- **Instalación**: `_instalar_extension.py` (lo llama `install_service.bat`)
  empaqueta un `.crx` firmado (`chrome --pack-extension`, `extension.pem` estable →
  id estable), escribe `updates.xml` local y la política
  `HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionSettings\<id>` = `force_installed`.
  Tras instalar hay que **reabrir Chrome** una vez.
- **Limitación (hallada 2026-09-18)**: Chrome solo aplica esa política en **PC
  gestionadas** (unidas a dominio o Azure AD). En Windows Home / WORKGROUP la ignora y
  la extensión no aparece. `install_service.bat` lo detecta, avisa sin detenerse y al
  final imprime la carga manual: `chrome://extensions` → Modo de desarrollador →
  **Cargar descomprimida** → `validator_app\proxy\.extension_build` (Chrome muestra
  un aviso por el modo desarrollador). Alternativa sin Chrome: el icono "Renovar
  sesion WinForce" del Escritorio. Ver "PC gestionada".

---

## F

### FastAPI
Framework web async para Python. Usado en `server.py` del proxy.
- Ventajas: concurrencia nativa (async/await), validación Pydantic automática, Swagger UI en `/docs`, inyección de dependencias (`Depends`)
- Corre con `uvicorn` (ASGI server)

---

## G

### Geodata (Distrito, Ubigeo, Código Postal, Segmentación)
Datos geográficos que WinForce **NO devuelve** en cobertura/score. El navegador los calcula llamando directo a Equifax OAuth.
- En `api.py:141-151` se envían 25 campos vacíos (`""`) en el payload `score_cliente`
- El servidor WinForce los rellena internamente o no son obligatorios para el score

### Gitignore (Qué NUNCA Subir)
```
config.yaml
proxy_token.txt
admin_key.txt
generator/private_key.pem
tools/captura.json
tools/js/
tools/captura_inicio.png
*.pyc
__pycache__/
.pytest_cache/
.ruff_cache/
dist/
build/
*.exe
```

---

## H

### Health Check (`GET /health`)
Endpoint público del proxy para verificar que está vivo y la sesión WinForce activa.
Respuesta: `{"status":"ok","version":"dev","session_age":45,"logged_in":true,"session_alive":true}`.
Hoy el proxy informa `dev`; el SHA embebido se usa en el ejecutable agente.

---

## I

### Instalador re-ejecutable (`install_service.bat`)
Cada uno de los 12 pasos comprueba si ya está hecho y lo salta ("ya estaba" vs "hecho
ahora"), así que se puede ejecutar varias veces sin romper nada; al final imprime un
resumen por paso. La ventana no se cierra sola (el script se relanza con `cmd /k`).
- Si ya hay tokens, el paso 5 pregunta **C**onservar (por defecto a los 20 s) o
  **R**egenerar (reutiliza el puerto y reinicia el servicio).
- **Trampa de CMD**: un `)` sin escapar dentro de un `echo` en un bloque `( ... )` cierra
  el bloque y aborta el script (así se cortó el paso 5). Escapar con `^)`; dentro de
  `set "VAR=..."` (entre comillas) NO se escapa. `tests/test_install_bat.py` lo vigila.
- El paso 7 (extensión) solo informa; nunca detiene el instalador.

---

## K

### Keyring (Windows Credential Manager)
Almacén cifrado del SO **por usuario**. Cada usuario Windows tiene el suyo —
esto es justo lo que complica la Etapa 0.5 (ver abajo).
- **Agentes**: `JSWinClient`/`proxy_url` + `JSWinClient`/`proxy_token`
- **Proxy**: `JSWinProxy`/`credentials_cookies` (solo la `PHPSESSID` de sesión;
  ya no guarda usuario/contraseña — el login programático es código muerto
  eliminado en `1dcecc6`)
- **Standalone (GUI)**: `JSWinCoverage`/`session_cookie` (una `PHPSESSID` pegada
  a mano, ver `session_config.py`)
- **Activación**: `JSWinCoverage`/`activation_code` (por huella HW)

**LocalSystem vs owner (Etapa 0.5, RESUELTO 2026-09-11)**: el servicio de
Windows corre como **LocalSystem**, que tiene su propio almacén, distinto del
owner. `/local/renovar` y `/admin/rotar` (`set_session_cookie()`) escriben en
el keyring **del proceso del proxy** — correcto bajo LocalSystem. Antes,
`rotate_creds.py` (icono del Escritorio / `--manual`) escribía **directo** al
keyring **del owner** (`save_session_to_keyring()`) — el servicio LocalSystem
nunca vería esa cookie. Arreglado: `rotate_creds.push_session_cookie()` ya no
toca ningún keyring — empuja la cookie por HTTP, primero `/local/renovar`
(proceso vivo en `127.0.0.1`, sin admin key); si no conecta, cae a
`/admin/rotar` con `X-Admin-Key`. Si `/local/renovar` sí conecta pero rechaza
la cookie (401), **no** reintenta por `/admin/rotar` — sería la misma cookie
mala. El keyring del proceso del proxy queda como única fuente de verdad. De
paso se arregló un bug latente: `_verificar_proxy()` usaba `config.proxy_url`
(construido con `proxy_host`, que en producción es `0.0.0.0` — un bind de
escucha, no un destino válido) → ahora usa `config.proxy_local_url`
(`http://127.0.0.1:<puerto>`, la nueva property de `config.py`).

---

## L

### Loopback (127.0.0.1 / ::1)
La propia PC. El proxy siempre permite el tráfico loopback aunque no esté en
`allowed_networks` (`server._ip_in_allowed_networks`): así la PC del proxy puede usarse
como agente con `http://localhost:8080`. No abre nada: `X-Proxy-Token` sigue siendo
obligatorio. Bug histórico (2026-09-18): sin esto `localhost` daba 403 "IP no permitida".
**Ojo, no confundir con el bug de 2026-09-25**: eso era `localhost` en la MISMA PC
del proxy; si el agente corre en OTRA PC, `localhost` ahí apunta al agente mismo
(nada escuchando) y da `WinError 10061`, no 403 — hace falta la IP de LAN real del
proxy (la consola owner la detecta sola, ver "URL para los agentes" más abajo).

### Login asistido (`validator_app/proxy/login_asistido.py`)
Forma de renovar la sesión WinForce del proxy sin que el owner toque F12 ni copie
nada. Lo lanza `rotate_creds.py` (sin argumentos) y, en la PC del proxy, el icono
"Renovar sesion WinForce" del Escritorio (`pythonw.exe`, sin consola).
- **Cómo**: Playwright abre el **Google Chrome instalado** (`channel="chrome"`,
  con `ignore_default_args=["--enable-automation"]` +
  `--disable-blink-features=AutomationControlled` para que el gestor de
  contraseñas de Chrome autocomplete con normalidad) usando
  `launch_persistent_context` con perfil dedicado; si no hay Chrome, cae al
  Chromium empaquetado. El owner inicia sesión (una vez: sign-in de Google o
  "Guardar contraseña" → autofill en adelante), y el script sondea
  `context.cookies()` buscando la `PHPSESSID` de `appwinforce.win.pe`. Al
  encontrarla la valida con `core.api.validar_cookie_sesion()` y la guarda en
  keyring.
- **Por qué `context.cookies()` y no `document.cookie`**: la `PHPSESSID` es
  **HttpOnly** → invisible para JS de página; la API del contexto de Playwright sí
  la ve.
- **Perfil persistente** (`.browser_profile/`, gitignored): mantiene la sesión de
  Microsoft en disco → dentro de la misma jornada el SSO se salta el 2FA en
  renovaciones sucesivas. A la jornada siguiente vuelve a pedir 2FA (política de
  Microsoft). `--fresh` borra el perfil.
- **Fallback**: `rotate_creds --manual` (pegar la cookie a mano) para cuando
  Playwright/Chromium no está disponible. No arrastra Playwright.
- **Resultado** al owner: barra verde en la ventana + `tkinter.messagebox`
  "✓ Sesión renovada". Nada de stdout (corre bajo `pythonw`).

---

## M

### Microsoft 2FA (Login WinForce)
**Crítico**: Login en `appwinforce.win.pe` redirige a `login.microsoftonline.com` para segunda autenticación (2FA) con la misma cuenta.
- **Imposible automatizar** sin replicar todo el flujo OAuth2/SAML de Microsoft
- **Consecuencia**: Prueba de concurrencia 4-5 máquinas **inviable** (requiere 2FA manual cada una)
- **Solución**: Proxy local (1 sesión) + rotación manual via RDP (owner hace login en navegador + copia cookie)

### Reuse de PHPSESSID en login + SSO silencioso (observado 2026-09-04)
- **SSO silencioso de Azure AD**: si el navegador ya tiene sesión activa en
  `login.microsoftonline.com` (login previo con "mantener sesión iniciada"),
  el redirect de 2FA se completa solo, sin pedir credenciales ni segundo
  factor de nuevo. No es que WinForce "salte" el 2FA — es Microsoft
  reconociendo al usuario.
- **`acceso.php` no regenera el PHPSESSID al loguear**: al recargar sin sesión
  válida, el servidor emite una PHPSESSID anónima nueva y redirige al login;
  tras completar el login (incluso vía SSO), la cookie autenticada resultante
  es la **misma** que esa PHPSESSID anónima — no se llama a
  `session_regenerate_id()`. Relevante para quien rote/inyecte cookies
  manualmente: la cookie "vieja" que ves justo antes de loguear puede terminar
  siendo la cookie autenticada real.
- **Trampa práctica al copiar la cookie (observado 2026-09-04)**: si reusas
  una pestaña/panel de DevTools que ya tenías abierto de una sesión anterior,
  el panel Application → Cookies a veces no se refresca solo y muestra el
  valor viejo cacheado. Dos intentos de `tools/medir_keepalive.py` fallaron
  en el primer ping (HTML en vez de JSON) pese a "login fresco" — el tercer
  intento, con pestaña nueva y el panel de cookies reabierto, funcionó al
  toque. Antes de copiar `PHPSESSID`: pestaña nueva + reabrir DevTools.
- **Síntoma frontend de sesión muerta**: al expirar la `PHPSESSID`, tablas
  DataTables de la app (ej. `table_seguimiento`) muestran `Invalid JSON
  response` — el AJAX que las alimenta devuelve HTML (redirect a login) o un
  warning de PHP en vez de JSON limpio, mismo patrón que el bug de BOM UTF-8
  ya corregido en `coordenada.php` (`AGENTS.md`, "Bug real 1"), aquí en un
  endpoint distinto de WinForce. Es una señal visible en el navegador de que
  la sesión ya murió, útil para detectar el corte sin depender solo del log
  de `medir_sesion.py`.

### Dos límites de sesión: idle-timeout + tope absoluto (idle medido 2026-09-04, tope medido 2026-09-08)
> **CORRECCIÓN 2026-10-07 — el "tope absoluto ≈ 9.5 h" es UNA medición, no un hecho.**
> La corrida v3 arrancó el sábado 2026-09-05 a las 21:08 (sesión con 70 s de edad) y
> murió a las 9 h 31 m, es decir hacia las 06:38 del domingo, en una cuenta que casi no
> se usaba. El dueño del proyecto señala que pudo ser **alguien iniciando sesión con la
> misma cuenta por la mañana** (eso invalida la `PHPSESSID` anterior; al volver a iniciar
> sesión todo vuelve a la normalidad). Con un solo dato **no se puede distinguir** un
> tope real de esa interrupción, ni confirmarlo ni descartarlo. Tampoco se resuelve con
> el patrón de ~10 min tras renovar visto el 2026-10-02 (593 y 603 s, mismo `cookie_id`;
> ver `actualizacion-windows-11/pendientes.md` §1). **Consecuencia práctica: ninguna** —
> el owner igual tiene que renovar la cookie (2FA: no hay re-login programático) y el
> keepalive sigue siendo necesario. Solo cambia que no hay que dar por hecho un límite
> de 9.5 h. Cómo averiguarlo: `docs/rotacion-credenciales.md` → "Cómo investigar una
> muerte de sesión". Lo de abajo se conserva como estaba, leído con esta corrección.
>
> **ESTADO 2026-09-08 — investigación CERRADA (ver la corrección de arriba).** El punto 2 de abajo ("tope
> absoluto a ~40 min") queda **descartado**: ese 404 de v1 era un transitorio,
> no la sesión muriendo. Pero la corrida final de v3 (37 pings cada 15 min a lo
> largo de 9 h) **sí midió un tope absoluto real**: la sesión vivió confirmada
> hasta ≈ 9 h 16 m y murió limpia a ≈ 9 h 31 m desde el login, independiente de
> la actividad. Resumen del modelo real: **idle-timeout ~20 min (lo evita el
> keepalive) + tope absoluto ≈ 9.5 h (NO lo evita el keepalive)**. El texto
> original de abajo se conserva como histórico; leerlo con esta corrección
> delante.

**Contexto para quien diseñe/ajuste el keepalive de la Fase 2**: la sesión de
WinForce no muere por un único timeout — hay evidencia de **dos límites
independientes**, un patrón común en apps empresariales:

1. **Idle-timeout (~20 min sin actividad)**. Medido en Fase 0
   (`tools/medir_sesion.py`, solo pings de lectura `operador.php`): la sesión
   murió entre 1155s y 1350s de inactividad (`medir_sesion.log`). **Un ping
   de interacción real SÍ lo evita** — ver punto 2.
2. **¿Tope absoluto de sesión? (~40 min desde el login, hipótesis NO
   confirmada)**. Medido con `tools/medir_keepalive.py` v1 (pings reales de
   `validar_cobertura` cada 300s exactos, durante 45 min,
   `medir_keepalive.log`): la sesión sobrevivió pings exitosos hasta los
   2100s (35 min, muy por encima del idle-timeout de arriba — confirma que
   el ping real SÍ resetea ese reloj) pero el ping de los 2400s (40 min)
   falló. **Corrección importante**: el error real de esa falla, revisado
   despues en el log, fue un **HTTP 404 genérico** ("Not Found", estilo
   Apache, charset iso-8859-1) — **no** el patrón de "HTML de login"
   (HTTP 200, charset UTF-8) que sí vimos en otros casos de sesión muerta.
   Un 404 así es compatible con un tope real de sesión, pero también con un
   hipo transitorio de red/servidor o un bloqueo anti-abuso puntual — con un
   solo dato no se puede distinguir. **No dar esto por confirmado** sin una
   segunda muerte con el mismo patrón.

**Implicación de diseño (actualizada 2026-09-08)**: un keepalive (Fase 2) evita
la muerte por inactividad — confirmado con 9 h de pings sin fallo. El **tope
absoluto ≈ 9.5 h desde el login ya es un hecho medido**, no una hipótesis: la
Fase 2 debe asumirlo. El keepalive no lo evita, así que la Fase 2 tiene que
**avisar al owner** cuando la sesión muera pese al keepalive (no solo reintentar
en silencio); el re-login programado es inviable por el 2FA, de modo que el owner
reinyecta la cookie **al inicio del turno** (hay ~1.5 h de margen sobre la
jornada de 8 h).

### Revisión del método (2026-09-05): por qué v1/v2 no permiten concluir
Al retomar la investigación se detectaron dos defectos de método que hacen
**inservibles** los datos de v1 y v2 (y con ellos la hipótesis anti-bot):

1. **No se medía la edad real de la sesión.** El cronómetro arrancaba con el
   script, no con el login. Como `acceso.php` **no regenera la `PHPSESSID`**
   (ver arriba) y el panel de DevTools puede mostrar una cookie cacheada, la
   sesión de v2 pudo llevar ya 10+ min viva al empezar: "murió a 1100s de
   test" podía ser ~1700s de sesión — normal, sin necesidad de bot.
2. **Cualquier error se tomaba como "sesión muerta" y cortaba la corrida.** El
   404/iso-8859-1 de v1 y el 200+HTML de v2 son fallos **distintos**;
   mezclarlos produjo el modelo contradictorio "idle-timeout + tope absoluto".

`tools/medir_keepalive.py` **v3** corrige ambos: `--login-hora`/`--edad-inicial`
obligatorios y columna `edad_sesion_s` en el log; cada fallo se clasifica
(`SESION_MUERTA` / `TRANSITORIO` / `OTRO`) y, antes de dar la sesión por
muerta, se **confirma** de forma independiente con
`core.api.validar_cookie_sesion()`. Un transitorio ya no corta la prueba.
La corrida se hace con el intervalo de producción (~900s), no con los
180-420s de laboratorio, para validar directamente el diseño de la Fase 2.
Coordenadas rotativas desde `tools/coords_prueba.txt` — **49 puntos** (10 que
dio el usuario + 39 generados con rejilla+jitter dentro de su polígono), todos
ubicaciones públicas de Lima, no domicilios de clientes.

**Resultado final de la corrida v3 (reporte recibido 2026-09-08):** arrancó
2026-09-05 21:08 con la sesión a 70s de edad, ping fijo cada 900s, 49 coords
rotativas. **37 pings consecutivos VIVA**; última confirmación a **33 370s
(≈ 9 h 16 m)** de edad de sesión. Murió **limpia** a **34 270s (≈ 9 h 31 m)**:
categoría `SESION_MUERTA`, patrón HTTP 200 + `text/html` (HTML de login),
**confirmado de forma independiente** por `core.api.validar_cookie_sesion()`.
Lecturas:
- **keepalive de 15 min funciona** — un ping real de `validar_cobertura` resetea
  el reloj de expiración; idle-timeout de Fase 0 **descartado** como causa de
  esta muerte;
- **detección anti-bot descartada** — 37 pings variados en 9 h, 0 fallos;
- **"tope a 40 min" descartado** — era el 404 ambiguo de v1;
- **sí existe un tope absoluto de sesión ≈ 9.5 h desde el login**, independiente
  de la actividad → la Fase 2 lo asume (avisar al owner + reinyección de cookie
  al inicio del turno).
Un dato limpio basta aquí (a diferencia del 404 ambiguo de v1): patrón de muerte
inequívoco, idle-timeout excluido por los pings activos, confirmación
independiente. Una 2ª corrida solo afinaría el número exacto. **Investigación
CERRADA.**

### Middleware Auth (Proxy)
En `server.py`: valida requests antes de llegar a endpoints.
- `/api/*` → `X-Proxy-Token` header + IP en `allowed_networks`
- `/admin/*` → `X-Admin-Key` header (solo owner)

---

## N

### NAT / IP pública del router
Los PC de la oficina salen a Internet por una o varias IP públicas del router (aquí
`162.120.185.241`, `38.253.147.12`, `72.14.201.203`). Son la **salida NAT**: solo las
ven servidores externos (WinForce, Equifax, páginas de "cuál es mi IP"). El tráfico
agente → proxy dentro de la LAN usa IPs privadas (192.168.x.x), que es lo que ve
`allowed_networks`. Por eso **no se agregan a la whitelist**: solo tendrían efecto con el
puerto 8080 expuesto a Internet, que está prohibido.

---

## P

### PC gestionada
PC unida a un dominio de Active Directory o a Azure AD, o inscrita en la gestión de
Chrome. Solo en ellas Chrome aplica la política `ExtensionSettings`/`force_installed`
desde un `file:///` que usa el instalador. Windows 10 Pro **no** basta por sí solo: debe
estar unido a un dominio/Azure AD. El instalador detecta `PartOfDomain` y
`AzureAdJoined`. En una PC no gestionada la extensión se carga a mano (ver "Extensión").

### Proxy Local (Reverse Proxy Interno)
Servidor intermedio en PC oficina que:
1. Recibe peticiones de agentes (LAN/VPN)
2. Valida token + IP
3. Reenvía a WinForce usando **SU propia sesión** (cookies en keyring)
4. Devuelve respuesta a agente
- Evita: una sesión concurrente por agente, rotación de credenciales máquina por máquina, bloqueo por IP
- Stack: FastAPI + uvicorn + winsw service
- Puerto: 8080 (configurable)

### Proxy Token (Token Compartido)
Secreto de 256-bit (64 chars hex) compartido entre proxy y **todos** los agentes.
- Generado auto en `install_service.bat` (`secrets.token_hex(32)`)
- Guardado en `config.yaml` (proxy) + keyring agentes (`JSWinClient`/`proxy_token`)
- **No es secreto crítico**: solo valida en LAN/VPN + IP binding. Si se filtra, atacante ya está en la red.

---

## R

### Reiniciar servicio (por qué hace falta)
El servicio `JSWinProxy` (Python + uvicorn) carga `server.py` y `config.yaml` **una sola
vez, al arrancar**. Cambiar código, `allowed_networks` o tokens no surte efecto hasta
reiniciarlo (caso real 2026-09-18: el arreglo de loopback siguió dando 403 porque el
servicio corría desde las 13:03). Formas: botón **Reiniciar servicio** de la consola
owner (PowerShell elevado con aviso UAC; códigos de salida 0 ok / 2 UAC cancelado / otro
fallo), o `Restart-Service JSWinProxy` en PowerShell como Administrador. La sesión
WinForce se conserva (la cookie vive en el keyring de LocalSystem, no en memoria).

### Rotación de Credenciales (Cada 1-2 Meses)
WinForce cambia el user/pass, pero el proxy solo recibe una sesión ya iniciada.
- **Actual**: owner inicia sesión en WinForce y la extensión de Chrome manda la
  `PHPSESSID` a `/local/renovar`; la consola owner/login asistido es fallback.
- **Remoto futuro**: owner vía VPN → `POST /admin/rotar` con `X-Admin-Key` y
  `php_sessid`, nunca usuario/contraseña.

### requirements-proxy.txt
Dependencias **solo del proxy** (NO van en .exe agentes):
```
-r requirements.txt
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.7
pydantic-settings>=2.3
# winsw se descarga binario, no pip
```
Separado de `requirements-dev.txt` para que .exe final sea ligero.

---

## S

### Score (Validación Crediticia)
Consulta a `POST /controllers/cliente.php` con `accion=score_cliente` + muchos campos `data[...]`.
- Respuesta: `{"response":"success","data":"<JSON-string con reporte SOAP Equifax>"}`
- Parseo: `json.loads(data)` → busca recursivamente `ns3ResumenScoreRP3.Puntaje` (ej: 423), `NivelRiesgo` (ej: MUY ALTO), `ResumenDeuda.DeudaTotal`
- Payload incluye: `tipo_doc` (Catálogo 06 SUNAT: 1=DNI, 4=CE, 6=RUC — **distinto** de `tipo_doc_value`/`tipo_doc_text`, que sí usan la tabla interna 1=DNI/2=CE/3=RUC), documento, coordenadas, cobertura, ~19 campos geodata vacíos.
- `deuda_total` puede llegar como **int `0`** (no string) cuando no hay deuda → `_parsear_score` lo normaliza a str y `ScoreResponse` usa `coerce_numbers_to_str` (fix `3f63e8f`, hallado en la validación real de la Etapa B).
- **Bug real, RUC (2026-09-29)**: un RUC sin el `tipo_doc` de SUNAT (se mandaba
  el mismo valor que `tipo_doc_value`, "3") fallaba con `HTTP 502: "Por favor,
  corregir los campos faltantes"` — WinForce no dice qué campo falta.
  Encontrado comparando, campo por campo, una captura real de `tools/captura.py`
  (RUC `10096548031`, score exitoso 575/ALTO) contra el payload del código.
  Dos diferencias: `tipo_doc` debía ser `6` (no `3`), y el campo de longitud
  se llama `logintud` en WinForce (typo real de ellos, no `longitud`). Con
  ambos corregidos y el resto del payload en blanco ("payload mínimo" sigue
  valiendo para RUC), la prueba en vivo devolvió el mismo score exacto que la
  captura del navegador (575/ALTO) — confirma que **no hace falta** llenar
  geodata real para RUC, solo esos dos campos. El valor de CE en la tabla
  SUNAT (`4`) es una hipótesis razonada (mismo catálogo), no confirmada: una
  prueba con CE `007187041` devolvió `success` sin puntaje tanto con
  `tipo_doc=2` como con `tipo_doc=4` — compatible con que ese documento de
  prueba simplemente no tenga historial en Equifax, no decide la hipótesis.

### Sesión caducada (HTTP 503, Etapa R)
Cuando el proxy ya sabe que su sesión con WinForce murió (`_session_dead_since` está puesto), `validar_cobertura`/`validar_score` lanzan `SesionCaducadaError` **antes de tocar WinForce** → el handler responde **HTTP 503** + `Retry-After: 120` + `{"detail": ..., "codigo": "ERR_SESION_CADUCADA", "owner_avisado": true}`.
- Es "servicio temporalmente no disponible", no un error del agente. Se resuelve solo cuando el owner renueva la cookie (extensión / `/admin/rotar`), que limpia `_session_dead_since`.
- **No se reintenta**: `ProxyClient` trata el 503 como terminal (`ProxySesionCaducadaError`), sin backoff. La GUI del agente muestra un aviso suave ("reintenta en 2-3 minutos"), no el diálogo rojo de error.
- Antes de la Etapa R el proxy llamaba a WinForce igual → recibía el HTML de login → HTTP 502 opaco, y no había forma de que el agente supiera que era la sesión.

### Standalone Mode (Modo Sin Proxy)
Si la app **no tiene config de proxy** en keyring → usa
`validator_app.core.api.ValidatorAPI` directo contra WinForce.
- **Solo para desarrollo/pruebas/owner** — NO producción (riesgo bloqueo 20 sesiones)
- El login programático es inviable por el 2FA → se configura pegando la cookie
  `PHPSESSID` en el diálogo **⚙ Configuración → Configurar Sesión (standalone)**.
  Se valida contra WinForce (`validar_cookie_sesion`) y se guarda en el keyring
  `JSWinCoverage`/`session_cookie`. `validator_app/gui/session_config.py`
  (`cliente_standalone()`) construye el `ValidatorAPI` con esa cookie inyectada.
- Cuando la cookie expira, `validar` falla con un error de WinForce y el usuario
  la re-pega (mismo diálogo). No hay re-login automático.

---

## T

### Tailscale (VPN Mesh)
VPN zero-config basada en WireGuard. Gratis hasta 100 devices.
- Instalación: `winget install Tailscale.Tailscale` → login cuenta empresa → auto-mesh
- IPs estables: `100.64.x.y` (CGNAT range)
- DNS interno: `proxy.oficina.local` configurable en admin console
- **Permite escalar a remotos sin cambios de código**

### Token (Ver Proxy Token)

---

## U

### UAC (Control de cuentas de usuario)
Aviso de Windows que pide permiso para ejecutar algo como Administrador. La consola
owner lo usa en **Reiniciar servicio** (`Start-Process ... -Verb RunAs`) para no tener
que abrirla como administrador ni escribir comandos. Si se cancela el aviso, el botón
lo informa sin fallar.

### "URL para los agentes" (consola owner)
Campo de solo lectura en el recuadro "Proxy y sesion WinForce" con
`http://<ip-de-LAN-detectada>:<puerto>`, listo para copiar y pegar en cada agente
(⚙ Configuración → Configurar Proxy). `generator/owner_app.py::detectar_ip_lan()`
la obtiene con un socket UDP conectado a `8.8.8.8:80` (no envía nada; `connect()`
en UDP solo fija la ruta) y lee `getsockname()[0]`; si no hay ruta por defecto,
respaldo con `socket.getaddrinfo(gethostname(), ...)`. Existe porque, con agente y
proxy en PC distintas, configurar `localhost` en el agente da `WinError 10061`
(ver nota en "Loopback" más arriba) — se agregó 2026-09-25 al primer despliegue
real multi-PC.

---

## V

### ValidatorAPI (Core)
Clase principal en `validator_app/core/api.py`:
- `login(usuario, password)` → crea sesión, verifica con `operador.php`
- `validar_cobertura(lat, lon)` → GET coordenada.php
- `validar_score(tipo, num, lat, lon, cobertura, geodata?)` → POST cliente.php + parseo SOAP
- `validar(lat, lon, tipo, num)` → flujo completo cobertura → score
- `auto_relogin_if_needed()` → llamado antes de cada request en proxy
- `get_session_cookies()` / `set_session_cookies()` → persistencia keyring

---

## W

### WinForce (Sistema del ISP)
Sistema de validación del proveedor de internet (`appwinforce.win.pe`).
- Login: formulario → redirect Microsoft 2FA → cookie `PHPSESSID`
- Cobertura: coordenadas → SI/NO + tipo + id_celda
- Score: documento + coordenadas → reporte Equifax SOAP (puntaje, riesgo, deuda)
- Límites: 2-3 sesiones concurrentes por cuenta, timeout 3 min, rotación credenciales 1-2 meses

### winsw (Windows Service Wrapper)
Herramienta que convierte cualquier exe en servicio Windows nativo.
- Config: `winsw.xml` (nombre, descripción, exe, args, logs)
- Comandos: `winsw.exe install | start | stop | uninstall | status`
- Logs stdout/stderr: `<repo>\logs\`. El Visor de Eventos solo recibe las
  alertas de sesión 101/102 creadas por el proxy.

### Windows 11 — diferencias que afectan al proyecto (2026-10-02)
Detectadas al instalar la PC oficina en Windows 11 Pro 25H2. Detalle en `actualizacion-windows-11/`.
- **Red Pública por defecto**: las redes nuevas quedan como *Públicas*; una regla de firewall `Domain,Private` no aplica ahí (el agente ve **timeout**). El instalador usa `-Profile Any` + `-RemoteAddress` con los rangos LAN/Tailscale. Ver la categoría con `Get-NetConnectionProfile`.
- **`wmic` eliminado** (24H2+): la huella (`fingerprint.py`) lee lo mismo por CIM (`Win32_Processor.ProcessorId`, `Win32_Volume.SerialNumber`) cuando `wmic` no existe; `huellas_compatibles()` acepta también la huella vieja calculada sin `wmic`. **Reemplazado el 2026-10-07:** la huella pasó a MachineGuid + CPU del registro (sin `wmic`/PowerShell/MAC/volumen); lo anterior quedó en `huellas_legacy()` solo para la transición. **No se borra salvo petición expresa del usuario**: el actualizador salta directo al último Release y un agente que se salte la transición perdería la activación.
- **Windows Terminal como consola por defecto**: cada `subprocess` lanzado desde una app con ventana abre una Terminal visible que roba el foco → usar `creationflags=subprocess.CREATE_NO_WINDOW`.
- **Historial del portapapeles (Win+V) y nube**: guardan lo copiado aunque la app lo borre. Para secretos: formatos `ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory=0`, `CanUploadToCloudClipboard=0` (`owner_app.copiar_sin_historial`). El dueño del portapapeles NO debe ser una ventana de Tk: Tk lo vacía al cerrarse.
- **Smart App Control**: bloquea `.exe` sin firma, sin la opción "ejecutar de todas formas" de SmartScreen; queda en el Visor de Eventos → `Microsoft-Windows-CodeIntegrity/Operational` (IDs 3033/3077). Python sí está firmado, así que correr desde el código funciona. Solución de fondo: firmar los `.exe` (`actualizacion-windows-11/pendientes.md`).
- **No es de Windows 11 pero salió ahí**: `config.yaml` tiene ACL SYSTEM+Administradores → cualquier proceso **no elevado** que llame `get_config()` recibe `PermissionError`; para `/local/*` usar `config.proxy_local_url_seguro()`.

---

## Siglas

| Sigla | Significado |
|-------|-------------|
| **CE** | Carnet de Extranjería (9 chars alfanumérico) |
| **DNI** | Documento Nacional de Identidad (8 dígitos) |
| **RUC** | Registro Único de Contribuyentes (11 dígitos) |
| **ISP** | Internet Service Provider (el cliente/empresa) |
| **SOAP** | Simple Object Access Protocol (XML legacy, usa Equifax) |
| **TLS** | Transport Layer Security (HTTPS) |
| **CGNAT** | Carrier-Grade NAT (rango 100.64.0.0/10, usado por Tailscale) |
| **CIDR** | Notación de rango de red, p. ej. `192.168.0.0/16` (lo que va en `allowed_networks`) |
| **NAT** | Network Address Translation: el router comparte su IP pública entre los PC de la LAN |
| **UAC** | User Account Control: aviso de Windows para elevar a Administrador |
| **AAD** | Azure Active Directory (una PC "unida" es PC gestionada) |
| **mTLS** | Mutual TLS (certificados cliente+servidor, no usado aún) |

---

## Patrones de Código en Este Proyecto

### TDD (Test-Driven Development)
- Tests en `tests/` → `pytest`
- Flujo: Rojo (test falla) → Verde (implementa mínimo) → Refactor
- Bitácora: `TestingLog.md`

### Typing Moderno (Python 3.12+)
```python
# Usar builtins, no typing
list[str]          # no List[str]
dict[str, Any]     # no Dict[str, Any]
str | None         # no Optional[str]
from __future__ import annotations  # en todos los archivos
```

### Errores Tipados
```python
class APIError(Exception): pass
class LoginError(APIError): pass
class ScoreError(APIError): pass
# En proxy/client.py:
class ProxyConnectionError(APIError): pass
class ProxyAuthError(APIError): pass
```

### Keyring Helper
```python
import keyring
keyring.set_password("servicio", "usuario", "secreto")
keyring.get_password("servicio", "usuario")  # None si no existe
keyring.delete_password("servicio", "usuario")
```

---

## Dónde Buscar Más

| Tema | Archivo |
|------|---------|
| Arquitectura completa | `docs/arquitectura.md` |
| Instalación proxy | `docs/proxy-deploy.md` |
| Config agentes | `docs/proxy-config.md` |
| Rotación credenciales | `docs/rotacion-credenciales.md` |
| Escalabilidad remota | `docs/escalabilidad-remota.md` + `Escalabilidad.md` |
| Historial decisiones | `AGENTS.md` (Historial) + `PlanesAprobados.md` |
| Tests y bugs | `TestingLog.md` |
| Control de acceso (whitelist + token) | `docs/arquitectura.md` → "Control de acceso al proxy" |
| VPN y whitelist | `Escalabilidad.md` + `docs/escalabilidad-remota.md` |
| Qué llevar a la PC owner oficial | `docs/proxy-deploy.md` → "Qué llevar a la PC owner" |
| Resumen día actual | `ResumenDelDia.md` |
| Resumenes pasados | `resumenes/YYYY-MM-DD.md` |

## Mapa de cobertura y reglas de venta por zona (2026-10-09)
- **Capas**: `COBERTURA` (3.361 polígonos, con el campo `PROYECTO`), `FRAUDE`, `PREFERENTE 2`,
  `CODIGOS BLOQUEADOS` y `ZONA F`. Viven embebidas en el .exe (`validator_app/data/capas.json.gz`,
  generado por `tools/preparar_capas.py`) y **no se suben al repo** (datos de terceros).
- **Reglas**: bloqueada/fraude → no se vende ni se consulta el score; Preferente 2 → score ≥ 401;
  el resto → ≥ 201; sin cobertura pero con cobertura a ≤ 300 m → "extensible" (no cruzar avenidas
  grandes de doble vía, eso hoy lo juzga el asesor mirando el mapa).
- **Solo la cobertura en vivo depende de WinForce** (`validar_cobertura`). Si falla, la decisión
  queda `SIN_CONFIRMAR` con los datos locales. Si WinForce dice NO, nunca es "vender".
- **Zona F** = copia de Fraude (27 de sus 28 polígonos son idénticos); significado pendiente.
- **Origen de los polígonos**: el mapa de WinForce son tiles PNG de Equifax (sin geometría); salen de
  una app web de terceros que los sirve sin login. Por eso se embebieron: el tercero puede desaparecer.
- `PrintWindow` (Win32): captura el contenido de UNA ventana aunque otra esté encima; es la forma
  segura de sacar capturas de la app (`ImageGrab` de una región copia lo que haya encima).

