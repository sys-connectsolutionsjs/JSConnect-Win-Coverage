"""Prueba de cobertura/score usando una cookie PHPSESSID capturada del navegador.

Uso (requiere PYTHONPATH=. si validator_app no esta instalado editable):
    python tools/probar_con_cookie.py

No pide usuario/contrasena: se asume que ya iniciaste sesion manualmente en el
navegador (incluyendo el 2FA de Microsoft) y copiaste el valor de la cookie
PHPSESSID (F12 -> Application -> Cookies -> https://appwinforce.win.pe).

Si la primera prueba falla, permite reintentar con el User-Agent real del
navegador (F12 -> Console -> escribe `navigator.userAgent` y copia el
resultado) para descartar que el servidor ate la sesion al User-Agent.
"""

import getpass

from validator_app.core import api, session
from validator_app.gui import fields


def _diagnosticar(
    php_sessid: str,
    user_agent: str | None,
    endpoint: str = "operador.php",
    params: dict | None = None,
) -> None:
    """Hace una peticion cruda a un endpoint y muestra lo que el core oculta."""
    sesion = session.crear_sesion()
    sesion.cookies.set("PHPSESSID", php_sessid, domain="appwinforce.win.pe")
    if user_agent:
        sesion.headers["User-Agent"] = user_agent
    if params is None:
        params = {"accion": "get_operador"}

    etiqueta = "real del navegador" if user_agent else "del core"
    print(f"\n--- Diagnostico {endpoint} (User-Agent: {etiqueta}) ---")
    print(f"Headers enviados: {dict(sesion.headers)}")
    try:
        resp = sesion.get(
            f"{session.CONTROLLERS}/{endpoint}",
            params=params,
            timeout=session.TIEMPO_LOGIN,
        )
    except Exception as e:
        print(f"[ERROR RED] {e}")
        return
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', '?')}")
    print(f"URL final: {resp.url}")
    if resp.history:
        print(f"Hubo redirects: {[r.url for r in resp.history]}")
    else:
        print("Sin redirects (respuesta directa).")
    cuerpo = resp.text[:300]
    print(f"Cuerpo (primeros 300 chars): {cuerpo!r}")
    try:
        datos = resp.json()
        print(f"JSON parseado OK: {datos}")
    except ValueError:
        print("El cuerpo NO es JSON valido (ver arriba).")


def _diagnosticar_ambos(php_sessid: str, user_agent: str | None, lat: float, lon: float) -> None:
    _diagnosticar(php_sessid, user_agent, "operador.php", {"accion": "get_operador"})
    _diagnosticar(
        php_sessid,
        user_agent,
        "coordenada.php",
        {
            "accion": "validar_cobertura",
            "data[latitud]": repr(float(lat)),
            "data[longitud]": repr(float(lon)),
        },
    )


def _diagnosticar_score(
    cliente, tipo: str, documento: str, lat: float, lon: float, cobertura: str
) -> None:
    """Repite la peticion cruda de score_cliente e inspecciona la profundidad
    real del encoding de 'data', sin pasar por _extraer_score (que asume dict).
    No imprime nombre/deuda/documento del reporte real."""
    import json as _json_mod

    data = {
        "tipo_doc": api.TIPOS_DOCUMENTO[tipo],
        "documento_identidad": documento,
        "tipo_doc_value": api.TIPOS_DOCUMENTO[tipo],
        "tipo_doc_text": api.TEXTOS_DOCUMENTO[tipo],
        "canal_id": "0",
        "longitud": repr(float(lon)),
        "latitud": repr(float(lat)),
        "serv_cobertura": cobertura,
    }
    for campo in (
        "distrito", "departamento", "provincia", "tipo_via", "nom_via",
        "nom_hu", "numero", "ubigeo", "cod_postal", "serv_poligono",
        "zona_riesgo", "equi_fecha_sunat", "nse", "equi_deuda",
        "dir_tipo_via", "dir_via", "dir_numero", "direccion_instalacion",
        "desc_vlr_segmentacion", "desc_vlr_condominio",
    ):
        data[campo] = ""
    payload = {"accion": "score_cliente"}
    payload.update({f"data[{clave}]": str(valor) for clave, valor in data.items()})

    resp = cliente._sesion.post(f"{session.CONTROLLERS}/cliente.php", data=payload)
    print(f"\n--- Diagnostico score_cliente ---\nStatus: {resp.status_code}")
    capa = api._json(resp, "score-diagnostico")
    if isinstance(capa, list):
        capa = capa[0] if capa else {}
    response = capa.get("response") if isinstance(capa, dict) else "?"
    print(f"type(capa)={type(capa)} response={response}")
    dato = capa.get("data") if isinstance(capa, dict) else None
    profundidad = 0
    valor = dato
    while isinstance(valor, str) and profundidad < 4:
        print(f"Profundidad {profundidad}: type=str len={len(valor)} inicio={valor[:60]!r}")
        try:
            valor = _json_mod.loads(valor)
        except ValueError:
            print(f"  -> json.loads fallo en profundidad {profundidad}, se detiene aqui.")
            break
        profundidad += 1
    print(f"Profundidad final: type={type(valor)} (se necesitaron {profundidad} json.loads)")


