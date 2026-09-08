# JSConnect Win Proxy - Guía Rápida de Despliegue

> Resumen ejecutivo para el owner/administrador. Ver `docs/proxy-deploy.md` para detalles completos.

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
1. ✅ Verifica Python 3.12+
2. ✅ Instala dependencias (`requirements-proxy.txt`)
3. ✅ Descarga `winsw.exe` (service wrapper)
4. ✅ Genera tokens seguros (`proxy_token` + `admin_key` = 64 chars hex cada uno)
4. ✅ Crea `config.yaml` (gitignored)
5. ✅ Genera `winsw.xml` con paths absolutos
6. ✅ Instala servicio `JSWinProxy` (auto-inicio, auto-restart)
7. ✅ Inicia servicio y prueba `/health`
8. ✅ **Muestra tokens en consola** + guarda en `proxy_token.txt` / `admin_key.txt`

---

## Tokens Generados (COPIAR Y GUARDAR SEGURO)

```
========================================
TOKEN PROXY (distribuir a 20 agentes):
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

## Configuración de los 20 Agentes

### Opción A: Via GUI (usuario final)
1. Ejecutar `JSConnect-Win-Coverage.exe`
2. Menú **⚙️ Configuración** → **Configurar Proxy**
3. Ingresar:
   - **IP:puerto**: `192.168.1.50:8080` (IP de la PC oficina)
   - **Token**: `a1b2c3d4e5f6...` (token de arriba)
4. Click **Probar conexión** → "✓ OK (45ms)"
5. Click **Guardar**

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
# Como Administrador en PC proxy
New-NetFirewallRule -DisplayName "JSWinProxy API" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow -Profile Domain,Private
```

---

## Renovar / Rotar la Sesión WinForce

Ver `docs/rotacion-credenciales.md` para detalles completos.

### Login asistido (por defecto — renovación diaria y cambio de credenciales)
1. En la PC del proxy, **doble clic en "Renovar sesion WinForce"** (Escritorio).
2. Se abre el **Google Chrome instalado** (perfil dedicado) → el owner inicia
   sesión (incluye Microsoft el 1er login del día).
3. La barra superior se pone **verde** → cerrar la ventana → cuadro "✓ Sesión renovada".

Sin consola, sin F12. El `.lnk` lo crea `install_service.bat`; corre
`pythonw.exe -m validator_app.proxy.rotate_creds`. La **primera vez** conviene
iniciar sesión en Chrome (cuenta de Google) o guardar la contraseña de Microsoft
en esa ventana → luego se autocompleta y solo hay que aprobar el 2FA. Ver
`docs/rotacion-credenciales.md`.

### Fallback manual (si Playwright se rompe)
```powershell
python -m validator_app.proxy.rotate_creds --manual    # pide pegar PHPSESSID (F12)
python -m validator_app.proxy.rotate_creds --fresh      # asistido, perfil limpio
python -m validator_app.proxy.rotate_creds --preview    # probar la ventana, sin guardar nada
curl http://localhost:8080/admin/status                # verificar: logged_in: true
```

---

## Comandos Útiles

```powershell
# Ver estado servicio
sc query JSWinProxy

# Ver logs
# Visor de Eventos -> Applications and Services Logs -> JSWinProxy

# Detener/Iniciar/Reiniciar
.\validator_app\proxy\winsw.exe stop
.\validator_app\proxy\winsw.exe start
.\validator_app\proxy\winsw.exe restart

# Desinstalar
.\validator_app\proxy\uninstall_service.bat

# Renovar la sesion WinForce (o doble clic en el icono del Escritorio)
python -m validator_app.proxy.rotate_creds           # asistido (navegador)
python -m validator_app.proxy.rotate_creds --manual  # pegar PHPSESSID a mano

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
├── rotate_creds.py          # CLI renovar sesión: asistido (default) / --manual
├── login_asistido.py        # Captura la PHPSESSID con navegador (Playwright)
├── .browser_profile/        # GITIGNORED - perfil persistente del login asistido
├── server.py                # FastAPI app (en repo)
├── client.py                # Cliente agentes (en repo, va en .exe)
├── config.py                # Pydantic Settings (en repo)
└── __init__.py
```

---

## Troubleshooting Rápido

| Síntoma | Solución |
|---------|----------|
| `sc query` → STOPPED | Ver logs en Visor de Eventos → JSWinProxy |
| `curl /health` → Connection refused | `sc start JSWinProxy` + firewall rule |
| Agentes: "401 Unauthorized" | Token distinto en agente vs `config.yaml` |
| Agentes: "403 Forbidden" | IP no en `allowed_networks` (verifica LAN/VPN) |
| WinForce: sesión muerta / `session_dead_since` en `/admin/status` | Doble clic en "Renovar sesion WinForce" (o `rotate_creds --manual`) |
| "Playwright no está instalado" al renovar | `python -m playwright install chromium` (o re-correr `install_service.bat`) |
| `install_service.bat` falla descarga winsw | Descargar manual de GitHub releases → `validator_app/proxy/winsw.exe` |

---

## Escalabilidad Futura (Agentes Remotos)

Cuando haya vendedores en campo / home office:

1. Instalar **Tailscale** en PC proxy + laptops (1-click, gratis ≤100 devices)
2. Agentes usan IP Tailscale del proxy (`100.64.x.y:8080`) + **mismo token**
3. Cero cambios de código, misma arquitectura

Ver `docs/escalabilidad-remota.md` y `Escalabilidad.md` para guía completa.