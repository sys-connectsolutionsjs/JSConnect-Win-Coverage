# Cambios por archivo (commit `5cb8768`)

Base: `7e800b0` (último commit del repo original). 10 archivos de código, 9 de
tests (1 nuevo). Para cada uno: **qué hacía**, **qué hace ahora**, **por qué**,
**riesgo**, **cómo revertir** y **qué test lo cubre**.

---

## 1. `validator_app/proxy/install_service.bat` (instalador del proxy)

Corre como Administrador en la PC oficina. Es re-ejecutable (cada paso detecta si
ya está hecho).

### 1a. Firewall — paso `[11/13]`
- **Antes:** `New-NetFirewallRule ... -Profile Domain,Private`. Si la regla ya
  existía, se saltaba sin revisarla.
- **Ahora:**
  ```bat
  set "FW_REMOTOS=192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,100.64.0.0/10"
  New-NetFirewallRule ... -Profile Any -RemoteAddress !FW_REMOTOS!
  ```
  Si la regla existe, se **actualiza** con `Set-NetFirewallRule` (puerto, perfil,
  rangos), no se salta.
- **Por qué:** Windows 11 clasifica las redes nuevas como **Públicas**. En esta PC
  la red "Red 3" es Pública → la regla `Domain,Private` no aplicaba → los agentes
  daban timeout. `-Profile Any` sola abriría el puerto a cualquiera en una red
  pública; por eso se limita a los mismos rangos que `allowed_networks` de
  `config.py` (LAN privada + Tailscale CGNAT).
- **Riesgo:** bajo. Si la LAN de la oficina usa un rango no privado (raro), habría
  que agregarlo a `FW_REMOTOS` y a `allowed_networks`.
- **Revertir:** volver a `-Profile Domain,Private` y quitar `-RemoteAddress`.
- **Test:** `tests/test_install_bat.py::test_firewall_cubre_red_publica_de_windows_11_solo_desde_lan`.

### 1b. ACL de `config.yaml` y tokens
- **Antes:** `icacls ... "BUILTIN\Administradores:F"`, con fallback a
  `Administrators` **solo** para `config.yaml`; los `.txt` sin fallback. Siempre
  imprimía `[OK]`.
- **Ahora:** `icacls ... *S-1-5-18:F *S-1-5-32-544:F` (SIDs de SYSTEM y
  Administradores) para los 3 archivos; si falla, `[WARN]`.
- **Por qué:** los nombres de grupo cambian con el idioma de Windows; los SIDs no.
- **Riesgo:** ninguno conocido (los SIDs son universales).
- **Test:** `test_acl_por_sid_independiente_del_idioma`.

### 1c. Detección de puerto ocupado — paso `[6/13]`
- **Antes:** `netstat -an | findstr ":!PROXY_PORT! "`. **Nunca funcionó**: cada
  lado de un pipe corre en un `cmd` hijo sin delayed expansion, así que `findstr`
  buscaba literalmente `:!PROXY_PORT! `. Además, al regenerar tokens, `ver >nul`
  dejaba errorlevel 0 y el puerto propio se reportaba "en uso".
- **Ahora:** subrutinas `:puerto_en_uso` (PowerShell
  `Get-NetTCPConnection -LocalPort N -State Listen`) y `:puerto_libre_forzado`.
- **Test:** `test_puerto_ocupado_no_usa_pipe_con_delayed_expansion`. Probado
  aparte en un `.bat` de prueba (ver `verificacion.md`).

### 1d. Health check
- **Antes:** `if %errorLevel% equ 0` **dentro** de un bloque → se expandía al leer
  el bloque (siempre 0) → siempre "[EXITO]". `curl` sin `-f` (un HTTP 500 contaba
  como éxito).
- **Ahora:** `curl -s -f` y `if !errorLevel! equ 0`.
- **Test:** `test_health_check_dentro_del_bloque_usa_errorlevel_diferido`.

### 1e. Python real para `pip` y el icono del Escritorio
- **Antes:** `pip install` (el primero del PATH, puede ser de otro Python) y
  `where pythonw.exe` (puede devolver el alias de Microsoft Store o nada).
- **Ahora:** `PYTHON_EXE` se resuelve con `sys.executable` justo después del
  paso 1; `"%PYTHON_EXE%" -m pip install ...`; `pythonw.exe` se toma de la misma
  carpeta que `PYTHON_EXE` (con `where` solo como respaldo).
- **Test:** `test_pip_e_icono_usan_el_interprete_real`.

---

## 2. `validator_app/activation/fingerprint.py` (huella de la PC)

