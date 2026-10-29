# ResumenDelDia.md — Historial del día

Fecha: 2026-10-28

## Rotación del resumen anterior

El detalle íntegro del 2026-10-27 quedó en `resumenes/2026-10-27.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- **Plan Proxy 24/7: código implementado** (TDD, 500 → 568 tests, `ruff` limpio, sin commit todavía).
  - `validator_app/proxy/autologin.py` (nuevo):
    - `login_automatico()`: Chromium headless con perfil `.browser_profile_servicio/`. Primero deja actuar al SSO silencioso. Llena usuario y contraseña una sola vez cada uno y acepta KMSI. Si Microsoft rechaza la credencial lanza `CredencialInvalidaError` y no reintenta. Si se agota el tiempo deja la captura `logs/autologin_fallo.png`.
    - `FrenoAutologin`: espera 0 → 2 → 10 → 30 min, tope de 6 por hora, pausa de 30 min tras 2 muertes a menos de 10 min de un autologin.
    - CLI `--probar`.
  - `server.py`:
    - credencial en el keyring del servicio (`credentials_login`) y `POST /local/credenciales` (admin key + loopback, sin eco);
    - relogin en un hilo único lanzado desde `_marcar_sesion_muerta()` y desde el keepalive (también cuando no hay sesión);
    - aviso al owner solo si el autologin falla, se pausa o la credencial es inválida;
    - eventos nuevos en la bitácora y bloque `autologin` en `/health` y `/admin/status`.
  - `rotate_creds.py --guardar-login` (consola de Administrador).
  - `config.py` / `config.yaml.example`: `autologin_*`.
  - `install_service.bat`, `winsw.xml.example` y `login_asistido.usar_navegadores_compartidos()`: Chromium compartido en `validator_app\proxy\.ms-playwright` (SYSTEM no ve el `%LOCALAPPDATA%` del admin).
  - Docs: `docs/rotacion-credenciales.md` (sección "Autologin desatendido"), `docs/escalabilidad-remota.md` (runbook Tailscale), README (es/en), README_PROXY, AGENTS (estructura), TestingLog, PlanesAprobados (pasos sacados de la cola).
- **Ajustes de diseño respecto al plan del 2026-10-27**:
  - el relogin vive en su propio hilo con reintentos, porque `_marcar_sesion_muerta()` es idempotente;
  - el aviso al owner se suprime mientras el autologin pueda resolverlo;
  - el éxito queda en la bitácora como `renovada` con `origen: autologin`;
  - `PLAYWRIGHT_BROWSERS_PATH` también lo fija el código, para que el login asistido del owner encuentre el navegador.
- **Guardar la credencial sin terminal** (pedido del usuario; 568 → 585 tests):
  - consola owner, sección "Autologin de WinForce": muestra el estado leído de `/health` y tiene el botón **Configurar...** (usuario + contraseña, UAC solo para leer la admin key; la contraseña sale de la consola sin elevar);
  - `install_service.bat` pregunta al final `[AUTOLOGIN]` (por defecto No; en una reinstalación ya configurada solo lo informa);
  - `push_credencial_login` acepta la admin key y la URL ya resueltas.
  
  Desde la extensión **no**: no puede presentar la admin key, así que habría que abrir `/local/credenciales` a cualquier programa de la PC.
- **Frenado del autologin configurable** (pedido del usuario; 585 → 637 tests):
  - reglas: el 1.er intento es inmediato; el 2.º, de 1 a 5 min; el 3.º, desde el 2.º hasta 10; el 4.º, desde el 3.º hasta 15; del 5.º en adelante, un intervalo fijo de 1 a 20 min;
  - perfiles: Recomendado 1-2-3/5 (por defecto), Rápido, Demasiado rápido (no recomendado), Lento óptimo, Lento, Demasiado lento (no recomendado) y Personalizado;
  - se elige en la consola owner → "Frenado..." (UAC), se aplica en vivo por `POST /local/freno` y se guarda en `autologin_freno.json`;
  - la pausa por "otra persona usa la cuenta" es el intervalo fijo del perfil; el tope por hora sale del frenado (se quitó `autologin_max_por_hora`).
- **Decisión: no hay opción de 30 s.** Lo pidió el usuario como pregunta y se le recomendó no hacerlo: el frenado solo actúa cuando el relogin *falla*; cuando otra persona usa la cuenta, el relogin funciona y la bota, y eso lo limita la pausa. Reloguear cada pocos segundos no gana la pelea, y tantos logins pueden hacer que marquen la cuenta.
- **Bug del botón "Instalar extensión en Chrome"**: el instalador solo creaba `.extension_build` si encontraba Chrome, y lo marcaba como hecho aunque no la creara; el botón mostraba la ruta sin comprobar que existiera. Ahora la carpeta se arma siempre, y si falta el botón ofrece "Preparar carpeta" (UAC). En esta PC el servicio no está instalado, así que el botón dice "Instala el servicio primero".
- **Sin verificar en vivo**: el login real contra Microsoft y Playwright corriendo como LocalSystem.

## Pendiente al iniciar

- **Verificación en vivo del autologin** (`PlanesAprobados.md` → plan Proxy 24/7 → "Verificación en vivo"): `autologin --probar`, reinstalar el servicio (opción C), `--guardar-login`, matar la sesión y ver `renovada/autologin`.
- ~~Implementar el plan Proxy 24/7~~ → código hecho el 2026-10-28 (pasos 1-6). Orden que se siguió:
  1. `FrenoAutologin`;
  2. `autologin.py`;
  3. `POST /local/credenciales` + `rotate_creds --guardar-login`;
  4. relogin en `server.py`;
  5. `PLAYWRIGHT_BROWSERS_PATH`;
  6. verificación en vivo;
  7. Tailscale.
- Mientras tanto: averiguar quién más entra con la cuenta dedicada del proxy (Chrome del owner, celular, otra PC).
- Después: desinstalar el servicio en esta PC y migrar al host definitivo (plan → "Migración al host definitivo").
- Que los asesores pulsen "Buscar actualizaciones" para pasar a `v2026.10.23`.
- Cobertura observada (7e).
- Reactivar los agentes con la huella estable (**NO borrar `huellas_legacy()`**) y reemplazar a mano el `.exe` del owner si sigue en `v2026.10.07`.
- Probar un agente W10 contra el owner W11; archivo del pendrive con URL + token; firma de código.
- Detección automática de "no cruzar avenida de doble vía" y dibujar los huecos de los polígonos.
- Diferido: Etapa C.12, `actualizar_score_cliente` / `newsearch.php`, backlog v1.1.
