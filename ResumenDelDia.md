# ResumenDelDia.md — Historial del día

Fecha: 2026-09-04

## Qué se hizo hoy

### 2026-09-04 — Sesión — Retomar Fase 0 (medir vida de la PHPSESSID)

#### Fix de entorno
- `tools/medir_sesion.py` fallaba con `ModuleNotFoundError: No module named
  'validator_app'` al correrlo con `C:\Python314\python.exe` directo. Causa: el
  paquete no estaba instalado en modo editable en ese intérprete (`pip show
  validator-app` no lo encontraba en ningún Python de la máquina). Resuelto con
  `C:\Python314\python.exe -m pip install -e .`; verificado corriendo
  `tools/medir_sesion.py --help` sin `PYTHONPATH=.`.

#### Primera medición
- Corrida con parámetros por defecto (`--espera-inicial 30 --incremento 15
  --max 600`): la sesión seguía **viva a los 525s** de inactividad acumulada,
  se alcanzó el tope `--max` sin encontrar el punto real de expiración.
- Hipótesis planteada por el usuario: `session.gc_maxlifetime` por defecto de
  PHP son 1440s (24 min) — la primera corrida no llegó a cruzar ese umbral.
  Se prepara una segunda corrida con `--max 3600` (1 hora) para confirmarlo.

#### Hallazgo de autenticación (durante la preparación de la 2ª corrida)
- Al recargar la app con F12 abierto se observó: la PHPSESSID cambia y
  redirige al login (sesión anterior ya no reconocida) → login con
  correo/contraseña salta la pantalla interactiva de 2FA (SSO silencioso de
  Azure AD, ya había sesión de Microsoft activa) → la PHPSESSID final
  resultó ser la **misma** cookie anónima que apareció justo tras la recarga.
  Conclusión: `acceso.php` no regenera el PHPSESSID al loguear (reusa la
  cookie anónima ya presente en vez de emitir una nueva). Documentado en
  `anotaciones.md` (sección "Reuse de PHPSESSID en login + SSO silencioso").

- Durante la conversación sobre el hallazgo de SSO, la sesión que se iba a usar
  para la corrida `--max 3600` volvió a morir por el tiempo transcurrido
  (síntoma visible: `DataTables warning ... Invalid JSON response` en
  `table_seguimiento`, mismo patrón que el bug BOM ya corregido en
  `coordenada.php`). El usuario se re-logueó y relanzó la medición.

#### Fase 0 completada — resultado de la medición
- `medir_sesion.log` quedó con 4 corridas: dos con `--max` por defecto (600s)
  llegaron VIVA hasta 525s sin morir; una corrida corta murió entre 135s y 210s
  (anómala, coincide con la recarga que reemplazó la PHPSESSID — no es idle-timeout
  real); la corrida `--max 3600` (limpia) dio el dato bueno: **VIVA a 1155s,
  MUERTA a 1350s** (19.25–22.5 min de inactividad real).
- Conclusión: el idle-timeout real está algo por debajo del `gc_maxlifetime`
  default de PHP (1440s/24min) pero en el mismo orden de magnitud. El
  `keepalive_interval_seconds` de ~90s ya planeado para la Fase 2 da margen
  amplio (12-15x), no requiere ajuste.
- Detalle completo registrado en `PlanesAprobados.md` (Fase 0) y
  `anotaciones.md` (síntomas de sesión muerta).

#### Decisión de keepalive revisada + resultado del smoke-test
- El usuario, viendo que 1155s queda muy cerca de un límite hipotético de
  1200s (20 min), pidió fijar el intervalo objetivo en 19 min (1140s) en vez
  de los ~90s originalmente sugeridos — pendiente de confirmar que un ping
  realmente resetea el reloj de expiración antes de darlo por bueno (ver
  siguiente punto).
- **Hallazgo al revisar el patrón del log de Fase 0**: en la corrida limpia
  (`--max 3600`), la sesión murió a tiempo fijo desde el login (~1200-1350s)
  a pesar de pings exitosos en el camino — consistente con que el ping de
  solo lectura (`operador.php?accion=get_operador`) no re-escribe la sesión
  del lado del servidor (PHP `session.lazy_write`) y por eso no resetea el
  reloj. Si es así, ningún intervalo de keepalive basado en ese endpoint
  funcionaría.
- Creado `tools/medir_keepalive.py`: smoke-test con pings de **interacción
  real** (`validar_cobertura`, no solo lectura) cada `--intervalo` segundos
  (default 5 min) durante `--duracion` segundos (default 45 min), para
  confirmar si eso sí evita la muerte de la sesión. Detalle técnico
  encontrado al construirlo: `ValidatorAPI` tiene un guard interno de 120s de
  inactividad (`core/api.py:197`) que da un falso "sesión expirada" del lado
  del cliente si se reutiliza la misma instancia entre pings separados por
  más de 120s — el script usa una instancia nueva en cada ping para evitarlo.
