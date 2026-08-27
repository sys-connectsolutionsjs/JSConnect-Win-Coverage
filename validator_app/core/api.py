"""Cliente de la API interna del sistema de validacion (Fase 1).

Flujo descubierto en la Fase 0 (ver tools/captura.json y AGENTS.md):
- login: POST controllers/acceso.php -> cookie PHPSESSID.
- cobertura: GET controllers/coordenada.php?accion=validar_cobertura.
- score: POST controllers/cliente.php con accion=score_cliente; la respuesta
  es JSON con el reporte SOAP de Equifax dentro de un string ("data").
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from validator_app.core import session

TIPOS_DOCUMENTO = {"DNI": "1", "RUC": "3", "CE": "2"}
TEXTOS_DOCUMENTO = {"DNI": "DNI", "RUC": "RUC", "CE": "Carnet de extranjeria"}


class APIError(Exception):
    def __init__(self, message: str, code: str = "ERR_UNKNOWN"):
        super().__init__(message)
        self.code = code


class LoginError(APIError):
    def __init__(self, message: str, code: str = "ERR_LOGIN"):
        super().__init__(message, code)


class ScoreError(APIError):
    def __init__(self, message: str, code: str = "ERR_SCORE"):
        super().__init__(message, code)


class CoberturaError(APIError):
    def __init__(self, message: str, code: str = "ERR_COBERTURA"):
        super().__init__(message, code)


class SessionError(APIError):
    def __init__(self, message: str, code: str = "ERR_SESSION"):
        super().__init__(message, code)


class NetworkError(APIError):
    def __init__(self, message: str, code: str = "ERR_NETWORK"):
        super().__init__(message, code)


class ConfigError(APIError):
    def __init__(self, message: str, code: str = "ERR_CONFIG"):
        super().__init__(message, code)


ERROR_CODES: dict[str, dict[str, str]] = {
    "ERR_UNKNOWN": {
        "category": "General",
        "description": "Error desconocido no clasificado",
    },
    "ERR_LOGIN": {
        "category": "Autenticacion",
        "description": "Error en login contra WinForce",
    },
    "ERR_LOGIN_CREDENTIALS": {
        "category": "Autenticacion",
        "description": "Credenciales incorrectas",
    },
    "ERR_LOGIN_SESSION": {
        "category": "Autenticacion",
        "description": "Login OK pero sesion no quedo activa",
    },
    "ERR_LOGIN_2FA": {
        "category": "Autenticacion",
        "description": "Login requiere 2FA Microsoft (no automatizable)",
    },
    "ERR_SESSION": {
        "category": "Sesion",
        "description": "Error de sesion (expirada, invalida, no iniciada)",
    },
    "ERR_SESSION_EXPIRED": {
        "category": "Sesion",
        "description": "Sesion expirada por inactividad (>120s)",
    },
    "ERR_SESSION_COOKIES": {
        "category": "Sesion",
        "description": "Error guardando/restaurando cookies de sesion",
    },
    "ERR_COBERTURA": {
        "category": "Cobertura",
        "description": "Error consultando cobertura",
    },
    "ERR_COBERTURA_INVALID": {
        "category": "Cobertura",
        "description": "Respuesta invalida del servidor de cobertura",
    },
    "ERR_SCORE": {
        "category": "Score",
        "description": "Error consultando score crediticio",
    },
    "ERR_SCORE_PARSE": {
        "category": "Score",
        "description": "Error parseando reporte SOAP de Equifax",
    },
    "ERR_SCORE_MISSING": {
        "category": "Score",
        "description": "Reporte sin puntaje valido",
    },
    "ERR_NETWORK": {
        "category": "Red",
        "description": "Error de conexion/timeout de red",
    },
    "ERR_NETWORK_TIMEOUT": {
        "category": "Red",
        "description": "Timeout en peticion HTTP",
    },
    "ERR_NETWORK_DNS": {
        "category": "Red",
        "description": "Error resolviendo DNS",
    },
    "ERR_CONFIG": {
        "category": "Configuracion",
        "description": "Error de configuracion (token, URL, keyring)",
    },
    "ERR_CONFIG_KEYRING": {
        "category": "Configuracion",
        "description": "Error accediendo a Windows Keyring",
    },
    "ERR_CONFIG_PROXY": {
        "category": "Configuracion",
        "description": "Proxy no configurado o invalido",
    },
    "ERR_PROXY_AUTH": {
        "category": "Proxy",
        "description": "Token de proxy invalido o IP no permitida",
    },
    "ERR_PROXY_SERVER": {
        "category": "Proxy",
        "description": "Error interno del servidor proxy",
    },
    "ERR_PROXY_UNAVAILABLE": {
        "category": "Proxy",
        "description": "Proxy no disponible (caido, firewall)",
    },
    "ERR_VALIDATION": {
        "category": "Validacion",
        "description": "Error validando entrada (coordenadas, documento)",
    },
    "ERR_VALIDATION_COORDS": {
        "category": "Validacion",
        "description": "Formato de coordenadas invalido",
    },
    "ERR_VALIDATION_DOC": {
        "category": "Validacion",
        "description": "Tipo/documento invalido",
    },
    "ERR_ACTIVATION": {
        "category": "Activacion",
        "description": "Error de activacion/licencia",
    },
    "ERR_ACTIVATION_INVALID": {
        "category": "Activacion",
        "description": "Codigo de activacion invalido o de otra maquina",
    },
    "ERR_UPDATER": {
        "category": "Actualizacion",
        "description": "Error buscando/aplicando actualizaciones",
    },
}


def _diagnostico(resp) -> str:
    """Resumen tecnico de una respuesta (sin datos sensibles) para errores."""
    tipo = "?"
    if hasattr(resp, "headers"):
        for clave, valor in resp.headers.items():
            if clave.lower() == "content-type":
                tipo = valor
                break
    cuerpo = getattr(resp, "text", "") or ""
    if cuerpo:
        cuerpo = f" body={cuerpo[:80]!r}"
    return f"HTTP {resp.status_code} {tipo}{cuerpo}"


def _formato_coordenada(valor: float) -> str:
    return repr(float(valor))


class ValidatorAPI:
    def __init__(self):
        self._sesion: Any | None = None
        self._last_activity: float = 0
        self._session_max_idle: int = 120

    def login(self, usuario: str, contrasena: str) -> ValidatorAPI:
        sesion = session.crear_sesion()
        resp = sesion.post(
            f"{session.CONTROLLERS}/acceso.php",
            data={
                "accion": "iniciar_sesion",
                "username": usuario,
                "password": contrasena,
            },
            timeout=session.TIEMPO_LOGIN,
        )
        self._verificar_login(resp)
        self._verificar_sesion_activa(sesion, _diagnostico(resp))
        self._sesion = sesion
        self._last_activity = time.time()
        return self

    @staticmethod
    def _verificar_login(resp) -> None:
        if resp.status_code >= 400:
            raise LoginError(f"Error HTTP {resp.status_code} al iniciar sesion.", "ERR_LOGIN")
        try:
            datos = resp.json()
        except ValueError:
            return
        lista = datos if isinstance(datos, list) else [datos]
        for item in lista:
            if isinstance(item, dict) and item.get("response") == "success":
                return
        comentario = "Credenciales incorrectas"
        if lista and isinstance(lista[0], dict):
            comentario = str(lista[0].get("comment", comentario))
        raise LoginError(comentario, "ERR_LOGIN_CREDENTIALS")

    @staticmethod
    def _verificar_sesion_activa(sesion, diagnostico_login: str = "?") -> None:
        resp = sesion.get(
            f"{session.CONTROLLERS}/operador.php",
            params={"accion": "get_operador"},
            timeout=session.TIEMPO_LOGIN,
        )
        detalle_operador = _diagnostico(resp)
        try:
            datos = resp.json()
        except ValueError:
            raise LoginError(
                "No se pudo iniciar sesion (la sesion no quedo activa). "
                f"[{diagnostico_login}; operador: {detalle_operador}]",
                "ERR_LOGIN_SESSION",
            ) from None
        lista = datos if isinstance(datos, list) else [datos]
        ok = any(
            isinstance(x, dict) and x.get("response") == "success" for x in lista
        )
        if not ok:
            comentario = ""
            if lista and isinstance(lista[0], dict):
                comentario = f" ({lista[0].get('comment', '')})"
            raise LoginError(
                "No se pudo iniciar sesion (la sesion no quedo activa). "
                f"[{diagnostico_login}; operador: {detalle_operador}]{comentario}",
                "ERR_LOGIN_SESSION",
            )

    def _requerir_sesion(self) -> None:
        if self._sesion is None:
            raise SessionError("Primero debes iniciar sesion.", "ERR_SESSION")

    def auto_relogin_if_needed(self, credentials: tuple[str, str] | None = None) -> None:
        """Re-login silencioso si sesión >120s idle o expirada."""
        if self._sesion is None:
            return
        if self._last_activity == 0:
            return
        if time.time() - self._last_activity > self._session_max_idle:
            if credentials:
                self.login(*credentials)
            else:
                raise SessionError(
                    "Sesion expirada y no hay credenciales para re-login automatico",
                    "ERR_SESSION_EXPIRED",
                )

    def get_session_cookies(self) -> dict[str, str]:
        """Exporta cookies de sesión para persistencia (keyring)."""
        if self._sesion is None:
            return {}
        return dict(self._sesion.cookies)

    def set_session_cookies(self, cookies: dict[str, str]) -> None:
        """Restaura cookies de sesión desde persistencia."""
        if self._sesion is None:
            self._sesion = session.crear_sesion()
        for name, value in cookies.items():
            self._sesion.cookies.set(name, value, domain="appwinforce.win.pe")

    def _update_activity(self) -> None:
        self._last_activity = time.time()

    def validar_cobertura(self, lat: float, lon: float) -> dict[str, Any]:
        self._requerir_sesion()
        self.auto_relogin_if_needed()
        resp = self._sesion.get(
            f"{session.CONTROLLERS}/coordenada.php",
            params={
                "accion": "validar_cobertura",
                "data[latitud]": _formato_coordenada(lat),
                "data[longitud]": _formato_coordenada(lon),
            },
            timeout=session.TIEMPO_COBERTURA,
        )
        self._update_activity()
        datos = _json(resp, "cobertura")
        if not isinstance(datos, dict) or datos.get("response") != "success":
            comentario = datos.get("comment", "") if isinstance(datos, dict) else ""
            raise CoberturaError(
                str(comentario) or "El servidor rechazo la consulta de cobertura.",
                "ERR_COBERTURA_INVALID",
            )
        valor = str(datos.get("cobertura", "")).upper()
        return {
            "hay_cobertura": valor == "SI",
            "cobertura": valor,
            "tipo": datos.get("tipo", ""),
            "id_celda": datos.get("id_celda", ""),
            "comment": datos.get("comment", ""),
        }

    def validar_score(
        self,
        tipo_documento: str,
        numero: str,
        lat: float,
        lon: float,
        cobertura: str = "NO",
        geodata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._requerir_sesion()
        self.auto_relogin_if_needed()
        data = {
            "tipo_doc": TIPOS_DOCUMENTO[tipo_documento],
            "documento_identidad": numero,
            "tipo_doc_value": TIPOS_DOCUMENTO[tipo_documento],
            "tipo_doc_text": TEXTOS_DOCUMENTO[tipo_documento],
            "canal_id": "0",
            "longitud": _formato_coordenada(lon),
            "latitud": _formato_coordenada(lat),
            "serv_cobertura": cobertura,
        }
        campos_vacios = (
            "distrito", "departamento", "provincia", "tipo_via", "nom_via",
            "nom_hu", "numero", "ubigeo", "cod_postal", "serv_poligono",
            "zona_riesgo", "equi_fecha_sunat", "nse", "equi_deuda",
            "dir_tipo_via", "dir_via", "dir_numero", "direccion_instalacion",
            "desc_vlr_segmentacion", "desc_vlr_condominio",
        )
        for campo in campos_vacios:
            data[campo] = ""
        if geodata:
            data.update({clave: valor for clave, valor in geodata.items() if valor is not None})
        payload = {"accion": "score_cliente"}
        payload.update({f"data[{clave}]": str(valor) for clave, valor in data.items()})
        resp = self._sesion.post(
            f"{session.CONTROLLERS}/cliente.php",
            data=payload,
            timeout=session.TIEMPO_SCORE,
        )
        self._update_activity()
        return self._parsear_score(resp)

    def _parsear_score(self, resp) -> dict[str, Any]:
        capa = _json(resp, "score")
        if isinstance(capa, list):
            capa = capa[0] if capa else {}
        if not isinstance(capa, dict) or capa.get("response") != "success":
            comentario = capa.get("comment", "") if isinstance(capa, dict) else ""
            raise ScoreError(
                str(comentario) or "El sistema rechazo la consulta de score.",
                "ERR_SCORE",
            )
        dato = capa.get("data")
        if not dato:
            raise ScoreError("El sistema no devolvio el reporte de score.", "ERR_SCORE_MISSING")
        # El reporte llega doble-encodificado (confirmado contra el servidor real:
        # 2 capas de json.loads antes de obtener el dict). Se decodifica de forma
        # tolerante a profundidad, con tope de seguridad, en vez de asumir un
        # numero fijo de capas.
        reporte = dato
        for _ in range(3):
            if not isinstance(reporte, str):
                break
            try:
                reporte = json.loads(reporte)
            except (TypeError, ValueError):
                raise ScoreError(
                    "Reporte de score en formato inesperado.", "ERR_SCORE_PARSE"
                ) from None
        if not isinstance(reporte, dict):
            raise ScoreError("Reporte de score en formato inesperado.", "ERR_SCORE_PARSE")
        return self._extraer_score(reporte)

    @staticmethod
    def _extraer_score(reporte) -> dict[str, Any]:
        credit = (
            reporte.get("soapBody", {})
            .get("ns3GetReporteOnlineResponse", {})
            .get("ns2ReporteCrediticio", reporte)
        )
        nombre = None
        documento = None
        puntaje = None
        riesgo = None
        conclusion = None
        deuda = None

        def recorrer(obj) -> None:
            nonlocal nombre, documento, puntaje, riesgo, conclusion, deuda
            if isinstance(obj, dict):
                datos_principales = obj.get("DatosPrincipales")
                if isinstance(datos_principales, dict):
                    nombre = datos_principales.get("Nombre") or nombre
                    documento = datos_principales.get("NumeroDocumento") or documento
                if puntaje is None and "Puntaje" in obj and "NivelRiesgo" in obj:
                    valor = obj.get("Puntaje")
                    if valor not in (None, ""):
                        try:
                            puntaje = int(valor)
                        except (TypeError, ValueError):
                            puntaje = None
                        riesgo = obj.get("NivelRiesgo")
                        conclusion = obj.get("Conclusion")
                if deuda is None and "DeudaTotal" in obj:
                    deuda = obj.get("DeudaTotal")
                for valor in obj.values():
                    recorrer(valor)
            elif isinstance(obj, list):
                for item in obj:
                    recorrer(item)

        recorrer(credit)
        return {
            "valor": puntaje,
            "riesgo": riesgo,
            "conclusion": conclusion,
            "deuda_total": deuda,
            "nombre": nombre,
            "documento": documento,
            "valido": puntaje is not None,
        }

    def validar(
        self, lat: float, lon: float, tipo_documento: str, numero: str
    ) -> dict[str, Any]:
        cobertura = self.validar_cobertura(lat, lon)
        score = None
        if cobertura["hay_cobertura"]:
            score = self.validar_score(
                tipo_documento,
                numero,
                lat,
                lon,
                cobertura=cobertura["cobertura"],
            )
        return {"cobertura": cobertura, "score": score}


def _json(resp, contexto: str):
    try:
        return resp.json()
    except ValueError:
        pass
    # Algunos endpoints anteponen un BOM UTF-8 a la respuesta JSON; requests
    # (json.loads) no lo tolera, aunque el resto del contenido sea valido.
    texto = getattr(resp, "text", "")
    if texto.startswith("﻿"):
        try:
            return json.loads(texto[1:])
        except ValueError:
            pass
    raise APIError(
        f"Respuesta inesperada del servidor al consultar {contexto}. "
        f"[{_diagnostico(resp)}]",
        "ERR_NETWORK",
    )


_cliente = None
_lock = threading.Lock()


def obtener_cliente() -> ValidatorAPI:
    global _cliente
    with _lock:
        if _cliente is None:
            _cliente = ValidatorAPI()
        return _cliente
