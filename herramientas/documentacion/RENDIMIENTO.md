# FASE 5 — Rendimiento y estados de carga
**Intranet de vendedores · 29-ago-2026 · trabajo y medición LOCAL (working tree, sin publicar)**

Archivo tocado: `intranet/index.html` (+ un asset NUEVO: `intranet/assets/logo-nav.png`).
No se tocó `modulos.js`, ni ningún asset existente, ni `web2/`. Sin git.

---

## 1. El elemento LCP, identificado

| Página | Elemento LCP | Confirmado en |
|---|---|---|
| Portada (cartelera) | **TEXTO**: `p.m-p` del primer post («Ya está el video del embalaje especial…») | Lighthouse prod 28-ago, Lighthouse local y PerformanceObserver (Playwright) — los tres coinciden |
| Descargables | **TEXTO**: `p.m-lead` («Todo el material para descargar y compartir…») | Lighthouse local + PerformanceObserver |

**No es una imagen, ni el logo.** Es el primer texto del contenido pintado por JS. Por eso los 2,9 s de prod se descomponían en TTFB 1,24 s + *element render delay* 0,53 s (y en Descargables local el render delay era 1,52 s). Las dos causas del render delay, medidas:

1. **La hoja de Google Fonts era EL único recurso render-blocking** (auditoría `render-blocking-insight`: score 0, ahorro estimado 1.870 ms local). El primer pintado seguía 1:1 a la respuesta de `fonts.googleapis.com`: en corridas reales el CSS tardó 1,1 s → FCP 1,2 s; tardó 4,2 s → FCP 4,4 s; y en una corrida tardó **14–20 s con la página BLANCA todo ese tiempo**. El sitio entero era rehén de la latencia de Google.
2. **La cadena de datos era serial, al final, y sin caché**: parsear el documento entero (290 KB) → recién ahí pedir `modulos.js?v=<timestamp>` (257 KB) → esperar → pedir `galerias.js?v=<timestamp>` → esperar → pintar. El `?v=Date.now()` cambiaba EN CADA VISITA, así que el navegador volvía a bajar los 257 KB completos aunque nada hubiera cambiado (nunca un 304).

El CLS también quedó explicado con nombre y apellido: **el `div.footer`**. Antes de que llegue el JS el main está casi vacío y el pie queda a la vista (~364 px); al pintarse el feed, el pie sale disparado hacia abajo → 0,058–0,092 de CLS según la página. (El swap de Montserrat aportaba una parte menor; se cubrió igual.)

---

## 2. Antes / después

### Lighthouse local móvil (localhost:8815, mismas condiciones, sin CDN ni gzip)

| Métrica | Portada ANTES | Portada DESPUÉS | Descarg. ANTES | Descarg. DESPUÉS |
|---|---|---|---|---|
| Performance | 69 | **73–78** | 74 | **73** ¹ |
| FCP | 4,0 s | 2,2–3,8 s ¹ | 2,9 s ¹ | 3,8 s ¹ |
| LCP | 5,4 s | **4,8 s** | 5,0 s | **4,8 s** |
| CLS | 0,073 | **0** | 0,089 | **0** |
| TBT | 0 ms | 0–160 ms | 0 ms | 0 ms |
| Peso total | 874 KiB | **620 KiB** (−29 %) | 810 KiB | **620 KiB** (−23 %) |
| Render-blocking | FALLA (−1.870 ms) | **PASA** | FALLA | **PASA** |

¹ El Lighthouse local tiene ±1 s de ruido entre corridas: el server local (`python http.server`) no comprime, así que el documento de 290 KB domina la simulación — en prod Vercel lo sirve gzip (~60 KB) y ese piso desaparece. Por eso la señal fuerte está en la tabla siguiente.

### Playwright con throttling estable (red 1,6 Mbps/150 ms + CPU 4×, mediana de 3, A/B contra la versión HEAD servida idéntica)

