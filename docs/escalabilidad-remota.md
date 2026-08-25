# Escalabilidad a Agentes Remotos

> Guía para futuros programadores: cómo extender la arquitectura a agentes fuera de la LAN.

---

## Situación Actual (2026-08-25)

| Métrica | Valor |
|---------|-------|
| Agentes | 20 en LAN oficina |
| Proxy | 1 (PC fija oficina) |
| Autenticación | Token compartido + IP LAN binding |
| Credenciales WinForce | Solo en keyring PC proxy |
| Acceso owner | RDP a PC proxy |

---

## Objetivo Futuro

Soportar **N agentes remotos** (laptops de vendedores en campo, home office, otras sedes) **sin cambiar la arquitectura del proxy**.

---

## Solución Recomendada: VPN + Mismo Proxy

### Por qué VPN (no AnyDesk, no Tunnels manuales, no API pública)

| Opción | Escalabilidad | Seguridad | Mantenimiento | Costo |
|--------|---------------|-----------|---------------|-------|
| **Tailscale / WireGuard (VPN mesh)** | ✅ 100+ devices gratis | ✅ Cifrado E2E, zero-trust | ✅ 1-click install, auto-mesh | $0 (Tailscale gratis ≤100) |
| AnyDesk / TeamViewer | ❌ Manual 1-a-1 | ⚠️ Acceso remoto completo | ❌ No automatizable | $ |
| Ngrok / Cloudflare Tunnel | ⚠️ Exposición pública | ⚠️ Requiere auth extra | ⚠️ Config por agente | $/gratis limitado |
| API pública en VPS | ✅ Escalable | ❌ Superficie ataque | ⚠️ Hosting + hardening | $ |

**Decisión**: **Tailscale** (o WireGuard si prefieren self-hosted). Instalación 1-click en PC proxy + cada laptop. Mesh automático. IPs estables `100.x.y.z`. Mismo token, mismo proxy, **cero cambios de código**.

---

## Implementación Paso a Paso (Para Futuro Dev)

### 1. Instalar Tailscale en PC Proxy
```powershell
# En PC proxy (como Admin)
winget install Tailscale.Tailscale
# Login con cuenta empresa (Google/GitHub/Microsoft)
# Anotar IP Tailscale: ej. 100.64.12.34
```

### 2. Instalar Tailscale en Cada Laptop Remota
```powershell
# En cada laptop (usuario final, no requiere Admin)
winget install Tailscale.Tailscale
# Login con misma cuenta empresa → se une a la tailnet automáticamente
```

### 3. Verificar Conectividad
```powershell
# Desde laptop remota
ping 100.64.12.34  # IP Tailscale de la PC proxy
curl http://100.64.12.34:8080/health
# {"status":"ok","version":"...","logged_in":true}
```

### 4. Configurar Agentes Remotos (Igual que LAN)
- IP proxy: `100.64.12.34:8080` (IP Tailscale, no LAN)
- Token: **El mismo** que agentes LAN
- Keyring: `JSWinClient`/`proxy_url` = `http://100.64.12.34:8080`

**Resultado**: Agentes remotos indistinguibles de agentes LAN para el proxy.

---

## Auto-Discovery (Para Que No Configuren IP Manual)

### Endpoint Ya Preparado en Proxy
```
GET /admin/config  (sin auth, solo LAN/VPN)
```
Respuesta:
```json
{
  "proxy_url": "http://100.64.12.34:8080",
  "token": "a1b2c3d4e5f6...",
  "timeouts": {"connect": 5, "read": 30},
  "version": "c0d2f2a"
}
```

### Cliente Preparado
```python
# validator_app/proxy/client.py
@classmethod
def from_discovery(cls, discovery_url: str = "http://proxy.oficina.local:8080/admin/config") -> "ProxyClient":
    resp = httpx.get(discovery_url, timeout=5)
    resp.raise_for_status()
    cfg = resp.json()
    return cls(base_url=cfg["proxy_url"], token=cfg["token"], timeout=cfg["timeouts"]["read"])
```

### DNS Interno (Opcional pero Recomendado)
- Configurar en router/DNS de la tailnet: `proxy.oficina.local` → `100.64.12.34`
- Agentes usan `http://proxy.oficina.local:8080/admin/config` para auto-configurarse
- Si cambia IP proxy → actualizar DNS, agentes se reconfiguran solos

