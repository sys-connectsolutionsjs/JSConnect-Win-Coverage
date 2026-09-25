# ResumenDelDia.md — Historial del día

Fecha: 2026-09-25

## Rotación del resumen anterior

El detalle íntegro de hoy quedó en `resumenes/2026-09-25.md` (snapshot) y su
entrada condensada en `HistorialResumenes.md`. (Nota: el resumen del 2026-09-22
había quedado sin rotar de la sesión anterior; se rotó al abrir esta sesión sin
pérdida de contenido.)

## Qué se hizo hoy

Ver el detalle completo en `resumenes/2026-09-25.md`. En síntesis:

- **Fix**: "URL para los agentes" en la consola owner (`generator/owner_app.py`)
  — detecta la IP de LAN de la PC del proxy y la muestra lista para copiar,
  arreglando el `WinError 10061` que daba `localhost` al configurar un agente en
  una PC distinta a la del proxy.
- **Tests**: 193 → **201**, TDD rojo→verde, ruff limpio.
- **Documentación**: `docs/proxy-deploy.md`, `README.md` (es/en), `TestingLog.md`,
  `anotaciones.md`, `AGENTS.md`, `Roadmap.md`, `HistorialResumenes.md`.
- **Release**: `v2026.09.25` publicado con ambos `.exe` reconstruidos.

## Segunda parte de la sesión

- **Fix**: el chequeo de actualización (`updater/check.py`) comparaba el commit
  embebido contra `release["target_commitish"]` — que en la API de GitHub
  Releases es la rama del tag (`"main"`), no un SHA — así que siempre creía que
  había una versión nueva. `_commit_de_tag()` (NUEVO) resuelve el SHA real vía
  `/commits/{tag}`. Verificado en vivo contra `v2026.09.25`: resuelve el commit
  correcto. 201 → **206 tests**, ruff limpio.
- **Decisión de proceso**: un Release ya no se publica por cada commit — solo
  cuando el usuario lo pide explícitamente. Este fix quedó comiteado y pusheado
  **sin Release nuevo**.

## Tercera parte de la sesión

- **Fix**: el mismo agente pasó de `WinError 10061` a **Timeout** tras corregir la
  IP — firma de un firewall sin regla (descarta en silencio, no rechaza).
  `install_service.bat` solo imprimía el comando `New-NetFirewallRule`, nunca lo
  ejecutaba. Nuevo paso `[11/13]` (idempotente, con fallback manual si el
  firewall es de dominio); `uninstall_service.bat` la quita. Se le dio al usuario
  el comando manual para desbloquearse ya mismo. 206 → **209 tests**, ruff limpio.

## Cuarta parte de la sesión

- **Fix**: coordenadas y documento pasan a ser independientes. Solo coordenadas
  → cobertura; solo documento → score directo (`lat=lon=None`, en blanco en el
  payload, mismo patrón que los campos de geodata opcionales); ambos → el flujo
  de siempre. **Verificado en vivo** contra WinForce real (reinicio del proxy +
  token dado por el usuario): score sin coordenadas para el DNI de prueba
  **10412031** devolvió Score 862/BAJO riesgo. 209 → **212 tests**, ruff limpio.

## Cierre técnico de la sesión

- Reconstruido `JSConnect-Win-Coverage.exe` (commit `513a2f7`, incluye los 4
  cambios de hoy); `JSConnect-Win-Owner.exe` reutilizado sin cambios (su código
  no se tocó desde el build de esta mañana). Publicado **Release
  `v2026.09.25.1`** (nuevo tag, no pisa `v2026.09.25` de esta mañana — decisión
  del usuario) con ambos `.exe` y checksums SHA-256.
- **Confirmado con la app real** (no solo el smoke headless de antes): instancia
  real de `App`, cliente falso con las dataclasses reales de `ProxyClient`,
  `mainloop()` de verdad. Los 4 casos (solo coordenadas, solo documento, ambos,
  ninguno) se comportaron exactamente como se diseñó.

## Pendiente al cerrar hoy

- Confirmar en la PC del agente real que reportó ambos errores que ya conecta de
  punta a punta.
- Probar el paso `[11/13]` en una instalación/reinstalación real (no ejecutable
  desde este entorno).
- Resto de pendientes de cierres anteriores (Etapa D/E en la PC oficial, Fase 5 de
  documentación, decisión de `actualizar_score_cliente`/`newsearch.php`) sigue abierto.
