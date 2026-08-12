/* ===================================================================
   MURO - CONTENIDO DE PRUEBA
   Este archivo existe SOLO en la rama "muro", para poder ver el feed
   funcionando sin tocar modulos.js (que lo reescribe el panel en cada
   publicacion). En produccion no existe y la intranet lo ignora.

   Cuando el muro se apruebe, los posts se cargan desde el panel y este
   archivo se borra.
   =================================================================== */
window.MURO_DEMO = {
  key: 'muro',
  title: 'Muro',
  desc: 'Todo lo nuevo del equipo, en un solo lugar',
  icon: 'megaphone',
  color: '--c-hudson',
  ready: true,
  content: {
    tipo: 'muro',
    docs: [

/* ---------- FIJADO ---------- */
{
  id: 'normas-whatsapp',
  reacciones: { like: 9, heart: 1 },
  titulo: 'Normas de atención por WhatsApp: lectura obligatoria',
  autor: 'Marketing',
  sucursal: 'Central',
  fecha: '2026-08-04',
  etiqueta: 'importante',
  fijado: true,
  html: `<p class="m-lead">Repasamos las reglas de atención por WhatsApp. Son las mismas de siempre, pero hubo consultas repetidas sobre los tiempos de respuesta.</p>
  <div class="checklist">
    <div class="ci"><div class="ci-ic" style="background:var(--c-success)"><span class="ico"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></span></div><div><b>Responder dentro de la hora</b> en el horario del local.</div></div>
    <div class="ci"><div class="ci-ic" style="background:var(--c-success)"><span class="ico"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></span></div><div><b>Siempre presentarse</b> con nombre y sucursal en el primer mensaje.</div></div>
    <div class="ci"><div class="ci-ic" style="background:var(--c-danger)"><span class="ico"><svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></span></div><div><b>No enviar precios</b> antes de tomar los datos del cliente.</div></div>
  </div>
  <div class="note"><span class="ico"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg></span><div>El detalle completo, con los ejemplos de cada situación, está en el módulo <b>Normas de WhatsApp</b>.</div></div>`
},

/* ---------- PROMO con galeria real ---------- */
{
  id: 'placas-agosto',
  reacciones: { like: 12, heart: 5 },
  titulo: 'Ya están las placas de promociones bancarias de agosto',
  autor: 'Marketing',
  sucursal: 'Central',
  fecha: '2026-08-10',
  etiqueta: 'promo',
  html: `<p class="m-p">Subimos las placas nuevas de cuotas para que las compartas con tus clientes. Están también en <b>Material descargable</b>.</p>
  <div class="gallery">
    <div class="gcard">
      <img class="gimg" src="assets/promos_bancarias/Historia Promos bancarias 01.jpg" alt="Promos bancarias 01" loading="lazy" onclick="openLightbox('assets/promos_bancarias/Historia Promos bancarias 01.jpg','Promos bancarias 01')">
      <div class="gmeta"><div class="gtitle">Promos bancarias 01</div>
      <a class="dl-btn" href="assets/promos_bancarias/Historia Promos bancarias 01.jpg" download="Promos bancarias 01.jpg"><span class="ico"><svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></span> Descargar</a></div>
    </div>
    <div class="gcard">
      <img class="gimg" src="assets/promos_bancarias/Mes del Mundial - 18 y 24 cuotas.jpeg" alt="18 y 24 cuotas" loading="lazy" onclick="openLightbox('assets/promos_bancarias/Mes del Mundial - 18 y 24 cuotas.jpeg','18 y 24 cuotas')">
      <div class="gmeta"><div class="gtitle">18 y 24 cuotas</div>
      <a class="dl-btn" href="assets/promos_bancarias/Mes del Mundial - 18 y 24 cuotas.jpeg" download="18 y 24 cuotas.jpeg"><span class="ico"><svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></span> Descargar</a></div>
    </div>
  </div>`
},

/* ---------- ANUNCIO con foto a todo el ancho ---------- */
{
  id: 'entregas-nuevo-camion',
  reacciones: { like: 7, heart: 2 },
  titulo: 'Sumamos un camión más al servicio de entregas',
  autor: 'Logística',
  sucursal: 'Central',
  fecha: '2026-08-09',
  etiqueta: 'anuncio',
  html: `<p class="m-p">Desde esta semana sale una unidad más todos los días. Podés confirmarle al cliente la entrega con más margen.</p>
  <div class="m-img"><img src="assets/entregas/Servicio de entregas integral.jpg" alt="Servicio de entregas" loading="lazy" onclick="openLightbox('assets/entregas/Servicio de entregas integral.jpg','Servicio de entregas')"></div>`
},

/* ---------- LOGRO ---------- */
{
  id: 'julio-record',
  reacciones: { like: 14, heart: 11 },
  titulo: 'Julio cerró con el mejor mes de derivaciones del año',
  autor: 'Ezequiel',
  sucursal: 'Marketing',
  fecha: '2026-08-08',
  etiqueta: 'logro',
  html: `<p class="m-lead">Cerramos julio con el número más alto de derivaciones desde que medimos. Gracias a todo el equipo por sostener el ritmo de respuesta.</p>
  <p class="m-p">Lo que más movió la aguja fue la <b>velocidad de la primera respuesta</b>: las consultas contestadas dentro de la hora cerraron muy por encima del resto.</p>
  <p class="m-p">El detalle por sucursal está en el reporte de <b>Métricas</b>.</p>`
},

/* ---------- CAPACITACION ---------- */
{
  id: 'chatbot-derivar',
  reacciones: { like: 6 },
  titulo: 'Cómo derivar una consulta desde el chatbot Lucy',
  autor: 'Marketing',
  sucursal: 'Central',
  fecha: '2026-08-06',
  etiqueta: 'capacitacion',
  html: `<p class="m-p">Repasamos el paso a paso para tomar una consulta que llega por el chatbot y derivarla a la sucursal que corresponde.</p>
  <div class="flow">
    <div class="step"><div class="si" style="background:var(--c-caba)"><span class="ico"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg></span></div><div class="st">Llega la consulta</div><div class="sd">El chatbot toma los datos básicos</div></div>
    <div class="step"><div class="si" style="background:var(--c-canning)"><span class="ico"><svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></span></div><div class="st">Derivás</div><div class="sd">Elegís la sucursal más cercana al cliente</div></div>
    <div class="step"><div class="si" style="background:var(--c-hudson)"><span class="ico"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></span></div><div class="st">Confirmás</div><div class="sd">El vendedor toma el contacto y avisa</div></div>
  </div>
  <div class="note"><span class="ico"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg></span><div>Las capturas de cada pantalla están en el módulo <b>Tutorial del ChatBot</b>.</div></div>`
},

/* ---------- ANUNCIO ---------- */
{
  id: 'plazos-living',
  reacciones: { like: 4 },
  titulo: 'Cambio en los plazos de entrega de living',
  autor: 'Logística',
  sucursal: 'Central',
  fecha: '2026-08-05',
  etiqueta: 'anuncio',
  html: `<p class="m-p">Desde esta semana los sillones de la línea principal salen con un plazo de <b>15 a 20 días</b> en lugar de 20 a 25.</p>
  <p class="m-p">Importante: informarlo así al cliente en el momento de la venta. Si ya vendiste con el plazo anterior, no hace falta avisar, va a llegar antes.</p>`
},

/* ---------- EQUIPO ---------- */
{
  id: 'bienvenida-carla',
  reacciones: { like: 10, heart: 8 },
  titulo: 'Se suma Carla al equipo de Canning',
  autor: 'Recursos Humanos',
  sucursal: 'Central',
  fecha: '2026-08-01',
  etiqueta: 'equipo',
  html: `<p class="m-p">Esta semana arranca <b>Carla</b> en el salón de Canning. Viene de atención al cliente y ya está con los accesos al chatbot.</p>
  <p class="m-p">Si la ven por el salón, denle la bienvenida.</p>`
}

    ]
  }
};
