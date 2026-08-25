# Configuración de Agentes (Cliente Proxy)

> Cómo configurar cada una de las 20 máquinas agente para usar el proxy local.

---

## Requisitos por Máquina

- Windows 10
- `JSConnect-Win-Coverage.exe` (última release)
- Acceso LAN a la PC proxy (puerto 8080)
- Token del proxy (entregado por owner al instalar proxy)

---

## Método 1: Via GUI (Recomendado, Usuario Final)

1. Ejecutar `JSConnect-Win-Coverage.exe`
2. Menú superior **⚙️ Configuración** → **Configurar Proxy**
3. Completar diálogo:
   ```
   ┌─────────────────────────────────────┐
   │ Configurar Proxy                    │
   ├─────────────────────────────────────┤
   │ IP:puerto del proxy:                │
   │ [ 192.168.1.50:8080            ]    │
   │                                     │
   │ Token:                              │
   │ [ **************************** ]    │
   │                                     │
   │ [ Probar conexión ]   [ Guardar ]   │
   └─────────────────────────────────────┘
   ```
4. Click **Probar conexión** → espera 2-3 segundos
   - ✅ Verde: "Conexión OK (45 ms)" → proxy responde, token válido
   - ❌ Rojo: "Error: ..." → revisar IP, token, firewall, servicio proxy
5. Click **Guardar** → credenciales guardadas en **Windows Keyring** local
6. La app usa proxy automáticamente en siguiente validación

### Qué se guarda en Keyring (por usuario Windows)
```
Servicio: JSWinClient
Usuario:  proxy_url      → "http://192.168.1.50:8080"
Usuario:  proxy_token    → "a1b2c3d4e5f6..." (token compartido)
```

---

## Método 2: Via Script (Despliegue Masivo / IT)

```powershell
# Ejecutar en cada máquina (PowerShell como usuario que usa la app)
# Requiere: Python 3.13+ con keyring instalado (pip install keyring)

$proxyUrl = "http://192.168.1.50:8080"
$proxyToken = "a1b2c3d4e5f67890..."  # 64 chars hex

python -c "
import keyring
keyring.set_password('JSWinClient', 'proxy_url', '$proxyUrl')
keyring.set_password('JSWinClient', 'proxy_token', '$proxyToken')
print('Configurado:', keyring.get_password('JSWinClient', 'proxy_url'))
"
```

### Via Batch (sin Python, usa `cmdkey` nativo)
```bat
@echo off
set PROXY_URL=http://192.168.1.50:8080
set PROXY_TOKEN=a1b2c3d4e5f67890...

:: cmdkey no guarda valores arbitrarios bien; mejor usar keyring via Python
:: Esta opción solo si no hay Python en agentes (raro)
```

---

## Verificación de Configuración

### Desde la App
1. Menú **⚙️ Configuración** → **Configurar Proxy**
2. Los campos vienen pre-rellenados desde keyring
3. Click **Probar conexión** → confirma que sigue funcionando

### Desde Línea de Comandos (Debug)
```powershell
# Ver qué hay en keyring
python -c "
import keyring
print('URL:', keyring.get_password('JSWinClient', 'proxy_url'))
print('Token:', keyring.get_password('JSWinClient', 'proxy_token')[:8] + '...')
"

# Test directo al proxy
curl -H "X-Proxy-Token: a1b2c3d4e5f6..." http://192.168.1.50:8080/health
```

---

## Modo Standalone (Sin Proxy)

Si **no hay configuración de proxy** guardada en keyring:
- La app usa `validator_app.core.api.ValidatorAPI` directo
- Requiere credenciales WinForce en keyring local (`JSWinCoverage`/`credentials`)
- **Útil para**: desarrollo, pruebas, owner validando solo
- **No usar en producción** (riesgo bloqueo por 20 sesiones concurrentes)

---

## Estructura de Configuración en Disco

| Archivo/Ubicación | Contenido | Quién escribe |
|-------------------|-----------|---------------|
| Windows Keyring (`JSWinClient`/`proxy_url`) | `http://192.168.1.50:8080` | GUI / Script despliegue |
| Windows Keyring (`JSWinClient`/`proxy_token`) | `a1b2c3d4e5f6...` | GUI / Script despliegue |
| `validator_app/proxy/config.yaml` (PC proxy) | Token + admin_key + settings | `install_service.bat` |
| `validator_app/proxy/proxy_token.txt` (PC proxy) | Token legible para owner | `install_service.bat` |

---

## Troubleshooting Agentes

| Error | Causa | Solución |
|-------|-------|----------|
| "Proxy no configurado" | Keyring vacío | Configurar via GUI o script |
| "Connection refused" | Proxy caído / IP incorrecta / Firewall | Verificar servicio proxy + firewall + IP |
| "401 Unauthorized" | Token incorrecto / expirado | Verificar token en keyring = `config.yaml` proxy |
| "403 Forbidden" | IP no en `allowed_networks` | Verificar red LAN / VPN; proxy config `allowed_networks` |
| "Timeout" | Proxy sobrecargado / WinForce lento | Reintentar; proxy tiene retry 3x backoff |
| "Score: error parsing" | WinForce cambió respuesta | Actualizar proxy (pull repo + rebuild service) |

---

## Para Futuros Programadores: Auto-Discovery (v2)

Cuando haya agentes remotos (VPN), no querrán configurar IP/token manualmente.

**Preparado en código**:
```python
# validator_app/proxy/client.py
class ProxyClient:
    @classmethod
    def from_discovery(cls) -> "ProxyClient":
        # 1. Descubrir proxy via DNS/mDNS/Config central
        # 2. GET http://<proxy>/admin/config → {proxy_url, token, timeouts}
        # 3. Auto-configurarse
        pass
```

**Endpoint proxy** (`GET /admin/config`):
```json
{
  "proxy_url": "http://192.168.1.50:8080",
  "token": "a1b2c3d4e5f6...",
  "timeouts": {"connect": 5, "read": 30},
  "version": "commit-sha"
}
```

**Requisitos para activar**:
- DNS interno `proxy.oficina.local` → IP proxy
- O VPN con DNS push
- Endpoint `/admin/config` público en LAN (sin auth, solo info de conexión)