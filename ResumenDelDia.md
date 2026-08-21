# ResumenDelDia.md — Historial del día

Fecha: 2026-08-21

Nota: el resumen de cierre que se presenta al usuario es CONCISO (puntos clave),
sin repetir todo lo documentado aquí.
Rotación: al iniciar sesión de un día nuevo, lo anterior se MUEVE a
`HistorialResumenes.md`; este archivo solo guarda la sesión del día en curso.

## Qué se hizo hoy

### 2026-08-21 — Sesión (análisis Fase 1.5)
- [Dato del negocio] Aclarada la arquitectura de la app anterior de los terceros:
  hosteaban TODO en su servidor (PC = solo interfaz vía link); cobraban extra por
  PC; Win siempre vio UNA IP con UNA cuenta. Si no prendían su servidor, la app
  moría aunque se iniciara sesión.
- [Conclusión] No era concurrencia real: era el modelo proxy (opción B) alquilado.
  La lentitud venía de su infraestructura. B propia replica el modelo probado sin
  terceros ni costos -> refuerza la recomendación B.
- [Docs] Actualizados AGENTS.md (historial Fase 1.5) y PlanesAprobados.md
  (restricciones del negocio + refuerzo de la decisión).
- [Docs] Creado `HistorialResumenes.md` (archivo histórico): los resúmenes de
  días pasados se mueven allí para mantener este archivo ligero. Movidas las
  sesiones del 2026-08-19 (mañana y tarde).
- La prueba de concurrencia (Paso 2) sigue valiendo para saber si la opción A
  (app directa, N IPs) también es viable.

## Pendiente al volver
- **EJECUTAR la prueba de concurrencia** (Fase 1.5, Paso 2): en 4-5 máquinas a la vez
  con `python tools/probar_concurrencia.py --ciclos 5 --log concurrencia.log`.
  Observar si Win bloquea/avisa/fuerza cierres; registrar resultados en AGENTS.md y
  decidir arquitectura A/B (Paso 3). La herramienta YA está creada (Paso 1 hecho).
  Coordenadas de prueba: `-12.087718994493725, -76.98571219979543` (San Borja,
  cobertura SI) · DNI de prueba: `75020496`. El log TSV es fecha/máquina/ciclo/
  OK|FALLO/detalle. NO subir el log a GitHub (borrarlo al terminar).
- Luego implementar lo elegido (Paso 4) y, posteriormente, la **Fase 2** (gestión
  visual de activación: `GeneradorActividad.exe`).
- Revisar el estado de la herramienta **Captura de API** (traer `captura.json` desde
  la otra PC; ver sus propios MD).
- Ver PlanesAprobados.md y AGENTS.md para el resto de pendientes.