"""Cliente HTTP para el Proxy Local (usado por agentes .exe).

Proporciona interfaz simple con retries, timeouts y errores tipados.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx


class ProxyError(Exception):
    """Error base del cliente proxy."""
    pass


class ProxyConnectionError(ProxyError):
    """No se pudo conectar al proxy."""
    pass


class ProxyAuthError(ProxyError):
    """Token invalido o IP no permitida."""
    pass


class ProxyServerError(ProxyError):
    """Error 5xx del proxy o error de WinForce."""
    pass


class ProxyTimeoutError(ProxyError):
    """Timeout en la peticion."""
    pass


@dataclass
class CoberturaResult:
    hay_cobertura: bool
    cobertura: str
    tipo: str
    id_celda: str
    comment: str


@dataclass
class ScoreResult:
    valor: int | None
    riesgo: str | None
    conclusion: str | None
    deuda_total: str | None
    nombre: str | None
    documento: str | None
    valido: bool


@dataclass
class HealthResult:
    status: str
    version: str
    session_age: int | None
    logged_in: bool


class ProxyClient:
    """Cliente para comunicarse con el proxy local.

    Uso:
        client = ProxyClient("http://192.168.1.50:8080", "token_aqui")
        cobertura = client.validar_cobertura(-12.08, -76.98)
        if cobertura.hay_cobertura:
            score = client.validar_score("DNI", "75020496", -12.08, -76.98, "SI")
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        connect_timeout: float = 5.0,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self.max_retries = max_retries
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> ProxyClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "X-Proxy-Token": self.token,
            "Content-Type": "application/json",
            "User-Agent": "JSConnect-WinCoverage-Agent/1.0",
        }

    def _request_with_retry(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                url = f"{self.base_url}{path}"
                resp = self.client.request(method, url, headers=self._headers(), **kwargs)
                if resp.status_code == 401:
                    raise ProxyAuthError("Token de proxy invalido o expirado")
                if resp.status_code == 403:
                    raise ProxyAuthError(
                        "IP no permitida en el proxy (verifica allowed_networks)"
                    )
                if 500 <= resp.status_code < 600:
                    raise ProxyServerError(
                        f"Error del proxy: HTTP {resp.status_code} - {resp.text[:200]}"
                    )
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException:
                last_exc = ProxyTimeoutError(
                    f"Timeout tras {self.timeout.connect}s conect / "
                    f"{self.timeout.read}s lectura"
                )
            except httpx.ConnectError as e:
                last_exc = ProxyConnectionError(f"No se puede conectar al proxy: {e}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    raise
                last_exc = ProxyServerError(
                    f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                )
            except ProxyError:
                raise
            except Exception as e:
                last_exc = ProxyError(f"Error inesperado: {e}")

            if attempt < self.max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait)

        raise last_exc or ProxyError("Error desconocido tras reintentos")

    def health_check(self) -> HealthResult:
        """Verifica que el proxy esta vivo y la sesion WinForce activa."""
        resp = self._request_with_retry("GET", "/health")
        data = resp.json()
        return HealthResult(
            status=data.get("status", "unknown"),
            version=data.get("version", "unknown"),
            session_age=data.get("session_age"),
            logged_in=data.get("logged_in", False),
        )

    def validar_cobertura(self, lat: float, lon: float) -> CoberturaResult:
        """Valida cobertura en coordenadas dadas."""
        resp = self._request_with_retry("POST", "/api/cobertura", json={"lat": lat, "lon": lon})
        data = resp.json()
        return CoberturaResult(
            hay_cobertura=data.get("hay_cobertura", False),
            cobertura=data.get("cobertura", "NO"),
            tipo=data.get("tipo", ""),
            id_celda=data.get("id_celda", ""),
            comment=data.get("comment", ""),
        )

    def validar_score(
        self,
        tipo_doc: str,
        num_doc: str,
        lat: float,
        lon: float,
        cobertura: str = "SI",
    ) -> ScoreResult:
        """Consulta score crediticio."""
        resp = self._request_with_retry(
            "POST",
            "/api/score",
            json={
                "tipo_doc": tipo_doc,
                "num_doc": num_doc,
                "lat": lat,
                "lon": lon,
                "cobertura": cobertura,
            },
        )
        data = resp.json()
        return ScoreResult(
            valor=data.get("valor"),
            riesgo=data.get("riesgo"),
            conclusion=data.get("conclusion"),
            deuda_total=data.get("deuda_total"),
            nombre=data.get("nombre"),
            documento=data.get("documento"),
            valido=data.get("valido", False),
        )

    @classmethod
    def from_discovery(
        cls, discovery_url: str = "http://proxy.oficina.local:8080/admin/config"
    ) -> ProxyClient:
        """Auto-configura el cliente consultando /admin/config del proxy.

        Util para agentes remotos que no conocen IP/token de antemano.
        Requiere DNS interno 'proxy.oficina.local' apuntando al proxy.
        """
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(discovery_url)
            resp.raise_for_status()
            cfg = resp.json()
        return cls(
            base_url=cfg["proxy_url"],
            token=cfg["token"],
            timeout=cfg.get("timeouts", {}).get("read", 30),
        )

    @classmethod
    def from_keyring(cls, service: str = "JSWinClient") -> ProxyClient | None:
        """Crea cliente desde Windows Keyring (configuracion guardada por GUI)."""
        try:
            import keyring
            url = keyring.get_password(service, "proxy_url")
            token = keyring.get_password(service, "proxy_token")
            if url and token:
                return cls(base_url=url, token=token)
        except Exception:
            pass
        return None

    def save_to_keyring(self, service: str = "JSWinClient") -> None:
        """Guarda configuracion en Windows Keyring."""
        import keyring
        keyring.set_password(service, "proxy_url", self.base_url)
        keyring.set_password(service, "proxy_token", self.token)
