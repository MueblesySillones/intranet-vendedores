# REPORTE FASE 2B — rediseño del editor de bloques

**Fecha:** 29-08-2026 · Implementa la sección 5 ("Dirección propuesta") de `EDITOR-BLOQUES.md`, los 10 puntos. Todo sobre `herramientas\panel\web2\` (app.js, styles.css, rediseno.css, index.html). **muro.js no se tocó** (la unificación del seg fue solo CSS). Nada fuera de web2 fue modificado; la intranet real solo se leyó para armar el sandbox.

**Resultado de la batería: 30 verificaciones automatizadas, 0 FAIL** (Playwright sobre el panel corriendo desde el código, proyecto sandbox, puerto 8141, con `/api/publicar`, `/api/enviar` y `/api/shutdown` bloqueadas por route() en todo el contexto).

---

## 1. Qué cambió, archivo por archivo

### styles.css
| Línea (aprox) | Cambio |
|---|---|
| 542-556 | **Tríada hover → seleccionado → escribiendo**: hover punteado (`1px dashed accent 45%, offset 7px`), seleccionado igual que antes (2px accent, offset 7) y **chip `:before` con `attr(data-nom)`** arriba a la izquierda. `.gb-block.is-selected:has([contenteditable]:focus){outline-offset:2px}` = anillo pegado al escribir. `.gb-block` ya era `position:relative` y no tenía `:before` propio (verificado). |
| 557-570 | **Handles**: botonera sin caja (fondo `rgba(233,227,217,.6)`, sin borde ni sombra, sin blur), botones 30×30 con glifos 13px color `--ink2`, `position:relative` para el tooltip, tooltip CSS `:after` con `attr(data-lbl)`, ✕ separado (`margin-top:4px; padding-top:4px; border-top:1px solid var(--line)`). `left` pasó de -44 a **-46px** para que la pastilla no pise el anillo de selección (que llega hasta -9px). |
| 276 | `.chip-estado`: chip verde de estado (fondo `--ok` al 10%, texto `#3F5A3C` = **6,5:1 medido** sobre el fondo compuesto, pedido ≥4,5). |
| 158 | `.toast` z-index 50 → **200** (ver decisión D1: era un bug que tapaba TODOS los toasts en el editor). |
| 165-166 | `.toast .toast-btn`: el botón inline del toast con acción (subrayado, negrita, blanco). |
| 368-372 | **EXCEPCIÓN AUTORIZADA al espejo**: bloque `.doc-preview .m-warn` con el CSS EXACTO del contrato, comentario "espejo de intranet/index.html — si tocás una, tocá la otra". |
| ~645 (antes 572-574 y 904) | Eliminados los estilos de `.gb-insp-acts` y su mención en la lista de selectores de A2. |

### app.js
| Línea | Cambio |
|---|---|
| 26-41 | `toastAccion(msg, rotulo, fn, tipo)`: variante del toast con botón inline y 6 s en pantalla; `toast()` viejo intacto (su `textContent` pisa el botón). |
| 1292, 1305, 1318, 1331, 1358, 1577 | **Bloque Advertencia**: `GRUPOS_BLOQUE` ('Listas y avisos', después de nota), sinónimos en `ALIAS_BLOQUE`, `SVG_WARN` (const compartida canvas/export con comentario de CONTRATO), entrada en `BLOQUE_INFO` (label/desc exactos del contrato), default en `bloqueNuevo` (t:'advertencia' con el texto "Escribí acá la advertencia…"), miniatura en `BLOQUE_MINI` (triángulo suave + "!" sólido, coherente con imagen/video). |
| 2056 | Render en el canvas: `.m-warn > .ico + .mw-tx` con el texto `contenteditable` como los demás bloques de texto. |
| 3335 | Export en `bloqueHTML` (lo que consume `bloquesHTML`): emite EXACTAMENTE el HTML del contrato. |
| 2100-2103 | `bloqueCanvas` emite **`data-nom`** con la misma expresión del título del inspector (subtítulo incluido), escapado con `esc()`. |
| 1830 | `gbHandle()`: cada botón lleva `data-lbl` ("Arrastrar para mover", "Subir", "Bajar", "Eliminar bloque") + `aria-label`; se quitaron los `title` para no duplicar tooltip nativo + CSS. |
| 2209-2211 | **Inspector des-duplicado**: fuera los 3 botones ↑↓✕; queda la ayuda (`BLOQUE_AYUDA`, que ya se montaba arriba) y los ajustes reales. |
| 3683, 3735, 3768-3800 | **Rehacer**: `redoStack` sobre el MISMO mecanismo de snapshots del undo. `deshacer()` empuja el estado actual a redo antes de aplicar; `rehacer()` es el espejo; cada edición nueva (detectada por el watcher `vigilarEstado`) vacía redo; `actualizarUndoBtn` maneja `disabled` + title de los dos ("Nada para deshacer/rehacer todavía"); `arrancarEdicion` resetea ambas pilas; el click de `#detRedo` queda enganchado al lado del de `#detUndo`. |
| 1810-1824 | `borrarBloque`: llama `vigilarEstado()` **antes y después** del splice para que el checkpoint del borrado exista al instante (sin esperar el tick de 1 s), y muestra `toastAccion('Bloque eliminado', 'Deshacer', deshacer)`. |
| 3690-3716 | `actualizarBotones`: **ESTADO ≠ ACCIÓN** — los botones dicen siempre "Guardar"/"Publicar"; el chip `#detEstado` muestra "Guardado ✓" / "Publicado ✓" o se esconde si hay cambios sin guardar. |

