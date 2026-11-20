(() => {
  "use strict";

  JSC.iniciar({});

  const conPuntero = matchMedia("(hover: hover) and (prefers-reduced-motion: no-preference)");
  if (!conPuntero.matches) return;

  document.querySelector(".bento").addEventListener("pointermove", (evento) => {
    const bloque = evento.target.closest(".bloque");
    if (!bloque) return;
    const caja = bloque.getBoundingClientRect();
    bloque.style.setProperty("--mx", `${evento.clientX - caja.left}px`);
    bloque.style.setProperty("--my", `${evento.clientY - caja.top}px`);
  });
})();
