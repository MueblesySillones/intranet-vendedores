# DIAGNOSTICO
Hoy la paleta son 5 `<details>` cerrados (app.js:908-915, y app.js:335 los fuerza cerrados al entrar al módulo): el usuario abre un documento vacío y ve CUATRO palabras — Texto, Elementos, Datos, Medios — y ni una pista de que adentro hay 25 bloques. Descubrir "Podio" o "Sección de descargas" exige abrir grupo por grupo y leer 25 renglones de texto plano (styles.css:482-485: columna de botones label+small, cero imagen), sin buscador y sin manera de saber cómo se ve cada cosa antes de insertarla. Los nombres de grupo no ayudan: "Elementos" y "Datos" no significan nada para un vendedor, y "Sección de descargas" (lo que más se usa) está enterrada en "Medios". Peor: los `<details>` son independientes, así que con 2-3 abiertos la columna de 340px (styles.css:451) mide 800px+ y el inspector "Bloque seleccionado" (index.html:101) queda fuera de pantalla en una notebook chica; y selectBlock (app.js:1185) scrollea el panel hasta el inspector, o sea que después de tocar un bloque la paleta desaparece hacia arriba. Y al insertar, insertBloque (app.js:929-937) solo lleva la vista al bloque nuevo si tiene `[contenteditable]`: con separador, espacio, imagen, video, galería o pdf el usuario clickea y no ve absolutamente nada pasar. El panel ya tiene 40 SVG inline sin usar acá (ICONS, app.js:179-218) y un renderizador real de bloques (bloqueCanvas, app.js:1124-1171) que sirve de preview gratis.


## Grilla de miniaturas siempre visible en vez de 5 desplegables cerrados  [alto/medio]
**Donde:** app.js:898-916 (renderGbAdd) + styles.css:476-485 y 736-742

Reemplazar los <details> por grupos SIEMPRE abiertos con una grilla de 2 columnas de tarjetas: miniatura SVG (esquema de cómo se ve el bloque) + nombre. Sin imágenes externas: son rects/lines dibujados a mano.