- **Resultado**: sobrevivió pings exitosos hasta los 2100s (35 min) — muy por
  encima del idle-timeout de Fase 0 (~20 min), confirmando que el ping real
  SÍ resetea ese reloj — pero murió igual a los 2400s (40 min) pese a seguir
  pingueando. **Conclusión de trabajo**: hay dos límites de sesión
  independientes — idle-timeout (~20 min, evitable con actividad) y un tope
  absoluto de sesión (~40 min desde el login, NO evitable con actividad,
  solo con re-login real). Documentado en detalle en `anotaciones.md` ("Dos
  límites de sesión: idle-timeout + tope absoluto").
- **Siguiente paso decidido**: construir un test v2 con intervalos variables
  entre pings (no cada 5 min exactos, por si el patrón regular dispara
  detección de bots) intentando sostener la sesión más allá de los 40 min.
  Si eso también falla, un test v3 rotando coordenadas distintas por si hay
  detección anti-bot más sofisticada.

#### Fase 1 (C) completada — limpiar login muerto del proxy
- `core/api.py`: nuevo helper compartido `validar_cookie_sesion()` (reutiliza
  `_verificar_sesion_activa`).
- `rotate_creds.py`: `validate_session_cookie()` reescrito para delegar en el
  helper (elimina duplicación).
- `server.py`: `AdminLoginRequest` → `AdminCookieRequest` (`{php_sessid}`);
  `/admin/login` y `/admin/rotar` actualizados (ambos intercambiables);
  `_relogin_silent()` reescrito para recargar+revalidar la cookie del keyring
  en vez del login programático inviable (código muerto en dos capas: ni la
  clave de keyring que leía se escribía nunca, ni el login hubiera funcionado
  por el 2FA); `session_alive` agregado a `/health` y `/admin/status`.
- `docs/rotacion-credenciales.md` actualizado (contrato `{php_sessid}`).
- 3 tests nuevos en `tests/test_api.py` para `validar_cookie_sesion()`
  (cookie válida, inválida, respuesta HTML). **40 tests pasando, ruff limpio.**
- Detalle completo en `PlanesAprobados.md` (Fase 1).

#### Corrección: el "tope de 40 min" no se sostuvo — indicios de anti-bot
- Corrida del test v2 (`tools/medir_keepalive.py`, pings reales de
  `validar_cobertura` con intervalos variables 180-420s, misma coordenada de
  siempre): la sesión murió a los **1100s (18.3 min)** — **antes** que el
  idle-timeout pasivo de Fase 0 (1155-1350s, sin ningún ping) y muchísimo
  antes que v1 (2400s). Error real: HTTP 200 con HTML de login (mismo patrón
  de "sesión muerta" de siempre, no el 404 raro de v1.
- **Esto contradice el modelo simple de "idle-timeout + tope absoluto"**
  documentado antes: si el ping real solo ayuda o es neutro, nunca debería
  morir antes que la prueba pasiva. Murió más rápido haciendo *más*
  actividad — señal fuerte de que algo externo (no un timeout mecánico) está
  interviniendo.
- **Dato adicional**: dos intentos previos de arrancar v2 fallaron en el
  primer ping (HTML en vez de JSON) pese a "login fresco" — se resolvió con
  pestaña nueva + DevTools reabierto (ver `anotaciones.md`, nota práctica),
  pero no se puede descartar del todo que fuera la misma sesión "contaminada"
  (recordar: `acceso.php` no regenera el PHPSESSID al loguear).
- **Hipótesis de trabajo actual**: en ~2 horas se hicieron **4 sesiones
  automatizadas seguidas**, todas contra la **misma coordenada exacta**
  (`-12.073802720229136, -77.03793556536581`, repetida decenas de veces).
  Query idéntico repetido + actividad automatizada acumulada reciente es una
  firma de bot plausible — más que la regularidad del intervalo (que ya se
  corrigió en v2 y no bastó).
- **Decisión**: pausar las pruebas automatizadas por hoy (no seguir
  encadenando sesiones) para no alimentar una posible detección acumulativa.
  `tools/medir_keepalive.py` ya soporta `--coords-lista` (rotar entre varias
  coordenadas reales) para la próxima corrida — el usuario dará la lista de
  coordenadas en la siguiente sesión de trabajo.
- Corregido en `anotaciones.md`: la conclusión anterior de "tope absoluto
  confirmado a los 40 min" queda como hipótesis sin confirmar, no como hecho
  (el error de v1 fue un 404 genérico, dato insuficiente por sí solo).

#### Pendiente
- Correr el test con `--coords-lista` (coordenadas rotativas) una vez el
  usuario dé la lista — dejar pasar tiempo antes de la próxima corrida
  automatizada.
- Registrar la decisión final de `keepalive_interval_seconds` en
  `PlanesAprobados.md` (Fase 0) una vez cerrada la investigación.
- Fase 2 (B) — **bloqueada** hasta cerrar la investigación de arriba (qué
  endpoint usar, si hace falta rotar coordenadas, qué intervalo es seguro).
- Fase 3 (D) — diálogo de cookie en la GUI.
- Fase 4 — tests. Fase 5 — documentación.
