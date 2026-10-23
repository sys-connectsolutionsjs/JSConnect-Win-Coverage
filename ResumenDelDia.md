# ResumenDelDia.md — Historial del día

Fecha: 2026-10-21

## Rotación del resumen anterior

El detalle íntegro del 2026-10-13 quedó en `resumenes/2026-10-13.md` y su entrada
condensada en `HistorialResumenes.md`. La sesión abierta el 2026-10-14 no tuvo trabajo (sin commits),
por eso no tiene snapshot propio.

## Qué se hizo hoy

- Confirmado que el 2026-10-14 no hubo trabajo (sin commits); este resumen pasó a la fecha de hoy.
- Revertido `validator_app/version.py` a `"unknown"` (lo había dejado el build de v2026.10.13).
- **Obsidian**: `.obsidian/` en `.gitignore`; 373 referencias entre `.md` pasaron a enlaces
  markdown relativos (se ven en GitHub y en el grafo); el mapa de conocimiento de `AGENTS.md`
  enlaza todos los documentos y es el nodo central; convención de enlaces escrita en `AGENTS.md`.
  Los snapshots de `resumenes/` no se tocaron. Test nuevo `tests/test_enlaces_docs.py` (3).
- **Log de sesiones** (`logs/sesion_eventos.jsonl`, 2026-09-29 → 2026-10-21): 49 muertes, todas de
  lunes a viernes entre las 9 y las 17 h (1 sola a las 13 h); sesiones que sobreviven la noche y dos
  que sobrevivieron el fin de semana (~66-69 h). No hay tope de 9.5 h: la sesión muere por otro login
  con la misma cuenta. La jefatura aprobó una **cuenta dedicada**.
- **Corrección**: el login de WinForce no es 2FA, es solo el SSO de Microsoft (Entra ID). Falta
  corregirlo en la documentación.
- **My Maps propio** de Preferente 2 / Códigos bloqueados: el mapa de origen ("PARAMETROS VENTAS",
  138 polígonos) se separó en dos KML (`datos_capas/`, gitignored) y el usuario los importó en el mapa
  de la empresa. Verificado: su KML público trae las mismas 2 capas y polígonos idénticos, y
  `proxy/capas.py` lo interpreta. Falta poner su URL en `capas_kml_url` del `config.yaml` del proxy.
- **Escaneo masivo de Lima** para capas: no se implementa (riesgo de perder la cuenta dedicada; el
  permiso es de WinForce). En su lugar: cobertura observada a partir de las consultas reales.
- **(2026-10-23) El mapa no cargaba**: OpenStreetMap bloquea el User-Agent fijo `TkinterMapView`
  de `tkintermapview` (responde la imagen "Access blocked"). Arreglo: `gui/tiles.py` hace que las
  tiles salgan con el User-Agent del proyecto; test `tests/test_tiles_mapa.py` (3), 500 tests en
  verde. **Necesita un Release nuevo** para llegar a los agentes.

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
