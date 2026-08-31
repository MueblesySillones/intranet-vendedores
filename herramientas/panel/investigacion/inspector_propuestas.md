## El titulo de la seccion pasa a ser el nombre del bloque (y el vacio dice la verdad)
**Donde:** web/index.html:101 · web/app.js:1203-1208 · web/styles.css:459

1) index.html:101 — darle id al rotulo y una clase a la seccion:
<div class="gb-sec gb-sec-insp"><div class="gb-sec-t" id="gbInspTitle">Bloque seleccionado</div>
2) app.js:1203-1208 — reemplazar el bloque de apertura de renderInspector por:
  const box = $('#gbInspector'), T = $('#gbInspTitle'); box.innerHTML = '';
  reanimar(box, 'mov-cambio', 300);
  if (SEL == null || !BLOQUES[SEL]) {
    T.textContent = 'Bloque seleccionado'; T.classList.remove('activo');
    box.innerHTML = BLOQUES.length
      ? '<div class="gb-empty-insp">Tocá un bloque del documento y acá aparecen <b>sus</b> ajustes.</div>'
      : '<div class="gb-empty-insp">Todavía no hay bloques.<br>Elegí uno en <b>Agregar bloque</b> ↑</div>';
    return; }
  const bk = BLOQUES[SEL];
  T.textContent = 'Ajustes de: ' + (BLOQUE_INFO[bk.t === 'titulo' && bk.nivel === 'h2' ? 'subtitulo' : bk.t] || { label: bk.t }).label;
  T.classList.add('activo');
(borra las dos lineas del lbl 'Bloque: ' + estilos inline, app.js:1207-1208)
3) styles.css, al lado de .gb-sec-t (linea 459):
.gb-sec-insp .gb-sec-t{position:sticky; top:0; background:#fff; padding:8px 0; margin:0 0 10px; z-index:2}
.gb-sec-insp .gb-sec-t.activo{text-transform:none; letter-spacing:0; font-size:13px; color:var(--accent);
  border-left:3px solid var(--accent); padding-left:9px}
El borde acento repite exactamente el color del outline del bloque en el canvas: el ojo une las dos cosas sin leer.

## La ayuda "donde se escribe el texto" siempre en el mismo lugar, para todos los bloques
**Donde:** web/app.js:1200 (mapa nuevo), 1673 (insNota), 1727/1741/1747/1768 (borrar) · web/styles.css:486

1) app.js, arriba de renderInspector (~linea 1200), agregar el mapa:
const BLOQUE_AYUDA = {
  tabla:'Las celdas se escriben <b>en la tabla</b>. Enter dentro de una celda agrega otra fila.',
  kpis:'El período, el número y la nota se escriben <b>en las tarjetas</b>. Acá elegís la variación y cuál va destacada.',
  barras:'El nombre y el número se escriben <b>en la barra</b>. El largo se calcula solo: la más grande ocupa el 100%.',
  podio:'Puesto, nombre, sucursal y números se escriben <b>en las tarjetas</b>.',
  tarjetas:'El título y el texto se escriben <b>en la tarjeta</b>. Acá van el ícono, el color y cuántas entran por fila.',
  lista:'El texto de cada ítem se escribe <b>en el documento</b> (Enter agrega otro).',
  chat:'Los mensajes se escriben <b>en las burbujas</b>. Acá cambiás de lado o agregás.',
  pasos:'Título y descripción se escriben <b>en el paso</b>. Acá van el ícono, el color y la flecha.',
  situacion:'El título y los mensajes se escriben <b>en la tarjeta</b>.',
  galeria:'Subí las placas acá; el nombre lo podés editar acá o abajo de cada placa.',
};
2) app.js:1663 — que insNota acepte una clase extra:
function insNota(html, cls) { const p = document.createElement('p'); p.className = 'fld-note' + (cls ? ' ' + cls : ''); p.style.margin='4px 0 0'; p.innerHTML = html; return p; }
3) app.js, justo despues de fijar el titulo (ver propuesta 1):
if (BLOQUE_AYUDA[bk.t]) box.appendChild(insNota(BLOQUE_AYUDA[bk.t], 'insp-ayuda'));
4) borrar las notas sueltas que quedan duplicadas: app.js:1727 (tabla), 1741 (kpis), 1747 (barras, es la primera linea de la funcion), 1768 (podio), y los lbl() redundantes de renderInspector 1225 ('Pasos (ícono, color y conexión)') y 1227 ('Burbujas (cliente = blanca...)').
5) styles.css, junto a .gb-empty-insp (linea 486):
#gbInspector .insp-ayuda{background:#F2EFE9; border:1px solid var(--line); border-radius:9px;
  padding:9px 11px; line-height:1.45; color:var(--ink2); margin:0 0 6px}