| Métrica | Portada ANTES | Portada DESPUÉS | Descarg. ANTES | Descarg. DESPUÉS |
|---|---|---|---|---|
| FCP | 14.944 ms (rango 1.008–20.508: lotería de Google Fonts) | **1.412 ms, estable ±70** | 920 ms | 1.420 ms ² |
| LCP | 17.276 ms (mejor corrida: 4.724) | **3.692 ms, estable** | 4.588 ms | **3.784 ms** |
| CLS | 0,060 | **0** | 0,092 | **0,004** |

² Único retroceso, y es un canje deliberado: los datos ahora empiezan a bajar durante el parseo y compiten por el ancho de banda con el documento (+0,5 s de FCP en red angosta), a cambio de −0,8 s de LCP, que es cuando el vendedor VE el contenido. En prod con HTTP/2 y gzip la competencia pesa menos.

**Sin regresiones funcionales**: buscador global con «cuotas» = 13 resultados antes y después · axe-core (copia de la casa, tags A/AA incl. WCAG 2.2) = **CERO violaciones** en portada, Descargables y Manual · cero desbordes en 1440/768/390 × 3 páginas · feed, módulos, galerías y lightbox pintan igual (capturas).

---

## 3. Qué se aplicó (y por qué)

1. **Google Fonts sin bloquear** (`media="print" onload` + `<noscript>` de respaldo) + **preconnect a `fonts.gstatic.com`** (faltaba; solo estaba el de googleapis) + **se quitó el peso 300** de la URL (no lo usa ningún archivo: los usados son 400–800). El texto pinta al instante con el respaldo y Montserrat entra cuando llega.
2. **Respaldo tipográfico con métricas ajustadas** (`@font-face 'Montserrat-respaldo'`, Arial con `size-adjust 112,65 %` + overrides): el swap casi no mueve nada.
3. **Arranque temprano y paralelo de los datos**: `modulos.js` y `galerias.js` se piden desde el `<head>` (antes esperaban el parseo completo) y en paralelo (antes en serie), con una compuerta que pinta recién cuando documento Y datos están. Orden `modulos → muro-demo` conservado (solo en local).
4. **Chau `?v=timestamp`**: con el sufijo, cada visita bajaba 257 KB sí o sí. Sin él, Vercel manda `ETag` + `max-age=0, must-revalidate`: cada visita PREGUNTA igual si hay versión nueva (frescura idéntica) pero la respuesta habitual es un 304 vacío. ⚠️ *Al publicar, verificar una vez los headers reales: `curl -sI https://…/modulos.js | grep -i "etag\|cache-control"`.*
5. **`mediosDelPanel()`**: corrige el string del panel antes de pintarlo (modulos.js intacto): toda `<img>` gana `decoding="async"`; la primera imagen del primer post visible pierde `loading="lazy"` y gana `fetchpriority="high"` (hoy el primer post es video, pero el día que sea foto, esa foto es el LCP y el lazy la mataba); y en celular los `<video>` con proporción escrita (`--arw/--arh`) arrancan `preload="none"` — el `preload="metadata"` del marcado disparaba **2×65 KB de mp4** antes de que `videosDelFeed()` llegara a apagarlo (regresión de carrera, verificada: ahora 0 pedidos de mp4 en el load).
6. **CLS estructural**: `main` con `min-height:100vh` + columna flex + `.footer{margin-top:auto}` → el pie nace abajo del pliegue y el contenido aparece en lugar reservado. CLS 0,060/0,092 → **0/0,004**.
7. **Esqueletos** (CSS + 15 líneas de JS): shimmer suave con los grises de la casa (`#E8E4DF`→`#F7F5F1`, 1,8 s) en las placas de galería (`.gcard .gimg`), las galerías del feed y las fotos del feed (`.mu-cuerpo .m-img img`, con alto mínimo de 170 px mientras baja). Cada `<img>` recibe la clase `lista` al cargar **o fallar** (listener en captura + MutationObserver; sin brillo eterno sobre un 404). `prefers-reduced-motion`: gris plano sin animación. Verificado: al abrir un grupo, 4/4 placas apagan el shimmer al llegar; la foto del feed reserva la caja EXACTA (el navegador ya conoce el tamaño por el header del PNG) → cero salto.
8. **Logo liviano**: `logo.png` (151 KB, 926×419) se mostraba a 92–144 px. Nuevo asset `assets/logo-nav.png` (18 KB, 280×127, alcanza @2,7×) referenciado solo desde el header, con `width/height`. **−132 KB en cada página.** El original queda intacto.
9. **Área táctil del slider de video** `.mr-linea` 20→24 px (solo la zona de toque; el riel visible sigue de 3–5 px). Era la única falla axe/Lighthouse (WCAG 2.2 AA 2.5.8) — **preexistente** (la versión HEAD también da 96 en Lighthouse-A11y por esto); con el fix, axe queda en CERO y A11y local en 100.

