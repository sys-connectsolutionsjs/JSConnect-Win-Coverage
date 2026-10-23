"""Tiles del mapa: OpenStreetMap bloquea el User-Agent fijo "TkinterMapView" (2026-10-23)."""

import pytest

from validator_app.core import direccion
from validator_app.gui import tiles

map_widget = pytest.importorskip("tkintermapview.map_widget")


@pytest.fixture
def get_falso(monkeypatch):
    llamadas = []

    def falso(url, *args, **kwargs):
        llamadas.append((url, kwargs))
        return "respuesta"

    monkeypatch.setattr(map_widget, "requests", map_widget.requests)
    monkeypatch.setattr(tiles.requests, "get", falso)
    return llamadas


def test_las_tiles_usan_el_user_agent_del_proyecto(get_falso):
    tiles.usar_user_agent_propio()
    resp = map_widget.requests.get(
        "https://a.tile.openstreetmap.org/12/1172/2178.png",
        stream=True,
        headers={"User-Agent": "TkinterMapView"},
    )
    assert resp == "respuesta"
    url, kwargs = get_falso[0]
    assert url.endswith("2178.png")
    assert kwargs["stream"] is True
    assert kwargs["headers"]["User-Agent"] == direccion.USER_AGENT


def test_aplicarlo_dos_veces_no_anida_envoltorios(get_falso):
    tiles.usar_user_agent_propio()
    primero = map_widget.requests
    tiles.usar_user_agent_propio()
    assert map_widget.requests is primero


def test_el_user_agent_no_es_el_bloqueado():
    assert "TkinterMapView" not in direccion.USER_AGENT
