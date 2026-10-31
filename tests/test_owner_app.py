"""Logica sin interfaz de la consola grafica del owner."""

import json

import pytest

from generator import owner_app


def test_normalizar_huella_acepta_formato_valido():
    assert owner_app.normalizar_huella(" 7f3a-9c21-d04e-b5a8 ") == "7F3A-9C21-D04E-B5A8"


def test_normalizar_huella_rechaza_valor_corto():
    with pytest.raises(ValueError, match="Huella"):
        owner_app.normalizar_huella("corta")


def test_normalizar_huella_rechaza_formato_largo_incorrecto():
    with pytest.raises(ValueError, match="Huella"):
        owner_app.normalizar_huella("ESTA-HUELLA-NO-ES-VALIDA")


def test_estado_servicio_interpreta_running():
    assert owner_app.estado_servicio("STATE              : 4  RUNNING") == "Servicio proxy: activo"


def test_estado_servicio_interpreta_stop():
    assert owner_app.estado_servicio("STATE              : 1  STOPPED") == (
        "Servicio proxy: detenido"
    )


def test_consultar_proxy_sin_permiso_sobre_config_usa_puerto_por_defecto(monkeypatch):
    import validator_app.proxy.config as config

    def sin_permiso(*args, **kwargs):
        raise PermissionError("config.yaml")

    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"logged_in": True, "session_alive": True}

    visitadas = []
    monkeypatch.setattr(config, "ProxyConfig", sin_permiso)
    monkeypatch.setattr(
        owner_app.httpx, "get", lambda url, timeout: visitadas.append(url) or Respuesta()
    )

    assert owner_app.consultar_proxy() == "Proxy: operativo; sesion WinForce viva"
    assert visitadas == ["http://127.0.0.1:8080/health"]


def test_consultar_proxy_config_invalida_usa_puerto_por_defecto(monkeypatch):
    """En el .exe empaquetado config.yaml no existe: ProxyConfig() lanza
    ValidationError. La consola debe consultar /health igualmente."""
    import validator_app.proxy.config as config

    def sin_tokens(*args, **kwargs):
        raise ValueError("proxy_token y admin_key son obligatorios")

    visitadas = []

    def sin_respuesta(url, timeout):
        visitadas.append(url)
        raise OSError("sin conexion")

    monkeypatch.setattr(config, "ProxyConfig", sin_tokens)
    monkeypatch.setattr(owner_app.httpx, "get", sin_respuesta)

    assert owner_app.consultar_proxy() == "Proxy: no responde localmente"
    assert visitadas == ["http://127.0.0.1:8080/health"]


def test_detectar_ip_lan_usa_socket_udp():
    class SocketFalso:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def connect(self, destino):
            pass

        def getsockname(self):
            return ("192.168.1.50", 12345)

    assert owner_app.detectar_ip_lan(socket_factory=lambda *a, **k: SocketFalso()) == "192.168.1.50"


def test_detectar_ip_lan_usa_respaldo_si_falla_el_socket():
    def socket_roto(*args, **kwargs):
        raise OSError("sin ruta por defecto")

    def resolver_falso(host, puerto, family):
        return [(None, None, None, None, ("192.168.1.77", 0))]

    ip = owner_app.detectar_ip_lan(socket_factory=socket_roto, resolver=resolver_falso)
    assert ip == "192.168.1.77"


def test_detectar_ip_lan_descarta_loopback_y_apipa():
    def socket_roto(*args, **kwargs):
        raise OSError("sin ruta por defecto")

    def resolver_falso(host, puerto, family):
        return [
            (None, None, None, None, ("127.0.0.1", 0)),
            (None, None, None, None, ("169.254.1.2", 0)),
            (None, None, None, None, ("192.168.1.77", 0)),
        ]

    ip = owner_app.detectar_ip_lan(socket_factory=socket_roto, resolver=resolver_falso)
    assert ip == "192.168.1.77"


