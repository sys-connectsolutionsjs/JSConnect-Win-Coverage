(() => {
  "use strict";

  const paneles = [...document.querySelectorAll("[data-paso]")];
  const indicadores = [...document.querySelectorAll("[data-indicador]")];
  const coordenadas = document.getElementById("coordenadas");
  let paso = 1;
  let enfocarAlTerminar = false;

  const mostrarPaso = (numero) => {
    paso = numero;
    paneles.forEach((panel) => {
      panel.hidden = Number(panel.dataset.paso) !== numero;
    });
    indicadores.forEach((indicador) => {
      const k = Number(indicador.dataset.indicador);
      indicador.dataset.avance = k < numero ? "hecho" : k === numero ? "actual" : "pendiente";
      if (k === numero) indicador.setAttribute("aria-current", "step");
      else indicador.removeAttribute("aria-current");
    });
  };

  // los cambios de pantalla ocultan el control que tenía el foco: se pasa al encabezado nuevo
  const enfocarEncabezado = () => {
    document.getElementById(`h-paso-${paso}`)?.focus({ preventScroll: true });
  };

  const irAPaso = (numero) => {
    if (numero === paso) return Promise.resolve();
    const direccion = numero > paso ? "forward" : "backward";
    return JSC.transicion(() => mostrarPaso(numero), { tipos: [direccion] }).finally(enfocarEncabezado);
  };

  // el paso que corresponde a cada estado de la sesión
  const pasoDe = (estado) => {
    if (estado.fase === "inicial") return 1;
    if (estado.fase === "cargando" && estado.origen === "validar") return paso;
    return 3;
  };

  mostrarPaso(1);

  const sesion = JSC.iniciar({
    tipos: (_previo, estado) => {
      const destino = pasoDe(estado);
      if (destino === paso) return [];
      return [destino > paso ? "forward" : "backward"];
    },
    transicion: (actualizar, opciones) =>
      JSC.transicion(actualizar, opciones).finally(() => {
        if (!enfocarAlTerminar) return;
        enfocarAlTerminar = false;
        enfocarEncabezado();
      }),
    render: (_vista, estado) => {
      const destino = pasoDe(estado);
      if (destino === paso) return;
      // el foco solo se mueve cuando el cambio viene del formulario, no de la barra de prueba
      enfocarAlTerminar = estado.origen === "validar";
      mostrarPaso(destino);
    },
  });

  document.querySelector('[data-ir="2"]').addEventListener("click", () => {
    JSC.mostrarError("coordenadas", "error-coordenadas", "");
    const texto = coordenadas.value.trim();
    if (texto) {
      try {
        JSC.parseCoordenadas(texto);
      } catch (error) {
        JSC.mostrarError("coordenadas", "error-coordenadas", error.message);
        coordenadas.focus();
        return;
      }
    }
    irAPaso(2);
  });

  document.querySelector('[data-ir="1"]').addEventListener("click", () => irAPaso(1));
  document.querySelector("[data-nueva]").addEventListener("click", () => sesion.elegirCaso("inicial"));

  coordenadas.addEventListener("keydown", (evento) => {
    if (evento.key !== "Enter") return;
    evento.preventDefault();
    document.querySelector('[data-ir="2"]').click();
  });

  // si VALIDAR encuentra un error en un campo de otro paso, se vuelve a ese paso
  document.getElementById("formulario").addEventListener("submit", () => {
    const invalido = document.querySelector('#formulario [aria-invalid="true"]');
    if (!invalido) return;
    const destino = Number(invalido.closest("[data-paso]").dataset.paso);
    if (destino !== paso) irAPaso(destino).then(() => invalido.focus());
  });
})();
