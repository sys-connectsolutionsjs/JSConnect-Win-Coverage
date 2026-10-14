# ResumenDelDia.md — Historial del día

Fecha: (se fija al abrir la proxima sesion)

## Rotación del resumen anterior

El detalle íntegro del 2026-10-13 quedó en `resumenes/2026-10-13.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- (nada todavía)

## Pendiente al iniciar

- **Release `v2026.10.13` publicado**: ver cómo reciben la actualización los agentes ("Buscar
  actualizaciones") y probar la ficha y el mapa con asesores reales.
- **Proxy de la oficina**: recopiar `proxy-update\` (el `core/api.py` de allí es anterior al fix de
  nombres; funciona igual con el agente nuevo) y reiniciar `JSWinProxy`.
- **Reemplazar a mano el `.exe` del owner** instalado (`v2026.10.07`) por el de `v2026.10.13` (no trae
  el actualizador).
- `capas_kml_url` en el `config.yaml` del proxy (opcional; hoy `/api/capas` da 503 y los agentes usan
  las capas embebidas).
- Detección automática de "no cruzar avenida de doble vía" (vías OSM) y dibujar los huecos de los
  polígonos (243; las reglas sí los respetan).
- **Reactivar los agentes** con la huella estable (25 hoy: 18 + 7; 41 previstos). **NO borrar
  `huellas_legacy()`** salvo petición expresa (`AGENTS.md` → "Versionado").
- Probar un agente W10 real contra el owner W11 y revisar `Get-NetConnectionProfile` / la regla
  `JSWinProxy API`.
- Poner `W11-JSConnect-Win-Coverage` en privado solo cuando sus `.exe` ya se hayan actualizado.
- Observar por qué la sesión de WinForce muere ~10 min tras renovar (`docs/rotacion-credenciales.md`).
- Archivo del pendrive con URL + token para el agente (idea acordada; su propio Release).
- Firma de código de los `.exe` (Smart App Control en Windows 11).
- Monitorear la primera semana de producción (sesión del proxy, RUC/CE) y probar el pendrive en una
  PC owner limpia.
- Diferido: Etapa C.12 (modo standalone), `actualizar_score_cliente` / `newsearch.php`, resto del
  backlog v1.1.