def test_detectar_ip_lan_devuelve_none_si_no_hay_candidatas():
    def socket_roto(*args, **kwargs):
        raise OSError("sin ruta por defecto")

    def resolver_falso(host, puerto, family):
        return [(None, None, None, None, ("127.0.0.1", 0))]

    assert owner_app.detectar_ip_lan(socket_factory=socket_roto, resolver=resolver_falso) is None


def test_url_para_agentes_con_ip():
    assert owner_app.url_para_agentes("192.168.1.50", 8080) == "http://192.168.1.50:8080"


def test_url_para_agentes_sin_ip():
    assert owner_app.url_para_agentes(None, 8080) == ""


def test_puerto_proxy_local_usa_puerto_de_la_url(monkeypatch):
    monkeypatch.setattr(owner_app, "_url_proxy_local", lambda: "http://0.0.0.0:8090")
    assert owner_app.puerto_proxy_local() == 8090


def test_puerto_proxy_local_por_defecto(monkeypatch):
    monkeypatch.setattr(
        owner_app, "_url_proxy_local", lambda: owner_app.URL_PROXY_LOCAL_POR_DEFECTO
    )
    assert owner_app.puerto_proxy_local() == 8080


def test_ruta_extension_build_no_devuelve_una_carpeta_que_no_existe():
    """Bug 2026-10-28: se devolvia `<instalacion>\\.extension_build` aunque el
    instalador no la hubiera creado (sin Chrome no la creaba)."""
    from pathlib import Path

    ruta, aviso, preparable = owner_app.ruta_extension_build(
        ruta_instalacion=lambda: Path(r"C:\no-existe\validator_app\proxy")
    )
    assert ruta is None
    assert preparable is True
    assert r"C:\no-existe\validator_app\proxy\.extension_build" in aviso


def test_ruta_extension_build_sin_servicio_instalado():
    from validator_app.proxy import secretos

    def falla():
        raise secretos.SecretosError("servicio JSWinProxy no instalado")

    ruta, aviso, preparable = owner_app.ruta_extension_build(ruta_instalacion=falla)
    assert ruta is None
    assert preparable is False
    assert "install_service.bat" in aviso
    assert "no instalado" in aviso


def test_comando_reinicio_pide_elevacion_y_reinicia_el_servicio():
    comando = owner_app.comando_reinicio()
    assert comando[0] == "powershell"
    script = comando[-1]
    assert "-Verb RunAs" in script
    assert "Restart-Service JSWinProxy" in script


class _Resultado:
    def __init__(self, returncode):
        self.returncode = returncode


def test_reiniciar_servicio_ok():
    assert owner_app.reiniciar_servicio(lambda *a, **k: _Resultado(0)) == (
        True,
        "Servicio reiniciado.",
    )


def test_reiniciar_servicio_uac_cancelado():
    ok, mensaje = owner_app.reiniciar_servicio(
        lambda *a, **k: _Resultado(owner_app.CODIGO_UAC_CANCELADO)
    )
    assert ok is False
    assert "UAC" in mensaje


def test_reiniciar_servicio_fallo_dentro_de_la_sesion_elevada():
    ok, mensaje = owner_app.reiniciar_servicio(lambda *a, **k: _Resultado(1))
    assert ok is False
    assert "codigo 1" in mensaje


def test_reiniciar_servicio_no_lanza_si_powershell_no_existe():
    def sin_powershell(*a, **k):
        raise OSError("no existe")

    ok, mensaje = owner_app.reiniciar_servicio(sin_powershell)
    assert ok is False
    assert "PowerShell" in mensaje


def test_comando_propio_en_desarrollo():
    assert owner_app._comando_propio()[-2:] == ["-m", "generator.owner_app"]


