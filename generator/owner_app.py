"""Consola grafica para el owner: activaciones y estado local del proxy."""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from urllib.parse import urlsplit

import httpx
import ttkbootstrap as ttk  # drop-in del ttk de siempre + tema (bootstyle=)

from generator import generar
from validator_app import version
from validator_app.updater import check as update_check
from validator_app.updater import download


def normalizar_huella(valor: str) -> str:
    huella = valor.strip().upper()
    if not re.fullmatch(r"[0-9A-F]{4}(?:-[0-9A-F]{4}){3}", huella):
        raise ValueError("Huella invalida. Debe tener el formato XXXX-XXXX-XXXX-XXXX.")
    return huella


def estado_servicio(salida: str) -> str:
    salida = salida.upper()
    if "RUNNING" in salida:
        return "Servicio proxy: activo"
    if "STOPPED" in salida:
        return "Servicio proxy: detenido"
    return "Servicio proxy: no instalado o sin estado disponible"


# Windows 11 abre las consolas en Windows Terminal: sin este flag cada `sc` o
# `powershell` lanzado desde esta ventana muestra una Terminal que roba el foco.
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

CODIGO_UAC_CANCELADO = 2
ESPERA_ARRANQUE_SEGUNDOS = 5
SEGUNDOS_OCULTAR_SECRETO = 30
SEGUNDOS_LIMPIAR_PORTAPAPELES = 60


def comando_reinicio() -> list[str]:
    """PowerShell que pide elevacion (aviso UAC) y reinicia el servicio.

    Codigos de salida: 0 = reiniciado, 2 = no se concedio/no se pudo elevar
    (UAC cancelado), cualquier otro = el reinicio fallo dentro de la sesion elevada."""
    script = (
        "try { "
        "$p = Start-Process powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
        "-ErrorAction Stop "
        "-ArgumentList '-NoProfile','-Command','Restart-Service JSWinProxy -ErrorAction Stop'; "
        "exit $p.ExitCode "
        f"}} catch {{ exit {CODIGO_UAC_CANCELADO} }}"
    )
    return ["powershell", "-NoProfile", "-Command", script]


def reiniciar_servicio(runner=subprocess.run) -> tuple[bool, str]:
    """Reinicia JSWinProxy con permisos de administrador (pide confirmacion UAC).

    La sesion WinForce se conserva: la cookie vive en el keyring, no en memoria."""
    try:
        resultado = runner(
            comando_reinicio(), capture_output=True, text=True, timeout=120, check=False,
            creationflags=SIN_VENTANA,
        )
    except subprocess.TimeoutExpired:
        return False, "El reinicio tardo demasiado. Revisa el estado del servicio."
    except OSError as exc:
        return False, f"No se pudo lanzar PowerShell: {exc}"
    if resultado.returncode == 0:
        return True, "Servicio reiniciado."
    if resultado.returncode == CODIGO_UAC_CANCELADO:
        return False, "No se concedio el permiso de administrador (aviso UAC cancelado)."
    return False, f"No se pudo reiniciar el servicio (codigo {resultado.returncode})."


def consultar_servicio() -> str:
    try:
        resultado = subprocess.run(
            ["sc", "query", "JSWinProxy"], capture_output=True, text=True, timeout=5,
            check=False, creationflags=SIN_VENTANA,
        )
    except OSError:
        return "Servicio proxy: no se pudo consultar"
    return estado_servicio(resultado.stdout + resultado.stderr)


_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002
_HWND_MESSAGE = -3  # padre de las ventanas "message-only" (invisibles)
# Formatos que el historial del portapapeles (Win+V) y la sincronizacion en la
# nube de Windows 10 1809+/11 respetan: con ellos el secreto no queda guardado
# alli aunque la consola lo borre del portapapeles a los 60 s.
_FORMATOS_PRIVADOS = (
    "ExcludeClipboardContentFromMonitorProcessing",
    "CanIncludeInClipboardHistory",
    "CanUploadToCloudClipboard",
)


