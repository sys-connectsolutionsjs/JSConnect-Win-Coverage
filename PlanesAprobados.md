# PlanesAprobados.md — Planes de trabajo aprobados

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Contexto
App de escritorio (Python/Tkinter) para un call center que valida COBERTURA
(coordenadas) y SCORE crediticio (DNI/RUC/CE) replicando la API interna de
appwinforce.win.pe (sin scrapear HTML). Repo:
https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Estado del proyecto (2026-08-25)
- Fase 0 (captura de la API): COMPLETA.
- Fase 1 (núcleo core): COMPLETA — 25 tests, ruff limpio.
- Fase 1.5 (decisión de autenticación): **DECIDIDA — Opción B (Proxy Local)**.
- Fase 0 Documentación: COMPLETA — `docs/`, `Escalabilidad.md`, `anotaciones.md`, `resumenes/`.
- **Próxima fase**: FASE 1 Proxy Implementation — implementar `validator_app/proxy/` completo.

## Descubrimientos técnicos (Fase 0)
- Login: POST /controllers/acceso.php (accion=iniciar_sesion) -> cookie PHPSESSID.
- Cobertura: GET /controllers/coordenada.php?accion=validar_cobertura
  &data[latitud]=..&data[longitud]=.. -> {cobertura: SI/NO, tipo, id_celda}.
- Score: POST /controllers/cliente.php accion=score_cliente (payload data[...]).
  Respuesta: JSON doble-encodificado con reporte SOAP Equifax; puntaje en
  ns3ResumenScoreRP3.Puntaje (ej: 423) y DeudaTotal en ResumenDeuda.
- Tipos de doc: 1=DNI, 2=Carnet extranjería, 3=RUC, 4=Pasaporte.
- Geodata (distrito/ubigeo/cod_postal/segmentación): la calcula el navegador
  llamando a la geoapi de Equifax (oauth client_credentials). Credenciales en
  el header Authorization (embebidas en el JS del sitio).

## Fase 1 — Núcleo (construida)
- validator_app/core/session.py: sesión requests con headers de navegador.
- validator_app/core/api.py: login(), validar_cobertura(), validar_score()
  (parser del reporte Equifax), validar(). Errores: APIError/LoginError/ScoreError.
- tools/probar_core.py: arnés de prueba en consola (login->cobertura->score).
- tools/captura.py mejorada: redacción de formularios, guarda HTML,
  MAX_BODY_CHARS=200000, --guardar-js (JS en tools/js/), salida sin buffer.
- Tests: tests/test_api.py (14 casos). Total: 25 tests, ruff limpio.

## Decisión de autenticación — análisis
### Restricciones del negocio
- Los agentes NO tienen cuenta de WinForce (solo el responsable).
- La app debe ser OFFLINE y de mínimo costo.
- ~20 máquinas con internet constante.
- Win (la ISP) permite 2-3 personas simultáneas por cuenta; cierra la sesión
  a los 3 minutos sin uso.
- Win ROTA las credenciales cada 1-2 meses (desactiva la cuenta anterior y
  entrega usuario/contraseña nuevos al responsable).
- Hay una PC fija disponible en la oficina (encendida en horario laboral).

### Opciones analizadas
A) Credenciales por máquina (keyring) + auto-relogin.
   + Simple, $0, sin dependencias.
   - Hasta 20 sesiones concurrentes de la misma cuenta -> riesgo de bloqueo.
   - Cada rotación (1-2 meses) = actualizar keyring en las 20 máquinas.
B) Proxy local en la PC de la oficina (LAN).
   + 1-2 sesiones de WinForce desde UNA IP -> sin riesgo de bloqueo.
   + Credenciales SOLO en el proxy; rotación = actualizar 1 sola PC.
   + Sigue siendo offline (solo LAN, sin VPS), costo ~$0.
   - Punto único de falla (mitigable con una 2ª PC de respaldo).
C) Cuentas propias por agente: DESCARTADA (no tienen cuentas).
D) Sesión en caché por máquina: DESCARTADA (expiraciones + misma cuenta).

### Hallazgo crítico 2026-08-25
**Login WinForce redirige a `login.microsoftonline.com` para 2FA Microsoft** con la misma cuenta.
Esto hace **inviable la prueba de concurrencia** planificada (4-5 máquinas simultáneas requerirían 2FA manual cada una).

### Decisión aprobada (2026-08-25)
**Opción B (Proxy Local) APROBADA** definitivamente. No se realiza prueba de concurrencia.
Razones documentadas en `AGENTS.md` (Historial 2026-08-25) y `ResumenDelDia.md`.

## Plan Proxy Local — FASE 1 Implementation

