# ResumenDelDia.md — Historial del día

Fecha: 2026-09-18

## Rotación del resumen anterior

El resumen del 2026-09-16 ya estaba preservado en `resumenes/2026-09-16.md` y en
`HistorialResumenes.md`. Hoy se abre el día 2026-09-18 y su contenido se registró
también en `resumenes/2026-09-18.md` y en el historial.

## Qué se hizo hoy

- Se aclaró la **Etapa E** (runbook de la PC owner, bloqueada por acceso físico) y
  se decidió hacer antes un **ensayo completo en la PC de desarrollo**; la oficina
  tiene 15 PC, meta 35, con 2 agentes piloto primero.
- Hallazgos: la consola owner no crea acceso directo en el Escritorio; el
  instalador no crea regla de firewall; `winsw install` fallaba al ejecutar el
  `.bat` dos veces.
- `install_service.bat` ahora se relanza con `cmd /k` (no se cierra), verifica
  cada paso (`ya estaba` / `hecho ahora`) y muestra un resumen final.
  `docs/proxy-deploy.md` documenta la re-ejecución segura.
- Verificado solo el camino sin Administrador; la ejecución elevada está
  pendiente. Cambios **sin commitear** (`install_service.bat`,
  `docs/proxy-deploy.md`, más estos documentos).

- **Bug del paso 5 corregido**: la primera corrida elevada se cortaba al llegar
  al paso 5. Causa: `)` sin escapar en `echo` dentro de bloques `( ... )`
  (líneas de los pasos 3, 5, 8, 10, 11 y 12); CMD parsea el bloque entero y
  aborta. Se escaparon y se añadió `tests/test_install_bat.py` como guarda
  (143 tests, ruff limpio).
- El paso 5 ahora avisa si ya hay tokens y pregunta **C**onservar (por defecto a
  los 20 s) o **R**egenerar (reinicia el servicio y reutiliza el puerto).

- **Extensión de Chrome**: en esta PC (Windows 10 Home, WORKGROUP) Chrome ignora
  la política de fuerza-instalación; nunca se había probado de punta a punta. El
  paso 7 ya no dice "verificado": detecta PC gestionada (dominio/Azure AD), solo
  avisa y al final imprime la carga manual. La PC del jefe (Windows 10 Pro)
  debería aplicarla. Nota: con `config.yaml` instalado (ACL SYSTEM/Admins),
  `tests/test_proxy.py` falla con PermissionError si se ejecuta sin elevar
  (37 casos); se resuelve al desinstalar el ensayo o ejecutando pytest elevado.

- **Consola owner**: "falta configurar el servicio" era un `PermissionError` al
  leer `config.yaml`, no Chrome. Además, en el `.exe` empaquetado `config.yaml`
  no existe (ValidationError). Ahora cualquier fallo usa `127.0.0.1:8080` y el
  estado real lo da `/health`; `.exe` reconstruido. `tests/conftest.py` aísla el `config.yaml` real (146 tests, ruff
  limpio).
- **Abierto**: la sesión WinForce murió tres veces (15:06, 15:32, 15:45) pese a
  renovaciones 200; hipótesis sin confirmar: dos logins en paralelo se invalidan.
- Todo commiteado y subido a `origin/main`.

## Siguiente paso

1. Confirmar la sesión estable con una sola vía de login (Chrome + extensión) y
   `/health` a 1, 5 y 10 minutos.
2. Continuar el ensayo: reiniciar el servicio, agente contra el proxy, firewall,
   `logs\`, `tools/probar_concurrencia.py` y `uninstall_service.bat`.
3. Después, la Etapa D en la PC owner oficial (pasos en
   `resumenes/2026-09-16.md`), la Etapa E y la Fase 5.