def test_comando_propio_congelado(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert owner_app._comando_propio() == [sys.executable]


class _ResultadoElevado:
    def __init__(self, returncode):
        self.returncode = returncode


def _extraer_ruta_salida(script: str) -> str:
    """El ultimo elemento de -ArgumentList es la ruta de salida."""
    marca = "-ArgumentList "
    inicio = script.index(marca) + len(marca)
    fin = script.index(" -Verb RunAs", inicio)
    lista = script[inicio:fin]
    return lista.rstrip(",").rsplit(",", 1)[-1].strip("'")


def test_ejecutar_elevado_ok(monkeypatch, tmp_path):
    """El runner nunca escribe realmente (es PowerShell simulado): quien
    escribe el archivo temporal es el propio test, imitando lo que haria el
    subproceso elevado."""
    capturado = {}

    def runner(args, **kwargs):
        script = args[-1]
        capturado["script"] = script
        ruta = _extraer_ruta_salida(script)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"proxy_token": "x" * 64, "admin_key": "y" * 64}, f)
        return _ResultadoElevado(0)

    datos = owner_app._ejecutar_elevado(["--leer-secretos"], runner=runner)
    assert datos == {"proxy_token": "x" * 64, "admin_key": "y" * 64}
    assert "-Verb RunAs" in capturado["script"]
    assert "-RedirectStandardOutput" not in capturado["script"]


def test_ejecutar_elevado_uac_cancelado(monkeypatch):
    def runner(args, **kwargs):
        return _ResultadoElevado(owner_app.CODIGO_UAC_CANCELADO)

    with pytest.raises(RuntimeError, match="UAC"):
        owner_app._ejecutar_elevado(["--leer-secretos"], runner=runner)


def test_ejecutar_elevado_propaga_error_del_subcomando():
    def runner(args, **kwargs):
        script = args[-1]
        ruta = _extraer_ruta_salida(script)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"error": "No existe config.yaml"}, f)
        return _ResultadoElevado(0)

    with pytest.raises(RuntimeError, match="No existe config"):
        owner_app._ejecutar_elevado(["--leer-secretos"], runner=runner)


def test_ejecutar_elevado_borra_el_temporal_incluso_si_falla():
    ruta_capturada = {}

    def runner(args, **kwargs):
        script = args[-1]
        ruta_capturada["ruta"] = _extraer_ruta_salida(script)
        return _ResultadoElevado(owner_app.CODIGO_UAC_CANCELADO)

    with pytest.raises(RuntimeError):
        owner_app._ejecutar_elevado(["--leer-secretos"], runner=runner)

    from pathlib import Path

    assert not Path(ruta_capturada["ruta"]).exists()


def test_rotar_secreto_elevado_devuelve_solo_el_valor_pedido():
    def runner(args, **kwargs):
        script = args[-1]
        ruta = _extraer_ruta_salida(script)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"admin_key": "z" * 64}, f)
        return _ResultadoElevado(0)

    assert owner_app.rotar_secreto_elevado("admin_key", runner=runner) == "z" * 64


def test_main_subcomando_leer_secretos_escribe_json(monkeypatch, tmp_path):
    import sys

    from validator_app.proxy import secretos as secretos_mod

    monkeypatch.setattr(secretos_mod, "ruta_instalacion", lambda: tmp_path)
    monkeypatch.setattr(
        secretos_mod, "leer_secretos", lambda base_dir: {"proxy_token": "a", "admin_key": "b"}
    )
    ruta_salida = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", ["owner_app.exe", "--leer-secretos", str(ruta_salida)])

    assert owner_app.main() == 0
    assert json.loads(ruta_salida.read_text(encoding="utf-8")) == {
        "proxy_token": "a",
        "admin_key": "b",
    }


def test_main_subcomando_rotar_requiere_argumento_valido(monkeypatch, capsys):
    import sys

    monkeypatch.setattr(sys, "argv", ["owner_app.exe", "--rotar-secretos", "algo-invalido"])

    assert owner_app.main() == 1
    salida = json.loads(capsys.readouterr().out)
    assert "error" in salida


