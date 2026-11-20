"""Logica del nucleo JS de los prototipos web, ejecutada con node y comparada con Python.

Sin navegador: `datos.js` y `nucleo.js` se cargan en un contexto vacio (sin `document`),
asi se prueba el modelo (clasificacion del score, parseo, sesion) sin tocar el DOM.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from validator_app.gui import fields, ficha, main_window

RAIZ = Path(__file__).resolve().parents[1] / "validator_app" / "web" / "prototipos"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node no esta instalado")

PUNTAJES = [0, 1, 150, 200, 201, 300, 380, 400, 401, 534, 600, 601, 612, 700, 800, 801, 900, 901, 950, 999]
INVALIDOS = [-1, 1000, 12.5, None, "abc", True]
DOCUMENTOS = ["00000001", "12345678", "12345678901", "A12345678", "123456789", "1234567", "  12345678 ", " ", "abc", ""]
COORDENADAS = [
    "-12.0, -77.0",
    "-12;-77",
    " -12.5 ,  -77.5 ",
    "-12,-77,1",
    "abc, 1",
    "91, 0",
    "0, 181",
    "",
    "-12.0",
    "0x10, 1",
]
CASOS = ["inicial", "vende", "no_vende", "extensible", "bloqueado", "error_cobertura", "cargando"]

HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const [, , dir, entradaRuta] = process.argv;
const entrada = JSON.parse(fs.readFileSync(entradaRuta, 'utf8'));
const ctx = {};
ctx.window = ctx;
vm.createContext(ctx);
for (const archivo of ['datos.js', 'nucleo.js']) {
  vm.runInContext(fs.readFileSync(dir + '/comun/' + archivo, 'utf8'), ctx, { filename: archivo });
}
const JSC = ctx.JSC;
const salida = {};

salida.score = entrada.puntajes.map((v) => JSC.clasificarScore(v));
salida.invalidos = entrada.invalidos.map((v) => JSC.clasificarScore(v));
salida.documentos = entrada.documentos.map((d) => JSC.detectarTipoDocumento(d));
salida.coordenadas = entrada.coordenadas.map((t) => {
  try { return { ok: JSC.parseCoordenadas(t) }; } catch (e) { return { error: e.message }; }
});
salida.rangos = entrada.rangos.map((r) => JSC.rangoSinPrefijo(r));
salida.casos = JSC.CASOS.map((c) => c.id);
salida.tiempoCarga = JSC.TIEMPO_CARGA_MS;

const resumen = (vista) => ({
  fase: vista.fase,
  etiquetas: vista.ficha.map((par) => par[0]),
  scoreFicha: Object.fromEntries(vista.ficha)['SCORE'],
  veredicto: vista.veredicto.texto,
  estadoTexto: vista.estadoTexto,
  aviso: vista.aviso,
  pendiente: vista.pendiente ? vista.pendiente.mensaje : null,
  cargando: vista.cargando,
  verDetalle: Boolean(vista.detalle),
});
salida.vistas = {};
for (const caso of JSC.CASOS) {
  salida.vistas[caso.id] = resumen(JSC.vista({ casoId: caso.id, fase: caso.fase, confirmado: false }));
}
salida.vistaConfirmada = resumen(JSC.vista({ casoId: 'extensible', fase: 'resultado', confirmado: true }));
salida.fichaVende = JSC.vista({ casoId: 'vende', fase: 'resultado', confirmado: false }).ficha;
salida.copiarTodo = JSC.textoCopiarTodo(salida.fichaVende);

function crear() {
  const log = [];
  const cola = [];
  const sesion = JSC.crearSesion({
    render: (vista, estado, previo) =>
      log.push([estado.fase, estado.casoId, vista.score.titulo, vista.pendiente !== null, previo ? previo.fase : null]),
    transicion: (actualizar) => actualizar(),
    esperar: (fn, ms) => { cola.push({ fn, ms, cancelado: false }); return cola.length - 1; },
    limpiar: (id) => { if (cola[id]) cola[id].cancelado = true; },
  });
  const correr = () => cola.filter((t) => !t.cancelado).forEach((t) => t.fn());
  return { sesion, log, cola, correr };
}

const e = {};
{ const s = crear(); s.sesion.elegirCaso('vende'); e.elegir = s.log; }
{
  const s = crear(); s.sesion.elegirCaso('vende'); s.log.length = 0;
  s.sesion.validar();
  e.validarAntes = s.log.slice(); e.validarEspera = s.cola.map((t) => t.ms);
  s.correr();
  e.validarDespues = s.log.slice();
}
{
  const s = crear(); s.sesion.elegirCaso('vende'); s.log.length = 0;
  s.sesion.validar(); s.sesion.validar();
  e.dobleCancelados = s.cola.map((t) => t.cancelado);
  s.correr();
  e.dobleLog = s.log.slice();
}
{
  const s = crear(); s.sesion.elegirCaso('extensible');
  e.extensibleAntes = s.log.slice(); s.log.length = 0;
  s.sesion.confirmarScore();
  e.extensibleDespues = s.log.slice();
  s.sesion.elegirCaso('vende'); s.log.length = 0;
  s.sesion.elegirCaso('extensible');
  e.extensibleReinicia = s.log.slice();
}
{ const s = crear(); s.sesion.elegirCaso('cargando'); s.log.length = 0; s.sesion.validar(); e.cargandoLog = s.log.slice(); e.cargandoCola = s.cola.length; }
{ const s = crear(); s.sesion.validar(); s.correr(); e.inicialLog = s.log.slice(); }
{ const s = crear(); s.sesion.elegirCaso('vende'); s.log.length = 0; s.sesion.confirmarScore(); e.sinPendiente = s.log.slice(); }
{ const s = crear(); s.sesion.elegirCaso('no-existe'); e.desconocido = s.log.slice(); e.estadoDesconocido = s.sesion.estado.casoId; }
{ const s = crear(); s.sesion.inicializar(); e.inicializar = s.log.slice(); }
salida.sesion = e;

console.log(JSON.stringify(salida));
"""


