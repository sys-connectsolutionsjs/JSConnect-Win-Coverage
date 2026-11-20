(() => {
  "use strict";

  const JSC = (window.JSC = window.JSC || {});

  JSC.TIEMPO_CARGA_MS = 900;
  JSC.COLOR_INACTIVO = "#9AA0A6";

  JSC.NIVELES = [
    { tope: 200, riesgo: "MUY ALTO", categoria: "MUY MALO", color: "#C8102E" },
    { tope: 400, riesgo: "ALTO", categoria: "MALO", color: "#D9480F" },
    { tope: 600, riesgo: "REGULAR", categoria: "BUENO", color: "#B8860B" },
    { tope: 800, riesgo: "BAJO", categoria: "MUY BUENO", color: "#2B8A3E" },
    { tope: 999, riesgo: "MUY BAJO", categoria: "EXCELENTE", color: "#1A237E" },
  ];

  JSC.ETIQUETAS = [
    "APELLIDOS Y NOMBRES",
    "DOCUMENTO DE IDENTIDAD (DNI, RUC, CE)",
    "NACIONALIDAD Y FECHA DE NACIMIENTO",
    "SCORE",
    "DIRECCIÓN DETALLADA",
    "DEPARTAMENTO",
    "PROVINCIA",
    "DISTRITO",
  ];

  const COORDENADAS = "-12.00000, -77.00000";
  const DOCUMENTO = "00000001";
  const DIRECCION = ["AV. EJEMPLO 123 MZ. A LT. 4 (LIMA, LIMA, LIMA)", "LIMA", "LIMA", "LIMA"];

  JSC.CASOS = [
    {
      id: "inicial",
      nombre: "Inicial",
      fase: "inicial",
      entrada: { coordenadas: "", documento: "" },
      cobertura: { titulo: "—", nota: "sin coordenadas", estilo: "secondary" },
      zona: { titulo: "—", nota: "sin coordenadas", estilo: "secondary" },
      score: { titulo: "—", nota: "ingresa un documento", estilo: "secondary" },
      valorScore: null,
      veredicto: { texto: "—", estilo: "secondary", nota: "Ingresa coordenadas y/o un documento" },
      aviso: "",
      ficha: [],
      detalle: "",
    },
    {
      id: "vende",
      nombre: "Vende",
      fase: "resultado",
      entrada: { coordenadas: COORDENADAS, documento: DOCUMENTO },
      cobertura: { titulo: "✔ Hay cobertura", nota: "", estilo: "success" },
      zona: { titulo: "Normal", nota: "mín. 201", estilo: "info" },
      score: { titulo: "✔ VENDE", nota: "612 (mín. 201)", estilo: "success" },
      valorScore: 612,
      veredicto: { texto: "VENDE", estilo: "success", nota: "Cobertura, zona y score cumplen" },
      aviso: "",
      ficha: ["EJEMPLO PRUEBA UNO", "DNI " + DOCUMENTO, "PERUANA, 01/01/1990", null, ...DIRECCION],
      detalle: "JSConnect-Win · 2026-11-20 10:30 · versión prototipo\nCoordenadas: -12.0, -77.0\nDocumento: DNI 00000001\nCobertura WinForce: sí\nDecisión: Con cobertura. Score minimo para vender: 201.\nCapas del punto: ninguna\nScore mínimo de la zona: 201\nScore: 612 (SCORE: 601 - 700)",
    },
    {
      id: "no_vende",
      nombre: "No vende",
      fase: "resultado",
      entrada: { coordenadas: COORDENADAS, documento: DOCUMENTO },
      cobertura: { titulo: "✔ Hay cobertura", nota: "", estilo: "success" },
      zona: { titulo: "Preferente 2", nota: "mín. 401\n⚠ zona de fraude", estilo: "warning" },
      score: { titulo: "✖ NO VENDE", nota: "380 (mín. 401)", estilo: "danger" },
      valorScore: 380,
      veredicto: { texto: "NO VENDE", estilo: "danger", nota: "Score 380 bajo el mínimo de la zona (401)" },
      aviso: "",
      ficha: ["EJEMPLO PRUEBA DOS", "DNI " + DOCUMENTO, "PERUANA, 12/03/1978", null, ...DIRECCION],
      detalle: "JSConnect-Win · 2026-11-20 10:30 · versión prototipo\nCoordenadas: -12.0, -77.0\nDocumento: DNI 00000001\nCobertura WinForce: sí\nDecisión: Con cobertura. Score minimo para vender: 401.\nCapas del punto: PREFERENTE 2\nFraude: zona de fraude (informativo)\nScore mínimo de la zona: 401\nScore: 380 (SCORE: 301 - 400)",
    },
    {
      id: "extensible",
      nombre: "Zona extensible",
      fase: "resultado",
      entrada: { coordenadas: COORDENADAS, documento: DOCUMENTO },
      cobertura: { titulo: "▲ Posible extensión", nota: "a 120 m", estilo: "warning" },
      zona: { titulo: "Normal", nota: "mín. 201", estilo: "info" },
      score: { titulo: "Necesita 201+", nota: "pendiente de confirmar", estilo: "secondary" },
      valorScore: null,
      veredicto: { texto: "POSIBLE EXTENSIÓN", estilo: "warning", nota: "Consulta el score para decidir" },
      aviso: "",
      ficha: ["", "DNI " + DOCUMENTO, "", null, ...DIRECCION],
      detalle: "JSConnect-Win · 2026-11-20 10:30 · versión prototipo\nCoordenadas: -12.0, -77.0\nDocumento: DNI 00000001\nCobertura WinForce: no\nDecisión: Sin cobertura en el punto, pero hay cobertura a 120 m (proyecto PROYECTO EJEMPLO). Se puede extender el servicio desde ahi. Score minimo en la zona: 201.\nCapas del punto: ninguna\nCobertura más cercana: 120 m (PROYECTO EJEMPLO)\nScore mínimo de la zona: 201",
      scorePendiente: {
        mensaje: "Sin cobertura en el punto, pero hay cobertura a 120 m (proyecto PROYECTO EJEMPLO). Se puede extender el servicio desde ahi. Score minimo en la zona: 201.",
        alConfirmar: {
          score: { titulo: "✔ VENDE", nota: "534 (mín. 201)", estilo: "success" },
          valorScore: 534,
          veredicto: { texto: "POSIBLE EXTENSIÓN", estilo: "warning", nota: "Score 534 · confirma con soporte" },
          ficha: ["EJEMPLO PRUEBA TRES", "DNI " + DOCUMENTO, "PERUANA, 15/06/1985", null, ...DIRECCION],
          detalle: "JSConnect-Win · 2026-11-20 10:30 · versión prototipo\nCoordenadas: -12.0, -77.0\nDocumento: DNI 00000001\nCobertura WinForce: no\nDecisión: Sin cobertura en el punto, pero hay cobertura a 120 m (proyecto PROYECTO EJEMPLO). Se puede extender el servicio desde ahi. Score minimo en la zona: 201.\nCapas del punto: ninguna\nCobertura más cercana: 120 m (PROYECTO EJEMPLO)\nScore mínimo de la zona: 201\nScore: 534 (SCORE: 501 - 600)",
        },
      },
    },
    {
      id: "bloqueado",
      nombre: "Código bloqueado",
      fase: "resultado",
      entrada: { coordenadas: COORDENADAS, documento: DOCUMENTO },
      cobertura: { titulo: "✔ Hay cobertura", nota: "", estilo: "success" },
      zona: { titulo: "✖ Código bloqueado", nota: "no vender", estilo: "danger" },
      score: { titulo: "No se consulta", nota: "código bloqueado", estilo: "secondary" },
      valorScore: null,
      veredicto: { texto: "NO VENDE", estilo: "danger", nota: "Código bloqueado: no se consulta el score" },
      aviso: "",
      ficha: ["", "DNI " + DOCUMENTO, "", null, ...DIRECCION],
      detalle: "JSConnect-Win · 2026-11-20 10:30 · versión prototipo\nCoordenadas: -12.0, -77.0\nDocumento: DNI 00000001\nCobertura WinForce: sí\nDecisión: Codigo bloqueado: no vender, no consultar el score.\nCapas del punto: CODIGOS BLOQUEADOS",
    },
    {
      id: "error_cobertura",
      nombre: "Error de cobertura",
      fase: "resultado",
      entrada: { coordenadas: COORDENADAS, documento: DOCUMENTO },
      cobertura: { titulo: "▲ Reintenta", nota: "el mapa lo cubre", estilo: "warning" },
      zona: { titulo: "Normal", nota: "mín. 201", estilo: "info" },
      score: { titulo: "Necesita 201+", nota: "no se consultó", estilo: "secondary" },
      valorScore: null,
      veredicto: { texto: "SIN CONFIRMAR", estilo: "warning", nota: "Reintenta la consulta de cobertura" },
      aviso: "WinForce no respondió · reintenta",
      ficha: ["", "DNI " + DOCUMENTO, "", null, ...DIRECCION],
      detalle: "JSConnect-Win · 2026-11-20 10:30 · versión prototipo\nCoordenadas: -12.0, -77.0\nDocumento: DNI 00000001\nCobertura WinForce: sin respuesta\nDecisión: No se pudo confirmar la cobertura con WinForce. Score minimo en la zona: 201.\nCapas del punto: ninguna\nScore mínimo de la zona: 201\nError de cobertura: TimeoutError: Timeout tras 5.0s conect / 30.0s lectura",
    },
    {
      id: "cargando",
      nombre: "Cargando",
      fase: "cargando",
      entrada: { coordenadas: COORDENADAS, documento: DOCUMENTO },
    },
  ];
})();
