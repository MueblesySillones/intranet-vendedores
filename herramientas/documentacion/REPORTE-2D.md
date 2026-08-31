# REPORTE FASE 2D — consolidación del sistema de diseño (panel web2)

**Fecha:** 29-08-2026 · **Agente 2D** · Alcance: `herramientas/panel/web2/` (styles.css, rediseno.css, panel_datos.css, app.js, index.html; muro.js revisado, sin cambios). Ni un valor dentro de las reglas `.doc-preview` (espejo del sitio publicado): las 232 líneas de esas reglas se delimitaron por parser CSS (22 tramos, incluidas continuaciones multilínea que no dicen "doc-preview") y todas las pasadas las saltearon.

## 1. Conteos antes → después (fuera del espejo `.doc-preview`)

| Archivo | `font-size` px totales | valores distintos | radios literales | radios distintos | sombras negras `rgba(0,0,0,…)` |
|---|---|---|---|---|---|
| styles.css | **113 → 37** | 18 → 8 | **75 → 4** | 20 → 3 | **7 → 0** |
| rediseno.css | **35 → 11** | 12 → 5 | **36 → 2** | 15 → 2 | 0 → 0 |
| panel_datos.css | **40 → 11** | 15 → 8 | **1 → 0** | 1 → 0 | 0 → 0 |

| Archivo | `.cssText=` | `.style.x=` reales |
|---|---|---|
| app.js | **32 → 0** | 46 → 35 |
| muro.js | 0 → 0 | 5 → 5 (posicionamiento medido) |

Nota sobre el "78" de la auditoría: ese conteo de `.style.x=` incluía los 32 `.cssText=` (el patrón los matchea). Los `.style.x` reales eran 46; quedaron 35, todos dinámicos o anotados (§5).

## 2. Migración C1 por grupos (brecha 1), en el orden del plan

- **(a)** `12.5px→--t-sm`, `13/13.5px→--t-md`: 76 líneas (42 styles + 17 rediseno + 17 panel_datos). Pasada verificada antes de seguir.
- **(b)** `11/11.5/10.5/10px→--t-xs`: 37 líneas (22+4+11). Los **cuatro 9.5px** fuera del espejo quedaron como literal CON comentario, por el criterio del prompt (difieren >1px del token y son rótulos mínimos): `.col-badge`, el chip `data-nom` del editor (`.gb-block.is-selected:before`), `.hist-chip` y `.dt-dt-t`.
- **(c)** sombras negras → `--sombra-*` cálidas equivalentes: `.console`→3, `#toast`→3 (nivel "flotante"), `.modal-box`→4 (geometría idéntica), `.ord-flota`→2, `.ord-flota.alzada`→3 (calco exacto en negro de la sombra 3), `#gbFloat`→3, `.img-lightbox img`→4 (sobre telón oscuro la diferencia de alfa no se percibe). El único `rgba(0,0,0,…)` que queda es el **fondo** de `.ord-hueco` (tinte al 2.5%: no es sombra).
- **(d)** radios → `--r-*`: el mapa del prompt (12→md, 9/8→sm, 16→lg, 999→full, 6/7→xs) + cercanos con Δ≤1px (10→sm, 11/13→md, 5→xs) + píldoras con render idéntico (99px→full; el 20px de `.col-badge`→full, comentado) + marcos 14/18→lg + compuestos por componente (`6px 6px 6px 0`, `0 0 10px 10px`, etc.). **Quedan con comentario en el código**: dos 4px (chip de código y foco del contenteditable: `--r-xs` los pasa de rosca) y un 3px (`.gb-droplinea`: mitad exacta de su alto). **Quedan sin comentario, anotados acá**: los dos 20px del bottom-sheet de rediseno.css (elección fresca de la 2a/2b que no pisé) y un `0 !important` (no tokenizable).
- **(extra, riesgo cero)** los tamaños que ya coincidían con la escala: `15→--t-lg`, `17→--t-xl`, `20→--t-2xl` (16 líneas, mismo píxel renderizado).

