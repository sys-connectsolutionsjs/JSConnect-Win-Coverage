(() => {
  "use strict";

  JSC.iniciar({
    // el panel solo se funde al cambiar de resultado; la carga muestra esqueletos sin transición
    conTransicion: (previo, estado) => previo.fase !== "inicial" || estado.fase !== "cargando",
  });
})();
