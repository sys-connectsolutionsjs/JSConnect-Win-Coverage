"""Limites del mapa: encierra la vista en Peru (logica pura, sin tkinter)."""

import math

# (lat norte, lon oeste, lat sur, lon este), con un pequeno margen sobre la frontera.
PERU_BBOX = (0.2, -81.5, -18.5, -68.5)
ZOOM_MIN_PERU = 5


def _a_tile(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    n = 2**zoom
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def _ajuste_eje(inicio: float, fin: float, minimo: float, maximo: float) -> float:
    if fin - inicio >= maximo - minimo:
        return (minimo + maximo) / 2 - (inicio + fin) / 2
    if inicio < minimo:
        return minimo - inicio
    if fin > maximo:
        return maximo - fin
    return 0.0


def ajuste_vista(sup_izq, inf_der, zoom: int, bbox=PERU_BBOX) -> tuple[float, float]:
    """Corrimiento (dx, dy) en tiles para que la vista quede dentro de `bbox`.

    Si la vista es mas grande que el bbox en un eje, la centra en ese eje.
    """
    x0, y0 = _a_tile(bbox[0], bbox[1], zoom)
    x1, y1 = _a_tile(bbox[2], bbox[3], zoom)
    dx = _ajuste_eje(sup_izq[0], inf_der[0], x0, x1)
    dy = _ajuste_eje(sup_izq[1], inf_der[1], y0, y1)
    return dx, dy
