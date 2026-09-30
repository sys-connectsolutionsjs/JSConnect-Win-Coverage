# Roadmap — JSConnect Win Coverage

Vista única de **qué se hizo**, **qué falta** y **en qué orden**. El detalle de
cada hito vive en `HistorialResumenes.md` y en `resumenes/<fecha>.md`.

Última actualización: 2026-09-30.

---

## Estado en una línea

**La Etapa D se completó (2026-09-29): el sistema ya está instalado en todas
las máquinas de la oficina y el usuario reportó que funciona sin incidencias**
(cuenta de WinForce de producción separada de la usada en desarrollo). El
score de RUC y el auto-actualizador, ambos con bugs reales encontrados en el
primer uso real del agente, quedaron corregidos y verificados en vivo antes del
despliegue. Lo que sigue: monitorear la primera semana en producción y escribir
el runbook de la Etapa E con el detalle real de esa instalación.

---

## Línea de tiempo — entregado

| Fecha | Hito | Commit(s) |
|---|---|---|
| 2026-08-19 | **Fase 0-1** — descubrimiento de la API interna, núcleo `core/` y tests | `e837681` |
| 2026-08-21 | **Arquitectura B** — proxy local para 20 agentes; SSO Microsoft 2FA | `a3bebf4` |
| 2026-08-25 | **Fase 1** — proxy FastAPI y códigos de error | `7cf7ea1` `f63660b` `801ce05` |
| 2026-08-27 | **Core real** — cobertura y score; fixes de BOM y doble codificación | `c72188c` `7bc6550` |
| 2026-09-04/05 | Login programático retirado, keepalive medido y fallos visibles | `1dcecc6` `5506ed4` `3925dbf` |
| 2026-09-08 | **Fase 2A** — keepalive “latido perezoso” | `b3adb38` |
| 2026-09-08 | **Fase 2.5/2.5d** — login asistido y extensión Chrome | `28b7698` `c96de4c` `cb085da` `499ba5f` `e517a2b` |
| 2026-09-08 | **Fases 3/4** — GUI standalone y cobertura FastAPI por tests | `5cf8e3f` `76afb9d` |
| 2026-09-09 | **Etapas 0/A/B/C** — config real, proxy y GUI end-to-end con WinForce | `d9c1ef7` `ffa213a` `7992e01` `3f63e8f` `898b9ab` `ffc5296` `f91b9fb` |
| 2026-09-09 | **Etapa R** — fail-fast 503 y avisos de sesión muerta | `82f3604`…`67ec0e4` |
| 2026-09-11 | **Etapa 0.5** — cookie enviada al proceso LocalSystem por HTTP | `f5eb257` |
| 2026-09-15 | Ensayo del instalador: WinSW 404 y redirecciones CMD corregidos | `abff2e4` `7306b9b` |
| 2026-09-16 | **Activación RSA + consola owner** — firma real, UX de portapapeles, builds separados y prueba manual exitosa | `784bd27` |
| 2026-09-18 | **Ensayo en la PC dev** — instalador re-ejecutable, consola owner con Reiniciar servicio, Activación/Huella en el agente, loopback permitido y tests hermeticos (157) | `2c4a757` `63ca477` + cierre del día |
| 2026-09-21 | **Credenciales en la consola owner** — panel Mostrar/Copiar/Rotar, `/admin/*` restringido a loopback y comparación en tiempo constante | `9367775` |
| 2026-09-21 | **Releases de owner + agente** — primer Release conjunto (`v2026.09.21`), fix de selección de asset/checksum en el updater cuando hay dos `.exe`, 191 tests | `3af91f6` |
| 2026-09-22 | **Fix UAC + idioma en la consola owner** — Mostrar/Rotar ya no fallan con "UAC cancelado" falso ni con `sc qc` en español; confirmaciones ampliadas; Release `v2026.09.22`, 193 tests | `6a6d94e` |
| 2026-09-25 | **"URL para los agentes" en la consola owner** — detecta la IP de LAN y la muestra lista para copiar, arreglando `WinError 10061` al configurar un agente en PC distinta a la del proxy (primer despliegue multi-PC real); Release `v2026.09.25`, 201 tests | `a575e85` |
| 2026-09-25 | **Fix del chequeo de actualización** — `target_commitish` es la rama, no un SHA; el updater creía siempre que había una versión nueva. Resuelve el commit real del tag vía `/commits/{tag}`. Sin Release nuevo (decisión: Release solo a pedido explícito, no por cada commit). 206 tests | `55cc7a6` |
| 2026-09-25 | **Firewall automático en el instalador** — `install_service.bat` abre el puerto del proxy en Windows Firewall (era solo una nota impresa); sin regla, un agente remoto fallaba con timeout en vez de error inmediato. Idempotente, con fallback manual si el firewall es de dominio; `uninstall_service.bat` la quita. 209 tests | `534b54e` |
| 2026-09-25 | **Validar cobertura o score por separado** — el botón VALIDAR ya no exige coordenadas Y documento a la vez; verificado en vivo contra WinForce real (score sin coordenadas, DNI de prueba 10412031). Release `v2026.09.25.1`, 212 tests | `513a2f7` |
| 2026-09-25 | **Rediseño visual (3 etapas)** — iconos distintos agente/owner/extensión (bug de bundling de Pillow corregido en el camino), tema ttkbootstrap (agente claro `cosmo` / owner oscuro `superhero`) con indicadores de cobertura/score coloreados por riesgo y fix de contraste WCAG en el owner, barra lateral de navegación extensible en el agente (rediseñada a ítem plano tras feedback). 219 tests | `d45d221`…`fefc16a` |
| 2026-09-27 | **Diagramas PlantUML versionados y corregidos** — `docs/DiagramasUML/` nunca se había commiteado (regla de `.gitignore` rota); movidos a `docs/diagramas/` (8 diagramas, incluida la consola owner que faltaba), corregidos contra el código real, `tests/test_diagramas.py` como guarda. 224 tests | `6119b6e`, `a465d56` |
| 2026-09-29 | **Reconfirmar antes de declarar la sesión muerta + bitácora de eventos** — falso positivo real (`/health` marcó "MUERTA" una sesión viva tras un solo timeout); `_confirmar_muerte()` reintenta antes de decidir; `logs/sesion_eventos.jsonl` registra cada renovación/muerte con causa y edad de la cookie. 235 tests | `3c3d4c1`, `dc7f4ea` |
| 2026-09-29 | **Enter valida + textos de riesgo/puntaje más claros** — `<Return>`/`<KP_Enter>` disparan la validación; "MUY ALTO" pasa a "riesgo: MUY ALTO" y "VALIDO" a "puntaje obtenido" (no implica aprobación). 238 tests | `c30f783` |
| 2026-09-29 | **Fix del auto-actualizador** — la app no se cerraba al actualizar, el `.bat` movía el `.exe` sin comprobar el resultado y relanzaba la versión vieja (segunda ventana, diálogo de proxy roto). Ahora espera el cierre real del proceso, reintenta el `move`, y la GUI se cierra sola con una barra de progreso. Release `v2026.09.29.1`, 238 tests | `71337be` |
| 2026-09-29 | **Fix: el score de RUC fallaba con "campos faltantes"** — `data[tipo_doc]` usa el Catálogo 06 de SUNAT (6 para RUC, no 3) y el campo de longitud se llama `logintud` en WinForce (typo real de ellos). Encontrado comparando una captura real de `tools/captura.py` contra el payload; verificado en vivo dos veces (mismo puntaje 575/ALTO que la captura del navegador). Release `v2026.09.29.2`, 240 tests | `9395033` |
| 2026-09-29 | **Icono nuevo de la extensión de Chrome** — reemplaza el cuadrado verde con flecha por un recuadro naranja con bordes redondeados y la "W" de Win | `136d225` |
| 2026-09-29 | **Etapa D completada** — instalado en todas las máquinas de la oficina; el usuario reportó funcionando sin incidencias, con una cuenta de WinForce de producción distinta de la usada en desarrollo. RUC y CE confirmados funcionando en producción. Reportado por el usuario, no verificable contra código | (despliegue operativo, sin commit) |
| 2026-09-30 | **Ventana del agente: logo, borrador y tabla comercial de scores** — logo junto a los campos, botones de limpiar con icono de borrador, rango de 100 puntos copiable + riesgo/color según la tabla de la empresa (el `NivelRiesgo` de WinForce ya no se muestra); Release `v2026.09.30`, 264 tests | `2e49cd2` |

