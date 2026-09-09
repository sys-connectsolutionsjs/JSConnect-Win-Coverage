# JSConnect-Win-Coverage

Aplicación de escritorio para validar en instantes cobertura y score crediticio de clientes en un call center de un proveedor de internet.

---

## Español

### ¿Qué es?
Aplicación de escritorio para Windows que acelera la validación de clientes. Consulta en milisegundos:
- **Cobertura de servicio** a partir de coordenadas (latitud, longitud).
- **Score crediticio** por documento: DNI (8 dígitos), RUC (11 dígitos) o Carnet de Extranjería (9 caracteres, puede incluir letras).

En lugar de scrapear HTML, replica directamente las llamadas HTTP (JSON) a la API interna del sistema de validación, sin cargar página, sin mapa ni navegador.

### Arquitectura Actual (2026-08-25)
```
┌─────────────┐     LAN/VPN      ┌──────────────┐     HTTPS      ┌─────────────┐
│  20 Agentes │ ◄──────────────► │  Proxy Local │ ◄────────────► │  WinForce   │
│   (.exe)    │  Token compartido │  (PC Oficina)│  1 sesión      │  + Equifax  │
└─────────────┘                  └──────────────┘                └─────────────┘
                                    │
                              winsw service
                              FastAPI + uvicorn
                              Puerto 8080
```
- **Proxy Local (Opción B)**: Decidida tras detectar que WinForce redirige a Microsoft 2FA, haciendo inviable la concurrencia multi-máquina.
- 20 agentes LAN → 1 proxy → 1-2 sesiones WinForce desde una sola IP → sin riesgo de bloqueo.
- Sesión WinForce (cookie `PHPSESSID`) **solo en la PC del proxy** (Windows Keyring). Renovarla (≈1 vez por jornada, por el tope de sesión) = **doble clic en el icono "Renovar sesion WinForce" del Escritorio** → el encargado inicia sesión en la ventana que se abre y el script captura la cookie solo (sin F12, sin copiar/pegar). El login programático usuario/contraseña es inviable por el 2FA de Microsoft.
- Escalable a agentes remotos vía **Tailscale VPN** (mismo token, misma arquitectura, cero cambios de código).

### Características
- Consulta directa a la API interna (rápido y ligero).
- Entrada de coordenadas en formato `-11.956037627741102, -77.04065381800075`.
- Detección automática del tipo de documento (DNI/RUC/CE).
- Sesión automática: el proxy revalida y recarga la cookie del keyring cuando lleva >120s inactivo, mantiene la sesión viva con un *keepalive* "latido perezoso" (pinga WinForce solo si no hubo tráfico real de los agentes) y **verifica la cookie al arrancar**. Si la sesión muere pese al keepalive (tope absoluto ≈ 9.5 h por login): el owner recibe un **aviso automático** (popup en su escritorio vía tarea programada + toast de la extensión de Chrome), y los agentes reciben un **HTTP 503 claro** ("reintenta en unos minutos") en vez de un error opaco — el proxy no martillea WinForce mientras tanto.
- Credenciales guardadas cifradas con el Administrador de Credenciales de Windows (keyring).
- Sistema de activación por código RSA (solo personal autorizado).
- Botón de actualizaciones contra GitHub Releases.
- Ejecutable único, portable, anclable a la barra de tareas.
- **Nuevo**: Configuración de proxy via GUI (menú ⚙️ Configuración → Configurar Proxy).

### Requisitos
- Windows 10.
- Python 3.12+ (solo para desarrollo; el .exe final no necesita Python).
- **Para proxy (PC oficina)**: Python 3.12+, puerto 8080 libre, permisos de Administrador.

### Uso (Agentes)
1. Ejecuta `JSConnect-Win-Coverage.exe` (o `python main.py` en desarrollo).
2. Actívalo con el código proporcionado por el encargado.
3. **Primera vez**: Menú **⚙️ Configuración** → **Configurar Proxy** → ingresa IP:puerto del proxy + token → Probar conexión → Guardar.
4. Ingresa las coordenadas y/o el documento del cliente.
5. Pulsa **Validar** → resultado de cobertura y score al instante.

### Modo standalone (desarrollo / pruebas / owner — sin proxy)
Si no configuras proxy, la app va directa a WinForce. Como el login
usuario/contraseña es inviable por el 2FA de Microsoft: Menú **⚙️ Configuración →
Configurar Sesión (standalone)** → pega la cookie `PHPSESSID` de un login manual
en el navegador (F12 → Application → Cookies) → **Probar y guardar**. Se valida
contra WinForce y se guarda cifrada en el keyring. Cuando expire, vuelve a pegarla.
**No usar en los 20 agentes** (riesgo de bloqueo por sesiones concurrentes).

