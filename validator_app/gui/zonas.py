"""Textos y estilos del resultado (sin tkinter, para poder probarlos).

Desde el 2026-11-03 el resultado se muestra en tres tarjetas (Cobertura, Zona y
Score) con frases cortas; lo tecnico va a `detalle_para_copiar()`. Cada tarjeta
es (titulo, nota, estilo ttkbootstrap)."""

from validator_app.core import geo
from validator_app.proxy.client import ProxySesionCaducadaError

SIN_DATO = "—"


def plan_score(decision: geo.Decision) -> str:
    """Que hacer con el score segun la zona: "pedir", "confirmar" (el asesor
    decide, el score gasta una consulta de Equifax) o "no" pedirlo."""
    return {geo.VENDER: "pedir", geo.EXTENSIBLE: "confirmar"}.get(decision.estado, "no")


def _metros(distancia: float) -> str:
    return f"{distancia:.0f} m"


def tarjeta_cobertura(hay_cobertura: bool | None, decision: geo.Decision | None) -> tuple:
    """`hay_cobertura`: respuesta de WinForce; None si no respondio."""
    if decision is None:
        return SIN_DATO, "sin coordenadas", "secondary"
    if hay_cobertura:
        return "✔ Hay cobertura", "", "success"
    distancia = decision.distancia_m
    if hay_cobertura is None:
        if decision.estado == geo.BLOQUEADA:
            nota = ""
        elif distancia is None:
            nota = "el mapa no lo cubre"
        elif distancia == 0:
            nota = "el mapa lo cubre"
        else:
            nota = f"cobertura a {_metros(distancia)}"
        return "▲ Reintenta", nota, "warning"
    if decision.estado == geo.EXTENSIBLE:
        if not distancia:
            return "▲ Confirma con soporte", "el mapa lo cubre", "warning"
        return "▲ Posible extensión", f"a {_metros(distancia)}", "warning"
    return "✖ Sin cobertura", "", "danger"


def tarjeta_zona(decision: geo.Decision | None) -> tuple:
    """El fraude solo informa (nota en ambar); los codigos bloqueados no se venden."""
    if decision is None:
        return SIN_DATO, "sin coordenadas", "secondary"
    if decision.estado == geo.BLOQUEADA:
        return "✖ Código bloqueado", "no vender", "danger"
    titulo = "Preferente 2" if geo.CAPA_PREFERENTE in decision.capas else "Normal"
    notas = [f"mín. {decision.score_minimo}"]
    if decision.en_fraude:
        notas.append("⚠ zona de fraude")
    elif decision.fraude_m is not None:
        notas.append(f"⚠ fraude a {_metros(decision.fraude_m)}")
    estilo = "warning" if len(notas) > 1 else "info"
    return titulo, "\n".join(notas), estilo


def tarjeta_score(
    valor: int | None = None,
    vendible: bool | None = None,
    minimo: int | None = None,
    motivo: str = "",
) -> tuple:
    """Veredicto primero. Con `valor`, si vende segun el rango y el minimo de la
    zona; sin el, `motivo`: no_consultado, pendiente, error, no_disponible,
    bloqueada, sin_documento, listo o consultando (estos dos, del boton del Mapa)."""
    if valor is not None:
        detalle = f"{valor} (mín. {minimo})" if minimo is not None else f"{valor}"
        if not vendible:
            return "✖ NO VENDE", "rango no vendible", "danger"
        if minimo is not None and valor < minimo:
            return "✖ NO VENDE", detalle, "danger"
        return "✔ VENDE", detalle, "success"
    if motivo == "bloqueada":
        return "No se consulta", "código bloqueado", "secondary"
    if motivo == "error":
        return "▲ Sin score", "reintenta", "warning"
    if motivo == "no_disponible":
        return "▲ Sin score", "puntaje no disponible", "warning"
    if motivo == "consultando":
        return "Consultando…", "", "secondary"
    nota = {
        "pendiente": "pendiente de confirmar",
        "listo": "pulsa CONSULTAR SCORE",
        "sin_documento": "ingresa un documento",
    }.get(motivo, "no se consultó")
    titulo = f"Necesita {minimo}+" if minimo is not None and motivo != "sin_documento" else SIN_DATO
    return titulo, nota, "secondary"


def linea_estado(cobertura_exc: Exception | None, score_exc: Exception | None) -> str:
    """Una sola linea con lo que fallo y que hacer; el error exacto va al detalle."""
    partes = []
    if isinstance(cobertura_exc, ProxySesionCaducadaError) or isinstance(
        score_exc, ProxySesionCaducadaError
    ):
        partes.append("Sesión del proxy caducada · reintenta en 2-3 min")
    if cobertura_exc is not None and not isinstance(cobertura_exc, ProxySesionCaducadaError):
        partes.append("WinForce no respondió · reintenta")
    if score_exc is not None and not isinstance(score_exc, ProxySesionCaducadaError):
        partes.append("No se pudo obtener el score · reintenta")
    return "\n".join(partes)


def _error_exacto(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def detalle_para_copiar(
    *, fecha, version, lat, lon, tipo_doc, num_doc, hay_cobertura, decision,
    score_valor, rango, cobertura_exc, score_exc,
) -> str:
    """Texto plano para mandar por WhatsApp a soporte: todos los datos y el error
    exacto, sin recortar."""
    lineas = [f"JSConnect-Win · {fecha} · versión {version}"]
    lineas.append(f"Coordenadas: {lat}, {lon}" if lat is not None else "Coordenadas: —")
    if num_doc:
        lineas.append(f"Documento: {tipo_doc} {num_doc}")
    if lat is not None:
        respuesta = {True: "sí", False: "no", None: "sin respuesta"}[hay_cobertura]
        lineas.append(f"Cobertura WinForce: {respuesta}")
    if decision is not None:
        lineas.append(f"Decisión: {decision.mensaje}")
        lineas.append("Capas del punto: " + (", ".join(decision.capas) or "ninguna"))
        if decision.distancia_m:
            proyecto = f" ({decision.proyecto})" if decision.proyecto else ""
            lineas.append(f"Cobertura más cercana: {_metros(decision.distancia_m)}{proyecto}")
        if decision.en_fraude:
            lineas.append("Fraude: zona de fraude (informativo)")
        elif decision.fraude_m is not None:
            lineas.append(f"Fraude: a {_metros(decision.fraude_m)} (informativo)")
        if decision.score_minimo is not None:
            lineas.append(f"Score mínimo de la zona: {decision.score_minimo}")
    if score_valor is not None:
        lineas.append(f"Score: {score_valor} ({rango})" if rango else f"Score: {score_valor}")
    if cobertura_exc is not None:
        lineas.append(f"Error de cobertura: {_error_exacto(cobertura_exc)}")
    if score_exc is not None:
        lineas.append(f"Error de score: {_error_exacto(score_exc)}")
    return "\n".join(lineas)

