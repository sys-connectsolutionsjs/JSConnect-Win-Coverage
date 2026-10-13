"""Direccion de unas coordenadas: parsers de Geofinder (Equifax) y OpenStreetMap.

Geofinder es la fuente buena (la misma que usa WinForce); OpenStreetMap es el respaldo
aproximado cuando Geofinder no esta disponible. Todos devuelven el mismo dict:
direccion, departamento, provincia, distrito, fuente, aproximada.
"""

from __future__ import annotations

import re

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "JSConnect-WinCoverage/1.0 (soporte interno)"
TIMEOUT_OSM_S = 8.0
_PREFIJOS_OSM = ("Provincia de ", "Departamento de ", "Distrito de ", "Municipalidad de ")


class DireccionNoDisponible(Exception):
    """No se pudo obtener la direccion de la fuente consultada."""


def _texto(valor) -> str:
    return str(valor).strip() if valor not in (None, "") else ""


def con_ubicacion(detalle: str, distrito: str, provincia: str, departamento: str) -> str:
    """`DETALLE (DISTRITO, PROVINCIA, DEPARTAMENTO)`: el formato de Geofinder en WinForce."""
    if detalle and distrito and provincia and departamento:
        return f"{detalle} ({distrito}, {provincia}, {departamento})"
    return detalle


def de_geofinder(datos) -> dict | None:
    """Respuesta de `geoapi/nyg/pe/coordinates/v1` -> dict, o None si no trae direccion."""
    if not isinstance(datos, dict):
        return None
    numero = _texto(datos.get("numero"))
    partes = [_texto(datos.get("via"))]
    if numero:
        partes.append(numero)
    else:
        manzana, lote = _texto(datos.get("manzana")), _texto(datos.get("lt_muni"))
        if manzana:
            partes.append(f"MZ {manzana}")
        if lote:
            partes.append(f"LT {lote}")
    partes.append(_texto(datos.get("nom_hu")))
    detalle = " ".join(p for p in partes if p)
    distrito = _texto(datos.get("distrito"))
    if not detalle and not distrito:
        return None
    departamento, provincia = _texto(datos.get("departamen")), _texto(datos.get("provincia"))
    return {
        "direccion": con_ubicacion(detalle, distrito, provincia, departamento),
        "departamento": departamento,
        "provincia": provincia,
        "distrito": distrito,
        "fuente": "geofinder",
        "aproximada": False,
    }


_PARENTESIS_FINAL = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")


