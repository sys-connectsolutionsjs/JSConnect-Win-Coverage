# Anotaciones Técnicas - Glosario del Proyecto

> **Para futuros programadores**: Términos, conceptos y decisiones que no son obvios al leer el código.
> Si no entiendes algo, busca aquí. Si no está, agrégalo.

---

## A

### API Interna (WinForce)
El sistema del ISP (`appwinforce.win.pe`) expone una API JSON interna en `/controllers/*.php` que el navegador usa vía AJAX. **No es pública documentada**, pero no requiere scraping: replicamos las llamadas HTTP directas.
- Endpoints: `acceso.php` (login), `coordenada.php` (cobertura), `cliente.php` (score), `operador.php` (verificar sesión), `document.php` (tipos doc), `newsearch.php` (crear lead)

### Auto-relogin Silencioso
Mecanismo en `ValidatorAPI` (proxy y standalone) que detecta sesión expirada o >120s sin uso → hace login automático en background → reintenta la petición original. El agente/cliente no ve error.
- **Ojo (Etapa R, 2026-09-09)**: en el proxy, `auto_relogin_if_needed()` ya NO refresca `_last_activity` — solo lo hace una llamada real y exitosa a WinForce. Antes lo refrescaba en toda petición (incluso las fallidas), y con 20 agentes reintentando contra una sesión muerta el keepalive nunca pinchaba → nadie se enteraba de la muerte.

### Aviso de sesión muerta (Etapa R, 3 capas)
Cuando el proxy confirma que la sesión WinForce murió (`_marcar_sesion_muerta()`), avisa por tres vías independientes, cada una degrada sola:
1. **HTTP 503 al agente** — ver "Sesión caducada (HTTP 503)".
2. **Evento de Windows + tarea programada** — el proxy escribe un evento (`eventcreate`, origen `JSWinProxy`, ID **101** = caducó / **102** = renovada) en el Registro de Aplicación; `install_service.bat` registra la tarea `JSWinProxy-AvisoSesion` (`schtasks /sc ONEVENT`) que le saca un `msg *` al owner en su escritorio. Es la vía nativa para que un servicio **LocalSystem** (sesión 0, sin escritorio) alcance a un humano. En foreground sin elevar, `eventcreate` da "Acceso denegado" (esperado; bajo el servicio funciona).
3. **Toast de la extensión de Chrome** — `background.js` dispara `chrome.notifications` solo en la transición viva↔muerta (estado previo en `chrome.storage.session`), no cada sondeo.
4. **Webhook opcional** — `config.alert_webhook_url` (vacío = desactivado): POST `{"text": ...}`, forma que aceptan Teams/Slack/Discord. Para owner remoto o varias oficinas.

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
- Solo en **Windows Keyring de la PC proxy** (`JSWinProxy`/`credentials`)
- Rotación: `rotate_creds.py` via RDP (v1) o endpoint `/admin/rotar` (v2 VPN)

---

## D

### DNS Interno (Tailnet)
En Tailscale: nombre `proxy.oficina.local` → IP Tailscale del proxy (ej. `100.64.12.34`).
Permite auto-discovery: agentes usan `http://proxy.oficina.local:8080/admin/config` para auto-configurarse.

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
Respuesta: `{"status":"ok","version":"<commit-sha>","session_age":45,"logged_in":true}`

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
> **ESTADO 2026-09-08 — investigación CERRADA.** El punto 2 de abajo ("tope
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

## P

### Proxy Local (Reverse Proxy Interno)
Servidor intermedio en PC oficina que:
1. Recibe peticiones de agentes (LAN/VPN)
2. Valida token + IP
3. Reenvía a WinForce usando **SU propia sesión** (cookies en keyring)
4. Devuelve respuesta a agente
- Evita: 20 sesiones concurrentes, rotación credenciales en 20 máquinas, bloqueo por IP
- Stack: FastAPI + uvicorn + winsw service
- Puerto: 8080 (configurable)

### Proxy Token (Token Compartido)
Secreto de 256-bit (64 chars hex) compartido entre proxy y **todos** los agentes.
- Generado auto en `install_service.bat` (`secrets.token_hex(32)`)
- Guardado en `config.yaml` (proxy) + keyring agentes (`JSWinClient`/`proxy_token`)
- **No es secreto crítico**: solo valida en LAN/VPN + IP binding. Si se filtra, atacante ya está en la red.

---

## R

### Rotación de Credenciales (Cada 1-2 Meses)
Proceso para actualizar user/pass WinForce en el proxy.
- **v1 (actual)**: Owner RDP a PC proxy → `python -m validator_app.proxy.rotate_creds` → pega cookie `PHPSESSID` de navegador (tras login manual con 2FA)
- **v2 (futuro)**: Owner via VPN → `POST /admin/rotar` con `X-Admin-Key` + user/pass nuevo

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
- Payload incluye: tipo_doc (1=DNI, 2=CE, 3=RUC), documento, coordenadas, cobertura, 25 campos geodata vacíos
- `deuda_total` puede llegar como **int `0`** (no string) cuando no hay deuda → `_parsear_score` lo normaliza a str y `ScoreResponse` usa `coerce_numbers_to_str` (fix `3f63e8f`, hallado en la validación real de la Etapa B).

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
- Logs: Visor de Eventos → Aplicaciones y Servicios → `JSWinProxy`

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
| Resumen día actual | `ResumenDelDia.md` |
| Resumenes pasados | `resumenes/YYYY-MM-DD.md` |