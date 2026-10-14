"""Ficha del cliente (direccion + datos del documento) copiable dato por dato o completa."""

from __future__ import annotations

import ttkbootstrap as ttk

ETIQUETAS = (
    "APELLIDOS Y NOMBRES",
    "DOCUMENTO DE IDENTIDAD (DNI, RUC, CE)",
    "NACIONALIDAD Y FECHA DE NACIMIENTO",
    "SCORE",
    "DIRECCIÓN DETALLADA",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DISTRITO",
)
_PREFIJO_RANGO = "SCORE:"


def rango_sin_prefijo(rango: str | None) -> str | None:
    """'SCORE: 500 - 599' -> '500 - 599' (la etiqueta ya dice SCORE)."""
    if rango and rango.startswith(_PREFIJO_RANGO):
        return rango[len(_PREFIJO_RANGO):].strip()
    return rango


def _nombre_completo(score: dict, persona: dict) -> str:
    nombres, paterno = persona.get("nombres") or "", persona.get("apellido_paterno") or ""
    if nombres:
        if paterno and nombres.startswith(paterno):
            return nombres  # ya es el nombre completo (APELLIDOS NOMBRES)
        partes = (paterno, persona.get("apellido_materno"), nombres)
        return " ".join(p for p in partes if p)
    # Empresas (RUC 20): sin directorio de personas, la razon social.
    return persona.get("razon_social") or score.get("nombre") or ""


def armar_ficha(score, direccion, tipo, numero, rango) -> list[tuple[str, str]]:
    """[(etiqueta, valor)] en el orden de ETIQUETAS; lo desconocido va en blanco.

    La direccion sale SOLO de las coordenadas: sin ellas queda en blanco.
    """
    score = score or {}
    persona = score.get("persona") or {}
    direccion = direccion or {}
    documento = " ".join(p for p in (tipo, numero) if p)
    nacimiento = ", ".join(
        p for p in (persona.get("nacionalidad"), persona.get("fecha_nacimiento")) if p
    )
    valores = (
        _nombre_completo(score, persona),
        documento,
        nacimiento,
        rango_sin_prefijo(rango) or "",
        direccion.get("direccion") or "",
        direccion.get("departamento") or "",
        direccion.get("provincia") or "",
        direccion.get("distrito") or "",
    )
    return list(zip(ETIQUETAS, valores, strict=True))


def texto_copiar_todo(items) -> str:
    return "\n".join(f"{etiqueta}: {valor}".rstrip() for etiqueta, valor in items)


class FichaCliente(ttk.LabelFrame):
    """Una fila por dato con su boton de copiar y un boton 'Copiar todo'."""

    ANCHO_VALOR = 230

    def __init__(self, master, titulo: str = "Datos del cliente", **kwargs):
        super().__init__(master, text=titulo, padding=8, bootstyle="info", **kwargs)
        self._items: list[tuple[str, str]] = []
        self._valores: list[ttk.Label] = []
        self._botones: list[ttk.Button] = []
        self.lbl_aviso = ttk.Label(
            self, text="", wraplength=self.ANCHO_VALOR + 40, justify="left",
            foreground="#C8102E", font=("Segoe UI", 9, "bold"),
        )
        self.lbl_aviso.grid(row=0, column=0, columnspan=2, sticky="we")
        self.lbl_aviso.grid_remove()
        for fila, etiqueta in enumerate(ETIQUETAS):
            ttk.Label(self, text=etiqueta, font=("Segoe UI", 8, "bold")).grid(
                row=fila * 2 + 1, column=0, columnspan=2, sticky="w", pady=(4, 0)
            )
            valor = ttk.Label(self, text="—", wraplength=self.ANCHO_VALOR, justify="left")
            valor.grid(row=fila * 2 + 2, column=0, sticky="we")
            boton = ttk.Button(
                self, text="\U0001f4cb", width=3, bootstyle="secondary-outline",
                state="disabled", command=lambda i=fila: self._copiar(i),
            )
            boton.grid(row=fila * 2 + 2, column=1, sticky="e", padx=(6, 0))
            self._valores.append(valor)
            self._botones.append(boton)
        self.columnconfigure(0, weight=1)
        self.btn_todo = ttk.Button(
            self, text="\U0001f4cb Copiar todo", bootstyle="primary", state="disabled",
            command=self._copiar_todo,
        )
        self.btn_todo.grid(
            row=len(ETIQUETAS) * 2 + 1, column=0, columnspan=2, sticky="we", pady=(8, 0)
        )

    def mostrar(self, items, aviso: str | None = None) -> None:
        self._items = list(items)
        for i, (_etiqueta, valor) in enumerate(self._items):
            self._valores[i].config(text=valor or "—")
            self._botones[i].config(state="normal" if valor else "disabled")
        self.btn_todo.config(state="normal" if any(v for _e, v in self._items) else "disabled")
        self.lbl_aviso.config(text=aviso or "")
        if aviso:
            self.lbl_aviso.grid()
        else:
            self.lbl_aviso.grid_remove()

    def limpiar(self) -> None:
        self.mostrar([(e, "") for e in ETIQUETAS])

    def _poner_en_portapapeles(self, texto: str, boton: ttk.Button, original: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.update()
        boton.config(text="✓" if original == "\U0001f4cb" else "✓ Copiado")
        self.after(1500, lambda: boton.config(text=original))

    def _copiar(self, indice: int) -> None:
        if indice < len(self._items) and self._items[indice][1]:
            self._poner_en_portapapeles(self._items[indice][1], self._botones[indice], "\U0001f4cb")

    def _copiar_todo(self) -> None:
        if self._items:
            self._poner_en_portapapeles(
                texto_copiar_todo(self._items), self.btn_todo, "\U0001f4cb Copiar todo"
            )
