"""Tests de la carga de configuracion del proxy (validator_app.proxy.config).

Regresion del bug historico: `SettingsConfigDict` declaraba `yaml_file` pero
faltaba `settings_customise_sources` con `YamlConfigSettingsSource`, asi que
`config.yaml` se ignoraba en silencio y el servicio moria con `ValidationError`
(los tokens son obligatorios y sin default).
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from validator_app.proxy import config as C

TOK = "a" * 64
ADM = "b" * 64


@pytest.fixture
def yaml_file(monkeypatch, tmp_path):
    """Redirige el `yaml_file` del modelo a un archivo temporal y aisla el env."""
    path = tmp_path / "config.yaml"
    monkeypatch.setitem(C.ProxyConfig.model_config, "yaml_file", path)
    for var in list(os.environ):
        if var.startswith("PROXY_"):
            monkeypatch.delenv(var, raising=False)
    C.reset_config()
    yield path
    C.reset_config()


def test_lee_config_yaml(yaml_file):
    yaml_file.write_text(
        f'proxy_token: "{TOK}"\nadmin_key: "{ADM}"\nproxy_port: 9999\n',
        encoding="utf-8",
    )
    cfg = C.ProxyConfig()
    assert cfg.proxy_token == TOK
    assert cfg.admin_key == ADM
    assert cfg.proxy_port == 9999  # del YAML, no el default 8080


def test_env_gana_sobre_yaml(yaml_file, monkeypatch):
    yaml_file.write_text(
        f'proxy_token: "{TOK}"\nadmin_key: "{ADM}"\nproxy_port: 9999\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PROXY_PROXY_PORT", "7777")
    cfg = C.ProxyConfig()
    assert cfg.proxy_port == 7777


def test_sin_ninguna_fuente_es_error(yaml_file):
    # yaml_file apunta a un archivo que no existe y no hay env vars.
    assert not yaml_file.exists()
    with pytest.raises(ValidationError):
        C.ProxyConfig()


def test_yaml_incompleto_completa_con_defaults(yaml_file):
    yaml_file.write_text(
        f'proxy_token: "{TOK}"\nadmin_key: "{ADM}"\n', encoding="utf-8"
    )
    cfg = C.ProxyConfig()
    assert cfg.proxy_port == 8080  # default
    assert cfg.keepalive_interval_seconds == 900  # default
    assert "192.168.0.0/16" in cfg.allowed_networks


def test_yaml_file_apunta_junto_al_modulo():
    # El servicio arranca con cwd = raiz del repo; la ruta debe ser absoluta y
    # vivir en validator_app/proxy/, no en el cwd.
    assert C._CONFIG_YAML.is_absolute()
    assert C._CONFIG_YAML.parent.name == "proxy"
    assert C._CONFIG_YAML.name == "config.yaml"


def test_proxy_local_url_ignora_proxy_host(yaml_file):
    # proxy_host=0.0.0.0 (bind de escucha) no es un destino valido para un
    # cliente; las llamadas locales (rotate_creds.py) deben ir a 127.0.0.1.
    yaml_file.write_text(
        f'proxy_token: "{TOK}"\nadmin_key: "{ADM}"\n'
        'proxy_host: "0.0.0.0"\nproxy_port: 9999\n',
        encoding="utf-8",
    )
    cfg = C.ProxyConfig()
    assert cfg.proxy_url == "http://0.0.0.0:9999"
    assert cfg.proxy_local_url == "http://127.0.0.1:9999"
