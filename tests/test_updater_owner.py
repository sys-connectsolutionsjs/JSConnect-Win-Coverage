"""Actualizacion de la consola owner: compara por SHA-256 y comparte el flujo del agente.

Sin red real ni cmd.exe: consultar_ultimo_release y requests.get/Popen se monkeypatchean.
"""

from __future__ import annotations

import pytest

from validator_app.updater import check, download

ASSET_AGENTE = {
    "name": "JSConnect-Win-Coverage.exe",
    "browser_download_url": "https://example.com/JSConnect-Win-Coverage.exe",
}
ASSET_OWNER = {
    "name": "JSConnect-Win-Owner.exe",
    "browser_download_url": "https://example.com/JSConnect-Win-Owner.exe",
}


class _Respuesta:
    def __init__(self, content=b""):
        self._content = content

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _notas(hash_agente="A" * 64, hash_owner="B" * 64):
    return (
        f"## JSConnect-Win-Coverage.exe\nSHA-256: {hash_agente}\n\n"
        f"## JSConnect-Win-Owner.exe\nSHA-256: {hash_owner}\n\n"
        "## Que trae\n- algo\n"
    )


def _release(assets, body, tag="v2026.10.07.1"):
    return {"tag_name": tag, "target_commitish": "main", "body": body, "assets": assets}


@pytest.fixture
def exe_owner(tmp_path):
    ruta = tmp_path / "JSConnect-Win-Owner.exe"
    ruta.write_bytes(b"owner-viejo")
    return ruta


def test_owner_ofrece_actualizacion_si_el_hash_difiere(monkeypatch, exe_owner):
    release = _release([ASSET_AGENTE, ASSET_OWNER], _notas(hash_owner="B" * 64))
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)

    info = check.hay_actualizacion_owner(exe_owner)

    assert info["tag"] == "v2026.10.07.1"
    assert info["nombre_asset"] == "JSConnect-Win-Owner.exe"
    assert info["url_descarga"] == "https://example.com/JSConnect-Win-Owner.exe"


def test_owner_al_dia_si_el_hash_coincide(monkeypatch, exe_owner):
    mismo = download.sha256_de(exe_owner)
    monkeypatch.setattr(
        check, "consultar_ultimo_release",
        lambda: _release([ASSET_OWNER], _notas(hash_owner=mismo)),
    )
    assert check.hay_actualizacion_owner(exe_owner) is None


def test_owner_compara_sin_distinguir_mayusculas(monkeypatch, exe_owner):
    mismo = download.sha256_de(exe_owner).lower()
    monkeypatch.setattr(
        check, "consultar_ultimo_release",
        lambda: _release([ASSET_OWNER], _notas(hash_owner=mismo)),
    )
    assert check.hay_actualizacion_owner(exe_owner) is None


def test_owner_no_toma_el_hash_del_agente(monkeypatch, exe_owner):
    """El release trae dos bloques de checksum: el owner solo mira el suyo."""
    mismo = download.sha256_de(exe_owner)
    release = _release([ASSET_AGENTE, ASSET_OWNER], _notas(hash_agente="C" * 64, hash_owner=mismo))
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)
    assert check.hay_actualizacion_owner(exe_owner) is None


def test_owner_none_si_el_release_no_trae_su_asset(monkeypatch, exe_owner):
    """Release solo del agente: aunque el hash 'difiera', no hay nada que descargar."""
    monkeypatch.setattr(
        check, "consultar_ultimo_release", lambda: _release([ASSET_AGENTE], _notas())
    )
    assert check.hay_actualizacion_owner(exe_owner) is None


def test_owner_none_si_las_notas_no_traen_su_hash(monkeypatch, exe_owner):
    """Sin hash no se ofrece una descarga que no se puede verificar."""
    notas = "## JSConnect-Win-Coverage.exe\nSHA-256: " + "A" * 64 + "\n"
    monkeypatch.setattr(
        check, "consultar_ultimo_release", lambda: _release([ASSET_OWNER], notas)
    )
    assert check.hay_actualizacion_owner(exe_owner) is None


def test_owner_none_sin_release_o_con_error_de_red(monkeypatch, exe_owner):
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: None)
    assert check.hay_actualizacion_owner(exe_owner) is None

    def falla():
        raise RuntimeError("sin red")

    monkeypatch.setattr(check, "consultar_ultimo_release", falla)
    assert check.hay_actualizacion_owner(exe_owner) is None


def test_owner_none_si_no_puede_leer_su_propio_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(
        check, "consultar_ultimo_release", lambda: _release([ASSET_OWNER], _notas())
    )
    assert check.hay_actualizacion_owner(tmp_path / "no-existe.exe") is None


def test_agente_sigue_marcando_su_asset(monkeypatch):
    release = _release([ASSET_OWNER, ASSET_AGENTE], _notas())
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)
    monkeypatch.setattr(check, "version_actual", lambda: "viejo")
    monkeypatch.setattr(check, "_commit_de_tag", lambda tag: "nuevo")

    assert check.hay_actualizacion()["nombre_asset"] == "JSConnect-Win-Coverage.exe"


def _preparar_descarga(monkeypatch, tmp_path, contenido):
    exe_actual = tmp_path / "JSConnect-Win-Owner.exe"
    exe_actual.write_bytes(b"viejo")
    monkeypatch.setattr(download.sys, "frozen", True, raising=False)
    monkeypatch.setattr(download.sys, "executable", str(exe_actual))
    monkeypatch.setattr(download.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: _Respuesta(contenido))
    procesos = []
    monkeypatch.setattr(download.subprocess, "Popen", lambda *a, **k: procesos.append(a))
    return procesos


def test_aplicar_actualizacion_del_owner_usa_su_asset_y_su_checksum(monkeypatch, tmp_path):
    contenido = b"owner-nuevo"
    procesos = _preparar_descarga(monkeypatch, tmp_path, contenido)
    hash_owner = download.hashlib.sha256(contenido).hexdigest().upper()
    info = {
        "url_descarga": "https://example.com/JSConnect-Win-Owner.exe",
        "nombre_asset": "JSConnect-Win-Owner.exe",
        # el hash del agente es distinto: debe usarse el del bloque del owner
        "notes": _notas(hash_agente="F" * 64, hash_owner=hash_owner),
    }

    assert download.aplicar_actualizacion(info) is True

    assert procesos
    assert (tmp_path / "jsconnect_update" / "JSConnect-Win-Owner.exe").read_bytes() == contenido
    bat = (tmp_path / "jsconnect_update" / "updater.bat").read_text(encoding="utf-8")
    assert "JSConnect-Win-Owner.exe" in bat


def test_aplicar_actualizacion_del_owner_rechaza_checksum_incorrecto(monkeypatch, tmp_path):
    _preparar_descarga(monkeypatch, tmp_path, b"owner-manipulado")
    info = {
        "url_descarga": "https://example.com/JSConnect-Win-Owner.exe",
        "nombre_asset": "JSConnect-Win-Owner.exe",
        "notes": _notas(hash_owner="E" * 64),
    }
    with pytest.raises(ValueError, match="Checksum no coincide"):
        download.aplicar_actualizacion(info)
