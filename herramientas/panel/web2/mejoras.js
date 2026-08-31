/* ============================================================================
   MEJORAS — capa de prueba, APAGADA por defecto
   ============================================================================
   Se prende agregando ?mejoras=1 a la direccion. No se activa sola.

   Que hay adentro (mejoras.css): la barra lateral atenuada al estilo Linear,
   el indicador de estado sin forma de boton, el hover de la paleta como velo
   del 4% y el halo blanco en la seleccion del bloque (los dos ultimos, del
   codigo fuente de Gutenberg).

   POR QUE NO ENTRA TODAVIA
   Cambia la apariencia de pantallas que el equipo usa todos los dias, asi que
   va a un release aparte, despues de mirarla un tiempo. Lo que SI quedo
   permanente —los iconos en SVG, `tabular-nums`, la marca del sidebar y el
   arreglo de la vista previa— vive en el codigo real, no aca: eso no se apaga.

   Para verla:  http://127.0.0.1:8124/?mejoras=1
   ========================================================================== */
(function () {
  'use strict';
  var params = new URLSearchParams(location.search);
  if (params.get('mejoras') !== '1') return;
  document.body.classList.add('mejoras');
})();
