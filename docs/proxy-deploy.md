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

Después de instalar, ambos tokens **también** se pueden ver, copiar y rotar desde
la consola owner (panel "Credenciales del proxy") sin volver a este resumen — ver
[Recuperar o rotar los tokens desde la consola owner](#recuperar-o-rotar-los-tokens-desde-la-consola-owner).

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

## Construir los ejecutables en la PC oficial (desde cero)

Ensayado el 2026-09-18 en un clon limpio de `main` (commit `55952fb`): clon 3 s, `venv` +
dependencias 76 s, `build-owner.ps1` 60 s, `build.ps1` 45 s (≈3 min en total); `pytest`
en el clon: 157 passed; ambos `.exe` arrancan y responden.

Requisitos: Git, Python 3.14.7 con "Add to PATH", Internet.

```powershell
# Usar una carpeta CORTA (p. ej. C:\jsconnect): con rutas largas pip falla con
# "WinError 206: el nombre del archivo o la extensión es demasiado largo".
git clone https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage.git C:\jsconnect
cd C:\jsconnect
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File build-owner.ps1     # -> dist\JSConnect-Win-Owner.exe
powershell -ExecutionPolicy Bypass -File build.ps1           # -> dist\JSConnect-Win-Coverage.exe (agente)
git checkout -- validator_app/version.py                     # build.ps1 lo reescribe con el SHA
```

Después, en `dist\` junto al exe del owner: copiar `private_key.pem` (del pendrive),
restringir su ACL y **borrarla del pendrive**. Abrir `JSConnect-Win-Owner.exe`: debe decir
"Llave privada: disponible"; hacer una activación de control (huella de un agente →
código → activar).

Notas:
- Hay que **clonar** (no bajar un zip): `build.ps1` embebe `git rev-parse HEAD`; sin `.git`
  queda `unknown` y la comprobación de actualizaciones no coincide con el Release.
- El `.exe` que se distribuya a las 15 PC debe ser el que se publique en el Release
  (SHA-256 incluido): la app resuelve el commit real del tag del Release (`GET
  /commits/{tag}`, no `target_commitish` — ese campo es la rama, no un SHA; bug
  corregido 2026-09-25) y lo compara con el embebido. `publish-release.ps1` solo
  imprime el comando `gh release create`; si no hay `gh` instalado se sube a mano
  desde GitHub → Releases → Draft.
- Sin firma de código, Windows SmartScreen pedirá *Más información → Ejecutar de todas
  formas* la primera vez.
- El botón **Renovar sesion WinForce** de la consola owner empaquetada no se ha probado
  dentro del `.exe` (necesita Chromium/Playwright); en la PC del proxy usar la extensión o
  el icono del Escritorio (que corren desde el repo con `python`).

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

### Cómo consigue el trabajador el `.exe`

No hace falta `git` ni cuenta de GitHub para descargarlo: entra a la pestaña
**Releases** del repositorio en GitHub (`.../releases/latest`), y descarga el
asset **`JSConnect-Win-Coverage.exe`** de la versión más reciente — el nombre
ya lo distingue de `JSConnect-Win-Owner.exe`, que se publica en el mismo
release pero es para la consola del owner, no para los agentes. Ejecutarlo no
requiere instalación.

Si se prefiere distribuirlo por otro medio (WhatsApp, USB, carpeta compartida):
como WhatsApp bloquea archivos `.exe` sueltos, hay que comprimirlo primero en
un `.zip`. Esto **no rompe el chequeo de actualizaciones** — la app compara el
commit embebido en el propio `.exe` contra el último Release, sin importar por
qué canal llegó a la PC — siempre que sea una copia íntegra de un build real
(no un `.exe` recortado o re-empaquetado).

### Opción A: Configuración manual (una vez por máquina)
1. Activar la PC: **Copiar huella** en el agente → generar/copiar código en
   `JSConnect-Win-Owner.exe` → **Pegar código** y **Activar** en el agente.
2. Ejecutar `JSConnect-Win-Coverage.exe`
3. Menú **⚙️ Configuración** → **Configurar Proxy**
4. Ingresar:
   - **URL del proxy**: `http://192.168.1.50:8080` — **nunca `localhost`** (el
     agente corre en otra PC: `localhost` ahí apunta al propio agente, no al
     proxy, y da `WinError 10061`). La IP correcta se copia con el botón
     **Copiar** junto a "URL para los agentes" en `JSConnect-Win-Owner.exe`
     (la detecta sola); si hace falta a mano, `ipconfig` en la PC del proxy →
     dirección IPv4.
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

