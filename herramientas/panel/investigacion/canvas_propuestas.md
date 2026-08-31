## El papel tiene que parecer papel: mesa de trabajo con textura detrás del documento
**Donde:** styles.css:503-505 (bloque "consolidación"); afecta 453-454 y 607

En el bloque de consolidación (después de styles.css:503), agregar:

.gb-canvas{ background:#E9E3D9;
  background-image:radial-gradient(rgba(124,106,85,.11) 1px, transparent 1px);
  background-size:16px 16px; background-position:-1px -1px; }
.gb-doc.doc-preview{ box-shadow:0 1px 2px rgba(40,35,28,.07), 0 16px 38px rgba(40,35,28,.13);
  margin:0 auto 32px; }

#E9E3D9 es --line (#E4DFD6) apenas aclarado: sigue siendo la paleta japandi, no un gris de app. El punteado a 16px es el código universal de "mesa de trabajo" (Canva/Figma/Gutenberg) y además hace que la sombra nueva de la hoja se lea. NO tocar la sombra de is-mobile: `.gb-doc.doc-preview.is-mobile` (styles.css:607) tiene specificity 0,3,0 y le gana a esta regla (0,2,0), así que el marco negro del teléfono queda intacto.

## El bloque seleccionado dice su nombre, y el hover marca a quién pertenece la barra ⠿↑↓✕
**Donde:** app.js:1170 y styles.css:462

JS — app.js:1170, agregar el nombre al wrapper (la expresión ya existe en 1207):

  const nom = (BLOQUE_INFO[bk.t === 'titulo' && bk.nivel === 'h2' ? 'subtitulo' : bk.t] || { label: bk.t }).label;
  return `<div class="db gb-block" data-i="${i}" data-nom="${esc(nom)}">${gbHandle()}${inner}</div>`;

CSS — junto a styles.css:462:

.gb-block:not(.is-selected):hover{ outline:1px dashed rgba(124,106,85,.45); outline-offset:7px; border-radius:5px }
.gb-block.is-selected:before{
  content:attr(data-nom); position:absolute; left:-1px; top:-9px; transform:translateY(-100%);
  background:var(--accent); color:#fff; font-size:9.5px; font-weight:800; letter-spacing:.08em;
  text-transform:uppercase; padding:3px 8px; border-radius:6px 6px 6px 0; white-space:nowrap;
  pointer-events:none; z-index:6; animation:movAparece .15s ease }

El chip usa el mismo lenguaje que `.gb-diapo-l` (438) y `.col-badge` (339), así que no introduce un componente nuevo. `.gb-block` ya es position:relative (460) y no tiene ningún :before propio (el único :before cercano es `.gb-doc:empty:before`, 455, y los de [data-ph] que están en los hijos): no hay colisión. El chip queda dentro del padding-top de 30px del papel incluso para el primer bloque.

## La vista celular tiene que romper igual que la intranet real
**Donde:** styles.css:607-613 y index.html:63-66

Espejar las reglas reales. En intranet/index.html:505-512 están @media(max-width:640px) y @media(max-width:420px); el papel is-mobile tiene 392px − 2×16px de padding = 360px útiles, o sea cae en el tramo de 420px. Agregar después de styles.css:613:

/* espejo de intranet/index.html:505-512 — si tocás una, tocá la otra */
.doc-preview.is-mobile .m-tarj.cols-2,
.doc-preview.is-mobile .m-tarj.cols-3,
.doc-preview.is-mobile .m-tarj.cols-4{ grid-template-columns:1fr }
.doc-preview.is-mobile .m-barras .bl{ width:66px; font-size:12px }
.doc-preview.is-mobile .m-barras .br{ width:auto }
.doc-preview.is-mobile .m-barras .bchip{ font-size:9.5px; padding:3px 7px }
.doc-preview.is-mobile .m-kpis .kv{ font-size:30px }
.doc-preview.is-mobile .m-tabla table{ min-width:320px }

(Specificity 0,4,0 contra el 0,2,0 de `.doc-preview .m-tarj.cols-3` en 426: gana sin !important.)

Y que el toggle diga qué es, en vez de dos emojis — index.html:64-65:
  <button ... id="vtDesktop" class="vt active">🖥 <span class="vt-tx">Escritorio</span></button>
  <button ... id="vtMobile" class="vt">📱 <span class="vt-tx">Celular</span></button>
con (styles.css:604):
  .vt{ display:flex; align-items:center; gap:5px; font-size:12.5px; font-weight:600; color:var(--ink2) }
  .vt.active{ color:var(--ink) }
  @media(max-width:1180px){ .vt-tx{ display:none } }

## Los controles del bloque: contraste AA, área de toque usable y ✕ separado del resto
**Donde:** app.js:954 y styles.css:466-472

JS — app.js:954, agregar etiquetas legibles:

function gbHandle(){ return `<div class="gb-handle">`+
  `<button type="button" class="gb-grip" data-lbl="Arrastrar para mover">⠿</button>`+
  `<button type="button" class="gb-h-up" data-lbl="Subir">↑</button>`+
  `<button type="button" class="gb-h-down" data-lbl="Bajar">↓</button>`+
  `<button type="button" class="gb-h-del" data-lbl="Eliminar bloque">✕</button></div>`; }

