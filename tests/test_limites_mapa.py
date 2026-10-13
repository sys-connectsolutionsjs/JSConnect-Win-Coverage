import math

from validator_app.gui import limites_mapa as lm


def _tile(lat, lon, zoom):
    n = 2**zoom
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _vista(lat, lon, zoom, ancho_t=4.0, alto_t=2.5):
    cx, cy = _tile(lat, lon, zoom)
    return (cx - ancho_t / 2, cy - alto_t / 2), (cx + ancho_t / 2, cy + alto_t / 2)


def test_lima_zoom_12_sin_ajuste():
    sup, inf = _vista(-12.0464, -77.0428, 12, ancho_t=4.4, alto_t=2.7)
    assert lm.ajuste_vista(sup, inf, 12) == (0, 0)


def test_vista_al_oeste_vuelve_al_borde():
    sup, inf = _vista(-12.0, -90.0, 8, ancho_t=3, alto_t=2)
    dx, dy = lm.ajuste_vista(sup, inf, 8)
    assert dx > 0 and dy == 0
    assert math.isclose(sup[0] + dx, _tile(0, lm.PERU_BBOX[1], 8)[0])


def test_vista_al_este_vuelve_al_borde():
    sup, inf = _vista(-12.0, -60.0, 8, ancho_t=3, alto_t=2)
    dx, dy = lm.ajuste_vista(sup, inf, 8)
    assert dx < 0 and dy == 0
    assert math.isclose(inf[0] + dx, _tile(0, lm.PERU_BBOX[3], 8)[0])


def test_vista_al_norte_y_al_sur():
    sup, inf = _vista(8.0, -77.0, 8, ancho_t=2, alto_t=1.5)
    assert lm.ajuste_vista(sup, inf, 8)[1] > 0
    sup, inf = _vista(-30.0, -77.0, 8, ancho_t=2, alto_t=1.5)
    assert lm.ajuste_vista(sup, inf, 8)[1] < 0


def test_vista_mas_grande_que_peru_queda_centrada():
    z = 5
    x0, y0 = _tile(lm.PERU_BBOX[0], lm.PERU_BBOX[1], z)
    x1, y1 = _tile(lm.PERU_BBOX[2], lm.PERU_BBOX[3], z)
    ancho, alto = (x1 - x0) * 1.5, (y1 - y0) * 1.5
    sup = (x0 - 3.0, y0 + 2.0)
    inf = (sup[0] + ancho, sup[1] + alto)
    dx, dy = lm.ajuste_vista(sup, inf, z)
    assert math.isclose((sup[0] + inf[0]) / 2 + dx, (x0 + x1) / 2)
    assert math.isclose((sup[1] + inf[1]) / 2 + dy, (y0 + y1) / 2)


def test_zoom_minimo_definido():
    assert lm.ZOOM_MIN_PERU == 5
