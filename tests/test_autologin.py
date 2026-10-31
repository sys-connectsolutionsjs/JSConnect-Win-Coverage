"""Tests del autologin desatendido del proxy (plan Proxy 24/7, 2026-10-28).

`FrenoAutologin` es logica pura (reloj inyectable). `login_automatico` se prueba
con un navegador falso que simula las pantallas reales: formulario de WinForce,
puerta de acceso y SSO de Microsoft. El login real (Playwright) no corre en CI.
"""

from pathlib import Path
from typing import ClassVar

import pytest

from validator_app.proxy import autologin


class Reloj:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def avanzar(self, s: float) -> None:
        self.t += s


def _freno(reloj: Reloj, **kw) -> autologin.FrenoAutologin:
    return autologin.FrenoAutologin(reloj=reloj, **kw)


# --------------------------------------------------------------------------
# FrenoAutologin
# --------------------------------------------------------------------------

def test_freno_permite_el_primer_intento():
    f = _freno(Reloj())
    assert f.puede_intentar() == (True, "")


def test_freno_espera_escalonada_tras_fallos():
    r = Reloj()
    f = _freno(r, esperas=(0, 120, 600, 1800))

    f.registrar_intento()
    f.registrar_fallo()
    assert f.puede_intentar() == (False, "esperando")
    assert f.espera_restante() == 120
    r.avanzar(120)
    assert f.puede_intentar() == (True, "")

    f.registrar_intento()
    f.registrar_fallo()
    assert f.espera_restante() == 600
    r.avanzar(600)
    f.registrar_intento()
    f.registrar_fallo()
    assert f.espera_restante() == 1800
    r.avanzar(1800)
    f.registrar_intento()
    f.registrar_fallo()
    assert f.espera_restante() == 1800


def test_freno_exito_reinicia_la_espera():
    r = Reloj()
    f = _freno(r)
    f.registrar_intento()
    f.registrar_fallo()
    r.avanzar(120)
    f.registrar_intento()
    f.registrar_exito()
    assert f.puede_intentar() == (True, "")
    assert f.espera_restante() == 0


def test_freno_tope_por_hora():
    r = Reloj()
    f = _freno(r, max_por_hora=3)
    for _ in range(3):
        assert f.puede_intentar()[0]
        f.registrar_intento()
        f.registrar_exito()
        r.avanzar(60)
    assert f.puede_intentar() == (False, "tope_por_hora")
    r.avanzar(3600)
    assert f.puede_intentar() == (True, "")


def test_freno_dos_muertes_rapidas_seguidas_pausan():
    r = Reloj()
    f = _freno(r, muerte_rapida_s=600, pausa_s=1800)

    f.registrar_intento()
    f.registrar_exito()
    r.avanzar(100)
    assert f.registrar_muerte() is False

    f.registrar_intento()
    f.registrar_exito()
    r.avanzar(100)
    assert f.registrar_muerte() is True
    assert f.puede_intentar() == (False, "pausado")

    assert f.estado()["pausado_hasta"] is not None

    r.avanzar(1800)
    assert f.puede_intentar() == (True, "")
    assert f.estado()["pausado_hasta"] is None


def test_freno_una_muerte_lenta_reinicia_el_contador_de_muertes_rapidas():
    r = Reloj()
    f = _freno(r, muerte_rapida_s=600)

    f.registrar_intento()
    f.registrar_exito()
    r.avanzar(100)
    assert f.registrar_muerte() is False

    f.registrar_intento()
    f.registrar_exito()
    r.avanzar(5000)
    assert f.registrar_muerte() is False

    f.registrar_intento()
    f.registrar_exito()
    r.avanzar(100)
    assert f.registrar_muerte() is False
    assert f.puede_intentar() == (True, "")


def test_freno_muerte_sin_autologin_previo_no_cuenta_como_rapida():
    f = _freno(Reloj())
    assert f.registrar_muerte() is False
    assert f.registrar_muerte() is False
    assert f.puede_intentar() == (True, "")


def test_freno_credencial_invalida_desactiva_hasta_reactivar():
    r = Reloj()
    f = _freno(r)
    f.registrar_intento()
    f.registrar_credencial_invalida()
    assert f.puede_intentar() == (False, "credencial_invalida")
    r.avanzar(10**6)
    assert f.puede_intentar() == (False, "credencial_invalida")

    f.reactivar()
    assert f.puede_intentar() == (True, "")


