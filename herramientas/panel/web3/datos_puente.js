/* ══════════════════ LA SECCION DATOS, ENCHUFADA ══════════════════
   panel_datos.js sabe DIBUJAR un tablero y no sabe de donde vienen los datos:
   recibe todo como argumento. Eso es a proposito — asi se puede probar sola,
   sin servidor, que es como se probo (57 chequeos).

   Este archivo es el unico que habla con las rutas. Maneja la LISTA de
   reportes: cada uno tiene su planilla, su nombre y su propia decision de que
   se publica. Si mañana los datos llegan de otro lado, se cambia aca y el
   tablero no se entera.
   ══════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var RAIZ = null;
  var LISTA = [];          // los reportes, como los devuelve el servidor
  var ABIERTO = null;      // el id del que se esta mirando

  function api(ruta, opciones) {
    return fetch(ruta, opciones || {}).then(function (r) {
      return r.json().catch(function () { return {}; });
    });
  }

  function post(ruta, cuerpo) {
    return api(ruta, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo || {})
    });
  }

  function aviso(texto, tipo) {
    if (window.toast) window.toast(texto, tipo || 'ok');
  }

  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* El numerito del menu contaba CUANTOS NUMEROS ESTABAN PUBLICADOS a la
     intranet. Como los reportes no se publican, ese numero no le decia nada a
     nadie: ahora muestra cuantos reportes hay conectados, que es lo que la
     persona quiere saber de un vistazo. */
  function contador(n) {
    var e = document.getElementById('navNDatos');
    if (!e) return;
    e.textContent = n || '';
    e.hidden = !n;
  }

  /* ─────────────────────── la lista de reportes ─────────────────────── */
  function traerLista() {
    return api('/api/datos/estado').then(function (r) {
      LISTA = (r && r.reportes) || [];
      contador(LISTA.length);
      return LISTA;
    });
  }

  function pintarLista(mensaje) {
    ABIERTO = null;
    var filas = LISTA.map(function (r) {
      return '<button type="button" class="dt-rep" data-id="' + esc(r.id) + '">' +
        '<span class="dt-rep-t">' + esc(r.titulo) + '</span>' +
        '<span class="dt-rep-f">' + esc(r.archivo || 'sin planilla') + '</span>' +
        /* Sin la etiqueta de publicado: un reporte de derivaciones es para
           adentro —se mira, se baja en Word o se imprime— y no va al sitio de
           los vendedores. Poner «nada publicado» en cada fila anuncia una
           función que no se usa. El dato sigue existiendo del lado del
           servidor por si algún día vuelve. */
        '<span class="dt-rep-x" data-borrar="' + esc(r.id) + '" title="Quitar este reporte">×</span>' +
        '</button>';
    }).join('');

    RAIZ.innerHTML =
      '<div class="dt-cab"><h2>Datos</h2>' +
      '<p>Cada reporte tiene su planilla. El panel la lee, la entiende y arma ' +
      'el tablero.</p></div>' +
      (mensaje ? '<div class="dt-error">' + esc(mensaje) + '</div>' : '') +
      (filas ? '<div class="dt-reps">' + filas + '</div>'
             : '<div class="dt-nada">Todavía no hay ningún reporte.</div>') +
      '<div class="dt-nuevo">' +
      '<div class="dt-nuevo-t">Agregar un reporte</div>' +
      '<div class="dt-tabs">' +
      '<button type="button" class="dt-tab on" data-tab="archivo">Un archivo de esta PC</button>' +
      '<button type="button" class="dt-tab" data-tab="google">Una planilla o documento de Google</button>' +
      '</div>' +
      '<div id="dtPanArchivo">' +
      '<div class="dt-conectar">' +
      '<input type="text" id="dtNombre" placeholder="Nombre (ej: Derivaciones)" autocomplete="off">' +
      '<input type="text" id="dtRuta" placeholder="Ruta del archivo .csv o .xlsx" autocomplete="off">' +
      '<button type="button" class="btn active" id="dtIr">Conectar</button>' +
      '</div>' +
      '<p class="dt-chico">La planilla se lee desde acá y no se copia a ningún lado. ' +
      'Los datos de clientes no salen de esta computadora.</p>' +
      '</div>' +
      '<div id="dtPanGoogle" hidden></div>' +
      '</div>';

    document.getElementById('dtIr').onclick = conectar;
    var campo = document.getElementById('dtRuta');
    if (campo) campo.onkeydown = function (e) { if (e.key === 'Enter') conectar(); };
    pintarGoogle();
  }

  /* ─────────────────────── Google ───────────────────────
     La planilla vive en Drive y tiene datos de clientes, así que NO se comparte
     por link público: el panel entra con una cuenta y la lee en privado. Todo
     pasa en esta computadora.

     Hay dos formas de conectar y la pantalla las ordena a propósito:

       LA CUENTA DEL PANEL (adelante). Google da una dirección de mail; le
       compartís el archivo desde Drive igual que a un compañero. No hay
       pantalla de permisos, no aparece el cartel de "aplicación no verificada",
       y no se vence a los siete días. Y el panel ve exactamente los archivos
       que le compartieron, ni uno más.

       OAUTH (escondido atrás de un link). Es el camino anterior. Sigue
       funcionando para quien ya lo tenga configurado.

     Por eso, con la cuenta cargada, lo más grande de la pantalla es el mail con
     un botón de copiar: es lo único que hay que hacer para cada archivo nuevo. */
  var ULTIMO = null;   // el ultimo analisis, para saber que ofrecer

  function pintarGoogle() {
    var caja = document.getElementById('dtPanGoogle');
    if (!caja) return;
    api('/api/datos/google').then(function (g) {
      if (!g || g.disponible === false) {
        caja.innerHTML = '<p class="dt-chico">No se pudo cargar la conexión con ' +
          'Google: ' + esc(g && g.error || '') + '</p>';
        return;
      }
      var cta = g.cuenta || {};
      if (cta.conectado) { conCuenta(caja, cta); return; }
      if (g.conectado) { conOauth(caja); return; }
      sinNada(caja, g);
    });
  }

  /* ── conectado con la cuenta del panel: el mail, grande ── */
  function conCuenta(caja, cta) {
    caja.innerHTML =
      '<p class="dt-chico dt-ok">La cuenta de Google del panel está cargada.</p>' +
      '<div class="dt-mail">' +
      '<div class="dt-mail-t">Compartí cada planilla o documento con esta dirección:</div>' +
      '<div class="dt-mail-fila">' +
      '<code class="dt-mail-v" id="dtMail">' + esc(cta.mail || '') + '</code>' +
      '<button type="button" class="btn" id="dtCopiar">Copiar</button>' +
      '</div>' +
      '<div class="dt-mail-p">En Drive: abrí el archivo → <b>Compartir</b> → pegá ' +
      'esta dirección → dejala en <b>Lector</b> → <b>Enviar</b>.</div>' +
      '</div>' +
      '<div id="dtLista"><div class="dt-cargando">Buscando los archivos ' +
      'que le compartiste…</div></div>' +
      '<p class="dt-chico">Solo lectura: el panel no puede modificar ni borrar ' +
      'nada de tu Drive, y solo ve los archivos que le compartas. ' +
      '<a href="#" id="dtGSalir">Quitar la cuenta</a></p>';
    pintarLista2();
    document.getElementById('dtCopiar').onclick = copiarMail;
    document.getElementById('dtGSalir').onclick = function (e) {
      e.preventDefault();
      if (!window.confirm('¿Quitar la cuenta de Google del panel? Los reportes ' +
                          'que usen archivos de Drive van a dejar de leerse.')) return;
      post('/api/datos/google-cuenta-borrar').then(function () {
        aviso('Cuenta quitada', 'ok'); pintarGoogle();
      });
    };
  }

  /* ── conectado con el camino viejo ── */
  function conOauth(caja) {
    caja.innerHTML =
      '<p class="dt-chico dt-ok">Conectado con Google (con el permiso del ' +
      'navegador). Pegá el link del archivo.</p>' +
      formLink() +
      '<p class="dt-chico">Solo lectura. ' +
      '<a href="#" id="dtGSalir">Desconectar</a></p>';
    engancharLink();
    document.getElementById('dtGSalir').onclick = function (e) {
      e.preventDefault();
      if (!window.confirm('¿Desconectar la cuenta de Google? Los reportes que ' +
                          'usen planillas de Drive van a dejar de leerse.')) return;
      post('/api/datos/google-desconectar').then(function () {
        aviso('Cuenta desconectada', 'ok'); pintarGoogle();
      });
    };
  }

  /* ── sin conectar: se ofrece la forma simple ── */
  function sinNada(caja, g) {
    var esperando = g.conectando && g.conectando.estado === 'esperando';
    var errG = g.conectando && g.conectando.estado === 'error' ? g.conectando.error : '';
    caja.innerHTML =
      (errG ? '<div class="dt-error">' + esc(errG) + '</div>' : '') +
      /* Primero el camino de cero configuración. Si la planilla está en
         «cualquiera con el link», Google la deja bajar sin credenciales y esto
         funciona en el acto: es la diferencia entre usar el panel hoy o usarlo
         cuando alguien termine un trámite en Google Cloud.
         Lo que NO se hace es usarlo sin decirlo — el aviso de abajo está para
         que quede claro que «con el link» significa cualquiera. */
      '<p class="dt-chico"><b>Si la planilla está compartida por link</b>, ' +
      'pegalo acá y listo: no hace falta configurar nada.</p>' +
      formLink() +
      '<p class="dt-chico dt-ojo">⚠️ «Cualquier persona con el link» es literal: ' +
      'no hace falta estar invitado ni tener cuenta de Google. Si la planilla ' +
      'tiene nombre, teléfono o mail de clientes, conviene la forma privada de ' +
      'acá abajo — y en Drive, sacarle el «cualquiera con el link».</p>' +
      '<div class="dt-corte"><span>para leer planillas privadas</span></div>' +
      '<p class="dt-chico">El panel entra con una cuenta propia, como entraría ' +
      'una persona. Google te da un archivo <b>.json</b> una sola vez; está ' +
      'explicado paso a paso en <b>COMO-CONECTAR-DRIVE.md</b>.</p>' +
      '<div class="dt-suelta" id="dtSuelta">' +
      '<textarea id="dtCJson" rows="3" spellcheck="false" ' +
      'placeholder="Arrastrá acá el archivo .json, o pegá su contenido"></textarea>' +
      '<div class="dt-suelta-b">' +
      '<label class="btn" for="dtCFile">Elegir el archivo…</label>' +
      '<input type="file" id="dtCFile" accept=".json,application/json" hidden>' +
      '<button type="button" class="btn active" id="dtCGuardar">Guardar la cuenta</button>' +
      '</div></div>' +
      '<p class="dt-chico dt-otra"><a href="#" id="dtVerOauth">Conectar de la otra ' +
      'forma (con el navegador)</a></p>' +
      '<div id="dtOauth" hidden>' +
      '<p class="dt-chico">Este camino usa un cliente de OAuth. Google avisa que ' +
      'la aplicación no está verificada, y mientras el proyecto esté en prueba el ' +
      'permiso se vence cada 7 días.</p>' +
      '<div class="dt-conectar">' +
      '<input type="text" id="dtGCid" placeholder="ID de cliente (…apps.googleusercontent.com)" autocomplete="off">' +
      '<input type="text" id="dtGSec" placeholder="Clave secreta (si Google te dio una)" autocomplete="off">' +
      '<button type="button" class="btn" id="dtGConn"' + (esperando ? ' disabled' : '') +
      '>' + (esperando ? 'Esperando…' : 'Conectar con el navegador') + '</button>' +
      '</div>' +
      (esperando ? '<p class="dt-chico">Se abrió el navegador. Entrá con la cuenta ' +
        'donde está la planilla y aceptá.</p>' : '') +
      '</div>';

    engancharLink();
    document.getElementById('dtCGuardar').onclick = guardarCuenta;
    document.getElementById('dtCFile').onchange = function () {
      leerArchivo(this.files && this.files[0]);
    };
    arrastrar(document.getElementById('dtSuelta'));

    var ver = document.getElementById('dtVerOauth');
    ver.onclick = function (e) {
      e.preventDefault();
      var d = document.getElementById('dtOauth');
      d.hidden = !d.hidden;
      ver.textContent = d.hidden ? 'Conectar de la otra forma (con el navegador)'
                                 : 'Esconder la otra forma';
    };
    if (esperando || errG) {               // si el baile esta en curso, mostrarlo
      document.getElementById('dtOauth').hidden = false;
      ver.textContent = 'Esconder la otra forma';
    }
    var b = document.getElementById('dtGConn');
    if (b && !esperando) b.onclick = arrancarGoogle;
    if (esperando) setTimeout(pintarGoogle, 2000);   // ver cómo viene
  }

  /* ── la lista de archivos: se elige, no se pega ──
     Pegar un link es hacer de cartero: se puede pegar el de la pestaña
     equivocada, el de un archivo parecido, o el de uno al que el panel no tiene
     acceso — y recién se ve el error al final.

     La lista además contesta sola la pregunta que más se hace acá: «¿lo
     compartí bien?». Si está en la lista, sí. Si no está, falta compartirlo.
     Igual queda la caja del link abajo, porque a veces uno tiene el link a mano
     y no el archivo en la cabeza. */
  function pintarLista2(buscar) {
    var caja = document.getElementById('dtLista');
    if (!caja) return;
    api('/api/datos/google-archivos' + (buscar ? '?buscar=' + encodeURIComponent(buscar) : ''))
      .then(function (r) {
        if (!r || r.error) {
          caja.innerHTML = '<div class="dt-error">' + esc((r && r.error) || 'no pude leer la lista') + '</div>' +
            verLink(true);
          engancharTodo();
          return;
        }
        var a = r.archivos || [];
        caja.innerHTML =
          '<div class="dt-buscar-f">' +
          '<input type="text" id="dtBuscar" placeholder="Buscar por nombre" ' +
          'autocomplete="off" value="' + esc(buscar || '') + '">' +
          '<span class="dt-chico">' + (a.length ? a.length + (a.length === 1 ? ' archivo' : ' archivos') : '') + '</span>' +
          '</div>' +
          (a.length ? '<div class="dt-arch">' + a.map(fila).join('') + '</div>'
                    : vacio(buscar)) +
          verLink(false);
        engancharTodo();
      });
  }

  function fila(f) {
    return '<button type="button" class="dt-arch-i" data-link="' + esc(f.link) + '" ' +
      'data-nombre="' + esc(f.nombre) + '">' +
      '<span class="dt-arch-q">' + esc(f.que_es) + '</span>' +
      '<span class="dt-arch-n">' + esc(f.nombre) + '</span>' +
      '<span class="dt-arch-f">' + esc(f.cuando) + '</span>' +
      '</button>';
  }

  function vacio(buscar) {
    if (buscar) {
      return '<div class="dt-nada">Ningún archivo compartido se llama así.</div>';
    }
    // El caso de recién empezar. No es un error: es el paso que falta, y hay
    // que decir cuál es en vez de dejar un vacío.
    return '<div class="dt-nada">Todavía no le compartiste ningún archivo. ' +
      'Copiá la dirección de arriba, abrí la planilla en Drive, tocá ' +
      '<b>Compartir</b> y pegala como <b>Lector</b>. Después volvé acá.</div>';
  }

  function verLink(abierto) {
    return '<p class="dt-chico dt-otra"><a href="#" id="dtVerLink">' +
      (abierto ? 'Esconder' : 'O pegar el link a mano') + '</a></p>' +
      '<div id="dtCajaLink"' + (abierto ? '' : ' hidden') + '>' + formLink() + '</div>';
  }

  function engancharTodo() {
    engancharLink();
    var b = document.getElementById('dtBuscar');
    if (b) {
      var t;
      b.oninput = function () {
        // Se espera a que deje de escribir: una consulta por tecla le pega a
        // Google diez veces para buscar una palabra.
        clearTimeout(t);
        t = setTimeout(function () { pintarLista2(b.value.trim()); }, 350);
      };
    }
    var v = document.getElementById('dtVerLink');
    if (v) {
      v.onclick = function (e) {
        e.preventDefault();
        var c = document.getElementById('dtCajaLink');
        c.hidden = !c.hidden;
        v.textContent = c.hidden ? 'O pegar el link a mano' : 'Esconder';
      };
    }
    [].forEach.call(document.querySelectorAll('.dt-arch-i'), function (el) {
      el.onclick = function () {
        conectarGoogle(el.getAttribute('data-link'), el.getAttribute('data-nombre'));
      };
    });
  }

  /* ── la caja donde se pega el link, igual en los dos casos ── */
  function formLink() {
    return '<div class="dt-conectar">' +
      '<input type="text" id="dtGNombre" placeholder="Nombre del reporte" autocomplete="off">' +
      '<input type="text" id="dtGLink" placeholder="Pegá el link de la planilla o del documento" autocomplete="off">' +
      '<button type="button" class="btn active" id="dtGIr">Conectar</button>' +
      '</div>';
  }

  function engancharLink() {
    var b = document.getElementById('dtGIr');
    // ⚠️ Envuelto en una función y NO `onclick = conectarGoogle`. Al asignar la
    // función directo, el navegador le pasa el EVENTO del clic como primer
    // argumento — que ahora es el link. El link terminaba siendo un MouseEvent
    // y el paso de elegir hoja nunca aparecía. Andaba antes porque la función
    // no tomaba parámetros y el evento caía en el vacío.
    if (b) b.onclick = function () { conectarGoogle(); };
    var c = document.getElementById('dtGLink');
    if (c) c.onkeydown = function (e) { if (e.key === 'Enter') conectarGoogle(); };
  }

  function copiarMail() {
    var m = (document.getElementById('dtMail') || {}).textContent || '';
    var listo = function () { aviso('Dirección copiada', 'ok'); };
    // El portapapeles moderno anda en 127.0.0.1 (cuenta como sitio seguro), pero
    // si el navegador lo niega igual se cae al truco viejo antes que dejar a la
    // persona copiando a mano una direccion de sesenta caracteres.
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(m).then(listo, function () { copiarViejo(m, listo); });
    } else { copiarViejo(m, listo); }
  }

  function copiarViejo(txt, listo) {
    var t = document.createElement('textarea');
    t.value = txt;
    t.style.position = 'fixed';
    t.style.opacity = '0';
    document.body.appendChild(t);
    t.select();
    try { document.execCommand('copy'); listo(); }
    catch (e) { aviso('No pude copiar. Seleccioná la dirección a mano.', 'err'); }
    document.body.removeChild(t);
  }

  /* ── el archivo .json: elegirlo o arrastrarlo ──
     Se lee acá con FileReader y viaja como texto al panel, que corre en esta
     misma PC. El archivo nunca sale de la máquina. */
  function leerArchivo(f) {
    if (!f) return;
    if (f.size > 64 * 1024) {
      aviso('Ese archivo es demasiado grande para ser el de la cuenta', 'err');
      return;
    }
    var r = new FileReader();
    r.onload = function () {
      document.getElementById('dtCJson').value = r.result || '';
      guardarCuenta();                     // ya lo eligio: no lo hagamos apretar otro boton
    };
    r.onerror = function () { aviso('No pude leer ese archivo', 'err'); };
    r.readAsText(f);
  }

  function arrastrar(caja) {
    if (!caja) return;
    ['dragenter', 'dragover'].forEach(function (ev) {
      caja.addEventListener(ev, function (e) {
        e.preventDefault(); caja.classList.add('encima');
      });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      caja.addEventListener(ev, function (e) {
        e.preventDefault(); caja.classList.remove('encima');
      });
    });
    caja.addEventListener('drop', function (e) {
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      leerArchivo(f);
    });
  }

  function guardarCuenta() {
    var txt = ((document.getElementById('dtCJson') || {}).value || '').trim();
    if (!txt) { errorCuenta('Falta el archivo de la cuenta'); return; }
    post('/api/datos/google-cuenta', { json: txt }).then(function (r) {
      if (!r || r.error) { errorCuenta((r && r.error) || 'no se pudo guardar'); return; }
      aviso('Cuenta guardada', 'ok');
      pintarGoogle();
    });
  }

  /* Los errores de este paso NO van solo al toast.
     El toast se esconde a los 3,2 segundos, y estos mensajes son instrucciones
     de 130 caracteres —"ese es el archivo de OAuth, tenes que ir a Cuentas de
     servicio"—. Leerlos lleva mas que eso, y perderlos deja a la persona
     apretando el mismo boton sin saber que cambiar. Quedan fijos hasta el
     proximo intento. */
  function errorCuenta(msg) {
    aviso(msg, 'err');
    var caja = document.getElementById('dtSuelta');
    if (!caja) return;
    var e = document.getElementById('dtCError');
    if (!e) {
      e = document.createElement('div');
      e.id = 'dtCError';
      e.className = 'dt-error';
      caja.parentNode.insertBefore(e, caja);
    }
    e.textContent = msg;
  }

  function arrancarGoogle() {
    var cid = (document.getElementById('dtGCid') || {}).value || '';
    var sec = (document.getElementById('dtGSec') || {}).value || '';
    if (!cid.trim()) { aviso('Falta el ID de cliente', 'err'); return; }
    post('/api/datos/google-conectar', {
      client_id: cid.trim(), client_secret: sec.trim()
    }).then(function (r) {
      if (r && r.error) { aviso(r.error, 'err'); return; }
      aviso('Se abrió el navegador para que aceptes', 'ok');
      setTimeout(pintarGoogle, 1200);
    });
  }

  /* ── paso 1: ¿qué hoja? ──
     Una planilla de trabajo tiene ocho pestañas y solo una es la que se busca.
     Agarrar la primera y no decir nada es la peor opción: los números salen,
     parecen razonables, y son de otra cosa. Así que se pregunta.

     Si hay una sola hoja no se pregunta nada: una pregunta con una sola
     respuesta posible es un clic al pedo. */
  function conectarGoogle(linkElegido, nombreElegido) {
    var link = linkElegido ||
      ((document.getElementById('dtGLink') || {}).value || '').trim();
    var nombre = nombreElegido ||
      ((document.getElementById('dtGNombre') || {}).value || '').trim();
    if (!link) { aviso('Falta el link del archivo', 'err'); return; }

    if (/\/document\/d\//.test(link)) { crearGoogle(link, nombre); return; }

    RAIZ.innerHTML = '<div class="dt-cargando">Mirando qué hojas tiene…</div>';
    api('/api/datos/google-hojas?link=' + encodeURIComponent(link))
      .then(function (r) {
        var h = (r && r.hojas) || [];
        // sin lista (o una sola) no hay nada que preguntar
        if (!r || r.error || h.length < 2) { crearGoogle(link, nombre); return; }
        elegirHoja(link, nombre, h);
      });
  }

  function elegirHoja(link, nombre, hojas) {
    var sirven = hojas.filter(function (h) { return h.sirve; });
    RAIZ.innerHTML =
      '<div class="dt-paso">' +
      '<button type="button" class="dt-volver" id="dtPasoVolver">← Volver</button>' +
      '<h2>¿Qué hoja querés leer?</h2>' +
      '<p class="dt-chico">Esta planilla tiene ' + hojas.length + ' hojas. ' +
      'Elegí una y el panel arma el tablero con esa. Después podés agregar las ' +
      'otras como reportes aparte.</p>' +
      '<div class="dt-hojas">' + hojas.map(filaHoja).join('') + '</div>' +
      (sirven.length < hojas.length
        ? '<p class="dt-chico">Las que están en gris no son tablas: suelen ser ' +
          'hojas de tablero, con varios cuadros sueltos. Un reporte necesita ' +
          'datos en filas y columnas.</p>' : '') +
      '</div>';
    document.getElementById('dtPasoVolver').onclick = function () {
      traerLista().then(function () { pintarLista(); });
    };
    [].forEach.call(document.querySelectorAll('.dt-hoja'), function (el) {
      if (el.disabled) return;
      el.onclick = function () {
        var gid = el.getAttribute('data-gid');
        // el gid se pega al final; si el link ya traía uno, se saca primero,
        // porque Google se queda con el que encuentra y no con el que quisimos
        var limpio = link.split('#')[0].replace(/([?&])gid=\d+&?/, '$1');
        crearGoogle(limpio + '#gid=' + gid,
                    nombre || el.getAttribute('data-nombre'));
      };
    });
  }

  function filaHoja(h) {
    var cols = (h.columnas || []).join(' · ');
    return '<button type="button" class="dt-hoja' + (h.sirve ? '' : ' no') + '"' +
      (h.sirve ? '' : ' disabled') +
      ' data-gid="' + esc(h.gid) + '" data-nombre="' + esc(h.nombre) + '">' +
      '<span class="dt-hoja-n">' + esc(h.nombre) + '</span>' +
      '<span class="dt-hoja-c">' + (h.sirve
        ? esc(h.cuantas + (h.cuantas === 1 ? ' columna: ' : ' columnas: ') + cols)
        : esc(h.motivo || 'no parece una tabla')) + '</span>' +
      (h.aviso ? '<span class="dt-hoja-a">' + esc(h.aviso) + '</span>' : '') +
      '</button>';
  }

  function crearGoogle(link, nombre) {
    RAIZ.innerHTML = '<div class="dt-cargando">Leyendo el archivo de Google…</div>';
    post('/api/datos/fuente-google', { link: link, titulo: nombre })
      .then(function (r) {
        if (!r || r.error) {
          traerLista().then(function () { pintarLista(r && r.error); });
          return;
        }
        aviso('Archivo conectado', 'ok');
        traerLista().then(function () { abrir(r.id); });
      });
  }

  function conectar() {
    var ruta = (document.getElementById('dtRuta') || {}).value || '';
    var nombre = (document.getElementById('dtNombre') || {}).value || '';
    ruta = ruta.trim().replace(/^"|"$/g, '');
    if (!ruta) { aviso('Falta la ruta del archivo', 'err'); return; }
    RAIZ.innerHTML = '<div class="dt-cargando">Leyendo la planilla…</div>';
    post('/api/datos/fuente', { ruta: ruta, titulo: nombre.trim() })
      .then(function (r) {
        if (!r || r.error) {
          traerLista().then(function () { pintarLista(r && r.error); });
          return;
        }
        aviso('Archivo conectado', 'ok');
        traerLista().then(function () { abrir(r.id); });
      });
  }

  /* ─────────────────────── un reporte abierto ─────────────────────── */
  function abrir(id) {
    ABIERTO = id;
    RAIZ.innerHTML = '<div class="dt-cargando">Leyendo la planilla…</div>';
    api('/api/datos/analizar?id=' + encodeURIComponent(id)).then(function (d) {
      if (!d || !d.ok) {
        traerLista().then(function () { pintarLista(d && d.error); });
        return;
      }
      /* Antes del tablero, el paso de reconocer y elegir. Se muestra una
         sola vez por reporte: cuando ya se eligio algo, se va derecho al
         tablero (y se puede volver desde ahi). */
      if (!(d.foco || []).length && (d.medidas || []).length) {
        descubrimiento(id, d);
        return;
      }
      tablero(id, d);
    });
  }

  /* ── lo que encontro, y despues que medir ──
     El orden importa. Preguntar «¿que queres medir?» sin haber mostrado que
     hay adentro es pedirle a alguien que elija a ciegas: la planilla la cargan
     ocho personas y nadie se acuerda de memoria de las 18 columnas. Primero se
     muestra lo que se detecto —una tarjeta por columna, con su tipo y sus
     valores mas frecuentes— y recien ahi la pregunta tiene de que agarrarse. */
  function descubrimiento(id, d) {
    var an = d.analisis || {};
    var cols = an.columnas || [];
    var conCliente = cols.filter(function (c) { return c.sensible; }).length;
    var meds = d.medidas || [];
    var elegidas = {};
    // ⚠️ Si ya hay una eleccion guardada, gana esa. Al volver a esta pantalla
    // desde «Que se mide», mostrar las sugeridas en vez de lo que la persona
    // eligio es pisarle la decision sin avisar: parece que no se guardo nada.
    var yaElegido = d.foco_guardado || [];
    if (yaElegido.length) {
      yaElegido.forEach(function (id) { elegidas[id] = true; });
    } else {
      meds.forEach(function (m) { if (m.sugerida) elegidas[m.id] = true; });
    }

    RAIZ.innerHTML =
      '<div class="dt-paso">' +
      '<button type="button" class="dt-volver" id="dtPasoVolver">← Reportes</button>' +
      '<h2>Esto encontré en «' + esc(d.titulo || 'la planilla') + '»</h2>' +
      '<p class="dt-chico">' + miles(an.filas) + ' filas · ' + cols.length +
      ' columnas' +
      (conCliente ? ' · <b class="dt-rojo">' + conCliente +
        (conCliente === 1 ? ' con datos de clientes' : ' con datos de clientes') +
        '</b>' : '') + '</p>' +
      '<div class="dt-detect">' + cols.map(tarjetaCol).join('') + '</div>' +

      '<div class="dt-corte"><span>y ahora</span></div>' +
      '<h2>¿Qué querés medir?</h2>' +
      '<p class="dt-chico">' + (yaElegido.length
        ? 'Están marcadas las que elegiste. Cambiá lo que quieras.'
        : 'Elegí lo que el reporte tiene que responder. Marqué algunas para ' +
          'empezar.') + ' Lo que no elijas no se pierde: queda más abajo en el ' +
      'tablero.</p>' +
      '<div class="dt-medidas">' + meds.map(function (m) {
        return filaMedida(m, !!elegidas[m.id]);
      }).join('') + '</div>' +
      '<div class="dt-paso-b">' +
      '<button type="button" class="btn active" id="dtArmar">Armar el reporte</button>' +
      '<button type="button" class="dt-volver" id="dtTodo">o mostrarme todo</button>' +
      '</div></div>';

    document.getElementById('dtPasoVolver').onclick = function () {
      traerLista().then(function () { pintarLista(); });
    };
    document.getElementById('dtArmar').onclick = function () {
      var ids = [].filter.call(
        document.querySelectorAll('.dt-medida input:checked'),
        function () { return true; }).map(function (i) { return i.value; });
      if (!ids.length) { aviso('Elegí al menos una, o tocá «mostrarme todo»', 'err'); return; }
      guardarFoco(id, ids, d);
    };
    // «todo» es una eleccion valida: se guarda igual, para no volver a preguntar
    document.getElementById('dtTodo').onclick = function () {
      guardarFoco(id, meds.map(function (m) { return m.id; }), d);
    };
  }

  function tarjetaCol(c) {
    var t = c.tipo, badge = ETIQ[t] || t, extra = '';
    if (c.sensible) {
      extra = 'No se publica nunca';
    } else if (t === 'fecha') {
      extra = (c.desde || '') + ' → ' + (c.hasta || '');
    } else if (c.grupos && c.grupos.length) {
      extra = c.grupos.slice(0, 3).map(function (g) {
        return esc(g.etiqueta) + ' ' + miles(g.cuenta);
      }).join(' · ');
    } else if (c.valores && c.valores.length) {
      extra = c.valores.slice(0, 3).map(function (v) {
        return esc(String(v.valor).slice(0, 22)) + ' ' + miles(v.cuenta);
      }).join(' · ');
    } else {
      extra = miles(c.distintos) + ' distintos';
    }
    var vacias = c.vacios ? (' · ' + miles(c.vacios) + ' vacías') : '';
    return '<div class="dt-dt' + (c.sensible ? ' cli' : '') + '">' +
      '<div class="dt-dt-h"><span class="dt-dt-n">' + esc(c.nombre || '(sin nombre)') +
      '</span><span class="dt-dt-t">' + esc(badge) + '</span></div>' +
      '<div class="dt-dt-c">' + miles(c.llenos) + ' cargadas' + vacias + '</div>' +
      '<div class="dt-dt-e">' + extra + '</div></div>';
  }

  var ETIQ = {
    fecha: 'Fecha', categoria: 'Lista', numero: 'Número',
    motivo: 'Texto repetido', contacto: 'Cliente', libre: 'Texto libre'
  };

  function filaMedida(m, marcada) {
    return '<label class="dt-medida' + (m.aviso ? ' ojo' : '') + '">' +
      '<input type="checkbox" value="' + esc(m.id) + '"' +
      (marcada ? ' checked' : '') + '>' +
      '<span class="dt-medida-t">' + esc(m.titulo) + '</span>' +
      '<span class="dt-medida-d">' + esc(m.detalle) + '</span>' +
      (m.aviso ? '<span class="dt-medida-a">' + esc(m.aviso) + '</span>' : '') +
      '</label>';
  }

  function guardarFoco(id, ids, d) {
    RAIZ.innerHTML = '<div class="dt-cargando">Armando el reporte…</div>';
    post('/api/datos/foco', { id: id, foco: ids }).then(function () {
      d.foco = ids;
      tablero(id, d);
    });
  }

  /* Lo elegido, primero. NO se saca nada: el resto queda abajo, en el mismo
     orden que tenia. Una eleccion que borra columnas obliga a rehacerla cada
     vez que alguien quiere mirar otra cosa; una que ordena, no. */
  function ordenarPorFoco(an, foco, medidas) {
    if (!an || !an.columnas || !(foco || []).length) return an;
    var quiero = {};
    (medidas || []).forEach(function (m) {
      if (foco.indexOf(m.id) < 0) return;
      // el id trae los indices de columna: "conteo:9", "cruce:3:7"
      String(m.id).split(':').slice(1).forEach(function (x) { quiero[x] = true; });
    });
    if (!Object.keys(quiero).length) return an;
    var elegidas = [], resto = [];
    an.columnas.forEach(function (c) {
      (quiero[String(c.i)] ? elegidas : resto).push(c);
    });
    var copia = {};
    for (var k in an) { if (an.hasOwnProperty(k)) copia[k] = an[k]; }
    copia.columnas = elegidas.concat(resto);
    return copia;
  }

  /* ── los vendedores que el panel no ubica ──
     Aparecen vendedores nuevos todos los meses y sucursales nuevas cada tanto
     (Pilar ya está, North Delta viene). Un mapa escrito a mano nace vencido: la
     versión anterior no conocía 5 nombres y sus 71 derivaciones desaparecían
     del corte por sucursal sin que nadie se enterara.

     Así que se pregunta. Una vez por nombre, y nunca más. */
  function pedirVendedores(id, d) {
    (function () {
      if (!d || !d.sin_ubicar) return;
      var nombres = Object.keys(d.sin_ubicar);
      if (!nombres.length) return;
      nombres.sort(function (a, b) { return d.sin_ubicar[b] - d.sin_ubicar[a]; });
      var sucs = d.sucursales_conocidas || [];
      var caja = document.createElement('div');
      caja.className = 'dt-vend';
      caja.innerHTML =
        '<div class="dt-vend-t">Hay ' + nombres.length + ' vendedor' +
        (nombres.length === 1 ? '' : 'es') + ' sin sucursal. Sus ' +
        miles(nombres.reduce(function (a, n) { return a + d.sin_ubicar[n]; }, 0)) +
        ' derivaciones no entran en el corte por sucursal.</div>' +
        '<div class="dt-vend-l">' + nombres.map(function (n) {
          return '<label class="dt-vend-i"><span>' + esc(n.charAt(0) + n.slice(1).toLowerCase()) +
            '<b>' + miles(d.sin_ubicar[n]) + '</b></span>' +
            '<select data-vend="' + esc(n) + '"><option value="">¿cuál?</option>' +
            sucs.map(function (x) {
              return '<option value="' + esc(x) + '">' + esc(x) + '</option>';
            }).join('') + '<option value="__nueva">otra sucursal…</option></select></label>';
        }).join('') + '</div>' +
        '<button type="button" class="btn active" id="dtVendOk">Guardar</button>';
      var cuerpo = document.getElementById('datosCuerpo');
      cuerpo.parentNode.insertBefore(caja, cuerpo);

      caja.addEventListener('change', function (ev) {
        if (ev.target.value !== '__nueva') return;
        var otra = window.prompt('¿Cómo se llama la sucursal?');
        if (otra && otra.trim()) {
          var o = document.createElement('option');
          o.value = o.textContent = otra.trim();
          ev.target.insertBefore(o, ev.target.lastChild);
          ev.target.value = otra.trim();
        } else { ev.target.value = ''; }
      });
      document.getElementById('dtVendOk').onclick = function () {
        var asig = {};
        [].forEach.call(caja.querySelectorAll('select'), function (sel) {
          if (sel.value && sel.value !== '__nueva') asig[sel.getAttribute('data-vend')] = sel.value;
        });
        if (!Object.keys(asig).length) { aviso('Elegí al menos una sucursal', 'err'); return; }
        post('/api/datos/vendedores', { asignaciones: asig }).then(function (r) {
          if (!r || r.error) { aviso((r && r.error) || 'no se pudo', 'err'); return; }
          aviso('Guardado', 'ok');
          abrir(id);                       // recargar con el mapa nuevo
        });
      };
    })();
  }

  function miles(n) {
    var x = Number(n);
    if (!isFinite(x)) return String(n == null ? '' : n);
    return x.toLocaleString('es-AR');
  }

  /* Qué es esta planilla, para el encabezado del tablero.
     El reconocimiento es del servidor (derivaciones.es_derivaciones); acá
     sólo se traduce a lo que la pantalla dibuja. Una planilla que nadie
     reconoció devuelve null y la sección no existe: es mejor no decir nada
     que decir "1.477 filas" como si fuera un logro. */
  function identidadDe(d) {
    var r = d && d.derivaciones;
    if (!d || !d.es_derivaciones || !r || !r.consultas) return null;
    return {
      que: 'Planilla de derivaciones',
      /* el período ya viene escrito del servidor, con la misma función que
         la portada del reporte: acá no se traduce ningún mes */
      cuando: r.periodo || '',
      cifras: [
        { n: r.consultas, r: 'consultas',
          ayuda: 'Una fila de la planilla es una consulta.' },
        { n: r.derivaciones, r: 'derivaciones',
          ayuda: 'Las consultas que llegaron a un vendedor. Es el número de marketing.' },
        { n: r.ventas, r: 'ventas',
          ayuda: 'Respuesta Final dice «Realizó la compra». Vale derivadas y no derivadas.' }
      ],
      /* Por qué estos tres no tienen interruptor: no son lecturas. Salen de
         lo que el equipo explicó que significa la planilla, no de mirar las
         columnas, y el lugar donde se publican es el reporte con diseño. */
      nota: 'Estos tres salen de lo que el equipo explicó que significa la planilla, '
        + 'no de leer las columnas. El reporte con diseño está en «Ver reporte».'
    };
  }

  function tablero(id, d) {
      ULTIMO = d;
      barra(d);
      var caja = document.getElementById('datosCuerpo');
      /* ⚠️ Los nombres son los que espera panel_datos.js —`alCambiar`,
         `alArreglar`— y no los que me resultaban cómodos. Esa pieza está
         probada contra estos nombres y no se toca desde acá. */
      window.pintarDatos(caja, {
        analisis: ordenarPorFoco(d.analisis, d.foco, d.medidas),
        avisos: d.avisos_lectura && d.avisos_lectura.length
          ? d.revision.concat([]) : d.revision,
        lecturas: d.lecturas,
        publicados: d.publicados || [],
        identidad: identidadDe(d),
        alCambiar: function (ids) { guardarPublicados(id, ids); },
        alArreglar: function (av) {
          /* Todavía no se puede abrir la planilla en la fila exacta: sería
             lanzar Excel desde el panel y eso depende de cada máquina. Por
             ahora se dice dónde está para poder ir a buscarla. */
          var filas = (av && av.filas) || [];
          aviso(filas.length
            ? 'Está en las filas: ' + filas.slice(0, 12).join(', ')
            : 'Ese aviso no apunta a filas puntuales', 'ok');
        }
      });
  }

  /* Lo que se publica se guarda en cuanto se toca un interruptor. Nada de
     "acordate de guardar": el que se olvida termina publicando de menos, o
     creyendo que publicó algo que no. */
  /* ⚠️ El fallo TIENE que avisarse. Antes, si el servidor no guardaba, este
     .then no hacía nada: el interruptor quedaba prendido en pantalla y la
     persona se iba creyendo que ese número iba a salir a la intranet —o que
     ya no salía—, cuando en el disco seguía como estaba. */
  function guardarPublicados(id, ids) {
    return post('/api/datos/publicados', { id: id, publicados: ids || [] })
      .then(function (r) {
        if (r && r.ok) { traerLista(); return r; }   // se actualiza el contador
        aviso((r && r.error) || 'No se pudo guardar. Probá de nuevo.', 'err');
        return r;
      }, function (e) {
        aviso('No se pudo guardar: ' + ((e && e.message) || 'sin conexión'), 'err');
      });
  }

  function barra(d) {
    var cuando = d.cuando ? (' · leída ' + d.cuando) : '';
    var cache = d.desde_cache ? ' (de la copia guardada)' : '';
    RAIZ.innerHTML =
      '<div class="dt-barra">' +
      '<button type="button" class="dt-volver" id="dtVolver">‹ Reportes</button>' +
      /* el <b> y el <span> son bloques distintos: en una sola línea el título
         quedaba pegado al origen ("DerivacionesPlanilla de Google") */
      '<div class="dt-barra-t"><b>' + esc(d.titulo || 'Reporte') + '</b>' +
      '<span>' + esc((d.origen || '') + cuando + cache) + '</span></div>' +
      '<div class="dt-barra-b">' +
      '<button type="button" class="dt-volver" id="dtMedir">Qué se mide</button>' +
      ((d.es_derivaciones)
        ? '<button type="button" class="btn active" id="dtDeck">Ver reporte</button>'
        : '') +
      '<button type="button" class="btn" id="dtWord">Descargar Word</button>' +
      '<button type="button" class="btn" id="dtPdf">Imprimir a PDF</button>' +
      '</div></div><div id="datosCuerpo"></div>';
    document.getElementById('dtVolver').onclick = function () {
      traerLista().then(function () { pintarLista(); });
    };
    var bm = document.getElementById('dtMedir');
    // Volver a elegir: se re-lee el analisis para que las propuestas salgan de
    // la planilla COMO ESTA HOY. Si la planilla cambio, las opciones cambian.
    if (bm) bm.onclick = function () {
      var id = ABIERTO;
      RAIZ.innerHTML = '<div class="dt-cargando">Leyendo la planilla…</div>';
      api('/api/datos/analizar?id=' + encodeURIComponent(id)).then(function (d2) {
        if (!d2 || !d2.ok) { abrir(id); return; }
        d2.foco_guardado = d2.foco || [];  // para marcar lo que ya se eligio
        d2.foco = [];                      // para que muestre la pregunta
        descubrimiento(id, d2);
      });
    };
    if (d.es_derivaciones) pedirVendedores(ABIERTO, d.derivaciones);
    var bd = document.getElementById('dtDeck');
    // Se abre en una pestaña y no adentro del panel: así se puede poner en
    // pantalla completa para mostrarlo, y el Ctrl+P del navegador lo saca a
    // PDF en 16:9 sin que el panel tenga que hacer nada.
    if (bd) bd.onclick = function () {
      window.open('/api/datos/deck?id=' + encodeURIComponent(ABIERTO), '_blank');
    };
    document.getElementById('dtWord').onclick = function () { descargar('word'); };
    document.getElementById('dtPdf').onclick = function () { descargar('pdf'); };
  }

  /* El Word se baja como archivo. El "PDF" abre el reporte en una pestaña y
     dispara la impresión: el PDF lo hace el navegador, que ya sabe, y así el
     panel no carga con una librería de PDF que pesaría más que todo lo demás. */
  function descargar(formato) {
    if (!ABIERTO) return;
    var base = '/api/datos/reporte?id=' + encodeURIComponent(ABIERTO) + '&formato=';
    if (formato === 'word') { window.location.href = base + 'word'; return; }
    var v = window.open(base + 'html', '_blank');
    if (!v) { aviso('El navegador bloqueó la ventana del reporte', 'err'); return; }
    v.addEventListener('load', function () {
      try { v.focus(); v.print(); } catch (e) { /* que lo imprima a mano */ }
    });
  }

  /* ─────────────────────── enganches ─────────────────────── */
  /* Pinta (o repinta) la sección entera. Lo llama el click del menú y
     también irASeccion (muro.js): así la pantalla se arma SIEMPRE que
     se entra, venga por donde venga. */
  function refrescarDatos() {
    RAIZ = document.getElementById('datosRaiz');
    if (!RAIZ) return;
    setTimeout(function () {
      traerLista().then(function () {
        if (ABIERTO) abrir(ABIERTO); else pintarLista();
      });
    }, 30);
  }
  window.refrescarDatos = refrescarDatos;

  document.addEventListener('click', function (e) {
    if (!e.target.closest) return;
    /* la entrada a la sección la maneja irASeccion (muro.js), que llama a
       refrescarDatos: acá ya no se escucha el menú, para no pintar dos veces */

    var x = e.target.closest('[data-borrar]');
    if (x && RAIZ && RAIZ.contains(x)) {
      e.stopPropagation();
      var id = x.getAttribute('data-borrar');
      var r = LISTA.filter(function (y) { return y.id === id; })[0] || {};
      var texto = 'Quitar "' + r.titulo + '"? Se pierde lo que elegiste medir; ' +
        'la planilla no se toca.';
      if (!window.confirm(texto)) return;
      post('/api/datos/borrar', { id: id }).then(function () {
        aviso('Reporte quitado', 'ok');
        traerLista().then(function () { pintarLista(); });
      });
      return;
    }

    var tab = e.target.closest('.dt-tab');
    if (tab && RAIZ && RAIZ.contains(tab)) {
      RAIZ.querySelectorAll('.dt-tab').forEach(function (t) {
        t.classList.toggle('on', t === tab);
      });
      var arch = tab.getAttribute('data-tab') === 'archivo';
      document.getElementById('dtPanArchivo').hidden = !arch;
      document.getElementById('dtPanGoogle').hidden = arch;
      return;
    }

    var fila = e.target.closest('.dt-rep');
    if (fila && RAIZ && RAIZ.contains(fila)) abrir(fila.getAttribute('data-id'));
  });

  /* el contador de la barra, apenas abre el panel */
  api('/api/datos/estado').then(function (r) {
    if (r && !r.error) contador(((r.reportes) || []).length);
  });
})();
