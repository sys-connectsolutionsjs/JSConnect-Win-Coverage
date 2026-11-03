"""Tarjetas del resultado y dialogo "Ver detalle", compartidos por la pagina
principal y la pagina Mapa (los textos salen de gui/zonas.py)."""

import tkinter as tk

import ttkbootstrap as ttk

from validator_app.gui import zonas


class Tarjeta(ttk.LabelFrame):
    """Marco del color del estado con un titulo en negrita y una nota corta,
    centrados de arriba abajo (si la tarjeta vecina es mas alta, quedan a media
    altura). Debajo del texto se pueden empaquetar mas widgets en `cuerpo`."""

    def __init__(self, parent, nombre: str, tamano_titulo: int = 12, ancho_texto: int = 260):
        super().__init__(parent, text=nombre, padding=8, bootstyle="secondary")
        self.cuerpo = ttk.Frame(self)
        self.cuerpo.pack(expand=True, fill="x")
        self._titulo = ttk.Label(
            self.cuerpo, text=zonas.SIN_DATO, font=("", tamano_titulo, "bold"),
            wraplength=ancho_texto, justify="left",
        )
        self._titulo.pack(anchor="w")
        self._nota = ttk.Label(self.cuerpo, text="", justify="left", wraplength=ancho_texto)
        self._nota.pack(anchor="w")

    def pintar(self, tarjeta: tuple) -> None:
        titulo, nota, estilo = tarjeta
        self.config(bootstyle=estilo)
        self._titulo.config(text=titulo, bootstyle=estilo)
        self._nota.config(text=nota)
        if nota:
            self._nota.pack(anchor="w")
        else:
            self._nota.pack_forget()


def mostrar_detalle(parent, texto: str) -> None:
    """Todos los datos y el error exacto, para copiarlos y mandarlos por WhatsApp."""
    if not texto:
        return
    dialog = tk.Toplevel(parent)
    dialog.title("Detalle de la validacion")
    dialog.geometry("620x360")
    dialog.transient(parent)
    frame = ttk.Frame(dialog, padding=12)
    frame.pack(fill="both", expand=True)
    caja = tk.Text(frame, wrap="word", height=14)
    caja.insert("1.0", texto)
    caja.config(state="disabled")
    caja.pack(fill="both", expand=True)

    def copiar():
        parent.clipboard_clear()
        parent.clipboard_append(texto)
        parent.update()
        boton.config(text="✓ Copiado")
        dialog.after(1500, lambda: boton.config(text="\U0001f4cb Copiar para WhatsApp"))

    boton = ttk.Button(
        frame, text="\U0001f4cb Copiar para WhatsApp", command=copiar, bootstyle="success"
    )
    boton.pack(fill="x", pady=(8, 0))
