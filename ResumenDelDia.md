# ResumenDelDia.md — Historial del día

Fecha: 2026-09-18

## Rotación del resumen anterior

El resumen del 2026-09-16 ya estaba preservado en `resumenes/2026-09-16.md` y en
`HistorialResumenes.md`. El detalle íntegro de hoy está en `resumenes/2026-09-18.md`
(snapshot) y su entrada condensada en `HistorialResumenes.md`.

## Qué se hizo hoy

- **Decisión**: ensayo completo del proxy en la PC de desarrollo antes de la PC owner
  oficial. La oficina tiene **15 PC** hoy (meta 35); piloto de 2 agentes primero. El
  ensayo no coexiste con el proxy de la oficina (una sola sesión WinForce).
- **Instalador re-ejecutable** (`install_service.bat`): ventana `cmd /k`, cada paso
  verifica "ya estaba"/"hecho ahora", resumen final y pregunta Conservar/Regenerar
  tokens. Bug del paso 5 (`)` sin escapar en `echo` dentro de bloques) corregido con
  `tests/test_install_bat.py`. Paso 7: si la PC no es gestionada (Windows Home/
  WORKGROUP) Chrome ignora la política; solo avisa y al final imprime la carga manual
  de la extensión.
- **Consola owner**: usa `127.0.0.1:8080` si no carga `config.yaml` (ACL o `.exe`
  empaquetado) en vez de "falta configurar el servicio"; botón **Reiniciar servicio**
  (PowerShell elevado con UAC).
- **Agente**: ⚙ Configuración → **Activación / Huella de la PC** (estado, copiar huella,
  reactivar); `activacion_vigente()` con tests.
- **Control de acceso**: `localhost` daba 403 "IP no permitida"; loopback ahora siempre
  permitido. Decisión: las IP públicas del router (`162.120.185.241`, `38.253.147.12`,
  `72.14.201.203`) NO se agregan (en LAN el proxy ve IPs privadas). VPN futura:
  Tailscale (`100.64.0.0/10`) ya cubierto; otra VPN, añadir su rango. Lección: el
  servicio solo carga código/config al arrancar; reiniciarlo tras cambios.
- **Tests**: `conftest.py` aísla el `config.yaml` real (antes 37 casos fallaban sin
  elevar). **157 tests, ruff limpio.**
- **Documentación** actualizada: glosario (`anotaciones.md`), `arquitectura.md`
  ("Control de acceso"), `Escalabilidad.md` (tabla VPN y lista corregida),
  `escalabilidad-remota.md`, `proxy-deploy.md` ("Qué llevar a la PC owner"),
  `proxy-config.md`, `rotacion-credenciales.md`, `README*.md`, `AGENTS.md`,
  `Roadmap.md`, `PlanesAprobados.md`, `TestingLog.md`.
- **Abierto**: la sesión WinForce murió 3 veces (15:06, 15:32, 15:45) pese a
  renovaciones 200; hipótesis sin confirmar: dos logins en paralelo se invalidan.

## Artefactos gitignorados creados en esta PC (para la PC owner oficial)

Dentro del repo (no viajan con `git clone`):

| Artefacto | Qué es | ¿Llevarlo? |
|---|---|---|
| `generator/private_key.pem` y `dist/private_key.pem` | Llave privada RSA del owner | **Sí, solo el `.pem`** (canal privado, ACL, borrar del pendrive) |
| `dist/JSConnect-Win-Owner.exe` | Consola owner (reconstruida 17:17) | Recomendado (no se publica en Releases) |
| `dist/JSConnect-Win-Coverage.exe` | Agente con "Activación / Huella" | Opcional; para las 15 PC usar Release |
| `validator_app/proxy/config.yaml`, `proxy_token.txt`, `admin_key.txt` | Tokens y config de ESTE ensayo | **No**: el instalador crea nuevos; no reutilizar |
| `validator_app/proxy/winsw.exe`, `winsw.xml` | Wrapper del servicio | No (se descarga / regenera) |
| `validator_app/proxy/extension.pem`, `extension.crx`, `updates.xml`, `.extension_build/` | Extensión empaquetada | No (se regenera; id nuevo) |
| `validator_app/proxy/.browser_profile/` | Perfil de Chrome del login asistido | No (contiene sesión) |
| `logs/` | Logs de winsw | No |
| `.venv/`, `build/`, `*.spec`, `.claude/hooks/*.local.json` | Entorno y builds locales | No |

Fuera del repo (estado de esta PC): servicio `JSWinProxy`, tarea `JSWinProxy-AvisoSesion`,
fuente de eventos `JSWinProxy`, política de Chrome `ExtensionSettings\<id>`, icono
"Renovar sesion WinForce" del Escritorio, Chromium en `%LOCALAPPDATA%\ms-playwright`,
`%APPDATA%\JSConnectWinCoverage\activacion.dat`, y entradas del Credential Manager
(`JSWinProxy`, `JSWinClient`). Se quitan con `uninstall_service.bat` + limpieza manual.

**Con `private_key.pem` basta para la firma de códigos**; el resto se regenera con
Git + Internet (Python 3.14.7, pip, Chromium, winsw). Detalle en `docs/proxy-deploy.md`.

## Siguiente sesión (continuar aquí)

1. Sesión WinForce estable con una sola vía de login; `/health` a 1, 5 y 10 min.
2. Persistencia tras reiniciar el servicio; logs sin secretos; aviso de sesión muerta.
3. Firewall + agente desde otra PC de la LAN; `tools/probar_concurrencia.py`.
4. Desinstalar el ensayo; publicar el agente (`publish-release.ps1`) para las 15 PC.
5. Etapa D/E en la PC owner oficial (llevar `private_key.pem`), luego Fase 5.
6. Decidir si el instalador debe crear la regla de firewall y el acceso directo de la
   consola owner.