1) styles.css — BORRAR las reglas .gb-add* (476-485) y poner en su lugar:
.gb-grupo{margin-bottom:12px}
.gb-grupo-t{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--ink3);margin:0 0 6px}
.gb-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.gb-tipo{display:flex;flex-direction:column;align-items:stretch;gap:5px;text-align:left;padding:7px;border:1px solid var(--line);border-radius:10px;background:#fff;cursor:pointer;font:inherit;font-size:12.5px;font-weight:600;color:var(--ink);line-height:1.2}
.gb-tipo:hover,.gb-tipo:focus-visible{border-color:var(--accent);background:var(--bg);outline:none}
.gb-mini{width:100%;height:32px;display:block;color:var(--ink3);background:#F0EDE8;border-radius:6px;padding:3px}
.gb-tipo:hover .gb-mini{color:var(--accent)}
.gb-mini rect,.gb-mini circle,.gb-mini polygon,.gb-mini path{fill:currentColor}
.gb-mini line{stroke:currentColor;stroke-width:2;stroke-linecap:round}
.gb-nores{font-size:12.5px;color:var(--ink3);padding:10px 2px}

2) styles.css bloque MOVIMIENTO — reemplazar las 6 reglas .gb-add de 737-742 por:
.gb-tipo{transition:border-color .13s,background .13s,transform .13s var(--mov)}
.gb-tipo:hover{transform:translateY(-1px)}
.gb-grupo{animation:movDesplegar .18s var(--mov)}

3) app.js — arriba de renderGbAdd, el set de miniaturas (viewBox 40x26, todo currentColor):
const mini=s=>`<svg class="gb-mini" viewBox="0 0 40 26" aria-hidden="true">${s}</svg>`;
const r=(x,y,w,h,o=1)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="1.2" opacity="${o}"/>`;
const BLOQUE_MINI={
 titulo:r(4,6,32,6)+r(4,15,20,3,.35),
 subtitulo:r(4,7,22,5)+r(4,15,32,3,.35)+r(4,20,26,3,.35),
 parrafo:r(4,6,32,3,.55)+r(4,12,32,3,.55)+r(4,18,22,3,.55),
 destacado:r(4,6,32,4.5,.8)+r(4,14,24,4.5,.8),
 kicker:r(4,8,7,10)+r(14,11,20,4,.45),
 lista:[6,13,20].map(y=>`<circle cx="7" cy="${y}" r="2.6"/>`+r(13,y-1.5,22,3,.45)).join(''),
 pasos:`<line x1="8" y1="13" x2="32" y2="13" opacity=".35"/><circle cx="8" cy="13" r="4"/><circle cx="20" cy="13" r="4" opacity=".6"/><circle cx="32" cy="13" r="4" opacity=".35"/>`,
 chat:`<rect x="4" y="5" width="20" height="7" rx="3.5" opacity=".45"/><rect x="16" y="15" width="20" height="7" rx="3.5"/>`,
 situacion:`<rect x="3" y="4" width="34" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".45"/>`+r(6,7,11,4)+r(6,14,20,3,.45),
 nota:r(4,5,3,16)+r(10,7,25,3,.45)+r(10,13,18,3,.45),
 separador:r(4,12,32,3),
 espacio:r(4,4,32,3,.35)+r(4,19,32,3,.35),
 tabla:r(4,5,32,4)+[11,16,21].map(y=>r(4,y,9,3,.4)+r(15.5,y,9,3,.4)+r(27,y,9,3,.4)).join(''),
 kpis:[4,15,26].map(x=>`<rect x="${x}" y="6" width="10" height="14" rx="2" opacity=".18"/>`+r(x+2,9,6,5)+r(x+2,16,6,2,.5)).join(''),
 barras:[[30,1],[22,.7],[14,.45]].map(([w,o],i)=>r(4,5+i*7,w,5,o)).join(''),
 podio:r(4,14,10,10,.45)+r(15,7,10,17)+r(26,17,10,7,.3),
 tarjetas:[4,15,26].map(x=>`<rect x="${x}" y="6" width="10" height="14" rx="2" opacity=".18"/><circle cx="${x+5}" cy="11" r="2.4"/>`+r(x+2,16,6,2,.5)).join(''),
 diapo:`<rect x="3" y="4" width="34" height="18" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3"/>`+r(9,11,22,4,.5),
 imagen:`<rect x="4" y="5" width="32" height="16" rx="2.5" opacity=".18"/><circle cx="12" cy="10" r="2.4"/><path d="M7 21l7-7 5 5 4-4 6 6z"/>`,
 video:`<rect x="4" y="5" width="32" height="16" rx="2.5" opacity=".18"/><polygon points="17,9 26,13 17,17"/>`,
 galeria:[4,15,26].map(x=>[5,14].map(y=>`<rect x="${x}" y="${y}" width="10" height="7" rx="1.5" opacity=".55"/>`).join('')).join(''),
 pdf:`<path d="M10 3h12l6 6v14H10z" opacity=".18"/><path d="M22 3l6 6h-6z"/>`+r(13,13,12,3,.55)+r(13,18,8,3,.55),
 embed:`<rect x="3" y="4" width="34" height="18" rx="2.5" opacity=".18"/>`+r(3,4,34,4,.45)+r(7,12,26,3,.45)+r(7,17,18,3,.45),
 boton:`<rect x="9" y="9" width="22" height="9" rx="4.5"/>`,
 plantilla:`<rect x="11" y="3" width="18" height="21" rx="2.5" opacity=".18"/><rect x="13" y="5" width="14" height="8" rx="1.5" opacity=".5"/>`+r(13,15,14,2.5,.5)+`<rect x="13" y="19" width="14" height="4" rx="2"/>`
};

4) app.js:908-915 — el cuerpo de renderGbAdd pasa a ser:
Object.entries(GRUPOS_BLOQUE).forEach(([grupo,tipos])=>{
  if(grupo==='Presentación'&&!PRESENTACION) return;
  const g=document.createElement('div'); g.className='gb-grupo';
  g.innerHTML=`<div class="gb-grupo-t">${grupo}</div>`;
  const grid=document.createElement('div'); grid.className='gb-grid';
  tipos.forEach(t=>{const inf=BLOQUE_INFO[t];
    const b=document.createElement('button'); b.type='button'; b.className='gb-tipo'; b.dataset.t=t; b.title=inf.desc;
    b.innerHTML=mini(BLOQUE_MINI[t]||'')+inf.label;
    b.onclick=()=>insertBloque(t); grid.appendChild(b);});
  g.appendChild(grid); box.appendChild(g);
});
Y BORRAR el memo de app.js:905 (`if(box.dataset.modo===modo) return;`) — con la propuesta 2 hay que re-renderizar en cada tecla. El chequeo de modo sigue vivo dentro del forEach, así que 'Nueva diapositiva' sigue sin aparecer en modo Página.

