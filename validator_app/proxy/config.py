"""Configuracion del proxy local (Pydantic Settings).

Lee de config.yaml + variables de entorno (precedencia: env > yaml > defaults).
config.yaml es GITIGNORED - solo existe en la PC del proxy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


class ProxyConfig(BaseSettings):
    # Servidor
    proxy_host: str = "0.0.0.0"
    proxy_port: int = 8080

    # Autenticacion (requeridos - se generan en install_service.bat)
    proxy_token: Annotated[str, Field(min_length=64, max_length=64)]
    admin_key: Annotated[str, Field(min_length=64, max_length=64)]

    # Keyring para credenciales WinForce
    win_keyring_service: str = "JSWinProxy"
    win_keyring_user: str = "credentials"

    # Timeouts
    session_max_idle_seconds: int = 120
    request_timeout: int = 30
    winforce_login_timeout: int = 30
    winforce_cobertura_timeout: int = 30
    winforce_score_timeout: int = 90

    # Redes permitidas (LAN + Tailscale CGNAT)
    allowed_networks: list[str] = [
        "192.168.0.0/16",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "100.64.0.0/10",
    ]

    # Base URL WinForce
    winforce_base_url: str = "https://appwinforce.win.pe"
    winforce_controllers: str = "https://appwinforce.win.pe/controllers"

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        env_prefix="PROXY_",
        extra="ignore",
    )

    @field_validator("allowed_networks", mode="before")
    @classmethod
    def _parse_networks(cls, v):
        if isinstance(v, str):
            return [net.strip() for net in v.split(",")]
        return v

    @property
    def proxy_url(self) -> str:
        return f"http://{self.proxy_host}:{self.proxy_port}"

    @property
    def winforce_controllers_url(self) -> str:
        return self.winforce_controllers


_config: ProxyConfig | None = None


def get_config() -> ProxyConfig:
    global _config
    if _config is None:
        _config = ProxyConfig()
    return _config


def reset_config() -> None:
    global _config
    _config = None
