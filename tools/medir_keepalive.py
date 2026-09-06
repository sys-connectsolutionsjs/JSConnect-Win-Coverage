"""Smoke-test v3: mide cuanto sobrevive una sesion de WinForce con pings de
interaccion real, midiendo EDAD DE SESION (no tiempo de test) y distinguiendo
una sesion muerta de un fallo transitorio.

Que cambio respecto de v2 (y por que los datos de v2 no servian)
----------------------------------------------------------------
v2 concluyo que podia haber deteccion anti-bot porque murio a los 1100s de
test, ANTES que la prueba pasiva de Fase 0 (1155-1350s) pese a hacer mas
actividad. Esa conclusion no se sostiene, por dos defectos de metodo que este
script corrige:

1. **No se medía la edad real de la sesion.** El cronometro arrancaba con el
   script, no con el login. Como `acceso.php` NO regenera la PHPSESSID (ver
   anotaciones.md, "Reuse de PHPSESSID") y el panel de DevTools puede mostrar
   una cookie cacheada, la sesion de v2 pudo llevar ya 10+ min viva: "murio a
   1100s de test" podia ser ~1700s de sesion, algo perfectamente normal.
   -> Ahora `--login-hora` / `--edad-inicial` son OBLIGATORIOS y el log
      registra `edad_sesion_s`.

2. **Cualquier error se tomaba como "sesion muerta" y cortaba la prueba.** v1
   murio con un HTTP 404 estilo Apache (iso-8859-1) y v2 con un HTTP 200 +
   HTML de login: son fallos DISTINTOS, y mezclarlos produjo el modelo
   contradictorio de "idle-timeout + tope absoluto".
   -> Ahora cada fallo se clasifica (SESION_MUERTA / TRANSITORIO / OTRO) y,
      antes de dar por muerta la sesion, se CONFIRMA de forma independiente
      con `core.api.validar_cookie_sesion()`. Un transitorio no corta la
      prueba: se reintenta con backoff.

Intervalo: usar el de produccion, no uno de laboratorio
-------------------------------------------------------
Por defecto 900s (15 min). El idle-timeout observado es ~1155-1350s, asi que
pinguear cada 90-420s (como v1/v2) es absurdamente conservador: son 160-320
consultas fantasma al dia contra la cuenta de Win. 900s deja ~4-7 min de
margen y son 32 pings en una jornada de 8h. Se corre con el intervalo que se
piensa usar en produccion para que la prueba VALIDE el diseño de la Fase 2 en
vez de medir un patron que nunca vamos a usar.

No pide usuario/contrasena: se asume que ya iniciaste sesion manualmente en el
navegador (incluyendo el 2FA de Microsoft) y copiaste el valor de la cookie
PHPSESSID (F12 -> Application -> Cookies -> https://appwinforce.win.pe).

PROTOCOLO (importante, el metodo vale tanto como el codigo):
  1. Pestana NUEVA + DevTools reabierto antes de copiar la cookie (si reusas
     un panel viejo puede mostrar un valor cacheado; ya costo dos corridas).
  2. Anota la HORA EXACTA del login.
  3. python tools/medir_keepalive.py --coords-archivo tools/coords_prueba.txt \
         --login-hora HH:MM
  4. Dejar correr sin limite hasta muerte confirmada.
  5. NO encadenar corridas: una por sesion de trabajo.

Uso (desde la raiz del repo):
    python tools/medir_keepalive.py [opciones]

    --login-hora HH:MM  hora del login manual (calcula la edad inicial sola)
    --edad-inicial S    alternativa: segundos ya transcurridos desde el login
    --intervalo S       segundos entre pings (por defecto 900 = 15 min)
    --intervalo-min S   si prefieres intervalo variable: minimo
    --intervalo-max S   si prefieres intervalo variable: maximo
    --duracion S        segundos totales; 0 = sin limite (por defecto 0)
    --coords-archivo F  archivo con una coordenada "lat, lon" por linea
    --coords-lista "lat1,lon1;lat2,lon2;..."  lista inline
    --coords "lat,lon"  una sola coordenada fija
    --log FILE          TSV de salida (por defecto medir_keepalive.log)
    --reintentos N      fallos transitorios seguidos tolerados (por defecto 3)
"""

