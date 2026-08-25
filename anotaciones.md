# Anotaciones Técnicas - Glosario del Proyecto

> **Para futuros programadores**: Términos, conceptos y decisiones que no son obvios al leer el código.
> Si no entiendes algo, busca aquí. Si no está, agrégalo.

---

## A

### API Interna (WinForce)
El sistema del ISP (`appwinforce.win.pe`) expone una API JSON interna en `/controllers/*.php` que el navegador usa vía AJAX. **No es pública documentada**, pero no requiere scraping: replicamos las llamadas HTTP directas.
- Endpoints: `acceso.php` (login), `coordenada.php` (cobertura), `cliente.php` (score), `operador.php` (verificar sesión), `document.php` (tipos doc), `newsearch.php` (crear lead)

### Auto-relogin Silencioso
Mecanismo en `ValidatorAPI` (proxy y standalone) que detecta sesión expirada o >120s sin uso → hace login automático en background → reintenta la petición original. El agente/cliente no ve error.

---

## C

### Cobertura (Validación de)
Consulta a `GET /controllers/coordenada.php?accion=validar_cobertura&data[latitud]=...&data[longitud]=...`.
Respuesta: `{"response":"success","cobertura":"SI|NO","tipo":"HORIZONTAL|VERTICAL|...","id_celda":"9754","comment":"..."}`.
- `cobertura: "SI"` → hay servicio disponible
- `tipo` → tecnología (HORIZONTAL = fibra/radio, VERTICAL = satelital, etc.)
- `id_celda` → identificador interno de la celda de cobertura

### Configuración (config.yaml / config.yaml.example)
- `config.yaml` = **archivo real con secretos** (gitignored, solo en PC proxy)
- `config.yaml.example` = **plantilla en repo** con placeholders y comentarios
- Leída por `config.py` via Pydantic Settings (precedencia: env vars > yaml > defaults)

### Credenciales WinForce
Usuario/contraseña del sistema del ISP. **Rotan cada 1-2 meses** (desactivan cuenta anterior + entregan nuevas al responsable).
- **NUNCA** en repo, **NUNCA** en agentes
- Solo en **Windows Keyring de la PC proxy** (`JSWinProxy`/`credentials`)
- Rotación: `rotate_creds.py` via RDP (v1) o endpoint `/admin/rotar` (v2 VPN)

---

## D

### DNS Interno (Tailnet)
En Tailscale: nombre `proxy.oficina.local` → IP Tailscale del proxy (ej. `100.64.12.34`).
Permite auto-discovery: agentes usan `http://proxy.oficina.local:8080/admin/config` para auto-configurarse.

---

## E

### Equifax (API Externa Crediticia)
API de bureo de crédito (`api.latam.equifax.com`). WinForce la usa para score.
- OAuth: `client_credentials` (credenciales embebidas en JS del sitio WinForce)
- Endpoints geodata: `coordinates`, `coordinates-ref`, `intersectz`, `capas`
- Reporte SOAP: respuesta `score_cliente` viene doble-encodificada (JSON string dentro de JSON)
- **Proxy NO replica geocoding Equifax**; envía campos geodata vacíos en `score_cliente`

---

## F

### FastAPI
Framework web async para Python. Usado en `server.py` del proxy.
- Ventajas: concurrencia nativa (async/await), validación Pydantic automática, Swagger UI en `/docs`, inyección de dependencias (`Depends`)
- Corre con `uvicorn` (ASGI server)

---

## G

### Geodata (Distrito, Ubigeo, Código Postal, Segmentación)
Datos geográficos que WinForce **NO devuelve** en cobertura/score. El navegador los calcula llamando directo a Equifax OAuth.
- En `api.py:141-151` se envían 25 campos vacíos (`""`) en el payload `score_cliente`
- El servidor WinForce los rellena internamente o no son obligatorios para el score

### Gitignore (Qué NUNCA Subir)
```
config.yaml
proxy_token.txt
admin_key.txt
generator/private_key.pem
tools/captura.json
tools/js/
tools/captura_inicio.png
*.pyc
__pycache__/
.pytest_cache/
.ruff_cache/
dist/
build/
*.exe
```

---

## H

