# ResumenDelDia.md — Historial del día

Fecha: (se fija al abrir la próxima sesión)

## Rotación del resumen anterior

El detalle íntegro del 2026-09-30 quedó en `resumenes/2026-09-30.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- (nada todavía)

- **Plugin `documentation`** (tarea 43 de AGENTS.md): repo
  `AngelSanchezDev/Documentation-plugin` v1.0.1, con hook `SessionStart` +
  `/documentation:cerrar-sesion` + `doc_sync.py` (21 tests en ese repo). Instalado
  en esta PC desde GitHub. Probado: proyecto nuevo (el hook crea los 7 archivos) y
  cierre completo con snapshot/historial/rotación. Commits con la identidad
  noreply de AngelSanchezDev; la cuenta `gh` activa se devolvió a
  `sys-connectsolutionsjs`. Dato: en este repo, `ResumenDelDia.md` dice
  "(se fija al abrir la proxima sesion)" y el hook lo sellará con la fecha del
  día en la próxima sesión.

- **2026-10-02 — Instalación de la PC oficina (Windows 11 Pro, proxy + owner) y
  fix del popup de sesión caducada.** En una instalación limpia,
  `install_service.bat` registra el origen `JSWinProxy` con `New-EventLog`, y
  `eventcreate` (que usaba `server._aviso_event_log`) rechaza ese origen siempre:
  "El parámetro de origen se usa para identificar solo las aplicaciones/scripts",
  porque solo acepta orígenes con `CustomSource=1`. El fallo pasaba en silencio
  (`check=False`), así que el evento 101 nunca se escribía y la tarea
  `JSWinProxy-AvisoSesion` nunca sacaba el popup. La nota anterior ("bajo
  LocalSystem funciona") no aplica a este caso. Fix: `_aviso_event_log` pasa a
  `ReportEventW` vía ctypes (+2 tests en `test_proxy.py`). Verificado de punta a
  punta: el evento 101 real disparó la tarea (resultado 0). La extensión ahora
  pone un badge al hacer clic ("…", "✓", "X", "!", "?") porque Windows puede
  ocultar la notificación de Chrome y el clic no daba ninguna señal visible.
  Además, Smart App Control (Windows 11) bloquea los `.exe` sin firma: aquí el
  agente corre desde el código fuente con un lanzador local. Hay que revisarlo
  antes de repartir el `.exe` a agentes con Windows 11.

## Pendiente al iniciar

- Monitorear la primera semana de producción (sesión del proxy, RUC/CE) —
  observación, no una tarea con pasos.
- Escribir el runbook de la Etapa E (`docs/proxy-deploy.md`) en cuanto el
  usuario comparta el detalle operativo real de la instalación.
- Fase 5 (barrido final de documentación): última tarea del plan grande,
  después de la Etapa E.
- Diferido a pedido del usuario: la duda de `Escalabilidad.md`, la decisión de
  `actualizar_score_cliente`/`newsearch.php`, y el backlog v1.1.