import argparse
import getpass
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Permite `python tools/medir_keepalive.py` desde la raiz del repo sin tener
# `validator_app` instalado editable ni exportar PYTHONPATH (mismo patron que
# tests/test_captura_guard.py). Al correr un script, Python pone tools/ en
# sys.path, no la raiz.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validator_app.core import api
from validator_app.gui import fields

VERSION = "v3"

# Estados de un ping
VIVA = "VIVA"
SESION_MUERTA = "SESION_MUERTA"
TRANSITORIO = "TRANSITORIO"
OTRO = "OTRO"

# HTTP que NO son sesion muerta: fallos de servidor/red pasajeros. El 404 esta
# aqui a proposito: v1 murio con un 404 estilo Apache y se conto como muerte de
# sesion sin ninguna prueba de que lo fuera.
_HTTP_TRANSITORIOS = {404, 429, 500, 502, 503, 504}

_RE_STATUS = re.compile(r"HTTP (\d{3})")


def _extraer_status(mensaje: str) -> int | None:
    """Saca el codigo HTTP del diagnostico que core.api embebe en el error."""
    m = _RE_STATUS.search(mensaje)
    return int(m.group(1)) if m else None


def _clasificar(exc: Exception) -> str:
    """Clasifica un fallo de ping SIN tocar la red.

    Es solo una hipotesis rapida: la decision real la toma _confirmar_muerte(),
    que pregunta al servidor. Sirve para no gastar una peticion extra cuando el
    fallo ya es obviamente transitorio.
    """
    code = getattr(exc, "code", "") or ""
    mensaje = str(exc)

    if code == "ERR_LOGIN_SESSION":
        return SESION_MUERTA

    # El status HTTP manda sobre el code: `_json()` de core/api.py envuelve como
    # ERR_NETWORK tanto un 200+HTML de login (sesion muerta) como un 503 (red),
    # asi que mirar solo el code los confundiria.
    status = _extraer_status(mensaje)
    if status == 200 and "text/html" in mensaje.lower():
        # 200 + HTML donde esperabamos JSON = redirect al login.
        return SESION_MUERTA
    if status in _HTTP_TRANSITORIOS:
        return TRANSITORIO

    if code.startswith("ERR_NETWORK"):
        return TRANSITORIO
    return OTRO


def _confirmar_muerte(php_sessid: str) -> tuple[bool, str]:
    """Verifica contra WinForce si la sesion murio de verdad.

    Reusa el helper compartido `core.api.validar_cookie_sesion()` (el mismo que
    usan el proxy y rotate_creds.py), asi que un cambio en la logica de "sesion
    activa" se propaga solo. Separa limpiamente "murio la sesion" de "fallo
    coordenada.php", que es justo la distincion que faltaba en v1/v2.
    """
    try:
        api.validar_cookie_sesion(php_sessid)
    except api.LoginError as e:
        return True, f"confirmada muerta: {e}"
    except Exception as e:
        # Ni viva ni muerta: no se pudo comprobar. No se cuenta como muerte.
        return False, f"no se pudo confirmar ({type(e).__name__}: {e})"
    return False, "sesion sigue viva (el fallo era del endpoint, no de la sesion)"


def _ping(php_sessid: str, lat: float, lon: float) -> tuple[bool, str, str]:
    """Un ping de actividad real. Devuelve (ok, categoria, detalle).

    Usa una instancia NUEVA de ValidatorAPI en cada ping: la clase tiene un
    guard interno `_session_max_idle = 120s` que, con la misma instancia
    reutilizada, lanzaria un falso "Sesion expirada" del lado del CLIENTE antes
    de tocar el servidor (ver auto_relogin_if_needed en core/api.py). Con una
    instancia nueva `_last_activity=0` y se mide el estado REAL del servidor.
    """
    cliente = api.ValidatorAPI()
    cliente.set_session_cookies({"PHPSESSID": php_sessid})
    try:
        cobertura = cliente.validar_cobertura(lat, lon)
    except Exception as e:
        code = getattr(e, "code", type(e).__name__)
        return False, _clasificar(e), f"{code}: {e}"
    return True, VIVA, f"cobertura={cobertura.get('cobertura')}"


def _parse_coords_lista(texto: str) -> list[tuple[float, float]]:
    coords = []
    for parte in texto.split(";"):
        parte = parte.strip()
        if not parte:
            continue
        coords.append(fields.parse_coordenadas(parte))
    if not coords:
        raise ValueError("--coords-lista no tenia ninguna coordenada valida")
    return coords