def _a_float(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def de_geofinder_ref(datos) -> dict | None:
    """Respuesta de `coordinates-ref/v1` (la direccion que muestra Geofinder en WinForce).

    El texto llega como `VIA NUM URBANIZACION (DISTRITO, PROVINCIA, DEPARTAMENTO)`: se separa
    el parentesis. `punto` es el punto ajustado (lat, lon) que WinForce usa en la 2.a consulta.
    """
    if not isinstance(datos, dict):
        return None
    texto = _texto(datos.get("direccion"))
    if not texto:
        return None
    detalle, admin = texto, ["", "", ""]
    m = _PARENTESIS_FINAL.match(texto)
    if m:
        detalle = m.group(1).strip()
        partes = [p.strip() for p in m.group(2).split(",")]
        if len(partes) == 3:
            admin = partes
    lat, lon = _a_float(datos.get("lat_y")), _a_float(datos.get("lon_x"))
    return {
        "direccion": texto,
        "detalle": detalle,
        "departamento": admin[2],
        "provincia": admin[1],
        "distrito": admin[0],
        "fuente": "geofinder",
        "aproximada": False,
        "punto": (lat, lon) if lat is not None and lon is not None else None,
    }


def _sin_prefijo(texto: str) -> str:
    for prefijo in _PREFIJOS_OSM:
        if texto.startswith(prefijo):
            return texto[len(prefijo):]
    return texto


def de_nominatim(datos) -> dict | None:
    """Respuesta de Nominatim `reverse` -> dict aproximado, o None si no hubo resultado."""
    if not isinstance(datos, dict) or datos.get("error"):
        return None
    dir_osm = datos.get("address")
    dir_osm = dir_osm if isinstance(dir_osm, dict) else {}
    calle = " ".join(
        p for p in (_texto(dir_osm.get("road")), _texto(dir_osm.get("house_number"))) if p
    )
    barrio = _texto(dir_osm.get("neighbourhood") or dir_osm.get("suburb"))
    detalle = ", ".join(p for p in (calle, barrio) if p) or _texto(datos.get("display_name"))
    if not detalle:
        return None
    distrito = dir_osm.get("city_district") or dir_osm.get("suburb") or dir_osm.get("city")
    distrito = distrito or dir_osm.get("town") or dir_osm.get("village")
    provincia = dir_osm.get("county") or dir_osm.get("state_district") or dir_osm.get("city")
    departamento = _sin_prefijo(_texto(dir_osm.get("state")))
    provincia, distrito = _sin_prefijo(_texto(provincia)), _sin_prefijo(_texto(distrito))
    return {
        "direccion": con_ubicacion(detalle, distrito, provincia, departamento),
        "departamento": departamento,
        "provincia": provincia,
        "distrito": distrito,
        "fuente": "osm",
        "aproximada": True,
    }


def consultar_osm(lat: float, lon: float, http=None) -> dict:
    """Direccion aproximada desde OpenStreetMap. Lanza DireccionNoDisponible si falla."""
    if http is None:
        import httpx

        http = httpx
    try:
        resp = http.get(
            NOMINATIM_URL,
            params={
                "format": "jsonv2", "lat": lat, "lon": lon, "zoom": 18,
                "addressdetails": 1, "accept-language": "es",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_OSM_S,
        )
        if resp.status_code != 200:
            raise DireccionNoDisponible(f"OpenStreetMap respondio HTTP {resp.status_code}.")
        resultado = de_nominatim(resp.json())
    except DireccionNoDisponible:
        raise
    except Exception as exc:
        raise DireccionNoDisponible(f"No se pudo consultar OpenStreetMap: {exc}") from exc
    if resultado is None:
        raise DireccionNoDisponible("OpenStreetMap no tiene direccion para ese punto.")
    return resultado


AVISO_OSM = (
    "DIRECCIÓN APROXIMADA (OpenStreetMap): NO es la de WinForce. El servicio de Geofinder "
    "debería reactivarse; avisa al administrador."
)
AVISO_PROXY_VIEJO = (
    "El proxy de la oficina es de una versión anterior y no tiene Geofinder: hay que actualizarlo."
)
MOTIVO_SIN_PROXY = "No hay un proxy configurado."
MOTIVO_SIN_RESPUESTA = "Geofinder no respondió."
AVISO_SIN_DIRECCION = "No se pudo obtener la direccion de las coordenadas."


def obtener(cliente, lat: float, lon: float, osm=consultar_osm) -> tuple[dict | None, str | None]:
    """Direccion de unas coordenadas: Geofinder via proxy y, si no, OpenStreetMap con aviso.

    Devuelve (direccion, aviso). `cliente` puede ser None o un cliente sin proxy
    (standalone): ambos van directo al respaldo.
    """
    consultar = getattr(cliente, "obtener_direccion", None)
    motivo = MOTIVO_SIN_PROXY
    if consultar is not None:
        try:
            return consultar(lat, lon), None
        except DireccionNoDisponible as exc:
            motivo = str(exc) or MOTIVO_SIN_RESPUESTA
        except Exception:
            motivo = MOTIVO_SIN_RESPUESTA
    try:
        return osm(lat, lon), f"{AVISO_OSM} {motivo}"
    except DireccionNoDisponible:
        return None, AVISO_SIN_DIRECCION
