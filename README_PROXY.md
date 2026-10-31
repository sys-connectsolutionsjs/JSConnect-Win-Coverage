# JSConnect Win Proxy - Guía Rápida de Despliegue

> Resumen ejecutivo para el owner/administrador. Ver [`docs/proxy-deploy.md`](docs/proxy-deploy.md) para detalles completos.

---

## Instalación One-Click (PC Oficina)

```powershell
# 1. Clonar repo
git clone https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage.git
cd JSConnect-Win-Coverage

# 2. Ejecutar COMO ADMINISTRADOR
.\validator_app\proxy\install_service.bat
```

### Qué hace el instalador automáticamente:
1. ✅ Verifica Python 3.12+ (producción recomendada: 3.14.7)
2. ✅ Instala dependencias y Chromium
3. ✅ Descarga `winsw.exe` v2.12.0
4. ✅ Genera tokens y `config.yaml` con ACL restringida
5. ✅ Empaqueta/fuerza-instala la extensión de Chrome
6. ✅ Genera `winsw.xml`, instala e inicia `JSWinProxy`
7. ✅ Prueba `/health`, abre el firewall y quita la suspensión con corriente (`[ENERGIA]`: la PC del proxy no debe dormirse)
8. ✅ Registra alertas de sesión y crea el acceso directo de renovación
9. ✅ Muestra y guarda los tokens en archivos gitignored

---

## Tokens Generados (COPIAR Y GUARDAR SEGURO)

```
========================================
TOKEN PROXY (distribuir a los agentes):
a1b2c3d4e5f6... (64 chars)
========================================
ADMIN KEY (solo owner - para /admin/*):
f6e5d4c3b2a1... (64 chars)
========================================
```

---

## Verificación Post-Instalación

```powershell
# Estado del servicio
sc query JSWinProxy
# STATE: RUNNING

# Health check local
curl http://localhost:8080/health
# {"status":"ok","version":"...","session_age":0,"logged_in":false}

# Health check desde otra máquina LAN
curl http://192.168.1.50:8080/health

# Swagger UI (documentación interactiva)
http://localhost:8080/docs
```

---

## Configuración de los Agentes (25 hoy, 41 previstos)

### Opción A: Via GUI (usuario final)
1. Activar la PC con el código que genera `JSConnect-Win-Owner.exe` para la
   huella copiada desde el agente.
2. Ejecutar `JSConnect-Win-Coverage.exe`
3. Menú **⚙️ Configuración** → **Configurar Proxy**
4. Ingresar:
   - **URL**: `http://192.168.1.50:8080`
   - **Token**: `a1b2c3d4e5f6...` (token de arriba)
5. Click **Probar conexión** → revisar conexión y estado de sesión
6. Click **Guardar**

### Opción B: Script masivo (IT)
```powershell
# En cada máquina (PowerShell como usuario de la app)
$proxyUrl = "http://192.168.1.50:8080"
$proxyToken = "a1b2c3d4e5f67890..."

python -c "
import keyring
keyring.set_password('JSWinClient', 'proxy_url', '$proxyUrl')
keyring.set_password('JSWinClient', 'proxy_token', '$proxyToken')
"
```

---

## Firewall (Windows Defender - PC Proxy)

```powershell
# Como Administrador en PC proxy (install_service.bat ya lo hace en el paso 11/13)
New-NetFirewallRule -DisplayName "JSWinProxy API" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow -Profile Any -RemoteAddress 192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,100.64.0.0/10
```

`-Profile Any` porque Windows 11 suele clasificar la red de la oficina como
**Pública** (con `Domain,Private` los agentes daban timeout); `-RemoteAddress`
limita el acceso a IP de LAN y Tailscale (los mismos rangos que `allowed_networks`).
Ver `actualizacion-windows-11/`.

---

## Renovar / Rotar la Sesión WinForce

Ver [`docs/rotacion-credenciales.md`](docs/rotacion-credenciales.md) para detalles completos.

### Autologin desatendido (vía principal desde 2026-10-28)
Con la credencial de la **cuenta dedicada** guardada, el proxy vuelve a entrar solo
cuando la sesión muere: Chromium dentro del servicio (la ventana no se ve), sin intervención del owner. Se configura
**una vez** (y de nuevo solo si WinForce cambia la contraseña): **consola owner → "Autologin de
WinForce" → Configurar...** (pide UAC), o respondiendo **S** a la pregunta del final de
`install_service.bat`. Para técnicos, en una consola de **Administrador**:
```powershell
python -m validator_app.proxy.rotate_creds --guardar-login   # usuario + contraseña -> keyring del servicio
python -m validator_app.proxy.autologin --probar             # opcional: login de prueba con ventana (no guarda nada)
curl http://localhost:8080/health                            # "login_configurado": true + bloque "autologin"
```
Solo se avisa al owner (popup, extensión, webhook) si el autologin falla, si Microsoft
rechaza la contraseña o si la sesión muere dos veces seguidas a minutos de entrar (otra
persona usa la cuenta → pausa). El **frenado** entre intentos fallidos (recomendado: al
instante, +1, +2, +3 min y luego cada 5) se cambia en la consola owner → **Frenado...**. La extensión y los fallbacks de abajo siguen
sirviendo para renovar a mano.

