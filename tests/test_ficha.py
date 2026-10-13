from validator_app.gui import ficha

PERSONA = {
    "nombres": "JUAN CARLOS", "apellido_paterno": "PEREZ", "apellido_materno": "GARCIA",
    "fecha_nacimiento": "17/05/1980", "nacionalidad": "PERU",
}
DIRECCION = {
    "direccion": "PASAJE 66 189 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)",
    "departamento": "CALLAO",
    "provincia": "CALLAO", "distrito": "CALLAO", "fuente": "geofinder", "aproximada": False,
}
SCORE = {"valor": 575, "nombre": "PEREZ GARCIA JUAN CARLOS", "persona": PERSONA}


def _dict(items):
    return dict(items)


def test_etiquetas_en_el_orden_pedido():
    items = ficha.armar_ficha(SCORE, DIRECCION, "DNI", "10412031", "500 - 599")
    assert [e for e, _v in items] == [
        "NOMBRES Y APELLIDOS",
        "DOCUMENTO DE IDENTIDAD (DNI, RUC, CE)",
        "NACIONALIDAD Y FECHA DE NACIMIENTO",
        "SCORE",
        "DIRECCIÓN DETALLADA",
        "DEPARTAMENTO",
        "PROVINCIA",
        "DISTRITO",
    ]


def test_valores_completos():
    d = _dict(ficha.armar_ficha(SCORE, DIRECCION, "DNI", "10412031", "500 - 599"))
    assert d["NOMBRES Y APELLIDOS"] == "JUAN CARLOS PEREZ GARCIA"
    assert d["DOCUMENTO DE IDENTIDAD (DNI, RUC, CE)"] == "DNI 10412031"
    assert d["NACIONALIDAD Y FECHA DE NACIMIENTO"] == "PERU, 17/05/1980"
    assert d["SCORE"] == "500 - 599"
    assert d["DIRECCIÓN DETALLADA"] == "PASAJE 66 189 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)"
    assert d["DEPARTAMENTO"] == "CALLAO" and d["PROVINCIA"] == "CALLAO"
    assert d["DISTRITO"] == "CALLAO"


def test_copiar_todo_respeta_el_formato():
    items = ficha.armar_ficha(SCORE, DIRECCION, "DNI", "10412031", "500 - 599")
    assert ficha.texto_copiar_todo(items) == (
        "NOMBRES Y APELLIDOS: JUAN CARLOS PEREZ GARCIA\n"
        "DOCUMENTO DE IDENTIDAD (DNI, RUC, CE): DNI 10412031\n"
        "NACIONALIDAD Y FECHA DE NACIMIENTO: PERU, 17/05/1980\n"
        "SCORE: 500 - 599\n"
        "DIRECCIÓN DETALLADA: PASAJE 66 189 BOCANEGRA SECTOR 2 (CALLAO, CALLAO, CALLAO)\n"
        "DEPARTAMENTO: CALLAO\n"
        "PROVINCIA: CALLAO\n"
        "DISTRITO: CALLAO"
    )


def test_solo_fecha_si_no_hay_nacionalidad():
    persona = {**PERSONA, "nacionalidad": ""}
    d = _dict(ficha.armar_ficha({"persona": persona}, None, "DNI", "1", None))
    assert d["NACIONALIDAD Y FECHA DE NACIMIENTO"] == "17/05/1980"


def test_nombre_completo_con_nombres_primero_aunque_haya_razon_social():
    # Una persona natural con RUC 10 trae RazonSocial = "APELLIDOS NOMBRES": no debe ganar.
    persona = {
        "nombres": "NOEMI MATILDE", "apellido_paterno": "CARRANZA",
        "apellido_materno": "JUAPE DE SEGOVIA",
        "razon_social": "CARRANZA JUAPE DE SEGOVIA NOEMI MATILDE",
    }
    d = _dict(ficha.armar_ficha({"persona": persona}, None, "DNI", "1", None))
    assert d["NOMBRES Y APELLIDOS"] == "NOEMI MATILDE CARRANZA JUAPE DE SEGOVIA"


def test_no_duplica_apellidos_si_nombres_ya_es_el_nombre_completo():
    persona = {"nombres": "CARRANZA JUAPE NOEMI", "apellido_paterno": "CARRANZA",
               "apellido_materno": "JUAPE"}
    d = _dict(ficha.armar_ficha({"persona": persona}, None, "DNI", "1", None))
    assert d["NOMBRES Y APELLIDOS"] == "CARRANZA JUAPE NOEMI"


def test_sin_score_ni_direccion_deja_en_blanco_lo_desconocido():
    d = _dict(ficha.armar_ficha(None, None, "DNI", "10412031", None))
    assert d["NOMBRES Y APELLIDOS"] == ""
    assert d["DOCUMENTO DE IDENTIDAD (DNI, RUC, CE)"] == "DNI 10412031"
    assert d["SCORE"] == ""
    assert d["DIRECCIÓN DETALLADA"] == "" and d["DISTRITO"] == ""
    assert ficha.texto_copiar_todo(ficha.armar_ficha(None, None, None, "", None)).startswith(
        "NOMBRES Y APELLIDOS:\n"
    )


def test_ruc_usa_la_razon_social():
    score = {"nombre": "EMPRESA SAC", "persona": {"razon_social": "EMPRESA SAC"}}
    d = _dict(ficha.armar_ficha(score, None, "RUC", "20123456789", None))
    assert d["NOMBRES Y APELLIDOS"] == "EMPRESA SAC"
    assert d["DOCUMENTO DE IDENTIDAD (DNI, RUC, CE)"] == "RUC 20123456789"


def test_sin_modulo_persona_cae_al_nombre_principal():
    d = _dict(ficha.armar_ficha({"nombre": "PEREZ GARCIA JUAN"}, None, "DNI", "1", None))
    assert d["NOMBRES Y APELLIDOS"] == "PEREZ GARCIA JUAN"


def test_nunca_inventa_direccion_si_no_hay_coordenadas():
    # Solo documento: direccion/departamento/provincia/distrito van en blanco aunque el
    # reporte traiga direccion fiscal.
    score = {"persona": {**PERSONA, "direccion_fiscal": "AV. X 1"}}
    d = _dict(ficha.armar_ficha(score, None, "DNI", "1", "500 - 599"))
    assert d["DIRECCIÓN DETALLADA"] == ""


def test_rango_sin_prefijo_score():
    assert ficha.rango_sin_prefijo("SCORE: 500 - 599") == "500 - 599"
    assert ficha.rango_sin_prefijo("500 - 599") == "500 - 599"
    assert ficha.rango_sin_prefijo(None) is None