### Qué se descartó (y por qué)

- **`content-visibility:auto`**: TBT ya es 0–40 ms, DOM chico (271/825 nodos) — no hay costo de render que amortizar; beneficio no medible y riesgo gratuito. (El buscador igual está a salvo: indexa `window.MODULES`, no el DOM — verificado además con el conteo «cuotas».)
- **`srcset/sizes` en placas**: imposible sin generar variantes de archivo, y los nombres los referencia `modulos.js` (prohibido tocarlo). Va como propuesta para el panel (abajo).
- **Recomprimir assets existentes**: prohibido con razón — el panel los regenera y el HTML publicado referencia esos nombres exactos.
- **Preload del `modulos.js`**: con `<link rel="preload">` no se puede porque la URL llevaba versión dinámica; resuelto mejor con el arranque temprano real.
- **Esqueleto estático del feed pre-render**: el `#lobby` nace `hidden` y se muestra en el mismo instante en que se pinta el feed — un esqueleto ahí adentro no se vería nunca. El hueco pre-render lo resuelve el `min-height` del main (el hero real ya pinta arriba).
- **Service workers / dependencias**: prohibido y innecesario.

---

## 4. Inventario de imágenes sobredimensionadas (servido vs. mostrado, celular 390 px @3×)

**El hallazgo grande: abrir todos los grupos de Descargables en un celular baja 45,9 MB (47 placas).**

| Caso | Servido | Mostrado (CSS) | Necesita (@3×) | Exceso píxeles | Peso |
|---|---|---|---|---|---|
| `descargables_gal_…0565_0.png` (línea exterior) | 1108×1568 | 110×138 | 330×413 | 3,4× | **2.173 KB** |
| `descargables_gal_…2698_0.png` | 882×1568 | 110×138 | 330×413 | 2,7× | 1.859 KB |
| `descargables_gal_…8192_2.png` (Sicilia) | 882×1568 | 110×138 | 330×413 | 2,7× | 1.813 KB |
| `descargables_gal_…7249_5.png` | 1568×882 | 110×138 | 330×413 | 4,8× | 1.566 KB |
| …y ~40 más del mismo patrón | ~882–1568 px | 110×138 | 330×413 | 2,7–4,8× | 0,7–1,6 MB c/u |
| `embajadores/Programa de Embajadores.jpg` | 1548×2189 | 255×360 | 764×1080 | 2× | 785 KB |
| `logo.png` (ya resuelto con `logo-nav.png`) | 926×419 | 92–144 px | 276×432 | 3,4× | 151 KB → 18 KB |

Además del exceso de píxeles, **las placas son PNG siendo fotos**: el desperdicio real en bytes es ~30–50× (una miniatura 330×413 en WebP/JPG pesa 25–60 KB, no 1–2 MB). Los módulos `promos_bancarias`/`promos_mensuales` (8,5 MB en assets) hoy no aparecen en el nav — peso dormido, no urgente.

## 5. Propuesta para el panel (quien sube las imágenes)

Como ya hace con el póster del video, **el panel debería generar variantes al subir cada placa**:

- `nombre_thumb.webp` (~440 px de lado mayor, calidad 80) → para la grilla de la galería (`.gimg`). ~30–60 KB.
- `nombre_zoom.webp` (~1200 px) → para el lightbox. ~150–250 KB.
- El **original intacto** → sigue siendo lo que baja el botón «Enviar/Descargar» (el vendedor manda la calidad completa al cliente, como hoy).
- En el HTML que escribe el panel: `src` → thumb, y el lightbox/descarga apuntando a zoom/original. Con eso, `srcset/sizes` ya ni hace falta en la grilla.
- Efecto estimado: **abrir toda la galería pasa de 45,9 MB a ~1,5–2,5 MB (−95 %)**, y cada grupo abre en ~1 s con datos móviles en vez de decenas de segundos.
- Para contenido viejo: un script de una sola pasada en el panel que genere thumbs de lo ya subido y reescriba su propio HTML (es quien es dueño de esos nombres).

