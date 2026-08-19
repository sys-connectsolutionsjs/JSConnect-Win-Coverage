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
from typing import Any

from validator_app.core import session

TIPOS_DOCUMENTO = {"DNI": "1", "RUC": "3", "CE": "2"}
TEXTOS_DOCUMENTO = {"DNI": "DNI", "RUC": "RUC", "CE": "Carnet de extranjeria"}


class APIError(Exception):
    pass


class LoginError(APIError):
    pass


class ScoreError(APIError):
    pass


def _formato_coordenada(valor: float) -> str:
    return repr(float(valor))


class ValidatorAPI:
    def __init__(self):
        self._sesion: Any | None = None

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
        self._verificar_sesion_activa(sesion)
        self._sesion = sesion
        return self

    @staticmethod
    def _verificar_login(resp) -> None:
        if resp.status_code >= 400:
            raise LoginError(f"Error HTTP {resp.status_code} al iniciar sesion.")
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
        raise LoginError(comentario)

    @staticmethod
    def _verificar_sesion_activa(sesion) -> None:
        resp = sesion.get(
            f"{session.CONTROLLERS}/operador.php",
            params={"accion": "get_operador"},
            timeout=session.TIEMPO_LOGIN,
        )
        try:
            datos = resp.json()
        except ValueError:
            raise LoginError("No se pudo iniciar sesion (la sesion no quedo activa).") from None
        lista = datos if isinstance(datos, list) else [datos]
        ok = any(
            isinstance(x, dict) and x.get("response") == "success" for x in lista
        )
        if not ok:
            raise LoginError("No se pudo iniciar sesion (la sesion no quedo activa).")

    def _requerir_sesion(self) -> None:
        if self._sesion is None:
            raise APIError("Primero debes iniciar sesion.")

    def validar_cobertura(self, lat: float, lon: float) -> dict[str, Any]:
        self._requerir_sesion()
        resp = self._sesion.get(
            f"{session.CONTROLLERS}/coordenada.php",
            params={
                "accion": "validar_cobertura",
                "data[latitud]": _formato_coordenada(lat),
                "data[longitud]": _formato_coordenada(lon),
            },
            timeout=session.TIEMPO_COBERTURA,
        )
        datos = _json(resp, "cobertura")
        if not isinstance(datos, dict) or datos.get("response") != "success":
            comentario = datos.get("comment", "") if isinstance(datos, dict) else ""
            raise APIError(str(comentario) or "El servidor rechazo la consulta de cobertura.")
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
        return self._parsear_score(resp)

    def _parsear_score(self, resp) -> dict[str, Any]:
        capa = _json(resp, "score")
        if isinstance(capa, list):
            capa = capa[0] if capa else {}
        if not isinstance(capa, dict) or capa.get("response") != "success":
            comentario = capa.get("comment", "") if isinstance(capa, dict) else ""
            raise ScoreError(str(comentario) or "El sistema rechazo la consulta de score.")
        dato = capa.get("data")
        if not dato:
            raise ScoreError("El sistema no devolvio el reporte de score.")
        try:
            reporte = json.loads(dato)
        except (TypeError, ValueError):
            raise ScoreError("Reporte de score en formato inesperado.") from None
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
        raise APIError(f"Respuesta inesperada del servidor al consultar {contexto}.") from None


_cliente = None
_lock = threading.Lock()


def obtener_cliente() -> ValidatorAPI:
    global _cliente
    with _lock:
        if _cliente is None:
            _cliente = ValidatorAPI()
        return _cliente
