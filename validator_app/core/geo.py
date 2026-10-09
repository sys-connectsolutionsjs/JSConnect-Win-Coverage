"""Geometria pura para las reglas de venta por zona (sin dependencias externas)."""

import gzip
import io
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

CAPA_COBERTURA = "COBERTURA"
CAPA_FRAUDE = "FRAUDE"
CAPA_PREFERENTE = "PREFERENTE 2"
CAPA_BLOQUEADOS = "CODIGOS BLOQUEADOS"
CAPA_ZONA_F = "ZONA F"

BLOQUEADA = "bloqueada"
SIN_COBERTURA = "sin_cobertura"
EXTENSIBLE = "extensible"
VENDER = "vender"
SIN_CONFIRMAR = "sin_confirmar"

SCORE_PREFERENTE = 401
SCORE_NORMAL = 201
RADIO_EXTENSION_M = 300

FORMATO_EMBEBIDO = 1
MAX_KML_BYTES = 200 * 1024 * 1024

_METROS_POR_GRADO = 6371000 * math.pi / 180
_NOMBRES_ZONAS_JS = {
    "ZONA_F": CAPA_ZONA_F,
    "ZONA_PREFERENTE_2": CAPA_PREFERENTE,
    "ZONA_CODIGOS_BLOQUEADOS": CAPA_BLOQUEADOS,
}


@dataclass(frozen=True)
class Poligono:
    anillo: tuple
    huecos: tuple = ()
    nombre: str = ""
    bbox: tuple = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if self.anillo:
            lats = [p[0] for p in self.anillo]
            lons = [p[1] for p in self.anillo]
            caja = (min(lats), min(lons), max(lats), max(lons))
        else:
            caja = (0.0, 0.0, 0.0, 0.0)
        object.__setattr__(self, "bbox", caja)


@dataclass(frozen=True)
class Decision:
    estado: str
    score_minimo: int | None
    mensaje: str
    distancia_m: float | None = None
    proyecto: str = ""
    avisos: tuple = ()
    capas: tuple = ()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _anillo(elemento) -> tuple:
    texto = next((e.text for e in elemento.iter() if _local(e.tag) == "coordinates"), "")
    puntos = []
    for token in (texto or "").split():
        partes = token.split(",")
        puntos.append((float(partes[1]), float(partes[0])))
    return tuple(puntos)


def _poligono(elemento, nombre: str = "") -> Poligono:
    exterior = ()
    huecos = []
    for hijo in elemento:
        etiqueta = _local(hijo.tag)
        if etiqueta == "outerBoundaryIs":
            exterior = _anillo(hijo)
        elif etiqueta == "innerBoundaryIs":
            huecos.append(_anillo(hijo))
    return Poligono(exterior, tuple(huecos), nombre)


def _texto_hijo(elemento, etiqueta: str) -> str:
    for hijo in elemento:
        if _local(hijo.tag) == etiqueta:
            return (hijo.text or "").strip()
    return ""


def parse_kml(texto: str, capa_por_defecto: str | None = None) -> dict:
    """Devuelve {capa: [Poligono, ...]} con puntos como (lat, lon).

    La capa es la carpeta (Folder) con nombre mas cercana al Placemark; los que
    no estan en ninguna van a `capa_por_defecto` o al nombre del Document."""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError as exc:
        raise ValueError(f"KML invalido: {exc}") from None
    padres = {hijo: padre for padre in raiz.iter() for hijo in padre}
    nombre_documento = next(
        (_texto_hijo(e, "name") for e in raiz.iter() if _local(e.tag) == "Document"), ""
    )
    capas = {}
    for placemark in raiz.iter():
        if _local(placemark.tag) != "Placemark":
            continue
        capa = None
        ancestro = padres.get(placemark)
        while ancestro is not None:
            if _local(ancestro.tag) == "Folder":
                capa = _texto_hijo(ancestro, "name") or None
                if capa:
                    break
            ancestro = padres.get(ancestro)
        capa = capa or capa_por_defecto or nombre_documento or "SIN CARPETA"
        nombre = _texto_hijo(placemark, "name")
        for elem in placemark.iter():
            if _local(elem.tag) == "Polygon":
                poli = _poligono(elem, nombre)
                if poli.anillo:
                    capas.setdefault(capa, []).append(poli)
    return capas


