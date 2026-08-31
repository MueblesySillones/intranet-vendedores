# REPORTE FASE 2C — Legibilidad de la vista del vendedor

**Fecha:** 29-08-2026 · **Agente 2C** · Un solo archivo tocado: `intranet/index.html` (+95 líneas de CSS, 0 borradas, diff limpio). `modulos.js`, `herramientas/` y el sitio en producción: intactos. Sin commits.

## Qué se cambió y dónde (líneas del index.html editado)

| Bloque | Líneas | Qué hace |
|---|---|---|
| **Columna de lectura** | 283–298 | `#secBody > .manual{ --col-texto:545px }` + `max-width` SOLO en los bloques de texto (`.m-lead, .m-p, .m-h, .m-h2, .m-sub, .m-kicker:not(.plegable), .note, .m-warn, .checklist, ul, ol`), alineados a la izquierda. Galerías, tablas, videos, imágenes, KPIs, barras y tarjetas siguen a 760px. |
| **Espejo `.m-h2`** | 300–301 | El panel emite subtítulos `.m-h2` pero la intranet nunca los estiló (se veían como texto común). Copia exacta de la regla del panel (`web2/styles.css:578`). |
| **Ritmo vertical** | 303–330 | Piso de 12px entre bloques `.db` (por colapso de márgenes: gana el margen mayor existente), aire ARRIBA de los títulos (kicker 26px, `.m-h` 18px, `.m-h2` 16px, destacado `.m-lead` 14px), pares pegados (kicker→título 12px, título→subtítulo 4px, con `:has()` para cuando cada pieza viene en su propio `.db`) y reset del primer bloque. |
| **Advertencia `.m-warn`** | 423–433 | El contrato compartido con el panel, EXACTO al carácter (4 reglas). Comentario aclara que es distinto de la nota verde y que el panel tiene el espejo. |
| **Impresión** | 1771–1806 | Primer `@media print` del sitio: tokens a blanco/tinta, sin sombras, se oculta el cromo (top, tabbar, menú, buscador, lightbox, botonera, filtros, pies de acción `.mu-pie`, "Ver publicación completa", botones, controles del deck), recortes expandidos (`.recortado` sin max-height ni degradé), galerías en grilla simple de 3 con las secciones plegadas abiertas, `break-inside:avoid` en piezas chicas, y la barra de controles del `<video>` oculta. |

## Los números de las verificaciones (a)–(g)

**(a) Caracteres por línea (párrafo `.m-p` del módulo Embalaje, 1440):**
- Antes: 760px → **104,8** por la fórmula del spec (`ancho/(14,5×0,5)`); 101,8 caracteres reales medidos con la métrica de la Montserrat cargada (canvas).
- Después: **545px → 75,2 por la fórmula (dentro de 60–78) y 73,0 caracteres reales (dentro de 60–75)**. En ch CSS: 56,8ch (el "0" de Montserrat mide 9,599px = 0,662em).
- A 390: 354px útiles → 48,8 por fórmula (el tope no muerde en celular, como corresponde).

**(b) Gaps entre bloques del manual (Embalaje, mismos pares que midió la auditoría):**
- Antes: `12, 14, 0, 14, 12, 0, 12, 0, 12, 14, 0, 14, 16` — los cuatro 0: checklist→destacado, párrafo→kicker, título→subtítulo, checklist→kicker.
- Después: `12, 14, 14, 14, 12, 26, 12, 4, 12, 14, 26, 14, 16` — **ningún 0**, idéntico a 1440 y 390. Títulos de sección: 26px arriba vs 12px abajo (más aire arriba, como pedía el spec). El 4 es el subtítulo pegado a su título, deliberado.

