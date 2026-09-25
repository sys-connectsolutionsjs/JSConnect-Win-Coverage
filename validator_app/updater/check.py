"""Verificacion de actualizaciones contra GitHub Releases."""

import logging

import requests

from validator_app import version

log = logging.getLogger(__name__)

# El Release puede traer mas de un asset .exe (agente + consola owner, desde
# que ambos se publican juntos): elegir por nombre exacto, nunca por posicion
# ni por "termina en .exe" - lo segundo puede devolver el .exe equivocado.
NOMBRE_ASSET_AGENTE = "JSConnect-Win-Coverage.exe"


def version_actual() -> str:
    return version.BUILD_COMMIT


def consultar_ultimo_release():
    url = f"https://api.github.com/repos/{version.REPO_OWNER}/{version.REPO_NAME}/releases/latest"
    headers = {"User-Agent": "JSConnect-Win-Coverage", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _commit_de_tag(tag_name: str) -> str | None:
    """SHA real al que apunta el tag de un Release.

    `release["target_commitish"]` NO es un SHA: es la rama sobre la que se creo
    el tag ("main"), y como tal nunca coincide con el commit embebido en el
    .exe (version.BUILD_COMMIT) - eso hacia que hay_actualizacion() creyera
    SIEMPRE que habia una version nueva. El endpoint de commits resuelve un tag
    igual que un SHA o una rama, asi que devuelve el commit real."""
    url = f"https://api.github.com/repos/{version.REPO_OWNER}/{version.REPO_NAME}/commits/{tag_name}"
    headers = {"User-Agent": "JSConnect-Win-Coverage", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("sha")
    except Exception as exc:
        log.warning("Error resolviendo el commit del tag %s: %s", tag_name, exc)
        return None


def hay_actualizacion():
    """Devuelve el nuevo release si hay, o None si no existe / hay error."""
    try:
        release = consultar_ultimo_release()
    except Exception as exc:
        log.warning("Error consultando actualizaciones: %s", exc)
        return None
    if not release:
        return None

    tag_name = release.get("tag_name") or ""
    if not tag_name:
        return None
    commit_remoto = _commit_de_tag(tag_name)
    if not commit_remoto or commit_remoto == version_actual():
        return None

    asset = next(
        (a for a in release.get("assets", []) if a.get("name") == NOMBRE_ASSET_AGENTE),
        None,
    )
    return {
        "tag": release.get("tag_name", "?"),
        "commit": commit_remoto,
        "notes": release.get("body", ""),
        "asset": asset,
        "url_descarga": asset["browser_download_url"] if asset else None,
    }
