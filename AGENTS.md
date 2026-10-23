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
```
JS-Win-Coverage/              (raíz del proyecto)
├── main.py                   # punto de entrada de la app
├── requirements.txt          # dependencias de producción
├── requirements-dev.txt      # dependencias de desarrollo
├── requirements-proxy.txt    # dependencias del proxy (fastapi, uvicorn, pydantic)
├── build.ps1                 # embebe commit SHA + empaqueta con PyInstaller
├── build-owner.ps1           # embebe commit SHA + empaqueta la consola privada del owner
├── publish-release.ps1       # prepara el Release en GitHub (asset .exe + SHA-256)
├── AGENTS.md                 # reglas del proyecto, contexto, pendientes abiertos y último cierre
├── PlanesAprobados.md        # COLA de planes aprobados (lo implementado se saca)
├── TestingLog.md             # metodología TDD + bitácora de pruebas
├── README.md                 # documentación pública (español + inglés)
├── ResumenDelDia.md          # historial del día en curso (resumen de cierre)
├── HistorialResumenes.md     # índice cronológico condensado de sesiones pasadas
├── Escalabilidad.md          # guía para futuros programadores (escalabilidad remota)
├── anotaciones.md            # glosario técnico para futuros devs
├── actualizacion-windows-11/ # adaptación de la PC owner/proxy a Windows 11 (2026-10-02)
├── .claude/
│   ├── settings.json         # config versionada (hook PostToolUse de doc-sync)
│   └── hooks/historial_sync.py  # recuerda sincronizar docs al rotar un resumen
├── tools/
│   ├── captura.py            # herramienta Playwright para descubrir la API interna
│   ├── probar_con_cookie.py  # diagnóstico end-to-end del core con cookie del navegador
│   ├── probar_core.py        # prueba manual del core (cobertura + score) por CLI
│   ├── probar_core_gui.py    # prueba manual del core con mini-GUI
│   ├── probar_concurrencia.py # comprueba si Win bloquea el uso simultáneo de la misma cuenta (se corre en varias máquinas a la vez)
│   ├── medir_keepalive.py    # mide cuánto sobrevive la sesión con pings reales cada N min (mide edad de sesión, clasifica la muerte)
│   ├── medir_sesion.py       # mide la vida real de una PHPSESSID sin actividad, para calibrar el keepalive
│   ├── coords_prueba.txt     # 49 coordenadas públicas (polígono de Lima) que medir_keepalive.py rota por ping
│   ├── generar_iconos.py     # NUEVO 2026-09-25: dibuja con Pillow (dev-only) los .ico/.png de assets/icons/ y de la extensión
│   └── preparar_capas.py     # NUEVO 2026-10-09: datos_capas/ (KMZ, KML de fraude, zonas.txt) -> validator_app/data/capas.json.gz
├── assets/
│   └── icons/                # NUEVO 2026-09-25: agent.ico/.png (--icon de build.ps1), owner.ico/.png (--icon de build-owner.ps1)
├── generator/
│   ├── generar.py            # generador de códigos de activación (SOLO encargado)
│   ├── owner_app.py          # consola gráfica: códigos + estado proxy + renovación
│   └── private_key.pem       # NUNCA se sube al repositorio (ver .gitignore)
├── docs/                     # documentación técnica permanente (inmutable)
│   ├── arquitectura.md
│   ├── proxy-deploy.md
│   ├── proxy-config.md
│   ├── rotacion-credenciales.md
│   ├── escalabilidad-remota.md
│   ├── historial-agents.md   # NUEVO 2026-10-07: tareas completadas + bitácora/cierres archivados de AGENTS.md
│   └── diagramas/            # NUEVO 2026-09-27: 8 diagramas PlantUML (.puml)
├── resumenes/                # snapshots diarios inmutables (2026-08-19, -25, -26, -27, ...)
│   └── <fecha>.md
├── tests/
│   ├── test_fields.py
│   ├── test_captura_guard.py
│   ├── test_api.py
│   ├── test_prueba_core.py
│   ├── test_medir_keepalive.py
│   ├── test_proxy.py        # keepalive + endpoints /local/* (FastAPI TestClient)
│   ├── test_login_asistido.py  # captura de PHPSESSID + dispatch de rotate_creds
│   ├── test_instalar_extension.py  # _crx_id + updates.xml
│   ├── test_session_config.py  # cookie standalone (Fase 3)
│   ├── test_activation.py    # verificación RSA y diagnósticos de código
│   ├── test_generator.py     # firma y ubicación segura del PEM
│   ├── test_owner_app.py     # lógica de la consola owner (estado, reinicio elevado, actualizaciones)
│   ├── test_updater.py       # actualizador del agente (por commit) y descarga/reemplazo
│   ├── test_updater_owner.py # actualizador de la consola owner (por SHA-256)
│   ├── test_gui_activacion.py  # activacion_vigente(), normalizar_url_proxy, resumir_error
│   ├── test_install_bat.py   # guardas estáticas de install_service.bat
│   └── test_diagramas.py     # guardas estáticas de docs/diagramas/*.puml
└── validator_app/
    ├── __init__.py
    ├── version.py            # SHA + tag embebidos (autogenerado en build)
    ├── core/                 # api.py (login, score, cobertura) + session.py · geo.py (reglas de venta por zona: KML/KMZ, distancias, decidir_venta) · capas_local.py (carga de capas con garantia) · direccion.py (direccion de unas coordenadas: parsers Geofinder/OSM y respaldo con aviso)
    ├── data/                 # capas.json.gz embebido en el .exe (GITIGNORED: datos de terceros)
    ├── gui/                  # main_window.py, fields.py, session_config.py (cookie standalone) · map_page.py (pagina Mapa) · limites_mapa.py (encierra el mapa en Peru: zoom minimo 5 + bbox) · tiles.py (tiles de OSM con el User-Agent del proyecto: OSM bloquea "TkinterMapView") · ficha.py (ficha del cliente copiable: dato por dato o todo junto) · zonas.py (textos/plan del score)
    ├── activation/           # fingerprint.py, signer.py, state.py
    ├── updater/              # check.py, download.py (agente por commit; owner por SHA-256)
    └── proxy/                # proxy local para los agentes de la LAN (25 hoy, 41 previstos)
        ├── __init__.py
        ├── config.py         # Pydantic Settings (lee config.yaml + env)
        ├── config.yaml       # GITIGNORED (secretos reales)
        ├── config.yaml.example  # plantilla en repo
        ├── server.py         # FastAPI app + endpoints (incl. GET /api/capas) + ValidatorAPI wrapper + keepalive
        ├── geofinder.py      # token OAuth de Equifax + direccion de coordenadas (GET /api/direccion); credencial geofinder_basic solo en config.yaml
        ├── capas.py          # CapasCache: reglas de venta (My Maps -> KML) con copia en disco; la URL va solo en config.yaml
        ├── client.py         # ProxyClient para agentes .exe
        ├── winsw.xml         # config servicio Windows
        ├── install_service.bat   # instala servicio (winsw, tokens, Chromium, icono Escritorio)
        ├── uninstall_service.bat # desinstala servicio
        ├── rotate_creds.py   # CLI renovar sesión (fallback): asistido / --manual / --preview
        ├── login_asistido.py # captura la PHPSESSID con navegador (Playwright, HttpOnly)
        ├── _instalar_extension.py  # empaqueta + fuerza-instala la extensión de Chrome
        ├── extension/        # extensión MV3 "Renovar sesion WinForce" (vía principal de renovación)
        └── .browser_profile/ · .extension_build/ · *.pem · *.crx · updates.xml  # GITIGNORED
```

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
### 1. Mapa interactivo de cobertura — PRIMERA VERSIÓN HECHA (2026-10-09; en el Release v2026.10.13)
Página "Mapa" (`gui/map_page.py`, `tkintermapview`) + reglas de venta por zona (`core/geo.py`):
bloqueada/fraude → no se vende ni se consulta el score; Preferente 2 → score ≥ 401, resto ≥ 201;
sin cobertura pero con cobertura a ≤ 300 m → "extensible" (confirma el asesor). Las capas van
embebidas en el .exe y solo la cobertura en vivo depende de WinForce. `core/api.py` NO cambió.
Falta: detección automática de "no cruzar avenida de doble vía" (hoy es visual) y dibujar los
huecos de los polígonos. La capa "Zona F" (copia de Fraude) se retiró el 2026-10-13; el mapa solo
muestra Perú y la barra del panel lateral es fija.