### index.html
- 249: botón `#detRedo` (↷) al lado de `#detUndo`, `disabled` con title explicativo.
- 257-258: `<span id="detEstado" class="chip-estado" hidden>` al lado de Publicar.

### rediseno.css
- 140-151: `.mp-modo` (seg Escritorio/Celular del muro) unificado al lenguaje del seg del editor: contenedor radio 10 + padding 3 + fondo `--bg` + borde `--line`, botones radio 8 / 12.5px / peso 600, **activo blanco con sombra** (antes: radio 999 y activo en tinta negra). Solo CSS: muro.js sigue toggleando `.on` igual que siempre.

---

## 2. Verificaciones (a)-(j), con números

Corrida completa: **30 OK / 0 FAIL**. Módulo real: EMBALAJE ESPECIAL (14 bloques).

| # | Verificación | Medido |
|---|---|---|
| (a) | reposo ≠ hover ≠ seleccionado ≠ en edición (computados) | reposo `outline:none` · hover `dashed 1px offset 7px rgba(124,106,85,.45)` · seleccionado `solid 2px offset 7px` · escribiendo `solid 2px offset 2px` |
| (b) | chip con el nombre | `data-nom="Destacado"` → `:before` content `"Destacado"`, fondo `rgb(124,106,85)`, 9.5px; se mantiene mientras se escribe |
| (c) | handles y tooltips | 4 botones exactos **30×30**; botonera `rgba(233,227,217,.6)`, borde 0, sombra none; ✕ con `4px|4px|1px`; tooltip `:after` = "Subir" visible en hover; los 4 `data-lbl` correctos |
| (d) | inspector sin duplicados | 0 nodos `.gb-i-up/.gb-i-down/.gb-i-del/.gb-insp-acts`; el texto del panel no contiene "Subir"/"Borrar" |
| (e) | rehacer | redo arranca `disabled` + title "Nada para rehacer todavía"; insertar (14→15) → undo (15→14, redo se prende) → redo (14→15, la advertencia vuelve, redo se apaga) |
| (f) | borrar con deshacer | ✕ → toast "Bloque eliminado — Deshacer" (15→14) → click en Deshacer → 14→15 con la advertencia de vuelta |
| (g) | estado ≠ acción | chip oculto con cambios sin guardar; tras Guardar: chip "Guardado ✓" y los botones siguen diciendo "Guardar" / "Publicar" |
| (h) | contrato del bloque | el `modulos.js` del SANDBOX contiene el HTML **carácter por carácter**: div.m-warn con span.ico + el svg exacto (path "M12 3.6 21.2 20H2.8z" / "M12 10v4" / "M12 17.2v.1") + div.mw-tx con el texto |
| (i) | consola | **0 errores** (console.error + pageerror) en todo el recorrido |
| (j) | desbordes | scrollWidth−clientWidth = **0** en home 1440, editor 1440 y editor 768 |
| (9) | un solo seg | `.mp-modo` radio 10px, padding 3px, fondo `--bg`; botón activo `#fff / --ink / radio 8px` (medido con los botones reales del muro renderizados) |

