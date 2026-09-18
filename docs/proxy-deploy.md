# Despliegue del Proxy en PC Oficina

> Guía paso a paso para instalar y configurar el proxy en la PC fija de la oficina.

---

## Prerrequisitos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Windows | 10/11 Pro/Enterprise | PC fija, encendida en horario laboral |
| Python | 3.14.7 recomendado; mínimo 3.12 | En PATH del sistema (`python --version`) |
| Git | Cualquiera | Para clonar repo |
| Puerto 8080 | Libre en firewall | `install_service.bat` verifica y permite cambiar |
| Permisos | Administrador local | Para instalar servicio Windows |

---

## Instalación (One-Click)

### Preparar la consola del owner

La llave privada no viene en el clon. Transfiere `private_key.pem` por un canal
privado, guárdala como `generator/private_key.pem` para ejecutar desde fuente o
como `dist/private_key.pem` junto a `JSConnect-Win-Owner.exe`, y limita su ACL al
owner, SYSTEM y Administradores. Antes de instalar el proxy, genera un código
para una huella de prueba y confirma la activación en el agente.

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

El instalador es **re-ejecutable sin riesgo**: cada paso comprueba si ya está hecho
(dependencias, Chromium, `winsw.exe`, tokens/`config.yaml`, servicio instalado y en
ejecución, tarea de aviso, icono del Escritorio), lo salta con "ya estaba" y
continúa; al final muestra un resumen "hecho ahora / ya estaba" por paso. La
ventana no se cierra sola: se relanza en `cmd /k`.

Si ya hay tokens (`config.yaml`), el paso 5 lo avisa y pregunta: **C** conserva
(por defecto tras 20 s; los agentes ya configurados siguen funcionando) o **R**
regenera (tokens nuevos, se reinicia el servicio y hay que reconfigurar cada
agente).

1. **Verifica Python 3.12+** en PATH
2. **Instala dependencias** desde la raíz del repositorio
3. **Instala Chromium** para el login asistido de fallback
4. **Descarga `winsw.exe` v2.12.0** con `curl.exe` y fallback TLS 1.2
5. **Genera tokens seguros**:
   - `proxy_token` = `secrets.token_hex(32)` (64 chars hex)
   - `admin_key` = `secrets.token_hex(32)` (64 chars hex)
6. **Crea `config.yaml`** (gitignored) con tokens + configuración y ACL
7. **Empaqueta y registra la política de la extensión de Chrome**. Chrome solo la
   aplica en PC gestionadas (dominio o Azure AD, p. ej. Windows 10 Pro unido a
   dominio); en Windows Home/WORKGROUP la ignora. El instalador lo detecta, avisa
   en el paso 7 **sin detenerse** y al final imprime cómo instalarla a mano
   (`chrome://extensions` → Modo de desarrollador → Cargar descomprimida →
   `validator_app\proxy\.extension_build`). Alternativa sin Chrome: el icono
   "Renovar sesion WinForce" del Escritorio.
8. **Genera `winsw.xml`** con paths absolutos
9. **Instala e inicia el servicio**
10. **Prueba el health check**
11. **Crea la tarea de aviso y la fuente de eventos**
12. **Crea el acceso directo de renovación y muestra el resumen**:
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

## Qué llevar a la PC owner (pendrive)

Casi todo se regenera solo desde Git/Internet. **Lo único imposible de regenerar es la
llave privada.**

| Llevar | Por qué |
|---|---|
| **`private_key.pem`** (obligatorio) | Firma los códigos de activación. Va en `dist\private_key.pem` junto a `JSConnect-Win-Owner.exe` (o `generator\private_key.pem`). **No** generar otra: los agentes ya construidos verifican con la llave pública actual. Copiarla por canal privado, restringir su ACL y **borrarla del pendrive** después. |
| `JSConnect-Win-Owner.exe` (recomendado) | No se publica en Releases; evita instalar el entorno de build en esa PC. Se construye con `build-owner.ps1`. |
| `JSConnect-Win-Coverage.exe` (opcional) | Para probar como agente en esa PC. Para las 15 PC usar el Release de GitHub (`publish-release.ps1`). |
| Instalador de Python 3.14.7 (opcional) | Si la PC no tiene Internet estable. Con "Add to PATH". |