### Desarrollo
```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium   # solo para tools/captura.py
python main.py
```

### Build del .exe
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```
El build incluye `validator_app/proxy/client.py` (cliente proxy) pero **NO** `server.py` (solo corre en PC oficina).

### Publicar una versión (Release)
```powershell
powershell -ExecutionPolicy Bypass -File publish-release.ps1
```
El Release se publica con el .exe y su checksum SHA-256. La app detecta la nueva versión comparando el commit del Release con el embebido en el ejecutable.

### Instalación del Proxy (PC Oficina — una sola vez)
```powershell
# 1. Clonar repo en PC oficina
git clone https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage.git
cd JSConnect-Win-Coverage

# 2. Ejecutar como Administrador
.\validator_app\proxy\install_service.bat
```
El instalador:
- Verifica Python 3.12+ e instala dependencias (`requirements-proxy.txt`)
- Descarga `winsw.exe` automáticamente
- Genera `proxy_token` y `admin_key` seguros (auto)
- Crea `config.yaml` (gitignored) e instala servicio `JSWinProxy`
- Prueba `/health` y muestra tokens en consola + guarda en `proxy_token.txt` / `admin_key.txt`

Ver `docs/proxy-deploy.md` para detalles completos, firewall, rotación de credenciales y troubleshooting.

### Seguridad y avisos
- Cada usuario usa su propia credencial del sistema de validación (modo standalone) **O** el proxy centralizado (modo producción).
- **Producción = Proxy Local**: agentes no tienen credenciales WinForce; solo token proxy LAN.
- Sin certificado de firma, Windows SmartScreen pedirá **Más información → Ejecutar de todas formas** la primera vez.
- Repositorio público sin licencia: todos los derechos reservados (ver Licencia).
- **NUNCA en repo**: `config.yaml`, `proxy_token.txt`, `admin_key.txt`, `generator/private_key.pem`, `tools/captura.json`, `tools/js/`, credenciales reales.

### Licencia
Todos los derechos reservados. Este repositorio no incluye licencia de uso, modificación ni distribución.

### Implementaciones futuras
Mapa interactivo de cobertura · Ofertas/catálogo de venta · Instalador con auto-actualización · Servidor de activación en línea · Validación por lotes (CSV/Excel) · Historial/CRM básico. Detalle en `AGENTS.md`.

### Documentación técnica (permanente, en `docs/`)
- `arquitectura.md` — Diagrama + decisiones clave + flujo de datos
- `proxy-deploy.md` — Instalación paso a paso PC proxy
- `proxy-config.md` — Configuración agentes (GUI + script masivo)
- `rotacion-credenciales.md` — Proceso rotación WinForce (RDP v1 → VPN v2)
- `escalabilidad-remota.md` — Guía para futuros programadores (VPN + auto-discovery)

---

## English

### What is it?
A Windows desktop application that speeds up customer validation in an internet provider call center. It queries in milliseconds:
- **Service coverage** from coordinates (latitude, longitude).
- **Credit score** by document: DNI (8 digits), RUC (11 digits) or Foreigner Card (9 characters, may include letters).

Instead of scraping HTML, it directly replicates the HTTP (JSON) calls to the provider's internal validation API — no page loading, no map, no browser.

### Current Architecture (2026-08-25)
```
┌─────────────┐     LAN/VPN      ┌──────────────┐     HTTPS      ┌─────────────┐
│  20 Agents  │ ◄──────────────► │  Local Proxy │ ◄────────────► │  WinForce   │
│   (.exe)    │  Shared token    │  (Office PC) │  1 session     │  + Equifax  │
└─────────────┘                  └──────────────┘                └─────────────┘
                                    │
                              winsw service
                              FastAPI + uvicorn
                              Port 8080