### Health Check (`GET /health`)
Endpoint público del proxy para verificar que está vivo y la sesión WinForce activa.
Respuesta: `{"status":"ok","version":"<commit-sha>","session_age":45,"logged_in":true}`

---

## K

### Keyring (Windows Credential Manager)
Almacén cifrado del SO por usuario. Cada usuario Windows tiene el suyo.
- **Agentes**: `JSWinClient`/`proxy_url` + `JSWinClient`/`proxy_token`
- **Proxy**: `JSWinProxy`/`credentials` (cookies sesión WinForce + user/pass)
- **Activación**: `JSWinCoverage`/`activation_code` (por huella HW)

---

## M

### Microsoft 2FA (Login WinForce)
**Crítico**: Login en `appwinforce.win.pe` redirige a `login.microsoftonline.com` para segunda autenticación (2FA) con la misma cuenta.
- **Imposible automatizar** sin replicar todo el flujo OAuth2/SAML de Microsoft
- **Consecuencia**: Prueba de concurrencia 4-5 máquinas **inviable** (requiere 2FA manual cada una)
- **Solución**: Proxy local (1 sesión) + rotación manual via RDP (owner hace login en navegador + copia cookie)

### Middleware Auth (Proxy)
En `server.py`: valida requests antes de llegar a endpoints.
- `/api/*` → `X-Proxy-Token` header + IP en `allowed_networks`
- `/admin/*` → `X-Admin-Key` header (solo owner)

---

## P

### Proxy Local (Reverse Proxy Interno)
Servidor intermedio en PC oficina que:
1. Recibe peticiones de agentes (LAN/VPN)
2. Valida token + IP
3. Reenvía a WinForce usando **SU propia sesión** (cookies en keyring)
4. Devuelve respuesta a agente
- Evita: 20 sesiones concurrentes, rotación credenciales en 20 máquinas, bloqueo por IP
- Stack: FastAPI + uvicorn + winsw service
- Puerto: 8080 (configurable)

### Proxy Token (Token Compartido)
Secreto de 256-bit (64 chars hex) compartido entre proxy y **todos** los agentes.
- Generado auto en `install_service.bat` (`secrets.token_hex(32)`)
- Guardado en `config.yaml` (proxy) + keyring agentes (`JSWinClient`/`proxy_token`)
- **No es secreto crítico**: solo valida en LAN/VPN + IP binding. Si se filtra, atacante ya está en la red.

---

## R

### Rotación de Credenciales (Cada 1-2 Meses)
Proceso para actualizar user/pass WinForce en el proxy.
- **v1 (actual)**: Owner RDP a PC proxy → `python -m validator_app.proxy.rotate_creds` → pega cookie `PHPSESSID` de navegador (tras login manual con 2FA)
- **v2 (futuro)**: Owner via VPN → `POST /admin/rotar` con `X-Admin-Key` + user/pass nuevo

### requirements-proxy.txt
Dependencias **solo del proxy** (NO van en .exe agentes):
```
-r requirements.txt
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.7
pydantic-settings>=2.3
# winsw se descarga binario, no pip
```
Separado de `requirements-dev.txt` para que .exe final sea ligero.

---

## S

### Score (Validación Crediticia)
Consulta a `POST /controllers/cliente.php` con `accion=score_cliente` + muchos campos `data[...]`.
- Respuesta: `{"response":"success","data":"<JSON-string con reporte SOAP Equifax>"}`
- Parseo: `json.loads(data)` → busca recursivamente `ns3ResumenScoreRP3.Puntaje` (ej: 423), `NivelRiesgo` (ej: MUY ALTO), `ResumenDeuda.DeudaTotal`
- Payload incluye: tipo_doc (1=DNI, 2=CE, 3=RUC), documento, coordenadas, cobertura, 25 campos geodata vacíos

### Standalone Mode (Modo Sin Proxy)
Si el agente **no tiene config de proxy** en keyring → usa `validator_app.core.api.ValidatorAPI` directo contra WinForce.
- Requiere credenciales WinForce en keyring local (`JSWinCoverage`/`credentials`)
- **Solo para desarrollo/pruebas/owner** — NO producción (riesgo bloqueo 20 sesiones)

---

## T

