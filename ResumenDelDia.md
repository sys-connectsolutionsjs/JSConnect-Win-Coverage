# ResumenDelDia.md — Historial del día

Fecha: 2026-11-20

## Rotación del resumen anterior

El detalle íntegro del 2026-11-06 quedó en `resumenes/2026-11-06.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- **Actualización obligatoria al abrir el agente (estilo Steam)**, con TDD (704 → 754 tests, `ruff` limpio):
  - `updater/check.py`: `ultimo_release_agente(timeout)`, `es_build_real()` y `chequeo_inicio(proxy)` con
    estados `dev` / `actualizar` / `al_dia` / `sin_conexion`; pregunta al proxy y, si no responde, a GitHub
    (timeout 5 s); descarta una descarga del proxy que no sea de los Releases de este repo.
  - Proxy: `GET /api/version` (token) con caché de 10 min (`proxy/version_cache.py`) y
    `ProxyClient.obtener_version()`; evita agotar los 60 consultas/hora de GitHub con 25+ agentes.
  - `updater/download.py`: ahora exige el checksum SHA-256 del Release y lo compara sin distinguir
    mayúsculas (antes un hash en minúsculas fallaba siempre y sin hash se instalaba sin verificar).
  - `gui/main_window.py`: `_inicio` busca antes de la activación; si hay versión nueva instala sin
    preguntar; sin conexión o con la instalación fallida avisa y deja entrar.
  - Documentado en README (es/en), `docs/arquitectura.md`, AGENTS.md y TestingLog.md.
- Decisiones del dueño: sin conexión **se deja entrar**; consultar **primero al proxy**.

## Pendiente al iniciar

- **Verificar en vivo** (nada de esto se probó con un `.exe` real): compilar con `build.ps1` desde un commit
  anterior, publicar/usar un Release más nuevo y abrir el `.exe` → debe mostrar "Buscando actualizaciones...",
  instalar solo y reabrir en la versión nueva. Repetir sin red (aviso y entra) y con el proxy apagado (cae a GitHub).
- **Orden de despliegue**: actualizar el proxy (`docs/proxy-deploy.md`) para que exista `/api/version`; luego
  publicar el Release del agente. Los agentes actuales se actualizan una vez a mano (⚙ → "Buscar actualizaciones").
- Revisar que `publish-release.ps1` siempre publique el SHA-256 de cada `.exe` (ahora es obligatorio).
- No hay commit todavía: los cambios están sin subir.
- Owner: armar el Word desde `vpn.md` y elegir la opción (preguntas en su sección 12). Preferencia: NetBird propio en Oracle Cloud Always Free.
- Con la opción elegida: plan TDD de tokens del proxy por asesor (AGENTS 7i) y prueba piloto (PC del proxy + 2 remotos).
- "Reiniciar servicio" (confirmación de 1 s) y, en la próxima muerte, ver en `consulta_reintentada` que la detección baja a ~1.5 s. Probar a más de 10 min de la anterior.
- Owner: identificar a quien usa la cuenta del proxy en el día (o darle otra) y medir un día laboral.
- Confirmar que los asesores se actualizan a `v2026.11.03` y recoger su opinión sobre las tarjetas (AGENTS 7h).
- Apagar el conector "Claude Docs" en claude.ai → Configuración → Conectores (opcional).
- Después: mini PC (7d), alto de la consola owner (7g), cobertura observada (7e); reactivar agentes (**NO borrar `huellas_legacy()`**).