### Stack Confirmado
- Framework: **FastAPI + uvicorn** (concurrencia nativa, validación Pydantic, Swagger)
- Auth agentes: **Token compartido 256-bit + validación IP LAN** (`192.168/16`, `10/8`, `172.16/12`, `100.64/10` para Tailscale)
- Auth admin: **API Key admin separada** (`X-Admin-Key`) para endpoints `/admin/*`
- Ejecución: **winsw service** (`JSWinProxy` / "JSConnect Win Proxy") — auto-inicio, auto-restart, logs eventos
- Config: **`config.yaml` gitignored + `config.yaml.example` en repo** — `install_service.bat` genera tokens auto
- Requirements: **`requirements-proxy.txt` separado** (.exe agentes no arrastra fastapi/uvicorn)
- GUI: **Diálogo modal** desde menú "⚙️ Configuración" (mueve "Buscar actualizaciones" ahí)
- Docs: **Carpeta `docs/` permanente** ≠ `AGENTS.md/PlanesAprobados.md` volátiles

### Acuerdos explícitos 2026-08-25
1. Token proxy auto-generado en `install_service.bat` + mostrado en consola + guardado en `proxy_token.txt`
2. Admin key igual (auto-generada + `admin_key.txt`)
3. Servicio: `JSWinProxy` / Display "JSConnect Win Proxy"
4. Puerto 8080 por defecto; `install_service.bat` verifica y permite cambiar si ocupado
5. Menú GUI: "⚙️ Configuración" → items: "Configurar Proxy", "Buscar actualizaciones"
6. Escalabilidad remota: VPN (Tailscale) + mismo proxy + mismo token; endpoint `/admin/config` para auto-discovery
7. Documentación técnica en `docs/` (permanente); glosario en `anotaciones.md`
8. `requirements-proxy.txt` con comentario explicando tradeoff separación vs simplicidad

### Pasos de implementación (orden)

#### FASE 1.1 — Proxy Server (config, server, winsw, install)
- `validator_app/proxy/config.py` — Pydantic Settings (lee config.yaml + env)
- `validator_app/proxy/config.yaml.example` — plantilla con placeholders
- `validator_app/proxy/server.py` — FastAPI app + endpoints + ValidatorAPI wrapper
- `validator_app/proxy/winsw.xml` — config servicio Windows
- `validator_app/proxy/install_service.bat` — instala servicio (descarga winsw, genera tokens, verifica puerto)
- `validator_app/proxy/uninstall_service.bat` — desinstala servicio
- `validator_app/proxy/__init__.py`

#### FASE 1.2 — Core Adaptado
- `validator_app/core/api.py` — añadir `auto_relogin_if_needed()` + persistencia cookies
- `validator_app/core/session.py` — exportar/importar cookies de sesión

#### FASE 1.3 — Cliente Proxy
- `validator_app/proxy/client.py` — `ProxyClient` con retries, timeouts, errores tipados, `from_discovery()`

#### FASE 1.4 — GUI Config Proxy
- `validator_app/gui/main_window.py` — menú "⚙️ Configuración" → diálogo modal IP:puerto + token (keyring local `JSWinClient`)

#### FASE 1.5 — Deploy & Docs
- `validator_app/proxy/rotate_creds.py` — CLI owner: rota credenciales WinForce (RDP híbrido: navega manual + pega cookie)
- `README_PROXY.md` — resumen deploy + comandos rápidos
- `requirements-proxy.txt` + actualizar `requirements-dev.txt` (incluye `-r requirements-proxy.txt`)
- `build.ps1` actualizado — incluye `proxy/client.py`, excluye `proxy/server.py`
- `docs/proxy-deploy.md`, `docs/proxy-config.md`, `docs/rotacion-credenciales.md`, `docs/escalabilidad-remota.md`, `docs/arquitectura.md` (ya creados en Fase 0 Docs)

## Pendientes adicionales (no bloquean el proxy)
- Prueba real del core (tools/probar_core.py) con credenciales del responsable.
- Decidir geodata del score (A: replicar Equifax / B: manual / C: mínimo) según prueba real.
- Decidir si la app llama a actualizar_score_cliente y/o newsearch.php.
- Conectar GUI a core (keyring para credenciales standalone, resultados del core) y ajustar main_window.py.

## Checklist próxima sesión (FASE 1 Proxy)
1. Leer `AGENTS.md` + `PlanesAprobados.md` + `docs/arquitectura.md` para contexto completo.
2. Implementar `validator_app/proxy/config.py` + `config.yaml.example`.
3. Implementar `validator_app/proxy/server.py` (FastAPI + 6 endpoints + middleware auth).
4. Implementar `validator_app/proxy/winsw.xml` + `install_service.bat` + `uninstall_service.bat`.
5. Tests unitarios proxy (`tests/test_proxy.py`).
6. Ejecutar `pytest` + `ruff check .` tras cada sub-fase.

## Notas de seguridad
- Credenciales de Win rotan cada 1-2 meses; nunca hardcodear; en proxy solo viven en keyring PC proxy.
- NO subir a GitHub: `config.yaml`, `proxy_token.txt`, `admin_key.txt`, `tools/captura.json`, `tools/js/`, `generator/private_key.pem`, credenciales reales.
- Token proxy = secreto LAN (binding IP); admin key = solo owner.