```
- **Local Proxy (Option B)**: Decided after discovering WinForce redirects to Microsoft 2FA, making multi-machine concurrency unfeasible.
- 20 LAN agents → 1 proxy → 1-2 WinForce sessions from single IP → no blocking risk.
- WinForce session (`PHPSESSID` cookie) **only on proxy PC** (Windows Keyring). Renewing it (≈once per workday, due to the session cap) = **double-click the "Renovar sesion WinForce" desktop icon** → the manager logs in on the window that opens and the script captures the cookie by itself (no F12, no copy/paste). Programmatic username/password login is unfeasible due to Microsoft 2FA.
- Scalable to remote agents via **Tailscale VPN** (same token, same architecture, zero code changes).

### Features
- Direct internal API calls (fast and lightweight).
- Coordinates input as `-11.956037627741102, -77.04065381800075`.
- Automatic document type detection (DNI/RUC/CE).
- Automatic session management: the proxy revalidates and reloads the keyring cookie when idle >120s, keeps the session warm with a "lazy heartbeat" keepalive (it pings WinForce only when agents produced no real traffic), and **verifies the cookie on startup**. If the session dies despite the keepalive (absolute ≈9.5 h cap per login): the owner gets an **automatic alert** (desktop popup via a scheduled task + Chrome-extension toast), and agents get a **clear HTTP 503** ("retry in a few minutes") instead of an opaque error — the proxy stops hammering WinForce meanwhile.
- Credentials stored encrypted via Windows Credential Manager (keyring).
- Activation-code licensing (authorized staff only).
- Update button against GitHub Releases.
- Single portable executable, pinnable to the taskbar.
- **New**: Proxy configuration via GUI (menu ⚙️ Configuración → Configurar Proxy).

### Requirements
- Windows 10.
- Python 3.12+ (development only; the final .exe does not need Python).
- **For proxy (office PC)**: Python 3.12+, port 8080 free, Administrator permissions.

### Usage (Agents)
1. Run `JSConnect-Win-Coverage.exe` (or `python main.py` in development).
2. Activate with the code provided by the manager.
3. **First time**: Menu **⚙️ Configuración** → **Configurar Proxy** → enter proxy IP:port + token → Test connection → Save.
4. Enter the coordinates and/or the customer document.
5. Press **Validate** → coverage and score results instantly.

### Standalone mode (dev / testing / owner — no proxy)
Without a proxy configured, the app talks to WinForce directly. Since
username/password login is unfeasible (Microsoft 2FA): menu **⚙️ Configuración →
Configurar Sesión (standalone)** → paste the `PHPSESSID` cookie from a manual
browser login (F12 → Application → Cookies) → **Probar y guardar**. It is
validated against WinForce and stored encrypted in the keyring; re-paste it when
it expires. **Do not use on the 20 agents** (concurrent-session block risk).

### Development
```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium   # only for tools/captura.py
python main.py
```

### Build the .exe
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```
The build includes `validator_app/proxy/client.py` (proxy client) but **NOT** `server.py` (runs only on office PC).

### Publish a release
```powershell
powershell -ExecutionPolicy Bypass -File publish-release.ps1
```
The release includes the .exe and its SHA-256 checksum. The app detects a new version by comparing the release commit with the one embedded in the executable.

### Proxy Installation (Office PC — one time)
```powershell
# 1. Clone repo on office PC
git clone https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage.git
cd JSConnect-Win-Coverage

# 2. Run as Administrator
.\validator_app\proxy\install_service.bat
```
The installer:
- Verifies Python 3.12+ and installs deps (`requirements-proxy.txt`)
- Downloads `winsw.exe` automatically
- Generates secure `proxy_token` and `admin_key` (auto)
- Creates `config.yaml` (gitignored) and installs `JSWinProxy` service
- Tests `/health` and shows tokens in console + saves to `proxy_token.txt` / `admin_key.txt`

See `docs/proxy-deploy.md` for full details, firewall, credential rotation, and troubleshooting.

### Security & notices
- Each user uses their own validation-system credentials (standalone mode) **OR** the centralized proxy (production mode).
- **Production = Local Proxy**: agents have no WinForce credentials; only LAN proxy token.
- Without a signing certificate, Windows SmartScreen will ask for **More info → Run anyway** on first launch.
- Public repository with no license: all rights reserved (see License).
- **NEVER in repo**: `config.yaml`, `proxy_token.txt`, `admin_key.txt`, `generator/private_key.pem`, `tools/captura.json`, `tools/js/`, real credentials.

### License
All rights reserved. This repository carries no license to use, modify or distribute its contents.

### Future implementations
Interactive coverage map · Sales offers/catalog · Installer with auto-update · Online activation server · Batch validation (CSV/Excel) · Basic history/CRM. Details in `AGENTS.md`.

### Technical documentation (permanent, in `docs/`)
- `arquitectura.md` — Diagram + key decisions + data flow
- `proxy-deploy.md` — Step-by-step proxy PC installation
- `proxy-config.md` — Agent configuration (GUI + mass deploy script)
- `rotacion-credenciales.md` — WinForce credential rotation process (RDP v1 → VPN v2)
- `escalabilidad-remota.md` — Guide for future programmers (VPN + auto-discovery)