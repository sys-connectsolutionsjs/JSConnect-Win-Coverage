"""Ventana principal de la aplicacion."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from validator_app.activation import fingerprint, signer
from validator_app.activation import state as activation_state
from validator_app.core import api
from validator_app.gui import fields, session_config
from validator_app.proxy.client import ProxyClient, ProxySesionCaducadaError
from validator_app.updater import check as update_check
from validator_app.updater import download


def _a_dict(objeto):
    """Normaliza el resultado de validar_cobertura/validar_score: ProxyClient
    devuelve dataclasses (CoberturaResult/ScoreResult), el core standalone
    devuelve dicts planos. El resto del codigo siempre trabaja con dicts."""
    return objeto.__dict__ if hasattr(objeto, "__dict__") else objeto


def activacion_vigente(huella: str) -> bool:
    """True si esta PC tiene guardado un codigo de activacion valido para su huella."""
    guardado = activation_state.leer()
    return bool(
        guardado
        and guardado.get("huella") == huella
        and signer.validar_codigo(huella, guardado.get("codigo", ""))
    )


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JSConnect Win Coverage")
        self.geometry("540x580")
        self.resizable(False, False)
        self._proxy_client: ProxyClient | None = None
        self._session_client: api.ValidatorAPI | None = None
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
        menu_config.add_command(
            label="Configurar Sesión (standalone)", command=self._abrir_config_sesion
        )
        menu_config.add_separator()
        menu_config.add_command(
            label="Activación / Huella de la PC", command=self._abrir_activacion
        )
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
        """Carga la config de proxy (o la sesion standalone) desde keyring."""
        try:
            self._proxy_client = ProxyClient.from_keyring()
        except Exception:
            self._proxy_client = None
        if self._proxy_client:
            self.lbl_estado.config(text=f"Estado: listo (proxy: {self._proxy_client.base_url})")
            return
        try:
            self._session_client = session_config.cliente_standalone()
        except Exception:
            self._session_client = None
        self._actualizar_estado_standalone()

    def _actualizar_estado_standalone(self) -> None:
        if self._session_client is not None:
            self.lbl_estado.config(text="Estado: listo (standalone, sesion configurada)")
        else:
            self.lbl_estado.config(
                text="Estado: standalone SIN sesion — menu ⚙ → Configurar Sesion"
            )

    def _inicio(self):
        self._verificar_activacion()

    def _verificar_activacion(self):
        if not signer.activacion_disponible():
            self.lbl_estado.config(text="Estado: modo desarrollo (activacion pendiente)")
            return
        huella = fingerprint.obtener_huella()
        if activacion_vigente(huella):
            return
        self._mostrar_activacion(huella)

    def _abrir_activacion(self):
        """Menu: muestra la huella de esta PC y permite (re)activarla en cualquier momento."""
        self._mostrar_activacion(fingerprint.obtener_huella(), requerida=False)

    def _mostrar_activacion(self, huella, requerida=True):
        dialog = tk.Toplevel(self)
        dialog.title("Activacion requerida" if requerida else "Activacion de esta PC")
        dialog.geometry("460x310")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        if not requerida:
            estado = "ACTIVADA" if activacion_vigente(huella) else "PENDIENTE de activar"
            ttk.Label(frame, text=f"Estado de esta PC: {estado}", font=("", 10, "bold")).pack(
                anchor="w", pady=(0, 8)
            )
        ttk.Label(frame, text="Huella de esta computadora:").pack(anchor="w")
        frame_huella = ttk.Frame(frame)
        frame_huella.pack(fill="x", pady=(2, 8))
        ttk.Label(frame_huella, text=huella, font=("Consolas", 11, "bold")).pack(
            side="left"
        )

        def copiar_huella():
            self.clipboard_clear()
            self.clipboard_append(huella)
            self.update()

        ttk.Button(frame_huella, text="Copiar huella", command=copiar_huella).pack(
            side="right"
        )
        ttk.Label(frame, text="Enviala al encargado e ingresa el codigo de activacion:").pack(
            anchor="w"
        )
        txt_codigo = ttk.Entry(frame, width=36, font=("Consolas", 10))
        txt_codigo.pack(fill="x", pady=(4, 10))

        def pegar_codigo():
            try:
                codigo = self.clipboard_get().strip()
            except tk.TclError:
                codigo = ""
            txt_codigo.delete(0, tk.END)
            txt_codigo.insert(0, codigo)

        def activar():
            codigo = txt_codigo.get().strip()
            valido, mensaje = signer.verificar_codigo(huella, codigo)
            if valido:
                activation_state.guardar(huella, codigo)
                dialog.destroy()
                self.lbl_estado.config(text="Estado: activado")
            else:
                messagebox.showerror(
                    "Activacion", mensaje, parent=dialog
                )

        botones = ttk.Frame(frame)
        botones.pack()
        ttk.Button(botones, text="Pegar codigo", command=pegar_codigo).pack(side="left")
        ttk.Button(botones, text="ACTIVAR", command=activar).pack(side="left", padx=(8, 0))
        if requerida:
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
        texto_coords = self.txt_coordenadas.get().strip()
        lat = lon = None
        if texto_coords:
            try:
                lat, lon = fields.parse_coordenadas(texto_coords)
            except ValueError as exc:
                messagebox.showerror("Coordenadas", str(exc))
                return

        numero = self.txt_documento.get().strip()
        tipo = None
        if numero:
            try:
                tipo = fields.detectar_tipo_documento(numero)
            except ValueError as exc:
                messagebox.showerror("Documento", str(exc))
                return

        if lat is None and tipo is None:
            messagebox.showerror("Validar", "Ingresa coordenadas y/o un documento.")
            return

        self.btn_validar.config(state="disabled")
        self.lbl_estado.config(text="Estado: validando...")
        threading.Thread(
            target=self._validar_en_hilo, args=(lat, lon, tipo, numero), daemon=True
        ).start()

    def _validar_en_hilo(self, lat, lon, tipo, numero):
        try:
            if self._proxy_client:
                cliente = self._proxy_client
            elif self._session_client is not None:
                cliente = self._session_client
            else:
                raise api.SessionError(
                    "No hay sesion configurada. Menu ⚙ Configuracion → "
                    "Configurar Sesion (standalone).",
                    "ERR_SESSION",
                )
            # ProxyClient y ValidatorAPI (standalone) exponen el mismo shape de
            # llamada para cobertura/score, asi que la logica de abajo sirve
            # para ambos sin ramas extra. Difieren en el TIPO de retorno
            # (dataclass vs dict plano): _a_dict() lo normaliza antes de leerlo.
            cobertura = None
            if lat is not None:
                cobertura = _a_dict(cliente.validar_cobertura(lat, lon))
            score = None
            if tipo is not None:
                if cobertura is not None:
                    # Ambos datos: mismo criterio de siempre, solo pide score
                    # si hay cobertura.
                    if cobertura["hay_cobertura"]:
                        score = _a_dict(
                            cliente.validar_score(tipo, numero, lat, lon, cobertura["cobertura"])
                        )
                else:
                    # Solo documento (sin coordenadas): score directo, sin
                    # cobertura que reportar.
                    score = _a_dict(
                        cliente.validar_score(tipo, numero, None, None, cobertura="NO")
                    )
            resultado = {
                "cobertura": cobertura,
                "score": score,
                "se_pidio_documento": tipo is not None,
            }
        except NotImplementedError:
            self.after(
                0,
                lambda: self._fin_validar("Estado: el nucleo aun no esta listo"),
            )
            return
        except ProxySesionCaducadaError:
            # No es un error del agente: la sesion del proxy con WinForce caduco y
            # el owner ya fue avisado. Mensaje suave, no el dialogo rojo.
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Sesion del proxy caducada",
                    "La sesion del proxy con WinForce caduco.\n\n"
                    "El administrador ya fue notificado. Vuelve a intentarlo en "
                    "2-3 minutos.",
                ),
            )
            self.after(
                0,
                lambda: self._fin_validar(
                    "Estado: sesion del proxy caducada - reintenta en unos minutos"
                ),
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
        if cobertura is None:
            self.lbl_cobertura.config(text="Cobertura: \u2014 (no se ingresaron coordenadas)")
        else:
            self.lbl_cobertura.config(
                text=f"Cobertura: {'SI' if cobertura['hay_cobertura'] else 'NO'}"
            )

        score = resultado.get("score")
        if score:
            texto_score = f"Score: {score.get('valor', '?')} - "
            texto_score += "VALIDO" if score.get("valido") else "NO VALIDO"
            self.lbl_score.config(text=texto_score)
        elif not resultado.get("se_pidio_documento"):
            self.lbl_score.config(text="Score: \u2014 (no se ingres\u00f3 documento)")
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
                if health.status != "ok":
                    self.after(0, lambda: self._on_test_result("mal", f"Status: {health.status}"))
                elif health.session_alive:
                    msg = f"OK (sesion WinForce viva, {health.session_age}s)"
                    self.after(0, lambda: self._on_test_result("ok", msg))
                elif health.logged_in:
                    msg = "proxy vivo, pero la sesion WinForce esta caida"
                    self.after(0, lambda: self._on_test_result("aviso", msg))
                else:
                    msg = "proxy vivo, sin sesion WinForce configurada"
                    self.after(0, lambda: self._on_test_result("aviso", msg))
            except Exception:
                self.after(0, lambda: self._on_test_result("mal", "Error de conexion"))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_test_result(self, estado: str, msg: str):
        self.btn_test.config(state="normal")
        marca = {"ok": "\u2713", "aviso": "\u26a0", "mal": "\u2717"}.get(estado, "\u2717")
        color = {"ok": "green", "aviso": "#b8860b", "mal": "red"}.get(estado, "red")
        self.lbl_test_result.config(text=f"{marca} {msg}", foreground=color)

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

    def _abrir_config_sesion(self) -> None:
        """Dialogo modal para pegar la cookie PHPSESSID (modo standalone)."""
        dialog = tk.Toplevel(self)
        dialog.title("Configurar Sesion (standalone)")
        dialog.geometry("460x260")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="Inicia sesion en appwinforce.win.pe en el navegador,\n"
            "copia la cookie PHPSESSID (F12 → Application → Cookies) y pegala aqui:",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.txt_sesion_cookie = ttk.Entry(frame, width=44, show="•")
        self.txt_sesion_cookie.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 4))
        if session_config.cargar_cookie():
            self.txt_sesion_cookie.insert(0, session_config.cargar_cookie())

        self._show_sesion = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Mostrar",
            variable=self._show_sesion,
            command=lambda: self.txt_sesion_cookie.config(
                show="" if self._show_sesion.get() else "•"
            ),
        ).grid(row=2, column=0, sticky="w", pady=(0, 10))

        self.lbl_sesion_result = ttk.Label(frame, text="", anchor="w")
        self.lbl_sesion_result.grid(row=3, column=0, columnspan=2, sticky="we", pady=(0, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, sticky="e")
        ttk.Button(btn_frame, text="Cerrar", command=dialog.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            btn_frame, text="Quitar sesion guardada",
            command=lambda: self._quitar_sesion(dialog),
        ).pack(side="right", padx=(8, 0))
        self.btn_sesion_test = ttk.Button(
            btn_frame, text="Probar y guardar",
            command=lambda: self._probar_y_guardar_sesion(dialog),
        )
        self.btn_sesion_test.pack(side="right")

    def _probar_y_guardar_sesion(self, dialog: tk.Toplevel) -> None:
        cookie = self.txt_sesion_cookie.get().strip()
        self.btn_sesion_test.config(state="disabled")
        self.lbl_sesion_result.config(text="Validando contra WinForce...", foreground="gray")

        def do_test():
            try:
                session_config.validar_y_guardar(cookie)
            except Exception as exc:
                msg = str(exc)
                self.after(0, lambda m=msg: self._on_sesion_result(False, m, dialog))
                return
            self.after(0, lambda: self._on_sesion_result(True, "", dialog))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_sesion_result(self, ok: bool, msg: str, dialog: tk.Toplevel) -> None:
        self.btn_sesion_test.config(state="normal")
        if ok:
            self._session_client = session_config.cliente_standalone()
            self._actualizar_estado_standalone()
            dialog.destroy()
            messagebox.showinfo("Sesion", "Sesion validada y guardada.")
        else:
            self.lbl_sesion_result.config(text=f"✗ {msg}", foreground="red")

    def _quitar_sesion(self, dialog: tk.Toplevel) -> None:
        session_config.borrar_cookie()
        self._session_client = None
        self._actualizar_estado_standalone()
        dialog.destroy()
        messagebox.showinfo("Sesion", "Sesion guardada eliminada.")

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