5) app.js:335 — `$('#gbAdd').querySelectorAll('details')...` ya no aplica: borrar esa línea (la reemplaza el reset del buscador de la propuesta 2).

Con 340px de sidebar y padding 14px quedan tarjetas de ~152px: entran nombre corto en 1 renglón. La `desc` de BLOQUE_INFO se conserva como `title` (tooltip) y como texto de búsqueda.


## Buscador de bloques con sinónimos (escribís 'excel' y aparece Tabla)  [alto/chico]
**Donde:** index.html:100 + app.js:898-916 + app.js:335

Un input arriba de la paleta que filtra por label + desc + alias, sin acentos, y con Enter que inserta el primer resultado.

1) index.html:100 — reemplazar la línea por:
<div class="gb-sec"><div class="gb-sec-t" id="gbAddT">Agregar bloque</div>
  <div class="gb-buscar-w"><input type="search" id="gbBuscar" class="gb-buscar" autocomplete="off" placeholder="Buscar bloque… (tabla, foto, whatsapp)"></div>
  <div id="gbAdd"></div></div>
(el input queda FUERA de #gbAdd a propósito: renderGbAdd lo re-dibuja todo y si el input estuviera adentro se perdería el foco en cada tecla)

2) styles.css, al lado de las reglas nuevas de la propuesta 1:
.gb-buscar-w{position:sticky;top:-14px;z-index:2;background:#fff;padding:0 0 8px}
.gb-buscar{width:100%;font:inherit;font-size:13px;padding:8px 11px 8px 30px;border:1px solid var(--line);border-radius:9px;color:var(--ink);background:var(--bg) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238A857B' stroke-width='2'><circle cx='11' cy='11' r='8'/><line x1='21' y1='21' x2='16.65' y2='16.65'/></svg>") no-repeat 9px 50%/14px 14px}
.gb-buscar:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(124,106,85,.14)}

3) app.js, junto a BLOQUE_INFO (app.js:806-833):
const ALIAS_BLOQUE={titulo:'encabezado h1 titular',subtitulo:'encabezado h2 seccion',parrafo:'texto cuerpo escribir',destacado:'copete intro lead resumen',kicker:'etiqueta rotulo numero paso',lista:'checklist tildes puntos bullets requisitos',pasos:'flujo proceso diagrama circuito',chat:'whatsapp conversacion mensaje burbuja cliente',situacion:'objecion caso guion respuesta cliente',nota:'aviso importante atencion recuadro recordatorio',separador:'linea divisoria raya corte',espacio:'aire margen blanco separacion',tabla:'excel planilla grilla filas columnas precios',kpis:'numeros metricas cifras indicadores ventas',barras:'grafico ranking comparar chart',podio:'ranking top mejores primeros vendedores',tarjetas:'grilla iconos conceptos beneficios',diapo:'slide corte presentacion pantalla',imagen:'foto placa jpg png banner',video:'mp4 youtube reel clip',galeria:'descargas placas material bajar archivos fotos',pdf:'documento archivo folleto catalogo',embed:'iframe web informe looker mapa',boton:'link enlace url ir a',plantilla:'whatsapp carrusel mensaje plantilla'};
const norm=s=>(s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'');

4) dentro de renderGbAdd, arriba del forEach:
const q=norm(($('#gbBuscar')||{}).value||'').trim(); let hay=0;
y dentro del forEach, antes de crear el grupo:
const vis=tipos.filter(t=>!q||norm(BLOQUE_INFO[t].label+' '+BLOQUE_INFO[t].desc+' '+(ALIAS_BLOQUE[t]||'')).includes(q));
if(!vis.length) return; hay+=vis.length;   // y recorrer vis en vez de tipos
y al final:
if(!hay) box.insertAdjacentHTML('beforeend','<div class="gb-nores">Ningún bloque se llama así. Probá <b>tabla</b>, <b>foto</b>, <b>descargas</b> o <b>whatsapp</b>.</div>');