### 2. Ofertas / catálogo de venta
Al confirmar cobertura + score, sugerir planes por zona. Debe mantenerse separado
del núcleo (`core/`) para no acoplarlo a datos comerciales.

### 3. Instalador + auto-actualizador (bootstrap)
Cuando la app crezca (mapa + ofertas), un ejecutable pequeño que descargue/instale
la app y permita actualizaciones automáticas. El módulo `updater/` ya es la base.
NO necesario hoy: un .exe portable se ancla igual a la barra de tareas.

### 4. Servidor de activación en línea
Para revocar activaciones y controlar instalaciones a distancia. Requiere hosting.
La activación offline (RSA) actual ya es extensible a un modo online.

### 5. Validación por lotes (CSV/Excel)
Procesar varios clientes desde un archivo. Debe respetar el retardo configurable
entre validaciones para no saturar la API ni levantar sospechas de automatización.

### 6. Historial / CRM básico
Guardar validaciones pasadas (local, SQLite) para consulta rápida sin re-validar.
SQLite ya viene en Python; no añade dependencias.

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
3. **Observar las muertes de la sesión de WinForce** (~10 min tras renovar el 2026-10-02): hipótesis
   del dueño = login ajeno con la misma cuenta; pasos en [`docs/rotacion-credenciales.md`](docs/rotacion-credenciales.md) →
   "Cómo investigar una muerte de sesión". El tope de 9.5 h es una medición no concluyente.
