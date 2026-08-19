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
├── build.ps1                 # embebe commit SHA + empaqueta con PyInstaller
├── publish-release.ps1       # prepara el Release en GitHub (asset .exe + SHA-256)
├── tools/
│   └── captura.py            # herramienta Playwright para descubrir la API interna
├── generator/
│   ├── generar.py            # generador de códigos de activación (SOLO encargado)
│   └── private_key.pem       # NUNCA se sube al repositorio (ver .gitignore)
├── tests/
│   ├── test_fields.py
│   └── test_captura_guard.py
└── validator_app/
    ├── __init__.py
    ├── version.py            # SHA + tag embebidos (autogenerado en build)
    ├── core/                 # api.py (login, score, cobertura) + session.py
    ├── gui/                  # main_window.py, fields.py
    ├── activation/           # fingerprint.py, signer.py, state.py
    └── updater/              # check.py, download.py
```

## Comandos
- Instalar producción: `pip install -r requirements.txt`
- Instalar desarrollo: `pip install -r requirements-dev.txt`
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

## Archivos de documentación (mapa de conocimiento)
Estos archivos son el punto de partida de cualquier persona (o IA) que retome el
proyecto. Leerlos en este orden ANTES de tocar código:
1. **AGENTS.md** (este archivo): reglas del proyecto, contexto, historial y tareas
   pendientes. Es la puerta de entrada.
2. **PlanesAprobados.md**: planes de trabajo YA aprobados, con el razonamiento y las
   decisiones tomadas (ej: decisión de autenticación). Contiene además diseños listos
   para implementar (ej: el Paso 1 con el código de `tools/probar_concurrencia.py`).
   Leer antes de empezar una fase para no repetir análisis ni ignorar decisiones.
3. **TestingLog.md**: metodología TDD del proyecto (test rojo -> verde), inventario de
   tests y bitácora de problemas -> causa -> solución. Leer antes de escribir o
   modificar tests.
4. **README.md**: documentación pública del proyecto (español primero, luego inglés).
   Mantenerla actualizada ANTES de subir a GitHub.

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
- Repositorio remoto: https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Tareas pendientes
1. **PRUEBA DE CONCURRENCIA** (pendiente de ejecutar): validar desde 4-5 máquinas a
   la vez con la misma cuenta de Win para comprobar si la ISP bloquea; decidir entre
   proxy local (B) y credenciales por máquina (A). El diseño de la herramienta
   `tools/probar_concurrencia.py` está aprobado en PlanesAprobados.md (Paso 1).
   Actualizar este punto con los resultados en cuanto se haga la prueba.
2. **Prueba real del core** con credenciales del usuario (keyring): login → cobertura →
   score con un cliente de prueba. Decidir aquí si `score_cliente` acepta payload mínimo
   (opción C) o si hace falta la geodata.
3. (Si la prueba exige geodata) extraer las credenciales de cliente de Equifax con
   `python tools/captura.py --guardar-js` (JS en `tools/js/`) y replicar el geocoding.
4. Decidir si la app debe llamar a `actualizar_score_cliente` (registra el score en el
   sistema) o si basta con leerlo.
5. Conectar la GUI (keyring para credenciales, resultados del core) y ajustar
   `main_window.py` al resultado real del score.
6. Evaluar si la app debe crear el lead final (`POST controllers/newsearch.php`, multipart).
7. Actualizar README.md con el estado de Fase 1 antes de subir a GitHub.

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

### Fase 1 — Núcleo (core) [EN CURSO]
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
- **Pendiente**: prueba contra la API real con credenciales del usuario (keyring).

### Fase 1.5 — Decisión de autenticación [EN CURSO]
**2026-08-18**
- [Dato del negocio] Los agentes NO tienen cuenta de WinForce; la app debe ser offline
  y de mínimo costo; ~20 máquinas con internet; Win permite 2-3 personas simultáneas por
  cuenta, cierra la sesión a los 3 min sin uso, y ROTA las credenciales cada 1-2 meses
  (desactiva la cuenta anterior y entrega usuario/contraseña nuevos al responsable).
- [Análisis] Opciones:
  - A) Credenciales por máquina (keyring + auto-relogin): simple, $0, sin dependencias;
    pero hasta 20 sesiones concurrentes de la misma cuenta (riesgo de bloqueo) y la
    rotación mensual obliga a actualizar keyring en las 20 máquinas.
  - B) Proxy local en la PC de la oficina (LAN): 1-2 sesiones desde una sola IP (sin
    riesgo de bloqueo), credenciales SOLO en el proxy (rotación = actualizar 1 PC),
    offline, costo ~$0; punto único de falla. RECOMENDADA.
  - C) Cuentas propias por agente: descartada (no tienen cuentas).
  - D) Sesión en caché por máquina: descartada (expiraciones + misma cuenta).
- [Plan aprobado] Prueba de concurrencia en 4-5 máquinas primero; luego decidir A/B.
  Detalle completo en `PlanesAprobados.md`.

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

### Cierre de la sesión 2026-08-18 [CONTEXTO PARA LA SIGUIENTE]
- Se crearon `PlanesAprobados.md` (plan aprobado completo + diseño del Paso 1 con el
  código de `tools/probar_concurrencia.py` listo para implementar) y `TestingLog.md`
  (metodología TDD y bitácora de pruebas).
- Se añadió la sección "Archivos de documentación" (mapa de conocimiento) para que
  cualquier persona/IA retome el proyecto sin contexto previo.
- **Pendiente al retomar**: crear `tools/probar_concurrencia.py` con el diseño del
  Paso 1 de PlanesAprobados.md, ejecutarlo en 4-5 máquinas y decidir A/B.
- Estado general: Fase 0 completa, Fase 1 construida (25 tests, ruff limpio),
  Fase 1.5 en curso (decisión de autenticación pendiente de la prueba).