---

## Aprobado y pendiente — en orden de ejecución

### 0. Ensayo previo + Etapa D — COMPLETADOS (2026-09-29)

El ensayo en la PC de desarrollo (iniciado 2026-09-18) y la Etapa D (PC owner
oficial y servicio de Windows) quedaron **superados por el despliegue real**:
el usuario reportó el sistema instalado en **todas las máquinas de la
oficina**, funcionando **sin incidencias**, con una cuenta de WinForce de
producción **separada** de la usada en desarrollo. Detalle de los pasos
seguidos en `PlanesAprobados.md` ("Etapa D — PC owner oficial"). Falta
monitorear la primera semana en producción (no es una tarea con pasos, es
observación).

### 1. Etapa E — runbook de la PC owner

Ya no está bloqueada por la Etapa D (que se completó) — sí está pendiente de
que el usuario comparta el detalle operativo real de esa instalación (qué
pasos se siguieron, qué se ajustó) para poder escribir
`docs/proxy-deploy.md` sin inventar contenido. Debe cubrir: Python 3.14.7,
ACL, LocalSystem, firewall, alta de agentes y la renovación diaria de sesión.

### 2. Etapa C.12 — modo standalone, opcional

Probar pegando una `PHPSESSID` solo si se necesita el modo sin proxy. Hoy el modo
proxy configurado gana y habría que limpiar `JSWinClient` del keyring.

