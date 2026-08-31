# AUDITORÍA DE DISEÑO — Panel MyS + Intranet

**Fecha:** 28-08-2026 · **Agente B** · Medido, no opinado: inventario estático del CSS (excluyendo `.doc-preview`, que es espejo del sitio y no se le imputa al panel), axe-core 4.13 (WCAG A/AA) sobre las pantallas vivas, capturas en 1440/1024/768 y, para la intranet, también 390.

## 1. La deuda en números

### CSS (fuera del espejo `.doc-preview`)

| Archivo | Reglas | Colores distintos | `font-size` distintos (literales px) | Radios | Sombras |
|---|---|---|---|---|---|
| panel/styles.css | 747 | **66** | 22 (19) | **24** | **18** |
| panel/rediseno.css | 298 | 35 | 17 (12) | 18 | 11 |
| panel/panel_datos.css | 259 | 23 | 20 (15) | 7 | 5 |
| **intranet/index.html** | 878 | **107** | **29 (29)** | 20 | **27** |

**Lectura:** los tokens del plan (tipografía `--t-*`, radios `--r-*`, sombras `--sombra-*`, `--mesa/--hoja`, `--linea-int`, `--tap`, `--foco`) **existen y se usan**, pero la migración de los literales (la Tanda C1 del plan) quedó a medio camino: siguen 46 tamaños de letra escritos a mano en el panel y 29 en la intranet. La intranet nunca tuvo pasada de tokens: 107 colores y 27 sombras distintas.

### Estilos fuera del sistema (JS)

| Archivo | `.cssText=` | `.style.x=` | `style="…"` en templates |
|---|---|---|---|
| app.js | **32** | **78** | 32 |
| muro.js | 0 | 5 | 6 |
| panel_datos.js / datos_puente.js | 0 | 2 | 3 |

`app.js` sigue siendo la fuente principal de estilo inline (la unificación B7/B8 del plan se hizo para checkboxes pero no barrió el resto).

### Contraste de los tokens (calculado)

| Par | Ratio | Veredicto |
|---|---|---|
| `--ink3` #6E6960 sobre `--bg` / `--panel` / blanco | 4,84 / 5,22 / 5,45 | OK (el arreglo A1 del plan está hecho) |
| `--accent` sobre `--bg` · blanco sobre `--accent` | 4,60 · 5,19 | OK |
| `--accent2` (`--linea-int`) sobre blanco | 3,30 | OK como borde (≥3) |
| **`--line` como borde** sobre panel / blanco | **1,27 / 1,33** | **FALLA** — sigue siendo el borde de muchos controles |
| blanco sobre `--ok` | 4,79 | OK |

## 2. Lo que dijo axe-core (WCAG A/AA, pantallas vivas)

**Panel** (5 pantallas): limpio salvo **1 violación** en el editor — y es del espejo: el *kicker* renderiza `#6E6E6E` sobre `#F0EDE8` = **4,36** a 11px bold. Es deuda **de la intranet** (su `--ink3` local), exactamente como anticipaba el plan (§4.7).

**Intranet (vista vendedor)**:

| Vista | Violación | Nodos | Ejemplo |
|---|---|---|---|
| portada | `aria-required-attr` (**critical**) | 1 | `.mr-linea` sin `aria-valuenow` |
| portada | `color-contrast` (serious) | 3 | `.lat-t` #6E6E6E sobre #E8E4DF = **4,02** a 10px |
| embalaje | `color-contrast` | 4 | `#secSub` #6E6E6E sobre #F0EDE8 = 4,36 |
| descargables | `color-contrast` | **12** | ídem patrón |
| whatsapp | `color-contrast` | **11** | ídem patrón |

**Un solo cambio** —el `--ink3` de la intranet de `#6E6E6E` a `#6E6960` (el mismo valor que ya usa el panel)— arregla los ~30 nodos de contraste de una vez, y arregla también la única violación del panel (el espejo la hereda).

## 3. Desbordes y áreas táctiles

- **Cartelera del panel a 768px: desborde de 66px** (`.head-actions` 456px con el buscador de 290px). Único desborde encontrado en 15 combinaciones pantalla×ancho del panel. La intranet: **0 desbordes** en 12 combinaciones (1440/768/390).
- Objetivos táctiles menores a 32px (umbral del propio sistema, `--tap`): los 4 `link-discreto` del pie del sidebar (**29px** de alto, en todas las pantallas), los toggles `#vtDesktop/#vtMobile` (32×28), `#detBack` (34×31), `#detUndo` (36×31), y los botones del handle del editor (26×24 — ver EDITOR-BLOQUES.md). Los `input.dt-sw-i` de 1×1px son falsos positivos (checkbox oculto; el target real es la pastilla de 44px).
- Con el umbral del prompt (40px) caen además los botones `dt-volver` de Datos (29px de alto). Nota: el sistema declaró 32px como piso (`--tap`) con una excepción documentada; la tabla completa está en `qa/evidencia/panel-crawl.json`.

## 4. Los hallazgos del prompt, verificados uno por uno

### §3.8 Cartelera y compositor

