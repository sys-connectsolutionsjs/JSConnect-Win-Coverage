"""Consola grafica para el owner: activaciones y estado local del proxy."""

from __future__ import annotations

import re
import subprocess
import threading
import tkinter as tk
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


def consultar_servicio() -> str:
    try:
        resultado = subprocess.run(
            ["sc", "query", "JSWinProxy"], capture_output=True, text=True, timeout=5, check=False
        )
    except OSError:
        return "Servicio proxy: no se pudo consultar"
    return estado_servicio(resultado.stdout + resultado.stderr)


URL_PROXY_LOCAL_POR_DEFECTO = "http://127.0.0.1:8080"


def _url_proxy_local() -> str | None:
    """URL local del proxy, o None si config.yaml no existe o no es valido.

    config.yaml tiene ACL SYSTEM/Administradores: sin elevar da PermissionError,
    pero /health es publico, asi que se usa el puerto por defecto en vez de
    fingir que el servicio no esta configurado."""
    try:
        from validator_app.proxy.config import ProxyConfig

        return ProxyConfig().proxy_local_url
    except PermissionError:
        return URL_PROXY_LOCAL_POR_DEFECTO
    except Exception:
        return None


def consultar_proxy() -> str:
    url = _url_proxy_local()
    if url is None:
        return "Proxy: falta configurar el servicio"

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


class OwnerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JSConnect Win Coverage — Owner")
        self.geometry("590x390")
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
        codigo = self.txt_codigo.get()
        if not codigo:
            return
        self.clipboard_clear()
        self.clipboard_append(codigo)
        self.update()
        messagebox.showinfo("Activacion", "Codigo copiado al portapapeles.", parent=self)

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
    OwnerApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