**Qué quedó sin migrar y por qué** (59 font-sizes en total): los **12px** (20 apariciones) no están en ningún grupo del plan — quedan a mitad de camino entre `--t-xs` (11) y `--t-sm` (12.5); es una decisión de escala para el dueño del plan, no la tomé por él. Los display (22/24/26/28/32) y los intermedios 14/14.5/16/18/19 no tienen token en la escala de 6 pasos. Más los cuatro 9.5px documentados.

## 3. Bordes de control (brecha "A2 a medias")

Descubrimiento: la pasada A2 **ya existía** en styles.css (l.≈940) como lista explícita `border-color:var(--linea-int)` sobre `.btn`, `.tab`, `.col-act`, `.ctipo`, `.gal-add`, inputs de `.fld`, `.insp-input/.insp-sel`, `.doc-bar-in`, `.col-palabra input` — con el comentario de por qué es lista y no barrido ("un borde fuerte en las 25 tarjetas de la paleta seria una reja"). Lo hecho fue **extenderla**, no duplicarla:

- **styles.css**: se sumó `.doc-muro-fij` (checkbox-píldora de la barra del muro).
- **panel_datos.css**: bloque A2 espejo al final, mismo criterio escrito: `.dt-suelta textarea`, `.dt-conectar input[type=text]`, `.dt-buscar-f input`, `.dt-vend-i select`, `.dt-volver`, `.dt-mas`.
- **rediseno.css**: `.co-arch-sel` (el select "Archivar en": control aislado sin escalera de hover propia).

**Dudas que quedaron con `--line`, anotadas** (regla "en caso de duda, dejá"): `.dt-sw-p` (el interruptor se ve por forma — pastilla+perilla sobre `--mesa` — y su hover ya sube a accent2; comentado en el CSS), `.co-clip` y `.co-date` (reposo quieto a propósito → accent2 recién en hover: escalera dibujada por el rediseño del compositor, comentado en el CSS), `.insp-check` (fila-checkbox de B7 que se lee como ítem de lista), `.seg`/`.view-toggle` (segmented: es la brecha del componente duplicado, fuera de esta fase), `.mf.on`, `.cal-at`, `.blocks-palette button`, `.bk-iconmini button`, `.icon-opt`, `.gal-thumb` (opciones repetidas), `.dt-rc` (chip de estado, no botón), `.dt-mail-v` (visor de solo lectura).

**Código muerto detectado, no tocado**: `.bk-body textarea/input[type=text]` y `.rt-toolbar`/`.rt-editor` — 0 usos en app.js/index.html (el editor viejo). Candidatos a poda en una fase de limpieza.

## 4. Escala de espaciado (brecha 6)

Declarada en el `:root` de styles.css con su comentario: `--sp-1:4px · --sp-2:8px · --sp-3:12px · --sp-4:16px · --sp-5:24px · --sp-6:32px` (base 4). Sin barrido de paddings, tal como pide el plan. Ninguna línea que esta fase tocó pedía espaciado, así que la adopción real arranca en la próxima pasada que toque una línea con padding/gap por otra razón.

## 5. Inline styles de app.js (brecha 2)

**`.cssText=`: 32 → 0 (meta cumplida).** Los 32 eran estáticos. Fueron a clases del mismo vocabulario `insp-*` del inspector — nuevas: `insp-col`, `insp-col-fina`, `insp-lista`, `insp-num`, `insp-input.insp-flex`, `insp-img-prev`, `insp-nota-ok`, `insp-rompe`, `insp-contador` (+`.pasado`), `insp-cab-t`, `insp-item-t`, `insp-quitar-txt`, `insp-add-lado`, `btn-lado`, `insp-nota`, `#gbInspector .insp-ayuda.roja`, y la def de `.bk-lbl` — o a componentes que **ya existían**: `insp-caja` (2), `insp-sel` (2), `insp-input` (2), `insp-add` (3).

