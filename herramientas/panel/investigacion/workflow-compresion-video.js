export const meta = {
  name: 'mys-compresion-video',
  description: 'Disena la compresion automatica de video en el panel MyS (Python congelado, sin dependencias)',
  phases: [
    { title: 'Investigacion', detail: 'motor de compresion, comando exacto y limites de publicacion' },
    { title: 'Diseno', detail: 'UX del aviso + endpoint backend' },
    { title: 'Critica', detail: 'revision adversarial del plan' },
  ],
}

const ROOT = 'C:\\Users\\Redes 1\\Documents\\web dinamica-mys'
const CTX = [
  'Proyecto: ' + ROOT,
  '- Panel de administracion local del cliente: herramientas/panel/panel_server.py (Python 3, SOLO stdlib + Pillow, servidor http.server en 127.0.0.1:8124) + frontend plano herramientas/panel/web/index.html, app.js, styles.css.',
  '- Se distribuye CONGELADO con PyInstaller (--onedir, console=False) e instalador Inno Setup, a %LOCALAPPDATA%/PanelMyS/. Hoy el instalador de sucursal pesa ~61 MB. Rutas frozen-aware: sys.frozen / sys._MEIPASS (RES_DIR) y EXE_DIR. Estado por maquina en %LOCALAPPDATA%/PanelMyS_state/.',
  '- Los usuarios son NO TECNICOS (duenos y encargados de sucursales de una muebleria, Windows, sin permisos de admin en el flujo normal).',
  '- Ya existe un endpoint POST /api/upload-pdf que guarda un archivo crudo en intranet/assets/_modulos/<key>.pdf validando la firma y con tope de tamano. Es el patron a seguir.',
  '- PUBLICACION: los archivos de intranet/assets/_modulos/ se publican a GitHub y de ahi a Vercel mediante un Cloudflare Worker propio (el "cerebro"): el panel manda POST /publish con los archivos en base64, en BATCHES DE 40 ARCHIVOS por commit; el Worker crea un blob por archivo con la Git Data API (limite de 50 subrequests por invocacion en CF free) y despues tree+commit+ref.',
  '- El panel ya notifica cosas al usuario con toasts y con popups propios (funcion confirmar() styled).',
  'NO EDITES NINGUN ARCHIVO. Solo investigar/leer/reportar.',
].join('\n')

const PEDIDO = [
  'PEDIDO DEL USUARIO (literal, en respuesta a como manejar el peso de los videos): "Cuando se suba el video que el panel reduzca el peso. Cuando es asi que le notifique al usuario que va a comprimir el peso del video para que se pueda subir correctamente".',
  'O sea: el usuario arrastra un video (celular/camara: puede venir en 4K, 100-500 MB, H.265/HEVC de iPhone, vertical u horizontal), el panel le avisa "voy a comprimirlo para que se pueda publicar", lo comprime, y sube el resultado liviano.',
].join('\n')

phase('Investigacion')

