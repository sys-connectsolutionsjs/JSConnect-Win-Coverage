# Renovación de Sesión y Cambio de Credenciales WinForce

> Proceso para renovar la sesión diaria y usar las credenciales nuevas cuando
> WinForce las cambia cada 1-2 meses. Solo lo realiza el owner.

---

## Contexto

- WinForce **rota credenciales cada 1-2 meses**: desactiva cuenta anterior + entrega nuevo user/pass al responsable
- El proxy persiste la cookie `PHPSESSID` en el keyring de LocalSystem
  (`JSWinProxy`/`credentials_cookies`) y, **si se configura el autologin**, el usuario y la
  contraseña de la cuenta dedicada (`JSWinProxy`/`credentials_login`, mismo keyring cifrado).
  Nunca en `config.yaml`, en el repo ni en el log.
- Los agentes (25 hoy, 41 previstos) **no tienen credenciales WinForce** — solo token proxy LAN
- Rotación = actualizar 1 sola PC (la del proxy)

---

## Autologin desatendido (vía principal desde 2026-10-28)

Plan "Proxy 24/7" ([`PlanesAprobados.md`](../PlanesAprobados.md)). Cuando la sesión muere, el proxy vuelve a
entrar solo: `validator_app/proxy/autologin.py` abre Chromium **normal, no headless** (el servicio
corre como LocalSystem, en la sesión 0, así que la ventana no se ve en el escritorio) con su perfil propio `.browser_profile_servicio/`, envía el formulario de
WinForce (`/login`), pulsa "Iniciar con Microsoft" en la puerta de acceso
(`accesoventas.win.pe`), deja actuar al SSO silencioso de Microsoft y, si Microsoft pide los datos,
llena correo y contraseña (una vez cada uno), acepta "¿Mantener la sesión iniciada?", valida la
`PHPSESSID` con `core.api.validar_cookie_sesion()` y hace un ping real de cobertura. Microsoft
devuelve a `controllers/auth_app.php`, donde WinForce deja activa la sesión (~10 s en total,
comprobado el 2026-10-30).

> **Por qué no es headless (2026-10-30)**: WinForce responde **HTTP 410 "Request Denied!"** a
> Chromium headless (User-Agent `HeadlessChrome`) y 200 al normal. El User-Agent no se cambia: no
> se disfraza el navegador. Si WinForce rechaza el navegador, el autologin **se detiene y avisa**
> ("no es la contraseña"), sin reintentar, hasta reiniciar el servicio o volver a guardar la credencial.

### Configurarlo (una vez, y cada vez que WinForce cambie la contraseña)
Siempre en la PC del proxy (a distancia: escritorio remoto). Tres formas, de la más fácil a la
más técnica:
1. **Consola owner** (`JSConnect-Win-Owner.exe`) → sección **"Autologin de WinForce"** →
   **Configurar...** → usuario y contraseña → Guardar → aceptar el aviso UAC. La etiqueta muestra el
   estado (sin configurar, activo, en pausa, contraseña rechazada). Lo único que se eleva es la lectura
   de la admin key; la contraseña sale de la consola sin elevar y nunca pasa por la línea de comandos
   ni por un archivo temporal.
2. **Al instalar**: `install_service.bat` pregunta al final "Configurar ahora el usuario y la
   contraseña de WinForce para el autologin" (por defecto No; en una reinstalación con credencial ya
   guardada solo lo informa).
3. **Terminal de Administrador** (técnicos):
   ```powershell
   python -m validator_app.proxy.rotate_creds --guardar-login
   ```

Las tres terminan en `POST 127.0.0.1:<puerto>/local/credenciales` (loopback + `X-Admin-Key`); el
proceso del proxy guarda la credencial en **su** keyring. Si en ese momento no hay sesión, el
autologin arranca enseguida.

> **Por qué no desde la extensión de Chrome**: la extensión no puede leer la admin key
> (`config.yaml` solo lo leen SYSTEM y Administradores). Para aceptarla habría que dejar
> `/local/credenciales` abierto a cualquier proceso de la PC sin clave, y cualquier programa podría
> cambiar con qué cuenta entra el proxy; además la contraseña pasaría por el almacenamiento de la
> extensión. Para probar el flujo con ventana visible,
sin guardar nada: `python -m validator_app.proxy.autologin --probar` (ojo: es un login real con
la cuenta y bota la sesión actual del proxy).

### Cómo se ve
- `/health` y `/admin/status`: `login_configurado` y el bloque
  `autologin: {habilitado, en_curso, ultimo_intento, ultimo_resultado, pausado_hasta, motivo}`.