def test_main_subcomando_rotar_secretos_escribe_json(monkeypatch, tmp_path):
    import sys

    from validator_app.proxy import secretos as secretos_mod

    monkeypatch.setattr(secretos_mod, "ruta_instalacion", lambda: tmp_path)
    monkeypatch.setattr(secretos_mod, "rotar", lambda base_dir, cual: "z" * 64)
    ruta_salida = tmp_path / "out.json"
    monkeypatch.setattr(
        sys, "argv", ["owner_app.exe", "--rotar-secretos", "admin_key", str(ruta_salida)]
    )

    assert owner_app.main() == 0
    assert json.loads(ruta_salida.read_text(encoding="utf-8")) == {"admin_key": "z" * 64}


# --------------------------------------------------------------------------
# Windows 11: sin ventanas de Terminal y portapapeles privado
# --------------------------------------------------------------------------


class _ResultadoSimple:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


def test_reiniciar_y_elevar_no_abren_ventana(monkeypatch, tmp_path):
    """En Windows 11 cada consola se abre en Windows Terminal y roba el foco."""
    vistos = []

    def runner(args, **kwargs):
        vistos.append(kwargs.get("creationflags"))
        return _ResultadoSimple(0)

    owner_app.reiniciar_servicio(runner)
    with pytest.raises(RuntimeError):  # sin JSON de salida: da igual aqui
        owner_app._ejecutar_elevado(["--leer-secretos"], runner=runner)

    assert vistos == [owner_app.SIN_VENTANA, owner_app.SIN_VENTANA]


def test_consultar_servicio_no_abre_ventana(monkeypatch):
    vistos = []

    def fake_run(args, **kwargs):
        vistos.append((args, kwargs.get("creationflags")))
        return _ResultadoSimple(0)

    monkeypatch.setattr(owner_app.subprocess, "run", fake_run)
    owner_app.consultar_servicio()
    assert vistos == [(["sc", "query", "JSWinProxy"], owner_app.SIN_VENTANA)]


def test_copiar_sin_historial_devuelve_false_si_no_abre_el_portapapeles(monkeypatch):
    """Si la API Win32 falla, el caller cae al portapapeles normal de Tk."""
    import ctypes
    import types

    class _Fn:
        def __init__(self, ret):
            self.ret = ret

        def __call__(self, *a):
            return self.ret

    destruidas = []
    dll = types.SimpleNamespace(
        CreateWindowExW=_Fn(77), DestroyWindow=lambda h: destruidas.append(h),
        OpenClipboard=_Fn(0), EmptyClipboard=_Fn(1), CloseClipboard=_Fn(1),
        SetClipboardData=_Fn(1), RegisterClipboardFormatW=_Fn(1),
        GlobalAlloc=_Fn(1), GlobalLock=_Fn(1), GlobalUnlock=_Fn(1), GlobalFree=_Fn(1),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: dll, raising=False)

    assert owner_app.copiar_sin_historial("secreto") is False
    assert destruidas == [77]  # la ventana propia se libera igual


class _EtiquetaFalsa:
    def __init__(self):
        self.texto = None
        self.estado = None

    def config(self, **kwargs):
        self.texto = kwargs.get("text", self.texto)
        self.estado = kwargs.get("state", self.estado)


def _app_falsa(**extra):
    """OwnerApp sin Tk: solo los atributos que tocan los metodos de actualizacion."""
    import types

    app = types.SimpleNamespace(
        btn_actualizar=_EtiquetaFalsa(),
        lbl_update_aviso=_EtiquetaFalsa(),
        after=lambda ms, fn=None, *a: fn() if fn else None,
    )
    for nombre, valor in extra.items():
        setattr(app, nombre, valor)
    return app


def test_owner_busca_actualizacion_con_su_propio_exe(monkeypatch):
    llamadas = {}

    def hay(ruta):
        llamadas["ruta"] = ruta
        return {"tag": "v9"}

    monkeypatch.setattr(owner_app.update_check, "hay_actualizacion_owner", hay)
    mostrados = []
    app = _app_falsa(_mostrar_update=lambda info, silencioso: mostrados.append((info, silencioso)))

    owner_app.OwnerApp._buscar_update_hilo(app, True)

    assert llamadas["ruta"] == owner_app.sys.executable
    assert mostrados == [({"tag": "v9"}, True)]


