'use strict';

const $ = s => document.querySelector(s);

// ---------- helpers ----------
async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let m = 'Error ' + r.status;
    try { m = (await r.json()).error || m; } catch (e) {}
    throw new Error(m);
  }
  return r.json();
}
function toast(msg, tipo) {
  const t = $('#toast');
  t.textContent = msg;
  t.className = 'toast ' + (tipo || '');   // de paso pisa un .yendose a medio salir
  t.hidden = false;
  clearTimeout(toast._t); clearTimeout(toast._tf);
  toast._t = setTimeout(() => ocultarToast(t), 3200);
}
/* F4: el toast se despide con el fade de .yendose y recien despues hidden
   (mismo patron que el picker del muro). El boton de accion ("Deshacer") NO
   pasa por aca a proposito: si el usuario ya actuo, que desaparezca al toque
   es mejor feedback que cualquier fundido. */
function ocultarToast(t) {
  if (sinMovimiento()) { t.hidden = true; return; }
  t.classList.add('yendose');
  toast._tf = setTimeout(() => { t.hidden = true; t.classList.remove('yendose'); }, 180);
}
/* variante con accion inline ("Bloque eliminado — Deshacer"): mismo #toast y
   mas tiempo en pantalla, para llegar a tocar el boton. toast() comun sigue
   igual: su textContent pisa el boton viejo si quedo alguno. */
function toastAccion(msg, rotulo, fn, tipo) {
  const t = $('#toast');
  t.textContent = msg;
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'toast-btn'; b.textContent = rotulo;
  b.onclick = () => { clearTimeout(toast._t); t.hidden = true; fn(); };
  t.appendChild(b);
  t.className = 'toast ' + (tipo || '');
  t.hidden = false;
  clearTimeout(toast._t); clearTimeout(toast._tf);
  toast._t = setTimeout(() => ocultarToast(t), 6000);
}

/* F4: abrir/cerrar modales con salida suave. Cerrar era `hidden = true` en
   seco; el patron es el del picker del muro (#coPick en muro.js): clase
   .yendose -> el CSS despide la caja -> recien ahi hidden. El contador
   evita la carrera clasica: si algo REABRE el modal durante esos 150ms
   (dos confirmar() encadenados, p.ej.), el timeout viejo reconoce que ya
   no es el dueño y no esconde nada ajeno. Con "reducir movimiento" no hay
   teatro: se esconde al toque, como siempre. */
/* Los modales usan el armazón de la maqueta (.fondo + .modal): se muestran
   con la clase .on y el fondo queda trabado (body.trabado, sin scroll). */
function abrirModal(m) {
  if (!m) return;
  m._cierre = (m._cierre || 0) + 1;        // invalida cualquier cierre pendiente
  m.hidden = false;
  requestAnimationFrame(() => m.classList.add('on'));
  document.body.classList.add('trabado');
}
function esconderModal(m) {
  if (!m || !m.classList.contains('on')) return;
  m._cierre = (m._cierre || 0) + 1;
  m.classList.remove('on');
  if (!document.querySelector('.fondo.on')) document.body.classList.remove('trabado');
}

/* ===================================================================
   UN BOTON QUE ESTA TRABAJANDO

   Toda accion que va al servidor pasa por aca. Hace tres cosas que antes
   cada boton hacia (o no hacia) por su cuenta:

     1. El boton se apaga y dice que esta trabajando. Sin esto, guardar una
        publicacion con la red lenta eran CINCO SEGUNDOS sin ninguna senal:
        mismo texto, cursor de clickeable, sin aviso. Medido, no supuesto.
     2. No deja que entre un segundo click. Un doble click en "Publicar"
        creaba DOS publicaciones identicas en la cartelera de los
        vendedores — tambien medido.
     3. Si falla, se avisa. Antes, cuando el servidor devolvia un error, la
        promesa quedaba rechazada sin que nadie la atrapara: ni cartel, ni
        error, nada. La persona se iba creyendo que habia guardado.

   Devuelve lo que devuelva la accion, o undefined si fallo o si ya habia
   una en curso. `quieto:true` para el guardado automatico, que no tiene que
   gritar nada.
   =================================================================== */
async function conBoton(sel, trabajando, accion, { quieto = false } = {}) {
  const bs = (Array.isArray(sel) ? sel : [sel])
    .map(s => (typeof s === 'string' ? $(s) : s)).filter(Boolean);
  if (bs.some(b => b.dataset.ocupado === '1')) return;   // ya hay una en curso
  /* si el boton tiene un rotulo marcado, se escribe SOLO ahi: asi el icono
     SVG que lo acompaña sobrevive al "Publicando…" */
  const caras = bs.map(b => b.querySelector('[data-rotulo]') || b);
  const antes = caras.map(c => c.textContent);
  bs.forEach((b, i) => {
    b.dataset.ocupado = '1';
    b.disabled = true;
    if (trabajando) caras[i].textContent = trabajando;
  });
  if (trabajando && !quieto) toast(trabajando);
  try {
    return await accion();
  } catch (e) {
    console.error('[' + (trabajando || 'accion') + ']', e);
    if (!quieto) toast(e && e.message ? e.message : 'No se pudo completar', 'err');
  } finally {
    bs.forEach((b, i) => {
      delete b.dataset.ocupado;
      b.disabled = false;
      if (trabajando) caras[i].textContent = antes[i];
    });
  }
}

// ---------- estado git en la cabecera ----------
let gitPendiente = false;   // hay cambios commiteados sin subir, o sin commitear
function pintarGit(g) {
  const el = $('#gitState'), txt = $('#gitText'), btn = $('#btnPublicar');
  if (!g) return;
  if (g.limpio) {
    el.className = 'git clean';
    txt.textContent = g.ahead > 0 ? (g.ahead + ' commit(s) sin subir') : 'Todo publicado';
    btn.disabled = g.ahead === 0;
    gitPendiente = g.ahead > 0;
  } else {
    el.className = 'git dirty';
    txt.textContent = g.pendientes + ' cambio(s) sin publicar';
    btn.disabled = false;
    gitPendiente = true;
  }
  if (typeof actualizarBotones === 'function') actualizarBotones();   // refresca Guardar/Publicar del editor
}

function esc(s) { return (s || '').replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m])); }

/* ===================================================================
   LA TARJETA DE PUBLICAR

   Publicar es lo unico del panel que sale de esta computadora, y hasta
   ahora lo contaba un toast de 11px abajo de todo que dura 3 segundos.
   Dos cosas quedaban sin decir:
     1) que esta trabajando (se apreta y no pasa "nada visible");
     2) que subir al cerebro tarda ~3 s pero el VENDEDOR lo ve cuando
        Vercel termina de desplegar, ~30 s despues. Sin eso, la persona
        mira la intranet, ve lo viejo, y vuelve a publicar.
   La tarjeta cubre las dos etapas: barra en movimiento mientras trabaja,
   tilde verde + cuenta regresiva cuando termino, y se va sola.
   =================================================================== */
const SEGUNDOS_VERCEL = 30;
let pubCard = null, pubTimer = null, pubTick = null;

/* escribe el rotulo respetando el icono: los botones de la maqueta llevan un
   <svg> al lado del texto, y un textContent pelado se lo come. */
function rotularBoton(sel, texto) {
  const b = typeof sel === 'string' ? $(sel) : sel;
  if (!b) return;
  const cara = b.querySelector('[data-rotulo]');
  if (cara) cara.textContent = texto;
  else b.textContent = texto;
}

function pubCardEl() {
  if (pubCard && document.body.contains(pubCard)) return pubCard;
  pubCard = document.createElement('div');
  pubCard.className = 'pubcard';
  pubCard.id = 'pubCard';
  pubCard.setAttribute('role', 'status');
  pubCard.setAttribute('aria-live', 'polite');
  pubCard.innerHTML =
    '<div class="pubcard-fila">' +
      '<span class="pubcard-ic"><span class="aro"></span>' +
        '<svg class="pubcard-ok" viewBox="0 0 24 24" fill="none" stroke="currentColor">' +
        '<path d="M20 6 9 17l-5-5"/></svg></span>' +
      '<span class="pubcard-tx"><b data-tit>Publicando…</b><span data-sub></span>' +
        '<span class="pubcard-espera" data-espera hidden>' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:13px;height:13px">' +
          '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>' +
          '<span>Visible para los vendedores en <b data-seg></b></span></span>' +
      '</span>' +
    '</div>' +
    '<div class="pubcard-barra"><i></i></div>';
  /* se puede sacar del medio con un click: la cuenta de Vercel dura 30 s y
     mientras tanto la tarjeta tapa la paleta de bloques. */
  pubCard.title = 'Tocá para cerrar este aviso';
  pubCard.onclick = pubCardEsconder;
  document.body.appendChild(pubCard);
  return pubCard;
}

function pubCardMostrar(titulo, sub) {
  const c = pubCardEl();
  clearTimeout(pubTimer); clearInterval(pubTick);
  c.classList.remove('listo', 'error');
  c.querySelector('[data-tit]').textContent = titulo;
  c.querySelector('[data-sub]').textContent = sub || '';
  c.querySelector('[data-espera]').hidden = true;
  c.hidden = false;
  requestAnimationFrame(() => c.classList.add('on'));
}

/* el final feliz: tilde verde y la cuenta de lo que falta para que el
   vendedor lo vea. La tarjeta se va sola cuando termina esa cuenta. */
function pubCardListo() {
  const c = pubCardEl();
  c.classList.add('listo');
  c.querySelector('[data-tit]').textContent = '¡Publicado!';
  c.querySelector('[data-sub]').textContent = 'Ya salió de esta computadora.';
  /* La línea se rearma entera cada vez. Al llegar a cero se reemplaza por
     "ya lo están viendo", y eso se lleva puesto el <b data-seg>: en la
     publicación SIGUIENTE el contador ya no existía y reventaba con
     "Cannot set properties of null". */
  const esp = c.querySelector('[data-espera]');
  esp.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style="width:13px;height:13px">' +
    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>' +
    '<span>Visible para los vendedores en <b data-seg></b></span>';
  const seg = c.querySelector('[data-seg]');
  esp.hidden = false;
  let quedan = SEGUNDOS_VERCEL;
  seg.textContent = quedan + ' s';
  clearInterval(pubTick);
  pubTick = setInterval(() => {
    quedan--;
    if (quedan > 0) { seg.textContent = quedan + ' s'; return; }
    clearInterval(pubTick);
    esp.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'style="width:13px;height:13px"><path d="M20 6 9 17l-5-5"/></svg>' +
      '<span>Los vendedores ya lo están viendo.</span>';
    clearTimeout(pubTimer);
    pubTimer = setTimeout(pubCardEsconder, 2600);
  }, 1000);
}

function pubCardError(msg) {
  const c = pubCardEl();
  clearInterval(pubTick);
  c.classList.add('error');
  c.querySelector('[data-tit]').textContent = 'No se pudo publicar';
  c.querySelector('[data-sub]').textContent = msg || 'Probá de nuevo en un momento.';
  c.querySelector('[data-espera]').hidden = true;
  clearTimeout(pubTimer);
  pubTimer = setTimeout(pubCardEsconder, 7000);   // el error se queda mas
}

function pubCardEsconder() {
  if (!pubCard) return;
  clearInterval(pubTick); clearTimeout(pubTimer);
  pubCard.classList.remove('on');
  const c = pubCard;
  setTimeout(() => { if (c && !c.classList.contains('on')) c.hidden = true; }, 220);
}

// ---------- refrescos ----------
async function refrescarGit() {
  // en modo cerebro (publicacion directa) el estado de git local no aplica:
  // ocultamos el pill y NO corremos git; el boton Publicar queda siempre activo.
  if (MODO_CEREBRO) {
    const gs = $('#gitState'); if (gs) gs.hidden = true;
    actualizarPublicarHome();
    if (typeof actualizarBotones === 'function') actualizarBotones();
    return;
  }
  try { pintarGit(await api('/api/estado-git')); } catch (e) {}
}

// ---------- publicar ----------
/* `sinPreguntar` lo usa el compositor de la cartelera: ahí la persona ya
   apretó un botón que dice "Publicar", y volver a preguntarle si quiere
   publicar es preguntarle dos veces lo mismo.
   ⚠️ Va SEPARADO de `_reintento` a propósito. `_reintento` significa "ya
   pedimos la clave una vez, no la vuelvas a pedir"; si el compositor lo
   reusara para saltear la pregunta, una clave faltante terminaría en un
   return mudo en vez de pedirla. */
async function publicarCambios(_reintento, sinPreguntar) {
  // Antes usaba el confirm() del navegador, que arranca con "127.0.0.1 dice" en
  // fuente del sistema: para alguien no técnico eso parece un error de Windows,
  // no una pregunta del panel. Y además ahora decimos QUÉ se sube.
  if (!_reintento && !sinPreguntar) {
    const nombres = (Array.isArray(MODULOS) ? MODULOS : [])
      .filter(m => editados.has(m.key)).map(m => '·  ' + m.title);
    const detalle = nombres.length
      ? 'Se van a publicar estos módulos:\n' + nombres.join('\n')
      : 'No hay cambios anotados en esta computadora. Se sube igual lo que haya.';
    if (!await confirmar(detalle + '\n\nLos vendedores lo ven en ~30 segundos.',
      'Sí, publicar', 'Publicar al sitio', 'ok')) return;
  }
  const btns = [$('#btnPublicar'), $('#detPublicar')];
  btns.forEach(b => b && (b.disabled = true));
  rotularBoton('#detPublicar', 'Publicando…');
  pubCardMostrar('Publicando…', 'Subiendo los cambios al sitio.');
  try {
    const r = await api('/api/publicar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    if (r.falta_token) {
      btns.forEach(b => b && (b.disabled = false));
      // la tarjeta se va: lo que sigue es una pregunta, no un trabajo en curso
      pubCardEsconder();
      if (!_reintento && await pedirToken()) return publicarCambios(true, sinPreguntar);
      return;
    }
    /* ⚠️ El aviso de error va colgado de `!r.ok` y de nada mas. Antes el
       `else` colgaba de `if (r.ok && typeof actualizarBotones === 'function')`,
       asi que el dia que alguien renombre actualizarBotones, un publicado
       EXITOSO iba a avisar "No se pudo publicar". Hoy no pasa de casualidad. */
    if (!r.ok) {
      console.error('Publicar:', r.log);
      const detalle = (r.log || '').split('\n').pop() || 'probá de nuevo';
      pubCardError(detalle);
      toast('No se pudo publicar: ' + detalle, 'err');
    } else {
      if (r.nada) {
        // no hubo nada que subir: no corresponde la cuenta de Vercel
        pubCardEsconder();
        toast('No había cambios para publicar');
      } else {
        pubCardListo();
      }
      limpiarEditados();
      if (typeof actualizarBotones === 'function') actualizarBotones();
    }
    return !!r.ok;
  } catch (e) {
    console.error('Publicar:', e);
    pubCardError(e && e.message ? e.message : '');
    toast(e.message, 'err');
    return false;
  } finally {
    // en el `finally` y no despues del try: con un `return` adentro, la linea
    // de abajo no llegaba a correr y los botones quedaban apagados para siempre
    btns.forEach(b => b && (b.disabled = false));
    // el rotulo definitivo lo decide actualizarBotones (Publicar / Publicado ✓)
    if (typeof actualizarBotones === 'function') actualizarBotones();
  }
}

// pide y guarda la clave de publicacion (una sola vez por computadora)
async function pedirToken() {
  const t = prompt('Pegá tu CLAVE DE PUBLICACIÓN (te la pasa el administrador).\nSe guarda una sola vez en esta computadora.');
  if (!t || !t.trim()) return false;
  try {
    const r = await api('/api/set-publish-token', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: t.trim() }) });
    if (r.ok) { toast('Clave guardada ✓', 'ok'); return true; }
    toast('No se pudo guardar la clave', 'err'); return false;
  } catch (e) { toast(e.message, 'err'); return false; }
}
// ---------- rol: central vs colaborador (ambos publican DIRECTO via el cerebro) ----------
let ES_CENTRAL = true;   // hasta que /api/config diga lo contrario
let MODO_CEREBRO = true; // publicacion directa: se ignora el estado de git local

async function cargarConfig() {
  let cfg;
  try { cfg = await api('/api/config'); }
  catch (e) { return; }                 // sin config => se comporta como central
  ES_CENTRAL = cfg.es_central !== false;
  MODO_CEREBRO = cfg.cerebro !== false;
  // la direccion del sitio online: para armar links que sirven fuera de esta PC
  window.WEB_PUBLICA = (cfg.web_publica || '').replace(/\/$/, '');
  const nv = $('#navVersion');
  if (nv) {
    /* La que se ve es la version PUBLICA (texto libre, ej "1.2.2"). La interna
       (`cfg.version`, un entero) es la que usa el auto-update y no se muestra:
       al equipo no le dice nada y confundirlas rompe el mecanismo. Queda en el
       title, que sirve para soporte. */
    const pub = cfg.version_publica || cfg.version;
    if (pub) nv.textContent = 'Versión ' + pub;
    nv.title = (cfg.version_label || '') + (cfg.version ? '  ·  build ' + cfg.version : '');
  }
  aplicarRol(cfg);
}

function aplicarRol(cfg) {
  const central = ES_CENTRAL;
  // PUBLICACION DIRECTA: todos publican con el mismo boton (via el cerebro)
  $('#btnPublicar').hidden = false;
  $('#btnBandeja').hidden  = true;    // el modelo de aprobaciones ya no se usa
  $('#btnEnviar').hidden   = true;
  /* "Traer última versión" baja una copia desde la central, y eso necesita
     que la computadora tenga una central a la que llegar. Desde que las
     sucursales se instalan sin Tailscale, muchas no la tienen: el botón
     estaba a la vista y lo único que hacía era dar un error. Se muestra sólo
     si hay una dirección de central configurada. */
  const hayCentral = !!(cfg && (cfg.central_url || '').trim());
  $('#btnTraer').hidden    = central || !hayCentral;
  // con el cerebro, el estado de git local no aplica
  const gs = $('#gitState');
  if (gs) gs.hidden = true;
  // el selector de sucursal del sidebar muestra quién es esta computadora
  const nombre = central ? 'Central' : ((cfg && cfg.usuario) || 'Sucursal');
  const sn = $('#sucNombre'), sa = $('#sucAv'), sb2 = $('#sucBtn');
  if (sn) sn.textContent = nombre;
  if (sa) sa.textContent = (nombre.trim().charAt(0) || 'C').toUpperCase();
  if (sb2) sb2.title = central ? 'Esta computadora publica al sitio.' : 'Publicás directo al sitio online.';
  // botón de publicar dentro del editor. Va por rotularBoton y no por
  // textContent: el botón lleva un <svg> al lado del texto y un textContent
  // pelado se lo comía (quedaba "Publicar" sin el ícono del avión).
  rotularBoton('#detPublicar', 'Publicar');
}

function accionPublicarEditor() { return publicarCambios(); }

// OJO: NO poner `= publicarCambios` a secas. El handler recibe el evento del
// click como primer argumento, que cae en `_reintento` y al ser truthy saltea
// la confirmación: durante mucho tiempo publicar desde la home no preguntó nada.
$('#btnPublicar').onclick = () => publicarCambios();
$('#btnEnviar').onclick = () => enviarPropuesta();
$('#btnTraer').onclick = () => traerUltima();
$('#detPublicar').onclick = accionPublicarEditor;
$('#btnCerrar').onclick = async () => {
  if (!await confirmar('¿Cerrar el panel? Lo que no publicaste queda guardado en esta computadora.', 'Cerrar', 'Cerrar el panel')) return;
  try { await api('/api/shutdown', { method: 'POST' }); } catch (e) {}
  document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:Montserrat,sans-serif;color:#5B574F;font-size:16px;text-align:center;padding:24px">El panel se cerró. Ya podés cerrar esta pestaña. 👋</div>';
};

// ---------- colaborador: enviar propuesta / traer última ----------
async function enviarPropuesta() {
  const msg = prompt('¿Querés dejar una nota para quien apruebe? (opcional)\nEj: "Actualicé las promos bancarias de julio."') || '';
  if (msg === null) return;
  const btns = [$('#btnEnviar'), $('#detPublicar')];
  btns.forEach(b => b && (b.disabled = true));
  toast('Enviando cambios a la central…');
  try {
    const r = await api('/api/enviar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensaje: msg })
    });
    if (r.ok) toast('✓ Enviado. La central va a revisar tus cambios.', 'ok');
    else toast(r.error || 'No se pudo enviar', 'err');
  } catch (e) { toast(e.message, 'err'); }
  btns.forEach(b => b && (b.disabled = false));
}

async function traerUltima() {
  const btn = $('#btnTraer');
  const sigue = await confirmar(
    'Se va a reemplazar tu copia local con la última versión publicada. Los cambios que no hayas enviado se pierden.',
    'Traer última versión', 'Traer última versión');
  if (!sigue) return;
  const bar = $('#traerBar'), txt = bar.querySelector('.traer-txt'), rel = bar.querySelector('.traer-relleno');
  const pinta = (m, pct) => {
    if (m) txt.textContent = m;
    if (pct > 0) { rel.classList.remove('sin-total'); rel.style.width = pct + '%'; }
    else rel.classList.add('sin-total');
  };
  if (btn) btn.disabled = true;
  bar.hidden = false; pinta('Conectando con el cerebro…', 0);
  try {
    const r = await api('/api/traer', { method: 'POST' });
    if (!r.ok || !r.job) throw new Error(r.error || 'No se pudo empezar la descarga');
    for (;;) {
      await new Promise(res => setTimeout(res, 600));
      let j;
      try { j = await api('/api/job?id=' + encodeURIComponent(r.job)); }
      catch (e) { continue; }                    // un tropiezo de red no corta la espera
      if (j.estado === 'error') throw new Error(j.error || 'No se pudo traer');
      pinta(j.msg, j.pct | 0);
      if (j.estado === 'listo') break;
    }
    pinta('¡Listo! Recargando el panel…', 100);
    setTimeout(() => location.reload(), 700);
  } catch (e) {
    bar.hidden = true;
    if (btn) btn.disabled = false;
    toast(e.message, 'err');
  }
}

function consola(texto, titulo) {
  $('#consoleTitle').textContent = titulo || 'Salida';
  $('#consoleBody').textContent = texto;
  $('#console').hidden = false;
}
$('#consoleClose').onclick = () => $('#console').hidden = true;

/* ===================================================================
   MÓDULOS (Fase 2) — lista de botones del menú: agregar/editar/quitar
   =================================================================== */

// SVG de los iconos (copia de los del sitio) para mostrarlos en el panel
const ICONS = {
  book:'<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
  card:'<rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/>',
  tag:'<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>',
  truck:'<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
  award:'<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>',
  search:'<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  chart:'<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
  play:'<circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>',
  ext:'<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
  clock:'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
  file:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
  check:'<polyline points="20 6 9 17 4 12"/>',
  users:'<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  user:'<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  map:'<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
  mic:'<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/>',
  shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  box:'<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
  store:'<path d="M3 9l1.5-5h15L21 9"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/>',
  ruler:'<rect x="2" y="7" width="20" height="10" rx="1"/><line x1="6" y1="7" x2="6" y2="11"/><line x1="10" y1="7" x2="10" y2="11"/><line x1="14" y1="7" x2="14" y2="11"/><line x1="18" y1="7" x2="18" y2="11"/>',
  whatsapp:'<path d="M3 21l1.65-4.8a8.5 8.5 0 1 1 3.4 3.05L3 21z"/><path d="M9 8.5c0 4 2.5 6.5 6.5 6.5l1-1.8-2-1-.9 1c-1.2-.5-2.1-1.4-2.6-2.6l1-.9-1-2-1.5.3a1.5 1.5 0 0 0-.5 1.2z"/>',
  chatBubble:'<path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.8-5.5A8 8 0 1 1 21 12z"/><line x1="8.5" y1="11" x2="15.5" y2="11"/><line x1="8.5" y1="14" x2="13" y2="14"/>',
  megaphone:'<path d="M3 11v2a1 1 0 0 0 1 1h2l9 5V5L6 10H4a1 1 0 0 0-1 1z"/><path d="M18 8a5 5 0 0 1 0 8"/><line x1="7" y1="14" x2="8" y2="19"/>',
  lock:'<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/><line x1="12" y1="15" x2="12" y2="17"/>',
  funnel:'<path d="M3 5h18l-7 8v6l-4 2v-8L3 5z"/>',
  refresh:'<path d="M4 12a8 8 0 0 1 13.7-5.6L20 8"/><path d="M20 4v4h-4"/><path d="M20 12a8 8 0 0 1-13.7 5.6L4 16"/><path d="M4 20v-4h4"/>',
  verified:'<path d="M12 2l2.3 1.6 2.8-.2 1 2.6 2.3 1.6-.8 2.7.8 2.7-2.3 1.6-1 2.6-2.8-.2L12 22l-2.3-1.6-2.8.2-1-2.6-2.3-1.6.8-2.7-.8-2.7 2.3-1.6 1-2.6 2.8.2L12 2z"/><path d="M9 12l2 2 4-4"/>',
  phone:'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
  reply:'<polyline points="9 17 4 12 9 7"/><path d="M20 18v-2a4 4 0 0 0-4-4H4"/>',
  home:'<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  layers:'<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
  arrowR:'<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
  arrowL:'<line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>',
  arrowLR:'<polyline points="7 7 2 12 7 17"/><polyline points="17 7 22 12 17 17"/><line x1="2" y1="12" x2="22" y2="12"/>',
  arrowDR:'<polyline points="15 10 20 15 15 20"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/>',
  x:'<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
};
const ICON_ORDER = ['download','book','play','chart','whatsapp','award','search','image','tag','card',
  'truck','store','box','ruler','shield','users','user','map','phone','chatBubble','megaphone',
  'mic','clock','funnel','refresh','verified','reply','lock','ext','home','layers','check'];
const COLORS = [
  { v: '--c-hudson', hex: '#1A1A2E' }, { v: '--c-caba', hex: '#2C6E8A' },
  { v: '--c-canning', hex: '#3A7A55' }, { v: '--c-norcenter', hex: '#8A5A2C' },
  { v: '--c-success', hex: '#1A6A3A' }, { v: '--c-warn', hex: '#9A6A00' },
  { v: '--c-danger', hex: '#B4231F' }, { v: '--c-info', hex: '#1A4A8A' },
];
const HEX = Object.fromEntries(COLORS.map(c => [c.v, c.hex]));
/* La cartelera se llamaba 'muro' hasta agosto de 2026. Lo ya guardado con el
   nombre viejo se sigue leyendo; lo que se guarda de ahora en más va como
   'cartelera'. Un solo lugar decide, así no quedan chequeos sueltos. */
const esCartelera = c => !!c && (c.tipo === 'cartelera' || c.tipo === 'muro');
const iconSvg = k => `<svg viewBox="0 0 24 24">${ICONS[k] || ICONS.layers}</svg>`;

let MODULOS = [];
const GRUPOS_DESCARGABLES = ['fechas_especiales', 'promos_bancarias', 'promos_mensuales', 'entregas', 'porque'];

// estado de la pantalla de detalle (working copy)
let det = null, detIdx = null, detNew = false, detOriginal = null;

async function cargarModulos() {
  try {
    const d = await api('/api/modulos');
    MODULOS = d.modulos || [];
    pintarModulos();
  } catch (e) { toast(e.message, 'err'); }
}

function pintarModulos() {
  const cont = $('#modList');
  cont.innerHTML = '';
  /* La Cartelera NO se lista: no es un módulo, es la portada. Está guardada
     acá adentro por comodidad de almacenamiento (hereda respaldo, validación
     y publicación sin un segundo camino), pero mostrarla la hacía parecer una
     sección más —numerada y arrastrable entre las diez reales— y abría una
     segunda puerta a una pantalla que ya tiene la suya. Se edita desde la
     sección Cartelera. */
  const visibles = MODULOS.map((m, idx) => ({ m, idx }))
                          .filter(x => !esCartelera(x.m.content));
  visibles.forEach((x, pos) => cont.appendChild(modCard(x.m, x.idx, pos + 1)));
  // la tarjeta punteada de "Agregar módulo" cierra la grilla (maqueta)
  const add = document.createElement('button');
  add.type = 'button'; add.className = 'card mod nuevo-mod';
  add.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 5v14M5 12h14"/></svg>Agregar módulo';
  add.onclick = nuevoModulo;
  cont.appendChild(add);
  if (typeof pintarContadores === 'function') pintarContadores();
  actualizarPublicarHome();
  listaOrdenable(cont, {
    item: '.mod:not(.nuevo-mod)', grip: '.ord',
    alSoltar: (desde, hasta) => {
      /* ⚠️ `desde` y `hasta` son posiciones de la lista VISIBLE, y la Cartelera
         no está en ella. Aplicarlas directo sobre MODULOS movería el módulo
         equivocado. Se reordena la lista visible y se rearma MODULOS con la
         Cartelera adelante — su posición no la ve nadie: la intranet la saca
         de los módulos y el panel no la lista. */
      const lista = visibles.map(x => x.m);
      lista.splice(hasta, 0, lista.splice(desde, 1)[0]);
      const portada = MODULOS.filter(m => esCartelera(m.content));
      MODULOS.length = 0;
      MODULOS.push.apply(MODULOS, portada.concat(lista));
      pintarModulos();                       // renumera las posiciones
      persistModulos('Orden actualizado.').catch(err => toast(err.message, 'err'));
    },
  });
}

/* ===================================================================
   BUSCAR EN TODO EL PANEL
   Con 9 módulos y bibliotecas adentro, encontrar "dónde estaba el texto de
   garantía" obligaba a abrir módulo por módulo. Esto mira TODO el contenido
   guardado, incluidos los documentos de cada biblioteca.
   =================================================================== */
function textoDeBloque(b) {
  if (!b || typeof b !== 'object') return '';
  const partes = [];
  const push = v => { if (typeof v === 'string' && v.trim()) partes.push(txtOf(v)); };
  // OJO: no todo lo que se llama igual es una lista. En el bloque "tarjetas",
  // `cols` es un NÚMERO (cuántas entran por fila), no un arreglo de columnas.
  const lista = v => (Array.isArray(v) ? v : []);
  ['html', 'texto', 'titulo', 'label', 'nombre', 'caption', 'alt', 'tag', 'resp', 'n'].forEach(k => push(b[k]));
  lista(b.items).forEach(it => {
    if (typeof it === 'string') return push(it);
    if (!it) return;
    ['html', 'label', 'valor', 'pie', 'nombre', 'suc', 'extra', 'titulo', 'texto', 'chip', 'puesto'].forEach(k => push(it[k]));
  });
  lista(b.steps).forEach(s => s && ['titulo', 'desc'].forEach(k => push(s[k])));
  lista(b.mensajes).forEach(m => push(typeof m === 'string' ? m : (m || {}).html));
  lista(b.tarjetas).forEach(c => c && ['texto', 'btnTexto'].forEach(k => push(c[k])));
  lista(b.cols).forEach(c => push((c || {}).h));
  lista(b.filas).forEach(f => lista((f || {}).celdas).forEach(push));
  return partes.join(' · ');
}

function buscarEnTodo(q) {
  const n = sinTilde(q).trim();
  if (n.length < 2) return [];
  const res = [];
  const mirar = (m, idx, bloques, docIdx, docTitulo) => {
    const texto = (bloques || []).map(textoDeBloque).join(' · ');
    const donde = sinTilde(texto);
    const pos = donde.indexOf(n);
    if (pos === -1) return;
    const desde = Math.max(0, pos - 45);
    res.push({
      idx, key: m.key, titulo: m.title, docIdx, docTitulo,
      frag: (desde ? '…' : '') + texto.slice(desde, pos + n.length + 65).trim() + '…',
    });
  };
  MODULOS.forEach((m, idx) => {
    const c = m.content || {};
    // el nombre del módulo también cuenta
    if (sinTilde((m.title || '') + ' ' + (m.desc || '')).includes(n)) {
      res.push({ idx, key: m.key, titulo: m.title, frag: m.desc || 'Nombre del módulo' });
    }
    if (c.tipo === 'coleccion' || esCartelera(c)) (c.docs || []).forEach((d, di) => mirar(m, idx, d.bloques, di, d.titulo));
    else if (c.tipo === 'bloques') mirar(m, idx, c.bloques);
  });
  return res;
}

function pintarBusqueda() {
  const q = $('#buscarTodo').value;
  const caja = $('#buscarRes'), lista = $('#modList');
  const hay = sinTilde(q).trim().length >= 2;
  caja.hidden = !hay; lista.hidden = hay;
  $('#btnAddModulo2').hidden = hay;
  if (!hay) return;
  const res = buscarEnTodo(q);
  caja.innerHTML = '';
  if (!res.length) {
    caja.innerHTML = '<div class="buscar-nada">No encontré <b>' + esc(q) + '</b> en ningún módulo.</div>';
    return;
  }
  const t = document.createElement('div'); t.className = 'buscar-cuenta';
  t.textContent = res.length === 1 ? '1 resultado' : (res.length + ' resultados');
  caja.appendChild(t);
  res.forEach(r => {
    const a = document.createElement('button'); a.type = 'button'; a.className = 'buscar-item';
    a.innerHTML = '<div class="buscar-t">' + esc(r.titulo) +
      (r.docTitulo ? ' <span class="buscar-doc">› ' + esc(r.docTitulo) + '</span>' : '') + '</div>' +
      '<div class="buscar-f">' + esc(r.frag) + '</div>';
    a.onclick = async () => {
      $('#buscarTodo').value = ''; pintarBusqueda();
      await openDetalle(r.idx);
      if (r.docIdx != null) setTimeout(() => abrirDoc(r.docIdx), 250);
    };
    caja.appendChild(a);
  });
}
if ($('#buscarTodo')) {
  $('#buscarTodo').oninput = pintarBusqueda;
  $('#buscarTodo').onkeydown = e => { if (e.key === 'Escape') { e.target.value = ''; pintarBusqueda(); } };
}

// "Editado" = módulo guardado pero todavía NO publicado (se limpia al publicar)
const EDITADOS_KEY = 'mys_editados_sin_publicar';
let editados = new Set();
try { const v = localStorage.getItem(EDITADOS_KEY); if (v) editados = new Set(JSON.parse(v)); } catch (e) {}
function guardarEditados() { try { localStorage.setItem(EDITADOS_KEY, JSON.stringify([...editados])); } catch (e) {} }
function marcarEditado(key) { if (!key) return; editados.add(key); guardarEditados(); actualizarPublicarHome(); }
function limpiarEditados() { editados.clear(); guardarEditados(); if (Array.isArray(MODULOS)) pintarModulos(); actualizarPublicarHome(); }

/* El panel YA sabe cuántos módulos faltan publicar (`editados`), pero la home
   mostraba siempre el mismo botón, tocaras 3 módulos o ninguno. Ahora lo dice.
   Nunca se deshabilita: republicar es inofensivo, y un botón apagado en la
   acción más importante genera más dudas que las que resuelve.
   Límite honesto: `editados` vive en el localStorage de ESTA computadora, así
   que no sabe lo que editó otra sucursal. Es mejor que nada, no es la verdad
   del servidor. */
function actualizarPublicarHome() {
  const b = $('#btnPublicar'); if (!b) return;
  const n = MODO_CEREBRO ? editados.size : (gitPendiente ? -1 : 0);
  b.disabled = false;
  if (n === 0) {
    b.textContent = 'Todo publicado ✓';
    b.classList.remove('btn-pub'); b.classList.add('btn-done');
    b.title = 'El sitio online está igual que este panel.';
  } else {
    b.textContent = n > 0 ? ('Publicar ' + n + (n > 1 ? ' cambios' : ' cambio')) : 'Publicar cambios';
    b.classList.add('btn-pub'); b.classList.remove('btn-done');
    b.title = 'Sube al sitio lo que editaste. Se ve en ~30 segundos.';
  }
}

/* `pos` es el numero que se muestra. Va aparte de `idx` porque la Cartelera
   no se lista: si se usara idx+1, la numeracion arrancaria en 2. */