- Bitácora `logs/sesion_eventos.jsonl`: `muerta` → `renovada` con `origen: "autologin"`; si
  falla, `autologin_fallido`; `credencial_guardada` al configurar; `autologin_pausado` (abajo).
- **La consulta del asesor no falla** (desde 2026-10-30): si la sesión está muerta o muere en esa
  misma consulta (incluida una respuesta HTML de WinForce en vez de JSON: es su página de login; el proxy
  revisa la cookie y solo si está muerta lo trata como muerte), el proxy espera al autologin hasta `autologin_espera_consulta_s` (15 s por defecto;
  el agente corta a los 30 s) y la repite una sola vez. Queda `consulta_reintentada` con
  `detalle: "deteccion X s, autologin Y s, consulta Z s, total T s"` en la bitácora y "consulta … salvada por el autologin" en
  `winsw.err.log`. Si el autologin está en pausa, esperando su frenado, sin credencial o no termina a
  tiempo: 503 al instante como antes y `consulta_sin_sesion`.
- El owner **no recibe aviso** mientras el autologin pueda resolverlo; el badge de la extensión
  puede ponerse rojo unos segundos durante el relogin.

### Frenado y freno anti-bucle (`FrenoAutologin`)
El **frenado** (espera entre intentos **fallidos**: red, Microsoft caído, pantalla rara) se elige
en la consola owner → "Autologin de WinForce" → **Frenado...** (UAC). Se aplica en vivo
(`POST /local/freno`) y se guarda en `validator_app/proxy/autologin_freno.json` (gitignored).
Reglas: el 1.er intento es inmediato; antes del 2.º, 1-5 min; antes del 3.º, desde el 2.º
hasta 10; antes del 4.º, desde el 3.º hasta 15; del 5.º en adelante, un intervalo fijo de
1-20 min. Nada por debajo de 1 minuto.

| Rango | Minutos (2.º-3.º-4.º, luego cada) | Nota |
|---|---|---|
| Recomendado (por defecto) | 1-2-3, cada 5 | — |
| Rápido | 1-1-2, cada 3 | Si otra persona usa la cuenta, se botan más seguido |
| Demasiado rápido (no recomendado) | 1-1-1, cada 1 | Pelea por la sesión cada minuto; riesgo de que marquen la cuenta |
| Lento óptimo | 2-4-6, cada 10 | — |
| Lento | 3-6-10, cada 15 | La sesión puede quedar caída hasta 15 min |
| Demasiado lento (no recomendado) | 5-10-15, cada 20 | Los agentes pueden quedar sin servicio 20 min |
| Personalizado | según las reglas | — |

- **Ojo: el frenado no decide la "pelea" por la cuenta.** Cuando otra persona usa la cuenta,
  el relogin del proxy *funciona* y la bota; la pelea la limita la **pausa**: dos muertes
  seguidas a menos de `autologin_muerte_rapida_s` (600 s) de un autologin → pausa igual al
  intervalo fijo del frenado (5 min en el recomendado) + aviso. Reloguear cada pocos segundos
  no "gana": se botan uno al otro, los agentes fallan igual y tantos logins con la misma cuenta
  pueden hacer que Microsoft o WinForce la marquen. La solución de fondo es averiguar quién más
  entra con la cuenta.
- Tope por hora: lo que el frenado cabe en 60 min + 2 (solo red de seguridad). Si se alcanza →
  aviso "el proxy no logró volver a entrar".
- **Contraseña rechazada** por WinForce o Microsoft → no se reintenta (evita bloquear la cuenta),
  el autologin queda desactivado hasta guardar la nueva con `--guardar-login`, y se avisa.
- El keepalive (cada 15 min) relanza el autologin mientras no haya sesión: tras una pausa se
  reanuda solo, y en un host recién instalado consigue la primera `PHPSESSID` sin intervención.
- En la pantalla de Microsoft el correo se reescribe si se pierde. La contraseña se envía una sola vez
  por intento. Ojo: la pantalla del correo trae un `input[name=passwd]` oculto (`.moveOffScreen`) que
  Playwright da por visible; el selector lo excluye.
- **Cada fallo deja una imagen** de lo que se veía: `logs/autologin_fallo.png` es la última y
  `logs/autologin_fallos/` conserva las 20 más recientes. La ruta queda en la bitácora. Muestra el
  correo, nunca la contraseña.
