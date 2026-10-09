"""Cache de las capas de reglas de venta (Google My Maps publicado como KML).

Una descarga al dia basta para toda la LAN; si la descarga falla se sirve la
ultima copia guardada en disco (junto a config.yaml, GITIGNORED).
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from validator_app.core import geo

log = logging.getLogger("proxy.capas")

RUTA_CACHE_POR_DEFECTO = Path(__file__).resolve().parent / "capas_cache.kml"


class CapasNoDisponiblesError(Exception):
    """No hay capas: la descarga fallo y tampoco existe copia en disco."""


@dataclass
class CapasDisponibles:
    version: str
    capas: dict


def descargar_kml(url: str) -> str:
    resp = httpx.get(
        url,
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "JSConnect-WinCoverage-Proxy/1.0"},
    )
    resp.raise_for_status()
    return resp.text


def _interpretar(texto: str) -> CapasDisponibles:
    capas = geo.parse_kml(texto)
    if not any(capas.values()):
        raise ValueError("el KML no trae poligonos")
    version = hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]
    return CapasDisponibles(version, capas)


class CapasCache:
    def __init__(
        self,
        url: str,
        ruta_cache: Path = RUTA_CACHE_POR_DEFECTO,
        ttl_s: float = 86400,
        descargar: Callable[[str], str] = descargar_kml,
        reloj: Callable[[], float] = time.monotonic,
    ):
        self.url = url
        self.ruta_cache = Path(ruta_cache)
        self.ttl_s = ttl_s
        self._descargar = descargar
        self._reloj = reloj
        self._actual: CapasDisponibles | None = None
        self._cargado_en: float | None = None

    def _vigente(self) -> bool:
        return (
            self._actual is not None
            and self._cargado_en is not None
            and self._reloj() - self._cargado_en < self.ttl_s
        )

    def _desde_disco(self) -> CapasDisponibles | None:
        try:
            return _interpretar(self.ruta_cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def obtener(self) -> CapasDisponibles:
        if self._vigente():
            return self._actual
        if not self.url:
            previo = self._actual or self._desde_disco()
            if previo is None:
                raise CapasNoDisponiblesError("Capas de venta no configuradas")
            self._actual = previo
            self._cargado_en = self._reloj()
            return previo
        try:
            texto = self._descargar(self.url)
            nuevo = _interpretar(texto)
        except Exception as exc:
            log.warning("capas: no se pudo descargar/validar el KML: %s", exc)
            previo = self._actual or self._desde_disco()
            if previo is None:
                raise CapasNoDisponiblesError("Capas de venta no disponibles") from exc
            self._actual = previo
            self._cargado_en = self._reloj()
            return previo
        try:
            self.ruta_cache.write_text(texto, encoding="utf-8")
        except OSError as exc:
            log.warning("capas: no se pudo guardar la copia en disco: %s", exc)
        self._actual = nuevo
        self._cargado_en = self._reloj()
        return nuevo
