"""Verificacion de actualizaciones contra GitHub Releases."""

import logging

import requests

from validator_app import version

log = logging.getLogger(__name__)


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


def hay_actualizacion():
    """Devuelve el nuevo release si hay, o None si no existe / hay error."""
    try:
        release = consultar_ultimo_release()
    except Exception as exc:
        log.warning("Error consultando actualizaciones: %s", exc)
        return None
    if not release:
        return None

    commit_remoto = release.get("target_commitish") or release.get("tag_name") or ""
    if not commit_remoto or commit_remoto == version_actual():
        return None

    asset = next(
        (a for a in release.get("assets", []) if a.get("name", "").lower().endswith(".exe")),
        None,
    )
    return {
        "tag": release.get("tag_name", "?"),
        "commit": commit_remoto,
        "notes": release.get("body", ""),
        "asset": asset,
        "url_descarga": asset["browser_download_url"] if asset else None,
    }