def parse_kmz(datos: bytes, capa_por_defecto: str | None = None) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            kmls = [i for i in z.infolist() if i.filename.lower().endswith(".kml")]
            if not kmls:
                raise ValueError("el KMZ no contiene ningun .kml")
            elegido = next((i for i in kmls if i.filename.lower() == "doc.kml"), kmls[0])
            if elegido.file_size > MAX_KML_BYTES:
                raise ValueError("el KML dentro del KMZ es demasiado grande")
            texto = z.read(elegido).decode("utf-8")
    except zipfile.BadZipFile:
        raise ValueError("KMZ invalido") from None
    return parse_kml(texto, capa_por_defecto)


def parse_zonas_js(texto: str) -> dict:
    """Lee `var ZONA_X_POLYGONS_DATA = [[[lat, lon], ...], ...];` (formato de zonas.txt)."""
    sin_comentarios = re.sub(r"//[^\n]*", "", texto)
    capas = {}
    patron = r"var\s+(ZONA_\w+?)_POLYGONS_DATA\s*=\s*(\[[\s\S]*?\])\s*;"
    for m in re.finditer(patron, sin_comentarios):
        cuerpo = re.sub(r",\s*(?=[\]}])", "", m.group(2))
        try:
            datos = json.loads(cuerpo)
        except ValueError:
            continue
        nombre = _NOMBRES_ZONAS_JS.get(m.group(1), m.group(1).replace("_", " "))
        capas[nombre] = [
            Poligono(tuple((float(a), float(b)) for a, b in poli)) for poli in datos if poli
        ]
    return capas


def capas_a_json(capas: dict, decimales: int | None = None) -> dict:
    def punto(p):
        return [round(p[0], decimales), round(p[1], decimales)] if decimales else list(p)

    return {
        nombre: [
            {
                "nombre": poli.nombre,
                "anillo": [punto(p) for p in poli.anillo],
                "huecos": [[punto(p) for p in hueco] for hueco in poli.huecos],
            }
            for poli in polis
        ]
        for nombre, polis in capas.items()
    }


def capas_de_json(datos: dict) -> dict:
    return {
        nombre: [
            Poligono(
                tuple(tuple(p) for p in poli["anillo"]),
                tuple(tuple(tuple(p) for p in hueco) for hueco in poli["huecos"]),
                poli.get("nombre", ""),
            )
            for poli in polis
        ]
        for nombre, polis in datos.items()
    }


def guardar_capas_embebidas(capas: dict, ruta, decimales: int = 6) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = {"version": FORMATO_EMBEBIDO, "capas": capas_a_json(capas, decimales)}
    ruta.write_bytes(gzip.compress(json.dumps(cuerpo, separators=(",", ":")).encode("utf-8")))


def _ruta_embebida() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        empaquetada = Path(base) / "validator_app" / "data" / "capas.json.gz"
        if empaquetada.exists():
            return empaquetada
    return Path(__file__).resolve().parent.parent / "data" / "capas.json.gz"


def cargar_capas_embebidas(ruta=None) -> dict:
    """Capas incluidas en el .exe; {} si no estan o no se pueden leer."""
    try:
        bruto = gzip.decompress(Path(ruta or _ruta_embebida()).read_bytes())
        cuerpo = json.loads(bruto)
        if cuerpo.get("version") != FORMATO_EMBEBIDO:
            return {}
        return capas_de_json(cuerpo["capas"])
    except (OSError, EOFError, ValueError, KeyError, TypeError):
        return {}


def combinar_capas(base: dict, remotas: dict) -> dict:
    """Las reglas del My Maps (proxy) reemplazan a las embebidas; el resto no cambia."""
    resultado = dict(base)
    for nombre in (CAPA_PREFERENTE, CAPA_BLOQUEADOS):
        if remotas.get(nombre):
            resultado[nombre] = remotas[nombre]
    return resultado