function modCard(m, idx, pos) {
  // tarjeta de la maqueta: ícono neutro + orden + título/desc + pie con meta
  const c = document.createElement('button');
  c.type = 'button';
  const dNov = diasDeNovedad(m.actualizado);
  const esNuevo = dNov !== null && dNov <= 14;
  c.className = 'card mod' + (esNuevo ? ' con-nuevo' : '') + (m.hidden ? ' mod-oculto' : '');
  c.dataset.idx = idx;
  const cu = m.content || {};
  let meta = '';
  if (cu.tipo === 'coleccion') {
    const n = (cu.docs || []).length;
    meta = n + ' ' + (cu.palabra || 'documento') + (n === 1 ? '' : 's');
  } else if (cu.tipo === 'bloques') {
    const n = (cu.bloques || []).length;
    meta = n + (n === 1 ? ' bloque' : ' bloques');
  } else if (cu.tipo === 'embed') meta = 'Web embebida';
  else if (m.key === 'descargables') meta = 'Galería de placas';
  else meta = 'Diseño del sistema';
  const chips = [];
  if (!m.ready) chips.push('<span class="chip-pronto">Próximamente</span>');
  if (editados.has(m.key)) chips.push('<span class="chip-pronto chip-pend">Sin publicar</span>');
  if (m.hidden) chips.push('<span class="chip-pronto">No se ve en el menú</span>');
  c.innerHTML = `
    <div class="mod-cab">
      <span class="mod-ic">${iconSvg(m.icon)}</span>
      ${esNuevo ? '<span class="chip-nuevo">NUEVO</span>' : ''}<span class="ord" title="Arrastrá para ordenar" style="margin-left:${esNuevo ? '8px' : 'auto'}">${String(pos == null ? idx + 1 : pos).padStart(2, '0')}</span>
    </div>
    <b>${esc(m.title)}</b>
    <p>${esc(m.desc || '')}</p>
    <div class="mod-pie">
      ${m.ready && !m.hidden && !editados.has(m.key) ? '<span>' + esc(meta) + '</span>' : chips.join('')}
      <span class="ir">Abrir <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="m9 18 6-6-6-6"/></svg></span>
    </div>`;
  c.onclick = e => { if (!e.target.closest('.ord')) openDetalle(idx); };
  return c;
}

async function persistModulos(msg) {
  const r = await api('/api/modulos', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ modulos: MODULOS })
  });
  MODULOS = r.modulos; pintarModulos();
  if (typeof renderMuro === 'function' && !$('#viewMuro').hidden) renderMuro();
  if (msg !== false) toast(msg || 'Módulos guardados. Acordate de Publicar para subirlo.', 'ok');
  refrescarGit();
}

/* ===================================================================
   PANTALLA DE DETALLE DE MÓDULO (apariencia + contenido + editor visual)
   =================================================================== */
const nuevoModulo = () => {
  det = { title: '', desc: '', icon: 'layers', color: '--c-hudson', ready: true, builtin: false };
  detNew = true; detIdx = null;
  renderDetalle();
};
$('#btnAddModulo').onclick = nuevoModulo;
// el mismo botón al final de la lista: el módulo nuevo aparece JUSTO ahí
if ($('#btnAddModulo2')) $('#btnAddModulo2').onclick = nuevoModulo;

function openDetalle(idx) {
  det = JSON.parse(JSON.stringify(MODULOS[idx]));   // copia de trabajo
  detIdx = idx; detNew = false;
  renderDetalle();
}

function mostrarDetalle(on) {
  // El estado del editor se fija PRIMERO: así, al salir, volverASeccion ya lo
  // ve cerrado y el guard del menú (irASeccion, muro.js) no vuelve a entrar.
  $('#viewDetalle').hidden = !on;
  document.body.classList.toggle('editing', on);
  // el rediseño tiene varias secciones: se esconden todas y al salir se vuelve
  // a la que estabas (lo resuelve volverASeccion, de muro.js)
  if (on) document.querySelectorAll('.lienzo > .main-sec').forEach(v => {
    if (v.id !== 'viewDetalle') v.hidden = true;
  });
  else if (typeof volverASeccion === 'function') volverASeccion();
  else $('#viewModulos').hidden = false;
  if (!on) { pararEdicion(); editorSnapshot = null; $('#detMoreMenu').hidden = true; cargarModulos(); }
  window.scrollTo(0, 0);
}

async function renderDetalle() {
  // --- apariencia ---
  $('#detBarTitle').textContent = detNew ? 'Nuevo módulo' : (det.title || 'Módulo');
  /* El mismo nombre, tambien arriba del papel: el canvas arrancaba
     directo en el primer bloque y no se veia QUE se estaba editando. */
  var _nom = $('#gbDocNom'); if (_nom) _nom.textContent = detNew ? 'Nuevo módulo' : (det.title || 'módulo');
  var _sub = $('#gbDocSub');
  if (_sub) {
    var _n = (det.bloques && det.bloques.length) || 0;
    _sub.textContent = 'Se ve en el menú de la intranet' + (_n ? (' · ' + _n + (_n === 1 ? ' bloque' : ' bloques')) : '');
  }
  $('#dTitle').value = det.title || '';
  $('#dDesc').value = det.desc || '';
  $('#dReady').checked = det.ready !== false;
  pintarDIconGrid(); pintarDColorGrid(); pintarDPreview();
  $('#detDelete').hidden = detNew;   // se puede eliminar cualquier módulo ya guardado
  $('#detHide').hidden = detNew;
  $('#detHide').textContent = det.hidden ? 'Mostrar en el menú' : 'Ocultar del menú';
  actualizarMenuMas();
  // --- contenido ---
  await renderContenidoEditor();
  // al entrar se arranca en la paleta con el buscador limpio; apariencia abierta
  // solo en módulo nuevo (que necesita título sí o sí)
  const bus = $('#gbBuscar'); if (bus) bus.value = '';
  gbPane('agregar');
  $('#apSec').classList.toggle('open', detNew);
  mostrarDetalle(true);
  setVista('desktop');
  editorSnapshot = estadoEditor();   // base para detectar cambios sin guardar
  arrancarEdicion();                 // botones + autoguardado + historial de deshacer
}

function pintarDIconGrid() {
  const g = $('#dIconGrid'); g.innerHTML = '';
  ICON_ORDER.forEach(k => {
    const b = document.createElement('button');
    b.className = 'icon-opt' + (k === det.icon ? ' sel' : '');
    b.innerHTML = iconSvg(k);
    b.onclick = () => { det.icon = k; pintarDIconGrid(); pintarDPreview(); };
    g.appendChild(b);
  });
}
function pintarDColorGrid() {
  const g = $('#dColorGrid'); g.innerHTML = '';
  COLORS.forEach(c => {
    const b = document.createElement('button');
    b.className = 'color-opt' + (c.v === det.color ? ' sel' : '');
    b.style.background = c.hex;
    b.onclick = () => { det.color = c.v; pintarDColorGrid(); pintarDPreview(); };
    g.appendChild(b);
  });
}
function pintarDPreview() {
  $('#detPreview').innerHTML = `
    <span class="mod-ic" style="background:${HEX[det.color]}">${iconSvg(det.icon)}</span>
    <div class="mod-info">
      <div class="mod-t">${esc($('#dTitle').value || 'Título del módulo')}</div>
      <div class="mod-d">${esc($('#dDesc').value || 'Subtítulo…')}</div>
    </div>`;
}
$('#dTitle').oninput = pintarDPreview;
$('#dDesc').oninput = pintarDPreview;

async function renderContenidoEditor() {
  const key = det.key;
  // 'descargables' usa el gestor de galería SALVO que ya tenga contenido de bloques (migrado) → ahí va al editor de bloques (reversible)
  const esBloques = det.content && (det.content.tipo === 'bloques' || det.content.tipo === 'coleccion');
  if (key === 'descargables' && !esBloques) {
    mostrarPane('galeria');
    $('#detRestore').hidden = true;
    $('#dModoFld').hidden = true;
    $('#docBar').hidden = true;
    COLECCION = null; DOC_IDX = null; ES_MURO = false;   /* que no quede sucio de otro módulo */
    moveApA('#galApSlot');
    await renderDescargables();
    return;
  }
  $('#dModoFld').hidden = false;
  let data = {};
  if (key) { try { data = await api('/api/contenido?key=' + encodeURIComponent(key)); } catch (e) {} }
  detOriginal = data.original || null;
  $('#detRestore').hidden = !det.builtin;     // "restaurar diseño del sistema" solo aplica a builtin

  // --- muro: el módulo es un feed de publicaciones ---
  if (esCartelera(det.content)) {
    COLECCION = JSON.parse(JSON.stringify(det.content.docs || []));
    ES_MURO = true; COL_PALABRA = 'publicación';
    COLECCION.forEach(prepararPost);
    DOC_IDX = null; BLOQUES = []; PRESENTACION = false; SEL = null;
    irALista();
    return;
  }
  // --- biblioteca: el módulo guarda varios documentos ---
  if (det.content && det.content.tipo === 'coleccion') {
    COLECCION = JSON.parse(JSON.stringify(det.content.docs || []));
    ES_MURO = false;
    COL_PALABRA = det.content.palabra || '';
    DOC_IDX = null; BLOQUES = []; PRESENTACION = false; SEL = null;
    irALista();
    return;
  }
  // --- documento único ---
  COLECCION = null; DOC_IDX = null; ES_MURO = false;
  $('#docBar').hidden = true;
  mostrarPane('bloques');
  BLOQUES = migrarABloques(det.content || null, detOriginal);
  PRESENTACION = !!(det.content && det.content.presentacion);
  SEL = BLOQUES.length ? 0 : null;
  pintarModo();
  renderGbEditor();
}

/* ===================================================================
   EDITOR DE BLOQUES estilo WordPress Gutenberg (canvas editable + panel)
   =================================================================== */
let BLOQUES = [];
let SEL = null;               // índice del bloque seleccionado
let PRESENTACION = false;     // el documento se ve como diapositivas en vez de página
let COLECCION = null;         // si el módulo es una BIBLIOTECA, acá viven sus documentos
let DOC_IDX = null;           // cuál de esos documentos está abierto en el editor
let COL_PALABRA = '';         // cómo llama el usuario a cada uno ("reporte", "capacitación"…)
let ES_MURO = false;          // la colección es un MURO: sus piezas son publicaciones con autor y fecha

// la palabra con la que el panel se refiere a cada pieza de la biblioteca
function palabra() { return (COL_PALABRA || '').trim().toLowerCase() || 'documento'; }
function palabraM() { return mayus(palabra()); }
function palabras() {
  const p = palabra();
  if (/[sz]$/.test(p)) return p;
  if (/ción$/.test(p)) return p.replace(/ción$/, 'ciones');     // capacitación → capacitaciones
  if (/[aeiou]$/.test(p)) return p + 's';
  return p + 'es';                                              // informe → informes lo cubre la vocal
}
function mayus(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
// "el reporte" / "la capacitación": las palabras terminadas en -ción o -a van en femenino
function fem() { return /(ción|dad|a)$/.test(palabra()); }
function elLa() { return fem() ? 'la' : 'el'; }
function unUna() { return fem() ? 'una' : 'un'; }

function mostrarPane(p) {
  document.querySelectorAll('#editorBody .cpane').forEach(el => el.hidden = el.dataset.pane !== p);
}
function modoActual() {
  if (COLECCION) return ES_MURO ? 'muro' : 'biblioteca';
  return PRESENTACION ? 'presentacion' : 'pagina';
}
function nuevoId() { return 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

// ---- interruptor Página / Presentación / Biblioteca (acordeón de Apariencia) ----
function pintarModo() {
  const modo = modoActual();
  $('#dModo').querySelectorAll('.seg-b').forEach(b => b.classList.toggle('active', b.dataset.modo === modo));
  const notas = {
    muro: 'El módulo es un <b>muro de novedades</b>: las publicaciones se ven todas seguidas, la más nueva arriba, con quién la publicó y cuándo. Sirve para comunicar al equipo.',
    biblioteca: 'El módulo guarda <b>varios documentos</b> y el vendedor elige cuál abrir. Cada documento se ve como página o presentación por separado.',
    presentacion: BLOQUES.some(b => b.t === 'diapo')
      ? 'Se ve a pantalla completa, con flechas y menú de diapositivas.'
      : 'Se ve a pantalla completa. Agregá bloques <b>“Nueva diapositiva”</b> para cortar; sin cortes queda todo en una sola.',
    pagina: 'Se lee de corrido, como el resto de los módulos.',
  };
  $('#dModoNota').innerHTML = notas[modo];
  $('#gbDoc').classList.toggle('modo-presentacion', PRESENTACION);
  // el interruptor del documento abierto (dentro de una biblioteca)
  $('#docModo').querySelectorAll('.seg-b').forEach(b =>
    b.classList.toggle('active', (b.dataset.modo === 'presentacion') === PRESENTACION));
  /* en un muro, la barra de arriba muestra los datos de la publicación y
     esconde lo que no aplica: una publicación no es una presentación, y su
     "etiqueta" es el tipo (Anuncio, Promoción…), que se elige de la lista. */
  const dm = $('#docMuro'); if (dm) dm.hidden = !ES_MURO;
  $('#docEtiqueta').hidden = ES_MURO;
  $('#docModo').hidden = ES_MURO;
  $('#docBar').querySelector('.doc-bar-lbl').hidden = ES_MURO;
  // con el acordeón cerrado igual se lee qué es el módulo ("Reporte · Biblioteca")
  const am = $('#apMeta');
  if (am) {
    const nm = { pagina: 'Página', presentacion: 'Presentación', biblioteca: 'Biblioteca', muro: 'Cartelera' }[modo] || '';
    am.textContent = (($('#dTitle') || {}).value || 'Sin nombre') + ' · ' + nm;
  }
}

$('#dModo').addEventListener('click', async e => {
  const b = e.target.closest('.seg-b'); if (!b) return;
  const modo = b.dataset.modo;
  if (modo === modoActual()) return;

  /* muro <-> biblioteca: las dos guardan una LISTA de piezas. Pasar de muro a
     biblioteca NO es gratis: los datos de publicación (quién, cuándo, fijada)
     dejan de guardarse, así que se avisa antes. */
  if ((modo === 'muro' || modo === 'biblioteca') && COLECCION) {
    if (modo === 'biblioteca' && ES_MURO && COLECCION.length && !await confirmar(
      'Las ' + COLECCION.length + ' publicaciones pasan a ser documentos de una biblioteca: ' +
      'se pierden el autor, la fecha y lo que esté fijado, y el vendedor deja de verlas como muro.',
      'Sí, pasar a biblioteca', 'Dejar de ser un muro')) { pintarModo(); return; }
    ES_MURO = modo === 'muro';
    if (ES_MURO) { COLECCION.forEach(prepararPost); COL_PALABRA = 'publicación'; }
    if (DOC_IDX == null) irALista(); else { pintarModo(); volcarDatosPost(); }
    return;
  }
  if (modo === 'biblioteca' || modo === 'muro') {
    ES_MURO = modo === 'muro';
    // si el módulo se llama "Reporte de …", asumimos que cada pieza es un reporte
    if (ES_MURO) COL_PALABRA = 'publicación';
    else if (!COL_PALABRA) {
      const t = ($('#dTitle').value || '').toLowerCase();
      COL_PALABRA = ['reporte', 'informe', 'capacitación', 'comunicado', 'catálogo', 'manual']
        .find(p => t.includes(p)) || '';
    }
    // lo que había escrito pasa a ser la primera pieza de la lista
    COLECCION = [{
      id: nuevoId(), titulo: ($('#dTitle').value.trim() || (ES_MURO ? 'Primera publicación' : 'Documento 1')),
      etiqueta: '', archivado: false, presentacion: ES_MURO ? false : PRESENTACION,
      bloques: JSON.parse(JSON.stringify(BLOQUES)),
    }];
    if (ES_MURO) COLECCION.forEach(prepararPost);
    DOC_IDX = null;
    irALista();
    return;
  }
  if (COLECCION) {
    ES_MURO = false;
    // salir de biblioteca: se conserva SOLO el primer documento
    if (COLECCION.length > 1 && !await confirmar(
      'Este módulo tiene ' + COLECCION.length + ' documentos. Si lo pasás a un documento único se conserva ' +
      'solamente el primero (“' + (COLECCION[0].titulo || 'sin nombre') + '”) y se pierden los demás.',
      'Sí, dejar uno solo', 'Pasar a documento único')) { pintarModo(); return; }
    if (DOC_IDX != null) guardarDocEnColeccion();
    const primero = COLECCION[0] || { bloques: [] };
    BLOQUES = JSON.parse(JSON.stringify(primero.bloques || []));
    SEL = BLOQUES.length ? 0 : null;
    COLECCION = null; DOC_IDX = null;
    $('#docBar').hidden = true;
    mostrarPane('bloques');
  }
  PRESENTACION = modo === 'presentacion';
  pintarModo(); renderGbEditor();
});

// ---- interruptor del DOCUMENTO abierto dentro de una biblioteca ----
$('#docModo').addEventListener('click', e => {
  const b = e.target.closest('.seg-b'); if (!b) return;
  PRESENTACION = b.dataset.modo === 'presentacion';
  pintarModo(); renderGbAdd(); renderCanvas(); if (SEL != null) selectBlock(SEL);
});
$('#docTitulo').oninput = () => { if (COLECCION && DOC_IDX != null) COLECCION[DOC_IDX].titulo = $('#docTitulo').value; };
$('#docEtiqueta').oninput = () => { if (COLECCION && DOC_IDX != null) COLECCION[DOC_IDX].etiqueta = $('#docEtiqueta').value; };
/* los datos de la publicación se escriben en el acto: si esperaran a "Guardar",
   ni el autoguardado ni el deshacer se enterarían de que cambió algo */
['docAutor', 'docSucursal', 'docFecha', 'docTipo', 'docFijado', 'docConfirmar'].forEach(id => {
  const el = $('#' + id); if (!el) return;
  const prop = { docAutor: 'autor', docSucursal: 'sucursal', docFecha: 'fecha', docTipo: 'etiqueta', docFijado: 'fijado', docConfirmar: 'confirmar' }[id];
  const escribir = () => {
    if (!COLECCION || DOC_IDX == null || !ES_MURO) return;
    COLECCION[DOC_IDX][prop] = (el.type === 'checkbox') ? el.checked : el.value;
  };
  el.addEventListener('input', escribir);
  el.addEventListener('change', escribir);      // date y select avisan por change
});
$('#docBack').onclick = () => irALista();

/* ---- biblioteca: lista de documentos ---- */
function irALista() {
  if (DOC_IDX != null) guardarDocEnColeccion();
  DOC_IDX = null;
  $('#docBar').hidden = true;
  mostrarPane('coleccion');
  moveApA('#colApSlot');
  pintarModo();
  renderColeccion();
}
/* ---- muro: datos de cada publicación ---- */
const ETIQUETAS_MURO = ['anuncio', 'promo', 'capacitacion', 'logro', 'importante', 'equipo'];
function hoyISO() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
/* Completa lo que le falta a una pieza para funcionar como publicación. Se
   usa también al convertir una biblioteca en muro: ahí la "etiqueta" era
   texto libre (“Mensual”) y como tipo no sirve, así que se descarta. */
function prepararPost(d) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d.fecha || '')) d.fecha = hoyISO();
  if (d.autor == null) d.autor = 'Marketing';
  if (d.sucursal == null) d.sucursal = '';
  if (ETIQUETAS_MURO.indexOf(d.etiqueta) < 0) d.etiqueta = '';
  d.fijado = !!d.fijado;
  /* OJO: no se toca `presentacion`. Se ignora mientras sea muro (el html se
     genera siempre como página), pero si el módulo vuelve a ser biblioteca,
     pisarlo acá convertiría en página cualquier documento que fuera
     presentación, sin que nadie lo haya pedido. */
}
function volcarDatosPost() {
  const d = (COLECCION && COLECCION[DOC_IDX]) || null;
  if (!d || !ES_MURO) return;
  $('#docAutor').value = d.autor || '';
  $('#docSucursal').value = d.sucursal || '';
  $('#docFecha').value = d.fecha || '';
  $('#docTipo').value = ETIQUETAS_MURO.indexOf(d.etiqueta) >= 0 ? d.etiqueta : '';
  $('#docFijado').checked = !!d.fijado;
  $('#docConfirmar').checked = !!d.confirmar;
  /* si ya tiene fecha de baja se muestra la FECHA, no el atajo con el que se
     eligió: lo que importa es qué día deja de verse */
  $('#docVence').value = d.vence ? 'fecha' : '';
  $('#docVenceF').value = d.vence || '';
  $('#docVenceF').hidden = !d.vence;
}

/* ---- vencimiento: los atajos calculan la fecha, que queda a la vista ---- */
function sumarDias(iso, n) {
  const p = String(iso || '').split('-').map(Number);
  const base = (p.length === 3 && p[0]) ? new Date(p[0], p[1] - 1, p[2]) : new Date();
  base.setDate(base.getDate() + n);
  return isoDe(base);
}
function finDeMes(iso) {
  const p = String(iso || '').split('-').map(Number);
  const base = (p.length === 3 && p[0]) ? new Date(p[0], p[1] - 1, p[2]) : new Date();
  return isoDe(new Date(base.getFullYear(), base.getMonth() + 1, 0));   // día 0 = último del mes
}
function isoDe(d) {
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') +
         '-' + String(d.getDate()).padStart(2, '0');
}
function aplicarVencimiento() {
  const modo = $('#docVence').value;
  const desde = $('#docFecha').value || hoyISO();
  const campo = $('#docVenceF');
  if (!modo) { campo.hidden = true; campo.value = ''; }
  else if (modo === 'finmes') { campo.hidden = false; campo.value = finDeMes(desde); }
  else if (modo === 'fecha') { campo.hidden = false; if (!campo.value) campo.value = sumarDias(desde, 30); }
  else { campo.hidden = false; campo.value = sumarDias(desde, Number(modo) || 30); }
  if (COLECCION && DOC_IDX != null && ES_MURO) COLECCION[DOC_IDX].vence = campo.value;
}
$('#docVence').addEventListener('change', aplicarVencimiento);
$('#docVenceF').addEventListener('change', () => {
  if (COLECCION && DOC_IDX != null && ES_MURO) COLECCION[DOC_IDX].vence = $('#docVenceF').value;
});

function guardarDocEnColeccion() {
  const d = COLECCION && COLECCION[DOC_IDX]; if (!d) return;
  d.bloques = JSON.parse(JSON.stringify(BLOQUES));
  d.presentacion = ES_MURO ? false : PRESENTACION;
  d.titulo = $('#docTitulo').value.trim() || d.titulo;
  if (ES_MURO) {
    d.autor = $('#docAutor').value.trim();
    d.sucursal = $('#docSucursal').value.trim();
    d.fecha = $('#docFecha').value || d.fecha || hoyISO();
    d.etiqueta = $('#docTipo').value;
    d.fijado = $('#docFijado').checked;
    d.confirmar = $('#docConfirmar').checked;
    d.vence = $('#docVence').value ? ($('#docVenceF').value || '') : '';
  } else {
    d.etiqueta = $('#docEtiqueta').value.trim();
  }
}
function abrirDoc(i) {
  const d = COLECCION[i]; if (!d) return;
  DOC_IDX = i;
  $('#docTitulo').placeholder = ES_MURO
    ? 'Título de la publicación · ej: Ya están las placas de agosto'
    : 'Nombre ' + (fem() ? 'de la ' : 'del ') + palabra() + ' · ej: Julio 2026';
  $('#docBack').title = 'Volver a la lista de ' + palabras();
  if (ES_MURO) prepararPost(d);
  /* ⚠️ Una publicación vieja puede traer el `html` armado y NINGÚN bloque (las
     que se cargaron a mano o desde afuera del panel). Antes el canvas abría
     VACÍO: parecía que no tenía cuerpo. Y era peor que un susto — apenas se
     agregaba un bloque, `bloques.length` pasaba a 1 y al guardar se
     regeneraba el html desde ese único bloque: el cuerpo original se perdía.
     Es el patrón que destruyó Marzo–Mayo, corrido un paso.

     No se convierte con htmlABloques() a propósito: probado contra los 10
     html reales del proyecto, una galería se desarma en imágenes sueltas y se
     lleva puestos los NOMBRES de las placas y sus botones de Descargar.
     Un solo bloque `html` va y vuelve IDÉNTICO en los 10 casos, así que el
     cuerpo entra entero y se le puede agregar cosas al lado sin romper nada. */
  BLOQUES = (Array.isArray(d.bloques) && d.bloques.length)
    ? JSON.parse(JSON.stringify(d.bloques))
    : ((d.html || '').trim() ? [{ t: 'html', html: d.html }] : []);
  PRESENTACION = ES_MURO ? false : !!d.presentacion;
  SEL = BLOQUES.length ? 0 : null;
  $('#docTitulo').value = d.titulo || '';
  $('#docEtiqueta').value = d.etiqueta || '';
  $('#docBar').hidden = false;
  mostrarPane('bloques');
  pintarModo();
  volcarDatosPost();
  renderGbEditor();
}
// cuenta las diapositivas con el MISMO criterio que bloquesHTML: una por cada
// grupo con contenido (un corte al principio, o dos seguidos, no crean una vacía)
function contarSlides(bloques) {
  let n = 0, cuerpo = 0, titulo = '';
  (bloques || []).forEach(b => {
    if (b.t === 'diapo') { if (cuerpo || titulo) n++; cuerpo = 0; titulo = txtOf(b.titulo); }
    else cuerpo++;
  });
  if (cuerpo || titulo) n++;
  return n;
}
function resumenDoc(d) {
  const bl = d.bloques || [];
  if (d.presentacion) {
    const n = contarSlides(bl);
    return n + (n === 1 ? ' diapositiva' : ' diapositivas');
  }
  return bl.length + (bl.length === 1 ? ' bloque' : ' bloques');
}
// refresca los textos que dependen de cómo el usuario llama a cada pieza
function pintarPalabra() {
  $('#colTitulo').textContent = ES_MURO ? 'Publicaciones del muro' : mayus(palabras()) + ' de este módulo';
  $('#colAdd').textContent = ES_MURO ? '+ Nueva publicación' : '+ ' + (fem() ? 'Nueva' : 'Nuevo') + ' ' + palabra();
  $('#colDup').textContent = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M9 9h10v10H9zM5 15V5h10"/></svg> Duplicar ' + elLa() + ' primer' + (fem() ? 'a' : '') + ' ' + palabra();
  if ($('#colPalabra').value !== (COL_PALABRA || '')) $('#colPalabra').value = COL_PALABRA || '';
  /* en un muro no aplican: cada publicación se escribe de cero, no se clona una
     estructura de números mes a mes, y el nombre de la pieza es fijo. */
  const l = $('#colPalabra').closest('label'); if (l) l.hidden = ES_MURO;
  $('#colDup').hidden = ES_MURO;
  $('#colNuevoMes').hidden = ES_MURO;
}
/* ===================================================================
   LISTAS ORDENABLES (reportes, módulos)

   Un solo motor para todas. La tarjeta se despega y sigue el dedo, las
   demás se corren solas con animación, y al soltar aterriza en su lugar.

   OJO — el bug que arreglaba esto: antes cada lista se re-enganchaba en
   CADA render sobre un contenedor que NO se destruye (#colList). Los
   listeners se acumulaban, así que el segundo arrastre disparaba dos
   handlers, el tercero tres… y cada uno hacía su propio splice: el
   reporte terminaba en cualquier lado. Por eso `dataset.ordenable`.
   =================================================================== */

// mueve los elementos a su lugar nuevo con una animación (técnica FLIP:
// mido dónde están AHORA, aplico el cambio, y los animo desde donde estaban).
// Se mide ANTES de cancelar las animaciones en curso: así, si el usuario mueve
// rápido y se encadenan varios reacomodos, cada uno arranca desde la posición
// real que se ve en pantalla y no pega tirones.
function conDeslizamiento(cont, sel, aplicarCambio) {
  const nodos = [...cont.querySelectorAll(sel)].filter(n => n.style.display !== 'none');
  const antes = new Map(nodos.map(n => [n, n.getBoundingClientRect().top]));
  nodos.forEach(n => n.getAnimations().forEach(a => a.cancel()));
  aplicarCambio();
  nodos.forEach(n => {
    const salto = antes.get(n) - n.getBoundingClientRect().top;
    if (!salto) return;
    n.animate([{ transform: `translateY(${salto}px)` }, { transform: 'none' }],
      { duration: 190, easing: 'cubic-bezier(.2,.8,.2,1)' });
  });
}

let ORD_EN_CURSO = false;    // no dejar arrancar otro arrastre mientras uno aterriza

function listaOrdenable(cont, { item, grip, alSoltar }) {
  if (!cont || cont.dataset.ordenable === '1') return;   // ¡una sola vez por contenedor!
  cont.dataset.ordenable = '1';

  cont.addEventListener('pointerdown', e => {
    if (e.button !== 0 || ORD_EN_CURSO) return;
    if (grip && !e.target.closest(grip)) return;         // solo se arrastra desde el ⠿
    const el = e.target.closest(item);
    if (!el || !cont.contains(el)) return;
    e.preventDefault();

    const puntero = e.pointerId;                         // ignorar un segundo dedo
    const x0 = e.clientX, y0 = e.clientY;
    const caja = el.getBoundingClientRect();
    const offX = e.clientX - caja.left, offY = e.clientY - caja.top;
    const desde = [...cont.querySelectorAll(item)].indexOf(el);
    let activo = false, hueco = null, fantasma = null;

    const ubicar = (x, y, extra) =>
      `translate(${Math.round(x - offX)}px, ${Math.round(y - offY)}px)` + (extra || '');

    const desenganchar = () => {
      document.removeEventListener('pointermove', mover);
      document.removeEventListener('pointerup', soltar);
      document.removeEventListener('pointercancel', cancelar);
    };

    // deja todo como estaba: la tarjeta nunca se movió del DOM, solo estaba tapada
    const limpiar = () => {
      if (hueco) hueco.remove();
      if (fantasma) fantasma.remove();
      el.style.display = '';
      document.body.classList.remove('ord-arrastrando');
      ORD_EN_CURSO = false;
    };

    const arrancar = ev => {
      activo = true;
      ORD_EN_CURSO = true;
      const s = window.getSelection(); if (s) s.removeAllRanges();
      // hueco del mismo alto: la lista no pega un salto al sacar la tarjeta
      hueco = document.createElement('div');
      hueco.className = 'ord-hueco';
      hueco.style.height = caja.height + 'px';
      el.parentNode.insertBefore(hueco, el);
      // copia que flota siguiendo la mano
      fantasma = el.cloneNode(true);
      fantasma.classList.add('ord-flota');
      fantasma.style.width = caja.width + 'px';
      fantasma.style.height = caja.height + 'px';
      fantasma.style.transform = ubicar(ev.clientX, ev.clientY);
      document.body.appendChild(fantasma);
      requestAnimationFrame(() => fantasma.classList.add('alzada'));
      el.style.display = 'none';
      document.body.classList.add('ord-arrastrando');
    };

    const dondeCae = y => {
      for (const n of cont.querySelectorAll(item)) {
        if (n === el) continue;
        const r = n.getBoundingClientRect();
        if (y < r.top + r.height / 2) return n;
      }
      return null;
    };

    // si algo re-dibujó la lista mientras arrastrábamos, la tarjeta y el hueco
    // quedaron huérfanos: se abandona sin romper nada (mejor que tirar un error
    // y dejar la copia flotante pegada en la pantalla)
    const seguimosVivos = () => cont.contains(el) && cont.contains(hueco);

    function mover(ev) {
      if (ev.pointerId !== puntero) return;
      if (!activo) {
        // umbral: un toque corto sigue siendo un click, no un arrastre
        if (Math.hypot(ev.clientX - x0, ev.clientY - y0) < 6) return;
        arrancar(ev);
      }
      if (!seguimosVivos()) { desenganchar(); limpiar(); return; }
      fantasma.style.transform = ubicar(ev.clientX, ev.clientY, ' scale(1.02) rotate(-1.1deg)');
      const ref = dondeCae(ev.clientY);
      if (ref !== hueco.nextElementSibling) {
        conDeslizamiento(cont, item, () => {
          if (ref) cont.insertBefore(hueco, ref); else cont.appendChild(hueco);
        });
      }
    }

    // el sistema abortó el gesto (por ejemplo entró otro dedo, o se fue el foco):
    // se cancela de verdad, NO se confirma un reordenamiento que nadie pidió
    function cancelar(ev) {
      if (ev && ev.pointerId !== puntero) return;
      desenganchar();
      if (activo) limpiar();
    }

    function soltar(ev) {
      if (ev && ev.pointerId !== puntero) return;
      desenganchar();
      if (!activo) return;                       // fue un click, no un arrastre
      document.body.classList.remove('ord-arrastrando');
      if (!seguimosVivos()) { limpiar(); return; }

      const aterrizar = () => {
        if (!seguimosVivos()) { limpiar(); return; }
        hueco.parentNode.insertBefore(el, hueco);
        hueco.remove();
        el.style.display = '';
        fantasma.remove();
        ORD_EN_CURSO = false;
        el.animate([{ transform: 'scale(1.03)' }, { transform: 'none' }],
          { duration: 200, easing: 'cubic-bezier(.2,.8,.2,1)' });
        const hasta = [...cont.querySelectorAll(item)].indexOf(el);
        if (hasta !== desde && typeof alSoltar === 'function') alSoltar(desde, hasta);
      };

      // vuela hasta el hueco antes de soltarse del todo
      const destino = hueco.getBoundingClientRect();
      fantasma.classList.remove('alzada');
      const vuelo = fantasma.animate(
        [{ transform: fantasma.style.transform },
        { transform: `translate(${Math.round(destino.left)}px, ${Math.round(destino.top)}px)` }],
        { duration: 170, easing: 'cubic-bezier(.2,.8,.2,1)' });
      vuelo.onfinish = aterrizar;
      vuelo.oncancel = aterrizar;                // si algo la corta, igual hay que acomodar
    }

    document.addEventListener('pointermove', mover);
    document.addEventListener('pointerup', soltar);
    document.addEventListener('pointercancel', cancelar);
  });
}

/* la línea de abajo del título en la lista del muro: quién, cuándo y de qué tipo */
const NOMBRE_TIPO = {
  anuncio: 'Anuncio', promo: 'Promoción', capacitacion: 'Capacitación',
  logro: 'Logro', importante: 'Importante', equipo: 'Equipo',
};
function metaPost(d) {
  const partes = [];
  if (d.autor) partes.push(esc(d.autor) + (d.sucursal ? ' (' + esc(d.sucursal) + ')' : ''));
  if (d.fecha) partes.push(esc(fechaCorta(d.fecha)));
  if (NOMBRE_TIPO[d.etiqueta]) partes.push(NOMBRE_TIPO[d.etiqueta]);
  const v = avisoVence(d);
  if (v) partes.push(v);
  return partes.join(' · ') || '<i>sin datos de publicación</i>';
}
/* Cuánto le queda de vida. Lo vencido se avisa fuerte: el vendedor ya no lo ve
   y conviene que quien publica se entere sin tener que abrirlo. */
function avisoVence(d) {
  if (!d.vence) return '';
  const dias = diasHasta(d.vence);
  if (dias === null) return '';
  if (dias < 0) return '<b class="col-av">⏳ ya no se ve (venció el ' + esc(fechaCorta(d.vence)) + ')</b>';
  if (dias === 0) return '<b class="col-pv">último día</b>';
  if (dias <= 7) return '<b class="col-pv">' + (dias === 1 ? 'vence mañana' : 'vence en ' + dias + ' días') + '</b>';
  return 'hasta el ' + esc(fechaCorta(d.vence));
}
function diasHasta(f) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(f || '')) return null;
  const p = f.split('-').map(Number);
  const h = new Date();
  return Math.round((Date.UTC(p[0], p[1] - 1, p[2]) -
                     Date.UTC(h.getFullYear(), h.getMonth(), h.getDate())) / 86400000);
}
const MESES_C = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
function fechaCorta(f) {
  const p = String(f || '').split('-');
  if (p.length !== 3) return '';
  return Number(p[2]) + ' ' + (MESES_C[Number(p[1]) - 1] || '') + ' ' + p[0];
}

