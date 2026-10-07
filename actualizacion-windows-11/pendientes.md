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

## 3. Releases: dos repos, dos canales de actualización  ✅ RESUELTO 2026-10-07
- **Resuelto:** los dos repos se unieron en `JSConnect-Win-Coverage` (fast-forward de
  los 4 commits de W11). `W11-JSConnect-Win-Coverage` queda archivado; el único canal
  de actualización es este repo. Lo de abajo es el historial de la decisión.
- **Publicado 2026-10-02:** Release
  [`v2026.10.02-w11`](https://github.com/sys-connectsolutionsjs/W11-JSConnect-Win-Coverage/releases/tag/v2026.10.02-w11)
  (tag → `4fe66d3`, agente + owner). Verificado que su actualizador no ofrece una
  actualización falsa. **Queda pendiente** decidir si este repo reemplaza al
  original como fuente oficial o conviven.
- **Decidido 2026-10-02:** los `.exe` publicados en **este** repo se compilan con
  `powershell -ExecutionPolicy Bypass -File build.ps1 -RepoName "W11-JSConnect-Win-Coverage"`,
  así su actualizador busca Releases **aquí**. Sin el parámetro, `build.ps1` sigue
  apuntando al repo original (valor por defecto).
- **Por qué importa:** el actualizador compara el commit embebido con el commit del
  tag del último Release **del repo que tiene grabado**. Un `.exe` de este repo que
  apuntara al original vería `v2026.09.30` (otro commit) y ofrecería "actualizar",
  o sea **volver a la versión vieja**.
- Los agentes con el `.exe` del repo original siguen mirando el original; no ven
  los Releases de aquí. Para pasarlos a este canal hay que entregarles el `.exe`
  de aquí **a mano una vez**.
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
