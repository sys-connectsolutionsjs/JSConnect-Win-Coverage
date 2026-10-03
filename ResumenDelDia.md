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

### 2026-10-02 — PC oficina en Windows 11 (owner + proxy)

> Detalle completo para revisar con calma: **[`actualizacion-windows-11/`](actualizacion-windows-11/README.md)**
> (cambios por archivo, verificación, cambios en la PC, pendientes).
> Código: commit `5cb8768`. Solo en el repo `W11-JSConnect-Win-Coverage`;
> el repo original no se tocó.

1. **Instalación de la PC oficina** (Windows 11 Pro 25H2, build 26200). Se instaló
   Git, Python 3.14.7 (todos los usuarios), el `.venv` y Chromium. Se clonó el
   repo y se ejecutó `install_service.bat`: servicio `JSWinProxy` en el
   puerto 8080, tokens nuevos, tarea de aviso e icono del Escritorio. También se
   compilaron `JSConnect-Win-Owner.exe` y `JSConnect-Win-Coverage.exe`.
2. **Smart App Control** (Windows 11) bloquea `JSConnect-Win-Coverage.exe` porque
   no está firmado. En esta PC el agente corre desde el código con el lanzador
   `%LOCALAPPDATA%\JSConnect-Win-Coverage\lanzar_agente.pyw` y accesos directos
   con AppUserModelID propio, anclables a la barra de tareas.
3. **El popup "sesión caducada" nunca salía.** `eventcreate` rechaza el origen
   `JSWinProxy` registrado con `New-EventLog`, y el error se perdía en silencio.
   Se corrigió con `ReportEventW` (ctypes). Verificado en producción: la sesión
   caducó de verdad a las 18:29 y la tarea mostró el popup (resultado 0). La
   extensión de Chrome ahora pone un badge al hacer clic (…, ✓, X, !, ?).
4. **Adaptación a Windows 11** (6 problemas reales, ver la carpeta):
   - firewall con perfil Any, limitado a la LAN, porque la red es Pública;
   - huella sin `wmic`, por CIM, compatible hacia atrás;
   - renovar la sesión sin elevar, porque `config.yaml` tiene ACL de administrador;
   - `CREATE_NO_WINDOW` para que Windows Terminal no robe el foco;
   - secretos fuera del historial Win+V;
   - bugs de `install_service.bat`: puerto, health check, ACL por SID y Python real.

   Resultado: 287 tests en verde y el instalador re-ejecutado completo en la PC.
5. **Los agentes siguen en Windows 10** con el Release `v2026.09.30` y no
   necesitan nada: la API del proxy no cambió y la huella en Windows 10 es
   idéntica.
6. **Subida al repo `W11-JSConnect-Win-Coverage`**: el remoto `w11`, con el commit
   de código `5cb8768` y este commit de documentación.

## Pendiente al iniciar

- **Revisar con calma la adaptación a Windows 11** (`actualizacion-windows-11/`)
  antes de darla por buena.
- **Investigar por qué la sesión de WinForce muere unos 10 min después de cada
  renovación** (`actualizacion-windows-11/pendientes.md` §1).
- Probar un **agente real con Windows 10** contra el proxy de la PC con Windows 11
  (`actualizacion-windows-11/verificacion.md`).
- Decidir **dónde se publica el Release** (repo original o W11; `REPO_NAME` en
  `build.ps1`).
- Monitorear la primera semana de producción (sesión del proxy, RUC/CE) —
  observación, no una tarea con pasos.
- Escribir el runbook de la Etapa E (`docs/proxy-deploy.md`) en cuanto el
  usuario comparta el detalle operativo real de la instalación.
- Fase 5 (barrido final de documentación): última tarea del plan grande,
  después de la Etapa E.
- Diferido a pedido del usuario: la duda de `Escalabilidad.md`, la decisión de
  `actualizar_score_cliente`/`newsearch.php`, y el backlog v1.1.
