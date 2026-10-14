"""Panel lateral del Mapa: su barra de desplazamiento no debe aparecer/desaparecer."""

import pytest

from validator_app.gui import map_page


@pytest.fixture
def pagina():
    ttk = pytest.importorskip("ttkbootstrap")
    try:
        raiz = ttk.Window(themename="cosmo")
    except Exception as exc:  # sin pantalla disponible
        pytest.skip(f"Tk no disponible: {exc}")
    raiz.geometry("1120x700")
    raiz.attributes("-alpha", 0)
    pagina = map_page.MapaPage(raiz, lambda: None, lambda: {}, lambda v: None, lambda o: o)
    pagina.pack(fill="both", expand=True)
    raiz.update()
    yield pagina
    raiz.destroy()


def test_la_barra_del_panel_no_se_oculta_nunca(pagina):
    panel = pagina.panel_lateral
    assert panel._auto_hide is False
    assert panel._vbar.winfo_ismapped()


def test_salir_del_panel_no_cambia_el_ancho_del_contenido(pagina):
    panel = pagina.panel_lateral
    antes = panel.winfo_width()
    panel._on_leave(None)
    pagina.update()
    assert panel._vbar.winfo_ismapped()
    assert panel.winfo_width() == antes
    panel._on_enter(None)
    pagina.update()
    assert panel.winfo_width() == antes


def test_el_contenido_conserva_su_ancho_completo(pagina):
    # La barra ocupa su propio espacio: el contenido sigue midiendo ANCHO_LATERAL.
    assert pagina.panel_lateral.winfo_width() >= map_page.ANCHO_LATERAL - 4