4. **Probar el pendrive en una PC owner limpia** ([`docs/proxy-deploy.md`](docs/proxy-deploy.md) → "Instalación con pendrive").
5. **Firma de código** de los `.exe` (Smart App Control en Windows 11).
6. **Pasar `W11-JSConnect-Win-Coverage` (archivado) a privado**, solo cuando sus `.exe` ya se
   hayan actualizado a `v2026.10.07`.
7. **Que el agente lea la URL y el token de un archivo del pendrive** (idea acordada; después de la
   Fase 5, con su propio Release).
7b. **Mapa de cobertura**: probarlo con los asesores y llevar la URL de `capas_kml_url` al
   `config.yaml` del proxy (opcional: sin ella los agentes usan las reglas embebidas; `/api/capas`
   responde 503 sin ella, lo esperado). Release publicado en `v2026.10.13`. La "Zona F" ya se retiró.
    **`v2026.10.23`** arregla el mapa sin fondo (OSM bloqueaba el User-Agent `TkinterMapView`).
8. Decidir si la app llama a `actualizar_score_cliente` (registra score) o basta con leerlo —
   **PENDIENTE** (diferido por el usuario).
9. Evaluar si la app debe crear el lead final (`POST controllers/newsearch.php`, multipart) —
   **PENDIENTE** (diferido por el usuario).
10. Etapa C.12 (modo standalone con `PHPSESSID`, opcional) — para otro momento.
11. Monitorear la primera semana de producción (sesión del proxy, RUC/CE) — observación, no una
    tarea con pasos.

## Historial (bitácora del proyecto)
> El historial por fases y los cierres de sesión anteriores (2026-08-18 → 2026-10-02) están en
> [`docs/historial-agents.md`](docs/historial-agents.md). Aquí queda **solo el último cierre**;
> al escribir el siguiente, este se mueve a ese archivo (ver su cabecera).

### Cierre de la sesión 2026-10-13 [CONTEXTO PARA LA SIGUIENTE — dirección Geofinder, ficha copiable, mapa solo Perú, Release v2026.10.13]

- **Para qué**: el asesor necesita la **dirección** de las coordenadas y los **datos del documento**
  para copiarlos a WinForce sin reescribir, y el mapa no debía cargar el mundo entero.
