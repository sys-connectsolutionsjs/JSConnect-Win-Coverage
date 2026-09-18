"""Consola grafica para el owner: activaciones y estado local del proxy."""

from __future__ import annotations

import re
import subprocess
import threading
import time
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


CODIGO_UAC_CANCELADO = 2
ESPERA_ARRANQUE_SEGUNDOS = 5


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
        self.btn_reiniciar = ttk.Button(
            buttons, text="Reiniciar servicio", command=self.reiniciar_servicio
        )
        self.btn_reiniciar.pack(side="left", padx=(8, 0))

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
    OwnerApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