def copiar_sin_historial(texto: str) -> bool:
    """Copia `texto` al portapapeles marcado como privado (sin historial ni nube).

    El dueño del portapapeles es una ventana de mensajes propia y no la de Tk:
    con OpenClipboard(NULL), SetClipboardData falla, y si el dueño es una ventana
    de Tk, Tk vacía el portapapeles al cerrarla (copiar, cerrar la consola y
    pegar dejaba de funcionar). Devuelve False si algo falla, para que el caller
    use el portapapeles normal de Tk."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except (ImportError, OSError, AttributeError):
        return False

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalFree.argtypes = [wintypes.HANDLE]

    def _poner(formato: int, datos: bytes) -> bool:
        h = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(datos))
        if not h:
            return False
        p = kernel32.GlobalLock(h)
        if not p:
            kernel32.GlobalFree(h)
            return False
        ctypes.memmove(p, datos, len(datos))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(formato, h):
            kernel32.GlobalFree(h)  # solo si el sistema NO tomo la propiedad
            return False
        return True

    hwnd = user32.CreateWindowExW(
        0, "STATIC", None, 0, 0, 0, 0, 0, wintypes.HWND(_HWND_MESSAGE), None, None, None
    )
    if not hwnd:
        return False
    try:
        if not user32.OpenClipboard(hwnd):
            return False
        try:
            if not user32.EmptyClipboard():
                return False
            if not _poner(_CF_UNICODETEXT, (texto + "\0").encode("utf-16-le")):
                return False
            cero = (0).to_bytes(4, "little")
            for nombre in _FORMATOS_PRIVADOS:
                formato = user32.RegisterClipboardFormatW(nombre)
                if formato:
                    _poner(formato, cero)
            return True
        finally:
            user32.CloseClipboard()
    finally:
        user32.DestroyWindow(hwnd)


URL_PROXY_LOCAL_POR_DEFECTO = "http://127.0.0.1:8080"


def _url_proxy_local() -> str:
    """URL local del proxy: la de config.yaml si se puede leer, o la de por defecto.

    Solo hace falta el puerto para /health, que es publico. config.yaml puede no
    leerse por ACL (SYSTEM/Administradores: PermissionError) o, en el .exe
    empaquetado, no existir junto al modulo (ValidationError por tokens
    obligatorios); en ambos casos el estado real lo dice /health, no un
    "falta configurar" engañoso."""
    try:
        from validator_app.proxy.config import ProxyConfig

        return ProxyConfig().proxy_local_url
    except Exception:
        return URL_PROXY_LOCAL_POR_DEFECTO


def _leer_health() -> dict | None:
    """JSON de /health (publico, sin elevar) o None si el proxy no responde."""
    try:
        respuesta = httpx.get(f"{_url_proxy_local()}/health", timeout=5)
        respuesta.raise_for_status()
        return respuesta.json()
    except Exception:
        return None


def describir_proxy(datos: dict | None) -> str:
    if datos is None:
        return "Proxy: no responde localmente"
    if datos.get("session_alive"):
        return "Proxy: operativo; sesion WinForce viva"
    if datos.get("logged_in"):
        return "Proxy: operativo; sesion WinForce caducada"
    return "Proxy: operativo; sin sesion WinForce"


def consultar_proxy() -> str:
    return describir_proxy(_leer_health())


def describir_autologin(datos: dict | None) -> str:
    """Texto de estado del autologin a partir de /health (bloque `autologin`)."""
    if datos is None:
        return "Autologin: proxy no responde"
    estado = datos.get("autologin")
    if not datos.get("login_configurado") or not estado:
        return "Autologin: sin configurar (pulsa Configurar)"
    motivo = estado.get("motivo") or ""
    if motivo == "credencial_invalida":
        return "Autologin: contrasena rechazada; vuelve a guardarla"
    if motivo == "navegador_rechazado":
        return "Autologin: WinForce rechazo el navegador (no es la contrasena)"
    if not estado.get("habilitado"):
        return "Autologin: apagado (autologin_enabled en config.yaml)"
    if estado.get("en_curso"):
        return "Autologin: entrando a WinForce ahora..."
    if motivo == "pausado":
        hora = (estado.get("pausado_hasta") or "")[11:16]
        return f"Autologin: en pausa hasta las {hora} (otra persona usa la cuenta)"
    if motivo == "tope_por_hora":
        return "Autologin: tope de intentos por hora; reintenta solo mas tarde"
    if motivo == "esperando":
        return "Autologin: reintentando tras un fallo"
    resultado = estado.get("ultimo_resultado")
    return f"Autologin: activo; ultimo intento: {resultado}" if resultado else "Autologin: activo"


_ORDEN_PERFILES = (
    "recomendado", "rapido", "demasiado_rapido", "lento_optimo", "lento", "demasiado_lento",
)


def perfiles_para_combo() -> list[tuple[str, str]]:
    """(clave, nombre visible) de los perfiles de frenado, con Personalizado al final."""
    from validator_app.proxy import autologin

    return [(c, autologin.PERFILES_FRENO[c]["nombre"]) for c in _ORDEN_PERFILES] + [
        (autologin.PERFIL_PERSONALIZADO, autologin.NOMBRE_PERSONALIZADO)
    ]


def rangos_freno(segundo: int, tercero: int) -> tuple[tuple[int, int], ...]:
    """Rango permitido de cada paso del frenado: el 3.o arranca en el 2.o y el 4.o
    en el 3.o (reglas de autologin.validar_freno)."""
    return (1, 5), (segundo, 10), (tercero, 15), (1, 20)


def ajustar_minutos(minutos) -> list[int]:
    """Sube el 3.o/4.o si quedaron por debajo del paso anterior."""
    segundo, tercero, cuarto, fijo = (int(m) for m in minutos)
    tercero = max(tercero, segundo)
    cuarto = max(cuarto, tercero)
    return [segundo, tercero, cuarto, fijo]


def linea_de_tiempo_freno(minutos) -> str:
    segundo, tercero, cuarto, fijo = minutos
    return (
        f"Intentos: inmediato, +{segundo}, +{tercero}, +{cuarto} min, luego cada {fijo} min"
        f" · pausa por otra persona: {fijo} min"
    )


def describir_freno(datos: dict | None) -> str:
    if datos is None:
        return "Frenado: proxy no responde"
    freno = (datos.get("autologin") or {}).get("freno")
    if not freno:
        return "Frenado: (el proxy no lo informa)"
    minutos = freno["minutos"]
    pasos = "-".join(str(m) for m in minutos[:4])
    return f"Frenado: {freno['nombre']} ({pasos}, luego cada {minutos[4]} min)"


def guardar_freno_autologin(
    perfil: str, minutos, leer=None, enviar=None, url=None
) -> str:
    """Valida el frenado ANTES de pedir UAC y lo envia a POST /local/freno."""
    from validator_app.proxy import autologin

    perfil, minutos = autologin.resolver_freno(perfil, minutos)
    if leer is None:
        leer = leer_secretos_elevado
    if enviar is None:
        from validator_app.proxy.rotate_creds import push_freno_autologin as enviar
    admin_key = leer()["admin_key"]
    ok, mensaje = enviar(perfil, list(minutos), admin_key, url or _url_proxy_local())
    if not ok:
        raise RuntimeError(mensaje)
    return mensaje


def _ip_valida(ip: str) -> bool:
    """Descarta loopback (127.x) y direcciones APIPA (169.254.x, sin DHCP)."""
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (direccion.is_loopback or direccion.is_link_local)


def detectar_ip_lan(socket_factory=socket.socket, resolver=socket.getaddrinfo) -> str | None:
    """IP de LAN de esta PC (donde corre el proxy), para armar la URL de agentes.

    Metodo principal: socket UDP a una IP publica y leer con que interfaz saldria
    (no llega a enviar nada, "connect" en UDP solo fija la ruta). Si no hay ruta
    por defecto (sin red), respaldo con getaddrinfo(hostname). En ambos casos se
    descartan loopback y APIPA; solo importa la IP de LAN real."""
    try:
        with socket_factory(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        if _ip_valida(ip):
            return ip
    except OSError:
        pass

    try:
        candidatas = resolver(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return None
    for _familia, _tipo, _proto, _canonico, direccion in candidatas:
        ip = direccion[0]
        if _ip_valida(ip):
            return ip
    return None


def url_para_agentes(ip: str | None, puerto: int) -> str:
    if not ip:
        return ""
    return f"http://{ip}:{puerto}"


def puerto_proxy_local() -> int:
    puerto = urlsplit(_url_proxy_local()).port
    return puerto if puerto is not None else 8080


def ruta_extension_build(ruta_instalacion=None) -> tuple[Path | None, str, bool]:
    """Carpeta ".extension_build" real de esta instalacion, para "Cargar
    descomprimida" en chrome://extensions. Se resuelve con
    secretos.ruta_instalacion() (vive el directorio real via `sc qc`, no un
    directorio a mano) porque en el .exe onefile construir la ruta a partir de
    este propio modulo apuntaria al directorio temporal de extraccion de
    PyInstaller, no a la instalacion real (mismo problema que config.yaml,
    ver secretos.py).

    Devuelve (ruta, aviso, preparable). `ruta` solo viene si la carpeta EXISTE (con
    su manifest.json): antes se devolvia aunque no existiera. Sin ruta, `aviso`
    explica por que y `preparable` dice si la consola puede armarla (servicio
    instalado pero carpeta ausente -> boton "Preparar carpeta")."""
    from validator_app.proxy import secretos

    if ruta_instalacion is None:
        ruta_instalacion = secretos.ruta_instalacion
    try:
        base = ruta_instalacion()
    except secretos.SecretosError as exc:
        return None, (
            f"No se pudo ubicar la instalacion del proxy ({exc}). "
            "Instala el servicio primero con install_service.bat."
        ), False
    build = Path(base) / ".extension_build"
    if (build / "manifest.json").exists():
        return build, "", False
    return None, (
        f"La carpeta de la extension aun no esta preparada en {build}. Pulsa "
        "«Preparar carpeta» (pide permiso de administrador)."
    ), True


# ==================== SUBCOMANDOS ELEVADOS (sin GUI) ====================
# config.yaml tiene ACL de SYSTEM+Administradores (install_service.bat:273-276):
# leerlo o rotarlo exige correr elevado. En vez de debilitar la ACL (expondria
# los tokens a cualquier proceso no elevado del owner, perdiendo el filtro de
# UAC), la consola se relanza a si misma solo para estas dos operaciones.

_FLAG_LEER = "--leer-secretos"
_FLAG_ROTAR = "--rotar-secretos"
_FLAG_PREPARAR_EXT = "--preparar-extension"


def _comando_propio() -> list[str]:
    """Como relanzar este mismo programa: el .exe congelado, o el modulo en
    desarrollo (python -m generator.owner_app)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "generator.owner_app"]


