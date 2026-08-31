export const meta = {
  name: 'mys-video-y-presentacion',
  description: 'Diagnostica por que el modo presentacion no genera diapositivas y disena el bloque de video del panel MyS',
  phases: [
    { title: 'Diagnostico', detail: 'tres agentes rastrean el bug de presentacion (panel, intranet, datos reales)' },
    { title: 'Diseno', detail: 'spec del bloque video (backend+panel y render intranet)' },
    { title: 'Sintesis', detail: 'plan de implementacion unico' },
  ],
}

const ROOT = 'C:\\Users\\Redes 1\\Documents\\web dinamica-mys'
const CTX = `Proyecto: ${ROOT}
- Intranet estatica publicada en Vercel: intranet/index.html (1501 lineas, todo el CSS+JS inline), intranet/modulos.js (window.MODULES, lo escribe el panel), intranet/assets/.
- Panel de administracion local (Python stdlib + Pillow): herramientas/panel/panel_server.py (1603 lineas) + frontend plano herramientas/panel/web/{index.html,app.js (2441 lineas),styles.css}.
- El panel tiene un editor tipo Gutenberg: bloques con t:'titulo'|'parrafo'|'imagen'|'pdf'|'galeria'|'diapo'|... . app.js: bloqueNuevo() crea, bloqueCanvas() dibuja el bloque editable en el canvas, <tipo>Inspector() son los ajustes del panel derecho, bloqueHTML() genera el HTML final que se guarda en modulos.js, bloquesHTML(bloques, presentacion) arma el documento.
- Un modulo puede estar en modo 'pagina', 'presentacion' (content.presentacion=true -> secciones <section class="dk-slide">) o 'biblioteca' (content.tipo='coleccion' con varios documentos, cada uno con su flag presentacion).
- La intranet renderiza con renderContent()/renderSection() y, si presenta===true, llama initDeck().
- El bloque 'pdf' (POST /api/upload-pdf en panel_server.py) es el analogo mas cercano para archivos no-imagen: guarda el archivo crudo en intranet/assets/_modulos/<key>.pdf, valida firma, tope de tamano, y el ctype se agrega en _servir_estatico.
- Los archivos de intranet/assets/_modulos/ son "gestionados": viajan al deploy via el cerebro Cloudflare (POST /publish, batching de 40 archivos por commit, commitea a GitHub -> Vercel).
NO EDITES NINGUN ARCHIVO. Sos un agente de investigacion: solo leer y reportar con citas file:line exactas.`

phase('Diagnostico')

const DIAG_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['hallazgos', 'resumen'],
  properties: {
    resumen: { type: 'string' },
    hallazgos: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['titulo', 'archivo', 'linea', 'evidencia', 'porQueRompe', 'confianza'],
        properties: {
          titulo: { type: 'string' },
          archivo: { type: 'string' },
          linea: { type: 'number' },
          evidencia: { type: 'string', description: 'codigo citado literal' },
          porQueRompe: { type: 'string' },
          confianza: { type: 'string', enum: ['alta', 'media', 'baja'] },
          arreglo: { type: 'string' },
        },
      },
    },
  },
}

