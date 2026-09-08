"""Servidor Proxy FastAPI para JSConnect Win Coverage.

Endpoints:
- POST /api/cobertura  {lat, lon} -> CoberturaResponse
- POST /api/score      {tipo_doc, num_doc, lat, lon, cobertura?} -> ScoreResponse
- GET  /health         -> {status, version, session_age, logged_in, session_alive}
- GET  /admin/config   -> {proxy_url, token, timeouts} (auto-discovery)
- POST /admin/login    {php_sessid} -> inyecta y valida cookie de sesion WinForce
- POST /admin/rotar    {php_sessid} -> rota la cookie de sesion WinForce
- GET  /admin/status   -> {logged_in, session_age, creds_updated, session_alive}

Nota: el login programatico (usuario/password) es inviable por el 2FA de
Microsoft (ver AGENTS.md/anotaciones.md). La cookie PHPSESSID se obtiene
siempre de un login manual en navegador y se inyecta via /admin/login o
/admin/rotar (ambas hacen lo mismo: validar + guardar en keyring).

Auth:
- /api/*      -> X-Proxy-Token header + IP en allowed_networks
- /admin/*    -> X-Admin-Key header (solo owner)
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
import random
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from validator_app.core import api as core_api
from validator_app.proxy.config import ProxyConfig, get_config, reset_config

log = logging.getLogger(__name__)

# Segundos que se reutiliza el ultimo resultado de validar la cookie antes de
# volver a preguntarle a WinForce (evita una peticion de red por cada /health).
SESSION_ALIVE_TTL_SECONDS = 30

# Coordenadas que el keepalive rota al azar en cada ping, para no martillear
# siempre el mismo query contra WinForce. Subconjunto de ubicaciones PUBLICAS de
# Lima (Jesus Maria / Lince / San Isidro) de tools/coords_prueba.txt, donde
# viven las 49 completas que usa tools/medir_keepalive.py. NO son domicilios de
# clientes. Embebidas (no leidas de disco) porque el cwd del servicio no es
# fiable y tools/ puede no estar en el deploy.
_KEEPALIVE_COORDS: list[tuple[float, float]] = [
    (-12.0712441748165, -77.03826026511716),
    (-12.063877213667501, -77.04326554484533),
    (-12.065493554702455, -77.02953115727665),
    (-12.057527207575193, -77.0408649786354),
    (-12.062260862664193, -77.04716154605693),
    (-12.052716496803216, -77.03354521899678),
    (-12.058066001705464, -77.04680736412837),
    (-12.053332272583939, -77.04047144316046),
    (-12.055987789450054, -77.02547774198794),
    (-12.050676729437065, -77.04956211237528),
    (-12.068486573439170, -77.039798169965209),
    (-12.061203707094689, -77.037233988170613),
]


# Modelos Pydantic para requests/responses
class CoberturaRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class CoberturaResponse(BaseModel):
    hay_cobertura: bool
    cobertura: str
    tipo: str
    id_celda: str
    comment: str


class ScoreRequest(BaseModel):
    tipo_doc: str = Field(..., pattern="^(DNI|RUC|CE)$")
    num_doc: str = Field(..., min_length=8, max_length=11)
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    cobertura: str | None = "SI"


class ScoreResponse(BaseModel):
    valor: int | None
    riesgo: str | None
    conclusion: str | None
    deuda_total: str | None
    nombre: str | None
    documento: str | None
    valido: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    session_age: int | None
    logged_in: bool
    session_alive: bool


class AdminConfigResponse(BaseModel):
    proxy_url: str
    token: str
    timeouts: dict[str, int]
    version: str


class AdminCookieRequest(BaseModel):
    php_sessid: str


class KeepaliveStatus(BaseModel):
    enabled: bool
    last_ping_at: str | None
    last_ping_ok: bool | None
    consecutive_failures: int
    session_dead_since: str | None


class AdminStatusResponse(BaseModel):
    logged_in: bool
    session_age: int | None
    creds_updated: str | None
    proxy_version: str
    session_alive: bool
    keepalive: KeepaliveStatus


# Wrapper ValidatorAPI para el proxy (singleton con persistencia)
class ProxyValidatorAPI:
    def __init__(self, config: ProxyConfig):
        self.config = config
        self._client: core_api.ValidatorAPI | None = None
        self._last_activity: float = 0
        self._creds_updated: str | None = None
        self._session_alive: bool = False
        self._session_alive_cookie: str | None = None
        self._session_alive_checked_at: float = 0.0
        # Estado del keepalive (Fase 2A)
        self._keepalive_last_ping_at: float = 0.0
        self._keepalive_last_ping_ok: bool | None = None
        self._keepalive_consecutive_failures: int = 0
        self._session_dead_since: float | None = None

    def _get_client(self) -> core_api.ValidatorAPI:
        if self._client is None:
            self._client = core_api.ValidatorAPI()
            # El proxy gestiona la frescura de la sesion por su cuenta
            # (auto_relogin_if_needed + _relogin_silent + el loop de keepalive).
            # El guard idle interno del cliente-core lanzaria SessionError en
            # cada hueco de trafico >120s, antes de tocar la red; se neutraliza.
            self._client._session_max_idle = 10**9
        return self._client

    def auto_relogin_if_needed(self) -> None:
        """Re-login silencioso si sesión >120s idle o expirada."""
        now = time.time()
        if now - self._last_activity > self.config.session_max_idle_seconds:
            self._relogin_silent()
        self._last_activity = now

    def _relogin_silent(self) -> None:
        """Recupera la sesion recargando y revalidando la cookie mas reciente
        guardada en keyring (por si el owner la roto con rotate_creds.py
        mientras el proxy seguia corriendo). El login programatico es
        inviable por el 2FA de Microsoft; esta es la unica recuperacion
        automatica posible.

        Nunca propaga: los callers siguen adelante y dejan que la peticion
        real falle con su propio error. Pero cada motivo de fallo queda
        registrado, porque una recuperacion que no ocurre es invisible de
        otro modo."""
        import json

        import keyring

        keyring_ref = f"{self.config.win_keyring_service}/{self.config.win_keyring_user}_cookies"
        remedio = (
            "Haz login manual en el navegador y envia la PHPSESSID con "
            "POST /admin/rotar (o ejecuta rotate_creds.py)."
        )

        cookies_json = keyring.get_password(
            self.config.win_keyring_service,
            self.config.win_keyring_user + "_cookies",
        )
        if not cookies_json:
            log.warning(
                "Relogin omitido: no hay cookies guardadas en keyring (%s). %s",
                keyring_ref,
                remedio,
            )
            return

        try:
            cookies = json.loads(cookies_json)
        except ValueError as e:
            log.error(
                "Relogin fallido: las cookies del keyring (%s) no son JSON valido: %s. "
                "El valor guardado esta corrupto. %s",
                keyring_ref,
                e,
                remedio,
            )
            return

        php_sessid = cookies.get("PHPSESSID")
        if not php_sessid:
            log.warning(
                "Relogin omitido: las cookies del keyring (%s) no traen PHPSESSID "
                "(claves presentes: %s). %s",
                keyring_ref,
                sorted(cookies) if isinstance(cookies, dict) else type(cookies).__name__,
                remedio,
            )
            return

        try:
            core_api.validar_cookie_sesion(php_sessid)
        except core_api.LoginError as e:
            log.warning(
                "Relogin fallido: la PHPSESSID guardada en keyring (%s) ya no esta activa "
                "en WinForce: %s. %s",
                keyring_ref,
                e,
                remedio,
            )
            return
        except Exception as e:
            log.exception(
                "Relogin fallido: error inesperado validando la PHPSESSID contra WinForce: %s. "
                "Si es un fallo de red o WinForce esta caido, se reintentara solo; "
                "si persiste, revisa conectividad antes de rotar la cookie.",
                e,
            )
            return

        self._get_client().set_session_cookies({"PHPSESSID": php_sessid})
        self._invalidate_session_alive_cache()
        log.info("Relogin OK: sesion restaurada desde la cookie del keyring.")

    def _save_session_cookies(self) -> None:
        """Persiste cookies de sesion en keyring."""
        import json

        import keyring

        client = self._get_client()
        cookies = client.get_session_cookies()
        if cookies:
            keyring.set_password(
                self.config.win_keyring_service,
                self.config.win_keyring_user + "_cookies",
                json.dumps(cookies),
            )

    def _load_session_cookies(self) -> None:
        """Restaura cookies de sesion desde keyring al arrancar el proxy.

        No propaga: el proxy debe levantar aunque no haya sesion, para poder
        recibir la cookie por /admin/login. Pero deja dicho en el log por que
        arranco sin sesion y como arreglarlo, porque si no el primer /api/*
        falla sin ninguna pista."""
        import json

        import keyring

        keyring_ref = f"{self.config.win_keyring_service}/{self.config.win_keyring_user}_cookies"
        remedio = (
            "Haz login manual en el navegador y envia la PHPSESSID con "
            "POST /admin/rotar (o ejecuta rotate_creds.py)."
        )

        cookies_json = keyring.get_password(
            self.config.win_keyring_service,
            self.config.win_keyring_user + "_cookies",
        )
        if not cookies_json:
            log.warning(
                "Arranque sin sesion: no hay cookies guardadas en keyring (%s). %s",
                keyring_ref,
                remedio,
            )
            return

        try:
            cookies = json.loads(cookies_json)
        except ValueError as e:
            log.error(
                "Arranque sin sesion: las cookies del keyring (%s) no son JSON valido: %s. "
                "El valor guardado esta corrupto. %s",
                keyring_ref,
                e,
                remedio,
            )
            return

        try:
            self._get_client().set_session_cookies(cookies)
        except Exception as e:
            log.exception(
                "Arranque sin sesion: no se pudieron aplicar las cookies del keyring (%s): %s. %s",
                keyring_ref,
                e,
                remedio,
            )
            return

        log.info("Sesion restaurada desde keyring (%s).", keyring_ref)

    def validar_cobertura(self, lat: float, lon: float) -> dict:
        self.auto_relogin_if_needed()
        client = self._get_client()
        try:
            return client.validar_cobertura(lat, lon)
        except core_api.APIError as e:
            if "sesion" in str(e).lower() or "expirada" in str(e).lower():
                self._relogin_silent()
                return client.validar_cobertura(lat, lon)
            raise

    def validar_score(
        self,
        tipo_doc: str,
        num_doc: str,
        lat: float,
        lon: float,
        cobertura: str = "SI",
    ) -> dict:
        self.auto_relogin_if_needed()
        client = self._get_client()
        try:
            return client.validar_score(tipo_doc, num_doc, lat, lon, cobertura=cobertura)
        except core_api.APIError as e:
            if "sesion" in str(e).lower() or "expirada" in str(e).lower():
                self._relogin_silent()
                return client.validar_score(tipo_doc, num_doc, lat, lon, cobertura=cobertura)
            raise

    def set_session_cookie(self, php_sessid: str) -> None:
        """Inyecta y valida una cookie PHPSESSID obtenida de un login manual
        en navegador (usado por /admin/login y /admin/rotar). Lanza
        LoginError si la cookie no esta activa."""
        core_api.validar_cookie_sesion(php_sessid)
        client = self._get_client()
        client.set_session_cookies({"PHPSESSID": php_sessid})
        self._save_session_cookies()
        self._creds_updated = time.strftime("%Y-%m-%dT%H:%M:%S")
        # El owner renovo la cookie: la sesion vuelve a estar sana.
        self._session_dead_since = None
        self._keepalive_consecutive_failures = 0
        self._invalidate_session_alive_cache()

    def _invalidate_session_alive_cache(self) -> None:
        """Fuerza que el proximo get_status() vuelva a preguntarle a WinForce."""
        self._session_alive_checked_at = 0.0

    def _is_session_alive(self, php_sessid: str) -> bool:
        """Valida la cookie contra WinForce, reutilizando el ultimo resultado
        durante SESSION_ALIVE_TTL_SECONDS.

        /health se sondea con frecuencia y cada validacion es una peticion de
        red a WinForce; sin cache un monitor cada segundo genera una peticion
        por segundo. El cache se ata a la cookie concreta, asi que inyectar una
        nueva sesion nunca devuelve un resultado viejo."""
        now = time.time()
        if (
            self._session_alive_cookie == php_sessid
            and now - self._session_alive_checked_at < SESSION_ALIVE_TTL_SECONDS
        ):
            return self._session_alive

        try:
            core_api.validar_cookie_sesion(php_sessid)
            alive = True
        except core_api.LoginError:
            alive = False
        except Exception as e:
            # Un fallo de red no prueba que la sesion este muerta: se reporta
            # como no-viva para este chequeo, pero no se cachea.
            log.exception(
                "No se pudo comprobar si la sesion sigue viva: %s. "
                "session_alive se reporta como False sin cachear; probablemente "
                "sea red o WinForce caido, no una cookie expirada.",
                e,
            )
            return False

        self._session_alive = alive
        self._session_alive_cookie = php_sessid
        self._session_alive_checked_at = now
        return alive

    # ---------------------- keepalive ("latido perezoso") ----------------------

    def _keepalive_tick(self) -> dict:
        """Un ciclo del keepalive. Sincrono y sin estado global: el loop async
        lo llama con asyncio.to_thread.

        "Latido perezoso": si los agentes ya generaron trafico real dentro del
        intervalo, no se pinga (su trabajo normal ya mantiene la sesion viva).
        El ping solo cubre los huecos (almuerzo, primera hora)."""
        now = time.time()
        inactivo = now - self._last_activity
        if self._last_activity and inactivo < self.config.keepalive_interval_seconds:
            return {"accion": "omitido", "motivo": "trafico_reciente"}

        client = self._get_client()
        php_sessid = client._sesion.cookies.get("PHPSESSID") if client._sesion else None
        if not php_sessid:
            return {"accion": "omitido", "motivo": "sin_sesion"}

        lat, lon = random.choice(_KEEPALIVE_COORDS)
        try:
            client.validar_cobertura(lat, lon)
        except Exception as exc:
            return self._keepalive_registrar_fallo(php_sessid, exc)

        self._keepalive_last_ping_at = time.time()
        self._last_activity = self._keepalive_last_ping_at
        self._keepalive_last_ping_ok = True
        self._keepalive_consecutive_failures = 0
        self._session_dead_since = None
        return {"accion": "ping", "resultado": "VIVA", "coord": (lat, lon)}

    def _keepalive_registrar_fallo(self, php_sessid: str, exc: Exception) -> dict:
        """Clasifica un ping fallido: muerte de sesion vs. fallo del endpoint vs.
        indeterminado. Confirma contra WinForce con validar_cookie_sesion(),
        igual que _confirmar_muerte() de tools/medir_keepalive.py."""
        self._keepalive_last_ping_at = time.time()
        self._keepalive_last_ping_ok = False
        self._keepalive_consecutive_failures += 1
        try:
            core_api.validar_cookie_sesion(php_sessid)
        except core_api.LoginError:
            primera_vez = self._session_dead_since is None
            if primera_vez:
                self._session_dead_since = time.time()
                log.error(
                    "keepalive: la sesion WinForce MURIO y el keepalive no puede "
                    "recuperarla (tope absoluto de sesion ~9.5h desde el login; el "
                    "re-login programatico es inviable por el 2FA de Microsoft). "
                    "AVISO AL OWNER: renueva la cookie -> 'Renovar sesion' en la PC "
                    "del proxy, `python -m validator_app.proxy.rotate_creds`, o "
                    "POST /admin/rotar. Detalle del ping: %s",
                    exc,
                )
            else:
                log.warning(
                    "keepalive: la sesion WinForce sigue muerta (%s fallos "
                    "seguidos); esperando a que el owner renueve la cookie.",
                    self._keepalive_consecutive_failures,
                )
            return {"accion": "ping", "resultado": "SESION_MUERTA", "error": str(exc)}
        except Exception as exc2:
            log.warning(
                "keepalive: el ping fallo y no se pudo confirmar si la sesion "
                "sigue viva (%s). Probablemente red/WinForce caido; se reintenta "
                "en el proximo ciclo. Detalle del ping: %s",
                exc2,
                exc,
            )
            return {"accion": "ping", "resultado": "INDETERMINADO", "error": str(exc)}

        log.warning(
            "keepalive: el ping fallo pero la sesion sigue viva -> fallo del "
            "endpoint, no de la sesion (%s).",
            exc,
        )
        return {"accion": "ping", "resultado": "TRANSITORIO", "error": str(exc)}

    def _keepalive_status(self) -> dict:
        def _iso(ts: float | None) -> str | None:
            return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) if ts else None

        return {
            "enabled": self.config.keepalive_enabled,
            "last_ping_at": _iso(self._keepalive_last_ping_at or None),
            "last_ping_ok": self._keepalive_last_ping_ok,
            "consecutive_failures": self._keepalive_consecutive_failures,
            "session_dead_since": _iso(self._session_dead_since),
        }

    def get_status(self) -> dict:
        client = self._get_client()
        session_age = int(time.time() - self._last_activity) if self._last_activity else None
        logged_in = client._sesion is not None
        php_sessid = client._sesion.cookies.get("PHPSESSID") if client._sesion else None
        session_alive = self._is_session_alive(php_sessid) if php_sessid else False
        return {
            "logged_in": logged_in,
            "session_age": session_age,
            "creds_updated": self._creds_updated,
            "proxy_version": "dev",
            "session_alive": session_alive,
            "keepalive": self._keepalive_status(),
        }


_proxy_api: ProxyValidatorAPI | None = None


def get_proxy_api() -> ProxyValidatorAPI:
    global _proxy_api
    if _proxy_api is None:
        config = get_config()
        _proxy_api = ProxyValidatorAPI(config)
        _proxy_api._load_session_cookies()
    return _proxy_api


# Auth dependencies
async def verify_proxy_token(
    request: Request,
    x_proxy_token: Annotated[str | None, Header(alias="X-Proxy-Token")] = None,
) -> None:
    config = get_config()
    if x_proxy_token != config.proxy_token:
        raise HTTPException(status_code=401, detail="Token de proxy invalido")

    # Validar IP en redes permitidas
    client_ip = request.client.host if request.client else "unknown"
    if not _ip_in_allowed_networks(client_ip, config.allowed_networks):
        raise HTTPException(status_code=403, detail=f"IP no permitida: {client_ip}")


async def verify_admin_key(
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    config = get_config()
    if x_admin_key != config.admin_key:
        raise HTTPException(status_code=401, detail="Admin key invalida")


def _ip_in_allowed_networks(ip_str: str, networks: list[str]) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in ipaddress.ip_network(net) for net in networks)
    except Exception:
        return False


async def _keepalive_loop(
    proxy_api: ProxyValidatorAPI, interval: float, stop: asyncio.Event
) -> None:
    """Corre _keepalive_tick() cada `interval` segundos hasta que se pida parar.

    Cada tick corre en un hilo (asyncio.to_thread) porque el cliente-core es
    sincrono (requests). Un tick que lanza no mata el loop."""
    log.info("keepalive: loop iniciado (intervalo %ss)", interval)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            break  # se pidio parar
        except TimeoutError:
            pass
        try:
            resultado = await asyncio.to_thread(proxy_api._keepalive_tick)
            log.debug("keepalive: %s", resultado)
        except Exception:
            log.exception("keepalive: error inesperado en el tick (el loop sigue)")
    log.info("keepalive: loop detenido")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    proxy_api = get_proxy_api()  # Inicializa singleton
    config = get_config()
    task: asyncio.Task | None = None
    if config.keepalive_enabled:
        stop = asyncio.Event()
        task = asyncio.create_task(
            _keepalive_loop(proxy_api, config.keepalive_interval_seconds, stop)
        )
        app.state.keepalive_stop = stop
        app.state.keepalive_task = task

    yield

    # Shutdown
    if task is not None:
        app.state.keepalive_stop.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    reset_config()


app = FastAPI(
    title="JSConnect Win Coverage Proxy",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ENDPOINTS PUBLICOS (AGENTES) ====================

@app.post(
    "/api/cobertura",
    response_model=CoberturaResponse,
    dependencies=[Depends(verify_proxy_token)],
)
async def api_cobertura(request: CoberturaRequest):
    proxy_api = get_proxy_api()
    result = proxy_api.validar_cobertura(request.lat, request.lon)
    return CoberturaResponse(**result)


@app.post(
    "/api/score",
    response_model=ScoreResponse,
    dependencies=[Depends(verify_proxy_token)],
)
async def api_score(request: ScoreRequest):
    proxy_api = get_proxy_api()
    result = proxy_api.validar_score(
        tipo_doc=request.tipo_doc,
        num_doc=request.num_doc,
        lat=request.lat,
        lon=request.lon,
        cobertura=request.cobertura or "SI",
    )
    return ScoreResponse(**result)


@app.get("/health", response_model=HealthResponse)
async def health():
    proxy_api = get_proxy_api()
    status = proxy_api.get_status()
    return HealthResponse(
        status="ok",
        version="dev",
        session_age=status["session_age"],
        logged_in=status["logged_in"],
        session_alive=status["session_alive"],
    )


# ==================== ENDPOINTS ADMIN (OWNER) ====================

@app.get(
    "/admin/config",
    response_model=AdminConfigResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def admin_config():
    config = get_config()
    return AdminConfigResponse(
        proxy_url=config.proxy_url,
        token=config.proxy_token,
        timeouts={
            "connect": 5,
            "read": config.request_timeout,
            "winforce_login": config.winforce_login_timeout,
            "winforce_cobertura": config.winforce_cobertura_timeout,
            "winforce_score": config.winforce_score_timeout,
        },
        version="dev",
    )


@app.post("/admin/login", dependencies=[Depends(verify_admin_key)])
async def admin_login(request: AdminCookieRequest):
    proxy_api = get_proxy_api()
    proxy_api.set_session_cookie(request.php_sessid)
    return {"ok": True, "message": "Cookie WinForce validada y guardada"}


@app.post("/admin/rotar", dependencies=[Depends(verify_admin_key)])
async def admin_rotar(request: AdminCookieRequest):
    proxy_api = get_proxy_api()
    proxy_api.set_session_cookie(request.php_sessid)
    return {"ok": True, "message": "Cookie rotada y guardada en keyring"}


@app.get(
    "/admin/status",
    response_model=AdminStatusResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def admin_status():
    proxy_api = get_proxy_api()
    status = proxy_api.get_status()
    return AdminStatusResponse(
        logged_in=status["logged_in"],
        session_age=status["session_age"],
        creds_updated=status["creds_updated"],
        proxy_version=status["proxy_version"],
        session_alive=status["session_alive"],
        keepalive=KeepaliveStatus(**status["keepalive"]),
    )


# ==================== ERROR HANDLERS ====================

@app.exception_handler(core_api.LoginError)
async def login_error_handler(request: Request, exc: core_api.LoginError):
    return JSONResponse(
        status_code=401, content={"detail": f"Error de login WinForce: {exc}"}
    )


@app.exception_handler(core_api.ScoreError)
async def score_error_handler(request: Request, exc: core_api.ScoreError):
    return JSONResponse(status_code=502, content={"detail": f"Error de score: {exc}"})


@app.exception_handler(core_api.APIError)
async def api_error_handler(request: Request, exc: core_api.APIError):
    return JSONResponse(
        status_code=502, content={"detail": f"Error API WinForce: {exc}"}
    )


if __name__ == "__main__":
    import uvicorn

    # Sin esto el nivel raiz es WARNING y los log.info de sesion/relogin no se
    # verian; los warning saldrian por el handler de ultimo recurso, sin hora.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    config = get_config()
    uvicorn.run(app, host=config.proxy_host, port=config.proxy_port)
