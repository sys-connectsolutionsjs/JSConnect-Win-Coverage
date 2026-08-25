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

## Procedimiento Actual (v1 — RDP Presencial)

### Paso a Paso

1. **Owner recibe nuevas credenciales** de WinForce (email/contraseña nueva)

2. **Hace RDP a la PC de la oficina** (donde corre el proxy)

3. **Abre PowerShell** en la carpeta del proyecto:
   ```powershell
   cd C:\ruta\a\JSConnect-Win-Coverage
   python -m validator_app.proxy.rotate_creds
   ```

4. **El script pide interactivamente**:
   ```
   ========================================
   ROTACIÓN DE CREDENCIALES WINFORCE
   ========================================
   Usuario (email): nuevo_usuario@empresa.com
   Contraseña: ****************
   ========================================
   Probando login en WinForce...
   ✓ Login exitoso
   ✓ Sesión activa verificada
   ✓ Cookies guardadas en keyring (JSWinProxy/credentials)
   ========================================
   Credenciales rotadas correctamente.
   ```

5. **Verificación opcional**:
   ```powershell
   curl http://localhost:8080/admin/status
   # {"logged_in":true,"session_age":5,"creds_updated":"2026-08-25T14:30:00"}
   ```

6. **Listo**: Siguientes validaciones de agentes usan credenciales nuevas automáticamente

---

## Qué Hace `rotate_creds.py` Internamente

```python
# validator_app/proxy/rotate_creds.py
def main():
    # 1. Lee credenciales actuales del keyring (para mostrar info)
    # 2. Pide nuevo usuario/contraseña (getpass, no se ve en pantalla)
    # 3. Crea ValidatorAPI temporal → login() → verifica sesión activa
    # 4. Si OK: extrae cookies de sesión → guarda en keyring JSWinProxy/credentials
    # 5. Actualiza timestamp "creds_updated" en keyring
    # 6. Proxy detecta cookies nuevas en siguiente request (auto-relogin)
```

**No requiere reiniciar el servicio** — el proxy lee keyring en cada request (o cachea con TTL corto).

---

## Procedimiento Futuro (v2 — Remoto via VPN)

Cuando haya agentes remotos y VPN (Tailscale):

1. Owner conecta VPN a la red de la oficina
2. Llama endpoint protegido:
   ```bash
   curl -X POST http://proxy.oficina.local:8080/admin/rotar \
     -H "X-Admin-Key: <admin_key>" \
     -H "Content-Type: application/json" \
     -d '{"usuario":"nuevo@empresa.com","password":"nueva_pass"}'
   ```
3. Proxy valida `X-Admin-Key` → hace login → guarda cookies → responde OK

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
| `rotate_creds.py` → "Login fallido" | Credenciales incorrectas / WinForce caído | Verificar user/pass en web WinForce manualmente |
| "Sesión no quedó activa" | 2FA Microsoft no completado | **Crítico**: Login WinForce redirige a Microsoft 2FA. El script `rotate_creds.py` **debe** manejar el flujo completo (ver nota abajo) |
| Agentes siguen fallando tras rotación | Proxy cachea cookies viejas | Reiniciar servicio: `sc stop JSWinProxy && sc start JSWinProxy` |
| Keyring no accesible | Usuario distinto al del servicio | Ejecutar `rotate_creds.py` como **mismo usuario** que corre el servicio (SYSTEM o usuario admin) |

---

## ⚠️ NOTA CRÍTICA: Login WinForce + Microsoft 2FA

**El login de WinForce redirige a `login.microsoftonline.com` para 2FA**.

Esto significa:
- `rotate_creds.py` **NO puede ser solo HTTP POST** a `acceso.php`
- Debe usar **Playwright/Selenium** o replicar el flujo completo OAuth2/SAML
- **Alternativa práctica (v1)**: Owner hace login **manual en navegador** dentro de la PC proxy → copia cookies `PHPSESSID` → script las inyecta en keyring

### Implementación Realista v1 (Híbrida)

```python
# rotate_creds.py v1 - Híbrido
def main():
    print("""
    PASO 1: Abre Chrome en ESTA PC (la del proxy)
    PASO 2: Ve a https://appwinforce.win.pe/login
    PASO 3: Inicia sesión con las NUEVAS credenciales (incluye 2FA Microsoft)
    PASO 4: Cuando estés en el dashboard, pulsa ENTER aquí
    """)
    input("Presiona ENTER cuando hayas iniciado sesión en el navegador... ")
    
    # Extraer cookies de la sesión del navegador (via Chrome DevTools Protocol o archivo)
    # O más simple: que el owner copie PHPSESSID manualmente
    php_sessid = getpass.getpass("Pega el valor de cookie PHPSESSID: ")
    
    # Validar que la cookie funciona
    api = ValidatorAPI()
    api._sesion.cookies.set("PHPSESSID", php_sessid, domain="appwinforce.win.pe")
    api._verificar_sesion_activa(api._sesion)
    
    # Guardar en keyring
    save_session_cookies({"PHPSESSID": php_sessid})
    print("✓ Credenciales rotadas (via cookie de sesión)")
```

**Esta es la única forma viable v1** sin replicar Microsoft 2FA. Documentado aquí para que futuros devs no pierdan tiempo intentando automatizar lo imposible.

---

## Checklist Rotación (Para Owner)

- [ ] Recibí nuevas credenciales WinForce (email)
- [ ] Hice RDP a PC proxy
- [ ] Abrí Chrome → login WinForce con nuevas credenciales (incluye 2FA Microsoft)
- [ ] Copié cookie `PHPSESSID` (F12 → Application → Cookies)
- [ ] Ejecuté `python -m validator_app.proxy.rotate_creds`
- [ ] Pegué `PHPSESSID` cuando pidió
- [ ] Verifiqué `curl /admin/status` → `logged_in: true`
- [ ] Probé validación desde un agente → funciona
- [ ] Borré credenciales viejas de mi portapapeles / notas