def test_owner_chequeo_silencioso_solo_avisa_en_la_etiqueta(monkeypatch):
    preguntas = []
    monkeypatch.setattr(owner_app.messagebox, "askyesno", lambda *a, **k: preguntas.append(a))
    app = _app_falsa()

    owner_app.OwnerApp._mostrar_update(app, {"tag": "v9"}, True)

    assert "v9" in app.lbl_update_aviso.texto
    assert app.btn_actualizar.estado == "normal"
    assert preguntas == []  # nunca interrumpe con una ventana


def test_owner_sin_actualizacion_silencioso_deja_la_etiqueta_vacia_y_manual_dice_al_dia():
    app = _app_falsa()
    owner_app.OwnerApp._mostrar_update(app, None, True)
    assert app.lbl_update_aviso.texto == ""

    owner_app.OwnerApp._mostrar_update(app, None, False)
    assert app.lbl_update_aviso.texto == "Estas al dia"


def test_owner_manual_pregunta_y_aplica_solo_si_acepta(monkeypatch):
    aplicadas = []
    abiertos = []

    class _Hilo:
        def __init__(self, target, args=(), daemon=None):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(owner_app.threading, "Thread", _Hilo)
    monkeypatch.setattr(owner_app.download, "aplicar_actualizacion", aplicadas.append)
    app = _app_falsa(
        _abrir_progreso_actualizacion=lambda: abiertos.append(True),
        _aplicar_update_hilo=lambda info: aplicadas.append(info),
    )
    info = {"tag": "v9"}

    monkeypatch.setattr(owner_app.messagebox, "askyesno", lambda *a, **k: False)
    owner_app.OwnerApp._mostrar_update(app, info, False)
    assert aplicadas == [] and abiertos == []

    monkeypatch.setattr(owner_app.messagebox, "askyesno", lambda *a, **k: True)
    owner_app.OwnerApp._mostrar_update(app, info, False)
    assert aplicadas == [info] and abiertos == [True]


def test_owner_en_codigo_fuente_no_se_actualiza(monkeypatch):
    avisos = []
    monkeypatch.setattr(owner_app.messagebox, "showinfo", lambda *a, **k: avisos.append(a))
    monkeypatch.delattr(owner_app.sys, "frozen", raising=False)
    app = _app_falsa(_es_exe=lambda: False)

    owner_app.OwnerApp.buscar_actualizacion(app)

    assert avisos and app.btn_actualizar.estado is None  # no deshabilito el boton


def test_owner_error_al_aplicar_muestra_el_motivo(monkeypatch):
    errores = []
    cerrados = []

    def falla(info):
        raise ValueError("Checksum no coincide")

    monkeypatch.setattr(owner_app.download, "aplicar_actualizacion", falla)
    monkeypatch.setattr(owner_app.messagebox, "showerror", lambda *a, **k: errores.append(a))
    app = _app_falsa(_cerrar_progreso_actualizacion=lambda: cerrados.append(True))

    owner_app.OwnerApp._aplicar_update_hilo(app, {"tag": "v9"})

    assert cerrados == [True]
    assert errores and "Checksum no coincide" in errores[0][1]


# --------------------------------------------------------------------------
# Autologin de WinForce desde la consola (plan Proxy 24/7, 2026-10-28)
# --------------------------------------------------------------------------

def _health(**autologin):
    base = {
        "habilitado": True, "en_curso": False, "ultimo_intento": None,
        "ultimo_resultado": None, "pausado_hasta": None, "motivo": "",
    }
    base.update(autologin)
    return {"status": "ok", "login_configurado": True, "autologin": base}


def test_describir_autologin_sin_configurar():
    assert owner_app.describir_autologin(
        {"status": "ok", "login_configurado": False, "autologin": {"habilitado": False}}
    ) == "Autologin: sin configurar (pulsa Configurar)"


