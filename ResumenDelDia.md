# ResumenDelDia.md — Historial del día

Fecha: (se fija al abrir la proxima sesion)

## Rotación del resumen anterior

El detalle íntegro del 2026-11-20 quedó en `resumenes/2026-11-20.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- (nada todavía)

## Pendiente al iniciar

### Prototipo web (retomar aquí; rama `worktree-prototipo-web`)

- **Subir la rama**: `git push -u origin worktree-prototipo-web` (y `main`, que tiene `444972f` sin subir).
- **Faltan 3 archivos** en `validator_app/web/prototipos/`: `index.html` (galería con enlaces a `bento/index.html`, `panel/index.html`, `pasos/index.html`, `compacta/index.html` y `protagonista/index.html`, una miniatura hecha solo con CSS y una línea por variante), `galeria.css` y `README.md` (con la política "Browser Support: solo Chromium/WebView2 reciente; se permiten funciones Newly available sin polyfills" y cómo abrir la galería). Sin URLs `http(s)://` ni `onclick` en línea.
- **Tests**: hoy 869 pasan y 9 fallan. Siete por los 3 archivos de arriba; dos reales: `base.css` no contiene `dialog::backdrop` literal (usa `dialog.dialogo::backdrop`) y `panel.css` no declara `::view-transition-group`. `ruff check tests/test_web_nucleo_js.py` da 17 errores (líneas de más de 100 caracteres y orden de imports).
- **Revisar en un Chromium real** (la venv ya tiene Playwright y Chromium): capturas a 1000×700 y a pantalla completa, en claro y oscuro, con los 7 casos de prueba y la consola sin errores. Lo más probable que falle: el layout de `bento`, las transiciones de vista de `pasos` y `protagonista`, y el `<details>` animado de `compacta`.
- **Probar a mano**: copiar al portapapeles abriendo el archivo con `file://`, cierre con clic fuera (`closedby="any"`) en los diálogos, foco al cambiar de paso en `pasos` y los esqueletos de carga.
- **Documentar**: README raíz (es/en), y la política de navegadores en AGENTS.md (la sugiere la skill).
- **El owner elige** una variante o una mezcla; entonces la Fase B (conectar con Python), no empezada.

### Otros pendientes

- **Actualizar el proxy** para que exista `/api/version` (ver docs/proxy-deploy.md) y **probar la actualización al abrir** con un `.exe` real: uno más viejo con un Release más nuevo; repetir sin red (avisa y entra) y con el proxy apagado (cae a GitHub). Los agentes en `v2026.11.03` se actualizan una vez a mano desde ⚙ → "Buscar actualizaciones".
- Revisar que `publish-release.ps1` siempre publique el SHA-256 de cada `.exe` (ahora es obligatorio).
- Owner: armar el Word desde `vpn.md` y elegir la opción (preguntas en su sección 12). Preferencia: NetBird propio en Oracle Cloud Always Free; después, plan TDD de tokens del proxy por asesor (AGENTS 7i).
- "Reiniciar servicio" (confirmación de 1 s) y, en la próxima muerte, ver en `consulta_reintentada` que la detección baja a ~1.5 s. Probar a más de 10 min de la anterior.
- Owner: identificar a quien usa la cuenta del proxy en el día (o darle otra) y medir un día laboral.
- Confirmar que los asesores se actualizan a `v2026.11.03` y recoger su opinión sobre las tarjetas (AGENTS 7h).
- Apagar el conector "Claude Docs" en claude.ai → Configuración → Conectores (opcional).
- Después: mini PC (7d), alto de la consola owner (7g), cobertura observada (7e); reactivar agentes (**NO borrar `huellas_legacy()`**).
