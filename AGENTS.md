# AGENTS.md — Proyecto JSConnect-Win-Coverage

## Resumen
Aplicación de escritorio para Windows (call center de un proveedor de servicio de
internet) que acelera la validación de clientes: **cobertura de servicio**
(coordenadas) y **score crediticio** (DNI 8 dígitos / RUC 11 dígitos / Carnet de
Extranjería 9 caracteres alfanumérico). En lugar de scrapear HTML, replica las
llamadas HTTP (JSON) a la API interna del sistema de validación, devolviendo la
información en milisegundos, sin cargar página, sin mapa ni navegador.

## Stack
- Python 3.14+ (usar 3.13 si una librería no soporta 3.14)
- HTTP: `requests` · GUI: `tkinter` (incluido) · Credenciales: `keyring`
- Licencias/activación: `cryptography` (RSA, firma asimétrica)
- Empaquetado: `PyInstaller` (un único .exe portable)
- Dev: `playwright` (solo captura, NO va en el .exe) · Tests: `pytest` · Lint: `ruff`
- Plataforma: Windows 10 (única soportada)

## Estructura
```
JS-Win-Coverage/              (raíz del proyecto)
├── main.py                   # punto de entrada de la app
├── requirements.txt          # dependencias de producción
├── requirements-dev.txt      # dependencias de desarrollo
├── requirements-proxy.txt    # dependencias del proxy (fastapi, uvicorn, pydantic)
├── build.ps1                 # embebe commit SHA + empaqueta con PyInstaller
├── publish-release.ps1       # prepara el Release en GitHub (asset .exe + SHA-256)
├── AGENTS.md                 # reglas del proyecto, contexto, historial y pendientes
├── PlanesAprobados.md        # COLA de planes aprobados (lo implementado se saca)
├── TestingLog.md             # metodología TDD + bitácora de pruebas
├── README.md                 # documentación pública (español + inglés)
├── ResumenDelDia.md          # historial del día en curso (resumen de cierre)
├── Escalabilidad.md          # guía para futuros programadores (escalabilidad remota)
├── anotaciones.md            # glosario técnico para futuros devs
├── tools/
│   └── captura.py            # herramienta Playwright para descubrir la API interna
├── generator/
│   ├── generar.py            # generador de códigos de activación (SOLO encargado)
│   └── private_key.pem       # NUNCA se sube al repositorio (ver .gitignore)
├── docs/                     # documentación técnica permanente (inmutable)
│   ├── arquitectura.md
│   ├── proxy-deploy.md
│   ├── proxy-config.md
│   ├── rotacion-credenciales.md
│   └── escalabilidad-remota.md
├── resumenes/                # historial diario inmutable
│   └── 2026-08-19.md
├── tests/
│   ├── test_fields.py
│   ├── test_captura_guard.py
│   └── test_api.py
└── validator_app/
    ├── __init__.py
    ├── version.py            # SHA + tag embebidos (autogenerado en build)
    ├── core/                 # api.py (login, score, cobertura) + session.py
    ├── gui/                  # main_window.py, fields.py
    ├── activation/           # fingerprint.py, signer.py, state.py
    ├── updater/              # check.py, download.py
    └── proxy/                # NUEVO: proxy local para 20 agentes LAN
        ├── __init__.py
        ├── config.py         # Pydantic Settings (lee config.yaml + env)
        ├── config.yaml       # GITIGNORED (secretos reales)
        ├── config.yaml.example  # plantilla en repo
        ├── server.py         # FastAPI app + endpoints + ValidatorAPI wrapper
        ├── client.py         # ProxyClient para agentes .exe
        ├── winsw.xml         # config servicio Windows
        ├── install_service.bat   # instala servicio (descarga winsw, genera tokens)
        ├── uninstall_service.bat # desinstala servicio
        └── rotate_creds.py   # CLI owner: rota credenciales WinForce (RDP)
```

## Comandos
- Instalar producción: `pip install -r requirements.txt`
- Instalar desarrollo: `pip install -r requirements-dev.txt`
- Instalar proxy (PC oficina): `.\validator_app\proxy\install_service.bat` (como Admin)
- Navegador de captura: `python -m playwright install chromium`
- Ejecutar la app: `python main.py`
- Build: `powershell -ExecutionPolicy Bypass -File build.ps1`
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
  va acompañado de su test. Bitácora detallada en `TestingLog.md`.

