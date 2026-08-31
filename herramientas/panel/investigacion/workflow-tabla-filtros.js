export const meta = {
  name: 'mys-tabla-filtros',
  description: 'Disena filtros y ordenamiento para el bloque tabla del panel MyS',
  phases: [
    { title: 'Estudio', detail: 'como esta hecho hoy el bloque tabla (panel + intranet)' },
    { title: 'Spec', detail: 'diseno de ordenar/filtrar, dos enfoques en paralelo' },
    { title: 'Eleccion', detail: 'juez elige y fusiona' },
  ],
}

const ROOT = 'C:\\Users\\Redes 1\\Documents\\web dinamica-mys'
const CTX = `Proyecto: ${ROOT}
- Intranet estatica publicada en Vercel: intranet/index.html (1501 lineas, TODO el CSS y JS inline), intranet/modulos.js (window.MODULES, lo escribe el panel).
- Panel local: herramientas/panel/web/app.js (2441 lineas) = editor de bloques tipo Gutenberg. bloqueNuevo() crea el bloque, bloqueCanvas() lo dibuja editable, <tipo>Inspector() son los ajustes del panel derecho, bloqueHTML() genera el HTML FINAL que se guarda dentro de modulos.js y que la intranet inserta tal cual con innerHTML.
- El bloque 'tabla' ya existe: app.js linea 699 (BK_META), 729 (bloqueNuevo), 870 tablaHTML(bk, ed), 1306 tablaInspector(bk), 1682 (bloqueHTML). Render actual: <div class="m-tabla"><table><thead>...<tbody>...</table></div>.
- CLAVE: el HTML se genera UNA VEZ en el panel y se guarda estatico. La interactividad (ordenar/filtrar) tiene que vivir en el JS de intranet/index.html, enganchandose por delegacion a los elementos que el panel emita (data-attributes).
NO EDITES NINGUN ARCHIVO. Solo leer y reportar con citas file:line exactas.`

phase('Estudio')

const estudio = await agent(`${CTX}

TAREA: documenta con precision como funciona HOY el bloque 'tabla', de punta a punta.
1. app.js: leé completas tablaHTML (~870-882), tablaInspector (~1306-1345), el caso 'tabla' de bloqueNuevo (~729), de bloqueCanvas (~974) y de bloqueHTML (~1682). Pega el codigo real.
2. Cual es el MODELO exacto del bloque? (columnas, filas, celdas: son strings? html inline? hay tipos de columna?). El usuario edita las celdas inline en el canvas (prop 'celda', ver app.js ~1559 y ~1585). Como se guardan.
3. intranet/index.html: buscá el CSS de .m-tabla / .m-tabla table / th / td. Pegalo. Hay algo de JS que toque tablas hoy? Hay reglas responsive/mobile para tablas (scroll horizontal)?
4. En herramientas/panel/web/styles.css: el CSS espejo bajo .doc-preview para .m-tabla.
5. Hay tablas ya publicadas? Busca '"t":"tabla"' en intranet/modulos.js y reporta cuantas hay, cuantas columnas/filas tipicas, y si las celdas contienen numeros, plata ($), porcentajes, fechas o texto. Esto define que tipos de orden hacen falta.
Respondé en markdown denso con el codigo citado.`, { label: 'estudio:tabla', phase: 'Estudio' })

phase('Spec')

const SPEC = {
  type: 'object',
  additionalProperties: false,
  required: ['nombre', 'resumen', 'ux', 'modelo', 'cambios'],
  properties: {
    nombre: { type: 'string' },
    resumen: { type: 'string' },
    ux: { type: 'string', description: 'que ve y hace el vendedor en el celular' },
    modelo: { type: 'string', description: 'campos nuevos del bloque tabla en JSON' },
    contras: { type: 'array', items: { type: 'string' } },
    cambios: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['archivo', 'donde', 'que', 'codigo'],
        properties: {
          archivo: { type: 'string' },
          donde: { type: 'string' },
          que: { type: 'string' },
          codigo: { type: 'string' },
        },
      },
    },
  },
}

