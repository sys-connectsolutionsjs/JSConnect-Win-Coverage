# Rotación de Credenciales WinForce

> Proceso para actualizar usuario/contraseña de WinForce cada 1-2 meses.
> Solo el owner (responsable) puede hacerlo. Credenciales NUNCA salen de la PC proxy.

---

## Contexto

- WinForce **rota credenciales cada 1-2 meses**: desactiva cuenta anterior + entrega nuevo user/pass al responsable
- Credenciales viven **SOLO en la PC proxy** (keyring `JSWinProxy`/`credentials`)
- 20 agentes **no tienen credenciales WinForce** — solo token proxy LAN
- Rotación = actualizar 1 sola PC (la del proxy)

---

## Procedimiento — Extensión de Chrome (vía principal)

> Renovación diaria de la sesión (por el tope absoluto de sesión ≈ 9.5 h). El
> owner no necesita saber nada técnico y **no sale de su navegador de siempre**.

`install_service.bat` fuerza-instala en el Chrome de la PC del proxy la extensión
**"Renovar sesion WinForce"** (política de Chrome — el owner no puede quitarla por
error, no hace falta modo desarrollador). Tras instalar, **hay que reabrir Chrome**
una vez para que aparezca.

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
- **`python -m validator_app.proxy.rotate_creds --manual`**: pega la `PHPSESSID`
  a mano (F12). No necesita Playwright ni el navegador.

### Configuración de una vez — autocompletar la contraseña (solo para el fallback)

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
4. `save_session_to_keyring()` → `JSWinProxy/credentials_cookies` + timestamp.
5. El proxy en marcha la recoge en el siguiente request (`_relogin_silent`) o el
   loop de keepalive; **no hace falta reiniciar el servicio**.

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

## Procedimiento Futuro (v2 — Remoto via VPN)

Cuando haya agentes remotos y VPN (Tailscale):

1. Owner hace login manual en el navegador (incluye 2FA Microsoft) y copia la
   cookie `PHPSESSID` (igual que en v1)
2. Con VPN conectada, llama el endpoint protegido:
   ```bash
   curl -X POST http://proxy.oficina.local:8080/admin/rotar \
     -H "X-Admin-Key: <admin_key>" \
     -H "Content-Type: application/json" \
     -d '{"php_sessid":"<valor de la cookie>"}'
   ```
3. Proxy valida `X-Admin-Key` → valida la cookie contra WinForce → guarda en
   keyring → responde OK. `/admin/login` hace exactamente lo mismo, con el
   mismo body — ambos endpoints son intercambiables.

**Requisitos v2**:
- VPN configurada (Tailscale gratis 100 devices)
- HTTPS en proxy (self-signed cert + `uvicorn --ssl-keyfile --ssl-certfile`)
- `admin_key` conocido solo por owner (generado en `install_service.bat`)

---

## Verificación de Estado

```powershell
# Estado rápido
curl http://localhost:8080/admin/status
# {
#   "logged_in": true,
#   "session_age_seconds": 45,
#   "creds_updated": "2026-08-25T14:30:00",
#   "proxy_version": "c0d2f2a"
# }

# Health check completo
curl http://localhost:8080/health
# {
#   "status": "ok",
#   "version": "c0d2f2a",
#   "session_age": 45,
#   "logged_in": true
# }
```

---

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| El icono no abre nada / "Playwright no está instalado" | Chromium no descargado en esa PC | `python -m playwright install chromium` (o `install_service.bat`); mientras tanto `rotate_creds --manual` |
| La ventana no llega a ponerse verde | Login no completado (falta el paso de Microsoft) | Volver a abrir el icono e iniciar sesión **por completo** antes de cerrar |
| El navegador asistido se queda en un estado raro | Perfil corrupto | `python -m validator_app.proxy.rotate_creds --fresh` (borra `.browser_profile/`) |
| Agentes siguen fallando tras renovar | Proxy con cookie vieja en memoria | Reiniciar servicio: `winsw.exe restart` (o esperar al siguiente `_relogin_silent` / ping de keepalive) |
| Keyring no accesible | Usuario distinto al del servicio | Correr `rotate_creds` como el **mismo usuario** que corre el servicio |

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