- **Antes:** CPU y volumen con `wmic cpu get ProcessorId` y
  `wmic volume get DriveLetter,SerialNumber`. Sin `wmic`, en silencio: CPU =
  variable `PROCESSOR_IDENTIFIER` y volumen = vacío.
- **Ahora:**
  - Si **hay** `wmic` (Windows 10): exactamente igual que antes → **misma huella**.
  - Si **no hay** `wmic` (Windows 11 24H2+): una sola llamada a PowerShell/CIM
    (`Win32_Processor.ProcessorId` y el `SerialNumber` del primer `Win32_Volume`
    con letra) — **los mismos valores** que daba `wmic`, así que una PC que pasa de
    Windows 10 a 11 conserva su huella.
  - Nueva `huellas_compatibles()`: la huella actual + (sin `wmic`) la que se
    calculaba antes con el respaldo débil, para no invalidar activaciones viejas.
  - `CREATE_NO_WINDOW` en las llamadas.
- **Riesgo:** medio-bajo. Supuesto clave: CIM devuelve el mismo `ProcessorId` y el
  mismo orden de volúmenes que `wmic` (mismo proveedor WMI). Verificado en esta PC
  que el valor CIM es estable; **no** se pudo comparar contra `wmic` aquí porque
  esta PC ya no lo tiene.
- **Revertir:** `git checkout 7e800b0 -- validator_app/activation/fingerprint.py`
  (y revertir `main_window.py`, que usa `huellas_compatibles`).
- **Tests:** `tests/test_fingerprint.py` (nuevo, 5 tests): CIM sin ventana, misma
  huella wmic vs CIM, huella legacy aceptada, respaldo si PowerShell falla.

## 3. `validator_app/gui/main_window.py` (ventana del agente)

- **Antes:** `activacion_vigente(huella)` exigía que la huella guardada fuera
  **igual** a la actual.
- **Ahora:** `activacion_vigente(huella, alternativas=())` acepta la guardada si
  coincide con la actual **o** con alguna alternativa de la misma PC; la firma RSA
  se verifica contra la huella **guardada**. La app pasa
  `fingerprint.huellas_compatibles()`.
- **Riesgo:** bajo — las alternativas son huellas calculadas en la misma PC; la
  firma sigue siendo obligatoria.
- **Test:** `tests/test_gui_activacion.py::test_activacion_vigente_con_huella_alternativa_de_la_misma_pc`.

## 4. `validator_app/proxy/server.py` (servicio del proxy)

- **Antes:** `_aviso_event_log` ejecutaba
  `eventcreate /L APPLICATION /SO JSWinProxy /ID 101 ...` con `check=False` y la
  salida capturada.
- **Ahora:** `RegisterEventSourceW` + `ReportEventW` + `DeregisterEventSource`
  (advapi32 vía ctypes). Se quitó `import subprocess`.
- **Por qué:** `eventcreate` solo escribe en orígenes creados por él mismo
  (`CustomSource=1`). El instalador registra `JSWinProxy` con `New-EventLog`, así
  que `eventcreate` respondía *"El parámetro de origen se usa para identificar solo
  las aplicaciones/scripts"* **siempre**, incluso como LocalSystem. El error se
  perdía (`check=False`) → nunca había evento 101 → la tarea
  `JSWinProxy-AvisoSesion` nunca sacaba el popup. La nota vieja de AGENTS.md
  ("bajo LocalSystem funciona") no aplicaba a instalaciones nuevas.
- **Riesgo:** bajo. Verificado en producción: el evento 101 real de las 18:29:48
  disparó la tarea (resultado 0).
- **Tests:** `tests/test_proxy.py::test_aviso_event_log_usa_reportevent_con_origen_jswinproxy`
  (ERROR e INFORMATION) y `test_aviso_event_log_falla_si_reportevent_falla`.

## 5. `validator_app/proxy/config.py`

- **Nuevo:** `proxy_local_url_seguro()` — URL local del proxy **sin exigir** leer
  `config.yaml`. Orden: `config.yaml` → puerto que el instalador escribió en
  `.extension_build/background.js` (legible sin elevar) → `http://127.0.0.1:8080`.
- **Por qué:** ver punto 6.
- **Tests:** `tests/test_config.py` (3 tests nuevos de `proxy_local_url_seguro`).

## 6. `validator_app/proxy/rotate_creds.py` (renovar sesión)

Lo usan el icono **"Renovar sesion WinForce"** del Escritorio y el botón de
renovar de la consola owner (que llama `rotate_creds.main` en el mismo proceso).

- **Antes:** `get_config()` al principio → `PermissionError` porque `config.yaml`
  tiene ACL SYSTEM+Administradores y estos procesos corren **sin elevar**.
  Comprobado en esta PC: fallaba siempre.
