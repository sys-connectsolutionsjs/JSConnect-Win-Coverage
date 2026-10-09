"""Textos y estilos del resultado de zona (sin tkinter, para poder probarlos)."""

from validator_app.core import geo
from validator_app.proxy.client import ProxySesionCaducadaError

_ETIQUETAS = {
    geo.VENDER: ("CON COBERTURA", "success"),
    geo.EXTENSIBLE: ("EXTENSIBLE", "warning"),
    geo.SIN_COBERTURA: ("SIN COBERTURA", "danger"),
    geo.BLOQUEADA: ("ZONA BLOQUEADA — no vender", "danger"),
    geo.SIN_CONFIRMAR: ("COBERTURA SIN CONFIRMAR", "warning"),
}


def resumen_decision(decision: geo.Decision) -> tuple[str, str]:
    """(texto de varias lineas, estilo ttkbootstrap) para mostrar la decision."""
    etiqueta, estilo = _ETIQUETAS[decision.estado]
    lineas = [etiqueta]
    if decision.estado == geo.EXTENSIBLE:
        if decision.distancia_m:
            lineas[0] += f" — cobertura a {decision.distancia_m:.0f} m"
            if decision.proyecto:
                lineas[0] += f" ({decision.proyecto})"
        else:
            lineas[0] += " — el mapa lo muestra cubierto"
    if decision.score_minimo is not None:
        lineas.append(f"Score minimo en la zona: {decision.score_minimo}")
    if decision.capas:
        lineas.append("Este punto está en: " + ", ".join(decision.capas))
    lineas.extend(f"• {aviso}" for aviso in decision.avisos)
    return "\n".join(lineas), estilo


def veredicto_score(valor, minimo) -> tuple[str, bool] | None:
    """Si el score alcanza el minimo de la zona; None si falta alguno de los datos."""
    if valor is None or minimo is None:
        return None
    if valor >= minimo:
        return f"Alcanza el minimo de la zona ({minimo}).", True
    return f"NO alcanza el minimo de la zona ({minimo}).", False


def plan_score(decision: geo.Decision) -> str:
    """Que hacer con el score segun la zona: "pedir", "confirmar" (el asesor
    decide, el score gasta una consulta de Equifax) o "no" pedirlo."""
    return {geo.VENDER: "pedir", geo.EXTENSIBLE: "confirmar"}.get(decision.estado, "no")


def condiciones_de_venta(decision: geo.Decision) -> str:
    """Condiciones de venta de la zona del punto (solo datos locales)."""
    if decision.estado == geo.BLOQUEADA:
        return "No se vende: zona bloqueada (fraude), ni con score 999."
    texto = f"Se vende solo con score {decision.score_minimo} o más"
    if geo.CAPA_PREFERENTE in decision.capas:
        texto += " (zona Preferente 2)"
    texto += "."
    cercana = next((a for a in decision.avisos if a.startswith("Zona de fraude cercana")), None)
    return f"{texto}\n• {cercana}" if cercana else texto


def mensaje_sin_cobertura(motivo: str, decision: geo.Decision) -> str:
    """Texto cuando WinForce no dio la cobertura pero el resto de los datos si."""
    return (
        f"No se pudo obtener la información de cobertura ({motivo}).\n"
        "Del resto de los datos sí. Condiciones de venta de esta zona:\n"
        f"{condiciones_de_venta(decision)}"
    )


def motivo_cobertura(exc: Exception, limite: int = 80) -> str:
    """Motivo corto de por que no se pudo obtener la cobertura (para el asesor)."""
    if isinstance(exc, ProxySesionCaducadaError):
        return (
            "sesión del proxy caducada; el administrador ya fue avisado, "
            "reintenta en 2-3 minutos"
        )
    texto = " ".join(str(exc).split()) or exc.__class__.__name__
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"
