"""Pagina "Mapa": capas de cobertura, fraude y reglas de venta sobre OpenStreetMap."""

import contextlib
import threading
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from validator_app.core import api, geo
from validator_app.gui import fields, zonas

CENTRO_LIMA = (-12.0464, -77.0428)
RADIO_DIBUJO_M = 2000
MAX_POLIGONOS_CERCANOS = 600
# Rellenos punteados (el lienzo de Tk no tiene transparencia); Preferente 2 cubre
# casi toda la ciudad y se aclara para no tapar las demas capas ni el mapa base.
RELLENO_NORMAL = "gray25"
RELLENO_TENUE = "gray12"

# Orden de dibujo: la ultima capa queda encima. Zona F va al final: sus poligonos son
# identicos a los de Fraude y asi se ven (en morado) sobre los rojos.
CAPAS_VISUALES = (
    (geo.CAPA_COBERTURA, "Cobertura", "#2E9E4F"),
    (geo.CAPA_PREFERENTE, "Preferente 2 (score 401+)", "#1971C2"),
    (geo.CAPA_BLOQUEADOS, "Codigos bloqueados", "#7B1E3A"),
    (geo.CAPA_FRAUDE, "Fraude", "#E03131"),
    (geo.CAPA_ZONA_F, "Zona F (por confirmar)", "#9C36B5"),
)
# Pocas y de tamano chico: al marcarlas se dibujan TODAS, esten donde esten. Cobertura
# (3.361) y Preferente 2 (casi toda Lima) solo se dibujan cerca del punto o de la vista.
CAPAS_COMPLETAS = frozenset({geo.CAPA_FRAUDE, geo.CAPA_BLOQUEADOS, geo.CAPA_ZONA_F})
ANCHO_LATERAL = 300


