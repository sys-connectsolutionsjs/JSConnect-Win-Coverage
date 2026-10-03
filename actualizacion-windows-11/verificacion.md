# Verificación

Todo lo de "Probado" se ejecutó el **2026-10-02** en la PC de oficina real
(Windows 11 Pro 25H2, build 26200, español; IP de LAN `192.168.18.107`).

## Probado en la PC real

| Qué | Cómo | Resultado |
|---|---|---|
| Suite de tests | `pytest -q` + `ruff check validator_app tests generator` | **287 passed**, ruff limpio |
| Firewall | `Get-NetFirewallRule -DisplayName 'JSWinProxy API'` + `Test-NetConnection 192.168.18.107 -Port 8080` | `Profile: Any`, `RemoteAddress` = 4 rangos LAN/Tailscale, conexión **OK** |
| `wmic` ausente | `Get-Command wmic` | No existe (confirma el problema 2) |
| Huella sin `wmic` | `obtener_huella()` dos veces | Estable; CPU `178BFBFF00A50F00` y volumen `3402271654` leídos por CIM (~1.3 s) |
| Aviso de sesión caducada (prueba) | `_aviso_event_log(101, ...)` → evento + tarea | Evento 101 escrito, tarea `JSWinProxy-AvisoSesion` disparada en el mismo segundo, resultado 0 |
| Aviso de sesión caducada (**real**) | La sesión WinForce caducó sola a las 18:18 y 18:29 | El **servicio** (LocalSystem) escribió los eventos 101/102; la tarea corrió a las **18:29:48, resultado 0** |
| Causa del bug del popup | `eventcreate ... /SO JSWinProxy` | Error *"El parámetro de origen se usa para identificar solo las aplicaciones/scripts"*; el origen tiene `EventMessageFile` de .NET y sin `CustomSource` |
| Renovar sin elevar | `get_config()` sin elevar | Antes: `PermissionError` (confirmado). Ahora: `proxy_local_url_seguro()` → `http://127.0.0.1:8080`, `_verificar_proxy()` lee `/local/estado` |
| Portapapeles privado | `copiar_sin_historial()` + `Get-Clipboard` + formatos | Texto legible en otras apps, legible **tras cerrar la consola y terminar el proceso**, formatos de exclusión presentes, la limpieza de los 60 s lo borra |
| Lógica nueva del `.bat` | `.bat` de prueba aislado | Puerto 8080 → "en uso", 8099 → "libre", regenerar → "libre", `pythonw` correcto, health check distingue ok / no ok |
| Instalador completo | `install_service.bat` re-ejecutado elevado (entrada simulada "C" = conservar tokens) | Los 13 pasos OK; regla de firewall "ya estaba - actualizada"; tokens conservados |
| Servicio tras reinicio | `Restart-Service JSWinProxy` + `/local/estado` | Arranca con el código nuevo y **conserva** la sesión WinForce |
| `.exe` del owner | `dist\JSConnect-Win-Owner.exe` reconstruido y abierto | Corre; Smart App Control **no** lo bloqueó |
| `.exe` del agente | `dist\JSConnect-Win-Coverage.exe` | **Bloqueado** por Smart App Control en esta PC (no es un fallo del código) |
| Extensión de Chrome | 7 clics registrados en `logs/winsw.out.log` | `POST /local/renovar` 200 OK → la renovación siempre funcionó; lo que faltaba era una señal visible |

## NO probado todavía

- **Un agente real con Windows 10** contra este proxy: "Probar conexión" a
  `http://192.168.18.107:8080`, huella igual a la de antes, validar un caso.
- **Que la huella CIM sea idéntica a la de `wmic`** en una misma PC: no se pudo
  comparar aquí porque esta PC ya no tiene `wmic`. Se puede comprobar en un
  agente con Windows 10 corriendo desde el código:
  ```powershell
  python -c "from validator_app.activation import fingerprint as f; print(f._cpu(), f._volume_serial()); f._hay_wmic = lambda: False; f._cim_cache = None; print(f._cpu(), f._volume_serial())"
  ```
  (las dos líneas deben coincidir).
- **Consola owner en uso real** sin ventanas de Terminal ("Actualizar estado",
  Reiniciar servicio, Mostrar / Rotar tokens).
- **El badge nuevo de la extensión** después de recargarla en `chrome://extensions`.
- **El actualizador** con un Release nuevo (no se publicó ninguno).