Queda como una caja calida distinta de los rotulos: se lee como "esto te lo explico", no como "otro campo mas".

## Un solo checkbox, y que se note cuando esta prendido
**Donde:** web/styles.css:524 · web/app.js:1665-1672, 1312, 1418, 1545, 1833

1) styles.css, junto a .insp-input (linea 524):
.insp-check{display:flex; align-items:center; gap:9px; font-size:12.5px; color:var(--ink2);
  border:1px solid var(--line); border-radius:9px; padding:9px 11px; background:#fff; cursor:pointer;
  transition:background .13s, border-color .13s, color .13s}
.insp-check:hover{border-color:var(--accent2)}
.insp-check input{accent-color:var(--accent); width:15px; height:15px; margin:0; flex:0 0 auto}
.insp-check.on{background:#F3EFE8; border-color:var(--accent2); color:var(--ink); font-weight:600}
2) app.js:1665-1672 — insCheck pasa a usarla y a mantener el estado 'on':
function insCheck(obj, prop, texto) {
  const l = document.createElement('label'); l.className = 'insp-check';
  const c = document.createElement('input'); c.type = 'checkbox'; c.checked = !!obj[prop];
  l.classList.toggle('on', c.checked);
  c.onchange = () => { obj[prop] = c.checked; l.classList.toggle('on', c.checked); renderCanvas(); renderInspector(); };
  l.append(c, document.createTextNode(texto)); return l;
}
3) los cuatro checkbox a mano pasan a insCheck (misma pinta, menos codigo):
- app.js:1312-1316 (imagen, descargable) -> wrap.appendChild(insCheck(bk,'descargable','Permitir descargar (botón “Descargar”)'))
- app.js:1418-1422 (pdf) -> insCheck(bk,'descargable','Mostrar botón “Descargar”')  [ojo: hoy el default es true; inicializar antes con: if (bk.descargable === undefined) bk.descargable = true;]
- app.js:1545-1550 (video) -> insCheck(bk,'descargable','Permitir descargar el video')
- app.js:1833-1837 (situacion, conResp) -> insCheck(bk,'conResp','Mostrar “Respuesta recomendada”')  [inicializar: if (bk.conResp === undefined) bk.conResp = true;]
Ojo: insCheck llama renderInspector(), que es justo lo que esos cuatro necesitan (muestran/esconden campos al tildar), asi que el comportamiento no cambia.

## Un solo vocabulario para agregar y quitar (y el quitar siempre en el mismo rincon)
**Donde:** web/styles.css:487, 570 · web/app.js:1647-1649, 1629, 1857, 1273, 1875, 1348

1) styles.css, junto a .gb-insp-acts (linea 487):
.insp-caja{border:1px solid var(--line); border-radius:9px; padding:9px; background:#fff;
  display:flex; flex-direction:column; gap:7px}
.insp-del{border:none; background:none; color:var(--ink3); cursor:pointer; font-size:13px; line-height:1;
  width:24px; height:24px; border-radius:6px; flex:0 0 auto; transition:background .13s, color .13s}