const diagnosticos = await parallel([
  () => agent(`${CTX}

TAREA (lado PANEL): el usuario dice "el bloque de presentacion no funciona, no me genera una diapositiva". Rastrea TODO el camino en el panel:
1. Como se activa el modo presentacion (interruptor Pagina/Presentacion/Biblioteca en el acordeon Apariencia, app.js ~lineas 455-560).
2. El bloque 'diapo': bloqueNuevo, bloqueCanvas (~979), su inspector (~1405), y como aparece en la paleta de bloques (BK_GRUPOS 'Presentacion': ['diapo'] ~684).
3. bloquesHTML(bloques, presentacion) ~1695-1720: la logica de corte en slides. OJO: mira que pasa si el usuario pone el PRIMER bloque diapo al principio, o si NO pone ningun diapo, o si pone diapo al final. Que devuelve si no hay bloques? Devuelve '' -> el modulo queda vacio?
4. detSave (~2196-2210): que se guarda exactamente en content ({tipo,bloques,html,presentacion}) y en el caso coleccion (~2196). Se guarda presentacion en TODOS los caminos? Hay algun camino donde se pierda?
5. El caso 'intacto' (~2204): un builtin sin cambios no guarda content -> si el usuario solo cambia el modo a presentacion sin tocar bloques, se guarda?
6. Verifica si la paleta de bloques muestra el grupo Presentacion siempre o solo en modo presentacion.
Reporta cada bug concreto con archivo:linea, el codigo citado, por que rompe y el arreglo propuesto.`, { label: 'diag:panel', phase: 'Diagnostico', schema: DIAG_SCHEMA }),

  () => agent(`${CTX}

TAREA (lado INTRANET): rastrea por que un modulo en modo presentacion no muestra diapositivas en intranet/index.html:
1. renderSection (~1216-1244): presenta = mod.content.tipo === 'bloques' && !!mod.content.presentacion. Que pasa con el modo BIBLIOTECA (content.tipo==='coleccion')? Ahi presenta queda FALSE aunque el documento abierto sea una presentacion. Busca COL_KEY/COL_DOC y como se abre un documento de una coleccion, y si llama initDeck.
2. renderContent(~1319+): como envuelve el html de tipo bloques. Envuelve en <div class="manual">? Eso rompe las <section class="dk-slide">?
3. initDeck(): busca su definicion completa. Que selector usa para juntar las slides (dkSlides)? Sobre que contenedor? Que pasa si las .dk-slide estan anidadas dentro de .manual o de .db? Ninguna slide recibe la clase .on -> .deck .dk-slide{display:none} las esconde TODAS (CSS linea 485-486) => pantalla vacia. Verifica si la clase .deck se aplica a algun ancestro y donde.
4. body.classList.toggle('report-mode', ...) linea 1237 y el CSS de .report-mode / .deck / .dk-stage / .dk-bar: quien pone la clase 'deck'? Si nadie la pone, las slides se ven todas apiladas; si alguien la pone y initDeck falla, no se ve NADA. Determina cual de los dos sintomas ocurre.
5. Revisa que el modulos.js publicado tenga o no el html con dk-slide.
Reporta cada bug con archivo:linea, codigo citado, por que rompe, arreglo propuesto.`, { label: 'diag:intranet', phase: 'Diagnostico', schema: DIAG_SCHEMA }),

  () => agent(`${CTX}

TAREA (DATOS REALES + reproduccion): quiero evidencia dura de que esta guardado hoy.
1. Lee intranet/modulos.js. Es un archivo grande de una sola linea; usa grep/node para inspeccionarlo, NO lo vuelques entero. Busca modulos con "presentacion":true y con bloques de tipo "diapo". Reporta: cuantos modulos hay, cuales tienen presentacion:true, si su campo html contiene '<section class="dk-slide"' o no, y cuantas dk-slide tiene cada uno.
2. Si hay modulos con presentacion:true pero html SIN dk-slide -> es prueba de que el guardado rompe. Si tienen dk-slide pero no se ven -> el bug es de render.
3. Busca tambien modulos con content.tipo === 'coleccion' y documentos con presentacion:true adentro.
4. Revisa git log reciente de intranet/index.html y intranet/modulos.js (git -C "${ROOT}" log --oneline -15 -- intranet/index.html) para ver si el codigo de deck se publico o quedo sin publicar (memoria del proyecto dice que hubo desyncs git vs cerebro). Compara: existe initDeck en el index.html LOCAL y esta commiteado? git status del repo.
5. Reporta el estado exacto con evidencia citada.`, { label: 'diag:datos', phase: 'Diagnostico', schema: DIAG_SCHEMA }),
])

phase('Diseno')

const SPEC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['resumen', 'cambios'],
  properties: {
    resumen: { type: 'string' },
    riesgos: { type: 'array', items: { type: 'string' } },
    cambios: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['archivo', 'donde', 'que', 'codigo'],
        properties: {
          archivo: { type: 'string' },
          donde: { type: 'string', description: 'funcion o linea de anclaje exacta' },
          que: { type: 'string' },
          codigo: { type: 'string', description: 'codigo propuesto, lo mas completo posible' },
        },
      },
    },
  },
}

