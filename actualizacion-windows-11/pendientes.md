# Pendientes y decisiones abiertas

Nada de esto se resolvió en la sesión del 2026-10-02.

## 1. La sesión de WinForce muere ~10 min después de cada renovación  ⚠️
- Observado: renovada a las ~18:08 y 18:19, declarada muerta a las 18:18 y 18:29
  (`edad_cookie_s` 603 y 593 en `logs/sesion_eventos.jsonl`). Misma cookie
  (`cookie_id f7d11867`) reenviada por la extensión.
- No se investigó. Hipótesis: (a) WinForce corta por inactividad antes de los 900 s
  del keepalive (`keepalive_interval_seconds`); (b) la sesión se cerró en el
  navegador del owner; (c) reenviar la misma cookie no la "revive".
- **No es de Windows 11.** Mientras pase, los agentes reciben HTTP 503
  ("reintenta en unos minutos") hasta que se renueve.

## 2. Smart App Control bloquea los `.exe` sin firma
- En Windows 11 con Smart App Control activo, `JSConnect-Win-Coverage.exe` no
  abre (en esta PC el owner sí abrió). En Windows 10 no existe: solo SmartScreen.
- Solución de fondo: **firmar** los `.exe` con un certificado de firma de código
  comercial. Mientras tanto, en Windows 11: correr desde el código (lanzador) o
  desactivar Smart App Control (en muchas versiones no se puede volver a activar
  sin reinstalar Windows).

## 3. ¿Dónde se publica el Release?
- El actualizador de los agentes busca Releases en el repo **original**:
  `REPO_NAME = "JSConnect-Win-Coverage"` en `build.ps1` (se escribe a
  `validator_app/version.py` al compilar).
- Si este repo W11 pasa a ser el oficial: cambiar `REPO_NAME` en `build.ps1`,
  recompilar y entregar el `.exe` nuevo **a mano una vez** (los `.exe` viejos
  siguen mirando el repo original).
- Los agentes con Windows 10 **no necesitan** el `.exe` nuevo (ver
  `cambios-por-archivo.md` §9).

## 4. Elevación de la consola owner corriendo desde el código
- `_ejecutar_elevado` (`generator/owner_app.py`) relanza
  `python -m generator.owner_app` con `Start-Process -Verb RunAs`; un proceso
  elevado arranca en `C:\Windows\System32`, así que **desde el código** ("Mostrar"
  / "Rotar" tokens) fallaría por no encontrar el módulo. Con el `.exe` funciona.
  Tampoco cita argumentos con espacios. No es de Windows 11; no se tocó.

## 5. Windows 10 sin soporte
- Windows 10 dejó de recibir actualizaciones de seguridad en octubre de 2025
  (salvo ESU). No afecta al funcionamiento de la app; sí a la seguridad de las PC
  de agentes.

## 6. Verificaciones que faltan
Ver `verificacion.md` → "NO probado todavía".