**(c) `.m-warn` inyectado por JS:** captura en `qa/screenshots/2c-mwarn.png`. Computed styles = contrato exacto (flex, gap 12, fondo rgb(251,239,236), borde 1px rgb(232,197,189), filo izquierdo 4px rgb(180,35,31), radio 12, padding 14/16, texto rgb(90,38,32) 14,5px/600, line-height 22,475px = 1,55, ícono 20×20). Contraste #5A2620 sobre #FBEFEC = **10,77:1** (a mano, WCAG) y axe con el bloque presente: 0 violaciones.

**(d) axe-core WCAG A/AA (mismo axe.min.js de la auditoría):** portada **0**, #embalaje_especial **0**, #descargables **0**, #whatsapp **0**. También 0 con el `.m-warn` de prueba inyectado.

**(e) Desbordes horizontales:** 0px en las 4 vistas × 3 anchos (1440/768/390) = 12 combinaciones.

**(f) Feed de la portada:** la tarjeta `.mu-post` sigue midiendo **692px a 1440** (igual que antes del cambio; el tope de texto va scopeado a `#secBody > .manual` y no toca `.mu-cuerpo .manual`, `.dk-stage .manual` ni `.arch-i .manual`). Piezas anchas dentro del módulo a 1440: video 760, galería 760, `.dl-section` 760, kicker plegable de galería 760; texto 545.

**(g) Tests de la sesión anterior:** `test_link_post.py` → **27 OK, 0 fallas** (escritorio y celular). `intranet/muro-demo.js` no existía: se creó temporal con la estructura que el test espera (key `cartelera-prueba`, post-uno/post-fijado/post-tres) y **se borró al terminar** (git status: solo `M intranet/index.html`).

**(h) Capturas:** `2c-antes-embalaje-1440.png`, `2c-antes-embalaje-390.png`, `2c-despues-embalaje-1440.png`, `2c-despues-embalaje-390.png`, `2c-mwarn.png`, `2c-print.pdf` (módulo Embalaje impreso, 2 páginas) y `2c-print-portada.pdf` (cartelera impresa), todo en `qa/screenshots/`.

## Decisiones distintas del spec, con su porqué

1. **545px y no 600–640px.** El spec pedía a la vez "apuntar a ~600–640px" y "criterio (a): `ancho/(font×0,5)` entre 60 y 78". Son incompatibles: 600px da 82,8 y 640px da 88,3 por esa fórmula — cualquier valor en esa banda falla el criterio verificable. Medido en el navegador, el caracter promedio del cuerpo Montserrat 14,5px mide 7,469px, así que 60–75 caracteres reales = 448–560px. 545px cumple los tres marcos a la vez: 75,2 por la fórmula del gate, 73,0 caracteres reales, y queda a un renglón de libro (37,6em). El número y la medición quedaron en el comentario del CSS.
2. **`.m-h2` espejado del panel.** No estaba en las 4 tareas, pero el subtítulo llegaba del panel sin ningún estilo (se veía como párrafo) y la tarea de ritmo lo trata como título. Una regla, copiada literal del panel para no inventar.
3. **Subtítulo a 4px de su título** (en vez del piso de 12): título+subtítulo son una unidad tipográfica; 12px los separaba como bloques distintos. El piso general sigue siendo 12.
4. **Controles del video ocultos en print** (extra chico): Chromium imprimía la barrita de play/volumen sobre el frame del video; sin ella queda una foto con su epígrafe.
5. **El ritmo va scopeado a la vista de módulo** (`#secBody > .manual`), no a todo `.manual`: el feed de la cartelera y el deck componen distinto y la auditoría no les imputó problemas de ritmo. Radio de explosión mínimo.

## Cómo se probó

Server local `ThreadingTCPServer` en 8811 sirviendo la raíz del proyecto + Playwright/Chromium. Scripts de medición y verificación en el scratchpad de la sesión (`qa2c/medir.py`, `qa2c/verificar.py`, `qa2c/imprimir.py`); el JSON completo de la pasada final en `qa2c/verificacion-final.json`. Los PDFs se generaron con `page.pdf()` (A4, márgenes 10mm, `print_background`) y se revisaron página por página renderizados con PyMuPDF.
