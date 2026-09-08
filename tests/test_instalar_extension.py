"""Tests de las partes puras de validator_app.proxy._instalar_extension.

El `main()` (empaquetar el .crx con chrome, escribir el registro) se prueba a
mano en la PC del proxy.
"""

import hashlib

from validator_app.proxy import _instalar_extension as ext


def test_crx_id_formato_y_determinismo():
    der = b"clave-publica-de-prueba"
    got = ext._crx_id(der)
    assert len(got) == 32
    assert all("a" <= c <= "p" for c in got)
    assert ext._crx_id(der) == got  # determinista

    # coincide con la definición: sha256(der) -> 32 primeros hex -> 0-f a a-p
    esperado = "".join(
        chr(ord("a") + int(h, 16)) for h in hashlib.sha256(der).hexdigest()[:32]
    )
    assert got == esperado


def test_crx_id_cambia_con_la_clave():
    assert ext._crx_id(b"clave-A") != ext._crx_id(b"clave-B")


def test_render_updates_xml():
    xml = ext._render_updates_xml("abcdefabcdefabcdefabcdefabcdefab", "file:///C:/x/e.crx", "1.2.3")
    assert "abcdefabcdefabcdefabcdefabcdefab" in xml
    assert "file:///C:/x/e.crx" in xml
    assert 'version="1.2.3"' in xml or "version='1.2.3'" in xml
    assert xml.lstrip().startswith("<?xml")
