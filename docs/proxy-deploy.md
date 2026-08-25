# Despliegue del Proxy en PC Oficina

> Guía paso a paso para instalar y configurar el proxy en la PC fija de la oficina.

---

## Prerrequisitos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Windows | 10/11 Pro/Enterprise | PC fija, encendida en horario laboral |
| Python | 3.13+ | En PATH del sistema (`python --version`) |
| Git | Cualquiera | Para clonar repo |
| Puerto 8080 | Libre en firewall | `install_service.bat` verifica y permite cambiar |
| Permisos | Administrador local | Para instalar servicio Windows |

---

## Instalación (One-Click)

```powershell
# 1. Clonar repo (o copiar carpeta validator_app/proxy/)
git clone https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage.git
cd JSConnect-Win-Coverage

# 2. Ejecutar instalador como Administrador
# Click derecho en install_service.bat → "Ejecutar como administrador"
# O en PowerShell Admin:
.\validator_app\proxy\install_service.bat
```

### Qué hace `install_service.bat` (automático)

1. **Verifica Python 3.13+** en PATH
2. **Instala dependencias**: `pip install -r requirements-proxy.txt`
3. **Descarga `winsw.exe`** desde GitHub releases (última versión)
4. **Genera tokens seguros**:
   - `proxy_token` = `secrets.token_hex(32)` (64 chars hex)
   - `admin_key` = `secrets.token_hex(32)` (64 chars hex)
5. **Crea `config.yaml`** (gitignored) con tokens + configuración
6. **Genera `winsw.xml`** con paths correctos absolutos
7. **Instala servicio**: `winsw.exe install`
8. **Inicia servicio**: `winsw.exe start`
9. **Prueba health check**: `curl http://localhost:8080/health`
10. **Muestra resumen** en consola:
    ```
    ========================================
    PROXY INSTALADO CORRECTAMENTE
    ========================================
    Servicio: JSWinProxy (JSConnect Win Proxy)
    Puerto: 8080
    Health: http://localhost:8080/health
    
    TOKEN PROXY (distribuir a agentes):
    a1b2c3d4e5f6... (64 chars)
    
    ADMIN KEY (guardar seguro, solo owner):
    f6e5d4c3b2a1... (64 chars)
    
    Archivos generados (gitignored):
    - config.yaml
    - proxy_token.txt
    - admin_key.txt
    ========================================
    ```

---

## Verificación Post-Instalación

```powershell
# 1. Verificar servicio corriendo
sc query JSWinProxy
# STATE: RUNNING

# 2. Health check local
curl http://localhost:8080/health
# {"status":"ok","version":"<commit-sha>","session_age":0,"logged_in":false}

# 3. Health check desde otra máquina LAN
curl http://<IP-PC-OFICINA>:8080/health

# 4. Ver logs (Visor de Eventos)
# Aplicaciones y Servicios → JSWinProxy
```

---

## Configuración de Agentes (20 máquinas)

### Opción A: Configuración manual (una vez por máquina)
1. Ejecutar `JSConnect-Win-Coverage.exe`
2. Menú **⚙️ Configuración** → **Configurar Proxy**
3. Ingresar:
   - **IP:puerto**: `192.168.1.50:8080` (IP de la PC oficina)
   - **Token**: `a1b2c3d4e5f6...` (el token mostrado al instalar proxy)
4. Click **Probar conexión** → debe mostrar "OK (45ms)" en verde
5. Click **Guardar**

### Opción B: Configuración masiva (script)
```powershell
# En cada máquina (requiere keyring accesible)
python -c "
import keyring
keyring.set_password('JSWinClient', 'proxy_token', 'a1b2c3d4e5f6...')
keyring.set_password('JSWinClient', 'proxy_url', 'http://192.168.1.50:8080')
"
```

---

## Firewall (Windows Defender)

```powershell
# En PC proxy (como Admin): permitir puerto 8080 entrante
New-NetFirewallRule -DisplayName "JSWinProxy API" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow -Profile Domain,Private
```

---

## Rotación de Credenciales WinForce (Cada 1-2 meses)

Ver `docs/rotacion-credenciales.md` — proceso detallado.

Resumen rápido:
1. Owner hace **RDP a PC proxy**
2. Ejecuta: `python -m validator_app.proxy.rotate_creds`
3. Ingresa nuevo usuario/contraseña WinForce
4. Script hace login → verifica sesión → guarda cookies en keyring
5. Listo: siguientes validaciones usan credenciales nuevas

---

## Backup y Recuperación

| Qué | Dónde | Frecuencia |
|-----|-------|------------|
| `config.yaml` | `validator_app/proxy/config.yaml` | Tras cada cambio |
| `proxy_token.txt` | `validator_app/proxy/proxy_token.txt` | Una vez (instalación) |
| `admin_key.txt` | `validator_app/proxy/admin_key.txt` | Una vez (instalación) |
| Keyring credenciales WinForce | Windows Credential Manager (usuario que corre servicio) | Automático tras rotación |

**Para migrar a otra PC**:
1. Copiar `config.yaml`, `proxy_token.txt`, `admin_key.txt`
2. Ejecutar `install_service.bat` en nueva PC (detecta config existente → no regenera tokens)
3. Actualizar IP en agentes (o DNS interno `proxy.oficina.local`)

---

## Desinstalación

```powershell
# Como Administrador
.\validator_app\proxy\uninstall_service.bat
# Detiene servicio, lo desinstala, borra winsw.exe
# NO borra config.yaml / proxy_token.txt / admin_key.txt (manual si se desea)
```

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `sc query JSWinProxy` → STATE: STOPPED | Puerto ocupado / Python no en PATH / deps faltantes | Ver logs en Visor de Eventos → JSWinProxy |
| `curl /health` → Connection refused | Servicio no inició / firewall bloquea | `sc start JSWinProxy` + firewall rule |
| Agentes: "Proxy auth failed" | Token distinto / IP no en allowed_networks | Verificar token en keyring agente = config.yaml proxy |
| WinForce: "Credenciales incorrectas" | Credenciales rotadas / expiradas | Ejecutar `rotate_creds.py` via RDP |
| `install_service.bat` falla descarga winsw | Sin internet / GitHub bloqueado | Descargar `winsw.exe` manual a `validator_app/proxy/` y reintentar |