function renderColeccion() {
  pintarPalabra();
  const box = $('#colList'); box.innerHTML = '';
  if (!COLECCION.length) {
    box.innerHTML = '<p class="muted" style="padding:22px;text-align:center">Todavía no hay ' + palabras() +
      '. Tocá <b>' + esc($('#colAdd').textContent) + '</b>.</p>';
    return;
  }
  const primeroVisible = COLECCION.findIndex(x => !x.archivado);
  COLECCION.forEach((d, i) => {
    const card = document.createElement('div');
    card.className = 'col-item' + (d.archivado ? ' archivado' : '');
    card.dataset.i = i;
    /* En un muro el orden lo da la FECHA (y lo fijado va arriba), así que
       arrastrar no cambiaría nada en la intranet: mejor no ofrecerlo que
       dejar al admin acomodando tarjetas para nada. */
    card.innerHTML = `
      ${ES_MURO ? '<span class="col-grip apagado" title="En el muro se ordenan solas: primero lo fijado, después por fecha">🕒</span>'
                : '<button type="button" class="col-grip" title="Arrastrá para ordenar"><svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true" focusable="false"><circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg></button>'}
      <div class="col-info">
        <div class="col-t">${esc(d.titulo || 'Sin nombre')}
          ${(ES_MURO && d.fijado && !d.archivado) ? '<span class="col-badge fij"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 17v4M8 4h8l-1 6 3 3H6l3-3z"/></svg> Fijada</span>' : ''}
          ${(ES_MURO && d.confirmar) ? '<span class="col-badge conf">✓ Pide confirmación</span>' : ''}
          ${(!ES_MURO && !d.archivado && i === primeroVisible) ? '<span class="col-badge">Último</span>' : ''}
          ${d.archivado ? '<span class="col-badge arch">Oculto</span>' : ''}</div>
        <div class="col-d">${ES_MURO ? metaPost(d)
        : (d.etiqueta ? esc(d.etiqueta) + ' · ' : '') + resumenDoc(d) + (d.presentacion ? ' · presentación'
        : ((d.bloques || []).some(b => b.t === 'diapo') ? ' · <b class="col-av">⚠️ tiene cortes de diapositiva sin uso</b>' : ''))}</div>
      </div>
      <button type="button" class="col-act col-edit" title="Abrir para editarlo">✏️ Editar</button>
      <button type="button" class="col-act col-arch" title="${d.archivado
        ? 'Volver a mostrárselo a los vendedores'
        : 'Los vendedores dejan de verlo, pero vos lo conservás acá'}">${d.archivado ? '👁 Mostrar' : '🚫 Ocultar'}</button>
      <button type="button" class="col-act col-del" title="Eliminar para siempre"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg></button>`;
    card.querySelector('.col-edit').onclick = () => abrirDoc(i);
    card.querySelector('.col-info').onclick = () => abrirDoc(i);
    card.querySelector('.col-arch').onclick = () => { d.archivado = !d.archivado; renderColeccion(); };
    card.querySelector('.col-del').onclick = async () => {
      if (!await confirmar('¿Eliminar ' + elLa() + ' ' + palabra() + ' “' + (d.titulo || 'sin nombre') +
        '”? No se puede deshacer.', 'Sí, eliminar', 'Eliminar ' + palabra())) return;
      COLECCION.splice(i, 1); renderColeccion();
    };
    box.appendChild(card);
  });
  if (!ES_MURO) listaOrdenable(box, {
    item: '.col-item', grip: '.col-grip',
    alSoltar: (desde, hasta) => {
      COLECCION.splice(hasta, 0, COLECCION.splice(desde, 1)[0]);
      renderColeccion();
    },
  });
}
$('#colPalabra').oninput = () => { COL_PALABRA = $('#colPalabra').value; pintarPalabra(); };
$('#colAdd').onclick = () => {
  const nuevo = { id: nuevoId(), titulo: '', etiqueta: '', archivado: false, presentacion: false, bloques: [] };
  if (ES_MURO) prepararPost(nuevo);       // nace con la fecha de hoy y el autor por defecto
  // en un muro lo más nuevo va arriba: la publicación entra primera, no última
  if (ES_MURO) COLECCION.unshift(nuevo); else COLECCION.push(nuevo);
  abrirDoc(ES_MURO ? 0 : COLECCION.length - 1);
  $('#docTitulo').focus();
};
/* Deja la ESTRUCTURA y borra los datos que cambian mes a mes.
   Lo que se repite (nombre de la sucursal, encabezado de la tabla, título de la
   sección) se conserva; lo que hay que cargar de nuevo queda en blanco.
   Antes "Duplicar" copiaba todo CON los números viejos y había que borrarlos
   a mano uno por uno, que es el trabajo real de cada mes. */
function vaciarNumeros(bloques) {
  (bloques || []).forEach(b => {
    if (b.t === 'kpis') (b.items || []).forEach(k => { k.valor = ''; k.pie = ''; k.tend = ''; });
    else if (b.t === 'barras') (b.items || []).forEach(k => { k.valor = ''; k.chip = ''; });
    else if (b.t === 'podio') (b.items || []).forEach(k => { k.nombre = ''; k.suc = ''; k.valor = ''; k.extra = ''; });
    else if (b.t === 'tabla') {
      const cols = b.cols || [];
      (b.filas || []).forEach(f => {
        f.celdas = (f.celdas || []).map((c, i) => (cols[i] && cols[i].num) ? '' : c);
      });
    }
  });
  return bloques;
}

function nuevoDesde(idx, vaciar) {
  const base = JSON.parse(JSON.stringify(COLECCION[idx]));
  base.id = nuevoId();
  base.archivado = false;
  if (vaciar) { vaciarNumeros(base.bloques); base.titulo = ''; }
  else base.titulo = (base.titulo || palabraM()) + ' (copia)';
  COLECCION.unshift(base);
  renderColeccion();
  if (vaciar) {
    abrirDoc(0);
    $('#docTitulo').focus();
    toast('Listo: quedó la misma estructura con los números en blanco. Ponele nombre.', 'ok');
  } else {
    toast('Copia lista. Cambiale el nombre y los números.', 'ok');
  }
}

$('#colDup').onclick = () => {
  if (!COLECCION.length) { toast('Primero creá ' + unUna() + ' ' + palabra(), 'err'); return; }
  nuevoDesde(0, false);
};
$('#colNuevoMes').onclick = () => {
  if (!COLECCION.length) { toast('Primero creá ' + unUna() + ' ' + palabra(), 'err'); return; }
  const i = Math.max(0, COLECCION.findIndex(x => !x.archivado));
  nuevoDesde(i, true);
};
const BK_ICONOS = ['check', 'x', 'clock', 'map', 'mic', 'phone', 'truck', 'shield', 'award', 'users', 'user', 'store', 'box', 'ruler', 'card', 'megaphone', 'chatBubble', 'lock'];
/* Los nombres de grupo son SOLO rótulos (nada guardado depende de ellos), así
   que dicen lo que diría un vendedor y no lo que diría un programador.
   "Sección de descargas" era el bloque estrella y estaba enterrado cuarto. */
const GRUPOS_BLOQUE = {
  'Texto': ['titulo', 'subtitulo', 'parrafo', 'destacado', 'kicker'],
  'Listas y avisos': ['lista', 'pasos', 'nota', 'advertencia', 'chat', 'situacion'],
  'Fotos, videos y archivos': ['imagen', 'galeria', 'video', 'pdf', 'plantilla', 'embed', 'boton'],
  'Números y tablas': ['tabla', 'kpis', 'barras', 'podio', 'tarjetas'],
  'Separaciones': ['separador', 'espacio'],
  'Presentación': ['diapo'],
};
// sinónimos: nadie busca "kicker", buscan "excel", "foto", "whatsapp", "ranking"
const ALIAS_BLOQUE = {
  titulo: 'encabezado h1 titular', subtitulo: 'encabezado h2 seccion',
  parrafo: 'texto cuerpo escribir', destacado: 'copete intro lead resumen',
  kicker: 'etiqueta rotulo numero paso', lista: 'checklist tildes puntos bullets requisitos',
  pasos: 'flujo proceso diagrama circuito', chat: 'whatsapp conversacion mensaje burbuja cliente',
  situacion: 'objecion caso guion respuesta cliente', nota: 'aviso importante atencion recuadro recordatorio',
  advertencia: 'peligro cuidado alerta atencion rojo critico grave error prohibido',
  separador: 'linea divisoria raya corte', espacio: 'aire margen blanco separacion',
  tabla: 'excel planilla grilla filas columnas precios', kpis: 'numeros metricas cifras indicadores ventas',
  barras: 'grafico ranking comparar chart', podio: 'ranking top mejores primeros vendedores',
  tarjetas: 'grilla iconos conceptos beneficios', diapo: 'slide corte presentacion pantalla',
  imagen: 'foto placa jpg png banner', video: 'mp4 youtube reel clip',
  galeria: 'descargas placas material bajar archivos fotos', pdf: 'documento archivo folleto catalogo',
  embed: 'iframe web informe looker mapa', boton: 'link enlace url ir a',
  plantilla: 'whatsapp carrusel mensaje plantilla',
};
/* CONTRATO con la intranet (bloque Advertencia): este svg y la estructura
   .m-warn > .ico + .mw-tx se emiten IGUALES aca y en intranet/index.html —
   si cambia uno, cambia el otro. */
const SVG_WARN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.6 21.2 20H2.8z"/><path d="M12 10v4"/><path d="M12 17.2v.1"/></svg>';
const BLOQUE_INFO = {
  ref: { label: 'Señalar un módulo', desc: 'Tarjeta que lleva a donde vive el material' },
  titulo: { label: 'Título', desc: 'Encabezado grande' },
  subtitulo: { label: 'Subtítulo', desc: 'Encabezado mediano' },
  parrafo: { label: 'Párrafo', desc: 'Texto normal' },
  destacado: { label: 'Destacado', desc: 'Frase de intro grande' },
  kicker: { label: 'Etiqueta con número', desc: 'Rótulo chico arriba de un título' },
  lista: { label: 'Lista de chequeo', desc: 'Ítems con tilde' },
  pasos: { label: 'Pasos (diagrama)', desc: 'Flujo con íconos' },
  chat: { label: 'Ejemplo (chat)', desc: 'Burbujas de WhatsApp' },
  situacion: { label: 'Situación', desc: 'Tarjeta con etiqueta + respuesta' },
  nota: { label: 'Nota', desc: 'Recuadro con ícono' },
  advertencia: { label: 'Advertencia', desc: 'Aviso importante que no puede pasarse por alto' },
  separador: { label: 'Línea', desc: 'Divisoria fina' },
  espacio: { label: 'Espacio', desc: 'Aire en blanco' },
  tabla: { label: 'Tabla', desc: 'Filas y columnas de datos' },
  kpis: { label: 'Tarjetas de número', desc: 'Cifras grandes con variación' },
  barras: { label: 'Barras comparativas', desc: 'Ranking con barras de color' },
  podio: { label: 'Podio', desc: 'Top de vendedores o sucursales' },
  tarjetas: { label: 'Tarjetas con ícono', desc: 'Ideas o conceptos en grilla' },
  diapo: { label: 'Nueva diapositiva', desc: 'Corta acá en modo presentación' },
  imagen: { label: 'Imagen', desc: 'Subí una foto' },
  video: { label: 'Video', desc: 'Subí un video o pegá un link' },
  galeria: { label: 'Placas para descargar', desc: 'Grilla de imágenes que el vendedor baja' },
  pdf: { label: 'PDF', desc: 'Documento: visor o tarjeta' },
  embed: { label: 'Web embebida', desc: 'Informe / catálogo' },
  boton: { label: 'Botón / link', desc: 'Enlace a otra página' },
  plantilla: { label: 'Plantilla de WhatsApp', desc: 'Como la ve el cliente: texto, botones o carrusel' },
  html: { label: 'Diseño del sistema', desc: 'Bloque original' },
};

function bloqueNuevo(t) {
  switch (t) {
    case 'titulo': return { t: 'titulo', nivel: 'h1', html: '' };
    case 'subtitulo': return { t: 'titulo', nivel: 'h2', html: '' };
    case 'destacado': return { t: 'destacado', html: '' };
    case 'parrafo': return { t: 'parrafo', html: '' };
    case 'kicker': return { t: 'kicker', n: '', html: '' };
    case 'nota': return { t: 'nota', icono: 'clock', color: '', html: '' };
    case 'advertencia': return { t: 'advertencia', html: 'Escribí acá la advertencia…' };
    case 'lista': return { t: 'lista', items: [{ icono: 'check', color: '--c-success', html: '' }] };
    case 'chat': return { t: 'chat', label: 'Ejemplo', items: [{ lado: 'out', html: '' }] };
    case 'situacion': return { t: 'situacion', tag: 'Situación', tagColor: '--c-warn', titulo: '', conResp: true, resp: 'Respuesta recomendada', respIcono: 'arrowDR', respColor: '--c-success', mensajes: [{ lado: 'out', html: '' }] };
    /* Plantilla de WhatsApp con la estructura REAL de Meta:
       encabezado (texto 60 / imagen) + cuerpo (1024) + pie (60) + botones.
       Formato carrusel: una burbuja + de 2 a 10 tarjetas, cada una con imagen
       obligatoria, hasta 160 caracteres y hasta 2 botones. */
    case 'plantilla': return {
      t: 'plantilla',
      categoria: 'marketing',          // marketing | utilidad | autenticacion
      formato: 'simple',               // simple | carrusel
      encabezado: { tipo: 'ninguno', texto: '', src: '' },
      cuerpo: '', pie: '',
      botones: [],
      tarjetas: [
        { src: '', cuerpo: '', botones: [{ tipo: 'enlace', texto: 'Ver ficha', url: '' }] },
        { src: '', cuerpo: '', botones: [{ tipo: 'enlace', texto: 'Ver ficha', url: '' }] },
      ],
    };
    case 'pasos': return { t: 'pasos', steps: [{ titulo: '', desc: '', icono: 'users', color: '--c-caba' }] };
    case 'espacio': return { t: 'espacio', alto: 'md' };
    case 'separador': return { t: 'separador', grosor: 4 };
    // las tablas NUEVAS nacen ordenables; las ya publicadas no tienen estas
    // claves, quedan igual que siempre hasta que el dueño las active
    case 'tabla': return {
      t: 'tabla',
      orden: true,          // el vendedor ordena tocando el título de la columna
      buscar: false,        // barra de búsqueda arriba (para tablas largas)
      cols: [{ h: 'Concepto', num: false }, { h: 'Cantidad', num: true }],
      filas: [{ celdas: ['', ''], destaque: '' }, { celdas: ['', ''], destaque: '' }],
    };
    // los campos numéricos arrancan VACÍOS (con texto de ayuda): si vinieran con un
    // "0" precargado, al tipear encima quedaría "0416"
    case 'kpis': return { t: 'kpis', items: [{ label: '', valor: '', pie: '', tend: '', lead: false }] };
    case 'barras': return { t: 'barras', items: [{ label: '', valor: '', color: '--c-hudson', chip: '', tono: 'gr' }] };
    case 'podio': return { t: 'podio', items: [{ puesto: '1°', nombre: '', suc: '', valor: '', vlabel: 'ventas', extra: '', lead: false }] };
    case 'tarjetas': return { t: 'tarjetas', cols: 3, orient: 'v', items: [{ icono: 'award', color: '--c-hudson', titulo: '', texto: '' }] };
    case 'diapo': return { t: 'diapo', titulo: '', grupo: '' };
    case 'imagen': return { t: 'imagen', src: '', alt: '', caption: '', tam: 'md', descargable: false, dlNombre: '' };
    // orient/ar los completa solo al subir (midiendo el archivo); descargable
    // arranca APAGADO porque la mayoría son videos de ejemplo, para mirar nomás
    case 'video': return { t: 'video', src: '', url: '', poster: '', caption: '', tam: 'md', orient: 'horiz', ar: '16/9', descargable: false, dlNombre: '' };
    case 'galeria': return { t: 'galeria', titulo: 'Sección de descargas', items: [{ src: '', nombre: '' }] };
    case 'pdf': return { t: 'pdf', src: '', nombre: '', modo: 'tarjeta', alto: 'md', descargable: true };
    case 'embed': return { t: 'embed', url: '', alto: 'md' };
    case 'boton': return { t: 'boton', texto: 'Abrir', url: '' };
    /* señalar: la publicación no copia el contenido, apunta al módulo donde vive */
    case 'ref': return { t: 'ref', key: '', mod: '', sub: '', clase: '', detalle: '',
                         prev: null, icon: 'layers', color: '--c-hudson' };
    case 'html': return { t: 'html', html: '' };
    default: return { t, html: '' };
  }
}

/* ===================================================================
   PLANTILLA DE WHATSAPP — se dibuja igual que la ve el cliente
   Límites reales de Meta: encabezado de texto 60 · cuerpo 1024 · pie 60 ·
   hasta 2 botones de enlace y 1 de teléfono · carrusel de 2 a 10 tarjetas con
   imagen obligatoria, 160 caracteres y hasta 2 botones cada una.
   Clases con prefijo `wt-` a propósito: las `wa-` ya las usa el maquetado del
   teléfono del Manual y compartirlas fue exactamente lo que rompió el diseño.
   =================================================================== */
const WA_CATS = { marketing: 'Marketing', utilidad: 'Utilidad', autenticacion: 'Autenticación' };
const WA_TIPOS_BTN = { rapida: 'Respuesta rápida', enlace: 'Enlace', telefono: 'Teléfono' };

// las variables {{1}} se muestran resaltadas para que se entienda qué se reemplaza
function waTexto(s) {
  return esc(s || '').replace(/\{\{\s*(\w+)\s*\}\}/g, '<span class="wt-var">{{$1}}</span>')
    .replace(/\n/g, '<br>');
}
function waIconoBtn(tipo) {
  if (tipo === 'enlace') return ICO('ext');
  if (tipo === 'telefono') return ICO('phone');
  return '';   // respuesta rápida: en WhatsApp NO lleva ícono
}
function waBotonesHTML(botones, clase) {
  const bs = (botones || []).filter(b => (b.texto || '').trim());
  if (!bs.length) return '';
  return bs.map(b => `<div class="${clase}">${waIconoBtn(b.tipo)}${esc(b.texto)}</div>`).join('');
}

// tiene algo cargado (sirve para detectar las que quedaron a medias)
function waTarjetaLlena(c) {
  return !!(c && ((c.src || '').trim() || (c.cuerpo || '').trim() ||
    (c.botones || []).some(b => (b.texto || '').trim())));
}
// se puede publicar solo si tiene FOTO: Meta la exige en cada tarjeta, y sin
// ella la tarjeta se ve como un hueco gris al lado de las demás
function waTarjetaPublicable(c) { return !!(c && (c.src || '').trim()); }

/* ed=true dibuja el lienzo del editor: ahí las tarjetas a medio llenar se ven
   como huecos para poder completarlas. En el sitio publicado no salen. */
function plantillaHTML(bk, ed) {
  const cat = WA_CATS[bk.categoria] || 'Marketing';
  const enc = bk.encabezado || {};
  let cabeza = '';
  if (enc.tipo === 'imagen' && enc.src) cabeza = `<div class="wt-hdr"><img src="${esc(enc.src)}" alt="" loading="lazy"></div>`;
  else if (enc.tipo === 'texto' && (enc.texto || '').trim()) cabeza = `<div class="wt-hdrt">${esc(enc.texto)}</div>`;

  const cuerpo = (bk.cuerpo || '').trim();
  const pie = (bk.pie || '').trim();
  // sin nada adentro NO se dibuja la burbuja: quedaba un globo verde con la
  // hora sola, que parecía un error
  const hayBurbuja = !!(cuerpo || cabeza) || ed;
  const burbuja = hayBurbuja ? (`<div class="wt-msg">${cabeza}` +
    (cuerpo ? `<div class="wt-body">${waTexto(cuerpo)}</div>`
      : (ed ? '<div class="wt-body wt-ph">Escribí acá el mensaje →</div>' : '')) +
    (pie ? `<div class="wt-foot">${esc(pie)}</div>` : '') +
    `<span class="wt-time">10:41 ${ICO('check')}</span></div>`) : '';

  if (bk.formato === 'carrusel') {
    const usables = (bk.tarjetas || []).filter(c => ed || waTarjetaPublicable(c));
    const cards = usables.map(c => {
      const txt = (c.cuerpo || '').trim();
      const btns = waBotonesHTML(c.botones, 'wt-cbtn');
      return `<div class="wt-card">` +
        `<div class="wt-cimg">${c.src ? `<img src="${esc(c.src)}" alt="" loading="lazy">` : ICO('image')}</div>` +
        // el cuerpo se emite SIEMPRE: es lo que mantiene las tarjetas parejas
        `<div class="wt-cbody">${txt ? waTexto(txt) : (ed ? '<span class="wt-ph">Sin texto</span>' : '')}</div>` +
        (btns ? `<div class="wt-cbtns">${btns}</div>` : '') +
        `</div>`;
    }).join('');
    if (!cards) return '';
    return `<div class="wt"><div class="wt-cat">${esc(cat)} · Carrusel</div>${burbuja}` +
      `<div class="wt-car">${cards}</div>` +
      `<div class="wt-hint">← deslizá para ver las tarjetas →</div></div>`;
  }
  if (!cuerpo && !cabeza && !ed) return '';
  return `<div class="wt"><div class="wt-cat">${esc(cat)}</div>${burbuja}` +
    (waBotonesHTML(bk.botones, 'wt-btn') ? `<div class="wt-btns">${waBotonesHTML(bk.botones, 'wt-btn')}</div>` : '') +
    `</div>`;
}

/* Meta exige que TODAS las tarjetas tengan los mismos componentes (si una lleva
   texto, todas) y la foto es obligatoria. Si no, rechaza la plantilla. */
function plantillaAvisos(bk) {
  const av = [];
  if (bk.formato !== 'carrusel') {
    if (!(bk.cuerpo || '').trim()) av.push('Falta el <b>cuerpo del mensaje</b>.');
    return av;
  }
  const ts = bk.tarjetas || [];
  const listas = ts.filter(waTarjetaPublicable);
  if (!(bk.cuerpo || '').trim()) av.push('El carrusel necesita un <b>mensaje arriba</b>.');
  // sin foto no se publica: es el motivo #1 por el que Meta rechaza un carrusel
  const sinFoto = ts.map((c, i) => waTarjetaPublicable(c) ? 0 : i + 1).filter(Boolean);
  if (sinFoto.length) {
    av.push('Sin foto (no se publica): <b>tarjeta ' + sinFoto.join(', ') +
      '</b>. WhatsApp la pide obligatoria.');
  }
  if (listas.length < 2) av.push('Un carrusel necesita <b>al menos 2 tarjetas con foto</b>.');
  const conTexto = listas.filter(c => (c.cuerpo || '').trim()).length;
  if (conTexto && conTexto !== listas.length) av.push('Si una tarjeta lleva texto, <b>todas</b> tienen que llevarlo.');
  const nb = listas.map(c => (c.botones || []).filter(b => (b.texto || '').trim()).length);
  if (nb.length && new Set(nb).size > 1) av.push('Todas las tarjetas tienen que tener <b>la misma cantidad de botones</b>.');
  return av;
}

// modelo viejo ({tarjetas:[{src,texto,btnTexto,btnUrl}]}) → modelo nuevo
function migrarPlantilla(bk) {
  if (bk.cuerpo !== undefined || bk.encabezado) return bk;
  const viejas = bk.tarjetas || [];
  bk.categoria = 'marketing';
  bk.encabezado = { tipo: viejas[0] && viejas[0].src ? 'imagen' : 'ninguno', texto: '', src: (viejas[0] || {}).src || '' };
  bk.cuerpo = (viejas[0] || {}).texto || '';
  bk.pie = '';
  bk.botones = (viejas[0] || {}).btnTexto
    ? [{ tipo: (viejas[0].btnUrl ? 'enlace' : 'rapida'), texto: viejas[0].btnTexto, url: viejas[0].btnUrl || '' }] : [];
  if (viejas.length > 1) {
    bk.formato = 'carrusel';
    bk.tarjetas = viejas.map(v => ({
      src: v.src || '', cuerpo: v.texto || '',
      botones: v.btnTexto ? [{ tipo: v.btnUrl ? 'enlace' : 'rapida', texto: v.btnTexto, url: v.btnUrl || '' }] : [],
    }));
  } else {
    bk.formato = 'simple';
    bk.tarjetas = [{ src: '', cuerpo: '', botones: [] }, { src: '', cuerpo: '', botones: [] }];
  }
  return bk;
}

function lbl(t) { const s = document.createElement('div'); s.className = 'bk-lbl'; s.textContent = t; return s; }
function iconMini(obj, prop) {
  const wrap = document.createElement('div'); wrap.className = 'bk-iconmini';
  BK_ICONOS.forEach(k => {
    const b = document.createElement('button'); b.type = 'button';
    b.innerHTML = `<svg viewBox="0 0 24 24">${ICONS[k] || ''}</svg>`;
    if (obj[prop] === k) b.classList.add('sel');
    b.onclick = () => { obj[prop] = k; renderCanvas(); renderInspector(); };
    wrap.appendChild(b);
  });
  return wrap;
}

// ---- apariencia: moverla al panel lateral cuando el tipo es Documento ----
function moveApA(slotSel) { const ap = $('#apSec'), slot = $(slotSel); if (ap && slot && ap.parentNode !== slot) { slot.appendChild(ap); ap.classList.add('open'); } }

function renderGbEditor() { moveApA('#gbApSlot'); renderGbAdd(); renderCanvas(); renderInspector(); }

// ---- panel: agregar bloque (desplegables Texto / Elementos) ----
/* ---- miniaturas de la paleta ----
   Dibujadas a mano en un viewBox de 40x26, todo en currentColor: cero archivos
   externos y funcionan offline. Muestran la FORMA del bloque, que es lo que el
   usuario reconoce; nadie sabe qué es un "kicker" leyendo la palabra. */