## 6. Tiempo real («ver la publicación nueva sin refrescar») — solo presupuesto, NO implementado

| | **Polling con revalidación (recomendado)** | SSE / WebSocket |
|---|---|---|
| Cómo | Cada 60–120 s, `fetch('modulos.js', {cache:'no-cache'})` con `If-None-Match` (el ETag lo da Vercel gratis). 304 → nada; 200 → re-render del feed + aviso «hay novedades» | Backend persistente que empuje eventos |
| Backend | **Ninguno** (Vercel estático ya alcanza) | No existe hoy: función/edge con conexiones vivas, o un servicio (Pusher/Ably/Supabase Realtime) |
| Costo de tráfico | 304 vacío ≈ 200–300 bytes → ~15 KB/hora por vendedor abierto | Conexión abierta por dispositivo, keep-alives, reconexiones |
| Costo de armar | ~30–50 líneas en index.html, un día con pruebas | Días + infra nueva + otra cosa que se puede caer |
| Latencia de novedad | 1–2 minutos (sobra: se publica unas veces por día) | Segundos (nadie lo necesita acá) |
| Riesgos | Casi ninguno; cuidar re-render sin pisar lo que el vendedor está leyendo (pintar solo si cambió el ETag y avisar con una chapita) | Estado, reconexión, límites de conexiones del plan |

**Recomendación: polling de 90 s con ETag.** Nota técnica: conviene comparar el ETag guardado y NO re-pintar si el vendedor tiene el buscador o un post abierto — mostrar la chapita «Hay publicaciones nuevas» (el componente de aviso ya existe) y re-pintar al tocarla. Decisión del dueño; nada de esto quedó implementado.

---

## 7. Capturas (en `qa/screenshots/`)

- `f5-base-portada.png` / `f5-base-descargables.png` — estado ANTES (celular)
- `f5-final-portada.png` / `f5-final-descargables.png` — estado DESPUÉS (celular)
- `f5-desktop-portada.png` / `f5-desktop-descargables.png` — 1440 px, sin cambios de layout
- `f5-esqueleto-galeria.png` — placas en shimmer al abrir un grupo con red lenta
- `f5-esqueleto-feed.png` — foto del feed bajando: el brillo ocupa la caja final exacta (post demo inyectado solo en runtime para la captura; el archivo real no tiene posts con foto hoy)
- `f5-esqueleto-reduced-motion.png` — con `prefers-reduced-motion`: gris plano, sin animación
- `f5-galeria-cargada.png` — mismo grupo ya cargado: shimmer apagado (4/4 con clase `lista`)

## 8. Notas para después de publicar

1. Verificar headers de `modulos.js` en prod (el punto 4 del §3): debe verse `etag` y `cache-control: … must-revalidate`. Si algún día Vercel cambiara a caché larga sin revalidación, reponer un `?v=` PERO fijo por versión (escrito por el panel al guardar), nunca `Date.now()`.
2. Re-correr Lighthouse contra prod y comparar con `qa/lighthouse-intranet-prod.report.json` (28-ago: Perf 92 · LCP 2,9 s · CLS 0,058). Con fuente sin bloquear + datos en paralelo + 304 + CLS 0, el LCP prod debería quedar bien abajo de 2,5 s.
3. En la máquina de trabajo del dueño existe `muro-demo.js`: sigue cargando después de `modulos.js` como siempre (solo en localhost). Si el demo alguna vez usara `GALLERIES`, avisar — hoy galerias.js baja en paralelo.
4. La falla de área táctil `.mr-linea` era preexistente (HEAD también da 96); quedó en 24 px y axe en cero. Si la fase de accesibilidad prefiere otra solución visual, tocar solo esa regla.
