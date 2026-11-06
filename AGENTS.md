# AGENTS.md — Proyecto JSConnect-Win-Coverage

## Resumen
Aplicación de escritorio para Windows (call center de un proveedor de servicio de
internet) que acelera la validación de clientes: **cobertura de servicio**
(coordenadas) y **score crediticio** (DNI 8 dígitos / RUC 11 dígitos / Carnet de
Extranjería 9 caracteres alfanumérico). En lugar de scrapear HTML, replica las
llamadas HTTP (JSON) a la API interna del sistema de validación, devolviendo la
información en milisegundos, sin cargar página, sin mapa ni navegador.

## Stack
- Python 3.12+ (`requires-python = ">=3.12"` es el piso; **producción y desarrollo
  estandarizados en 3.14.7**, instalado para todos los usuarios y en el PATH)
- HTTP: `requests` (agente) y `httpx` (cliente del proxy y consola owner) · Proxy:
  `fastapi` + `uvicorn` · GUI: `tkinter` + `ttkbootstrap` · Credenciales: `keyring`
- Licencias/activación: `cryptography` (RSA, firma asimétrica)
- Empaquetado: `PyInstaller` (un único .exe portable)
- Dev: `playwright` (solo captura, NO va en el .exe) · Tests: `pytest` · Lint: `ruff`
- Plataforma: agentes en **Windows 10** (probado); PC oficina (owner + proxy) en
  Windows 10 o **Windows 11 Pro** (probado en 25H2 el 2026-10-02, ver
  `actualizacion-windows-11/`). En Windows 11 con Smart App Control los `.exe`
  sin firma se bloquean.

## Estructura
La estructura se ve con `ls` / el árbol del repo; componentes y flujos en
[`docs/arquitectura.md`](docs/arquitectura.md); lo que nunca va al repo, en «Notas de seguridad».

**Informes diarios:** las reglas de creación y la estética de la plantilla están
consolidadas en `C:\Users\Angel\Documents\JSCONECTSOLUTIONS\Informe de avanzes\Reportes-Diarios-JS-Connect\GUIA_INFORMES.md`.
Para generar un informe, leer también `REGLAS_CREACION_INFORMES.txt`, verificar la
plantilla `18_08_26_informe_avance_proyecto_winforce.docx` y no copiar hechos de
`artifact.md` si pertenecen a una sesión histórica distinta.

## Comandos
- Instalar producción: `pip install -r requirements.txt`
- Instalar desarrollo: `pip install -r requirements-dev.txt`
- Instalar proxy (PC oficina): `.\validator_app\proxy\install_service.bat` (como Admin)
- Navegador de captura: `python -m playwright install chromium`
- Ejecutar la app: `python main.py`
- Build: `powershell -ExecutionPolicy Bypass -File build.ps1`
- Consola owner: `python generator/owner_app.py`
- Build owner: `powershell -ExecutionPolicy Bypass -File build-owner.ps1`
- Publicar Release: `powershell -ExecutionPolicy Bypass -File publish-release.ps1`
- Tests: `pytest`
- Lint: `ruff check .`

## Convenciones
- Identificadores y código en inglés; textos de interfaz y mensajes en español.
- Sin comentarios salvo docstrings breves.
- Nunca hardcodear credenciales; cada usuario guarda las suyas vía keyring.
- La llave privada de activación, tokens y archivos de captura NUNCA van al repo.
- **TDD (semáforo)**: los tests se escriben PRIMERO (rojo → falla), luego se
  implementa lo mínimo para que pasen (verde). Cualquier cambio de comportamiento
  va acompañado de su test. Bitácora detallada en [`TestingLog.md`](TestingLog.md).

## README.md (obligatorio)
- El README.md debe mantenerse **ACTUALIZADO** con todos los cambios relevantes
  (funciones nuevas, comandos, estructura, configuración) **ANTES de subir el
  repositorio a GitHub**. Es responsabilidad de quien toque el código.