.insp-del:hover{background:#FBEFEC; color:var(--danger)}
.insp-add{width:100%; border:1px dashed var(--line); background:none; border-radius:9px; padding:9px;
  cursor:pointer; color:var(--ink2); font-size:12.5px; transition:background .13s, border-color .13s, color .13s}
.insp-add:hover{border-color:var(--accent2); background:var(--bg); color:var(--ink)}
2) app.js:1647-1649 — las tres fabricas pierden el cssText:
function insCaja(){ const d=document.createElement('div'); d.className='insp-caja'; return d; }
function insAdd(txt,fn){ const b=document.createElement('button'); b.type='button'; b.className='insp-add'; b.textContent=txt; b.onclick=fn; return b; }
function insDel(fn){ const b=document.createElement('button'); b.type='button'; b.className='insp-del'; b.textContent='✕'; b.title='Quitar'; b.onclick=fn; return b; }
3) los cinco casos sueltos pasan al mismo molde:
- lista (app.js:1629-1636): card -> insCaja(); head -> insHead(txtOf(o.html) || 'Tarjeta '+(i+1), () => { bk.items.splice(i,1); ... }); borrar el del inline de 1632.
- chat (1857-1863): del inline -> insDel(...).
- pasos (1273-1280): row -> insCaja(); poner el borrar ARRIBA con insHead('Paso '+(i+1), () => {...}) y eliminar el boton "Quitar paso" del final (1276-1277); el add de 1282 -> insAdd('+ Agregar paso', ...).
- plantilla (1875-1899): card -> insCaja(); reemplazar lbl('Tarjeta '+(i+1)) por insHead('Tarjeta '+(i+1), onDel) y borrar el "Quitar tarjeta" del final (1893-1895); add de 1898 -> insAdd(...). "Quitar imagen" (1882) queda como esta: no borra el item, borra el archivo.
- galeria (1348): .gal-del -> insDel; se puede borrar la regla .gal-del de styles.css:570.
Regla que queda: recuadro = un item; la cruz siempre arriba a la derecha; el boton punteado de ancho completo siempre agrega uno mas.

## Los dos interruptores Pagina/Presentacion tienen que decir a que le mandan
**Donde:** web/index.html:91, 145-146, 154 · web/app.js:446-461 · web/styles.css:370

1) index.html:91 — rotular el interruptor del documento, antes del div.seg:
<span class="doc-bar-lbl">Este documento:</span>
2) index.html:154 — cambiar el label del otro: <span>Cómo se ve el contenido</span> -> <span>Qué es este módulo</span>
3) index.html:145-146 — el acordeon deja de llamarse solo "Apariencia" y muestra resumen cuando esta cerrado (.acc-meta ya existe en styles.css:237 y no se usa en ningun lado):
<span class="acc-title">Módulo: nombre, ícono y tipo</span>
<span class="acc-meta" id="apMeta"></span>
4) app.js, al final de pintarModo() (~linea 460):
const nm = {pagina:'Página', presentacion:'Presentación', biblioteca:'Biblioteca'}[modo];
const am = $('#apMeta'); if (am) am.textContent = ($('#dTitle').value || 'Sin nombre') + ' · ' + nm;
5) styles.css, junto a .doc-bar-e (linea 370):
.doc-bar-lbl{font-size:11.5px; font-weight:600; color:var(--ink3); white-space:nowrap}
.accordion.open .acc-meta{display:none}
Con eso, cerrado el acordeon sigue diciendo "Catálogo primavera · Biblioteca" y la barra de arriba dice "Este documento: Página": ya no hay dos controles gemelos anonimos.

## Los errores del bloque Video salen en negro: var(--err) no existe
**Donde:** web/app.js:1508-1511, 1522, 1565, 1595, 1615

1) app.js — cambiar var(--err) por var(--danger) en las 4 apariciones: 1522 (link invalido), 1565 (pesa demasiado), 1595 (falta el compresor), 1615 (catch general).
2) app.js:1508-1511 — el input del link:
const link = document.createElement('input'); link.type='text'; link.className='insp-input';
link.placeholder='https://youtube.com/watch?v=…'; link.value = bk.url || '';
(borrar la linea 1511 con el style.cssText: .insp-input ya define borde, radio, padding y ancho — styles.css:524)
3) opcional, para que el error se lea como error y no como nota, styles.css junto a .fld-note (linea 191):
#gbInspector .fld-note.err{color:var(--danger); background:#FBF0EC; border:1px solid #E6C9C3; border-radius:9px; padding:8px 10px}
y en videoInspector usar estado.classList.toggle('err', ...) en vez de tocar style.color a mano.
