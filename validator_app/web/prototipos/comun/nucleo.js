(() => {
  "use strict";

  const JSC = (window.JSC = window.JSC || {});
  const hayDocumento = typeof document !== "undefined";

  // ---------------------------------------------------------------------------
  // Modelo (sin DOM): replica las reglas de la app en Python
  // ---------------------------------------------------------------------------

  JSC.clasificarScore = (valor) => {
    let puntaje;
    if (typeof valor === "number") {
      if (!Number.isInteger(valor)) return null;
      puntaje = valor;
    } else if (typeof valor === "string" && /^\s*[+-]?\d+\s*$/.test(valor)) {
      puntaje = parseInt(valor, 10);
    } else {
      return null;
    }
    if (puntaje < 0 || puntaje > 999) return null;
    const nivel = JSC.NIVELES.find((n) => puntaje <= n.tope);
    let inicio;
    let fin;
    if (puntaje <= 200) {
      inicio = 0;
      fin = 200;
    } else if (puntaje >= 901) {
      inicio = 901;
      fin = 999;
    } else {
      inicio = Math.floor((puntaje - 1) / 100) * 100 + 1;
      fin = inicio + 99;
    }
    return {
      rango: `SCORE: ${inicio} - ${fin}`,
      riesgo: nivel.riesgo,
      categoria: nivel.categoria,
      color: nivel.color,
      vendible: puntaje > 200,
    };
  };

  JSC.rangoSinPrefijo = (rango) => {
    if (rango && rango.startsWith("SCORE:")) return rango.slice("SCORE:".length).trim();
    return rango;
  };

  JSC.detectarTipoDocumento = (texto) => {
    const numero = String(texto ?? "").trim();
    if (/^\d{8}$/.test(numero)) return "DNI";
    if (/^\d{11}$/.test(numero)) return "RUC";
    if (/^[0-9A-Za-z]{9}$/.test(numero)) return "CE";
    return null;
  };

  const NUMERO = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;

  JSC.parseCoordenadas = (texto) => {
    const partes = String(texto ?? "")
      .replaceAll(";", ",")
      .split(",")
      .map((parte) => parte.trim());
    if (partes.length !== 2) {
      throw new Error("Formato esperado: latitud, longitud (separadas por coma)");
    }
    if (!NUMERO.test(partes[0]) || !NUMERO.test(partes[1])) {
      throw new Error(
        "Las coordenadas deben ser numeros (ej: -11.956037627741102, -77.04065381800075)",
      );
    }
    const lat = Number(partes[0]);
    const lon = Number(partes[1]);
    if (lat < -90 || lat > 90) throw new Error("Latitud fuera de rango (-90 a 90)");
    if (lon < -180 || lon > 180) throw new Error("Longitud fuera de rango (-180 a 180)");
    return [lat, lon];
  };

  JSC.textoCopiarTodo = (items) =>
    items.map(([etiqueta, valor]) => `${etiqueta}: ${valor}`.trimEnd()).join("\n");

  const casoPorId = (id) => JSC.CASOS.find((caso) => caso.id === id) || null;

  JSC.vista = (estado) => {
    const inicial = JSC.CASOS[0];
    const caso = casoPorId(estado.casoId) || inicial;
    const cargando = estado.fase === "cargando";
    let base = caso;
    let pendiente = null;
    if (cargando) {
      base = { ...inicial, entrada: caso.entrada };
    } else if (caso.scorePendiente) {
      if (estado.confirmado) base = { ...caso, ...caso.scorePendiente.alConfirmar };
      else pendiente = { mensaje: caso.scorePendiente.mensaje };
    }
    const rango = base.valorScore == null ? null : JSC.clasificarScore(base.valorScore);
    const indiceScore = JSC.ETIQUETAS.indexOf("SCORE");
    const ficha = JSC.ETIQUETAS.map((etiqueta, i) => [
      etiqueta,
      i === indiceScore ? (rango ? JSC.rangoSinPrefijo(rango.rango) : "") : base.ficha[i] || "",
    ]);
    const nivel = rango ? JSC.NIVELES.findIndex((n) => n.categoria === rango.categoria) : -1;
    return {
      fase: estado.fase,
      casoId: caso.id,
      cargando,
      entrada: caso.entrada,
      cobertura: base.cobertura,
      zona: base.zona,
      score: base.score,
      valorScore: base.valorScore ?? null,
      veredicto: cargando ? { texto: "Validando…", estilo: "secondary", nota: "" } : base.veredicto,
      aviso: cargando ? "" : base.aviso,
      ficha,
      rango,
      rangoLinea: rango
        ? rango.rango + (rango.vendible ? "" : " — NO SE LE PUEDE VENDER")
        : "Rango: —",
      nivel: nivel >= 0 ? nivel : null,
      pendiente,
      detalle: cargando ? "" : base.detalle,
      estadoTexto: cargando ? "Estado: validando..." : "Estado: listo",
    };
  };

  JSC.crearSesion = (opciones) => {
    const {
      render,
      transicion = (actualizar, o) => JSC.transicion(actualizar, o),
      esperar = (fn, ms) => setTimeout(fn, ms),
      limpiar = (id) => clearTimeout(id),
      tipos = () => [],
      conTransicion = () => true,
    } = opciones;
    const inicial = JSC.CASOS[0];
    const estado = { casoId: inicial.id, fase: inicial.fase, confirmado: false, origen: "caso" };
    let espera = null;

    const cancelar = () => {
      if (espera !== null) {
        limpiar(espera);
        espera = null;
      }
    };

    const aplicar = (cambios) => {
      const previo = { ...estado };
      Object.assign(estado, cambios);
      const pintar = () => render(JSC.vista(estado), estado, previo);
      if (conTransicion(previo, estado)) transicion(pintar, { tipos: tipos(previo, estado) });
      else pintar();
    };

    return {
      estado,
      inicializar() {
        render(JSC.vista(estado), estado, null);
      },
      elegirCaso(id) {
        const caso = casoPorId(id);
        if (!caso) return;
        cancelar();
        aplicar({ casoId: caso.id, fase: caso.fase, confirmado: false, origen: "caso" });
      },
      validar() {
        const caso = casoPorId(estado.casoId);
        cancelar();
        aplicar({ fase: "cargando", confirmado: false, origen: "validar" });
        if (caso.fase === "cargando") return;
        const destino = caso.fase === "inicial" ? casoPorId("vende") : caso;
        espera = esperar(() => {
          espera = null;
          aplicar({ casoId: destino.id, fase: destino.fase, confirmado: false, origen: "validar" });
        }, JSC.TIEMPO_CARGA_MS);
      },
      confirmarScore() {
        const caso = casoPorId(estado.casoId);
        if (!caso || !caso.scorePendiente || estado.confirmado || estado.fase !== "resultado") return;
        aplicar({ confirmado: true, origen: "confirmar" });
      },
    };
  };

  // ---------------------------------------------------------------------------
  // Transiciones de vista (con deteccion: sin soporte solo se actualiza el DOM)
  // ---------------------------------------------------------------------------

  JSC.transicion = (actualizar, opciones = {}) => {
    if (!hayDocumento || !document.startViewTransition) {
      actualizar();
      return Promise.resolve();
    }
    const tipos = opciones.tipos || [];
    let transicion;
    try {
      transicion = tipos.length
        ? document.startViewTransition({ update: actualizar, types: tipos })
        : document.startViewTransition(actualizar);
    } catch {
      actualizar();
      return Promise.resolve();
    }
    transicion.ready.catch(() => {});
    return transicion.finished.catch(() => {});
  };

  if (!hayDocumento) return;

  // ---------------------------------------------------------------------------
  // DOM comun a las variantes
  // ---------------------------------------------------------------------------

  const crear = (etiqueta, propiedades = {}, texto = "") => {
    const nodo = document.createElement(etiqueta);
    Object.assign(nodo, propiedades);
    if (texto) nodo.textContent = texto;
    return nodo;
  };

  JSC.reducirMovimiento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  JSC.pintarTarjeta = (nodo, tarjeta, cargando = false) => {
    nodo.dataset.estilo = cargando ? "secondary" : tarjeta.estilo;
    nodo.querySelector("[data-titulo]").textContent = cargando ? "—" : tarjeta.titulo;
    nodo.querySelector("[data-nota]").textContent = cargando ? "" : tarjeta.nota;
    nodo.setAttribute("aria-busy", String(cargando));
  };

  const pintarVeredicto = (nodo, vista) => {
    nodo.dataset.estilo = vista.veredicto.estilo;
    nodo.setAttribute("aria-busy", String(vista.cargando));
    const texto = nodo.querySelector("[data-veredicto-texto]");
    const nota = nodo.querySelector("[data-veredicto-nota]");
    if (texto) texto.textContent = vista.veredicto.texto;
    if (nota) nota.textContent = vista.veredicto.nota;
  };

  JSC.montarFicha = (lista, prefijo) => {
    lista.textContent = "";
    JSC.ETIQUETAS.forEach((etiqueta, i) => {
      const valor = crear("span", { className: "ficha__valor", id: `${prefijo}-${i}` });
      const boton = crear("button", { type: "button", className: "boton boton--icono" }, "📋");
      boton.setAttribute("command", "--copy");
      boton.setAttribute("commandfor", valor.id);
      boton.setAttribute("aria-label", `Copiar ${etiqueta}`);
      const copiar = crear("span", { className: "copiar" });
      copiar.append(boton, crear("span", { className: "tip" }));
      copiar.lastChild.setAttribute("role", "status");
      const dd = crear("dd");
      dd.append(valor, copiar);
      const fila = crear("div", { className: "ficha__fila" });
      fila.append(crear("dt", {}, etiqueta), dd);
      lista.append(fila);
    });
  };

  JSC.pintarFicha = (lista, items) => {
    if (!lista.firstElementChild) JSC.montarFicha(lista, lista.id || "ficha");
    items.forEach(([, valor], i) => {
      const nodo = lista.querySelectorAll(".ficha__valor")[i];
      nodo.textContent = valor;
    });
  };

  const inicioDeNivel = (i) => (i === 0 ? 0 : JSC.NIVELES[i - 1].tope + 1);

  JSC.pintarLeyenda = (lista, vista) => {
    if (!lista.firstElementChild) {
      JSC.NIVELES.forEach((nivel, i) => {
        const item = crear("li", { className: "leyenda__item" });
        item.dataset.nivel = String(i + 1);
        item.append(
          crear("span", { className: "leyenda__color" }),
          crear("span", {}, `${nivel.categoria} ${inicioDeNivel(i)}-${nivel.tope}`),
        );
        lista.append(item);
      });
    }
    lista.dataset.conNivel = String(vista.nivel !== null);
    [...lista.children].forEach((item, i) => {
      item.dataset.activo = String(vista.nivel === i);
    });
  };

  JSC.pintarMedidor = (nodo, vista) => {
    if (!nodo.firstElementChild) {
      JSC.NIVELES.forEach((_, i) => {
        const tramo = crear("span", { className: "medidor__tramo" });
        tramo.dataset.nivel = String(i + 1);
        nodo.append(tramo);
      });
      nodo.append(crear("span", { className: "medidor__marca" }));
      nodo.setAttribute("role", "img");
    }
    const conValor = vista.valorScore !== null;
    nodo.dataset.conValor = String(conValor);
    nodo.querySelectorAll(".medidor__tramo").forEach((tramo, i) => {
      tramo.dataset.activo = String(vista.nivel === i);
    });
    nodo.style.setProperty("--pos", conValor ? `${(vista.valorScore / 999) * 100}%` : "0%");
    nodo.setAttribute(
      "aria-label",
      conValor
        ? `Score ${vista.valorScore}, ${vista.rango.rango.replace("SCORE: ", "rango ")}, ${vista.rango.categoria}`
        : "Sin score",
    );
  };

  // --- copiar ----------------------------------------------------------------

  const temporizadores = new WeakMap();
  let ultimoMensaje = "";

  const reportar = (boton, mensaje, ok) => {
    const burbuja = boton.nextElementSibling;
    if (!burbuja) return;
    clearTimeout(temporizadores.get(boton));
    boton.removeAttribute("data-copiado");
    boton.removeAttribute("data-fallo");
    burbuja.textContent = "";
    void boton.offsetWidth;
    boton.setAttribute(ok ? "data-copiado" : "data-fallo", "");
    // VoiceOver omite un mensaje identico al anterior: un espacio fino lo distingue
    const anuncio = mensaje === ultimoMensaje ? `${mensaje} ` : mensaje;
    ultimoMensaje = mensaje;
    requestAnimationFrame(() => {
      burbuja.textContent = anuncio;
    });
    temporizadores.set(
      boton,
      setTimeout(() => {
        boton.removeAttribute("data-copiado");
        boton.removeAttribute("data-fallo");
        burbuja.textContent = "";
      }, 2000),
    );
  };

  const copiarAntiguo = (texto) => {
    const campo = Object.assign(document.createElement("textarea"), { value: texto });
    campo.setAttribute("readonly", "");
    campo.style.cssText = "position:fixed;inset-block-start:0;opacity:0";
    document.body.append(campo);
    campo.select();
    try {
      return document.execCommand("copy");
    } finally {
      campo.remove();
    }
  };

  const textoDe = (objetivo, comando) => {
    if (comando === "--copy-all") {
      const items = [...objetivo.querySelectorAll(".ficha__fila")].map((fila) => [
        fila.querySelector("dt").textContent,
        fila.querySelector(".ficha__valor").textContent,
      ]);
      return JSC.textoCopiarTodo(items);
    }
    return objetivo.matches("input, textarea") ? objetivo.value : objetivo.innerText.trim();
  };

  const copiar = async (boton, objetivo, comando) => {
    const texto = textoDe(objetivo, comando);
    if (!texto) {
      reportar(boton, "Sin dato", false);
      return;
    }
    try {
      await navigator.clipboard.writeText(texto);
      reportar(boton, "Copiado", true);
    } catch {
      let copiado = false;
      try {
        copiado = copiarAntiguo(texto);
      } catch {
        copiado = false;
      }
      reportar(boton, copiado ? "Copiado" : "No se pudo copiar", copiado);
    }
  };

  JSC.activarCopiado = () => {
    if ("CommandEvent" in window) {
      // los eventos `command` no burbujean: se escuchan en captura
      document.addEventListener(
        "command",
        (evento) => {
          if (evento.command.startsWith("--copy")) copiar(evento.source, evento.target, evento.command);
        },
        true,
      );
      return;
    }
    document.addEventListener("click", (evento) => {
      const boton = evento.target.closest('button[command^="--copy"]');
      const objetivo = boton && document.getElementById(boton.getAttribute("commandfor"));
      if (objetivo) copiar(boton, objetivo, boton.getAttribute("command"));
    });
  };

  // --- dialogos --------------------------------------------------------------

  JSC.montarDialogos = (sesion) => {
    document.body.insertAdjacentHTML(
      "beforeend",
      `
<dialog id="detalle" class="dialogo" closedby="any" aria-labelledby="detalle-titulo">
  <form method="dialog">
    <h2 id="detalle-titulo">Detalle de la validación</h2>
    <pre id="detalle-texto" tabindex="0"></pre>
    <div class="dialogo__acciones">
      <span class="copiar">
        <button type="button" class="boton" command="--copy" commandfor="detalle-texto">📋 Copiar para WhatsApp</button>
        <span class="tip" role="status"></span>
      </span>
      <button class="boton boton--primario" value="cerrar" autofocus>Cerrar</button>
    </div>
  </form>
</dialog>
<dialog id="confirmar-score" class="dialogo" closedby="any" aria-labelledby="confirmar-titulo">
  <form method="dialog">
    <h2 id="confirmar-titulo">Consultar score</h2>
    <p id="confirmar-mensaje"></p>
    <p>El score gasta una consulta de Equifax. ¿Consultarlo de todas formas?</p>
    <div class="dialogo__acciones">
      <button class="boton" value="cancelar" autofocus>Cancelar</button>
      <button class="boton boton--primario" value="consultar">Consultar</button>
    </div>
  </form>
</dialog>`,
    );
    const confirmar = document.getElementById("confirmar-score");
    confirmar.addEventListener("close", () => {
      const acepto = confirmar.returnValue === "consultar";
      confirmar.returnValue = "";
      if (acepto) sesion.confirmarScore();
    });
  };

  // --- barra de prueba y tema ----------------------------------------------------

  const TEMAS = [
    ["auto", "automático", ""],
    ["light", "claro", "light"],
    ["dark", "oscuro", "dark"],
  ];

  const leerTema = () => {
    try {
      return localStorage.getItem("jsc-tema") || "auto";
    } catch {
      return "auto";
    }
  };

  const aplicarTema = (clave) => {
    const tema = TEMAS.find((t) => t[0] === clave) || TEMAS[0];
    document.documentElement.style.colorScheme = tema[2];
    document.querySelectorAll("[data-tema]").forEach((boton) => {
      boton.textContent = `Tema: ${tema[1]}`;
    });
    try {
      localStorage.setItem("jsc-tema", tema[0]);
    } catch {
      // sin almacenamiento: el tema vuelve a automatico al recargar
    }
  };

  JSC.montarBarraPrueba = (contenedor, sesion) => {
    if (!contenedor) return;
    const opciones = JSC.CASOS.map(
      (caso) =>
        `<label class="prueba__opcion"><input type="radio" name="caso" value="${caso.id}"><span>${caso.nombre}</span></label>`,
    ).join("");
    contenedor.className = "prueba";
    contenedor.innerHTML = `
      <a class="prueba__volver" href="../index.html">← Galería</a>
      <div class="prueba__casos" role="radiogroup" aria-labelledby="prueba-titulo"><span id="prueba-titulo" class="prueba__titulo">Caso de prueba</span>${opciones}</div>
      <button type="button" class="boton boton--sutil" data-tema></button>`;
    contenedor.addEventListener("change", (evento) => {
      if (evento.target.name === "caso") sesion.elegirCaso(evento.target.value);
    });
    contenedor.querySelector("[data-tema]").addEventListener("click", () => {
      const siguiente = TEMAS[(TEMAS.findIndex((t) => t[0] === leerTema()) + 1) % TEMAS.length];
      aplicarTema(siguiente[0]);
    });
    aplicarTema(leerTema());
  };

  JSC.sincronizarBarra = (estado) => {
    const radio = document.querySelector(`input[name="caso"][value="${estado.casoId}"]`);
    if (radio) radio.checked = true;
  };

  // --- formulario --------------------------------------------------------------

  const porId = (id) => document.getElementById(id);

  const actualizarTipo = () => {
    const tipo = JSC.detectarTipoDocumento(porId("documento").value);
    document.querySelectorAll("[data-tipo-documento]").forEach((nodo) => {
      nodo.textContent = `Tipo: ${tipo ?? "—"}`;
    });
  };

  const mostrarError = (idCampo, idError, mensaje) => {
    const error = porId(idError);
    if (!error) return;
    error.textContent = mensaje;
    error.hidden = !mensaje;
    const campo = idCampo && porId(idCampo);
    if (!campo) return;
    if (mensaje) {
      campo.setAttribute("aria-invalid", "true");
      campo.setAttribute("aria-describedby", idError);
    } else {
      campo.removeAttribute("aria-invalid");
      campo.removeAttribute("aria-describedby");
    }
  };

  const limpiarErrores = () => {
    mostrarError("coordenadas", "error-coordenadas", "");
    mostrarError("documento", "error-documento", "");
    mostrarError(null, "error-general", "");
  };

  JSC.mostrarError = mostrarError;
  JSC.limpiarErrores = limpiarErrores;

  JSC.rellenarEntrada = (entrada) => {
    porId("coordenadas").value = entrada.coordenadas;
    porId("documento").value = entrada.documento;
    actualizarTipo();
    limpiarErrores();
  };

  JSC.activarFormulario = (sesion) => {
    porId("documento").addEventListener("input", actualizarTipo);
    document.querySelectorAll("[data-limpiar]").forEach((boton) => {
      boton.addEventListener("click", () => {
        const campo = porId(boton.dataset.limpiar);
        campo.value = "";
        actualizarTipo();
        campo.focus();
      });
    });
    porId("formulario").addEventListener("submit", (evento) => {
      evento.preventDefault();
      limpiarErrores();
      const coordenadas = porId("coordenadas").value.trim();
      const documento = porId("documento").value.trim();
      let primerError = null;
      if (coordenadas) {
        try {
          JSC.parseCoordenadas(coordenadas);
        } catch (error) {
          mostrarError("coordenadas", "error-coordenadas", error.message);
          primerError = primerError || porId("coordenadas");
        }
      }
      if (documento && !JSC.detectarTipoDocumento(documento)) {
        mostrarError(
          "documento",
          "error-documento",
          "Documento no reconocido (DNI 8 digitos, RUC 11, CE 9 caracteres)",
        );
        primerError = primerError || porId("documento");
      }
      if (!coordenadas && !documento) {
        mostrarError(null, "error-general", "Ingresa coordenadas y/o un documento.");
        primerError = porId("coordenadas");
      }
      if (primerError) {
        primerError.focus();
        return;
      }
      sesion.validar();
    });
  };

  // --- pintado comun ---------------------------------------------------------------

  JSC.pintarComun = (vista, estado, previo) => {
    const todos = (selector) => document.querySelectorAll(selector);
    todos("[data-tarjeta]").forEach((nodo) =>
      JSC.pintarTarjeta(nodo, vista[nodo.dataset.tarjeta], vista.cargando),
    );
    todos("[data-veredicto]").forEach((nodo) => pintarVeredicto(nodo, vista));
    todos("[data-estado]").forEach((nodo) => {
      nodo.textContent = vista.estadoTexto;
    });
    todos("[data-aviso]").forEach((nodo) => {
      nodo.textContent = vista.aviso;
      nodo.hidden = !vista.aviso;
    });
    todos("[data-rango-linea]").forEach((nodo) => {
      nodo.textContent = vista.rangoLinea;
      nodo.dataset.nivel = vista.nivel === null ? "" : String(vista.nivel + 1);
      nodo.dataset.sinVenta = String(Boolean(vista.rango) && !vista.rango.vendible);
    });
    todos("[data-valor-score]").forEach((nodo) => {
      nodo.textContent = vista.valorScore === null ? "—" : String(vista.valorScore);
      nodo.dataset.nivel = vista.nivel === null ? "" : String(vista.nivel + 1);
    });
    todos("[data-medidor]").forEach((nodo) => JSC.pintarMedidor(nodo, vista));
    todos("[data-leyenda]").forEach((nodo) => JSC.pintarLeyenda(nodo, vista));
    todos("[data-ficha]").forEach((nodo) => JSC.pintarFicha(nodo, vista.ficha));
    todos('[data-accion="ver-detalle"]').forEach((boton) => {
      boton.disabled = !vista.detalle;
    });
    todos('[data-accion="consultar-score"]').forEach((boton) => {
      boton.hidden = !vista.pendiente;
    });
    todos("[data-ocupado]").forEach((nodo) => nodo.setAttribute("aria-busy", String(vista.cargando)));
    const validar = porId("validar");
    if (validar) validar.disabled = vista.cargando;
    porId("detalle-texto").textContent = vista.detalle;
    porId("confirmar-mensaje").textContent = vista.pendiente ? vista.pendiente.mensaje : "";
    if (!previo || estado.origen === "caso") JSC.rellenarEntrada(vista.entrada);
    JSC.sincronizarBarra(estado);
  };

  JSC.iniciar = (opciones) => {
    const sesion = JSC.crearSesion({
      render: (vista, estado, previo) => {
        JSC.pintarComun(vista, estado, previo);
        if (opciones.render) opciones.render(vista, estado, previo);
      },
      tipos: opciones.tipos,
      conTransicion: opciones.conTransicion,
      transicion: opciones.transicion,
    });
    JSC.montarDialogos(sesion);
    JSC.activarCopiado();
    JSC.montarBarraPrueba(porId("barra-prueba"), sesion);
    JSC.activarFormulario(sesion);
    sesion.inicializar();
    return sesion;
  };
})();
