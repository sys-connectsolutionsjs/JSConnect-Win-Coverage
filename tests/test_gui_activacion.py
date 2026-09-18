"""Comprobacion de activacion usada por la ventana principal (sin instanciar Tk)."""

from validator_app.gui import main_window

HUELLA = "3A05-5810-F921-AE0C"


def _guardado(monkeypatch, valor):
    monkeypatch.setattr(main_window.activation_state, "leer", lambda: valor)


def test_activacion_vigente_con_codigo_valido(monkeypatch):
    _guardado(monkeypatch, {"huella": HUELLA, "codigo": "abc"})
    monkeypatch.setattr(main_window.signer, "validar_codigo", lambda h, c: True)
    assert main_window.activacion_vigente(HUELLA) is True


def test_activacion_no_vigente_sin_estado_guardado(monkeypatch):
    _guardado(monkeypatch, None)
    assert main_window.activacion_vigente(HUELLA) is False


def test_activacion_no_vigente_si_la_huella_guardada_es_de_otra_pc(monkeypatch):
    _guardado(monkeypatch, {"huella": "0000-0000-0000-0000", "codigo": "abc"})
    monkeypatch.setattr(main_window.signer, "validar_codigo", lambda h, c: True)
    assert main_window.activacion_vigente(HUELLA) is False


def test_activacion_no_vigente_con_codigo_invalido(monkeypatch):
    _guardado(monkeypatch, {"huella": HUELLA, "codigo": "malo"})
    monkeypatch.setattr(main_window.signer, "validar_codigo", lambda h, c: False)
    assert main_window.activacion_vigente(HUELLA) is False
