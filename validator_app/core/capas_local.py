"""Capas de venta en el agente: copia embebida en el .exe + reglas al dia del proxy."""

import json
import threading
from pathlib import Path

from validator_app.core import geo

RUTA_CACHE_REGLAS = (
    Path.home() / "AppData" / "Roaming" / "JSConnectWinCoverage" / "capas_reglas.json"
)


def _leer_cache(ruta: Path):
    try:
        cuerpo = json.loads(Path(ruta).read_text(encoding="utf-8"))
        return cuerpo["version"], geo.capas_de_json(cuerpo["capas"])
    except (OSError, ValueError, KeyError, TypeError):
        return None, {}


def _guardar_cache(ruta: Path, version: str, capas: dict) -> None:
    try:
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        cuerpo = {"version": version, "capas": geo.capas_a_json(capas)}
        Path(ruta).write_text(json.dumps(cuerpo, separators=(",", ":")), encoding="utf-8")
    except OSError:
        pass


def _desde_proxy(cliente, version):
    """Respuesta del proxy con reglas nuevas, o None (sin proxy, caido o sin cambios)."""
    obtener = getattr(cliente, "obtener_capas", None)
    if not callable(obtener):
        return None
    try:
        respuesta = obtener(version)
    except Exception:
        return None
    if respuesta is not None and respuesta.actualizado and respuesta.capas is not None:
        return respuesta
    return None


def cargar_capas(cliente=None, ruta_cache=RUTA_CACHE_REGLAS) -> dict:
    """Capas embebidas; si el proxy responde, sus reglas (PREFERENTE 2 / BLOQUEADOS)
    reemplazan a las embebidas. Sin proxy o si falla, se usa la ultima copia local."""
    base = geo.cargar_capas_embebidas()
    version, remotas = _leer_cache(ruta_cache)
    respuesta = _desde_proxy(cliente, version)
    if respuesta is not None:
        remotas = respuesta.capas
        _guardar_cache(ruta_cache, respuesta.version, remotas)
    return geo.combinar_capas(base, remotas)


class CapasCargadas:
    """Carga de capas en segundo plano con garantia: quien decide espera a que terminen.

    Lo local (copia embebida + ultima copia de las reglas) queda listo de inmediato; el
    proxy, que puede tardar o estar caido, solo actualiza despues las reglas.
    `obtener` solo debe llamarse desde hilos de trabajo, nunca desde la interfaz."""

    def __init__(self):
        self._listo = threading.Event()
        self._capas: dict = {}

    @property
    def listo(self) -> bool:
        return self._listo.is_set()

    def cargar(self, cliente=None, ruta_cache=RUTA_CACHE_REGLAS) -> None:
        base, version = {}, None
        try:
            base = geo.cargar_capas_embebidas()
            version, remotas = _leer_cache(ruta_cache)
            self._capas = geo.combinar_capas(base, remotas)
        except Exception:
            self._capas = {}
        finally:
            self._listo.set()
        respuesta = _desde_proxy(cliente, version)
        if respuesta is not None:
            _guardar_cache(ruta_cache, respuesta.version, respuesta.capas)
            self._capas = geo.combinar_capas(base, respuesta.capas)

    def obtener(self, espera_s: float = 10) -> dict:
        self._listo.wait(espera_s)
        return self._capas
