"""Cache en memoria del ultimo Release del agente.

Los agentes de la oficina salen a internet por la misma IP publica, y la API de
GitHub sin autenticar solo permite 60 consultas por hora por IP: el proxy consulta
una vez cada pocos minutos y responde a todos los agentes desde aqui.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class VersionCache:
    def __init__(
        self,
        consultar: Callable[[], dict | None],
        ttl_s: float = 600,
        reloj: Callable[[], float] = time.monotonic,
        reintento_s: float = 60,
    ):
        self._consultar = consultar
        self._ttl_s = ttl_s
        self._reloj = reloj
        self._reintento_s = reintento_s
        self._lock = threading.Lock()
        self._tiene_dato = False
        self._valor: dict | None = None
        self._vence = 0.0
        self._ultimo_fallo: float | None = None
        self._ultimo_error: Exception | None = None

    def obtener(self) -> dict | None:
        """Ultimo release (None si el repo no tiene). Si GitHub falla sirve el ultimo
        dato bueno; sin dato previo lanza la excepcion."""
        with self._lock:
            ahora = self._reloj()
            if self._tiene_dato and ahora < self._vence:
                return self._valor
            if self._ultimo_fallo is not None and ahora < self._ultimo_fallo + self._reintento_s:
                return self._servir_ante_fallo()
            try:
                valor = self._consultar()
            except Exception as exc:
                self._ultimo_fallo = ahora
                self._ultimo_error = exc
                if self._tiene_dato:
                    return self._valor
                raise
            self._valor = valor
            self._tiene_dato = True
            self._vence = ahora + self._ttl_s
            self._ultimo_fallo = None
            self._ultimo_error = None
            return valor

    def _servir_ante_fallo(self) -> dict | None:
        if self._tiene_dato:
            return self._valor
        raise self._ultimo_error or RuntimeError("Version no disponible")