- **Ahora:**
  - `push_session_cookie()` usa `/local/renovar` con `proxy_local_url_seguro()`;
    solo si no conecta intenta leer `admin_key` para `/admin/rotar`, y si no puede,
    devuelve un error claro ("comprueba que el servicio JSWinProxy esté encendido").
  - `_verificar_proxy()` usa `/local/estado` (solo local, sin admin key) en vez de
    `/admin/status`.
  - `--manual` ya no imprime datos que salían de `config.yaml`.
- **Tests:** `tests/test_login_asistido.py` (3 nuevos: sin `config.yaml` legible,
  proxy caído con mensaje claro, `/local/estado` sin admin key).

## 7. `generator/owner_app.py` (consola del owner)

### 7a. Sin ventanas de Terminal
- `SIN_VENTANA = CREATE_NO_WINDOW` en `reiniciar_servicio`, `consultar_servicio`
  (`sc query`, que corre en cada "Actualizar estado") y `_ejecutar_elevado`.
- **Tests:** `test_reiniciar_y_elevar_no_abren_ventana`, `test_consultar_servicio_no_abre_ventana`.

### 7b. Portapapeles privado para secretos
- **Antes:** `clipboard_clear()` + `clipboard_append()` de Tk; borrado a los 60 s.
  El historial Win+V y la nube conservaban una copia igual.
- **Ahora:** `copiar_sin_historial(texto)` (Win32 vía ctypes) cuando `limpiar=True`
  (tokens, código de activación): pone `CF_UNICODETEXT` + los formatos
  `ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory=0`
  y `CanUploadToCloudClipboard=0`. Si algo falla, usa el portapapeles de Tk como
  antes. El borrado a los 60 s sigue igual.
- **Detalle importante:** el dueño del portapapeles es una **ventana de mensajes
  propia**, no la de Tk. Con la ventana de Tk como dueña, al cerrar la consola Tk
  vaciaba el portapapeles (copiar → cerrar → pegar dejaba de funcionar). Con
  `OpenClipboard(NULL)`, `SetClipboardData` falla.
- **Riesgo:** bajo (tiene respaldo a Tk). Probado en real (ver `verificacion.md`).
- **Test:** `test_copiar_sin_historial_devuelve_false_si_no_abre_el_portapapeles`.

## 8. `validator_app/proxy/secretos.py` (leer/rotar tokens, corre elevado)

- ACL por SID (`*S-1-5-18:F *S-1-5-32-544:F`) en vez de
  `BUILTIN\Administradores` → `Administrators`.
- `CREATE_NO_WINDOW` en `sc qc`, `icacls` y `Restart-Service`.
- **Test:** `tests/test_secretos.py::test_rotar_icacls_usa_sids_independientes_del_idioma`
  (reemplaza al test del fallback en inglés, que ya no aplica).

## 9. `validator_app/updater/download.py` (actualizador del agente)

- `subprocess.Popen(["cmd", "/c", updater.bat], creationflags=CREATE_NO_WINDOW)`.
  El `.bat` sigue teniendo consola (oculta), así que `timeout` funciona.
- **Riesgo:** bajo. Es el único cambio que llega a los agentes con Windows 10
  (además de la huella, que allí no cambia nada).

## 10. `validator_app/proxy/extension/background.js` (extensión de Chrome)

- Badge al hacer clic: `…` procesando, `✓` verde ok, `X` rechazada, `!` sin
  sesión en el navegador, `?` proxy inalcanzable. Antes, con éxito, el badge
  quedaba vacío y la única señal era una notificación de Chrome que Windows puede
  ocultar (el owner hizo 7 clics sin ver nada).
- `revisarEstado()` no cambió: cada 5 min deja el badge vacío si la sesión vive.
- **Para que tome el cambio:** reconstruir `.extension_build` (lo hace
  `install_service.bat` paso 7) y recargar la extensión en `chrome://extensions`.

---

## Tests (resumen)

| Archivo | Cambio |
|---|---|
| `tests/test_fingerprint.py` | **nuevo** (5 tests) |
| `tests/test_install_bat.py` | +5 guardas estáticas del `.bat` |
| `tests/test_proxy.py` | +3 (evento por `ReportEventW`) |
| `tests/test_login_asistido.py` | +3 (renovar sin `config.yaml`) |
| `tests/test_config.py` | +3 (`proxy_local_url_seguro`) |
| `tests/test_owner_app.py` | +3 (sin ventana, portapapeles) |
| `tests/test_gui_activacion.py` | +1 (huella alternativa) |
| `tests/test_secretos.py` | 1 reemplazado (SIDs) |

Total al cierre: **287 passed**, `ruff` limpio.
