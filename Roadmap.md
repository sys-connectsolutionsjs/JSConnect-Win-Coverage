# Roadmap — JSConnect Win Coverage

Vista única de **qué se hizo**, **qué falta** y **en qué orden**. El detalle de
cada hito vive en `HistorialResumenes.md` y en `resumenes/<fecha>.md`.

Última actualización: 2026-09-18.

---

## Estado en una línea

El núcleo, proxy, keepalive, extensión, GUI, detección de sesión muerta,
persistencia bajo LocalSystem y activación RSA están construidos y probados. La
consola owner también generó un código que activó correctamente un agente. El
siguiente paso es cerrar el ensayo completo en la PC de desarrollo (en curso desde
2026-09-18) y luego instalar y validar el servicio en la PC owner oficial; nada
corre en producción todavía.

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

---

## Aprobado y pendiente — en orden de ejecución

### 0. Ensayo previo en la PC de desarrollo — en curso (2026-09-18)

Instalador re-ejecutable con pregunta de tokens ya probado dos veces; consola owner
(con Reiniciar servicio) y agente contra el proxy probados. Falta:
sesión WinForce estable (una sola vía de login), persistencia tras reiniciar el
servicio, agente contra el proxy, firewall (el instalador solo imprime el
comando), carga con `tools/probar_concurrencia.py` y desinstalar el ensayo.
Hallazgo: `localhost` daba 403 por `allowed_networks` (corregido: loopback siempre
permitido; ver `docs/arquitectura.md`, "Control de acceso"). Hallazgo: la extensión de Chrome forzada por política solo se aplica en PC
gestionada (dominio/Azure AD); en las demás se carga a mano (Modo de
desarrollador → Cargar descomprimida → `.extension_build`).

### 1. Etapa D — PC owner oficial y servicio de Windows

1. Clonar/actualizar `main` en la PC owner oficial.
2. Transferir `private_key.pem` por un canal privado, fuera de Git, y restringir
   su ACL. Construir/abrir la consola owner y realizar una activación de control.
3. Ejecutar `install_service.bat` como Administrador y verificar sus 12 pasos.
4. Iniciar sesión en WinForce y renovar la cookie por la extensión o la consola.
5. Reiniciar el servicio y confirmar que LocalSystem recupera la cookie.
6. Configurar un agente con URL completa `http://<ip>:8080` y token; validar
   cobertura y score reales.
7. Revisar `<repo>\logs\` sin secretos, alertas y firewall limitado a la LAN.

La etapa requiere acceso físico a la PC owner oficial y el traslado privado del
PEM. Es el siguiente trabajo operativo.

### 2. Etapa E — runbook de la PC owner

Actualizar `docs/proxy-deploy.md` con el procedimiento observado en la Etapa D:
Python 3.14.7, ACL, LocalSystem, firewall, alta de agentes y renovación diaria.

### 3. Etapa C.12 — modo standalone, opcional

Probar pegando una `PHPSESSID` solo si se necesita el modo sin proxy. Hoy el modo
proxy configurado gana y habría que limpiar `JSWinClient` del keyring.

### 4. Fase 5 — barrido final de documentación

Resolver el checklist histórico que siga vigente después de D/E. En este cierre
se actualizaron los documentos afectados por activación y handoff; los snapshots
anteriores permanecen inmutables.

---

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
| D | acceso a la PC owner oficial y transferencia privada del PEM |
| E | resultados reales de la Etapa D |