def test_describir_autologin_health_viejo_sin_bloque():
    assert owner_app.describir_autologin({"status": "ok"}) == (
        "Autologin: sin configurar (pulsa Configurar)"
    )


def test_describir_autologin_sin_proxy():
    assert owner_app.describir_autologin(None) == "Autologin: proxy no responde"


def test_describir_autologin_activo_y_ultimo_resultado():
    assert owner_app.describir_autologin(_health(ultimo_resultado="ok")) == (
        "Autologin: activo; ultimo intento: ok"
    )
    assert owner_app.describir_autologin(_health()) == "Autologin: activo"


def test_describir_autologin_en_curso():
    assert owner_app.describir_autologin(_health(en_curso=True)) == (
        "Autologin: entrando a WinForce ahora..."
    )


def test_describir_autologin_pausado_muestra_la_hora():
    texto = owner_app.describir_autologin(
        _health(motivo="pausado", pausado_hasta="2026-10-28T15:42:10")
    )
    assert texto == "Autologin: en pausa hasta las 15:42 (otra persona usa la cuenta)"


def test_describir_autologin_credencial_rechazada():
    texto = owner_app.describir_autologin(
        _health(habilitado=False, motivo="credencial_invalida",
                ultimo_resultado="credencial_invalida")
    )
    assert texto == "Autologin: contrasena rechazada; vuelve a guardarla"


def test_describir_autologin_navegador_rechazado():
    texto = owner_app.describir_autologin(
        _health(habilitado=False, motivo="navegador_rechazado",
                ultimo_resultado="navegador_rechazado")
    )
    assert texto == "Autologin: WinForce rechazo el navegador (no es la contrasena)"


def test_describir_autologin_apagado_en_config():
    texto = owner_app.describir_autologin(_health(habilitado=False))
    assert texto == "Autologin: apagado (autologin_enabled en config.yaml)"


def test_describir_autologin_tope_y_espera():
    assert owner_app.describir_autologin(_health(motivo="tope_por_hora")) == (
        "Autologin: tope de intentos por hora; reintenta solo mas tarde"
    )
    assert owner_app.describir_autologin(_health(motivo="esperando")) == (
        "Autologin: reintentando tras un fallo"
    )


def test_guardar_credencial_autologin_pide_uac_y_envia_sin_elevar():
    llamadas = {}

    def leer():
        llamadas["leer"] = True
        return {"proxy_token": "t" * 64, "admin_key": "k" * 64}

    def enviar(usuario, password, admin_key, url):
        llamadas["enviar"] = (usuario, password, admin_key, url)
        return True, "Credencial guardada en el keyring del proxy."

    msg = owner_app.guardar_credencial_autologin(
        " proxy@empresa.pe ", "secreta", leer=leer, enviar=enviar,
        url="http://127.0.0.1:8080",
    )
    assert llamadas["leer"] is True
    assert llamadas["enviar"] == ("proxy@empresa.pe", "secreta", "k" * 64,
                                  "http://127.0.0.1:8080")
    assert "secreta" not in msg


def test_guardar_credencial_autologin_la_password_no_va_al_proceso_elevado(monkeypatch):
    """La lectura elevada recibe solo su flag: ni usuario ni contrasena viajan por
    la linea de comandos del proceso con UAC."""
    vistos = []
    monkeypatch.setattr(
        owner_app, "_ejecutar_elevado",
        lambda args, runner=None: vistos.append(list(args)) or {"admin_key": "k" * 64},
    )
    owner_app.guardar_credencial_autologin(
        "u@x.pe", "secreta", enviar=lambda *a: (True, "ok"), url="http://127.0.0.1:8080"
    )
    assert vistos == [["--leer-secretos"]]


def test_guardar_credencial_autologin_vacios_no_piden_uac():
    def leer():
        raise AssertionError("no debia pedir UAC")

    with pytest.raises(ValueError):
        owner_app.guardar_credencial_autologin("", "x", leer=leer, enviar=None, url="u")
    with pytest.raises(ValueError):
        owner_app.guardar_credencial_autologin("u", "", leer=leer, enviar=None, url="u")


