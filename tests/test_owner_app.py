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


def test_ruta_extension_build_con_servicio_instalado():
    from pathlib import Path

    ruta, aviso = owner_app.ruta_extension_build(
        ruta_instalacion=lambda: Path(r"C:\proxy\validator_app\proxy")
    )
    assert ruta == Path(r"C:\proxy\validator_app\proxy\.extension_build")
    assert aviso == ""


def test_ruta_extension_build_sin_servicio_instalado():
    from validator_app.proxy import secretos

    def falla():
        raise secretos.SecretosError("servicio JSWinProxy no instalado")

    ruta, aviso = owner_app.ruta_extension_build(ruta_instalacion=falla)
    assert ruta is None
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
