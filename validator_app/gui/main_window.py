"""Ventana principal de la aplicacion."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from validator_app.activation import fingerprint, signer
from validator_app.activation import state as activation_state
from validator_app.core import api
from validator_app.gui import fields
from validator_app.proxy.client import ProxyClient
from validator_app.updater import check as update_check
from validator_app.updater import download


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JSConnect Win Coverage")
        self.geometry("540x580")
        self.resizable(False, False)
        self._proxy_client: ProxyClient | None = None
        self._build_ui()
        self._load_proxy_config()
        self.after(200, self._inicio)

    def _build_ui(self):
        # Menu bar
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        menu_config = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="\u2699 Configuraci\u00f3n", menu=menu_config)
        menu_config.add_command(label="Configurar Proxy", command=self._abrir_config_proxy)
        menu_config.add_separator()
        menu_config.add_command(label="Buscar actualizaciones", command=self._buscar_actualizacion)

        main = ttk.Frame(self, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Coordenadas (latitud, longitud):").grid(row=0, column=0, sticky="w")
        self.txt_coordenadas = ttk.Entry(main, width=52)
        self.txt_coordenadas.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 8))

        ttk.Label(main, text="Documento (DNI/RUC/CE):").grid(row=2, column=0, sticky="w")
        self.txt_documento = ttk.Entry(main, width=32)
        self.txt_documento.grid(row=3, column=0, sticky="we", pady=(2, 2))
        self.lbl_tipo = ttk.Label(main, text="Tipo: \u2014")
        self.lbl_tipo.grid(row=3, column=1, sticky="w", padx=(8, 0))
        self.txt_documento.bind("<KeyRelease>", self._on_documento_cambio)

        self.btn_validar = ttk.Button(main, text="VALIDAR", command=self._validar)
        self.btn_validar.grid(row=4, column=0, columnspan=2, pady=10, sticky="we")

        frame_res = ttk.LabelFrame(main, text="Resultado", padding=10)
        frame_res.grid(row=5, column=0, columnspan=2, sticky="we")
        self.lbl_cobertura = ttk.Label(frame_res, text="Cobertura: \u2014")
        self.lbl_cobertura.pack(anchor="w")
        self.lbl_score = ttk.Label(frame_res, text="Score: \u2014")
        self.lbl_score.pack(anchor="w")

        self.lbl_estado = ttk.Label(main, text="Estado: iniciando...", anchor="w")
        self.lbl_estado.grid(row=6, column=0, columnspan=2, sticky="we", pady=(10, 0))

    def _load_proxy_config(self) -> None:
        """Carga configuracion de proxy desde keyring si existe."""
        try:
            self._proxy_client = ProxyClient.from_keyring()
            if self._proxy_client:
                self.lbl_estado.config(text=f"Estado: listo (proxy: {self._proxy_client.base_url})")
            else:
                self.lbl_estado.config(text="Estado: listo (modo standalone)")
        except Exception:
            self._proxy_client = None
            self.lbl_estado.config(text="Estado: listo (modo standalone)")

    def _inicio(self):
        self._verificar_activacion()

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
            self.lbl_tipo.config(text="Tipo: \u2014")

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
            if self._proxy_client:
                # Modo proxy
                cobertura = self._proxy_client.validar_cobertura(lat, lon)
                score = None
                if cobertura.hay_cobertura:
                    score = self._proxy_client.validar_score(
                        tipo, numero, lat, lon, cobertura.cobertura
                    )
                resultado = {
                    "cobertura": cobertura.__dict__,
                    "score": score.__dict__ if score else None,
                }
            else:
                # Modo standalone (core directo)
                resultado = api.obtener_cliente().validar(lat, lon, tipo, numero)
        except NotImplementedError:
            self.after(
                0,
                lambda: self._fin_validar("Estado: el nucleo aun no esta listo"),
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
            self.lbl_score.config(text="Score: \u2014 (sin cobertura)")
        self._fin_validar("Estado: listo")

    def _fin_validar(self, estado):
        self.btn_validar.config(state="normal")
        self.lbl_estado.config(text=estado)

    def _abrir_config_proxy(self):
        """Dialogo modal para configurar proxy."""
        dialog = tk.Toplevel(self)
        dialog.title("Configurar Proxy")
        dialog.geometry("440x320")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)

        # IP:puerto
        ttk.Label(frame, text="IP:puerto del proxy:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.txt_proxy_url = ttk.Entry(frame, width=40)
        self.txt_proxy_url.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 12))
        if self._proxy_client:
            self.txt_proxy_url.insert(0, self._proxy_client.base_url)

        # Token
        lbl_token = ttk.Label(frame, text="Token (X-Proxy-Token):")
        lbl_token.grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.txt_proxy_token = ttk.Entry(frame, width=40, show="\u2022")
        self.txt_proxy_token.grid(row=3, column=0, columnspan=2, sticky="we", pady=(0, 12))
        if self._proxy_client:
            self.txt_proxy_token.insert(0, self._proxy_client.token)

        # Boton mostrar/ocultar token
        self._show_token = tk.BooleanVar(value=False)

        def toggle_token():
            self.txt_proxy_token.config(show="" if self._show_token.get() else "\u2022")

        ttk.Checkbutton(
            frame,
            text="Mostrar token",
            variable=self._show_token,
            command=toggle_token,
        ).grid(row=4, column=0, sticky="w", pady=(0, 12))

        # Boton probar conexion
        self.btn_test = ttk.Button(
            frame,
            text="Probar conexi\u00f3n",
            command=lambda: self._test_proxy_connection(dialog),
        )
        self.btn_test.grid(row=5, column=0, sticky="we", pady=(0, 8))

        # Label resultado test
        self.lbl_test_result = ttk.Label(frame, text="", anchor="w")
        self.lbl_test_result.grid(row=6, column=0, columnspan=2, sticky="we", pady=(0, 12))

        # Botones guardar/cancelar
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky="e")
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            btn_frame, text="Guardar", command=lambda: self._save_proxy_config(dialog)
        ).pack(side="right")

        frame.columnconfigure(0, weight=1)

    def _test_proxy_connection(self, dialog: tk.Toplevel) -> None:
        """Prueba conexion al proxy en hilo separado."""
        url = self.txt_proxy_url.get().strip()
        token = self.txt_proxy_token.get().strip()
        if not url or not token:
            self.lbl_test_result.config(text="Completa IP:puerto y token", foreground="red")
            return

        self.btn_test.config(state="disabled")
        self.lbl_test_result.config(text="Probando...", foreground="gray")

        def do_test():
            try:
                client = ProxyClient(base_url=url, token=token, timeout=10.0)
                health = client.health_check()
                client.close()
                if health.status == "ok" and health.logged_in:
                    msg = f"OK ({health.session_age}s, logged_in)"
                    self.after(0, lambda: self._on_test_result(True, msg))
                elif health.status == "ok":
                    msg = "OK (proxy vivo, sesion WinForce inactiva)"
                    self.after(0, lambda: self._on_test_result(True, msg))
                else:
                    msg = f"Status: {health.status}"
                    self.after(0, lambda: self._on_test_result(False, msg))
            except Exception:
                self.after(0, lambda: self._on_test_result(False, "Error de conexion"))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_test_result(self, success: bool, msg: str):
        self.btn_test.config(state="normal")
        if success:
            self.lbl_test_result.config(text=f"\u2713 {msg}", foreground="green")
        else:
            self.lbl_test_result.config(text=f"\u2717 {msg}", foreground="red")

    def _save_proxy_config(self, dialog: tk.Toplevel) -> None:
        """Guarda configuracion de proxy en keyring y recarga cliente."""
        url = self.txt_proxy_url.get().strip()
        token = self.txt_proxy_token.get().strip()
        if not url or not token:
            messagebox.showerror("Error", "IP:puerto y token son obligatorios", parent=dialog)
            return

        # Validar formato URL
        if not (url.startswith("http://") or url.startswith("https://")):
            messagebox.showerror(
                "Error", "La URL debe empezar con http:// o https://", parent=dialog
            )
            return

        try:
            # Probar antes de guardar
            client = ProxyClient(base_url=url, token=token, timeout=10.0)
            health = client.health_check()
            client.close()
            if health.status != "ok":
                msg = f"Proxy respondio status '{health.status}'.\n¿Guardar de todas formas?"
                if not messagebox.askyesno("Advertencia", msg, parent=dialog):
                    return
        except Exception as exc:
            msg = f"No se pudo conectar al proxy:\n{exc}\n\n¿Guardar de todas formas?"
            if not messagebox.askyesno("Error", msg, parent=dialog):
                return

        # Guardar en keyring
        client = ProxyClient(base_url=url, token=token)
        client.save_to_keyring()

        # Recargar cliente en memoria
        self._proxy_client = ProxyClient.from_keyring()
        self.lbl_estado.config(text=f"Estado: listo (proxy: {self._proxy_client.base_url})")
        dialog.destroy()
        messagebox.showinfo("Guardado", "Configuracion de proxy guardada correctamente.")

    def _buscar_actualizacion(self):
        # Reutilizar el boton del menu (ya no hay boton en la UI principal)
        threading.Thread(target=self._buscar_update_hilo, daemon=True).start()

    def _buscar_update_hilo(self):
        info = update_check.hay_actualizacion()
        self.after(0, lambda: self._mostrar_update(info))

    def _mostrar_update(self, info):
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