const investigacion = await agent(CTX + '\n\n' + PEDIDO + `

TAREA DE INVESTIGACION. Respondé estas preguntas con precision tecnica y fuentes (usá WebSearch/WebFetch cuando haga falta; verificá lo que afirmes):

1. MOTOR. Python stdlib no comprime video. Evaluá y COMPARÁ estas opciones para una app PyInstaller congelada en Windows, y recomendá UNA:
   (a) Bundlear ffmpeg.exe en el instalador. Cuanto pesa realmente el build mas chico y usable de ffmpeg para Windows (gyan.dev "essentials" vs BtbN, static, y si se puede achicar). Da numeros reales verificados.
   (b) Descargar ffmpeg la primera vez que se usa, cachearlo en %LOCALAPPDATA%/PanelMyS_state/bin/, con URL fija + verificacion sha256. Da URLs candidatas estables y como obtener el hash.
   (c) Comprimir en el NAVEGADOR con WebCodecs (el panel se abre en el navegador del usuario, Chrome/Edge modernos). Es viable sin librerias externas ni CDN (el panel no carga nada de afuera)? Que tan realista es muxear a MP4 a mano. Se honesto sobre la complejidad y el riesgo.
   (d) Cualquier otra que se te ocurra (Windows trae algo nativo? Media Foundation via ctypes? evaluá y descartá con razones).
   Recomendá una con un plan B explicito.

2. COMANDO. Dado ffmpeg disponible, dame el comando EXACTO para dejar un video listo para web, que:
   - Reencodee a H.264 (libx264) + AAC, yuv420p, con faststart (moov al principio, indispensable para que arranque rapido en el celular).
   - Convierta desde HEVC/H.265 de iPhone (que Chrome/Android no siempre reproduce) y desde .mov/.mkv/.avi/.webm.
   - CAPE la resolucion SIN deformar y respetando la orientacion: un vertical 9:16 y un horizontal 16:9 tienen que quedar bien. Da la expresion de scale que limita el LADO MAYOR (no el ancho) a por ejemplo 1080 o 720, con -2 para mantener paridad.
   - Baje el bitrate a un objetivo razonable para un clip de producto de muebleria de 15 a 90 segundos, apuntando a un archivo final de pocos MB. Elegi CRF o bitrate objetivo y justifica.
   - Arregle la ROTACION (los videos de celular traen matriz de rotacion en metadata; explicá el problema del display matrix y como evitar que quede acostado).
   - Quite metadata innecesaria.
   Explicá cada flag en una linea.

3. PROGRESO. Como leer el progreso de ffmpeg desde Python para mostrarle una barra al usuario: flag -progress pipe:1 -nostats, que campos emite (out_time_us, total_size, progress=continue/end), y como sacar la DURACION total de antemano (ffprobe? o parsear del stderr?). Si se puede evitar ffprobe (un binario mas), decilo.

4. WINDOWS. subprocess con CREATE_NO_WINDOW (la app es windowed: si no, parpadea una consola negra), como matar el proceso si el usuario cancela, timeout razonable, y por que hay que evitar shell=True.

5. LIMITES DE PUBLICACION. Con el cerebro descripto arriba (base64 a Git Data API, batches de 40 archivos, Cloudflare Worker free): que tope de tamano por video es seguro? Considera: memoria de un Worker de CF free, el tamano maximo practico de un blob por la API de GitHub, y que un batch de 40 archivos podria juntar varios videos. Recomendá (a) tope por archivo, (b) si hay que batchear por BYTES ademas de por cantidad, con el numero. Ademas: limites de repo de GitHub y de Vercel para archivos estaticos, y advertencia sobre que un repo git guarda TODAS las versiones de cada video para siempre.

Respondé en espanol, markdown denso, con numeros verificados y sin relleno.`, { label: 'invest:compresion', phase: 'Investigacion' })

phase('Diseno')

