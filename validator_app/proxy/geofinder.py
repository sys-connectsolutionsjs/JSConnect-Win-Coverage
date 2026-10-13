"""Cliente de Geofinder (API de geolocalizacion de Equifax que usa WinForce).

El token OAuth (`client_credentials`) dura ~24 min y se cachea; la credencial
(`Authorization: Basic ...`) vive solo en config.yaml del proxy (GITIGNORED).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from validator_app.core import direccion

URL_TOKEN = "https://api.latam.equifax.com/v2/oauth/token"
URL_REFERENCIA = "https://api.latam.equifax.com/geoapi/nyg/pe/coordinates-ref/v1"
URL_COORDENADAS = "https://api.latam.equifax.com/geoapi/nyg/pe/coordinates/v1"
SCOPE = "https://api.latam.equifax.com/geoapi/nyg/pe"
HOLGURA_TOKEN_S = 60
TIMEOUT_S = 10.0


class GeofinderEquifax:
    def __init__(
        self,
        basic: str,
        http=None,
        reloj: Callable[[], float] = time.monotonic,
    ):
        valor = (basic or "").strip()
        if valor.lower().startswith("basic "):
            valor = valor[6:].strip()
        self._basic = valor
        self._http = http
        self._reloj = reloj
        self._token: str | None = None
        self._vence: float = 0.0
        self._lock = threading.Lock()

    def _cliente(self):
        if self._http is None:
            import httpx

            self._http = httpx.Client(timeout=TIMEOUT_S)
        return self._http

    def _renovar_token(self) -> str:
        try:
            resp = self._cliente().post(
                URL_TOKEN,
                headers={"Authorization": f"Basic {self._basic}"},
                data={"grant_type": "client_credentials", "scope": SCOPE},
                timeout=TIMEOUT_S,
            )
            if resp.status_code != 200:
                raise direccion.DireccionNoDisponible(
                    f"Equifax rechazo el token (HTTP {resp.status_code})."
                )
            cuerpo = resp.json()
            token = cuerpo["access_token"]
            expira = float(cuerpo.get("expires_in", 0))
        except direccion.DireccionNoDisponible:
            raise
        except Exception as exc:
            raise direccion.DireccionNoDisponible(f"No se pudo obtener el token: {exc}") from exc
        self._token = token
        self._vence = self._reloj() + max(expira - HOLGURA_TOKEN_S, 0)
        return token

    def _token_vigente(self) -> str:
        if self._token is None or self._reloj() >= self._vence:
            return self._renovar_token()
        return self._token

    def _pedir(self, url: str, lat: float, lon: float, token: str):
        return self._cliente().get(
            url,
            params={"x": lon, "y": lat, "type": "json"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT_S,
        )

    def _obtener(self, url: str, lat: float, lon: float):
        """GET a Geofinder con el token vigente; si responde 401 renueva el token y repite."""
        try:
            resp = self._pedir(url, lat, lon, self._token_vigente())
            if resp.status_code == 401:
                resp = self._pedir(url, lat, lon, self._renovar_token())
            if resp.status_code != 200:
                raise direccion.DireccionNoDisponible(
                    f"Geofinder respondio HTTP {resp.status_code}."
                )
            return resp.json()
        except direccion.DireccionNoDisponible:
            raise
        except Exception as exc:
            raise direccion.DireccionNoDisponible(f"No se pudo consultar Geofinder: {exc}") from exc

    def consultar(self, lat: float, lon: float) -> dict:
        """Direccion de las coordenadas, siguiendo el mismo flujo que WinForce en el navegador.

        1) `coordinates-ref` con las coordenadas tal cual: da la direccion y el punto ajustado;
        2) `coordinates` con ese punto ajustado: departamento/provincia/distrito. Si la 2.a
        falla se usa el parentesis de la 1.a.
        """
        if not self._basic:
            raise direccion.DireccionNoDisponible("Geofinder no esta configurado en el proxy.")
        with self._lock:
            base = direccion.de_geofinder_ref(self._obtener(URL_REFERENCIA, lat, lon))
            if base is None:
                raise direccion.DireccionNoDisponible("Geofinder no devolvio direccion.")
            punto = base.pop("punto") or (lat, lon)
            detalle_ref = base.pop("detalle")
            try:
                detalle = direccion.de_geofinder(self._obtener(URL_COORDENADAS, *punto))
            except direccion.DireccionNoDisponible:
                detalle = None
        if detalle:
            for clave in ("departamento", "provincia", "distrito"):
                base[clave] = detalle[clave] or base[clave]
            base["direccion"] = direccion.con_ubicacion(
                detalle_ref, base["distrito"], base["provincia"], base["departamento"]
            ) or base["direccion"]
        return base