### 3. Fase 5 — barrido final de documentación

Resolver el checklist histórico que siga vigente después de E. En este cierre
se actualizaron los documentos afectados por activación y handoff; los snapshots
anteriores permanecen inmutables.

---

## Investigaciones abiertas (2026-09-29)

- **"Dos logins en paralelo" invalidan la sesión** — hipótesis abierta desde
  el 2026-09-18. Recontextualizada: producción usa una cuenta de WinForce
  **distinta** de la de desarrollo, así que el escenario concreto que se
  investigaba en esta PC (dev y prod compartiendo cuenta) ya no aplica. Sigue
  en observación esta semana por si la sesión de producción muere sin causa
  clara. Tabla de experimentos lista en `docs/rotacion-credenciales.md`
  ("¿Por qué se cerró la sesión?") si hace falta retomarla.
- **`tipo_doc=4` para CE** en el Catálogo 06 de SUNAT — **CONFIRMADO**:
  probado en producción junto con RUC, ambos funcionando (2026-09-29,
  reportado por el usuario).
- **Duda del usuario en `Escalabilidad.md`** (2026-09-27, comentario a mano
  bajo "No hay que reescribir nada para escalar") — **diferida a pedido del
  usuario**, no urgente, se revisa otro día.

## Backlog v1.1

- Cobertura sin DNI en la GUI.
- Mejor detección de cierre manual del navegador asistido.
- Mapa, catálogo de venta, bootstrap de actualización, activación en línea,
  lotes y CRM básico.
- Decidir `actualizar_score_cliente` y creación final de lead.

---

## Bloqueos conocidos

| Etapa | Bloqueada por |
|---|---|
| E | que el usuario comparta el detalle operativo real de la instalación (Etapa D ya se completó) |
