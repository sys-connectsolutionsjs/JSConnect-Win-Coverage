"""Chequeo obligatorio de version al iniciar el agente (estilo Steam).

Sin red real: el proxy, GitHub y la descarga se sustituyen por dobles.
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


def _release(assets, tag_name="v2026.09.22", body=""):
    return {"tag_name": tag_name, "target_commitish": "main", "body": body, "assets": assets}


ASSET_AGENTE = {
    "name": "JSConnect-Win-Coverage.exe",
    "browser_download_url": "https://example.com/JSConnect-Win-Coverage.exe",
}
ASSET_OWNER = {
    "name": "JSConnect-Win-Owner.exe",
    "browser_download_url": "https://example.com/JSConnect-Win-Owner.exe",
}


def _url_oficial(nombre="JSConnect-Win-Coverage.exe"):
    return (
        f"https://github.com/{check.version.REPO_OWNER}/{check.version.REPO_NAME}"
        f"/releases/download/v2026.11.20/{nombre}"
    )


def _info_release(commit="commit-nuevo", url=None):
    url = url or _url_oficial()
    return {
        "tag": "v2026.11.20",
        "commit": commit,
        "notes": "",
        "asset": {"name": "JSConnect-Win-Coverage.exe", "browser_download_url": url},
        "url_descarga": url,
        "nombre_asset": "JSConnect-Win-Coverage.exe",
    }


class _ProxyFalso:
    def __init__(self, cuerpo=None, falla=False):
        self.cuerpo = cuerpo
        self.falla = falla
        self.llamadas = []

    def obtener_version(self, timeout=5.0):
        self.llamadas.append(timeout)
        if self.falla:
            raise RuntimeError("proxy caido")
        return self.cuerpo


@pytest.fixture
def build_real(monkeypatch):
    monkeypatch.setattr(check, "es_build_real", lambda: True)
    monkeypatch.setattr(check, "version_actual", lambda: "commit-viejo")


def _github_no_debe_llamarse(timeout=None):
    raise AssertionError("no deberia consultar GitHub directo")


def test_ultimo_release_agente_devuelve_el_release_sin_comparar(monkeypatch):
    release = _release(assets=[ASSET_OWNER, ASSET_AGENTE], body="notas")
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)
    monkeypatch.setattr(check, "_commit_de_tag", lambda tag: "sha-remoto")

    info = check.ultimo_release_agente()

    assert info["commit"] == "sha-remoto"
    assert info["tag"] == "v2026.09.22"
    assert info["notes"] == "notas"
    assert info["url_descarga"] == "https://example.com/JSConnect-Win-Coverage.exe"


def test_ultimo_release_agente_none_si_no_hay_release(monkeypatch):
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: None)
    assert check.ultimo_release_agente() is None


def test_ultimo_release_agente_lanza_si_no_hay_red(monkeypatch):
    def falla():
        raise RuntimeError("sin red")

    monkeypatch.setattr(check, "consultar_ultimo_release", falla)
    with pytest.raises(RuntimeError):
        check.ultimo_release_agente()


def test_ultimo_release_agente_lanza_si_no_resuelve_el_commit(monkeypatch):
    release = _release(assets=[ASSET_AGENTE])
    monkeypatch.setattr(check, "consultar_ultimo_release", lambda: release)
    monkeypatch.setattr(check, "_commit_de_tag", lambda tag: None)
    with pytest.raises(RuntimeError, match="commit"):
        check.ultimo_release_agente()


def test_ultimo_release_agente_pasa_el_timeout_a_las_dos_consultas(monkeypatch):
    vistos = []

    def release(timeout=15):
        vistos.append(("release", timeout))
        return _release(assets=[ASSET_AGENTE])

    def commit(tag, timeout=15):
        vistos.append(("commit", timeout))
        return "sha"

    monkeypatch.setattr(check, "consultar_ultimo_release", release)
    monkeypatch.setattr(check, "_commit_de_tag", commit)

    check.ultimo_release_agente(timeout=5)

    assert vistos == [("release", 5), ("commit", 5)]


def test_es_build_real_exige_exe_compilado_y_commit_conocido(monkeypatch):
    monkeypatch.setattr(check.sys, "frozen", True, raising=False)
    monkeypatch.setattr(check.version, "BUILD_COMMIT", "a" * 40)
    assert check.es_build_real() is True

    monkeypatch.setattr(check.version, "BUILD_COMMIT", "unknown")
    assert check.es_build_real() is False

    monkeypatch.setattr(check.version, "BUILD_COMMIT", "a" * 40)
    monkeypatch.setattr(check.sys, "frozen", False, raising=False)
    assert check.es_build_real() is False


def test_chequeo_inicio_en_desarrollo_no_consulta_nada(monkeypatch):
    monkeypatch.setattr(check, "es_build_real", lambda: False)
    monkeypatch.setattr(check, "ultimo_release_agente", _github_no_debe_llamarse)
    proxy = _ProxyFalso(cuerpo={"release": _info_release()})

    assert check.chequeo_inicio(proxy) == ("dev", None)
    assert proxy.llamadas == []


def test_chequeo_inicio_usa_el_proxy_primero_y_no_toca_github(monkeypatch, build_real):
    monkeypatch.setattr(check, "ultimo_release_agente", _github_no_debe_llamarse)
    info = _info_release("commit-nuevo")
    proxy = _ProxyFalso(cuerpo={"release": info})

    estado, devuelto = check.chequeo_inicio(proxy)

    assert estado == "actualizar"
    assert devuelto == info
    assert len(proxy.llamadas) == 1


def test_chequeo_inicio_al_dia_si_el_proxy_trae_el_mismo_commit(monkeypatch, build_real):
    monkeypatch.setattr(check, "ultimo_release_agente", _github_no_debe_llamarse)
    proxy = _ProxyFalso(cuerpo={"release": _info_release("commit-viejo")})
    assert check.chequeo_inicio(proxy) == ("al_dia", None)


def test_chequeo_inicio_al_dia_si_el_proxy_dice_que_no_hay_release(monkeypatch, build_real):
    monkeypatch.setattr(check, "ultimo_release_agente", _github_no_debe_llamarse)
    proxy = _ProxyFalso(cuerpo={"release": None})
    assert check.chequeo_inicio(proxy) == ("al_dia", None)


def test_chequeo_inicio_sin_proxy_va_a_github_con_timeout_corto(monkeypatch, build_real):
    vistos = []

    def github(timeout=None):
        vistos.append(timeout)
        return _info_release("commit-nuevo")

    monkeypatch.setattr(check, "ultimo_release_agente", github)

    estado, info = check.chequeo_inicio(None)

    assert estado == "actualizar"
    assert info["commit"] == "commit-nuevo"
    assert vistos == [check.TIMEOUT_INICIO]
    assert check.TIMEOUT_INICIO <= 5


@pytest.mark.parametrize("proxy", [_ProxyFalso(cuerpo=None), _ProxyFalso(falla=True)])
def test_chequeo_inicio_si_el_proxy_no_responde_cae_a_github(monkeypatch, build_real, proxy):
    monkeypatch.setattr(
        check, "ultimo_release_agente", lambda timeout=None: _info_release("commit-viejo")
    )
    assert check.chequeo_inicio(proxy) == ("al_dia", None)


def test_chequeo_inicio_sin_conexion_si_proxy_y_github_fallan(monkeypatch, build_real):
    def github(timeout=None):
        raise RuntimeError("sin red")

    monkeypatch.setattr(check, "ultimo_release_agente", github)
    assert check.chequeo_inicio(_ProxyFalso(falla=True)) == ("sin_conexion", None)


def test_chequeo_inicio_github_sin_release_es_al_dia(monkeypatch, build_real):
    monkeypatch.setattr(check, "ultimo_release_agente", lambda timeout=None: None)
    assert check.chequeo_inicio(None) == ("al_dia", None)


def test_chequeo_inicio_ignora_una_descarga_del_proxy_que_no_es_del_repo_oficial(
    monkeypatch, build_real
):
    """El proxy podria estar comprometido: un agente nunca debe bajar un .exe de
    una URL que no sea la de Releases de ESTE repo. Se descarta la respuesta y se
    pregunta a GitHub directo."""
    hostil = _info_release(
        "commit-nuevo", url="https://evil.example.com/JSConnect-Win-Coverage.exe"
    )
    oficial = _info_release("commit-nuevo")
    monkeypatch.setattr(check, "ultimo_release_agente", lambda timeout=None: oficial)

    estado, info = check.chequeo_inicio(_ProxyFalso(cuerpo={"release": hostil}))

    assert estado == "actualizar"
    assert info["url_descarga"] == _url_oficial()


def test_chequeo_inicio_release_sin_asset_del_agente_no_ofrece_actualizar(
    monkeypatch, build_real
):
    info = _info_release("commit-nuevo")
    info["url_descarga"] = None
    monkeypatch.setattr(check, "ultimo_release_agente", lambda timeout=None: info)
    assert check.chequeo_inicio(None) == ("al_dia", None)


def _preparar_descarga(monkeypatch, tmp_path, contenido):
    exe_actual = tmp_path / "JSConnect-Win-Coverage.exe"
    exe_actual.write_bytes(b"viejo")
    monkeypatch.setattr(download.sys, "frozen", True, raising=False)
    monkeypatch.setattr(download.sys, "executable", str(exe_actual))
    monkeypatch.setattr(download.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        download.requests, "get", lambda *a, **k: _Respuesta(content=contenido)
    )
    procesos = []
    monkeypatch.setattr(download.subprocess, "Popen", lambda *a, **k: procesos.append(a))
    return procesos


def test_aplicar_actualizacion_acepta_checksum_en_minusculas(monkeypatch, tmp_path):
    contenido = b"contenido-nuevo"
    procesos = _preparar_descarga(monkeypatch, tmp_path, contenido)
    checksum = download.hashlib.sha256(contenido).hexdigest().lower()

    info = {
        "url_descarga": "https://example.com/JSConnect-Win-Coverage.exe",
        "notes": f"## JSConnect-Win-Coverage.exe\nSHA-256: `{checksum}`\n",
    }

    assert download.aplicar_actualizacion(info) is True
    assert procesos


def test_aplicar_actualizacion_rechaza_un_release_sin_checksum(monkeypatch, tmp_path):
    """Con la instalacion automatica no se acepta un .exe que no se pueda verificar."""
    procesos = _preparar_descarga(monkeypatch, tmp_path, b"sin-hash")

    info = {"url_descarga": "https://example.com/JSConnect-Win-Coverage.exe", "notes": "sin hash"}

    with pytest.raises(ValueError, match=r"(?i)checksum"):
        download.aplicar_actualizacion(info)
    assert procesos == []
