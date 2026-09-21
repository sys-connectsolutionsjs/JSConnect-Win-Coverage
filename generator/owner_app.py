"""Consola grafica para el owner: activaciones y estado local del proxy."""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import httpx

from generator import generar


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
            comando_reinicio(), capture_output=True, text=True, timeout=120, check=False
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
            ["sc", "query", "JSWinProxy"], capture_output=True, text=True, timeout=5, check=False
        )
    except OSError:
        return "Servicio proxy: no se pudo consultar"
    return estado_servicio(resultado.stdout + resultado.stderr)


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


def consultar_proxy() -> str:
    url = _url_proxy_local()

    try:
        respuesta = httpx.get(f"{url}/health", timeout=5)
        respuesta.raise_for_status()
        datos = respuesta.json()
    except Exception:
        return "Proxy: no responde localmente"

    if datos.get("session_alive"):
        return "Proxy: operativo; sesion WinForce viva"
    if datos.get("logged_in"):
        return "Proxy: operativo; sesion WinForce caducada"
    return "Proxy: operativo; sin sesion WinForce"


# ==================== SUBCOMANDOS ELEVADOS (sin GUI) ====================
# config.yaml tiene ACL de SYSTEM+Administradores (install_service.bat:273-276):
# leerlo o rotarlo exige correr elevado. En vez de debilitar la ACL (expondria
# los tokens a cualquier proceso no elevado del owner, perdiendo el filtro de
# UAC), la consola se relanza a si misma solo para estas dos operaciones.

_FLAG_LEER = "--leer-secretos"
_FLAG_ROTAR = "--rotar-secretos"


def _comando_propio() -> list[str]:
    """Como relanzar este mismo programa: el .exe congelado, o el modulo en
    desarrollo (python -m generator.owner_app)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "generator.owner_app"]


def _ejecutar_elevado(args_extra: list[str], runner=subprocess.run) -> dict:
    """Relanza este programa elevado con `args_extra`, captura su stdout (JSON)
    y lo devuelve como dict. Mismo patron de codigos que comando_reinicio():
    CODIGO_UAC_CANCELADO si el usuario cancela el UAC.

    Usa Start-Process -RedirectStandardOutput en vez de anidar redirecciones de
    shell: evita el escapado de comillas de un comando dentro de otro."""
    fd, ruta_salida = tempfile.mkstemp(prefix="jsconnect_owner_", suffix=".json")
    os.close(fd)
    try:
        partes = _comando_propio() + args_extra
        archivo, resto = partes[0], partes[1:]
        lista_args = ",".join(f"'{a}'" for a in resto)
        script = (
            "try { "
            f"$p = Start-Process -FilePath '{archivo}' -ArgumentList {lista_args} "
            f"-Verb RunAs -Wait -PassThru -WindowStyle Hidden -ErrorAction Stop "
            f"-RedirectStandardOutput '{ruta_salida}'; "
            "exit $p.ExitCode "
            f"}} catch {{ exit {CODIGO_UAC_CANCELADO} }}"
        )
        resultado = runner(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=60, check=False,
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


def _correr_subcomando_leer() -> int:
    from validator_app.proxy import secretos

    try:
        base_dir = secretos.ruta_instalacion()
        valores = secretos.leer_secretos(base_dir)
        print(json.dumps(valores))
    except secretos.SecretosError as exc:
        print(json.dumps({"error": str(exc)}))
    return 0


def _correr_subcomando_rotar(cual: str) -> int:
    from validator_app.proxy import secretos

    try:
        base_dir = secretos.ruta_instalacion()
        valor_nuevo = secretos.rotar(base_dir, cual)
        print(json.dumps({cual: valor_nuevo}))
    except secretos.SecretosError as exc:
        print(json.dumps({"error": str(exc)}))
    return 0


def leer_secretos_elevado(runner=subprocess.run) -> dict:
    """Devuelve {"proxy_token": ..., "admin_key": ...} pidiendo elevacion via UAC."""
    return _ejecutar_elevado([_FLAG_LEER], runner=runner)


def rotar_secreto_elevado(cual: str, runner=subprocess.run) -> str:
    """Rota `cual` ('proxy_token' o 'admin_key') pidiendo elevacion via UAC.
    Devuelve el valor nuevo."""
    datos = _ejecutar_elevado([_FLAG_ROTAR, cual], runner=runner)
    return datos[cual]


class OwnerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JSConnect Win Coverage — Owner")
        self.geometry("590x560")
        self.resizable(False, False)
        self._build_ui()
        self.actualizar_estado()

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
        self.lbl_proxy.pack(anchor="w", pady=(4, 10))
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
            foreground="#8a1f1f",
            justify="left",
        ).grid(row=len(etiquetas) * 2, column=0, columnspan=4, sticky="w", pady=(12, 0))

        self.lbl_llave = ttk.Label(main, text="", foreground="#555555")
        self.lbl_llave.pack(anchor="w", pady=(14, 0))

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

    def _copiar_de_entry(self, entry: ttk.Entry, titulo: str, mensaje_ok: str) -> None:
        valor = entry.get()
        if not valor:
            return
        self.clipboard_clear()
        self.clipboard_append(valor)
        self.update()
        messagebox.showinfo(titulo, mensaje_ok, parent=self)
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
                "reciban el token nuevo.\n\n¿Continuar?"
            )
        else:
            aviso = (
                "Se generara un ADMIN KEY nuevo.\n\n"
                "Solo afecta a esta consola y a herramientas de administracion.\n\n"
                "¿Continuar?"
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
                messagebox.showinfo(
                    "Rotar credencial", "Credencial rotada y servicio reiniciado.", parent=self
                )

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
            proxy = consultar_proxy()
            self.after(0, lambda: self.lbl_servicio.config(text=servicio))
            self.after(0, lambda: self.lbl_proxy.config(text=proxy))

        threading.Thread(target=consultar, daemon=True).start()

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


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == _FLAG_LEER:
        return _correr_subcomando_leer()
    if argv and argv[0] == _FLAG_ROTAR:
        if len(argv) < 2 or argv[1] not in ("proxy_token", "admin_key"):
            print(json.dumps({"error": f"{_FLAG_ROTAR} requiere 'proxy_token' o 'admin_key'"}))
            return 1
        return _correr_subcomando_rotar(argv[1])

    OwnerApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