| # | Hallazgo del prompt | Veredicto medido |
|---|---|---|
| 1 | Pozo de aire en el compositor | **RESUELTO** — textarea arranca en 80px, 18px hasta las etiquetas; y el compositor entero arranca **colapsado** (129px→413px), el patrón que §3.10 pedía evaluar |
| 2 | Título y cuerpo sin jerarquía | **RESUELTO** — título 19px/650, cuerpo 14,5px/400 |
| 3 | Seis etiquetas sin estado activo | **RESUELTO** — `.co-tipo.on` con el color del tipo en tres intensidades (fondo 10%, filo 34%); selección única verificada |
| 4 | Fila inferior mezcla naturalezas | **PARCIAL** — siguen en una sola fila plana (Fijar x=491, Confirmación x=628, Archivar x=832), pero la dependencia check→select funciona (F8) |
| 5 | Filtros con tres tipografías desalineadas | **PARCIAL** — hoy "Todas 2" y "Papelera 2" comparten estilo (12,5px/600) y línea base; lo que queda es "Papelera" flotando al extremo derecho (x 476 vs 1099) sin anclaje |
| 6 | Sidebar con jerarquía floja | **VIGENTE** — 4 nav arriba, hueco, y abajo 4 links de texto de 11px y 29px de alto + el selector "Central" |
| 7 | "Todo publicado ✓" compite | **MATIZADO** — es un **botón** a propósito (decisión D4 del plan: republicar es inocuo y el rótulo cambia a "Publicar N cambios" cuando hay pendientes). Se le puede bajar peso visual sin apagarlo |
| 8 | Segmented controls inconsistentes | **VIGENTE** — el de la Cartelera: 12px, radio 0, activo fondo `--ink`; el del editor (`.seg-b`): 11,5px, radio 8px, activo blanco. Mismo patrón, dos componentes |

### §3.9 Selector "Señalar un módulo" (traído como bug prioritario)

**RESUELTO en `web2`** — el rediseño del mockup ya está implementado: filas compactas (`co-pick-i`), **"el módulo entero" primero** (`es-mod`) y las piezas debajo (`es-pieza`) con nombre + clase + conteo y miniaturas apiladas ("+3"), desplegador con contador (`co-desp`), **desborde interno 0px** (medido con un módulo desplegado), scroll vertical propio. Capturas: `selector-cerrado.png`, `selector-desplegado.png`.

Quedan tres del checklist del mockup: **no hay buscador adentro del selector**, el `max-height` es `none` (hoy lo salva el viewport), y el estado seleccionado de una fila no se midió como "anillo + check". Ninguno bloquea; van como pulido.

### §3.10 Feed

La anatomía pedida ya está en la tarjeta (intranet y vista previa del panel): avatar con inicial, fecha relativa, menú ⋯, etiqueta como badge, "Ver publicación completa" en celular, pie de acciones separado, fijadas en su tira propia, tarjeta de módulo señalado (bloque `ref`), y desde hoy el link de Compartir lleva a la publicación exacta. Ancho de columna a 1440: **692px** (la banda recomendada era ~680). **Faltan**: esqueletos de carga (todo aparece en seco) y marca de "no leída" en el panel (la intranet sí la tiene: `NUEVO`).

## 5. Vista del vendedor (§3.6) — lo que queda

1. **Ancho de línea: 105 caracteres** (párrafo de 760px a 14,5px). El rango pedido es 60–75. Es el hallazgo de legibilidad más importante de la intranet.
2. Interlineado 1,6 ✓ (en objetivo).
3. **Ritmo vertical: hay saltos de 0px** entre bloques consecutivos del manual (secuencia medida: 12, 14, **0**, 14, 12, **0**, 12, **0**, 12, 14, **0**, 14, 16). Los bloques con gap 0 se leen amontonados.
4. **No existe un bloque de advertencia** visualmente distinto: solo está `.note` (verde, informativa). Un "NO APTO PARA…" hoy se escribe como nota o párrafo — el prompt pide tratamiento inconfundible propio.
5. Contraste: los ~30 nodos `#6E6E6E` de §2.
6. **Sin `@media print`**: imprimir un módulo sale como pantalla.
7. Responsive: 0 desbordes en 390/768; el recorte "Ver publicación completa" y los targets de 44px ya están (arreglos previos).

## 6. Top 10 priorizado (lo que la Fase 2 debería atacar primero)

1. `--ink3` intranet → `#6E6960` (30 nodos AA de una vez) + `aria-valuenow` en `.mr-linea`.
2. Desborde 66px de la cartelera del panel a 768.
3. ~~A13: insertar bloque siempre visible~~ — **retirado: ya estaba resuelto en web2** (falsa alarma de la sonda, re-verificado).
4. Ancho de línea de la intranet a 60–75ch (`max-width` en el manual).
5. Ritmo: eliminar los gaps de 0px entre bloques del manual.
6. Bloque de advertencia propio en la intranet (y en la paleta del editor).
7. Bordes de control con `--linea-int` donde quedó `--line` (1,3:1).
8. Un solo segmented control (Cartelera + editor).
9. Targets: `link-discreto` del sidebar y toggles de vista a ≥32px.
10. Migración de literales a tokens por grupos (la C1 del plan, en el orden que el plan ya deja escrito).

Evidencia completa: `qa/evidencia/*.json` · capturas: `qa/screenshots/` (27 del panel, 12 de la intranet, editor y selector).
