(() => {
  "use strict";

  const heroe = document.querySelector(".heroe");
  const panel = document.getElementById("detalle-panel");
  const boton = document.querySelector("[data-expandir]");
  let expandido = false;

  const aplicar = (valor) => {
    expandido = valor;
    heroe.dataset.expandido = String(valor);
    panel.hidden = !valor;
    boton.setAttribute("aria-expanded", String(valor));
  };

  boton.addEventListener("click", () => JSC.transicion(() => aplicar(!expandido)));

  JSC.iniciar({});
})();
