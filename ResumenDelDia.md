# ResumenDelDia.md — Historial del día

Fecha: 2026-09-22

## Rotación del resumen anterior

El resumen del 2026-09-21 ya estaba preservado en `resumenes/2026-09-21.md` y en
`HistorialResumenes.md`. El detalle íntegro de hoy está en `resumenes/2026-09-22.md`
(snapshot) y su entrada condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- **Origen**: al probar en vivo (desde casa, PC con el proxy de desarrollo
  instalado) el panel "Credenciales del proxy" agregado ayer, el botón
  **Mostrar** fallaba con "No se concedió el permiso de administrador (aviso UAC
  cancelado)" **sin que apareciera ningún diálogo de UAC**, incluso corriendo la
  consola ya como Administrador.
- **Bug 1 (causa raíz)**: `_ejecutar_elevado()` combinaba `-Verb RunAs` con
  `-RedirectStandardOutput` en el mismo `Start-Process` de PowerShell —
  combinación inválida (`-Verb` exige `UseShellExecute=true` para elevar;
  `-RedirectStandardOutput` exige `UseShellExecute=false` para redirigir stdout).
  PowerShell rechazaba el `Start-Process` antes de mostrar ningún UAC real, y el
  `catch` del script lo traducía al mismo código que "UAC cancelado". Fix: la
  ruta del archivo de salida se pasa como argumento posicional al proceso
  relanzado; el subcomando elevado (`--leer-secretos`/`--rotar-secretos`) ahora
  escribe el JSON directamente en ese archivo en vez de usar stdout.
- **Confirmaciones agregadas/ampliadas** (pedido explícito, previendo que el
  personal abra la consola con doble clic en vez de "Ejecutar como
  administrador"): **Mostrar** ahora pide confirmación propia antes de disparar
  el UAC (antes no pedía ninguna); **Rotar** menciona en su aviso previo que
  Windows pedirá permiso de administrador, y su mensaje final indica dónde
  colocar el valor nuevo (proxy_token → reconfigurar cada agente vía ⚙
  Configuración → Configurar Proxy; admin_key → solo uso local).
- **Bug 2 (destapado al verificar el fix del Bug 1 en vivo)**: con el UAC real ya
  funcionando, Mostrar/Rotar fallaban con "No se encontró config.yaml" **aunque
  el servicio JSWinProxy estaba instalado y corriendo, y config.yaml existía**.
  Causa: `ruta_instalacion()` buscaba la etiqueta en inglés `BINARY_PATH_NAME` en
  la salida de `sc qc`, pero esta PC (como toda la oficina) tiene Windows en
  **español**, donde esa etiqueta sale como `NOMBRE_RUTA_BINARIO` — nunca
  matcheaba, caía al fallback de desarrollo (inválido en el `.exe` empaquetado,
  apunta al directorio temporal de PyInstaller) y fallaba. Fix (decisión del
  owner: detectar el idioma en vez de cambiar de comando): `ruta_instalacion()`
  ahora reconoce ambas etiquetas, inglés primero y español como segunda opción.
- **Verificación en vivo end-to-end** (esta PC, servicio real instalado):
  Mostrar y Rotar completos — confirmación de la app → UAC real de Windows →
  resultado correcto — para `proxy_token` y `admin_key`.
- **Tests**: 191 → **193** (`test_owner_app.py` 21→22, `test_secretos.py`
  11→12, incluye el caso de la etiqueta en español). Suite completa en verde,
  `ruff` limpio.
- **Documentación**: `docs/proxy-deploy.md` (confirmación previa al UAC, aviso
  ampliado de Rotar) y `TestingLog.md` actualizados.
- **Release**: se publicó `v2026.09.22` con los `.exe` de owner + agente ya
  corregidos, reemplazando `v2026.09.21` (que tenía ambos bugs).

## Siguiente sesión (continuar aquí)

1. Esta PC es de **desarrollo/pruebas** (home), no la PC oficial de la oficina:
   falta repetir la verificación del flujo elevado (UAC real, `sc qc` bilingüe,
   rotación end-to-end) en la PC oficial cuando se instale ahí.
2. Probar en vivo la ruta completa de descarga+reemplazo del updater
   (`aplicar_actualizacion`) contra `v2026.09.22` desde una versión anterior.
3. Sesión WinForce estable con una sola vía de login; `/health` a 1, 5 y 10 min.
4. Persistencia tras reiniciar el servicio; logs sin secretos; aviso de sesión
   muerta.
5. Firewall + agente desde otra PC de la LAN; `tools/probar_concurrencia.py`.
6. Desinstalar el ensayo; distribuir el Release publicado a las 15 PC.
7. Etapa D/E en la PC owner oficial (llevar `private_key.pem`), luego Fase 5.
8. Decidir si el instalador debe crear la regla de firewall y el acceso directo
   de la consola owner.
