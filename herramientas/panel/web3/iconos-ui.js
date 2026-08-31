/* ============================================================================
   ICONOS-UI — los íconos del cromo del panel, en SVG
   ============================================================================
   Se carga ANTES que app.js. Deja `UI` global (y `ico(nombre, tam)`).

   POR QUÉ EXISTE ESTE ARCHIVO
   Los botones de la herramienta venían dibujados con caracteres tipográficos
   (← ↺ ↶ ↷ ⋯ ⧉ ✦ ⠿ ↑ ↓ ✕) y dos emojis de color (📥 y 📌). Tres problemas
   concretos, no de gusto:

   1. Un carácter hereda la escala tipográfica. Cuando el panel se conectó al
      sistema de tokens, los handles del bloque CAMBIARON DE TAMAÑO solos. Un
      vector no se mueve.
   2. Los emojis los dibuja la fuente de emoji de Windows: dos manchas de color
      saturado en una interfaz cálida y sobria, imposibles de teñir.
   3. Cada glifo depende de que la fuente instalada lo tenga. ⠿ (Braille) y ⧉
      no están garantizados en todos lados y caen a un rectángulo vacío.

   El panel ya usaba SVG para los 25 bloques. Esto termina de aplicar el mismo
   criterio al resto.

   CONVENCIONES
   - viewBox 0 0 24 24, `currentColor`, sin `fill`: heredan color del botón.
   - stroke-width 1.6: con Montserrat, 1.5 se ve anémico y 2 se ve tosco.
   - Tamaño por defecto 16px; 18 para los de navegación.
   ========================================================================== */
(function (raiz) {
  'use strict';

  var D = {
    /* navegación y barra */
    volver:    'M15 6l-6 6 6 6',
    bajar:     'M12 4v11m0 0 4-4m-4 4-4-4M5 19h14',
    bandeja:   'M4 14h4l1.5 2.5h5L16 14h4M4 14 6 6h12l2 8v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z',
    restaurar: 'M3 12a9 9 0 1 0 3-6.7M3 4v5h5',
    refrescar: 'M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5',
    deshacer:  'M9 7 4 12l5 5M4 12h10a6 6 0 0 1 0 12h-1',
    rehacer:   'M15 7l5 5-5 5M20 12H10a6 6 0 0 0 0 12h1',
    mas:       'M5 12h.01M12 12h.01M19 12h.01',

    /* acciones sobre un elemento */
    cerrar:    'M6 6l12 12M18 6L6 18',
    subir:     'M12 19V5m0 0-6 6m6-6 6 6',
    bajar1:    'M12 5v14m0 0 6-6m-6 6-6-6',
    duplicar:  'M9 9h10v10H9zM5 15V5h10',
    nuevo:     'M12 4v16M4 12h16',
    pegar:     'M9 4h6v3H9zM7 5H6a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-1',
    fijar:     'M12 17v4M8 4h8l-1 6 3 3H6l3-3z',

    /* el agarre: seis puntos, como Notion y Gutenberg. Va con fill, no stroke:
       son puntos, y a 1.6 de trazo se empastarían. */
    agarre:    null
  };

  function svg(d, tam, extra) {
    return '<svg viewBox="0 0 24 24" width="' + tam + '" height="' + tam +
      '" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"' +
      ' stroke-linejoin="round" aria-hidden="true" focusable="false"' + (extra || '') + '>' +
      '<path d="' + d + '"/></svg>';
  }

  /* Los seis puntos del agarre, dibujados con círculos rellenos. */
  function agarre(tam) {
    var c = '';
    [[9, 6], [15, 6], [9, 12], [15, 12], [9, 18], [15, 18]].forEach(function (p) {
      c += '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="1.5"/>';
    });
    return '<svg viewBox="0 0 24 24" width="' + tam + '" height="' + tam +
      '" fill="currentColor" aria-hidden="true" focusable="false">' + c + '</svg>';
  }

  /* ico('volver')  ->  el SVG listo para meter en innerHTML */
  function ico(nombre, tam) {
    tam = tam || 16;
    if (nombre === 'agarre') return agarre(tam);
    var d = D[nombre];
    if (!d) { return ''; }
    return svg(d, tam);
  }

  raiz.UI = D;
  raiz.ico = ico;
})(window);
