"""Lectura y rotacion de proxy_token / admin_key (sin GUI ni elevacion real)."""

import pytest

from validator_app.proxy import secretos

_TOKEN = "a" * 64
_ADMIN = "b" * 64

_CONFIG_YAML_VALIDO = f"""# Configuracion del Proxy Local JSConnect Win Coverage
# Generado automaticamente por install_service.bat - 21/09/2026 10:00:00

proxy_host: "0.0.0.0"
proxy_port: 8080

proxy_token: "{_TOKEN}"
admin_key: "{_ADMIN}"

win_keyring_service: "JSWinProxy"
win_keyring_user: "credentials"

allowed_networks:
  - "192.168.0.0/16"
  - "10.0.0.0/8"

winforce_base_url: "https://appwinforce.win.pe"
"""


@pytest.fixture
def base_dir(tmp_path):
    (tmp_path / "config.yaml").write_text(_CONFIG_YAML_VALIDO, encoding="utf-8")
    return tmp_path


def test_leer_secretos_ok(base_dir):
    valores = secretos.leer_secretos(base_dir)
    assert valores == {"proxy_token": _TOKEN, "admin_key": _ADMIN}


def test_leer_secretos_config_ausente(tmp_path):
    with pytest.raises(secretos.SecretosError, match="No existe"):
        secretos.leer_secretos(tmp_path)


def test_leer_secretos_sin_permiso(base_dir, monkeypatch):
    def sin_permiso(*args, **kwargs):
        raise PermissionError("denegado")

    from pathlib import Path

    monkeypatch.setattr(Path, "read_text", sin_permiso)
    with pytest.raises(secretos.SecretosError, match="permiso"):
        secretos.leer_secretos(base_dir)


def test_leer_secretos_faltan_claves(tmp_path):
    (tmp_path / "config.yaml").write_text('proxy_token: "solo-esta"\n', encoding="utf-8")
    with pytest.raises(secretos.SecretosError, match="admin_key"):
        secretos.leer_secretos(tmp_path)


class _Resultado:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_rotar_preserva_el_resto_del_archivo(base_dir):
    llamadas = []

    def runner(args, **kwargs):
        llamadas.append(args)
        return _Resultado(0)

    nuevo = secretos.rotar(base_dir, "proxy_token", runner=runner)

    assert len(nuevo) == 64
    assert nuevo != _TOKEN

    texto = (base_dir / "config.yaml").read_text(encoding="utf-8")
    assert f'proxy_token: "{nuevo}"' in texto
    assert f'admin_key: "{_ADMIN}"' in texto  # el otro secreto no se toca
    assert 'proxy_port: 8080' in texto
    assert '"192.168.0.0/16"' in texto
    assert "# Configuracion del Proxy Local" in texto

    assert (base_dir / "proxy_token.txt").read_text(encoding="utf-8") == nuevo

    # icacls (config.yaml + .txt) y Restart-Service
    comandos = [c[0] for c in llamadas]
    assert any(c == "icacls" for c in comandos)
    assert any("Restart-Service" in " ".join(c) for c in llamadas)


def test_rotar_admin_key_no_toca_proxy_token(base_dir):
    def runner(args, **kwargs):
        return _Resultado(0)

    nuevo = secretos.rotar(base_dir, "admin_key", runner=runner)

    texto = (base_dir / "config.yaml").read_text(encoding="utf-8")
    assert f'admin_key: "{nuevo}"' in texto
    assert f'proxy_token: "{_TOKEN}"' in texto


def test_rotar_cual_invalido(base_dir):
    with pytest.raises(secretos.SecretosError, match="invalido"):
        secretos.rotar(base_dir, "otra_cosa", runner=lambda *a, **k: _Resultado(0))


def test_rotar_icacls_cae_a_administrators_en_ingles(base_dir):
    """Si el sistema esta en ingles, BUILTIN\\Administradores falla y se
    reintenta con Administrators (mismo fallback de install_service.bat)."""
    intentos = []

    def runner(args, **kwargs):
        if "icacls" in args:
            intentos.append(args)
            if "BUILTIN\\Administradores:F" in args:
                return _Resultado(1)
        return _Resultado(0)

    secretos.rotar(base_dir, "proxy_token", runner=runner)

    assert any("BUILTIN\\Administradores:F" in a for a in intentos)
    assert any("BUILTIN\\Administrators:F" in a for a in intentos)


def test_ruta_instalacion_usa_binpath_del_servicio(tmp_path, monkeypatch):
    carpeta = tmp_path / "validator_app" / "proxy"
    carpeta.mkdir(parents=True)
    (carpeta / "config.yaml").write_text(_CONFIG_YAML_VALIDO, encoding="utf-8")
    exe = carpeta / "JSWinProxy.exe"

    salida = f'        BINARY_PATH_NAME   : "{exe}"\n'

    def runner(args, **kwargs):
        return _Resultado(0, stdout=salida)

    assert secretos.ruta_instalacion(runner=runner) == carpeta


def test_ruta_instalacion_servicio_no_instalado_cae_a_desarrollo(monkeypatch):
    from pathlib import Path

    def runner(args, **kwargs):
        return _Resultado(1, stderr="El servicio especificado no existe")

    monkeypatch.setattr(Path, "exists", lambda self: True)
    assert secretos.ruta_instalacion(runner=runner) == secretos._BASE_DIR_DESARROLLO


def test_ruta_instalacion_sin_servicio_ni_config_local_falla_claro(monkeypatch):
    from pathlib import Path

    def runner(args, **kwargs):
        return _Resultado(1, stderr="El servicio especificado no existe")

    monkeypatch.setattr(Path, "exists", lambda self: False)
    with pytest.raises(secretos.SecretosError, match="config"):
        secretos.ruta_instalacion(runner=runner)
