"""Tiles de OpenStreetMap con el User-Agent del proyecto.

tkintermapview pide cada tile con el User-Agent fijo "TkinterMapView", que OSM
bloquea (devuelve la imagen "Access blocked"). Se envuelve el `requests` de su
modulo para que todas sus peticiones salgan identificadas como la app.
"""

import types

import requests

from validator_app.core import direccion


def _get_con_user_agent(url, *args, **kwargs):
    headers = dict(kwargs.get("headers") or {})
    headers["User-Agent"] = direccion.USER_AGENT
    kwargs["headers"] = headers
    return requests.get(url, *args, **kwargs)


def usar_user_agent_propio() -> None:
    """Idempotente: solo envuelve una vez el `requests` de tkintermapview."""
    from tkintermapview import map_widget

    if getattr(map_widget.requests, "_user_agent_propio", False):
        return
    envoltorio = types.SimpleNamespace(**vars(map_widget.requests))
    envoltorio.get = _get_con_user_agent
    envoltorio._user_agent_propio = True
    map_widget.requests = envoltorio