5) cablear una sola vez (al lado de los otros listeners de arranque):
$('#gbBuscar').oninput=()=>renderGbAdd();
$('#gbBuscar').onkeydown=e=>{
  if(e.key==='Escape'){e.target.value='';renderGbAdd();}
  if(e.key==='Enter'){const b=$('#gbAdd .gb-tipo'); if(b){b.click(); e.target.value=''; renderGbAdd();}}
};

6) app.js:335 (al abrir un módulo) pasa a: `$('#gbBuscar').value='';`


## Decir DÓNDE va a caer el bloque y llevarlo siempre a la vista  [alto/chico]
**Donde:** app.js:929-937

1) app.js:929-937 — insertBloque queda:
function insertBloque(t){
  const nb=bloqueNuevo(t);
  if(SEL!=null&&SEL<BLOQUES.length){BLOQUES.splice(SEL+1,0,nb);SEL++;} else {BLOQUES.push(nb);SEL=BLOQUES.length-1;}
  renderCanvas(); renderInspector();
  const el=bloqueEl(SEL);
  reanimar(el,'gb-nuevo',400);
  const ce=el&&el.querySelector('[contenteditable]'); if(ce) ce.focus();
  if(el) el.scrollIntoView({block:'center',behavior:sinMovimiento()?'auto':'smooth'});   // ← el arreglo
  if(!ce) reanimar(el,'gb-recien',600);   // los bloques sin texto pulsan, así se ven
  actualizarDestino();
}

2) el rótulo de destino, función nueva:
function actualizarDestino(){
  const h=$('#gbAddT'); if(!h) return;
  const bk=(SEL!=null)?BLOQUES[SEL]:null;
  const nom=bk?(BLOQUE_INFO[bk.t==='titulo'&&bk.nivel==='h2'?'subtitulo':bk.t]||{label:bk.t}).label:null;
  h.innerHTML='Agregar bloque'+(nom?`<span class="gb-destino">debajo de: ${esc(nom)}</span>`:'<span class="gb-destino">al final del documento</span>');
}
Llamarla al final de selectBlock (app.js:1179-1186) y de renderInspector (app.js:1202).

3) styles.css, junto a .gb-sec-t (459):
.gb-destino{display:block;text-transform:none;letter-spacing:0;font-size:11.5px;font-weight:600;color:var(--accent);margin-top:3px}

4) además, el mensaje de documento vacío (styles.css:455) dice 'panel de la derecha →' pero abajo de 900px el sidebar queda ABAJO (styles.css:507-509): agregar
@media(max-width:900px){.gb-doc:empty:before{content:'Tu documento está vacío. Agregá bloques desde el panel de abajo ↓'}}


## Vista previa real del bloque al pasar el mouse (reusando bloqueCanvas)  [alto/medio]
**Donde:** app.js:1124 (bloqueCanvas, se reusa) + renderGbAdd

El panel YA tiene el renderizador real: bloqueCanvas(bk,i) (app.js:1124-1171). Se le pasa un bloque de ejemplo y se muestra en un flotante a la izquierda del sidebar.

1) index.html, antes de </body>: <div id="gbPv" class="gb-pv" hidden></div>

