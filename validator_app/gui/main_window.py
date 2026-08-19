"""Ventana principal de la aplicacion."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from validator_app.activation import fingerprint, signer
from validator_app.activation import state as activation_state
from validator_app.core import api
from validator_app.gui import fields
from validator_app.updater import check as update_check
from validator_app.updater import download


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JSConnect Win Coverage")
        self.geometry("540x580")
        self.resizable(False, False)
        self._build_ui()
        self.after(200, self._inicio)

    def _build_ui(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Coordenadas (latitud, longitud):").grid(row=0, column=0, sticky="w")
        self.txt_coordenadas = ttk.Entry(main, width=52)
        self.txt_coordenadas.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 8))

        ttk.Label(main, text="Documento (DNI/RUC/CE):").grid(row=2, column=0, sticky="w")
        self.txt_documento = ttk.Entry(main, width=32)
        self.txt_documento.grid(row=3, column=0, sticky="we", pady=(2, 2))
        self.lbl_tipo = ttk.Label(main, text="Tipo: —")
        self.lbl_tipo.grid(row=3, column=1, sticky="w", padx=(8, 0))
        self.txt_documento.bind("<KeyRelease>", self._on_documento_cambio)

        self.btn_validar = ttk.Button(main, text="VALIDAR", command=self._validar)
        self.btn_validar.grid(row=4, column=0, columnspan=2, pady=10, sticky="we")

        frame_res = ttk.LabelFrame(main, text="Resultado", padding=10)
        frame_res.grid(row=5, column=0, columnspan=2, sticky="we")
        self.lbl_cobertura = ttk.Label(frame_res, text="Cobertura: —")
        self.lbl_cobertura.pack(anchor="w")
        self.lbl_score = ttk.Label(frame_res, text="Score: —")
        self.lbl_score.pack(anchor="w")

        frame_inferior = ttk.Frame(main)
        frame_inferior.grid(row=6, column=0, columnspan=2, sticky="we", pady=(10, 0))
        self.btn_update = ttk.Button(
            frame_inferior, text="Buscar actualizaciones", command=self._buscar_actualizacion
        )
        self.btn_update.pack(side="left")

        self.lbl_estado = ttk.Label(main, text="Estado: iniciando...", anchor="w")
        self.lbl_estado.grid(row=7, column=0, columnspan=2, sticky="we", pady=(10, 0))

    def _inicio(self):
        self._verificar_activacion()
        self.lbl_estado.config(text="Estado: listo")

    def _verificar_activacion(self):
        if not signer.activacion_disponible():
            self.lbl_estado.config(text="Estado: modo desarrollo (activacion pendiente)")
            return
        huella = fingerprint.obtener_huella()
        guardado = activation_state.leer()
        if (
            guardado
            and guardado.get("huella") == huella
            and signer.validar_codigo(huella, guardado.get("codigo", ""))
        ):
            return
        self._mostrar_activacion(huella)

    def _mostrar_activacion(self, huella):
        dialog = tk.Toplevel(self)
        dialog.title("Activacion requerida")
        dialog.geometry("460x280")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Huella de esta computadora:").pack(anchor="w")
        ttk.Label(frame, text=huella, font=("Consolas", 11, "bold")).pack(anchor="w", pady=(2, 8))
        ttk.Label(frame, text="Enviala al encargado e ingresa el codigo de activacion:").pack(
            anchor="w"
        )
        txt_codigo = ttk.Entry(frame, width=36, font=("Consolas", 10))
        txt_codigo.pack(fill="x", pady=(4, 10))

        def activar():
            codigo = txt_codigo.get().strip()
            if signer.validar_codigo(huella, codigo):
                activation_state.guardar(huella, codigo)
                dialog.destroy()
                self.lbl_estado.config(text="Estado: activado")
            else:
                messagebox.showerror(
                    "Activacion", "Codigo invalido o de otra maquina.", parent=dialog
                )

        ttk.Button(frame, text="ACTIVAR", command=activar).pack()
        ttk.Label(
            frame, text="Sin codigo valido la aplicacion no valida.", foreground="gray"
        ).pack(pady=(10, 0))

    def _on_documento_cambio(self, _event=None):
        numero = self.txt_documento.get().strip()
        try:
            tipo = fields.detectar_tipo_documento(numero)
            self.lbl_tipo.config(text=f"Tipo: {tipo}")
        except ValueError:
            self.lbl_tipo.config(text="Tipo: —")

    def _validar(self):
        try:
            lat, lon = fields.parse_coordenadas(self.txt_coordenadas.get())
        except ValueError as exc:
            messagebox.showerror("Coordenadas", str(exc))
            return
        numero = self.txt_documento.get().strip()
        if not numero:
            messagebox.showerror("Documento", "Ingresa un documento.")
            return
        try:
            tipo = fields.detectar_tipo_documento(numero)
        except ValueError as exc:
            messagebox.showerror("Documento", str(exc))
            return

        self.btn_validar.config(state="disabled")
        self.lbl_estado.config(text="Estado: validando...")
        threading.Thread(
            target=self._validar_en_hilo, args=(lat, lon, tipo, numero), daemon=True
        ).start()

    def _validar_en_hilo(self, lat, lon, tipo, numero):
        try:
            resultado = api.obtener_cliente().validar(lat, lon, tipo, numero)
        except NotImplementedError:
            self.after(
                0,
                lambda: self._fin_validar("Estado: el nucleo aun no esta listo (Fase 1: captura)"),
            )
            return
        except Exception as exc:
            msg = str(exc)
            self.after(0, lambda m=msg: messagebox.showerror("Error", m))
            self.after(0, lambda: self._fin_validar("Estado: error en la validacion"))
            return
        self.after(0, lambda: self._mostrar_resultado(resultado))

    def _mostrar_resultado(self, resultado):
        cobertura = resultado["cobertura"]
        self.lbl_cobertura.config(
            text=f"Cobertura: {'SI' if cobertura['hay_cobertura'] else 'NO'}"
        )
        score = resultado.get("score")
        if score:
            texto_score = f"Score: {score.get('valor', '?')} - "
            texto_score += "VALIDO" if score.get("valido") else "NO VALIDO"
            self.lbl_score.config(text=texto_score)
        else:
            self.lbl_score.config(text="Score: — (sin cobertura)")
        self._fin_validar("Estado: listo")

    def _fin_validar(self, estado):
        self.btn_validar.config(state="normal")
        self.lbl_estado.config(text=estado)

    def _buscar_actualizacion(self):
        self.btn_update.config(state="disabled")
        threading.Thread(target=self._buscar_update_hilo, daemon=True).start()

    def _buscar_update_hilo(self):
        info = update_check.hay_actualizacion()
        self.after(0, lambda: self._mostrar_update(info))

    def _mostrar_update(self, info):
        self.btn_update.config(state="normal")
        if info is None:
            self.lbl_estado.config(text="Estado: sin actualizaciones disponibles")
            return
        notas = (info.get("notes", "") or "")[:400]
        texto = f"Nueva version {info['tag']}\n\n{notas}\n\n¿Descargar e instalar?"
        resp = messagebox.askyesno("Actualizacion disponible", texto)
        if resp:
            self.lbl_estado.config(text="Estado: descargando actualizacion...")
            threading.Thread(target=self._aplicar_update_hilo, args=(info,), daemon=True).start()

    def _aplicar_update_hilo(self, info):
        try:
            download.aplicar_actualizacion(info)
        except Exception as exc:
            msg = str(exc)
            self.after(0, lambda m=msg: messagebox.showerror("Actualizacion", m))
            self.after(0, lambda: self.lbl_estado.config(text="Estado: error al actualizar"))
            return
        self.after(0, lambda: self.lbl_estado.config(text="Estado: reinicia la app para completar"))


def main():
    app = App()
    app.mainloop()
    return 0