## Recuperar o rotar los tokens desde la consola owner

`JSConnect-Win-Owner.exe` tiene un panel **"Credenciales del proxy"** con, por cada
token, botones **Mostrar** / **Copiar** / **Rotar**. Requiere correr la consola en
la **misma PC que el servicio del proxy** (el admin key solo se acepta desde
`127.0.0.1`, ver Troubleshooting) y pide un aviso UAC de administrador cada vez
que se usa (`config.yaml` tiene ACL de SYSTEM+Administradores). Antes de pedir el
UAC, la consola pide su propia confirmacion (para que Windows no sorprenda con el
aviso incluso si se abrio con doble clic, sin "Ejecutar como administrador").

- **Mostrar**: revela el valor 30 s y luego se oculta solo; no queda en pantalla.
- **Copiar**: copia al portapapeles y lo limpia solo a los 60 s.
- **Rotar**: avisa que se pedira UAC, genera un valor nuevo, reescribe
  `config.yaml` + el `.txt`, reaplica la ACL y reinicia el servicio; el mensaje
  final indica donde colocar el valor nuevo. Rotar el **proxy token** invalida el
  de todos los agentes ya configurados (hay que recargarles el nuevo desde ⚙
  Configuracion → Configurar Proxy, igual que con **R** en el instalador); rotar
  el **admin key** solo afecta a esta consola y a scripts de administracion.

No hace falta abrir `config.yaml` a mano ni tener a la vista el resumen final del
instalador. **`private_key.pem` no aparece aquí ni en ningún otro lugar de la
consola** — es la única credencial no rotable, y su exposición se maneja aparte
(ver "Qué llevar a la PC owner").

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
| Agentes: "Proxy auth failed" | Token distinto / IP no en allowed_networks | Verificar token en keyring agente = config.yaml proxy (consola owner → panel Credenciales → Mostrar) |
| `/admin/*` responde 403 desde otra PC | El admin key solo se acepta desde `127.0.0.1` (evita que viaje por LAN: expone el proxy_token vía `/admin/config`) | Usar la consola owner en la propia PC del proxy, o `rotate_creds.py`/scripts locales |
| Agente: "No se pudo conectar al proxy" con `WinError 10061` | Se configuró `http://localhost:8080` (o `127.0.0.1`) en un agente que corre en otra PC — ahí `localhost` apunta al propio agente, no al proxy | Copiar la IP real desde `JSConnect-Win-Owner.exe` ("URL para los agentes") y usarla en el agente; si sigue fallando, revisar el firewall del puerto en la PC del proxy |
| Un cambio en `server.py` o `config.yaml` no surte efecto | El servicio Python carga el código y la configuración solo al arrancar | Consola owner → **Reiniciar servicio** (pide UAC) o `Restart-Service JSWinProxy` como Administrador; la sesión WinForce persiste |
| Agente: "IP no permitida: <ip>" (403) | La IP que ve el proxy no está en `allowed_networks` (localhost siempre pasa) | Añadir su CIDR en `config.yaml` + `Restart-Service JSWinProxy`; las IP públicas del router NO se agregan |
| WinForce: sesión caducada | Tope absoluto o login expirado | Iniciar sesión y renovar desde extensión/consola owner |
| `install_service.bat` falla descarga winsw | Sin internet / GitHub bloqueado | Descargar `winsw.exe` manual a `validator_app/proxy/` y reintentar |