def _probar_variante(php_sessid: str, user_agent: str | None, lat: float, lon: float) -> bool:
    """Intenta validar cobertura con una variante de headers. Devuelve True si funciono."""
    cliente = api.ValidatorAPI()
    cliente.set_session_cookies({"PHPSESSID": php_sessid})
    if user_agent:
        cliente._sesion.headers["User-Agent"] = user_agent

    try:
        cobertura = cliente.validar_cobertura(lat, lon)
    except Exception as e:
        print(f"[FALLO] {e}")
        return False
    print(f"[OK] Cobertura: {cobertura}")
    return True


def main() -> int:
    php_sessid = getpass.getpass("Pega el valor de la cookie PHPSESSID: ").strip()
    if not php_sessid:
        print("[ERROR] Cookie vacia. Cancelado.")
        return 1

    coords = input("Coordenadas (lat, lon): ").strip()
    try:
        lat, lon = fields.parse_coordenadas(coords)
    except Exception as e:
        print(f"[ERROR] Coordenadas invalidas: {e}")
        return 1

    print("\n=== Variante 1: headers del core (User-Agent hardcodeado) ===")
    ok_core = _probar_variante(php_sessid, None, lat, lon)

    if ok_core:
        print("\nLa cookie funciona con los headers actuales del core.")
    else:
        _diagnosticar_ambos(php_sessid, None, lat, lon)

        user_agent = ""
        while not user_agent:
            user_agent = input(
                "\n>>> PASO REQUERIDO <<<\n"
                "En tu navegador (donde SI funciona la sesion): F12 -> pestana Console ->\n"
                "escribe navigator.userAgent y presiona Enter -> copia el texto que te\n"
                "devuelve (sin las comillas) y pegalo aqui.\n"
                "Escribe 'omitir' si de verdad quieres saltarte este paso: "
            ).strip()
            if user_agent.lower() == "omitir":
                print(
                    "[OMITIDO] Variante 2 no probada. "
                    "La hipotesis del User-Agent queda sin confirmar."
                )
                return 1
            if not user_agent:
                print("[AVISO] Quedo vacio. Este paso es el que falta para confirmar la causa.")

        print("\n=== Variante 2: User-Agent real del navegador ===")
        ok_real = _probar_variante(php_sessid, user_agent, lat, lon)
        if not ok_real:
            _diagnosticar_ambos(php_sessid, user_agent, lat, lon)
        else:
            print(
                "\n[CONCLUSION] La variante con User-Agent real SI funciono. "
                "El servidor ata la sesion al User-Agent."
            )
        return 1

    documento = input(
        "\nNumero de documento (DNI/RUC/CE) para probar score, o Enter para omitir: "
    ).strip()
    if not documento:
        return 0

    cliente = api.ValidatorAPI()
    cliente.set_session_cookies({"PHPSESSID": php_sessid})
    cobertura_data = cliente.validar_cobertura(lat, lon)
    if not isinstance(cobertura_data, dict) or not cobertura_data.get("hay_cobertura"):
        print("Sin cobertura, no se prueba score.")
        return 0

    tipo = fields.detectar_tipo_documento(documento)
    try:
        score = cliente.validar_score(
            tipo, documento, lat, lon, cobertura=cobertura_data["cobertura"]
        )
    except Exception as e:
        print(f"[ERROR SCORE] {e}")
        _diagnosticar_score(cliente, tipo, documento, lat, lon, cobertura_data["cobertura"])
        return 1

    print(
        f"\nScore: valor={score.get('valor')} riesgo={score.get('riesgo')} "
        f"valido={score.get('valido')}"
    )
    print(
        "(nombre/documento/deuda_total no se imprimen aqui por privacidad; "
        "revisa la variable 'score' en el debugger si lo necesitas)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
