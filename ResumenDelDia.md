# ResumenDelDia.md — Historial del día

Fecha: 2026-10-07

## Rotación del resumen anterior

El detalle íntegro del 2026-10-02 (PC oficina en Windows 11 + nota del plugin
`documentation` del 2026-10-06) quedó en `resumenes/2026-10-02.md` y su entrada
condensada en `HistorialResumenes.md`. El repo `W11-JSConnect-Win-Coverage` tenía ese
mismo resumen sin rotar; al unirse, se rotó una sola vez aquí.

## Qué se hizo hoy

### 2026-10-07 — Unificación W10 + W11, huella estable y red del owner

1. **Un solo repo.** El repo W11 estaba exactamente 4 commits por delante de este
   (`5cb8768`, `a40a0d5`, `4fe66d3`, `84aa745`), en línea recta: se trajo con
   `git merge --ff-only` desde un clon local (sin conflictos) y se trajo también el tag
   `v2026.10.02-w11`. `ResumenDelDia.md` se conservó con `git stash`.
2. **Diagnóstico de "owner W11 + agentes W10 se rompe".** La activación no depende de
   la versión de Windows (la huella se firma en cada agente). Lo que rompía es el PC
   owner, que además hospeda el proxy: la regla de firewall solo cubría `Domain,Private`
   y Windows 11 deja la red en **Pública** → agentes con timeout. Ya estaba corregido en
   la rama W11 (`-Profile Any` limitado a la LAN).
3. **Huella estable** (`validator_app/activation/fingerprint.py`): la huella antigua
   (`MachineGuid|MAC|CPU|volumen`) cambiaba con VPN/Wi-Fi aleatorio, un USB o la falta de
   `wmic`, y por eso se perdía el estado "activado". La nueva usa solo MachineGuid + CPU
   del registro (sin subprocess). `activacion_vigente()` devuelve `"vigente"`,
   `"transicion"` (activación hecha con la huella antigua: sigue funcionando y pide
   reactivar) o `None`. `huellas_legacy()` solo se calcula si la guardada no es la
   actual. Commit `212f300`.
4. **Red del owner** (`install_service.bat`, commit `ce3f60a`): si la red es Pública y
   el PC no está en dominio, **ofrece** pasarla a Privada (`choice`, por defecto NO, 60 s)
   y avisa si el perfil Público bloquea todo lo entrante. Nunca cambia nada sin
   preguntar, para que otros call centers instalen sin tocar su red. Documentado en
   `docs/proxy-deploy.md`.
5. **Documentación**: README (es/en), `AGENTS.md` (cierre de sesión), `anotaciones.md`,
   `actualizacion-windows-11/` (banner + pendiente §3 resuelto) y `docs/proxy-config.md`.
6. **Tests**: 287 → **291**, ruff limpio.
7. **Release `v2026.10.07`** (tag → `57a42bc`, agente + owner) en este repo. Verificado
   contra GitHub: el `.exe` nuevo no se ofrece una actualización falsa y el de
   `v2026.09.30` sí detecta `v2026.10.07`. Prueba en esta PC (Windows 10): con la
   activación real arranca en "transición" (la huella guardada está entre las antiguas).
8. **Repo W11 archivado**: recibió el mismo código por fast-forward, un aviso en su README
   (`e23c146`) y un release puente `v2026.10.07` (mismo `.exe`, que ya consulta este
   repo) para que cualquier `.exe` del canal W11 se pase solo al oficial. Luego se
   archivó con `gh repo archive`; sigue público (el usuario lo pondrá privado más adelante,
   cuando esos `.exe` ya se hayan actualizado).

9. **Etapa E completada — runbook con pendrive.** El usuario contó su procedimiento
   real (Python en la PC owner; repo, `.exe` y `private_key.pem` por pendrive; agentes
   con `.exe` + URL + token por pendrive; Python **3.14.7**). Quedó en
   `docs/proxy-deploy.md` → "Instalación con pendrive", verificado contra
   `install_service.bat` (13 pasos): Python para todos los usuarios, copia a
   `C:\jsconnect` (rutas absolutas en `winsw.xml`), pip siempre elevado, extensión
   manual, red Pública. **No probado de punta a punta** desde un pendrive en una PC
   limpia. Idea futura (no existe): que el agente lea URL y token de un archivo del
   pendrive. También se puso al día el `Roadmap.md`.

## Pendiente al iniciar

- **Reactivar los agentes** con la huella nueva (hoy 25: 18 + 7; a futuro 41). Funcionan
  en "transición" hasta entonces. **NO borrar `huellas_legacy()`** (ni su uso en
  `validator_app/gui/main_window.py`) salvo que el usuario lo pida expresamente: el
  actualizador salta directo al último Release, y quien se salte la transición perdería
  la activación. Regla completa en `AGENTS.md` → "Versionado y actualizaciones".
- **Probar un agente W10 real contra el owner W11** y revisar en el owner
  `Get-NetConnectionProfile` / la regla `JSWinProxy API`.
- Poner `W11-JSConnect-Win-Coverage` en privado (ya archivado) **solo después** de que
  los `.exe` del canal W11 se hayan actualizado a `v2026.10.07`; si no, pierden su canal.
- **Investigar por qué la sesión de WinForce muere ~10 min después de cada renovación**
  (`actualizacion-windows-11/pendientes.md` §1).
- Firma de código de los `.exe` (Smart App Control en Windows 11).
- Monitorear la primera semana de producción (sesión del proxy, RUC/CE) —
  observación, no una tarea con pasos.
- **Probar el recorrido del pendrive** en una PC owner limpia (Etapa E ya escrita) y
  anotar lo que se ajuste en `docs/proxy-deploy.md`.
- Fase 5 (barrido final de documentación): última tarea del plan grande; la Etapa E
  ya está hecha.
- Diferido a pedido del usuario: la duda de `Escalabilidad.md`, la decisión de
  `actualizar_score_cliente`/`newsearch.php`, y el backlog v1.1.
