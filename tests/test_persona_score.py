"""Datos de la persona dentro del reporte del score (modulos 602 y 877 de Equifax)."""

from validator_app.core.api import ValidatorAPI


def _reporte(*modulos, principales=None):
    return {
        "soapBody": {
            "ns3GetReporteOnlineResponse": {
                "ns2ReporteCrediticio": {
                    "DatosPrincipales": principales
                    or {"TipoDocumento": "1", "NumeroDocumento": "10412031",
                        "Nombre": "PEREZ GARCIA JUAN CARLOS"},
                    "Modulos": {"Modulo": list(modulos)},
                }
            }
        }
    }


SCORE = {
    "Codigo": "822",
    "Data": {"ns3ResumenScoreRP3": {"Puntaje": "575", "NivelRiesgo": "ALTO", "Conclusion": "x"}},
}
PERSONA = {
    "Codigo": "602",
    "Data": {
        "ns3DirectorioPersona": {
            # Equifax manda Nombres como "APELLIDOS NOMBRES" (nombre completo)
            "Nombres": "PEREZ GARCIA JUAN CARLOS", "PrimerNombre": "JUAN",
            "SegundoNombre": "CARLOS", "ApellidoPaterno": "PEREZ", "ApellidoMaterno": "GARCIA",
            "TipoDocumento": "DNI", "NumeroDocumento": "10412031",
            "FechaNacimiento": "1980-05-17T00:00:00", "Sexo": "M", "EstadoCivil": "SOLTERO",
            "Nacionalidad": "PERUANA", "Telefono": "999111222",
        }
    },
}
SUNAT = {
    "Codigo": "877",
    "Data": {
        "ns3DirectorioSUNAT": {
            "Directorio": {
                "RUC": "20123456789", "RazonSocial": "EMPRESA SAC",
                "EstadoContribuyente": "ACTIVO", "CondicionContribuyente": "HABIDO",
                "Direcciones": {"Direccion": "AV. LOS OLIVOS 123 - LIMA"},
            }
        }
    },
}


def test_extrae_datos_de_la_persona():
    r = ValidatorAPI._extraer_score(_reporte(SCORE, PERSONA))
    p = r["persona"]
    assert p["nombres"] == "JUAN CARLOS"
    assert p["apellido_paterno"] == "PEREZ" and p["apellido_materno"] == "GARCIA"
    assert p["fecha_nacimiento"] == "17/05/1980"
    assert p["sexo"] == "M" and p["estado_civil"] == "SOLTERO"
    assert p["nacionalidad"] == "PERUANA"
    assert "lugar_nacimiento" not in p
    assert r["valor"] == 575


def test_fecha_en_varios_formatos():
    def fecha(valor):
        mod = {"Codigo": "602", "Data": {"ns3DirectorioPersona": {"FechaNacimiento": valor}}}
        return ValidatorAPI._extraer_score(_reporte(mod))["persona"]["fecha_nacimiento"]

    assert fecha("19800517") == "17/05/1980"
    assert fecha("17/05/1980") == "17/05/1980"
    assert fecha("1980-05-17") == "17/05/1980"
    assert fecha("mayo de 1980") == "mayo de 1980"
    assert fecha("") == ""


def test_nombres_usa_primer_y_segundo_nombre_no_el_nombre_completo():
    mod = {
        "Codigo": "602",
        "Data": {"ns3DirectorioPersona": {
            "Nombres": "RIOS LOPEZ ANA", "PrimerNombre": "ANA", "SegundoNombre": "",
            "ApellidoPaterno": "RIOS", "ApellidoMaterno": "LOPEZ",
        }},
    }
    assert ValidatorAPI._extraer_score(_reporte(mod))["persona"]["nombres"] == "ANA"


def test_sin_primer_nombre_cae_al_campo_nombres():
    mod = {"Codigo": "602", "Data": {"ns3DirectorioPersona": {"Nombres": "ANA MARIA"}}}
    assert ValidatorAPI._extraer_score(_reporte(mod))["persona"]["nombres"] == "ANA MARIA"


def test_extrae_datos_sunat_de_un_ruc():
    r = ValidatorAPI._extraer_score(_reporte(SCORE, SUNAT))
    p = r["persona"]
    assert p["razon_social"] == "EMPRESA SAC"
    assert p["estado_contribuyente"] == "ACTIVO"
    assert p["condicion_contribuyente"] == "HABIDO"
    assert p["direccion_fiscal"] == "AV. LOS OLIVOS 123 - LIMA"


def test_direccion_fiscal_como_lista_toma_la_primera():
    mod = {
        "Codigo": "877",
        "Data": {
            "ns3DirectorioSUNAT": {
                "Directorio": {"Direcciones": {"Direccion": ["A 1", "B 2"]}}
            }
        },
    }
    assert ValidatorAPI._extraer_score(_reporte(mod))["persona"]["direccion_fiscal"] == "A 1"


def test_sin_modulos_de_persona_queda_vacio_pero_con_nombre_principal():
    r = ValidatorAPI._extraer_score(_reporte(SCORE))
    assert r["persona"] == {}
    assert r["nombre"] == "PEREZ GARCIA JUAN CARLOS"


def test_reporte_sin_estructura_no_rompe():
    r = ValidatorAPI._extraer_score({})
    assert r["persona"] == {} and r["valido"] is False


def test_scoreresponse_del_proxy_incluye_persona_opcional():
    from validator_app.proxy.server import ScoreResponse

    base = {"valor": 1, "riesgo": None, "conclusion": None, "deuda_total": None,
            "nombre": None, "documento": None, "valido": True}
    assert ScoreResponse(**base).persona is None
    r = ScoreResponse(**base, persona={"nombres": "ANA"})
    assert r.model_dump()["persona"] == {"nombres": "ANA"}


def test_proxyclient_lee_persona_y_tolera_proxy_viejo():
    from unittest import mock

    from validator_app.proxy.client import ProxyClient

    c = ProxyClient("http://p", "t")
    resp = mock.Mock()
    c._request_with_retry = mock.Mock(return_value=resp)
    resp.json.return_value = {"valor": 500, "valido": True, "persona": {"nombres": "ANA"}}
    assert c.validar_score("DNI", "10412031").persona == {"nombres": "ANA"}
    resp.json.return_value = {"valor": 500, "valido": True}
    assert c.validar_score("DNI", "10412031").persona is None
