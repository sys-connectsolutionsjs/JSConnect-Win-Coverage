# ResumenDelDia.md — Historial del día

Fecha: 2026-09-08

## Qué se hizo hoy

### 2026-09-08 — Sesión — Actualizar el repo, cerrar la investigación de keepalive y rotar resúmenes

#### Inicio
- Repo local **6 commits por detrás** de `origin/main` (`1dcecc6` → `3c1baa5`).
  `git pull --ff-only` limpio, fast-forward, sin conflictos. Los 6 commits
  (`5506ed4`, `44d1132`, `3925dbf`, `26e7567`, `82f9a4c`, `3c1baa5`) son de la
  sesión 2026-09-05, hecha en la otra máquina y ya pusheada.
- Revisado el diff del proxy (`5506ed4`, único commit que toca
  `validator_app/proxy/server.py`): caché de `session_alive` 30s atada a la
  cookie + logging de cada fallo de sesión con remedio + `logging.basicConfig`
  en `__main__`. Sin cambio de contrato ni rutas nuevas.

#### Desenlace de la corrida keepalive v3 — investigación CERRADA
Llegó el reporte final del test (`tools/medir_keepalive.py` v3, corrida iniciada
2026-09-05 21:08, ping fijo cada 900s, 49 coords rotativas):
- **37 pings consecutivos VIVA**; última confirmación VIVA a los **33 370s de
  edad de sesión (556.2 min ≈ 9 h 16 m)**.
- Murió **limpia** a los **34 270s (571.2 min ≈ 9 h 31 m)**: categoría del ping
  `SESION_MUERTA`, patrón HTTP 200 + `text/html` (HTML de login), **confirmado de
  forma independiente** por `core.api.validar_cookie_sesion()`.

Lecturas:
- **Idle-timeout descartado como causa** de esta muerte — ping real cada 900s y
  última confirmación VIVA 900s antes de morir. El keepalive de 15 min resuelve
  el idle-timeout de Fase 0 (~1200s) con holgura enorme.
- **Anti-bot acumulativo descartado** — 37 pings con coords variadas en 9 h, 0 fallos.
- **"Tope absoluto a 40 min" descartado** — era el 404 ambiguo de v1.
- **Sí existe un tope absoluto de sesión ≈ 9.5 h desde el login**, independiente
  de la actividad. Queda por encima de la jornada de 8 h con ~1.5 h de margen →
  reinyectar la cookie al inicio del turno, no a media mañana.

Un dato limpio basta aquí (a diferencia del 404 ambiguo de v1): patrón de muerte
inequívoco, idle-timeout excluido por los pings activos, confirmación
independiente, anti-bot excluido. Una 2ª corrida solo afinaría el número exacto
y no cambia el diseño de la Fase 2.

#### Rotación de resúmenes
- La sesión **2026-09-05** se movió a `HistorialResumenes.md` (condensada, con el
  desenlace v3 incluido para que quede autocontenida). `ResumenDelDia.md`
  reabierto con la fecha de hoy.
- `resumenes/2026-09-05.md` (snapshot completo) **no se creó** — igual que
  `2026-09-04.md`; se deja como deuda menor.

#### Sincronización de documentación — HECHO
- **Investigación cerrada sincronizada** en los tres docs:
  - `PlanesAprobados.md`: addendum (ahora 2026-09-08), Fase 0 (act. 2026-09-08
    con el desenlace), Fase 2 → "[LISTA PARA IMPLEMENTAR]" + aviso al owner por el
    tope ≈ 9.5 h, "cola activa" (bullet de la corrida marcado CERRADO).
  - `anotaciones.md` (`## M`): "Dos límites de sesión" (recuadro de estado +
    "Implicación de diseño": el tope ≈ 9.5 h ya es un hecho medido) y "Revisión
    del método" (resultado final en vez de "en curso toda la noche").
  - `AGENTS.md`: ítems 15 ("[CERRADA]") y 16 ("[LISTA PARA IMPLEMENTAR]"), tree
    (`.claude/`, `HistorialResumenes.md`), nota del hook en la regla de
    auto-actualización, y `### Cierre de la sesión 2026-09-08`.