- `logs/autologin_pasos/` guarda el rastro del **último** intento: `traza.txt` (pasos, navegaciones y
  tiempos, con URL sin valores de parámetros) y una imagen antes de cada acción.
- Si falla siempre: ver esas imágenes y probar `--probar`.
  Los selectores de WinForce (`#username`, `#password`, `#ingresar`, avisos `.swal2-popup`), de la
  puerta de acceso (`button.login-button.azure`) y de Microsoft (`input[name=loginfmt]`, `input[name=passwd]:not(.moveOffScreen)`, `#idSIButton9`, `#KmsiCheckboxField`,
  `#usernameError`/`#passwordError`) están en `autologin.py`.

---

## Procedimiento — Extensión de Chrome (renovación manual)

> Renovación de la sesión a mano (si el autologin no está configurado, está pausado o falla).
> El "tope de ≈ 9.5 h" quedó descartado el 2026-10-21: las sesiones mueren
> cuando otra persona inicia sesión con la misma cuenta). El owner no necesita saber nada técnico y **no sale de su navegador
> de siempre**.

`install_service.bat` fuerza-instala en el Chrome de la PC del proxy la extensión
**"Renovar sesion WinForce"** (política de Chrome — el owner no puede quitarla por
error, no hace falta modo desarrollador). Tras instalar, **hay que reabrir Chrome**
una vez para que aparezca.

> **PC no gestionada** (Windows Home/WORKGROUP, o sin dominio/Azure AD): Chrome ignora
> esa política y la extensión no aparece. El instalador lo avisa y al final imprime la
> carga manual: `chrome://extensions` → Modo de desarrollador → Cargar descomprimida →
> `validator_app\proxy\.extension_build`. Alternativa: el icono "Renovar sesion
> WinForce" del Escritorio. Usar **una sola vía de login a la vez**: dos logins en
> paralelo pueden invalidar la sesión (hipótesis abierta desde 2026-09-18).

> **Para desarrollo/pruebas** (cargarla descomprimida + proxy local + casos de
> error): ver [`README_PROXY.md`](../README_PROXY.md) → "Probar la extensión en desarrollo".

### Para el owner

1. Trabaja normal en Chrome, con la sesión de WinForce abierta como siempre.
2. Cuando el proxy detecta que la sesión murió, el **icono de la extensión** (barra
   de Chrome, arriba a la derecha) muestra un **badge rojo `!`**.
3. **Un clic en el icono.** La extensión lee la sesión de WinForce del propio
   navegador y la manda al proxy.
4. Sale una notificación **"Sesión del proxy renovada. Listo."** El badge se apaga.

Si al pulsar sale "No hay sesión de WinForce en este navegador", es que la sesión
de WinForce del owner también caducó → que abra `appwinforce.win.pe`, inicie
sesión (SSO de Microsoft: correo y contraseña), y vuelva a pulsar el icono.

### Fallbacks (para el técnico / si el proxy está caído)

- **Icono "Renovar sesion WinForce" del Escritorio** (login asistido con navegador
  aparte): doble clic → login → barra verde → cuadro "✓". Ver
  `python -m validator_app.proxy.rotate_creds [--preview|--fresh]`.
- **Consola `JSConnect-Win-Owner.exe`**: el botón **Renovar sesión WinForce**
  lanza el mismo flujo asistido y luego refresca el estado del proxy.
- **`python -m validator_app.proxy.rotate_creds --manual`**: pega la `PHPSESSID`
  a mano (F12). No necesita Playwright ni el navegador.

### Configuración de una vez — autocompletar la contraseña

La ventana abre el **Google Chrome instalado** con un perfil propio (separado del
Chrome normal). Para que la contraseña se autocomplete, la **primera vez** haz una
de estas dos:

- **Iniciar sesión en Chrome** en esa ventana (menú ⋮ arriba a la derecha →
  "Activar la sincronización" con la cuenta de Google del owner). Quedan
  disponibles todas las contraseñas guardadas de esa cuenta.
- O simplemente **pulsar "Guardar"** cuando Chrome ofrezca guardar la contraseña
  de Microsoft tras el primer login.

Desde entonces: doble clic → contraseña autocompletada → listo.

> Si esa PC no tiene Google Chrome, la ventana usa el navegador empaquetado
> (Chromium), que tiene su propio "Guardar contraseña" local pero sin sync.

### Qué hace por dentro

