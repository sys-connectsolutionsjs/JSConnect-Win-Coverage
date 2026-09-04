"""Mide la vida real de la sesion (PHPSESSID) sin actividad, para calibrar el
intervalo del keepalive del proxy (Fase 2 del plan "Sesion WinForce robusta").

Metodo: parte de una cookie PHPSESSID valida (login manual + 2FA en el
navegador, igual que tools/probar_con_cookie.py) y hace pings a operador.php
con esperas de inactividad crecientes entre cada uno. En cuanto un ping falla,
la sesion murio en algun punto entre el ultimo ping exitoso y el fallido: ese
es el rango real del idle-timeout. Con eso se calibra
keepalive_interval_seconds de la Fase 2 (debe quedar por debajo del limite
inferior de ese rango, con margen).

Uso (requiere PYTHONPATH=. si validator_app no esta instalado editable):
    python tools/medir_sesion.py [--espera-inicial S] [--incremento S] [--max S] [--log FILE]

    --espera-inicial  segundos de espera antes del primer ping (por defecto 30)
    --incremento      segundos que se suman a la espera en cada paso exitoso
                       (por defecto 15; usar un valor menor para mas precision)
    --max             tope de segundos de espera acumulada antes de abandonar
                       (por defecto 600 = 10 min)
    --log             archivo TSV de salida (por defecto medir_sesion.log)

No pide usuario/contrasena: se asume que ya iniciaste sesion manualmente en el
navegador (incluyendo el 2FA de Microsoft) y copiaste el valor de la cookie
PHPSESSID (F12 -> Application -> Cookies -> https://appwinforce.win.pe).
"""

import argparse
import getpass
import sys
import time
from datetime import datetime
from pathlib import Path

from validator_app.core import api


def _sesion_viva(cliente: api.ValidatorAPI) -> bool:
    """Reusa la misma validacion que login()/auto_relogin (sin volver a implementarla)."""
    try:
        api.ValidatorAPI._verificar_sesion_activa(cliente._sesion)
    except api.LoginError:
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mide cuanto dura viva la sesion de WinForce sin actividad."
    )
    parser.add_argument("--espera-inicial", type=float, default=30.0)
    parser.add_argument("--incremento", type=float, default=15.0)
    parser.add_argument("--max", type=float, default=3600.0)
    parser.add_argument("--log", default="medir_sesion.log")
    args = parser.parse_args()

    php_sessid = getpass.getpass("Pega el valor de la cookie PHPSESSID: ").strip()
    if not php_sessid:
        print("[ERROR] Cookie vacia. Cancelado.")
        return 1

    cliente = api.ValidatorAPI()
    cliente.set_session_cookies({"PHPSESSID": php_sessid})

    log = Path(args.log)
    print(f"Log: {log.resolve()}")
    print("=" * 66)

    if not _sesion_viva(cliente):
        print("[ERROR] La cookie no esta activa (revisa que sea reciente y valida).")
        return 1
    print("[OK] Cookie activa. Iniciando medicion...\n")

    espera = args.espera_inicial
    espera_total = 0.0
    ultima_viva = 0.0

    while espera_total + espera <= args.max:
        print(
            f"Esperando {espera:.0f}s sin actividad "
            f"(total acumulado: {espera_total + espera:.0f}s)..."
        )
        time.sleep(espera)
        espera_total += espera

        viva = _sesion_viva(cliente)
        marca = datetime.now().isoformat(timespec="seconds")
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{marca}\t{espera_total:.0f}\t{'VIVA' if viva else 'MUERTA'}\n")

        if not viva:
            print(
                f"\n[RESULTADO] La sesion murio entre {ultima_viva:.0f}s y "
                f"{espera_total:.0f}s de inactividad."
            )
            print(
                f"Recomendacion: keepalive_interval_seconds <= {ultima_viva:.0f}s "
                "(con margen de seguridad, ej. la mitad)."
            )
            return 0

        print(f"[OK] Sesion sigue viva a los {espera_total:.0f}s.")
        ultima_viva = espera_total
        espera += args.incremento

    print(
        f"\n[RESULTADO] La sesion sigue viva tras {espera_total:.0f}s de inactividad "
        "(se alcanzo el tope --max). No expira tan rapido como se pensaba; "
        "sube --max para seguir midiendo."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