## README.md (obligatorio)
- El README.md debe mantenerse **ACTUALIZADO** con todos los cambios relevantes
  (funciones nuevas, comandos, estructura, configuración) **ANTES de subir el
  repositorio a GitHub**. Es responsabilidad de quien toque el código.
- Está redactado en **español primero y luego en inglés** dentro del mismo archivo.

## Versionado y actualizaciones
- La "versión" = SHA del commit + tag del Release.
- `build.ps1` lee `git rev-parse HEAD` y lo embebe en `validator_app/version.py`.
- La app consulta `GET /repos/{owner}/{repo}/releases/latest` y compara el commit
  del Release con el embebido. Si difieren → ofrece descargar el asset .exe.
- El .exe descargado se valida por SHA-256 (checksum publicado en las notas del
  Release) antes de reemplazar al actual.
- Límite de API sin autenticación: 60 consultas/hora (suficiente para botón manual).

## Implementaciones futuras
### 1. Mapa interactivo de cobertura
Mostrar el punto validado sobre un mapa (propio) para dar contexto visual al agente.
No depende de la API interna: la cobertura ya llega como dato. Tkinter `Canvas` o
WebView embebido. La validación central (`core/api.py`) NO debe cambiar.

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
- **`ResumenDelDia.md`** = historial del DÍA. Lleva la fecha dentro y se va
  actualizando a medida que se trabaja (lo que se hizo, lo que se pospuso, lo que
  queda pendiente al volver). Sirve de base para el resumen de cierre de sesión.
- **`PlanesAprobados.md`** es una **COLA de trabajo, NO un historial**: cada vez que
  se implementa algo que estaba en la cola, se **saca** de ahí (se marca como hecho o
  se elimina). El historial de lo hecho vive en AGENTS.md (bitácora) y en
  ResumenDelDia.md.
- **`README.md`** se actualiza con los avances cuando el plan implementado lo amerite
  (seguridad, funciones nuevas, estructura, comandos, etc.).
- **Cierre de sesión**: al terminar una sesión se actualiza AGENTS.md (Historial) con
  el resumen de lo hecho en el día. Después, al confirmar el usuario que ya terminó la
  sesión, se le pregunta si desea presentar el resumen del día desde
  `ResumenDelDia.md`.
- **Rotación de resúmenes** (al abrir un día nuevo): el contenido de `ResumenDelDia.md`
  se reparte en dos destinos que NO compiten, cada uno con un rol distinto:
  - `resumenes/<fecha>.md`: snapshot COMPLETO e inmutable de la sesión que cierra (todo
    el detalle, tal cual quedó en `ResumenDelDia.md`).
  - `HistorialResumenes.md`: entrada CONDENSADA de esa sesión, agregada arriba del todo
    (orden cronológico inverso) — es el índice navegable, no el detalle completo.
  - Después de rotar, `ResumenDelDia.md` empieza limpio con la fecha del día nuevo.

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
   anotar en `ResumenDelDia.md` lo que se hizo, y sacar de la cola de
   `PlanesAprobados.md` lo que ya se implementó. Basta con narrar lo trabajado; esta
   anotación intermedia NO exige re-verificar el estado global del proyecto.

3. **Al CERRAR sesión — actualización auditada**
   Antes de escribir el cierre, auditar contra el código lo hecho en la sesión
   (¿existen los archivos/funciones que se van a declarar completados?, ¿`pytest` y
   `ruff check .` en verde?). Recién con eso verificado:
   - Marcar `[COMPLETADO]` en `## Tareas pendientes` lo que se comprobó implementado
     — **sin borrarlas de la lista**, se dejan visibles para trazabilidad.
   - Añadir la entrada correspondiente en `## Historial` + un nuevo
     `### Cierre de la sesión <fecha>`.
   - Actualizar `README.md` si el cambio lo amerita (seguridad, funciones nuevas,
     estructura, comandos) y `docs/` si cambió algo técnico permanente.
   - Rotar `ResumenDelDia.md` según la regla de rotación de arriba.

   **Regla de oro**: nunca marcar algo como completado o pendiente en la documentación
   sin haberlo comprobado en el código.

