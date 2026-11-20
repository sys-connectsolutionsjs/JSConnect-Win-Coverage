"""Actualizacion obligatoria al abrir el agente: flujo de la ventana principal sin Tk."""

import pytest

from validator_app.gui import main_window

App = main_window.App

INFO = {
    "tag": "v2026.11.20",
    "commit": "nuevo",
    "notes": "",
    "url_descarga": "https://github.com/o/r/releases/download/v1/JSConnect-Win-Coverage.exe",
    "nombre_asset": "JSConnect-Win-Coverage.exe",
}


class _Etiqueta:
    def __init__(self):
        self.texto = ""

    def config(self, text=""):
        self.texto = text


_CREADOS: list = []


class _HiloFalso:
    def __init__(self, target=None, args=(), daemon=None):
        self.target = target
        self.args = args
        self.iniciado = False
        _CREADOS.append(self)

    def start(self):
        self.iniciado = True


class _AppFalsa:
    """Registra lo que la ventana haria; `after` ejecuta al instante."""

    def __init__(self):
        self.eventos = []
        self.lbl_estado = _Etiqueta()
        self._proxy_client = object()

    def after(self, ms, funcion=None, *args):
        if funcion is not None:
            funcion(*args)

    def _verificar_activacion(self):
        self.eventos.append("activacion")

    def _abrir_progreso_actualizacion(self, texto=None, titulo=None):
        self.eventos.append(("abrir", texto))

    def _cerrar_progreso_actualizacion(self):
        self.eventos.append("cerrar")

    def _actualizacion_lista(self):
        self.eventos.append("lista")

    def _resultado_chequeo_inicio(self, estado, info):
        self.eventos.append(("resultado", estado, info))

    def _aplicar_update_hilo(self, info, continuar_al_fallar=False):
        self.eventos.append(("aplicar", info, continuar_al_fallar))

    def _chequeo_inicio_hilo(self):
        self.eventos.append("chequeo")


@pytest.fixture(autouse=True)
def hilos(monkeypatch):
    _CREADOS.clear()
    monkeypatch.setattr(main_window.threading, "Thread", _HiloFalso)
    return _CREADOS


@pytest.mark.parametrize(
    ("estado", "accion"),
    [
        ("actualizar", "instalar"),
        ("sin_conexion", "avisar"),
        ("al_dia", "continuar"),
        ("dev", "continuar"),
        ("lo-que-sea", "continuar"),
    ],
)
def test_accion_inicio(estado, accion):
    assert main_window.accion_inicio(estado) == accion


def test_inicio_en_desarrollo_va_directo_a_la_activacion(monkeypatch, hilos):
    monkeypatch.setattr(main_window.update_check, "es_build_real", lambda: False)
    app = _AppFalsa()

    App._inicio(app)

    assert app.eventos == ["activacion"]
    assert hilos == []


def test_inicio_en_exe_real_busca_antes_de_activar(monkeypatch, hilos):
    monkeypatch.setattr(main_window.update_check, "es_build_real", lambda: True)
    app = _AppFalsa()

    App._inicio(app)

    assert app.eventos == [("abrir", "Buscando actualizaciones...")]
    assert len(hilos) == 1
    assert hilos[0].iniciado
    assert hilos[0].target == app._chequeo_inicio_hilo


def test_hilo_de_chequeo_usa_el_proxy_de_la_ventana(monkeypatch):
    vistos = []

    def chequeo(proxy):
        vistos.append(proxy)
        return "actualizar", INFO

    monkeypatch.setattr(main_window.update_check, "chequeo_inicio", chequeo)
    app = _AppFalsa()

    App._chequeo_inicio_hilo(app)

    assert vistos == [app._proxy_client]
    assert app.eventos == [("resultado", "actualizar", INFO)]


def test_hilo_de_chequeo_trata_un_error_inesperado_como_sin_conexion(monkeypatch):
    def chequeo(proxy):
        raise RuntimeError("fallo raro")

    monkeypatch.setattr(main_window.update_check, "chequeo_inicio", chequeo)
    app = _AppFalsa()

    App._chequeo_inicio_hilo(app)

    assert app.eventos == [("resultado", "sin_conexion", None)]


def test_resultado_actualizar_instala_sin_preguntar_y_no_activa_todavia(hilos):
    app = _AppFalsa()

    App._resultado_chequeo_inicio(app, "actualizar", INFO)

    assert app.eventos[0] == "cerrar"
    assert app.eventos[1][0] == "abrir"
    assert "v2026.11.20" in app.eventos[1][1]
    assert "activacion" not in app.eventos
    assert len(hilos) == 1
    assert hilos[0].iniciado
    assert hilos[0].target == app._aplicar_update_hilo
    assert hilos[0].args == (INFO, True)


def test_resultado_al_dia_sigue_con_la_activacion(hilos):
    app = _AppFalsa()

    App._resultado_chequeo_inicio(app, "al_dia", None)

    assert app.eventos == ["cerrar", "activacion"]
    assert hilos == []


def test_resultado_sin_conexion_avisa_y_deja_entrar(hilos):
    app = _AppFalsa()

    App._resultado_chequeo_inicio(app, "sin_conexion", None)

    assert app.eventos == ["cerrar", "activacion"]
    assert "no se pudo comprobar" in app.lbl_estado.texto
    assert hilos == []


def test_instalacion_fallida_en_el_inicio_avisa_y_deja_entrar(monkeypatch):
    def falla(info):
        raise ValueError("Checksum no coincide")

    errores = []
    monkeypatch.setattr(main_window.download, "aplicar_actualizacion", falla)
    monkeypatch.setattr(main_window.messagebox, "showerror", lambda t, m: errores.append(m))
    app = _AppFalsa()

    App._aplicar_update_hilo(app, INFO, True)

    assert errores == ["Checksum no coincide"]
    assert app.eventos == ["cerrar", "activacion"]


def test_instalacion_fallida_desde_el_menu_no_dispara_la_activacion(monkeypatch):
    def falla(info):
        raise ValueError("Checksum no coincide")

    monkeypatch.setattr(main_window.download, "aplicar_actualizacion", falla)
    monkeypatch.setattr(main_window.messagebox, "showerror", lambda t, m: None)
    app = _AppFalsa()

    App._aplicar_update_hilo(app, INFO)

    assert "activacion" not in app.eventos


def test_instalacion_correcta_cierra_la_app_y_no_activa(monkeypatch):
    monkeypatch.setattr(main_window.download, "aplicar_actualizacion", lambda info: True)
    app = _AppFalsa()

    App._aplicar_update_hilo(app, INFO, True)

    assert app.eventos == ["lista"]
