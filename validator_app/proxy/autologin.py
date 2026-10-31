"""Autologin desatendido de WinForce para el proxy (plan Proxy 24/7, 2026-10-28).

El login son tres pasos: el formulario propio de WinForce (`/login`, que responde
"Redireccionar" y recarga), la puerta de acceso ("Iniciar con Microsoft") y el SSO
de Microsoft Entra ID (solo correo y contrasena, sin segundo factor). La credencial
vive en el keyring del servicio (nunca en config.yaml ni en el repo).

`FrenoAutologin` evita pelear por la sesion: si otra persona sigue entrando con
la misma cuenta, cada relogin del proxy la bota y ella bota al proxy. Con dos
muertes rapidas seguidas el proxy se pausa y avisa al owner.
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from validator_app.core import api as core_api
from validator_app.proxy import login_asistido

# Frenado entre intentos FALLIDOS, en minutos: espera antes del 2.o, 3.o y 4.o intento
# y el intervalo fijo del 5.o en adelante (el 1.o siempre es inmediato). Reglas (pedido
# del owner, 2026-10-28): 2.o de 1 a 5; 3.o desde el 2.o hasta 10; 4.o desde el 3.o hasta
# 15; fijo de 1 a 20. Nada por debajo de 1 min: reloguear cada pocos segundos no gana la
# pelea por la cuenta (bota al otro y el otro bota al proxy) y puede hacer que Microsoft o
# WinForce marquen la cuenta.
PERFIL_RECOMENDADO = "recomendado"
PERFIL_PERSONALIZADO = "personalizado"
PERFILES_FRENO: dict[str, dict] = {
    "recomendado": {
        "nombre": "Rango de relogin recomendado",
        "minutos": (1, 2, 3, 5),
        "aviso": "",
    },
    "rapido": {
        "nombre": "Rango rapido",
        "minutos": (1, 1, 2, 3),
        "aviso": "Mas relogins: si otra persona usa la cuenta, se botan mas seguido.",
    },
    "demasiado_rapido": {
        "nombre": "Rango demasiado rapido (no recomendado)",
        "minutos": (1, 1, 1, 1),
        "aviso": (
            "Pelea por la sesion cada minuto con quien entre a la cuenta: no se gana, se "
            "botan uno al otro, y Microsoft o WinForce pueden marcar o bloquear la cuenta."
        ),
    },
    "lento_optimo": {
        "nombre": "Rango lento optimo",
        "minutos": (2, 4, 6, 10),
        "aviso": "",
    },
    "lento": {
        "nombre": "Rango lento",
        "minutos": (3, 6, 10, 15),
        "aviso": "Si falla, la sesion puede quedar caida hasta 15 min seguidos.",
    },
    "demasiado_lento": {
        "nombre": "Rango demasiado lento (no recomendado)",
        "minutos": (5, 10, 15, 20),
        "aviso": "Los agentes pueden quedar sin servicio hasta 20 min seguidos.",
    },
}
NOMBRE_PERSONALIZADO = "Rango personalizado"


def validar_freno(minutos) -> tuple[int, int, int, int]:
    """Comprueba las reglas del frenado y devuelve los 4 valores como enteros."""
    valores = tuple(minutos)
    if len(valores) != 4:
        raise ValueError("El frenado necesita 4 valores: 2.o, 3.o, 4.o intento y el fijo.")
    if any(isinstance(v, bool) or float(v) != int(v) for v in valores):
        raise ValueError("El frenado va en minutos enteros (minimo 1 minuto).")
    segundo, tercero, cuarto, fijo = (int(v) for v in valores)
    if not 1 <= segundo <= 5:
        raise ValueError("La espera antes del 2.o intento va de 1 a 5 min.")
    if not segundo <= tercero <= 10:
        raise ValueError(f"La espera antes del 3.o intento va de {segundo} a 10 min.")
    if not tercero <= cuarto <= 15:
        raise ValueError(f"La espera antes del 4.o intento va de {tercero} a 15 min.")
    if not 1 <= fijo <= 20:
        raise ValueError("El intervalo fijo (del 5.o intento en adelante) va de 1 a 20 min.")
    return segundo, tercero, cuarto, fijo


def resolver_freno(perfil: str, minutos=None) -> tuple[str, tuple[int, int, int, int]]:
    """(perfil, minutos validos). Un perfil con nombre usa SUS minutos; el
    personalizado valida los recibidos."""
    if perfil in PERFILES_FRENO:
        return perfil, PERFILES_FRENO[perfil]["minutos"]
    if perfil == PERFIL_PERSONALIZADO:
        return perfil, validar_freno(minutos or ())
    raise ValueError(f"Perfil de frenado desconocido: {perfil}")


def esperas_de(minutos) -> tuple[int, ...]:
    """Minutos del frenado -> esperas en segundos, con el 1.er intento en 0."""
    return (0, *(m * 60 for m in validar_freno(minutos)))


def tope_por_hora(esperas) -> int:
    """Intentos que el frenado cabe en 60 min, mas 2: red de seguridad que con un
    frenado valido no deberia activarse."""
    t, intentos, i = 0.0, 0, 0
    while t < 3600:
        intentos += 1
        i += 1
        t += esperas[min(i, len(esperas) - 1)]
    return intentos + 2


ESPERAS_POR_DEFECTO = esperas_de(PERFILES_FRENO[PERFIL_RECOMENDADO]["minutos"])

# Perfil del navegador SOLO del servicio (SYSTEM), separado del `.browser_profile/` del
# login asistido del owner: dos procesos no pueden abrir el mismo perfil a la vez.
PERFIL_SERVICIO = Path(__file__).resolve().parent / ".browser_profile_servicio"
CAPTURA_FALLO = Path(__file__).resolve().parents[2] / "logs" / "autologin_fallo.png"
MAX_CAPTURAS = 20

_SEL_WF_USUARIO = "#username"
_SEL_WF_PASSWORD = "#password"
_SEL_WF_INGRESAR = "#ingresar"
_SEL_WF_RECHAZOS = (".swal2-popup.swal2-icon-error", ".swal2-popup.swal2-icon-warning")
_SEL_PUERTA_MICROSOFT = "button.login-button.azure"
_SEL_USUARIO = "input[name=loginfmt]"
# La pantalla del correo trae un campo de contrasena oculto (.moveOffScreen) que Playwright
# da por visible: sin excluirlo, la contrasena se escribe ahi y Siguiente sale sin correo.
_SEL_PASSWORD = "input[name=passwd]:not(.moveOffScreen)"
_SEL_SIGUIENTE = "#idSIButton9"
_SEL_KMSI = "#KmsiCheckboxField"
_SEL_ERROR_USUARIO = "#usernameError"
_SEL_ERRORES = (_SEL_ERROR_USUARIO, "#passwordError")
_POLL_S = 1.0
# Si Microsoft recarga su pagina (`sso_reload`) el correo escrito puede perderse.
# Reescribirlo no es un intento de contrasena.
_MAX_ENVIOS_USUARIO = 3
_GRACIA_ERROR_USUARIO_S = 3.0


class AutologinError(Exception):
    """El autologin no se completo (timeout, red, pantalla desconocida)."""


class CredencialInvalidaError(AutologinError):
    """WinForce o Microsoft rechazaron el usuario o la contrasena. No se reintenta:
    insistir con una contrasena mala puede bloquear la cuenta."""


class NavegadorRechazadoError(AutologinError):
    """WinForce rechazo el navegador antes del formulario. No se reintenta: insistir
    contra su filtro no lo abre y puede hacer que bloquee la IP o la cuenta."""


def _import_sync_playwright():
    login_asistido.usar_navegadores_compartidos()
    from playwright.sync_api import sync_playwright

    return sync_playwright


def _visible(page, selector: str) -> bool:
    try:
        return bool(page.is_visible(selector))
    except Exception:
        return False


def _php_valida(context) -> str | None:
    try:
        php = login_asistido._php_sessid_de_cookies(context.cookies())
    except Exception:
        return None
    if not php:
        return None
    try:
        core_api.validar_cookie_sesion(php)
    except Exception:
        return None
    return php


def _texto_de(page, selector: str) -> str:
    try:
        return " ".join(page.inner_text(selector).split())
    except Exception:
        return ""


def _usuario_vacio(page) -> bool:
    try:
        return bool(page.is_visible(_SEL_USUARIO)) and page.input_value(_SEL_USUARIO) == ""
    except Exception:
        return False


def _guardar_captura(page, captura: Path) -> Path | None:
    """Guarda lo que se ve ahora: `captura` es siempre el ultimo fallo y la carpeta
    `<captura>s/` conserva los ultimos. Nunca lanza: no debe tapar el error real."""
    captura = Path(captura)
    try:
        captura.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(captura))
    except Exception:
        return None
    historial = captura.parent / f"{captura.stem}s"
    try:
        historial.mkdir(exist_ok=True)
        copia = historial / time.strftime("%Y%m%d-%H%M%S.png")
        shutil.copyfile(captura, copia)
        for vieja in sorted(historial.glob("*.png"))[:-MAX_CAPTURAS]:
            vieja.unlink()
    except Exception:
        return captura
    return copia


def _url_segura(url: str) -> str:
    """Host y ruta, con solo los NOMBRES de los parametros: sus valores traen codigos."""
    partes = urlsplit(url)
    nombres = sorted(parse_qs(partes.query, keep_blank_values=True))
    return f"{partes.netloc}{partes.path} {nombres}" if nombres else partes.netloc + partes.path


class _Traza:
    """Rastro del ULTIMO intento: `traza.txt` (pasos, navegaciones y tiempos) y una imagen
    antes de cada accion. Sin correo ni contrasena en texto. Nunca lanza."""

    def __init__(self, page, carpeta: Path, reloj: Callable[[], float]):
        self._page = page
        self._carpeta = Path(carpeta)
        self._reloj = reloj
        self._inicio = reloj()
        self._n = 0
        with contextlib.suppress(Exception):
            self._carpeta.mkdir(parents=True, exist_ok=True)
            for viejo in self._carpeta.iterdir():
                viejo.unlink()
        self.nota("inicio")

    def nota(self, texto: str) -> None:
        with contextlib.suppress(Exception), open(
            self._carpeta / "traza.txt", "a", encoding="utf-8"
        ) as f:
            f.write(f"+{self._reloj() - self._inicio:6.1f}s {texto}\n")

    def paso(self, nombre: str) -> None:
        self._n += 1
        self.nota(f"paso {self._n}: {nombre}")
        with contextlib.suppress(Exception):
            self._page.screenshot(path=str(self._carpeta / f"{self._n:02d}-{nombre}.png"))


def _completar_login(context, page, usuario, password, timeout_s, reloj, dormir, traza) -> str:
    limite = reloj() + timeout_s
    formulario_enviado = puerta_pulsada = False
    password_enviada = False
    envios_usuario = 0
    gracia_usuario = 0.0
    while reloj() < limite:
        php = _php_valida(context)
        if php:
            return php
        vacio = _usuario_vacio(page)
        for sel in _SEL_ERRORES:
            if sel == _SEL_ERROR_USUARIO and (vacio or reloj() < gracia_usuario):
                continue
            if _visible(page, sel):
                raise CredencialInvalidaError(
                    "Microsoft rechazo el usuario o la contrasena de WinForce guardados en "
                    f"el proxy: {_texto_de(page, sel)}"
                )
        for sel in _SEL_WF_RECHAZOS:
            if _visible(page, sel):
                raise CredencialInvalidaError(f"WinForce rechazo el acceso: {_texto_de(page, sel)}")
        if not formulario_enviado and _visible(page, _SEL_WF_USUARIO):
            traza.paso("formulario")
            page.fill(_SEL_WF_USUARIO, usuario)
            page.fill(_SEL_WF_PASSWORD, password)
            page.click(_SEL_WF_INGRESAR)
            formulario_enviado = True
        elif not puerta_pulsada and _visible(page, _SEL_PUERTA_MICROSOFT):
            traza.paso("puerta")
            page.click(_SEL_PUERTA_MICROSOFT)
            puerta_pulsada = True
        elif not password_enviada and _visible(page, _SEL_PASSWORD):
            traza.paso("password")
            page.fill(_SEL_PASSWORD, password)
            page.click(_SEL_SIGUIENTE)
            password_enviada = True
        elif (
            envios_usuario < _MAX_ENVIOS_USUARIO
            and (vacio or envios_usuario == 0)
            and _visible(page, _SEL_USUARIO)
        ):
            traza.paso("correo")
            page.fill(_SEL_USUARIO, usuario)
            page.click(_SEL_SIGUIENTE)
            envios_usuario += 1
            gracia_usuario = reloj() + _GRACIA_ERROR_USUARIO_S
        elif _visible(page, _SEL_KMSI):
            traza.paso("kmsi")
            page.click(_SEL_SIGUIENTE)
        dormir(_POLL_S)

    raise AutologinError(f"El login no termino en {timeout_s:.0f} s.")


def login_automatico(
    usuario: str,
    password: str,
    timeout_s: float = 90,
    headless: bool = False,
    playwright=None,
    perfil: Path = PERFIL_SERVICIO,
    captura: Path = CAPTURA_FALLO,
    reloj: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> str:
    """Inicia sesion en WinForce y devuelve una PHPSESSID ya validada.

    Usa Chromium normal, no headless: WinForce responde HTTP 410 a `HeadlessChrome`.
    Como servicio corre en la sesion 0, asi que la ventana no se ve en el escritorio.

    Envia el formulario de WinForce, elige Microsoft en la puerta de acceso y deja
    actuar al SSO silencioso (el perfil persistente recuerda la sesion de Microsoft);
    solo si Microsoft pide los datos los llena. La contrasena se envia una sola vez;
    el correo se reescribe si la pagina lo pierde.

    Cada fallo deja una captura de la pantalla y su ruta en el mensaje. Lanza
    CredencialInvalidaError, NavegadorRechazadoError o AutologinError."""
    if playwright is None:
        try:
            playwright = _import_sync_playwright()
        except ImportError as e:
            raise AutologinError(
                "Playwright no esta instalado en esta PC (ejecuta install_service.bat)."
            ) from e

    Path(perfil).mkdir(parents=True, exist_ok=True)
    with playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(perfil), headless=headless
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            traza = _Traza(page, Path(captura).parent / "autologin_pasos", reloj)

            def al_navegar(frame) -> None:
                if frame == page.main_frame:
                    traza.nota(f"navega a {_url_segura(frame.url)}")

            with contextlib.suppress(Exception):
                page.on("framenavigated", al_navegar)
            try:
                respuesta = None
                with contextlib.suppress(Exception):
                    respuesta = page.goto(login_asistido.LOGIN_URL)
                if respuesta is not None and respuesta.status >= 400:
                    raise NavegadorRechazadoError(
                        f"WinForce rechazo el navegador automatico (HTTP {respuesta.status})."
                    )
                return _completar_login(
                    context, page, usuario, password, timeout_s, reloj, dormir, traza
                )
            except Exception as e:
                traza.nota(f"fallo: {type(e).__name__}")
                ruta = _guardar_captura(page, captura)
                conocido = isinstance(e, AutologinError)
                detalle = str(e) if conocido else (str(e).splitlines() or [repr(e)])[0]
                if ruta:
                    detalle = f"{detalle} Captura: {ruta}"
                raise (type(e) if conocido else AutologinError)(detalle) from e
        finally:
            with contextlib.suppress(Exception):
                context.close()


def _main_probar(timeout_s: float) -> int:
    """Login de prueba CON ventana y perfil temporal (sin SSO recordado): ejercita
    el flujo completo del formulario de Microsoft. No guarda nada en el proxy.
    Ojo: es un login real con la cuenta, asi que invalida la sesion del proxy."""
    usuario = input("Usuario de WinForce (correo de Microsoft): ").strip()
    password = getpass.getpass("Contrasena (no se muestra): ")
    if not usuario or not password:
        print("[ERROR] Usuario o contrasena vacios. Cancelado.")
        return 1
    with tempfile.TemporaryDirectory(prefix="jswin-autologin-") as perfil:
        try:
            php = login_automatico(
                usuario, password, timeout_s=timeout_s, headless=False, perfil=Path(perfil)
            )
        except CredencialInvalidaError as e:
            print(f"[ERROR] Credencial invalida: {e}")
            return 1
        except AutologinError as e:
            print(f"[ERROR] {e}")
            return 1
    print(f"[OK] Login automatico completado (PHPSESSID de {len(php)} caracteres). "
          "No se guardo nada en el proxy.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Autologin desatendido de WinForce (lo usa el servicio del proxy)."
    )
    parser.add_argument(
        "--probar",
        action="store_true",
        help="Login de prueba con ventana visible, sin guardar nada.",
    )
    parser.add_argument("--timeout", type=float, default=180, help="Segundos (por defecto 180).")
    args = parser.parse_args(argv)
    if args.probar:
        return _main_probar(args.timeout)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())


def _iso(ts: float | None) -> str | None:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) if ts else None


class FrenoAutologin:
    """Decide si el proxy puede intentar un autologin ahora. Logica pura."""

    def __init__(
        self,
        max_por_hora: int | None = None,
        muerte_rapida_s: float = 600,
        esperas: tuple[float, ...] = ESPERAS_POR_DEFECTO,
        pausa_s: float | None = None,
        reloj: Callable[[], float] = time.time,
    ):
        self.muerte_rapida_s = muerte_rapida_s
        self._reloj = reloj
        self.configurar(esperas, pausa_s, max_por_hora)
        self._intentos: list[float] = []
        self._fallos = 0
        self._proximo_permitido = 0.0
        self._pausado_hasta = 0.0
        self._detenido_por = ""
        self._ultimo_exito: float | None = None
        self._muertes_rapidas = 0
        self._ultimo_intento: float | None = None
        self._ultimo_resultado: str | None = None

    def configurar(
        self, esperas, pausa_s: float | None = None, max_por_hora: int | None = None
    ) -> None:
        """Cambia el frenado en vivo. La pausa por muertes rapidas es el intervalo
        fijo y el tope por hora sale del propio frenado, salvo que se indiquen."""
        self.esperas = tuple(esperas)
        self.pausa_s = self.esperas[-1] if pausa_s is None else pausa_s
        self.max_por_hora = tope_por_hora(self.esperas) if max_por_hora is None else max_por_hora

    def puede_intentar(self) -> tuple[bool, str]:
        ahora = self._reloj()
        if self._detenido_por:
            return False, self._detenido_por
        if ahora < self._pausado_hasta:
            return False, "pausado"
        if sum(1 for t in self._intentos if ahora - t < 3600) >= self.max_por_hora:
            return False, "tope_por_hora"
        if ahora < self._proximo_permitido:
            return False, "esperando"
        return True, ""

    def espera_restante(self) -> float:
        return max(0.0, self._proximo_permitido - self._reloj())

    def registrar_intento(self) -> None:
        ahora = self._reloj()
        self._intentos = [t for t in self._intentos if ahora - t < 3600]
        self._intentos.append(ahora)
        self._ultimo_intento = ahora

    def registrar_exito(self) -> None:
        self._fallos = 0
        self._proximo_permitido = 0.0
        self._ultimo_exito = self._reloj()
        self._ultimo_resultado = "ok"

    def registrar_fallo(self) -> None:
        self._fallos += 1
        espera = self.esperas[min(self._fallos, len(self.esperas) - 1)]
        self._proximo_permitido = self._reloj() + espera
        self._ultimo_resultado = "fallo"

    def _detener(self, motivo: str) -> None:
        self._detenido_por = motivo
        self._ultimo_resultado = motivo

    def registrar_credencial_invalida(self) -> None:
        self._detener("credencial_invalida")

    def registrar_navegador_rechazado(self) -> None:
        self._detener("navegador_rechazado")

    def reactivar(self) -> None:
        """Credencial nueva guardada: borron y cuenta nueva."""
        self._detenido_por = ""
        self._fallos = 0
        self._proximo_permitido = 0.0
        self._pausado_hasta = 0.0
        self._muertes_rapidas = 0

    def registrar_muerte(self) -> bool:
        """Anota una muerte de sesion. True si con ella se activo la pausa (dos
        muertes seguidas a menos de `muerte_rapida_s` de un autologin exitoso)."""
        ahora = self._reloj()
        if self._ultimo_exito is None or ahora - self._ultimo_exito >= self.muerte_rapida_s:
            self._muertes_rapidas = 0
            return False
        self._muertes_rapidas += 1
        if self._muertes_rapidas < 2:
            return False
        self._muertes_rapidas = 0
        self._pausado_hasta = ahora + self.pausa_s
        self._ultimo_resultado = "pausado"
        return True

    def estado(self) -> dict:
        _, motivo = self.puede_intentar()
        pausado = self._pausado_hasta if self._pausado_hasta > self._reloj() else None
        return {
            "habilitado": not self._detenido_por,
            "ultimo_intento": _iso(self._ultimo_intento),
            "ultimo_resultado": self._ultimo_resultado,
            "pausado_hasta": _iso(pausado),
            "motivo": motivo,
        }
