/* ===================================================================
   SECCIÓN MURO + NAVEGACIÓN DEL PANEL REDISEÑADO
   Se carga DESPUÉS de app.js y usa su motor: MODULOS, det, openDetalle,
   renderDetalle, abrirDoc, persistModulos, confirmar, toast…
   Acá no hay lógica de contenido: solo la cáscara nueva y las acciones
   rápidas sobre las publicaciones (fijar, ocultar, duplicar, borrar).
   =================================================================== */
(function () {
  'use strict';

  const SECS = ['muro', 'modulos', 'datos', 'metricas', 'archivadas'];
  let SEC = 'muro';
  let FILTRO = 'todas';

  /* ---------------- navegación ---------------- */
  function vistaDe(sec) {
    return document.getElementById(
      sec === 'muro' ? 'viewMuro' :
      sec === 'modulos' ? 'viewModulos' :
      sec === 'datos' ? 'viewDatos' :
      sec === 'archivadas' ? 'viewArch' : 'viewMetricas');
  }
  function irASeccion(sec) {
    if (SECS.indexOf(sec) < 0) sec = 'muro';
    /* Con el menú a la vista mientras se edita, tocar una sección tiene que
       SALIR del editor primero — por la puerta de siempre, que pregunta si
       hay cambios sin guardar. Al cerrar, volverASeccion() trae hasta acá. */
    const ed = document.getElementById('viewDetalle');
    if (ed && !ed.hidden) {
      SEC = sec;
      const back = document.getElementById('detBack');
      if (back) back.click();
      return;
    }
    SEC = sec;
    SECS.forEach(s => { const v = vistaDe(s); if (v) v.hidden = s !== sec; });
    document.querySelectorAll('#navSecs .item').forEach(b =>
      b.classList.toggle('on', b.dataset.sec === sec));
    if (sec === 'muro') renderMuro();
    if (sec === 'modulos') pintarModulos();
    if (sec === 'archivadas') pintarArchivadas();
    /* Datos se pinta al ENTRAR, venga por click o por código: sin esto la
       pantalla quedaba vacía si el enganche por click no llegaba a correr. */
    if (sec === 'datos' && typeof window.refrescarDatos === 'function') window.refrescarDatos();
    /* Métricas es la vista previa de la maqueta: estática, no se pinta. */
    /* Datos NO se pinta desde aca: lo hace datos_puente.js, que va a buscar la
       planilla al servidor. Leerla al entrar al panel seria una espera que
       nadie pidio, asi que se carga recien la primera vez que se entra. */
    window.scrollTo(0, 0);
  }
  window.irASeccion = irASeccion;
  /* al cerrar el editor se vuelve a la sección donde estabas */
  window.volverASeccion = () => irASeccion(SEC);

  document.getElementById('navSecs').addEventListener('click', e => {
    const h = e.target.closest('.grupo > h4');
    if (h) { h.parentElement.classList.toggle('cerrado'); return; }
    const b = e.target.closest('.item'); if (b) irASeccion(b.dataset.sec);
  });
  /* buscar del sidebar: lleva al buscador global (que vive en Módulos) */
  const navB = document.getElementById('navBuscar');
  if (navB) navB.onclick = () => {
    irASeccion('modulos');
    const q = document.getElementById('buscarTodo');
    if (q) setTimeout(() => q.focus(), 60);
  };

  /* ---------------- datos ---------------- */
  const TIPOS = {
    anuncio: { t: 'Anuncio', c: '#1A4A8A' }, promo: { t: 'Promoción', c: '#8A5A2C' },
    capacitacion: { t: 'Capacitación', c: '#255C74' }, logro: { t: 'Logro', c: '#1A6A3A' },
    importante: { t: 'Importante', c: '#B4231F' }, equipo: { t: 'Equipo', c: '#5A554D' }
  };
  /* tiene que coincidir con DIAS_PAPELERA de panel_server.py, que es quien
     realmente aplica el plazo al guardar. Acá es solo para lo que se muestra. */
  const DIAS_PAPELERA = 15;

  function idxMuro() { return (MODULOS || []).findIndex(m => esCartelera(m.content)); }
  function moduloMuro() { const i = idxMuro(); return i < 0 ? null : MODULOS[i]; }
  /* lo que sigue vivo en la papelera: el servidor purga al guardar, pero entre
     guardado y guardado hay que filtrar acá o se muestran vencidas */
  function enPapelera() {
    const m = moduloMuro();
    const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
    return ((m && m.content.papelera) || []).filter(function (d) {
      const q = diasEnPapelera(d);
      return q !== null && q < DIAS_PAPELERA;
    });
  }

  /* cuántos días lleva tirada. Fecha LOCAL: con toISOString(), de noche en
     Argentina el UTC ya es el día siguiente y la cuenta se corre un día. */
  function diasEnPapelera(d) {
    const t = String((d && d.borradoEl) || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return 0;
    const p = t.split('-');
    const cuando = new Date(+p[0], +p[1] - 1, +p[2]);
    const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
    return Math.floor((hoy - cuando) / 86400000);
  }

  function postsDelMuro() {
    const m = moduloMuro();
    return (m && m.content && m.content.docs) ? m.content.docs : [];
  }
  /* mismo criterio que la intranet: fijadas primero, después por fecha */
  function ordenados(docs) {
    return docs.map((d, i) => ({ d, i })).sort((a, b) => {
      if (!!b.d.fijado !== !!a.d.fijado) return b.d.fijado ? 1 : -1;
      return String(b.d.fecha || '').localeCompare(String(a.d.fecha || ''));
    });
  }
  function estadoDe(d) {
    if (d.archivado) return 'oculta';
    const dv = d.vence ? diasHasta(d.vence) : null;
    if (dv !== null && dv < 0) return 'vencida';
    const df = d.fecha ? diasHasta(d.fecha) : null;
    if (df !== null && df > 0) return 'programada';
    return 'publicada';
  }
  const AV_COLORES = ['#E9E3D9', '#EFE9E0', '#E6E9E2', '#EDE6DC'];
  function colorAutor(n) {
    let s = 0; String(n || 'MyS').split('').forEach(c => { s = (s + c.charCodeAt(0)) % 997; });
    return AV_COLORES[s % AV_COLORES.length];
  }
  function iniciales(n) {
    return String(n || 'MyS').trim().split(/\s+/).slice(0, 2)
      .map(p => p.charAt(0).toUpperCase()).join('') || 'M';
  }
  function cuando(d) {
    const dias = d.fecha ? diasHasta(d.fecha) : null;
    if (dias === null) return 'sin fecha';
    if (dias === 0) return 'hoy';
    if (dias === 1) return 'mañana';
    if (dias > 1) return 'en ' + dias + ' días';
    if (dias === -1) return 'ayer';
    if (dias > -7) return 'hace ' + (-dias) + ' días';
    return fechaCorta(d.fecha);
  }

  /* ---------------- pintar ---------------- */
  const ICO = {
    editar: '<svg viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>',
    fijar: '<svg viewBox="0 0 24 24"><path d="M9 3h6l-1 6 4 3v2H6v-2l4-3z"/><line x1="12" y1="14" x2="12" y2="21"/></svg>',
    ojo: '<svg viewBox="0 0 24 24"><path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12z"/><circle cx="12" cy="12" r="3"/></svg>',
    ojoNo: '<svg viewBox="0 0 24 24"><path d="M17.9 17.9A10 10 0 0 1 12 19.5C5 19.5 1.5 12 1.5 12a18 18 0 0 1 5.1-6M9.9 5.7A10 10 0 0 1 12 5.5c7 0 10.5 6.5 10.5 6.5a18 18 0 0 1-2.7 3.9"/><line x1="2" y1="2" x2="22" y2="22"/></svg>',
    copiar: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
    borrar: '<svg viewBox="0 0 24 24"><path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/></svg>'
  };

  /* ------------------------- LA PAPELERA -------------------------
     Lo eliminado no se pierde: queda DIAS_PAPELERA días acá. Vive en
     content.papelera, aparte de content.docs, así la intranet no lo ve
     nunca — no hay riesgo de que un vendedor lea algo ya borrado. */
  function pintarPapelera(cont, lista) {
    cont.innerHTML = '';
    var aviso = document.createElement('div');
    aviso.className = 'pap-aviso';
    aviso.innerHTML = '<span class="pap-ic">' + ICO.borrar + '</span>' +
      '<span>Lo que borrás se guarda acá <b>' + DIAS_PAPELERA + ' días</b>. ' +
      'Después se va solo, sin vuelta atrás.</span>';
    cont.appendChild(aviso);

    lista.forEach(function (d, k) {
      var q = diasEnPapelera(d);
      var quedan = DIAS_PAPELERA - q;
      var el = document.createElement('article');
      el.className = 'mp en-papelera' + (quedan <= 3 ? ' urgente' : '');
      el.innerHTML =
        '<div class="mp-head">' +
          '<span class="mp-av" style="background:' + colorAutor(d.autor) + '">' +
            esc(iniciales(d.autor)) + '</span>' +
          '<span class="mp-quien"><span class="mp-autor">' +
            esc(d.autor || 'Muebles y Sillones') + '</span>' +
            '<span class="mp-meta">se publicó el ' + esc(fechaCorta(d.fecha) || '—') + '</span></span>' +
          '<span class="pap-plazo' + (quedan <= 3 ? ' urgente' : '') + '">' +
            (quedan <= 0 ? 'se va hoy' : quedan === 1 ? 'queda 1 día' : 'quedan ' + quedan + ' días') +
          '</span>' +
        '</div>' +
        '<div class="mp-tit">' + esc(d.titulo || 'Sin título') + '</div>' +
        '<div class="pap-acts">' +
          '<button type="button" class="btn btn-ghost" data-p="restaurar">Restaurar</button>' +
          '<button type="button" class="btn-txt del" data-p="siempre">Eliminar definitivamente</button>' +
        '</div>';
      el.querySelector('[data-p="restaurar"]').onclick = function () { restaurar(k); };
      el.querySelector('[data-p="siempre"]').onclick = function () { borrarParaSiempre(k, d); };
      cont.appendChild(el);
    });
  }

  /* el índice llega de la lista VIVA, que puede no coincidir con la guardada
     si alguna ya venció: se busca por id para no restaurar la equivocada */
  function indiceReal(k) {
    var mod = moduloMuro(); if (!mod) return -1;
    var viva = enPapelera()[k];
    if (!viva) return -1;
    var todas = mod.content.papelera || [];
    for (var i = 0; i < todas.length; i++) {
      if (todas[i] === viva) return i;
      if (todas[i].id && viva.id && todas[i].id === viva.id) return i;
    }
    return -1;
  }

  async function restaurar(k) {
    var mod = moduloMuro(); if (!mod) return;
    var i = indiceReal(k); if (i < 0) return;
    var d = mod.content.papelera[i];
    var vuelve = JSON.parse(JSON.stringify(d));
    delete vuelve.borradoEl;
    mod.content.docs = mod.content.docs || [];
    mod.content.docs.unshift(vuelve);
    /* mismo cuidado que en duplicar: restaurar mete una publicacion arriba
       de todo y corre los indices */
    if (COMP.editando !== null && COMP.editando !== undefined) COMP.editando++;
    mod.content.papelera.splice(i, 1);
    await persistModulos(false);
    if (!enPapelera().length) FILTRO = 'todas';   /* vacía: no dejar la pantalla en blanco */
    refrescarVista();
    pintarContadores();
    toast('Volvió a la cartelera. Fijate la fecha, porque entró arriba de todo.', 'ok');
  }

  async function borrarParaSiempre(k, d) {
    var mod = moduloMuro(); if (!mod) return;
    var ok = await confirmar('“' + (d.titulo || 'sin título') + '” se borra para siempre. ' +
      'Esta vez sí que no hay vuelta atrás.', 'Borrar para siempre', 'Borrar definitivamente');
    if (!ok) return;
    var i = indiceReal(k); if (i < 0) return;
    mod.content.papelera.splice(i, 1);
    await persistModulos(false);
    if (!enPapelera().length) FILTRO = 'todas';
    refrescarVista();
    pintarContadores();
    toast('Borrada para siempre.', 'ok');
  }

  /* según dónde estés parado, se repinta la lista que corresponde */
  function refrescarVista() {
    if (SEC === 'archivadas') pintarArchivadas();
    else renderMuro();
  }

  /* ===================================================================
     VISTA ARCHIVADAS (maqueta): lo que salió de la cartelera.
     Arriba las archivadas (se pueden volver a publicar); abajo, si hay,
     la papelera con su cuenta regresiva.
     =================================================================== */
  function miniDe(d) {
    var src = '';
    (d.bloques || []).some(function (bk) {
      if (!bk) return false;
      if (bk.t === 'imagen' && bk.src) { src = bk.src; return true; }
      if (bk.t === 'galeria') {
        var it = (bk.items || []).filter(function (x) { return x && x.src; })[0];
        if (it) { src = it.src; return true; }
      }
      if (bk.t === 'video' && bk.poster) { src = bk.poster; return true; }
      return false;
    });
    return src
      ? '<span class="mini-ph"><img src="/intranet/' + esc(src) + '" alt="" loading="lazy"></span>'
      : '<span class="mini-ph"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 7h16M4 12h12M4 17h8"/></svg></span>';
  }

  function archCard(d, meta, botones) {
    var tipo = TIPOS[d.etiqueta];
    var el = document.createElement('div');
    el.className = 'card arch';
    el.innerHTML = miniDe(d) +
      '<span class="t"><b>' + esc(d.titulo || 'Sin título') + '</b>' +
      '<span class="meta">' + (tipo ? '<i style="background:' + tipo.c + '"></i>' + esc(tipo.t) + ' · ' : '') +
      esc(meta) + '</span></span>' +
      '<span class="bts">' + botones + '</span>';
    return el;
  }

  function pintarArchivadas() {
    var cont = document.getElementById('archLista');
    var sub = document.getElementById('archSub');
    if (!cont) return;
    cont.innerHTML = '';
    var mod = moduloMuro();
    var q = (document.getElementById('archBuscar').value || '').trim().toLowerCase();
    var docs = mod ? (mod.content.docs || []) : [];
    var ocultas = docs.map(function (d, i) { return { d: d, i: i }; })
      .filter(function (x) { return estadoDe(x.d) === 'oculta'; })
      .filter(function (x) {
        return !q || ((x.d.titulo || '') + ' ' + (x.d.autor || '')).toLowerCase().includes(q);
      });
    var tacho = enPapelera().filter(function (d) {
      return !q || ((d.titulo || '') + ' ' + (d.autor || '')).toLowerCase().includes(q);
    });

    if (sub) {
      var n = ocultas.length;
      sub.textContent = (n === 1 ? '1 publicación fuera de la cartelera' :
        n + ' publicaciones fuera de la cartelera') + ' · nadie las ve';
    }

    ocultas.forEach(function (x) {
      var d = x.d, i = x.i;
      var el = archCard(d,
        'Archivada' + (d.autor ? ' · por ' + d.autor : ''),
        '<button type="button" class="btn btn-2" data-a="volver"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg> Volver a publicar</button>' +
        '<button type="button" class="btn btn-3" data-a="tirar" title="Mandar a la papelera"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg></button>');
      el.querySelector('[data-a="volver"]').onclick = async function () {
        d.archivado = false;
        d.fecha = hoyISO();   /* vuelve arriba de todo, con la fecha de hoy */
        await persistModulos(false);
        refrescarVista(); pintarContadores();
        toast('Volvió a la cartelera, arriba de todo.', 'ok');
      };
      el.querySelector('[data-a="tirar"]').onclick = function () { accionPost('borrar', i, el); };
      cont.appendChild(el);
    });

    if (!ocultas.length && !tacho.length) {
      cont.innerHTML = '<div class="card vacio">' +
        '<span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg></span>' +
        '<h3>' + (q ? 'No encontré nada con eso' : 'No hay nada archivado') + '</h3>' +
        '<p>' + (q ? 'Probá con otra palabra.' : 'Cuando archives una publicación desde la cartelera, va a aparecer acá.') + '</p></div>';
      return;
    }

    if (tacho.length) {
      var kick = document.createElement('div');
      kick.className = 'mp-grupo';
      kick.textContent = 'Papelera';
      cont.appendChild(kick);
      var aviso = document.createElement('div');
      aviso.className = 'aviso-caja';
      aviso.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>' +
        '<span><b>Lo que borrás se guarda ' + DIAS_PAPELERA + ' días</b>' +
        '<span>Después se va solo, sin vuelta atrás.</span></span>';
      cont.appendChild(aviso);
      tacho.forEach(function (d, k) {
        var quedan = DIAS_PAPELERA - diasEnPapelera(d);
        var el = archCard(d,
          (quedan <= 0 ? 'Se va hoy' : quedan === 1 ? 'Queda 1 día' : 'Quedan ' + quedan + ' días') +
          (d.autor ? ' · por ' + d.autor : ''),
          '<button type="button" class="btn btn-2" data-a="rest"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg> Restaurar</button>' +
          '<button type="button" class="btn btn-3 btn-del" data-a="def" title="Eliminar definitivamente"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M18 6 6 18M6 6l12 12"/></svg></button>');
        if (quedan <= 3) el.classList.add('urgente');
        el.querySelector('[data-a="rest"]').onclick = function () { restaurar(k); };
        el.querySelector('[data-a="def"]').onclick = function () { borrarParaSiempre(k, d); };
        cont.appendChild(el);
      });
    }
  }
  var archB = document.getElementById('archBuscar');
  if (archB) archB.addEventListener('input', pintarArchivadas);


  /* ===================================================================
     VISTA REAL — cada publicación se ve como la ve el vendedor
     No se copia el maquetado de la intranet a mano: se le PIDE su hoja de
     estilos y se la mete en un shadow root. Dos ventajas sobre copiar:
       · nunca se desincroniza — es literalmente el mismo CSS;
       · queda aislada, no se filtra ni una regla al panel.
     Lo único que se replica acá es la estructura del <article>, que cambia
     mucho menos seguido que los estilos.
     =================================================================== */
  var CSS_INTRANET = null;      // se pide una sola vez
  var CSS_PIDIENDO = null;

  /* La hoja de la intranet, tal cual. Se pide UNA vez y se guarda cruda,
     porque las dos vistas la necesitan distinta: el shadow root quiere :host
     y el iframe quiere :root. */
  function hojaCruda() {
    if (CSS_INTRANET !== null) return Promise.resolve(CSS_INTRANET);
    if (CSS_PIDIENDO) return CSS_PIDIENDO;
    /* ⚠️ ACOPLAMIENTO CON EL SITIO — leer antes de tocar intranet/index.html
       Esta vista previa es el sitio de verdad: para dibujarlo necesita la MISMA
       hoja de estilos que se publica. Durante mucho tiempo el CSS vivía adentro
       de un <style> en index.html y acá se lo recortaba con indexOf.

       El 30-ago-2026 ese CSS se sacó a css/sistema.css + css/sitio.css, y el
       recorte pasó a devolver cadena vacía: la vista previa quedó sin estilos y
       las publicaciones se veían como HTML pelado. No hubo ningún error en
       consola, porque el `: ''` de abajo se lo tragaba en silencio.

       Ahora se leen los <link> declarados en el propio index.html, así que si
       mañana los archivos cambian de nombre o se agrega uno, esto sigue
       andando sin tocarlo. El <style> inline queda como respaldo. */
    CSS_PIDIENDO = fetch('/intranet/index.html')
      .then(function (r) { return r.text(); })
      .then(function (t) {
        var hojas = [];
        var re = /<link[^>]+rel=["']stylesheet["'][^>]*>/gi, m;
        while ((m = re.exec(t))) {
          var href = (m[0].match(/href=["']([^"']+)["']/) || [])[1] || '';
          /* solo las propias: las de Google Fonts no hacen falta acá y
             además tardan */
          if (href && !/^https?:/i.test(href)) hojas.push(href);
        }
        if (!hojas.length) {                       // respaldo: el <style> viejo
          var a = t.indexOf('<style>'), b = t.indexOf('</style>');
          return (a >= 0 && b > a) ? t.slice(a + 7, b) : '';
        }
        return Promise.all(hojas.map(function (h) {
          var url = h.charAt(0) === '/' ? h : '/intranet/' + h;
          return fetch(url).then(function (r) {
            if (!r.ok) throw new Error(url + ' -> ' + r.status);
            return r.text();
          });
        })).then(function (partes) { return partes.join('\n'); });
      })
      .then(function (css) {
        /* las rutas son relativas a /intranet/, no a la raíz del panel */
        css = css.replace(/url\((['"]?)assets\//g, 'url($1/intranet/assets/');
        css = css.replace(/url\((['"]?)\.\.\/assets\//g, 'url($1/intranet/assets/');
        if (!css) console.warn('[muro] la vista previa se quedó sin CSS del sitio');
        CSS_INTRANET = css;
        return css;
      })
      .catch(function (e) {
        /* antes esto moría mudo y la falla se veía recién en pantalla */
        console.warn('[muro] no pude traer el CSS del sitio:', e);
        CSS_INTRANET = ''; return '';
      });
    return CSS_PIDIENDO;
  }
  /* :root no existe adentro de un shadow root: las variables van al host */
  function estiloIntranet() {
    return hojaCruda().then(function (c) { return c.replace(/:root\b/g, ':host'); });
  }

  /* el mismo arreglo para el html de la publicación */
  function rutasAbsolutas(html) {
    return String(html || '')
      .replace(/(src|href)=(["'])assets\//g, '$1=$2/intranet/assets/');
  }

  var AV_INTRA = ['--c-hudson', '--c-caba', '--c-canning', '--c-norcenter'];
  function colorAutorIntra(n) {
    var t = String(n || '').trim() || 'MyS', h = 0;
    for (var i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) >>> 0;
    return AV_INTRA[h % AV_INTRA.length];
  }

  function fechaLindaIntra(f) {
    var d = deISO(f);
    if (!d) return 'Publicado';
    var hoy = hoyLocal();
    var q = Math.round((hoy - d) / 86400000);
    if (q <= 0) return 'hoy';
    if (q === 1) return 'ayer';
    if (q < 7) return 'hace ' + q + ' días';
    return d.getDate() + ' ' + MESES[d.getMonth()].slice(0, 3) + ' ' + d.getFullYear();
  }

  /* La misma estructura que arma la intranet en postHTML(). Si allá cambia,
     hay que tocar acá — por eso se replica lo MÍNIMO: el resto lo pone el CSS. */
  function articuloComoVendedor(d) {
    var tipo = TIPOS[d.etiqueta];
    var marcas = tipo
      ? '<span class="mu-marcas"><span class="mu-tag" style="background:' +
        'rgba(0,0,0,.06);color:' + tipo.c + '">' + esc(tipo.t) + '</span></span>'
      : '';
    return '<article class="mu-post">' +
      (d.fijado ? '<div class="mu-fijado">FIJADO</div>' : '') +
      '<div class="mu-head">' +
        '<span class="mu-av" style="background:var(' + colorAutorIntra(d.autor) + ')">' +
          esc(iniciales(d.autor)) + '</span>' +
        '<span class="mu-quien"><span class="mu-autor">' +
          esc(d.autor || 'Muebles y Sillones') + '</span>' +
        '<span class="mu-meta">' +
          [d.sucursal, fechaLindaIntra(d.fecha)].filter(Boolean).map(esc)
            .join('<span class="mu-sep">·</span>') + '</span></span>' +
        marcas +
      '</div>' +
      (d.titulo ? '<div class="mu-titulo">' + esc(d.titulo) + '</div>' : '') +
      '<div class="mu-cuerpo"><div class="manual">' + rutasAbsolutas(d.html) + '</div></div>' +
      '</article>';
  }

  /* Monta la vista adentro de un shadow root. Devuelve el host. */
  /* ══════════════════ CÓMO SE VE: ESCRITORIO O CELULAR ══════════════════
     El 90% del uso pasa en un teléfono y hasta acá se publicaba mirando una
     caja de 684px. La vista de celular NO puede ser la misma achicada: las
     media queries de la intranet se evalúan contra la ventana, así que una
     caja angosta adentro de una pantalla ancha sigue recibiendo el diseño de
     escritorio. Un <iframe> sí tiene viewport propio, y por eso a 390px de
     ancho aparece de verdad el diseño de celular. */
  var VISTA_MODO = 'escritorio';
  try { VISTA_MODO = localStorage.getItem('mp:modo') || 'escritorio'; } catch (e) {}

  function montarVistaCelular(d) {
    var caja = document.createElement('div');
    caja.className = 'mp-vista mp-cel';
    var fr = document.createElement('iframe');
    fr.className = 'mp-frame';
    fr.setAttribute('title', 'Así se ve en un celular');
    fr.setAttribute('scrolling', 'no');
    caja.appendChild(fr);
    hojaCruda().then(function (css) {
      fr.srcdoc = '<!doctype html><html><head><meta charset="utf-8">' +
        '<style>' + css +
        '\nhtml,body{ margin:0; padding:0; background:var(--bg); }' +
        '\n.mu-post{ margin:0 !important; }' +
        '\n.mu-cuerpo{ max-height:none !important; }' +
        '\n.mu-cuerpo::after{ display:none !important; }' +
        '</style></head><body>' + articuloComoVendedor(d) + '</body></html>';
      fr.onload = function () {
        try {
          var doc = fr.contentDocument;
          doc.querySelectorAll('video').forEach(function (v) {
            v.setAttribute('controls', '');
            v.muted = true; v.playsInline = true; v.preload = 'metadata';
            if (!/#t=/.test(v.src)) v.src = v.src + '#t=0.1';
          });
          /* el iframe no se estira solo: se le da el alto de su contenido */
          var alto = function () {
            fr.style.height = Math.max(140, doc.body.scrollHeight) + 'px';
          };
          alto();
          doc.querySelectorAll('img').forEach(function (im) {
            if (!im.complete) im.addEventListener('load', alto, { once: true });
          });
        } catch (e) {}
      };
    });
    return caja;
  }

  function montarComoSea(d) {
    return VISTA_MODO === 'celular' ? montarVistaCelular(d) : montarVista(d);
  }

  function pintarModoVista() {
    var caja = document.getElementById('mpModo');
    if (!caja) return;
    caja.querySelectorAll('[data-modo]').forEach(function (b) {
      b.classList.toggle('on', b.dataset.modo === VISTA_MODO);
      b.setAttribute('aria-pressed', b.dataset.modo === VISTA_MODO ? 'true' : 'false');
    });
  }

  function montarVista(d) {
    var host = document.createElement('div');
    host.className = 'mp-vista';
    var sh = host.attachShadow({ mode: 'open' });
    sh.innerHTML = '<div class="cargando"></div>';
    estiloIntranet().then(function (css) {
      sh.innerHTML = '<style>' + css +
        /* el feed vive adentro de una tarjeta del panel: sin margen propio y
           sin el recorte de "Ver publicación completa", que acá no aplica */
        '\n:host{ display:block; }' +
        '\n.mu-post{ margin:0 !important; border:0 !important; border-radius:0 !important; }' +
        '\n.mu-cuerpo{ max-height:none !important; }' +
        '\n.mu-cuerpo::after{ display:none !important; }' +
        '</style>' + articuloComoVendedor(d);
      /* Los videos de la vista previa arrancan mudos y quietos: son varios y
         no se trata de mirarlos todos, sino de revisar la publicación.
         Pero llevan controles: el que carga tiene que poder darle play y
         chequear que el video sea el que va. En la cartelera del vendedor no
         los llevan — ahí arrancan solos y se manejan con la barra propia. */
      sh.querySelectorAll('video').forEach(function (v) {
        v.setAttribute('controls', '');
        v.muted = true; v.playsInline = true; v.preload = 'metadata';
        if (!/#t=/.test(v.src)) v.src = v.src + '#t=0.1';
      });
    });
    return host;
  }

  /* La tarjeta de publicación de la maqueta: cabecera con autor/fecha/etiqueta,
     título, cuerpo, un solo MEDIO grande (foto, placas o video) y los demás
     archivos como tarjetas de adjunto. Las acciones viven al pie. */
  function adjCard(ic, titulo, sub, data) {
    var ICONO_ADJ = {
      descarga: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/>',
      video: '<path d="m22 8-6 4 6 4V8z"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
      pdf: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
      link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
      tabla: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>'
    };
    return '<div class="adj"' + (data || '') + '>' +
      '<span class="adj-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor">' +
      (ICONO_ADJ[ic] || ICONO_ADJ.link) + '</svg></span>' +
      '<span class="t"><b>' + esc(titulo) + '</b><span>' + esc(sub) + '</span></span>' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M7 17 17 7M8 7h9v9"/></svg></div>';
  }

  function contenidoFeed(d) {
    var cuerpo = [], medio = '', adjs = [];
    var bloques = Array.isArray(d.bloques) ? d.bloques : [];
    bloques.forEach(function (bk) {
      if (!bk || !bk.t) return;
      if (bk.t === 'parrafo') {
        var h = bk.html || escBr(bk.texto || '');
        if (txtOf(h)) cuerpo.push('<p>' + h + '</p>');
        return;
      }
      if (bk.t === 'lista') {
        var its = (bk.items || []).map(function (it) {
          var h2 = typeof it === 'string' ? it : ((it && (it.html || it.texto)) || '');
          return txtOf(h2) ? '<li><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 6 9 17l-5-5"/></svg><span>' + h2 + '</span></li>' : '';
        }).join('');
        if (its) cuerpo.push('<ul class="lista">' + its + '</ul>');
        return;
      }
      if (bk.t === 'galeria') {
        var fotos = (bk.items || []).filter(function (it) { return it && it.src; });
        if (!fotos.length) return;
        if (!medio) {
          if (fotos.length === 1) {
            medio = '<div class="medio"><img src="/intranet/' + esc(fotos[0].src) + '" alt="" loading="lazy"></div>';
          } else {
            medio = '<div class="medio grilla" data-n="' + Math.min(fotos.length, 3) + '">' +
              fotos.slice(0, 3).map(function (it) {
                return '<figure><img src="/intranet/' + esc(it.src) + '" alt="" loading="lazy"></figure>';
              }).join('') +
              '<span class="contador"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>' +
              fotos.length + (fotos.length === 1 ? ' placa' : ' placas') + '</span></div>';
          }
        } else {
          adjs.push(adjCard('descarga', bk.titulo || 'Galería',
            'Galería · ' + fotos.length + (fotos.length === 1 ? ' imagen' : ' imágenes')));
        }
        return;
      }
      if (bk.t === 'imagen' && bk.src) {
        if (!medio) medio = '<div class="medio"><img src="/intranet/' + esc(bk.src) + '" alt="" loading="lazy"></div>';
        else adjs.push(adjCard('descarga', bk.caption || bk.alt || 'Imagen', 'Imagen'));
        return;
      }
      if (bk.t === 'video' && (bk.src || bk.url)) {
        var nom = (bk.caption || bk.dlNombre || 'Video').trim() || 'Video';
        if (!medio) {
          medio = '<div class="medio">' +
            (bk.poster
              ? '<img src="/intranet/' + esc(bk.poster) + '" alt="" loading="lazy">'
              : (bk.src ? '<video src="/intranet/' + esc(bk.src) + '" preload="metadata" muted playsinline></video>' : '')) +
            '<span class="play"><svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M6 4l14 8-14 8z"/></svg></span></div>';
        } else {
          adjs.push(adjCard('video', nom, bk.src ? 'Video · MP4' : 'Video · link'));
        }
        return;
      }
      if (bk.t === 'pdf' && (bk.src || bk.nombre)) {
        adjs.push(adjCard('pdf', bk.nombre || 'Documento', 'PDF' + (bk.descargable ? ' · descarga directa' : ''),
          bk.src ? ' data-pdf="' + esc(bk.src) + '"' : ''));
        return;
      }
      if (bk.t === 'ref') {
        var mRef = (MODULOS || []).filter(function (m) { return m.key === bk.mod; })[0];
        var tRef = mRef ? (mRef.title || bk.mod) : (bk.mod || 'Módulo');
        var subRef = (bk.sub || '').trim();
        if (subRef.toLowerCase() === String(tRef).toLowerCase()) subRef = '';
        adjs.push(adjCard('link', tRef + (subRef ? ' · ' + subRef : ''),
          'Módulo de la intranet', ' data-ref="' + esc(bk.mod || '') + '"'));
        return;
      }
      if (bk.t === 'tabla' && (bk.titulo || '').trim()) {
        adjs.push(adjCard('tabla', bk.titulo, 'Tabla · se ve completa en la intranet'));
      }
    });
    /* publicación cargada con el cuerpo ya armado (sin bloques) */
    if (!bloques.length && (d.html || '').trim()) {
      cuerpo.push('<div class="html-libre">' + d.html + '</div>');
    }
    return { cuerpo: cuerpo.join(''), medio: medio, adjs: adjs.join('') };
  }

  function tarjetaPost(d, i) {
    const est = estadoDe(d);
    const tipo = TIPOS[d.etiqueta];
    const dias = d.fecha ? diasHasta(d.fecha) : null;
    const esNueva = est === 'publicada' && dias !== null && dias >= -1;

    /* la línea de tiempo dice el estado, sin chips aparte */
    var cuandoTx;
    if (est === 'programada') cuandoTx = 'Sale ' + cuando(d);
    else if (est === 'vencida') cuandoTx = 'Ya no se ve' + (d.vence ? ' · venció el ' + fechaCorta(d.vence) : '');
    else if (est === 'oculta') cuandoTx = 'Archivada';
    else {
      cuandoTx = cuando(d).charAt(0).toUpperCase() + cuando(d).slice(1);
      if (d.vence) {
        const q = diasHasta(d.vence);
        if (q !== null && q >= 0) cuandoTx += q === 0 ? ' · último día' : (q <= 7 ? ' · vence en ' + q + ' días' : ' · hasta el ' + fechaCorta(d.vence));
      }
      if (d.confirmar) cuandoTx += ' · pide confirmación';
    }

    const c = contenidoFeed(d);
    const el = document.createElement('article');
    el.className = 'card pub' + (est === 'vencida' ? ' pub-vencida' : '') + (est === 'oculta' ? ' pub-oculta' : '');
    el.dataset.i = i;
    el.innerHTML = `
      <div class="pub-cab">
        <span class="av">${esc(iniciales(d.autor))}</span>
        <span class="quien"><b>${esc(d.autor || 'Muebles y Sillones')}</b><time>${esc(cuandoTx)}</time></span>
        ${esNueva ? '<span class="nuevo">NUEVO</span>' : ''}
        ${tipo ? '<span class="marca-etq"><i style="background:' + tipo.c + '"></i>' + esc(tipo.t) + '</span>' : ''}
      </div>
      <h3>${esc(d.titulo || 'Sin título')}</h3>
      ${c.cuerpo ? '<div class="cuerpo">' + c.cuerpo + '</div>' : ''}
      ${c.medio}
      ${c.adjs}
      <div class="acc">
        <button type="button" data-a="compartir"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.5 8.5 0 0 1-3.8-.9L3 21l2-5.2A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z"/></svg>Compartir</button>
        <button type="button" data-a="abrir"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M7 17 17 7M8 7h9v9"/></svg>Abrir</button>
        <button type="button" class="sep" data-a="editar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>Editar</button>
        <button type="button" class="solo mp-mas" data-a="menu" aria-haspopup="true" aria-expanded="false" title="Más opciones" aria-label="Más opciones"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg></button>
      </div>`;
    el.addEventListener('click', ev => {
      const mas = ev.target.closest('.mp-mas');
      if (mas) { ev.stopPropagation(); abrirMenuPost(mas, d, i, el); return; }
      const b = ev.target.closest('[data-a]');
      if (b) {
        ev.stopPropagation();
        const a = b.dataset.a;
        if (a === 'editar') return accionPost('editar', i, el);
        /* el link que sirve fuera de esta compu: el sitio online. Si por lo que
           sea no hay direccion publica, cae al preview local. */
        const urlPub = (window.WEB_PUBLICA || location.origin) +
          '/intranet/#cartelera/' + encodeURIComponent(d.id || '');
        if (a === 'abrir') return window.open(urlPub, '_blank');
        if (a === 'compartir') {
          try {
            navigator.clipboard.writeText(urlPub);
            toast('Link copiado. Se lo podés mandar a cualquier vendedor.', 'ok');
          } catch (e) { toast('No pude copiar el link', 'err'); }
          return;
        }
      }
      const adjRef = ev.target.closest('.adj[data-ref]');
      if (adjRef) {
        const idx2 = (MODULOS || []).findIndex(m => m.key === adjRef.dataset.ref);
        if (idx2 >= 0) { openDetalle(idx2); }
        return;
      }
      const adjPdf = ev.target.closest('.adj[data-pdf]');
      if (adjPdf) { window.open('/intranet/' + adjPdf.dataset.pdf, '_blank'); return; }
    });
    return el;
  }

  /* ------- el menú de los tres puntitos -------
     Antes eran cinco íconos siempre a la vista, arriba de cada publicación.
     Ahora hay un solo ⋯ y las acciones viven adentro, con su nombre escrito:
     un tacho y un ojo sueltos no dicen qué hacen hasta que los tocás. */
  function cerrarMenuPost() {
    var m = document.getElementById('mpMenu');
    if (m) m.remove();
    document.querySelectorAll('.mp-mas[aria-expanded="true"]')
      .forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
  }

  function abrirMenuPost(boton, d, i, el) {
    var abierto = boton.getAttribute('aria-expanded') === 'true';
    cerrarMenuPost();
    if (abierto) return;                 /* segundo toque: cierra */
    boton.setAttribute('aria-expanded', 'true');

    var opciones = [
      { a: 'editar', t: 'Editar', ic: ICO.editar },
      { a: 'fijar', t: d.fijado ? 'Dejar de fijar' : 'Fijar arriba', ic: ICO.fijar },
      { a: 'ocultar', t: d.archivado ? 'Volver a mostrarla' : 'Archivar',
        ic: d.archivado ? ICO.ojoNo : ICO.ojo },
      { a: 'duplicar', t: 'Duplicar', ic: ICO.copiar },
      { a: 'borrar', t: 'Eliminar', ic: ICO.borrar, peligro: true },
    ];
    var m = document.createElement('div');
    m.className = 'mp-menu'; m.id = 'mpMenu';
    m.innerHTML = opciones.map(function (o) {
      return '<button type="button" class="mp-mi' + (o.peligro ? ' del' : '') +
        '" data-a="' + o.a + '"><span class="mi-ic">' + o.ic + '</span>' + o.t + '</button>';
    }).join('');
    document.body.appendChild(m);

    /* se posiciona pegado al botón, y si no entra abajo se abre hacia arriba */
    var r = boton.getBoundingClientRect();
    var alto = m.offsetHeight, ancho = m.offsetWidth;
    var arriba = (r.bottom + alto + 10 > window.innerHeight) && (r.top - alto - 6 > 0);
    m.style.top = (arriba ? r.top - alto - 6 : r.bottom + 6) + 'px';
    m.style.left = Math.max(8, Math.min(r.right - ancho, window.innerWidth - ancho - 8)) + 'px';
    if (arriba) m.classList.add('hacia-arriba');

    m.querySelectorAll('.mp-mi').forEach(function (b) {
      b.onclick = function (ev) {
        ev.stopPropagation();
        cerrarMenuPost();
        accionPost(b.dataset.a, i, el);
      };
    });
  }

  document.addEventListener('click', function (e) {
    if (!e.target.closest('#mpMenu') && !e.target.closest('.mp-mas')) cerrarMenuPost();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    /* este handler corre ANTES que el del compositor, así que deja una marca:
       si no, al cerrar el menú el compositor creía que no había nada abierto
       y se cerraba él también, llevándose el borrador */
    if (document.getElementById('mpMenu')) e.__capaCerrada = true;
    cerrarMenuPost();
  });
  window.addEventListener('scroll', cerrarMenuPost, true);

  /* -------- el aside de la maqueta: estado + etiquetas (que filtran) -------- */
  function pintarAside(cuenta, porEtiqueta) {
    var est = document.getElementById('asideEstado');
    if (est) {
      var pend = (typeof editados !== 'undefined' && editados) ? editados.size : 0;
      est.innerHTML =
        '<div class="dato"><span>A la vista</span><b>' + cuenta.vivas + '</b></div>' +
        '<div class="dato"><span>Fijadas arriba</span><b>' + cuenta.fijadas + '</b></div>' +
        '<div class="dato"><span>Archivadas</span><b>' + cuenta.ocultas + '</b></div>' +
        '<div class="dato"><span>Sin publicar</span><b>' + pend + '</b></div>';
    }
    var caja = document.getElementById('asideEtiquetas');
    if (caja) {
      caja.innerHTML = Object.keys(TIPOS).map(function (k) {
        var v = TIPOS[k];
        var on = FILTRO === 'etq:' + k;
        return '<button type="button" data-etq="' + k + '"' + (on ? ' class="on"' : '') +
          '><i style="background:' + v.c + '"></i>' + v.t +
          '<span class="n">' + (porEtiqueta[k] || 0) + '</span></button>';
      }).join('');
      caja.querySelectorAll('button').forEach(function (b) {
        b.onclick = function () {
          var f = 'etq:' + b.dataset.etq;
          FILTRO = (FILTRO === f) ? 'todas' : f;
          renderMuro();
        };
      });
    }
  }

  function renderMuro() {
    const mod = moduloMuro();
    const cont = document.getElementById('muroLista');
    const sub = document.getElementById('muroSub');
    document.getElementById('compAv').textContent = iniciales('Marketing');

    if (!mod) {
      cont.innerHTML = `<div class="card vacio">
        <span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/></svg></span>
        <h3>Todavía no hay una cartelera</h3>
        <p>La cartelera es la portada de la intranet: lo primero que ven los vendedores al entrar.</p>
        <div class="bts"><button type="button" class="btn btn-1" id="crearMuro">Crear la cartelera</button></div></div>`;
      document.getElementById('crearMuro').onclick = crearMuro;
      sub.textContent = 'Todavía no está creada.';
      pintarAside({ vivas: 0, fijadas: 0, ocultas: 0 }, {});
      return;
    }

    const docs = postsDelMuro();
    const q = (document.getElementById('muroBuscar').value || '').trim().toLowerCase();
    const cuenta = { todas: 0, programadas: 0, fijadas: 0, vencidas: 0, ocultas: 0 };
    const porEtiqueta = {};
    docs.forEach(d => {
      const e = estadoDe(d);
      cuenta.todas++;
      if (e === 'programada') cuenta.programadas++;
      if (e === 'vencida') cuenta.vencidas++;
      if (e === 'oculta') cuenta.ocultas++;
      if (d.fijado && e !== 'oculta') cuenta.fijadas++;
      if (d.etiqueta && e !== 'oculta' && e !== 'vencida')
        porEtiqueta[d.etiqueta] = (porEtiqueta[d.etiqueta] || 0) + 1;
    });
    cuenta.vivas = cuenta.todas - cuenta.ocultas - cuenta.vencidas;

    /* el subtítulo de la maqueta: cuántas a la vista y cuándo fue la última */
    var masNueva = '';
    docs.forEach(d => {
      if (estadoDe(d) !== 'publicada') return;
      if (!masNueva || String(d.fecha || '') > masNueva) masNueva = String(d.fecha || '');
    });
    sub.textContent = cuenta.vivas + ' a la vista' +
      (masNueva ? ' · última ' + cuando({ fecha: masNueva }) : '');

    pintarAside(cuenta, porEtiqueta);

    cont.innerHTML = '';
    let listados = ordenados(docs).filter(({ d }) => {
      const e = estadoDe(d);
      if (FILTRO.indexOf('etq:') === 0) {
        if (d.etiqueta !== FILTRO.slice(4)) return false;
        if (e === 'oculta') return false;
      } else {
        if (FILTRO === 'programadas' && e !== 'programada') return false;
        if (FILTRO === 'vencidas' && e !== 'vencida') return false;
        if (FILTRO === 'ocultas' && e !== 'oculta') return false;
        if (FILTRO === 'fijadas' && !(d.fijado && e !== 'oculta')) return false;
        if (FILTRO === 'todas' && e === 'oculta') return false;   /* lo oculto no ensucia */
      }
      if (q && !((d.titulo || '') + ' ' + (d.autor || '') + ' ' + txtOf(d.html || ''))
        .toLowerCase().includes(q)) return false;
      return true;
    });

    if (!listados.length) {
      cont.innerHTML = `<div class="card vacio">
        <span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg></span>
        <h3>${q ? 'No encontré nada con eso' : 'Nada por acá'}</h3>
        <p>${q ? 'Probá con otra palabra.' : 'Cuando publiques algo, va a aparecer en esta lista.'}</p></div>`;
      return;
    }
    let grupoPuesto = '';
    listados.forEach(({ d, i }) => {
      const e = estadoDe(d);
      const g = d.fijado && e !== 'oculta' ? 'Fijadas arriba' : e === 'programada' ? 'Programadas' : 'Publicaciones';
      if (FILTRO === 'todas' && g !== grupoPuesto) {
        grupoPuesto = g;
        if (grupoPuesto !== 'Publicaciones' || cuenta.fijadas || cuenta.programadas) {
          const h = document.createElement('div');
          h.className = 'mp-grupo'; h.textContent = g;
          cont.appendChild(h);
        }
      }
      cont.appendChild(tarjetaPost(d, i));
    });
  }
  window.renderMuro = renderMuro;

  document.getElementById('muroBuscar').addEventListener('input', renderMuro);
  var btnNueva = document.getElementById('btnNuevaPub');
  if (btnNueva) btnNueva.onclick = function () { abrirComp(''); };

  /* ---------------- acciones rápidas ---------------- */
  async function accionPost(a, i, el) {
    const mod = moduloMuro(); if (!mod) return;
    const docs = mod.content.docs;
    const d = docs[i]; if (!d) return;
    if (a === 'editar') return editarPublicacion(i);
    if (a === 'fijar') { d.fijado = !d.fijado; }
    else if (a === 'ocultar') { d.archivado = !d.archivado; }
    else if (a === 'duplicar') {
      const copia = JSON.parse(JSON.stringify(d));
      copia.id = nuevoId();
      copia.titulo = (d.titulo || 'Publicación') + ' (copia)';
      copia.fecha = hoyISO();
      copia.fijado = false;
      docs.unshift(copia);
      /* ⚠️ unshift corre TODOS los indices un lugar. Si el compositor esta
         abierto editando, su COMP.editando apunta ahora a otra publicacion y
         al guardar la pisaria entera. Ya estaba contemplado en 'borrar'; esto
         faltaba. */
      if (COMP.editando !== null && COMP.editando !== undefined) COMP.editando++;
    } else if (a === 'borrar') {
      const ok = await confirmar('“' + (d.titulo || 'sin título') + '” deja de verse ya mismo. ' +
        'Queda ' + DIAS_PAPELERA + ' días en la papelera por si fue sin querer.',
        'Eliminar', 'Eliminar publicación');
      if (!ok) return;
      const alTacho = JSON.parse(JSON.stringify(d));
      alTacho.borradoEl = hoyISO();
      mod.content.papelera = mod.content.papelera || [];
      mod.content.papelera.unshift(alTacho);
      docs.splice(i, 1);
      /* si estabas corrigiendo justo esa, el compositor queda apuntando a un
         índice que ya no existe: se cierra antes de que guarde sobre otra */
      if (COMP.editando === i) cerrarComp();
      else if (COMP.editando !== null && COMP.editando > i) COMP.editando--;
    }
    await persistModulos(false);
    refrescarVista();
    pintarContadores();
    toast(a === 'borrar' ? 'Fue a la papelera. Tenés ' + DIAS_PAPELERA + ' días para recuperarla.' :
          a === 'duplicar' ? 'Copia creada. Editala y publicá.' :
          a === 'fijar' ? (d.fijado ? 'Fijada arriba de todo.' : 'Ya no está fijada.') :
          (d.archivado ? 'Los vendedores dejan de verla.' : 'Vuelve a verse.'), 'ok');
  }

  /* ---------------- abrir el editor ---------------- */
  /* El texto que se muestra en el textarea.
     ⚠️ Ojo con el orden: `bk.html` manda sobre `bk.texto`, igual que en
     bloqueHTML(). Al revés, un párrafo editado después en el editor completo
     (que deja los dos campos) volvía a su versión vieja al abrirlo acá. */
  function textoPlano(bk) {
    if (bk.html) {
      return String(bk.html)
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/p>\s*<p[^>]*>/gi, '\n\n')
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
        .trim();
    }
    return bk.texto || '';
  }

  /* la cabecera y el boton cambian segun se este creando o corrigiendo */
  function marcarModo() {
    var editando = COMP.editando !== null && COMP.editando !== undefined;
    /* "Guardar y publicar" y no "Guardar cambios": el botón sube al sitio, y
       un rótulo que solo dice "guardar" hace pensar que queda en la máquina
       —que es justo lo que pasaba antes de verdad—. */
    var rot = document.querySelector('#coPublicar [data-rotulo]');
    if (rot) rot.textContent = editando ? 'Guardar y publicar' : 'Publicar';
    else elCo('coPublicar').textContent = editando ? 'Guardar y publicar' : 'Publicar';
    var tit = document.getElementById('compTitulo');
    if (tit) tit.textContent = editando ? 'Editar publicación' : 'Crear publicación';
    elCo('coCuando').textContent = editando ? 'editando una publicación' : 'Hoy';
    document.getElementById('composer').classList.toggle('editando', editando);
  }

  /* ------- el modal del compositor (armazón de la maqueta) -------
     La ventana nace en la posición de la card y crece: se lee como que la
     card se estiró y se levantó, en vez de aparecer de la nada. */
  function abrirModalComp() {
    var f = document.getElementById('fondo');
    var card = document.getElementById('composer');
    var modal = f.querySelector('.modal');
    if (card && modal && !sinMovimiento() && !document.getElementById('viewMuro').hidden) {
      var c = card.getBoundingClientRect();
      var dy = Math.round((c.top + c.height / 2) - window.innerHeight / 2);
      modal.style.setProperty('--nace', Math.max(-260, Math.min(260, dy)) + 'px');
    }
    f.classList.add('on');
    document.body.classList.add('trabado');
  }
  function cerrarModalComp() {
    var f = document.getElementById('fondo');
    f.classList.remove('on');
    if (!document.querySelector('.fondo.on')) document.body.classList.remove('trabado');
  }

  /* los interruptores del modal reflejan las casillas reales del motor */
  function pintarSwitches() {
    [['coFijarBtn', 'coFijar'], ['coConfirmarBtn', 'coConfirmar'], ['coArchivarBtn', 'coArchivar']]
      .forEach(function (p) {
        var b = document.getElementById(p[0]), c = elCo(p[1]);
        if (b && c) b.setAttribute('aria-pressed', c.checked ? 'true' : 'false');
      });
  }
  [['coFijarBtn', 'coFijar'], ['coConfirmarBtn', 'coConfirmar'], ['coArchivarBtn', 'coArchivar']]
    .forEach(function (p) {
      var b = document.getElementById(p[0]);
      if (!b) return;
      b.onclick = function () {
        var c = elCo(p[1]);
        c.checked = !c.checked;
        c.dispatchEvent(new Event('change'));
        pintarSwitches();
      };
    });

  /* Editar SIN salir del muro. Antes esto abria el editor de modulos entero.

     ⚠️ El peligro: una publicacion que llego con el `html` ya armado y SIN
     `bloques` (las que se cargaron a mano, o desde afuera del panel) no se
     puede representar acá. Si la abrimos igual, al guardar se regeneraria el
     html desde una lista de bloques vacia y la publicacion quedaria EN BLANCO.
     Es el mismo patron que borro Marzo-Mayo. Por eso esas van al editor de
     siempre, avisando. */
  async function editarPublicacion(i) {
    var idx = idxMuro(); if (idx < 0) return;
    var d = (MODULOS[idx].content.docs || [])[i];
    if (!d) return;

    var tieneBloques = Array.isArray(d.bloques) && d.bloques.length;
    if (!tieneBloques && (d.html || '').trim()) {
      var seguir = await confirmar(
        'Esta publicación se cargó con el cuerpo ya armado, así que no se puede ' +
        'corregir en la caja de acá arriba. Se abre el editor completo, que sí ' +
        'la respeta tal cual está.',
        'Abrir el editor', 'Necesita el editor completo', 'ok');
      if (!seguir) return;
      openDetalle(idx);
      mostrarDetalle(true);
      await esperar(function () { return Array.isArray(window.COLECCION) || COLECCION; });
      abrirDoc(i);
      return;
    }

    var bloques = (d.bloques || []).map(function (bk) {
      return JSON.parse(JSON.stringify(bk));      /* copia: cancelar no debe tocar nada */
    });
    var texto = '';
    COMP.parrafo0 = null; COMP.texto0 = '';
    if (bloques.length && bloques[0].t === 'parrafo') {
      var pr = bloques.shift();
      texto = textoPlano(pr);
      /* ⚠️ El compositor escribe en un textarea, que no sabe de negritas ni de
         links. Se guarda el bloque ENTERO: si al final el texto quedó igual, se
         devuelve tal cual y el formato sobrevive. Antes se reescribía siempre
         como texto pelado y una publicación con una palabra en negrita perdía
         el formato por venir a corregirle una coma. */
      COMP.parrafo0 = pr;
      COMP.texto0 = texto;
    }

    COMP.abierto = true;
    COMP.editando = i;
    COMP.tipo = d.etiqueta || '';
    COMP.bloques = bloques;
    abrirModalComp();
    elCo('coTitulo').value = d.titulo || '';
    elCo('coTexto').value = texto;
    elCo('coFijar').checked = !!d.fijado;
    elCo('coConfirmar').checked = !!d.confirmar;
    elCo('coVence').value = d.vence || '';
    /* corrigiendo, lo que ya eligió quien publicó manda: nada de que la
       propuesta automática le cambie el módulo por abrir a arreglar una coma */
    COMP.archTocado = true;
    pintarArchivar();
    var puedeIr = !!d.archivar && (MODULOS || []).some(function (m) {
      return m.key === d.archivar && puedeArchivar(m);
    });
    elCo('coArchivar').checked = puedeIr;
    if (puedeIr) elCo('coArchivarMod').value = d.archivar;
    pintarArchEstado();
    marcarModo();
    pintarVence();
    pintarTipos();
    pintarAdjuntos();
    pintarSwitches();
    setTimeout(function () { elCo('coTitulo').focus(); }, 260);
  }
  async function nuevaPublicacion(tipo) {
    const idx = idxMuro();
    if (idx < 0) return crearMuro(tipo);
    openDetalle(idx);
    mostrarDetalle(true);
    await esperar(() => COLECCION);
    document.getElementById('colAdd').click();       // crea y abre una en blanco
    await esperar(() => !document.getElementById('docBar').hidden);
    if (tipo) {
      const sel = document.getElementById('docTipo');
      sel.value = tipo; sel.dispatchEvent(new Event('change'));
    }
    document.getElementById('docTitulo').focus();
  }
  /* espera a que el motor de app.js termine de armar la pantalla */
  function esperar(cond, ms) {
    return new Promise(res => {
      const t0 = Date.now();
      (function ver() {
        let ok = false;
        try { ok = !!cond(); } catch (e) { ok = false; }
        if (ok || Date.now() - t0 > (ms || 2500)) return res();
        setTimeout(ver, 40);
      })();
    });
  }

  async function crearMuro(tipo) {
    const ok = await confirmar('Se crea un módulo nuevo llamado “Muro”, que pasa a ser la portada ' +
      'de la intranet: lo primero que ven los vendedores al entrar.', 'Crear el muro', 'Crear el muro', 'ok');
    if (!ok) return;
    MODULOS.unshift({
      key: '', title: 'Cartelera', desc: 'Todo lo nuevo del equipo, en un solo lugar',
      icon: 'megaphone', color: '--c-hudson', ready: true,
      content: { tipo: 'cartelera', docs: [] }
    });
    await persistModulos(false);
    renderMuro();
    nuevaPublicacion(tipo);
  }

  document.getElementById('compAbrir').onclick = () => abrirComp('');
  document.querySelectorAll('.comp-at').forEach(b =>
    b.onclick = () => abrirComp(b.dataset.tipo));


  /* ===================================================================
     COMPOSITOR EN LÍNEA
     Antes, publicar te sacaba del muro: openDetalle() + mostrarDetalle()
     te metían en el editor de módulos entero y desde ahí se simulaban
     clicks. Funcionaba, pero se sentía como editar un módulo, no como
     publicar un aviso. Ahora la caja crece acá mismo.

     El muro es un TABLERO DE AVISOS: lo simple se escribe acá; lo grande
     vive en un módulo y la publicación lo SEÑALA (bloque 'ref').
     =================================================================== */
  /* archTocado: si quien publica toca la casilla o cambia de módulo, la
     propuesta automática deja de meterse. */
  const COMP = { abierto: false, tipo: '', bloques: [], editando: null, archTocado: false,
                 parrafo0: null, texto0: '' };

  function elCo(id) { return document.getElementById(id); }

  /* ═══════════════ ARCHIVAR LA PUBLICACIÓN EN UN MÓDULO ═══════════════
     Un aviso importante tiene dos vidas: hoy, arriba de la cartelera, y
     después, cuando alguien lo va a buscar tres semanas más tarde. Antes eso
     se resolvía escribiendo lo mismo dos veces. Ahora la publicación deja
     anotado a qué módulo pertenece y el módulo la muestra.
     NO se copia nada: la publicación sigue siendo una sola. Por eso
     corregirla o borrarla se ve en los dos lados sin sincronizar nada.
     ═══════════════════════════════════════════════════════════════════ */
  /* Quedan afuera la cartelera (sería archivarse dentro de sí misma), los
     informes embebidos y las presentaciones: meter un aviso suelto ahí rompe
     la navegación con flechas. */
  function puedeArchivar(m) {
    if (!m || !m.key) return false;
    var c = m.content || {};
    if (esCartelera(c)) return false;
    if (c.tipo === 'embed') return false;
    if (c.tipo === 'bloques' && c.presentacion) return false;
    return true;
  }
  function modulosArchivables() { return (MODULOS || []).filter(puedeArchivar); }

  function pintarArchivar() {
    var wrap = elCo('coArchWrap'), sel = elCo('coArchivarMod');
    if (!wrap || !sel) return;
    var mods = modulosArchivables();
    var antes = sel.value;
    sel.innerHTML = mods.map(function (m) {
      return '<option value="' + esc(m.key) + '">' + esc(m.title || m.key) + '</option>';
    }).join('');
    if (antes && mods.some(function (m) { return m.key === antes; })) sel.value = antes;
    wrap.hidden = !mods.length;
    pintarArchEstado();
  }
  function pintarArchEstado() {
    var cb = elCo('coArchivar'), sel = elCo('coArchivarMod');
    if (cb && sel) sel.disabled = !cb.checked;
    if (typeof pintarSwitches === 'function') pintarSwitches();
  }

  /* el módulo de avisos, por clave y —si en otra instalación se llama
     distinto— por nombre */
  function claveAvisos() {
    var mods = modulosArchivables();
    var exacto = mods.filter(function (m) { return m.key === 'comunicacion_importante'; })[0];
    if (exacto) return exacto.key;
    var porNombre = mods.filter(function (m) {
      return /important/i.test(String(m.title || ''));
    })[0];
    return porNombre ? porNombre.key : '';
  }

  /* Al marcar "Importante" se PROPONE archivar en el módulo de avisos, que es
     donde ese aviso va a seguir existiendo cuando se caiga del feed. Es una
     propuesta: si quien publica la toca, no se vuelve a meter. */
  function sugerirArchivo() {
    if (COMP.archTocado) return;
    var cb = elCo('coArchivar'), sel = elCo('coArchivarMod');
    if (!cb || !sel) return;
    if (COMP.tipo !== 'importante') { cb.checked = false; pintarArchEstado(); return; }
    var k = claveAvisos();
    if (!k) return;
    sel.value = k;
    cb.checked = true;
    pintarArchEstado();
  }
  function archivoElegido() {
    var cb = elCo('coArchivar'), sel = elCo('coArchivarMod');
    return (cb && cb.checked && sel && sel.value) || '';
  }

  function abrirComp(tipo) {
    COMP.abierto = true;
    COMP.tipo = tipo || '';
    COMP.bloques = [];
    COMP.editando = null;
    marcarModo();
    abrirModalComp();
    elCo('coTitulo').value = '';
    elCo('coTexto').value = '';
    elCo('coFijar').checked = false;
    elCo('coConfirmar').checked = false;
    elCo('coVence').value = '';
    COMP.archTocado = false;
    elCo('coArchivar').checked = false;
    pintarVence();
    pintarTipos();
    pintarArchivar();
    sugerirArchivo();
    pintarAdjuntos();
    pintarSwitches();
    setTimeout(function () { elCo('coTitulo').focus(); }, 260);
  }

  function cerrarComp() {
    COMP.abierto = false;
    COMP.bloques = [];
    COMP.editando = null;
    marcarModo();
    cerrarModalComp();
    elCo('coTipos').classList.remove('on');
    cerrarPicker();
  }

  /* ¿hay algo escrito que se perdería al cerrar? */
  function hayBorrador() {
    if (!COMP.abierto) return false;
    if (elCo('coTitulo').value.trim()) return true;
    var t = elCo('coTexto').value.trim();
    if (t && t !== (COMP.texto0 || '')) return true;
    return (COMP.bloques || []).length > 0;
  }

  /* El cierre que pide permiso.
     ⚠️ Va SEPARADO de cerrarComp() a propósito: cerrarComp también lo llama
     el propio publicar() cuando ya guardó, y ahí preguntar "¿descartás lo
     escrito?" sobre algo que acaba de publicarse sería absurdo.
     Los cuatro caminos de salida —la X, Escape, el clic en el fondo y el
     botón viejo— tiraban el borrador sin decir nada: se escribía un aviso
     largo, un clic al costado y no quedaba nada. */
  var cerrandoComp = false;
  async function cerrarCompPidiendo() {
    if (cerrandoComp) return;                 /* dos Escape seguidos */
    if (!hayBorrador()) { cerrarComp(); return; }
    cerrandoComp = true;
    try {
      var ok = await confirmar(
        'Lo que escribiste todavía no se publicó. Si salís ahora se pierde.',
        'Descartar', 'Salir sin publicar');
      if (ok) cerrarComp();
    } finally { cerrandoComp = false; }
  }

  /* #B4231F -> "180,35,31", para poder pedir el mismo color con alpha */
  function rgbDe(hex) {
    var h = String(hex || '').replace('#', '');
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    if (isNaN(n)) return '110,105,96';
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255].join(',');
  }

  /* la etiqueta se elige con el selector de la maqueta: pastilla + menú */
  function pintarTipos() {
    var pop = elCo('coTipos');
    pop.innerHTML = Object.keys(TIPOS).map(function (k) {
      var v = TIPOS[k];
      return '<button type="button" data-t="' + k + '"><i style="background:' + v.c + '"></i>' + v.t +
        (COMP.tipo === k ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 6 9 17l-5-5"/></svg>' : '') +
        '</button>';
    }).join('');
    pop.querySelectorAll('button').forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation();
        COMP.tipo = (COMP.tipo === b.dataset.t) ? '' : b.dataset.t;
        pop.classList.remove('on');
        pintarTipos();
        sugerirArchivo();      /* "Importante" propone el módulo de avisos */
        pintarSwitches();
      };
    });
    var cara = TIPOS[COMP.tipo];
    var nom = document.getElementById('etqNombre'), col = document.getElementById('etqColor');
    if (nom) nom.textContent = cara ? cara.t : 'Sin etiqueta';
    if (col) { col.hidden = !cara; if (cara) col.style.background = cara.c; }
  }
  var btnEtq = document.getElementById('btnEtq');
  if (btnEtq) btnEtq.onclick = function (e) { e.stopPropagation(); elCo('coTipos').classList.toggle('on'); };
  document.addEventListener('click', function (e) {
    if (!e.target.closest('#coTipos') && !e.target.closest('#btnEtq'))
      elCo('coTipos').classList.remove('on');
  });

  /* ------------------------- adjuntos ------------------------- */
  var AD_NOMBRE = {
    imagen: 'Foto', galeria: 'Varias fotos', video: 'Video',
    pdf: 'PDF', lista: 'Lista', ref: 'Señala un módulo'
  };

  function pintarAdjuntos() {
    var cont = elCo('coAdjuntos');
    /* tarjetas "cargado" de la maqueta: miniatura + nombre + detalle + sacar */
    var ICONO_CARG = {
      imagen: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
      galeria: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
      video: '<path d="m22 8-6 4 6 4V8z"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
      pdf: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
      lista: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
      ref: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>'
    };
    cont.innerHTML = COMP.bloques.map(function (bk, i) {
      var titulo = AD_NOMBRE[bk.t] || nombreBloque(bk.t);
      var detalle = '', miniSrc = '', its;
      if (bk.t === 'imagen') { detalle = bk.src ? 'Lista para publicar' : 'Sin foto todavía'; miniSrc = bk.src || ''; }
      if (bk.t === 'galeria') {
        its = (bk.items || []).filter(function (it) { return it.src; });
        titulo = (bk.titulo || '').trim() || 'Varias fotos';
        detalle = 'Galería · ' + its.length + (its.length === 1 ? ' imagen' : ' imágenes');
        miniSrc = its.length ? its[0].src : '';
      }
      if (bk.t === 'video') {
        titulo = (bk.caption || bk.dlNombre || '').trim() || 'Video';
        detalle = bk.src ? 'Video listo' : (bk.url ? 'Video · link' : 'Sin video todavía');
        miniSrc = bk.poster || '';
      }
      if (bk.t === 'pdf') { titulo = bk.nombre || 'PDF'; detalle = bk.src ? 'PDF listo' : 'Sin archivo todavía'; }
      if (bk.t === 'lista') detalle = 'Lista · ' + (bk.items || []).length + ' ítems';
      if (bk.t === 'ref') {
        var mRef = (MODULOS || []).filter(function (m) { return m.key === bk.mod; })[0];
        titulo = mRef ? (mRef.title || bk.mod) : 'Señalar un módulo';
        detalle = [bk.sub, 'módulo de la intranet'].filter(Boolean).join(' · ') || 'sin elegir';
      }
      /* un bloque hecho con el editor completo (tabla, pasos, chat…): acá no se
         edita, pero SE CONSERVA. Borrarlo en silencio seria perder contenido. */
      if (!AD_NOMBRE[bk.t]) detalle = 'Se mantiene tal cual';
      var mini = miniSrc
        ? '<span class="mini-ph"><img src="/intranet/' + esc(miniSrc) + '" alt="" loading="lazy"></span>'
        : '<span class="mini-ph mini-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor">' +
          (ICONO_CARG[bk.t] || ICONO_CARG.lista) + '</svg></span>';
      return '<div class="cargado' + (AD_NOMBRE[bk.t] ? '' : ' ajeno') + '">' + mini +
        '<span class="t"><b>' + esc(titulo) + '</b><span>' + esc(detalle) + '</span></span>' +
        '<button type="button" class="co-adj-x" data-i="' + i + '" aria-label="Sacar" title="Sacar">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M18 6 6 18M6 6l12 12"/></svg></button></div>';
    }).join('');
    cont.querySelectorAll('.co-adj-x').forEach(function (b) {
      b.onclick = function () { COMP.bloques.splice(+b.dataset.i, 1); pintarAdjuntos(); };
    });
  }

  /* el nombre lindo de un bloque que el compositor no sabe editar */
  function nombreBloque(t) {
    var info = (typeof BLOQUE_INFO !== 'undefined') ? BLOQUE_INFO[t] : null;
    return (info && info.label) || t;
  }

  /* Los VIDEOS van por otra puerta: /api/upload-video mira el códec y, si el
     navegador no lo sabe mostrar, lo convierte a H.264 solo.

     ⚠️ Por qué importa: un video de iPhone viene en HEVC (H.265) 4K de 10 bits.
     Chrome no lo decodifica — el vendedor vería un rectángulo NEGRO con sonido,
     porque el audio sí carga. Y un clip de 4 segundos pesa 11 MB: un minuto
     serían 160 MB de datos móviles. Convertido queda en 0,5 MB y se ve. */
  /* Cuánto mide el video, medido acá mismo antes de subirlo. Un <video> sobre
     un objectURL alcanza: no hace falta el servidor ni ffmpeg. */
  function medirVideo(file) {
    var url = URL.createObjectURL(file);
    return medirVideoURL(url).then(function (m) {
      try { URL.revokeObjectURL(url); } catch (e) {}
      return m;
    });
  }
  function medirVideoURL(url) {
    return new Promise(function (res) {
      var v = document.createElement('video');
      var listo = function (w, h) {
        if (listo.hecho) return;
        listo.hecho = true;
        res({ w: w || 0, h: h || 0 });
      };
      v.preload = 'metadata';
      v.onloadedmetadata = function () { listo(v.videoWidth, v.videoHeight); };
      v.onerror = function () { listo(0, 0); };
      setTimeout(function () { listo(v.videoWidth, v.videoHeight); }, 6000);
      v.src = url;
    });
  }

  /* El bloque de video con su forma REAL. `medido` es lo que le dice a la
     intranet que puede confiar en el marcado y no bajar el archivo para
     averiguar si es vertical. Si no se pudo medir, queda como antes. */
  async function bloqueVideo(file) {
    var url = URL.createObjectURL(file);
    var medida = await medirVideoURL(url);
    /* el póster se saca del archivo local ANTES de subirlo: es gratis */
    var blob = await capturarPoster(url);
    try { URL.revokeObjectURL(url); } catch (e) {}
    var src = await subirVideo(file);
    var b = { t: 'video', src: src, tam: 'md' };
    if (blob) {
      try {
        b.poster = await subir(new File([blob], 'poster.jpg', { type: 'image/jpeg' }),
                               'poster', 'jpg');
      } catch (e) {}
    }
    if (medida.w && medida.h) {
      b.orient = (medida.w / medida.h) < 0.95 ? 'vert' : 'horiz';
      b.ar = medida.w + '/' + medida.h;
      b.medido = true;
    } else {
      b.orient = 'horiz';
    }
    return b;
  }

  async function subirVideo(file) {
    var cap = await api('/api/video-capacidad');
    if (file.size > cap.max_subida) {
      throw new Error('Ese video pesa ' + (file.size / 1048576).toFixed(0) +
        ' MB y el máximo que puedo recibir son ' + Math.round(cap.max_subida / 1048576) + ' MB.');
    }
    /* Lo único que se pregunta: bajar 104 MB de compresor la primera vez.
       Descargar eso sin avisar sería una falta de respeto. La conversión en sí
       no se pregunta: el usuario pidió que pase sola. */
    if (!cap.compresor) {
      var ok = await confirmar(
        'Es la primera vez que subís un video en esta computadora. Para poder ' +
        'dejarlo en un formato que se vea en todos los celulares tengo que ' +
        'descargar el compresor: son ' + cap.mb_descarga + ' MB, una sola vez.',
        'Descargar', 'Falta el compresor', 'ok');
      if (!ok) throw new Error('Sin el compresor no puedo preparar el video.');
      toast('Descargando el compresor…');
      var r0 = await api('/api/preparar-compresor', { method: 'POST' });
      if (r0.job) await esperarJob(r0.job, function (j) {
        toast('Descargando el compresor… ' + (j.pct || 0) + '%');
      });
    }

    toast('Subiendo el video…');
    var fd = new FormData();
    fd.append('key', 'cartelera-vid-' + Date.now());
    fd.append('file', file);
    var r = await api('/api/upload-video', { method: 'POST', body: fd });
    if (r.falta_ffmpeg) throw new Error(r.error || 'Falta el compresor.');
    if (r.job) {
      var j = await esperarJob(r.job, function (x) {
        toast('Preparando el video… ' + (x.pct || 0) + '%');
      });
      if (j.estado === 'error') throw new Error(j.error || 'No se pudo preparar el video.');
      toast('Video listo' + (j.info ? ' (' + j.info + ')' : ''), 'ok');
      return j.src;
    }
    toast('Video listo', 'ok');
    return r.src;
  }

  /* sube un archivo por el mismo camino que usa el editor de módulos */
  function subir(file, etiqueta, fmt) {
    var fd = new FormData();
    fd.append('key', 'muro-' + (etiqueta || 'archivo') + '-' + Date.now());
    if (fmt) fd.append('fmt', fmt);
    fd.append('file', file);
    return api('/api/upload-contenido', { method: 'POST', body: fd }).then(function (r) { return r.src; });
  }

  /* ══════════════ EL PRIMER CUADRO DEL VIDEO, COMO IMAGEN ══════════════
     Sin esto, en celular —donde el video ya no se baja— el vendedor ve un
     rectángulo negro en vez del sillón. El póster pesa ~40 KB contra los 500
     del video: se ve lo mismo que antes y no se gastan datos.
     Se achica a 720px de ancho porque es un cartel, no la pieza. */
  function capturarPoster(url) {
    return new Promise(function (res) {
      var v = document.createElement('video');
      var listo = false;
      var fallar = function () { if (!listo) { listo = true; res(null); } };
      v.preload = 'metadata';
      v.muted = true;
      v.playsInline = true;
      v.onerror = fallar;
      v.onloadeddata = function () {
        if (listo) return;
        listo = true;
        try {
          var an = v.videoWidth, al = v.videoHeight;
          if (!an || !al) return res(null);
          var esc = Math.min(1, 720 / Math.max(an, al));
          var c = document.createElement('canvas');
          c.width = Math.round(an * esc);
          c.height = Math.round(al * esc);
          c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
          c.toBlob(function (b) { res(b || null); }, 'image/jpeg', 0.72);
        } catch (e) { res(null); }
      };
      setTimeout(fallar, 9000);
      /* #t= le pide al navegador que se posicione en un cuadro con imagen:
         el segundo cero de muchos videos es negro */
      v.src = url + (url.indexOf('#') >= 0 ? '' : '#t=0.15');
    });
  }

  /* sube el póster y devuelve su ruta, o '' si no se pudo */
  async function subirPoster(url) {
    try {
      var blob = await capturarPoster(url);
      if (!blob) return '';
      return await subir(new File([blob], 'poster.jpg', { type: 'image/jpeg' }),
                         'poster', 'jpg');
    } catch (e) { return ''; }
  }

  function pedirArchivo(accept, multiple) {
    return new Promise(function (res) {
      var inp = document.createElement('input');
      inp.type = 'file'; inp.accept = accept; inp.multiple = !!multiple; inp.hidden = true;
      inp.onchange = function () { res([].slice.call(inp.files)); inp.remove(); };
      document.body.appendChild(inp); inp.click();
    });
  }

  async function agregarAdjunto(que) {
    if (que === 'ref') return abrirPicker();

    if (que === 'lista') {
      COMP.bloques.push({ t: 'lista', items: [{ icono: 'check', html: 'Primer punto' }] });
      pintarAdjuntos();
      toast('Lista agregada: editá los puntos antes de publicar', 'ok');
      return;
    }

    var acc = { foto: 'image/*', galeria: 'image/*', video: 'video/*',
                pdf: 'application/pdf,.pdf' }[que];
    var files = await pedirArchivo(acc, que === 'galeria');
    if (!files.length) return;
    toast('Subiendo…');
    try {
      if (que === 'galeria') {
        var items = [];
        for (var i = 0; i < files.length; i++) {
          items.push({ src: await subir(files[i], 'gal'),
                       nombre: files[i].name.replace(/\.[^.]+$/, '').slice(0, 60) });
        }
        COMP.bloques.push({ t: 'galeria', titulo: '', items: items });
      } else if (que === 'foto') {
        COMP.bloques.push({ t: 'imagen', src: await subir(files[0], 'img'), alt: '', tam: 'md' });
      } else if (que === 'video') {
        COMP.bloques.push(await bloqueVideo(files[0]));
      } else if (que === 'pdf') {
        COMP.bloques.push({ t: 'pdf', src: await subir(files[0], 'pdf'), modo: 'tarjeta',
                            nombre: files[0].name.replace(/\.pdf$/i, '').slice(0, 60),
                            descargable: true });
      }
      pintarAdjuntos();
      toast('Listo', 'ok');
    } catch (e) { toast(e.message || 'No se pudo subir', 'err'); }
  }

  /* ------------- señalar un módulo (o algo de adentro) ------------- */
  function cerrarPicker() {
    var v = document.getElementById('coPick');
    if (!v) return;
    if (v._porEscape) document.removeEventListener('keydown', v._porEscape);
    v.classList.add('yendose');
    document.body.classList.remove('con-modal');
    setTimeout(function () { if (v.parentNode) v.remove(); }, 140);
  }

  /* qué piezas señalables tiene un módulo: las que tienen NOMBRE PROPIO.
     "bloque 4" no le dice nada a nadie, así que eso no se ofrece. */
  /* Qué piezas señalables tiene un módulo, y con QUÉ se pueden mostrar.
     Cada pieza puede traer una vista previa: la tarjeta de la cartelera no
     describe el material, lo muestra. `prev` viaja con el bloque 'ref'. */
  function piezasDe(m) {
    var c = m.content || {}, out = [];
    if (c.tipo === 'coleccion') {
      (c.docs || []).forEach(function (d) {
        if (d.archivado || !(d.titulo || '').trim()) return;
        out.push({ sub: d.titulo,
                   clase: d.presentacion ? 'presentación' : (c.palabra || 'documento'),
                   detalle: '', prev: null });
      });
    }
    var nVid = 0, nImg = 0;
    (c.bloques || []).forEach(function (bk) {
      var n, its;

      if (bk.t === 'galeria' && (bk.titulo || '').trim()) {
        its = (bk.items || []).filter(function (it) { return it.src; });
        n = its.length;
        out.push({ sub: bk.titulo, clase: 'galería',
                   detalle: n + (n === 1 ? ' imagen' : ' imágenes'),
                   prev: n ? { t: 'fotos', srcs: its.slice(0, 3).map(function (it) { return it.src; }),
                               total: n } : null });
      }

      if (bk.t === 'imagen' && bk.src) {
        nImg++;
        out.push({ sub: (bk.caption || bk.alt || '').trim() || ('Imagen ' + nImg),
                   clase: 'imagen', detalle: '',
                   prev: { t: 'foto', src: bk.src } });
      }

      if (bk.t === 'video' && (bk.src || bk.url)) {
        nVid++;
        /* Un video subido se puede previsualizar de verdad. Uno pegado de
           YouTube o Drive no: ahí sirve el poster si lo pusieron, y si no,
           la tarjeta queda compacta con su ícono. */
        out.push({ sub: (bk.caption || bk.dlNombre || '').trim() || ('Video ' + nVid),
                   clase: 'video', detalle: bk.src ? '' : 'link',
                   prev: bk.src ? { t: 'video', src: bk.src, poster: bk.poster || '',
                                    ar: bk.ar || '16/9', orient: bk.orient || 'horiz' }
                       : (bk.poster ? { t: 'foto', src: bk.poster } : null) });
      }

      if (bk.t === 'pdf' && (bk.nombre || '').trim())
        out.push({ sub: bk.nombre, clase: 'PDF', detalle: '', prev: null });
      if (bk.t === 'tabla' && (bk.titulo || '').trim())
        out.push({ sub: bk.titulo, clase: 'tabla', detalle: '', prev: null });
    });
    return out;
  }

  /* la miniatura que se ve en la lista del selector */
  function miniPrev(prev) {
    if (!prev) return '';
    if (prev.t === 'video')
      return '<span class="cp-mini es-vid"><video src="/intranet/' + esc(prev.src) +
        '" preload="metadata" muted playsinline></video><i></i></span>';
    /* si el archivo ya no esta, un cuadrado neutro: el icono de imagen rota
       del navegador es mas feo que no mostrar nada */
    var caido = " onerror=\"this.closest('.cp-mini').classList.add('sin-foto')\"";
    if (prev.t === 'foto')
      return '<span class="cp-mini"><img src="/intranet/' + esc(prev.src) +
        '" alt="" loading="lazy"' + caido + '></span>';
    if (prev.t === 'fotos')
      return '<span class="cp-mini"><img src="/intranet/' + esc(prev.srcs[0]) +
        '" alt="" loading="lazy"' + caido + '>' +
        (prev.total > 1 ? '<b>+' + (prev.total - 1) + '</b>' : '') + '</span>';
    return '';
  }

  function abrirPicker() {
    if (document.getElementById('coPick')) { cerrarPicker(); return; }

    var mods = (MODULOS || []).filter(function (m) {
      return !m.hidden && !esCartelera(m.content);
    });

    /* Elegir POR BLOQUE. La fila del módulo DESPLIEGA (ya no elige el módulo
       entero de una); adentro se elige el bloque puntual —o "Todo el módulo"—
       y se confirma con Adjuntar, así se ve qué quedó antes de cerrar.
       Compacto: filas finas, buscador arriba, un módulo abierto a la vez. */
    var abrev = { 'galería': 'gal', 'imagen': 'img', 'video': 'vid', 'reporte': 'rep',
                  'presentación': 'pre', 'documento': 'doc', 'PDF': 'pdf', 'tabla': 'tab' };
    var filas = [];

    var cuerpo = mods.map(function (m) {
      var hex = colorHex(m.color);
      var rgb = rgbDe(hex);
      var pz = piezasDe(m);
      var items = [];

      var iTodo = filas.length;
      filas.push({ m: m, sub: '', clase: 'módulo', detalle: '', prev: null, todo: true });
      items.push(
        '<button type="button" class="co-b co-b-todo" data-i="' + iTodo + '">' +
          '<span class="co-b-dot">★</span>' +
          '<span class="co-b-tx"><b>Todo el módulo</b><small>' +
            (pz.length ? pz.length + (pz.length === 1 ? ' bloque' : ' bloques') : 'el módulo entero') +
          '</small></span><span class="co-b-pick"></span></button>');

      pz.forEach(function (z) {
        var i = filas.length;
        filas.push({ m: m, sub: z.sub, clase: z.clase, detalle: z.detalle, prev: z.prev, todo: false });
        var det = [z.clase, z.detalle].filter(Boolean).join(' · ');
        items.push(
          '<button type="button" class="co-b" data-i="' + i + '">' +
            '<span class="co-b-dot">' + esc(abrev[z.clase] || (z.clase || '').slice(0, 3)) + '</span>' +
            '<span class="co-b-tx"><b>' + esc(z.sub) + '</b>' +
              (det ? '<small>' + esc(det) + '</small>' : '') +
            '</span><span class="co-b-pick"></span></button>');
      });

      var busca = esc((m.title + ' ' + (m.desc || '') + ' ' +
        pz.map(function (z) { return z.sub + ' ' + z.clase; }).join(' ')).toLowerCase());
      return '<div class="co-g" data-b="' + busca + '" style="--rgb:' + rgb + '">' +
        '<button type="button" class="co-m">' +
          '<span class="co-m-ic" style="background:' + hex + '">' + ICONO(m.icon) + '</span>' +
          '<span class="co-m-tx"><b>' + esc(m.title) + '</b>' +
            (m.desc ? '<small>' + esc(m.desc) + '</small>' : '') + '</span>' +
          (pz.length ? '<span class="co-m-n">' + pz.length + '</span>' : '') +
          '<span class="co-m-fl">' + FLECHA() + '</span>' +
        '</button>' +
        '<div class="co-bl" hidden>' + items.join('') + '</div>' +
      '</div>';
    }).join('');

    var ov = document.createElement('div');
    ov.className = 'co-modal'; ov.id = 'coPick';
    ov.innerHTML =
      '<div class="co-modal-fondo"></div>' +
      '<div class="co-modal-caja" role="dialog" aria-modal="true" aria-label="Elegir un bloque">' +
        '<div class="co-modal-head">' +
          '<div class="cm-tit"><b>¿Qué bloque mandás?</b>' +
          '<span>la publicación va a llevar una tarjeta hasta ahí</span></div>' +
          '<button type="button" class="co-modal-x" aria-label="Cerrar">&times;</button>' +
        '</div>' +
        '<div class="co-busca">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><path d="M21 21l-4-4"></path></svg>' +
          '<input type="text" placeholder="Buscar módulo o bloque…" aria-label="Buscar módulo o bloque">' +
        '</div>' +
        '<div class="co-lista"></div>' +
        '<div class="co-pie">' +
          '<div class="co-pie-st">Elegí un bloque para adjuntar.</div>' +
          '<button type="button" class="co-pie-ok" disabled>Adjuntar</button>' +
        '</div>' +
      '</div>';
    var lista = ov.querySelector('.co-lista');
    lista.innerHTML = cuerpo || '<div class="vacio">No hay módulos para señalar todavía.</div>';
    document.body.appendChild(ov);
    document.body.classList.add('con-modal');
    var clip = elCo('coClip'); if (clip) clip.setAttribute('aria-expanded', 'false');
    var menu = document.getElementById('coMenu'); if (menu) menu.hidden = true;

    var elegido = null;
    var st = ov.querySelector('.co-pie-st');
    var ok = ov.querySelector('.co-pie-ok');

    /* desplegar un módulo: uno abierto a la vez */
    ov.querySelectorAll('.co-m').forEach(function (b) {
      b.onclick = function () {
        var g = b.closest('.co-g');
        var abierto = g.classList.contains('abierto');
        ov.querySelectorAll('.co-g.abierto').forEach(function (o) {
          o.classList.remove('abierto');
          o.querySelector('.co-bl').hidden = true;
        });
        if (!abierto) {
          g.classList.add('abierto');
          g.querySelector('.co-bl').hidden = false;
          g.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      };
    });

    /* elegir un bloque: se marca (no cierra); Adjuntar confirma */
    ov.querySelectorAll('.co-b').forEach(function (b) {
      b.onclick = function () {
        ov.querySelectorAll('.co-b.elegido').forEach(function (x) { x.classList.remove('elegido'); });
        b.classList.add('elegido');
        elegido = filas[+b.dataset.i];
        st.innerHTML = elegido.todo
          ? 'Vas a mandar <b>todo «' + esc(elegido.m.title) + '»</b>'
          : 'Vas a mandar <b>' + esc(elegido.sub) + '</b> <span class="co-pie-de">de ' + esc(elegido.m.title) + '</span>';
        ok.disabled = false;
      };
    });

    ok.onclick = function () {
      if (!elegido) return;
      var f = elegido;
      COMP.bloques.push({ t: 'ref', key: f.m.key, mod: f.m.title, sub: f.sub,
                          clase: f.clase, detalle: f.detalle, prev: f.prev || null,
                          icon: f.m.icon || 'layers', color: f.m.color || '--c-hudson' });
      cerrarPicker(); pintarAdjuntos();
    };

    /* buscador: filtra por módulo o por nombre de bloque, y abre lo que matchea */
    var inp = ov.querySelector('.co-busca input');
    inp.oninput = function () {
      var q = inp.value.trim().toLowerCase();
      ov.querySelectorAll('.co-g').forEach(function (g) {
        var hit = !q || (g.dataset.b || '').indexOf(q) >= 0;
        g.style.display = hit ? '' : 'none';
        if (q && hit) { g.classList.add('abierto'); g.querySelector('.co-bl').hidden = false; }
        else if (!q) { g.classList.remove('abierto'); g.querySelector('.co-bl').hidden = true; }
      });
    };

    ov.querySelector('.co-modal-x').onclick = cerrarPicker;
    ov.querySelector('.co-modal-fondo').onclick = cerrarPicker;
    /* ⚠️ Al pasar el selector a ventana flotante, Escape dejó de cerrarlo: el
       handler del compositor le cede el turno viendo #coPick en el DOM. */
    ov._porEscape = function (e) { if (e.key === 'Escape') cerrarPicker(); };
    document.addEventListener('keydown', ov._porEscape);
  }

  function FLECHA() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" ' +
      'stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>';
  }

  /* El color del módulo llega como el NOMBRE de una variable ('--c-caba').
     ⚠️ Esas variables NO estan definidas en :root del panel: viven adentro de
     .doc-preview (styles.css). Pedirlas con getComputedStyle en la raiz devolvia
     vacio, asi que TODO caia al gris de reserva y los iconos del selector
     quedaban blancos sobre transparente, o sea invisibles.
     app.js ya tiene el mapa autoritativo: HEX['--c-caba'] === '#2C6E8A'. */
  function colorHex(varName) {
    if (!varName) return '#6E6960';
    var n = String(varName).trim();
    if (typeof HEX !== 'undefined' && HEX[n]) return HEX[n];
    var v = getComputedStyle(document.documentElement).getPropertyValue(n);
    return (v || '').trim() || '#6E6960';
  }


  /* el ícono del módulo, del mismo juego que usa el panel */
  function ICONO(nombre) {
    /* ICONS se declara con const en app.js: vive en el ambito global del
       script pero NO cuelga de window. Como muro.js carga despues, se lo
       nombra directo; el typeof evita romper si algun dia se va. */
    var g = (typeof ICONS !== 'undefined') ? ICONS : {};
    var d = g[nombre] || g.layers || '';
    return '<span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg></span>';
  }

  /* --------------------------- publicar --------------------------- */
  async function publicar() {
    var titulo = elCo('coTitulo').value.trim();
    if (!titulo) { toast('Ponele un título al aviso', 'err'); elCo('coTitulo').focus(); return; }

    var bloques = [];
    var texto = elCo('coTexto').value.trim();
    if (texto) {
      /* si no se tocó una letra, vuelve el bloque original con su formato */
      if (COMP.parrafo0 && texto === COMP.texto0) bloques.push(COMP.parrafo0);
      else bloques.push({ t: 'parrafo', texto: texto });
    }
    COMP.bloques.forEach(function (bk) { bloques.push(bk); });
    if (!bloques.length) { toast('Escribí algo o adjuntá una pieza', 'err'); return; }

    /* Migracion silenciosa: una publicacion vieja puede traer videos sin
       medir, porque el compositor guardaba orient:'horiz' fijo. Se miden ahora
       —desde el archivo ya subido— y con eso la intranet deja de bajarlos en
       celular. Solo se toca lo que no tiene la marca. */
    for (var vi = 0; vi < bloques.length; vi++) {
      var bkv = bloques[vi];
      if (!bkv || bkv.t !== 'video' || !bkv.src) continue;
      if (bkv.medido && bkv.poster) continue;
      if (!bkv.medido) {
        var md = await medirVideoURL('/intranet/' + bkv.src);
        if (md.w && md.h) {
          bkv.orient = (md.w / md.h) < 0.95 ? 'vert' : 'horiz';
          bkv.ar = md.w + '/' + md.h;
          bkv.medido = true;
        }
      }
      /* y el póster, que es lo que evita el rectángulo negro en celular */
      if (!bkv.poster) {
        var ps = await subirPoster('/intranet/' + bkv.src);
        if (ps) bkv.poster = ps;
      }
    }

    var idx = idxMuro();
    if (idx < 0) {                    /* todavía no existe el muro: se crea solo */
      var ok0 = await confirmar('Se crea el muro, que pasa a ser la portada de la intranet: ' +
        'lo primero que ven los vendedores al entrar.', 'Crear el muro y publicar', 'Publicar', 'ok');
      if (!ok0) return;
      MODULOS.unshift({
        key: '', title: 'Cartelera', desc: 'Todo lo nuevo del equipo, en un solo lugar',
        icon: 'megaphone', color: '--c-hudson', ready: true,
        content: { tipo: 'cartelera', docs: [] }
      });
      idx = 0;
    }
    var cont = MODULOS[idx].content;
    cont.docs = cont.docs || [];
    var editando = COMP.editando !== null && COMP.editando !== undefined;
    var previa = editando ? cont.docs[COMP.editando] : null;
    if (editando && !previa) { toast('No encontré esa publicación', 'err'); return; }

    var doc = {
      /* corrigiendo se conserva la identidad: id, autor, fecha de publicación
         y si estaba oculta. Cambiar la fecha la haría saltar como nueva. */
      id: previa ? (previa.id || nuevoId()) : nuevoId(),
      titulo: titulo,
      autor: previa ? (previa.autor || 'Marketing') : 'Marketing',
      sucursal: previa ? (previa.sucursal || '') : '',
      fecha: previa ? (previa.fecha || hoyISO()) : hoyISO(),
      etiqueta: COMP.tipo || '',
      fijado: elCo('coFijar').checked,
      confirmar: elCo('coConfirmar').checked,
      vence: elCo('coVence').value || '',
      archivado: previa ? !!previa.archivado : false,
      archivar: archivoElegido(),
      bloques: bloques,
      html: bloquesHTML(bloques, false)
    };
    if (editando) cont.docs[COMP.editando] = doc;
    else cont.docs.unshift(doc);      /* lo más nuevo va arriba */

    /* ⚠️ SI ESTO FALLA HAY QUE DESHACERLO EN MEMORIA.
       `cont.docs` ya se tocó arriba. Si el guardado no llega al disco y se
       deja igual, la pantalla muestra una publicación que no existe, y el
       próximo guardado —de cualquier otra cosa— se la lleva puesta al
       servidor sin que nadie la haya confirmado. */
    var era = editando;
    var guardado = await persistModulos(false).then(
      function () { return true; },
      function (e) {
        if (era) cont.docs[COMP.editando] = previa;
        else cont.docs.shift();
        toast(e && e.message ? e.message : 'No se pudo guardar. Probá de nuevo.', 'err');
        return false;
      });
    if (!guardado) return;
    cerrarComp();
    renderMuro();
    if (window.pintarContadores) window.pintarContadores();

    /* ⚠️ ACA SE SUBE AL SITIO, Y NO EN UN SEGUNDO BOTON.
       Este boton dice "Publicar" (o "Guardar cambios" sobre algo que YA esta
       publicado), asi que tiene que llegar al vendedor. Antes solo escribia
       modulos.js en esta computadora y subirlo era otro boton, arriba, en
       otra pantalla: se corrigio una publicacion, se apreto Guardar, y el
       vendedor siguio viendo la version vieja sin que nada avisara.
       Los carteles de publicarCambios cuentan el resto. */
    if (typeof window.publicarCambios === 'function') {
      var subio = await window.publicarCambios(false, true);
      if (subio === false) {
        toast('Se guardó en esta computadora, pero no se pudo subir. ' +
              'Probá con "Publicar cambios".', 'err');
      }
      return;
    }
    toast(era ? 'Cambios guardados' : 'Publicado', 'ok');
  }

  (function () {
    var caja = document.getElementById('mpModo');
    if (!caja) return;
    caja.querySelectorAll('[data-modo]').forEach(function (b) {
      b.onclick = function () {
        if (VISTA_MODO === b.dataset.modo) return;
        VISTA_MODO = b.dataset.modo;
        try { localStorage.setItem('mp:modo', VISTA_MODO); } catch (e) {}
        pintarModoVista();
        renderMuro();
      };
    });
    pintarModoVista();
  })();

  elCo('coArchivar').onchange = function () { COMP.archTocado = true; pintarArchEstado(); };
  elCo('coArchivarMod').onchange = function () { COMP.archTocado = true; };

  elCo('coCerrar').onclick = cerrarCompPidiendo;
  elCo('coCancelar').onclick = cerrarCompPidiendo;
  /* El botón se apaga y avisa mientras trabaja, y no acepta un segundo
     click: sin esto, un doble click creaba dos publicaciones iguales. */
  elCo('coPublicar').onclick = function () {
    var editando = COMP.editando !== null && COMP.editando !== undefined;
    return window.conBoton('#coPublicar', 'Publicando…', publicar)
      /* conBoton devuelve el rótulo que había ANTES de trabajar; si el
         guardado salió bien, cerrarComp() ya cambió de modo y ese rótulo
         quedó vencido. marcarModo() lo vuelve a poner como corresponde. */
      .then(marcarModo, marcarModo);
  };
  document.querySelectorAll('.co-ad').forEach(function (b) {
    b.onclick = function () { agregarAdjunto(b.dataset.ad); };
  });

  /* ---------------- el clip: una sola puerta a los adjuntos ---------------- */
  var clip = elCo('coClip'), menu = elCo('coMenu');
  clip.onclick = function (e) {
    e.stopPropagation();
    var abierto = !menu.hidden;
    menu.hidden = abierto;
    clip.setAttribute('aria-expanded', String(!abierto));
    if (!abierto) cerrarPicker();
  };
  menu.querySelectorAll('.co-mi').forEach(function (b) {
    b.onclick = function () {
      menu.hidden = true;
      clip.setAttribute('aria-expanded', 'false');
      agregarAdjunto(b.dataset.ad);
    };
  });
  document.addEventListener('click', function (e) {
    if (!menu.hidden && !menu.contains(e.target) && e.target !== clip) {
      menu.hidden = true; clip.setAttribute('aria-expanded', 'false');
    }
  });

  /* ------------------- arrastrar y soltar sobre el compositor -------------------
     El pedido: que no haga falta apretar "Foto" y buscar el archivo. Se suelta
     encima y listo. Varias fotos juntas entran como galería, una sola como foto.
     Se cuenta con un contador porque dragleave salta con cada hijo que se cruza. */
  var zona = elCo('compOpen'), drop = elCo('coDrop'), hondo = 0;

  function traeArchivos(e) {
    var dt = e.dataTransfer;
    return !!(dt && dt.types && [].indexOf.call(dt.types, 'Files') >= 0);
  }
  zona.addEventListener('dragenter', function (e) {
    if (!traeArchivos(e)) return;
    e.preventDefault(); hondo++; drop.hidden = false; zona.classList.add('soltando');
  });
  zona.addEventListener('dragover', function (e) {
    if (!traeArchivos(e)) return;
    e.preventDefault(); e.dataTransfer.dropEffect = 'copy';
  });
  zona.addEventListener('dragleave', function () {
    hondo = Math.max(0, hondo - 1);
    if (!hondo) { drop.hidden = true; zona.classList.remove('soltando'); }
  });
  zona.addEventListener('drop', async function (e) {
    if (!traeArchivos(e)) return;
    e.preventDefault();
    hondo = 0; drop.hidden = true; zona.classList.remove('soltando');
    var files = [].slice.call(e.dataTransfer.files);
    if (!files.length) return;
    await soltar(files);
  });

  async function soltar(files) {
    var imgs = files.filter(function (f) { return /^image\//.test(f.type); });
    var vids = files.filter(function (f) { return /^video\//.test(f.type); });
    var pdfs = files.filter(function (f) { return f.type === 'application/pdf'; });
    var otros = files.length - imgs.length - vids.length - pdfs.length;
    if (otros) toast('Solo entran imágenes, videos y PDF', 'err');
    if (!imgs.length && !vids.length && !pdfs.length) return;
    toast('Subiendo…');
    try {
      if (imgs.length === 1) {
        COMP.bloques.push({ t: 'imagen', src: await subir(imgs[0], 'img'), alt: '', tam: 'md' });
      } else if (imgs.length > 1) {
        var items = [];
        for (var i = 0; i < imgs.length; i++) {
          items.push({ src: await subir(imgs[i], 'gal'),
                       nombre: imgs[i].name.replace(/\.[^.]+$/, '').slice(0, 60) });
        }
        COMP.bloques.push({ t: 'galeria', titulo: '', items: items });
      }
      for (var v = 0; v < vids.length; v++) {
        COMP.bloques.push(await bloqueVideo(vids[v]));
      }
      for (var d = 0; d < pdfs.length; d++) {
        COMP.bloques.push({ t: 'pdf', src: await subir(pdfs[d], 'pdf'), modo: 'tarjeta',
                            nombre: pdfs[d].name.replace(/\.pdf$/i, '').slice(0, 60),
                            descargable: true });
      }
      pintarAdjuntos();
      toast('Listo', 'ok');
    } catch (err) { toast(err.message || 'No se pudo subir', 'err'); }
  }

  /* pegar una imagen del portapapeles: el mismo camino */
  zona.addEventListener('paste', function (e) {
    var items = (e.clipboardData && e.clipboardData.files) || [];
    var files = [].slice.call(items);
    if (files.length) { e.preventDefault(); soltar(files); }
  });
  /* Escape cierra de a UNA capa, de la más chica a la más grande.
     ⚠️ Sin esta lista, Escape con el calendario abierto cerraba TAMBIEN el
     compositor y te llevaba puesto el borrador entero. */
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    /* Dos formas de saber que había algo encima, porque el orden en que se
       registran los handlers decide cuál sirve:
       - los que corren DESPUÉS (calendario) todavía están en el DOM;
       - los que corren ANTES (menú de la publicación) ya se cerraron, y por
         eso dejan la marca en el evento. */
    var encima = e.__capaCerrada ||
                 document.getElementById('calPop') ||
                 document.getElementById('mpMenu') ||
                 document.getElementById('coPick') ||
                 (!document.getElementById('coMenu').hidden ? 1 : null);
    /* El menú de etiquetas es una capa más, y faltaba en esta lista: con él
       abierto, Escape se saltaba al compositor y cerraba TODO —incluido lo
       que la persona había escrito—. El que sí estaba, #coMenu, es el puente
       oculto del compositor viejo: está siempre hidden, así que nunca frenó
       nada. Este lo cierra acá mismo porque no tiene handler propio. */
    var etq = document.getElementById('coTipos');
    if (!encima && etq && etq.classList.contains('on')) {
      etq.classList.remove('on');
      return;
    }
    if (encima) return;               /* lo cierra quien lo abrió */
    if (COMP.abierto) cerrarCompPidiendo();
  });


  /* ===================================================================
     CALENDARIO PROPIO
     El <input type="date"> obligaba a acertarle a un ícono de 16px para
     abrirlo, y lo que salía era el almanaque de Chrome: no se puede
     estilar y no tiene nada que ver con el resto del panel. Este abre
     tocando el campo entero y trae los atajos que se usan de verdad.
     El valor sigue viviendo en #coVence (hidden), así que todo el
     código que lo lee o lo escribe no se entera del cambio.
     =================================================================== */
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  var DIAS_S = ['lu', 'ma', 'mi', 'ju', 'vi', 'sá', 'do'];
  var CAL_MES = null;                       /* mes que se está mirando */

  function hoyLocal() {
    var h = new Date(); h.setHours(0, 0, 0, 0); return h;
  }
  /* fecha LOCAL a texto. Con toISOString(), de noche en Argentina el UTC ya
     es el día siguiente y la fecha sale corrida. */
  function aISO(d) {
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) +
           '-' + ('0' + d.getDate()).slice(-2);
  }
  function deISO(t) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(t || ''))) return null;
    var p = t.split('-');
    return new Date(+p[0], +p[1] - 1, +p[2]);
  }

  function pintarVence() {
    var v = elCo('coVence').value;
    var d = deISO(v);
    var tx = elCo('coVenceTx');
    var btn = elCo('coVenceBtn');
    if (!d) { tx.textContent = 'Siempre'; btn.classList.remove('con-fecha'); return; }
    btn.classList.add('con-fecha');
    var hoy = hoyLocal();
    var q = Math.round((d - hoy) / 86400000);
    tx.textContent = d.getDate() + ' de ' + MESES[d.getMonth()] +
      (d.getFullYear() !== hoy.getFullYear() ? ' de ' + d.getFullYear() : '') +
      (q === 0 ? ' · hoy' : q === 1 ? ' · mañana' : q > 1 && q <= 30 ? ' · en ' + q + ' días' : '');
  }

  function cerrarCal() {
    var c = document.getElementById('calPop');
    if (c) c.remove();
    var b = elCo('coVenceBtn');
    if (b) b.setAttribute('aria-expanded', 'false');
  }

  function abrirCal() {
    if (document.getElementById('calPop')) { cerrarCal(); return; }
    var btn = elCo('coVenceBtn');
    btn.setAttribute('aria-expanded', 'true');
    var sel = deISO(elCo('coVence').value);
    CAL_MES = new Date((sel || hoyLocal()).getFullYear(), (sel || hoyLocal()).getMonth(), 1);

    var pop = document.createElement('div');
    pop.className = 'cal-pop'; pop.id = 'calPop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Elegir hasta cuándo se ve');
    document.body.appendChild(pop);
    pintarCal(pop);

    var r = btn.getBoundingClientRect();
    var alto = pop.offsetHeight, ancho = pop.offsetWidth;
    var arriba = (r.bottom + alto + 12 > window.innerHeight) && (r.top - alto - 8 > 0);
    pop.style.top = (arriba ? r.top - alto - 8 : r.bottom + 8) + 'px';
    pop.style.left = Math.max(10, Math.min(r.left, window.innerWidth - ancho - 10)) + 'px';
    pop.classList.add(arriba ? 'arriba' : 'abajo');
  }

  function pintarCal(pop) {
    var hoy = hoyLocal();
    var sel = deISO(elCo('coVence').value);
    var y = CAL_MES.getFullYear(), m = CAL_MES.getMonth();
    var primero = new Date(y, m, 1);
    /* la semana arranca el lunes: getDay() manda 0 para domingo */
    var corr = (primero.getDay() + 6) % 7;
    var cuantos = new Date(y, m + 1, 0).getDate();

    var celdas = '';
    for (var i = 0; i < corr; i++) celdas += '<span class="cal-v"></span>';
    for (var dia = 1; dia <= cuantos; dia++) {
      var f = new Date(y, m, dia);
      var cls = 'cal-d';
      if (sel && +f === +sel) cls += ' sel';
      if (+f === +hoy) cls += ' hoy';
      if (f < hoy) cls += ' pasado';
      celdas += '<button type="button" class="' + cls + '" data-f="' + aISO(f) + '"' +
        (f < hoy ? ' disabled' : '') + '>' + dia + '</button>';
    }

    pop.innerHTML =
      '<div class="cal-head">' +
        '<button type="button" class="cal-nav" data-m="-1" aria-label="Mes anterior">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg></button>' +
        '<b>' + MESES[m] + ' ' + y + '</b>' +
        '<button type="button" class="cal-nav" data-m="1" aria-label="Mes siguiente">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg></button>' +
      '</div>' +
      '<div class="cal-sem">' + DIAS_S.map(function (x) {
        return '<span>' + x + '</span>'; }).join('') + '</div>' +
      '<div class="cal-grid">' + celdas + '</div>' +
      '<div class="cal-atajos">' +
        '<button type="button" class="cal-at" data-at="7">Una semana</button>' +
        '<button type="button" class="cal-at" data-at="15">Quince días</button>' +
        '<button type="button" class="cal-at" data-at="mes">Fin de mes</button>' +
      '</div>' +
      '<div class="cal-pie">' +
        '<button type="button" class="cal-quitar"' + (sel ? '' : ' disabled') + '>Que se vea siempre</button>' +
      '</div>';

    pop.querySelectorAll('.cal-nav').forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation();
        CAL_MES = new Date(CAL_MES.getFullYear(), CAL_MES.getMonth() + (+b.dataset.m), 1);
        pintarCal(pop);
      };
    });
    pop.querySelectorAll('.cal-d').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); ponerVence(b.dataset.f); };
    });
    pop.querySelectorAll('.cal-at').forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation();
        var h = hoyLocal(), f;
        if (b.dataset.at === 'mes') f = new Date(h.getFullYear(), h.getMonth() + 1, 0);
        else { f = new Date(h); f.setDate(h.getDate() + (+b.dataset.at)); }
        ponerVence(aISO(f));
      };
    });
    pop.querySelector('.cal-quitar').onclick = function (e) {
      e.stopPropagation(); ponerVence('');
    };
  }

  function ponerVence(t) {
    elCo('coVence').value = t || '';
    pintarVence();
    cerrarCal();
  }

  elCo('coVenceBtn').onclick = function (e) { e.stopPropagation(); abrirCal(); };
  document.addEventListener('click', function (e) {
    if (!e.target.closest('#calPop') && !e.target.closest('#coVenceBtn')) cerrarCal();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') cerrarCal();
  });
  window.addEventListener('scroll', cerrarCal, true);

  /* ---------------- contadores de la barra lateral ---------------- */
  function pintarContadores() {
    const docs = postsDelMuro();
    const vivas = docs.filter(d => estadoDe(d) === 'publicada').length;
    const nm = document.getElementById('navNMuro');
    nm.hidden = !vivas; nm.textContent = vivas;
    const nd = document.getElementById('navNMod');
    const n = (MODULOS || []).filter(m => !m.hidden && !esCartelera(m.content)).length;
    nd.hidden = !n; nd.textContent = n;
    const na = document.getElementById('navNArch');
    if (na) {
      const arch = docs.filter(d => estadoDe(d) === 'oculta').length + enPapelera().length;
      na.hidden = !arch; na.textContent = arch;
    }
    pintarEstadoNav();
  }
  window.pintarContadores = pintarContadores;

  /* ---------- el estado del sidebar: qué falta publicar y cuándo fue el último envío ---------- */
  function cuandoHora(ms) {
    var d = new Date(ms), hoy = new Date();
    var hora = d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
    if (d.toDateString() === hoy.toDateString()) return 'hoy ' + hora;
    var ayer = new Date(hoy); ayer.setDate(hoy.getDate() - 1);
    if (d.toDateString() === ayer.toDateString()) return 'ayer ' + hora;
    return 'el ' + d.toLocaleDateString('es-AR', { day: 'numeric', month: 'numeric' });
  }
  function pintarEstadoNav() {
    var est = document.getElementById('estadoNav');
    var tit = document.getElementById('estadoTit'), sub = document.getElementById('estadoSub');
    if (!est || !tit) return;
    var pend = (typeof editados !== 'undefined' && editados) ? editados.size : 0;
    est.classList.toggle('pendiente', pend > 0);
    if (pend > 0) {
      tit.textContent = pend === 1 ? '1 cambio sin publicar' : pend + ' cambios sin publicar';
      sub.textContent = 'Tocá «Publicar cambios» para subirlos';
    } else {
      tit.textContent = 'Todo publicado';
      var t = 0; try { t = +localStorage.getItem('mys_ultimo_envio') || 0; } catch (e) {}
      sub.textContent = t ? ('Último envío ' + cuandoHora(t)) : 'La intranet está al día';
    }
  }
  window.pintarEstadoNav = pintarEstadoNav;

  /* al publicar OK se anota la hora del envío (para el "Último envío hoy…") */
  if (typeof publicarCambios === 'function') {
    var _pubOriginal = publicarCambios;
    window.publicarCambios = async function () {
      var ok = await _pubOriginal.apply(this, arguments);
      if (ok) {
        try { localStorage.setItem('mys_ultimo_envio', String(Date.now())); } catch (e) {}
        pintarEstadoNav();
      }
      return ok;
    };
  }
  if (typeof actualizarPublicarHome === 'function') {
    var _aph = actualizarPublicarHome;
    window.actualizarPublicarHome = function () { _aph(); pintarEstadoNav(); };
  }

  /* clic en el fondo oscuro del compositor: se cierra (patrón de la maqueta) */
  var fondoComp = document.getElementById('fondo');
  if (fondoComp) fondoComp.addEventListener('click', function (e) {
    if (e.target === fondoComp) cerrarCompPidiendo();
  });

  /* al arrancar: la sección Cartelera es la casa */
  const arrancar = () => { pintarContadores(); irASeccion('muro'); };
  if (document.readyState === 'complete') setTimeout(arrancar, 350);
  else window.addEventListener('load', () => setTimeout(arrancar, 350));
})();
