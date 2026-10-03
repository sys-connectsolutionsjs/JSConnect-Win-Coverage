# Actualización Windows 11 — PC owner/proxy

> Registro de la adaptación hecha el **2026-10-02** para que la **PC de oficina
> (owner + proxy)** funcione en **Windows 11 Pro 25H2** (build 26200, español).
> Los **agentes siguen en Windows 10** y no necesitan cambiar nada.
>
> Esta carpeta existe para revisar con calma **qué cambió y por qué**, porque la
> adaptación se hizo en una sola sesión asistida por IA. Nada aquí reemplaza
> revisar el diff.

## Contenido de esta carpeta

| Archivo | Para qué sirve |
|---|---|
| [`cambios-por-archivo.md`](cambios-por-archivo.md) | Cada archivo tocado: antes / después, motivo, riesgo, cómo revertir, qué test lo cubre |
| [`verificacion.md`](verificacion.md) | Qué se probó de verdad en la PC real (con resultados) y qué falta probar |
| [`cambios-en-esta-pc.md`](cambios-en-esta-pc.md) | Lo que se hizo en el sistema de la PC **fuera del repo** (instalaciones, firewall, accesos directos) |
| [`pendientes.md`](pendientes.md) | Problemas detectados que **no** se resolvieron y decisiones abiertas |

## Roles de cada PC

| PC | Windows | Qué corre | ¿Necesita el código nuevo? |
|---|---|---|---|
| Oficina (owner + proxy) | **11 Pro 25H2** | Servicio `JSWinProxy`, consola owner, extensión de Chrome | **Sí** — es para lo que se hizo esto |
| Agentes (call center) | 10 | `JSConnect-Win-Coverage.exe` del Release `v2026.09.30` | **No** — siguen funcionando igual |

## Los 6 problemas encontrados en Windows 11 (resumen)

Todos se detectaron **en la PC real**, no por suposición.

| # | Problema | Causa | Efecto | Solución |
|---|---|---|---|---|
| 1 | Agentes de otras PC no conectan al proxy | Windows 11 marcó la red como **Pública**; la regla de firewall solo cubría `Domain,Private` | Timeout en los agentes | Regla con `-Profile Any` **limitada** a rangos LAN/Tailscale (`-RemoteAddress`) |
| 2 | La huella de activación depende de `wmic` | Windows 11 24H2+ **eliminó `wmic`** | Huella más débil; una PC que pase de Win10 a Win11 perdería su activación | Si no hay `wmic`, leer **los mismos valores** por CIM/PowerShell; aceptar también la huella vieja |
| 3 | El popup "sesión caducada" nunca salía | `eventcreate` **rechaza** el origen `JSWinProxy` porque el instalador lo registra con `New-EventLog` (el error se tragaba en silencio) | El owner no se enteraba de que la sesión murió | Escribir el evento con la API Win32 `ReportEventW` (ctypes) |
| 4 | Icono "Renovar sesion WinForce" y botón de la consola owner fallaban siempre | `rotate_creds` leía `config.yaml`, que tiene ACL solo para SYSTEM + Administradores → `PermissionError` sin elevar | No se podía renovar la sesión por esas vías | `/local/renovar` ya no necesita leer `config.yaml` |
| 5 | Ventanas de Terminal que aparecen solas y roban el foco | En Windows 11 la consola por defecto es **Windows Terminal**; ningún `subprocess` usaba `CREATE_NO_WINDOW` | Molestia visible en la consola owner y el actualizador | `creationflags=CREATE_NO_WINDOW` en todos los subprocess de apps con ventana |
| 6 | Tokens copiados quedan en el historial del portapapeles | Historial **Win+V** y sincronización en la nube de Windows 11 | `proxy_token` / `admin_key` guardados aunque la app los borre a los 60 s | Copia Win32 marcada como privada (sin historial ni nube) |

Además se corrigieron **bugs del instalador** (`install_service.bat`) que no eran
de Windows 11 pero reaparecían al reinstalar: detección de puerto ocupado,
health check que siempre decía "EXITO", ACL por nombre traducido de grupo, `pip`
y `pythonw` del intérprete equivocado. Y la **extensión de Chrome** ahora
muestra un badge al hacer clic (antes no daba señal visible).

## Qué NO cambió

- **La API del proxy** que usan los agentes (`/api/*`, `/health`, tokens). Un
  agente con el `.exe` del Release `v2026.09.30` funciona igual contra este proxy.
- **La huella en Windows 10**: con `wmic` presente se calcula exactamente igual.
- **El flujo de activación**, la llave pública, el formato de `config.yaml`.
- **El repo original** (`sys-connectsolutionsjs/JSConnect-Win-Coverage`): no se
  le subió nada. Todo esto vive solo en `W11-JSConnect-Win-Coverage`.

## Cómo revisarlo

```powershell
# Los commits de esta adaptación
git log --oneline 7e800b0..HEAD

# El diff completo del código (commit 5cb8768)
git diff 7e800b0 5cb8768 -- . ':!*.md'

# Un archivo concreto
git diff 7e800b0 5cb8768 -- validator_app/activation/fingerprint.py

# Tests (287 al cierre de la sesión)
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check validator_app tests generator
```

Orden sugerido de lectura del diff (de mayor a menor impacto):
1. `validator_app/proxy/install_service.bat` — firewall, ACL, puerto, health check
2. `validator_app/activation/fingerprint.py` + `validator_app/gui/main_window.py` — huella / activación
3. `validator_app/proxy/server.py` — aviso por evento de Windows
4. `validator_app/proxy/rotate_creds.py` + `validator_app/proxy/config.py` — renovar sin elevar
5. `generator/owner_app.py` — sin ventanas + portapapeles privado
6. `validator_app/proxy/secretos.py`, `validator_app/updater/download.py`, `validator_app/proxy/extension/background.js`

## Cómo revertir todo

```powershell
git revert 5cb8768   # deshace el código; la regla de firewall de la PC se ajusta aparte
```
La regla de firewall de la PC se cambió a mano (ver `cambios-en-esta-pc.md`); para
volver a la anterior:
`Set-NetFirewallRule -DisplayName "JSWinProxy API" -Profile Domain,Private -RemoteAddress Any`
(como Administrador) — y con eso los agentes **dejan de conectar** mientras la red
siga clasificada como Pública.