const disenos = await parallel([
  () => agent(CTX + '\n\n' + PEDIDO + '\n\nINVESTIGACION PREVIA:\n' + investigacion + `

TAREA: disena el BACKEND de la compresion en panel_server.py. Lee primero el endpoint /api/upload-pdf real y el patron de handlers del archivo para calcar el estilo (nombres en espanol, comentarios cortos, sin dependencias).

Entrega codigo concreto para:
1. Localizar el motor: funcion buscar_ffmpeg() que chequea, en orden, RES_DIR/bin/ffmpeg.exe (bundleado), %LOCALAPPDATA%/PanelMyS_state/bin/ffmpeg.exe (descargado), y el PATH del sistema. Devuelve ruta o None.
2. Si es None: endpoint que descarga el motor una sola vez (URL pinneada + sha256 + progreso + extraccion segura del zip reusando el _zip_seguro que ya existe en el archivo). Manejo de "sin internet".
3. POST /api/upload-video: recibe el archivo (ojo: el body puede pesar 500 MB; el panel de hoy lee el body entero en memoria? verificalo y si es asi propone leer a un archivo temporal en streaming por chunks). Valida extension/firma. Guarda a temporal. Sondea duracion, resolucion y orientacion.
4. Compresion en background con progreso consultable: propone el mecanismo (hilo + dict de trabajos con id + GET /api/video-progreso?id=), porque un POST bloqueante de 3 minutos rompe el navegador y el usuario no ve nada. Incluí cancelacion.
5. Resultado: escribe intranet/assets/_modulos/<key>.mp4, borra temporales SIEMPRE (try/finally), devuelve src, peso_original, peso_final, ancho, alto, orientacion y duracion.
6. Casos de borde: video ya chico y ya H.264 (se recomprime igual o se copia? decidí y justifica), ffmpeg falla, disco lleno, el usuario cierra el panel a mitad.
Codigo listo para pegar, frozen-aware, sin dependencias nuevas.`, { label: 'dis:backend', phase: 'Diseno' }),

  () => agent(CTX + '\n\n' + PEDIDO + '\n\nINVESTIGACION PREVIA:\n' + investigacion + `

TAREA: disena la EXPERIENCIA del usuario en el panel (herramientas/panel/web/app.js + styles.css). El usuario es el dueno de la muebleria, no tecnico. Lee primero como estan hechos hoy: subirPdfBloque, subirImgsGaleria (subida de archivos), toast(), confirmar() (popup propio), y el patron de los inspectores de bloque.

Diseña y entrega codigo concreto para:
1. El AVISO PREVIO que pidio el usuario. Escribi el TEXTO EXACTO en espanol rioplatense, claro y sin jerga. Debe explicar en una frase por que se comprime ("para que cargue rapido en el celular de los vendedores y se pueda publicar") y mostrar el peso actual. Decidí si es un confirmar() con "Comprimir y subir" / "Cancelar", o automatico con aviso. Justifica. Contemplá el caso de un video que YA esta liviano (no hay que asustar al usuario con un popup al pedo).
2. La barra de PROGRESO mientras comprime: que muestra (porcentaje, tiempo estimado, "no cierres el panel"), como consulta el endpoint de progreso, y el boton Cancelar.
3. El RESULTADO: mensaje tipo "Listo: pasó de 148 MB a 6,2 MB". Que se ve en el bloque despues.
4. El caso "falta el motor de compresion": el texto EXACTO del popup que le pide descargar por unica vez ("Necesito descargar una herramienta de 40 MB, una sola vez"), con su progreso y su manejo de error sin internet.
5. Errores en criollo: archivo que no es video, video muy largo, ffmpeg fallo. Nada de mensajes tecnicos crudos.
6. El video ya subido en el bloque: mostrar peso final y un boton "Reemplazar video".
Entrega el codigo JS/CSS listo para pegar, en el estilo del archivo (espanol, funciones cortas). Todo el texto visible al usuario, en espanol rioplatense.`, { label: 'dis:ux', phase: 'Diseno' }),
])

phase('Critica')

const critica = await agent(CTX + '\n\n' + PEDIDO + `

Sos un revisor ADVERSARIAL y despues el arquitecto final. Te paso una investigacion y dos disenos (backend y UX) para agregar compresion de video al panel.

PRIMERO, tratá de romperlo. Verificá leyendo el codigo REAL de panel_server.py y app.js:
- El servidor de hoy, como lee el body de un POST? Lee todo a memoria con read(Content-Length)? Entonces un video de 500 MB revienta la RAM: confirmá o desmentí con la linea exacta.
- El servidor es http.server monohilo o ThreadingHTTPServer? Si es monohilo, una compresion de 2 minutos CONGELA todo el panel y el polling de progreso nunca responde: confirmá con la linea exacta. Es el bug mas grave posible de este diseno.
- El limite de tamano actual del upload de PDF: de donde sale y aplica tambien al video?
- Los temporales: donde caen?
- El swap del auto-updater (rename de la carpeta %LOCALAPPDATA%/PanelMyS) borraria un ffmpeg.exe cacheado dentro de la carpeta de la app? Por eso el cache va en PanelMyS_state: verificá que el diseno lo respete.
- Antivirus: descargar y ejecutar un .exe nuevo desde %LOCALAPPDATA% en PCs de sucursales, que riesgo real tiene (SmartScreen/Defender) y como se mitiga.
- Que pasa si dos personas suben videos a la vez, o si el mismo bloque se sube dos veces (colision del nombre de archivo por key).

DESPUES, entregá el PLAN FINAL consolidado: decision de motor (con plan B), tope de tamano, cambios por archivo en orden, y la lista de verificaciones a correr. Marcá explicitamente lo que hay que CORREGIR de los disenos que te pasaron.

DISENO BACKEND:
` + disenos[0] + `

DISENO UX:
` + disenos[1] + `

Respondé en espanol, markdown denso, accionable, sin relleno. Los bugs confirmados van primero, con archivo:linea.`, { label: 'critica:final', phase: 'Critica' })

return { critica, investigacion, disenos: disenos.filter(Boolean) }