@pytest.fixture(scope="module")
def js(tmp_path_factory) -> dict:
    carpeta = tmp_path_factory.mktemp("nucleo_js")
    entrada = carpeta / "entrada.json"
    entrada.write_text(
        json.dumps(
            {
                "puntajes": PUNTAJES,
                "invalidos": INVALIDOS,
                "documentos": DOCUMENTOS,
                "coordenadas": COORDENADAS,
                "rangos": ["SCORE: 500 - 599", "SCORE:   1 - 2", "otro", "", None],
            }
        ),
        encoding="utf-8",
    )
    script = carpeta / "arnes.js"
    script.write_text(HARNESS, encoding="utf-8")
    resultado = subprocess.run(
        [NODE, str(script), str(RAIZ), str(entrada)],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


@pytest.mark.parametrize(
    "archivo",
    ["datos.js", "nucleo.js", *(f"../{v}/{v}.js" for v in ("bento", "panel", "pasos", "compacta", "protagonista"))],
)
def test_la_sintaxis_del_js_es_valida(archivo):
    ruta = RAIZ / "comun" / archivo
    resultado = subprocess.run([NODE, "--check", str(ruta)], capture_output=True, text=True, check=False)
    assert resultado.returncode == 0, resultado.stderr


def test_clasificar_score_coincide_con_la_app(js):
    assert js["score"] == [main_window.clasificar_score(v) for v in PUNTAJES]


def test_clasificar_score_rechaza_lo_mismo_que_la_app(js):
    assert js["invalidos"] == [main_window.clasificar_score(v) for v in INVALIDOS]
    assert all(r is None for r in js["invalidos"])


def test_detectar_tipo_de_documento_coincide_con_la_app(js):
    esperado = []
    for documento in DOCUMENTOS:
        try:
            esperado.append(fields.detectar_tipo_documento(documento))
        except ValueError:
            esperado.append(None)
    assert js["documentos"] == esperado


def test_parse_coordenadas_coincide_con_la_app(js):
    esperado = []
    for texto in COORDENADAS:
        try:
            esperado.append({"ok": list(fields.parse_coordenadas(texto))})
        except ValueError as exc:
            esperado.append({"error": str(exc)})
    assert js["coordenadas"] == esperado


def test_rango_sin_prefijo_coincide_con_la_app(js):
    entradas = ["SCORE: 500 - 599", "SCORE:   1 - 2", "otro", "", None]
    assert js["rangos"] == [ficha.rango_sin_prefijo(r) for r in entradas]


def test_los_casos_de_prueba_y_el_tiempo_de_carga(js):
    assert js["casos"] == CASOS
    assert 300 <= js["tiempoCarga"] <= 2000


def test_cada_vista_trae_la_ficha_completa_en_el_orden_de_la_app(js):
    for caso in CASOS:
        assert js["vistas"][caso]["etiquetas"] == list(ficha.ETIQUETAS), caso


def test_el_score_de_la_ficha_sale_del_rango(js):
    vistas = js["vistas"]
    assert vistas["vende"]["scoreFicha"] == ficha.rango_sin_prefijo(main_window.clasificar_score(612)["rango"])
    assert vistas["no_vende"]["scoreFicha"] == ficha.rango_sin_prefijo(main_window.clasificar_score(380)["rango"])
    assert vistas["extensible"]["scoreFicha"] == ""
    assert js["vistaConfirmada"]["scoreFicha"] == ficha.rango_sin_prefijo(main_window.clasificar_score(534)["rango"])


def test_veredictos_y_estado_de_cada_caso(js):
    vistas = js["vistas"]
    assert {c: v["veredicto"] for c, v in vistas.items()} == {
        "inicial": "—",
        "vende": "VENDE",
        "no_vende": "NO VENDE",
        "extensible": "POSIBLE EXTENSIÓN",
        "bloqueado": "NO VENDE",
        "error_cobertura": "SIN CONFIRMAR",
        "cargando": "Validando…",
    }
    assert vistas["cargando"]["estadoTexto"] == "Estado: validando..."
    assert vistas["cargando"]["cargando"] is True
    assert vistas["vende"]["estadoTexto"] == "Estado: listo"
    assert vistas["error_cobertura"]["aviso"] == "WinForce no respondió · reintenta"
    assert vistas["vende"]["aviso"] == ""
    assert js["vistaConfirmada"]["veredicto"] == vistas["extensible"]["veredicto"]


def test_ver_detalle_solo_con_resultado(js):
    vistas = js["vistas"]
    assert [c for c, v in vistas.items() if v["verDetalle"]] == [
        "vende", "no_vende", "extensible", "bloqueado", "error_cobertura",
    ]


def test_el_score_de_una_zona_extensible_espera_la_confirmacion(js):
    vistas = js["vistas"]
    assert vistas["extensible"]["pendiente"].startswith("Sin cobertura en el punto, pero hay cobertura a 120 m")
    assert js["vistaConfirmada"]["pendiente"] is None
    assert all(v["pendiente"] is None for c, v in vistas.items() if c != "extensible")


def test_copiar_todo_coincide_con_la_app(js):
    pares = [tuple(par) for par in js["fichaVende"]]
    assert len(pares) == len(ficha.ETIQUETAS)
    assert js["copiarTodo"] == ficha.texto_copiar_todo(pares)


def test_sesion_elegir_un_caso_muestra_el_resultado_al_instante(js):
    assert js["sesion"]["elegir"] == [["resultado", "vende", "✔ VENDE", False, "inicial"]]


def test_sesion_validar_pasa_por_la_carga_y_luego_el_resultado(js):
    sesion = js["sesion"]
    assert sesion["validarAntes"] == [["cargando", "vende", "—", False, "resultado"]]
    assert sesion["validarEspera"] == [js["tiempoCarga"]]
    assert sesion["validarDespues"][-1] == ["resultado", "vende", "✔ VENDE", False, "cargando"]


def test_sesion_validar_dos_veces_cancela_la_espera_anterior(js):
    sesion = js["sesion"]
    assert sesion["dobleCancelados"] == [True, False]
    resultados = [fila for fila in sesion["dobleLog"] if fila[0] == "resultado"]
    assert len(resultados) == 1


def test_sesion_confirmar_el_score_de_la_zona_extensible(js):
    sesion = js["sesion"]
    assert sesion["extensibleAntes"] == [["resultado", "extensible", "Necesita 201+", True, "inicial"]]
    assert sesion["extensibleDespues"] == [["resultado", "extensible", "✔ VENDE", False, "resultado"]]


def test_sesion_cambiar_de_caso_reinicia_la_confirmacion(js):
    assert js["sesion"]["extensibleReinicia"][-1][2:4] == ["Necesita 201+", True]


def test_sesion_validar_un_caso_cargando_no_termina_nunca(js):
    sesion = js["sesion"]
    assert [fila[0] for fila in sesion["cargandoLog"]] == ["cargando"]
    assert sesion["cargandoCola"] == 0


def test_sesion_validar_desde_el_inicio_muestra_el_caso_vende(js):
    assert js["sesion"]["inicialLog"][-1][:3] == ["resultado", "vende", "✔ VENDE"]


def test_sesion_ignora_lo_que_no_aplica(js):
    sesion = js["sesion"]
    assert sesion["sinPendiente"] == []
    assert sesion["desconocido"] == []
    assert sesion["estadoDesconocido"] == "inicial"


def test_sesion_inicializar_pinta_sin_estado_previo(js):
    assert js["sesion"]["inicializar"] == [["inicial", "inicial", "—", False, None]]