- Está redactado en **español primero y luego en inglés** dentro del mismo archivo.

## Versionado y actualizaciones
- La "versión" = SHA del commit + tag del Release.
- `build.ps1` lee `git rev-parse HEAD` y lo embebe en `validator_app/version.py`.
- La app consulta `GET /repos/{owner}/{repo}/releases/latest`, resuelve el commit
  real del tag con `GET /repos/{owner}/{repo}/commits/{tag}` (`_commit_de_tag()`;
  `target_commitish` del release NO sirve — es el nombre de la rama, no un SHA;
  bug corregido 2026-09-25) y lo compara con el embebido. Si difieren → ofrece
  descargar el asset .exe.
- El .exe descargado se valida por SHA-256 (checksum publicado en las notas del
  Release) antes de reemplazar al actual.
- Límite de API sin autenticación: 60 consultas/hora (dos llamadas por chequeo desde
  2026-09-25: `releases/latest` + `commits/{tag}`; sigue sobrando para botón manual).
- **Desde 2026-09-21, el Release trae dos `.exe`** (agente + consola owner, ver
  `publish-release.ps1`): `updater/check.py` elige el asset por nombre EXACTO
  (`NOMBRE_ASSET_AGENTE`), nunca por sufijo `.exe`, y `updater/download.py::
  extraer_checksum()` recorta las notas al bloque del archivo pedido antes de
  buscar el hash — evita que el agente se autoactualice con el `.exe` del owner
  o cruce checksums entre ambos.
- **La consola owner también busca actualizaciones** (desde `v2026.10.07.1`): botón
  "Buscar actualizaciones" en `generator/owner_app.py`, más un chequeo silencioso al
  abrir que solo avisa en una etiqueta. A diferencia del agente (que compara el commit
  embebido con el del tag), el owner compara el **SHA-256 de su propio `.exe`** con el que
  el Release publica para `JSConnect-Win-Owner.exe` (`check.hay_actualizacion_owner`):
  por commit entraría en bucle si un Release reutiliza un owner viejo. Sin asset del owner
  o sin su hash en las notas no ofrece nada. El flujo de descarga/reemplazo es el mismo
  (`download.aplicar_actualizacion`, que toma el asset de `info["nombre_asset"]`) y la
  `private_key.pem` junto al `.exe` no se toca. `build-owner.ps1` ahora también graba
  `validator_app/version.py`. **El owner `v2026.10.07` ya instalado no trae este
  actualizador: hay que reemplazar su `.exe` a mano una sola vez.**
- **El agente salta directo al último Release**, sin pasar por los intermedios (el
  actualizador solo mira `releases/latest`). Un agente en el Release 1 que ve el 3
  descarga el 3; no instala el 2.
- **REGLA — NO borrar `huellas_legacy()` (ni su uso en `main_window.py`) por iniciativa
  propia.** Solo se hace si el usuario lo pide **expresamente**. Por qué: la huella
  antigua solo se acepta mientras exista; un agente que salte de `v2026.09.30` directo a
  un Release sin ella pierde la activación sin pasar por la "transición" y tiene que
  reactivar. Antes de pedirlo, el usuario debe confirmar que **todos** los agentes ya
  abrieron `v2026.10.07` (o posterior) y se reactivaron. Aplica igual a cualquier otro
  código de compatibilidad con activaciones antiguas.

## Implementaciones futuras
Ver [`Roadmap.md`](Roadmap.md) → «Implementaciones futuras» (movido el 2026-11-06).

## Reglas de trabajo (flujo del día)
- **[`ResumenDelDia.md`](ResumenDelDia.md)** = historial del DÍA. Lleva la fecha dentro y se va
  actualizando a medida que se trabaja (lo que se hizo, lo que se pospuso, lo que
  queda pendiente al volver). Sirve de base para el resumen de cierre de sesión.