def poligonos_cercanos(capas: dict, lat: float, lon: float, radio_m: float) -> dict:
    """Por capa, los poligonos cuya caja toca el cuadrado de `radio_m` alrededor del punto."""
    margen_lat = radio_m / _METROS_POR_GRADO
    margen_lon = margen_lat / max(math.cos(math.radians(lat)), 0.01)
    return {
        nombre: [
            p
            for p in polis
            if p.bbox[0] <= lat + margen_lat
            and p.bbox[2] >= lat - margen_lat
            and p.bbox[1] <= lon + margen_lon
            and p.bbox[3] >= lon - margen_lon
        ]
        for nombre, polis in capas.items()
    }


def circulo(lat: float, lon: float, radio_m: float, n: int = 36) -> list:
    """Puntos (lat, lon) de un circulo de `radio_m` alrededor del punto, empezando al norte."""
    dlat = radio_m / _METROS_POR_GRADO
    dlon = dlat / max(math.cos(math.radians(lat)), 0.01)
    return [
        (lat + dlat * math.cos(2 * math.pi * i / n), lon + dlon * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def _en_anillo(lat: float, lon: float, anillo: tuple) -> bool:
    dentro = False
    n = len(anillo)
    for i in range(n):
        lat1, lon1 = anillo[i]
        lat2, lon2 = anillo[(i + 1) % n]
        if (lat1 > lat) != (lat2 > lat):
            lon_cruce = lon1 + (lat - lat1) * (lon2 - lon1) / (lat2 - lat1)
            if lon < lon_cruce:
                dentro = not dentro
    return dentro


def punto_en_poligono(lat: float, lon: float, poligono: Poligono) -> bool:
    min_lat, min_lon, max_lat, max_lon = poligono.bbox
    if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
        return False
    if not _en_anillo(lat, lon, poligono.anillo):
        return False
    return not any(_en_anillo(lat, lon, hueco) for hueco in poligono.huecos)


def _dist_segmento_m(lat, lon, p1, p2) -> float:
    escala_lon = math.cos(math.radians(lat))
    ax, ay = (p1[1] - lon) * escala_lon, p1[0] - lat
    bx, by = (p2[1] - lon) * escala_lon, p2[0] - lat
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
    t = 0.0 if largo2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / largo2))
    return math.hypot(ax + t * dx, ay + t * dy) * _METROS_POR_GRADO


def distancia_a_poligono_m(lat: float, lon: float, poligono: Poligono) -> float:
    """0 si el punto esta dentro; si no, metros hasta el borde mas cercano."""
    if punto_en_poligono(lat, lon, poligono):
        return 0
    mejor = math.inf
    for anillo in (poligono.anillo, *poligono.huecos):
        n = len(anillo)
        for i in range(n):
            mejor = min(mejor, _dist_segmento_m(lat, lon, anillo[i], anillo[(i + 1) % n]))
    return mejor


def _poligono_que_contiene(lat: float, lon: float, capas: dict, nombre: str):
    return next((p for p in capas.get(nombre, ()) if punto_en_poligono(lat, lon, p)), None)


def _mas_cercano(lat: float, lon: float, capas: dict, nombre: str, radio_m: float):
    """(distancia_m, Poligono) del mas cercano dentro de `radio_m`, o None."""
    margen_lat = radio_m / _METROS_POR_GRADO
    margen_lon = margen_lat / max(math.cos(math.radians(lat)), 0.01)
    mejor = None
    for poli in capas.get(nombre, ()):
        min_lat, min_lon, max_lat, max_lon = poli.bbox
        if not (
            min_lat - margen_lat <= lat <= max_lat + margen_lat
            and min_lon - margen_lon <= lon <= max_lon + margen_lon
        ):
            continue
        d = distancia_a_poligono_m(lat, lon, poli)
        if d <= radio_m and (mejor is None or d < mejor[0]):
            mejor = (d, poli)
    return mejor


def capas_en_punto(lat: float, lon: float, capas: dict) -> tuple:
    """Nombres de TODAS las capas que contienen el punto (ej. ("FRAUDE", "ZONA F"))."""
    return tuple(
        nombre
        for nombre, polis in capas.items()
        if any(punto_en_poligono(lat, lon, p) for p in polis)
    )


