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
1. **FASE 0 DOCUMENTACIÓN** (EN CURSO): Completar `docs/`, `Escalabilidad.md`, `anotaciones.md`, actualizar `AGENTS.md`, `PlanesAprobados.md`, `README.md`
2. **FASE 1 PROXY SERVER**: Implementar `validator_app/proxy/` completo (config, server, winsw, install, client, tests)
3. **FASE 2 CORE ADAPTADO**: Añadir `auto_relogin_if_needed()` + persistencia cookies en `api.py`/`session.py`
4. **FASE 3 CLIENTE PROXY**: `ProxyClient` con retries, timeouts, errores tipados, `from_discovery()`
5. **FASE 4 GUI CONFIG PROXY**: Menú "⚙️ Configuración" → diálogo modal IP:puerto + token (keyring local)
6. **FASE 5 DEPLOY & DOCS**: `rotate_creds.py`, `README_PROXY.md`, `requirements-proxy.txt`, `build.ps1` actualizado
7. **Prueba real del core** con credenciales del usuario (keyring): login → cobertura → score cliente prueba
8. Decidir si la app debe llamar a `actualizar_score_cliente` (registra score) o basta con leerlo
9. Conectar GUI a core (keyring para credenciales, resultados del core) y ajustar `main_window.py`
10. Evaluar si la app debe crear el lead final (`POST controllers/newsearch.php`, multipart)
11. **Sistema de códigos de error**: Incorporar `code` a todas las excepciones (`APIError`, `LoginError`, `ScoreError`, `CoberturaError`, `SessionError`, `NetworkError`, `ConfigError`, etc.) + diccionario `ERROR_CODES` en `api.py` con categoría y descripción para logging/monitoreo futuro

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

### Decisión pendiente (geodata del score)
  - A) Replicar Equifax: oauth `client_credentials` + reverse-geocoding (igual que el
    navegador). Fiel para cualquier coordenada; requiere credenciales del sitio (extraer
    con `--guardar-js`).
  - B) Entrada manual: pedir al agente distrito/ubigeo/dirección del lead y omitir
    segmentación/nse (en la captura venían vacíos en un caso). Requiere probar qué campos
    son obligatorios.
  - C) Payload mínimo: probar `score_cliente` solo con coordenadas + documento y ver si el
    servidor rellena la geodata.
  - Estado: el core ya acepta un dict `geodata` opcional; la GUI aún no lo envía (se
    resolverá en la prueba real).

### Cierre de la sesión 2026-08-25 [CONTEXTO PARA LA SIGUIENTE]
- Se completó **FASE 0 Documentación**: creados `docs/` (5 archivos), `resumenes/2026-08-19.md`, `Escalabilidad.md`, `anotaciones.md`, actualizados `AGENTS.md`, `PlanesAprobados.md`, `README.md`, `ResumenDelDia.md`
- **Decisión arquitectónica definitiva**: Proxy Local (Opción B) — 2FA Microsoft bloquea concurrencia
- **Próxima sesión**: FASE 1 — Implementar `validator_app/proxy/` completo (config.py, server.py, winsw.xml, install_service.bat, client.py, tests)
- Estado general: Fase 0 completa, Fase 1 completa, Fase 1.5 decidida (Proxy Local), FASE 0 Docs completada, listo para FASE 1 Proxy Implementation