# ResumenDelDia.md — Historial del día

Fecha: 2026-09-21

## Rotación del resumen anterior

El resumen del 2026-09-18 ya estaba preservado en `resumenes/2026-09-18.md` y en
`HistorialResumenes.md`. El detalle íntegro de hoy está en `resumenes/2026-09-21.md`
(snapshot) y su entrada condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- **Origen**: el owner propuso mostrar/copiar `proxy_token` y `admin_key` en la
  consola owner, bajo la premisa de un `key.pem` generado por el instalador —
  premisa incorrecta (el instalador solo genera los dos tokens; la llave crítica
  es `private_key.pem`, de otro instalador, no rotable). La idea se validó igual
  por otra razón: la consola ya vive junto a esa llave, así que exponer
  credenciales rotables ahí no aumenta el riesgo marginal.
- **Hallazgos de seguridad**: `admin_key` era superconjunto de `proxy_token`
  (`/admin/config` lo devolvía en claro); `verify_admin_key` no validaba IP con
  el server en `0.0.0.0`; `proxy_token` abre `/api/score` (score por DNI, dato
  personal de terceros).
- **`server.py`**: `/admin/*` restringido a loopback (no configurable, a
  diferencia de `allowed_networks`); comparación de tokens con
  `secrets.compare_digest`.
- **`secretos.py`** (nuevo): lectura y rotación de ambos tokens, preservando el
  resto de `config.yaml`, reaplicando la ACL y reiniciando el servicio.
- **`owner_app.py`**: panel "Credenciales del proxy" — Mostrar (se oculta a los
  30 s), Copiar (limpia el portapapeles a los 60 s), Rotar (con confirmación
  reforzada para el proxy token). Corre vía relanzo elevado con UAC (`--leer-
  secretos`/`--rotar-secretos`), sin debilitar la ACL de `config.yaml`.
  `private_key.pem` nunca aparece en la GUI.
- **Tests**: 157 → **178** (`test_secretos.py` nuevo, `test_owner_app.py` y
  `test_proxy.py` ampliados). Suite completa en verde.
- **Documentación**: `docs/arquitectura.md` y `docs/proxy-deploy.md`
  actualizados con el comportamiento loopback-only y el panel nuevo.

## Siguiente sesión (continuar aquí)

1. Probar el flujo elevado en la PC oficial con el servicio instalado: UAC real,
   `sc qc` contra un binPath real, rotación end-to-end (agente con token viejo →
   401 → token nuevo → 200).
2. Sesión WinForce estable con una sola vía de login; `/health` a 1, 5 y 10 min.
3. Persistencia tras reiniciar el servicio; logs sin secretos; aviso de sesión
   muerta.
4. Firewall + agente desde otra PC de la LAN; `tools/probar_concurrencia.py`.
5. Desinstalar el ensayo; publicar el agente (`publish-release.ps1`) para las
   15 PC.
6. Etapa D/E en la PC owner oficial (llevar `private_key.pem`), luego Fase 5.
7. Decidir si el instalador debe crear la regla de firewall y el acceso directo
   de la consola owner.
