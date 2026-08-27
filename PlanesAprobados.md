# PlanesAprobados.md — Planes de trabajo aprobados

Fecha de creación: 2026-08-18 · Proyecto: JSConnect-Win-Coverage

## Contexto
App de escritorio (Python/Tkinter) para un call center que valida COBERTURA
(coordenadas) y SCORE crediticio (DNI/RUC/CE) replicando la API interna de
appwinforce.win.pe (sin scrapear HTML). Repo:
https://github.com/sys-connectsolutionsjs/JSConnect-Win-Coverage

## Estado del proyecto (verificado 2026-08-26)
- Fase 0 (captura de la API): COMPLETA.
- Fase 1 (núcleo core): COMPLETA — 35 tests, ruff limpio.
- Fase 1.5 (decisión de autenticación): **DECIDIDA — Opción B (Proxy Local)**.
- Fase 0 Documentación: COMPLETA — `docs/`, `Escalabilidad.md`, `anotaciones.md`, `resumenes/`.
- **Proxy Local (FASES 1.1–1.5) IMPLEMENTADO**: `validator_app/proxy/` completo
  (server.py, config.py, client.py, rotate_creds.py, winsw.xml, install/uninstall .bat),
  core adaptado (`auto_relogin_if_needed`, persistencia cookies), GUI conectada
  (menú "⚙️ Configuración"). Detalle en `AGENTS.md` (Historial → Fase Proxy —
  Implementación).
- **Gap detectado**: no existe `tests/test_proxy.py` — el plan original (FASE 1.1,
  paso 5 abajo) lo pedía y no se hizo. El proxy no tiene tests unitarios propios;
  los 35 tests actuales cubren core/activation/GUI fields, no `validator_app/proxy/`.
- **Próxima fase**: ya no es implementar el proxy (hecho). Ver "Pendientes
  adicionales" abajo — la prueba real del core es el siguiente paso lógico.

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

## Plan Proxy Local — IMPLEMENTADO (sacado de la cola 2026-08-26)
El plan completo de FASES 1.1–1.5 (stack, acuerdos, pasos de implementación) se
ejecutó íntegramente. El detalle verificado vive en `AGENTS.md` (Historial → Fase
Proxy — Implementación), no se duplica aquí. Único cabo suelto: **no se creó
`tests/test_proxy.py`** (ver "Gap detectado" arriba) — si se retoma, es cola nueva,
no parte de este plan ya cerrado.

## Prueba real del core — COMPLETADA (2026-08-27)
Login manual (2FA) + cookie inyectada vía `tools/probar_con_cookie.py` (nuevo, conservar
como herramienta de diagnóstico) → cobertura (SI, HORIZONTAL, celda 8764) → score (423,
MUY ALTO). Dos bugs reales encontrados y corregidos: BOM UTF-8 en `_json()` (cobertura) y
doble-encodificado no implementado en `_parsear_score` (score, ya documentado desde Fase 0
pero nunca hecho). 37 tests pasando, ruff limpio. Detalle completo en `AGENTS.md`
(Historial → "Prueba real end-to-end (2026-08-27)") y `ResumenDelDia.md`.

**Geodata del score — RESUELTA: opción C (payload mínimo)**. El score respondió bien
enviando solo coordenadas + documento, sin geodata. No hace falta replicar Equifax (A) ni
pedir datos manuales (B).

## Pendientes adicionales (cola activa)
- Decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`.
- Conectar GUI a core end-to-end (más allá de la config de proxy) y ajustar
  `main_window.py` si hace falta — el modo standalone hoy siempre falla
  (`main_window.py:174` nunca hace login).
- Escribir `tests/test_proxy.py` (gap del plan anterior).
- `requirements.txt` no incluye `httpx` aunque `proxy/client.py` lo usa (afecta el .exe
  del agente).
- `pyproject.toml` exige `Python>=3.14`; la máquina de esta sesión solo tiene 3.12.2
  instalado (workaround: `PYTHONPATH=.` en vez de instalar editable).

## Notas de seguridad
- Credenciales de Win rotan cada 1-2 meses; nunca hardcodear; en proxy solo viven en keyring PC proxy.
- NO subir a GitHub: `config.yaml`, `proxy_token.txt`, `admin_key.txt`, `tools/captura.json`, `tools/js/`, `generator/private_key.pem`, credenciales reales.
- Token proxy = secreto LAN (binding IP); admin key = solo owner.