### Tailscale (VPN Mesh)
VPN zero-config basada en WireGuard. Gratis hasta 100 devices.
- Instalación: `winget install Tailscale.Tailscale` → login cuenta empresa → auto-mesh
- IPs estables: `100.64.x.y` (CGNAT range)
- DNS interno: `proxy.oficina.local` configurable en admin console
- **Permite escalar a remotos sin cambios de código**

### Token (Ver Proxy Token)

---

## V

### ValidatorAPI (Core)
Clase principal en `validator_app/core/api.py`:
- `login(usuario, password)` → crea sesión, verifica con `operador.php`
- `validar_cobertura(lat, lon)` → GET coordenada.php
- `validar_score(tipo, num, lat, lon, cobertura, geodata?)` → POST cliente.php + parseo SOAP
- `validar(lat, lon, tipo, num)` → flujo completo cobertura → score
- `auto_relogin_if_needed()` → llamado antes de cada request en proxy
- `get_session_cookies()` / `set_session_cookies()` → persistencia keyring

---

## W

### WinForce (Sistema del ISP)
Sistema de validación del proveedor de internet (`appwinforce.win.pe`).
- Login: formulario → redirect Microsoft 2FA → cookie `PHPSESSID`
- Cobertura: coordenadas → SI/NO + tipo + id_celda
- Score: documento + coordenadas → reporte Equifax SOAP (puntaje, riesgo, deuda)
- Límites: 2-3 sesiones concurrentes por cuenta, timeout 3 min, rotación credenciales 1-2 meses

### winsw (Windows Service Wrapper)
Herramienta que convierte cualquier exe en servicio Windows nativo.
- Config: `winsw.xml` (nombre, descripción, exe, args, logs)
- Comandos: `winsw.exe install | start | stop | uninstall | status`
- Logs: Visor de Eventos → Aplicaciones y Servicios → `JSWinProxy`

---

## Siglas

| Sigla | Significado |
|-------|-------------|
| **CE** | Carnet de Extranjería (9 chars alfanumérico) |
| **DNI** | Documento Nacional de Identidad (8 dígitos) |
| **RUC** | Registro Único de Contribuyentes (11 dígitos) |
| **ISP** | Internet Service Provider (el cliente/empresa) |
| **SOAP** | Simple Object Access Protocol (XML legacy, usa Equifax) |
| **TLS** | Transport Layer Security (HTTPS) |
| **CGNAT** | Carrier-Grade NAT (rango 100.64.0.0/10, usado por Tailscale) |
| **mTLS** | Mutual TLS (certificados cliente+servidor, no usado aún) |

---

## Patrones de Código en Este Proyecto

### TDD (Test-Driven Development)
- Tests en `tests/` → `pytest`
- Flujo: Rojo (test falla) → Verde (implementa mínimo) → Refactor
- Bitácora: `TestingLog.md`

### Typing Moderno (Python 3.14+)
```python
# Usar builtins, no typing
list[str]          # no List[str]
dict[str, Any]     # no Dict[str, Any]
str | None         # no Optional[str]
from __future__ import annotations  # en todos los archivos
```

### Errores Tipados
```python
class APIError(Exception): pass
class LoginError(APIError): pass
class ScoreError(APIError): pass
# En proxy/client.py:
class ProxyConnectionError(APIError): pass
class ProxyAuthError(APIError): pass
```

### Keyring Helper
```python
import keyring
keyring.set_password("servicio", "usuario", "secreto")
keyring.get_password("servicio", "usuario")  # None si no existe
keyring.delete_password("servicio", "usuario")
```

---

## Dónde Buscar Más

| Tema | Archivo |
|------|---------|
| Arquitectura completa | `docs/arquitectura.md` |
| Instalación proxy | `docs/proxy-deploy.md` |
| Config agentes | `docs/proxy-config.md` |
| Rotación credenciales | `docs/rotacion-credenciales.md` |
| Escalabilidad remota | `docs/escalabilidad-remota.md` + `Escalabilidad.md` |
| Historial decisiones | `AGENTS.md` (Historial) + `PlanesAprobados.md` |
| Tests y bugs | `TestingLog.md` |
| Resumen día actual | `ResumenDelDia.md` |
| Resumenes pasados | `resumenes/YYYY-MM-DD.md` |