def capas_visibles(capas: dict, visibles) -> dict:
    """Solo las capas marcadas, para DIBUJAR; la decision siempre usa todas."""
    return {nombre: polis for nombre, polis in capas.items() if nombre in visibles}


def decidir_venta(
    lat: float,
    lon: float,
    hay_cobertura: bool | None,
    capas: dict,
    radio_m: float = RADIO_EXTENSION_M,
) -> Decision:
    """`hay_cobertura`: respuesta de WinForce; None si no se pudo obtener (se decide
    con los datos locales y la cobertura queda SIN_CONFIRMAR)."""
    en_capas = capas_en_punto(lat, lon, capas)
    if CAPA_FRAUDE in en_capas or CAPA_BLOQUEADOS in en_capas:
        return Decision(
            BLOQUEADA,
            None,
            "Zona bloqueada (fraude): no vender, no consultar el score.",
            capas=en_capas,
        )
    minimo = SCORE_PREFERENTE if CAPA_PREFERENTE in en_capas else SCORE_NORMAL

    avisos = []
    fraude = _mas_cercano(lat, lon, capas, CAPA_FRAUDE, radio_m)
    if fraude:
        avisos.append(f"Zona de fraude cercana (a {fraude[0]:.0f} m): vende con cuidado.")
    if CAPA_ZONA_F in en_capas:
        avisos.append("Zona F (significado por confirmar): no cambia la decision.")

    if hay_cobertura:
        return Decision(
            VENDER,
            minimo,
            f"Con cobertura. Score minimo para vender: {minimo}.",
            avisos=tuple(avisos),
            capas=en_capas,
        )

    cubierto = _poligono_que_contiene(lat, lon, capas, CAPA_COBERTURA)
    cercano = None if cubierto else _mas_cercano(lat, lon, capas, CAPA_COBERTURA, radio_m)

    if hay_cobertura is None:
        if cubierto:
            distancia, proyecto = 0, cubierto.nombre
            referencia = "El mapa de cobertura (copia fija) lo muestra cubierto"
        elif cercano:
            distancia, proyecto = cercano[0], cercano[1].nombre
            referencia = f"El mapa de cobertura (copia fija) muestra cobertura a {distancia:.0f} m"
        else:
            distancia, proyecto = None, ""
            referencia = (
                f"El mapa de cobertura (copia fija) no muestra cobertura a {radio_m:.0f} m"
            )
        avisos.append(f"{referencia} (sin confirmar con WinForce).")
        return Decision(
            SIN_CONFIRMAR,
            minimo,
            f"No se pudo confirmar la cobertura con WinForce. Score minimo en la zona: {minimo}.",
            distancia_m=distancia,
            proyecto=proyecto,
            avisos=tuple(avisos),
            capas=en_capas,
        )

    if cubierto:
        avisos.append(
            "WinForce dice NO aunque el mapa de cobertura (copia fija) lo cubre: "
            "confirmar antes de vender."
        )
        return Decision(
            EXTENSIBLE,
            minimo,
            "WinForce dice NO en el punto, pero el mapa de cobertura lo muestra cubierto"
            f"{f' (proyecto {cubierto.nombre})' if cubierto.nombre else ''}. "
            f"Confirmar antes de vender. Score minimo en la zona: {minimo}.",
            distancia_m=0,
            proyecto=cubierto.nombre,
            avisos=tuple(avisos),
            capas=en_capas,
        )

    if cercano:
        distancia, poli = cercano
        avisos.append("Solo por calles: no cruzar avenidas grandes de doble via.")
        return Decision(
            EXTENSIBLE,
            minimo,
            f"Sin cobertura en el punto, pero hay cobertura a {distancia:.0f} m"
            f"{f' (proyecto {poli.nombre})' if poli.nombre else ''}. Se puede extender el "
            f"servicio desde ahi. Score minimo en la zona: {minimo}.",
            distancia_m=distancia,
            proyecto=poli.nombre,
            avisos=tuple(avisos),
            capas=en_capas,
        )
    return Decision(
        SIN_COBERTURA,
        minimo,
        f"Sin cobertura en el punto ni a {radio_m:.0f} m a la redonda. "
        f"Score minimo en la zona: {minimo}.",
        avisos=tuple(avisos),
        capas=en_capas,
    )