`python -m validator_app.proxy.rotate_creds` (lo que lanza el icono, vía
`pythonw.exe` = sin ventana de consola):
1. `validator_app/proxy/login_asistido.py` abre Chromium con un **perfil
   persistente** (`.browser_profile/`, gitignored → el SSO de Microsoft recuerda
   el dispositivo dentro de la jornada).
2. Sondea `context.cookies()` (ve las cookies **HttpOnly**, a diferencia de
   `document.cookie`) buscando `PHPSESSID` en `appwinforce.win.pe`.
3. Cuando la encuentra, la valida con `core.api.validar_cookie_sesion()`
   (petición real a `operador.php`). Si pasa → capturada.
4. `push_session_cookie()` **empuja la cookie por HTTP al proxy** (no la escribe
   en ningún keyring de este proceso — el servicio corre como LocalSystem, que
   tiene su propio Windows Keyring, distinto del owner). Primero intenta
   `POST /local/renovar` (proceso vivo en `127.0.0.1`, sin admin key); si no
   logra conectar, cae a `POST /admin/rotar` con `X-Admin-Key`. Ambos terminan
   en `set_session_cookie()` del lado del servidor, que sí guarda en el keyring
   **del proceso del proxy** — la única fuente de verdad.
5. El proxy queda con la sesión nueva de inmediato (fue el propio `POST` el que
   la aplicó); **no hace falta reiniciar el servicio**.

### Fallback: `--manual` (para el técnico)

Si Playwright/Chromium se rompe en esa PC:
```powershell
python -m validator_app.proxy.rotate_creds --manual
```
Pide pegar la `PHPSESSID` a mano (F12 → Application → Cookies). Mismo resto del
flujo (validar → keyring → verificar). `--fresh` borra el perfil del navegador si
el asistido se atasca.

### Probar la ventana sin renovar nada: `--preview`

```powershell
python -m validator_app.proxy.rotate_creds --preview
```
Abre la ventana de captura y muestra si funciona (imprime la `PHPSESSID` en la
terminal, cuadro "no se guardo nada"). **No** toca el keyring ni necesita
`config.yaml`. Útil para inspeccionar la UX en una máquina de desarrollo.

---

## Renovación remota (no disponible hoy)

`/admin/*` (incluido `POST /admin/rotar`) **solo responde a conexiones desde la propia
PC del proxy** (loopback) **y** exige `X-Admin-Key`; desde otra PC da 403 aunque la
clave sea correcta (`validator_app/proxy/server.py`, `_es_local`). Por eso no se puede
renovar la sesión por VPN con `curl` desde otra máquina.

Para renovar sin estar en la oficina: conectarse por escritorio remoto (RDP) a la PC
del proxy y ahí usar la extensión de Chrome o el icono "Renovar sesion WinForce"; o,
desde esa misma PC:

```powershell
curl.exe -X POST http://localhost:8080/admin/rotar `
  -H "X-Admin-Key: <admin_key>" -H "Content-Type: application/json" `
  -d '{\"php_sessid\":\"<valor de la cookie>\"}'
```

El proxy valida la `X-Admin-Key`, valida la cookie contra WinForce, la guarda en el
keyring y responde OK (`/admin/login` es equivalente).

Un acceso remoto real (VPN tipo Tailscale + HTTPS) exigiría **cambiar esa restricción**
de loopback en el servidor: es una decisión de diseño pendiente, no una configuración.
Ver [`docs/escalabilidad-remota.md`](escalabilidad-remota.md).

---

## Verificación de Estado

```powershell
# Estado rápido
curl.exe -H "X-Admin-Key: <admin_key>" http://localhost:8080/admin/status
# {
#   "logged_in": true,
#   "session_age": 45,
#   "creds_updated": "2026-08-25T14:30:00",
#   "proxy_version": "dev"
# }

# Health check completo
curl http://localhost:8080/health
# {
#   "status": "ok",
#   "version": "dev",
#   "session_age": 45,
#   "logged_in": true
# }
```

---

## ¿Por qué se cerró la sesión?

Desde 2026-09-29 el proxy guarda un evento por cada cambio de estado de la
sesión en `logs/sesion_eventos.jsonl` (junto a `logs/winsw.*.log`, una línea
JSON por evento). Antes de este archivo, la única forma de saber por qué
murió una sesión era leer los `winsw.err.log` a mano — y ni siquiera ahí
quedaba la edad de la cookie ni un detalle claro de la causa.

```powershell
# Ultimos eventos, con causa y edad de la cookie al morir
Get-Content logs\sesion_eventos.jsonl -Tail 20
# o desde el admin (loopback, con admin_key):
curl.exe -H "X-Admin-Key: <admin_key>" http://localhost:8080/admin/status
```

