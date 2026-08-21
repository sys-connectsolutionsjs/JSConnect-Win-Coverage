"""Logica del arnes de prueba del nucleo, compartida por consola y GUI.

Ejecuta el flujo login -> cobertura -> score y devuelve las lineas de salida
(los errores se reportan como lineas "[ERROR ...]" para mostrarlas en pantalla).
"""

from __future__ import annotations

from validator_app.core import api
from validator_app.gui import fields


def ejecutar_prueba(
    usuario: str, contrasena: str, coordenadas: str, documento: str
) -> list[str]:
    lineas: list[str] = []
    usuario = usuario.strip()
    contrasena = contrasena.strip()
    documento = documento.strip()
    if not usuario or not contrasena:
        return ["[ERROR] Usuario y contrasena son obligatorios."]

    try:
        lat, lon = fields.parse_coordenadas(coordenadas)
    except ValueError as exc:
        return [f"[ERROR] {exc}"]

    try:
        cliente = api.obtener_cliente().login(usuario, contrasena)
    except api.LoginError as exc:
        return [f"[ERROR LOGIN] {exc}"]

    lineas.append("Login OK (sesion activa).")

    try:
        cobertura = cliente.validar_cobertura(lat, lon)
    except api.APIError as exc:
        lineas.append(f"[ERROR COBERTURA] {exc}")
        return lineas

    lineas.append(
        f"Cobertura: {cobertura['cobertura']} | "
        f"tipo={cobertura['tipo']} | id_celda={cobertura['id_celda']}"
    )
    if not cobertura["hay_cobertura"]:
        lineas.append("Sin cobertura: no se valida score.")
        return lineas

    try:
        tipo = fields.detectar_tipo_documento(documento)
    except ValueError as exc:
        lineas.append(f"[ERROR] {exc}")
        return lineas

    try:
        score = cliente.validar_score(
            tipo, documento, lat, lon, cobertura=cobertura["cobertura"]
        )
    except api.ScoreError as exc:
        lineas.append(f"[ERROR SCORE] {exc}")
        return lineas

    lineas.append(f"Score: {score['valor']} | riesgo: {score['riesgo']}")
    if score["nombre"]:
        lineas.append(f"Titular: {score['nombre']} ({score['documento']})")
    if score["deuda_total"] is not None:
        lineas.append(f"Deuda total: {score['deuda_total']}")
    return lineas
