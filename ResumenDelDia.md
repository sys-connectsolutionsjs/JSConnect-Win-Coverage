# ResumenDelDia.md — Historial del día

Fecha: 2026-10-30

## Rotación del resumen anterior

El detalle íntegro del 2026-10-28 quedó en `resumenes/2026-10-28.md` y su entrada
condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- Se retomó el plan Proxy 24/7 con un ensayo sin credenciales sobre `/login`, antes de gastar un login real.
- **Bug corregido** (TDD, 637 → 643 tests): el autologin no pasaba por el formulario de WinForce y
  habría agotado siempre el tiempo. Ahora envía `#username`/`#password`/`#ingresar` una sola vez, y un
  rechazo de WinForce cuenta como credencial inválida, sin reintento. Sin commit todavía.
- El owner instaló el servicio y guardó la credencial, pero el autologin no entraba: 47 rechazos HTTP 410
  de WinForce a Chromium headless desde las 11:15. La contraseña nunca llegó a enviarse.
- **Decisión y cambio** (TDD, 643 → 647 tests): el servicio usa Chromium normal, sin cambiar el
  User-Agent. Si WinForce rechaza el navegador, el autologin se detiene y avisa una vez, y la consola
  dice que no es la contraseña. **Sin comprobar en vivo**: el UAC del reinicio del servicio se canceló y
  sigue corriendo el código anterior, que reintenta cada 5 min.
- Tras reiniciar el servicio el owner: se acabó el 410, Chromium normal funciona como LocalSystem y
  WinForce acepta el formulario. Cada intento se quedaba 90 s en una tercera pantalla
  (`accesoventas.win.pe`, "Iniciar con Microsoft / Google"), que `logs/autologin_fallo.png` dejó ver.
- **Cambio** (TDD, 647 → 650 tests): el autologin pulsa "Iniciar con Microsoft" una sola vez por intento.
  **Sin comprobar en vivo**: hace falta otro reinicio del servicio.
- Tras ese reinicio el autologin llegó a Microsoft y se detuvo con "credencial inválida" (15:28 y 15:29).
  No había imagen de ese error.
- **Cambio** (TDD, 650 → 658 tests): cada fallo guarda una imagen en `logs/autologin_fallos/` (últimas 20),
  además de `logs/autologin_fallo.png`, y la bitácora lleva la ruta y el texto de Microsoft.
- La primera imagen (15:38) corrigió el diagnóstico: el campo de correo estaba vacío, así que era un falso
  "credencial inválida" y la contraseña aún no se ha probado en Microsoft. Causa probable, sin confirmar:
  recarga `sso_reload`.
- **Cambio** (TDD, 658 → 663 tests): el correo se reescribe hasta 3 veces y ese aviso no apaga el autologin.
  Requiere reiniciar el servicio.
- Tras ese reinicio el correo pasó, pero la contraseña quedó escrita sin enviarse (15:48), sin error.
- **Cambio** (TDD, 663 → 667 tests): espera 1.5 s, escribe una sola vez y reenvía con Enter si la pantalla
  no avanza (máximo 3 envíos). Requiere reiniciar el servicio.
- Con ese cambio siguió fallando (15:56, correo vacío otra vez). Causas sin demostrar: se añadió
  `logs/autologin_pasos/` (traza + imagen por paso, 667 → 670 tests). Requiere reiniciar el servicio.
- **Causa real encontrada con el rastro**: la pantalla del correo trae un campo de contraseña oculto que
  Playwright da por visible; el correo nunca se escribía. Selector corregido, y retirados el reenvío con
  Enter y la espera (se basaban en una hipótesis equivocada). 667 tests. Requiere reiniciar el servicio.
- **Primer login automático real (16:11:54)**: el proxy entró solo, sin intervención, en ~10 s, y
  `/health` volvió a `session_alive: true`.
- Falta: consulta real desde un agente, prueba de muerte de sesión, regenerar el owner y decidir sobre el
  token `win-azure-oauth2` (recomendación inicial: no guardarlo aparte).
- Pendiente: confirmar `renovada` con `origen: autologin` y regenerar el owner con
  `build-owner.ps1` (el `.exe` debe estar cerrado).
- Visto en el log, sin relación con el autologin: `capas` no pudo validar el KML de `capas_kml_url` (tarea 7b).
- A vigilar: la sesión renovada a mano a las 11:21 murió a los 304 s.
- Tras el login, la sesión siguió viva más de 1 h. Los "errores de red" de 16:58 y 17:22 eran la **PC
  suspendida**: 15 suspensiones entre 16:50 y 17:37 (sin uso 30 min con corriente; la tarjeta de red la
  despertaba ~2 min). El proxy los tomó bien como red, no como sesión muerta, pero dormido no atiende.