Cada línea trae `{ts, evento, origen, cookie_id, edad_cookie_s, detalle}`.
`cookie_id` es un hash corto (no permite recuperar la `PHPSESSID`); sirve para
ver si dos eventos hablan de la misma cookie o de una distinta. Cómo leerla:

| Lo que ves en la bitácora | Causa probable |
|---|---|
| `evento: "muerta"`, `edad_cookie_s` ≈ 34200 (≈9.5h) | Posible tope absoluto de sesión (una sola medición, 2026-09-05/06) **o** un login ajeno con la misma cuenta. En ambos casos toca renovar. Ver "Cómo investigar una muerte de sesión" abajo. |
| `evento: "muerta"` a los pocos minutos de un `"renovada"` con **otro** `cookie_id` | Alguien inició sesión con la misma cuenta desde otro lado (Chrome cotidiano vs. ventana del icono, u otra PC) invalidó la sesión — hipótesis abierta desde 2026-09-18, aún no confirmada de forma controlada. |
| `evento: "muerta"`, `origen` menciona `/health` o `/admin/status`, `detalle` con `Timeout`/`ConnectionError` | WinForce estuvo lento o caído, no la cookie — el proxy ya reconfirma antes de declarar muerte (ver más abajo), pero si el segundo intento *también* falló, puede seguir siendo un corte de red largo, no la cookie. |
| `evento: "falso_positivo_evitado"` | El proxy vio una respuesta fallida puntual, reconfirmó, y la sesión seguía viva — no pasó nada, es solo el registro de que el mecanismo funcionó. |
| `evento: "muerta"`, `origen: "keepalive: ping fallido..."` | El latido de los 15 min detectó la muerte en un hueco sin tráfico real (almuerzo, madrugada). |

**Reconfirmación antes de declarar muerte** (2026-09-29): una sola respuesta
fallida de WinForce (timeout, error puntual) ya no basta para marcar la sesión
muerta. El proxy espera unos segundos y reintenta una vez
(`_confirmar_muerte()` en `server.py`) antes de avisar al owner — evita el
falso positivo real visto ese día: un `ReadTimeout` de 30s en `/health` marcó
"MUERTA" una sesión que, al reiniciar el servicio, resultó seguir viva.

### Qué NO mata la sesión

- **Cerrar la pestaña de WinForce.** La `PHPSESSID` vive en el servidor; nada
  en la extensión ni en el proxy manda un logout al cerrar una pestaña.
- **Cerrar todo Chrome.** Mismo motivo — el proxy sigue usando la cookie que
  ya tiene guardada, sin depender de que el navegador siga abierto.

### Qué probablemente sí la mata (sin confirmar con una prueba controlada)

- Pulsar "Cerrar sesión" dentro de WinForce en el Chrome del owner (comparte
  la misma `PHPSESSID` que usa el proxy).
- Iniciar sesión con la misma cuenta desde otra PC o otro navegador al mismo
  tiempo (la hipótesis de "dos logins en paralelo" del 2026-09-18). **Es la
  explicación que el dueño del proyecto considera más probable** para las muertes de
  sesión (2026-10-07): alguien entra con esa cuenta, la `PHPSESSID` anterior queda
  invalidada y, al volver a iniciar sesión, todo regresa a la normalidad.

### Cómo investigar una muerte de sesión

No hay un tope de 9.5 h demostrado (ver la corrección del 2026-10-07 en
[`anotaciones.md`](../anotaciones.md)), así que cada muerte se mira con estos pasos:

1. `Get-Content logs\sesion_eventos.jsonl -Tail 20` y anotar `ts`, `evento`, `origen`,
   `cookie_id` y `edad_cookie_s` de la muerte y de la renovación anterior.
2. Preguntar **a quién usa esa cuenta**: ¿alguien inició sesión en WinForce a esa hora
   (otro PC, el celular, otro navegador)? Es el dato que falta para confirmar la
   hipótesis; el proxy no lo puede saber.
3. Distinguir los patrones:
   - **Muere a una hora "rara" y con edad variable** → apunta a un login ajeno.
   - **Muere siempre a la misma edad** (p. ej. ≈ 34 200 s, o ≈ 600 s tras renovar, como
     el 2026-10-02: 603 y 593 s con el mismo `cookie_id`) → apunta a un límite del
     servidor o a un temporizador del propio proxy.
   - **El mismo `cookie_id` en dos renovaciones seguidas** → la segunda reinyectó una
     cookie que ya estaba muerta; no es una sesión nueva.
