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


# --------------------------------------------------------------------------
# Carpeta .extension_build (la usa "Cargar descomprimida" y el boton de la consola)
# --------------------------------------------------------------------------

def _plantilla(base):
    plantilla = base / "extension"
    plantilla.mkdir(parents=True)
    (plantilla / "manifest.json").write_text(
        '{"version": "1.0.0", "host_permissions": ["http://127.0.0.1:8080/*"]}', encoding="utf-8"
    )
    (plantilla / "background.js").write_text(
        'const PROXY = "http://127.0.0.1:8080";', encoding="utf-8"
    )
    (plantilla / "icono.png").write_bytes(b"png")
    return plantilla


def test_preparar_build_usa_el_puerto_de_config_yaml(tmp_path):
    _plantilla(tmp_path)
    (tmp_path / "config.yaml").write_text(
        'proxy_host: "0.0.0.0"\nproxy_port: 9100\nproxy_token: "x"\n', encoding="utf-8"
    )
    build = ext.preparar_build(tmp_path)
    assert build == tmp_path / ".extension_build"
    assert "9100" in (build / "background.js").read_text(encoding="utf-8")
    assert "9100" in (build / "manifest.json").read_text(encoding="utf-8")
    assert "8080" not in (build / "background.js").read_text(encoding="utf-8")
    assert (build / "icono.png").exists()


def test_preparar_build_sin_config_usa_8080(tmp_path):
    _plantilla(tmp_path)
    build = ext.preparar_build(tmp_path)
    assert "8080" in (build / "background.js").read_text(encoding="utf-8")


def test_preparar_build_reemplaza_una_carpeta_vieja(tmp_path):
    _plantilla(tmp_path)
    vieja = tmp_path / ".extension_build"
    vieja.mkdir()
    (vieja / "basura.txt").write_text("x", encoding="utf-8")
    ext.preparar_build(tmp_path)
    assert not (vieja / "basura.txt").exists()


def test_preparar_build_sin_plantilla_da_error_claro(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError, match="plantilla"):
        ext.preparar_build(tmp_path)


def test_main_sin_chrome_deja_la_carpeta_y_devuelve_1(tmp_path, monkeypatch, capsys):
    """Bug 2026-10-28: sin Chrome, main() no creaba .extension_build y devolvia 0;
    el instalador marcaba 'politica registrada' y el boton de la consola owner
    mostraba una carpeta que no existia."""
    _plantilla(tmp_path)
    monkeypatch.setattr(ext, "_PROXY_DIR", tmp_path)
    monkeypatch.setattr(ext, "_localizar_chrome", lambda: None)
    monkeypatch.setattr(ext, "_puerto_proxy", lambda: 9200)
    assert ext.main([]) == 1
    build = tmp_path / ".extension_build"
    assert "9200" in (build / "background.js").read_text(encoding="utf-8")
    assert "Cargar descomprimida" in capsys.readouterr().out


def test_main_si_falla_el_crx_devuelve_1_con_la_carpeta_lista(tmp_path, monkeypatch):
    import subprocess

    _plantilla(tmp_path)
    monkeypatch.setattr(ext, "_PROXY_DIR", tmp_path)
    monkeypatch.setattr(ext, "_localizar_chrome", lambda: "chrome.exe")
    monkeypatch.setattr(ext, "_puerto_proxy", lambda: 8080)

    def falla(_chrome):
        raise subprocess.CalledProcessError(1, "chrome")

    monkeypatch.setattr(ext, "_empaquetar_crx", falla)
    assert ext.main([]) == 1
    assert (tmp_path / ".extension_build" / "manifest.json").exists()