def test_guardar_credencial_autologin_uac_cancelado_propaga():
    def leer():
        raise RuntimeError("No se concedio el permiso de administrador (aviso UAC cancelado).")

    with pytest.raises(RuntimeError, match="UAC"):
        owner_app.guardar_credencial_autologin(
            "u@x.pe", "p", leer=leer, enviar=lambda *a: (True, ""), url="u"
        )


def test_guardar_credencial_autologin_error_del_proxy_es_runtime_error():
    with pytest.raises(RuntimeError, match="JSWinProxy"):
        owner_app.guardar_credencial_autologin(
            "u@x.pe", "p",
            leer=lambda: {"admin_key": "k" * 64},
            enviar=lambda *a: (False, "Comprueba que el servicio JSWinProxy este encendido"),
            url="u",
        )


def test_consultar_proxy_devuelve_texto_y_datos_de_health(monkeypatch):
    class Respuesta:
        def raise_for_status(self):
            pass

        def json(self):
            return {"session_alive": True, "login_configurado": True}

    monkeypatch.setattr(owner_app, "_url_proxy_local", lambda: "http://127.0.0.1:8080")
    monkeypatch.setattr(owner_app.httpx, "get", lambda url, timeout: Respuesta())
    datos = owner_app._leer_health()
    assert datos == {"session_alive": True, "login_configurado": True}
    assert owner_app.describir_proxy(datos) == "Proxy: operativo; sesion WinForce viva"
    assert owner_app.describir_proxy(None) == "Proxy: no responde localmente"


# --------------------------------------------------------------------------
# Frenado del autologin desde la consola (perfiles + personalizado)
# --------------------------------------------------------------------------

def test_rangos_freno_se_encadenan():
    assert owner_app.rangos_freno(1, 1) == ((1, 5), (1, 10), (1, 15), (1, 20))
    assert owner_app.rangos_freno(4, 7) == ((1, 5), (4, 10), (7, 15), (1, 20))


def test_ajustar_minutos_sube_los_pasos_que_quedan_por_debajo():
    assert owner_app.ajustar_minutos([4, 2, 3, 5]) == [4, 4, 4, 5]
    assert owner_app.ajustar_minutos([2, 8, 3, 5]) == [2, 8, 8, 5]
    assert owner_app.ajustar_minutos([1, 2, 3, 5]) == [1, 2, 3, 5]


def test_linea_de_tiempo_del_freno():
    assert owner_app.linea_de_tiempo_freno([1, 2, 3, 5]) == (
        "Intentos: inmediato, +1, +2, +3 min, luego cada 5 min · pausa por otra persona: 5 min"
    )


def test_perfiles_para_combo_en_orden_y_con_personalizado_al_final():
    claves = [clave for clave, _nombre in owner_app.perfiles_para_combo()]
    assert claves[0] == "recomendado"
    assert claves[-1] == "personalizado"
    assert set(claves) == {
        "recomendado", "rapido", "demasiado_rapido", "lento_optimo", "lento",
        "demasiado_lento", "personalizado",
    }


def test_describir_freno_desde_health():
    datos = _health(freno={
        "perfil": "recomendado", "nombre": "Rango de relogin recomendado",
        "minutos": [0, 1, 2, 3, 5], "pausa_min": 5,
    })
    assert owner_app.describir_freno(datos) == (
        "Frenado: Rango de relogin recomendado (0-1-2-3, luego cada 5 min)"
    )
    assert owner_app.describir_freno(None) == "Frenado: proxy no responde"
    assert owner_app.describir_freno({"status": "ok"}) == "Frenado: (el proxy no lo informa)"


def test_guardar_freno_valida_antes_de_pedir_uac():
    def leer():
        raise AssertionError("no debia pedir UAC")

    with pytest.raises(ValueError, match="1 a 5"):
        owner_app.guardar_freno_autologin(
            "personalizado", [9, 9, 9, 9], leer=leer, enviar=None, url="u"
        )