4. Una prueba controlada barata: renovar en un momento en que **nadie más usa la
   cuenta** (p. ej. antes de la hora de entrada) y mirar si la sesión llega a las ≈ 10
   min y a las ≈ 9.5 h. Si sobrevive, el culpable era un login ajeno.

---

## Geofinder (dirección de las coordenadas)
La dirección que muestra la app sale de **Geofinder**, una API de Equifax que WinForce usa desde el
navegador. No depende de la sesión de WinForce: el proxy pide un token OAuth (`client_credentials`,
dura ~24 min y se renueva solo) con la credencial `Authorization: Basic …` de la app de WinForce.
- **Dónde va**: `geofinder_basic` en `validator_app/proxy/config.yaml` (gitignored). Nunca en el repo,
  chat ni documentos. Vacío = los agentes muestran la dirección de OpenStreetMap con un aviso.
- **Cómo obtenerla**: en WinForce, F12 → Network → filtro `oauth` → petición
  `api.latam.equifax.com/v2/oauth/token` → Headers → `Authorization: Basic …` (se pega solo lo que
  sigue a `Basic`). `tools/captura.py` la oculta a propósito.
- **Cuándo cambia**: solo si WinForce/Equifax rotan la credencial. Síntoma: en la ficha del cliente
  aparece el aviso de dirección aproximada (OpenStreetMap). Se repite el procedimiento y se reinicia
  el servicio del proxy.

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| El icono no abre nada / "Playwright no está instalado" | Chromium no descargado en esa PC | `python -m playwright install chromium` (o `install_service.bat`); mientras tanto `rotate_creds --manual` |
| La ventana no llega a ponerse verde | Login no completado (falta el paso de Microsoft) | Volver a abrir el icono e iniciar sesión **por completo** antes de cerrar |
| El navegador asistido se queda en un estado raro | Perfil corrupto | `python -m validator_app.proxy.rotate_creds --fresh` (borra `.browser_profile/`) |
| Agentes siguen fallando tras renovar | La cookie fue rechazada o la sesión volvió a caducar | Revisar el mensaje de la consola/extensión y `/admin/status` con admin key |
| La cookie no sobrevive al reinicio | No llegó al proceso LocalSystem | Renovar con el proxy activo y verificar `/local/renovar`; revisar logs |
| No se sabe por qué murió la sesión | Falta revisar la bitácora | Ver "¿Por qué se cerró la sesión?" arriba — `logs/sesion_eventos.jsonl` o `/admin/status` |

---

## ⚠️ NOTA: Login WinForce + SSO de Microsoft (Entra ID)

El login de WinForce son tres pasos: su formulario propio (`/login`, que llama a `acceso.php`,
responde "Redireccionar" y recarga), la puerta de acceso `accesoventas.win.pe` ("Iniciar con Microsoft"
o "Iniciar con Google") y `login.microsoftonline.com` (SSO de Microsoft Entra ID,
solo correo y contraseña; **no hay segundo factor**, corregido el 2026-10-23). No hay login
directo por HTTP; hoy la `PHPSESSID` sale de un login en navegador. El **login asistido**
(`login_asistido.py`, Playwright) automatiza la parte de *extraer* la cookie —
el owner solo inicia sesión. `context.cookies()` de Playwright ve la `PHPSESSID`
aunque sea HttpOnly (`document.cookie` no la vería). El perfil persistente hace
que el SSO de Microsoft no vuelva a pedir la contraseña dentro de la misma jornada.

No hace falta replicar el flujo OAuth2/SAML por HTTP: si algún día el proxy debe
re-loguearse solo, se hace con Playwright llenando usuario y contraseña (guardados en el
keyring del host).

---

## Checklist (Para el Owner)

Renovación diaria (extensión):
- [ ] Vi el badge rojo `!` en el icono de la extensión de Chrome
- [ ] (Si hacía falta) abrí `appwinforce.win.pe` e inicié sesión (SSO de Microsoft)
- [ ] Un clic en el icono de la extensión
- [ ] Salió la notificación "Sesión del proxy renovada"

Cambio de credenciales (cada 1-2 meses, cuando WinForce las rota):
- [ ] Recibí el nuevo usuario/contraseña de WinForce
- [ ] Inicié sesión en `appwinforce.win.pe` con las **nuevas** (SSO de Microsoft)
- [ ] Un clic en el icono de la extensión → "Sesión del proxy renovada"