def _parse_coords_archivo(ruta: str) -> list[tuple[float, float]]:
    coords = []
    for numero, linea in enumerate(Path(ruta).read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        try:
            coords.append(fields.parse_coordenadas(linea))
        except Exception as e:
            raise ValueError(f"linea {numero} invalida ({linea!r}): {e}") from None
    if not coords:
        raise ValueError(f"{ruta} no tenia ninguna coordenada valida")
    return coords


def _edad_desde_hora(hhmm: str) -> float:
    """Segundos transcurridos desde una hora HH:MM de hoy."""
    try:
        hora = datetime.strptime(hhmm.strip(), "%H:%M").time()
    except ValueError:
        raise ValueError(f"hora invalida {hhmm!r}, se espera HH:MM (24h)") from None
    ahora = datetime.now()
    momento = ahora.replace(hour=hora.hour, minute=hora.minute, second=0, microsecond=0)
    edad = (ahora - momento).total_seconds()
    if edad < 0:
        raise ValueError(
            f"la hora de login {hhmm} esta en el futuro (ahora son las "
            f"{ahora.strftime('%H:%M')}). Revisa el dato."
        )
    return edad


def _resolver_edad_inicial(args) -> float:
    """La edad inicial es obligatoria: sin ella la corrida no es interpretable."""
    if args.edad_inicial is not None:
        return float(args.edad_inicial)
    if args.login_hora:
        return _edad_desde_hora(args.login_hora)
    print(
        "La EDAD DE LA SESION al empezar es obligatoria: sin ella no se puede\n"
        "distinguir 'murio joven' de 'ya venia vieja', que es exactamente el\n"
        "error que invalido la corrida v2."
    )
    return _edad_desde_hora(input("Hora del login manual (HH:MM, 24h): "))


def _resolver_coords(args) -> list[tuple[float, float]]:
    if args.coords_archivo:
        return _parse_coords_archivo(args.coords_archivo)
    if args.coords_lista:
        return _parse_coords_lista(args.coords_lista)
    texto = args.coords or input("Coordenadas (lat, lon): ").strip()
    return [fields.parse_coordenadas(texto)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mide la vida de una sesion WinForce con pings reales, "
        "midiendo edad de sesion y distinguiendo muerte real de fallo transitorio."
    )
    parser.add_argument("--login-hora", default=None, help="hora del login manual, HH:MM")
    parser.add_argument("--edad-inicial", type=float, default=None, help="segundos desde el login")
    parser.add_argument("--intervalo", type=float, default=None, help="intervalo fijo (def. 900)")
    parser.add_argument("--intervalo-min", type=float, default=900.0)
    parser.add_argument("--intervalo-max", type=float, default=900.0)
    parser.add_argument("--duracion", type=float, default=0.0, help="0 = sin limite")
    parser.add_argument("--coords", default=None)
    parser.add_argument("--coords-lista", default=None)
    parser.add_argument("--coords-archivo", default=None)
    parser.add_argument("--log", default="medir_keepalive.log")
    parser.add_argument("--reintentos", type=int, default=3, help="transitorios seguidos tolerados")
    args = parser.parse_args()

    intervalo_min = args.intervalo_min
    intervalo_max = args.intervalo_max
    if args.intervalo is not None:
        intervalo_min = intervalo_max = args.intervalo
    if intervalo_min > intervalo_max:
        print("[ERROR] --intervalo-min no puede ser mayor que --intervalo-max.")
        return 1

    try:
        edad_inicial = _resolver_edad_inicial(args)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1

    php_sessid = getpass.getpass("Pega el valor de la cookie PHPSESSID: ").strip()
    if not php_sessid:
        print("[ERROR] Cookie vacia. Cancelado.")
        return 1

    try:
        coords_lista = _resolver_coords(args)
    except Exception as e:
        print(f"[ERROR] Coordenadas invalidas: {e}")
        return 1

    log = Path(args.log)
    print(f"Log: {log.resolve()}")
    print(
        f"Sesion ya tiene {edad_inicial:.0f}s ({edad_inicial / 60:.1f} min) al empezar.\n"
        f"Ping cada {intervalo_min:.0f}-{intervalo_max:.0f}s con "
        f"{len(coords_lista)} coordenada(s), "
        + (
            f"durante {args.duracion:.0f}s."
            if args.duracion > 0
            else "sin limite (Ctrl+C para cortar)."
        )
    )
    print("=" * 66)

    # Cabecera de corrida: sin esto las corridas se apilan en el mismo fichero
    # sin separador y no se pueden distinguir despues.
    with log.open("a", encoding="utf-8") as fh:
        fh.write(
            f"# {datetime.now().isoformat(timespec='seconds')}\t{VERSION}\t"
            f"edad_inicial={edad_inicial:.0f}\tintervalo={intervalo_min:.0f}-{intervalo_max:.0f}\t"
            f"coords={len(coords_lista)}\treintentos={args.reintentos}\n"
            "# marca\tedad_sesion_s\ttranscurrido_s\tespera_s\testado\tcategoria\tcoords\tdetalle\n"
        )

    def registrar(edad, transcurrido, espera, estado, categoria, lat, lon, detalle):
        with log.open("a", encoding="utf-8") as fh:
            fh.write(
                f"{datetime.now().isoformat(timespec='seconds')}\t{edad:.0f}\t"
                f"{transcurrido:.0f}\t{espera:.0f}\t{estado}\t{categoria}\t"
                f"{lat},{lon}\t{detalle}\n"
            )

    lat, lon = random.choice(coords_lista)
    ok, categoria, detalle = _ping(php_sessid, lat, lon)
    registrar(edad_inicial, 0, 0, VIVA if ok else "MUERTA", categoria, lat, lon, detalle)
    if not ok:
        print(f"[ERROR] La cookie no esta activa desde el primer ping ({categoria}): {detalle}")
        print("Revisa el protocolo: pestana nueva + DevTools reabierto antes de copiar.")
        return 1
    print(f"[OK] Ping inicial. edad={edad_inicial:.0f}s coords=({lat},{lon}) {detalle}")

    transcurrido = 0.0
    transitorios_seguidos = 0

    while args.duracion <= 0 or transcurrido < args.duracion:
        espera = random.uniform(intervalo_min, intervalo_max)
        time.sleep(espera)
        transcurrido += espera
        edad = edad_inicial + transcurrido

        lat, lon = random.choice(coords_lista)
        ok, categoria, detalle = _ping(php_sessid, lat, lon)

        if ok:
            transitorios_seguidos = 0
            registrar(edad, transcurrido, espera, VIVA, categoria, lat, lon, detalle)
            print(
                f"[OK] Viva a los {edad:.0f}s de sesion ({edad / 60:.1f} min) "
                f"[test {transcurrido:.0f}s, espera {espera:.0f}s]. "
                f"coords=({lat},{lon}) {detalle}"
            )
            continue

        # Fallo: confirmar contra el servidor antes de dar la sesion por muerta.
        murio, veredicto = _confirmar_muerte(php_sessid)
        registrar(
            edad, transcurrido, espera,
            "MUERTA" if murio else "FALLO",
            categoria, lat, lon, f"{detalle} | {veredicto}",
        )

        if murio:
            print(
                f"\n[RESULTADO] Sesion MUERTA a los {edad:.0f}s de sesion "
                f"({edad / 60:.1f} min). Categoria del ping: {categoria}."
            )
            print(f"Confirmacion independiente: {veredicto}")
            print(
                f"Contexto: idle-timeout pasivo medido en Fase 0 = 1155-1350s; "
                f"intervalo usado aqui = {intervalo_min:.0f}-{intervalo_max:.0f}s."
            )
            return 0

        transitorios_seguidos += 1
        print(
            f"[WARN] Ping fallo a los {edad:.0f}s ({categoria}) pero la sesion "
            f"sigue viva -> {veredicto}. "
            f"Transitorio {transitorios_seguidos}/{args.reintentos}. Detalle: {detalle}"
        )
        if transitorios_seguidos >= args.reintentos:
            print(
                f"\n[ABORTADO] {args.reintentos} fallos transitorios seguidos sin "
                "muerte de sesion. Algo pasa con el endpoint o la red, no con la "
                "sesion; la corrida no es concluyente."
            )
            return 2

    edad_final = edad_inicial + transcurrido
    print(
        f"\n[RESULTADO] Sesion VIVA tras {edad_final:.0f}s de edad "
        f"({edad_final / 60:.1f} min), con pings cada "
        f"{intervalo_min:.0f}-{intervalo_max:.0f}s sobre {len(coords_lista)} coordenada(s)."
    )
    print(
        "Si esta edad supera holgadamente los 1155-1350s del idle-timeout pasivo, "
        "el keepalive funciona y el intervalo usado es viable para la Fase 2."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