- **Cambio** (TDD, 667 → 668 tests): `install_service.bat` quita la suspensión e hibernación con corriente
  (`[ENERGIA]`, sin número); como los demás pasos, si ya estaba así dice "ya estaba" sin tocar nada (669 tests). En esta PC hay que aplicarlo a mano con `powercfg` como Administrador.
  Lista del host definitivo (mini PC) ampliada en PlanesAprobados.
- Capas: el owner cambió `capas_kml_url` a un enlace de descarga KML (18:31); falta reiniciar el servicio
  y ver `GET /api/capas` 200.
- Capas: tras el reinicio (18:49) el proxy descargó el KML nuevo y `GET /api/capas` dio 200.
- **Prueba de muerte superada (19:00)**: el owner entró con la misma cuenta en otra PC; la consulta de un
  agente dio 502 (la que detectó la muerte), `muerta` 19:00:50 y `renovada` con `origen: autologin`
  19:01:02 (12 s); la siguiente cobertura, 200. **SSO silencioso confirmado**: la traza no pasó por correo ni
  contraseña (Microsoft recordó la sesión del perfil del servicio). Por eso no hace falta guardar aparte el
  token `win-azure-oauth2`.
- **Cambio** (TDD, 669 → 678 tests): la consulta del asesor espera al autologin (hasta 15 s) y se repite
  sola en vez de dar 502/503; los endpoints dejan de congelar el proxy mientras esperan. Medición en
  `consulta_reintentada` (espera y total). Requiere "Reiniciar servicio" y repetir la prueba de muerte.
- 19:40: segunda prueba de muerte, aún con el código anterior (502; autologin 6 s). 19:41: al reiniciar,
  el servicio no arrancó por `autologin_espera_consulta_s:` vacío en `config.yaml` (10061 en los agentes);
  el owner lo corrigió. **Cambio** (679 tests): clave vacía = valor por defecto con aviso, y la medición
  separa detección, autologin y consulta.
- ~20:00, tercera prueba (con la espera cargada): 502 otra vez. La cookie pasó la validación y murió
  segundos después; WinForce devolvió su página de login ("Respuesta inesperada") y el proxy no lo tomaba
  como sesión muerta. **Cambio** (683 tests): esa respuesta se comprueba como posible muerte y los 502 quedan
  en el log. Requiere reiniciar el servicio y repetir la prueba sin abrir `/health` antes.
- Documentación del flujo real corregida (rotación de credenciales, anotaciones, plan, AGENTS 7f, TestingLog, README).

## Pendiente al iniciar (martes 2026-11-03)

- **Primero**: "Reiniciar servicio" en la consola owner y comprobar `/health` (`session_alive: true`).
- **Prueba de la consulta que espera al autologin** (AGENTS → último cierre, paso 2): sin abrir `/health` ni la
  consola antes, entrar con la cuenta del proxy en otra PC y consultar una cobertura desde un agente.
  Esperado: el asesor recibe la cobertura (sin 502/503) y `logs/sesion_eventos.jsonl` muestra `muerta` →
  `renovada` (autologin) → `consulta_reintentada` con `deteccion / autologin / consulta / total`. Si sale 502,
  `winsw.err.log` ya trae la línea `502 en /api/...` con el detalle.
- Con 2-3 muertes medidas, decidir recortes: confirmación de 3 s → 1 s, no revalidar la misma cookie.
- Vigilar la concurrencia el primer día laboral (hasta 40 consultas a la vez, sesión `requests` compartida).
- Observar un día laboral del autologin (pausa por "muertes rápidas" = alguien más usa la cuenta).
- Regenerar `JSConnect-Win-Owner.exe` con `build-owner.ps1` (consola cerrada). Sin Release hasta que el owner lo pida.
- Push: el commit del 2026-10-30 quedó solo en local.
- Después: migrar a la mini PC (PlanesAprobados → "Migración al host definitivo", lista ampliada) y Tailscale.
- Revisar el alto de la consola owner (AGENTS 7g).
- Cobertura observada (7e).
- Reactivar los agentes con la huella estable (**NO borrar `huellas_legacy()`**).
- Probar un agente W10 contra el owner W11; archivo del pendrive con URL + token; firma de código.
- Detección automática de "no cruzar avenida de doble vía" y dibujar los huecos de los polígonos.
- Diferido: Etapa C.12, `actualizar_score_cliente` / `newsearch.php`, backlog v1.1.