def test_freno_navegador_rechazado_detiene_hasta_reactivar():
    r = Reloj()
    f = _freno(r)
    f.registrar_intento()
    f.registrar_navegador_rechazado()
    assert f.puede_intentar() == (False, "navegador_rechazado")
    r.avanzar(10**6)
    assert f.puede_intentar() == (False, "navegador_rechazado")

    est = f.estado()
    assert est["habilitado"] is False
    assert est["motivo"] == "navegador_rechazado"
    assert est["ultimo_resultado"] == "navegador_rechazado"

    f.reactivar()
    assert f.puede_intentar() == (True, "")


def test_freno_reactivar_limpia_pausa_y_espera():
    r = Reloj()
    f = _freno(r)
    f.registrar_intento()
    f.registrar_fallo()
    f._pausado_hasta = r() + 1800
    f.reactivar()
    assert f.puede_intentar() == (True, "")


def test_freno_estado_expone_lo_necesario():
    r = Reloj()
    f = _freno(r)
    est = f.estado()
    assert est["habilitado"] is True
    assert est["ultimo_intento"] is None
    assert est["ultimo_resultado"] is None
    assert est["pausado_hasta"] is None
    assert est["motivo"] == ""

    f.registrar_intento()
    f.registrar_fallo()
    est = f.estado()
    assert est["ultimo_intento"] is not None
    assert est["ultimo_resultado"] == "fallo"
    assert est["motivo"] == "esperando"

    f.registrar_credencial_invalida()
    est = f.estado()
    assert est["habilitado"] is False
    assert est["ultimo_resultado"] == "credencial_invalida"


@pytest.mark.parametrize("resultado", ["ok", "fallo", "credencial_invalida"])
def test_freno_estado_no_falla_en_ningun_resultado(resultado):
    f = _freno(Reloj())
    f.registrar_intento()
    {"ok": f.registrar_exito, "fallo": f.registrar_fallo,
     "credencial_invalida": f.registrar_credencial_invalida}[resultado]()
    assert f.estado()["ultimo_resultado"] == resultado


# --------------------------------------------------------------------------
# login_automatico (navegador falso: maquina de estados de las pantallas)
# --------------------------------------------------------------------------

_COOKIE_WF = {"name": "PHPSESSID", "value": "php-ok", "domain": "appwinforce.win.pe"}


class FakePage:
    """Simula el formulario de WinForce, la puerta de acceso y el SSO de Microsoft.

    `pantallas` es la secuencia que se recorre: cada `click` avanza a la
    siguiente. "listo" pone la cookie de WinForce en el contexto."""

    VISIBLES: ClassVar[dict[str, set[str]]] = {
        "form": {"#username", "#password", "#ingresar"},
        "form_error": {"#username", "#password", "#ingresar", ".swal2-popup.swal2-icon-error"},
        "form_aviso": {"#username", "#password", "#ingresar", ".swal2-popup.swal2-icon-warning"},
        "puerta": {"button.login-button.azure", "button.login-button.google"},
        # La pantalla del correo trae un campo de contrasena oculto (.moveOffScreen) que
        # Playwright da por visible: solo un selector que lo excluya evita confundirlo.
        "usuario": {"input[name=loginfmt]", "input[name=passwd]"},
        "password": {"input[name=passwd]:not(.moveOffScreen)"},
        "kmsi": {"#KmsiCheckboxField"},
        "vacio_aviso": {"input[name=loginfmt]", "#usernameError"},
        "error_password": {"input[name=passwd]:not(.moveOffScreen)", "#passwordError"},
        "error_usuario": {"input[name=loginfmt]", "#usernameError"},
        "colgado": set(),
        "listo": set(),
    }

    def __init__(self, context, pantallas):
        self.context = context
        self.pantallas = list(pantallas)
        self.i = 0
        self.llenados: list[tuple[str, str]] = []
        self.clicks: list[str] = []
        self.main_frame = type("Frame", (), {"url": ""})()
        self.manejador = lambda frame: None
        self.capturas: list[str] = []
        self.visitado = None
        self.respuesta = None
        self.aviso = ""
        self._aplicar()

    @property
    def actual(self):
        return self.pantallas[self.i]

    def _aplicar(self):
        if self.actual == "listo":
            self.context.cookies_actuales = [_COOKIE_WF]

    def goto(self, url):
        self.visitado = url
        return self.respuesta

    def is_visible(self, selector):
        return selector in self.VISIBLES[self.actual]

    def on(self, evento, manejador):
        self.manejador = manejador

    def navegar(self, url):
        self.main_frame.url = url
        self.manejador(self.main_frame)

    def inner_text(self, selector):
        return self.aviso

    def input_value(self, selector):
        return "" if self.actual in ("usuario", "vacio_aviso") else "x"

    def fill(self, selector, valor):
        self.llenados.append((selector, valor))

    def click(self, selector):
        self.clicks.append(selector)
        if self.i < len(self.pantallas) - 1 and "error" not in self.actual:
            self.i += 1
            self._aplicar()

    def screenshot(self, path):
        self.capturas.append(str(path))
        Path(path).write_bytes(b"png")


