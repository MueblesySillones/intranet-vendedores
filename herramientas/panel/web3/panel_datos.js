/* =====================================================================
   SECCIÓN "DATOS" DEL PANEL — la pantalla (pieza D)

   Se dibuja sola: no le pide nada al servidor, recibe todo por argumento.
   Va después de app.js, igual que muro.js, y usa el mismo dialecto:
   una IIFE, var, strings de HTML y nada más. Sin frameworks ni build,
   porque el panel se distribuye como .exe y acá no hay dónde compilar.

       pintarDatos(contenedor, { analisis, avisos, lecturas, publicados })

   ---------------------------------------------------------------------
   LA FORMA DE LOS DATOS  (esto es lo que tiene que respetar quien integre)
   ---------------------------------------------------------------------

   analisis   lo que devuelve analizar() en analizador.py, tal cual:
              { filas, columnas:[{ i, nombre, tipo, llenos, vacios,
                                   distintos, sensible, valores?, grupos?,
                                   desde?, hasta?, parecidos? }] }
              o { error: "..." } si la planilla no tenía datos.

   avisos     lo que devuelve revisar() en revisor.py, tal cual:
              [{ gravedad:'grave'|'aviso'|'dato', titulo, detalle,
                 filas:[n], ejemplos:[texto] }]

   lecturas   LO DEFINE ESTA PIEZA. Cada conclusión que salió de la
              planilla, con su número YA calculado — acá no se calcula
              nada, solo se dibuja.

              id       string   único y ESTABLE para una misma planilla.
                                Es la llave del interruptor: es lo que se
                                guarda en `publicados` y lo único que
                                después viaja a la intranet.
              texto    string   la conclusión escrita, sin el número
                                adentro (el número se dibuja aparte).
              valor    number|string   el número ya calculado.
              formato  'entero'|'decimal'|'porcentaje'|'texto'   (def. 'entero')
              unidad   string   opcional, el pie del número ("derivaciones").
              forma    'numero'|'corte'|'ranking'|'tabla'   cómo se dibuja
                                (def. 'numero').
              corte    [{ etiqueta, valor }]   obligatorio si forma no es
                                'numero'. Viene YA recortado: se dibuja
                                entero, para que lo que se ve y lo que se
                                publica sean exactamente lo mismo.
              columna  string | [string] | null   nombre EXACTO de la o
                                las columnas de `analisis` de las que sale.
                                null / ausente = no sale de ninguna columna
                                (por ejemplo, la cuenta de filas).
              sobre    number   sobre cuántas filas se calculó.
              seguro   bool     false = no se pudo calcular con certeza
                                (def. true).
              publicable bool   false = se puede mirar pero no se publica,
                                por un motivo que no es la certeza (def. true).
              porque   string   por qué no. Obligatorio si `seguro` o
                                `publicable` son false.

              Se aceptan además los nombres que ya usa lecturas.py (pieza A),
              que se escribió en paralelo: `columnas` por `columna`, `base`
              por `sobre`, `apto_publicar` por `publicable` y
              `motivo_no_apto` por `porque`. La forma canónica es la de
              arriba; los otros nombres se traducen al entrar.

   publicados LO DEFINE ESTA PIEZA. Un ARRAY de `id` de lectura:

                  ['planilla.filas', 'sucursal.reparto']

              Array y no Set porque tiene que poder guardarse en JSON tal
              cual, sin convertir, cuando el coordinador lo mande a
              persistir. Se acepta también un Set o un objeto {id:true}
              por comodidad, pero lo que sale de acá es siempre un array.
              Un id que no corresponde a ninguna lectura PUBLICABLE se
              ignora y no se cuenta: así una planilla nueva no arrastra
              permisos de la anterior.

   identidad  OPCIONAL. Qué es esta planilla, para quien la reconoció.
              La pieza no reconoce nada: dibuja lo que le pasan.

              { que:    'Planilla de derivaciones',
                cuando: 'Enero 2026 — Agosto 2026',
                cifras: [{ n:7081, r:'consultas', ayuda:'una fila = una consulta' }],
                nota:   'de dónde salen estos números' }

              Sin `cifras` la sección no se dibuja. Estos números NO tienen
              interruptor: no son para publicar, son para saber qué se está
              mirando antes de decidir nada.

   Además, opcionales, los dos enganches con el resto del panel:
              alCambiar(idsPublicados, { id, prendido })
              alArreglar(aviso, fila)      fila puede ser null

   Devuelve { publicados(), cuenta(), volverAPintar(datos) }.
   ===================================================================== */