- **[`PlanesAprobados.md`](PlanesAprobados.md)** es una **COLA de trabajo, NO un historial**: cada vez que
  se implementa algo que estaba en la cola, se **saca** de ahí (se marca como hecho o
  se elimina). El historial de lo hecho vive en [`docs/historial-agents.md`](docs/historial-agents.md) (bitácora
  archivada), en el último cierre de AGENTS.md y en ResumenDelDia.md.
- **[`README.md`](README.md)** se actualiza con los avances cuando el plan implementado lo amerite
  (seguridad, funciones nuevas, estructura, comandos, etc.).
- **Cierre de sesión** (automatizable con `/documentation:cerrar-sesion`, ver tarea 43 en
  [`docs/historial-agents.md`](docs/historial-agents.md)): al terminar una sesión se actualiza AGENTS.md con el resumen
  de lo hecho en el día **en un solo `### Cierre de la sesión <fecha>`** (el último). Antes de
  escribirlo, el cierre anterior se **mueve** tal cual a [`docs/historial-agents.md`](docs/historial-agents.md)
  (sección "Historial", el más nuevo al final); así `AGENTS.md` no vuelve a crecer sin
  límite. Las tareas completadas también van a ese archivo; en `## Tareas pendientes`
  solo queda lo abierto. Después, al confirmar el usuario que ya terminó la
  sesión, se le pregunta si desea presentar el resumen del día desde
  [`ResumenDelDia.md`](ResumenDelDia.md).
- **Rotación de resúmenes** (al abrir un día nuevo): el contenido de [`ResumenDelDia.md`](ResumenDelDia.md)
  se reparte en dos destinos que NO compiten, cada uno con un rol distinto:
  - `resumenes/<fecha>.md`: snapshot COMPLETO e inmutable de la sesión que cierra (todo
    el detalle, tal cual quedó en [`ResumenDelDia.md`](ResumenDelDia.md)).
  - [`HistorialResumenes.md`](HistorialResumenes.md): entrada CONDENSADA de esa sesión, agregada arriba del todo
    (orden cronológico inverso) — es el índice navegable, no el detalle completo.
  - Después de rotar, [`ResumenDelDia.md`](ResumenDelDia.md) empieza limpio con la fecha del día nuevo.

## Regla de auto-actualización de la documentación

Esta documentación existe para que cualquiera (persona o IA) pueda retomar el proyecto
sin perder contexto. Para que no se desactualice como ya pasó una vez (ver cierre de
sesión 2026-08-25, que quedó desfasado del código real), se sigue este proceso en
**tres momentos**:

1. **Al INICIAR sesión — ojeada de verificación (barata, no exhaustiva)**
   Antes de tocar código: leer este archivo (Tareas pendientes + último cierre de
   sesión) y confirmar contra el árbol real que el proyecto es el que la documentación
   describe — ¿existen los archivos/funciones que se dan por pendientes o por hechos?,
   ¿`pytest` y `ruff check .` siguen en verde? Si hay desfase, **reportarlo al usuario y
   corregir la doc antes de empezar la tarea nueva**. No es una auditoría línea por
   línea; es una comprobación rápida de coherencia.

2. **Durante la sesión — registro narrativo (sin auditar)**
   Al terminar cada tarea significativa (fase, feature o fix con tests en verde),
   anotar en [`ResumenDelDia.md`](ResumenDelDia.md) lo que se hizo, y sacar de la cola de
   [`PlanesAprobados.md`](PlanesAprobados.md) lo que ya se implementó. Basta con narrar lo trabajado; esta
   anotación intermedia NO exige re-verificar el estado global del proyecto.