class FakeContext:
    def __init__(self, pantallas, cookies=None):
        self.cookies_actuales = list(cookies or [])
        self.pages = []
        self.page = FakePage(self, pantallas)
        self.pages.append(self.page)
        self.cerrado = False
        self.lanzado_con: dict = {}

    def cookies(self):
        return list(self.cookies_actuales)

    def new_page(self):
        return self.page

    def close(self):
        self.cerrado = True


def _fake_playwright(ctx):
    class _Chromium:
        def launch_persistent_context(self, **kw):
            ctx.lanzado_con = kw
            return ctx

    class _P:
        chromium = _Chromium()

    class _CM:
        def __enter__(self):
            return _P()

        def __exit__(self, *a):
            return False

    return lambda: _CM()


class RelojMono:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.t += s


@pytest.fixture
def cookie_valida(monkeypatch):
    from validator_app.core import api as core_api

    llamadas = []
    monkeypatch.setattr(core_api, "validar_cookie_sesion", lambda php: llamadas.append(php))
    return llamadas


def _login(ctx, tmp_path, **kw):
    reloj = RelojMono()
    return autologin.login_automatico(
        "proxy@empresa.pe",
        "secreta",
        playwright=_fake_playwright(ctx),
        perfil=tmp_path / "perfil",
        captura=tmp_path / "fallo.png",
        reloj=reloj,
        dormir=reloj.dormir,
        **kw,
    )


