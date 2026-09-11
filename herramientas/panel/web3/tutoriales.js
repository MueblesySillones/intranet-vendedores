/* ════════════════════ TUTORIALES ════════════════════
   Videos instructivos con LÍNEA DE TIEMPO, como los capítulos de YouTube.

   Así lo pidió el equipo: «una pantalla donde se pueden cargar videos de
   tutoriales, que se pueda ver en pantalla completa y grande, y que tenga una
   línea de tiempo donde se coloca el minuto con el tutorial. Por ejemplo,
   minuto 3:25 "cómo editar módulos", y en la misma línea minuto 5 "cómo subir
   una publicación". Esto tiene que ser editable y ajustable».

   CÓMO FUNCIONA LA LÍNEA, Y POR QUÉ ASÍ

   La barra no es una barra sola: son TRAMOS, uno por capítulo, separados por
   una ranura —igual que YouTube—. El ancho de cada tramo es lo que dura ese
   capítulo, así que de un vistazo se ve cuánto ocupa cada tema. Adentro de
   cada tramo se llena lo que ya se vio.

   ⚠️ El tiempo de un capítulo se pone MIRANDO EL VIDEO: se pausa donde
   corresponde y se aprieta «Marcar acá». Escribir «3:25» a mano también se
   puede, pero pedirlo como única forma obliga a anotar los minutos en un papel
   mientras se mira. Igual se puede corregir escribiendo, porque el que grabó
   el video no siempre es el que carga los capítulos.

   ⚠️ Los capítulos se guardan ORDENADOS y sin repetir el segundo. Dos marcas
   en el mismo lugar no se pueden dibujar, y desordenadas «el capítulo de
   ahora» saltaría para atrás mientras el video avanza.

   QUIÉN PUEDE QUÉ

   Mirar, todos. Subir y editar, solo la central: un tutorial es material que
   se hace una vez y lo ve todo el mundo, igual que un módulo.
   ════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var LISTA = [];        // los tutoriales cargados
  var ABIERTO = null;    // el que se está mirando, o null si es la lista
  var EDIT = false;      // editando los capítulos del abierto
  var CAPS = [];         // los capítulos mientras se editan (el borrador)
  var CARGADO = false;

  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function aviso(t, tipo) { if (window.toast) window.toast(t, tipo || 'ok'); }

  /* ⚠️ `ES_CENTRAL` es un `let` de app.js, no una propiedad de window: un
     `let` del ámbito global NO se cuelga de window, así que `window.ES_CENTRAL`
     siempre daría undefined y todas las sucursales se creerían la central. Se
     lee por nombre, con `typeof` para no explotar si app.js no cargó. */
  function central() {
    try {
      return (typeof ES_CENTRAL === 'undefined') ? true : ES_CENTRAL !== false;
    } catch (e) {
      return true;
    }
  }

  function raiz() { return document.getElementById('tutRaiz'); }

  function video() { return document.getElementById('tutVideo'); }

  /* ⚠️ El `src` se guarda RELATIVO —«assets/_tutoriales/x.mp4»— porque así lo
     necesita la intranet publicada, que se sirve desde su propia raíz. Pero el
     panel vive en otra: acá los archivos de la intranet salen por
     `/intranet/…`, y sin el prefijo el video daba 404 y el reproductor quedaba
     en negro sin decir por qué. */
  function url(src) {
    src = String(src || '');
    return src.charAt(0) === '/' ? src : '/intranet/' + src;
  }

  /* ───────────── el tiempo, escrito y leído ─────────────
     Un tutorial de 8 minutos no necesita horas; uno de una hora sí. El formato
     sale del número, no de una preferencia. */
  function reloj(seg) {
    seg = Math.max(0, Math.floor(seg || 0));
    var h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), s = seg % 60;
    var dd = function (n) { return (n < 10 ? '0' : '') + n; };
    return h ? (h + ':' + dd(m) + ':' + dd(s)) : (m + ':' + dd(s));
  }

  /* «3:25» → 205. Acepta «205», «3:25» y «1:03:25». Devuelve null si no se
     entiende, para no convertir un error de tipeo en un salto al segundo 0. */
  function segundos(txt) {
    var partes = String(txt || '').trim().split(':');
    if (!partes.length || partes.some(function (p) { return !/^\d{1,3}$/.test(p.trim()); })) {
      return null;
    }
    var n = 0;
    for (var i = 0; i < partes.length; i++) n = n * 60 + parseInt(partes[i], 10);
    return n;
  }

  /* ───────────── traer y guardar ───────────── */
  function cargar() {
    return window.api('/api/tutoriales').then(function (r) {
      LISTA = (r && r.tutoriales) || [];
      CARGADO = true;
      pintar();
    }).catch(function () {
      LISTA = []; CARGADO = true; pintar();
    });
  }

  function guardar(lista, dice) {
    return window.api('/api/tutoriales', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tutoriales: lista })
    }).then(function (r) {
      if (r && r.error) throw new Error(r.error);
      LISTA = (r && r.tutoriales) || lista;
      if (dice) aviso(dice, 'ok');
      /* un tutorial cambiado es un cambio sin publicar, como cualquier otro */
      if (window.marcarOtroCambio) window.marcarOtroCambio();
      return LISTA;
    });
  }

  function elDe(id) {
    return LISTA.filter(function (t) { return t.id === id; })[0] || null;
  }

  /* ───────────── la pantalla ───────────── */
  function pintar() {
    var r = raiz();
    if (!r) return;
    if (ABIERTO && elDe(ABIERTO)) { pintarUno(elDe(ABIERTO)); return; }
    ABIERTO = null;
    pintarLista();
  }

  function pintarLista() {
    var r = raiz();
    var puede = central();
    r.innerHTML =
      '<div class="tut-h"><h3>Tutoriales</h3>' +
      (puede ? '<button type="button" class="btn active" id="tutNuevo">Subir un tutorial</button>' : '') +
      '</div>' +
      (LISTA.length
        ? '<div class="tut-l">' + LISTA.map(tarjeta).join('') + '</div>'
        : '<p class="dt-chico" id="tutVacio">' +
          (puede
            ? 'Todavía no hay ninguno. Un tutorial es un video —cómo editar un módulo, cómo subir una publicación— con una línea de tiempo adentro: marcás el minuto donde empieza cada tema y después se puede saltar directo a eso.'
            : 'Todavía no hay tutoriales cargados. Los sube la central y aparecen acá cuando traés la última versión.') +
          '</p>');
    if (puede) {
      document.getElementById('tutNuevo').onclick = abrirSubir;
    }
  }

  function tarjeta(t) {
    var n = (t.capitulos || []).length;
    return '<article class="tut-c" data-tut="' + esc(t.id) + '">' +
      (central() ? '<button type="button" class="tut-x" data-borrar-tut="' + esc(t.id) +
        '" title="Quitar este tutorial">×</button>' : '') +
      '<div class="tut-cp">' + esc(reloj(t.duracion)) +
        (n ? ' · ' + n + (n === 1 ? ' capítulo' : ' capítulos') : '') + '</div>' +
      '<h4 class="tut-cn">' + esc(t.titulo) + '</h4>' +
      (t.nota ? '<p class="tut-cd">' + esc(t.nota) + '</p>' : '') +
      '<div class="tut-cb"><button type="button" class="btn active" data-ver-tut="' +
        esc(t.id) + '">Ver el tutorial</button></div>' +
      '</article>';
  }

  /* Los íconos del reproductor, dibujados y no escritos: un ▶ de texto cambia
     de forma y de tamaño según la tipografía que tenga la máquina. */
  var ICONOS = {
    play: '<path d="M8 5v14l11-7z"/>',
    pausa: '<path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/>',
    son: '<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/>',
    mudo: '<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="m17 9 4 6M21 9l-4 6"/>',
    full: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'
  };

  function icono(k) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' +
      ICONOS[k] + '</svg>';
  }

  function alternar() {
    var v = video();
    if (!v) return;
    if (v.paused) { v.play().catch(function () {}); } else { v.pause(); }
  }

  function mudo() {
    var v = video();
    if (!v) return;
    v.muted = !v.muted;
    var b = document.getElementById('tutMudo');
    if (b) {
      b.innerHTML = icono(v.muted ? 'mudo' : 'son');
      b.title = v.muted ? 'Con sonido' : 'Silenciar';
    }
  }

  function pintarPlay() {
    var v = video(), b = document.getElementById('tutPlay');
    if (!v || !b) return;
    b.innerHTML = icono(v.paused ? 'play' : 'pausa');
    b.title = v.paused ? 'Reproducir' : 'Pausar';
  }

  /* ───────────── el reproductor ───────────── */
  function pintarUno(t) {
    var r = raiz();
    var puede = central();
    CAPS = (t.capitulos || []).map(function (c) { return { t: c.t, texto: c.texto }; });
    r.innerHTML =
      '<div class="tut-h">' +
        '<button type="button" class="btn" id="tutVolver">‹ Tutoriales</button>' +
        '<div class="tut-ht"><h3>' + esc(t.titulo) + '</h3>' +
          (t.nota ? '<p>' + esc(t.nota) + '</p>' : '') + '</div>' +
      '</div>' +
      '<div class="tut-caja" id="tutCaja">' +
        /* ⚠️ SIN `controls`: el navegador trae su propia barra de progreso y
           quedaba una arriba de la otra con la de capítulos. Acá la barra de
           capítulos ES la barra de progreso, que es de lo que se trata. */
        '<video id="tutVideo" playsinline preload="metadata" ' +
          'src="' + esc(url(t.src)) + '"></video>' +
        /* la línea va PEGADA abajo del video y adentro de la misma caja: en
           pantalla completa tiene que seguir estando, que es donde más sirve */
        '<div class="tut-linea">' +
          '<div class="tut-barra" id="tutBarra"></div>' +
          '<div class="tut-ctrl">' +
            '<button type="button" class="tut-b" id="tutPlay" title="Reproducir">' +
              icono('play') + '</button>' +
            '<span class="tut-reloj"><span id="tutAhora">0:00</span> / ' +
              '<span id="tutDur">0:00</span></span>' +
            '<b id="tutCapAhora"></b>' +
            '<button type="button" class="tut-b" id="tutMudo" title="Silenciar">' +
              icono('son') + '</button>' +
            '<button type="button" class="tut-b" id="tutFull" title="Pantalla completa">' +
              icono('full') + '</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div class="tut-bajo">' +
        (puede ? '<button type="button" class="btn" id="tutEditar">✎ Editar capítulos</button>' +
                 '<button type="button" class="btn active" id="tutGuardar" hidden>Guardar capítulos</button>' +
                 '<button type="button" class="btn" id="tutCancelar" hidden>Cancelar</button>' +
                 '<button type="button" class="btn" id="tutMarcar" hidden>+ Marcar acá</button>' : '') +
      '</div>' +
      '<div class="tut-caps" id="tutCaps"></div>';

    document.getElementById('tutVolver').onclick = function () {
      if (EDIT && !window.confirm('Estás editando los capítulos. ¿Salir sin guardar?')) return;
      EDIT = false; ABIERTO = null; pintar();
    };
    document.getElementById('tutFull').onclick = pantallaCompleta;
    document.getElementById('tutPlay').onclick = alternar;
    document.getElementById('tutMudo').onclick = mudo;
    if (puede) {
      document.getElementById('tutEditar').onclick = function () { modoEdicion(true); };
      document.getElementById('tutCancelar').onclick = function () {
        CAPS = (elDe(ABIERTO).capitulos || []).map(function (c) {
          return { t: c.t, texto: c.texto };
        });
        modoEdicion(false);
      };
      document.getElementById('tutGuardar').onclick = guardarCaps;
      document.getElementById('tutMarcar').onclick = marcarAca;
    }
    engancharVideo(t);
    pintarCaps();
    dibujarLinea();
  }

  function engancharVideo(t) {
    var v = video();
    if (!v) return;
    v.addEventListener('loadedmetadata', function () {
      dibujarLinea();
      var d = document.getElementById('tutDur');
      if (d) d.textContent = reloj(v.duration);
      /* la duración se guarda la primera vez que alguien lo abre: así la lista
         la puede mostrar sin tener que bajar cada video */
      if (central() && !t.duracion && isFinite(v.duration) && v.duration > 0) {
        var copia = LISTA.map(function (x) {
          return x.id === t.id
            ? Object.assign({}, x, { duracion: Math.round(v.duration) }) : x;
        });
        guardar(copia).catch(function () {});
      }
    });
    v.addEventListener('timeupdate', alCorrer);
    v.addEventListener('seeked', alCorrer);
    v.addEventListener('play', pintarPlay);
    v.addEventListener('pause', pintarPlay);
    v.addEventListener('ended', pintarPlay);
    /* tocar el video lo arranca y lo para, como en cualquier reproductor */
    v.addEventListener('click', alternar);
    pintarPlay();
  }

  /* Teclas, mientras se está mirando un tutorial: espacio arranca y para, las
     flechas mueven cinco segundos. ⚠️ No cuando el foco está en un campo: si
     no, escribir el texto de un capítulo pausaría el video en cada espacio. */
  document.addEventListener('keydown', function (ev) {
    var v = video();
    if (!v || !ABIERTO) return;
    var d = document.activeElement;
    if (d && (d.tagName === 'INPUT' || d.tagName === 'TEXTAREA' || d.isContentEditable)) {
      return;
    }
    if (ev.key === ' ' || ev.key === 'k') { ev.preventDefault(); alternar(); }
    else if (ev.key === 'ArrowRight') { ev.preventDefault(); v.currentTime += 5; }
    else if (ev.key === 'ArrowLeft') { ev.preventDefault(); v.currentTime -= 5; }
  });

  /* ───────────── la línea de tiempo ─────────────
     Un tramo por capítulo, con una ranura entre uno y otro. El ancho de cada
     tramo es lo que dura ese capítulo: de un vistazo se ve cuánto ocupa cada
     tema, que es justo lo que se quiere de una línea de tiempo. */
  function tramos() {
    var v = video();
    var dur = (v && isFinite(v.duration) && v.duration) ||
              (elDe(ABIERTO) || {}).duracion || 0;
    var caps = (EDIT ? CAPS : ((elDe(ABIERTO) || {}).capitulos || []))
      .slice().sort(function (a, b) { return a.t - b.t; });
    if (!dur) return { dur: 0, lista: [] };
    var puntos = caps.filter(function (c) { return c.t < dur; });
    if (!puntos.length || puntos[0].t > 0) {
      puntos = [{ t: 0, texto: '' }].concat(puntos);
    }
    var lista = puntos.map(function (c, i) {
      var fin = (i + 1 < puntos.length) ? puntos[i + 1].t : dur;
      return { desde: c.t, hasta: fin, texto: c.texto, i: i };
    });
    return { dur: dur, lista: lista };
  }

  function dibujarLinea() {
    var caja = document.getElementById('tutBarra');
    if (!caja) return;
    var d = tramos();
    if (!d.dur) { caja.innerHTML = '<div class="tut-seg" style="flex-grow:1"><i></i></div>'; return; }
    caja.innerHTML = d.lista.map(function (s) {
      var largo = Math.max(0.5, s.hasta - s.desde);
      return '<div class="tut-seg" style="flex-grow:' + largo + '" data-t="' + s.desde +
        '"' + (s.texto ? ' title="' + esc(reloj(s.desde) + ' · ' + s.texto) + '"' : '') +
        '><i></i></div>';
    }).join('');
    caja.onclick = function (ev) {
      var v = video();
      if (!v || !isFinite(v.duration)) return;
      var r = caja.getBoundingClientRect();
      var f = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width));
      v.currentTime = f * v.duration;
    };
    alCorrer();
  }

  function alCorrer() {
    var v = video();
    if (!v) return;
    var d = tramos();
    var ahora = v.currentTime || 0;
    var caja = document.getElementById('tutBarra');
    if (caja) {
      var segs = caja.querySelectorAll('.tut-seg');
      for (var i = 0; i < segs.length && i < d.lista.length; i++) {
        var s = d.lista[i];
        var largo = Math.max(0.001, s.hasta - s.desde);
        var parte = Math.min(1, Math.max(0, (ahora - s.desde) / largo));
        segs[i].firstChild.style.width = (parte * 100) + '%';
        segs[i].classList.toggle('on', ahora >= s.desde && ahora < s.hasta);
      }
    }
    var t = document.getElementById('tutAhora');
    if (t) t.textContent = reloj(ahora);
    var cual = null;
    for (var j = 0; j < d.lista.length; j++) {
      if (ahora >= d.lista[j].desde) cual = d.lista[j];
    }
    var b = document.getElementById('tutCapAhora');
    if (b) b.textContent = (cual && cual.texto) || '';
    var filas = document.querySelectorAll('#tutCaps .tut-cap');
    for (var k = 0; k < filas.length; k++) {
      filas[k].classList.toggle('on',
        cual != null && parseInt(filas[k].dataset.t, 10) === cual.desde);
    }
  }

  /* ───────────── la lista de capítulos ───────────── */
  function pintarCaps() {
    var caja = document.getElementById('tutCaps');
    if (!caja) return;
    var caps = (EDIT ? CAPS : ((elDe(ABIERTO) || {}).capitulos || []))
      .slice().sort(function (a, b) { return a.t - b.t; });
    if (!caps.length) {
      caja.innerHTML = '<p class="dt-chico">' +
        (EDIT
          ? 'Todavía no hay capítulos. Poné el video donde empieza un tema y apretá <b>+ Marcar acá</b>.'
          : 'Este tutorial todavía no tiene capítulos marcados.') + '</p>';
      return;
    }
    caja.innerHTML = caps.map(function (c, i) {
      if (EDIT) {
        return '<div class="tut-cap edit" data-t="' + c.t + '" data-i="' + i + '">' +
          '<input class="tut-t" value="' + esc(reloj(c.t)) + '" data-campo="t" ' +
            'inputmode="numeric" aria-label="Minuto">' +
          '<input class="tut-x2" value="' + esc(c.texto) + '" data-campo="texto" ' +
            'maxlength="120" placeholder="De qué habla acá">' +
          '<button type="button" class="tut-quitar" title="Quitar este capítulo">×</button>' +
          '</div>';
      }
      return '<button type="button" class="tut-cap" data-t="' + c.t + '">' +
        '<span class="tut-t">' + esc(reloj(c.t)) + '</span>' +
        '<span class="tut-x2">' + esc(c.texto) + '</span></button>';
    }).join('');
    if (EDIT) engancharEdicion(caja);
    alCorrer();
  }

  function engancharEdicion(caja) {
    var filas = caja.querySelectorAll('.tut-cap.edit');
    for (var i = 0; i < filas.length; i++) {
      (function (fila) {
        var idx = parseInt(fila.dataset.i, 10);
        var tt = fila.querySelector('[data-campo="t"]');
        var tx = fila.querySelector('[data-campo="texto"]');
        var orden = CAPS.slice().sort(function (a, b) { return a.t - b.t; });
        var cap = orden[idx];
        tt.onchange = function () {
          var n = segundos(tt.value);
          if (n === null) {
            aviso('El minuto se escribe como 3:25', 'err');
            tt.value = reloj(cap.t);
            return;
          }
          cap.t = n;
          pintarCaps(); dibujarLinea();
        };
        tx.oninput = function () { cap.texto = tx.value; };
        tx.onchange = function () { dibujarLinea(); };
        fila.querySelector('.tut-quitar').onclick = function () {
          CAPS = CAPS.filter(function (c) { return c !== cap; });
          pintarCaps(); dibujarLinea();
        };
      }(filas[i]));
    }
  }

  function modoEdicion(v) {
    EDIT = v;
    ['tutGuardar', 'tutCancelar', 'tutMarcar'].forEach(function (id) {
      var e = document.getElementById(id);
      if (e) e.hidden = !v;
    });
    var e = document.getElementById('tutEditar');
    if (e) e.hidden = v;
    pintarCaps();
    dibujarLinea();
    if (v) {
      aviso('Poné el video donde empieza un tema y apretá «+ Marcar acá»', 'ok');
    }
  }

  function marcarAca() {
    var v = video();
    if (!v) return;
    var seg = Math.floor(v.currentTime || 0);
    if (CAPS.some(function (c) { return c.t === seg; })) {
      aviso('Ya hay un capítulo en ' + reloj(seg), 'err');
      return;
    }
    CAPS.push({ t: seg, texto: '' });
    pintarCaps(); dibujarLinea();
    /* el foco va al texto del capítulo recién marcado: marcarlo y no poder
       escribir de qué habla obligaría a buscarlo con el mouse */
    var orden = CAPS.slice().sort(function (a, b) { return a.t - b.t; });
    var i = orden.findIndex(function (c) { return c.t === seg; });
    var fila = document.querySelector('#tutCaps .tut-cap.edit[data-i="' + i + '"]');
    if (fila) { var tx = fila.querySelector('[data-campo="texto"]'); if (tx) tx.focus(); }
  }

  function guardarCaps() {
    var t = elDe(ABIERTO);
    if (!t) return;
    var sinTexto = CAPS.filter(function (c) { return !String(c.texto || '').trim(); });
    if (sinTexto.length) {
      aviso('Hay ' + sinTexto.length + ' capítulo(s) sin texto: escribí de qué habla o quitalos', 'err');
      return;
    }
    var btn = document.getElementById('tutGuardar');
    btn.disabled = true; btn.textContent = 'Guardando…';
    var copia = LISTA.map(function (x) {
      return x.id === t.id ? Object.assign({}, x, { capitulos: CAPS.slice() }) : x;
    });
    guardar(copia, 'Capítulos guardados').then(function () {
      btn.disabled = false; btn.textContent = 'Guardar capítulos';
      modoEdicion(false);
    }).catch(function (e) {
      btn.disabled = false; btn.textContent = 'Guardar capítulos';
      aviso(e.message || 'No se pudo guardar', 'err');
    });
  }

  /* ⚠️ Pantalla completa sobre la CAJA, no sobre el <video>: si fuera el video,
     el navegador pone sus controles y la línea de capítulos —que es para lo que
     se hizo esto— desaparece justo cuando más se ve. */
  function pantallaCompleta() {
    var caja = document.getElementById('tutCaja');
    if (!caja) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else if (caja.requestFullscreen) {
      caja.requestFullscreen().catch(function () {
        var v = video();
        if (v && v.requestFullscreen) v.requestFullscreen();
      });
    }
  }

  /* ───────────── subir uno nuevo ───────────── */
  function abrirSubir() {
    var modal = document.getElementById('tutModal');
    if (!modal) return;
    document.getElementById('tutTitulo').value = '';
    document.getElementById('tutNota').value = '';
    document.getElementById('tutArchivo').value = '';
    var e = document.getElementById('tutSubirMal');
    if (e) { e.hidden = true; e.textContent = ''; }
    var p = document.getElementById('tutSubirPaso');
    if (p) { p.hidden = true; p.textContent = ''; }
    if (window.abrirModal) window.abrirModal(modal);
    setTimeout(function () {
      var i = document.getElementById('tutTitulo');
      if (i) i.focus();
    }, 60);
  }

  function cerrarSubir() {
    var modal = document.getElementById('tutModal');
    if (window.esconderModal) window.esconderModal(modal);
  }

  /* Cuánto dura el video, medido acá antes de subirlo: un <video> sobre un
     objectURL alcanza y evita tener que abrirlo después para saberlo. */
  function medir(file) {
    return new Promise(function (res) {
      var url = URL.createObjectURL(file);
      var v = document.createElement('video');
      v.preload = 'metadata';
      v.onloadedmetadata = function () {
        var d = isFinite(v.duration) ? Math.round(v.duration) : 0;
        try { URL.revokeObjectURL(url); } catch (e) {}
        res(d);
      };
      v.onerror = function () {
        try { URL.revokeObjectURL(url); } catch (e) {}
        res(0);
      };
      v.src = url;
    });
  }

  function subir() {
    var titulo = (document.getElementById('tutTitulo').value || '').trim();
    var nota = (document.getElementById('tutNota').value || '').trim();
    var file = (document.getElementById('tutArchivo').files || [])[0];
    var mal = document.getElementById('tutSubirMal');
    var paso = document.getElementById('tutSubirPaso');
    var decir = function (t) {
      mal.textContent = t; mal.hidden = !t;
    };
    var andando = function (t) {
      paso.textContent = t || ''; paso.hidden = !t;
    };
    if (!titulo) { decir('Ponele un nombre al tutorial.'); return; }
    if (!file) { decir('Elegí el video.'); return; }
    decir('');
    var btn = document.getElementById('tutSubir');
    btn.disabled = true;
    andando('Subiendo el video…');

    var clave = 'tut-' + Date.now().toString(36);
    var fd = new FormData();
    fd.append('key', clave);
    fd.append('file', file);
    var duracion = 0;
    medir(file).then(function (d) {
      duracion = d;
      return window.api('/api/upload-tutorial', { method: 'POST', body: fd });
    }).then(function (r) {
      if (r && r.falta_ffmpeg) {
        throw new Error('Este video hay que convertirlo y falta el compresor. ' +
          'Entrá a un módulo con video y aceptá bajarlo, o subí un mp4 más liviano.');
      }
      if (r && r.error) throw new Error(r.error);
      if (r && r.job) {
        andando('Achicando el video… 0%');
        return window.esperarJob(r.job, function (j) {
          andando('Achicando el video… ' + (j.pct || 0) + '%');
        }).then(function (j) { return j.src; });
      }
      return r.src;
    }).then(function (src) {
      andando('Guardando…');
      var nuevo = {
        id: clave, titulo: titulo, nota: nota, src: src,
        duracion: duracion, capitulos: [],
        creado: new Date().toISOString().slice(0, 10)
      };
      return guardar([nuevo].concat(LISTA), 'Tutorial subido').then(function (l) {
        return { lista: l, src: src };
      });
    }).then(function (r) {
      btn.disabled = false; andando('');
      cerrarSubir();
      /* ⚠️ El id se busca POR EL VIDEO, no se da por sentado. El servidor
         normaliza la clave —«tut-abc» le vuelve como «tut_abc»—, así que dar
         por hecha la que se mandó dejaba abierto un tutorial que no existe y
         la pantalla volvía a la lista sin decir por qué. */
      var puesto = (r.lista || []).filter(function (t) { return t.src === r.src; })[0];
      ABIERTO = puesto ? puesto.id : null;
      pintar();
    }).catch(function (e) {
      btn.disabled = false; andando('');
      decir(e.message || 'No se pudo subir el video.');
    });
  }

  /* ───────────── los clicks de la sección ───────────── */
  document.addEventListener('click', function (ev) {
    if (!ev.target.closest) return;
    var r = raiz();
    if (!r) return;
    var ver = ev.target.closest('[data-ver-tut]');
    if (ver && r.contains(ver)) {
      ABIERTO = ver.getAttribute('data-ver-tut'); EDIT = false; pintar(); return;
    }
    var x = ev.target.closest('[data-borrar-tut]');
    if (x && r.contains(x)) {
      var id = x.getAttribute('data-borrar-tut');
      var t = elDe(id);
      if (!t || !window.confirm('¿Quitar el tutorial "' + t.titulo + '"? ' +
                                'Se borra también el video.')) return;
      guardar(LISTA.filter(function (y) { return y.id !== id; }), 'Tutorial quitado')
        .then(pintar);
      return;
    }
    var cap = ev.target.closest('.tut-cap:not(.edit)');
    if (cap && r.contains(cap)) {
      var v = video();
      if (v) { v.currentTime = parseInt(cap.dataset.t, 10) || 0; v.play().catch(function () {}); }
      return;
    }
  });

  document.addEventListener('click', function (ev) {
    if (!ev.target.closest) return;
    if (ev.target.closest('[data-cerrar-tut]')) { cerrarSubir(); return; }
    if (ev.target.id === 'tutSubir') { subir(); }
  });

  /* La sección se pinta al ENTRAR, no al abrir el panel: traer la lista es un
     viaje al servidor que nadie pidió mientras mira la cartelera. */
  window.refrescarTutoriales = function () {
    if (!CARGADO) { cargar(); return; }
    pintar();
  };
}());
