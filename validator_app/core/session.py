"""Sesion HTTP con el sistema de validacion (descubierto en la Fase 0)."""

import requests

BASE_URL = "https://appwinforce.win.pe"
CONTROLLERS = f"{BASE_URL}/controllers"

TIEMPO_LOGIN = 30
TIEMPO_COBERTURA = 30
TIEMPO_SCORE = 90

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE_URL}/login",
}


def crear_sesion() -> requests.Session:
    sesion = requests.Session()
    sesion.headers.update(HEADERS)
    return sesion
