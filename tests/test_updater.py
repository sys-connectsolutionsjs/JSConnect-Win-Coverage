"""validator_app/updater: chequeo de actualizaciones y descarga/reemplazo.

Sin red real: requests.get se monkeypatchea con una respuesta falsa.
"""

from __future__ import annotations

import pytest

from validator_app.updater import check, download


class _Respuesta:
    def __init__(self, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self._content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data

    def iter_content(self, chunk_size):
        yield self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _release(assets, target_commitish="deadbeef", tag_name="v2026.09.22", body=""):
    return {
        "tag_name": tag_name,
        "target_commitish": target_commitish,
        "body": body,
        "assets": assets,
    }


ASSET_AGENTE = {
    "name": "JSConnect-Win-Coverage.exe",
    "browser_download_url": "https://example.com/JSConnect-Win-Coverage.exe",
}
ASSET_OWNER = {
    "name": "JSConnect-Win-Owner.exe",
    "browser_download_url": "https://example.com/JSConnect-Win-Owner.exe",
}


def test_hay_actualizacion_elige_el_asset_del_agente_aunque_el_owner_venga_primero(monkeypatch):
    """El release trae DOS .exe; el owner aparece antes en la lista. El agente
    debe seguir eligiendo el suyo por nombre exacto, no por posicion."""
    release = _release(assets=[ASSET_OWNER, ASSET_AGENTE])
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)
    monkeypatch.setattr(check, "version_actual", lambda: "otro-commit")

    info = check.hay_actualizacion()

    assert info["asset"]["name"] == "JSConnect-Win-Coverage.exe"
    assert info["url_descarga"] == "https://example.com/JSConnect-Win-Coverage.exe"


def test_hay_actualizacion_asset_ausente_si_solo_esta_el_del_owner(monkeypatch):
    release = _release(assets=[ASSET_OWNER])
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)
    monkeypatch.setattr(check, "version_actual", lambda: "otro-commit")

    info = check.hay_actualizacion()

    assert info["asset"] is None
    assert info["url_descarga"] is None


def test_hay_actualizacion_none_si_mismo_commit(monkeypatch):
    release = _release(assets=[ASSET_AGENTE], target_commitish="mismo")
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)
    monkeypatch.setattr(check, "version_actual", lambda: "mismo")

    assert check.hay_actualizacion() is None


def test_hay_actualizacion_none_si_no_hay_release(monkeypatch):
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: None)
    assert check.hay_actualizacion() is None


def test_hay_actualizacion_none_si_consulta_lanza(monkeypatch):
    def falla():
        raise RuntimeError("sin red")

    monkeypatch.setattr(check, "consultar_ultimo_release", falla)
    assert check.hay_actualizacion() is None


def test_consultar_ultimo_release_404_devuelve_none(monkeypatch):
    monkeypatch.setattr(
        check.requests, "get", lambda *a, **k: _Respuesta(status_code=404)
    )
    assert check.consultar_ultimo_release() is None


NOTAS_DOS_ARCHIVOS = (
    "## JSConnect-Win-Coverage.exe\n"
    "SHA-256: `" + "a" * 64 + "`\n"
    "\n"
    "## JSConnect-Win-Owner.exe\n"
    "SHA-256: `" + "b" * 64 + "`\n"
)


def test_extraer_checksum_con_dos_archivos_no_cruza_los_hashes():
    assert download.extraer_checksum(NOTAS_DOS_ARCHIVOS, "JSConnect-Win-Coverage.exe") == "a" * 64
    assert download.extraer_checksum(NOTAS_DOS_ARCHIVOS, "JSConnect-Win-Owner.exe") == "b" * 64


def test_extraer_checksum_un_solo_archivo_sin_nombre_mantiene_compatibilidad():
    notas = f"Checksum SHA-256:\n\n{'c' * 64}\nJSConnect-Win-Coverage.exe"
    assert download.extraer_checksum(notas) == "c" * 64


def test_extraer_checksum_nombre_no_encontrado_devuelve_none():
    assert download.extraer_checksum(NOTAS_DOS_ARCHIVOS, "OtroArchivo.exe") is None


def test_aplicar_actualizacion_requiere_exe_congelado(monkeypatch):
    monkeypatch.setattr(download.sys, "frozen", False, raising=False)
    with pytest.raises(RuntimeError, match="compilado"):
        download.aplicar_actualizacion({"url_descarga": "https://example.com/x.exe"})


def test_aplicar_actualizacion_sin_url_falla(monkeypatch):
    monkeypatch.setattr(download.sys, "frozen", True, raising=False)
    with pytest.raises(ValueError, match="asset"):
        download.aplicar_actualizacion({"url_descarga": None})


def test_aplicar_actualizacion_checksum_no_coincide(monkeypatch, tmp_path):
    monkeypatch.setattr(download.sys, "frozen", True, raising=False)
    monkeypatch.setattr(download.sys, "executable", str(tmp_path / "JSConnect-Win-Coverage.exe"))
    monkeypatch.setattr(download.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        download.requests, "get",
        lambda *a, **k: _Respuesta(content=b"contenido-falso"),
    )

    info = {
        "url_descarga": "https://example.com/JSConnect-Win-Coverage.exe",
        "notes": (
            "## JSConnect-Win-Coverage.exe\n"
            "SHA-256: `" + "f" * 64 + "`\n"
        ),
    }
    with pytest.raises(ValueError, match="Checksum no coincide"):
        download.aplicar_actualizacion(info)


def test_aplicar_actualizacion_ok_lanza_el_updater(monkeypatch, tmp_path):
    exe_actual = tmp_path / "JSConnect-Win-Coverage.exe"
    exe_actual.write_bytes(b"viejo")
    monkeypatch.setattr(download.sys, "frozen", True, raising=False)
    monkeypatch.setattr(download.sys, "executable", str(exe_actual))
    monkeypatch.setattr(download.tempfile, "gettempdir", lambda: str(tmp_path))

    contenido = b"contenido-nuevo"
    checksum_real = download.hashlib.sha256(contenido).hexdigest().upper()
    monkeypatch.setattr(
        download.requests, "get", lambda *a, **k: _Respuesta(content=contenido)
    )

    procesos = []
    monkeypatch.setattr(
        download.subprocess, "Popen", lambda *a, **k: procesos.append((a, k))
    )

    info = {
        "url_descarga": "https://example.com/JSConnect-Win-Coverage.exe",
        "notes": (
            "## JSConnect-Win-Coverage.exe\n"
            f"SHA-256: `{checksum_real}`\n"
        ),
    }
    assert download.aplicar_actualizacion(info) is True
    assert procesos, "deberia lanzar el updater.bat via subprocess.Popen"
