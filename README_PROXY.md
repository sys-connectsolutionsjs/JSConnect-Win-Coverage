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
1. ✅ Verifica Python 3.13+
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

## Rotación de Credenciales WinForce (Cada 1-2 Meses)

Ver `docs/rotacion-credenciales.md` para detalles completos.

### Resumen (v1 - RDP Híbrido):
1. Owner recibe nuevas credenciales WinForce
2. **RDP a PC proxy**
3. Abre Chrome → `https://appwinforce.win.pe/login` → Login con NUEVAS credenciales (incluye 2FA Microsoft)
4. F12 → Application → Cookies → Copia `PHPSESSID` (Value)
5. Ejecuta: `python -m validator_app.proxy.rotate_creds`
6. Pega `PHPSESSID` cuando pida
7. Verifica: `curl http://localhost:8080/admin/status` → `logged_in: true`

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

# Rotar credenciales (RDP)
python -m validator_app.proxy.rotate_creds

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
├── rotate_creds.py          # CLI rotación (en repo)
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
| WinForce: "Credenciales incorrectas" | Ejecutar `rotate_creds.py` via RDP |
| `install_service.bat` falla descarga winsw | Descargar manual de GitHub releases → `validator_app/proxy/winsw.exe` |

---

## Escalabilidad Futura (Agentes Remotos)

Cuando haya vendedores en campo / home office:

1. Instalar **Tailscale** en PC proxy + laptops (1-click, gratis ≤100 devices)
2. Agentes usan IP Tailscale del proxy (`100.64.x.y:8080`) + **mismo token**
3. Cero cambios de código, misma arquitectura

Ver `docs/escalabilidad-remota.md` y `Escalabilidad.md` para guía completa.