2) styles.css:
.gb-pv{position:fixed;right:352px;width:340px;max-height:320px;overflow:hidden;z-index:60;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:0 10px 34px rgba(40,35,28,.16);padding:12px;pointer-events:none}
.gb-pv .gb-pv-doc{margin:0;max-width:none;padding:14px;min-height:0;background:#F0EDE8;border:1px solid var(--line);border-radius:10px}
.gb-pv .gb-handle{display:none!important}
.gb-pv [contenteditable]{cursor:default}
@media(max-width:1200px){.gb-pv{display:none}}   /* en notebooks chicas no hay lugar: no molesta */
En el bloque MOVIMIENTO: .gb-pv:not([hidden]){animation:movModal .16s var(--mov)}

3) app.js, al lado de BLOQUE_MINI:
const DEMO_BLOQUE={
 titulo:{html:'Objetivos de julio'}, subtitulo:{html:'Cómo cerrar la venta'},
 parrafo:{html:'Escribí acá lo que van a leer los vendedores.'},
 destacado:{html:'Este mes duplicamos la promo bancaria.'},
 kicker:{n:'3',html:'Objeción de precio'},
 lista:{items:[{icono:'check',color:'--c-success',html:'Confirmá el stock'},{icono:'check',color:'--c-success',html:'Ofrecé la financiación'}]},
 chat:{label:'Ejemplo',items:[{lado:'in',html:'¿Hacen envío a Canning?'},{lado:'out',html:'Sí, sin cargo desde $300.000.'}]},
 nota:{icono:'clock',html:'Acordate de cargar la venta el mismo día.'},
 boton:{texto:'Ver catálogo'},
 barras:{items:[{label:'Hudson',valor:'120',color:'--c-hudson',tono:'gr'},{label:'CABA',valor:'86',color:'--c-caba',tono:'gr'}]},
 podio:{items:[{puesto:'1°',nombre:'Ana',suc:'Hudson',valor:'42',vlabel:'ventas',lead:true}]},
 kpis:{items:[{label:'Ventas',valor:'128',pie:'julio',tend:'+12%'}]},
 tabla:{cols:[{h:'Concepto',num:false},{h:'Cantidad',num:true}],filas:[{celdas:['Sillón 3 cuerpos','12']},{celdas:['Mesa ratona','8']}]},
 tarjetas:{items:[{icono:'award',color:'--c-hudson',titulo:'Garantía',texto:'2 años en estructura.'}]}
};
function demoBloque(t){return Object.assign(bloqueNuevo(t),DEMO_BLOQUE[t]||{});}
let pvT=null;
function pvMostrar(btn){
  clearTimeout(pvT);
  pvT=setTimeout(()=>{
    const p=$('#gbPv'), b=btn.getBoundingClientRect();
    p.innerHTML=`<div class="gb-doc doc-preview gb-pv-doc">${bloqueCanvas(demoBloque(btn.dataset.t),0)}</div>`;
    p.querySelectorAll('[contenteditable]').forEach(e=>e.removeAttribute('contenteditable'));
    p.hidden=false;
    p.style.top=Math.max(72,Math.min(window.innerHeight-p.offsetHeight-16,b.top-24))+'px';
  },240);   // 240ms: no dispara mientras el mouse cruza la grilla
}
function pvOcultar(){clearTimeout(pvT);$('#gbPv').hidden=true;}

4) en el forEach de renderGbAdd, al crear cada .gb-tipo:
b.onmouseenter=()=>pvMostrar(b); b.onfocus=()=>pvMostrar(b);
b.onmouseleave=pvOcultar; b.onblur=pvOcultar; b.addEventListener('click',pvOcultar);

Bonus honesto: imagen/video/pdf/embed sin src ya renderizan su propio placeholder ('Subí una imagen desde los ajustes de la derecha →'), que es exactamente lo que el usuario necesita saber antes de insertar.


## Renombrar/reordenar los grupos y sumar 'Los que más usás'  [medio/chico]
**Donde:** app.js:799-833

1) app.js:799-805, renombrar y reordenar (las CLAVES de GRUPOS_BLOQUE son solo rótulos: nada guardado depende de ellas, el chequeo de app.js:909 usa 'Presentación', que se conserva):
const GRUPOS_BLOQUE={
  'Texto':['titulo','subtitulo','parrafo','destacado','kicker'],
  'Listas y avisos':['lista','pasos','nota','chat','situacion'],
  'Fotos, videos y archivos':['imagen','galeria','video','pdf','plantilla','embed','boton'],
  'Números y tablas':['tabla','kpis','barras','podio','tarjetas'],
  'Separaciones':['separador','espacio'],
  'Presentación':['diapo'],
};
(ojo: si se toca el rótulo 'Presentación' hay que tocar también app.js:909)
Y dos labels que hoy mienten un poco, en BLOQUE_INFO (app.js:806-833):
  galeria:{label:'Placas para descargar',desc:'Grilla de imágenes que el vendedor baja'}
  kicker:{label:'Etiqueta con número',desc:'Rótulo chico arriba de un título'}