Tres arreglos reales que los cssText tapaban:
1. `link.className='insp-inp'` — clase **inexistente** (typo); el cssText a mano replicaba `insp-input`. Corregido a `insp-input` (comentado en el código).
2. Las dos **cruces rojas fijas** (inspector de tarjetas y de chat) eran pre-B7: pasaron a `insDel()` — LA cruz del inspector (gris, roja al hover), exactamente la unificación que el comentario de B7 documenta.
3. El aviso "Meta lo va a rechazar" pintaba borde/fondo a mano en dos lugares → variante `.insp-ayuda.roja`.

**`.style.x=`: 46 → 35.** Migrados los 11 obviamente estáticos y triviales: `flex` del input de galería (→`insp-flex`), el pintado de error ×2 (→`.roja`), el contador pasado de límite ×2 (→`classList.toggle('pasado')`), `marginBottom` de `lbl()` (→`.bk-lbl`), `margin` de `insNota()` (→`.insp-nota`), dos `margin='0'` redundantes con `.fld-note{margin:0}` (borrados). **Los 35 que quedan, todos con razón**: geometría medida de los drags (hueco/fantasma/ghost), posicionamiento de barras y popovers flotantes, anchos calculados de barras de datos (%), `backgroundImage` con URL dinámica, colores de dots que vienen del dato (`c.hex`), el protocolo dinámico de color de los estados de subida (`poner(txt,color)`), toggles de display del buscador y los drags, y 2 márgenes puntuales de `fld-note` ahora comentados ("no amerita clase"). En muro.js los 5 son posicionamiento medido: quedan.

Los `style="…"` de templates HTML (32 según la auditoría) no estaban en el alcance del ítem 4 y no se tocaron.

## 6. Checkboxes fuera del inspector (ítem opcional)

Los del plan B7 (`pdf.descargable` ×3, `situacion.conResp`) **ya estaban** migrados a `insCheck()` con el default inicializado antes de leer el checked. El único `label.fld.row` que quedaba era `#dReady` ("Disponible / Próximamente" del editor de módulo): migrado al componente `insp-check` **sin tocar JS** — el estado prendido se resuelve con un gemelo `:has(> input:checked)` de `.insp-check.on`, en regla separada para que un navegador sin `:has` no invalide el `.on` de los demás. Su default `ready !== false` ya se inicializaba en la carga (l.570) y el undo escribe `checked` directo, que con `:has` queda sincronizado gratis — sin riesgo de dar vuelta bloques publicados.

## 7. Incidente de la corrida (transparencia)

Un heredoc de bash colapsó una doble barra invertida y Python evaluó la secuencia resultante («\1») como escape octal: aparecieron **102 bytes `0x01`** donde iba el grupo capturado en los reemplazos de radios (grupo d). Detectado por chequeo de bytes de control, reparado limpio (ningún original tenía espacio tras `border-radius:`, así que el byte sobraba), y la suite QA se relanzó desde cero sobre archivos sanos. También se normalizaron los finales de línea a **CRLF** (convención dominante del proyecto) que mis escrituras habían pasado a LF. Verificación final: 0 bytes de control en los 6 archivos, llaves CSS balanceadas, `node --check` OK en app.js y muro.js tras cada edición.

## 8. Resultado de la suite QA (`correr_todo.py`, puertos 8143/8813, sandbox)

| Bloque | Resultado | Detalle |
|---|---|---|
| **t1 crawl** | **0 fallas** · 34 ok · 8 avisos | avisos = targets <32px preexistentes (botones de 31px del editor, `dt-sw-i` 1×1 que son falsos positivos documentados) · 18 pantallas |
| **t2 flujos** | **0 fallas** · 19 ok · 2 avisos | F5 ocultar ("ofrece Mostrar: False") y F17 Atrás del navegador ("about:blank"): estados INCONSISTENTE no bloqueantes, en flujos que esta fase (solo estilo) no tocó |
| **t3 intranet** | **0 fallas** · 29 ok · 2 avisos | criterios de diseño conocidos (letra del manual 14.5px, columna del feed 692px) — territorio de la fase de intranet |
| **t4 visual** | falló contra la baseline vieja, **como estaba previsto** | 9 señaladas: 3 del panel (mías) + 5 de intranet (del agente paralelo, ya commiteadas) + 1 timeout transitorio; diffs revisados uno a uno (§9) |