CSS — reemplazar/ampliar styles.css:466-472:

.gb-handle{ left:-48px; top:-2px; padding:4px; gap:2px }
.gb-handle button{ position:relative; width:30px; height:28px; font-size:13px; color:var(--ink2) }   /* #5B574F = 6,4:1 */
.gb-handle .gb-h-del{ margin-top:4px; padding-top:4px; height:32px; border-top:1px solid var(--line); border-radius:0 0 5px 5px }
.gb-handle button:focus-visible{ outline:2px solid var(--accent); outline-offset:1px }
.gb-handle button:hover:after{
  content:attr(data-lbl); position:absolute; left:calc(100% + 9px); top:50%; transform:translateY(-50%);
  background:var(--ink); color:#fff; font-size:11px; font-weight:600; padding:4px 9px; border-radius:6px;
  white-space:nowrap; z-index:8; pointer-events:none; animation:movAparece .12s ease }

El tooltip sale hacia la derecha (sobre el papel, transitorio) y reusa el look de #gbFloat (490). Verificado que no se corta: el papel arranca a 16px del borde del scroll (padding de .gb-canvas, 503) y la botonera con left:-48px + padding 28px del papel queda en x≈−4px del papel, dentro del área visible incluso cuando el lienzo colapsa a 1 columna en ≤900px.

## Biblioteca: que se vea de un saque cuál ve primero el vendedor, cuál está oculto y de qué trata
**Donde:** app.js:556 y 748/754; styles.css:331-333

JS — app.js:748:
  card.className = 'col-item' + (d.archivado ? ' archivado' : (i === primeroVisible ? ' es-ultimo' : ''));
(primeroVisible ya está calculado en 745). Y en 754 cambiar el texto del chip por algo que diga la consecuencia: <span class="col-badge">Se ve primero</span>.

JS — app.js:556, que el resumen diga de qué trata (el bloque título guarda el texto en bk.html, ver 1129):

function resumenDoc(d){
  const bl = d.bloques || [];
  if (d.presentacion){ const n = contarSlides(bl); return n + (n===1?' diapositiva':' diapositivas'); }
  const n = bl.length, cuenta = n + (n===1?' bloque':' bloques');
  const t = bl.find(b => b.t==='titulo' && txtOf(b.html));
  return t ? cuenta + ' · ' + esc(txtOf(t.html).slice(0,44)) : cuenta;
}
(esc() es obligatorio: el resultado entra por innerHTML en 756.)

CSS — reemplazar styles.css:331-333:
.col-item{ display:flex; align-items:center; gap:10px; background:var(--panel); border:1px solid var(--line);
  border-left:3px solid transparent; border-radius:12px; padding:11px 13px; box-shadow:var(--shadow) }
.col-item.es-ultimo{ background:#fff; border-left-color:var(--accent) }
.col-item.es-ultimo .col-t{ font-size:15.5px }
.col-item.archivado{ opacity:1; background:var(--bg); border-style:dashed; box-shadow:none }
.col-item.archivado .col-t{ color:var(--ink3) }

Sacar opacity mantiene los botones de acción legibles; el borde punteado + fondo hundido siguen diciendo "esta no se publica", pero sin romper contraste.

## Descargables: número de posición visible y "ver grande" descubrible sin adivinanza
**Donde:** styles.css:640-672 e index.html:136

CSS — junto a styles.css:640-672:

.gal-grid{ counter-reset:gcard }
.gcard-mini{ counter-increment:gcard }
.gcard-mini:after{ content:counter(gcard); position:absolute; top:6px; left:6px; min-width:19px; height:19px;
  padding:0 5px; border-radius:999px; background:rgba(255,255,255,.92); color:var(--ink2);
  font-size:10.5px; font-weight:800; display:grid; place-items:center; z-index:2 }
.gcard-mini:before{ content:'⤢ Ver grande'; position:absolute; left:0; right:0; bottom:22px; z-index:1;
  background:linear-gradient(transparent, rgba(28,24,20,.74)); color:#fff; font-size:10.5px; font-weight:700;
  text-align:center; padding:16px 4px 6px; opacity:0; transition:opacity .13s; pointer-events:none }
.gcard-mini:hover:before{ opacity:1 }
.gx{ opacity:.45 }
.gcard-mini:hover .gx{ opacity:1; background:rgba(40,35,28,.66) }

Detalles verificados: la tarjeta que se arrastra queda en display:none (app.js:2473) y los elementos display:none no incrementan counters, así que la numeración se recalcula sola mientras arrastrás — el .gcard-placeholder tampoco cuenta. El `bottom:22px` deja el rótulo justo arriba de .gcard-cap (10,5px + padding 5px). No hace falta tocar el cursor: `.gcard-mini img` tiene pointer-events:none (645), el cursor sale de .gcard-mini.

Y en index.html:136, cambiar el párrafo de instrucciones por uno que nombre las tres acciones en el orden en que se usan: "Tocá una imagen para verla en grande · Arrastrala para cambiarle el orden o pasarla a otra sección · Tocá la ✕ para borrarla".
