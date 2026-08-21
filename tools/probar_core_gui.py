"""Arnes de prueba del nucleo con interfaz grafica (Fase 1).

Uso:
    python tools/probar_core_gui.py

Misma logica que tools/probar_core.py pero en ventana: campos de usuario,
contrasena, coordenadas y documento; el flujo login -> cobertura -> score
corre en un hilo aparte para no congelar la interfaz.
"""

import threading
import tkinter as tk
from tkinter import ttk

from validator_app.gui import prueba_core

COORDENADAS_PREDETERMINADAS = "-12.087718994493725, -76.98571219979543"
DOCUMENTO_PREDETERMINADO = "75020496"


class PruebaCoreApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Prueba del nucleo - JSConnect Win Coverage")
        self.geometry("620x480")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Usuario (email):").grid(row=0, column=0, sticky="w")
        self.txt_usuario = ttk.Entry(main, width=42)
        self.txt_usuario.grid(row=1, column=0, sticky="we", pady=(2, 8))

        ttk.Label(main, text="Contrasena:").grid(row=2, column=0, sticky="w")
        self.txt_contrasena = ttk.Entry(main, width=42, show="*")
        self.txt_contrasena.grid(row=3, column=0, sticky="we", pady=(2, 8))

        ttk.Label(main, text="Coordenadas (latitud, longitud):").grid(row=4, column=0, sticky="w")
        self.txt_coordenadas = ttk.Entry(main, width=52)
        self.txt_coordenadas.insert(0, COORDENADAS_PREDETERMINADAS)
        self.txt_coordenadas.grid(row=5, column=0, sticky="we", pady=(2, 8))

        ttk.Label(main, text="Documento (DNI/RUC/CE):").grid(row=6, column=0, sticky="w")
        self.txt_documento = ttk.Entry(main, width=32)
        self.txt_documento.insert(0, DOCUMENTO_PREDETERMINADO)
        self.txt_documento.grid(row=7, column=0, sticky="w", pady=(2, 8))

        self.btn_validar = ttk.Button(
            main, text="VALIDAR", command=self._validar
        )
        self.btn_validar.grid(row=8, column=0, sticky="we", pady=(4, 10))

        frame_salida = ttk.LabelFrame(main, text="Salida", padding=8)
        frame_salida.grid(row=9, column=0, sticky="nsew")
        main.rowconfigure(9, weight=1)
        main.columnconfigure(0, weight=1)

        self.txt_salida = tk.Text(frame_salida, height=14, state="disabled", wrap="word")
        scroll = ttk.Scrollbar(frame_salida, command=self.txt_salida.yview)
        self.txt_salida.configure(yscrollcommand=scroll.set)
        self.txt_salida.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _escribir_salida(self, texto):
        self.txt_salida.config(state="normal")
        for linea in texto:
            self.txt_salida.insert("end", linea + "\n")
        self.txt_salida.config(state="disabled")

    def _validar(self):
        usuario = self.txt_usuario.get().strip()
        contrasena = self.txt_contrasena.get()
        coordenadas = self.txt_coordenadas.get().strip()
        documento = self.txt_documento.get().strip()
        if not usuario or not contrasena:
            self._escribir_salida(["[ERROR] Usuario y contrasena son obligatorios."])
            return

        self.btn_validar.config(state="disabled")
        self._escribir_salida(["", "--- Validando... ---"])
        threading.Thread(
            target=self._validar_en_hilo,
            args=(usuario, contrasena, coordenadas, documento),
            daemon=True,
        ).start()

    def _validar_en_hilo(self, usuario, contrasena, coordenadas, documento):
        try:
            lineas = prueba_core.ejecutar_prueba(usuario, contrasena, coordenadas, documento)
        except Exception as exc:
            lineas = [f"[ERROR] {type(exc).__name__}: {exc}"]
        self.after(0, lambda: self._fin_validacion(lineas))

    def _fin_validacion(self, lineas):
        self._escribir_salida(lineas)
        self.btn_validar.config(state="normal")


def main() -> int:
    app = PruebaCoreApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