(function () {
  'use strict';

  /* ---------------------------------------------------------------
     Utilidades. Todo local: la pieza tiene que poder correr suelta,
     sin app.js al lado, porque así se prueba.
     --------------------------------------------------------------- */
  var ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/[&<>"']/g, function (c) { return ESCAPES[c]; });
  }

  /* Los puntos de mil a mano. El panel se abre con el navegador que haya
     en la PC del local, y toLocaleString('es-AR') no devuelve lo mismo en
     todos: con esto 1802 es "1.802" siempre. */
  function miles(n) {
    var neg = n < 0, s = String(Math.abs(Math.round(n))), r = '', i;
    for (i = 0; i < s.length; i++) {
      if (i && (s.length - i) % 3 === 0) r += '.';
      r += s.charAt(i);
    }
    return (neg ? '-' : '') + r;
  }

  /* El número escrito. NO redondea de más: si viene entero no se le
     inventa una coma, y si viene con decimales se muestra uno solo.
     Un número que se ve más preciso de lo que es engaña igual que uno
     mal calculado. */
  function numeroEscrito(lec) {
    var f = lec.formato, v = lec.valor, n, uno, ent, dec;
    if (f === 'texto') return String(v === null || v === undefined ? '—' : v);
    n = typeof v === 'number' ? v : parseFloat(String(v).replace(',', '.'));
    if (!isFinite(n)) return String(v === null || v === undefined ? '—' : v);
    /* Sin formato declarado se mira el número: si trae decimales, se
       muestran. Redondear 57,9 a 58 porque nadie declaró el formato es
       inventar precisión que no está, y encima para el otro lado. */
    if (!f) f = (n % 1 === 0) ? 'entero' : 'decimal';
    if (f === 'entero') return miles(n);
    uno = Math.round(n * 10) / 10;
    if (uno % 1 === 0) { dec = ''; ent = miles(uno); }
    else {
      dec = ',' + (Math.abs(Math.round(uno * 10)) % 10);
      ent = (uno < 0 ? '-' : '') + miles(Math.floor(Math.abs(uno)));
    }
    return ent + dec + (f === 'porcentaje' ? '%' : '');
  }

  /* Íconos dibujados, no emoji: el emoji es lo único de color que hay y
     rompe la paleta. Mismo criterio que el resto del panel. */
  var ICO = {
    candado: '<svg viewBox="0 0 24 24"><rect x="4.5" y="10.3" width="15" height="10.2" rx="2.2"/>' +
      '<path d="M8 10.3V7.4a4 4 0 0 1 8 0v2.9"/></svg>',
    alerta: '<svg viewBox="0 0 24 24"><path d="M12 3.6 21.2 20H2.8z"/>' +
      '<path d="M12 10v4"/><path d="M12 17.2v.1"/></svg>',
    ojo: '<svg viewBox="0 0 24 24"><path d="M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12z"/>' +
      '<circle cx="12" cy="12" r="3"/></svg>',
    flecha: '<svg viewBox="0 0 24 24"><path d="M5 12h13"/><path d="m13 6 6 6-6 6"/></svg>'
  };

  /* Cómo se llama cada tipo del analizador para alguien de marketing.
     "categoria" no le dice nada a nadie; "lista" sí. */
  var TIPOS = {
    fecha:     { t: 'Fecha',   d: 'sirve para la línea de tiempo' },
    categoria: { t: 'Lista',   d: 'valores que se repiten: de acá salen los cortes' },
    numero:    { t: 'Número',  d: 'se puede sumar y promediar' },
    contacto:  { t: 'Cliente', d: 'nombre, teléfono o mail' },
    motivo:    { t: 'Motivo',  d: 'escrito a mano, hay que agrupar antes de contar' },
    libre:     { t: 'Texto',   d: 'casi no se repite, no se cuenta' }
  };

  /* Los cuatro colores de la intranet, rotando. Los define .doc-preview,
     así que solo valen adentro de la vista previa. */
  var COLORES = ['--c-hudson', '--c-caba', '--c-canning', '--c-norcenter'];

  /* ---------------------------------------------------------------
     QUÉ SE PUEDE PUBLICAR Y QUÉ NO
     --------------------------------------------------------------- */
  function mapaCols(an) {
    var m = {}, cs = (an && an.columnas) || [], i;
    for (i = 0; i < cs.length; i++) m[cs[i].nombre] = cs[i];
    return m;
  }

  /* Traduce los nombres de campo de lecturas.py a los de acá. Se hace una
     sola vez, al entrar, y no se toca el objeto que mandaron: la pieza A ya
     tiene su test pasando y no hay por qué pedirle que se renombre. */
  function normalizarLectura(l) {
    var n = {}, k;
    for (k in l) if (Object.prototype.hasOwnProperty.call(l, k)) n[k] = l[k];
    if (n.columna === undefined && n.columnas !== undefined) n.columna = n.columnas;
    if (n.sobre === undefined && n.base !== undefined) n.sobre = n.base;
    if (n.publicable === undefined && n.apto_publicar !== undefined) {
      n.publicable = n.apto_publicar;
    }
    if (!n.porque && n.motivo_no_apto) n.porque = n.motivo_no_apto;
    return n;
  }

  function columnasDe(lec) {
    var c = lec.columna;
    if (c === null || c === undefined || c === '') return [];
    return Object.prototype.toString.call(c) === '[object Array]' ? c : [c];
  }

  /* Devuelve null si la lectura se puede publicar, o el motivo por el que
     NO. Un motivo distinto de null significa que no se dibuja interruptor:
     ni prendido ni apagado, no existe.

     ⚠️ Una columna que la lectura nombra y que NO está en el análisis
     también traba. Es un error de la pieza que arma las lecturas, y ante la
     duda gana "no se publica": marcar de más cuesta un chequeo, marcar de
     menos cuesta el teléfono de un cliente en una página pública. Es el
     mismo criterio con el que analizador.py decide qué es contacto. */
  function trabaDe(lec, cols) {
    var ns, i, c;
    if (lec.seguro === false) {
      return { clase: 'incierto',
               texto: lec.porque || 'no se pudo calcular con certeza' };
    }
    if (lec.sensible === true) {
      return { clase: 'trabado', texto: 'tiene datos de clientes' };
    }
    /* Se calculó bien, se puede mirar, pero no sale. Es distinto de "no se
       pudo calcular": el número está y es correcto. */
    if (lec.publicable === false) {
      return { clase: 'trabado', texto: lec.porque || 'no puede publicarse' };
    }
    ns = columnasDe(lec);
    for (i = 0; i < ns.length; i++) {
      c = cols[ns[i]];
      if (!c) {
        return { clase: 'trabado',
                 texto: 'sale de “' + ns[i] + '”, que no está en la planilla' };
      }
      if (c.sensible) {
        return { clase: 'trabado',
                 texto: 'sale de “' + ns[i] + '”, que tiene datos de clientes' };
      }
    }
    return null;
  }

  /* Un id de lectura entra a un selector CSS: si trae comillas o barras
     rompe el querySelector en silencio y el interruptor deja de encontrar
     su tarjeta. Se escapan, en vez de confiar en cómo los arme la pieza A. */
  function selId(id) {
    return '[data-id="' + String(id).replace(/(["\\])/g, '\\$1') + '"]';
  }

  /* Se aceptan array, Set u objeto, pero solo sobrevive lo que hoy es
     publicable. Un id viejo que quedó guardado de otra planilla no puede
     prender nada por su cuenta. */
  function normalizarPublicados(publicados, publicables) {
    var validos = {}, salida = {}, lista, i;
    for (i = 0; i < publicables.length; i++) validos[publicables[i].id] = true;
    if (!publicados) lista = [];
    else if (typeof Set === 'function' && publicados instanceof Set) {
      lista = []; publicados.forEach(function (x) { lista.push(x); });
    } else if (Object.prototype.toString.call(publicados) === '[object Array]') {
      lista = publicados;
    } else {
      lista = [];
      Object.keys(publicados).forEach(function (k) { if (publicados[k]) lista.push(k); });
    }
    for (i = 0; i < lista.length; i++) if (validos[lista[i]]) salida[lista[i]] = true;
    return salida;
  }

  /* ---------------------------------------------------------------
     1 · QUÉ ENCONTRÓ EN LA PLANILLA
     --------------------------------------------------------------- */
  function columnaHTML(c) {
    var t = TIPOS[c.tipo] || TIPOS.libre;
    var total = c.llenos + c.vacios;
    var h = '';

    h += '<article class="dt-col' + (c.sensible ? ' sensible' : '') + '">';
    h += '<div class="dt-col-h">';
    h += '<span class="dt-col-n" title="' + esc(c.nombre) + '">' + esc(c.nombre) + '</span>';
    h += '<span class="dt-tipo t-' + esc(c.tipo) + '">' + esc(t.t) + '</span>';
    h += '</div>';

    /* El candado va ARRIBA de todo lo demás, no al pie: es lo primero que
       tiene que leerse de una columna con datos de clientes. */
    if (c.sensible) {
      h += '<div class="dt-col-traba"><span class="dt-ic">' + ICO.candado + '</span>' +
        '<span>Tiene datos de clientes. <b>No se publica nunca</b>, ni agregada.</span></div>';
    }

    h += '<div class="dt-col-cif">' +
      '<span><b>' + miles(c.llenos) + '</b> cargadas</span>' +
      '<span><b>' + miles(c.distintos) + '</b> distintas</span>' +
      (c.vacios
        ? '<span class="' + (total && c.vacios > total * 0.05 ? 'flojo' : '') + '"><b>' +
          miles(c.vacios) + '</b> vacías</span>'
        : '') +
      '</div>';

    if (c.desde) {
      h += '<div class="dt-col-x">de <b>' + esc(c.desde) + '</b> a <b>' + esc(c.hasta) + '</b></div>';
    }
    /* Solo se muestran los valores de las columnas que NO son sensibles.
       En una de contacto, "los 5 más repetidos" sería una lista de
       teléfonos de clientes dibujada en pantalla. */
    if (!c.sensible && c.valores && c.valores.length) {
      h += '<ul class="dt-vals">';
      c.valores.slice(0, 5).forEach(function (v) {
        var w = Math.max(4, Math.round(v.cuenta / c.valores[0].cuenta * 100));
        h += '<li><span class="dv-t">' + esc(v.valor) + '</span>' +
          '<span class="dv-b"><i style="width:' + w + '%"></i></span>' +
          '<span class="dv-n">' + miles(v.cuenta) + '</span></li>';
      });
      h += '</ul>';
      if (c.valores.length > 5) {
        h += '<div class="dt-col-x">y ' + miles(c.valores.length - 5) +
          (c.valores.length - 5 === 1 ? ' valor más' : ' valores más') + '</div>';
      }
    }
    if (!c.sensible && c.grupos && c.grupos.length) {
      h += '<ul class="dt-vals">';
      c.grupos.slice(0, 4).forEach(function (g) {
        h += '<li><span class="dv-t">' + esc(g.etiqueta) + '</span>' +
          '<span class="dv-b"></span><span class="dv-n">' + miles(g.cuenta) + '</span></li>';
      });
      h += '</ul>';
    }
    h += '</article>';
    return h;
  }

  function seccionColumnas(an) {
    var cs = (an && an.columnas) || [];
    var sens = cs.filter(function (c) { return c.sensible; }).length;
    var h = '<section class="dt-sec"><div class="dt-sec-h">' +
      '<h3>Qué encontró en la planilla</h3><p class="muted">' +
      '<b>' + miles((an && an.filas) || 0) + '</b> filas · <b>' + miles(cs.length) +
      '</b> columnas' +
      (sens ? ' · <b class="dt-rojo">' + miles(sens) + ' con datos de clientes</b>' : '') +
      '</p></div>';
    if (!cs.length) {
      h += '<div class="vacio"><b>No se pudo leer la planilla</b><p>' +
        esc((an && an.error) || 'No trajo ninguna columna.') + '</p></div></section>';
      return h;
    }
    /* Un resumen, no un inventario. Antes esto eran 18 tarjetas y mil pixeles
       de pantalla que decian, columna por columna, lo mismo que dice esta
       linea. Quien quiere el detalle de una columna lo tiene en el tablero de
       abajo, donde ademas esta el numero que sale de ella. */
    var nombres = cs.filter(function (c) { return c.nombre; });
    h += '<div class="dt-resumen">' +
      nombres.map(function (c) {
        return '<span class="dt-rc' + (c.sensible ? ' cli' : '') + '">' +
          esc(c.nombre) + '</span>';
      }).join('') + '</div>';
    if (sens) {
      h += '<p class="dt-nota-cli">Las ' + miles(sens) + ' en rojo tienen datos de ' +
        'clientes: no se publican nunca, ni siquiera sumadas.</p>';
    }
    h += '</section>';
    return h;
  }

  /* ---------------------------------------------------------------
     2 · LO QUE ESTÁ MAL CARGADO
     --------------------------------------------------------------- */
  var GRAV = {
    grave: 'Grave', aviso: 'Para mirar', dato: 'Para saber'
  };

  function avisoHTML(a, k, hayHandler) {
    var filas = a.filas || [], ejem = a.ejemplos || [];
    var g = GRAV[a.gravedad] ? a.gravedad : 'dato';
    var h = '<article class="dt-av g-' + g + '" data-k="' + k + '">';
    h += '<div class="dt-av-h">' +
      '<span class="dt-grav g-' + g + '"><span class="dt-ic">' + ICO.alerta + '</span>' +
      esc(GRAV[g]) + '</span>' +
      '<span class="dt-av-t">' + esc(a.titulo) + '</span></div>';
    if (a.detalle) h += '<p class="dt-av-d">' + esc(a.detalle) + '</p>';
    if (ejem.length) {
      h += '<ul class="dt-ejem">' + ejem.map(function (e) {
        return '<li>' + esc(e) + '</li>';
      }).join('') + '</ul>';
    }
    if (filas.length) {
      h += '<div class="dt-av-p">' +
        '<button type="button" class="btn-txt dt-av-ver" data-k="' + k + '">' +
        (filas.length === 1 ? 'ver la fila' : 'ver las ' + miles(filas.length) + ' filas') +
        '</button>';
      if (hayHandler) {
        h += '<button type="button" class="btn btn-ghost dt-av-ir" data-k="' + k + '">' +
          'Ir a arreglarlo <span class="dt-ic">' + ICO.flecha + '</span></button>';
      }
      h += '</div>';
      /* Las filas son botones SOLO si hay a dónde ir. Un chip que parece
         apretable y no hace nada es peor que un chip quieto. */
      h += '<div class="dt-filas" hidden>' + filas.map(function (n) {
        return hayHandler
          ? '<button type="button" class="dt-fila" data-k="' + k + '" data-fila="' + esc(n) +
            '">fila ' + esc(n) + '</button>'
          : '<span class="dt-fila">fila ' + esc(n) + '</span>';
      }).join('') + '</div>';
    } else if (hayHandler) {
      h += '<div class="dt-av-p"><button type="button" class="btn btn-ghost dt-av-ir" data-k="' +
        k + '">Ir a arreglarlo <span class="dt-ic">' + ICO.flecha + '</span></button></div>';
    }
    h += '</article>';
    return h;
  }

  function seccionAvisos(avisos, hayHandler) {
    var cuenta = { grave: 0, aviso: 0, dato: 0 }, h;
    avisos.forEach(function (a) {
      if (cuenta[a.gravedad] === undefined) cuenta.dato++; else cuenta[a.gravedad]++;
    });
    h = '<section class="dt-sec"><div class="dt-sec-h"><h3>Lo que está mal cargado</h3>' +
      '<p class="muted">Un tablero sobre datos mal cargados no es inútil: es peor, ' +
      'porque se ve bien.</p></div>';
    if (!avisos.length) {
      h += '<div class="vacio"><b>No hay nada raro</b>' +
        '<p>La planilla pasó las revisiones. Los números de abajo se apoyan en datos ' +
        'que cierran.</p></div></section>';
      return h;
    }
    h += '<div class="muro-filtros dt-filtros">' +
      '<button type="button" class="mf on" data-grav="todo">Todo <b>' + avisos.length + '</b></button>' +
      (cuenta.grave ? '<button type="button" class="mf" data-grav="grave">Graves <b>' + cuenta.grave + '</b></button>' : '') +
      (cuenta.aviso ? '<button type="button" class="mf" data-grav="aviso">Para mirar <b>' + cuenta.aviso + '</b></button>' : '') +
      (cuenta.dato ? '<button type="button" class="mf" data-grav="dato">Para saber <b>' + cuenta.dato + '</b></button>' : '') +
      '</div>';
    /* Plegada de entrada. 34 avisos abiertos son seis mil pixeles de pagina
       que casi nunca se leen enteros; plegados son una linea que dice cuantos
       hay y se abre si a alguien le interesa. */
    h += '<div class="dt-avisos plegado" id="dtAvisos">' + avisos.map(function (a, k) {
      return avisoHTML(a, k, hayHandler);
    }).join('') + '</div>' +
      '<button type="button" class="dt-mas" id="dtVerAvisos">Ver los ' +
      avisos.length + '</button></section>';
    return h;
  }

  /* ---------------------------------------------------------------
     3 · EL TABLERO   +   4 · LOS INTERRUPTORES
     El número se dibuja con las clases que el panel YA usa para los
     bloques de la intranet (.m-kpis, .m-barras, .m-podio, .m-tabla),
     adentro de un .doc-preview que es el que les da los colores. Así lo
     que se ve acá es literalmente lo que se vería publicado, sin
     mantener un segundo juego de estilos que se desincroniza.
     --------------------------------------------------------------- */
  function vistaHTML(lec) {
    var corte = lec.corte || [], max = 1, h;
    corte.forEach(function (c) { max = Math.max(max, Math.abs(+c.valor || 0)); });

    if (lec.forma === 'corte') {
      return '<div class="m-barras">' + corte.map(function (c, i) {
        var w = Math.max(6, Math.round(Math.abs(+c.valor || 0) / max * 100));
        /* Sin la columna .br de los chips: el único número que se podría
           poner ahí es "% del mayor", que en la barra más larga siempre
           dice 100% y no informa nada. El largo de la barra ya es esa
           comparación, y sin la columna quedan 126px más para leerla. */
        return '<div class="ba">' +
          '<div class="bl" title="' + esc(c.etiqueta) + '">' + esc(c.etiqueta) + '</div>' +
          '<div class="bt"><div class="bf" style="width:' + w + '%;background:var(' +
          COLORES[i % COLORES.length] + ')"><span class="bn">' +
          miles(+c.valor || 0) + '</span></div></div>' +
          '</div>';
      }).join('') + '</div>';
    }
    if (lec.forma === 'ranking') {
      return '<div class="m-podio">' + corte.map(function (c, i) {
        return '<div class="pod' + (i === 0 ? ' lead' : '') + '">' +
          '<div class="rank">' + (i + 1) + '°</div>' +
          '<div class="name">' + esc(c.etiqueta) + '</div>' +
          '<div class="sales">' + miles(+c.valor || 0) + '</div>' +
          '<div class="slbl">' + esc(lec.unidad || '') + '</div>' +
          '</div>';
      }).join('') + '</div>';
    }
    if (lec.forma === 'tabla') {
      h = '<div class="m-tabla"><table><thead><tr><th>Valor</th>' +
        '<th class="num">' + esc(lec.unidad || 'Cantidad') + '</th></tr></thead><tbody>';
      corte.forEach(function (c) {
        h += '<tr><td>' + esc(c.etiqueta) + '</td><td class="num">' +
          miles(+c.valor || 0) + '</td></tr>';
      });
      return h + '</tbody></table></div>';
    }
    /* forma 'numero' — un solo KPI. La grilla de .m-kpis con un hijo queda
       en una columna y la tarjeta de afuera es la que ordena.
       El pie (.kt) va vacío a propósito: "sobre N filas" ya está al pie de
       la tarjeta, y repetido dos veces en 3 cm se leía como un error. */
    return '<div class="m-kpis"><div class="kpi">' +
      '<div class="kl">' + esc(lec.unidad || 'total') + '</div>' +
      '<div class="kv">' + esc(numeroEscrito(lec)) + '</div>' +
      '<div class="kt"></div></div></div>';
  }

  function numeroHTML(lec, traba, prendido) {
    var ancho = (lec.forma === 'corte' || lec.forma === 'tabla' || lec.forma === 'ranking');
    var h = '<article class="dt-num' +
      (traba ? ' ' + traba.clase : (prendido ? ' on' : '')) +
      (ancho ? ' ancho' : '') + '" data-id="' + esc(lec.id) + '">';

    h += '<div class="dt-num-h"><span class="dt-num-t">' + esc(lec.texto) + '</span>';
    if (!traba && prendido) h += '<span class="dt-chip pub">PUBLICADO</span>';
    if (traba && traba.clase === 'trabado') {
      h += '<span class="dt-chip lock"><span class="dt-ic">' + ICO.candado +
        '</span>NO SE PUBLICA</span>';
    }
    h += '</div>';

    /* Sin certeza no se dibuja ningún número. Uno mal calculado es peor que
       ninguno, porque se ve bien y nadie lo revisa. */
    if (traba && traba.clase === 'incierto') {
      h += '<div class="dt-num-nose"><b>No se puede calcular con certeza.</b>' +
        '<span>' + esc(traba.texto) + '</span></div>';
    } else {
      h += '<div class="dt-num-vista doc-preview">' + vistaHTML(lec) + '</div>';
    }

    h += '<div class="dt-num-p">';
    if (traba) {
      /* La regla dura: una lectura trabada NO tiene interruptor. Ni apagado.
         No se dibuja ningún <input>, así que no hay nada que prender por
         error, ni por click ni por teclado ni por un script de más arriba.
         El motivo largo ya está arriba cuando falta certeza: acá va la
         consecuencia, que es lo único que se repite en las dos situaciones. */
      h += '<span class="dt-num-traba ' + traba.clase + '"><span class="dt-ic">' +
        (traba.clase === 'incierto' ? ICO.ojo : ICO.candado) + '</span>' +
        (traba.clase === 'incierto'
          ? 'Sin certeza no hay número que publicar'
          : esc(traba.texto)) + '</span>';
    } else {
      h += '<label class="dt-sw"><input type="checkbox" class="dt-sw-i" data-id="' +
        esc(lec.id) + '"' + (prendido ? ' checked' : '') + '>' +
        '<span class="dt-sw-p" aria-hidden="true"></span>' +
        '<span class="dt-sw-t">Publicar</span></label>';
      if (lec.sobre) {
        h += '<span class="dt-num-sobre">sobre ' + miles(lec.sobre) + ' filas</span>';
      }
    }
    h += '</div></article>';
    return h;
  }

  /* =================================================================
     LO QUE ES LA PLANILLA
     Va arriba de todo y no tiene interruptores: no es algo para publicar,
     es para saber qué se está mirando. Sin esto la pantalla abría con
     "En Operador, L tiene 8,4 veces lo de C" y nunca decía que la planilla
     tenía 7.081 consultas y 3.165 derivaciones — que es lo primero que
     cualquiera quiere saber.

     Es OPCIONAL y genérica: la pieza dibuja lo que le pasan. Si nadie
     reconoció la planilla, esta sección no existe y no se nota.

         identidad: { que, cuando, cifras:[{n, r, ayuda?}], nota?, accion? }
     ================================================================= */
  function seccionIdentidad(id) {
    var h;
    if (!id || !id.cifras || !id.cifras.length) return '';
    h = '<section class="dt-id"><div class="dt-id-h">' +
      '<b>' + esc(id.que || 'Esta planilla') + '</b>' +
      (id.cuando ? '<span>' + esc(id.cuando) + '</span>' : '') + '</div>' +
      '<div class="dt-id-cifras">' +
      id.cifras.map(function (c) {
        return '<div class="dt-id-c"' +
          (c.ayuda ? ' title="' + esc(c.ayuda) + '"' : '') + '>' +
          '<b>' + esc(typeof c.n === 'number' ? miles(c.n) : c.n) + '</b>' +
          '<span>' + esc(c.r) + '</span></div>';
      }).join('') + '</div>' +
      (id.nota ? '<p class="dt-id-n">' + esc(id.nota) + '</p>' : '') +
      '</section>';
    return h;
  }

  /* Por qué una lectura no sale. Cuatro familias y no veintitrés motivos
     escritos uno por uno: veintitrés carteles distintos que dicen casi lo
     mismo se leen como ruido, cuatro se leen como una lista de tareas. */
  var FAMILIAS = [
    { k: 'incierto', t: 'No se pudieron calcular con certeza',
      d: 'Falta un dato o la cuenta no cierra. Un número mal calculado es peor que ninguno.' },
    { k: 'clientes', t: 'Salen de datos de clientes',
      d: 'Nombre, teléfono o mail. Estos no se publican nunca, ni siquiera sumados.' },
    { k: 'gente', t: 'Nombran a alguien del equipo',
      d: 'La intranet es pública y sin contraseña: no puede tener el nombre de un vendedor ni de un operador al lado de un número.' },
    { k: 'reparo', t: 'Dependen de categorías que están repetidas',
      d: 'La misma opción escrita de dos formas parte el número en dos. Se arregla en la planilla y estos vuelven solos.' },
    { k: 'otro', t: 'Quedaron afuera por otro motivo', d: '' }
  ];

  function familiaDe(lec, traba) {
    if (traba.clase === 'incierto') return 'incierto';
    if (/datos de clientes/.test(traba.texto || '')) return 'clientes';
    if (/^Nombra a alguien/.test(traba.texto || '')) return 'gente';
    if ((lec.reparos && lec.reparos.length) || /reparo/.test(traba.texto || '')) return 'reparo';
    return 'otro';
  }

  /* Los reparos, dichos UNA vez. Acá se juntan y se muestran como lo que
     son —una lista de columnas para revisar— con las dos formas enfrentadas,
     que puestas una al lado de la otra se leen en un segundo.

     ⚠️ Dos expresiones y no una: la primera es la de hoy, la segunda la que
     escribía lecturas.py antes de afinar el detector. Se dejan las dos
     porque este parseo se rompe en silencio —si ninguna coincide, la fila
     igual se dibuja, pero con el texto largo crudo y "la planilla" en vez
     del nombre de la columna—, y eso ya pasó una vez. */
  var RE_REPAROS = [
    /^en (.+?), «.+?» est[aá] cargada de dos formas \((.+?)\), as[ií] que/i,
    /^en (.+?) hay opciones que parecen la misma cosa \((.+)\)/i
  ];

  function _parseReparo(r) {
    for (var i = 0; i < RE_REPAROS.length; i++) {
      var m = RE_REPAROS[i].exec(r);
      if (m) return m;
    }
    return [];
  }

  function reparosJuntos(lecturas) {
    var vistos = {}, lista = [];
    lecturas.forEach(function (l) {
      (l.reparos || []).forEach(function (r) {
        var m, col, par;
        if (vistos[r]) { vistos[r].veces++; return; }
        m = _parseReparo(r);
        col = m[1] || '';
        par = (m[2] || '').split(' / ');
        vistos[r] = { texto: r, columna: col, a: par[0] || '', b: par[1] || '', veces: 1 };
        lista.push(vistos[r]);
      });
    });
    return lista;
  }

  function reparosHTML(reps) {
    if (!reps.length) return '';
    return '<ul class="dt-rep-lista">' + reps.map(function (r) {
      return '<li><span class="dt-rep-c">' + esc(r.columna || 'la planilla') + '</span>' +
        (r.a && r.b
          ? '<span class="dt-rep-p"><i>' + esc(r.a) + '</i>' +
            '<em>vs</em><i>' + esc(r.b) + '</i></span>'
          : '<span class="dt-rep-p">' + esc(r.texto) + '</span>') +
        '<span class="dt-rep-n">' + r.veces +
        (r.veces === 1 ? ' número' : ' números') + '</span></li>';
    }).join('') + '</ul>';
  }

  /* Una lectura trabada, en una línea. SIN la vista previa: esa vista está
     para mostrar cómo se vería el número EN LA INTRANET, y este número no
     va a ir nunca a la intranet. Dibujarla igual era ocupar media pantalla
     con el ensayo de algo que no se estrena. */
  function miniHTML(lec, traba) {
    return '<li class="dt-mini' + (traba.clase === 'incierto' ? ' incierto' : '') + '">' +
      '<span class="dt-mini-v">' +
      (traba.clase === 'incierto' ? '—' : esc(numeroEscrito(lec))) + '</span>' +
      '<span class="dt-mini-t">' + esc(lec.texto) + '</span></li>';
  }

  /* =================================================================
     PARA ARREGLAR EN LA PLANILLA
     Lo único de esta pantalla que se arregla en otro lado, y lo único que
     devuelve números: cada valor cargado de dos formas parte un número en
     dos, y unificarlo en la planilla lo desbloquea acá solo.

     Se dibuja aparte de «lo que quedó afuera» aunque a veces sean la misma
     causa, porque son dos cosas distintas: allá hay una lista de números
     que no se pueden usar, y acá una lista corta de cosas para hacer. La
     mayoría de estos duplicados hoy no traban nada — igual conviene
     arreglarlos antes de que aparezca la lectura que sí los toque.

     ⚠️ Solo `valor_duplicado` y `valor_sospechoso`. El resto de los avisos
     del revisor no se dibujan a propósito: eran 34 tarjetas y 6.637 px,
     casi todas describiendo el funcionamiento normal de la planilla.
     ================================================================= */
  var RE_DOS_FORMAS = /^(.+?):\s*«(.+)»\s*est[aá] cargada de dos formas/i;
  var RE_PARECEN    = /^(.+?):\s*dos opciones se parecen/i;

  function seccionArreglar(avisos, abierto) {
    var dup = [], sos = [], h;
    (avisos || []).forEach(function (a) {
      var t = a.titulo || '', m;
      if (a.clase === 'valor_duplicado' || RE_DOS_FORMAS.test(t)) {
        m = RE_DOS_FORMAS.exec(t) || [];
        dup.push({ columna: m[1] || '', par: a.ejemplos || [], filas: a.filas_afectadas || 0 });
      } else if (a.clase === 'valor_sospechoso' || RE_PARECEN.test(t)) {
        m = RE_PARECEN.exec(t) || [];
        sos.push({ columna: m[1] || '', par: a.ejemplos || [] });
      }
    });
    if (!dup.length && !sos.length) return '';

    function lista(xs, conFilas) {
      return '<ul class="dt-rep-lista">' + xs.map(function (x) {
        return '<li><span class="dt-rep-c">' + esc(x.columna || 'la planilla') + '</span>' +
          '<span class="dt-rep-p"><i>' + esc(x.par[0] || '') + '</i>' +
          '<em>y</em><i>' + esc(x.par[1] || '') + '</i></span>' +
          (conFilas && x.filas
            ? '<span class="dt-rep-n">' + miles(x.filas) + ' filas</span>'
            : '') + '</li>';
      }).join('') + '</ul>';
    }

    h = '<section class="dt-sec dt-afuera dt-arreglar' + (abierto ? ' abierta' : '') + '">' +
      '<button type="button" class="dt-afuera-h" aria-expanded="' +
      (abierto ? 'true' : 'false') + '">' +
      '<span class="dt-ic dt-afuera-fl">' + ICO.flecha + '</span>' +
      '<b>Para arreglar en la planilla</b><span class="dt-afuera-r">' +
      (dup.length
        ? dup.length + (dup.length === 1
            ? ' valor está cargado de dos formas' : ' valores están cargados de dos formas')
        : '') +
      (dup.length && sos.length ? ' · ' : '') +
      (sos.length ? sos.length + ' para mirar' : '') +
      '</span></button><div class="dt-afuera-c"' + (abierto ? '' : ' hidden') + '>';

    if (dup.length) {
      h += '<div class="dt-grupo"><div class="dt-grupo-h"><b>El mismo valor, ' +
        'escrito de dos formas</b><span>' + dup.length + '</span></div>' +
        '<p class="dt-grupo-d">Es el mismo valor: cambia una tilde, un espacio, ' +
        'una mayúscula o el orden de las palabras. Mientras estén así, todo ' +
        'número que salga de ese valor está partido en dos. Unificarlos en la ' +
        'planilla es lo único que hay que hacer.</p>' + lista(dup, true) + '</div>';
    }
    if (sos.length) {
      h += '<div class="dt-grupo"><div class="dt-grupo-h"><b>Se parecen mucho, ' +
        'pero decidís vos</b><span>' + sos.length + '</span></div>' +
        '<p class="dt-grupo-d">Pueden ser un tipeo o dos cosas distintas. ' +
        'El panel no lo sabe, así que <b>no traba ningún número</b>.</p>' +
        lista(sos, false) + '</div>';
    }
    return h + '</div></section>';
  }

  function seccionTablero(publicables, cols, pub) {
    var h = '<section class="dt-sec"><div class="dt-sec-h">' +
      /* Se llamaba "Para publicar en la intranet". Los reportes no se
         publican: son para adentro. Lo que esta seccion muestra es lo que el
         panel pudo leer de la planilla con certeza. */
      '<h3>Lo que dice la planilla</h3>' +
      '<p class="muted">Lo que el panel pudo leer con certeza. ' +
      'Abajo, lo que no se puede afirmar y por qué.</p></div>';
    if (!publicables.length) {
      h += '<div class="vacio"><b>De esta planilla no se puede afirmar ningún número</b>' +
        '<p>Están todos abajo, con el motivo de cada uno.</p></div></section>';
      return h;
    }
    h += '<div class="dt-nums">' + publicables.map(function (l) {
      return numeroHTML(l, null, !!pub[l.id]);
    }).join('') + '</div></section>';
    return h;
  }

  /* =================================================================
     LO QUE QUEDÓ AFUERA
     Plegado y al final. Antes estas 23 lecturas estaban mezcladas con las
     5 publicables, cada una con su tarjeta grande y su cartel rojo: la
     pantalla era 80% cosas que no se pueden usar, y los 5 números que sí
     había que decidir estaban perdidos en el medio.
     ================================================================= */
  function seccionAfuera(trabadas, cols, abierto) {
    var grupos = {}, reps, h;
    if (!trabadas.length) return '';
    trabadas.forEach(function (x) {
      var f = familiaDe(x.lec, x.traba);
      (grupos[f] = grupos[f] || []).push(x);
    });
    reps = reparosJuntos(trabadas.map(function (x) { return x.lec; }));

    h = '<section class="dt-sec dt-afuera' + (abierto ? ' abierta' : '') + '">' +
      '<button type="button" class="dt-afuera-h" aria-expanded="' +
      (abierto ? 'true' : 'false') + '">' +
      '<span class="dt-ic dt-afuera-fl">' + ICO.flecha + '</span>' +
      '<b>' + trabadas.length +
      (trabadas.length === 1 ? ' número quedó afuera' : ' números quedaron afuera') +
      '</b><span class="dt-afuera-r">' +
      FAMILIAS.filter(function (f) { return grupos[f.k]; })
        .map(function (f) { return grupos[f.k].length + ' ' + f.t.toLowerCase(); })
        .join(' · ') +
      '</span></button><div class="dt-afuera-c"' + (abierto ? '' : ' hidden') + '>';

    FAMILIAS.forEach(function (f) {
      var g = grupos[f.k];
      if (!g) return;
      h += '<div class="dt-grupo"><div class="dt-grupo-h"><b>' + esc(f.t) +
        '</b><span>' + g.length + '</span></div>' +
        (f.d ? '<p class="dt-grupo-d">' + esc(f.d) + '</p>' : '') +
        (f.k === 'reparo' ? reparosHTML(reps) : '') +
        '<ul class="dt-minis">' + g.map(function (x) {
          return miniHTML(x.lec, x.traba);
        }).join('') + '</ul></div>';
    });
    return h + '</div></section>';
  }

  /* ---------------------------------------------------------------
     LA BARRA DEL RECUENTO
     Va pegada arriba de todo y no se va nunca: es la única protección
     contra publicar sin querer, y sirve de poco si hay que scrollear
     para encontrarla.
     --------------------------------------------------------------- */
  function barraHTML(n, total) {
    /* PUBLICAR A LA INTRANET NO SE MUESTRA.
       Un reporte de derivaciones es para adentro: se mira, se baja en Word o
       se imprime. La franja de "N de M publicados" con su medidor y el botón
       de apagar todo ofrecía algo que no se usa, y ocupaba el lugar donde
       empieza lo que sí importa.
       Se devuelve vacío en vez de borrar la función: el motor sigue entero
       —los interruptores, el guardado y los endpoints—, así que el día que
       haya un informe que sí vaya al sitio, alcanza con sacar este return. */
    return '';
  }

  function barraHTMLcompleta(n, total) {
    var pct = total ? Math.round(n / total * 100) : 0;
    return '<div class="dt-barra' + (n ? ' hay' : '') + '">' +
      '<span class="dt-cuenta"><b class="dt-cuenta-n">' + n + '</b> de <b>' + total +
      '</b> publicados</span>' +
      '<span class="dt-medidor"><i style="width:' + pct + '%"></i></span>' +
      '<span class="dt-nota">' + (n
        ? 'Estos ' + (n === 1 ? 'número sale' : n + ' números salen') +
          ' a la intranet, que es pública y no tiene contraseña.'
        : 'Nada sale de esta computadora hasta que prendas algo.') + '</span>' +
      '<button type="button" class="btn btn-ghost dt-apagar"' + (n ? '' : ' disabled') +
      '>Apagar todo</button>' +
      '</div>';
  }

  /* =================================================================
     EL ARMADO
     ================================================================= */
  function pintarDatos(cont, datos) {
    if (!cont) return null;
    datos = datos || {};

    var an = datos.analisis || {};
    var cols = mapaCols(an);
    var avisos = datos.avisos || [];
    var lecturas = (datos.lecturas || []).map(normalizarLectura);
    var alCambiar = typeof datos.alCambiar === 'function' ? datos.alCambiar : null;
    var alArreglar = typeof datos.alArreglar === 'function' ? datos.alArreglar : null;

    var publicables = lecturas.filter(function (l) { return !trabaDe(l, cols); });
    var pub = normalizarPublicados(datos.publicados, publicables);

    function prendidos() {
      return publicables.filter(function (l) { return !!pub[l.id]; })
        .map(function (l) { return l.id; });
    }

    /* Cada lectura trabada, con su motivo ya resuelto: se calcula una vez
       acá y no dentro de cada dibujo. */
    var trabadas = [];
    lecturas.forEach(function (l) {
      var t = trabaDe(l, cols);
      if (t) trabadas.push({ lec: l, traba: t });
    });

    cont.classList.add('dt');
    /* ⚠️ EL ORDEN DE LA PANTALLA, Y POR QUÉ
       1. Qué planilla es y sus números de verdad — lo primero que se
          pregunta cualquiera que la abre.
       2. Sólo lo que se puede publicar, grande y con su interruptor: es la
          única decisión que esta pantalla le pide a la persona.
       3. Lo que quedó afuera, plegado y agrupado por motivo.
       4. Las columnas, como referencia.

       Antes 1 no existía, y 2 y 3 estaban mezclados en una sola grilla de
       28 tarjetas donde 23 decían "NO SE PUBLICA": había que barrer toda
       la pantalla para encontrar los 5 interruptores que importaban, y el
       mismo reparo de "opciones repetidas" aparecía escrito 18 veces.
       (Y antes de eso el orden era columnas → avisos → tablero, con 6.637
       px de quejas por delante de los números; esa parte ya se había
       arreglado y sigue así.) */
    cont.innerHTML =
      barraHTML(prendidos().length, publicables.length) +
      seccionIdentidad(datos.identidad) +
      seccionTablero(publicables, cols, pub) +
      seccionArreglar(avisos, false) +
      seccionAfuera(trabadas, cols, !publicables.length) +
      seccionColumnas(an);

    var barra = cont.querySelector('.dt-barra');

    /* Se repinta SOLO la barra, no la sección entera: repintar todo con
       cada click perdía el foco del interruptor recién tocado y el scroll
       saltaba al principio. */
    function refrescarBarra() {
      /* sin barra no hay nada que refrescar: barraHTML devuelve vacio desde
         que la franja de publicados no se muestra, y sin este freno el
         primer click en un interruptor reventaba con parentNode de null */
      if (!barra) return;
      var n = prendidos().length;
      var nuevo = document.createElement('div');
      var html = barraHTML(n, publicables.length);
      if (!html) return;
      nuevo.innerHTML = html;
      barra.parentNode.replaceChild(nuevo.firstChild, barra);
      barra = cont.querySelector('.dt-barra');
    }

    function cambiar(id, prendido) {
      var art = cont.querySelector('.dt-num' + selId(id));
      var chip;
      if (prendido) pub[id] = true; else delete pub[id];
      if (art) {
        art.classList.toggle('on', !!prendido);
        chip = art.querySelector('.dt-chip.pub');
        if (prendido && !chip) {
          chip = document.createElement('span');
          chip.className = 'dt-chip pub';
          chip.textContent = 'PUBLICADO';
          art.querySelector('.dt-num-h').appendChild(chip);
        } else if (!prendido && chip) {
          chip.parentNode.removeChild(chip);
        }
      }
      refrescarBarra();
      if (alCambiar) alCambiar(prendidos(), { id: id, prendido: !!prendido });
    }

    /* Un solo oyente para toda la sección: los interruptores y los avisos
       se repintan y con onclick por nodo había que volver a engancharlos.
       ⚠️ Volver a pintar el MISMO contenedor tiene que sacar los oyentes
       viejos primero: quedaban encima de los nuevos y un solo click
       cambiaba el interruptor dos veces, así que volvía a apagarse. */
    if (cont.__dtOyentes) {
      cont.removeEventListener('change', cont.__dtOyentes.change);
      cont.removeEventListener('click', cont.__dtOyentes.click);
    }
    cont.__dtOyentes = { change: alCambiarInput, click: alTocar };
    cont.addEventListener('change', alCambiarInput);
    cont.addEventListener('click', alTocar);

    function alCambiarInput(e) {
      var i = e.target;
      if (i && i.classList && i.classList.contains('dt-sw-i')) {
        cambiar(i.getAttribute('data-id'), i.checked);
      }
    }

    function alTocar(e) {
      var b = e.target.closest ? e.target.closest('button') : null;
      var art, filas, k;
      if (!b || !cont.contains(b)) return;

      if (b.classList.contains('dt-apagar')) {
        prendidos().forEach(function (id) {
          var i = cont.querySelector('.dt-sw-i' + selId(id));
          if (i) i.checked = false;
          cambiar(id, false);
        });
        return;
      }
      if (b.classList.contains('dt-afuera-h')) {
        art = b.closest('.dt-afuera');
        filas = art && art.querySelector('.dt-afuera-c');
        if (filas) {
          filas.hidden = !filas.hidden;
          art.classList.toggle('abierta', !filas.hidden);
          b.setAttribute('aria-expanded', filas.hidden ? 'false' : 'true');
        }
        return;
      }
      if (b.classList.contains('mf')) {
        cont.querySelectorAll('.dt-filtros .mf').forEach(function (x) {
          x.classList.toggle('on', x === b);
        });
        k = b.getAttribute('data-grav');
        cont.querySelectorAll('.dt-av').forEach(function (a) {
          a.hidden = k !== 'todo' && !a.classList.contains('g-' + k);
        });
        return;
      }
      if (b.classList.contains('dt-av-ver')) {
        art = b.closest('.dt-av');
        filas = art && art.querySelector('.dt-filas');
        if (filas) {
          /* la etiqueta de "abrir" se guarda la primera vez, antes de
             pisarla: si se recalcula después queda "ver las 0 filas" */
          if (!b.getAttribute('data-abrir')) b.setAttribute('data-abrir', b.textContent);
          filas.hidden = !filas.hidden;
          b.textContent = filas.hidden ? b.getAttribute('data-abrir') : 'ocultar las filas';
        }
        return;
      }
      if (b.classList.contains('dt-av-ir') && alArreglar) {
        alArreglar(avisos[+b.getAttribute('data-k')], null);
        return;
      }
      if (b.classList.contains('dt-fila') && alArreglar) {
        alArreglar(avisos[+b.getAttribute('data-k')], +b.getAttribute('data-fila'));
      }
    }

    return {
      publicados: prendidos,
      cuenta: function () {
        return { prendidos: prendidos().length, publicables: publicables.length,
                 trabadas: lecturas.length - publicables.length };
      },
      volverAPintar: function (otros) { return pintarDatos(cont, otros || datos); }
    };
  }

  window.pintarDatos = pintarDatos;
}());