## Archivos de documentación (mapa de conocimiento)
Estos archivos son el punto de partida de cualquier persona (o IA) que retome el
proyecto. Leerlos en este orden ANTES de tocar código:
1. **AGENTS.md** (este archivo): reglas del proyecto, contexto, historial y tareas
   pendientes. Es la puerta de entrada.
2. **PlanesAprobados.md**: **cola** de trabajo con los planes YA aprobados, el
   razonamiento y las decisiones tomadas (ej: decisión de autenticación). Contiene
   además diseños listos para implementar. Leer antes de empezar una fase para no repetir
   análisis ni ignorar decisiones. Se actualiza SACANDO de la cola lo implementado.
3. **TestingLog.md**: metodología TDD del proyecto (test rojo -> verde), inventario de
   tests y bitácora de problemas -> causa -> solución. Leer antes de escribir o
   modificar tests.
4. **README.md**: documentación pública del proyecto (español primero, luego inglés).
   Mantenerla actualizada ANTES de subir a GitHub.
5. **ResumenDelDia.md**: historial del día en curso (fecha dentro, se actualiza al
   trabajar). Fuente del resumen de cierre de sesión.
6. **Escalabilidad.md**: guía para futuros programadores (cómo escalar a remotos).
7. **anotaciones.md**: glosario técnico para términos que futuros devs desconozcan.
8. **docs/**: documentación técnica permanente (arquitectura, deploy, config, rotación, escalabilidad).
9. **HistorialResumenes.md**: índice cronológico condensado de resúmenes pasados (lo
   más nuevo arriba). Ver ahí si se necesita ubicar rápido en qué sesión pasó algo.
10. **resumenes/**: snapshots COMPLETOS e inmutables de cada sesión pasada
    (`resumenes/<fecha>.md`), con el detalle íntegro que tenía `ResumenDelDia.md` al
    cerrar esa sesión.

Convención para MD futuros: cuando una fase o plan genere un documento nuevo (ej:
DecisionesArquitectura.md, ManualOperador.md), se registra AQUÍ su existencia, propósito
e importancia, para que el mapa de conocimiento nunca quede incompleto.

## Notas de seguridad
- No subir a GitHub: llave privada de activación, credenciales reales, archivos de
  captura (`tools/captura.json` puede contener datos sensibles aunque esté redactado).
- Las credenciales de Win rotan cada 1-2 meses: mantener siempre centralizada su
  actualización (proxy local) o por keyring por máquina; nunca en el repo.
- El repo es público: el código de la API interna será visible. Los endpoints ya son
  públicos de facto (los usa el navegador), pero revisar antes de publicar.
- **Proxy**: `config.yaml`, `proxy_token.txt`, `admin_key.txt` son GITIGNORED — solo en PC proxy.
- Repositorio remoto: https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Tareas pendientes
1. **FASE 0 DOCUMENTACIÓN** [COMPLETADO — verificado 2026-08-26]: `docs/` (5 archivos), `Escalabilidad.md`, `anotaciones.md`, `resumenes/` existen y están al día.
2. **FASE 1 PROXY SERVER** [COMPLETADO — verificado 2026-08-26]: `validator_app/proxy/` completo — `server.py` (7 rutas: `/api/cobertura`, `/api/score`, `/health`, `/admin/config`, `/admin/login`, `/admin/rotar`, `/admin/status`), `config.py`, `winsw.xml`, `install_service.bat`, `uninstall_service.bat`.
3. **FASE 2 CORE ADAPTADO** [COMPLETADO — verificado 2026-08-26]: `auto_relogin_if_needed()` (`core/api.py:267`), `get_session_cookies()`/`set_session_cookies()` (`:282`/`:288`) implementados y usados en `validar_cobertura`/`validar_score`.
4. **FASE 3 CLIENTE PROXY** [COMPLETADO — verificado 2026-08-26]: `ProxyClient` (`proxy/client.py`) con retries, excepciones tipadas (`ProxyConnectionError`, `ProxyAuthError`, `ProxyServerError`, `ProxyTimeoutError`), `from_discovery()`, `from_keyring()`.
5. **FASE 4 GUI CONFIG PROXY** [COMPLETADO — verificado 2026-08-26]: menú "⚙️ Configuración" (`gui/main_window.py:33`) → diálogo modal `_abrir_config_proxy` (`:206`) con IP:puerto + token + keyring local.
6. **FASE 5 DEPLOY & DOCS** [COMPLETADO — verificado 2026-08-26]: `rotate_creds.py`, `README_PROXY.md`, `requirements-proxy.txt` presentes.
7. **Prueba real del core** con credenciales del usuario [COMPLETADO — verificado 2026-08-27]: login manual (2FA) + cookie inyectada vía `tools/probar_con_cookie.py` → cobertura SI (HORIZONTAL, celda 8764) → score (423, MUY ALTO). Ver Historial "Prueba real end-to-end" para el detalle de los 2 bugs encontrados y corregidos en el camino.
8. Decidir si la app debe llamar a `actualizar_score_cliente` (registra score) o basta con leerlo — **PENDIENTE**.
9. Conectar GUI a core (keyring para credenciales, resultados del core) end-to-end y ajustar `main_window.py` — **PENDIENTE de verificación real** (la config del proxy sí está conectada; falta confirmar el flujo completo login→cobertura→score contra la GUI).
10. Evaluar si la app debe crear el lead final (`POST controllers/newsearch.php`, multipart) — **PENDIENTE**.
11. **Sistema de códigos de error** [COMPLETADO — verificado 2026-08-26]: excepciones tipadas con `code` + diccionario `ERROR_CODES` en `api.py`, 35 tests pasando, ruff limpio.
12. **Decisión de geodata del score** [COMPLETADO — verificado 2026-08-27]: **opción C (payload mínimo)** confirmada — el score respondió correctamente enviando solo coordenadas + documento, con todos los campos de geodata vacíos en el payload. No hace falta replicar la geoapi de Equifax ni pedir datos manuales.
13. **`tools/probar_con_cookie.py`** [NUEVO, 2026-08-27]: herramienta de diagnóstico contra el servidor real (cookie de sesión capturada del navegador). Ya probó su valor detectando 2 bugs reales — conservar para futuras revalidaciones.

## Historial (bitácora del proyecto)
### Fase 0 — Descubrimiento de la API interna (COMPLETADA)
**2026-08-18**
- [Descubrimiento] El sistema usa una API interna JSON en `appwinforce.win.pe/controllers/*.php`
  más la API externa de Equifax (`api.latam.equifax.com`). No requiere scraping.
- [Descubrimiento] **Login**: `POST /controllers/acceso.php` con
  `accion=iniciar_sesion&username=...&password=...`. La sesión se mantiene con la cookie
  `PHPSESSID` (dominio appwinforce.win.pe). Las llamadas a `login.microsoftonline.com`
  (telemetría de Azure AD) NO son necesarias para la sesión.
- [Descubrimiento] **Cobertura**: `GET /controllers/coordenada.php?accion=validar_cobertura&data[latitud]=...&data[longitud]=...`
  → `{"response":"success","cobertura":"SI|NO","tipo":"HORIZONTAL|...","id_celda":"9754","comment":"..."}`.
  Ejemplo con cobertura: `cobertura=SI, tipo=HORIZONTAL, id_celda=9754`.
- [Descubrimiento] **Score**: `POST /controllers/cliente.php` con `accion=score_cliente`
  y muchos campos `data[...]`. La respuesta es `text/html` pero su contenido es JSON:
  `{"response":"success","data":"<JSON-string con el reporte SOAP de Equifax>"}`.
  El puntaje está en `data → soapBody.ns3GetReporteOnlineResponse.ns2ReporteCrediticio
  → Modulos.Modulo[].Data.ns3ResumenScoreRP3.Puntaje` (ej: 423) con `NivelRiesgo`
  (ej: MUY ALTO); la deuda en `ResumenDeuda.DeudaTotal`. Luego el sitio confirma con
  `actualizar_score_cliente` (envía `data[score_cliente]=423`).
- [Descubrimiento] **Tipos de documento**: `GET /controllers/document.php?accion=lista_documento`
  → 1=DNI, 2=Carnet de extranjería, 3=RUC, 4=Pasaporte.
- [Descubrimiento] **Geodata**: la dirección/distrito/ubigeo/código postal/segmentación NO
  las devuelve appwinforce: el navegador las calcula llamando DIRECTAMENTE a la geoapi de
  Equifax (oauth `client_credentials` → endpoints `coordinates`, `coordinates-ref`,
  `intersectz`, `capas`). Las credenciales van en el header `Authorization` (Basic) y están
  embebidas en el JS del sitio.
- [Descubrimiento] El flujo termina creando el lead con `POST /controllers/newsearch.php`
  (multipart/form-data). No es imprescindible para la validación en sí.
- [Problema→Solución] La contraseña del login quedó en TEXTO PLANO en captura.json:
  `redact_dict()` solo redactaba payloads JSON, y el login es formulario URL-encoded.
  → Nueva función `redact_form()` (parse_qsl + redactar campos sensibles) y marcador para
  multipart. Verificado: `password=%2A%2A%2A%2A%2A%2A%2A%2A`.
- [Problema→Solución] Las respuestas HTML (el score) se descartaban y el reporte se perdía.
  → Guardar el body crudo (truncado a 5000) cuando el content-type es text/json/xml.
- [Problema→Solución] La consola parecía congelada: Python bufferizaba la salida.
  → `sys.stdout.reconfigure(line_buffering=True)` en captura.py (+ usar `python -u`).
- [Problema→Solución] La guarda de instancia única daba falso positivo: el stub de Python de
  Microsoft Store (`WindowsApps\python.exe`) lanza el python real y ambos llevan
  `tools/captura.py` en su línea de comandos. → Excluir ancestros del árbol de procesos.
- [Problema→Solución] El usuario cerraba su Chrome normal en vez de la ventana del script.
  → Ventana maximizada + botón verde "TERMINAR CAPTURA" inyectado (setea
  `window.__captura_fin`) + auto-cierre `--minutos N` + evento `page.on("close")`.
- [Avance] captura.py validada end-to-end: 44 registros, cobertura SI y NO capturadas,
  score 423 extraído del reporte, password redactado, ruff limpio y 11 tests pasando.

### Fase 1 — Núcleo (core) [COMPLETADA]
**2026-08-18**
- [Avance] Construido `validator_app/core/session.py` (sesión `requests` con headers de
  navegador, tiempos de espera) y `validator_app/core/api.py` completo:
  `login()` (POST acceso.php + verificación de sesión activa vía `operador.php`),
  `validar_cobertura()` (GET coordenada.php) y `validar_score()` (POST cliente.php
  con `score_cliente` + parseo del reporte SOAP de Equifax).
- [Descubrimiento] El login del sitio usa `dataType:'json'` con `data[0].response` y
  `data[0].comment`; la respuesta de login puede llegar con el body vacío, por eso el
  login se verifica con una segunda llamada autenticada (`operador.php?accion=get_operador`).
- [Descubrimiento] La respuesta de `score_cliente` es `{"response":"success","data":"<JSON-string>"}`
  con el reporte SOAP de Equifax (doble-encodificado). El puntaje está en
  `ns3ResumenScoreRP3.Puntaje` (ej: 423) y la deuda en `ResumenDeuda.DeudaTotal`.
- [Problema→Solución] El reporte Equifax puede superar los 5000 caracteres y se truncaba
  (JSON inválido). → `MAX_BODY_CHARS` subido a 200000.
- [Problema→Solución] La búsqueda de credenciales de Equifax requiere los JS del sitio
  (tras el login). → Nueva opción `python tools/captura.py --guardar-js` que guarda los
  archivos JS cargados en `tools/js/` (gitignored).
- [Avance] Tests del núcleo (`tests/test_api.py`, 14 casos): payloads de login/cobertura/
  score, parseo del reporte, errores. Total del proyecto: 25 tests, ruff limpio.
  Bitácora TDD (problemas y soluciones) en `TestingLog.md`.

### Fase 1.5 — Decisión de Autenticación: Proxy Local (DECIDIDA 2026-08-25)
**2026-08-25** — Sesión de definición arquitectónica
- [Hallazgo crítico] Login WinForce redirige a `login.microsoftonline.com` para **2FA Microsoft** con la misma cuenta. Esto hace **inviable la prueba de concurrencia** planificada (4-5 máquinas simultáneas requerirían 2FA manual cada una).
- [Decisión] **Opción B (Proxy Local) APROBADA** por las razones documentadas en `PlanesAprobados.md`:
  - 1-2 sesiones WinForce desde UNA IP (PC oficina) → sin riesgo bloqueo
  - Credenciales SOLO en keyring de PC proxy → rotación = actualizar 1 PC
  - Offline (LAN), costo ~$0, escalable a remotos via VPN (Tailscale)
- [Stack Proxy Confirmado]:
  - Framework: **FastAPI + uvicorn** (concurrencia nativa, validación Pydantic, Swagger)
  - Auth agentes: **Token compartido 256-bit + validación IP LAN** (`192.168/16`, `10/8`, `172.16/12`, `100.64/10` para Tailscale)
  - Auth admin: **API Key admin separada** (`X-Admin-Key`) para endpoints `/admin/*`
  - Ejecución: **winsw service** (`JSWinProxy` / "JSConnect Win Proxy") — auto-inicio, auto-restart, logs eventos
  - Config: **`config.yaml` gitignored + `config.yaml.example` en repo** — `install_service.bat` genera tokens auto
  - Requirements: **`requirements-proxy.txt` separado** (.exe agentes no arrastra fastapi/uvicorn)
  - GUI: **Diálogo modal** desde menú "⚙️ Configuración" (mueve "Buscar actualizaciones" ahí)
  - Docs: **Carpeta `docs/` permanente** ≠ `AGENTS.md/PlanesAprobados.md` volátiles
- [Acuerdos explícitos 2026-08-25]:
  1. Token proxy auto-generado en `install_service.bat` + mostrado en consola + guardado en `proxy_token.txt`
  2. Admin key igual (auto-generada + `admin_key.txt`)
  3. Servicio: `JSWinProxy` / Display "JSConnect Win Proxy"
  4. Puerto 8080 por defecto; `install_service.bat` verifica y permite cambiar si ocupado
  5. Menú GUI: "⚙️ Configuración" → items: "Configurar Proxy", "Buscar actualizaciones"
  6. Escalabilidad remota: VPN (Tailscale) + mismo proxy + mismo token; endpoint `/admin/config` para auto-discovery
  7. Documentación técnica en `docs/` (permanente); glosario en `anotaciones.md`
  8. `requirements-proxy.txt` con comentario explicando tradeoff separación vs simplicidad

### Fase Proxy — Implementación [COMPLETADA, verificada 2026-08-26]
- [Avance] `validator_app/proxy/server.py` (FastAPI): 7 rutas — `POST /api/cobertura`,
  `POST /api/score`, `GET /health`, `GET /admin/config`, `POST /admin/login`,
  `POST /admin/rotar`, `GET /admin/status`. Middleware de auth por token (agentes) y
  `X-Admin-Key` (admin), validación de IP LAN (`_ip_in_allowed_networks`).
- [Avance] `validator_app/proxy/config.py`: `ProxyConfig` (Pydantic Settings) con
  `proxy_token`/`admin_key` (hex 64 chars), redes permitidas (LAN + rango Tailscale
  `100.64/10`), timeouts, `session_max_idle_seconds=120`.
- [Avance] `validator_app/proxy/client.py`: `ProxyClient` con retries
  (`_request_with_retry`), excepciones tipadas (`ProxyConnectionError`,
  `ProxyAuthError`, `ProxyServerError`, `ProxyTimeoutError`), `from_discovery()`,
  `from_keyring()`/`save_to_keyring()` (servicio `JSWinClient`).
- [Avance] `validator_app/proxy/rotate_creds.py`: CLI para rotar credenciales WinForce
  vía RDP (extrae `PHPSESSID`, valida sesión, guarda en keyring del proxy).
- [Avance] `validator_app/core/api.py`: `auto_relogin_if_needed()` (re-login si pasó
  `session_max_idle` desde la última actividad), `get_session_cookies()` /
  `set_session_cookies()` para persistencia, usados en `validar_cobertura`/`validar_score`.
- [Avance] `validator_app/gui/main_window.py`: menú "⚙️ Configuración" → diálogo modal
  `_abrir_config_proxy` (IP:puerto + token, toggle mostrar/ocultar, "Probar conexión"),
  guardado/carga vía `ProxyClient.from_keyring()`/`save_to_keyring()`.
- [Verificado] `python -m pytest -q` → 35 passed. `python -m ruff check .` → All checks passed.

### Decisión de geodata del score [RESUELTA 2026-08-27 — opción C]
  - A) Replicar Equifax: oauth `client_credentials` + reverse-geocoding (igual que el
    navegador). Fiel para cualquier coordenada; requiere credenciales del sitio (extraer
    con `--guardar-js`).
  - B) Entrada manual: pedir al agente distrito/ubigeo/dirección del lead y omitir
    segmentación/nse (en la captura venían vacíos en un caso). Requiere probar qué campos
    son obligatorios.
  - **C) Payload mínimo (GANADORA)**: probado `score_cliente` con coordenadas + documento
    reales y todos los campos de geodata vacíos → el servidor respondió correctamente
    (`valor=423, riesgo=MUY ALTO`). No hace falta replicar la geoapi de Equifax ni pedir
    datos manuales al agente. Ver Historial "Prueba real end-to-end (2026-08-27)".

### Prueba real end-to-end (2026-08-27) — dos bugs encontrados y corregidos
- Primera prueba del proyecto contra el servidor real de WinForce (antes todo se verificaba
  solo con dobles de prueba). Login manual en navegador (2FA) → cookie `PHPSESSID`
  capturada → inyectada en sesión `requests` vía nuevo `tools/probar_con_cookie.py`.
- **Bug 1 — BOM UTF-8 en `coordenada.php`**: el servidor antepone un BOM (`﻿`) a la
  respuesta JSON de cobertura; `resp.json()` de `requests` no lo tolera. `_json()`
  (`core/api.py:453`) lo convertía en "respuesta inesperada" sin mostrar la causa. El
  servidor SIEMPRE respondió bien — el bug era 100% del cliente. Fix: `_json()` reintenta
  `json.loads()` quitando el BOM antes de rendirse. Test de regresión
  `test_cobertura_si_con_bom` (con nueva clase `FakeResponseConBOM` que simula el fallo
  real de `requests.json()`).
- **Bug 2 — doble-encodificado del score no implementado**: `_parsear_score` hacía un solo
  `json.loads(dato)`, pero el servidor real envía **2 capas** (confirmado con diagnóstico:
  profundidad 0 = string de 23702 chars, profundidad 1 = string de 20876 chars, profundidad
  final = dict). Esto ya lo decía la Fase 0 (2026-08-18, "JSON doble-encodificado") pero la
  Fase 1 nunca lo implementó — nunca se detectó porque los tests usaban fixtures con una
  sola capa. Fix: decodificación tolerante a profundidad (hasta 3 iteraciones, tope de
  seguridad) en vez de asumir un número fijo de capas. Test de regresión
  `test_score_parsea_reporte_doble_encodificado`.
- **Resultado**: flujo completo cobertura (SI, HORIZONTAL, celda 8764) + score (423, MUY
  ALTO) verificado contra datos reales. **37 tests pasando, ruff limpio.**
- **Login programático confirmado inviable**: el 2FA de Microsoft bloquea una sesión
  `requests` limpia (mismo hallazgo de Fase 1.5, ahora verificado con credenciales reales)
  — valida la arquitectura de Proxy Local + flujo de cookie ya implementada.
- **Nueva herramienta permanente**: `tools/probar_con_cookie.py` — diagnóstico contra el
  servidor real inyectando una cookie de sesión capturada del navegador. Detecta BOM,
  redirects, profundidad de encoding. Conservar para futuras revalidaciones.

### Cierre de la sesión 2026-08-25 [CONTEXTO PARA LA SIGUIENTE — histórico, ver corrección abajo]
- Se completó **FASE 0 Documentación**: creados `docs/` (5 archivos), `resumenes/2026-08-19.md`, `Escalabilidad.md`, `anotaciones.md`, actualizados `AGENTS.md`, `PlanesAprobados.md`, `README.md`, `ResumenDelDia.md`
- **Decisión arquitectónica definitiva**: Proxy Local (Opción B) — 2FA Microsoft bloquea concurrencia
- Estado general al cierre: Fase 0 completa, Fase 1 (core) completa, Fase 1.5 decidida (Proxy Local), FASE 0 Docs completada
- **Nota de corrección (2026-08-26)**: este cierre decía "listo para FASE 1 Proxy Implementation" como próximo paso, pero según el commit log (`877689f`, `801ce05`, `f63660b`, `7cf7ea1`) las FASES 1–5 del proxy y el sistema de códigos de error **ya se implementaron en commits posteriores el mismo 2026-08-25**, sin que este archivo se actualizara. Ver `### Cierre de la sesión 2026-08-26` para el estado real verificado.

### Cierre de la sesión 2026-08-26 [CONTEXTO PARA LA SIGUIENTE]
- **Auditoría de inicio de sesión**: se detectó que este archivo (entonces `Claude.md` en disco, aunque el tracked de git ya era `AGENTS.md`) tenía las "Tareas pendientes" desfasadas del código real — daba por pendiente todo el proxy (FASES 1–5) y el cierre 2026-08-25 decía "listo para FASE 1", pero el código ya estaba implementado.
- **Verificado en el árbol real**: `validator_app/proxy/` completo (server.py con 7 rutas, config.py, client.py, rotate_creds.py, winsw.xml, install/uninstall .bat), `core/api.py` con `auto_relogin_if_needed()` (`:267`) y persistencia de cookies (`:282`/`:288`), GUI con menú "⚙️ Configuración" y diálogo de proxy (`main_window.py:33`/`:206`). **35 tests pasando, ruff limpio.**
- **Corregido**: archivo en disco renombrado de `Claude.md` a `AGENTS.md` (coincide con el nombre tracked en git y con el título interno; cero referencias rotas, todo el proyecto ya decía "AGENTS.md"). Marcadas `[COMPLETADO]` las tareas 1–6 y 11 de "Tareas pendientes" (dejadas visibles, no borradas). Añadida la regla de auto-actualización (3 momentos: inicio/durante/cierre) y la regla de rotación de resúmenes.
- **Pendiente real para la próxima sesión**: prueba real del core con credenciales (login→cobertura→score), decidir `actualizar_score_cliente`, conectar GUI↔core end-to-end, evaluar creación del lead final, y resolver la decisión de geodata del score (A/B/C, ver arriba).

### Cierre de la sesión 2026-08-27 [CONTEXTO PARA LA SIGUIENTE]
- **Prueba real del core completada** (ver Historial "Prueba real end-to-end (2026-08-27)"):
  login manual con 2FA → cookie inyectada → cobertura (SI) → score (423, MUY ALTO). Dos
  bugs reales encontrados y corregidos en el camino (BOM UTF-8 en `_json()`,
  doble-encodificado no implementado en `_parsear_score`). **37 tests pasando, ruff
  limpio.**
- **Decisión de geodata resuelta**: opción C (payload mínimo) — ya no es un pendiente.
- Marcadas `[COMPLETADO]` las tareas 7 y 12 de "Tareas pendientes"; añadida tarea 13
  registrando `tools/probar_con_cookie.py` como herramienta de diagnóstico permanente.
- **Pendiente real para la próxima sesión**: decidir `actualizar_score_cliente` (tarea 8),
  conectar GUI↔core end-to-end (tarea 9 — hoy solo el proxy está cableado en la GUI,
  standalone sigue roto en `main_window.py:174`), evaluar creación del lead final (tarea
  10). Deuda técnica sin resolver: `requirements.txt` sin `httpx`, `tests/test_proxy.py`
  inexistente, `pyproject.toml` exige Python≥3.14 con la máquina en 3.12 (workaround
  `PYTHONPATH=.` documentado). Commit de esta sesión pendiente de confirmar con el usuario;
  push del commit `abd62ad` (sesión 2026-08-26) también sigue pendiente.