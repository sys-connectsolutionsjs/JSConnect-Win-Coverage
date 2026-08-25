"""Servidor Proxy FastAPI para JSConnect Win Coverage.

Endpoints:
- POST /api/cobertura  {lat, lon} -> CoberturaResponse
- POST /api/score      {tipo_doc, num_doc, lat, lon, cobertura?} -> ScoreResponse
- GET  /health         -> {status, version, session_age, logged_in}
- GET  /admin/config   -> {proxy_url, token, timeouts} (auto-discovery)
- POST /admin/login    {usuario, password} -> prueba login WinForce
- POST /admin/rotar    {usuario, password} -> rota credenciales WinForce
- GET  /admin/status   -> {logged_in, session_age, creds_updated}

Auth:
- /api/*      -> X-Proxy-Token header + IP en allowed_networks
- /admin/*    -> X-Admin-Key header (solo owner)
"""

from __future__ import annotations

import ipaddress
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from validator_app.core import api as core_api
from validator_app.proxy.config import ProxyConfig, get_config, reset_config


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


class AdminConfigResponse(BaseModel):
    proxy_url: str
    token: str
    timeouts: dict[str, int]
    version: str


class AdminLoginRequest(BaseModel):
    usuario: str
    password: str


class AdminStatusResponse(BaseModel):
    logged_in: bool
    session_age: int | None
    creds_updated: str | None
    proxy_version: str


# Wrapper ValidatorAPI para el proxy (singleton con persistencia)
class ProxyValidatorAPI:
    def __init__(self, config: ProxyConfig):
        self.config = config
        self._client: core_api.ValidatorAPI | None = None
        self._last_activity: float = 0
        self._creds_updated: str | None = None

    def _get_client(self) -> core_api.ValidatorAPI:
        if self._client is None:
            self._client = core_api.ValidatorAPI()
        return self._client

    def auto_relogin_if_needed(self) -> None:
        """Re-login silencioso si sesión >120s idle o expirada."""
        now = time.time()
        if now - self._last_activity > self.config.session_max_idle_seconds:
            self._relogin_silent()
        self._last_activity = now

    def _relogin_silent(self) -> None:
        """Intenta re-logearse usando credenciales del keyring."""
        import json

        import keyring

        creds_json = keyring.get_password(
            self.config.win_keyring_service, self.config.win_keyring_user
        )
        if not creds_json:
            return
        try:
            creds = json.loads(creds_json)
            usuario = creds.get("usuario")
            password = creds.get("password")
            if usuario and password:
                client = self._get_client()
                client.login(usuario, password)
                self._save_session_cookies()
        except Exception:
            pass

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
        """Restaura cookies de sesion desde keyring."""
        import json

        import keyring

        cookies_json = keyring.get_password(
            self.config.win_keyring_service,
            self.config.win_keyring_user + "_cookies",
        )
        if cookies_json:
            try:
                cookies = json.loads(cookies_json)
                client = self._get_client()
                client.set_session_cookies(cookies)
            except Exception:
                pass

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

    def login_winforce(self, usuario: str, password: str) -> bool:
        """Login explicito (usado por /admin/login y /admin/rotar)."""
        client = self._get_client()
        client.login(usuario, password)
        self._save_session_cookies()
        self._creds_updated = time.strftime("%Y-%m-%dT%H:%M:%S")
        return True

    def get_status(self) -> dict:
        client = self._get_client()
        session_age = int(time.time() - self._last_activity) if self._last_activity else None
        logged_in = client._sesion is not None
        return {
            "logged_in": logged_in,
            "session_age": session_age,
            "creds_updated": self._creds_updated,
            "proxy_version": "dev",
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    get_proxy_api()  # Inicializa singleton
    yield
    # Shutdown
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
async def admin_login(request: AdminLoginRequest):
    proxy_api = get_proxy_api()
    proxy_api.login_winforce(request.usuario, request.password)
    return {"ok": True, "message": "Login WinForce exitoso, sesion guardada"}


@app.post("/admin/rotar", dependencies=[Depends(verify_admin_key)])
async def admin_rotar(request: AdminLoginRequest):
    proxy_api = get_proxy_api()
    proxy_api.login_winforce(request.usuario, request.password)
    return {"ok": True, "message": "Credenciales rotadas y guardadas en keyring"}


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

    config = get_config()
    uvicorn.run(app, host=config.proxy_host, port=config.proxy_port)