const PEDIDO = `PEDIDO DEL USUARIO (literal): "quiero que trabajemos en el bloque de tabla, ya que esta perfecto como se carga la tabla pero tambien quiero que tenga una opcion de filtro, asi cuando el usuario quiere filtrar/ordenar la tabla segun distintas opciones, pueda hacerlo. Ordenarlo por el numero mas alto o por el mas bajo..."
Contexto de uso: la ven VENDEDORES, mayormente desde el CELULAR. Tiene que ser obvio y con targets de 44px. El que arma la tabla es el dueno desde el panel (no tecnico).
Restriccion dura: el HTML de la tabla se genera en el panel y se guarda estatico en modulos.js; la interactividad va en el JS inline de intranet/index.html, enganchada por delegacion + data-attributes. NO hay build ni librerias externas: JS vanilla.
Otra restriccion: debe ser RETROCOMPATIBLE — las tablas ya publicadas sin la opcion activada tienen que seguir viendose igual.

ESTUDIO DEL CODIGO ACTUAL:
${estudio}`

const propuestas = await parallel([
  () => agent(`${CTX}

${PEDIDO}

TU ENFOQUE (A) — MINIMO Y ROBUSTO: "ordenar tocando el encabezado".
- Cada <th> se vuelve un boton: 1er toque ordena descendente (el numero mas alto arriba, que es lo que el usuario pidio primero), 2do ascendente, 3ro vuelve al orden original. Flechita ▲▼ visible en la columna activa.
- Un unico buscador de texto arriba de la tabla que filtra filas por coincidencia en cualquier celda (opcional, activable desde el panel).
- Deteccion automatica del tipo de dato por columna al ordenar (numero / plata "$ 1.234,50" formato argentino / porcentaje / fecha dd/mm/aaaa / texto con localeCompare es). Da la funcion de parseo COMPLETA y ojo con el separador de miles '.' y decimal ',' de Argentina.
- En el panel: un solo checkbox "Permitir ordenar" + otro "Mostrar buscador" en tablaInspector.
Entrega el spec con codigo listo para pegar (CSS + JS de intranet + cambios de app.js), con anclajes exactos. Prioriza que sea imposible de romper y que funcione en tablas con scroll horizontal en mobile.`, { label: 'spec:A-minimo', phase: 'Spec', schema: SPEC }),

  () => agent(`${CTX}

${PEDIDO}

TU ENFOQUE (B) — BARRA DE CONTROLES EXPLICITA: "ordenar y filtrar desde una barra arriba de la tabla".
- Una barra sobre la tabla con: un <select> "Ordenar por: <columna>" + un toggle Mayor→menor / Menor→mayor, un buscador, y filtros por columna (chips o <select> con los valores unicos de esa columna, ej. columna "Sucursal" -> elegir una).
- Pensado para el dedo en el celular (selects nativos = ruedita de iOS/Android, sin CSS custom fragil).
- Contador "mostrando X de Y filas" y boton "Limpiar filtros".
- En el panel: por columna, el dueno elige si es Texto/Numero/Plata/Fecha y si sirve para filtrar; asi el orden no adivina.
Entrega el spec con codigo listo para pegar (CSS + JS de intranet + cambios de app.js: tablaInspector con la config por columna, tablaHTML emitiendo los data-attributes), con anclajes exactos. Se explicito sobre como se guarda la config por columna sin romper las tablas ya publicadas.`, { label: 'spec:B-barra', phase: 'Spec', schema: SPEC }),
])

phase('Eleccion')

const veredicto = await agent(`${CTX}

Sos el arquitecto. Te paso 2 propuestas para agregar ordenar/filtrar al bloque tabla. El usuario es el dueno de una muebleria (no tecnico) que arma el contenido desde el panel; los lectores son vendedores en celular.

Tu trabajo:
1. Elegi UNA como base (o un hibrido concreto) y justifica en 3 renglones. Criterios, en orden: (a) que el vendedor entienda que puede ordenar SIN que se lo expliquen, (b) que el dueno lo configure con 1 o 2 clics, (c) que no rompa las tablas ya publicadas, (d) que funcione en celular con tablas anchas.
2. VERIFICA leyendo el codigo real que los anclajes que citan (tablaHTML ~870, tablaInspector ~1306, bloqueHTML ~1682, el CSS .m-tabla de intranet/index.html) existan tal como dicen. Corregi cualquier cita equivocada.
3. Entrega el PLAN FINAL de implementacion: por archivo, en orden, con el codigo consolidado listo para pegar. Incluí el modelo final del bloque tabla en JSON y como se degrada en tablas viejas.
4. Lista de verificaciones (que probar).

PROPUESTA A:
${JSON.stringify(propuestas[0], null, 1)}

PROPUESTA B:
${JSON.stringify(propuestas[1], null, 1)}

Respondé en espanol, markdown denso, accionable, sin relleno.`, { label: 'juez:tabla', phase: 'Eleccion' })

return { veredicto, propuestas: propuestas.filter(Boolean), estudio }