3. **Al CERRAR sesión — actualización auditada**
   Antes de escribir el cierre, auditar contra el código lo hecho en la sesión
   (¿existen los archivos/funciones que se van a declarar completados?, ¿`pytest` y
   `ruff check .` en verde?). Recién con eso verificado:
   - Lo que se comprobó implementado en `## Tareas pendientes` se marca
     `[COMPLETADO — <fecha>]` **y se mueve** a [`docs/historial-agents.md`](docs/historial-agents.md) (sección
     "Tareas pendientes (archivo)"); en `AGENTS.md` solo quedan las abiertas.
   - Añadir un nuevo `### Cierre de la sesión <fecha>` en `## Historial` (mover antes el
     anterior a [`docs/historial-agents.md`](docs/historial-agents.md)).
   - Actualizar [`README.md`](README.md) si el cambio lo amerita (seguridad, funciones nuevas,
     estructura, comandos) y `docs/` si cambió algo técnico permanente.
   - Rotar [`ResumenDelDia.md`](ResumenDelDia.md) según la regla de rotación de arriba.

   **Regla de oro**: nunca marcar algo como completado o pendiente en la documentación
   sin haberlo comprobado en el código.

**Recordatorio automático (hook)**: `.claude/hooks/historial_sync.py` (registrado en
`.claude/settings.json` como hook `PostToolUse`) vigila [`HistorialResumenes.md`](HistorialResumenes.md).
Cada vez que se le agregan entradas nuevas (`### YYYY-MM-DD`), inyecta un
recordatorio para sincronizar [`anotaciones.md`](anotaciones.md) / [`PlanesAprobados.md`](PlanesAprobados.md) / `AGENTS.md`;
cada 3 entradas nuevas acumuladas, además recuerda revisar [`README.md`](README.md). Es solo un
aviso — no edita nada y no reemplaza la verificación contra el código.

## Archivos de documentación (mapa de conocimiento)
Estos archivos son el punto de partida de cualquier persona (o IA) que retome el
proyecto. Leerlos en este orden ANTES de tocar código. Esta sección es además el
**nodo central del grafo** de Obsidian (el repo se puede abrir como bóveda; `.obsidian/`
está en `.gitignore`):
1. **[AGENTS.md](AGENTS.md)** (este archivo): reglas del proyecto, contexto, tareas abiertas y el
   último cierre de sesión. Es la puerta de entrada. Su historial viejo está en
   **[docs/historial-agents.md](docs/historial-agents.md)** (ver abajo).
2. **[Roadmap.md](Roadmap.md)**: vista única de qué se hizo, qué falta y en qué orden (línea de
   tiempo + cola aprobada + backlog v1.1 + bloqueos). Leer para ubicarse rápido
   antes de decidir en qué trabajar.
3. **[PlanesAprobados.md](PlanesAprobados.md)**: **cola** de trabajo con los planes YA aprobados, el
   razonamiento y las decisiones tomadas (ej: decisión de autenticación). Contiene
   además diseños listos para implementar. Leer antes de empezar una fase para no repetir
   análisis ni ignorar decisiones. Se actualiza SACANDO de la cola lo implementado.
4. **[TestingLog.md](TestingLog.md)**: metodología TDD del proyecto (test rojo -> verde), inventario de
   tests y bitácora de problemas -> causa -> solución. Leer antes de escribir o
   modificar tests.
5. **[README.md](README.md)**: documentación pública del proyecto (español primero, luego inglés).
   Mantenerla actualizada ANTES de subir a GitHub. Su guía corta del proxy para el owner es
   **[README_PROXY.md](README_PROXY.md)**.
6. **[ResumenDelDia.md](ResumenDelDia.md)**: historial del día en curso (fecha dentro, se actualiza al
   trabajar). Fuente del resumen de cierre de sesión.
