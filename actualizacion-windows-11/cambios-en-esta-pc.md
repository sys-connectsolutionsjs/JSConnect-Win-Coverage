# Cambios hechos en la PC de oficina (fuera del repo)

Todo esto se hizo en la PC real el **2026-10-02** y **no** está en Git. Sirve para
saber qué hay instalado y cómo deshacerlo. **No contiene tokens ni secretos**:
están en `validator_app/proxy/config.yaml`, `proxy_token.txt` y `admin_key.txt`
(gitignored, ACL de administrador) y en la consola owner → "Credenciales del
proxy".

## Software instalado

| Qué | Dónde | Cómo |
|---|---|---|
| Git 2.56 | `C:\Program Files\Git` | winget / instalador |
| Python 3.14.7 (todos los usuarios, en PATH del sistema) | `C:\Program Files\Python314` | `winget install Python.Python.3.14 --scope machine` |
| Repo clonado | `C:\Users\Usuario\Documents\Aplicacion_JS_Win_Coverage` | `git clone` del repo original |
| Entorno de desarrollo | `.venv\` del repo (`requirements-dev.txt`) | `python -m venv .venv` |
| Chromium de Playwright | `%LOCALAPPDATA%\ms-playwright\` | `python -m playwright install chromium` |

> El **servicio** usa el Python del sistema (`C:\Program Files\Python314`), **no**
> el `.venv`. Sus dependencias se instalaron ahí con `install_service.bat`
> (elevado). No hacer `pip install` sin elevar sobre ese Python: caería en el
> directorio del usuario y el servicio (LocalSystem) no lo vería.

## Proxy (`install_service.bat`)

- Servicio **`JSWinProxy`** (WinSW, LocalSystem, inicio automático), puerto **8080**.
- `config.yaml` + tokens nuevos generados en esta PC (los agentes deben usar
  **este** `proxy_token`).
- Tarea programada **`JSWinProxy-AvisoSesion`** (popup `msg *` con el evento 101).
- Origen de eventos `JSWinProxy` en el registro Aplicación.
- Política de Chrome `HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionSettings\eloaiabifjaghdfnfbjeffgecmkkidjg`
  (Chrome la ignora: la PC no está en dominio).
- Acceso directo **"Renovar sesion WinForce"** en el Escritorio
  (`C:\Program Files\Python314\pythonw.exe -m validator_app.proxy.rotate_creds`).
- El instalador se ejecutó 2 veces: instalación limpia y re-ejecución con el
  `.bat` nuevo (tokens conservados).
- El servicio se reinició 2 veces (fix del evento; luego el instalador) — la
  sesión WinForce se conservó.

## Firewall (cambiado a mano, además del instalador)

```powershell
# Como Administrador — lo que quedó aplicado:
Set-NetFirewallRule -DisplayName 'JSWinProxy API' -Profile Any `
  -RemoteAddress 192.168.0.0/16,10.0.0.0/8,172.16.0.0/12,100.64.0.0/10
```
La red de la oficina ("Red 3", Ethernet) está clasificada como **Pública** y se
dejó así (no se reclasificó).

## Extensión de Chrome

Cargada **sin empaquetar** a mano en el perfil de Chrome **"Profile 1"** desde
`validator_app\proxy\.extension_build`. Al cambiar `validator_app/proxy/extension/`
hay que reconstruir esa carpeta (paso 7 de `install_service.bat`) y pulsar
**recargar** en `chrome://extensions`.

## Agente en esta PC (por Smart App Control)

Smart App Control está **activo** (Windows 11) y bloquea
`JSConnect-Win-Coverage.exe` porque no está firmado. Como solución en esta PC:

- Lanzador `%LOCALAPPDATA%\JSConnect-Win-Coverage\lanzar_agente.pyw`: corre la
  app **desde el código** con `.venv\Scripts\pythonw.exe` (firmado) y fija el
  AppUserModelID `JSConnect.WinCoverage.Agente` para que el icono anclado y la
  ventana se agrupen en la barra de tareas. Si falla, escribe
  `error_agente.log` junto al lanzador.
- Accesos directos **"JSConnect Win Coverage"** en el Escritorio y en el Menú
  Inicio (mismo AppUserModelID, icono `assets\icons\agent.ico`).
- Consecuencia: en esta PC el agente corre el código del repo tal como esté
  (un `git pull` lo actualiza sin compilar).

## Ejecutables generados (`dist\`, gitignored) y Release

Compilados desde el commit **`4fe66d3`** y publicados en el Release
**[`v2026.10.02-w11`](https://github.com/sys-connectsolutionsjs/W11-JSConnect-Win-Coverage/releases/tag/v2026.10.02-w11)**
de este repo:

| Archivo | SHA-256 | Notas |
|---|---|---|
| `JSConnect-Win-Coverage.exe` | `9287A815F09AA69C7C979031E9E3311D0D40967A79FB702D6E32676E85D2EDCB` | `build.ps1 -RepoName "W11-JSConnect-Win-Coverage"`: su actualizador consulta **este** repo |
| `JSConnect-Win-Owner.exe` | `B6493EEC0D6994377D8C67E48A16687DD6E3F91968C1BFE826A665312863482B` | `build-owner.ps1`; corre en esta PC (Smart App Control no lo bloqueó) |

- Hubo builds intermedios (commits `7e800b0` y `5cb8768`) que **no** se publicaron; los
  hashes que circularon en la sesión para esos builds ya no corresponden a nada.
- `private_key.pem` — copiada por el owner junto al `.exe` del owner (llave de
  activación; nunca a Git).

## GitHub CLI

- `gh` 2.102 instalado (`C:\Program Files\GitHub CLI\gh.exe`, winget) y con sesión
  iniciada como `sys-connectsolutionsjs` (`gh auth login --web`). Con él se publicó el
  Release; `publish-release.ps1` imprime el comando `gh release create` equivalente.

## Git

- Identidad local del repo: `sys-connectsolutionsjs` / `sistemasconnectsolutionsjs@gmail.com`.
- Remoto nuevo **`w11`** → `https://github.com/sys-connectsolutionsjs/W11-JSConnect-Win-Coverage.git`;
  `main` sigue a `w11/main`. El remoto `origin` (repo original) **no** recibió nada
  (ni commits ni Releases: su último Release sigue siendo `v2026.09.30`).
- Commits subidos a `w11/main` el 2026-10-02:
  `5cb8768` (código Windows 11) → `a40a0d5` (documentación) → `4fe66d3`
  (`build.ps1 -RepoName`) → commit de esta actualización de documentación.
- Tag `v2026.10.02-w11` → `4fe66d3` (el commit embebido en los `.exe` del Release).