- **Hook de auto-actualización de docs creado**: `.claude/settings.json` +
  `.claude/hooks/historial_sync.py` (hook `PostToolUse`). Vigila
  `HistorialResumenes.md`: al agregar entradas recuerda sincronizar
  `anotaciones.md` / `PlanesAprobados.md` / `AGENTS.md`; cada 3 entradas nuevas,
  también `README.md`. Estado local en `historial_sync_state.local.json`
  (gitignored vía `.claude/hooks/*.local.json`).

#### Deuda técnica cerrada (antes de la Fase 2)
- **`httpx` → `requirements.txt`**: la GUI importa `ProxyClient`
  (`proxy/client.py` → `import httpx`) siempre, y `proxy/__init__.py` también;
  `pip install -r requirements.txt` + `python main.py` fallaba con
  `ModuleNotFoundError: httpx`. Quitado el duplicado y los comentarios falsos de
  `requirements-proxy.txt`.
- **`requires-python` → `>=3.12`**: piso real (tests en 3.12 desde 2026-08-27,
  cero sintaxis 3.13/3.14 en el código). `ruff target-version = "py312"`.
  Requisito de versión unificado en `3.12+`: `README.md` (ES+EN),
  `docs/proxy-deploy.md`, `docs/proxy-config.md`, `README_PROXY.md`,
  `install_service.bat`, `AGENTS.md`, `anotaciones.md`.
- **Snapshots faltantes creados**: `resumenes/2026-09-04.md` y
  `resumenes/2026-09-05.md`, recuperados verbatim de git
  (`44d1132~1` y `3c1baa5`).
- Sin cambios de código; **49 tests, ruff limpio**. Nota en `TestingLog.md`.

#### Fase 2A — Keepalive del proxy ("latido perezoso") — HECHO
- **`_keepalive_loop`** (`asyncio` en el `lifespan` de `server.py`) +
  **`ProxyValidatorAPI._keepalive_tick`** (síncrono, corre en `asyncio.to_thread`).
  Config `keepalive_enabled` / `keepalive_interval_seconds` (**900**) en `config.py`
  (+ `config.yaml.example`, `install_service.bat`).
- **Latido perezoso**: el tick no pinga si `now - _last_activity < intervalo`
  (los agentes ya mantienen la sesión viva); solo cubre los huecos. Ping =
  `validar_cobertura` con coord pública rotada al azar (`_KEEPALIVE_COORDS`, 12
  puntos embebidos; las 49 siguen en `tools/coords_prueba.txt`).
- **Aviso al owner**: ping fallido → se confirma con `validar_cookie_sesion()`.
  Endpoint caído → `TRANSITORIO` (warning). Sesión muerta → `log.error` (una vez)
  con el remedio + `session_dead_since` poblado en `/admin/status` (nuevo bloque
  `keepalive`). **No reintenta en silencio.**
- **Prerrequisito arreglado**: `_get_client()` pone `_session_max_idle = 10**9`
  en el cliente-core — su guard idle de 120 s lanzaba `SessionError` en cada hueco
  > 120 s (el proxy ya gestiona la frescura por su cuenta). Bug latente que el
  keepalive habría vuelto constante.
- **`tests/test_proxy.py` NUEVO** (12 tests: latido perezoso, clasificación de
  fallos, limpieza al renovar, regresión del guard, loop async). **61 tests, ruff
  limpio.**
- **Validado end-to-end contra WinForce real**: al arrancar en esta PC, el
  keepalive detectó la `PHPSESSID` muerta del keyring y disparó el `ERROR` de
  aviso al owner — exactamente lo diseñado.

#### Pendiente
- **Fase 2.5 — login asistido**: recolectar la `PHPSESSID` automáticamente cuando
  el owner se loguea (no sabe qué es F12). Recomendado: `rotate_creds` v2 con
  Playwright (`context.cookies()` evita el HttpOnly) + acceso directo "Renovar
  sesión" en el escritorio de la PC del proxy; `--manual` (copiar/pegar) como
  fallback. Perfil de navegador persistente → el SSO de Microsoft suele saltarse
  el 2FA en renovaciones sucesivas.
- Fase 3 (D) — diálogo de cookie en la GUI. Fase 4 — ampliar `tests/test_proxy.py`
  (FastAPI TestClient). Fase 5 — documentación.
- Menor: `config.yaml` no se está leyendo (pydantic-settings sin
  `YamlConfigSettingsSource`); el proxy va por defaults + env `PROXY_*`.
- Deuda restante: `tests/test_proxy.py` inexistente (= Fase 4); decidir
  `actualizar_score_cliente` / `newsearch.php`.