def _ejecutar_elevado(args_extra: list[str], runner=subprocess.run) -> dict:
    """Relanza este programa elevado con `args_extra`, lee el JSON que escribe en
    un archivo temporal y lo devuelve como dict. Mismo patron de codigos que
    comando_reinicio(): CODIGO_UAC_CANCELADO si el usuario cancela el UAC.

    La ruta del archivo va como argumento posicional extra (no como
    -RedirectStandardOutput): ese parametro exige UseShellExecute=false, mientras
    que -Verb RunAs exige UseShellExecute=true para poder elevar - combinarlos
    hace que PowerShell rechace el Start-Process antes de mostrar el UAC."""
    fd, ruta_salida = tempfile.mkstemp(prefix="jsconnect_owner_", suffix=".json")
    os.close(fd)
    try:
        partes = _comando_propio() + args_extra + [ruta_salida]
        archivo, resto = partes[0], partes[1:]
        lista_args = ",".join(f"'{a}'" for a in resto)
        script = (
            "try { "
            f"$p = Start-Process -FilePath '{archivo}' -ArgumentList {lista_args} "
            f"-Verb RunAs -Wait -PassThru -WindowStyle Hidden -ErrorAction Stop; "
            "exit $p.ExitCode "
            f"}} catch {{ exit {CODIGO_UAC_CANCELADO} }}"
        )
        resultado = runner(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=60, check=False,
            creationflags=SIN_VENTANA,
        )
        if resultado.returncode == CODIGO_UAC_CANCELADO:
            raise RuntimeError("No se concedio el permiso de administrador (aviso UAC cancelado).")
        if resultado.returncode != 0:
            raise RuntimeError(f"La operacion elevada fallo (codigo {resultado.returncode}).")

        try:
            salida = Path(ruta_salida).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"No se pudo leer el resultado: {exc}") from exc
        try:
            datos = json.loads(salida)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Respuesta invalida del proceso elevado: {salida[:200]}") from exc

        if "error" in datos:
            raise RuntimeError(datos["error"])
        return datos
    finally:
        with contextlib.suppress(OSError):
            Path(ruta_salida).unlink(missing_ok=True)


def _correr_subcomando_leer(ruta_salida: str) -> int:
    from validator_app.proxy import secretos

    try:
        base_dir = secretos.ruta_instalacion()
        resultado = secretos.leer_secretos(base_dir)
    except secretos.SecretosError as exc:
        resultado = {"error": str(exc)}
    Path(ruta_salida).write_text(json.dumps(resultado), encoding="utf-8")
    return 0


def _correr_subcomando_rotar(cual: str, ruta_salida: str) -> int:
    from validator_app.proxy import secretos

    try:
        base_dir = secretos.ruta_instalacion()
        valor_nuevo = secretos.rotar(base_dir, cual)
        resultado = {cual: valor_nuevo}
    except secretos.SecretosError as exc:
        resultado = {"error": str(exc)}
    Path(ruta_salida).write_text(json.dumps(resultado), encoding="utf-8")
    return 0


def _correr_subcomando_preparar_extension(ruta_salida: str) -> int:
    """Elevado: arma .extension_build en la instalacion real (el .exe onefile no
    puede usar las rutas de su propio modulo, ver ruta_extension_build)."""
    from validator_app.proxy import _instalar_extension, secretos

    try:
        ruta = _instalar_extension.preparar_build(secretos.ruta_instalacion())
        resultado = {"ruta": str(ruta)}
    except (secretos.SecretosError, OSError) as exc:
        resultado = {"error": str(exc)}
    Path(ruta_salida).write_text(json.dumps(resultado), encoding="utf-8")
    return 0


def preparar_extension_elevado(runner=subprocess.run) -> Path:
    """Arma la carpeta de la extension pidiendo elevacion via UAC; devuelve su ruta."""
    return Path(_ejecutar_elevado([_FLAG_PREPARAR_EXT], runner=runner)["ruta"])


def leer_secretos_elevado(runner=subprocess.run) -> dict:
    """Devuelve {"proxy_token": ..., "admin_key": ...} pidiendo elevacion via UAC."""
    return _ejecutar_elevado([_FLAG_LEER], runner=runner)


def rotar_secreto_elevado(cual: str, runner=subprocess.run) -> str:
    """Rota `cual` ('proxy_token' o 'admin_key') pidiendo elevacion via UAC.
    Devuelve el valor nuevo."""
    datos = _ejecutar_elevado([_FLAG_ROTAR, cual], runner=runner)
    return datos[cual]


def guardar_credencial_autologin(
    usuario: str, password: str, leer=leer_secretos_elevado, enviar=None, url=None
) -> str:
    """Guarda la credencial del autologin en el proxy. Lo unico que se eleva (UAC)
    es la lectura de la admin key de config.yaml; el envio a /local/credenciales
    sale de este proceso sin elevar, asi la contrasena nunca pasa por la linea de
    comandos ni por un archivo temporal del proceso elevado."""
    usuario = (usuario or "").strip()
    if not usuario or not password:
        raise ValueError("Escribe el usuario y la contrasena de WinForce.")
    if enviar is None:
        from validator_app.proxy.rotate_creds import push_credencial_login as enviar
    admin_key = leer()["admin_key"]
    ok, mensaje = enviar(usuario, password, admin_key, url or _url_proxy_local())
    if not ok:
        raise RuntimeError(mensaje)
    return mensaje


class OwnerApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title("JSConnect Win Coverage — Owner")
        self.resizable(False, False)
        self._build_ui()
        # Tamano segun el contenido (minimo 590x620): con escala de pantalla > 100 % un
        # tamano fijo recortaba los botones de abajo.
        self.update_idletasks()
        self.geometry(f"{max(590, self.winfo_reqwidth())}x{max(620, self.winfo_reqheight())}")
        self.actualizar_estado()
        # Chequeo silencioso de version: solo avisa en la etiqueta, no abre ventanas.
        self.after(1500, self._buscar_actualizacion_silenciosa)

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        activation = ttk.LabelFrame(main, text="Activar una PC", padding=12)
        activation.pack(fill="x")
        ttk.Label(activation, text="Huella de la PC:").grid(row=0, column=0, sticky="w")
        self.txt_huella = ttk.Entry(activation, width=46, font=("Consolas", 10))
        self.txt_huella.grid(row=1, column=0, sticky="we", pady=(3, 8))
        ttk.Button(activation, text="Generar codigo", command=self.generar_codigo).grid(
            row=1, column=1, padx=(8, 0)
        )
        ttk.Label(activation, text="Codigo de activacion:").grid(row=2, column=0, sticky="w")
        self.txt_codigo = ttk.Entry(activation, width=46, font=("Consolas", 9), state="readonly")
        self.txt_codigo.grid(row=3, column=0, sticky="we", pady=(3, 0))
        ttk.Button(activation, text="Copiar", command=self.copiar_codigo).grid(
            row=3, column=1, padx=(8, 0)
        )
        activation.columnconfigure(0, weight=1)

        proxy = ttk.LabelFrame(main, text="Proxy y sesion WinForce", padding=12)
        proxy.pack(fill="x", pady=(14, 0))
        self.lbl_servicio = ttk.Label(proxy, text="Servicio proxy: comprobando...")
        self.lbl_servicio.pack(anchor="w")
        self.lbl_proxy = ttk.Label(proxy, text="Proxy: comprobando...")
        self.lbl_proxy.pack(anchor="w", pady=(4, 8))

        ttk.Label(proxy, text="URL para los agentes (Menu ⚙ → Configurar Proxy):").pack(
            anchor="w"
        )
        url_frame = ttk.Frame(proxy)
        url_frame.pack(fill="x", pady=(3, 0))
        self.txt_url_agentes = ttk.Entry(
            url_frame, width=40, font=("Consolas", 9), state="readonly"
        )
        self.txt_url_agentes.pack(side="left", fill="x", expand=True)
        ttk.Button(url_frame, text="Copiar", command=self.copiar_url_agentes).pack(
            side="left", padx=(8, 0)
        )
        # "warning" (ambar), no "danger" (rojo): sobre el fondo oscuro de
        # "superhero" el rojo da un contraste WCAG de solo 2.78:1 (ilegible,
        # bajo el minimo de 4.5:1); el ambar da 5.66:1. Ver AGENTS.md 2026-09-25.
        self.lbl_url_agentes_aviso = ttk.Label(proxy, text="", bootstyle="warning")
        self.lbl_url_agentes_aviso.pack(anchor="w", pady=(2, 0))
        ttk.Label(
            proxy,
            text="Si el agente no conecta: revisa el firewall de esta PC para ese puerto.",
            bootstyle="secondary",
        ).pack(anchor="w", pady=(4, 10))

        buttons = ttk.Frame(proxy)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Actualizar estado", command=self.actualizar_estado).pack(
            side="left"
        )
        ttk.Button(buttons, text="Renovar sesion WinForce", command=self.renovar_sesion).pack(
            side="left", padx=(8, 0)
        )
        self.btn_reiniciar = ttk.Button(
            buttons, text="Reiniciar servicio", command=self.reiniciar_servicio
        )
        self.btn_reiniciar.pack(side="left", padx=(8, 0))
        ttk.Button(
            buttons, text="Instalar extensión en Chrome",
            command=self.mostrar_instrucciones_extension, bootstyle="secondary",
        ).pack(side="left", padx=(8, 0))

        autologin_frame = ttk.LabelFrame(main, text="Autologin de WinForce", padding=12)
        autologin_frame.pack(fill="x", pady=(14, 0))
        autologin_frame.columnconfigure(0, weight=1)
        self.lbl_autologin = ttk.Label(autologin_frame, text="Autologin: comprobando...")
        self.lbl_autologin.grid(row=0, column=0, sticky="w")
        ttk.Button(
            autologin_frame, text="Configurar...", command=self.configurar_autologin,
        ).grid(row=0, column=1, sticky="e")
        self.lbl_freno = ttk.Label(
            autologin_frame, text="Frenado: comprobando...", bootstyle="secondary"
        )
        self.lbl_freno.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(
            autologin_frame, text="Frenado...", command=self.configurar_freno,
            bootstyle="secondary",
        ).grid(row=1, column=1, sticky="e", pady=(6, 0))
        self._health: dict | None = None

        secretos_frame = ttk.LabelFrame(main, text="Credenciales del proxy", padding=12)
        secretos_frame.pack(fill="x", pady=(14, 0))
        secretos_frame.columnconfigure(0, weight=1)

        self.entradas_secretos: dict[str, ttk.Entry] = {}
        self.botones_mostrar: dict[str, ttk.Button] = {}
        self.botones_rotar: dict[str, ttk.Button] = {}
        self._temporizadores_secretos: dict[str, str] = {}

        etiquetas = {"proxy_token": "Proxy token:", "admin_key": "Admin key:"}
        for fila, (clave, etiqueta) in enumerate(etiquetas.items()):
            ttk.Label(secretos_frame, text=etiqueta).grid(
                row=fila * 2, column=0, columnspan=3, sticky="w", pady=(0 if fila == 0 else 8, 0)
            )
            entrada = ttk.Entry(
                secretos_frame, width=40, font=("Consolas", 9), state="readonly", show="•"
            )
            entrada.grid(row=fila * 2 + 1, column=0, sticky="we", pady=(3, 0))
            self.entradas_secretos[clave] = entrada

            btn_mostrar = ttk.Button(
                secretos_frame, text="Mostrar",
                command=lambda c=clave: self.mostrar_secreto(c),
            )
            btn_mostrar.grid(row=fila * 2 + 1, column=1, padx=(8, 0))
            self.botones_mostrar[clave] = btn_mostrar

            ttk.Button(
                secretos_frame, text="Copiar",
                command=lambda c=clave: self.copiar_secreto(c),
            ).grid(row=fila * 2 + 1, column=2, padx=(8, 0))

            btn_rotar = ttk.Button(
                secretos_frame, text="Rotar",
                command=lambda c=clave: self.rotar_secreto(c),
            )
            btn_rotar.grid(row=fila * 2 + 1, column=3, padx=(8, 0))
            self.botones_rotar[clave] = btn_rotar

        ttk.Label(
            secretos_frame,
            text=(
                "Estas credenciales dan acceso a consultas de cobertura y score por\n"
                "DNI. No las compartas por chat ni capturas. Si se filtraron, rotalas\n"
                "aqui mismo."
            ),
            bootstyle="warning",  # ver nota de contraste junto a lbl_url_agentes_aviso
            justify="left",
        ).grid(row=len(etiquetas) * 2, column=0, columnspan=4, sticky="w", pady=(12, 0))

        self.lbl_llave = ttk.Label(main, text="", bootstyle="secondary")
        self.lbl_llave.pack(anchor="w", pady=(14, 0))

        pie = ttk.Frame(main)
        pie.pack(fill="x", pady=(10, 0))
        ttk.Label(pie, text=f"Version: {version.BUILD_TAG}", bootstyle="secondary").pack(
            side="left"
        )
        self.btn_actualizar = ttk.Button(
            pie, text="Buscar actualizaciones", command=self.buscar_actualizacion,
            bootstyle="secondary",
        )
        self.btn_actualizar.pack(side="right")
        # ambar por contraste sobre el fondo oscuro (ver nota de lbl_url_agentes_aviso)
        self.lbl_update_aviso = ttk.Label(pie, text="", bootstyle="warning")
        self.lbl_update_aviso.pack(side="right", padx=(0, 10))

    # --- Actualizaciones de la propia consola (mismo flujo que el agente) ---------

    def _es_exe(self) -> bool:
        return bool(getattr(sys, "frozen", False))

    def buscar_actualizacion(self) -> None:
        if not self._es_exe():
            messagebox.showinfo(
                "Actualizaciones",
                "La consola solo se actualiza sola cuando corre como .exe compilado.",
                parent=self,
            )
            return
        self.btn_actualizar.config(state="disabled")
        self.lbl_update_aviso.config(text="Buscando...")
        threading.Thread(target=self._buscar_update_hilo, args=(False,), daemon=True).start()

    def _buscar_actualizacion_silenciosa(self) -> None:
        if self._es_exe():
            threading.Thread(target=self._buscar_update_hilo, args=(True,), daemon=True).start()

    def _buscar_update_hilo(self, silencioso: bool) -> None:
        info = update_check.hay_actualizacion_owner(sys.executable)
        self.after(0, lambda: self._mostrar_update(info, silencioso))

    def _mostrar_update(self, info, silencioso: bool) -> None:
        self.btn_actualizar.config(state="normal")
        if info is None:
            self.lbl_update_aviso.config(text="" if silencioso else "Estas al dia")
            return
        if silencioso:
            self.lbl_update_aviso.config(
                text=f"Nueva version {info['tag']}: pulsa Buscar actualizaciones"
            )
            return
        self.lbl_update_aviso.config(text="")
        texto = (
            f"Nueva version {info['tag']} de la consola owner.\n\n"
            "¿Descargar e instalar ahora? La consola se cerrara y se abrira sola; "
            "private_key.pem no se toca."
        )
        if messagebox.askyesno("Actualizacion disponible", texto, parent=self):
            self._abrir_progreso_actualizacion()
            threading.Thread(target=self._aplicar_update_hilo, args=(info,), daemon=True).start()

    def _abrir_progreso_actualizacion(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Actualizando")
        dialog.geometry("340x110")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Descargando e instalando la actualización...").pack(pady=(0, 10))
        barra = ttk.Progressbar(frame, mode="indeterminate", bootstyle="info-striped")
        barra.pack(fill="x")
        barra.start(12)
        self._dialogo_actualizacion = dialog

    def _cerrar_progreso_actualizacion(self) -> None:
        dialog = getattr(self, "_dialogo_actualizacion", None)
        if dialog is not None:
            dialog.grab_release()
            dialog.destroy()
            self._dialogo_actualizacion = None

    def _aplicar_update_hilo(self, info) -> None:
        try:
            download.aplicar_actualizacion(info)
        except Exception as exc:
            msg = str(exc)
            self.after(0, self._cerrar_progreso_actualizacion)
            self.after(0, lambda m=msg: messagebox.showerror("Actualizacion", m, parent=self))
            return
        self.after(0, self._actualizacion_lista)

    def _actualizacion_lista(self) -> None:
        """El updater.bat quedo esperando a que este proceso cierre para reemplazar
        el .exe y reabrirlo solo (ver validator_app/updater/download.py)."""
        self._cerrar_progreso_actualizacion()
        self.lbl_update_aviso.config(text="Actualizacion lista, reiniciando...")
        self.after(1200, self.destroy)

    def generar_codigo(self) -> None:
        try:
            huella = normalizar_huella(self.txt_huella.get())
            codigo = generar.firmar_codigo(huella)
        except Exception as exc:
            messagebox.showerror("Activacion", str(exc), parent=self)
            return
        self.txt_codigo.config(state="normal")
        self.txt_codigo.delete(0, tk.END)
        self.txt_codigo.insert(0, codigo)
        self.txt_codigo.config(state="readonly")

    def copiar_codigo(self) -> None:
        self._copiar_de_entry(self.txt_codigo, "Activacion", "Codigo copiado al portapapeles.")

    def copiar_url_agentes(self) -> None:
        if not self.txt_url_agentes.get():
            messagebox.showinfo(
                "URL para agentes",
                "No se detecto la IP de red de esta PC. Usa `ipconfig` (IPv4) "
                "y arma la URL manualmente.",
                parent=self,
            )
            return
        self._copiar_de_entry(
            self.txt_url_agentes,
            "URL para agentes",
            "URL copiada. Pegala en cada agente (Menu ⚙ → Configurar Proxy).",
            limpiar=False,
        )

    def _copiar_de_entry(
        self, entry: ttk.Entry, titulo: str, mensaje_ok: str, limpiar: bool = True
    ) -> None:
        valor = entry.get()
        if not valor:
            return
        # Secretos (limpiar=True): fuera del historial de Windows (Win+V) y de la
        # nube. Si la API no esta disponible, el portapapeles normal de Tk.
        if not (limpiar and copiar_sin_historial(valor)):
            self.clipboard_clear()
            self.clipboard_append(valor)
            self.update()
        messagebox.showinfo(titulo, mensaje_ok, parent=self)
        if not limpiar:
            return
        # El portapapeles conserva secretos entre aplicaciones; se limpia solo
        # si nadie mas lo sobreescribio mientras tanto.
        self.after(SEGUNDOS_LIMPIAR_PORTAPAPELES * 1000, lambda: self._limpiar_portapapeles(valor))

    def _limpiar_portapapeles(self, valor_esperado: str) -> None:
        try:
            actual = self.clipboard_get()
        except tk.TclError:
            return
        if actual == valor_esperado:
            self.clipboard_clear()

    def _set_entry(self, entry: ttk.Entry, valor: str) -> None:
        entry.config(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, valor)
        entry.config(state="readonly")

    def mostrar_secreto(self, cual: str) -> None:
        if not messagebox.askyesno(
            "Credenciales",
            "Para mostrar esta credencial, Windows pedira permiso de "
            "administrador (aviso UAC).\n\n¿Continuar?",
            parent=self,
        ):
            return

        boton = self.botones_mostrar[cual]
        boton.config(state="disabled")

        def trabajo() -> None:
            try:
                valores = leer_secretos_elevado()
                valor = valores[cual]
            except Exception as exc:
                # Python borra `exc` al salir del except; guardarlo aparte para
                # que el lambda diferido (self.after) no reviente con NameError.
                mensaje = str(exc)
                self.after(0, lambda: messagebox.showerror("Credenciales", mensaje, parent=self))
                self.after(0, lambda: boton.config(state="normal"))
                return

            def aplicar() -> None:
                self._set_entry(self.entradas_secretos[cual], valor)
                self.entradas_secretos[cual].config(show="")
                boton.config(state="normal")
                self._reprogramar_ocultar(cual)

            self.after(0, aplicar)

        threading.Thread(target=trabajo, daemon=True).start()

    def _reprogramar_ocultar(self, cual: str) -> None:
        anterior = self._temporizadores_secretos.pop(cual, None)
        if anterior is not None:
            self.after_cancel(anterior)
        id_temporizador = self.after(
            SEGUNDOS_OCULTAR_SECRETO * 1000, lambda: self._ocultar_secreto(cual)
        )
        self._temporizadores_secretos[cual] = id_temporizador

    def _ocultar_secreto(self, cual: str) -> None:
        self._temporizadores_secretos.pop(cual, None)
        entry = self.entradas_secretos[cual]
        self._set_entry(entry, "")
        entry.config(show="•")

    def copiar_secreto(self, cual: str) -> None:
        entry = self.entradas_secretos[cual]
        if not entry.get():
            messagebox.showinfo(
                "Credenciales", "Primero pulsa Mostrar para poder copiarlo.", parent=self
            )
            return
        etiqueta = "Proxy token" if cual == "proxy_token" else "Admin key"
        self._copiar_de_entry(entry, "Credenciales", f"{etiqueta} copiado al portapapeles.")

    def rotar_secreto(self, cual: str) -> None:
        if cual == "proxy_token":
            aviso = (
                "Se generara un PROXY TOKEN nuevo.\n\n"
                "Todos los agentes ya configurados dejaran de funcionar hasta que "
                "reciban el token nuevo.\n\n"
                "Windows pedira permiso de administrador (aviso UAC).\n\n¿Continuar?"
            )
            mensaje_exito = (
                "Credencial rotada y servicio reiniciado.\n\n"
                "El PROXY TOKEN cambio: hay que actualizarlo en cada agente "
                "(Menu ⚙ Configuracion → Configurar Proxy, o el script de "
                "keyring) antes de que puedan volver a conectarse."
            )
        else:
            aviso = (
                "Se generara un ADMIN KEY nuevo.\n\n"
                "Solo afecta a esta consola y a herramientas de administracion.\n\n"
                "Windows pedira permiso de administrador (aviso UAC).\n\n¿Continuar?"
            )
            mensaje_exito = (
                "Credencial rotada y servicio reiniciado.\n\n"
                "El ADMIN KEY nuevo solo lo usa esta consola y las herramientas "
                "de administracion; no hace falta distribuirlo a los agentes."
            )
        if not messagebox.askyesno("Rotar credencial", aviso, parent=self):
            return

        self.botones_rotar[cual].config(state="disabled")
        self.botones_mostrar[cual].config(state="disabled")

        def trabajo() -> None:
            try:
                valor_nuevo = rotar_secreto_elevado(cual)
            except Exception as exc:
                mensaje = str(exc)  # ver nota de mostrar_secreto: exc no sobrevive al except
                self.after(
                    0, lambda: messagebox.showerror("Rotar credencial", mensaje, parent=self)
                )
                self.after(0, lambda: self.botones_rotar[cual].config(state="normal"))
                self.after(0, lambda: self.botones_mostrar[cual].config(state="normal"))
                return

            def aplicar() -> None:
                self._set_entry(self.entradas_secretos[cual], valor_nuevo)
                self.entradas_secretos[cual].config(show="")
                self.botones_rotar[cual].config(state="normal")
                self.botones_mostrar[cual].config(state="normal")
                self._reprogramar_ocultar(cual)
                messagebox.showinfo("Rotar credencial", mensaje_exito, parent=self)

            self.after(0, aplicar)

        threading.Thread(target=trabajo, daemon=True).start()

    def actualizar_estado(self) -> None:
        self.lbl_llave.config(
            text=(
                "Llave privada: disponible y protegida localmente"
                if generar.PRIVATE_KEY_FILE.exists()
                else "Llave privada: falta private_key.pem"
            )
        )

        def consultar() -> None:
            servicio = consultar_servicio()
            health = _leer_health()
            proxy = describir_proxy(health)
            autologin = describir_autologin(health)
            freno = describir_freno(health)
            ip = detectar_ip_lan()
            url_agentes = url_para_agentes(ip, puerto_proxy_local())
            self.after(0, lambda: self.lbl_servicio.config(text=servicio))
            self.after(0, lambda: self.lbl_proxy.config(text=proxy))
            self.after(0, lambda: self.lbl_autologin.config(text=autologin))
            self.after(0, lambda: self.lbl_freno.config(text=freno))
            self.after(0, lambda: setattr(self, "_health", health))
            self.after(0, lambda: self._aplicar_url_agentes(url_agentes))

        threading.Thread(target=consultar, daemon=True).start()

    def _aplicar_url_agentes(self, url: str) -> None:
        self._set_entry(self.txt_url_agentes, url)
        self.lbl_url_agentes_aviso.config(
            text="" if url else "No se pudo detectar la IP de red; usa `ipconfig` (IPv4)."
        )

    def reiniciar_servicio(self) -> None:
        if not messagebox.askyesno(
            "Reiniciar servicio",
            "Se reiniciara el servicio del proxy (Windows pedira permiso de "
            "administrador).\n\nLa sesion de WinForce se conserva. Los agentes "
            "pueden fallar unos segundos.\n\n¿Continuar?",
            parent=self,
        ):
            return
        self.btn_reiniciar.config(state="disabled")

        def reiniciar() -> None:
            ok, mensaje = reiniciar_servicio()
            if ok:
                time.sleep(ESPERA_ARRANQUE_SEGUNDOS)
            else:
                self.after(
                    0, lambda: messagebox.showerror("Reiniciar servicio", mensaje, parent=self)
                )
            self.after(0, lambda: self.btn_reiniciar.config(state="normal"))
            self.after(0, self.actualizar_estado)

        threading.Thread(target=reiniciar, daemon=True).start()

    def configurar_autologin(self) -> None:
        """Dialogo de usuario/contrasena de la cuenta dedicada para el autologin."""
        dialogo = ttk.Toplevel(self)
        dialogo.title("Autologin de WinForce")
        dialogo.resizable(False, False)
        dialogo.transient(self)
        dialogo.grab_set()
        cuerpo = ttk.Frame(dialogo, padding=16)
        cuerpo.pack(fill="both", expand=True)

        ttk.Label(cuerpo, text="Usuario (correo de Microsoft de la cuenta dedicada):").pack(
            anchor="w"
        )
        txt_usuario = ttk.Entry(cuerpo, width=42)
        txt_usuario.pack(fill="x", pady=(3, 8))
        ttk.Label(cuerpo, text="Contraseña:").pack(anchor="w")
        txt_password = ttk.Entry(cuerpo, width=42, show="•")
        txt_password.pack(fill="x", pady=(3, 8))
        ttk.Label(
            cuerpo,
            text=(
                "Con la cuenta dedicada guardada, el proxy vuelve a entrar solo cuando\n"
                "la sesion muere. Solo hace falta repetirlo si WinForce cambia la\n"
                "contrasena. Se guarda cifrada en el keyring del servicio del proxy\n"
                "(nunca en config.yaml). Windows pedira permiso de administrador (UAC)."
            ),
            bootstyle="secondary",
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        botones = ttk.Frame(cuerpo)
        botones.pack(fill="x")
        btn_guardar = ttk.Button(botones, text="Guardar")
        btn_guardar.pack(side="right")
        ttk.Button(
            botones, text="Cancelar", command=dialogo.destroy, bootstyle="secondary"
        ).pack(side="right", padx=(0, 8))

        def guardar() -> None:
            usuario, password = txt_usuario.get(), txt_password.get()
            if not usuario.strip() or not password:
                messagebox.showerror(
                    "Autologin", "Escribe el usuario y la contraseña.", parent=dialogo
                )
                return
            btn_guardar.config(state="disabled")

            def trabajo() -> None:
                try:
                    guardar_credencial_autologin(usuario, password)
                except Exception as exc:
                    mensaje = str(exc)  # ver nota de mostrar_secreto: exc no sobrevive
                    self.after(
                        0, lambda: messagebox.showerror("Autologin", mensaje, parent=dialogo)
                    )
                    self.after(0, lambda: btn_guardar.config(state="normal"))
                    return

                def listo() -> None:
                    dialogo.destroy()
                    messagebox.showinfo(
                        "Autologin",
                        "Credencial guardada. Desde ahora el proxy vuelve a entrar solo a "
                        "WinForce cuando la sesion muera.",
                        parent=self,
                    )
                    self.actualizar_estado()

                self.after(0, listo)

            threading.Thread(target=trabajo, daemon=True).start()

        btn_guardar.config(command=guardar)
        txt_password.bind("<Return>", lambda _e: guardar())
        txt_usuario.focus_set()

    def configurar_freno(self) -> None:
        """Dialogo del frenado del autologin: perfiles con nombre o personalizado."""
        from validator_app.proxy import autologin

        perfiles = perfiles_para_combo()
        nombres = [nombre for _clave, nombre in perfiles]
        clave_de = {nombre: clave for clave, nombre in perfiles}
        actual = (self._health or {}).get("autologin") or {}
        freno_actual = actual.get("freno") or {}
        clave_actual = freno_actual.get("perfil", autologin.PERFIL_RECOMENDADO)
        minutos_actuales = (freno_actual.get("minutos") or [0, 1, 2, 3, 5])[1:]

        dialogo = ttk.Toplevel(self)
        dialogo.title("Frenado del autologin")
        dialogo.resizable(False, False)
        dialogo.transient(self)
        dialogo.grab_set()
        cuerpo = ttk.Frame(dialogo, padding=16)
        cuerpo.pack(fill="both", expand=True)

        ttk.Label(
            cuerpo,
            text=(
                "Espera entre intentos FALLIDOS de volver a entrar a WinForce.\n"
                "El 1.er intento siempre es inmediato."
            ),
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(cuerpo, text="Rango:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        combo = ttk.Combobox(cuerpo, values=nombres, state="readonly", width=40)
        combo.grid(row=1, column=1, sticky="we", pady=(10, 0))

        etiquetas = (
            "Antes del 2.º intento (min):",
            "Antes del 3.º intento (min):",
            "Antes del 4.º intento (min):",
            "Del 5.º en adelante, cada (min):",
        )
        valores = [tk.IntVar(value=m) for m in minutos_actuales]
        selectores = []
        for i, texto in enumerate(etiquetas):
            ttk.Label(cuerpo, text=texto).grid(row=2 + i, column=0, sticky="w", pady=(6, 0))
            sel = ttk.Spinbox(cuerpo, textvariable=valores[i], width=6, state="readonly")
            sel.grid(row=2 + i, column=1, sticky="w", pady=(6, 0))
            selectores.append(sel)

        lbl_linea = ttk.Label(cuerpo, text="", bootstyle="info", justify="left")
        lbl_linea.grid(row=6, column=0, columnspan=2, sticky="w", pady=(12, 0))
        lbl_aviso = ttk.Label(
            cuerpo, text="", bootstyle="warning", justify="left", wraplength=440
        )
        lbl_aviso.grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def minutos() -> list[int]:
            return ajustar_minutos([v.get() for v in valores])

        def refrescar() -> None:
            m = minutos()
            for var, valor in zip(valores, m, strict=True):
                var.set(valor)
            personalizado = clave_de[combo.get()] == autologin.PERFIL_PERSONALIZADO
            for sel, (desde, hasta) in zip(selectores, rangos_freno(m[0], m[1]), strict=True):
                sel.config(from_=desde, to=hasta, state="readonly" if personalizado else "disabled")
            lbl_linea.config(text=linea_de_tiempo_freno(m))
            clave = clave_de[combo.get()]
            aviso = autologin.PERFILES_FRENO.get(clave, {}).get("aviso", "")
            if personalizado:
                iguales = [
                    p for p in autologin.PERFILES_FRENO.values() if list(p["minutos"]) == m
                ]
                aviso = iguales[0]["aviso"] if iguales else ""
            lbl_aviso.config(text=aviso)

        def elegir_perfil(_evento=None) -> None:
            clave = clave_de[combo.get()]
            if clave in autologin.PERFILES_FRENO:
                for var, valor in zip(valores, autologin.PERFILES_FRENO[clave]["minutos"],
                                      strict=True):
                    var.set(valor)
            refrescar()

        for sel in selectores:
            sel.config(command=refrescar)
        combo.bind("<<ComboboxSelected>>", elegir_perfil)
        combo.set(dict(perfiles).get(clave_actual, nombres[0]))
        elegir_perfil()

        botones = ttk.Frame(cuerpo)
        botones.grid(row=8, column=0, columnspan=2, sticky="we", pady=(16, 0))
        btn_guardar = ttk.Button(botones, text="Guardar")
        btn_guardar.pack(side="right")
        ttk.Button(
            botones, text="Cancelar", command=dialogo.destroy, bootstyle="secondary"
        ).pack(side="right", padx=(0, 8))

        def restaurar() -> None:
            combo.set(dict(perfiles)[autologin.PERFIL_RECOMENDADO])
            elegir_perfil()

        ttk.Button(
            botones, text="Restaurar recomendado", command=restaurar, bootstyle="secondary"
        ).pack(side="left")

        def guardar() -> None:
            clave, m = clave_de[combo.get()], minutos()
            try:
                autologin.resolver_freno(clave, m)
            except ValueError as exc:
                messagebox.showerror("Frenado", str(exc), parent=dialogo)
                return
            btn_guardar.config(state="disabled")

            def trabajo() -> None:
                try:
                    guardar_freno_autologin(clave, m)
                except Exception as exc:
                    mensaje = str(exc)  # ver nota de mostrar_secreto: exc no sobrevive
                    self.after(
                        0, lambda: messagebox.showerror("Frenado", mensaje, parent=dialogo)
                    )
                    self.after(0, lambda: btn_guardar.config(state="normal"))
                    return

                def listo() -> None:
                    dialogo.destroy()
                    messagebox.showinfo(
                        "Frenado", "Frenado del autologin guardado y aplicado.", parent=self
                    )
                    self.actualizar_estado()

                self.after(0, listo)

            threading.Thread(target=trabajo, daemon=True).start()

        btn_guardar.config(command=guardar)

    def renovar_sesion(self) -> None:
        def renovar() -> None:
            try:
                from validator_app.proxy import rotate_creds

                resultado = rotate_creds.main([])
                if resultado == 0:
                    self.after(0, self.actualizar_estado)
            except Exception as exc:
                mensaje = str(exc)
                self.after(
                    0,
                    lambda: messagebox.showerror("Sesion WinForce", mensaje, parent=self),
                )

        threading.Thread(target=renovar, daemon=True).start()

    def mostrar_instrucciones_extension(self) -> None:
        """Dialogo con los pasos para cargar la extension 'Renovar sesion
        WinForce' a mano en chrome://extensions (mismo texto que imprime
        install_service.bat al final, con la ruta real de esta instalacion)."""
        ruta, aviso, preparable = ruta_extension_build()

        dialog = tk.Toplevel(self)
        dialog.title("Instalar extensión en Chrome")
        dialog.geometry("520x380")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=(
                "1. Abre Chrome y escribe: chrome://extensions\n"
                "2. Activa «Modo de desarrollador» (arriba a la derecha).\n"
                "3. Pulsa «Cargar descomprimida» y elige esta carpeta:"
            ),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        frame_ruta = ttk.Frame(frame)
        frame_ruta.pack(fill="x", pady=(0, 4))
        self.txt_ruta_extension = ttk.Entry(frame_ruta, font=("Consolas", 9), state="readonly")
        self.txt_ruta_extension.pack(side="left", fill="x", expand=True)
        self._set_entry(self.txt_ruta_extension, str(ruta) if ruta else "")
        btn_copiar = ttk.Button(
            frame_ruta, text="Copiar ruta",
            command=lambda: self._copiar_de_entry(
                self.txt_ruta_extension, "Instalar extensión", "Ruta copiada.", limpiar=False
            ),
        )
        btn_copiar.pack(side="left", padx=(8, 0))
        if not ruta:
            btn_copiar.config(state="disabled")
            lbl_aviso = ttk.Label(
                frame, text=aviso, bootstyle="warning", justify="left", wraplength=480
            )
            lbl_aviso.pack(anchor="w", pady=(4, 0))
            if preparable:
                btn_preparar = ttk.Button(frame, text="Preparar carpeta")

                def preparar() -> None:
                    btn_preparar.config(state="disabled")

                    def trabajo() -> None:
                        try:
                            nueva = preparar_extension_elevado()
                        except Exception as exc:
                            mensaje = str(exc)  # ver nota de mostrar_secreto
                            self.after(0, lambda: messagebox.showerror(
                                "Instalar extensión", mensaje, parent=dialog
                            ))
                            self.after(0, lambda: btn_preparar.config(state="normal"))
                            return

                        def listo() -> None:
                            self._set_entry(self.txt_ruta_extension, str(nueva))
                            btn_copiar.config(state="normal")
                            lbl_aviso.config(text="Carpeta preparada. Ya puedes copiar la ruta.")
                            btn_preparar.pack_forget()

                        self.after(0, listo)

                    threading.Thread(target=trabajo, daemon=True).start()

                btn_preparar.config(command=preparar)
                btn_preparar.pack(anchor="w", pady=(6, 0))

        ttk.Label(
            frame,
            text=(
                "4. Fija el icono con el puzzle y el pin, en la barra de Chrome.\n\n"
                "Chrome muestra un aviso por el modo desarrollador: es normal.\n"
                "Sin extension tambien se puede renovar la sesion con el icono\n"
                "«Renovar sesion WinForce» del Escritorio."
            ),
            justify="left",
            bootstyle="secondary",
        ).pack(anchor="w", pady=(12, 0))

        ttk.Button(frame, text="Cerrar", command=dialog.destroy, bootstyle="secondary").pack(
            anchor="e", pady=(16, 0)
        )


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == _FLAG_PREPARAR_EXT:
        if len(argv) < 2:
            print(json.dumps({"error": f"{_FLAG_PREPARAR_EXT} requiere la ruta de salida"}))
            return 1
        return _correr_subcomando_preparar_extension(argv[1])
    if argv and argv[0] == _FLAG_LEER:
        if len(argv) < 2:
            print(json.dumps({"error": f"{_FLAG_LEER} requiere la ruta de salida"}))
            return 1
        return _correr_subcomando_leer(argv[1])
    if argv and argv[0] == _FLAG_ROTAR:
        if len(argv) < 3 or argv[1] not in ("proxy_token", "admin_key"):
            mensaje = f"{_FLAG_ROTAR} requiere 'proxy_token' o 'admin_key' y la ruta de salida"
            print(json.dumps({"error": mensaje}))
            return 1
        return _correr_subcomando_rotar(argv[1], argv[2])

    OwnerApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
