"""Validacion y parseo de entradas del usuario."""

import re


def parse_coordenadas(texto: str):
    """Convierte '-11.956037627741102, -77.04065381800075' en (lat, lon)."""
    partes = [p.strip() for p in texto.replace(";", ",").split(",")]
    if len(partes) != 2:
        raise ValueError("Formato esperado: latitud, longitud (separadas por coma)")
    try:
        lat, lon = float(partes[0]), float(partes[1])
    except ValueError:
        raise ValueError(
            "Las coordenadas deben ser numeros (ej: -11.956037627741102, -77.04065381800075)"
        ) from None
    if not -90 <= lat <= 90:
        raise ValueError("Latitud fuera de rango (-90 a 90)")
    if not -180 <= lon <= 180:
        raise ValueError("Longitud fuera de rango (-180 a 180)")
    return lat, lon


def detectar_tipo_documento(numero: str) -> str:
    """Autodetecta DNI (8 digitos), RUC (11) o Carnet de Extranjeria (9, con letras)."""
    n = numero.strip()
    if re.fullmatch(r"\d{8}", n):
        return "DNI"
    if re.fullmatch(r"\d{11}", n):
        return "RUC"
    if re.fullmatch(r"[0-9A-Za-z]{9}", n):
        return "CE"
    raise ValueError("Documento no reconocido (DNI 8 digitos, RUC 11, CE 9 caracteres)")
