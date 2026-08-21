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

### 2026-08-21 — Sesión (arnés gráfico, tarea 2)
- [Tarea 2] El usuario intentó `tools/probar_core.py` y le confundió `getpass`
  (contraseña invisible = normal). → Se creó versión gráfica.
- [Avance TDD] Nueva lógica `validator_app/gui/prueba_core.py` (`ejecutar_prueba`)
  + `tools/probar_core_gui.py` (Tkinter: contraseña oculta, validación en hilo).
  6 tests nuevos (`tests/test_prueba_core.py`, mocks sin HTTP real). Total: 31
  tests, ruff limpio.
- [Prueba real #1] Falló con `[ERROR LOGIN] la sesion no quedo activa` (creds
  pegadas del portapapeles; en el navegador SÍ entran).
- [Fix TDD] `.strip()` de las entradas (espacios/saltos invisibles del
  portapapeles) + diagnóstico detallado en errores de login (`api._diagnostico`:
  status, content-type y body de 80 chars por endpoint, sin datos sensibles).
  4 tests nuevos. Total: 35 tests, ruff limpio.
- [Siguiente] Re-ejecutar `python tools/probar_core_gui.py`; si falla de nuevo,
  el mensaje mostrará qué respondió cada endpoint para diagnosticar.

### 2026-08-21 — Sesión (decisión B consolidada + infraestructura)
- [Prueba real #2] Re-ejecutada la GUI con diagnóstico: login responde
  `{"response":"success","comment":"Redireccionar"}` (en JSON con content-type
  text/html) pero `operador.php` devuelve una PÁGINA HTML completa → no hay sesión.
  Causa raíz: **login federado**. El flujo real del navegador es:
  `appwinforce.win.pe/login` (creds) -> "Redireccionar" -> `accesoventas.win.pe`
  (elegir Microsoft/Google) -> login Microsoft (MISMAS creds) -> recién ahí se
  establece la sesión. `requests` NO puede completar el SSO interactivo.
  → El proxy necesitará login vía navegador (Playwright) para establecer sesión,
  y luego replicar las llamadas API con esa cookie.
- [Dato del negocio] Los agentes NO tendrán credenciales Win en el día a día →
  **opción A descartada definitivamente; B (proxy local) ES la arquitectura**.
- [Dato del negocio] Infraestructura: hay UNA PC de oficina siempre encendida
  SOLO en jornada laboral → host ideal del proxy. La PC gamer se descarta como
  host permanente (costo eléctrico > ahorro); queda como BACKUP FRÍO (encender
  solo si la fija falla). Fuera de jornada el proxy está apagado = agentes no
  operan (aceptable).
- [Flujo reorganizado] Proxy en PC fija mantiene 1 sesión Win viva (re-login),
  expone `/cobertura` y `/score` por LAN con token simple; app agente sin login,
  apunta al proxy. Concurrencia: ya no es N IPs sino 1 IP → riesgo nulo; la prueba
  de concurrencia deja de ser crítica para decidir A/B.
- [Docs] Actualizados AGENTS.md (historial + tareas pendientes) y
  PlanesAprobados.md (decisión consolidada + pasos nuevos).

## Pendiente al volver
1. **Proxy local** (nuevo Paso 4): FastAPI/http.server en la PC fija que reuse
   `validator_app.core.api`, mantenga sesión viva (auto-relogin) y exponga
   `/cobertura` y `/score` con token LAN. Incluye resolver el **login vía
   navegador** (Playwright) para el SSO federado de accesoventas.win.pe.
2. **App agente**: quitar login de `main_window.py`; llamar al proxy local.
3. Configurar auto-start del proxy en la PC fija (jornada laboral).
4. Fase 2 (activación visual) y Captura de API (`captura.json`) siguen en cola.
5. Ver PlanesAprobados.md y AGENTS.md para el resto.