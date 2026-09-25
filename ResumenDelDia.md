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

## Pendiente al cerrar hoy

- Confirmar en la PC del agente real que reportó el error que copiar la URL desde
  la consola owner resuelve el `WinError 10061`.
- El instalador (`install_service.bat`) sigue sin crear una regla de firewall para
  el puerto del proxy — siguiente sospechoso si el agente aún no conecta.
- **Observación sin corregir** (fuera de alcance de hoy):
  `validator_app/updater/check.py:41` compara el commit embebido contra
  `release["target_commitish"]`, que en nuestros Releases vale literalmente
  `"main"` — nunca coincide, así que el chequeo de actualización puede dar
  siempre positivo.
- Resto de pendientes de cierres anteriores (Etapa D/E en la PC oficial, Fase 5 de
  documentación, decisión de `actualizar_score_cliente`/`newsearch.php`) sigue abierto.