### Extensión de Chrome (renovación manual — el owner no sale de su navegador)
`install_service.bat` fuerza-instala la extensión **"Renovar sesion WinForce"** en
el Chrome de la PC. **Reabrir Chrome** una vez tras instalar.
1. El owner trabaja normal en Chrome (sesión de WinForce abierta como siempre).
2. Sesión del proxy muerta → **badge rojo `!`** en el icono de la extensión.
3. **Un clic** → notificación "Sesión del proxy renovada". Listo.

La extensión lee la `PHPSESSID` de su sesión (`chrome.cookies`, incl. HttpOnly) y
la manda a `POST 127.0.0.1:<puerto>/local/renovar` (sin admin key: es local).

### Fallbacks (técnico / proxy caído)
```powershell
# Icono "Renovar sesion WinForce" del Escritorio = login asistido (navegador aparte)
python -m validator_app.proxy.rotate_creds            # asistido
python -m validator_app.proxy.rotate_creds --manual   # pegar PHPSESSID a mano (F12)
python -m validator_app.proxy.rotate_creds --preview  # probar la ventana, sin guardar
python -m validator_app.proxy.rotate_creds --fresh    # asistido, perfil de navegador limpio
curl.exe -H "X-Admin-Key: <admin_key>" http://localhost:8080/admin/status
```

### Probar la extensión en desarrollo (sin la política de fuerza-instalación)

> También es la vía de instalación en una **PC no gestionada** (sin dominio/Azure AD),
> donde Chrome ignora la política. Usa la carpeta `validator_app/proxy/.extension_build`
> (trae el puerto real) en lugar de `extension/`.

1. **Cargar descomprimida**: `chrome://extensions` → activar "Modo de
   desarrollador" → "Cargar descomprimida" → `validator_app/proxy/extension`.
   (Chrome avisará "Desactiva las extensiones en modo de desarrollador" al abrir;
   normal en pruebas. En producción va fuerza-instalada por política y no pasa.)

2. **Proxy local** (raíz del repo, PowerShell):
   ```powershell
   $env:PROXY_PROXY_TOKEN = (python -c "import secrets;print(secrets.token_hex(32))")
   $env:PROXY_ADMIN_KEY   = (python -c "import secrets;print(secrets.token_hex(32))")
   python -m validator_app.proxy.server
   ```
   Con una `PHPSESSID` muerta en el keyring, `/local/estado` devuelve
   `session_alive: false` → la extensión pone el badge rojo `!`.

3. **Forzar el sondeo** sin esperar 5 min: `chrome://extensions` → clic en
   "service worker" de la extensión → en la consola: `revisarEstado()`.

4. **Plomería** (sin login en WinForce), en esa misma consola o con `curl` desde
   la PC (que es 127.0.0.1):
   ```js
   fetch("http://127.0.0.1:8080/local/estado").then(r=>r.json()).then(console.log)
   fetch("http://127.0.0.1:8080/local/renovar",{method:"POST",
     headers:{"Content-Type":"application/json"},
     body:JSON.stringify({php_sessid:"falsa"})}).then(r=>console.log(r.status)) // 401
   ```

5. **Clic real**: en ese Chrome, login completo en `https://appwinforce.win.pe`
   (SSO de Microsoft) → clic en el icono → notificación "Sesión del proxy renovada" →
   `curl -H "X-Admin-Key: $env:PROXY_ADMIN_KEY" http://localhost:8080/admin/status`
   muestra `session_alive: true`.

6. **Limpieza**: quitar la extensión descomprimida en `chrome://extensions`;
   Ctrl+C al proxy.

---

## Comandos Útiles

```powershell
# Ver estado servicio
sc query JSWinProxy

# Ver logs
Get-ChildItem .\logs\
# El Visor de Eventos contiene las alertas 101/102 de sesión, no stdout/stderr

# Detener/Iniciar/Reiniciar
.\validator_app\proxy\winsw.exe stop
.\validator_app\proxy\winsw.exe start
.\validator_app\proxy\winsw.exe restart

# Desinstalar
.\validator_app\proxy\uninstall_service.bat

# Renovar la sesion WinForce (o doble clic en el icono del Escritorio)
python -m validator_app.proxy.rotate_creds           # asistido (navegador)
python -m validator_app.proxy.rotate_creds --manual  # pegar PHPSESSID a mano

# Credencial del autologin (consola de Administrador; al cambiar la contraseña)
python -m validator_app.proxy.rotate_creds --guardar-login

# Ver config actual
type .\validator_app\proxy\config.yaml
```