---

## Múltiples Proxies (High Availability / Load Balancing)

Cuando la carga crezca (>100 agentes) o quieran redundancia:

### Arquitectura
```
                    ┌─────────────┐
                    │  Load Balancer  │ (nginx/HAProxy/Tailscale Funnel)
                    │  proxy.oficina.local │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      ┌─────────┐    ┌─────────┐    ┌─────────┐
      │ Proxy 1 │    │ Proxy 2 │    │ Proxy 3 │
      │(PC Ofic)│    │(PC Resp)│    │(Cloud VM)│
      └────┬────┘    └────┬────┘    └────┬────┘
           │              │              │
           └──────────────┼──────────────┘
                          ▼
                   ┌─────────────┐
                   │  WinForce   │
                   │ (1 cuenta)  │
                   └─────────────┘
```

### Requisitos
1. **Session affinity** (sticky sessions) O **session store compartido** (Redis)
   - Opción A: LB con sticky sessions (cookie `PHPSESSID` → mismo proxy)
   - Opción B: Proxies comparten cookies via Redis (complejo, WinForce no soporta multi-session bien)
2. **Token compartido** igual en todos los proxies
3. **Credenciales WinForce** → solo en **UNO** proxy (el "master"); otros hacen forward interno
   - O más simple: solo 1 proxy activo (activo-pasivo), failover manual

### Configuración Proxy Múltiple (config.yaml)
```yaml
# Proxy master (habla con WinForce)
proxy_token: "shared-token"
admin_key: "admin-key-1"
win_keyring_service: "JSWinProxy"
is_master: true

# Proxy replicas (forward a master)
proxy_token: "shared-token"
admin_key: "admin-key-2"
win_keyring_service: "JSWinProxy"
is_master: false
master_url: "http://100.64.12.34:8080"  # IP Tailscale del master
```

---

## Métricas y Observabilidad (Preparado)

### Prometheus Metrics (Descomentar en `server.py`)
```python
# En server.py, descomentar:
from prometheus_client import Counter, Histogram, generate_latest

REQUEST_COUNT = Counter('proxy_requests_total', 'Total requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('proxy_request_duration_seconds', 'Request latency', ['endpoint'])

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Dashboards Grafana Sugeridos
- Requests/sec por endpoint (/api/cobertura, /api/score)
- Latencia p50/p95/p99
- Error rate (4xx, 5xx)
- Sesión WinForce age (cuándo hará auto-relogin)
- Agentes activos (unique IPs / hora)

---

## Checklist para Futuro Dev (Cuando Pidan Agentes Remotos)

- [ ] Instalar Tailscale en PC proxy + laptops (1-click cada una)
- [ ] Verificar `curl http://<tailscale-ip>:8080/health` desde laptop
- [ ] Configurar agente remoto con IP Tailscale + mismo token
- [ ] (Opcional) Configurar DNS `proxy.oficina.local` en tailnet
- [ ] (Opcional) Habilitar `/admin/config` y `ProxyClient.from_discovery()`
- [ ] Documentar en `README_PROXY.md` sección "Agentes Remotos"
- [ ] Probar con 1 laptop remota → validar cobertura + score → OK
- [ ] Escalar a N laptops

---

## Lo Que NO Hay Que Hacer

| ❌ No Hacer | Por Qué |
|-------------|---------|
| Exponer proxy en internet público (puerto 8080 en router) | Superficie de ataque, credenciales WinForce en riesgo |
| Crear API pública en VPS separada | Doble mantenimiento, credenciales en la nube, costo |
| Usar AnyDesk/TeamViewer para "conectar agentes remotos" | No escala, manual, seguridad cuestionable |
| Dar credenciales WinForce a agentes remotos | Rompe modelo de seguridad; rotación cada 1-2 meses imposible |
| Hardcodear IP proxy en .exe agentes | Impide migración, failover, DNS |

---

## Referencias

- `docs/arquitectura.md` — Diagrama y decisiones base
- `docs/proxy-deploy.md` — Instalación proxy (base para réplicas)
- `validator_app/proxy/client.py` — `ProxyClient.from_discovery()`
- `validator_app/proxy/server.py` — `GET /admin/config`
- Tailscale docs: https://tailscale.com/kb/