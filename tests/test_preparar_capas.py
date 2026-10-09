"""tools/preparar_capas.py: fuentes privadas (KMZ, KML de fraude, zonas.txt) -> capas.json.gz."""

import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import preparar_capas as pc

from validator_app.core import geo

CUADRO = (
    "-77.10,-12.00,0 -77.10,-11.90,0 -77.00,-11.90,0 -77.00,-12.00,0 -77.10,-12.00,0"
)


def _kml(cuerpo: str) -> str:
    return (
        '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"{cuerpo}</Document></kml>"
    )


def _placemark(nombre: str) -> str:
    return (
        f"<Placemark><name>{nombre}</name><Polygon><outerBoundaryIs><LinearRing>"
        f"<coordinates>{CUADRO}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>"
    )


@pytest.fixture
def datos(tmp_path):
    carpeta = tmp_path / "datos_capas"
    carpeta.mkdir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        placemarks = _placemark("P1") + _placemark("P2")
        z.writestr("doc.kml", _kml(f"<Folder><name>cobertura_win_2</name>{placemarks}</Folder>"))
    (carpeta / "COBERTURA_JUNIO.kmz").write_bytes(buf.getvalue())
    (carpeta / "zona_fraude.kml").write_text(_kml(_placemark("VMT")), encoding="utf-8")
    triangulo = "[[[-12.0,-77.1],[-11.9,-77.1],[-11.9,-77.0]]]"
    lineas = [
        f"var ZONA_{nombre}_POLYGONS_DATA = {triangulo};"
        for nombre in ("F", "PREFERENTE_2", "CODIGOS_BLOQUEADOS")
    ]
    (carpeta / "zonas.txt").write_text("\n".join(lineas), encoding="utf-8")
    return carpeta


def test_preparar_genera_las_cinco_capas(datos, tmp_path):
    salida = tmp_path / "out" / "capas.json.gz"
    conteo = pc.preparar(datos, salida)
    assert conteo == {
        geo.CAPA_COBERTURA: 2,
        geo.CAPA_FRAUDE: 1,
        geo.CAPA_PREFERENTE: 1,
        geo.CAPA_BLOQUEADOS: 1,
        geo.CAPA_ZONA_F: 1,
    }
    cargadas = geo.cargar_capas_embebidas(salida)
    assert [p.nombre for p in cargadas[geo.CAPA_COBERTURA]] == ["P1", "P2"]


def test_preparar_avisa_que_archivos_faltan(datos, tmp_path):
    (datos / "zona_fraude.kml").unlink()
    with pytest.raises(FileNotFoundError, match=r"zona_fraude\.kml"):
        pc.preparar(datos, tmp_path / "capas.json.gz")


def test_preparar_rechaza_fuentes_vacias(datos, tmp_path):
    (datos / "zonas.txt").write_text("// vacio", encoding="utf-8")
    with pytest.raises(ValueError, match=r"zonas\.txt"):
        pc.preparar(datos, tmp_path / "capas.json.gz")