const specs = await parallel([
  () => agent(`${CTX}

TAREA (spec BACKEND + PANEL del bloque VIDEO). El usuario quiere un bloque nuevo para subir VIDEOS. Requisitos suyos, literales:
- "los videos pueden ser la gran mayoria verticales o horizontales" -> el bloque tiene que verse bien en AMBAS orientaciones, sin deformar ni dejar franjas negras enormes.
- "tiene que tener una opcion de modificar el tamano para que no suceda que moleste en la pantalla del usuario" -> selector de tamano como el que ya tiene el bloque 'imagen' (tam: ch/md/gr/full).
Ademas debe soportar DOS fuentes: (a) archivo mp4 subido al proyecto, (b) link externo (YouTube/Vimeo/Drive) para videos pesados.

Estudia con detalle como esta hecho el bloque 'pdf' (el analogo mas cercano: endpoint /api/upload-pdf en panel_server.py, pdfInspector/subirPdfBloque en app.js, casos en bloqueNuevo/bloqueCanvas/bloqueHTML) y el bloque 'imagen' (por el selector tam en imagenInspector y por su render figure.m-img.tam-X).

Entrega un spec de IMPLEMENTACION con codigo concreto para:
1. panel_server.py: endpoint POST /api/upload-video (guarda crudo en intranet/assets/_modulos/<key>.mp4, valida firma de contenedor mp4/webm — el mp4 tiene 'ftyp' en los bytes 4-8, webm empieza con 1A 45 DF A3 —, tope de tamano razonable: propone cual y justifica pensando en que estos archivos se publican por el cerebro Cloudflare a GitHub via API en base64 y GitHub tiene limites por blob). Agregar .mp4/.webm al mapa de content-types de _servir_estatico. Confirmar que _modulos/*.mp4 ya cae en "gestionados" (rel_gestionados/_es_gestionado_rel) o si hay que tocarlo.
2. app.js: BK_META y BK_GRUPOS (grupo Medios), bloqueNuevo('video'), bloqueCanvas caso video, videoInspector (fuente archivo/link, subir archivo, URL externa, tamano, poster opcional, autoplay/loop/silenciado para clips cortos, controles), bloqueHTML caso video.
3. Modelo del bloque: propone el objeto exacto {t:'video', src, url, modo, tam, ...}.
4. Como detectar la orientacion: propone que el PANEL detecte el aspect ratio al subir (con un <video> temporal en el cliente leyendo videoWidth/videoHeight) y lo guarde en el bloque (ej. orient:'vertical'|'horizontal'), asi la intranet no tiene que esperar metadata. Da el codigo.
Se lo mas concreto posible: codigo listo para pegar, con los anclajes exactos (nombre de funcion + linea actual).`, { label: 'spec:panel-video', phase: 'Diseno', schema: SPEC_SCHEMA }),

  () => agent(`${CTX}

TAREA (spec RENDER + CSS del bloque VIDEO en la INTRANET). El bloque video se guarda en modulos.js como HTML ya generado y la intranet lo inserta tal cual dentro de .manual. Hay que agregar el CSS (y el JS minimo) en intranet/index.html.

Requisitos del usuario:
- La gran mayoria de los videos seran VERTICALES (tipo reel 9:16) u HORIZONTALES (16:9). Ambos tienen que verse bien.
- "opcion de modificar el tamano para que no suceda que moleste en la pantalla del usuario": un video vertical 9:16 a ancho completo en un celular ocupa mas de una pantalla entera -> hay que CAPAR el alto.

Estudia:
1. Como resolvio esto el bloque 'imagen': .m-img con alto tope 360px y clases .tam-ch/.tam-gr/.tam-full (buscalas en intranet/index.html). Reusa esa misma logica y nomenclatura.
2. El visor a pantalla completa existente: openLightbox (imagenes) y openPdf (#pdfview). Propone si conviene un boton "ver en grande" para video y como (pantalla completa nativa via requestFullscreen del <video>, que en iOS Safari funciona con webkitEnterFullscreen, vs un overlay propio). Se concreto sobre las limitaciones de iOS.
3. Mobile: media queries existentes en intranet/index.html.

Entrega CSS y HTML concretos:
- .m-video (contenedor), manejo de orientacion via clase .vert/.horiz + aspect-ratio, alto maximo por tamano (ch/md/gr/full) expresado en px y tambien acotado por vh para que NUNCA pase de ~70vh en mobile.
- El <video> con playsinline, preload="metadata", controls, poster opcional; explicita por que playsinline es obligatorio en iOS.
- Caso link externo (YouTube/Vimeo): iframe responsive con la misma caja y aspect-ratio; da la funcion que convierte una URL de YouTube/Vimeo/Drive normal a URL embebible.
- Regla RETROACTIVA si aplica.
Devolve codigo listo para pegar con el anclaje exacto (linea/selector vecino) de donde va cada bloque de CSS.`, { label: 'spec:intranet-video', phase: 'Diseno', schema: SPEC_SCHEMA }),
])

phase('Sintesis')

const plan = await agent(`${CTX}

Sos el arquitecto. Te paso el resultado de 3 diagnosticos del bug de presentacion y 2 specs del bloque de video nuevo. Tu trabajo:

A) Para el BUG DE PRESENTACION: cruza los 3 diagnosticos, descarta los hallazgos que se contradicen o que no tengan evidencia citada, y VERIFICA vos mismo leyendo el codigo los 2-3 hallazgos mas probables. Entrega la CAUSA RAIZ confirmada (o las causas, si son varias) con el arreglo exacto (archivo, funcion, codigo viejo -> codigo nuevo).

B) Para el BLOQUE VIDEO: fusiona los 2 specs en un unico plan de implementacion ordenado por archivo, sin duplicados ni contradicciones. Si los specs difieren en el modelo del bloque o en los nombres de clases CSS, elegi uno y decilo.

C) Entrega un ORDEN DE IMPLEMENTACION concreto (que archivo tocar primero y por que), y la lista de verificaciones a correr despues (que probar con Playwright / que mirar en la intranet).

DIAGNOSTICOS:
${JSON.stringify(diagnosticos.filter(Boolean), null, 1)}

SPECS DE VIDEO:
${JSON.stringify(specs.filter(Boolean), null, 1)}

Respondé en espanol, en markdown, denso y accionable. Nada de relleno.`, { label: 'sintesis', phase: 'Sintesis' })

return { plan, diagnosticos: diagnosticos.filter(Boolean), specs: specs.filter(Boolean) }
