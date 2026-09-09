# Roadmap — JSConnect Win Coverage

Vista única de **qué se hizo**, **qué falta** y **en qué orden**. El detalle de
cada hito vive en `HistorialResumenes.md` y en `resumenes/<fecha>.md`; aquí solo
se ordena y se enlaza.

Última actualización: 2026-09-09.

---

## Estado en una línea

El núcleo, el proxy, el keepalive, la extensión de Chrome y la GUI están
construidos y validados end-to-end contra WinForce real. Falta endurecer la
detección de "sesión muerta", instalar el servicio de Windows en la PC de oficina
y barrer la documentación. **Nada corre en producción todavía.**

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

---

## Aprobado y pendiente — en orden de ejecución

### 1. Etapa R — Robustez de sesión del proxy  ⏳ EN CURSO
Plan: `~/.claude/plans/steady-crunching-music.md`. **Desbloquea la Etapa D.**

El proxy puede quedarse sin sesión WinForce y nadie se entera hasta que un agente
falla. Cuatro frentes:
- **R1** detección fiable (bug de `_last_activity`, validar la cookie al arrancar,
  primer keepalive en ≤60s, centralizar "marcar muerta/viva").
- **R2** fail-fast: HTTP 503 + `Retry-After`, sin reintentos, panel claro en la GUI.
- **R3** aviso al owner por 3 vías independientes: GUI del agente (suelo) ·
  Evento de Windows + Tarea programada (backbone) · toast de la extensión ·
  webhook opcional (escalable a N oficinas).
- **R4** `/health` honesto + la GUI ve `session_alive`.

### 2. Etapa 0.5 — Coherencia del almacén de la cookie con LocalSystem
Texto aprobado: `~/.claude/plans/shimmying-skipping-mochi.md:145-158`.
`rotate_creds.py` escribe la `PHPSESSID` en el keyring **del owner**; el servicio
corre como **LocalSystem** y lee otro almacén. Cambiar `rotate_creds.py` para que
empuje la cookie por HTTP (`/local/renovar` local · `/admin/rotar` con
`X-Admin-Key` si no), dejando el keyring del servicio como única fuente de verdad.
**Bloquea la Etapa D.**

### 3. Etapa C.12 — Modo standalone en la GUI
Probar el modo standalone pegando la `PHPSESSID`. Solo si se necesita: hoy exige
borrar a mano el keyring de proxy porque el modo proxy siempre gana
(`main_window.py:75-77`). No bloquea nada.

### 4. Etapa D — Servicio de Windows en la PC de oficina
`install_service.bat` como Administrador, los 11 pasos verificados uno a uno; el
servicio sobrevive a un reinicio y recupera la cookie del keyring; logs en
`<repo>\logs\` sin secretos; regla de firewall solo hacia la LAN. Registra
también la Tarea programada de aviso de la Etapa R (Capa B).
**Bloqueada por las Etapas R y 0.5.**

### 5. Etapa E — Runbook de la PC de oficina
La máquina está definida pero no es accesible hoy. Dejar en `docs/proxy-deploy.md`
el procedimiento **ya verificado en la Etapa D** (no el teórico): prerrequisitos
(Python 3.14.7), instalador corregido, ACL, cuenta del servicio, firewall, alta de
los 20 agentes y el ritual diario de renovación de la cookie.
**Bloqueada por acceso físico a la oficina.**

### 6. Fase 5 — Barrido final de la documentación
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
| D | Etapas R y 0.5 |
| E | acceso físico a la PC de oficina |