7. **[Escalabilidad.md](Escalabilidad.md)**: guía para futuros programadores (cómo escalar a remotos).
8. **[anotaciones.md](anotaciones.md)**: glosario técnico para términos que futuros devs desconozcan.
9. **docs/**: documentación técnica permanente:
   - [docs/arquitectura.md](docs/arquitectura.md): componentes, flujos y control de acceso al proxy;
     sus diagramas PlantUML están en [docs/diagramas/README.md](docs/diagramas/README.md).
   - [docs/proxy-deploy.md](docs/proxy-deploy.md): instalar y actualizar el proxy en la PC de la oficina.
   - [docs/proxy-config.md](docs/proxy-config.md): configurar cada agente para usar el proxy.
   - [docs/rotacion-credenciales.md](docs/rotacion-credenciales.md): renovar la sesión de WinForce y
     cambiar credenciales (incluye Geofinder y cómo investigar una muerte de sesión).
   - [docs/escalabilidad-remota.md](docs/escalabilidad-remota.md): extender la arquitectura a agentes
     fuera de la LAN.
10. **[HistorialResumenes.md](HistorialResumenes.md)**: índice cronológico condensado de resúmenes pasados (lo
   más nuevo arriba), con un enlace a cada snapshot. Ver ahí si se necesita ubicar rápido en qué
   sesión pasó algo.
11. **resumenes/**: snapshots COMPLETOS e inmutables de cada sesión pasada
    (`resumenes/<fecha>.md`), con el detalle íntegro que tenía [ResumenDelDia.md](ResumenDelDia.md) al
    cerrar esa sesión. No se editan (tampoco para añadir enlaces).
12. **[docs/historial-agents.md](docs/historial-agents.md)**: archivo histórico de AGENTS.md — las tareas ya
    completadas y la bitácora por fases + cierres de sesión anteriores. Consultar ahí el
    "por qué" de una decisión antigua; no es lectura obligatoria al retomar el proyecto.
13. **[actualizacion-windows-11/README.md](actualizacion-windows-11/README.md)**: adaptación de la PC
    owner/proxy a Windows 11 (2026-10-02): cambios, verificación y pendientes de esa migración.
14. **[TraspasoInmediato.md](TraspasoInmediato.md)**: plan futuro (no implementado) para traspasar el
    proxy rápido entre dos PC.
15. **[SkillsPropuestas.md](SkillsPropuestas.md)**: cola de tareas repetitivas que podrían volverse
    skills personalizadas.
16. **[vpn.md](vpn.md)**: documento de decisión (2026-11-06, sin implementar) con todas las formas de
    llevar el proxy a los asesores remotos (NetBird/Headscale en Oracle Free, Cloudflare Tunnel, etc.),
    costos, riesgos y la recomendación del owner (NetBird propio).

Convención para MD futuros: cuando una fase o plan genere un documento nuevo (ej:
DecisionesArquitectura.md, ManualOperador.md), se registra AQUÍ su existencia, propósito
e importancia, para que el mapa de conocimiento nunca quede incompleto.

**Enlaces entre documentos**: un `.md` que cita a otro lo hace con un enlace markdown
**relativo a la carpeta del archivo** (destino `docs/proxy-deploy.md` desde la raíz,
`../AGENTS.md` desde `docs/`), no con la ruta suelta entre backticks: así funciona en
GitHub y en el grafo de Obsidian. No usar wikilinks `[[...]]` (GitHub no los muestra). Al
**mover texto entre carpetas** (cierre de AGENTS.md -> `docs/historial-agents.md`,
ResumenDelDia.md -> `resumenes/`) hay que ajustar las rutas relativas; en
[ResumenDelDia.md](ResumenDelDia.md) conviene citar sin enlace, porque termina copiado en `resumenes/`.
`tests/test_enlaces_docs.py` falla si queda un enlace roto (salvo en `resumenes/`, inmutable) o si
[HistorialResumenes.md](HistorialResumenes.md) no enlaza algún snapshot.

## Notas de seguridad
- No subir a GitHub: llave privada de activación, credenciales reales, archivos de
  captura (`tools/captura.json` puede contener datos sensibles aunque esté redactado).
- **Capas del mapa (datos de terceros / del negocio)**: `datos_capas/` y
  `validator_app/data/*.json.gz` están en `.gitignore` (lo vigila `tests/test_build_ps1.py`); la URL
  del mapa de reglas de venta (`capas_kml_url`) vive solo en el `config.yaml` del proxy, nunca en el
  código. Los polígonos salen de una app web de terceros; no copiar sus datos ni su dirección al repo.
  Los HAR/capturas de red (traen cookies) se guardan fuera del repo y se borran al terminar.
- Las credenciales de Win rotan cada 1-2 meses: mantener siempre centralizada su
  actualización (proxy local) o por keyring por máquina; nunca en el repo.
- El repo es público: el código de la API interna será visible. Los endpoints ya son
  públicos de facto (los usa el navegador), pero revisar antes de publicar.
- **Proxy**: `config.yaml`, `proxy_token.txt`, `admin_key.txt` son GITIGNORED — solo en PC proxy.
- **Control de acceso (whitelist + token, loopback siempre permitido)**: ver [`docs/arquitectura.md`](docs/arquitectura.md), sección "Control de acceso al proxy". Las IP públicas del router NO se agregan a `allowed_networks`. `/admin/*` exige además origen `127.0.0.1` (no configurable): el admin key expone el `proxy_token` vía `/admin/config`, así que nunca viaja por LAN.
- **Credenciales del proxy desde la consola owner**: `JSConnect-Win-Owner.exe` tiene un panel "Credenciales del proxy" (Mostrar/Copiar/Rotar) que pide UAC para leer/rotar `config.yaml`. `private_key.pem` **no** se expone ahí ni en ningún otro lugar de la consola — es la única credencial no rotable.
- Repositorio remoto: https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Tareas pendientes
> Solo lo que sigue **abierto**. Las tareas completadas (1-44) están en
> [`docs/historial-agents.md`](docs/historial-agents.md). La cola con el detalle y el orden
> está en [`PlanesAprobados.md`](PlanesAprobados.md) y [`Roadmap.md`](Roadmap.md).

1. **Reactivar los agentes** con la huella estable (25 hoy: 18 + 7; 41 a futuro). Funcionan en
   "transición" mientras tanto. **NO borrar `huellas_legacy()`** salvo petición expresa
   (regla en "Versionado y actualizaciones").
2. **Probar un agente W10 real contra el owner W11** y revisar en el owner
   `Get-NetConnectionProfile` / la regla `JSWinProxy API`.
3. **Muertes de la sesión de WinForce**: el log del 2026-09-29 al 2026-10-21 confirma la hipótesis del
   dueño (login ajeno con la misma cuenta; ninguna muerte fuera de horario de oficina, sesiones de
   hasta ~69 h el fin de semana). No hay tope de 9.5 h. **2026-11-03: confirmado por el owner** que otra
   persona usa la cuenta del proxy en el día (lunes 21 muertes, ~70 min caídas por el freno; noches y finde 0). **2026-10-27**: con la cuenta dedicada sigue muriendo → autologin (7c).
4. **Probar el pendrive en una PC owner limpia** ([`docs/proxy-deploy.md`](docs/proxy-deploy.md) → "Instalación con pendrive").
5. **Firma de código** de los `.exe` (Smart App Control en Windows 11).
6. **Pasar `W11-JSConnect-Win-Coverage` (archivado) a privado**, solo cuando sus `.exe` ya se
   hayan actualizado a `v2026.10.07`.
7. **Que el agente lea la URL y el token de un archivo del pendrive** (idea acordada; después de la
   Fase 5, con su propio Release).
7b. **Mapa de cobertura**: probarlo con los asesores y poner en `capas_kml_url` del `config.yaml` del
   proxy la URL KML del **My Maps de la empresa** (creado y verificado el 2026-10-21; la URL no va al
   repo). Sin ella `/api/capas` responde 503 y los agentes usan las reglas embebidas.
    **`v2026.10.23`** arregla el mapa sin fondo (OSM bloqueaba el User-Agent `TkinterMapView`).
7c. **Cuenta dedicada de WinForce para el proxy** (aprobada): renovar la sesión con ella, que nadie
    la use a mano, y medir 1-2 semanas con `logs/sesion_eventos.jsonl` (hoy las muertes son por logins
    ajenos en horario de oficina). Si aun así muere: **autologin desatendido** con Playwright
    (`login_asistido.py`) + usuario/contraseña en el keyring del host — viable, el login es solo el SSO
    de Microsoft (sin 2FA). **2026-10-27: con cuenta dedicada sigue muriendo → plan "Proxy 24/7:
    autologin desatendido + Tailscale" aprobado en [`PlanesAprobados.md`](PlanesAprobados.md).**
    **2026-10-28: CÓDIGO IMPLEMENTADO** (`0231cc2`: `proxy/autologin.py`, credencial y frenado desde la
    consola owner); **falta la verificación en vivo** (tarea 7f).
7d. **Mini PC como host 24/7 del proxy**: instalar con `install_service.bat`, encendido tras corte de
    luz (BIOS), sin suspensión, idealmente UPS; para lo "online", túnel (Tailscale) en vez de abrir
    puertos (**2026-11-06**: Tailscale gratis ya no aplica; ver 7i). **Diseñado 2026-10-27** en el mismo plan (Tailscale `--unattended`, sin abrir el 8080);
    runbook escrito el 2026-10-28 en [`docs/escalabilidad-remota.md`](docs/escalabilidad-remota.md). Falta la
    migración al host ([`PlanesAprobados.md`](PlanesAprobados.md) → "Migración al host definitivo").
7f. **Verificación en vivo del autologin** (NUEVA 2026-10-28). **2026-10-30**: WinForce responde HTTP 410 a
    Chromium headless; ya se usa Chromium normal (comprobado como LocalSystem, formulario aceptado) y se
    añadió la puerta "Iniciar con Microsoft". En Microsoft, un `passwd` oculto (`.moveOffScreen`) se
    confundía con la pantalla de contraseña (corregido). Cada fallo deja imagen en `logs/autologin_fallos/`
    y traza por pasos en `logs/autologin_pasos/`. **Primer login automático real: 2026-10-30, 16:11:54.**
    **2026-10-30, 19:00: prueba de muerte superada** (login en otra PC → `renovada` con `origen: autologin` en
    12 s, por SSO silencioso, sin escribir la contraseña; cobertura desde un agente 200). **No se guarda el token
    `win-azure-oauth2`** (decidido: basta el perfil del servicio). **2026-11-03: comprobado en vivo** que la consulta del asesor espera al
    autologin y se repite (16:19, total 11.7 s); la confirmación de muerte baja de 3 s a 1 s. Falta observar un día laboral; un `#passwordError` sí sería real, no repetirlo a ciegas. Luego, reevaluar
    guardar el token `win-azure-oauth2` (ver
    [`PlanesAprobados.md`](PlanesAprobados.md) → "Hallazgos del ensayo sin credenciales").
    En la PC de desarrollo haciendo de owner:
    `python -m validator_app.proxy.autologin --probar` (confirma los selectores reales; bota la
    sesión del proxy), instalar el servicio (`install_service.bat`), guardar la credencial (pregunta
    `[AUTOLOGIN]` o consola owner → Configurar...), comprobar en la consola el botón "Instalar extensión"
    y "Frenado...", y tumbar la sesión para ver `renovada` con `origen: autologin` en la bitácora.
7g. **Alto de la consola owner** (NUEVA 2026-10-28): 650 × 836 px; revisar en una pantalla de 768 px
    y, si no cabe, compactar o hacer desplazable.
7h. **Tarjetas del resultado** (NUEVA 2026-11-03, en `v2026.11.03`): recoger la opinión de los asesores
    sobre las tarjetas y los textos; ajustar frases en `gui/zonas.py` (tests en `tests/test_capas_gui.py`).
7i. **VPN para los asesores remotos** (NUEVA 2026-11-06): elegir entre las opciones de [`vpn.md`](vpn.md)
    (preferencia del owner: NetBird propio en Oracle Cloud Always Free). Antes de abrir a los remotos,
    **tokens del proxy por asesor y revocables**, límite de consultas y registro (plan TDD propio). Reemplaza
    al Tailscale de 7d para lo "online".
7e. **Cobertura observada** (TDD): el proxy registra cada `validar_cobertura` real (SQLite,
    gitignored), marca discrepancias con la capa local y las sirve como capa en `/api/capas`;
    sondeos extra acotados, apagados por defecto; exportar a KML desde la consola owner. Fraude /
    bloqueados / preferente no se pueden contrastar (WinForce solo responde cobertura).
8. Decidir si la app llama a `actualizar_score_cliente` (registra score) o basta con leerlo —
   **PENDIENTE** (diferido por el usuario).
9. Evaluar si la app debe crear el lead final (`POST controllers/newsearch.php`, multipart) —
   **PENDIENTE** (diferido por el usuario).
10. Etapa C.12 (modo standalone con `PHPSESSID`, opcional) — para otro momento.
11. Monitorear la primera semana de producción (sesión del proxy, RUC/CE) — observación, no una
    tarea con pasos.

## Historial (bitácora del proyecto)
> El historial por fases y los cierres de sesión anteriores (2026-08-18 → 2026-11-03) están en
> [`docs/historial-agents.md`](docs/historial-agents.md). Aquí queda **solo el último cierre**;
> al escribir el siguiente, este se mueve a ese archivo (ver su cabecera).

### Cierre de la sesión 2026-11-06 [CONTEXTO PARA LA SIGUIENTE — elegir la VPN para los asesores remotos (`vpn.md`), AGENTS.md recortado]

- **Hecho** (sin cambios de código; 704 tests en verde, `ruff` limpio; **sin commit**):
  - **VPN para remotos**: hoy hay más de 25 remotos con **PC personal** y se esperan 100-200 usuarios, con
    presupuesto US$0. El plan gratis de Tailscale ya no sirve (6 usuarios, no comercial) y los planes por
    usuario costarían US$300-1,600 al mes. Se escribió [`vpn.md`](vpn.md) como base del Word de decisión:
    glosario, todas las alternativas, costos con 50 y 200 remotos, riesgos y fuentes.
  - **Preferencia del owner: NetBird propio en Oracle Cloud Always Free** (panel oficial, sin cobro por
    usuario). Condiciones: cuenta en Pay As You Go (la VM gratuita "inactiva" puede ser reclamada), alerta de
    presupuesto en US$1 y copias semanales fuera de Oracle. Plan B: un VPS de ~US$5 al mes. Alternativas
    documentadas: Headscale en Oracle y Cloudflare Tunnel (no se instala nada en la PC del asesor, pero el
    proxy queda en internet).
  - **Requisito para cualquier opción**: tokens del proxy **por asesor y revocables**, límite de consultas y
    registro (hoy hay un solo `proxy_token`). Queda como tarea 7i; no se implementó.
  - `docs/escalabilidad-remota.md`: nota de **desactualizado** (decía "Tailscale gratis ≤100").
  - `/doctor`: se sacó de AGENTS.md el árbol de Estructura y "Implementaciones futuras" pasó a
    [`Roadmap.md`](Roadmap.md) (37,981 → ~28k caracteres). Modo de permisos por defecto del usuario: `plan`.
- **Sin probar / sin hacer**: nada del proxy se tocó; siguen abiertos los pasos del cierre 2026-11-03
  ("Reiniciar servicio" con la confirmación de 1 s, quién usa la cuenta del proxy, opinión sobre las tarjetas).
- **Siguiente paso**:
  1. El owner arma el Word desde `vpn.md` y elige (preguntas en su sección 12).
  2. Con la opción elegida: plan TDD de **tokens por asesor** (7i) y prueba piloto (PC del proxy + 2 remotos).
  3. Pendientes del 2026-11-03: "Reiniciar servicio" y medir la detección en `consulta_reintentada`; un día
     laboral sin el otro usuario de la cuenta; opinión de los asesores (7h).