---

## Estructura de Archivos (PC Proxy)

```
validator_app/proxy/
├── config.yaml              # GITIGNORED - config real con tokens
├── config.yaml.example      # Plantilla (en repo)
├── proxy_token.txt          # GITIGNORED - token legible para owner
├── admin_key.txt            # GITIGNORED - admin key legible
├── winsw.exe                # Descargado auto (no en repo)
├── winsw.xml                # Generado auto
├── install_service.bat      # Instalador (en repo)
├── uninstall_service.bat    # Desinstalador (en repo)
├── rotate_creds.py          # CLI renovar sesión (fallback): asistido / --manual / --guardar-login
├── login_asistido.py        # Captura la PHPSESSID con navegador (Playwright)
├── autologin.py             # Autologin desatendido (Chromium en el servicio) + freno anti-bucle
├── _instalar_extension.py   # Empaqueta + fuerza-instala la extensión de Chrome
├── extension/               # Extensión MV3 "Renovar sesion WinForce" (plantilla)
├── .browser_profile/        # GITIGNORED - perfil del login asistido
├── .browser_profile_servicio/ # GITIGNORED - perfil del autologin (SYSTEM)
├── .ms-playwright/          # GITIGNORED - Chromium compartido (servicio + owner)
├── .extension_build/ · extension.pem · extension.crx · updates.xml  # GITIGNORED
├── server.py                # FastAPI app + keepalive + endpoints /local/*
├── client.py                # Cliente agentes (en repo, va en .exe)
├── config.py                # Pydantic Settings (en repo)
└── __init__.py
```

---

## Troubleshooting Rápido

| Síntoma | Solución |
|---------|----------|
| `sc query` → STOPPED | Revisar `<repo>\logs\` |
| `curl /health` → Connection refused | `sc start JSWinProxy` + firewall rule |
| Agentes: "401 Unauthorized" | Token distinto en agente vs `config.yaml` |
| Agentes: "403 Forbidden" | IP no en `allowed_networks` (verifica LAN/VPN) |
| WinForce: sesión muerta / `session_dead_since` en `/admin/status` | Con credencial guardada el autologin la renueva solo (ver `autologin` en `/health`). Si no: badge rojo en la extensión → 1 clic. Fallback: icono del Escritorio o `rotate_creds --manual` |
| `/health` → `autologin.motivo: "credencial_invalida"` | Microsoft rechazó la contraseña: `rotate_creds --guardar-login` (Administrador) con la nueva |
| `/health` → `autologin.motivo: "pausado"` | La sesión murió 2 veces a minutos de entrar: alguien más usa la cuenta. Se reanuda solo tras el intervalo fijo del frenado (5 min en el recomendado); ver `logs/sesion_eventos.jsonl` |
| "Instalar extensión en Chrome" dice "la carpeta aún no está preparada" | Pulsa **Preparar carpeta** (UAC): arma `validator_app\proxy\.extension_build` con el puerto real. El instalador ahora la crea siempre, aunque no encuentre Chrome |
| Autologin falla siempre | Ver `logs/autologin_fallo.png` (pantalla donde se quedó) y probar `python -m validator_app.proxy.autologin --probar` |
| La extensión no aparece en Chrome | Reabrir Chrome. Si sigue: re-correr `python -m validator_app.proxy._instalar_extension` como Admin y ver que Chrome esté instalado |
| Extensión: "No se pudo contactar al proxy" | El servicio `JSWinProxy` está parado → `winsw.exe start` |
| "Playwright no está instalado" al usar el fallback | `python -m playwright install chromium` (o re-correr `install_service.bat`) |
| `install_service.bat` falla descarga winsw | Descargar manual de GitHub releases → `validator_app/proxy/winsw.exe` |

---

## Escalabilidad Futura (Agentes Remotos)

Cuando haya vendedores en campo / home office:

1. Instalar **Tailscale** en PC proxy + laptops (1-click, gratis ≤100 devices)
2. Agentes usan IP Tailscale del proxy (`100.64.x.y:8080`) + **mismo token**
3. Cero cambios de código, misma arquitectura

Ver [`docs/escalabilidad-remota.md`](docs/escalabilidad-remota.md) y [`Escalabilidad.md`](Escalabilidad.md) para guía completa.
