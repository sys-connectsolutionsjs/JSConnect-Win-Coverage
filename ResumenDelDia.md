# ResumenDelDia.md — Historial del día

Fecha: 2026-09-09

## Objetivo del día

**Poner en marcha todo lo construido: activar el proxy end-to-end.** Hasta ahora
cada pieza (keepalive, login asistido, extensión de Chrome, diálogo de la GUI) se
validó por separado con mocks y smoke tests; el sistema completo nunca ha corrido
contra una sesión WinForce viva y el instalador nunca se ha ejecutado de verdad.

Plan aprobado: `~/.claude/plans/shimmying-skipping-mochi.md`. Orden:
1. Rotar el resumen 2026-09-08 (hecho, ver abajo).
2. **Etapa 0** — desbloquear el arranque: `config.yaml` no se lee (`config.py`
   sin `settings_customise_sources`), `install_service.bat` tiene 3 bugs que lo
   detienen, `winsw.xml` está trackeado, incoherencia del almacén de la cookie.
3. **Etapa A** — proxy en primer plano en esta PC + auth.
4. **Etapa B** — sesión WinForce viva (2FA disponible ahora) + renovación por
   extensión + primera validación real de cobertura/score + keepalive real.
5. **Etapa C** — GUI contra el proxy + modo standalone.
6. **Etapa D** — servicio de Windows en esta PC (sobrevive a reinicio).
7. **Etapa E** — runbook para la PC de oficina (hoy NO accesible → solo se
   documenta, no se ejecuta).
8. **Fase 5** (barrido de docs) — solo si sobra tiempo; hay 11 incoherencias
   doc↔código ya localizadas.

---

## Estado al arranque (2026-09-09)

- Rama `main` = `origin/main` (`e13a778`), working tree limpio.
- Entorno esta PC: Python **3.14.7**; `fastapi` / `uvicorn` / `httpx` / `keyring` /
  `playwright` importan; Chrome en `C:\Program Files\Google\Chrome\Application\`;
  puerto 8080 libre.
- **104 tests** (pendiente re-verificar en verde tras la Etapa 0).

### Decisión sobre la versión de Python (aclarada hoy)
Nada corre en 3.12. `requires-python = ">=3.12"` es un **piso mínimo**, no una
versión fijada; el 3.12 entró ayer solo como compatibilidad hacia atrás para una
máquina ajena que no podía hacer `pip install -e .`. **No se toca `pyproject.toml`**
(el piso bajo es un seguro para la PC de oficina). La instalación de producción se
**estandariza en Python 3.14.7**, igual que desarrollo. Cabos para la Fase 5:
`TestingLog.md:11` y `SkillsPropuestas.md:53` aún dicen `py314`; `>=3.12` es hoy
una promesa sin verificar (última corrida en 3.12: 2026-08-27, ~40 tests).

---

## Trabajo del día

### Rotación del resumen 2026-09-08 — HECHO
- `resumenes/2026-09-08.md` creado (copia verbatim del `ResumenDelDia.md` anterior,
  cabecera ajustada a `# Resumen — 2026-09-08`).
- Entrada condensada añadida arriba del todo en `HistorialResumenes.md` (total: 9
  entradas; el hook `historial_sync.py` disparó el recordatorio de doc-sync, sin
  README porque necesita 3 acumuladas).
- `ResumenDelDia.md` reabierto con fecha 2026-09-09.
- Pendiente en esta rotación: sincronizar `AGENTS.md` (Historial + Tareas
  pendientes + Cierre) y `PlanesAprobados.md` (sacar de la cola lo ya implementado).

---

## Pendiente

### De la puesta en marcha
- Etapas 0 → E del plan aprobado.

### Fase 5 — Barrido final de docs (última del plan "Sesión WinForce robusta")
- `docs/proxy-config.md`, `docs/proxy-deploy.md`, `docs/rotacion-credenciales.md`,
  `docs/arquitectura.md` — coherencia general (extensión = principal, login
  asistido + `--manual` = fallback).
- 11 incoherencias doc↔código localizadas en la exploración de hoy (rotación por
  usuario/contraseña inexistente, `version` = `"dev"` vs commit SHA, ejemplos de
  `/admin/status` sin `X-Admin-Key`, `session_age_seconds` vs `session_age`,
  "IP:puerto" sin esquema vs la GUI que exige `http://`, keyring standalone,
  "logs en el Visor de Eventos", `/admin/config` "público", `config.yaml` no se
  lee, dos referencias a `py314`).

### Deuda vieja (no de hoy)
- Decidir si la app llama a `actualizar_score_cliente` y/o `newsearch.php`
  (Tareas pendientes 8 y 10 de `AGENTS.md`).