def test_login_sso_silencioso_no_llena_nada(tmp_path, cookie_valida):
    ctx = FakeContext(["listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert ctx.page.llenados == []
    assert cookie_valida == ["php-ok"]
    assert ctx.cerrado is True
    assert ctx.page.visitado == autologin.login_asistido.LOGIN_URL


def test_login_flujo_completo_usuario_password_kmsi(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario", "password", "kmsi", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert ctx.page.llenados == [
        ("input[name=loginfmt]", "proxy@empresa.pe"),
        ("input[name=passwd]:not(.moveOffScreen)", "secreta"),
    ]
    assert ctx.page.clicks == ["#idSIButton9"] * 3


def test_login_empieza_por_el_formulario_de_winforce(tmp_path, cookie_valida):
    ctx = FakeContext(["form", "password", "kmsi", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert ctx.page.llenados == [
        ("#username", "proxy@empresa.pe"),
        ("#password", "secreta"),
        ("input[name=passwd]:not(.moveOffScreen)", "secreta"),
    ]
    assert ctx.page.clicks == ["#ingresar", "#idSIButton9", "#idSIButton9"]


def test_login_formulario_mas_sso_silencioso_de_microsoft(tmp_path, cookie_valida):
    ctx = FakeContext(["form", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert ctx.page.clicks == ["#ingresar"]


def test_login_flujo_completo_pasa_por_la_puerta_de_microsoft(tmp_path, cookie_valida):
    ctx = FakeContext(["form", "puerta", "usuario", "password", "kmsi", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert ctx.page.clicks == [
        "#ingresar",
        "button.login-button.azure",
        "#idSIButton9",
        "#idSIButton9",
        "#idSIButton9",
    ]
    assert ctx.page.llenados == [
        ("#username", "proxy@empresa.pe"),
        ("#password", "secreta"),
        ("input[name=loginfmt]", "proxy@empresa.pe"),
        ("input[name=passwd]:not(.moveOffScreen)", "secreta"),
    ]


def test_login_puerta_con_sso_silencioso_no_llena_microsoft(tmp_path, cookie_valida):
    ctx = FakeContext(["form", "puerta", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert ctx.page.clicks == ["#ingresar", "button.login-button.azure"]
    assert ctx.page.llenados == [("#username", "proxy@empresa.pe"), ("#password", "secreta")]


def test_login_pulsa_la_puerta_una_sola_vez(tmp_path, cookie_valida):
    ctx = FakeContext(["puerta", "puerta", "colgado"])
    ctx.page.click = lambda sel: ctx.page.clicks.append(sel)
    with pytest.raises(autologin.AutologinError):
        _login(ctx, tmp_path, timeout_s=10)
    assert ctx.page.clicks == ["button.login-button.azure"]


def test_login_envia_el_formulario_una_sola_vez(tmp_path, cookie_valida):
    ctx = FakeContext(["form", "form", "colgado"])
    ctx.page.click = lambda sel: ctx.page.clicks.append(sel)
    with pytest.raises(autologin.AutologinError):
        _login(ctx, tmp_path, timeout_s=10)
    assert ctx.page.clicks == ["#ingresar"]


@pytest.mark.parametrize("pantalla", ["form_error", "form_aviso"])
def test_login_rechazo_de_winforce_no_reintenta(tmp_path, cookie_valida, pantalla):
    ctx = FakeContext(["form", pantalla])
    ctx.page.aviso = "Usuario  o\ncontrasena incorrectos"
    with pytest.raises(autologin.CredencialInvalidaError) as exc:
        _login(ctx, tmp_path)
    assert "Usuario o contrasena incorrectos" in str(exc.value)
    assert ctx.page.clicks == ["#ingresar"]
    assert ctx.cerrado is True


def test_login_winforce_deniega_el_navegador(tmp_path, cookie_valida):
    class Respuesta:
        status = 410

    ctx = FakeContext(["colgado"])
    ctx.page.respuesta = Respuesta()
    with pytest.raises(autologin.NavegadorRechazadoError) as exc:
        _login(ctx, tmp_path)
    assert isinstance(exc.value, autologin.AutologinError)
    assert not isinstance(exc.value, autologin.CredencialInvalidaError)
    assert "410" in str(exc.value)
    assert ctx.page.capturas == [str(tmp_path / "fallo.png")]
    assert ctx.cerrado is True


def test_login_usa_perfil_propio_y_navegador_normal(tmp_path, cookie_valida):
    ctx = FakeContext(["listo"])
    _login(ctx, tmp_path)
    assert ctx.lanzado_con["user_data_dir"] == str(tmp_path / "perfil")
    assert ctx.lanzado_con["headless"] is False


def test_login_password_incorrecta_no_reintenta(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario", "error_password"])
    with pytest.raises(autologin.CredencialInvalidaError):
        _login(ctx, tmp_path)
    assert ctx.page.llenados == [("input[name=loginfmt]", "proxy@empresa.pe")]
    assert ctx.cerrado is True


def test_login_usuario_inexistente_es_credencial_invalida(tmp_path, cookie_valida):
    ctx = FakeContext(["error_usuario"])
    with pytest.raises(autologin.CredencialInvalidaError):
        _login(ctx, tmp_path)


def _correos(ctx):
    return [v for sel, v in ctx.page.llenados if sel == "input[name=loginfmt]"]


def _passwords(ctx):
    return [v for sel, v in ctx.page.llenados if sel == "input[name=passwd]:not(.moveOffScreen)"]


def test_login_aviso_con_correo_vacio_no_es_credencial_invalida(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario", "vacio_aviso", "password", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert len(_correos(ctx)) == 2
    assert len(_passwords(ctx)) == 1


def test_login_recarga_silenciosa_reescribe_el_correo(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario", "usuario", "password", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert len(_correos(ctx)) == 2


def test_login_tope_de_envios_del_correo_no_apaga_el_autologin(tmp_path, cookie_valida):
    ctx = FakeContext(["vacio_aviso"])
    ctx.page.click = lambda sel: ctx.page.clicks.append(sel)
    with pytest.raises(autologin.AutologinError) as exc:
        _login(ctx, tmp_path, timeout_s=30)
    assert type(exc.value) is autologin.AutologinError
    assert len(_correos(ctx)) == 3


def test_login_aviso_persistente_con_correo_escrito_es_credencial_invalida(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario", "error_usuario"])
    with pytest.raises(autologin.CredencialInvalidaError):
        _login(ctx, tmp_path)
    assert len(_correos(ctx)) == 1


def test_login_campo_de_correo_ya_lleno_tambien_se_envia(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario", "password", "listo"])
    ctx.page.input_value = lambda sel: "precargado@empresa.pe"
    assert _login(ctx, tmp_path) == "php-ok"
    assert len(_correos(ctx)) == 1


def test_login_no_confunde_el_campo_oculto_con_la_password(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario", "password", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert [sel for sel, _ in ctx.page.llenados] == [
        "input[name=loginfmt]",
        "input[name=passwd]:not(.moveOffScreen)",
    ]


def test_traza_registra_pasos_con_imagen_y_sin_secretos(tmp_path, cookie_valida):
    ctx = FakeContext(["form", "puerta", "usuario", "password", "listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    carpeta = tmp_path / "autologin_pasos"
    texto = (carpeta / "traza.txt").read_text(encoding="utf-8")
    assert [p.name for p in sorted(carpeta.glob("*.png"))] == [
        "01-formulario.png", "02-puerta.png", "03-correo.png", "04-password.png",
    ]
    assert "formulario" in texto and "password" in texto
    assert "secreta" not in texto
    assert "proxy@empresa.pe" not in texto


def test_traza_se_reinicia_en_cada_intento(tmp_path, cookie_valida):
    carpeta = tmp_path / "autologin_pasos"
    carpeta.mkdir()
    (carpeta / "99-viejo.png").write_bytes(b"x")
    (carpeta / "traza.txt").write_text("viejo", encoding="utf-8")
    _login(FakeContext(["listo"]), tmp_path)
    assert not (carpeta / "99-viejo.png").exists()
    assert "viejo" not in (carpeta / "traza.txt").read_text(encoding="utf-8")


def test_traza_anota_navegaciones_sin_parametros(tmp_path, cookie_valida):
    ctx = FakeContext(["listo"])
    _login(ctx, tmp_path)
    ctx.page.navegar("https://login.microsoftonline.com/common/oauth2?code=SECRETO&sso_reload=true")
    texto = (tmp_path / "autologin_pasos" / "traza.txt").read_text(encoding="utf-8")
    assert "login.microsoftonline.com/common/oauth2" in texto
    assert "sso_reload" in texto
    assert "SECRETO" not in texto


def test_login_envia_la_password_una_sola_vez(tmp_path, cookie_valida):
    ctx = FakeContext(["password", "password", "colgado"])
    ctx.page.click = lambda sel: ctx.page.clicks.append(sel)
    with pytest.raises(autologin.AutologinError):
        _login(ctx, tmp_path, timeout_s=10)
    assert ctx.page.llenados.count(("input[name=passwd]:not(.moveOffScreen)", "secreta")) == 1


def test_login_timeout_guarda_captura(tmp_path, cookie_valida):
    ctx = FakeContext(["colgado"])
    with pytest.raises(autologin.AutologinError) as exc:
        _login(ctx, tmp_path, timeout_s=5)
    assert ctx.page.capturas == [str(tmp_path / "fallo.png")]
    assert str(tmp_path / "fallos") in str(exc.value)
    assert ctx.cerrado is True


@pytest.mark.parametrize(
    ("pantallas", "tipo"),
    [
        (["usuario", "error_password"], autologin.CredencialInvalidaError),
        (["error_usuario"], autologin.CredencialInvalidaError),
        (["form", "form_error"], autologin.CredencialInvalidaError),
        (["colgado"], autologin.AutologinError),
    ],
)
def test_login_cada_fallo_deja_captura_y_conserva_el_tipo(tmp_path, cookie_valida, pantallas, tipo):
    ctx = FakeContext(pantallas)
    with pytest.raises(autologin.AutologinError) as exc:
        _login(ctx, tmp_path, timeout_s=5)
    assert type(exc.value) is tipo
    assert (tmp_path / "fallo.png").exists()
    copias = list((tmp_path / "fallos").glob("*.png"))
    assert len(copias) == 1
    assert str(copias[0]) in str(exc.value)


def test_login_error_inesperado_deja_captura(tmp_path, cookie_valida):
    ctx = FakeContext(["usuario"])

    def falla(selector, valor):
        raise RuntimeError("Target closed\nllamada larga de Playwright")

    ctx.page.fill = falla
    with pytest.raises(autologin.AutologinError) as exc:
        _login(ctx, tmp_path)
    assert "Target closed" in str(exc.value)
    assert "llamada larga" not in str(exc.value)
    assert str(tmp_path / "fallos") in str(exc.value)
    assert ctx.cerrado is True


def test_login_si_la_captura_falla_sale_el_error_original(tmp_path, cookie_valida):
    ctx = FakeContext(["error_usuario"])

    def falla(path):
        raise RuntimeError("sin pantalla")

    ctx.page.screenshot = falla
    with pytest.raises(autologin.CredencialInvalidaError) as exc:
        _login(ctx, tmp_path)
    assert "Captura" not in str(exc.value)
    assert ctx.cerrado is True


def test_login_incluye_el_texto_de_microsoft(tmp_path, cookie_valida):
    ctx = FakeContext(["error_password"])
    ctx.page.aviso = "La cuenta o la\ncontrasena son incorrectas"
    with pytest.raises(autologin.CredencialInvalidaError) as exc:
        _login(ctx, tmp_path)
    assert "La cuenta o la contrasena son incorrectas" in str(exc.value)


def test_guardar_captura_conserva_las_20_mas_recientes(tmp_path):
    historial = tmp_path / "fallos"
    historial.mkdir()
    for i in range(25):
        (historial / f"20260101-0000{i:02d}.png").write_bytes(b"x")

    ctx = FakeContext(["colgado"])
    copia = autologin._guardar_captura(ctx.page, tmp_path / "fallo.png")

    restantes = sorted(historial.glob("*.png"))
    assert len(restantes) == 20
    assert copia == restantes[-1]
    assert not (historial / "20260101-000000.png").exists()


def test_login_cookie_aun_no_autenticada_sigue_esperando(tmp_path, monkeypatch):
    from validator_app.core import api as core_api

    intentos = []

    def validar(php):
        intentos.append(php)
        if len(intentos) < 3:
            raise core_api.LoginError("aun no", "ERR_LOGIN_SESSION")

    monkeypatch.setattr(core_api, "validar_cookie_sesion", validar)
    ctx = FakeContext(["listo"])
    assert _login(ctx, tmp_path) == "php-ok"
    assert len(intentos) == 3


def test_login_sin_playwright_da_error_claro(tmp_path, monkeypatch):
    monkeypatch.setattr(
        autologin, "_import_sync_playwright", lambda: (_ for _ in ()).throw(ImportError("x"))
    )
    with pytest.raises(autologin.AutologinError) as exc:
        autologin.login_automatico("u", "p", perfil=tmp_path, captura=tmp_path / "f.png")
    assert "playwright" in str(exc.value).lower()


def test_credencial_invalida_es_un_autologin_error():
    assert issubclass(autologin.CredencialInvalidaError, autologin.AutologinError)


# --------------------------------------------------------------------------
# CLI --probar
# --------------------------------------------------------------------------

def test_cli_probar_usa_ventana_y_perfil_temporal(monkeypatch, capsys):
    vistos = {}

    def fake_login(usuario, password, timeout_s, headless, perfil):
        vistos.update(usuario=usuario, password=password, headless=headless, perfil=perfil)
        return "x" * 26

    monkeypatch.setattr(autologin, "login_automatico", fake_login)
    monkeypatch.setattr("builtins.input", lambda _msg: "proxy@empresa.pe")
    monkeypatch.setattr(autologin.getpass, "getpass", lambda _msg: "secreta")

    assert autologin.main(["--probar"]) == 0
    assert vistos["headless"] is False
    assert Path(vistos["perfil"]) != autologin.PERFIL_SERVICIO
    salida = capsys.readouterr().out
    assert "[OK]" in salida
    assert "x" * 26 not in salida
    assert "secreta" not in salida


def test_cli_probar_credencial_invalida_devuelve_1(monkeypatch, capsys):
    def fake_login(*a, **kw):
        raise autologin.CredencialInvalidaError("rechazada")

    monkeypatch.setattr(autologin, "login_automatico", fake_login)
    monkeypatch.setattr("builtins.input", lambda _msg: "proxy@empresa.pe")
    monkeypatch.setattr(autologin.getpass, "getpass", lambda _msg: "mala")
    assert autologin.main(["--probar"]) == 1
    assert "Credencial invalida" in capsys.readouterr().out


def test_cli_sin_argumentos_muestra_ayuda():
    assert autologin.main([]) == 2


# --------------------------------------------------------------------------
# Frenado configurable (perfiles + personalizado)
# --------------------------------------------------------------------------

def test_freno_por_defecto_es_el_recomendado_0_1_2_3_5():
    r = Reloj()
    f = _freno(r)
    esperas = []
    for _ in range(6):
        f.registrar_intento()
        f.registrar_fallo()
        esperas.append(f.espera_restante())
        r.avanzar(f.espera_restante())
    assert esperas == [60, 120, 180, 300, 300, 300]
    assert f.pausa_s == 300


@pytest.mark.parametrize("minutos", [(1, 2, 3, 5), (5, 10, 15, 20), (1, 1, 1, 1), (3, 3, 15, 1)])
def test_validar_freno_acepta_valores_dentro_de_las_reglas(minutos):
    assert autologin.validar_freno(minutos) == minutos


@pytest.mark.parametrize(
    "minutos",
    [
        (0, 2, 3, 5),     # el 2.o va de 1 a 5
        (6, 6, 6, 6),
        (3, 2, 3, 5),     # el 3.o no puede ser menor que el 2.o
        (1, 11, 11, 5),   # el 3.o hasta 10
        (1, 5, 4, 5),     # el 4.o no puede ser menor que el 3.o
        (1, 2, 16, 5),    # el 4.o hasta 15
        (1, 2, 3, 0),     # el fijo va de 1 a 20
        (1, 2, 3, 21),
        (0.5, 1, 1, 1),   # nada de 30 s
        (1, 2, 3),        # faltan pasos
    ],
)
def test_validar_freno_rechaza_lo_que_rompe_las_reglas(minutos):
    with pytest.raises(ValueError):
        autologin.validar_freno(minutos)


def test_todos_los_perfiles_cumplen_las_reglas_y_tienen_nombre():
    assert autologin.PERFIL_RECOMENDADO in autologin.PERFILES_FRENO
    for clave, perfil in autologin.PERFILES_FRENO.items():
        assert autologin.validar_freno(perfil["minutos"]) == perfil["minutos"], clave
        assert perfil["nombre"]
    assert autologin.PERFILES_FRENO["recomendado"]["minutos"] == (1, 2, 3, 5)
    assert "no recomendado" in autologin.PERFILES_FRENO["demasiado_rapido"]["nombre"]
    assert "no recomendado" in autologin.PERFILES_FRENO["demasiado_lento"]["nombre"]
    assert autologin.PERFILES_FRENO["demasiado_rapido"]["aviso"]
    assert autologin.PERFILES_FRENO["demasiado_lento"]["aviso"]


def test_resolver_freno_perfil_ignora_minutos_y_personalizado_los_valida():
    assert autologin.resolver_freno("lento", [9, 9, 9, 9]) == ("lento", (3, 6, 10, 15))
    assert autologin.resolver_freno("personalizado", [2, 3, 4, 7]) == (
        "personalizado", (2, 3, 4, 7)
    )
    with pytest.raises(ValueError):
        autologin.resolver_freno("personalizado", [9, 9, 9, 9])
    with pytest.raises(ValueError):
        autologin.resolver_freno("inventado", [1, 2, 3, 5])


def test_esperas_de_pasa_a_segundos_con_el_primero_en_cero():
    assert autologin.esperas_de((1, 2, 3, 5)) == (0, 60, 120, 180, 300)


def test_tope_por_hora_cabe_el_perfil_mas_dos():
    # recomendado: intentos en los min 0, 1, 3, 6 y luego 11, 16, ... 56 -> 14
    assert autologin.tope_por_hora((0, 60, 120, 180, 300)) == 16
    assert autologin.tope_por_hora((0, 60, 60, 60, 60)) == 62


def test_configurar_cambia_esperas_pausa_y_tope_en_vivo():
    r = Reloj()
    f = _freno(r)
    f.configurar(autologin.esperas_de((5, 10, 15, 20)))
    assert f.pausa_s == 1200
    assert f.max_por_hora == autologin.tope_por_hora((0, 300, 600, 900, 1200))
    f.registrar_intento()
    f.registrar_fallo()
    assert f.espera_restante() == 300


def test_el_tope_no_corta_un_perfil_valido_en_la_primera_hora():
    r = Reloj()
    f = _freno(r)
    intentos = 0
    while r.t < 1_000_000.0 + 3600:
        ok, motivo = f.puede_intentar()
        if not ok:
            assert motivo == "esperando"
            r.avanzar(f.espera_restante())
            continue
        f.registrar_intento()
        f.registrar_fallo()
        intentos += 1
    assert intentos == 14