class MapaPage(ttk.Frame):
    def __init__(self, master, obtener_cliente, obtener_capas, clasificar_score, a_dict):
        """`obtener_capas` puede bloquearse esperando la carga: solo se llama en hilos."""
        super().__init__(master, padding=8)
        self._obtener_cliente = obtener_cliente
        self._obtener_capas = obtener_capas
        self._clasificar_score = clasificar_score
        self._a_dict = a_dict
        self.mapa = None
        self._capas: dict = {}
        self._ultimo: dict | None = None
        self._centro_dibujo: tuple | None = None
        self._construir()

    def _construir(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        barra = ttk.Frame(self)
        barra.grid(row=0, column=0, sticky="we", pady=(0, 6))
        ttk.Label(barra, text="Coordenadas:").pack(side="left")
        self.txt_coordenadas = ttk.Entry(barra, width=34)
        self.txt_coordenadas.pack(side="left", padx=(4, 12))
        ttk.Label(barra, text="Documento (opcional):").pack(side="left")
        self.txt_documento = ttk.Entry(barra, width=14)
        self.txt_documento.pack(side="left", padx=(4, 12))
        self.btn_zona = ttk.Button(
            barra, text="VALIDAR ZONA", command=self._validar_zona, bootstyle="primary"
        )
        self.btn_zona.pack(side="left")
        for entrada in (self.txt_coordenadas, self.txt_documento):
            entrada.bind("<Return>", lambda _e: self._validar_zona())

        cuerpo = ttk.Frame(self)
        cuerpo.grid(row=1, column=0, sticky="nsew")
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        self._contenedor_mapa = ttk.Frame(cuerpo)
        self._contenedor_mapa.grid(row=0, column=0, sticky="nsew")

        lateral = ttk.Frame(cuerpo, width=ANCHO_LATERAL)
        lateral.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        lateral.grid_propagate(False)
        ajuste = ANCHO_LATERAL - 30

        marco_zona = ttk.LabelFrame(lateral, text="Zona", padding=8, bootstyle="info")
        marco_zona.pack(fill="x")
        self.lbl_zona = ttk.Label(
            marco_zona, text="Ingresa coordenadas o haz clic derecho en el mapa.",
            wraplength=ajuste, justify="left",
        )
        self.lbl_zona.pack(anchor="w")

        marco_score = ttk.LabelFrame(lateral, text="Score", padding=8, bootstyle="info")
        marco_score.pack(fill="x", pady=(8, 0))
        self.lbl_score = ttk.Label(marco_score, text="—", wraplength=ajuste, justify="left")
        self.lbl_score.pack(anchor="w")
        self.lbl_veredicto = ttk.Label(marco_score, text="", wraplength=ajuste, justify="left")
        self.lbl_veredicto.pack(anchor="w")
        self.btn_score = ttk.Button(
            marco_score, text="CONSULTAR SCORE", command=self._consultar_score,
            bootstyle="success", state="disabled",
        )
        self.btn_score.pack(fill="x", pady=(6, 0))

        marco_capas = ttk.LabelFrame(
            lateral, text="Capas (solo mostrar u ocultar)", padding=8, bootstyle="info"
        )
        marco_capas.pack(fill="x", pady=(8, 0))
        self._visibles: dict[str, tk.BooleanVar] = {}
        for capa, etiqueta, color in CAPAS_VISUALES:
            var = tk.BooleanVar(value=True)
            self._visibles[capa] = var
            tk.Checkbutton(
                marco_capas, text=etiqueta, variable=var, fg=color, anchor="w",
                command=self._pintar_capas, activeforeground=color,
            ).pack(fill="x")
        ttk.Button(
            marco_capas, text="Dibujar capas en esta vista", command=self._capas_en_vista,
            bootstyle="secondary-outline",
        ).pack(fill="x", pady=(6, 0))

        self.lbl_info = ttk.Label(
            lateral, text="", wraplength=ajuste, justify="left", foreground="gray"
        )
        self.lbl_info.pack(anchor="w", pady=(8, 0))

    def al_mostrar(self) -> None:
        """Crea el mapa la primera vez que se abre la pagina (evita bajar tiles al arrancar)."""
        if self.mapa is not None:
            return
        try:
            from tkintermapview import TkinterMapView
        except ImportError:
            ttk.Label(
                self._contenedor_mapa, text="Mapa no disponible (falta tkintermapview)."
            ).pack()
            return
        self.mapa = TkinterMapView(self._contenedor_mapa, corner_radius=0)
        self.mapa.pack(fill="both", expand=True)
        self.mapa.set_position(*CENTRO_LIMA)
        self.mapa.set_zoom(12)
        self.mapa.add_right_click_menu_command(
            "Validar esta ubicacion", self._desde_mapa, pass_coords=True
        )
        threading.Thread(target=self._cargar_capas_en_hilo, daemon=True).start()

    def _cargar_capas_en_hilo(self) -> None:
        capas = self._obtener_capas()
        self.after(0, lambda: self._capas_listas(capas))

    def _capas_listas(self, capas: dict) -> None:
        self._capas = capas
        self._pintar_capas()

    def _desde_mapa(self, coords) -> None:
        self.txt_coordenadas.delete(0, tk.END)
        self.txt_coordenadas.insert(0, f"{coords[0]:.6f}, {coords[1]:.6f}")
        self._validar_zona()

    def _validar_zona(self) -> None:
        if self.mapa is None or self.btn_zona.instate(["disabled"]):
            return
        try:
            lat, lon = fields.parse_coordenadas(self.txt_coordenadas.get().strip())
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
        self.btn_zona.config(state="disabled")
        self.btn_score.config(state="disabled")
        self.lbl_zona.config(text="Validando cobertura...", bootstyle="default")
        threading.Thread(
            target=self._validar_en_hilo, args=(lat, lon, tipo, numero), daemon=True
        ).start()

    def _validar_en_hilo(self, lat, lon, tipo, numero) -> None:
        # Las capas son locales y siempre se esperan: la decision nunca se toma sin ellas.
        capas = self._obtener_capas()
        cobertura = error = None
        # Solo la cobertura en vivo depende de WinForce; si falla se decide con lo local.
        try:
            cliente = self._obtener_cliente()
            if cliente is None:
                raise api.SessionError(
                    "No hay sesion configurada. Menu Configuracion → Configurar Proxy "
                    "o Sesion (standalone).",
                    "ERR_SESSION",
                )
            cobertura = self._a_dict(cliente.validar_cobertura(lat, lon))
        except Exception as exc:
            error = zonas.motivo_cobertura(exc)
        hay = None if cobertura is None else cobertura["hay_cobertura"]
        decision = geo.decidir_venta(lat, lon, hay, capas)
        self.after(
            0, lambda: self._mostrar_zona(lat, lon, cobertura, error, decision, capas, tipo, numero)
        )

    def _mostrar_zona(self, lat, lon, cobertura, error, decision, capas, tipo, numero) -> None:
        self._capas = capas
        texto, estilo = zonas.resumen_decision(decision)
        if error:
            texto = f"{zonas.mensaje_sin_cobertura(error, decision)}\n\n{texto}"
        self.lbl_zona.config(text=texto, bootstyle=estilo)
        self._ultimo = {
            "lat": lat, "lon": lon, "cobertura": cobertura, "decision": decision,
            "tipo": tipo, "numero": numero,
        }
        self.lbl_veredicto.config(text="")
        plan = zonas.plan_score(decision)
        if error:
            self.lbl_score.config(text="Score no disponible: no se pudo confirmar la cobertura.")
            self.btn_score.config(state="disabled")
        elif tipo is None:
            self.lbl_score.config(text="Ingresa un documento para consultar el score.")
            self.btn_score.config(state="disabled")
        elif plan == "no":
            self.lbl_score.config(text="Score no disponible en esta zona (no se consulta).")
            self.btn_score.config(state="disabled")
        else:
            self.lbl_score.config(text="Listo para consultar el score.")
            self.btn_score.config(state="normal")

        self.mapa.delete_all_marker()
        self.mapa.set_position(lat, lon)
        self.mapa.set_zoom(16)
        self.mapa.set_marker(lat, lon, text="Cliente")
        self._centro_dibujo = (lat, lon)
        self._pintar_capas()
        self.btn_zona.config(state="normal")

    def _pintar_capas(self) -> None:
        """Dibuja u oculta capas. Es SOLO visual: la decision usa siempre todas las capas."""
        if self.mapa is None:
            return
        self.mapa.delete_all_polygon()
        marcadas = {capa for capa, var in self._visibles.items() if var.get()}
        a_dibujar = geo.capas_visibles(self._capas, marcadas)
        cercanos = {}
        if self._centro_dibujo is not None:
            lat, lon = self._centro_dibujo
            proximas = {c: p for c, p in a_dibujar.items() if c not in CAPAS_COMPLETAS}
            cercanos = geo.poligonos_cercanos(proximas, lat, lon, RADIO_DIBUJO_M)
        completas = cerca = 0
        for capa, etiqueta, color in CAPAS_VISUALES:
            es_completa = capa in CAPAS_COMPLETAS
            polis = a_dibujar.get(capa, ()) if es_completa else cercanos.get(capa, ())
            for poli in polis:
                if not es_completa and cerca >= MAX_POLIGONOS_CERCANOS:
                    break
                self._dibujar_poligono(poli, capa, etiqueta, color)
                if es_completa:
                    completas += 1
                else:
                    cerca += 1
        if self._ultimo:
            self.mapa.set_polygon(
                geo.circulo(self._ultimo["lat"], self._ultimo["lon"], geo.RADIO_EXTENSION_M),
                fill_color=None, outline_color="#111111", border_width=2, name="Radio 300 m",
            )
        self.lbl_info.config(
            text=f"{completas} zonas de capas completas y {cerca} a menos de 2 km del punto. "
            "Clic en una zona para ver su nombre."
        )

    def _dibujar_poligono(self, poli, capa: str, etiqueta: str, color: str) -> None:
        nombre = f"{etiqueta}: {poli.nombre}" if poli.nombre else etiqueta
        figura = self.mapa.set_polygon(
            list(poli.anillo), fill_color=color, outline_color=color, border_width=2,
            name=nombre, command=self._clic_poligono,
        )
        lienzo = getattr(figura, "canvas_polygon", None)
        if lienzo is not None:
            relleno = RELLENO_TENUE if capa == geo.CAPA_PREFERENTE else RELLENO_NORMAL
            with contextlib.suppress(tk.TclError):
                self.mapa.canvas.itemconfig(lienzo, stipple=relleno)

    def _clic_poligono(self, poligono) -> None:
        self.lbl_info.config(text=f"Zona: {poligono.name}")

    def _capas_en_vista(self) -> None:
        if self.mapa is None:
            return
        self._centro_dibujo = tuple(self.mapa.get_position())
        self._pintar_capas()

    def _consultar_score(self) -> None:
        u = self._ultimo
        if not u or u["tipo"] is None or u["cobertura"] is None:
            return
        decision = u["decision"]
        if zonas.plan_score(decision) == "confirmar" and not messagebox.askyesno(
            "Consultar score",
            f"{decision.mensaje}\n\nEl score gasta una consulta de Equifax. "
            "¿Consultarlo de todas formas?",
        ):
            return
        self.btn_score.config(state="disabled")
        self.lbl_score.config(text="Consultando score...")
        threading.Thread(target=self._score_en_hilo, args=(u,), daemon=True).start()

    def _score_en_hilo(self, u: dict) -> None:
        try:
            cliente = self._obtener_cliente()
            score = self._a_dict(
                cliente.validar_score(
                    u["tipo"], u["numero"], u["lat"], u["lon"], u["cobertura"]["cobertura"]
                )
            )
        except Exception as exc:
            mensaje = str(exc)
            self.after(0, lambda: self._error_score(mensaje))
            return
        self.after(0, lambda: self._mostrar_score(score, u["decision"]))

    def _error_score(self, mensaje: str) -> None:
        self.lbl_score.config(text="No se pudo consultar el score.")
        self.btn_score.config(state="normal")
        messagebox.showerror("Error", mensaje)

    def _mostrar_score(self, score: dict, decision: geo.Decision) -> None:
        valor = score.get("valor")
        clase = self._clasificar_score(valor)
        if clase:
            self.lbl_score.config(
                text=f"Score: {valor} — Riesgo {clase['riesgo']} ({clase['categoria']})\n"
                f"{clase['rango']}",
                foreground=clase["color"],
            )
        else:
            self.lbl_score.config(text="Score: — (puntaje no disponible)", foreground="")
        veredicto = zonas.veredicto_score(valor if clase else None, decision.score_minimo)
        if veredicto:
            texto, alcanza = veredicto
            self.lbl_veredicto.config(text=texto, foreground="#2B8A3E" if alcanza else "#C8102E")
        else:
            self.lbl_veredicto.config(text="")
        self.btn_score.config(state="normal")