**No llevar** (se regeneran o son específicos de cada PC): `config.yaml`,
`proxy_token.txt`, `admin_key.txt` (el instalador crea tokens nuevos en esa PC; no
reutilizar los de un ensayo), `winsw.exe` (se descarga), `extension.pem`/`.crx`/
`updates.xml`/`.extension_build` (se regeneran), `.venv`, `build/`, `*.spec`, `logs/`,
`.browser_profile/` (perfil de login: no compartir), `activacion.dat` (activación por
PC) ni entradas del Credential Manager (`JSWinProxy`, `JSWinClient`, `JSWinCoverage`).
La sesión de WinForce se inicia de nuevo en esa PC.

Además de la carpeta del repo (`git clone` o copia): Git, Python 3.14.7 e Internet
(Chromium ~150 MB y `winsw.exe` se descargan en la instalación).

---

## Verificación Post-Instalación

```powershell
# 1. Verificar servicio corriendo
sc query JSWinProxy
# STATE: RUNNING

# 2. Health check local
curl http://localhost:8080/health
# {"status":"ok","version":"dev","session_age":0,"logged_in":false,"session_alive":false}

# 3. Health check desde otra máquina LAN
curl http://<IP-PC-OFICINA>:8080/health

# 4. Ver logs de proceso
Get-ChildItem .\logs\

# Los eventos 101/102 del Visor de Eventos son solo alertas de sesión
```

---

## Configuración de Agentes (20 máquinas)

### Opción A: Configuración manual (una vez por máquina)
1. Activar la PC: **Copiar huella** en el agente → generar/copiar código en
   `JSConnect-Win-Owner.exe` → **Pegar código** y **Activar** en el agente.
2. Ejecutar `JSConnect-Win-Coverage.exe`
3. Menú **⚙️ Configuración** → **Configurar Proxy**
4. Ingresar:
   - **URL del proxy**: `http://192.168.1.50:8080`
   - **Token**: `a1b2c3d4e5f6...` (el token mostrado al instalar proxy)
5. Click **Probar conexión** → debe informar proxy conectado y estado de sesión
6. Click **Guardar**

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

## Renovación de la Sesión WinForce

Ver `docs/rotacion-credenciales.md` — proceso detallado.

Resumen rápido:
1. El owner inicia sesión normalmente en WinForce, con 2FA si corresponde.
2. Pulsa la extensión **Renovar sesión WinForce** en su Chrome cotidiano.
3. Como fallback, usa el botón de la consola owner o el acceso directo del
   Escritorio; ambos abren el login asistido.
4. La cookie se valida y se envía por HTTP al proceso LocalSystem, que la guarda
   en su propio keyring. No se guardan usuario ni contraseña.

---

## Backup y Recuperación

| Qué | Dónde | Frecuencia |
|-----|-------|------------|
| `config.yaml` | `validator_app/proxy/config.yaml` | Tras cada cambio |
| `proxy_token.txt` | `validator_app/proxy/proxy_token.txt` | Una vez (instalación) |
| `admin_key.txt` | `validator_app/proxy/admin_key.txt` | Una vez (instalación) |
| Keyring de sesión WinForce | Windows Credential Manager de LocalSystem | Automático tras renovación |
| `private_key.pem` | Solo estación owner, fuera de Git | Transferencia privada + ACL restringida |

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
| `sc query JSWinProxy` → STATE: STOPPED | Puerto ocupado / Python no en PATH / deps faltantes | Revisar `<repo>\logs\` |
| `curl /health` → Connection refused | Servicio no inició / firewall bloquea | `sc start JSWinProxy` + firewall rule |
| Agentes: "Proxy auth failed" | Token distinto / IP no en allowed_networks | Verificar token en keyring agente = config.yaml proxy |
| Un cambio en `server.py` o `config.yaml` no surte efecto | El servicio Python carga el código y la configuración solo al arrancar | Consola owner → **Reiniciar servicio** (pide UAC) o `Restart-Service JSWinProxy` como Administrador; la sesión WinForce persiste |
| Agente: "IP no permitida: <ip>" (403) | La IP que ve el proxy no está en `allowed_networks` (localhost siempre pasa) | Añadir su CIDR en `config.yaml` + `Restart-Service JSWinProxy`; las IP públicas del router NO se agregan |
| WinForce: sesión caducada | Tope absoluto o login expirado | Iniciar sesión y renovar desde extensión/consola owner |
| `install_service.bat` falla descarga winsw | Sin internet / GitHub bloqueado | Descargar `winsw.exe` manual a `validator_app/proxy/` y reintentar |
