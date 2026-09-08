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

## Procedimiento — Login Asistido (por defecto)

> Renovación diaria de la sesión (por el tope absoluto de sesión ≈ 9.5 h). El
> owner no necesita saber nada técnico.

### Para el owner

1. En el Escritorio de la PC del proxy, **doble clic en "Renovar sesion WinForce"**.
2. Se abre una ventana de Chrome en la página de login de WinForce.
3. **Inicia sesión como siempre.** El primer login de cada jornada incluye el
   paso de Microsoft (2FA); el resto del día se salta solo.
4. Cuando la barra superior de la ventana se pone **verde** ("Sesión capturada,
   ya puedes cerrar esta ventana"), ciérrala.
5. Aparece un cuadro **"✓ Sesión renovada correctamente"**. Listo.

No hay que abrir consola, ni F12, ni copiar nada.

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

Renovación diaria (login asistido):
- [ ] Doble clic en "Renovar sesion WinForce" (Escritorio de la PC del proxy)
- [ ] Inicié sesión en la ventana que se abrió (incluye Microsoft el 1er login del día)
- [ ] La barra se puso verde → cerré la ventana
- [ ] Salió el cuadro "✓ Sesión renovada"

Cambio de credenciales (cada 1-2 meses, cuando WinForce las rota):
- [ ] Recibí el nuevo usuario/contraseña de WinForce
- [ ] Doble clic en "Renovar sesion WinForce" e inicié sesión con las **nuevas**
- [ ] (Igual que arriba: barra verde → cerrar → "✓")