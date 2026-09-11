# ResumenDelDia.md — Historial del día

Fecha: 2026-09-11

## Qué se hizo hoy

### Etapa 0.5 — coherencia del almacén de la cookie con LocalSystem — HECHA

Se retomó a medio hacer (código cambiado pero sin commitear, tests rotos —
`tests/test_login_asistido.py` mockeaba la función vieja `save_session_to_keyring`,
renombrada a `push_session_cookie`; `ruff` marcaba un `import httpx` sin usar y
una línea larga).

- **`rotate_creds.py`**: `save_session_to_keyring()` (escribía directo al keyring
  **del owner**) → **`push_session_cookie()`**, que empuja la cookie por HTTP:
  `POST /local/renovar` (proceso vivo en `127.0.0.1`, sin admin key) y, si no
  conecta, cae a `POST /admin/rotar` con `X-Admin-Key`. Si `/local/renovar` sí
  conecta pero rechaza la cookie (401), **no** reintenta por `/admin/rotar`
  (sería la misma cookie mala). El keyring **del proceso del proxy**
  (LocalSystem en producción) queda como única fuente de verdad.
- **`config.py`**: nueva property `proxy_local_url` (`http://127.0.0.1:<puerto>`,
  ignora `proxy_host` a propósito — en producción es `0.0.0.0`, un bind de
  escucha, no un destino de cliente). Arregla de paso un bug latente:
  `_verificar_proxy()` usaba `proxy_url` y fallaba silenciosamente en la PC de
  oficina.
- **Tests**: renombrados los 4 mocks de `test_login_asistido.py` a
  `push_session_cookie`; 4 tests **nuevos** que ejercen `push_session_cookie` de
  verdad (con `httpx.post` monkeypatcheado, no solo mockeado a un lado): éxito
  por local, fallback a admin si no conecta, sin reintento si el local rechaza,
  falla limpio si nada responde. `tests/test_config.py` gana
  `test_proxy_local_url_ignora_proxy_host`.
- **Smoke en vivo**: proxy real arrancado en primer plano →
  `push_session_cookie("cookie-de-prueba-invalida")` → llegó de verdad a
  `/local/renovar`, WinForce la rechazó → `(False, ".../local/renovar devolvio
  HTTP 401: ...")`. Confirma la URL/puerto/payload contra el servidor real, no
  solo contra el mock.
- Docs sincronizados (`anotaciones.md`, `docs/rotacion-credenciales.md`,
  `PlanesAprobados.md`, `Roadmap.md`) — ya no describen `save_session_to_keyring()`.

**129 tests, ruff limpio.** Siguiente: **Etapa D** (nada la bloquea ya).
