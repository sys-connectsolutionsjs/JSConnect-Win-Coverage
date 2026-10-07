# Renovación de Sesión y Cambio de Credenciales WinForce

> Proceso para renovar la sesión diaria y usar las credenciales nuevas cuando
> WinForce las cambia cada 1-2 meses. Solo lo realiza el owner.

---

## Contexto

- WinForce **rota credenciales cada 1-2 meses**: desactiva cuenta anterior + entrega nuevo user/pass al responsable
- El proxy persiste **solo la cookie `PHPSESSID`** en el keyring de LocalSystem
  (`JSWinProxy`/`credentials_cookies`); no guarda usuario ni contraseña
- Los agentes (25 hoy, 41 previstos) **no tienen credenciales WinForce** — solo token proxy LAN
- Rotación = actualizar 1 sola PC (la del proxy)

---

## Procedimiento — Extensión de Chrome (vía principal)

> Renovación diaria de la sesión (WinForce usa 2FA, así que el proxy no puede volver a
> iniciar sesión solo; además hay un posible tope de ≈ 9.5 h, medido una vez y **no
> concluyente**). El owner no necesita saber nada técnico y **no sale de su navegador
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
> error): ver `README_PROXY.md` → "Probar la extensión en desarrollo".

### Para el owner

1. Trabaja normal en Chrome, con la sesión de WinForce abierta como siempre.
2. Cuando el proxy detecta que la sesión murió, el **icono de la extensión** (barra
   de Chrome, arriba a la derecha) muestra un **badge rojo `!`**.
3. **Un clic en el icono.** La extensión lee la sesión de WinForce del propio
   navegador y la manda al proxy.
4. Sale una notificación **"Sesión del proxy renovada. Listo."** El badge se apaga.

Si al pulsar sale "No hay sesión de WinForce en este navegador", es que la sesión
de WinForce del owner también caducó → que abra `appwinforce.win.pe`, inicie
sesión (incluye el 2FA de Microsoft), y vuelva a pulsar el icono.

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
Chrome normal). Para que la contraseña se autocomplete y solo quede aprobar el
2FA en el teléfono, la **primera vez** haz una de estas dos:

- **Iniciar sesión en Chrome** en esa ventana (menú ⋮ arriba a la derecha →
  "Activar la sincronización" con la cuenta de Google del owner). Quedan
  disponibles todas las contraseñas guardadas de esa cuenta.
- O simplemente **pulsar "Guardar"** cuando Chrome ofrezca guardar la contraseña
  de Microsoft tras el primer login.

Desde entonces: doble clic → contraseña autocompletada → aprobar 2FA → listo.

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
Ver `docs/escalabilidad-remota.md`.

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
`anotaciones.md`), así que cada muerte se mira con estos pasos:

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

## ⚠️ NOTA: Login WinForce + Microsoft 2FA

El login de WinForce redirige a `login.microsoftonline.com` para 2FA, así que el
login programático (usuario/contraseña por HTTP) es **inviable**. La `PHPSESSID`
sale siempre de un login manual en navegador. El **login asistido**
(`login_asistido.py`, Playwright) automatiza la parte de *extraer* la cookie —
el owner solo inicia sesión. `context.cookies()` de Playwright ve la `PHPSESSID`
aunque sea HttpOnly (`document.cookie` no la vería). El perfil persistente hace
que el SSO de Microsoft se salte el 2FA dentro de la misma jornada.

Documentado aquí para que futuros devs no pierdan tiempo intentando automatizar
el login OAuth2/SAML completo — no hace falta.

---

## Checklist (Para el Owner)

Renovación diaria (extensión):
- [ ] Vi el badge rojo `!` en el icono de la extensión de Chrome
- [ ] (Si hacía falta) abrí `appwinforce.win.pe` e inicié sesión (2FA Microsoft)
- [ ] Un clic en el icono de la extensión
- [ ] Salió la notificación "Sesión del proxy renovada"

Cambio de credenciales (cada 1-2 meses, cuando WinForce las rota):
- [ ] Recibí el nuevo usuario/contraseña de WinForce
- [ ] Inicié sesión en `appwinforce.win.pe` con las **nuevas** (2FA Microsoft)
- [ ] Un clic en el icono de la extensión → "Sesión del proxy renovada"
