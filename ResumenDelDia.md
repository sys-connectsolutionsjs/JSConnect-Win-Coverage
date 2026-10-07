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
10. **Punto 6 (sesión de WinForce) acordado con el usuario.** Su hipótesis (alguien inicia
    sesión con la misma cuenta y eso invalida la `PHPSESSID`; al volver a iniciar sesión todo
    se normaliza) es razonable y los datos no la descartan: el "tope de 9.5 h" salió de una
    sola corrida (sábado 21:08 → ≈ 06:38 del domingo). Los docs pasaron de "hecho medido" a
    "una medición, no concluyente" (`anotaciones.md` lleva la corrección; protocolo en
    `docs/rotacion-credenciales.md` → "Cómo investigar una muerte de sesión"). Sin cambios
    de código. El patrón de ~10 min tras renovar (593 y 603 s, mismo `cookie_id`) sigue sin
    explicar.
11. **Fase 5 completada** (barrido de documentación). La revisión contrastó los 19 hallazgos
    de 2026-09-09 con el código actual: 13 ya estaban corregidos; se corrigieron el resto y
    lo nuevo — `/admin/*` es solo loopback (no hay renovación/discovery remoto por VPN),
    ejemplos de versión `"dev"`, URL del proxy con `http://`, conteos de agentes (25 hoy, 41
    previstos), Python 3.14.7, avisos de "documento histórico" en `actualizacion-windows-11/`.
    Dato para la duda diferida de `Escalabilidad.md` (no tocada): lo de "no hay que reescribir
    nada" no se cumple para `/admin/*` remoto.
12. **3 bugs de código del agente** (Configurar Proxy): `IP:puerto` sin `http://` se
    normaliza (#14), "Probar conexión" muestra el motivo real (#19), guardar ya no revienta
    si el keyring falla (#18); además el texto de `session_age` dice "última actividad".
13. **La consola owner busca actualizaciones** (pedido del usuario): botón "Buscar
    actualizaciones", chequeo silencioso al abrir y versión en pantalla. Compara el
    **SHA-256** de su `.exe` con el del Release (no el commit, para no entrar en bucle si un
    Release reutiliza un owner viejo). `build-owner.ps1` ahora graba `version.py`. La
    ventana toma el tamaño de su contenido. **El owner ya instalado se reemplaza a mano una
    sola vez.**
14. **`AGENTS.md` dividido**: 113 KB → 26 KB. Las 43 tareas completadas y la bitácora por
    fases + cierres de sesión (2026-08-18 → 2026-10-02) pasaron tal cual a
    `docs/historial-agents.md` (verificado: ninguna línea perdida). `AGENTS.md` conserva
    reglas vivas, tareas abiertas y solo el último cierre; las reglas de cierre y el mapa
    de conocimiento reflejan la nueva convención.
15. **Release `v2026.10.07.1`** (tag → `154ba5e`, agente + owner), publicado y verificado
    contra GitHub: el agente `v2026.10.07` detecta la nueva y la nueva no se ofrece
    actualización a sí misma; el owner por hash igual; la descarga del owner coincide con su
    checksum. Tests 291 → **318**, ruff limpio. Los agentes en `v2026.09.30` saltan directo a
    esta versión (el actualizador solo mira el último Release).

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
- **Reemplazar a mano el `.exe` del owner** instalado (`v2026.10.07`) por el de
  `v2026.10.07.1`; desde ahí se actualiza solo.
- **Observar por qué la sesión de WinForce muere ~10 min después de renovar** (hipótesis del
  usuario: login ajeno con la misma cuenta; `docs/rotacion-credenciales.md` → "Cómo
  investigar una muerte de sesión").
- **Archivo del pendrive con URL + token para el agente** (idea acordada; ahora que la
  Fase 5 terminó, es lo siguiente a hacer si el usuario lo confirma; con su propio Release).
- Firma de código de los `.exe` (Smart App Control en Windows 11).
- Monitorear la primera semana de producción (sesión del proxy, RUC/CE) —
  observación, no una tarea con pasos.
- **Probar el recorrido del pendrive** en una PC owner limpia (Etapa E ya escrita) y
  anotar lo que se ajuste en `docs/proxy-deploy.md`.
- Diferido a pedido del usuario: Etapa C.12 (modo standalone), la duda de
  `Escalabilidad.md`, la decisión de `actualizar_score_cliente`/`newsearch.php` y el
  backlog v1.1.