**Capturas** en `qa\screenshots\`: 2b-estado-reposo, 2b-estado-hover, 2b-estado-seleccionado-chip, 2b-estado-edicion, 2b-handles-tooltip, 2b-inspector, 2b-paleta-advertencia, 2b-advertencia-canvas, 2b-undo-redo-barra, 2b-toast-deshacer, 2b-chip-guardado, 2b-seg-muro, 2b-editor-1440, 2b-editor-768 (.png).

---

## 3. Decisiones distintas del spec (y por qué)

- **D1 — `.toast` z-index 50 → 200 (no estaba en el spec).** El editor es `position:fixed` con `z-index:90` (`.editor-full`, styles.css:266): con 50, **todos** los toasts quedaban tapados mientras se edita — "Autoguardado ✓", "Publicando…", los errores, y el nuevo "Bloque eliminado — Deshacer" nacía invisible (verificado en vivo: el hit-test le daba el click al editor). Sin este arreglo el punto 8 del spec no existe para el usuario. 200 lo deja arriba de los modales del muro (120-140), que es lo correcto para un aviso transitorio no bloqueante.
- **D2 — handle a `left:-46px` (spec no fijaba valor; antes -44).** Con botones de 30px la pastilla mide 36px de ancho: en -44 su borde derecho pisaba el anillo de selección (offset 7 + 2px de trazo = llega a -9px). En -46 queda 1px de aire.
- **D3 — el ✕ conserva height:30px con el separador ADENTRO** (padding-top 4 + border-top), tal cual la receta CSS del spec. El glifo queda ~2px arriba del centro óptico; se priorizó la literalidad del spec y el "30×30" medible de la verificación (c).
- **D4 — advertencia vacía no se publica**: `bloqueHTML` devuelve vacío si el texto está vacío (mismo criterio que imagen sin foto o embed sin link — `bloquesHTML` ya filtra los bloques que no emiten). El contrato fija la estructura, no decía qué hacer con el vacío, y un recuadro rojo vacío en la intranet es peor que nada. OJO: el default trae texto ("Escribí acá la advertencia…"), así que guardar sin editar SÍ publica ese texto — es la consecuencia del default que fija el contrato.
- **D5 — sinónimos de búsqueda agregados** (`ALIAS_BLOQUE.advertencia: 'peligro cuidado alerta atencion rojo critico grave error prohibido'`). No estaba en el contrato, pero sin alias el buscador de la paleta lo encontraría solo por label/desc; es el mismo patrón de los otros 25 bloques.
- **D6 — `title` → `data-lbl` + `aria-label` en los handles.** Dejar los `title` nativos junto al tooltip CSS mostraba DOS tooltips; el `aria-label` conserva el nombre accesible que daba el `title`.
- **D7 — el chip del estado quedó a la derecha de Publicar** (el spec decía "a su lado" sin fijar lado): así el orden de lectura es acción → acción → estado resultante.

## 4. Notas para Fase 3

- El "+" entre bloques (`.gb-mas`, B9) **ya estaba implementado** en app.js:1892 — el veredicto "no implementado" de EDITOR-BLOQUES.md §4 quedó viejo. Convive bien con estos cambios.
- El chip del nombre pisa ~9px del bloque de arriba cuando el gap es el estándar de 16px (se ve en `2b-handles-tooltip.png`). Es la geometría que fija el spec y solo aparece en el bloque seleccionado; si en Fase 3 molesta, la salida es dar más aire al bloque seleccionado, no achicar el chip.
- El arrastre con el grip (⠿) no se re-probó acá (ya estaba pendiente de verificación manual en la auditoría §1); estos cambios no tocan su lógica (solo estilos del botón).
- El botón "Publicar" de la HOME conserva su patrón viejo ("Todo publicado ✓" como texto): el spec de 2B hablaba de la barra del editor. Queda anotado como candidato a unificar con el mismo chip.

## 5. Cómo se probó (reproducible)

1. Sandbox: copia de `intranet\` + `PanelMyS_state` en el scratchpad de la sesión (`sb\intranet`, `sb\estado`, `sb\herramientas` vacía para pasar `es_proyecto`).
2. Server desde el código: `MYS_PROYECTO=<sb>`, `MYS_PANEL_STATE=<sb>\estado`, `MYS_PANEL_PORT=8141`, `MYS_PANEL_WEB=web2`, import de `panel_server` con `webbrowser.open` anulado y `ThreadingHTTPServer((HOST, PORT), Handler)` directo (sin receptor, sin navegador).
3. Playwright (python, chromium headless, 1440×900 y 768×1024) con `context.route()` → fulfill ok:true para `**/api/publicar`, `**/api/enviar`, `**/api/shutdown` ANTES de abrir la página.
4. `node --check` sobre app.js (y muro.js de control) después de cada edición: OK.