const svgMini = s => `<svg class="gb-mini" viewBox="0 0 40 26" aria-hidden="true">${s}</svg>`;
const rc = (x, y, w, h, o = 1) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="1.2" opacity="${o}"/>`;
const BLOQUE_MINI = {
  ref: rc(4, 8, 11, 11, .5) + rc(19, 9, 17, 3.5) + rc(19, 15, 11, 3, .45),
  titulo: rc(4, 6, 32, 6) + rc(4, 15, 20, 3, .35),
  subtitulo: rc(4, 7, 22, 5) + rc(4, 15, 32, 3, .35) + rc(4, 20, 26, 3, .35),
  parrafo: rc(4, 6, 32, 3, .55) + rc(4, 12, 32, 3, .55) + rc(4, 18, 22, 3, .55),
  destacado: rc(4, 6, 32, 4.5, .8) + rc(4, 14, 24, 4.5, .8),
  kicker: rc(4, 8, 7, 10) + rc(14, 11, 20, 4, .45),
  lista: [6, 13, 20].map(y => `<circle cx="7" cy="${y}" r="2.6"/>` + rc(13, y - 1.5, 22, 3, .45)).join(''),
  pasos: '<line x1="8" y1="13" x2="32" y2="13" opacity=".35"/><circle cx="8" cy="13" r="4"/><circle cx="20" cy="13" r="4" opacity=".6"/><circle cx="32" cy="13" r="4" opacity=".35"/>',
  chat: '<rect x="4" y="5" width="20" height="7" rx="3.5" opacity=".45"/><rect x="16" y="15" width="20" height="7" rx="3.5"/>',
  situacion: '<rect x="3" y="4" width="34" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".45"/>' + rc(6, 7, 11, 4) + rc(6, 14, 20, 3, .45),
  nota: rc(4, 5, 3, 16) + rc(10, 7, 25, 3, .45) + rc(10, 13, 18, 3, .45),
  advertencia: '<path d="M20 3.5 34 22.5H6z" opacity=".3"/>' + rc(18.8, 10, 2.4, 6) + rc(18.8, 18.6, 2.4, 2.4),
  separador: rc(4, 12, 32, 3),
  espacio: rc(4, 4, 32, 3, .35) + rc(4, 19, 32, 3, .35),
  tabla: rc(4, 5, 32, 4) + [11, 16, 21].map(y => rc(4, y, 9, 3, .4) + rc(15.5, y, 9, 3, .4) + rc(27, y, 9, 3, .4)).join(''),
  kpis: [4, 15, 26].map(x => `<rect x="${x}" y="6" width="10" height="14" rx="2" opacity=".18"/>` + rc(x + 2, 9, 6, 5) + rc(x + 2, 16, 6, 2, .5)).join(''),
  barras: [[30, 1], [22, .7], [14, .45]].map(([w, o], i) => rc(4, 5 + i * 7, w, 5, o)).join(''),
  podio: rc(4, 14, 10, 10, .45) + rc(15, 7, 10, 17) + rc(26, 17, 10, 7, .3),
  tarjetas: [4, 15, 26].map(x => `<rect x="${x}" y="6" width="10" height="14" rx="2" opacity=".18"/><circle cx="${x + 5}" cy="11" r="2.4"/>` + rc(x + 2, 16, 6, 2, .5)).join(''),
  diapo: '<rect x="3" y="4" width="34" height="18" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3"/>' + rc(9, 11, 22, 4, .5),
  imagen: '<rect x="4" y="5" width="32" height="16" rx="2.5" opacity=".18"/><circle cx="12" cy="10" r="2.4"/><path d="M7 21l7-7 5 5 4-4 6 6z"/>',
  video: '<rect x="4" y="5" width="32" height="16" rx="2.5" opacity=".18"/><polygon points="17,9 26,13 17,17"/>',
  galeria: [4, 15, 26].map(x => [5, 14].map(y => `<rect x="${x}" y="${y}" width="10" height="7" rx="1.5" opacity=".55"/>`).join('')).join(''),
  pdf: '<path d="M10 3h12l6 6v14H10z" opacity=".18"/><path d="M22 3l6 6h-6z"/>' + rc(13, 13, 12, 3, .55) + rc(13, 18, 8, 3, .55),
  embed: '<rect x="3" y="4" width="34" height="18" rx="2.5" opacity=".18"/>' + rc(3, 4, 34, 4, .45) + rc(7, 12, 26, 3, .45) + rc(7, 17, 18, 3, .45),
  boton: '<rect x="9" y="9" width="22" height="9" rx="4.5"/>',
  plantilla: '<rect x="11" y="3" width="18" height="21" rx="2.5" opacity=".18"/><rect x="13" y="5" width="14" height="8" rx="1.5" opacity=".5"/>' + rc(13, 15, 14, 2.5, .5) + '<rect x="13" y="19" width="14" height="4" rx="2"/>',
};
const sinTilde = s => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
// qué grupos dejó abiertos el usuario (se recuerda mientras edita)
const GB_ABIERTOS = new Set(['Texto']);

function renderGbAdd() {
  const box = $('#gbAdd');
  // Se redibuja siempre (ya no se memoiza): el buscador filtra en cada tecla.
  // El grupo Presentación sigue apareciendo SOLO en modo presentación, si no
  // los cortes de diapositiva terminaban como divs vacíos en la intranet.
  box.innerHTML = '';
  const q = sinTilde(($('#gbBuscar') || {}).value || '').trim();
  let hay = 0;
  // grupos de la maqueta: siempre a la vista, con su cuenta al lado del rótulo
  Object.entries(GRUPOS_BLOQUE).forEach(([grupo, tipos]) => {
    if (grupo === 'Presentación' && !PRESENTACION) return;
    const vis = tipos.filter(t => !q ||
      sinTilde(BLOQUE_INFO[t].label + ' ' + BLOQUE_INFO[t].desc + ' ' + (ALIAS_BLOQUE[t] || '')).includes(q));
    if (!vis.length) return;
    hay += vis.length;
    const g = document.createElement('div'); g.className = 'pal-grupo';
    g.innerHTML = `<h5>${esc(grupo)} <span class="n">${vis.length}</span></h5>`;
    const grid = document.createElement('div'); grid.className = 'pal-grid';
    vis.forEach(t => {
      const inf = BLOQUE_INFO[t];
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'pal-b'; b.dataset.t = t; b.title = inf.desc;
      b.innerHTML = '<span class="mini">' + svgMini(BLOQUE_MINI[t] || '') + '</span>' +
        '<span class="rot">' + esc(inf.label) + '</span>';
      b.onclick = () => insertBloque(t);
      grid.appendChild(b);
    });
    g.appendChild(grid); box.appendChild(g);
  });
  if (!hay) box.insertAdjacentHTML('beforeend',
    '<div class="gb-nores">Ningún bloque se llama así. Probá <b>tabla</b>, <b>foto</b>, <b>descargas</b> o <b>whatsapp</b>.</div>');
}

// el panel derecho sigue a lo que tocás
function gbPane(p) {
  const panes = $('#gbPanes'); if (!panes) return;
  panes.querySelectorAll('.seg-b').forEach(b => b.classList.toggle('active', b.dataset.pane === p));
  $('#gbSidebar').querySelectorAll('.gb-pane').forEach(d => { d.hidden = d.dataset.pane !== p; });
  if (p === 'ajustes') $('#gbTabAjustes').classList.remove('avisa');
}
if ($('#gbPanes')) {
  $('#gbPanes').onclick = e => { const b = e.target.closest('.seg-b'); if (b) gbPane(b.dataset.pane); };
}
if ($('#btnPegar')) $('#btnPegar').onclick = pegarDesdePortapapeles;

/* ===================================================================
   AVISAR NOVEDAD
   Publicar y avisar son dos cosas distintas: muchas publicaciones son para ir
   viendo cómo queda. Acá se elige qué módulos se anuncian, y por eso el aviso
   nunca sale sin querer.
   =================================================================== */
function hoyLocal() {
  const d = new Date(), p = n => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
}
function diasDeNovedad(f) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(f || '')) return null;
  const p = f.split('-').map(Number);
  const h = new Date();
  return Math.round((Date.UTC(h.getFullYear(), h.getMonth(), h.getDate()) -
    Date.UTC(p[0], p[1] - 1, p[2])) / 86400000);
}

(function initAvisar() {
  const modal = $('#avisarModal'); if (!modal) return;
  const cerrar = () => { esconderModal(modal); };
  modal.querySelectorAll('[data-cerrar-avisar]').forEach(b => { b.onclick = cerrar; });

  $('#btnAvisar').onclick = () => {
    const caja = $('#avisarLista'); caja.innerHTML = '';
    (MODULOS || []).forEach((m, i) => {
      if (esCartelera(m.content)) return;   // la cartelera avisa por sí sola
      const d = diasDeNovedad(m.actualizado);
      const anunciado = d !== null && d <= 14;
      // fila de la maqueta: casilla dibujada + título + estado
      const fila = document.createElement('button');
      fila.type = 'button';
      fila.className = 'chk';
      fila.setAttribute('aria-pressed', anunciado ? 'true' : 'false');
      const c = document.createElement('input');
      c.type = 'checkbox'; c.checked = anunciado; c.dataset.i = i; c.hidden = true;
      fila.onclick = () => {
        c.checked = !c.checked;
        fila.setAttribute('aria-pressed', c.checked ? 'true' : 'false');
      };
      const sub = anunciado
        ? 'Anunciado ' + (d <= 0 ? 'hoy' : 'hace ' + d + (d === 1 ? ' día' : ' días'))
        : (m.actualizado ? 'Se anunció el ' + m.actualizado : 'Sin anunciar');
      fila.innerHTML = '<span class="caja"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 6 9 17l-5-5"/></svg></span>' +
        '<span class="t"><b>' + esc(m.title || m.key) + '</b><span>' + esc(sub) + '</span></span>' +
        (anunciado ? '<span class="ya">Ya avisado</span>' : '');
      fila.appendChild(c);
      caja.appendChild(fila);
    });
    abrirModal(modal);
  };

  $('#avisarGuardar').onclick = async () => {
    const hoy = hoyLocal();
    let n = 0;
    $('#avisarLista').querySelectorAll('input[type=checkbox]').forEach(c => {
      const m = MODULOS[+c.dataset.i]; if (!m) return;
      const d = diasDeNovedad(m.actualizado);
      const estaba = d !== null && d <= 14;
      if (c.checked && !estaba) { m.actualizado = hoy; n++; }        // se anuncia
      else if (!c.checked && estaba) { delete m.actualizado; n++; }  // se saca del aviso
    });
    if (!n) { cerrar(); toast('No cambiaste ningún aviso.'); return; }
    try {
      await persistModulos(false);
      cerrar();
      toast('Avisos actualizados. Publicando…');
      await publicarCambios(true);      // ya se confirmó acá, no vuelve a preguntar
    } catch (e) { toast(e.message, 'err'); }
  };
})();

/* ===================================================================
   HISTORIAL DE PUBLICACIONES (y volver atrás)
   Cada publicación ya quedaba guardada como una versión; lo que faltaba era
   poder verla y volver. Restaurar NO publica: trae la versión al panel para
   que la revises, y recién después apretás Publicar.
   =================================================================== */
(function initHistorial() {
  const modal = $('#histModal'); if (!modal) return;
  const cerrar = () => { esconderModal(modal); };
  modal.querySelectorAll('[data-cerrar-hist]').forEach(b => { b.onclick = cerrar; });

  const fechaLinda = f => {
    const d = new Date((f || '').replace(' ', 'T') + 'Z');
    if (isNaN(d)) return f || '';
    return d.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit' });
  };

  $('#btnHistorial').onclick = async () => {
    abrirModal(modal);
    const caja = $('#histLista');
    caja.innerHTML = '<div class="muted">Buscando las últimas publicaciones…</div>';
    let r;
    try { r = await api('/api/historial'); }
    catch (e) { caja.innerHTML = '<div class="hist-err">' + esc(e.message || 'No pude consultar el historial.') + '</div>'; return; }
    if (!r.ok) { caja.innerHTML = '<div class="hist-err">' + esc(r.error) + '</div>'; return; }
    if (!r.versiones.length) { caja.innerHTML = '<div class="muted">Todavía no hay publicaciones.</div>'; return; }

    caja.innerHTML = '';
    r.versiones.forEach((v, i) => {
      // hito de la línea de tiempo (maqueta): el de hoy lleva el punto verde
      const fila = document.createElement('div'); fila.className = 'hito' + (i === 0 ? ' hoy' : '');
      fila.innerHTML =
        '<b>' + esc(v.mensaje || 'Actualización desde el panel') + '</b>' +
        '<span class="cuando">' + esc(fechaLinda(v.fecha)) +
        (i === 0 ? ' · la que está publicada' : '') + '</span>';
      if (i > 0) {
        const wrap = document.createElement('span'); wrap.className = 'acc-h';
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'btn btn-2'; b.textContent = 'Volver a esta versión';
        b.onclick = async () => {
          if (!await confirmar(
            'Se va a traer al panel el contenido tal como estaba el ' + fechaLinda(v.fecha) + '.\n\n' +
            'Todavía NO se publica: lo revisás acá y, si está bien, apretás Publicar.\n' +
            'Lo que tenés ahora queda guardado en una copia.',
            'Sí, traerla', 'Volver a una versión anterior', 'ok')) return;
          b.disabled = true; b.textContent = 'Trayendo…';
          try {
            const res = await api('/api/restaurar', { method: 'POST', body: JSON.stringify({ sha: v.sha }) });
            if (!res.ok) throw new Error(res.error || 'No se pudo restaurar');
            cerrar();
            await cargarModulos();
            MODULOS.forEach(m => marcarEditado(m.key));   // queda pendiente de publicar
            pintarModulos();
            toast('Listo: volviste a la versión del ' + fechaLinda(v.fecha) + '. Revisala y publicá.', 'ok');
          } catch (e) {
            b.disabled = false; b.textContent = 'Volver a esta versión';
            toast(e.message, 'err');
          }
        };
        wrap.appendChild(b);
        fila.appendChild(wrap);
      }
      caja.appendChild(fila);
    });
  };
})();
if ($('#gbBuscar')) {
  const bus = $('#gbBuscar');
  bus.oninput = () => renderGbAdd();
  bus.onkeydown = e => {
    if (e.key === 'Escape') { bus.value = ''; renderGbAdd(); }
    // Enter inserta el primero: buscás "excel", Enter, y ya tenés la tabla
    if (e.key === 'Enter') {
      const b = $('#gbAdd .pal-b');
      if (b) { b.click(); bus.value = ''; renderGbAdd(); }
    }
  };
}

// ---- movimiento: reinicia una animación aunque la clase ya esté puesta ----
const sinMovimiento = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function reanimar(el, clase, ms) {
  if (!el || sinMovimiento()) return;
  el.classList.remove(clase);
  void el.offsetWidth;                       // fuerza el reinicio
  el.classList.add(clase);
  if (ms) setTimeout(() => el.classList.remove(clase), ms);
}
function bloqueEl(i) { return $('#gbDoc').querySelector(`.gb-block[data-i="${i}"]`); }

function insertBloque(t) {
  const nb = bloqueNuevo(t);
  if (SEL != null && SEL < BLOQUES.length) { BLOQUES.splice(SEL + 1, 0, nb); SEL++; }
  else { BLOQUES.push(nb); SEL = BLOQUES.length - 1; }
  renderCanvas(); renderInspector();
  reanimar(bloqueEl(SEL), 'gb-nuevo', 400);   // el bloque nuevo entra, no aparece de golpe
  // recién insertado se pasa DERECHO a sus ajustes: es lo primero que hay que
  // tocar y antes había que ir a buscar la pestaña a mano
  gbPane('ajustes');
  const el = $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"] [contenteditable]`);
  if (el) { el.focus(); el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
  else { const b = bloqueEl(SEL); if (b) b.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
}
function addBloque(t) { insertBloque(t); }   // alias compat
function moverBloque(i, d) { const j = i + d; if (j < 0 || j >= BLOQUES.length) return;[BLOQUES[i], BLOQUES[j]] = [BLOQUES[j], BLOQUES[i]]; SEL = j; renderCanvas(); selectBlock(j); }
function borrarBloque(i) {
  // checkpoint YA, sin esperar el tick del watcher: si tocan "Deshacer" del
  // toast al segundo, el tope de la pila tiene que ser JUSTO el pre-borrado
  vigilarEstado();
  const quitar = () => {
    BLOQUES.splice(i, 1);
    SEL = BLOQUES.length ? Math.min(i, BLOQUES.length - 1) : null;
    renderCanvas();
    if (SEL != null) selectBlock(SEL); else renderInspector();
    vigilarEstado();   // registra el borrado como paso propio de deshacer
    toastAccion('Bloque eliminado', 'Deshacer', () => deshacer());
  };
  const el = bloqueEl(i);
  if (!el || sinMovimiento()) return quitar();
  el.classList.add('gb-saliendo');            // se va desvaneciendo antes de irse
  setTimeout(quitar, 170);
}

// ---- canvas: el documento real, editable inline ----
function gbHandle() { return `<div class="gb-handle"><button type="button" class="gb-grip" data-lbl="Arrastrar para mover" aria-label="Arrastrar para mover"><svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" aria-hidden="true" focusable="false"><circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg></button><button type="button" class="gb-h-up" data-lbl="Subir" aria-label="Subir"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 19V5m0 0-6 6m6-6 6 6"/></svg></button><button type="button" class="gb-h-down" data-lbl="Bajar" aria-label="Bajar"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M12 5v14m0 0 6-6m-6 6-6-6"/></svg></button><button type="button" class="gb-h-del" data-lbl="Eliminar bloque" aria-label="Eliminar bloque"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>`; }

// ---- arrastrar bloques para reordenar (pointer events, desde el grip ⠿) ----
(function initBlockDrag() {
  const doc = $('#gbDoc'); if (!doc) return;
  let dragI = null, blockEl = null, linea = null, grip = null, pid = null;
  function indiceDestino(y) {
    for (const b of doc.querySelectorAll('.gb-block')) {
      if (b === blockEl) continue;
      const r = b.getBoundingClientRect();
      if (y < r.top + r.height / 2) return +b.dataset.i;
    }
    return BLOQUES.length;
  }
  function onMove(e) {
    if (dragI === null) return;
    const ti = indiceDestino(e.clientY);
    const ref = [...doc.querySelectorAll('.gb-block')].find(b => +b.dataset.i === ti);
    if (ref) doc.insertBefore(linea, ref); else doc.appendChild(linea);
  }
  function onUp(e) {
    if (grip) { grip.removeEventListener('pointermove', onMove); grip.removeEventListener('pointerup', onUp); grip.removeEventListener('pointercancel', onUp); try { grip.releasePointerCapture(pid); } catch (_) {} }
    if (linea && linea.parentNode) linea.remove();
    if (blockEl) blockEl.classList.remove('gb-dragging');
    if (dragI !== null) {
      let ti = indiceDestino(e.clientY);
      const item = BLOQUES.splice(dragI, 1)[0];
      if (ti > dragI) ti--;
      ti = Math.max(0, Math.min(ti, BLOQUES.length));
      BLOQUES.splice(ti, 0, item);
      SEL = ti; renderCanvas(); selectBlock(ti);
      reanimar(bloqueEl(ti), 'gb-recien', 700);   // marca dónde quedó
    }
    dragI = null; blockEl = null; grip = null; pid = null;
  }
  doc.addEventListener('pointerdown', e => {
    const g = e.target.closest('.gb-grip'); if (!g) return;
    const block = g.closest('.gb-block'); if (!block) return;
    e.preventDefault();
    dragI = +block.dataset.i; blockEl = block; grip = g; pid = e.pointerId;
    block.classList.add('gb-dragging');
    if (!linea) { linea = document.createElement('div'); linea.className = 'gb-droplinea'; }
    try { g.setPointerCapture(pid); } catch (_) {}
    g.addEventListener('pointermove', onMove);
    g.addEventListener('pointerup', onUp);
    g.addEventListener('pointercancel', onUp);
  });
})();

/* ---- botón "+" en el hueco entre bloques ----
   `insertBloque` mete el bloque nuevo DEBAJO del seleccionado. Esa regla no la
   descubre nadie: el usuario inserta al final y después sube el bloque a los
   golpes con ↑. Este botón la vuelve visible — aparece justo en el hueco donde
   tenés el mouse y deja el nuevo ahí.
   Vive FUERA de #gbDoc (que se reescribe entero en cada renderCanvas), así que
   no ensucia ni un byte del HTML que se publica. */
(function initMasEntre() {
  const canvas = document.querySelector('.gb-canvas');
  const doc = $('#gbDoc');
  if (!canvas || !doc) return;

  const b = document.createElement('button');
  b.type = 'button'; b.className = 'gb-mas'; b.textContent = '+';
  b.title = 'Agregar un bloque acá'; b.hidden = true;
  canvas.appendChild(b);
  let destino = null;

  const esconder = () => { b.hidden = true; destino = null; };

  canvas.addEventListener('mousemove', e => {
    if (!BLOQUES.length || $('#viewDetalle').hidden) return esconder();
    let mejor = null, dist = 1e9;
    doc.querySelectorAll('.gb-block').forEach(el => {
      const r = el.getBoundingClientRect();
      const d = Math.abs(e.clientY - r.bottom);
      if (d < dist && d < 22) { dist = d; mejor = el; }     // cerca del borde de abajo
    });
    if (!mejor) return esconder();
    const r = mejor.getBoundingClientRect(), c = canvas.getBoundingClientRect();
    destino = +mejor.dataset.i;
    b.style.top = (r.bottom - c.top + canvas.scrollTop - 13) + 'px';
    b.style.left = (r.left - c.left + canvas.scrollLeft + r.width / 2 - 13) + 'px';
    b.hidden = false;
  });
  canvas.addEventListener('mouseleave', esconder);
  canvas.addEventListener('scroll', esconder);

  b.onclick = () => {
    if (destino == null) return;
    selectBlock(destino);            // el bloque nuevo cae justo debajo de este
    gbPane('agregar');               // …y la paleta queda lista para elegirlo
    const s = $('#gbBuscar');
    if (s) { s.value = ''; renderGbAdd(); s.focus(); }
  };
})();

/* ===================================================================
   BLOQUES DE DATOS (tabla / números / barras / podio / tarjetas)
   Un solo constructor por bloque, usado por el canvas del editor (ed=true,
   con las zonas editables) y por el HTML final que se publica (ed=false).
   Así el editor y el sitio no se pueden desincronizar.
   =================================================================== */
// zona editable: en el canvas es contenteditable, en el HTML final es texto pelado
function zona(ed, valor, attrs, ph) {
  const v = valor || '';
  if (!ed) return v;
  return `<span contenteditable ${attrs}${ph ? ` data-ph="${esc(ph)}"` : ''}>${v}</span>`;
}
// pasa "1.116", "4,5%" o "362" a número (para calcular el largo de las barras)
function numDe(v) {
  const n = parseFloat(String(v == null ? '' : v).replace(/\./g, '').replace(',', '.').replace(/[^\d.\-]/g, ''));
  return isFinite(n) ? n : 0;
}
const TENDS = { up: '▲', down: '▼', flat: '▬' };
const TONOS = [['g', 'Verde'], ['y', 'Amarillo'], ['r', 'Rojo'], ['gr', 'Gris']];
// qué ítem se agrega cuando apretás Enter dentro de uno de estos bloques
const ITEM_NUEVO = {
  kpis: p => ({ label: '', valor: '', pie: '', tend: p.tend || '', lead: false }),
  barras: p => ({ label: '', valor: '', color: p.color || '--c-hudson', chip: '', tono: p.tono || 'gr' }),
  podio: p => ({ puesto: '', nombre: '', suc: '', valor: '', vlabel: p.vlabel || 'ventas', extra: '', lead: false }),
  tarjetas: p => ({ icono: p.icono || 'award', color: p.color || '--c-hudson', titulo: '', texto: '' }),
};

function tablaHTML(bk, ed) {
  const cols = bk.cols || [], filas = bk.filas || [];
  const ord = !!bk.orden, busc = !!bk.buscar;
  const th = cols.map((c, ci) => {
    const cls = [c.num ? 'num' : '', ord ? 'ord' : ''].filter(Boolean).join(' ');
    const txt = zona(ed, c.h, `data-prop="colh" data-c="${ci}"`, 'Columna');
    // La flechita la dibuja el CSS mirando aria-sort, así el HTML guardado no
    // se lleva ningún estado de ordenamiento adentro.
    // En el canvas del editor va un <span> y no un <button>: un contenteditable
    // adentro de un <button> no se puede editar.
    const inner = !ord ? txt
      : (ed ? `<span class="th-b">${txt}<span class="th-c" aria-hidden="true"></span></span>`
        : `<button type="button" class="th-b">${txt}<span class="th-c" aria-hidden="true"></span></button>`);
    return `<th${cls ? ` class="${cls}"` : ''}${ord ? ' aria-sort="none"' : ''}>${inner}</th>`;
  }).join('');
  const tr = filas.map((f, ri) => {
    const celdas = f.celdas || [];
    const tds = cols.map((c, ci) =>
      `<td${c.num ? ' class="num"' : ''}>${zona(ed, celdas[ci], `data-prop="celda" data-r="${ri}" data-c="${ci}"`, '—')}</td>`).join('');
    return `<tr${f.destaque ? ` class="fx-${f.destaque}"` : ''}>${tds}</tr>`;
  }).join('');
  const tabla = `<div class="m-tabla"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
  // sin ordenar ni buscar devuelve EXACTAMENTE lo mismo que siempre:
  // las tablas ya publicadas no cambian ni un pixel
  if (!ord && !busc) return tabla;
  const barra = busc
    ? `<div class="tb-bar"><input type="search" class="tb-q" placeholder="Buscar en la tabla…" aria-label="Buscar en la tabla"${ed ? ' disabled' : ''}><span class="tb-cont"></span><button type="button" class="tb-limpiar" hidden>Limpiar</button></div>`
    : '';
  const pista = ord ? '<div class="tb-pista">↕ Tocá un título para ordenar</div>' : '';
  return `<div class="m-tablaw">${barra}${pista}${tabla}<div class="tb-nada" hidden>No hay filas que coincidan con la búsqueda.</div></div>`;
}

function kpisHTML(bk, ed) {
  const items = ed ? (bk.items || []) : (bk.items || []).filter(k => txtOf(k.valor).length || txtOf(k.label).length);
  if (!items.length) return '';
  return `<div class="m-kpis">${items.map((k, idx) => `
    <div class="kpi${k.lead ? ' lead' : ''}">
      <div class="kl">${zona(ed, k.label, `data-prop="items" data-idx="${idx}" data-sub="label"`, 'Período')}</div>
      <div class="kv">${zona(ed, k.valor, `data-prop="items" data-idx="${idx}" data-sub="valor"`, '0')}</div>
      <div class="kt${k.tend ? ' t-' + k.tend : ''}">${k.tend ? TENDS[k.tend] + ' ' : ''}${zona(ed, k.pie, `data-prop="items" data-idx="${idx}" data-sub="pie"`, ed ? 'nota' : '')}</div>
    </div>`).join('')}</div>`;
}

// recalcula el ancho de las barras ya dibujadas (mismo criterio que barrasHTML)
function refrescarBarras(block, bk) {
  const items = bk.items || [];
  const max = Math.max(1, ...items.map(b => numDe(b.valor)));
  block.querySelectorAll('.m-barras .bf').forEach((el, i) => {
    if (!items[i]) return;
    el.style.width = Math.max(6, Math.round(numDe(items[i].valor) / max * 100)) + '%';
  });
}

function barrasHTML(bk, ed) {
  const items = ed ? (bk.items || []) : (bk.items || []).filter(b => txtOf(b.label).length);
  if (!items.length) return '';
  const max = Math.max(1, ...items.map(b => numDe(b.valor)));
  return `<div class="m-barras">${items.map((b, idx) => {
    const w = Math.max(6, Math.round(numDe(b.valor) / max * 100));
    return `<div class="ba">
      <div class="bl">${zona(ed, b.label, `data-prop="items" data-idx="${idx}" data-sub="label"`, 'Nombre')}</div>
      <div class="bt"><div class="bf" style="width:${w}%;background:var(${b.color || '--c-hudson'})"><span class="bn">${zona(ed, b.valor, `data-prop="items" data-idx="${idx}" data-sub="valor"`, '0')}</span></div></div>
      <div class="br">${(ed || txtOf(b.chip).length) ? `<span class="bchip ${b.tono || 'gr'}">${zona(ed, b.chip, `data-prop="items" data-idx="${idx}" data-sub="chip"`, 'etiqueta')}</span>` : ''}</div>
    </div>`;
  }).join('')}</div>`;
}

function podioHTML(bk, ed) {
  const items = ed ? (bk.items || []) : (bk.items || []).filter(p => txtOf(p.nombre).length);
  if (!items.length) return '';
  return `<div class="m-podio">${items.map((p, idx) => `
    <div class="pod${p.lead ? ' lead' : ''}">
      <div class="rank">${zona(ed, p.puesto, `data-prop="items" data-idx="${idx}" data-sub="puesto"`, '1°')}</div>
      <div class="name">${zona(ed, p.nombre, `data-prop="items" data-idx="${idx}" data-sub="nombre"`, 'Nombre')}</div>
      <div class="suc">${zona(ed, p.suc, `data-prop="items" data-idx="${idx}" data-sub="suc"`, 'Sucursal')}</div>
      <div class="sales">${zona(ed, p.valor, `data-prop="items" data-idx="${idx}" data-sub="valor"`, '0')}</div>
      <div class="slbl">${zona(ed, p.vlabel, `data-prop="items" data-idx="${idx}" data-sub="vlabel"`, 'ventas')}</div>
      ${(ed || txtOf(p.extra).length) ? `<div class="cv">${zona(ed, p.extra, `data-prop="items" data-idx="${idx}" data-sub="extra"`, 'conv. 0%')}</div>` : ''}
    </div>`).join('')}</div>`;
}

function tarjetasHTML(bk, ed) {
  const items = ed ? (bk.items || []) : (bk.items || []).filter(c => txtOf(c.titulo).length || txtOf(c.texto).length);
  if (!items.length) return '';
  return `<div class="m-tarj cols-${bk.cols || 3} orient-${bk.orient || 'v'}">${items.map((c, idx) => `
    <div class="tj">
      <span class="tj-ic" style="background:var(${c.color || '--c-hudson'})">${ICO(c.icono || 'award')}</span>
      <div class="tj-b">
        <div class="tj-t">${zona(ed, c.titulo, `data-prop="items" data-idx="${idx}" data-sub="titulo"`, 'Título')}</div>
        <div class="tj-p">${zona(ed, c.texto, `data-prop="items" data-idx="${idx}" data-sub="texto"`, 'Texto de la tarjeta…')}</div>
      </div>
    </div>`).join('')}</div>`;
}

function bloqueCanvas(bk, i) {
  const ed = (cls, prop, ph, extra) => `<${cls.tag} class="${cls.cls}" contenteditable data-prop="${prop}" data-ph="${ph}"${extra || ''}>${bk[prop] || ''}</${cls.tag}>`;
  let inner = '';
  switch (bk.t) {
    case 'destacado': inner = ed({ tag: 'p', cls: 'm-lead' }, 'html', 'Texto destacado…'); break;
    case 'titulo': inner = `<div class="${bk.nivel === 'h2' ? 'm-h2' : 'm-h'}" contenteditable data-prop="html" data-ph="${bk.nivel === 'h2' ? 'Subtítulo…' : 'Título…'}">${bk.html || ''}</div>`; break;
    case 'parrafo': inner = ed({ tag: 'p', cls: 'm-p' }, 'html', 'Escribí el texto…'); break;
    case 'kicker': inner = `<div class="m-kicker">${bk.n ? `<span class="n">${esc(bk.n)}</span>` : ''}<span contenteditable data-prop="html" data-ph="Etiqueta…">${bk.html || ''}</span></div>`; break;
    case 'nota': inner = `<div class="note"${bk.color ? ` style="--nota-acc:var(${bk.color})"` : ''}>${ICO(bk.icono || 'clock')}<div class="nt" contenteditable data-prop="html" data-ph="Texto de la nota…">${bk.html || ''}</div></div>`; break;
    case 'advertencia': inner = `<div class="m-warn"><span class="ico">${SVG_WARN}</span><div class="mw-tx" contenteditable data-prop="html" data-ph="Escribí acá la advertencia…">${bk.html || ''}</div></div>`; break;
    case 'lista': inner = `<div class="checklist">${(bk.items || []).map((it, idx) => { const o = (typeof it === 'string') ? { icono: 'check', html: it } : it; return `<div class="ci"><span class="ci-ic" style="background:var(${o.color || '--c-success'})">${ICO(o.icono || 'check')}</span><span contenteditable data-prop="items" data-idx="${idx}" data-sub="html" data-ph="Ítem…">${o.html || ''}</span></div>`; }).join('')}</div>`; break;
    case 'chat': inner = `<div class="chat"><div class="blabel" contenteditable data-prop="label" data-ph="Etiqueta">${bk.label || ''}</div>${(bk.items || []).map((m, idx) => { const it = (typeof m === 'string') ? { lado: 'out', html: m } : m; return `<div class="bubble ${it.lado === 'in' ? 'in' : 'out'}"><span contenteditable data-prop="items" data-idx="${idx}" data-sub="html" data-ph="${it.lado === 'in' ? 'Mensaje del cliente…' : 'Mensaje del vendedor…'}">${it.html || ''}</span><span class="time">${it.lado === 'in' ? '' : '✓✓'}</span></div>`; }).join('')}</div>`; break;
    case 'situacion': inner = `<div class="situ"><div class="sit-head"><span class="sit-tag" style="background:var(${bk.tagColor || '--c-warn'})">${esc(bk.tag || 'Situación')}</span><span contenteditable data-prop="titulo" data-ph="Título de la situación…">${bk.titulo || ''}</span></div>${bk.conResp ? `<div class="sit-arrow" style="color:var(${bk.respColor || '--c-success'})">${ICO(bk.respIcono || 'arrowDR')} ${esc(bk.resp || 'Respuesta recomendada')}</div>` : ''}<div class="chat">${(bk.mensajes || []).map((m, idx) => { const it = (typeof m === 'string') ? { lado: 'out', html: m } : m; return `<div class="bubble ${it.lado === 'in' ? 'in' : 'out'}"><span contenteditable data-prop="mensajes" data-idx="${idx}" data-sub="html" data-ph="${it.lado === 'in' ? 'Mensaje del cliente…' : 'Mensaje del vendedor…'}">${it.html || ''}</span><span class="time">${it.lado === 'in' ? '' : '✓✓'}</span></div>`; }).join('')}</div></div>`; break;
    case 'plantilla': {
      migrarPlantilla(bk);
      // en el lienzo se ven las rutas locales; el html publicado usa las relativas
      inner = plantillaHTML(bk, true).replace(/src="assets\//g, 'src="/intranet/assets/')
        || '<div class="blk-ph">Armá la plantilla desde los ajustes de la derecha →</div>';
      break;
    }
    case 'pasos': inner = `<div class="flow">${(bk.steps || []).map((s, idx) => `${idx ? `<div class="arrow">${ICO(s.conector || 'arrowR')}</div>` : ''}<div class="step"><div class="si" style="background:var(${s.color || '--c-caba'})">${ICO(s.icono || 'check')}</div><div class="st" contenteditable data-prop="steps" data-idx="${idx}" data-sub="titulo" data-ph="Título">${s.titulo || ''}</div><div class="sd" contenteditable data-prop="steps" data-idx="${idx}" data-sub="desc" data-ph="Descripción">${s.desc || ''}</div></div>`).join('')}</div>`; break;
    case 'separador': inner = `<div class="m-sep" style="height:${bk.grosor || 4}px"></div>`; break;
    case 'espacio': inner = `<div style="height:${({ sm: 14, md: 30, lg: 54 })[bk.alto] || 24}px;border:1px dashed var(--line);border-radius:6px"></div>`; break;
    case 'imagen': inner = bk.src
      ? `<figure class="blk-img tam-${bk.tam || 'md'}"><img src="/intranet/${esc(bk.src)}?t=${Date.now()}" alt="${esc(bk.alt || '')}"><figcaption contenteditable data-prop="caption" data-ph="Epígrafe (opcional)…">${bk.caption || ''}</figcaption>${bk.descargable ? `<a class="dl-btn" href="#" onclick="return false">${ICO('download')} Descargar</a>` : ''}</figure>`
      : `<div class="blk-ph">Subí una imagen desde los ajustes de la derecha →</div>`; break;
    case 'galeria': { const its = (bk.items || []).filter(it => it.src); inner = `<div class="dl-section"><div class="m-kicker"><span contenteditable data-prop="titulo" data-ph="Título de la sección…">${bk.titulo || ''}</span></div>${its.length ? `<div class="gallery">${(bk.items || []).map((it, idx) => it.src ? `<div class="gcard"><img class="gimg" src="/intranet/${esc(it.src)}?t=${Date.now()}" alt=""><div class="gmeta"><div class="gtitle" contenteditable data-prop="items" data-idx="${idx}" data-sub="nombre" data-ph="Nombre de la placa…">${it.nombre || ''}</div><a class="dl-btn" href="#" onclick="return false">${ICO('download')} Descargar</a></div></div>` : '').join('')}</div>` : `<div class="blk-ph">Agregá placas desde el panel de la derecha →</div>`}</div>`; break; }
    case 'video': {
      // el canvas se re-dibuja en CADA tecla: sin ?t= para no re-descargar el mp4
      const fuente = bk.src ? `<video src="/intranet/${esc(bk.src)}" controls preload="metadata" playsinline${bk.poster ? ` poster="/intranet/${esc(bk.poster)}"` : ''}></video>`
        : (bk.url ? `<iframe src="${esc(embedDeVideo(bk.url).url)}" loading="lazy" allowfullscreen></iframe>` : '');
      inner = fuente
        ? `<figure class="blk-video ${bk.orient === 'vert' ? 'vert' : 'horiz'} tam-${bk.tam || 'md'}" style="--arw:${arDe(bk)[0]};--arh:${arDe(bk)[1]}"><div class="v-box">${fuente}</div><figcaption contenteditable data-prop="caption" data-ph="Epígrafe (opcional)…">${bk.caption || ''}</figcaption>${bk.descargable && bk.src ? `<a class="dl-btn" href="#" onclick="return false">${ICO('download')} Descargar</a>` : ''}</figure>`
        : `<div class="blk-ph">Subí un video o pegá un link desde los ajustes de la derecha →</div>`;
      break;
    }
    case 'pdf': inner = bk.src
      ? (bk.modo === 'embebido'
        ? `<div class="blk-embed" data-h="${bk.alto || 'md'}"><iframe src="/intranet/${esc(bk.src)}#toolbar=0" loading="lazy"></iframe></div>`
        : `<div class="pdf-card"><span class="pdf-ic">${ICO('file')}</span><span class="pdf-meta"><span class="pdf-nombre">${esc(bk.nombre || 'Documento PDF')}</span><span class="pdf-sub">Tocar para abrir el PDF</span></span><span class="pdf-arrow">${ICO('ext')}</span></div>`)
      : `<div class="blk-ph">Subí un PDF desde los ajustes de la derecha →</div>`; break;
    case 'embed': inner = bk.url
      ? `<div class="blk-embed" data-h="${bk.alto || 'md'}"><iframe src="${esc(bk.url)}" loading="lazy"></iframe></div>`
      : `<div class="blk-ph">Pegá el link a embeber en los ajustes de la derecha →</div>`; break;
    case 'boton': inner = `<div class="blk-btn"><a class="dl-btn" href="#" onclick="return false">${ICO('ext')}<span contenteditable data-prop="texto" data-ph="Texto del botón…">${bk.texto || ''}</span></a></div>`; break;
    case 'ref': inner = `<div class="blk-ref"><span class="br-ic" style="background:var(${bk.color || '--c-hudson'})">${ICO(bk.icon || 'layers')}</span><span class="br-tx"><b>${esc(bk.mod || 'Ningún módulo elegido')}</b>${bk.sub ? ' › ' + esc(bk.sub) : ''}<span class="br-d">${esc([bk.clase, bk.detalle].filter(Boolean).join(' · '))}</span></span></div>`; break;
    case 'tabla': inner = tablaHTML(bk, true); break;
    case 'kpis': inner = kpisHTML(bk, true); break;
    case 'barras': inner = barrasHTML(bk, true); break;
    case 'podio': inner = podioHTML(bk, true); break;
    case 'tarjetas': inner = tarjetasHTML(bk, true); break;
    case 'diapo': inner = `<div class="gb-diapo${PRESENTACION ? '' : ' huerfano'}"><span class="gb-diapo-l">${PRESENTACION ? 'Diapositiva' : '⚠️ Corte sin uso'}</span><span class="gb-diapo-t" contenteditable data-prop="titulo" data-ph="Título de la diapositiva (para el menú)…">${bk.titulo || ''}</span>${PRESENTACION ? '' : '<span class="gb-diapo-av">Este documento se ve como página</span>'}</div>`; break;
    case 'html': inner = `<div class="blk-raw">${bk.html || ''}</div>`; break;
  }
  // el chip del seleccionado lee este nombre: el MISMO dato que el "Ajustes de:"
  const nom = (BLOQUE_INFO[bk.t === 'titulo' && bk.nivel === 'h2' ? 'subtitulo' : bk.t] || { label: bk.t }).label;
  return `<div class="db gb-block" data-i="${i}" data-nom="${esc(nom)}">${gbHandle()}${inner}</div>`;
}

function renderCanvas() {
  const doc = $('#gbDoc');
  doc.innerHTML = BLOQUES.map((bk, i) => bloqueCanvas(bk, i)).join('');
  if (SEL != null) { const el = doc.querySelector(`.gb-block[data-i="${SEL}"]`); if (el) el.classList.add('is-selected'); }
  pintarModo();   // el aviso de "agregá cortes" depende de los bloques que haya
}
function selectBlock(i) {
  SEL = i;
  $('#gbDoc').querySelectorAll('.gb-block').forEach(b => b.classList.toggle('is-selected', +b.dataset.i === i));
  renderInspector();
  // el panel derecho SIGUE a lo que tocás. Antes había que scrollear el sidebar
  // hasta el inspector, y eso empujaba la paleta fuera de pantalla.
  gbPane('ajustes');
}
// selector de color para un bloque (con opción "negro por defecto" si conDefault)
function colorPicker(bk, prop, conDefault) {
  const row = document.createElement('div'); row.className = 'bk-row';
  const opts = conDefault ? [{ v: '', hex: '#111111' }].concat(COLORS) : COLORS;
  opts.forEach(c => {
    const dot = document.createElement('button'); dot.type = 'button';
    dot.className = 'bk-cdot' + (((bk[prop] || '') === c.v) ? ' sel' : '');
    dot.style.background = c.hex; dot.title = c.v ? c.v.replace('--c-', '') : 'Negro (por defecto)';
    dot.onclick = () => { bk[prop] = c.v; renderCanvas(); renderInspector(); };
    row.appendChild(dot);
  });
  return row;
}

// ---- inspector contextual (ajustes no-textuales del bloque) ----
function renderInspector() {
  const box = $('#gbInspector'), T = $('#gbInspTitle'); box.innerHTML = '';
  reanimar(box, 'mov-cambio', 300);   // cambiar de bloque no debe ser un corte seco
  if (SEL == null || !BLOQUES[SEL]) {
    if (T) { T.textContent = 'Bloque seleccionado'; T.classList.remove('activo'); }
    // el vacío tiene que decir la VERDAD: no es lo mismo "todavía no elegiste"
    // que "no hay ni un bloque para elegir"
    box.innerHTML = BLOQUES.length
      ? '<div class="gb-empty-insp">Tocá un bloque del documento y acá aparecen <b>sus</b> ajustes.</div>'
      : '<div class="gb-empty-insp">Todavía no hay bloques.<br>Elegí uno en <b>+ Agregar bloque</b> ↑</div>';
    return;
  }
  const bk = BLOQUES[SEL];
  // el título de la sección ES el nombre del bloque: el dato que importa deja
  // de estar en gris de 11px, tercero en la jerarquía
  if (T) {
    T.textContent = 'Ajustes de: ' + (BLOQUE_INFO[bk.t === 'titulo' && bk.nivel === 'h2' ? 'subtitulo' : bk.t] || { label: bk.t }).label;
    T.classList.add('activo');
  }
  if (BLOQUE_AYUDA[bk.t]) box.appendChild(insNota(BLOQUE_AYUDA[bk.t], 'insp-ayuda'));

  if (bk.t === 'nota') {
    box.appendChild(lbl('Color de la barra y el ícono'));
    box.appendChild(colorPicker(bk, 'color', true));
    box.appendChild(lbl('Ícono'));
    box.appendChild(iconMini(bk, 'icono'));
  }
  else if (bk.t === 'titulo') {
    box.appendChild(lbl('Nivel'));
    const row = document.createElement('div'); row.className = 'bk-row';
    [['h1', 'Título'], ['h2', 'Subtítulo']].forEach(([lv, nm]) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = nm; b.className = 'ctipo' + ((bk.nivel || 'h1') === lv ? ' sel' : ''); b.onclick = () => { bk.nivel = lv; renderCanvas(); selectBlock(SEL); }; row.appendChild(b); });
    box.appendChild(row);
  }
  else if (bk.t === 'kicker') { box.appendChild(lbl('Número (opcional)')); const n = document.createElement('input'); n.type = 'text'; n.className = 'insp-input insp-num'; n.value = bk.n || ''; n.oninput = () => { bk.n = n.value; renderCanvas(); }; box.appendChild(n); }
  else if (bk.t === 'espacio') { box.appendChild(lbl('Tamaño')); const sel = document.createElement('select'); sel.innerHTML = '<option value="sm">Chico</option><option value="md">Medio</option><option value="lg">Grande</option>'; sel.value = bk.alto || 'md'; sel.className = 'insp-sel'; sel.onchange = () => { bk.alto = sel.value; renderCanvas(); selectBlock(SEL); }; box.appendChild(sel); }
  else if (bk.t === 'separador') { box.appendChild(lbl('Grosor de la línea')); const sel = document.createElement('select'); sel.innerHTML = '<option value="2">Fina (2px)</option><option value="4">Media (4px)</option><option value="6">Gruesa (6px)</option><option value="8">Extra gruesa (8px)</option>'; sel.value = String(bk.grosor || 4); sel.className = 'insp-sel'; sel.onchange = () => { bk.grosor = parseInt(sel.value, 10); renderCanvas(); selectBlock(SEL); }; box.appendChild(sel); }
  else if (bk.t === 'pasos') { box.appendChild(pasosInspector(bk)); }
  else if (bk.t === 'lista') { box.appendChild(listaInspector(bk)); }
  else if (bk.t === 'chat') { box.appendChild(chatInspector(bk)); }
  else if (bk.t === 'situacion') { box.appendChild(situacionInspector(bk)); }
  else if (bk.t === 'plantilla') { box.appendChild(plantillaInspector(bk)); }
  else if (bk.t === 'tabla') { box.appendChild(tablaInspector(bk)); }
  else if (bk.t === 'kpis') { box.appendChild(kpisInspector(bk)); }
  else if (bk.t === 'barras') { box.appendChild(barrasInspector(bk)); }
  else if (bk.t === 'podio') { box.appendChild(podioInspector(bk)); }
  else if (bk.t === 'tarjetas') { box.appendChild(tarjetasInspector(bk)); }
  else if (bk.t === 'diapo') { box.appendChild(diapoInspector(bk)); }
  else if (bk.t === 'imagen') { box.appendChild(imagenInspector(bk)); }
  else if (bk.t === 'video') { box.appendChild(videoInspector(bk)); }
  else if (bk.t === 'pdf') { box.appendChild(pdfInspector(bk)); }
  else if (bk.t === 'galeria') { box.appendChild(galeriaInspector(bk)); }
  else if (bk.t === 'embed') {
    box.appendChild(lbl('Link de la web / informe'));
    box.appendChild(urlInput(bk, 'url', 'https://lookerstudio.google.com/embed/…'));
    box.appendChild(lbl('Alto'));
    const sel = document.createElement('select'); sel.className = 'insp-sel';
    sel.innerHTML = '<option value="sm">Bajo</option><option value="md">Medio</option><option value="lg">Alto</option>';
    sel.value = bk.alto || 'md'; sel.onchange = () => { bk.alto = sel.value; renderCanvas(); selectBlock(SEL); };
    box.appendChild(sel);
  }
  else if (bk.t === 'boton') {
    box.appendChild(lbl('Dirección (URL)'));
    box.appendChild(urlInput(bk, 'url', 'https://…'));
    const p = document.createElement('p'); p.className = 'fld-note'; p.style.margin = '6px 0 0';   // aire puntual bajo el input de URL; no amerita clase p.textContent = 'El texto del botón se edita en el documento.'; box.appendChild(p);
  }
  else if (bk.t === 'html') { const p = document.createElement('p'); p.className = 'fld-note'; p.textContent = 'Bloque de diseño del sistema. Podés moverlo o borrarlo, pero su contenido no se edita por bloques.'; box.appendChild(p); }
  else {
    const p = document.createElement('p'); p.className = 'fld-note';
    p.innerHTML = (bk.t === 'lista' || bk.t === 'chat')
      ? 'Escribí los ítems en el documento (Enter agrega otro). <b>Seleccioná texto</b> y aparece la barra de <b>negrita / itálica / link</b>.'
      : 'Escribí directo en el documento. <b>Seleccioná el texto</b> que quieras y aparece arriba la barra para <b>negrita, itálica o link</b>.';
    box.appendChild(p);
  }

  // 2B: aca vivian ↑ Subir / ↓ Bajar / ✕ Borrar repetidos de la botonera del
  // bloque. Mover y borrar tienen UNA casa (los handles); el panel derecho
  // queda para la ayuda y los ajustes reales (§3.5.3 + §3.5.5 de la auditoria).
}
function pasosInspector(bk) {
  const cont = document.createElement('div'); cont.className = 'insp-col';
  bk.steps.forEach((s, i) => {
    const row = document.createElement('div'); row.className = 'insp-caja';
    const cdrow = document.createElement('div'); cdrow.className = 'bk-row';
    COLORS.forEach(c => { const dot = document.createElement('button'); dot.type = 'button'; dot.className = 'bk-cdot' + (s.color === c.v ? ' sel' : ''); dot.style.background = c.hex; dot.onclick = () => { s.color = c.v; renderCanvas(); renderInspector(); }; cdrow.appendChild(dot); });
    const del = document.createElement('button'); del.type = 'button'; del.textContent = 'Quitar paso'; del.className = 'insp-quitar-txt';
    del.onclick = () => { bk.steps.splice(i, 1); if (!bk.steps.length) bk.steps.push({ titulo: '', desc: '', icono: 'users', color: '--c-caba' }); renderCanvas(); renderInspector(); };
    row.append(lbl('Paso ' + (i + 1)), iconMini(s, 'icono'), cdrow);
    if (i > 0) { row.appendChild(lbl('↳ Flecha desde el paso anterior')); row.appendChild(conectorPicker(s)); }
    row.appendChild(del); cont.appendChild(row);
  });
  const add = document.createElement('button'); add.type = 'button'; add.textContent = '+ Agregar paso'; add.className = 'insp-add';
  add.onclick = () => { bk.steps.push({ titulo: '', desc: '', icono: 'check', color: '--c-canning', conector: 'arrowR' }); renderCanvas(); renderInspector(); };
  cont.appendChild(add);
  return cont;
}
function urlInput(obj, prop, ph) {
  const i = document.createElement('input'); i.type = 'text'; i.className = 'insp-input';
  i.placeholder = ph || 'https://…'; i.value = obj[prop] || '';
  i.oninput = () => { obj[prop] = i.value.trim(); renderCanvas(); $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"]`)?.classList.add('is-selected'); };
  return i;
}
function imagenInspector(bk) {
  const wrap = document.createElement('div'); wrap.className = 'insp-col';
  const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'btn btn-ghost'; btn.textContent = bk.src ? 'Cambiar imagen' : 'Subir imagen';
  const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.hidden = true;
  btn.onclick = () => inp.click();
  inp.onchange = () => { if (inp.files[0]) subirImagenBloque(bk, inp.files[0]); inp.value = ''; };
  wrap.append(btn, inp);
  if (bk.src) { const prev = document.createElement('img'); prev.src = '/intranet/' + bk.src + '?t=' + Date.now(); prev.className = 'insp-img-prev'; wrap.appendChild(prev); }
  // tamaño con el que se muestra en la intranet (el vendedor toca para verla grande)
  wrap.appendChild(lbl('Tamaño en la intranet'));
  const selTam = document.createElement('select'); selTam.className = 'insp-sel';
  selTam.innerHTML = '<option value="ch">Chico</option><option value="md">Mediano</option><option value="gr">Grande</option><option value="full">Completo (original)</option>';
  selTam.value = bk.tam || 'md';
  selTam.onchange = () => { bk.tam = selTam.value; renderCanvas(); selectBlock(SEL); };
  wrap.appendChild(selTam);
  const notaTam = document.createElement('p'); notaTam.className = 'fld-note'; notaTam.style.margin = '2px 0 0';   // pegada al select de tamano; no amerita clase
  notaTam.textContent = 'El vendedor toca la imagen para verla en grande.';
  wrap.appendChild(notaTam);
  // opción de descarga directa (la placa se baja al tocar el botón)
  wrap.appendChild(insCheck(bk, 'descargable', 'Permitir descargar (botón “Descargar”)'));
  if (bk.descargable) {
    wrap.appendChild(lbl('Nombre del archivo (opcional)'));
    const n = document.createElement('input'); n.className = 'insp-input'; n.placeholder = 'Ej: Promo bancaria junio'; n.value = bk.dlNombre || '';
    n.oninput = () => { bk.dlNombre = n.value; };
    wrap.appendChild(n);
  }
  return wrap;
}
// sección de descargas: lista compacta de placas (miniatura + nombre) con buscador y subida múltiple
function galeriaInspector(bk) {
  const wrap = document.createElement('div'); wrap.className = 'insp-col';
  wrap.appendChild(lbl('Título de la sección'));
  wrap.appendChild(inputProp(bk, 'titulo', 'Ej: Promos bancarias'));
  const total = (bk.items || []).length;
  wrap.appendChild(lbl('Placas (' + total + ')'));
  const lista = document.createElement('div'); lista.className = 'insp-lista';
  // buscador (cuando hay varias)
  if (total > 6) {
    const buscar = document.createElement('input'); buscar.className = 'insp-input'; buscar.placeholder = '🔎 Buscar placa por nombre…';
    buscar.oninput = () => { const q = buscar.value.trim().toLowerCase(); lista.querySelectorAll('.gal-row').forEach(r => { r.style.display = (!q || (r.dataset.nombre || '').includes(q)) ? '' : 'none'; }); };
    wrap.appendChild(buscar);
  }
  (bk.items || []).forEach((it, i) => {
    const row = document.createElement('div'); row.className = 'gal-row'; row.dataset.nombre = (it.nombre || '').toLowerCase();
    const thumb = document.createElement('button'); thumb.type = 'button'; thumb.className = 'gal-thumb'; thumb.title = it.src ? 'Cambiar imagen' : 'Subir imagen';
    if (it.src) thumb.style.backgroundImage = `url(/intranet/${it.src}?t=${Date.now()})`; else thumb.textContent = '+';
    const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.hidden = true;
    thumb.onclick = () => inp.click();
    inp.onchange = () => { if (inp.files[0]) subirImgGaleria(bk, i, inp.files[0]); inp.value = ''; };
    const nm = document.createElement('input'); nm.className = 'insp-input insp-flex'; nm.placeholder = 'Nombre'; nm.value = it.nombre || '';
    nm.oninput = () => { it.nombre = nm.value; row.dataset.nombre = nm.value.toLowerCase(); renderCanvas(); $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"]`)?.classList.add('is-selected'); };
    const del = document.createElement('button'); del.type = 'button'; del.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>'; del.title = 'Quitar'; del.className = 'gal-del';
    del.onclick = () => { bk.items.splice(i, 1); if (!bk.items.length) bk.items.push({ src: '', nombre: '' }); renderCanvas(); renderInspector(); };
    row.append(thumb, inp, nm, del); lista.appendChild(row);
  });
  wrap.appendChild(lista);
  // subir varias de una
  const addMulti = document.createElement('button'); addMulti.type = 'button'; addMulti.textContent = '+ Subir imágenes (varias)';
  addMulti.className = 'insp-add';
  const multiInp = document.createElement('input'); multiInp.type = 'file'; multiInp.accept = 'image/*'; multiInp.multiple = true; multiInp.hidden = true;
  addMulti.onclick = () => multiInp.click();
  multiInp.onchange = () => { const fs = [...multiInp.files]; multiInp.value = ''; if (fs.length) subirImgsGaleria(bk, fs); };
  wrap.append(addMulti, multiInp);
  return wrap;
}
async function subirImgGaleria(bk, i, file) {
  const fd = new FormData();
  fd.append('key', (det.key || $('#dTitle').value || 'modulo') + '-gal-' + Date.now());
  fd.append('file', file);
  toast('Subiendo placa…');
  try { const r = await api('/api/upload-contenido', { method: 'POST', body: fd }); bk.items[i].src = r.src; if (!bk.items[i].nombre) bk.items[i].nombre = file.name.replace(/\.[^.]+$/, ''); renderCanvas(); renderInspector(); toast('Placa lista', 'ok'); }
  catch (e) { toast(e.message, 'err'); }
}
// subida múltiple: agrega todas y renderiza una sola vez
async function subirImgsGaleria(bk, files) {
  toast('Subiendo ' + files.length + ' imágenes…');
  let ok = 0;
  for (let k = 0; k < files.length; k++) {
    const f = files[k];
    const fd = new FormData();
    fd.append('key', (det.key || $('#dTitle').value || 'modulo') + '-gal-' + Date.now() + '-' + k);
    fd.append('file', f);
    try { const r = await api('/api/upload-contenido', { method: 'POST', body: fd }); bk.items.push({ src: r.src, nombre: f.name.replace(/\.[^.]+$/, '') }); ok++; }
    catch (e) {}
  }
  // sacar las tarjetas vacías que pudieran haber quedado
  bk.items = bk.items.filter(it => it.src) ; if (!bk.items.length) bk.items.push({ src: '', nombre: '' });
  renderCanvas(); renderInspector();
  toast(ok + ' imágenes agregadas', 'ok');
}
async function subirImagenBloque(bk, file) {
  const fd = new FormData();
  fd.append('key', (det.key || $('#dTitle').value || 'modulo') + '-img-' + Date.now());
  fd.append('file', file);
  toast('Subiendo imagen…');
  try { const r = await api('/api/upload-contenido', { method: 'POST', body: fd }); bk.src = r.src; renderCanvas(); renderInspector(); toast('Imagen lista', 'ok'); }
  catch (e) { toast(e.message, 'err'); }
}
// PDF: subir documento + elegir cómo se muestra (tarjeta que abre / visor embebido)
function pdfInspector(bk) {
  const wrap = document.createElement('div'); wrap.className = 'insp-col';
  const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'btn btn-ghost'; btn.textContent = bk.src ? 'Cambiar PDF' : 'Subir PDF';
  const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'application/pdf,.pdf'; inp.hidden = true;
  btn.onclick = () => inp.click();
  inp.onchange = () => { if (inp.files[0]) subirPdfBloque(bk, inp.files[0]); inp.value = ''; };
  wrap.append(btn, inp);
  if (bk.src) { const p = document.createElement('div'); p.className = 'fld-note insp-nota-ok'; p.textContent = '✓ ' + bk.src.split('/').pop(); wrap.appendChild(p); }
  wrap.appendChild(lbl('Cómo se muestra'));
  const sel = document.createElement('select'); sel.className = 'insp-sel';
  sel.innerHTML = '<option value="tarjeta">Tarjeta (se abre al tocar)</option><option value="embebido">Visor embebido (se lee en la página)</option>';
  sel.value = bk.modo || 'tarjeta'; sel.onchange = () => { bk.modo = sel.value; renderCanvas(); selectBlock(SEL); };
  wrap.appendChild(sel);
  wrap.appendChild(lbl('Nombre visible'));
  wrap.appendChild(inputProp(bk, 'nombre', 'Ej: Catálogo 2026'));
  if ((bk.modo || 'tarjeta') === 'embebido') {
    wrap.appendChild(lbl('Alto del visor'));
    const alt = document.createElement('select'); alt.className = 'insp-sel';
    alt.innerHTML = '<option value="sm">Bajo</option><option value="md">Medio</option><option value="lg">Alto</option>';
    alt.value = bk.alto || 'md'; alt.onchange = () => { bk.alto = alt.value; renderCanvas(); selectBlock(SEL); };
    wrap.appendChild(alt);
  }
  // ⚠️ este bloque venía con "verdadero por omisión" (`descargable !== false`).
  // El checkbox unificado lee `!!bk.descargable`, así que si no dejamos el valor
  // explícito PRIMERO, todos los PDF ya publicados perderían su botón de
  // descarga en silencio la próxima vez que alguien abra el módulo y guarde.
  if (bk.descargable === undefined) bk.descargable = true;
  wrap.appendChild(insCheck(bk, 'descargable', 'Mostrar botón “Descargar”'));
  return wrap;
}
async function subirPdfBloque(bk, file) {
  const fd = new FormData();
  fd.append('key', (det.key || $('#dTitle').value || 'modulo') + '-pdf-' + Date.now());
  fd.append('file', file);
  toast('Subiendo PDF…');
  try {
    const r = await api('/api/upload-pdf', { method: 'POST', body: fd });
    bk.src = r.src;
    if (!bk.nombre) bk.nombre = file.name.replace(/\.[^.]+$/, '');
    renderCanvas(); renderInspector(); toast('PDF listo', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}
/* ---- VIDEO ------------------------------------------------------------
   Dos fuentes posibles: un archivo propio (se sube y se publica con el sitio)
   o un link externo (YouTube / Vimeo / Drive, que se embebe).
   El archivo propio se COMPRIME al subir si no entra en el tope de publicación,
   avisando siempre antes. */

// proporción real del video, para que la caja no le deje franjas negras
function arDe(bk) {
  const m = String(bk.ar || '').match(/^(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/);
  if (m) return [m[1], m[2]];
  return (bk.orient === 'vert') ? [9, 16] : [16, 9];
}

// convierte un link normal en su versión embebible
function embedDeVideo(url) {
  const u = (url || '').trim();
  let m;
  if ((m = u.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{6,})/)))
    return { url: 'https://www.youtube.com/embed/' + m[1], vert: /shorts\//.test(u), ok: true };
  if ((m = u.match(/vimeo\.com\/(?:video\/)?(\d+)/)))
    return { url: 'https://player.vimeo.com/video/' + m[1], vert: false, ok: true };
  if ((m = u.match(/drive\.google\.com\/file\/d\/([\w-]+)/)))
    return { url: 'https://drive.google.com/file/d/' + m[1] + '/preview', vert: false, ok: true };
  return { url: u, vert: false, ok: /^https?:\/\//i.test(u) };
}

// lee ancho/alto/duración del archivo sin subirlo (para saber si es vertical)
function medirVideo(file) {
  return new Promise(res => {
    const v = document.createElement('video');
    const urlObj = URL.createObjectURL(file);
    const listo = r => { URL.revokeObjectURL(urlObj); res(r); };
    v.preload = 'metadata';
    v.onloadedmetadata = () => listo({ w: v.videoWidth, h: v.videoHeight, dur: v.duration || 0 });
    v.onerror = () => listo(null);
    v.src = urlObj;
  });
}

const mbDe = b => (b / 1048576).toFixed(1).replace('.', ',') + ' MB';

// espera un trabajo largo del server (descarga del compresor / compresión)
async function esperarJob(id, onPaso) {
  for (;;) {
    const j = await api('/api/job?id=' + encodeURIComponent(id));
    if (onPaso) onPaso(j);
    if (j.estado === 'listo') return j;
    if (j.estado === 'error') throw new Error(j.error || 'No se pudo completar');
    await new Promise(r => setTimeout(r, 600));
  }
}

function videoInspector(bk) {
  const wrap = document.createElement('div'); wrap.className = 'insp-col';

  const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'btn btn-ghost';
  btn.textContent = bk.src ? 'Cambiar video' : 'Subir video';
  const inp = document.createElement('input'); inp.type = 'file';
  inp.accept = 'video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm'; inp.hidden = true;
  btn.onclick = () => inp.click();
  const estado = document.createElement('div'); estado.className = 'fld-note insp-rompe';
  const pintarEstado = () => {
    if (bk.src) { estado.style.color = 'var(--ok)'; estado.textContent = '✓ ' + bk.src.split('/').pop(); }
    else { estado.textContent = ''; }
  };
  pintarEstado();
  inp.onchange = () => { if (inp.files[0]) subirVideoBloque(bk, inp.files[0], estado, btn); inp.value = ''; };
  wrap.append(btn, inp, estado);

  wrap.appendChild(lbl('…o pegá un link (YouTube, Vimeo, Drive)'));
  const link = document.createElement('input'); link.type = 'text';
  link.className = 'insp-input';   // 2D: decia 'insp-inp' (clase inexistente) y lo parchaba un cssText
  link.placeholder = 'https://youtube.com/watch?v=…';
  link.value = bk.url || '';
  link.oninput = () => {
    bk.url = link.value.trim();
    if (bk.url) { bk.src = ''; pintarEstado(); btn.textContent = 'Subir video'; }
    const e = embedDeVideo(bk.url);
    if (bk.url && e.vert) { bk.orient = 'vert'; bk.ar = '9/16'; }
    renderCanvas();
  };
  wrap.appendChild(link);
  if (bk.url && !embedDeVideo(bk.url).ok) {
    const av = document.createElement('div'); av.className = 'fld-note';
    av.style.color = 'var(--err)'; av.textContent = 'Ese link no parece válido.';
    wrap.appendChild(av);
  }

  wrap.appendChild(lbl('Cómo está filmado'));
  const orow = document.createElement('div'); orow.className = 'bk-row';
  [['horiz', 'Horizontal'], ['vert', 'Vertical (celular)']].forEach(([v, nm]) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = nm;
    b.className = 'ctipo' + ((bk.orient || 'horiz') === v ? ' sel' : '');
    b.onclick = () => { bk.orient = v; bk.ar = (v === 'vert' ? '9/16' : '16/9'); renderCanvas(); selectBlock(SEL); };
    orow.appendChild(b);
  });
  wrap.appendChild(orow);

  wrap.appendChild(lbl('Tamaño en la intranet'));
  const tam = document.createElement('select'); tam.className = 'insp-sel';
  tam.innerHTML = '<option value="ch">Chico</option><option value="md">Medio</option>' +
    '<option value="gr">Grande</option><option value="full">Lo más grande posible</option>';
  tam.value = bk.tam || 'md';
  tam.onchange = () => { bk.tam = tam.value; renderCanvas(); selectBlock(SEL); };
  wrap.appendChild(tam);

  if (bk.src) {
    wrap.appendChild(insCheck(bk, 'descargable', 'Permitir descargar el video'));
    if (bk.descargable) {
      wrap.appendChild(lbl('Nombre del archivo al descargar'));
      wrap.appendChild(inputProp(bk, 'dlNombre', 'Ej: Cómo mostrar un sillón'));
    }
  }
  return wrap;
}

async function subirVideoBloque(bk, file, estado, btn) {
  const poner = (txt, color) => { estado.textContent = txt; estado.style.color = color || ''; };
  try {
    const cap = await api('/api/video-capacidad');
    if (file.size > cap.max_subida) {
      poner('Ese video pesa ' + mbDe(file.size) + ' y el máximo que puedo recibir es ' +
        mbDe(cap.max_subida) + '. Recortalo antes.', 'var(--err)');
      return;
    }
    const meta = await medirVideo(file);

    // AVISAR antes de comprimir (y antes de bajar el compresor, si falta)
    if (file.size > cap.max) {
      let msg = 'Este video pesa ' + mbDe(file.size) + ' y el máximo que se puede publicar es ' +
        mbDe(cap.max) + '. Lo voy a achicar automáticamente (queda en 720p, se sigue viendo bien).';
      if (!cap.compresor) {
        msg += '\n\nEs la primera vez que subís un video en esta computadora, así que antes ' +
          'tengo que descargar el compresor: son ' + cap.mb_descarga + ' MB, una sola vez.';
      }
      if (!await confirmar(msg, 'Sí, achicalo', 'Achicar el video')) { poner(''); return; }

      if (!cap.compresor) {
        poner('Descargando el compresor…');
        btn.disabled = true;
        const r = await api('/api/preparar-compresor', { method: 'POST' });
        if (r.job) await esperarJob(r.job, j => poner('Descargando el compresor… ' + (j.pct || 0) + '%'));
      }
    }

    poner('Subiendo el video…');
    btn.disabled = true;
    const fd = new FormData();
    fd.append('key', (det.key || $('#dTitle').value || 'modulo') + '-video-' + Date.now());
    fd.append('file', file);
    const r = await api('/api/upload-video', { method: 'POST', body: fd });

    if (r.falta_ffmpeg) { poner('Falta el compresor para poder achicar este video.', 'var(--err)'); return; }

    let src = r.src;
    if (r.job) {
      const j = await esperarJob(r.job, x => poner('Achicando el video… ' + (x.pct || 0) + '%'));
      src = j.src;
      toast('Video listo (' + (j.info || '') + ')', 'ok');
    } else {
      toast('Video listo', 'ok');
    }

    bk.src = src;
    bk.url = '';
    if (meta && meta.w && meta.h) {
      bk.orient = (meta.h > meta.w) ? 'vert' : 'horiz';
      bk.ar = meta.w + '/' + meta.h;
    }
    if (!bk.dlNombre) bk.dlNombre = file.name.replace(/\.[^.]+$/, '');
    renderCanvas(); renderInspector();
  } catch (e) {
    poner(e.message || 'No se pudo subir el video', 'var(--err)');
    toast(e.message || 'No se pudo subir el video', 'err');
  } finally {
    if (btn) btn.disabled = false;
  }
}

// lista de tarjetas: ícono POR tarjeta + agregar/quitar
function listaInspector(bk) {
  const cont = document.createElement('div'); cont.className = 'insp-col';
  cont.appendChild(lbl('Tarjetas (ícono + texto)'));
  (bk.items || []).forEach((it, i) => {
    const o = (typeof it === 'string') ? { icono: 'check', html: it } : it;
    if (typeof it === 'string') bk.items[i] = o;
    const card = document.createElement('div'); card.className = 'insp-caja';
    const head = document.createElement('div'); head.className = 'bk-row';
    const t = document.createElement('span'); t.className = 'insp-item-t'; t.textContent = txtOf(o.html) || 'Tarjeta ' + (i + 1);
    const del = insDel(() => { bk.items.splice(i, 1); if (!bk.items.length) bk.items.push({ icono: 'check', html: '' }); renderCanvas(); renderInspector(); });   // 2D: cruz roja fija pre-B7 -> la cruz comun
    head.append(t, del);
    card.append(head, lbl('Ícono'), iconMini(o, 'icono'), lbl('Color del ícono'), colorPicker(o, 'color'));
    cont.appendChild(card);
  });
  const add = document.createElement('button'); add.type = 'button'; add.textContent = '+ Agregar tarjeta'; add.className = 'insp-add';
  add.onclick = () => { bk.items.push({ icono: 'check', color: '--c-success', html: '' }); renderCanvas(); selectBlock(SEL); const el = $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"] [data-prop="items"][data-idx="${bk.items.length - 1}"]`); if (el) el.focus(); };
  cont.appendChild(add);
  return cont;
}
/* ===================================================================
   INSPECTORES de los bloques de datos
   =================================================================== */
function insCol() { const d = document.createElement('div'); d.className = 'insp-col'; return d; }
/* UN solo vocabulario para agregar y quitar en todo el panel:
   recuadro = un ítem · la cruz gris arriba a la derecha, roja recién al pasar
   por encima · el botón punteado de ancho completo siempre agrega uno más.
   Antes había cinco formas distintas de borrar, y las cruces eran rojas fijas:
   un inspector de 8 filas parecían 8 alertas sin que hubiera pasado nada. */
function insCaja() { const d = document.createElement('div'); d.className = 'insp-caja'; return d; }
function insAdd(txt, fn) {
  const b = document.createElement('button'); b.type = 'button';
  b.className = 'insp-add'; b.textContent = txt; b.onclick = fn; return b;
}
function insDel(fn) {
  const b = document.createElement('button'); b.type = 'button';
  b.className = 'insp-del'; b.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>'; b.title = 'Quitar'; b.onclick = fn; return b;
}
function insHead(titulo, onDel) {
  const h = document.createElement('div'); h.className = 'bk-row';
  const t = document.createElement('span');
  t.className = 'insp-cab-t';
  t.textContent = titulo; h.append(t);
  if (onDel) h.append(insDel(onDel));
  return h;
}
function insSelect(obj, prop, opts) {
  const s = document.createElement('select'); s.className = 'insp-sel';
  s.innerHTML = opts.map(([v, n]) => `<option value="${esc(v)}">${esc(n)}</option>`).join('');
  s.value = String(obj[prop] == null ? '' : obj[prop]);
  s.onchange = () => { obj[prop] = s.value; renderCanvas(); renderInspector(); };
  return s;
}
/* UN solo checkbox para todo el panel. Antes convivían dos familias y ninguna
   se veía prendida: opciones que cambian de verdad la intranet ("Permitir
   descargar", "Mostrar buscador") se veían igual tildadas que sin tildar si no
   mirabas el cuadradito de 13px. Ahora el prendido se nota en toda la fila. */
function insCheck(obj, prop, texto) {
  const l = document.createElement('label'); l.className = 'insp-check';
  const c = document.createElement('input'); c.type = 'checkbox'; c.checked = !!obj[prop];
  l.classList.toggle('on', c.checked);
  c.onchange = () => {
    obj[prop] = c.checked;
    l.classList.toggle('on', c.checked);
    renderCanvas(); renderInspector();
  };
  l.append(c, document.createTextNode(texto));
  return l;
}
function insNota(html, cls) {
  const p = document.createElement('p');
  p.className = 'fld-note insp-nota' + (cls ? ' ' + cls : '');
  p.innerHTML = html; return p;
}

/* "¿Dónde escribo el texto?" era la pregunta más repetida y tenía cuatro
   respuestas en cuatro lugares distintos (a veces arriba, a veces al final, a
   veces en ningún lado). Ahora sale siempre en el mismo lugar y con la misma
   forma: apenas abrís los ajustes del bloque. */
const BLOQUE_AYUDA = {
  tabla: 'Las celdas se escriben <b>en la tabla</b>. Enter dentro de una celda agrega otra fila.',
  kpis: 'El período, el número y la nota se escriben <b>en las tarjetas</b>. Acá elegís la variación y cuál va destacada.',
  barras: 'El nombre y el número se escriben <b>en la barra</b>. El largo se calcula solo: la más grande ocupa el 100%.',
  podio: 'Puesto, nombre, sucursal y números se escriben <b>en las tarjetas</b>.',
  tarjetas: 'El título y el texto se escriben <b>en la tarjeta</b>. Acá van el ícono, el color y cuántas entran por fila.',
  lista: 'El texto de cada ítem se escribe <b>en el documento</b> (Enter agrega otro).',
  chat: 'Los mensajes se escriben <b>en las burbujas</b>. Acá cambiás de lado o agregás.',
  pasos: 'Título y descripción se escriben <b>en el paso</b>. Acá van el ícono, el color y la flecha.',
  situacion: 'El título y los mensajes se escriben <b>en la tarjeta</b>.',
  galeria: 'Subí las placas acá; el nombre lo podés editar acá o abajo de cada placa.',
};
// agrega un ítem al final de un bloque y deja el cursor en su primer campo editable
function insAgregar(bk, item, sub) {
  bk.items.push(item); renderCanvas(); selectBlock(SEL);
  const el = $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"] [data-prop="items"][data-idx="${bk.items.length - 1}"][data-sub="${sub}"]`);
  if (el) el.focus();
}

function tablaInspector(bk) {
  const cont = insCol();
  cont.appendChild(lbl('Qué puede hacer el vendedor'));
  const caja0 = insCaja();
  caja0.append(
    insCheck(bk, 'orden', 'Ordenar tocando el título de la columna'),
    insCheck(bk, 'buscar', 'Mostrar buscador arriba de la tabla'));
  const nota = document.createElement('div'); nota.className = 'fld-note';
  nota.textContent = 'Si una columna tiene números, marcale "Son números" acá abajo: así se ordena por valor y no por texto (100 antes que 99).';
  caja0.appendChild(nota);
  cont.appendChild(caja0);
  cont.appendChild(lbl('Columnas'));
  (bk.cols || []).forEach((c, i) => {
    const caja = insCaja();
    const fila = document.createElement('div'); fila.className = 'bk-row';
    const inp = document.createElement('input');
    inp.type = 'text'; inp.className = 'insp-input'; inp.placeholder = 'Nombre de la columna'; inp.value = c.h || '';
    inp.classList.add('insp-flex');   // deja lugar al ✕ al costado
    inp.oninput = () => { c.h = inp.value; renderCanvas(); };
    fila.append(inp);
    if (bk.cols.length > 1) fila.append(insDel(() => {
      bk.cols.splice(i, 1);
      (bk.filas || []).forEach(f => { if (Array.isArray(f.celdas)) f.celdas.splice(i, 1); });
      renderCanvas(); renderInspector();
    }));
    caja.append(fila, insCheck(c, 'num', 'Son números (alinea a la derecha)'));
    cont.appendChild(caja);
  });
  cont.appendChild(insAdd('+ Agregar columna', () => {
    bk.cols.push({ h: '', num: false });
    (bk.filas || []).forEach(f => { if (!Array.isArray(f.celdas)) f.celdas = []; f.celdas.push(''); });
    renderCanvas(); renderInspector();
  }));

  cont.appendChild(lbl('Filas'));
  (bk.filas || []).forEach((f, i) => {
    const caja = insCaja();
    const nombre = txtOf((f.celdas || [])[0]) || 'Fila ' + (i + 1);
    caja.append(insHead(nombre, bk.filas.length > 1 ? () => { bk.filas.splice(i, 1); renderCanvas(); renderInspector(); } : null));
    caja.append(insSelect(f, 'destaque', [['', 'Normal'], ['ok', 'Resaltada en verde'], ['mal', 'Resaltada en rojo'], ['total', 'Fila de total (oscura)']]));
    cont.appendChild(caja);
  });
  cont.appendChild(insAdd('+ Agregar fila', () => {
    bk.filas.push({ celdas: (bk.cols || []).map(() => ''), destaque: '' });
    renderCanvas(); renderInspector();
  }));
  return cont;
}

function kpisInspector(bk) {
  const cont = insCol();
  (bk.items || []).forEach((k, i) => {
    const caja = insCaja();
    caja.append(insHead(txtOf(k.label) || 'Tarjeta ' + (i + 1), bk.items.length > 1 ? () => { bk.items.splice(i, 1); renderCanvas(); renderInspector(); } : null));
    caja.append(lbl('Variación'), insSelect(k, 'tend', [['', 'Sin variación'], ['up', '▲ Subió'], ['down', '▼ Bajó'], ['flat', '▬ Estable']]));
    caja.append(insCheck(k, 'lead', 'Destacada (fondo oscuro)'));
    cont.appendChild(caja);
  });
  cont.appendChild(insAdd('+ Agregar tarjeta', () => insAgregar(bk, ITEM_NUEVO.kpis({}), 'label')));
  return cont;
}

function barrasInspector(bk) {
  const cont = insCol();
  (bk.items || []).forEach((b, i) => {
    const caja = insCaja();
    caja.append(insHead(txtOf(b.label) || 'Barra ' + (i + 1), bk.items.length > 1 ? () => { bk.items.splice(i, 1); renderCanvas(); renderInspector(); } : null));
    caja.append(lbl('Color de la barra'), colorPicker(b, 'color'));
    caja.append(lbl('Color de la etiqueta'), insSelect(b, 'tono', TONOS));
    cont.appendChild(caja);
  });
  cont.appendChild(insAdd('+ Agregar barra', () => insAgregar(bk, ITEM_NUEVO.barras({}), 'label')));
  return cont;
}

function podioInspector(bk) {
  const cont = insCol();
  (bk.items || []).forEach((p, i) => {
    const caja = insCaja();
    caja.append(insHead(txtOf(p.nombre) || 'Puesto ' + (i + 1), bk.items.length > 1 ? () => { bk.items.splice(i, 1); renderCanvas(); renderInspector(); } : null));
    caja.append(insCheck(p, 'lead', 'Destacado (borde verde)'));
    cont.appendChild(caja);
  });
  cont.appendChild(insAdd('+ Agregar puesto', () => insAgregar(bk, ITEM_NUEVO.podio({}), 'nombre')));
  return cont;
}

function tarjetasInspector(bk) {
  const cont = insCol();
  cont.append(lbl('Tarjetas por fila'), insSelect(bk, 'cols', [['2', '2'], ['3', '3'], ['4', '4']]));
  cont.append(lbl('Forma'), insSelect(bk, 'orient', [['v', 'Ícono arriba (alto)'], ['h', 'Ícono al costado (bajo)']]));
  (bk.items || []).forEach((c, i) => {
    const caja = insCaja();
    caja.append(insHead(txtOf(c.titulo) || 'Tarjeta ' + (i + 1), bk.items.length > 1 ? () => { bk.items.splice(i, 1); renderCanvas(); renderInspector(); } : null));
    caja.append(lbl('Ícono'), iconMini(c, 'icono'), lbl('Color'), colorPicker(c, 'color'));
    cont.appendChild(caja);
  });
  cont.appendChild(insAdd('+ Agregar tarjeta', () => insAgregar(bk, ITEM_NUEVO.tarjetas({}), 'titulo')));
  return cont;
}

function diapoInspector(bk) {
  const cont = insCol();
  cont.append(lbl('Sección del menú (opcional)'), inputProp(bk, 'grupo', 'Ej: Derivaciones'));
  if (!PRESENTACION) {
    // antes esto se guardaba igual y no hacía nada: ni aviso ni forma de arreglarlo
    cont.appendChild(insNota('⚠️ Este documento se ve como <b>página</b>, así que el corte <b>no hace nada</b>. Pasalo a presentación para que corte de verdad.'));
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'btn btn-ghost';
    b.textContent = 'Convertir en presentación';
    b.onclick = () => {
      PRESENTACION = true;
      if (COLECCION && DOC_IDX != null) COLECCION[DOC_IDX].presentacion = true;
      pintarModo(); renderGbAdd(); renderCanvas(); selectBlock(SEL);
      toast('Ahora se ve como presentación: ' + contarSlides(BLOQUES) + ' diapositivas.', 'ok');
    };
    cont.appendChild(b);
    return cont;
  }
  cont.appendChild(insNota('Todo lo que va <b>debajo</b> de este bloque arranca una diapositiva nueva. Las diapositivas con la misma sección se agrupan en el menú.'));
  return cont;
}

// selector del ícono que conecta los pasos del diagrama
const CONECTORES = ['arrowR', 'arrowL', 'arrowLR', 'arrowDR', 'check', 'reply', 'refresh'];
function conectorPicker(obj, prop) {
  prop = prop || 'conector';
  const wrap = document.createElement('div'); wrap.className = 'bk-iconmini';
  CONECTORES.forEach(k => {
    const b = document.createElement('button'); b.type = 'button';
    b.innerHTML = `<svg viewBox="0 0 24 24">${ICONS[k] || ''}</svg>`;
    if ((obj[prop] || 'arrowR') === k) b.classList.add('sel');
    b.onclick = () => { obj[prop] = k; renderCanvas(); renderInspector(); };
    wrap.appendChild(b);
  });
  return wrap;
}
function inputProp(obj, prop, ph) {
  const i = document.createElement('input'); i.type = 'text'; i.className = 'insp-input'; i.placeholder = ph || ''; i.value = obj[prop] || '';
  i.oninput = () => { obj[prop] = i.value; renderCanvas(); $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"]`)?.classList.add('is-selected'); };
  return i;
}
function situacionInspector(bk) {
  const cont = document.createElement('div'); cont.className = 'insp-col';
  cont.appendChild(lbl('Texto de la etiqueta'));
  cont.appendChild(inputProp(bk, 'tag', 'Situación'));
  cont.appendChild(lbl('Color de la etiqueta'));
  cont.appendChild(colorPicker(bk, 'tagColor'));
  // ⚠️ mismo caso que el PDF: venía con "verdadero por omisión" (`conResp !== false`)
  if (bk.conResp === undefined) bk.conResp = true;
  cont.appendChild(insCheck(bk, 'conResp', 'Mostrar “Respuesta recomendada”'));
  if (bk.conResp) {
    cont.appendChild(lbl('Texto de la respuesta'));
    cont.appendChild(inputProp(bk, 'resp', 'Respuesta recomendada'));
    cont.appendChild(lbl('Ícono'));
    cont.appendChild(conectorPicker(bk, 'respIcono'));
    cont.appendChild(lbl('Color'));
    cont.appendChild(colorPicker(bk, 'respColor'));
  }
  cont.appendChild(lbl('Burbujas (cliente blanca / vendedor verde)'));
  cont.appendChild(chatInspector(bk, 'mensajes'));
  return cont;
}
// chat / situación: agregar/quitar burbujas y cambiar de lado (cliente/vendedor)
function chatInspector(bk, prop) {
  prop = prop || 'items';
  const cont = document.createElement('div'); cont.className = 'insp-col';
  (bk[prop] || []).forEach((m, i) => {
    const it = (typeof m === 'string') ? { lado: 'out', html: m } : m;
    if (typeof m === 'string') bk[prop][i] = it;
    const row = document.createElement('div'); row.className = 'bk-row';
    const tog = document.createElement('button'); tog.type = 'button'; tog.className = 'btn btn-ghost btn-lado';
    tog.textContent = it.lado === 'in' ? '⬅ Cliente (blanca)' : '➡ Vendedor (verde)';
    tog.onclick = () => { it.lado = it.lado === 'in' ? 'out' : 'in'; renderCanvas(); renderInspector(); };
    const del = insDel(() => { bk[prop].splice(i, 1); if (!bk[prop].length) bk[prop].push({ lado: 'out', html: '' }); renderCanvas(); renderInspector(); });   // 2D: idem, a la cruz comun
    row.append(tog, del); cont.appendChild(row);
  });
  const addRow = document.createElement('div'); addRow.className = 'bk-row';
  const mk = (txt, lado) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = txt; b.className = 'insp-add insp-add-lado'; b.onclick = () => { bk[prop].push({ lado, html: '' }); renderCanvas(); selectBlock(SEL); const el = $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"] [data-prop="${prop}"][data-idx="${bk[prop].length - 1}"]`); if (el) el.focus(); }; return b; };
  addRow.append(mk('+ Cliente', 'in'), mk('+ Vendedor', 'out'));
  cont.appendChild(addRow);
  return cont;
}
// plantilla WhatsApp: carrusel de tarjetas (imagen + texto + botón opcionales)
function plantillaInspector(bk) {
  migrarPlantilla(bk);
  const cont = insCol();
  // lo que Meta va a rechazar, dicho antes de publicar
  const avisos = plantillaAvisos(bk);
  if (avisos.length) {
    const n = insNota('⚠️ ' + avisos.join('<br>'), 'insp-ayuda roja');
    cont.appendChild(n);
  }
  const refrescar = () => { renderCanvas(); renderInspector(); };
  const soloCanvas = () => {
    renderCanvas();
    $('#gbDoc').querySelector(`.gb-block[data-i="${SEL}"]`)?.classList.add('is-selected');
  };

  // ---- categoría (la que define Meta al aprobarla) ----
  cont.appendChild(lbl('Categoría de la plantilla'));
  const fc = document.createElement('div'); fc.className = 'bk-row';
  Object.entries(WA_CATS).forEach(([v, n]) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = n;
    b.className = 'ctipo' + (bk.categoria === v ? ' sel' : '');
    b.onclick = () => { bk.categoria = v; refrescar(); };
    fc.appendChild(b);
  });
  cont.appendChild(fc);
  cont.appendChild(insNota({
    marketing: 'Promos, novedades y reactivar clientes fríos. <b>Necesita que el cliente haya aceptado recibir</b>.',
    utilidad: 'Seguimiento de algo que el cliente ya hizo: una compra, una visita agendada.',
    autenticacion: 'Solo códigos de verificación.',
  }[bk.categoria] || '', 'insp-ayuda'));

  // ---- formato ----
  cont.appendChild(lbl('Formato'));
  const ff = document.createElement('div'); ff.className = 'bk-row';
  [['simple', 'Un mensaje'], ['carrusel', 'Carrusel de tarjetas']].forEach(([v, n]) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = n;
    b.className = 'ctipo' + (bk.formato === v ? ' sel' : '');
    b.onclick = () => { bk.formato = v; refrescar(); };
    ff.appendChild(b);
  });
  cont.appendChild(ff);

  // ---- encabezado (solo en formato simple; el carrusel lo lleva cada tarjeta) ----
  if (bk.formato !== 'carrusel') {
    cont.appendChild(lbl('Encabezado'));
    const fe = document.createElement('div'); fe.className = 'bk-row';
    [['ninguno', 'Sin encabezado'], ['texto', 'Texto'], ['imagen', 'Imagen']].forEach(([v, n]) => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = n;
      b.className = 'ctipo' + (bk.encabezado.tipo === v ? ' sel' : '');
      b.onclick = () => { bk.encabezado.tipo = v; refrescar(); };
      fe.appendChild(b);
    });
    cont.appendChild(fe);
    if (bk.encabezado.tipo === 'texto') {
      cont.appendChild(campoContado(bk.encabezado, 'texto', 60, 'Título corto del mensaje', soloCanvas));
    } else if (bk.encabezado.tipo === 'imagen') {
      const caja = insCaja();
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-ghost';
      b.textContent = bk.encabezado.src ? 'Cambiar imagen' : 'Subir imagen';
      const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.hidden = true;
      b.onclick = () => inp.click();
      inp.onchange = () => { if (inp.files[0]) subirImgPlantilla(bk.encabezado, inp.files[0]); inp.value = ''; };
      caja.append(b, inp);
      if (bk.encabezado.src) caja.appendChild(insDel(() => { bk.encabezado.src = ''; refrescar(); }));
      caja.appendChild(insNota('WhatsApp la muestra apaisada (1.91:1). Máximo 5 MB.'));
      cont.appendChild(caja);
    }
  }

  // ---- cuerpo del mensaje ----
  cont.appendChild(lbl(bk.formato === 'carrusel' ? 'Mensaje de arriba del carrusel' : 'Cuerpo del mensaje'));
  cont.appendChild(campoContado(bk, 'cuerpo', 1024,
    'Ej: {{1}}, esta semana tenemos 3 y 6 cuotas sin interés…', soloCanvas, true));
  cont.appendChild(insNota('Escribí <b>{{1}}</b>, <b>{{2}}</b>… donde el sistema tiene que poner el dato real (nombre, modelo, sucursal). Se ven resaltadas en la vista previa.', 'insp-ayuda'));

  if (bk.formato !== 'carrusel') {
    cont.appendChild(lbl('Pie (opcional)'));
    cont.appendChild(campoContado(bk, 'pie', 60, 'Ej: Respondé BAJA para no recibir más', soloCanvas));
    cont.appendChild(lbl('Botones'));
    cont.appendChild(botonesPlantilla(bk, bk.botones, 3, refrescar, soloCanvas));
  } else {
    // ---- tarjetas del carrusel ----
    cont.appendChild(lbl('Tarjetas (' + (bk.tarjetas || []).length + ')'));
    (bk.tarjetas || []).forEach((c, i) => {
      const caja = insCaja();
      caja.appendChild(insHead('Tarjeta ' + (i + 1), (bk.tarjetas.length > 2) ? () => {
        bk.tarjetas.splice(i, 1); refrescar();
      } : null));
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn btn-ghost';
      b.textContent = c.src ? 'Cambiar foto' : 'Subir foto';
      const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.hidden = true;
      b.onclick = () => inp.click();
      inp.onchange = () => { if (inp.files[0]) subirImgPlantilla(c, inp.files[0]); inp.value = ''; };
      caja.append(b, inp);
      caja.appendChild(campoContado(c, 'cuerpo', 160, 'Texto de la tarjeta…', soloCanvas, true));
      caja.appendChild(botonesPlantilla(bk, c.botones, 2, refrescar, soloCanvas));
      cont.appendChild(caja);
    });
    if ((bk.tarjetas || []).length < 10) {
      cont.appendChild(insAdd('+ Agregar tarjeta', () => {
        bk.tarjetas.push({ src: '', cuerpo: '', botones: [] }); refrescar();
      }));
    }
    cont.appendChild(insNota('Entre 2 y 10 tarjetas. <b>Todas tienen que tener lo mismo</b>: si una lleva texto o botones, todas.', 'insp-ayuda'));
  }
  return cont;
}

/* campo con contador de caracteres: los límites son los de Meta y pasarse
   hace que la plantilla no se apruebe, así que se avisa antes */
function campoContado(obj, prop, max, ph, alCambiar, multi) {
  const caja = document.createElement('div');
  caja.className = 'insp-col-fina';
  const el = document.createElement(multi ? 'textarea' : 'input');
  el.className = 'insp-input'; el.placeholder = ph; el.value = obj[prop] || '';
  if (multi) el.rows = max > 300 ? 4 : 3;
  const cta = document.createElement('div'); cta.className = 'fld-note insp-contador';
  const pintar = () => {
    const n = (obj[prop] || '').length;
    cta.textContent = n + ' / ' + max;
    cta.classList.toggle('pasado', n > max);
  };
  el.oninput = () => { obj[prop] = el.value; pintar(); if (alCambiar) alCambiar(); };
  pintar();
  caja.append(el, cta);
  return caja;
}

/* editor de botones con los límites reales: hasta 2 de enlace y 1 de teléfono */
function botonesPlantilla(bk, lista, max, refrescar, soloCanvas) {
  const cont = insCol();
  (lista || []).forEach((b, i) => {
    const caja = insCaja();
    caja.appendChild(insHead('Botón ' + (i + 1), () => { lista.splice(i, 1); refrescar(); }));
    const fila = document.createElement('div'); fila.className = 'bk-row';
    Object.entries(WA_TIPOS_BTN).forEach(([v, n]) => {
      const t = document.createElement('button'); t.type = 'button'; t.textContent = n;
      t.className = 'ctipo' + (b.tipo === v ? ' sel' : '');
      t.onclick = () => { b.tipo = v; refrescar(); };
      fila.appendChild(t);
    });
    caja.appendChild(fila);
    caja.appendChild(campoContado(b, 'texto', 25, 'Texto del botón', soloCanvas));
    if (b.tipo === 'enlace') caja.appendChild(urlInput(b, 'url', 'https://…'));
    if (b.tipo === 'telefono') {
      const tel = document.createElement('input'); tel.className = 'insp-input';
      tel.placeholder = '+54 9 11 …'; tel.value = b.url || '';
      tel.oninput = () => { b.url = tel.value; };
      caja.appendChild(tel);
    }
    cont.appendChild(caja);
  });
  if ((lista || []).length < max) {
    cont.appendChild(insAdd('+ Agregar botón', () => { lista.push({ tipo: 'rapida', texto: '', url: '' }); refrescar(); }));
  }
  // avisos de los topes de Meta
  const enlaces = (lista || []).filter(b => b.tipo === 'enlace').length;
  const tels = (lista || []).filter(b => b.tipo === 'telefono').length;
  const avisos = [];
  if (enlaces > 2) avisos.push('WhatsApp permite <b>hasta 2 botones de enlace</b>.');
  if (tels > 1) avisos.push('WhatsApp permite <b>un solo botón de teléfono</b>.');
  if (avisos.length) {
    const n = insNota('⚠️ ' + avisos.join(' '), 'insp-ayuda roja');
    cont.appendChild(n);
  }
  return cont;
}

async function subirImgPlantilla(obj, file) {
  const fd = new FormData();
  fd.append('key', (det.key || $('#dTitle').value || 'modulo') + '-wa-' + Date.now());
  fd.append('file', file);
  toast('Subiendo imagen…');
  try {
    const r = await api('/api/upload-contenido', { method: 'POST', body: fd });
    obj.src = r.src; renderCanvas(); renderInspector(); toast('Imagen lista', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

// ---- saneo del rich-text inline (solo b/i/a/br) ----
/* ===================================================================
   PEGAR DESDE WORD, EXCEL O UNA PÁGINA
   Antes el panel tiraba TODO el formato al pegar (getData('text/plain')):
   pegabas tres páginas de Word y entraba un chorizo para rearmar a mano.
   OJO: htmlABloques() NO sirve para esto. Está afinado a las clases de la
   propia intranet (.m-h, .m-p, .checklist…); el HTML de Word no las tiene y
   caería en el pasamanos crudo, metiendo estilos y basura mso-* en el sitio
   publicado. Por eso este traductor aparte.
   =================================================================== */

/* Mete en el documento lo que vino del portapapeles. Devuelve true si hizo algo.
   Lo usan LOS DOS caminos: el Ctrl+V y el botón "Pegar de Word o Excel". */
function pegarEnDocumento(html, texto) {
  let nuevos = [];
  if (html && pegarEsEstructurado(html)) nuevos = pegarABloques(html);
  if (!nuevos.length && texto) {
    // texto pelado de varios renglones (WhatsApp, un mail) → un párrafo por renglón
    const partes = texto.split(/\r?\n\s*\r?\n|\r?\n/).map(s => s.trim()).filter(Boolean);
    if (partes.length > 1) nuevos = partes.map(p => ({ t: 'parrafo', html: esc(p) }));
    else if (partes.length === 1 && !BLOQUES.length) nuevos = [{ t: 'parrafo', html: esc(partes[0]) }];
  }
  if (!nuevos.length) return false;
  const i = (SEL == null ? BLOQUES.length - 1 : SEL);
  BLOQUES.splice(i + 1, 0, ...nuevos);
  SEL = i + nuevos.length;
  renderCanvas(); selectBlock(SEL);
  toast(nuevos.length === 1 ? 'Se pegó 1 bloque' : ('Se pegaron ' + nuevos.length + ' bloques'), 'ok');
  return true;
}

/* Botón visible: lee el portapapeles sin que el usuario tenga que saber Ctrl+V.
   Si el navegador no da permiso, se lo dice y le explica el atajo. */
async function pegarDesdePortapapeles() {
  if (!navigator.clipboard || !navigator.clipboard.read) {
    toast('Tocá el documento y apretá Ctrl+V.', 'err');
    return;
  }
  try {
    const items = await navigator.clipboard.read();
    for (const it of items) {
      const tipoImg = it.types.find(t => t.startsWith('image/'));
      if (tipoImg) {
        const blob = await it.getType(tipoImg);
        insertBloque('imagen');
        subirImagenBloque(BLOQUES[SEL], new File([blob], 'captura.png', { type: tipoImg }));
        return;
      }
      const html = it.types.includes('text/html') ? await (await it.getType('text/html')).text() : '';
      const texto = it.types.includes('text/plain') ? await (await it.getType('text/plain')).text() : '';
      if (pegarEnDocumento(html, texto)) return;
    }
    toast('No hay nada para pegar. Copiá primero en Word o Excel.', 'err');
  } catch (e) {
    toast('El navegador no me deja leer el portapapeles. Tocá el documento y apretá Ctrl+V.', 'err');
  }
}

// ¿vale la pena romperlo en bloques, o es una frase suelta que va inline?
function pegarEsEstructurado(html) {
  const d = document.createElement('div'); d.innerHTML = html;
  if (d.querySelector('table')) return true;
  let conTexto = 0;
  d.querySelectorAll('p,h1,h2,h3,h4,h5,h6,ul,ol,li,blockquote').forEach(n => {
    if ((n.textContent || '').trim()) conTexto++;
  });
  return conTexto >= 2;
}

function pegarABloques(html) {
  const cont = document.createElement('div');
  cont.innerHTML = html;
  // fuera lo que Word y Excel arrastran y nunca queremos publicar
  cont.querySelectorAll('style,script,meta,link,title').forEach(n => n.remove());
  [...cont.querySelectorAll('*')].forEach(n => {
    if (/^(O:|W:|X:|XML)/i.test(n.tagName)) { n.remove(); return; }
    // se cae TODO atributo (style, class, lang, mso-*) salvo el link de un <a>
    [...n.attributes].forEach(a => {
      if (!(n.tagName === 'A' && a.name === 'href')) n.removeAttribute(a.name);
    });
  });

  const limpio = el => sanitizeInline(el.innerHTML).replace(/\s+/g, ' ').trim();
  const bloques = [];

  const tablaDe = tb => {
    const filas = [...tb.querySelectorAll('tr')].filter(tr => tr.cells.length);
    if (filas.length < 2) return null;
    const cols = [...filas[0].cells].map(c => ({ h: (c.textContent || '').trim(), num: false }));
    const cuerpo = filas.slice(1).map(tr => ({
      celdas: cols.map((_, i) => ((tr.cells[i] || {}).textContent || '').trim()),
      destaque: '',
    }));
    // una columna es de números si la mayoría de sus celdas lo son
    cols.forEach((c, i) => {
      let n = 0, tot = 0;
      cuerpo.forEach(f => {
        const v = f.celdas[i]; if (!v) return;
        tot++; if (/^[-+]?[\d.,\s$%]+$/.test(v)) n++;
      });
      c.num = tot > 0 && n / tot >= 0.6;
    });
    return { t: 'tabla', orden: true, buscar: false, cols, filas: cuerpo };
  };

  const listaDe = ul => {
    const items = [...ul.querySelectorAll(':scope > li')]
      .map(li => ({ icono: 'check', color: '--c-success', html: limpio(li) }))
      .filter(o => txtOf(o.html).length);
    return items.length ? { t: 'lista', items } : null;
  };

  const ver = el => {
    if (!el || el.nodeType !== 1) return;
    const tag = el.tagName;
    if (tag === 'TABLE') { const b = tablaDe(el); if (b) bloques.push(b); return; }
    if (tag === 'UL' || tag === 'OL') { const b = listaDe(el); if (b) bloques.push(b); return; }
    if (/^H[1-6]$/.test(tag)) {
      const h = limpio(el);
      if (h) bloques.push({ t: 'titulo', nivel: (tag === 'H1' || tag === 'H2') ? 'h1' : 'h2', html: h });
      return;
    }
    if (tag === 'P' || tag === 'BLOCKQUOTE') {
      const h = limpio(el); if (h) bloques.push({ t: 'parrafo', html: h });
      return;
    }
    // las fotos NO viajan dentro del HTML del portapapeles: hay que subirlas
    if (tag === 'BR' || tag === 'IMG') return;
    if (el.children.length) { [...el.children].forEach(ver); return; }
    const h = limpio(el); if (h) bloques.push({ t: 'parrafo', html: h });
  };
  [...cont.children].forEach(ver);
  return bloques;
}

function sanitizeInline(html) {
  const tmp = document.createElement('div'); tmp.innerHTML = html;
  (function walk(node) {
    [...node.childNodes].forEach(ch => {
      if (ch.nodeType !== 1) return;
      const tag = ch.tagName;
      if (tag === 'BR') return;
      if (['B', 'STRONG', 'I', 'EM', 'A'].includes(tag)) {
        let el = ch;
        if (tag === 'STRONG') { el = document.createElement('b'); el.innerHTML = ch.innerHTML; ch.replaceWith(el); }
        else if (tag === 'EM') { el = document.createElement('i'); el.innerHTML = ch.innerHTML; ch.replaceWith(el); }
        if (el.tagName === 'A') { const href = el.getAttribute('href') || ''; [...el.attributes].forEach(a => el.removeAttribute(a.name)); if (/^(https?:|mailto:)/i.test(href)) { el.setAttribute('href', href); el.setAttribute('target', '_blank'); el.setAttribute('rel', 'noopener'); } }
        walk(el);
      } else {
        const frag = document.createDocumentFragment();
        while (ch.firstChild) frag.appendChild(ch.firstChild);
        ch.replaceWith(frag);
      }
    });
  })(tmp);
  return tmp.innerHTML;
}

// ---- listeners delegados del canvas (una sola vez) ----
(function initCanvasEvents() {
  const doc = $('#gbDoc'); if (!doc) return;
  doc.addEventListener('click', e => {
    const block = e.target.closest('.gb-block'); if (!block) return;
    const i = +block.dataset.i;
    const hb = e.target.closest('.gb-handle button');
    if (hb) { if (hb.classList.contains('gb-h-up')) moverBloque(i, -1); else if (hb.classList.contains('gb-h-down')) moverBloque(i, 1); else if (hb.classList.contains('gb-h-del')) borrarBloque(i); return; }
    if (SEL !== i) selectBlock(i);
  });
  doc.addEventListener('input', e => {
    const ce = e.target.closest('[contenteditable]'); if (!ce) return;
    const block = ce.closest('.gb-block'); if (!block) return;
    const bk = BLOQUES[+block.dataset.i]; if (!bk) return;
    const val = sanitizeInline(ce.innerHTML);
    const prop = ce.dataset.prop, idx = +ce.dataset.idx, sub = ce.dataset.sub;
    if (prop === 'items') { if (sub) bk.items[idx][sub] = val; else bk.items[idx] = val; }
    else if (prop === 'steps') bk.steps[idx][sub] = val;
    else if (prop === 'mensajes') bk.mensajes[idx][sub] = val;
    else if (prop === 'tarjetas') bk.tarjetas[idx][sub] = val;
    else if (prop === 'celda') {                       // celda de tabla
      const r = +ce.dataset.r, c = +ce.dataset.c;
      const fila = (bk.filas || [])[r];
      if (fila) { if (!Array.isArray(fila.celdas)) fila.celdas = []; fila.celdas[c] = val; }
    }
    else if (prop === 'colh') {                        // encabezado de columna
      const c = +ce.dataset.c;
      if ((bk.cols || [])[c]) bk.cols[c].h = val;
    }
    else bk[prop] = val;
    // el largo de las barras depende de los valores: se recalcula en el acto,
    // pero SIN re-renderizar (si no, se pierde el cursor mientras escribís)
    if (bk.t === 'barras') refrescarBarras(block, bk);
  });
  /* El pegado se escucha en DOCUMENT, no en #gbDoc.
     Antes exigía que el cursor estuviera dentro de un texto editable, y en un
     documento VACÍO no existe ninguno: apretabas Ctrl+V y no pasaba nada, que
     es justamente el caso que el propio cartel invitaba a probar. */
  document.addEventListener('paste', e => {
    if ($('#viewDetalle').hidden) return;                 // solo con el editor abierto
    if (e.target.closest('input, textarea')) return;      // los campos del panel pegan normal
    const cd = e.clipboardData || window.clipboardData;
    if (!cd) return;

    // 1) una captura de pantalla → se sube y se inserta sola
    const foto = [...(cd.files || [])].find(f => /^image\//.test(f.type));
    if (foto) {
      e.preventDefault();
      insertBloque('imagen');
      subirImagenBloque(BLOQUES[SEL], foto);
      return;
    }

    const dentro = e.target.closest('#gbDoc [contenteditable]');
    const html = cd.getData('text/html');
    const texto = cd.getData('text/plain');

    // 2) contenido CON estructura (Word, Excel, una página) → bloques de verdad
    if (pegarEnDocumento(html, dentro ? '' : texto)) { e.preventDefault(); return; }

    // 3) una frase suelta dentro de un texto: entra inline, como siempre
    if (dentro) {
      e.preventDefault();
      document.execCommand('insertText', false, texto);
    }
  });
  doc.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const ce = e.target.closest('[contenteditable]'); if (!ce) return;
    const prop = ce.dataset.prop;
    const block = ce.closest('.gb-block'); if (!block) return;
    const i = +block.dataset.i, bk = BLOQUES[i]; if (!bk) return;
    // Enter dentro de una tabla: agrega una fila debajo y sigue escribiendo ahí
    if (prop === 'celda') {
      e.preventDefault();
      const r = +ce.dataset.r, c = +ce.dataset.c;
      bk.filas.splice(r + 1, 0, { celdas: (bk.cols || []).map(() => ''), destaque: '' });
      renderCanvas(); selectBlock(i);
      const nl = $('#gbDoc').querySelector(`.gb-block[data-i="${i}"] [data-prop="celda"][data-r="${r + 1}"][data-c="${c}"]`);
      if (nl) nl.focus();
      return;
    }
    if (prop !== 'items' && prop !== 'mensajes') return;
    e.preventDefault();
    const idx = +ce.dataset.idx, sub = ce.dataset.sub;
    const arr = bk[prop]; const prev = arr[idx] || {};
    let nuevo;
    if (prop === 'mensajes') nuevo = { lado: prev.lado || 'out', html: '' };
    else if (bk.t === 'chat') nuevo = { lado: prev.lado || 'out', html: '' };
    else if (bk.t === 'lista') nuevo = { icono: prev.icono || 'check', color: prev.color || '--c-success', html: '' };
    else if (ITEM_NUEVO[bk.t]) nuevo = ITEM_NUEVO[bk.t](prev);
    else nuevo = '';
    arr.splice(idx + 1, 0, nuevo); renderCanvas(); selectBlock(i);
    const q = `[data-prop="${prop}"][data-idx="${idx + 1}"]` + (sub ? `[data-sub="${sub}"]` : '');
    const nl = $('#gbDoc').querySelector(`.gb-block[data-i="${i}"] ${q}`);
    if (nl) nl.focus();
  });
})();

// ---- barra flotante de formato (negrita / itálica / link) ----
(function initFloat() {
  try { document.execCommand('styleWithCSS', false, false); } catch (e) {}
  const bar = $('#gbFloat'); if (!bar) return;
  bar.addEventListener('mousedown', e => e.preventDefault());
  bar.querySelectorAll('button').forEach(b => {
    b.onclick = () => {
      const f = b.dataset.fmt;
      if (f === 'undo') { const u = $('#detUndo'); if (u && !u.disabled) u.click(); return; }
      if (f === 'redo') { const r = $('#detRedo'); if (r && !r.disabled) r.click(); return; }
      if (f === 'bold') document.execCommand('bold');
      else if (f === 'italic') document.execCommand('italic');
      else if (f === 'underline') document.execCommand('underline');
      else if (f === 'link') { const u = prompt('Dirección del link (https://...)'); if (u) document.execCommand('createLink', false, u); }
      else if (f === 'unlink') document.execCommand('unlink');
      syncActiveEditable(); posFloat();
    };
  });
  document.addEventListener('selectionchange', posFloat);
})();
function editableDeSeleccion() {
  const sel = window.getSelection(); if (!sel || !sel.rangeCount) return null;
  let n = sel.anchorNode; if (n && n.nodeType === 3) n = n.parentNode;
  return n && n.closest ? n.closest('#gbDoc [contenteditable]') : null;
}
function syncActiveEditable() { const ed = editableDeSeleccion(); if (ed) ed.dispatchEvent(new Event('input', { bubbles: true })); }
function posFloat() {
  const bar = $('#gbFloat'); const sel = window.getSelection();
  /* Barra FIJA: vive en el encabezado del papel y no se mueve ni desaparece.
     La flotante obligaba a descubrirla seleccionando texto; el que edita una
     vez por semana no la encontraba nunca. Cuando no hay nada seleccionado
     los botones quedan apagados, que es la unica senal que hace falta. */
  if (bar && bar.classList.contains('fija')) {
    const hay = !!(sel && !sel.isCollapsed && sel.rangeCount && editableDeSeleccion());
    bar.classList.toggle('sin-seleccion', !hay);
    bar.hidden = false;
    return;
  }
  if (!sel || sel.isCollapsed || !sel.rangeCount || !editableDeSeleccion()) { bar.hidden = true; return; }
  const rect = sel.getRangeAt(0).getBoundingClientRect();
  if (!rect.width && !rect.height) { bar.hidden = true; return; }
  bar.hidden = false;
  const bw = bar.offsetWidth || 150;
  let left = rect.left + rect.width / 2 - bw / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - bw - 8));
  bar.style.left = left + 'px';
  bar.style.top = Math.max(8, rect.top - bar.offsetHeight - 8) + 'px';
}

/* ---- generación del HTML final (lo que se guarda y publica) ---- */
const ICO = k => `<span class="ico"><svg viewBox="0 0 24 24">${ICONS[k] || ICONS.layers}</svg></span>`;
function escBr(s) { return esc(s).replace(/\n/g, '<br>'); }
function txtOf(html) { return (html || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').trim(); }
function extDe(src) { const m = (src || '').match(/\.([a-z0-9]{2,5})(?:\?|$)/i); return m ? m[1].toLowerCase() : 'png'; }
function itemsLlenos(arr) { return (arr || []).filter(x => txtOf(x).length); }

function bloqueHTML(bk) {
  switch (bk.t) {
    case 'destacado': return `<p class="m-lead">${bk.html || escBr(bk.texto || '')}</p>`;
    case 'titulo': return `<div class="${bk.nivel === 'h2' ? 'm-h2' : 'm-h'}">${bk.html || esc(bk.texto || '')}</div>`;
    case 'kicker': return `<div class="m-kicker">${bk.n ? `<span class="n">${esc(bk.n)}</span>` : ''}<span>${bk.html || esc(bk.texto || '')}</span></div>`;
    case 'parrafo': return `<p class="m-p">${bk.html || escBr(bk.texto || '')}</p>`;
    case 'lista': return `<div class="checklist">${(bk.items || []).map(it => (typeof it === 'string') ? { icono: 'check', html: it } : it).filter(o => txtOf(o.html).length).map(o => `<div class="ci"><span class="ci-ic" style="background:var(${o.color || '--c-success'})">${ICO(o.icono || 'check')}</span><span>${o.html}</span></div>`).join('')}</div>`;
    case 'chat': return `<div class="chat"><div class="blabel">${bk.label || 'Ejemplo'}</div>${(bk.items || []).map(m => (typeof m === 'string') ? { lado: 'out', html: m } : m).filter(it => txtOf(it.html).length).map(it => `<div class="bubble ${it.lado === 'in' ? 'in' : 'out'}"><span>${it.html}</span>${it.lado === 'in' ? '' : '<span class="time">✓✓</span>'}</div>`).join('')}</div>`;
    case 'situacion': return `<div class="situ"><div class="sit-head"><span class="sit-tag" style="background:var(${bk.tagColor || '--c-warn'})">${esc(bk.tag || 'Situación')}</span><span>${bk.titulo || ''}</span></div>${bk.conResp ? `<div class="sit-arrow" style="color:var(${bk.respColor || '--c-success'})">${ICO(bk.respIcono || 'arrowDR')} ${esc(bk.resp || 'Respuesta recomendada')}</div>` : ''}<div class="chat">${(bk.mensajes || []).map(m => (typeof m === 'string') ? { lado: 'out', html: m } : m).filter(it => txtOf(it.html).length).map(it => `<div class="bubble ${it.lado === 'in' ? 'in' : 'out'}"><span>${it.html}</span>${it.lado === 'in' ? '' : '<span class="time">✓✓</span>'}</div>`).join('')}</div></div>`;
    case 'plantilla': return plantillaHTML(migrarPlantilla(bk));
    case 'nota': return `<div class="note"${bk.color ? ` style="--nota-acc:var(${bk.color})"` : ''}>${ICO(bk.icono || 'clock')}<div class="nt">${bk.html || escBr(bk.texto || '')}</div></div>`;
    case 'advertencia': return txtOf(bk.html || bk.texto).length ? `<div class="m-warn"><span class="ico">${SVG_WARN}</span><div class="mw-tx">${bk.html || escBr(bk.texto || '')}</div></div>` : '';
    case 'pasos': return `<div class="flow">${(bk.steps || []).filter(s => txtOf(s.titulo).length).map((s, i) => `${i ? `<div class="arrow">${ICO(s.conector || 'arrowR')}</div>` : ''}<div class="step"><div class="si" style="background:var(${s.color || '--c-caba'})">${ICO(s.icono || 'check')}</div><div class="st">${s.titulo || ''}</div><div class="sd">${s.desc || ''}</div></div>`).join('')}</div>`;
    /* SEÑALAR UN MÓDULO — la cartelera es un tablero de avisos, así que en
       vez de duplicar lo que ya vive en un módulo, la publicación lo apunta.

       Si la pieza señalada se puede MOSTRAR (un video, una foto, una galería),
       la tarjeta la muestra: un renglón de texto no dice nada de un video.
       El video arranca mudo y se reproduce solo mientras está a la vista; el
       botón de sonido lo desmutea sin salir de la cartelera. Toque en la
       tarjeta = ir al módulo, siempre, tenga preview o no.
       Clases prefijadas mr- a propósito. */
    case 'ref': {
      if (!bk.key) return '';
      const sub = bk.sub ? `<span class="mr-sub">${esc(bk.sub)}</span>` : '';
      const pie = [bk.clase, bk.detalle].filter(Boolean).map(esc).join(' · ');
      const pv = bk.prev;

      let previa = '';
      let clase = 'm-ref';
      if (pv && pv.t === 'video' && pv.src) {
        const ar = String(pv.ar || '16/9').split('/');
        /* La forma se declara YA con lo que guardó el panel, así la caja no
           arranca en 16/9 y pega un salto cuando el archivo dice otra cosa.
           La intranet la corrige sola al leer las medidas reales del video. */
        const rr = (+ar[0] || 16) / (+ar[1] || 9);
        clase += ' con-previa con-video midiendo ' +
          (rr < .88 ? 'vertical' : (rr <= 1.2 ? 'cuadrado' : 'horizontal'));
        previa =
          `<span class="mr-pv" style="--arw:${(+ar[0] || 16)};--arh:${(+ar[1] || 9)}">` +
            /* El #t=0.1 no es un capricho: con preload="metadata" el navegador conoce
             las medidas pero NO pinta ningún cuadro, así que la tarjeta quedaba
             como un rectángulo gris hasta que el vendedor scrolleaba hasta ella.
             Pidiendo un instante concreto, pinta ese frame de entrada. */
          `<video class="mr-vid" src="${esc(pv.src)}#t=0.1" muted loop playsinline preload="metadata"` +
            (pv.poster ? ` poster="${esc(pv.poster)}"` : '') + `></video>` +
            `<span class="mr-son" role="button" tabindex="0" aria-label="Activar sonido">` +
              `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>` +
            `</span>` +
          `</span>`;
      } else if (pv && pv.t === 'foto' && pv.src) {
        clase += ' con-previa con-foto midiendo horizontal';
        previa = `<span class="mr-pv"><img class="mr-img" src="${esc(pv.src)}" alt="" loading="lazy"></span>`;
      } else if (pv && pv.t === 'fotos' && (pv.srcs || []).length) {
        clase += ' con-previa con-fotos';
        const resto = (pv.total || pv.srcs.length) - pv.srcs.length;
        previa = `<span class="mr-pv mr-tira">` +
          pv.srcs.map(s2 => `<img src="${esc(s2)}" alt="" loading="lazy">`).join('') +
          (resto > 0 ? `<span class="mr-mas">+${resto}</span>` : '') + `</span>`;
      }

      /* Si se señaló UN bloque, el link lleva hasta ese bloque y no al módulo
         entero: #modulo/b<posicion>. Era el reclamo del usuario — elegía la
         galería puntual y al vendedor lo dejaba arriba de todo, obligándolo a
         buscarla. Sin bloque elegido (o en una publicación vieja, que no
         guardó la posición) el link sigue siendo el de siempre. */
      let bi = (bk.bi === 0 || bk.bi > 0) ? bk.bi : null;
      /* Las publicaciones hechas antes de esto guardaron el nombre del bloque
         pero no su posición. Se busca por nombre, así toman el link fino sin
         que nadie tenga que rehacerlas. */
      if (bi === null) bi = posicionDeBloque(bk.key, bk.sub);
      const destino = bi === null ? esc(bk.key) : esc(bk.key) + '/b' + bi;
      return `<a class="${clase}" href="#${destino}">` + previa +
        `<span class="mr-fila">` +
          `<span class="mr-ic" style="background:var(${bk.color || '--c-hudson'})">${ICO(bk.icon || 'layers')}</span>` +
          `<span class="mr-tx"><span class="mr-t">${esc(bk.mod || '')}${sub}</span>` +
          (pie ? `<span class="mr-d">${pie}</span>` : '') + `</span>` +
          `<span class="mr-go">${ICO('ext')}</span>` +
        `</span></a>`;
    }
    case 'separador': return `<div class="m-sep" style="height:${bk.grosor || 4}px"></div>`;
    case 'espacio': return `<div style="height:${({ sm: 14, md: 30, lg: 54 })[bk.alto] || 24}px"></div>`;
    case 'imagen': return bk.src ? `<figure class="m-img tam-${bk.tam || 'md'}"><img src="${esc(bk.src)}" alt="${esc(bk.alt || '')}" loading="lazy">${bk.caption ? `<figcaption>${esc(bk.caption)}</figcaption>` : ''}${bk.descargable ? `<a class="dl-btn" href="${esc(bk.src)}" download="${esc((bk.dlNombre || bk.caption || bk.alt || 'imagen').slice(0, 60))}.${extDe(bk.src)}">${ICO('download')} Descargar</a>` : ''}</figure>` : '';
    case 'galeria': { const its = (bk.items || []).filter(it => it.src); if (!its.length) return ''; return `<div class="dl-section">${bk.titulo ? `<div class="m-kicker"><span>${esc(bk.titulo)}</span></div>` : ''}<div class="gallery">${its.map(it => { const nm = (it.nombre || 'placa').slice(0, 60); return `<div class="gcard"><img class="gimg" src="${esc(it.src)}" alt="${esc(it.nombre || '')}" loading="lazy" onclick="openLightbox('${esc(it.src)}','${esc(nm)}')"><div class="gmeta"><div class="gtitle">${esc(it.nombre || '')}</div><a class="dl-btn" href="${esc(it.src)}" download="${esc(nm)}.${extDe(it.src)}">${ICO('download')} Descargar</a></div></div>`; }).join('')}</div></div>`; }
    case 'video': {
      const ar = arDe(bk);
      const clase = `m-video ${bk.orient === 'vert' ? 'vert' : 'horiz'} tam-${bk.tam || 'md'}`;
      const estilo = `--arw:${ar[0]};--arh:${ar[1]}`;
      const pie = bk.caption ? `<figcaption>${bk.caption}</figcaption>` : '';
      if (bk.src) {
        const nm = (bk.dlNombre || bk.caption || 'video').slice(0, 60);
        const dl = bk.descargable
          ? `<a class="dl-btn" href="${esc(bk.src)}" download="${esc(txtOf(nm))}.${extDe(bk.src)}">${ICO('download')} Descargar</a>` : '';
        /* ⚠️ preload="metadata" NO evita la descarga: medido, Chrome se baja
           el mp4 entero cuando es chico (994 KB por un video de 4 segundos que
           nadie miró). Quien decide es la intranet, y para poder decidir sin
           abrir el archivo necesita saber la forma de antemano: eso es
           data-med, que solo se pone cuando el video se midió de verdad al
           subirlo. Sin la marca, la intranet mide como siempre. */
        const med = bk.medido ? ' data-med="1"' : '';
        return `<figure class="${clase}"${med} style="${estilo}"><div class="v-box"><video src="${esc(bk.src)}" controls preload="metadata" playsinline${bk.poster ? ` poster="${esc(bk.poster)}"` : ''}></video></div>${pie}${dl}</figure>`;
      }
      if (bk.url) {
        const e = embedDeVideo(bk.url);
        if (!e.ok) return '';
        return `<figure class="${clase}" style="${estilo}"><div class="v-box"><iframe src="${esc(e.url)}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen title="video"></iframe></div>${pie}</figure>`;
      }
      return '';
    }
    case 'pdf': {
      if (!bk.src) return '';
      const nombre = (bk.nombre || 'Documento').slice(0, 80);
      const dl = bk.descargable !== false ? `<div class="pdf-dl"><a class="dl-btn" href="${esc(bk.src)}" download="${esc(nombre)}.pdf">${ICO('download')} Descargar</a></div>` : '';
      if (bk.modo === 'embebido') {
        return `<div class="pdf-block"><div class="report-frame report-${bk.alto || 'md'}"><iframe src="${esc(bk.src)}#view=FitH" loading="lazy" title="${esc(nombre)}"></iframe></div>${dl}</div>`;
      }
      return `<div class="pdf-block"><button type="button" class="pdf-card" onclick="openPdf('${esc(bk.src)}','${esc(nombre)}')"><span class="pdf-ic">${ICO('file')}</span><span class="pdf-meta"><span class="pdf-nombre">${esc(nombre)}</span><span class="pdf-sub">Tocar para abrir el PDF</span></span><span class="pdf-arrow">${ICO('ext')}</span></button>${dl}</div>`;
    }
    case 'embed': return bk.url ? `<div class="report-frame report-${bk.alto || 'md'}"><iframe src="${esc(bk.url)}" loading="lazy" title="contenido embebido"></iframe></div>` : '';
    case 'boton': return bk.url ? `<div class="m-btn"><a class="dl-btn" href="${esc(bk.url)}" target="_blank" rel="noopener">${ICO('ext')} ${esc(txtOf(bk.texto) || 'Abrir')}</a></div>` : '';
    case 'tabla': return tablaHTML(bk, false);
    case 'kpis': return kpisHTML(bk, false);
    case 'barras': return barrasHTML(bk, false);
    case 'podio': return podioHTML(bk, false);
    case 'tarjetas': return tarjetasHTML(bk, false);
    case 'diapo': return '';   // solo marca el corte; lo usa bloquesHTML en modo presentación
    case 'html': return bk.html || '';
    default: return '';
  }
}

/* Arma el HTML final. En modo presentación agrupa los bloques en <section class="dk-slide">
   cortando en cada bloque "diapo"; la intranet le pone la navegación encima. */
/* Dónde está, adentro de un módulo, el bloque que se llama así.
   Lo usan los bloques `ref` para armar el link fino (#modulo/b<n>) cuando la
   publicación guardó el NOMBRE del bloque pero no su posición. El nombre es
   el mismo que muestra el selector: el título de la galería o de la tabla, el
   epígrafe de una imagen o un video, el nombre del PDF.
   Devuelve null si no lo encuentra, y ahí el link queda apuntando al módulo
   entero, que es lo que hacía siempre. */
function posicionDeBloque(key, sub) {
  const nombre = String(sub || '').trim().toLowerCase();
  if (!key || !nombre) return null;
  const m = (Array.isArray(MODULOS) ? MODULOS : []).find(x => x.key === key);
  const bl = (m && m.content && m.content.bloques) || [];
  let nVid = 0, nImg = 0;
  for (let i = 0; i < bl.length; i++) {
    const bk = bl[i];
    let n = '';
    if (bk.t === 'galeria' || bk.t === 'tabla') n = bk.titulo || '';
    else if (bk.t === 'pdf') n = bk.nombre || '';
    else if (bk.t === 'imagen') { nImg++; n = (bk.caption || bk.alt || '').trim() || ('Imagen ' + nImg); }
    else if (bk.t === 'video') { nVid++; n = (bk.caption || bk.dlNombre || '').trim() || ('Video ' + nVid); }
    else continue;
    if (String(n).trim().toLowerCase() === nombre) return i;
  }
  return null;
}

function bloquesHTML(bloques, presentacion) {
  const lista = bloques || [];
  // Un bloque que no renderiza nada NO se emite. Antes salía un
  // <div class="db"></div> vacío por cada corte en modo Página, y también por
  // cada bloque a medio cargar (una imagen sin foto, un embed sin link…).
  // `.db` no tiene estilos propios, así que sacarlos no cambia cómo se ve nada.
  /* data-bi = la posición del bloque en el módulo. Es el ancla que permite que
     una publicación mande al vendedor AL BLOQUE señalado y no al módulo
     entero: el link viaja como #modulo/b<posicion> y la intranet scrollea
     hasta acá. Se emite siempre; sin link a mano no molesta a nadie. */
  const db = (bk, i) => { const h = bloqueHTML(bk); return h ? `<div class="db" data-bi="${i}">${h}</div>` : ''; };
  if (!presentacion) return lista.map(db).join('');

  const slides = [];
  let actual = { titulo: '', grupo: '', cuerpo: [] };
  // una diapositiva cuenta si tiene contenido O si tiene título propio: antes
  // pedía cuerpo sí o sí, así que el flujo natural (poner el corte al final y
  // escribirle el título) no generaba NADA y la diapositiva se perdía en silencio
  const cerrar = () => { if (actual.cuerpo.length || actual.titulo) slides.push(actual); };
  lista.forEach(bk => {
    if (bk.t === 'diapo') {
      cerrar();
      actual = { titulo: txtOf(bk.titulo), grupo: txtOf(bk.grupo), cuerpo: [] };
    } else {
      const h = db(bk);
      if (h) actual.cuerpo.push(h);
    }
  });
  cerrar();
  if (!slides.length) return '';
  return slides.map((s, i) => {
    // sin bloques debajo vale como diapositiva de sección: se muestra el título
    const cuerpo = s.cuerpo.length ? s.cuerpo.join('')
      : `<div class="db"><div class="m-h">${esc(s.titulo)}</div></div>`;
    return `<section class="dk-slide" data-n="${i + 1}" data-titulo="${esc(s.titulo || tituloDeSlide(s) || 'Diapositiva ' + (i + 1))}" data-grupo="${esc(s.grupo)}">${cuerpo}</section>`;
  }).join('');
}
/* si la diapositiva no tiene título propio, usa el primer título/etiqueta que aparezca adentro */
function tituloDeSlide(s) {
  const m = s.cuerpo.join('').match(/<div class="m-h2?">([\s\S]*?)<\/div>/);
  return m ? txtOf(m[1]).slice(0, 60) : '';
}

/* ===================================================================
   CONVERSIÓN de contenido viejo / diseño del sistema → bloques editables
   =================================================================== */
function migrarABloques(c, original) {
  if (c && c.tipo === 'bloques' && Array.isArray(c.bloques)) {
    const b = JSON.parse(JSON.stringify(c.bloques));
    b.forEach(bk => {
      if (bk.html == null && bk.texto != null) bk.html = escBr(bk.texto);
      if (bk.t === 'chat' && Array.isArray(bk.items)) bk.items = bk.items.map(m => typeof m === 'string' ? { lado: 'out', html: m } : m);
      if (bk.t === 'lista' && Array.isArray(bk.items)) { const g = bk.icono; bk.items = bk.items.map(it => { const o = typeof it === 'string' ? { icono: g || 'check', html: it } : it; if (!o.icono) o.icono = 'check'; if (!o.color) o.color = '--c-success'; return o; }); delete bk.icono; }
    });
    return b;
  }
  if (c && c.tipo === 'html') { const b = htmlABloques(c.html); return b.length ? b : (c.html ? [{ t: 'html', html: c.html }] : []); }
  if (c && c.tipo === 'embed') return [{ t: 'embed', url: c.url || '', alto: 'md' }];
  if (c && c.tipo === 'imagen') return [{ t: 'imagen', src: c.src || '', alt: '' }];
  if (c && c.tipo === 'link') return [{ t: 'boton', texto: c.texto || 'Abrir', url: c.url || '' }];
  if (original) { const b = htmlABloques(original); return b.length ? b : [{ t: 'html', html: original }]; }
  return [];
}

// matchea un <svg> contra el set ICONS para recuperar el nombre del ícono
function iconoDeSvg(el) {
  if (!el) return '';
  const svg = el.tagName && el.tagName.toLowerCase() === 'svg' ? el : el.querySelector('svg');
  if (!svg) return '';
  const paths = svg.innerHTML.replace(/\s+/g, ' ').trim();
  for (const k in ICONS) { if ((ICONS[k] || '').replace(/\s+/g, ' ').trim() === paths) return k; }
  return '';
}
function colorDeSi(si) {
  const bg = (si && si.style && si.style.background) || '';
  const m = bg.match(/var\((--c-[a-z]+)\)/);
  return m ? m[1] : '';
}

// convierte el HTML diseñado (ej. Manual de derivaciones) a un array de bloques
function htmlABloques(html) {
  if (!html) return [];
  const cont = document.createElement('div'); cont.innerHTML = html;
  const raiz = cont.querySelector('.manual') || cont;
  const bloques = [];
  const BASURA = 'span.ico, svg, .time';
  const inline = el => { if (!el) return ''; const c = el.cloneNode(true); c.querySelectorAll(BASURA).forEach(n => n.remove()); return c.innerHTML.replace(/\s+/g, ' ').trim(); };
  const texto = el => { if (!el) return ''; const c = el.cloneNode(true); c.querySelectorAll(BASURA).forEach(n => n.remove()); return (c.textContent || '').replace(/\s+/g, ' ').trim(); };

  function kickerDe(el) {
    const c = el.cloneNode(true); let n = null;
    const sn = c.querySelector('span.n'); if (sn) { n = sn.textContent.trim(); sn.remove(); }
    c.querySelectorAll('span.ico, svg, .sit-tag').forEach(x => x.remove());
    return { t: 'kicker', n, html: c.innerHTML.replace(/\s+/g, ' ').trim() };
  }
  function chatDe(el) {
    const lb = el.querySelector('.blabel');
    return { t: 'chat', label: lb ? texto(lb) : '', items: [...el.querySelectorAll('.bubble')].map(bub => ({ lado: bub.classList.contains('in') ? 'in' : 'out', html: inline(bub) })) };
  }
  function notaDe(el) {
    const ic = iconoDeSvg(el.querySelector('.ico, svg'));
    const nt = el.querySelector('.nt') || el;
    return { t: 'nota', icono: ic || 'clock', color: '', html: inline(nt) };
  }
  function pasosDe(el) {
    const arrows = [...el.querySelectorAll('.arrow')].map(a => iconoDeSvg(a.querySelector('.ico, svg')) || 'arrowR');
    return {
      t: 'pasos',
      steps: [...el.querySelectorAll('.step')].map((s, i) => Object.assign({
        titulo: texto(s.querySelector('.st')), desc: texto(s.querySelector('.sd')),
        icono: iconoDeSvg(s.querySelector('.si')) || 'check', color: colorDeSi(s.querySelector('.si')) || '--c-caba'
      }, i > 0 ? { conector: arrows[i - 1] || 'arrowR' } : {}))
    };
  }
  function imagenDe(el) { const img = el.tagName === 'IMG' ? el : el.querySelector('img'); if (!img) return null; const cap = el.querySelector('figcaption'); return { t: 'imagen', src: (img.getAttribute('src') || '').replace(/\?.*$/, ''), alt: img.getAttribute('alt') || '', caption: cap ? (cap.textContent || '').trim() : '' }; }
  function embedDe(el) { const fr = el.tagName === 'IFRAME' ? el : el.querySelector('iframe'); return fr ? { t: 'embed', url: fr.getAttribute('src') || '', alto: 'md' } : null; }

  function procesar(el, out) {
    if (!el || el.nodeType !== 1) return;
    const cl = el.classList; const tag = el.tagName;
    if (cl.contains('m-lead')) { out.push({ t: 'destacado', html: inline(el) }); return; }
    if (cl.contains('m-kicker') || cl.contains('sit-head')) { out.push(kickerDe(el)); return; }
    if (cl.contains('m-h')) { out.push({ t: 'titulo', nivel: 'h1', html: inline(el) }); return; }
    if (cl.contains('m-sub')) { out.push({ t: 'parrafo', html: inline(el) }); return; }
    if (cl.contains('m-p')) { out.push({ t: 'parrafo', html: inline(el) }); return; }
    if (cl.contains('flow')) { out.push(pasosDe(el)); return; }
    if (cl.contains('checklist')) { out.push({ t: 'lista', items: [...el.querySelectorAll('.ci')].map(ci => ({ icono: iconoDeSvg(ci.querySelector('.ico, svg')) || 'check', color: '--c-success', html: inline(ci) })) }); return; }
    if (cl.contains('benefits')) { out.push({ t: 'lista', items: [...el.querySelectorAll('.benefit')].map(b => { const bt = texto(b.querySelector('.bt')); const bd = texto(b.querySelector('.bd')); return { icono: iconoDeSvg(b.querySelector('.bi .ico, .bi svg')) || 'check', html: bd ? `${bt} — ${bd}` : bt }; }) }); return; }
    if (cl.contains('chat')) { out.push(chatDe(el)); return; }
    if (cl.contains('note')) { out.push(notaDe(el)); return; }
    if (cl.contains('situ')) {
      const head = el.querySelector('.sit-head'), tagEl = head && head.querySelector('.sit-tag');
      const arrowEl = el.querySelector('.sit-arrow'), chat = el.querySelector('.chat');
      let titulo = '';
      if (head) { const cc = head.cloneNode(true); const tg = cc.querySelector('.sit-tag'); if (tg) tg.remove(); titulo = cc.innerHTML.replace(/\s+/g, ' ').trim(); }
      out.push({
        t: 'situacion', tag: tagEl ? texto(tagEl) : 'Situación', tagColor: '--c-warn', titulo,
        conResp: !!arrowEl, resp: arrowEl ? texto(arrowEl) : 'Respuesta recomendada',
        respIcono: arrowEl ? (iconoDeSvg(arrowEl.querySelector('.ico, svg')) || 'arrowDR') : 'arrowDR', respColor: '--c-success',
        mensajes: chat ? [...chat.querySelectorAll('.bubble')].map(bub => ({ lado: bub.classList.contains('in') ? 'in' : 'out', html: inline(bub) })) : []
      });
      // el resto (nota / párrafos sueltos dentro de la situación) van como bloques aparte
      [...el.children].forEach(ch => { if (ch === head || ch === arrowEl || ch === chat) return; const c = ch.classList; if (c && (c.contains('sit-head') || c.contains('sit-arrow') || c.contains('chat'))) return; procesar(ch, out); });
      return;
    }
    if (cl.contains('sit-arrow')) return;
    if (tag === 'A' && el.getAttribute('href')) { out.push({ t: 'boton', texto: texto(el) || 'Abrir', url: el.getAttribute('href') }); return; }
    if (tag === 'FIGURE' || tag === 'IMG' || el.querySelector(':scope > img')) { const b = imagenDe(el); if (b) { out.push(b); return; } }
    if (tag === 'IFRAME' || el.querySelector(':scope > iframe')) { const b = embedDe(el); if (b) { out.push(b); return; } }
    // contenedor conocido a aplanar, o que tenga adentro bloques reconocibles → descender
    const RECON = '.m-lead,.m-kicker,.sit-head,.m-h,.m-sub,.m-p,.flow,.checklist,.benefits,.chat,.note,.situ,figure,img,iframe,a[href]';
    if (cl.contains('m-block') || el.querySelector(RECON)) { [...el.children].forEach(h => procesar(h, out)); return; }
    // elemento desconocido con contenido propio (ej. mockup .wa, .hint) → preservar como bloque html (sin pérdida)
    if ((el.textContent || '').trim() || el.querySelector('img, svg')) out.push({ t: 'html', html: el.outerHTML });
  }
  [...raiz.children].forEach(el => procesar(el, bloques));
  return bloques;
}

/* ---- acordeón de apariencia + menú "⋯ Más" de la barra ---- */
$('#apToggle').onclick = () => $('#apSec').classList.toggle('open');

/* En un módulo NUEVO los tres ítems del menú están ocultos (no se puede ocultar,
   restaurar ni eliminar algo que todavía no existe), así que "⋯ Más" abría una
   cajita blanca VACÍA de 14px. Si no hay nada adentro, el botón no va. */
function actualizarMenuMas() {
  const menu = $('#detMoreMenu'), caja = document.querySelector('.ebar-more');
  if (!menu || !caja) return;
  const hay = [...menu.children].some(c => !c.hidden);
  caja.hidden = !hay;
  if (!hay) menu.hidden = true;
}
$('#detMore').onclick = e => {
  e.stopPropagation();
  actualizarMenuMas();
  $('#detMoreMenu').hidden = !$('#detMoreMenu').hidden;
};
document.addEventListener('click', e => { if (!e.target.closest('.ebar-more')) $('#detMoreMenu').hidden = true; });
// vista previa: abre el módulo en la intranet local, en otra pestaña
if ($('#detVista')) $('#detVista').onclick = () => {
  $('#detMoreMenu').hidden = true;
  const k = det && det.key ? det.key : '';
  window.open('/intranet/' + (k ? '#' + k : ''), '_blank');
};

/* ---- popup de confirmación (prolijo) ---- */
// tono: 'peligro' (por defecto, rojo) | 'ok' (una acción constructiva, no destruye nada)
function confirmar(msg, yesLabel, titulo, tono) {
  return new Promise(res => {
    const m = $('#confirmModal'), ov = m.querySelector('.modal-ov');
    $('#confirmAlt').hidden = true; $('#confirmNo').textContent = 'Cancelar';
    $('#confirmTitle').textContent = titulo || '¿Confirmás?';
    $('#confirmMsg').textContent = msg;
    $('#confirmYes').className = 'btn ' + (tono === 'ok' ? 'active' : 'btn-danger');
    $('#confirmYes').textContent = yesLabel || 'Eliminar';
    abrirModal(m);
    const cerrar = v => { esconderModal(m); $('#confirmYes').onclick = $('#confirmNo').onclick = ov.onclick = null; res(v); };
    $('#confirmYes').onclick = () => cerrar(true);
    $('#confirmNo').onclick = () => cerrar(false);
    ov.onclick = () => cerrar(false);
  });
}
// diálogo de 3 opciones para salir con cambios sin guardar
function confirmarSalida() {
  return new Promise(res => {
    const m = $('#confirmModal'), ov = m.querySelector('.modal-ov');
    $('#confirmTitle').textContent = 'Cambios sin guardar';
    $('#confirmMsg').textContent = 'Hiciste cambios que no guardaste. ¿Qué querés hacer antes de salir?';
    // sin esto heredaba el rojo de la confirmación anterior: "Guardar y salir"
    // no destruye nada, no puede verse como el botón de eliminar
    $('#confirmYes').className = 'btn active';
    $('#confirmYes').textContent = 'Guardar y salir';
    $('#confirmAlt').textContent = 'Salir sin guardar'; $('#confirmAlt').hidden = false;
    $('#confirmNo').textContent = 'Seguir editando';
    abrirModal(m);
    const cerrar = v => { esconderModal(m); $('#confirmAlt').hidden = true; $('#confirmNo').textContent = 'Cancelar'; $('#confirmYes').onclick = $('#confirmNo').onclick = $('#confirmAlt').onclick = ov.onclick = null; res(v); };
    $('#confirmYes').onclick = () => cerrar('save');
    $('#confirmAlt').onclick = () => cerrar('discard');
    $('#confirmNo').onclick = () => cerrar('cancel');
    ov.onclick = () => cerrar('cancel');
  });
}
// snapshot del estado del editor para detectar cambios sin guardar
let editorSnapshot = null;
function estadoEditor() {
  if ($('#viewDetalle').hidden || !det) return null;
  return JSON.stringify({
    t: $('#dTitle').value, d: $('#dDesc').value, r: $('#dReady').checked,
    ic: det.icon, co: det.color, hi: det.hidden, pr: PRESENTACION, blk: BLOQUES,
    col: COLECCION, di: DOC_IDX, pal: COL_PALABRA, mu: ES_MURO
  });
}
function hayCambios() { return editorSnapshot != null && estadoEditor() !== editorSnapshot; }
async function salirEditor() {
  if (hayCambios()) {
    const r = await confirmarSalida();
    if (r === 'cancel') return;
    if (r === 'save') { $('#detSave').click(); return; }   // guarda y sale (si el título falta, avisa y se queda)
  }
  editorSnapshot = null;
  mostrarDetalle(false);
}
// aviso del navegador si cierra/recarga la pestaña con cambios sin guardar
window.addEventListener('beforeunload', e => { if (hayCambios()) { e.preventDefault(); e.returnValue = ''; } });

// ---- estados de los botones (Guardar/Guardado), autoguardado y deshacer ----
let autosaveTimer = null, watchTimer = null, ultimoEstado = null;
let undoStack = [], redoStack = [], undoAplicando = false;

function actualizarBotones() {
  const dirty = hayCambios() || detNew;   // hay cambios sin guardar (o módulo nuevo)
  // Publicar pendiente: en modo cerebro se basa en si hay ediciones sin publicar
  // (no en git). Ambos roles ven el mismo estado.
  const pubPend = dirty || (MODO_CEREBRO ? (editados && editados.size > 0) : gitPendiente);
  /* 2B decia ESTADO ≠ ACCION y mandaba el resultado a un chip gris de 11px
     al costado. En uso real no alcanza: se apreta Guardar, el boton sigue
     diciendo "Guardar" y la persona no sabe si paso algo (lo reporto el
     usuario el 4-sep). El rotulo vuelve a contar el estado —"Guardado ✓",
     "Publicado ✓"— y con el primer cambio nuevo vuelve a ser una accion.
     El chip queda como refuerzo, no como unico aviso.
     ⚠️ conBoton restaura el rotulo que habia ANTES de trabajar, asi que los
     onclick de #detSave/#detPublicar llaman a esta funcion al terminar. */
  const sb = $('#detSave');
  if (sb && !sb.dataset.ocupado) {
    sb.classList.toggle('active', dirty);
    sb.classList.toggle('btn-hecho', !dirty);
    rotularBoton(sb, dirty ? 'Guardar' : 'Guardado ✓');
    sb.title = dirty ? 'Guarda los cambios en esta computadora.'
                     : 'No hay cambios sin guardar.';
  }
  const pb = $('#detPublicar');
  if (pb && !pb.disabled) {
    const hecho = !pubPend;
    pb.classList.toggle('btn-hecho', hecho);
    rotularBoton(pb, hecho ? 'Publicado ✓' : 'Publicar');
    pb.title = hecho ? 'El sitio online está igual que este panel.'
                     : 'Sube al sitio lo que editaste. Los vendedores lo ven en ~30 s.';
  }
  const ch = $('#detEstado');
  if (ch) {
    // con cambios sin guardar no hay nada que declarar: el chip se esconde
    if (dirty) ch.hidden = true;
    else {
      ch.hidden = false;
      const tx = $('#detEstadoTx');
      if (tx) tx.textContent = pubPend ? 'Guardado' : 'Publicado';
    }
  }
  if (MODO_CEREBRO) actualizarPublicarHome();
}
function actualizarUndoBtn() {
  const u = $('#detUndo');
  if (u) {
    u.disabled = !undoStack.length;
    // decir POR QUÉ está apagado es lo que destraba al usuario
    u.title = undoStack.length ? 'Deshacer (volver atrás)' : 'Nada para deshacer todavía';
  }
  const r = $('#detRedo');
  if (r) {
    r.disabled = !redoStack.length;
    r.title = redoStack.length ? 'Rehacer (volver adelante)' : 'Nada para rehacer todavía';
  }
}

// se ejecuta cada ~1s mientras se edita: detecta cambios → guarda checkpoint de deshacer + refresca botones
function vigilarEstado() {
  const s = estadoEditor();
  if (s === null) return;
  if (ultimoEstado === null) { ultimoEstado = s; return; }
  if (s !== ultimoEstado) {
    if (!undoAplicando) {
      undoStack.push(ultimoEstado);
      if (undoStack.length > 80) undoStack.shift();
      redoStack = [];   // una edicion nueva abre otra rama: lo rehacible muere
      actualizarUndoBtn();
    }
    ultimoEstado = s;
    actualizarBotones();
  }
}
function aplicarSnapshot(snap) {
  undoAplicando = true;
  $('#dTitle').value = snap.t || ''; $('#dDesc').value = snap.d || ''; $('#dReady').checked = !!snap.r;
  det.icon = snap.ic; det.color = snap.co; det.hidden = snap.hi;
  PRESENTACION = !!snap.pr;
  COLECCION = snap.col ? JSON.parse(JSON.stringify(snap.col)) : null;
  DOC_IDX = (snap.di == null) ? null : snap.di;
  COL_PALABRA = snap.pal || '';
  ES_MURO = !!snap.mu;
  BLOQUES = JSON.parse(JSON.stringify(snap.blk || []));
  SEL = BLOQUES.length ? Math.min(SEL == null ? 0 : SEL, BLOQUES.length - 1) : null;
  try { pintarDIconGrid(); pintarDColorGrid(); pintarDPreview(); pintarModo(); } catch (e) {}
  if (COLECCION && DOC_IDX == null) {           // estaba en la lista de documentos
    $('#docBar').hidden = true;
    mostrarPane('coleccion'); moveApA('#colApSlot'); renderColeccion();
  } else {
    $('#docBar').hidden = !COLECCION;
    if (COLECCION) {
      const d = COLECCION[DOC_IDX] || {};
      $('#docTitulo').value = d.titulo || ''; $('#docEtiqueta').value = d.etiqueta || '';
      volcarDatosPost();
    }
    mostrarPane('bloques');
    renderGbEditor();
  }
  actualizarBotones();
  ultimoEstado = estadoEditor();
  setTimeout(() => { undoAplicando = false; }, 30);
}
function deshacer() {
  if (!undoStack.length) return;
  const ahora = estadoEditor();   // lo que hay ANTES de volver: eso es lo rehacible
  if (ahora !== null) { redoStack.push(ahora); if (redoStack.length > 80) redoStack.shift(); }
  aplicarSnapshot(JSON.parse(undoStack.pop()));
  actualizarUndoBtn();
}
// rehacer es deshacer al reves, sobre el MISMO mecanismo de snapshots
function rehacer() {
  if (!redoStack.length) return;
  const ahora = estadoEditor();
  if (ahora !== null) { undoStack.push(ahora); if (undoStack.length > 80) undoStack.shift(); }
  aplicarSnapshot(JSON.parse(redoStack.pop()));
  actualizarUndoBtn();
}
function arrancarEdicion() {
  ultimoEstado = estadoEditor(); undoStack = []; redoStack = []; actualizarUndoBtn(); actualizarBotones();
  refrescarGit();   // refresca el estado del botón Publicar
  clearInterval(watchTimer); watchTimer = setInterval(vigilarEstado, 1000);
  clearInterval(autosaveTimer);
  autosaveTimer = setInterval(() => {
    if (!$('#viewDetalle').hidden && hayCambios() && $('#dTitle').value.trim()) {
      guardarModulo({ salir: false, auto: true }).then(ok => { if (ok) toast('Autoguardado ✓', 'ok'); });
    }
  }, 60000);
}
function pararEdicion() { clearInterval(watchTimer); clearInterval(autosaveTimer); watchTimer = autosaveTimer = null; ultimoEstado = null; }

$('#detUndo').onclick = () => deshacer();
$('#detRedo').onclick = () => rehacer();
// "Publicar" del editor: guarda primero si hay cambios, después publica
$('#detPublicar').onclick = async () => {
  if (hayCambios()) { const ok = await guardarModulo({ salir: false }); if (!ok) return; }
  try { await publicarCambios(); }
  finally { actualizarBotones(); }   // deja el rótulo que corresponde al estado real
};

/* ===================================================================
   MATERIAL DESCARGABLE — gestor de imágenes agrupado por sección
   =================================================================== */
/* ver imagen en grande (lightbox) */
function verImagen(file) {
  $('#imgLightboxImg').src = '/intranet/' + file + '?t=' + Date.now();
  abrirModal($('#imgLightbox'));
}
$('#imgLbClose').onclick = () => { esconderModal($('#imgLightbox')); };
$('#imgLightbox').onclick = e => { if (e.target.id === 'imgLightbox') esconderModal($('#imgLightbox')); };
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (!$('#imgLightbox').hidden) { esconderModal($('#imgLightbox')); return; }
  // los modales informativos cierran con Escape como todo lo demás. El de
  // confirmar NO entra acá a propósito: su Escape lo maneja confirmar() y una
  // pregunta destructiva no se descarta por accidente.
  for (const id of ['histModal', 'avisarModal', 'kitModal']) {
    const m = document.getElementById(id);
    /* con el armazón de la maqueta, "abierto" es la clase .on (no [hidden]) */
    if (m && m.classList.contains('on')) { const x = m.querySelector('[data-cerrar-hist], [data-cerrar-avisar], [data-cerrar-kit]'); if (x) x.click(); return; }
  }
});

/* clic en el fondo oscuro = cerrar, para los modales informativos.
   El compositor (#fondo) tiene su propio cierre; confirmar, aprobaciones y
   la actualización deciden solos, que para eso existen. */
document.addEventListener('click', e => {
  const f = e.target;
  if (!(f instanceof HTMLElement) || !f.classList.contains('fondo')) return;
  if (['fondo', 'confirmModal', 'bandeja', 'mActualizando'].includes(f.id)) return;
  const x = f.querySelector('[data-cerrar-hist], [data-cerrar-avisar], [data-cerrar-kit], .comp-cerrar');
  if (x) x.click();
});

/* grid de descargables que está bajo el cursor */
function gridUnder(x, y) {
  for (const g of document.querySelectorAll('#dGalGroups .gal-grid')) {
    const r = g.getBoundingClientRect();
    if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return g;
  }
  return null;
}

/* arrastre propio (pointer): la card se despega y flota en la mano.
   El click (toque sin arrastrar) abre la imagen en grande. */
let suppressZoomClick = false;
function attachDragZoom(card, sec, img) {
  card.addEventListener('click', e => {
    if (e.target.closest('.gx')) return;
    if (suppressZoomClick) { suppressZoomClick = false; return; }  // venía de un arrastre
    verImagen(img.file);
  });
  card.addEventListener('pointerdown', e => {
    if (e.button !== 0 || e.target.closest('.gx')) return;
    suppressZoomClick = false;
    const startX = e.clientX, startY = e.clientY;
    const r0 = card.getBoundingClientRect();
    const offX = e.clientX - r0.left, offY = e.clientY - r0.top;
    let dragging = false, ghost = null, ph = null;

    const begin = ev => {
      dragging = true;
      const sel = window.getSelection(); if (sel) sel.removeAllRanges();
      ghost = document.createElement('div');
      ghost.className = 'drag-ghost';
      ghost.style.width = r0.width + 'px';
      ghost.innerHTML = `<img src="${card.querySelector('img').src}" alt="">`;
      ghost.style.left = (ev.clientX - offX) + 'px';
      ghost.style.top = (ev.clientY - offY) + 'px';
      document.body.appendChild(ghost);
      requestAnimationFrame(() => ghost.classList.add('lift'));   // se despega y flota
      document.body.classList.add('grabbing');                   // mano cerrada
      ph = document.createElement('div');
      ph.className = 'gcard-placeholder';
      card.parentNode.insertBefore(ph, card);
      card.style.display = 'none';
    };
    const move = ev => {
      if (!dragging) {
        if (Math.hypot(ev.clientX - startX, ev.clientY - startY) < 6) return;
        begin(ev);
      }
      ghost.style.left = (ev.clientX - offX) + 'px';
      ghost.style.top = (ev.clientY - offY) + 'px';
      const grid = gridUnder(ev.clientX, ev.clientY);
      if (grid) {
        const empty = grid.querySelector('.gal-empty'); if (empty) empty.remove();
        const after = galAfterElement(grid, ev.clientX, ev.clientY);
        if (after == null) grid.appendChild(ph); else grid.insertBefore(ph, after);
      }
    };
    const up = async () => {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', up);
      if (!dragging) return;                 // fue un toque -> lo maneja el 'click'
      suppressZoomClick = true;              // que el click posterior no abra el zoom
      document.body.classList.remove('grabbing');
      if (ph && ph.parentNode) ph.parentNode.insertBefore(card, ph);
      if (ph) ph.remove();
      card.style.display = '';
      if (ghost) ghost.remove();
      await persistirLayout();
    };
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', up);
  });
}

async function renderDescargables() {
  const cont = $('#dGalGroups');
  cont.innerHTML = '<p class="muted">Cargando…</p>';
  let grupos = [];
  try { grupos = (await api('/api/descargables')).grupos; }
  catch (e) { cont.innerHTML = '<p class="muted">No se pudo cargar.</p>'; return; }
  cont.innerHTML = '';
  grupos.forEach(g => cont.appendChild(grupoBlock(g)));
}

function grupoBlock(g) {
  const wrap = document.createElement('div');
  wrap.className = 'gal-group';
  wrap.innerHTML = `
    <div class="gal-group-head">
      <div class="gal-group-t">${esc(g.label)} <span class="gal-count">${g.images.length}</span></div>
      <button class="btn btn-ghost gal-add" type="button">+ Adjuntar imagen</button>
      <input type="file" class="gal-file" accept="image/*" multiple hidden>
    </div>
    <div class="gal-grid" data-key="${g.key}"></div>`;
  const grid = wrap.querySelector('.gal-grid');
  if (!g.images.length) grid.innerHTML = '<div class="gal-empty">Arrastrá imágenes acá o tocá “Adjuntar imagen”.</div>';
  else g.images.forEach(img => grid.appendChild(galCard(img, g.key)));
  const file = wrap.querySelector('.gal-file');
  wrap.querySelector('.gal-add').onclick = () => file.click();
  file.onchange = () => { if (file.files.length) subirAGrupo(g.key, file.files); file.value = ''; };
  setupGrupoDnD(grid, g.key);
  return wrap;
}

function galCard(img, sec) {
  const c = document.createElement('div');
  c.className = 'gcard-mini';
  c.dataset.sec = sec;
  c.dataset.dl = img.download;
  c.innerHTML = `<button class="gx" type="button" title="Eliminar"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
    <img src="/intranet/${img.file}?t=${Date.now()}" alt="" draggable="false">
    <div class="gcard-cap">${esc(img.title)}</div>`;
  c.querySelector('.gx').onclick = async e => {
    e.stopPropagation();
    if (!await confirmar('¿Querés eliminar esta imagen? No se puede deshacer.', 'Sí, eliminar', 'Eliminar imagen')) return;
    try {
      await api('/api/borrar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ seccion: sec, download: img.download }) });
      toast('Imagen eliminada', 'ok'); renderDescargables(); refrescarGit();
    } catch (err) { toast(err.message, 'err'); }
  };
  attachDragZoom(c, sec, img);
  return c;
}

async function subirAGrupo(sec, files) {
  const fd = new FormData(); fd.append('seccion', sec);
  [...files].forEach(f => fd.append('file', f));
  toast('Subiendo ' + files.length + ' imagen(es)…');
  try {
    const r = await api('/api/upload', { method: 'POST', body: fd });
    if (r.errores && r.errores.length) toast(r.errores[0], 'err'); else toast('Imagen(es) agregada(s)', 'ok');
    renderDescargables(); refrescarGit();
  } catch (e) { toast(e.message, 'err'); }
}

function setupGrupoDnD(grid, sec) {
  // solo para archivos arrastrados desde el explorador (el reordenado usa pointer)
  grid.addEventListener('dragover', e => {
    if (e.dataTransfer && [...e.dataTransfer.types].includes('Files')) { e.preventDefault(); grid.classList.add('drop-on'); }
  });
  grid.addEventListener('dragleave', e => { if (!grid.contains(e.relatedTarget)) grid.classList.remove('drop-on'); });
  grid.addEventListener('drop', e => {
    grid.classList.remove('drop-on');
    if (e.dataTransfer.files && e.dataTransfer.files.length) { e.preventDefault(); subirAGrupo(sec, e.dataTransfer.files); }
  });
}

function galAfterElement(grid, x, y) {
  const cards = [...grid.querySelectorAll('.gcard-mini')].filter(el => el.style.display !== 'none' && el.offsetParent !== null);
  let best = null, bestDist = Infinity, after = false;
  for (const card of cards) {
    const r = card.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const dist = Math.hypot(x - cx, y - cy);
    if (dist < bestDist) { bestDist = dist; best = card; after = x > cx; }
  }
  if (!best) return null;
  return after ? best.nextSibling : best;
}

async function persistirLayout() {
  const orden = {};
  document.querySelectorAll('#dGalGroups .gal-grid').forEach(grid => {
    orden[grid.dataset.key] = [...grid.querySelectorAll('.gcard-mini')].map(c => ({ download: c.dataset.dl, from: c.dataset.sec }));
  });
  try {
    await api('/api/reorganizar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ orden }) });
    toast('Orden actualizado', 'ok'); renderDescargables(); refrescarGit();
  } catch (e) { toast(e.message, 'err'); renderDescargables(); }
}

// ---- acciones ----
async function guardarModulo({ salir = true, auto = false } = {}) {
  const title = $('#dTitle').value.trim();
  if (!title) { if (!auto) toast('Poné un título', 'err'); return false; }
  det.title = title;
  det.desc = $('#dDesc').value.trim();
  det.ready = $('#dReady').checked;
  // descargables en modo galería NO guarda bloques (lo maneja el gestor); en modo bloques (migrado) sí
  const galeriaMode = det.key === 'descargables' && !COLECCION &&
    !(det.content && det.content.tipo === 'bloques');
  if (COLECCION) {
    if (DOC_IDX != null) guardarDocEnColeccion();
    const sinNombre = COLECCION.filter(d => !(d.titulo || '').trim()).length;
    if (sinNombre) {
      if (!auto) toast(ES_MURO ? 'Ponele un título a cada publicación'
                               : 'Poné un nombre a cada ' + palabra() + ' (ej: Julio 2026)', 'err');
      return false;
    }
    if (!COLECCION.length) { if (!auto) toast('Agregá al menos ' + unUna() + ' ' + palabra(), 'err'); return false; }
    det.content = ES_MURO ? {
      tipo: 'cartelera',
      docs: COLECCION.map(d => ({
        id: d.id || nuevoId(),
        titulo: (d.titulo || '').trim(),
        autor: (d.autor || '').trim(),
        sucursal: (d.sucursal || '').trim(),
        fecha: d.fecha || hoyISO(),
        etiqueta: ETIQUETAS_MURO.indexOf(d.etiqueta) >= 0 ? d.etiqueta : '',
        fijado: !!d.fijado,
        confirmar: !!d.confirmar,          // pide "Entendido"
        vence: d.vence || '',                        // último día que se ve

        archivado: !!d.archivado,
        bloques: d.bloques || [],
        /* OJO: si la publicación NO tiene bloques (llegó con el html ya armado
           desde afuera del panel), regenerar la dejaría VACÍA. Ya pasó una vez
           con los documentos de una biblioteca: se guarda un módulo y se borra
           el cuerpo de piezas que nadie tocó. Sin bloques, se respeta el html. */
        html: (Array.isArray(d.bloques) && d.bloques.length)
          ? bloquesHTML(d.bloques, false)            // una publicación nunca es presentación
          : (d.html || ''),
      })),
    } : {
      tipo: 'coleccion',
      palabra: palabra(),
      docs: COLECCION.map(d => ({
        id: d.id || nuevoId(),
        titulo: (d.titulo || '').trim(),
        etiqueta: (d.etiqueta || '').trim(),
        archivado: !!d.archivado,
        presentacion: !!d.presentacion,
        /* si alguna vez fue muro, los datos de publicación viajan igual: no
           cuestan nada y volver a "Muro" recupera todo tal cual estaba */
        ...(d.autor !== undefined ? { autor: d.autor, sucursal: d.sucursal || '',
                                      fecha: d.fecha || '', fijado: !!d.fijado } : {}),
        bloques: d.bloques || [],
        html: (Array.isArray(d.bloques) && d.bloques.length)
          ? bloquesHTML(d.bloques, d.presentacion)
          : (d.html || ''),
      })),
    };
  }
  else if (!galeriaMode) {
    // un módulo del sistema que quedó EXACTO con su diseño original (1 bloque html sin tocar) → no escribir override
    const intacto = det.builtin && !PRESENTACION && BLOQUES.length === 1 && BLOQUES[0].t === 'html' && BLOQUES[0].html === detOriginal;
    if (intacto) {
      delete det.content;
    } else {
      if (!BLOQUES.length) { if (!auto) toast('Agregá al menos un bloque', 'err'); return false; }
      det.content = { tipo: 'bloques', bloques: BLOQUES, html: bloquesHTML(BLOQUES, PRESENTACION), presentacion: PRESENTACION };
    }
  }
  /* La fecha de novedad ya NO se pone al guardar: muchas publicaciones son
     para ir viendo cómo queda, y avisarle a los vendedores en cada una es
     ruido. Se marca a mano desde "Avisar novedad". */
  if (detNew) {
    MODULOS.push(det); detNew = false; detIdx = MODULOS.length - 1;
    // ya existe: ahora sí se puede ocultar y eliminar, y el menú "⋯ Más" tiene sentido
    $('#detDelete').hidden = false; $('#detHide').hidden = false;
    actualizarMenuMas();
  }
  else MODULOS[detIdx] = det;
  try {
    await persistModulos(auto ? false : 'Guardado ✓ No te olvides de publicar.');
    marcarEditado((MODULOS[detIdx] || det).key);   // queda "Editado" hasta que se publique
    editorSnapshot = estadoEditor();   // lo guardado pasa a ser la nueva base
    ultimoEstado = editorSnapshot;
    actualizarBotones();
    if (salir) mostrarDetalle(false);
    return true;
  } catch (e) { if (!auto) toast(e.message, 'err'); return false; }
}
// guarda y se queda en el editor. Va por conBoton para que se vea que está
// trabajando y para que un segundo click no dispare otro guardado.
/* conBoton deja el rótulo que había ANTES de trabajar; si el guardado salió
   bien ese rótulo quedó vencido ("Guardar" cuando ya está guardado). Por eso
   actualizarBotones corre al final, pase lo que pase. */
$('#detSave').onclick = () => conBoton('#detSave', 'Guardando…',
  () => guardarModulo({ salir: false })).then(actualizarBotones, actualizarBotones);

$('#detDelete').onclick = async () => {
  if (detNew) return;
  if (!await confirmar('¿Estás seguro que querés eliminar el módulo "' + det.title + '"? No se puede deshacer.', 'Sí, eliminar', 'Eliminar módulo')) return;
  editados.delete(det.key); guardarEditados();
  MODULOS.splice(detIdx, 1);
  try { await persistModulos('Módulo eliminado.'); mostrarDetalle(false); }
  catch (e) { toast(e.message, 'err'); }
};

$('#detHide').onclick = () => {
  det.hidden = !det.hidden;
  $('#detHide').textContent = det.hidden ? 'Mostrar en el menú' : 'Ocultar del menú';
  toast(det.hidden ? 'Quedará oculto al guardar' : 'Quedará visible al guardar');
};

$('#detRestore').onclick = async () => {
  if (!await confirmar('¿Volver al diseño original del sistema? Se quitarán los cambios que hiciste.', 'Sí, restaurar', 'Restaurar diseño')) return;
  delete det.content;
  $('#detMoreMenu').hidden = true;
  renderContenidoEditor();
  toast('Restaurado. Guardá el módulo para aplicar.');
};

$('#detBack').onclick = () => salirEditor();
$('#detCancel').onclick = () => salirEditor();

// ---------- toggle de vista escritorio / celular ----------
function setVista(v) {
  $('#gbDoc').classList.toggle('is-mobile', v === 'mobile');
  $('#vtMobile').classList.toggle('active', v === 'mobile');
  $('#vtDesktop').classList.toggle('active', v !== 'mobile');
}
$('#vtMobile').onclick = () => setVista('mobile');
$('#vtDesktop').onclick = () => setVista('desktop');

// ---------- central: bandeja de aprobaciones ----------
function actualizarPendientes(n) {
  const b = $('#pendBadge');
  if (!b) return;
  n = n || 0;
  b.textContent = n;
  b.hidden = n === 0;
  const btn = $('#btnBandeja');
  if (btn) btn.classList.toggle('tiene-pend', n > 0);
}

async function refrescarPendientes() {
  if (!ES_CENTRAL) return;
  try { const c = await api('/api/config'); actualizarPendientes(c.pendientes); } catch (e) {}
}

function fechaLinda(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function resumenTexto(r) {
  if (!r || typeof r !== 'object') return '';
  const et = { modulos: 'módulos', promos_bancarias: 'Promos bancarias', promos_mensuales: 'Promos vigentes',
    entregas: 'Placas de envío', fechas_especiales: 'Fechas especiales', porque: '¿Por qué elegirnos?',
    competencia: 'Competencia', chatbot: 'Chatbot' };
  return Object.keys(r).map(k => `${et[k] || k}: ${r[k]}`).join(' · ');
}

async function abrirBandeja() {
  abrirModal($('#bandeja'));
  await renderBandeja();
}
function cerrarBandeja() { esconderModal($('#bandeja')); }

async function renderBandeja() {
  const cont = $('#bandejaList');
  cont.innerHTML = '<p class="muted">Cargando…</p>';
  let data;
  try { data = await api('/api/aprobaciones'); }
  catch (e) { cont.innerHTML = '<p class="muted">No se pudo cargar.</p>'; return; }
  const lista = (data.aprobaciones || []).filter(a => a.estado === 'pendiente');
  actualizarPendientes(lista.length);
  $('#bandejaHint').textContent = lista.length
    ? 'Aprobar aplica los cambios a tu copia. Después revisás y tocás “Publicar cambios”.'
    : '';
  if (!lista.length) {
    cont.innerHTML = '<div class="bandeja-empty"><p>No hay propuestas pendientes.</p>'
      + '<p class="muted">Cuando un colaborador te mande cambios, aparecen acá.</p></div>';
    return;
  }
  cont.innerHTML = '';
  for (const p of lista) {
    const card = document.createElement('div');
    card.className = 'aprob-card';
    card.innerHTML = `
      <div class="aprob-top">
        <div>
          <div class="aprob-quien">${esc(p.usuario || 'Colaborador')}
            <span class="aprob-pc">${esc(p.pc || '')}</span></div>
          <div class="aprob-fecha">${esc(fechaLinda(p.fecha))}</div>
        </div>
      </div>
      ${p.mensaje ? `<div class="aprob-msg">“${esc(p.mensaje)}”</div>` : ''}
      <div class="aprob-resumen">${esc(resumenTexto(p.resumen))}</div>
      <div class="aprob-diff muted" data-diff>Comparando con tu versión…</div>
      <div class="aprob-acts">
        <button class="btn btn-ghost" data-rechazar>Rechazar</button>
        <button class="btn active" data-aprobar>Aprobar y aplicar</button>
      </div>`;
    cont.appendChild(card);
    // diff async
    api('/api/aprobacion?id=' + encodeURIComponent(p.id)).then(det => {
      const el = card.querySelector('[data-diff]');
      if (det.error) { el.textContent = det.error; return; }
      const n = det.nuevos.length, m = det.modificados.length, b = det.borrados.length;
      if (!n && !m && !b) { el.textContent = 'Sin diferencias con tu versión actual.'; return; }
      el.innerHTML = `<b>Cambios:</b> ${n} nueva(s) · ${m} modificada(s) · ${b} quitada(s)`;
    }).catch(() => {});
    card.querySelector('[data-aprobar]').onclick = () => aprobar(p);
    card.querySelector('[data-rechazar]').onclick = () => rechazar(p);
  }
}

async function aprobar(p) {
  if (!await confirmar(`Se aplicarán los cambios de ${p.usuario || 'el colaborador'} a tu copia. Después los revisás y publicás. ¿Aprobar?`, 'Sí, aplicar', 'Aprobar propuesta')) return;
  try {
    const r = await api('/api/aprobar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: p.id })
    });
    if (r.ok) {
      toast('✓ Aplicado. Revisá y tocá “Publicar cambios”.', 'ok');
      await renderBandeja();
      await cargarModulos();
      refrescarGit();
    } else toast(r.error || 'No se pudo aplicar', 'err');
  } catch (e) { toast(e.message, 'err'); }
}

async function rechazar(p) {
  if (!await confirmar(`¿Rechazar y descartar la propuesta de ${p.usuario || 'el colaborador'}? No se puede deshacer.`, 'Sí, rechazar', 'Rechazar propuesta')) return;
  try {
    const r = await api('/api/rechazar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: p.id })
    });
    if (r.ok) { toast('Propuesta rechazada'); await renderBandeja(); }
    else toast(r.error || 'No se pudo rechazar', 'err');
  } catch (e) { toast(e.message, 'err'); }
}

$('#btnBandeja').onclick = abrirBandeja;
$('#bandejaClose').onclick = cerrarBandeja;
$('#bandejaOv').onclick = cerrarBandeja;
$('#bandejaRefresh').onclick = renderBandeja;

// ---------- auto-actualizacion del panel (todos los roles) ----------
/* el modal "Actualizando el panel" (maqueta): pasos que se van tildando */
const ICO_PASO = {
  falta: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/></svg>',
  ahora: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 6 9 17l-5-5"/></svg>'
};
function updPaso(nombre, estado) {
  const p = document.querySelector('#updPasos [data-paso="' + nombre + '"]');
  if (!p) return;
  p.classList.remove('ok', 'ahora');
  if (estado !== 'falta') p.classList.add(estado);
  const s = p.querySelector('svg');
  if (s) s.outerHTML = ICO_PASO[estado] || ICO_PASO.falta;
}
function updProgreso(pct) {
  const f = $('#updProgFill'); if (f) f.style.width = pct + '%';
  const t = $('#updProgPct'); if (t) t.textContent = pct + '%';
}
async function chequearActualizacion() {
  let st;
  try { st = await api('/api/update-status'); } catch (e) { return; }
  if (!st || !st.disponible) return;
  const bar = $('#updateBar'); if (!bar) return;
  const txt = bar.querySelector('.update-txt');
  const btn = $('#btnUpdate');
  const setTxt = html => { if (txt) txt.innerHTML = html; };
  setTxt('<b>Hay una versión nueva del panel.</b> ' + esc(st.label || ('versión ' + st.version)));
  bar.hidden = false;
  let enCurso = false;
  btn.onclick = async () => {
    if (enCurso) return;                       // anti doble-submit (sincrono, antes del await)
    enCurso = true; btn.disabled = true;
    if (!await confirmar('El panel se va a actualizar y reiniciar solo en unos segundos. Guardá lo que estés editando antes de seguir.', 'Actualizar ahora', 'Actualizar el panel')) {
      enCurso = false; btn.disabled = false; return;
    }
    bar.classList.add('aplicando');
    setTxt('<b>Descargando y aplicando…</b> no cierres la ventana, el panel se reinicia solo.');
    // el modal de progreso de la maqueta
    const mUpd = $('#mActualizando');
    if (mUpd) {
      const v = $('#updProgVer');
      if (v) v.textContent = st.label || ('Versión ' + st.version);
      updPaso('bajar', 'ahora'); updPaso('verificar', 'falta');
      updPaso('instalar', 'falta'); updPaso('reabrir', 'falta');
      updProgreso(12);
      abrirModal(mUpd);
    }
    try {
      const r = await api('/api/update-apply', { method: 'POST' });
      if (r && r.aplicando) {
        btn.hidden = true;
        updPaso('bajar', 'ok'); updPaso('verificar', 'ok'); updPaso('instalar', 'ahora');
        updProgreso(58);
        setTxt('<b>Actualizando…</b> el panel se va a reiniciar solo. Esperá unos segundos.');
        esperarReinicio();
      } else {
        if (mUpd) esconderModal(mUpd);
        bar.classList.remove('aplicando'); btn.disabled = false; enCurso = false;
        setTxt('<b>No se pudo actualizar.</b> ' + esc((r && r.error) || ''));
        toast((r && r.error) || 'No se pudo actualizar', 'err');
      }
    } catch (e) {
      // el POST responde ANTES de salir; si el fetch falla, es un error real -> reintentar
      if (mUpd) esconderModal(mUpd);
      bar.classList.remove('aplicando'); btn.disabled = false; btn.hidden = false; enCurso = false;
      setTxt('<b>No se pudo iniciar la actualización.</b> Probá de nuevo.');
      toast('No se pudo iniciar la actualización', 'err');
    }
  };
}

// espera a que el panel se reinicie (server cae y vuelve) y recarga la version nueva
function esperarReinicio() {
  let cayo = false, intentos = 0;
  const t = setInterval(async () => {
    intentos++;
    try {
      await api('/api/config');
      if (cayo) {   // volvio -> cargar la version nueva
        clearInterval(t);
        updPaso('reabrir', 'ok'); updProgreso(100);
        location.reload();
      }
    } catch (e) {
      if (!cayo) { updPaso('instalar', 'ok'); updPaso('reabrir', 'ahora'); updProgreso(84); }
      cayo = true;                                          // se esta reiniciando
    }
    if (intentos > 40) clearInterval(t);                   // ~80s: dejar de insistir
  }, 2000);
}

// ---------- arranque ----------
cargarConfig().finally(() => {
  cargarModulos().catch(e => toast('No se pudo conectar con el panel: ' + e.message, 'err'));
  refrescarGit();
  chequearActualizacion();
  // la central revisa cada 20 s si llegaron propuestas nuevas
  setInterval(refrescarPendientes, 20000);
});

/* ===================================================================
   KIT DE RECUPERACIÓN
   Genera UN archivo .html autocontenido y cifrado con la info necesaria
   para retomar el control del sistema si esta computadora se pierde.
   Se abre con doble clic en cualquier navegador: no necesita el panel,
   ni internet, ni instalar nada.
   El cifrado lo hace el navegador (WebCrypto: PBKDF2-SHA256 + AES-GCM),
   así la contraseña nunca sale de acá ni queda guardada en ningún lado.
   =================================================================== */
const KIT_ITERACIONES = 250000;

function kitB64(buf) {
  let s = '';
  new Uint8Array(buf).forEach(b => { s += String.fromCharCode(b); });
  return btoa(s);
}

async function kitCifrar(texto, clave) {
  const cod = new TextEncoder();
  const sal = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const base = await crypto.subtle.importKey('raw', cod.encode(clave), 'PBKDF2', false, ['deriveKey']);
  const k = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: sal, iterations: KIT_ITERACIONES, hash: 'SHA-256' },
    base, { name: 'AES-GCM', length: 256 }, false, ['encrypt']);
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, k, cod.encode(texto));
  return { sal: kitB64(sal), iv: kitB64(iv), ct: kitB64(ct), iter: KIT_ITERACIONES };
}

/* El visor que se descarga. Se arma como lista de líneas (sin backticks
   adentro) para que el JavaScript del visor no se mezcle con el de acá. */
function kitVisorHTML(paquete, fecha) {
  const datos = JSON.stringify(paquete).replace(/</g, '\\u003c');
  const cierreScript = '<' + '/script>';
  return [
    '<!doctype html><html lang="es"><head><meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Kit de recuperación - Muebles y Sillones</title><style>',
    'body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#F7F5F1;color:#2C2A26;',
    'margin:0;padding:28px 18px;line-height:1.5}',
    '.caja{max-width:820px;margin:0 auto;background:#fff;border:1px solid #E4DFD6;border-radius:16px;padding:26px 28px}',
    'h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:26px 0 8px;color:#5A5348}',
    '.sub{color:#6E6E6E;font-size:13px;margin:0 0 20px}',
    'input{font:inherit;padding:10px 12px;border:1px solid #E4DFD6;border-radius:9px;width:240px}',
    'button{font:inherit;padding:10px 18px;border:0;border-radius:9px;background:#2C2A26;color:#fff;cursor:pointer}',
    '.err{color:#B5503F;font-size:13px;margin-top:10px;min-height:18px}',
    '.dato{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid #F0EDE7;font-size:14px;flex-wrap:wrap}',
    '.dato b{min-width:170px;color:#5A5348;font-weight:600}',
    '.dato span{font-family:ui-monospace,Consolas,monospace;word-break:break-all}',
    '.serv{border:1px solid #E4DFD6;border-radius:11px;padding:13px 15px;margin-bottom:10px}',
    '.serv h3{margin:0 0 5px;font-size:14px}.serv p{margin:3px 0;font-size:13px;color:#4A463F}',
    '.serv p b{color:#2C2A26}',
    'ol{padding-left:20px;font-size:14px}ol li{margin:6px 0}',
    '.aviso{background:#FBF0EC;border:1px solid #E6C9C3;border-radius:11px;padding:13px 15px;margin-top:18px;font-size:13.5px}',
    '.aviso li{margin:5px 0}.oculto{display:none}',
    '</style></head><body><div class="caja">',
    '<h1>Kit de recuperación</h1>',
    '<p class="sub">Intranet de vendedores &middot; Muebles y Sillones &middot; generado el ', fecha, '</p>',
    '<div id="login"><p>Escribí la contraseña con la que se generó este archivo.</p>',
    '<input type="password" id="p" autofocus> <button id="b">Abrir</button>',
    '<div class="err" id="e"></div></div>',
    '<div id="cont" class="oculto"></div></div>',
    '<script>var PAQ=', datos, ';',
    'function d(b){var s=atob(b),a=new Uint8Array(s.length);for(var i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a;}',
    'function fila(k,v){var x=document.createElement("div");x.className="dato";',
    'var b=document.createElement("b");b.textContent=k;var s=document.createElement("span");s.textContent=v;',
    'x.appendChild(b);x.appendChild(s);return x;}',
    'function h2(t){var e=document.createElement("h2");e.textContent=t;return e;}',
    'async function abrir(){',
    ' var e=document.getElementById("e");e.textContent="Descifrando...";',
    ' try{',
    '  var cod=new TextEncoder();',
    '  var base=await crypto.subtle.importKey("raw",cod.encode(document.getElementById("p").value),"PBKDF2",false,["deriveKey"]);',
    '  var k=await crypto.subtle.deriveKey({name:"PBKDF2",salt:d(PAQ.sal),iterations:PAQ.iter,hash:"SHA-256"},',
    '    base,{name:"AES-GCM",length:256},false,["decrypt"]);',
    '  var pt=await crypto.subtle.decrypt({name:"AES-GCM",iv:d(PAQ.iv)},k,d(PAQ.ct));',
    '  pintar(JSON.parse(new TextDecoder().decode(pt)));',
    ' }catch(x){e.textContent="Esa contraseña no es la correcta.";}',
    '}',
    'function pintar(K){',
    ' document.getElementById("login").className="oculto";',
    ' var c=document.getElementById("cont");c.className="";',
    ' c.appendChild(h2("Datos del sistema"));',
    ' [["Repositorio",K.sitio],["Rama",K.repo.rama],["Cerebro (publicador)",K.cerebro_url],',
    '  ["Clave de publicación",K.publish_token||"(sin clave cargada)"],',
    '  ["Carpeta del proyecto",K.proyecto],["Computadora",K.pc+" ("+K.rol+")"],',
    '  ["Versión del panel",String(K.version_panel)]].forEach(function(f){c.appendChild(fila(f[0],f[1]));});',
    ' c.appendChild(h2("Cuentas: qué desbloquea cada una"));',
    ' K.servicios.forEach(function(s){var x=document.createElement("div");x.className="serv";',
    '  var t=document.createElement("h3");t.textContent=s.nombre;x.appendChild(t);',
    '  [["Qué es",s.que_es],["Desbloquea",s.desbloquea],["Dónde está",s.donde],',
    '   ["Si lo perdés",s.si_lo_perdes]].forEach(function(p){',
    '    var e=document.createElement("p");var b=document.createElement("b");b.textContent=p[0]+": ";',
    '    e.appendChild(b);e.appendChild(document.createTextNode(p[1]));x.appendChild(e);});',
    '  c.appendChild(x);});',
    ' c.appendChild(h2("Cómo retomar el control, paso a paso"));',
    ' var ol=document.createElement("ol");',
    ' K.pasos.forEach(function(p){var li=document.createElement("li");',
    '  li.textContent=p.replace(/^\\d+\\.\\s*/,"").replace("<CEREBRO>",K.cerebro_url);ol.appendChild(li);});',
    ' c.appendChild(ol);',
    ' var av=document.createElement("div");av.className="aviso";',
    ' var t=document.createElement("b");t.textContent="Importante";av.appendChild(t);',
    ' var ul=document.createElement("ul");',
    ' K.avisos.forEach(function(a){var li=document.createElement("li");li.textContent=a;ul.appendChild(li);});',
    ' av.appendChild(ul);c.appendChild(av);',
    '}',
    'document.getElementById("b").onclick=abrir;',
    'document.getElementById("p").addEventListener("keydown",function(ev){if(ev.key==="Enter")abrir();});',
    cierreScript, '</body></html>',
  ].join('');
}

/* Una clave ARMADA por el panel: cuatro palabras y un número. Es tan fuerte como
   una de caracteres sueltos pero se puede dictar por teléfono o pasar por chat
   sin equivocarse, que es lo que hace falta para mandársela a un desarrollador. */
const KIT_PALABRAS = ('sillon,roble,lino,puerta,lampara,mesa,cuero,nogal,tela,marco,vidrio,piedra,' +
  'cobre,arena,hilo,pino,bronce,cedro,algodon,mimbre,laton,junco,fresno,yute,olmo,caoba,rafia,' +
  'terciopelo,pana,lana,seda,tierra,brisa,rio,monte,valle,costa,sierra,pampa,delta').split(',');

function kitClaveNueva() {
  const al = n => crypto.getRandomValues(new Uint32Array(1))[0] % n;
  const p = [];
  while (p.length < 4) {
    const w = KIT_PALABRAS[al(KIT_PALABRAS.length)];
    if (!p.includes(w)) p.push(w);
  }
  return p.join('-') + '-' + (10 + al(90));
}

(function initKit() {
  const modal = $('#kitModal'); if (!modal) return;
  const abrir = () => {
    $('#kitPass').value = kitClaveNueva();
    $('#kitAviso').textContent = '';
    abrirModal(modal);
    $('#kitPass').select();
  };
  $('#kitOtra').onclick = () => { $('#kitPass').value = kitClaveNueva(); $('#kitPass').select(); };
  $('#kitCopiar').onclick = async () => {
    const av = $('#kitAviso');
    try {
      await navigator.clipboard.writeText($('#kitPass').value);
      av.style.color = 'var(--ok)'; av.textContent = 'Clave copiada. Guardala junto con el archivo.';
    } catch (e) {
      $('#kitPass').select();
      av.style.color = 'var(--ink3)'; av.textContent = 'Copiala a mano (Ctrl+C): ya te la dejé seleccionada.';
    }
  };
  const cerrar = () => { esconderModal(modal); };
  const btn = $('#btnKit'); if (btn) btn.onclick = abrir;
  modal.querySelectorAll('[data-cerrar-kit]').forEach(b => { b.onclick = cerrar; });

  $('#kitGenerar').onclick = async () => {
    const av = $('#kitAviso');
    const p1 = $('#kitPass').value.trim();
    av.style.color = 'var(--danger)';
    if (p1.length < 8) { av.textContent = 'La clave tiene que tener al menos 8 caracteres.'; return; }
    av.style.color = 'var(--ink3)'; av.textContent = 'Generando…';
    try {
      const kit = await api('/api/kit-recuperacion', { method: 'POST' });
      const paquete = await kitCifrar(JSON.stringify(kit), p1);
      const html = kitVisorHTML(paquete, kit.generado);
      const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Kit de recuperacion MyS - ' + kit.generado.slice(0, 10).replace(/\//g, '-') + '.html';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      cerrar();
      toast('Kit generado. Guardalo en dos lugares distintos.', 'ok');
    } catch (e) {
      av.style.color = 'var(--danger)';
      av.textContent = e.message || 'No se pudo generar el kit.';
    }
  };
})();

/* ===================================================================
   MÉTRICAS — VISTA PREVIA
   Cómo está funcionando la intranet: qué se lee, qué se descarga, qué se
   busca y quién no confirmó lo obligatorio.
   Los números son de EJEMPLO. Lo real necesita base de datos: hoy la
   intranet es un sitio estático y no registra nada de lo que pasa.
   Lo que sí sale del contenido de verdad son los títulos, las fechas y
   los tipos de publicación.
   =================================================================== */
const MET_SUCURSALES = ['Hudson', 'CABA', 'Canning', 'Norcenter'];

/* números estables: la misma publicación da siempre lo mismo, así la
   pantalla no "baila" cada vez que se abre */
function metSemilla(txt) {
  let n = 0;
  for (let i = 0; i < String(txt).length; i++) n = (n * 31 + String(txt).charCodeAt(i)) % 100000;
  return n;
}
function metEntre(txt, min, max) {
  return min + (metSemilla(txt) % (max - min + 1));
}

function publicacionesDelMuro() {
  const mods = MODULOS || [];
  const muro = mods.find(m => esCartelera(m.content) && !m.hidden);
  if (!muro) return [];
  return (muro.content.docs || []).filter(d => !d.archivado);
}

function abrirMetricas() {
  document.querySelectorAll('.lienzo > .main').forEach(v => {
    if (v.id !== 'viewMetricas') v.hidden = true;
  });
  $('#viewDetalle').hidden = true;
  $('#viewMetricas').hidden = false;
  window.scrollTo(0, 0);
  renderMetricas();
}
function cerrarMetricas() {
  $('#viewMetricas').hidden = true;
  if (typeof irASeccion === 'function') irASeccion('modulos');
  else $('#viewModulos').hidden = false;
}

function renderMetricas() {
  const posts = publicacionesDelMuro();
  const vendedores = 14;                       // ejemplo

  $('#metAviso').innerHTML = `<span style="font-size:17px">⚠️</span>
    <span><b>Esto es una vista previa: los números son de ejemplo.</b><br>
    Los títulos, las fechas y los tipos SÍ son los de verdad. Para medir lo que pasa
    (quién abre, quién confirma, qué se descarga) hace falta conectar la base de datos:
    hoy la intranet es una página que no registra nada.</span>`;

  if (!posts.length) {
    $('#metBody').innerHTML = `<div class="met-sec"><div class="met-h">Todavía no hay un muro</div>
      <p class="met-sub">Creá un módulo de tipo <b>Muro</b> y publicá algo; acá vas a ver cómo funciona.</p></div>`;
    return;
  }

  /* --- KPIs --- */
  const delMes = posts.filter(p => (p.fecha || '').slice(0, 7) === hoyISO().slice(0, 7)).length;
  const obligatorias = posts.filter(p => p.confirmar);
  const lecturaProm = Math.round(posts.reduce((s, p) => s + metEntre(p.id + 'l', 45, 96), 0) / posts.length);
  const descargas = posts.reduce((s, p) => s + metEntre(p.id + 'd', 0, 40), 0);

  const kpis = [
    ['Publicaciones este mes', delMes, posts.length + ' en total'],
    ['Leen las publicaciones', lecturaProm + '%', 'promedio del equipo', lecturaProm >= 70 ? 'sube' : 'baja'],
    ['Placas descargadas', descargas, 'en los últimos 30 días'],
    ['Vendedores activos', metEntre('act', 9, vendedores) + ' de ' + vendedores, 'entraron esta semana'],
  ];

  /* --- tabla de publicaciones --- */
  const filas = posts.slice(0, 10).map(p => {
    const vistas = metEntre(p.id + 'v', 5, vendedores);
    const pct = Math.round(vistas / vendedores * 100);
    const conf = p.confirmar ? metEntre(p.id + 'c', 3, vistas) : null;
    return `<tr>
      <td><div class="met-tit">${esc(p.titulo || 'Sin título')}</div>
          <div class="met-meta">${esc(fechaCorta(p.fecha))}${NOMBRE_TIPO[p.etiqueta] ? ' · ' + NOMBRE_TIPO[p.etiqueta] : ''}${p.confirmar ? ' · pide confirmación' : ''}</div></td>
      <td style="width:150px"><div class="met-barra${pct < 60 ? ' flojo' : ''}"><span style="width:${pct}%"></span></div></td>
      <td class="met-pct" style="width:90px">${vistas}/${vendedores} la vieron</td>
      <td style="width:150px">${conf === null ? '<span class="met-meta">—</span>'
        : (conf >= vendedores ? '<span class="met-chip bien">todos confirmaron</span>'
           : `<span class="met-chip mal">faltan ${vendedores - conf}</span>`)}</td>
    </tr>`;
  }).join('');

  /* --- quién no confirmó --- */
  const pendiente = obligatorias[0];
  const faltantes = pendiente ? MET_SUCURSALES.map(s => ({
    s, faltan: metEntre(pendiente.id + s, 0, 3)
  })).filter(x => x.faltan) : [];

  /* --- lo más buscado / descargado (del contenido real) --- */
  const buscado = ['cuotas', 'plazo de entrega', 'garantía', 'promo bancaria', 'derivación', 'embalaje']
    .map(t => ({ t, n: metEntre('b' + t, 8, 90) })).sort((a, b) => b.n - a.n);
  const NOMBRE_SECCION = {
    fechas_especiales: 'Fechas especiales', promos_bancarias: 'Promociones bancarias',
    promos_mensuales: 'Promociones vigentes', entregas: 'Placas de envío', porque: '¿Por qué elegirnos?'
  };
  const placas = GRUPOS_DESCARGABLES.map(k => NOMBRE_SECCION[k] || k)
    .map(t => ({ t, n: metEntre('p' + t, 5, 60) })).sort((a, b) => b.n - a.n);

  $('#metBody').innerHTML = `
    <div class="met-kpis">${kpis.map(k => `<div class="met-k">
      <div class="met-kt">${esc(k[0])}</div><div class="met-kv">${esc(String(k[1]))}</div>
      <div class="met-kd${k[3] ? ' ' + k[3] : ''}">${esc(k[2])}</div></div>`).join('')}</div>

    <div class="met-sec">
      <div class="met-h">Publicación por publicación</div>
      <p class="met-sub">Cuántos vendedores la abrieron y, en las obligatorias, cuántos confirmaron.</p>
      <table class="met-tabla"><thead><tr>
        <th>Publicación</th><th>Alcance</th><th></th><th>Confirmaciones</th>
      </tr></thead><tbody>${filas}</tbody></table>
    </div>

    ${pendiente ? `<div class="met-sec">
      <div class="met-h">Quién no confirmó todavía</div>
      <p class="met-sub">De “${esc(pendiente.titulo || '')}”. Con la base conectada, acá va el nombre de cada uno y un botón para recordárselo.</p>
      ${faltantes.length ? `<ul class="met-lista">${faltantes.map(f => `<li>
          <span class="n">${f.faltan}</span> ${esc(f.s)}
          <span class="v">${f.faltan === 1 ? 'falta 1' : 'faltan ' + f.faltan}</span></li>`).join('')}</ul>`
        : `<p class="met-sub" style="margin:0">Confirmaron todos. 👏</p>`}
    </div>` : ''}

    <div class="met-cols">
      <div class="met-sec">
        <div class="met-h">Lo que más buscan</div>
        <p class="met-sub">Sirve para saber qué material falta o está escondido.</p>
        <ul class="met-lista">${buscado.map((x, i) => `<li><span class="n">${i + 1}</span>
          ${esc(x.t)}<span class="v">${x.n}</span></li>`).join('')}</ul>
      </div>
      <div class="met-sec">
        <div class="met-h">Lo que más descargan</div>
        <p class="met-sub">Qué placas están usando de verdad con los clientes.</p>
        <ul class="met-lista">${placas.map((x, i) => `<li><span class="n">${i + 1}</span>
          ${esc(x.t)}<span class="v">${x.n}</span></li>`).join('')}</ul>
      </div>
    </div>`;
}
$('#btnMetricas').onclick = abrirMetricas;
$('#metVolver').onclick = cerrarMetricas;
