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
- **Prototipo de interfaz web (rama `worktree-prototipo-web`, PAUSADO a medias)**: se instaló el plugin
  `modern-web-guidance` (telemetría desactivada con `DISABLE_TELEMETRY=1` en `.claude/settings.json`) y se
  empezó la Fase A: una galería de 5 variantes HTML/CSS/JS para comparar diseños antes de elegir (la app
  seguiría en Python y la interfaz se mostraría con pywebview sobre WebView2). Hecho: `validator_app/web/prototipos/comun/`
  (`tokens.css`, `base.css`, `datos.js`, `nucleo.js`) y las 5 variantes (`bento`, `panel`, `pasos`, `compacta`,
  `protagonista`, cada una con `index.html`, css y js). Tests nuevos: `tests/test_web_prototipos.py` y
  `tests/test_web_nucleo_js.py` (este ejecuta el JS con node y lo compara con Python: clasificación del score,
  parseo de coordenadas, tipo de documento y la sesión). **Ninguna página se ha abierto todavía en un navegador.**

## Pendiente al iniciar

### Prototipo web (retomar aquí; rama `worktree-prototipo-web`)

1. **Faltan 3 archivos** en `validator_app/web/prototipos/`: `index.html` (galería con enlaces a `bento/index.html`,
   `panel/index.html`, `pasos/index.html`, `compacta/index.html` y `protagonista/index.html`, una miniatura hecha solo
   con CSS y una línea de descripción por variante), `galeria.css` y `README.md`. El README debe incluir la política
   "Browser Support: solo Chromium/WebView2 reciente; se permiten funciones Newly available sin polyfills" y cómo abrir
   la galería. Sin URLs `http(s)://` ni `onclick` en línea (lo exigen los tests).
2. **Tests: hoy 115 pasan y 9 fallan.** Seis fallan solo por los 3 archivos de arriba. Los otros dos son reales:
   `base.css` no contiene la cadena `dialog::backdrop` (usa `dialog.dialogo::backdrop`: ajustar el test) y `panel.css`
   no declara `::view-transition-group` (agregar una regla de duración o relajar el test). Además
   `ruff check tests/test_web_nucleo_js.py` da 17 errores (líneas de más de 100 caracteres en el arnés JS y orden de
   imports): partir las líneas o mover el arnés a un `.js` aparte.
3. **Revisar en un Chromium real** (la venv ya tiene Playwright y Chromium): capturas a 1000×700 y a pantalla completa,
   en claro y oscuro, con los 7 casos de prueba, y la consola sin errores. Nada del CSS ni del DOM se ha visto todavía;
   lo más probable que falle: el layout de `bento`, las transiciones de vista de `pasos` y `protagonista`, y el
   `<details>` animado de `compacta`.
4. **Probar a mano**: copiar al portapapeles abriendo el archivo con `file://`, el cierre con clic fuera (`closedby="any"`)
   en los diálogos, el foco al cambiar de paso en `pasos` y el estado de carga (esqueletos).
5. **Documentar**: README raíz (es/en), TestingLog.md, y la política de navegadores en AGENTS.md (la sugiere la skill).
6. **El owner elige** una variante o una mezcla. Entonces la Fase B (no empezada): `validator_app/web/consulta.py`,
   `puente.py`, `main_web.py`, `build-web.ps1` y `requirements-web.txt` con `pywebview`; el `.exe` web no se publica en Releases.
7. **Ramas**: `main` local tiene 1 commit sin subir (`444972f`, telemetría desactivada); la rama del prototipo lo trae
   como `e9ecd6e`. Subir con `git push -u origin worktree-prototipo-web`.

### Otros pendientes

- **Verificar en vivo** (nada de esto se probó con un `.exe` real): compilar con `build.ps1` desde un commit
  anterior, publicar/usar un Release más nuevo y abrir el `.exe` → debe mostrar "Buscando actualizaciones...",
  instalar solo y reabrir en la versión nueva. Repetir sin red (aviso y entra) y con el proxy apagado (cae a GitHub).
- **Orden de despliegue**: actualizar el proxy (`docs/proxy-deploy.md`) para que exista `/api/version`; luego
  publicar el Release del agente. Los agentes actuales se actualizan una vez a mano (⚙ → "Buscar actualizaciones").
- Revisar que `publish-release.ps1` siempre publique el SHA-256 de cada `.exe` (ahora es obligatorio).
- La actualización obligatoria ya está en `main` (commit `290d8bd`, subido) y publicada como Release `v2026.11.20`.
- Owner: armar el Word desde `vpn.md` y elegir la opción (preguntas en su sección 12). Preferencia: NetBird propio en Oracle Cloud Always Free.
- Con la opción elegida: plan TDD de tokens del proxy por asesor (AGENTS 7i) y prueba piloto (PC del proxy + 2 remotos).
- "Reiniciar servicio" (confirmación de 1 s) y, en la próxima muerte, ver en `consulta_reintentada` que la detección baja a ~1.5 s. Probar a más de 10 min de la anterior.
- Owner: identificar a quien usa la cuenta del proxy en el día (o darle otra) y medir un día laboral.
- Confirmar que los asesores se actualizan a `v2026.11.03` y recoger su opinión sobre las tarjetas (AGENTS 7h).
- Apagar el conector "Claude Docs" en claude.ai → Configuración → Conectores (opcional).
- Después: mini PC (7d), alto de la consola owner (7g), cobertura observada (7e); reactivar agentes (**NO borrar `huellas_legacy()`**).
