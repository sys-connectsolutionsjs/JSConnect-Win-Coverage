# Roadmap — JSConnect Win Coverage

Vista única de **qué se hizo**, **qué falta** y **en qué orden**. El detalle de
cada hito vive en `HistorialResumenes.md` y en `resumenes/<fecha>.md`; aquí solo
se ordena y se enlaza.

Última actualización: 2026-09-11.

---

## Estado en una línea

El núcleo, el proxy, el keepalive, la extensión de Chrome, la GUI, la detección
robusta de "sesión muerta" y la coherencia del keyring bajo LocalSystem están
construidos y validados. Falta instalar el servicio de Windows en la PC de
oficina (D/E) y barrer la documentación (Fase 5). **Nada corre en producción
todavía.**

---

## Línea de tiempo — entregado

| Fecha | Hito | Commit(s) |
|---|---|---|
| 2026-08-19 | **Fase 0-1** — descubrimiento de la API interna de WinForce, núcleo `core/` y tests | `e837681` |
| 2026-08-19 | Reglas de trabajo: `ResumenDelDia` + `PlanesAprobados` como cola + automantenimiento de `AGENTS.md` | `c0d2f2a` `1148db2` `b7c64a2` |
| 2026-08-21 | **Decisión de arquitectura B** — proxy local para 20 agentes LAN; descubierto el SSO federado de Microsoft (2FA → login programático inviable) | `a3bebf4` |
| 2026-08-25 | **Fase 1 (Proxy)** — proxy local FastAPI completo; sistema de códigos de error | `7cf7ea1` `f63660b` `801ce05` |
| 2026-08-27 | **Prueba real del core** — cobertura + score con datos reales; corregidos BOM UTF-8 y doble-encodificado de las respuestas de WinForce | `c72188c` `7bc6550` |
| 2026-08-28 | Registrado el plan **"Sesión WinForce robusta"** (fases 2A → 5) | `fc81da8` |
| 2026-09-04 | Eliminado el login muerto de la Fase 1; investigación del keepalive real | `1dcecc6` |
| 2026-09-05 | Registro de fallos de sesión del proxy + caché de `session_alive`; `medir_keepalive` v3 | `5506ed4` `3925dbf` |
| 2026-09-08 | **Fase 2A** — keepalive del proxy ("latido perezoso") + fix del guard idle del cliente-core | `b3adb38` |
| 2026-09-08 | **Fase 2.5** — login asistido (Chrome real, autofill, `--preview`) | `28b7698` `c96de4c` `cb085da` |
| 2026-09-08 | **Fase 2.5d** — extensión de Chrome para renovar la sesión con un clic | `499ba5f` `e517a2b` |
| 2026-09-08 | **Fase 3** — diálogo de cookie en la GUI (arregla el modo standalone) | `5cf8e3f` |
| 2026-09-08 | **Fase 4** — tests de la capa FastAPI del proxy (endpoints + auth + handlers) | `76afb9d` |
| 2026-09-09 | **Etapa 0** — `config.yaml` se lee de verdad; 3 bugs de `install_service.bat`; `winsw.xml` fuera del control de versiones | `d9c1ef7` `ffa213a` |
| 2026-09-09 | **Etapa A** — proxy en primer plano en la PC de desarrollo + auth verificada | `7992e01` |
| 2026-09-09 | **Etapa B** — sesión WinForce viva + validación real cobertura/score end-to-end; fix `deuda_total` int | `3f63e8f` `898b9ab` |
| 2026-09-09 | **Etapa C** — GUI (Tkinter) contra el proxy, validada; la suite envenenaba el keyring (corregido); `install_service.bat:262` | `b70dacf` `ffc5296` `f91b9fb` |
| 2026-09-09 | **Etapa R** — robustez de la detección de sesión muerta: fix del bug de `_last_activity`, validación al arrancar, fail-fast 503, aviso al owner por 3 capas (GUI · Evento Windows+tarea · toast extensión · webhook) | `82f3604` `3c8c7bd` `6ee6cb6` `4924e70` `9f49b8e` `67ec0e4` |
| 2026-09-11 | **Etapa 0.5** — coherencia del almacén de la cookie con LocalSystem: `rotate_creds.py` ya no escribe el keyring del owner, empuja la cookie por HTTP (`/local/renovar` → `/admin/rotar`); de paso, fix del bug latente de `proxy_url` con `proxy_host=0.0.0.0` (`proxy_local_url` nueva) | `f5eb257` |

---

## Aprobado y pendiente — en orden de ejecución

### 1. Etapa C.12 — Modo standalone en la GUI
Probar el modo standalone pegando la `PHPSESSID`. Solo si se necesita: hoy exige
borrar a mano el keyring de proxy porque el modo proxy siempre gana
(`main_window.py:75-77`). No bloquea nada.

### 2. Etapa D — Servicio de Windows en la PC de oficina
`install_service.bat` como Administrador, los 12 pasos verificados uno a uno
(incluye la Tarea programada de aviso de la Etapa R); el servicio sobrevive a un
reinicio y recupera la cookie del keyring (prueba de fuego de la Etapa 0.5);
logs en `<repo>\logs\` sin secretos; regla de firewall solo hacia la LAN.
Verificar el popup de "sesión caducada" (bajo LocalSystem; en desarrollo
`eventcreate` da "Acceso denegado", es esperado). **Siguiente etapa — nada la
bloquea ya** (R y 0.5 hechas).

### 3. Etapa E — Runbook de la PC de oficina
La máquina está definida pero no es accesible hoy. Dejar en `docs/proxy-deploy.md`
el procedimiento **ya verificado en la Etapa D** (no el teórico): prerrequisitos
(Python 3.14.7), instalador corregido, ACL, cuenta del servicio, firewall, alta de
los 20 agentes y el ritual diario de renovación de la cookie.
**Bloqueada por acceso físico a la oficina.**

### 4. Fase 5 — Barrido final de la documentación
**La última del plan "Sesión WinForce robusta".** Consume el checklist de **19
incoherencias doc↔código** en `PlanesAprobados.md` (sección "Fase 5 — docs"), cada
una con `archivo:línea`. Coherencia general: extensión = vía principal, login
asistido + `--manual` = fallback.

---

## Backlog v1.1 (cambios menores)

- **Cobertura sin DNI**: dejar el documento vacío en la GUI → devuelve solo
  cobertura. Viable y limpio (~10 líneas: quitar el gate de `main_window.py:157-160`,
  saltar el score). El caso inverso (score sin coordenadas) es inviable sin
  coordenadas de relleno — fuera de la 1.1.
- **UX del login asistido**: el poller no detecta "ventana cerrada" de forma
  fiable (`ResumenDelDia.md`, hallazgo de la Etapa B). El patrón `page.on("close")`
  ya existe en `tools/captura.py` (`AGENTS.md:340-342`).
- Las 6 ideas de producto de `AGENTS.md:134-160` ("Implementaciones futuras":
  mapa interactivo, catálogo, instalador, servidor de activación, lotes, CRM).

---

## Bloqueos conocidos

| Etapa | Bloqueada por |
|---|---|
| D | nada (R y 0.5 completadas) |
| E | acceso físico a la PC de oficina |