## 9. Diffs visuales de t4, uno por uno

**Del panel (míos — los tres, cambios buscados de tokens):**
- `panel-modulos-1440` (0.98%): botones y links "Abrir" crecen 13→13.5px (`--t-md`), reflow del título truncado del módulo 4, esquinas de los iconos 11→12px (`--r-md`). Intencional.
- `panel-editor-1440` (2.28%): radios de la botonera (10→9), rótulos de la paleta 10/10.5→11px (`--t-xs`) que corren los grupos hacia abajo, tiles con radio 10→9, select de la barra 13→13.5. Intencional.
- `panel-datos-1440` (alto 2908→2889, −19px): encogimiento acumulado de los 11.5→11px en una página larga; captura actual revisada a ojo: intacta. Intencional.
- `panel-cartelera-1440` y `panel-metricas-1440`: dentro de tolerancia ya contra la baseline vieja (≤0.5%).

**De la intranet (no míos):** portada/embalaje/descargables/390 con +80px de alto y whatsapp distinto — es el trabajo **ya commiteado** del agente de intranet (columna de lectura, ritmo vertical, advertencia, contraste AA); el sandbox copia `intranet/` del repo y lo refleja.

**Baseline regenerada** con `correr_todo.py --capturar-baseline`: **10/10 capturas OK** (exit 0). Pantallas que cambiaron respecto de la baseline anterior: `panel-modulos-1440`, `panel-editor-1440`, `panel-datos-1440` (por esta fase) e `intranet-portada-1440`, `intranet-embalaje-1440`, `intranet-descargables-1440`, `intranet-whatsapp-1440`, `intranet-portada-390` (por la fase de intranet). `panel-cartelera-1440` y `panel-metricas-1440` sin cambio perceptible.

**Corridas de control contra la baseline nueva** (2× `--solo t4 --sin-sandbox`): el panel dio **5/5 verde** en la primera; en la segunda flaqueó la captura de Datos (salió 1440×900 = solo el viewport: el reporte tarda a veces más que los 8s de espera — limitación que el README de la suite ya documenta). La intranet mostró dos inestabilidades PROPIAS entre corridas: un `goto` que a veces excede los 30s, y la **portada difiere sola** porque el video del feed avanza entre capturas (el diff pinta únicamente el cuadro del reproductor, "0:18/0:29"). Ninguna de las tres es de esta fase; quedan señaladas para el dueño de la suite (congelar el primer frame del video y estirar los dos timeouts).

## 10. Pasada visual propia (Playwright, 5 pantallas a 1440)

Capturas en `capturas-2d/` junto a este reporte (`2d-cartelera`, `2d-modulos`, `2d-datos`, `2d-metricas`, `2d-editor`): las cinco revisadas a ojo — compositor, tarjetas, KPIs, tablas, paleta e inspector del editor en su lugar, sin desbordes nuevos ni componentes rotos. (Detalle de método: el editor se captura último porque es un overlay fijo que tapa la navegación lateral.)

## Para la próxima fase (deuda que dejo escrita)

1. Decidir los **12px** (¿`--t-sm` o `--t-xs`? 20 apariciones esperando una regla).
2. `insp-quitar-txt` ("Quitar paso") → cruz de `insDel` cuando se toque ese inspector (comentado en el CSS).
3. Poda del código muerto `.bk-body` / `.rt-toolbar` / `.rt-editor`.
4. Estabilidad de t4: congelar el video de la portada y los timeouts de `goto`/Datos.
5. El segmented duplicado (Cartelera vs `.seg-b`) sigue siendo la brecha 5 del DESIGN-SYSTEM.
