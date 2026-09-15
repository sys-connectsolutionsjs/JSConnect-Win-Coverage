# ResumenDelDia.md — Historial del día

Fecha: 2026-09-15

## Qué se hizo hoy

### Rotación del resumen 2026-09-11 — HECHO
`resumenes/2026-09-11.md` creado (snapshot completo: cierre de la Etapa 0.5 +
planificación de la Etapa D). Entrada condensada agregada en
`HistorialResumenes.md` (total: 11 entradas).

### Etapa D — instalar el servicio de Windows (ensayo en esta PC) — EN CURSO

Retomada del plan del 11-sep (nada la bloqueaba: R y 0.5 hechas). El owner
corrió `install_service.bat` como Administrador:

- `[1/12]` Python 3.14 OK, `[2/12]` deps OK, `[3/12]` Chromium (ya en caché) OK.
- **`[4/12]` (descargar `winsw.exe`) falló** — las dos URLs abortaron el
  instalador.

**Diagnóstico** (verificado con `curl` + la API de GitHub):
- `install_service.bat:89` apuntaba a
  `.../winsw/releases/download/v3.0.0/WinSW.NET4.exe` → **404, ese tag nunca
  existió como release estable** (solo hay `v3.0.0-alpha.9/10/11`; la última
  release real de `winsw/winsw` es **v2.12.0**). Bug de origen del script, no
  algo que se rompió ahora.
- El fallback a `/releases/latest/download/WinSW.NET4.exe` sí resuelve bien
  (a v2.12.0, `curl` lo baja limpio: 200, 852 KB) pero **también falló** en la
  terminal elevada del usuario con `Invoke-WebRequest` de PowerShell — causa
  probable: Windows PowerShell 5.1 no siempre negocia TLS 1.2 por defecto
  contra GitHub (síntoma clásico: falla silenciosa, `curl.exe` con la misma URL
  funciona). El `2>nul` del script se tragaba el error real, sin pista.

**Arreglado** (`abff2e4`): URL corregida a `v2.12.0` (real, verificada contra la
API de GitHub); descarga primero con `curl.exe`, fallback a PowerShell forzando
TLS 1.2; ya no se traga el error real. De paso, **5 flechas `->` sin escapar**
en `echo` (que en `cmd.exe` siempre son redirección) — la de la rama "no sos
administrador" ya había creado un archivo literal `Ejecutar como administrador`
en el repo durante la prueba de hoy (borrado); las otras 3 están en el resumen
final tras el paso 12, nunca ejercidas hasta esta primera corrida real.

**Pendiente**: que el owner vuelva a correr `install_service.bat` como
Administrador desde cero.