- **Hecho** (commits `2247945`, `5809c72`, `43dd799`, `9ac9fbe`, `ae07541`, en `main`):
  - **Dirección**: Geofinder (API de Equifax que usa WinForce) vía el proxy: `proxy/geofinder.py`
    (token OAuth `client_credentials` cacheado ~24 min; flujo del navegador: `coordinates-ref` con
    el punto tal cual → punto ajustado → `coordinates`), `GET /api/direccion`, `geofinder_basic`
    **solo** en el `config.yaml` del proxy y `/health.geofinder`. Respaldo OpenStreetMap
    (`core/direccion.py`) con **banner rojo** "DIRECCIÓN APROXIMADA… NO es la de WinForce" y el motivo.
    `DIRECCIÓN DETALLADA` sale como Geofinder: `DETALLE (DISTRITO, PROVINCIA, DEPARTAMENTO)`.
  - **Ficha copiable** (`gui/ficha.py`) en Cobertura/Score y Mapa: dato por dato y **Copiar todo**:
    APELLIDOS Y NOMBRES, DOCUMENTO DE IDENTIDAD, NACIONALIDAD Y FECHA DE NACIMIENTO, SCORE (rango),
    DIRECCIÓN DETALLADA, DEPARTAMENTO, PROVINCIA, DISTRITO. Datos de la persona del reporte
    (`persona`, módulos 602/877) como campo opcional de proxy y cliente. El score del Mapa ya se copia.
  - **Mapa solo Perú** (`gui/limites_mapa.py`: zoom mínimo 5 + borde por bbox) y **barra de
    desplazamiento fija** en el panel lateral (sin saltos al perder el foco).
  - **Zona F retirada** (era copia de Fraude; `capas_de_json` la ignora en datos viejos).
  - **Actualizar el proxy sin reinstalar**: `tools/empaquetar_actualizacion_proxy.ps1` (solo código,
    sin secretos) + [`docs/proxy-deploy.md`](docs/proxy-deploy.md).
- **Verificado en vivo** (proxy de la oficina, DNI de prueba): dirección idéntica a WinForce para
  `-12.02894226054663, -77.0938731550291`; orden del paréntesis confirmado con un punto de Lima;
  score + `persona` + Copiar todo con el formato pedido.
- **Hallazgos**: el proxy de la oficina era anterior al 2026-10-09 (404 en `/api/direccion` y
  `/api/capas`): el agente cayó a OpenStreetMap, que devuelve el objeto OSM más cercano ("Mercado 3
  de enero, 4298") y no la dirección de Equifax. El reporte **no trae lugar de nacimiento**; `Nombres`
  llega como nombre completo (APELLIDOS NOMBRES) y en personas con RUC 10 `RazonSocial` repite ese
  nombre. Un "nombre de otro DNI" fue un DNI mal digitado. `captura.py` oculta `Authorization`: la
  credencial de Geofinder se saca a mano con F12.
- **Decisiones del usuario**: respaldo OSM visible y copiable pero con alerta roja; solo documento →
  dirección en blanco; lugar de nacimiento reemplazado por nacionalidad; apellidos primero.
- **Estado**: tests 421 → **494**, `ruff` limpio. **Release `v2026.10.13` PUBLICADO**
  (2026-10-13, agente + consola owner, tag en `5abb5d2`, SHA-256 verificados contra las notas). El proxy de la oficina ya corre
  Geofinder, pero con un `core/api.py` anterior al fix de nombres (funciona igual con el agente nuevo).
- **Pendiente**:
  - recopiar `proxy-update\` a la PC owner cuando convenga (fix de nombres en `core/api.py`);
  - `capas_kml_url` en el `config.yaml` del proxy (opcional); probar el mapa con asesores;
  - detección automática de "no cruzar avenida de doble vía" (vías OSM) y dibujar los huecos;
  - los de siempre: reactivar los agentes (**NO borrar `huellas_legacy()`**), reemplazar a mano el
    `.exe` del owner si sigue en `v2026.10.07`, probar un agente W10 contra el owner W11, el archivo
    del pendrive con URL+token, firma de código, observar las muertes de sesión y probar el pendrive
    en una PC limpia.