2) 'Los que más usás', arriba de todo (solo cuando el buscador está vacío):
const FREC_KEY='panel_bloques_frec'; let FREC={};
try{FREC=JSON.parse(localStorage.getItem(FREC_KEY))||{}}catch(e){}
// dentro de insertBloque, al final:
FREC[t]=(FREC[t]||0)+1; try{localStorage.setItem(FREC_KEY,JSON.stringify(FREC))}catch(e){}
// en renderGbAdd, antes del forEach de grupos:
if(!q){
  const top=Object.keys(FREC).filter(t=>BLOQUE_INFO[t]&&(t!=='diapo'||PRESENTACION))
    .sort((a,b)=>FREC[b]-FREC[a]).slice(0,4);
  if(top.length>=3) box.appendChild(grupoEl('Los que más usás',top));
}
(grupoEl = extraer a función el cuerpo del forEach de la propuesta 1: recibe (titulo, tipos) y devuelve el .gb-grupo)

El panel ya usa localStorage con try/catch para 'editados' (app.js:262-263): mismo patrón, sigue andando offline y si falla no rompe nada.


## Botón + entre bloques del lienzo, que apunta a la paleta  [medio/medio]
**Donde:** app.js:957 (junto a initBlockDrag) + styles.css:453

Un solo botón '+' que sigue al hueco entre bloques y, al tocarlo, selecciona el bloque de arriba, resetea el buscador, lleva la paleta a la vista y le da el foco. No hace falta un popover nuevo: reusa la paleta del sidebar.

1) styles.css:453 (y el override de 503) — agregar position:relative a .gb-canvas, y:
#gbMas{position:absolute;width:22px;height:22px;border-radius:50%;border:1px solid var(--line);background:#fff;color:var(--accent);font-size:15px;line-height:1;padding:0;cursor:pointer;box-shadow:var(--shadow);z-index:6}
#gbMas:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
En MOVIMIENTO: #gbMas{transition:background .13s,color .13s,transform .13s var(--mov)} #gbMas:hover{transform:scale(1.12)}

2) app.js, al lado de initBlockDrag (app.js:957):
(function initMasEntre(){
  const canvas=document.querySelector('.gb-canvas'), doc=$('#gbDoc'); if(!canvas||!doc) return;
  const b=document.createElement('button'); b.id='gbMas'; b.type='button'; b.textContent='+';
  b.title='Agregar un bloque acá'; b.hidden=true; canvas.appendChild(b);
  let destino=null;
  canvas.addEventListener('mousemove',e=>{
    let mejor=null,dist=99;
    doc.querySelectorAll('.gb-block').forEach(el=>{const r=el.getBoundingClientRect();const d=Math.abs(e.clientY-r.bottom);if(d<dist&&d<20){dist=d;mejor=el;}});
    if(!mejor){b.hidden=true;destino=null;return;}
    const r=mejor.getBoundingClientRect(),c=canvas.getBoundingClientRect();
    b.style.top=(r.bottom-c.top+canvas.scrollTop-11)+'px';
    b.style.left=(r.left-c.left+r.width/2-11)+'px';
    destino=+mejor.dataset.i; b.hidden=false;
  });
  canvas.addEventListener('mouseleave',()=>{b.hidden=true;});
  b.onclick=()=>{ if(destino==null) return;
    selectBlock(destino);                        // ← el nuevo cae acá abajo
    const s=$('#gbBuscar'); if(s){s.value='';renderGbAdd();}
    const sec=$('#gbAdd').closest('.gb-sec'); if(sec) sec.scrollIntoView({behavior:sinMovimiento()?'auto':'smooth',block:'start'});
    if(s) s.focus();
  };
})();

3) para que el paso 2 no pelee con el scroll automático al inspector: en selectBlock (app.js:1185), condicionar ese scrollIntoView a que la llamada NO venga del '+' (pasar un flag: selectBlock(i,sinScroll) y llamarlo con true desde b.onclick).

El botón nunca aparece si no hay mouse encima, no toca el HTML que se publica y desaparece solo al re-renderizar (vive fuera de #gbDoc, que se reescribe entero en renderCanvas).