"""Verificacion de actualizaciones contra GitHub Releases."""

import logging
import sys
from pathlib import Path

import requests

from validator_app import version
from validator_app.updater import download

log = logging.getLogger(__name__)

TIMEOUT_INICIO = 5

# El Release puede traer mas de un asset .exe (agente + consola owner, desde
# que ambos se publican juntos): elegir por nombre exacto, nunca por posicion
# ni por "termina en .exe" - lo segundo puede devolver el .exe equivocado.
NOMBRE_ASSET_AGENTE = "JSConnect-Win-Coverage.exe"
NOMBRE_ASSET_OWNER = "JSConnect-Win-Owner.exe"


def version_actual() -> str:
    return version.BUILD_COMMIT


def es_build_real() -> bool:
    """True solo en un .exe compilado con un commit conocido (no en desarrollo)."""
    return bool(getattr(sys, "frozen", False)) and version.BUILD_COMMIT != "unknown"


def consultar_ultimo_release(timeout: float = 15):
    url = f"https://api.github.com/repos/{version.REPO_OWNER}/{version.REPO_NAME}/releases/latest"
    headers = {"User-Agent": "JSConnect-Win-Coverage", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _commit_de_tag(tag_name: str, timeout: float = 15) -> str | None:
    """SHA real al que apunta el tag de un Release.

    `release["target_commitish"]` NO es un SHA: es la rama sobre la que se creo
    el tag ("main"), y como tal nunca coincide con el commit embebido en el
    .exe (version.BUILD_COMMIT) - eso hacia que hay_actualizacion() creyera
    SIEMPRE que habia una version nueva. El endpoint de commits resuelve un tag
    igual que un SHA o una rama, asi que devuelve el commit real."""
    url = f"https://api.github.com/repos/{version.REPO_OWNER}/{version.REPO_NAME}/commits/{tag_name}"
    headers = {"User-Agent": "JSConnect-Win-Coverage", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("sha")
    except Exception as exc:
        log.warning("Error resolviendo el commit del tag %s: %s", tag_name, exc)
        return None


def ultimo_release_agente(timeout: float | None = None):
    """Ultimo Release del agente (sin compararlo con la version en ejecucion).

    None si el repo no tiene Release. Lanza si GitHub no responde o si no se
    resuelve el commit del tag: quien llama decide que hacer sin conexion."""
    extra = {} if timeout is None else {"timeout": timeout}
    release = consultar_ultimo_release(**extra)
    if not release:
        return None

    tag_name = release.get("tag_name") or ""
    if not tag_name:
        return None
    commit_remoto = _commit_de_tag(tag_name, **extra)
    if not commit_remoto:
        raise RuntimeError(f"No se pudo resolver el commit del tag {tag_name}")

    asset = next(
        (a for a in release.get("assets", []) if a.get("name") == NOMBRE_ASSET_AGENTE),
        None,
    )
    return {
        "tag": tag_name,
        "commit": commit_remoto,
        "notes": release.get("body", ""),
        "asset": asset,
        "url_descarga": asset["browser_download_url"] if asset else None,
        "nombre_asset": NOMBRE_ASSET_AGENTE,
    }


def hay_actualizacion():
    """Devuelve el nuevo release si hay, o None si no existe / hay error."""
    try:
        info = ultimo_release_agente()
    except Exception as exc:
        log.warning("Error consultando actualizaciones: %s", exc)
        return None
    if not info or info["commit"] == version_actual():
        return None
    return info


def _es_descarga_oficial(url: str | None) -> bool:
    """La URL pertenece a los Releases de ESTE repo (no se baja nada de otro sitio)."""
    prefijo = f"https://github.com/{version.REPO_OWNER}/{version.REPO_NAME}/releases/download/"
    return bool(url) and url.startswith(prefijo)


def _release_via_proxy(proxy_client):
    """(consulto, release): `consulto` es False si el proxy no dio una respuesta usable."""
    if proxy_client is None:
        return False, None
    try:
        cuerpo = proxy_client.obtener_version(timeout=TIMEOUT_INICIO)
    except Exception as exc:
        log.warning("El proxy no pudo informar la version: %s", exc)
        return False, None
    if not isinstance(cuerpo, dict) or "release" not in cuerpo:
        return False, None
    release = cuerpo["release"]
    if release and release.get("url_descarga") and not _es_descarga_oficial(
        release["url_descarga"]
    ):
        log.warning("El proxy ofrecio una descarga fuera del repo oficial; se ignora.")
        return False, None
    return True, release


def chequeo_inicio(proxy_client=None):
    """Chequeo de version al abrir el agente: (estado, info).

    Estados: "dev" (no es un .exe compilado), "actualizar" (con `info`),
    "al_dia" y "sin_conexion". Pregunta primero al proxy (que cachea GitHub y
    evita agotar el limite de la API por IP) y luego a GitHub directo."""
    if not es_build_real():
        return "dev", None

    consulto, release = _release_via_proxy(proxy_client)
    if not consulto:
        try:
            release = ultimo_release_agente(timeout=TIMEOUT_INICIO)
        except Exception as exc:
            log.warning("No se pudo comprobar la version al iniciar: %s", exc)
            return "sin_conexion", None

    if not release or not release.get("url_descarga"):
        return "al_dia", None
    if release.get("commit") == version_actual():
        return "al_dia", None
    return "actualizar", release


def hay_actualizacion_owner(ruta_exe):
    """Release nuevo para la consola owner, o None si esta al dia / no se sabe.

    A diferencia del agente (que compara commits), el owner compara el SHA-256 del
    .exe en ejecucion con el que el Release publica para JSConnect-Win-Owner.exe.
    Un Release puede reutilizar un owner viejo (solo se recompilo el agente): por
    commit el owner creeria SIEMPRE que hay una version nueva y se actualizaria en
    bucle. Por hash, si ya tiene ese mismo .exe no hay nada que hacer. Sin asset del
    owner o sin su hash en las notas, mejor None que ofrecer una descarga sin
    verificar."""
    try:
        release = consultar_ultimo_release()
    except Exception as exc:
        log.warning("Error consultando actualizaciones del owner: %s", exc)
        return None
    if not release:
        return None

    tag_name = release.get("tag_name") or ""
    asset = next(
        (a for a in release.get("assets", []) if a.get("name") == NOMBRE_ASSET_OWNER),
        None,
    )
    if not tag_name or not asset:
        return None

    notas = release.get("body", "")
    hash_remoto = download.extraer_checksum(notas, nombre_archivo=NOMBRE_ASSET_OWNER)
    if not hash_remoto:
        return None
    try:
        hash_local = download.sha256_de(Path(ruta_exe))
    except OSError as exc:
        log.warning("No se pudo leer el .exe del owner para comparar: %s", exc)
        return None
    if hash_local.lower() == hash_remoto.lower():
        return None

    return {
        "tag": tag_name,
        "commit": None,
        "notes": notas,
        "asset": asset,
        "url_descarga": asset["browser_download_url"],
        "nombre_asset": NOMBRE_ASSET_OWNER,
    }
