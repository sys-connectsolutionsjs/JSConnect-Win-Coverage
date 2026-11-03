# ResumenDelDia.md — Historial del día

Fecha: 2026-11-03

## Rotación del resumen anterior

El detalle íntegro del 2026-10-30 quedó en `resumenes/2026-10-30.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- **Bitácora del proxy**:
  - En horario de oficina la sesión muere cada 5-15 min: el lunes 21 muertes y ~70 min caída, casi todo por
    las pausas del freno; hoy 12 hasta las 14:50.
  - Noches y fin de semana: 0 muertes (la sesión del finde duró ~62 h).
  - El owner confirma que **otra persona usa la cuenta del proxy en el día** (ping-pong). Acción pendiente del
    owner: identificarla o darle otra cuenta. No se toca el freno.
  - Quien consulta `/health` cada 5 min es la extensión de Chrome (alarma `estado`), y por eso descubre casi
    todas las muertes. Se deja así.
- **Prueba en vivo de la consulta que espera al autologin: HECHA**.
  - 16:19: `consulta_reintentada` con detección 3.5 s, autologin 7.8 s, consulta 0.4 s y total 11.7 s. El
    asesor recibió la cobertura.
  - Tres muertes provocadas en 6 min (16:15, 16:19, 16:21) activaron la pausa del freno. Las consultas de
    16:21-16:23 dieron 503, con el aviso y las reglas locales. Las pruebas se espacian más de 10 min.
- **Recorte**: la confirmación de muerte baja de 3 s a 1 s (TDD). "No revalidar la misma cookie" quedó
  descartado, porque ahorraba ~0.3 s.
- **Resultado del asesor en 3 tarjetas** (los asesores decían "mucho texto"):
  - Cobertura · Zona · Score, con frases cortas elegidas por el owner. Una línea de aviso y **Ver detalle**,
    con el error exacto y "Copiar para WhatsApp".
  - Un error del score ya no tumba todo el resultado.
  - El panel del Mapa usa los mismos textos en vertical.
- **Regla de negocio nueva**: el **fraude solo informa** (dentro o cerca); deciden el score, la cobertura y
  WinForce. Los **códigos bloqueados siguen bloqueando**.
  - Actualizado en `core/geo.py`, README (es/en), AGENTS, arquitectura y anotaciones.
- Tests: 683 → 703, `ruff` limpio. Commit `c1e2e05` y `.exe` regenerado, sin Release.
- **Tarjetas también en la página Mapa** (la captura del owner mostraba ahí el texto plano de antes):
  - Cobertura y Zona lado a lado, con títulos a 10 pt que caben en ~125 px; Score debajo, con el botón.
  - Línea de aviso y "Ver detalle" también ahí. Un error del score ya no abre un diálogo rojo.
  - El contenido va centrado de arriba abajo en cada tarjeta (pedido del owner).
  - Widget compartido en `gui/tarjetas.py`. Comprobado con capturas de 5 casos y de la página principal.

## Pendiente al iniciar

- **Martes 2026-11-03, primero**: "Reiniciar servicio" en la consola owner y comprobar `/health` (`session_alive: true`).
- Prueba de la consulta que espera al autologin: sin abrir `/health` ni la consola antes, entrar con la cuenta del proxy en otra PC y consultar una cobertura desde un agente. Esperado: cobertura sin 502/503 y `muerta` → `renovada` (autologin) → `consulta_reintentada` con `deteccion / autologin / consulta / total` en `logs/sesion_eventos.jsonl`. Si sale 502, `winsw.err.log` trae `502 en /api/...`.
- Con 2-3 muertes medidas, decidir recortes (confirmación de 3 s → 1 s, no revalidar la misma cookie).
- Vigilar la concurrencia el primer día laboral (hasta 40 consultas a la vez, sesión `requests` compartida) y el autologin (pausa por "muertes rápidas" = alguien más usa la cuenta).
- Regenerar `JSConnect-Win-Owner.exe` con `build-owner.ps1` (consola cerrada). Push del commit `0a44e2d` cuando el owner lo pida; sin Release.
- Después: migrar a la mini PC (PlanesAprobados → "Migración al host definitivo") y Tailscale; alto de la consola owner (AGENTS 7g); cobertura observada (7e).
- Reactivar los agentes con la huella estable (**NO borrar `huellas_legacy()`**); agente W10 contra owner W11; archivo del pendrive con URL + token; firma de código.
- Diferido: Etapa C.12, `actualizar_score_cliente` / `newsearch.php`, backlog v1.1.
- **Release `v2026.11.03` publicado** (tag en `1b98a80`) con los dos `.exe`:
  - agente, SHA-256 `BEAE0634…6B00E`;
  - consola owner regenerada, SHA-256 `19B256D7…BB893`.
  - El actualizador lee bien los dos checksums de las notas (`extraer_checksum`).
