# ResumenDelDia.md — Historial del día

Fecha: (se fija al abrir la proxima sesion)

## Rotación del resumen anterior

El detalle íntegro del 2026-10-09 quedó en `resumenes/2026-10-09.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- (nada todavía)

## Pendiente al iniciar

- **Mapa de cobertura** (subido a `main` el 2026-10-09, **sin Release**): probarlo con asesores,
  **recompilar desde `main`** (el `.exe` de `dist\` es anterior a sacar la URL de `config.py`) y
  publicar con `publish-release.ps1`. Poner `capas_kml_url` en el `config.yaml` del proxy (opcional).
- **Zona F**: es copia de Fraude; el usuario se la enseñará a su jefe para saber qué significa.
- Detección automática de "no cruzar avenida de doble vía" (hoy es visual) y dibujar los huecos de
  los polígonos (243; las reglas sí los respetan).
- **Reactivar los agentes** con la huella nueva (hoy 25: 18 + 7; a futuro 41). Funcionan en
  "transición". **NO borrar `huellas_legacy()`** salvo petición expresa (`AGENTS.md` → "Versionado").
- **Reemplazar a mano el `.exe` del owner** instalado (`v2026.10.07`) por el de `v2026.10.07.1`.
- **Probar un agente W10 real contra el owner W11** y revisar `Get-NetConnectionProfile` / la regla
  `JSWinProxy API`.
- Poner `W11-JSConnect-Win-Coverage` en privado solo cuando sus `.exe` ya se hayan actualizado.
- Observar por qué la sesión de WinForce muere ~10 min tras renovar (`docs/rotacion-credenciales.md`).
- Archivo del pendrive con URL + token para el agente (idea acordada; su propio Release).
- Firma de código de los `.exe` (Smart App Control en Windows 11).
- Monitorear la primera semana de producción (sesión del proxy, RUC/CE) y probar el pendrive en una
  PC owner limpia.
- Diferido: Etapa C.12 (modo standalone), duda de `Escalabilidad.md`, `actualizar_score_cliente` /
  `newsearch.php`, resto del backlog v1.1.
