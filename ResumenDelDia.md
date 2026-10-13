# ResumenDelDia.md — Historial del día

Fecha: 2026-10-13

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

## Mapa limitado a Perú (2026-10-13)
- `gui/limites_mapa.py` (lógica pura: `PERU_BBOX`, `ZOOM_MIN_PERU = 5`, `ajuste_vista`) y subclase
  `_MapaPeru` en `map_page.py`: el mapa ya no deja alejar hasta ver el mundo ni arrastrar fuera de
  Perú (tiles del resto del mundo no se descargan). 6 tests nuevos en `tests/test_limites_mapa.py`
  (427 en total), `ruff` limpio; verificado con un Tk real: zoom piso 5 y la vista no sale de Perú.
- La validación de zona no cambia (la decide `geo.decidir_venta`, no el mapa). Sin Release aún.

## Dirección, ficha copiable y Zona F retirada (2026-10-13)
- **Dirección por coordenadas**: Geofinder (API de Equifax que usa WinForce; `GET .../geoapi/nyg/pe/
  coordinates/v1`) vía el proxy (`proxy/geofinder.py`, `GET /api/direccion`, credencial `geofinder_basic`
  solo en `config.yaml`) con respaldo OpenStreetMap y aviso de "aproximada, el servicio debe reactivarse"
  (`core/direccion.py`). Se pide en paralelo con la cobertura (no gasta score).
- **Datos del documento**: `core/api.py::_extraer_score` devuelve `persona` (módulos 602 y 877);
  `ScoreResponse`/`ScoreResult` con `persona` opcional.
- **Ficha copiable** (`gui/ficha.py`) en Cobertura/Score y Mapa: dato por dato y "Copiar todo" en el
  orden pedido; el score del Mapa ya se copia. Panel lateral del Mapa desplazable.
- **Zona F retirada** (copia de Fraude: 27 polígonos idénticos, el 28.º de Fraude no estaba en F).
- Tests 421 → 474, `ruff` limpio. `captura.json` fue reemplazado por una captura nueva (38 registros,
  sin score; confirma el formato de Geofinder; `Authorization` va oculto).
- **Seguimiento (misma sesión)**: la dirección salía "equivocada" porque el proxy de la oficina
  (la PC de oficina) es anterior y respondía 404; el agente usó OpenStreetMap (otra base de datos).
  Se ajustó Geofinder al flujo del navegador, se añadió banner rojo con el motivo, `/health.geofinder`
  y `tools/empaquetar_actualizacion_proxy.ps1` (paquete de pendrive sin secretos). 487 tests.
- **Formato**: `DIRECCIÓN DETALLADA` sale como Geofinder: `AVENIDA PERU 4298 BOCANEGRA SECTOR 3 (CALLAO, CALLAO, CALLAO)` (con el paréntesis); departamento/provincia/distrito siguen en líneas aparte.
- **Falta**: que el usuario ponga `geofinder_basic` en el proxy y actualice el proxy de la PC owner;
  Release. Score real probado (DNI 10412031): el reporte no trae lugar de nacimiento → la ficha
  usa "NACIONALIDAD Y FECHA DE NACIMIENTO"; los nombres salen "nombres primero" (PrimerNombre +
  SegundoNombre + apellidos).

