# ResumenDelDia.md — Historial del día

Fecha: 2026-09-30

## Rotación del resumen anterior

El detalle íntegro del 2026-09-29 quedó en `resumenes/2026-09-29.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- Rotación de resúmenes al abrir el día.
- **Ventana del agente — logo, limpiar campos y tabla de scores**:
  - Logo `assets/LogoJSConnectSolutions.png` arriba a la derecha
    (`_agregar_logo`, sin logo si el archivo falta); `build.ps1` lo embebe con
    `--add-data`.
  - Botón ✕ en coordenadas y documento (`_limpiar_coordenadas`/`_limpiar_documento`).
  - `clasificar_score()` (NUEVO, reemplaza `_bootstyle_riesgo`): rango de 100
    puntos, riesgo, categoría y color según la tabla de la empresa
    (0-200 MUY ALTO/rojo · 201-400 ALTO/naranja · 401-600 REGULAR/dorado ·
    601-800 BAJO/verde · 801-999 MUY BAJO/azul oscuro). El `NivelRiesgo` de
    WinForce ya no se muestra (no coincidía con la tabla).
  - Fila `Rango: SCORE: x - y` + botón Copiar (copia solo `SCORE: x - y`); en
    0-200 añade "NO SE LE PUEDE VENDER". Leyenda de las 5 categorías con la del
    cliente resaltada.
  - Verificado con una `App()` real (150, 250, 423, 650, 862, sin puntaje) y el
    portapapeles. **262 tests, ruff limpio.** Sin Release todavía.
- **Ajustes tras revisar el .exe**: logo correcto
  (`assets/LogoJSConnectSolutionsLogo.png`, solo el infinito; se recorta el
  margen blanco con `_recortar_margen`) ubicado a la derecha de los campos
  (filas 0-3, `rowspan=4`) en vez de una fila propia; ventana de 700 a 440 px de
  alto; `Tipo` pasa junto al botón de limpiar del documento. Botones de limpiar
  con icono de borrador (`assets/icons/borrador.png`, dibujado con Pillow en
  `tools/generar_iconos.py::generar_icono_borrador`; respaldo `✕` si falta).
  `build.ps1` embebe ambos. **264 tests, ruff limpio.**

- **Cierre**: documentación sincronizada (README es/en, TestingLog, AGENTS.md
  tarea 42 + cierre), commit, push y Release `v2026.09.30`.

## Pendiente al iniciar hoy

- Monitorear la primera semana de producción (sesión del proxy, RUC/CE) —
  observación, no una tarea con pasos.
- Escribir el runbook de la Etapa E (`docs/proxy-deploy.md`) en cuanto el
  usuario comparta el detalle operativo real de la instalación.
- Fase 5 (barrido final de documentación): última tarea del plan grande,
  después de la Etapa E.
- Diferido a otra sesión (a pedido del usuario): la duda de `Escalabilidad.md`,
  la decisión de `actualizar_score_cliente`/`newsearch.php`, y el backlog v1.1.
