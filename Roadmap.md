# Roadmap — JSConnect Win Coverage

Vista única de **qué se hizo**, **qué falta** y **en qué orden**. El detalle de
cada hito vive en `HistorialResumenes.md` y en `resumenes/<fecha>.md`.

Última actualización: 2026-10-09.

---

## Estado en una línea

**La Etapa D se completó (2026-09-29): el sistema ya está instalado en todas
las máquinas de la oficina y el usuario reportó que funciona sin incidencias**
(cuenta de WinForce de producción separada de la usada en desarrollo). El
score de RUC y el auto-actualizador, ambos con bugs reales encontrados en el
primer uso real del agente, quedaron corregidos y verificados en vivo antes del
despliegue. **Desde el 2026-10-07 hay un solo repo para Windows 10 y 11**
(Release `v2026.10.07.1`, huella de activación estable, consola owner con
actualizaciones propias), el runbook de la Etapa E está escrito (instalación con
pendrive) y la Fase 5 (barrido de documentación) terminó. Lo que sigue: reactivar
los agentes con la huella nueva, reemplazar a mano el `.exe` del owner una vez,
probar un agente W10 contra el owner W11 y monitorear la primera semana en
producción. **El 2026-10-09 se construyó el mapa de cobertura con reglas de venta por zona** (subido a `main`, **sin Release**): falta probarlo con asesores, recompilar y publicar.

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
| 2026-10-07 | **Repos W10 + W11 unificados, huella estable y runbook de la Etapa E** — el repo W11 (4 commits por delante) se unió por fast-forward y se archivó; la huella de activación pasa a MachineGuid + CPU del registro (las activaciones antiguas siguen válidas en "transición"); el instalador del proxy ofrece pasar una red Pública a Privada (por defecto NO); runbook de instalación con pendrive en `docs/proxy-deploy.md`. Release `v2026.10.07`, 291 tests | `212f300` `ce3f60a` `57a42bc` `12a7960` |
| 2026-10-07 | **Fase 5, consola owner con actualizaciones y `AGENTS.md` dividido** — barrido de documentación (19 hallazgos revalidados), 3 bugs de Configurar Proxy del agente arreglados (URL sin `http://`, error real en Probar conexión, keyring), la consola owner busca actualizaciones por SHA-256, `AGENTS.md` 113 KB → 26 KB (historial en `docs/historial-agents.md`), "tope de 9.5 h" marcado como medición no concluyente. Release `v2026.10.07.1`, 318 tests | `5f382a5` `46e8a32` `154ba5e` |
| 2026-10-09 | **Mapa de cobertura y reglas de venta por zona** — página Mapa (`tkintermapview`) con cobertura, fraude, Preferente 2 (score ≥ 401), códigos bloqueados y Zona F; decisión **antes** de gastar score (bloqueada → no se consulta; sin cobertura pero con cobertura a ≤ 300 m → "extensible"); solo la cobertura en vivo depende de WinForce (si falla se avisa y se dan las condiciones de la zona); capas embebidas en el .exe (datos de terceros, gitignored); ventana de una sola medida + pantalla completa (F11). **Sin Release aún**, 421 tests | `3942e2d` `89a6d03` |

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

### 1. Etapa E — runbook de la PC owner — COMPLETADA (2026-10-07)

Escrito en `docs/proxy-deploy.md` → "Instalación con pendrive", con el procedimiento
real del usuario: Python 3.14.7 para todos los usuarios, repo + `.exe` +
`private_key.pem` por pendrive (copiados a `C:\jsconnect`), `install_service.bat`,
extensión manual, firewall/red y alta de agentes. Falta probarlo de punta a punta
desde un pendrive en una PC limpia; que el agente lea URL y token de un archivo del
pendrive es una mejora posible (no existe).

### 1b. Pendiente tras la unificación W10 + W11 (2026-10-07)

- Reactivar los agentes con la huella nueva (25 hoy, 41 a futuro).
- Reemplazar a mano el `.exe` del owner instalado (`v2026.10.07`) por el de
  `v2026.10.07.1`; desde ahí se actualiza solo.
- Probar un agente W10 real contra el owner W11.
- Observar por qué la sesión de WinForce muere ~10 min después de renovar (hipótesis del
  dueño: un login ajeno con la misma cuenta; el "tope de 9.5 h" es una medición no
  concluyente). Pasos en `docs/rotacion-credenciales.md` → "Cómo investigar una muerte
  de sesión".
- Siguiente mejora acordada: que el agente lea la URL y el token de un archivo del
  pendrive (con su propio Release).
- Firma de código de los `.exe` y pasar el repo W11 (archivado) a privado cuando sus
  `.exe` se hayan actualizado.
- `huellas_legacy()` **no se borra** salvo petición expresa.

### 2. Etapa C.12 — modo standalone, opcional

Probar pegando una `PHPSESSID` solo si se necesita el modo sin proxy. Hoy el modo
proxy configurado gana y habría que limpiar `JSWinClient` del keyring.

### 3. Fase 5 — barrido final de documentación — COMPLETADA (2026-10-07)

Se revalidaron los 19 hallazgos contra el código (13 ya estaban resueltos), se
corrigieron los restantes y los 3 bugs de código de la ventana del agente, y se
dividió `AGENTS.md` (historial en `docs/historial-agents.md`). Detalle en
`PlanesAprobados.md` (Fase 5). Los snapshots de `resumenes/` permanecen inmutables.

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
- Catálogo de venta, bootstrap de actualización, activación en línea,
  lotes y CRM básico. (El mapa de cobertura ya tiene su primera versión, 2026-10-09; falta el
  Release y la detección automática de "no cruzar avenida de doble vía".)
- Decidir `actualizar_score_cliente` y creación final de lead.

---

## Bloqueos conocidos

| Etapa | Bloqueada por |
|---|---|
| — | Ninguno (la Etapa E se completó el 2026-10-07) |