def test_guardar_freno_envia_el_perfil_resuelto():
    enviados = []
    msg = owner_app.guardar_freno_autologin(
        "lento", [1, 1, 1, 1],
        leer=lambda: {"admin_key": "k" * 64},
        enviar=lambda *a: enviados.append(a) or (True, "Frenado del autologin actualizado"),
        url="http://127.0.0.1:8080",
    )
    assert enviados == [("lento", [3, 6, 10, 15], "k" * 64, "http://127.0.0.1:8080")]
    assert "Frenado" in msg


def test_guardar_freno_uac_cancelado_y_error_del_proxy():
    def cancelado():
        raise RuntimeError("aviso UAC cancelado")

    with pytest.raises(RuntimeError, match="UAC"):
        owner_app.guardar_freno_autologin(
            "recomendado", None, leer=cancelado, enviar=lambda *a: (True, ""), url="u"
        )
    with pytest.raises(RuntimeError, match="422"):
        owner_app.guardar_freno_autologin(
            "recomendado", None, leer=lambda: {"admin_key": "k" * 64},
            enviar=lambda *a: (False, "HTTP 422"), url="u",
        )


# --------------------------------------------------------------------------
# Boton "Instalar extension en Chrome": ruta real o "Preparar carpeta"
# --------------------------------------------------------------------------

def test_ruta_extension_build_solo_si_la_carpeta_existe(tmp_path):
    build = tmp_path / ".extension_build"
    build.mkdir()
    (build / "manifest.json").write_text("{}", encoding="utf-8")
    ruta, aviso, preparable = owner_app.ruta_extension_build(ruta_instalacion=lambda: tmp_path)
    assert ruta == build
    assert aviso == ""
    assert preparable is False


def test_ruta_extension_build_servicio_instalado_sin_carpeta_es_preparable(tmp_path):
    ruta, aviso, preparable = owner_app.ruta_extension_build(ruta_instalacion=lambda: tmp_path)
    assert ruta is None
    assert preparable is True
    assert "Preparar carpeta" in aviso


def test_preparar_extension_elevado_usa_su_flag(monkeypatch):
    vistos = []
    monkeypatch.setattr(
        owner_app, "_ejecutar_elevado",
        lambda args, runner=None: vistos.append(list(args)) or {"ruta": r"C:\p\.extension_build"},
    )
    from pathlib import Path

    assert owner_app.preparar_extension_elevado() == Path(r"C:\p\.extension_build")
    assert vistos == [["--preparar-extension"]]


def test_subcomando_preparar_extension_arma_la_carpeta(tmp_path, monkeypatch):
    from validator_app.proxy import secretos

    plantilla = tmp_path / "extension"
    plantilla.mkdir()
    (plantilla / "manifest.json").write_text('{"x": "8080"}', encoding="utf-8")
    (plantilla / "background.js").write_text('"http://127.0.0.1:8080"', encoding="utf-8")
    monkeypatch.setattr(secretos, "ruta_instalacion", lambda: tmp_path)
    salida = tmp_path / "salida.json"
    monkeypatch.setattr(owner_app.sys, "argv", ["owner", "--preparar-extension", str(salida)])

    assert owner_app.main() == 0
    datos = json.loads(salida.read_text(encoding="utf-8"))
    assert datos == {"ruta": str(tmp_path / ".extension_build")}
    assert (tmp_path / ".extension_build" / "manifest.json").exists()


def test_subcomando_preparar_extension_sin_plantilla_devuelve_error(tmp_path, monkeypatch):
    from validator_app.proxy import secretos

    monkeypatch.setattr(secretos, "ruta_instalacion", lambda: tmp_path)
    salida = tmp_path / "salida.json"
    owner_app._correr_subcomando_preparar_extension(str(salida))
    assert "error" in json.loads(salida.read_text(encoding="utf-8"))
