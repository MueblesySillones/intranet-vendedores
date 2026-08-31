# EDITOR DE BLOQUES — auditoría profunda y dirección

**Fecha:** 28-08-2026 · La pantalla donde más tiempo se pasa, auditada con más detalle que el resto (prompt §3.3). Todo medido en vivo sobre `web2` con el módulo real EMBALAJE ESPECIAL. Captura de referencia: `qa/screenshots/editor-estado-seleccionado.png`.

## 1. Los estados del bloque, medidos

| Estado | Qué se ve hoy (computado) | Veredicto |
|---|---|---|
| **reposo** | sin contorno, sin fondo — el contenido manda | ✅ correcto |
| **hover** | **idéntico a reposo** (ningún cambio computado) | ❌ no hay indicación de interactuable |
| **seleccionado** | `outline 2px solid #7C6A55` + botonera a la izquierda; **sin desplazamiento de layout** (x/ancho idénticos, verificado) | ✅ base sana (outline, no border) · ⚠️ el texto queda pegado al contorno |
| **en edición** | **idéntico a seleccionado** (mismos valores computados) | ❌ no se distingue "voy a mover" de "estoy escribiendo" |
| **arrastrando / drop target** | no medido en vivo (el grip no expuso caja en la sonda) — pendiente de verificación manual en Fase 3 | ⏳ |
| **foco por teclado** | `outline 2px #7C6A55, offset 2px` global (`:focus-visible`) | ✅ existe (A3 del plan aplicado) |
| **error / incompleto** | no existe como estado visual | ❌ |

**El faltante estructural es la tríada hover → seleccionado → en edición.** Hoy hay un solo escalón (seleccionado) y es ambiguo.

## 2. Handles y controles

- Botonera flotante: **⠿ ↑ ↓ ✕ de 26×24px** — por debajo del piso de 32px del propio sistema y del mínimo de 24px "de área efectiva" del prompt (justo en el límite), **✕ pegado a ↓ sin separación** ("quise bajar y lo borré" sigue a un pixel), **sin tooltips** (`data-lbl` del plan A12: no aplicado).
- La botonera aparece **solo con la selección** (bien), pero va **encajonada en una tarjeta blanca con borde propio** pegada al bloque (§3.5.4 vigente).
- **Duplicación confirmada** (§3.5.3): las mismas tres acciones viven en la botonera (↑ ↓ ✕) **y** en el panel derecho ("↑ Subir · ↓ Bajar · ✕ Borrar"). Hay que elegir una casa.
- **Borrar un bloque no confirma ni ofrece deshacer visible** (F10 de la auditoría funcional): elimina en seco; el ↶ de arriba lo salva pero nada lo dice.

## 3. Lo que la captura confirma de los hallazgos §3.5

| # | Hallazgo | Veredicto |
|---|---|---|
| 1 | Dos acentos peleando | **VIGENTE** — selección y título del inspector en marrón `#7C6A55`; "Publicado ✓", NOTA y checks en verde. Dos familias en la misma pantalla |
| 2 | El contorno no respira / border vs outline | **PARCIAL** — es `outline` (no desplaza: verificado), pero el texto toca el contorno; falta el padding interno simétrico |
| 3 | Controles duplicados | **VIGENTE** (medido arriba) |
| 4 | Barra flotante encajonada | **VIGENTE** — tarjeta con borde, pegada al bloque |
| 5 | Panel derecho desaprovechado | **VIGENTE** — "Ajustes de: Párrafo" + 3 botones y **dos tercios de columna vacía** |
| 6 | Segmented "+ Agregar / Ajustes" | **VIGENTE** — inconsistente con el seg de la Cartelera (radio 8px vs 0, tamaños distintos) |
| 7 | Anchos de bloque inconsistentes | **NO REPRODUCIDO** — los 14 bloques miden 662px exactos en este módulo |
| 8 | Ritmo vertical irregular | **PARCIAL** — en el editor es uniforme (16px entre todos); no hay ritmo *por tipo* de bloque, pero tampoco el caos de la captura vieja. (En la **vista del vendedor** sí hay gaps de 0px — está en AUDITORIA-DISENO §5) |
| 9 | Kicker gris sin contraste | **CONFIRMADO por axe**: 4,36:1 — deuda del `--ink3` de la intranet que el espejo hereda |
| 10 | Scroll del canvas como divisor | menor — el lienzo con `--mesa` y la hoja con sombra ya separan; pulido de scrollbar queda para Fase 2 |
| 11 | "Guardado ✓ / Publicado ✓" parecen botones | **VIGENTE, con matiz** — son los MISMOS botones Guardar/Publicar que alternan rótulo entre acción y estado, con "Cancelar" al lado. El control cambia de naturaleza sin cambiar de forma |
| 12 | Deshacer sin Rehacer | **VIGENTE** — no existe redo (`#detRedo` no está) |
| 13 | Contenido con palabras pegadas | **CONFIRMADO en contenido real**: "correctapreservación", "deembalaje", "mueblesespecificadas" están hoy en EMBALAJE ESPECIAL publicado. Mitad limpieza de contenido, mitad candidato a aviso del editor |

## 4. Interacciones medidas

- **Insertar con el documento scrolleado — CORREGIDO EL VEREDICTO (29-ago):** `insertBloque` ya hace `scrollIntoView` siempre (A13 estaba aplicado). Re-verificado con el caso real: el bloque insertado entra en pantalla. La sonda original midió el último bloque del documento, no el insertado.
- Insertar salta al panel "Ajustes" — desvío deliberado del B1 original, documentado en el código ("recién insertado se pasa derecho a sus ajustes").
- **Buscador de bloques con sinónimos funciona**: "foto" → 2 resultados, "whatsapp" → 2 (B3 ✓).
- **No hay "+" entre bloques** (B9 del plan: no implementado). La regla "se inserta debajo del seleccionado" sigue siendo invisible.
- Deshacer una inserción: funciona (14→15→14).
- Vista Celular: papel de **392px** ✓ (A15 aplicado); las reglas espejo del responsive están en styles.css.
- Paleta: miniaturas SVG + grilla siempre visible (B2 ✓), grupos renombrados (B4 ✓), título del inspector con el nombre del bloque (B5 ✓), ayuda "dónde se escribe" (B6, `BLOQUE_AYUDA` presente ✓), checkbox unificado `insp-check` (B7 ✓ en inspector).

## 5. Dirección propuesta (se implementa recién con el OK de Fase 2)

Conservar el paradigma (restricción dura del prompt) y completar el lenguaje que el propio sistema ya eligió — outline + acento + tres intensidades — para que **cada estado tenga su escalón**:

1. **hover**: contorno punteado suave (`1px dashed accent al 45%`, offset 7px) — ya estaba diseñado en el plan (A11) y no se aplicó.
2. **seleccionado**: lo de hoy (outline 2px accent) **+ chip con el nombre del bloque** arriba a la izquierda (`data-nom`, plan A11) + padding interno simétrico para que el texto respire sin mover el layout.
3. **en edición**: anillo pegado (offset 2px) vs anillo lejos (offset 7px) — la convención que el plan ya dejó escrita: *lejos = seleccionado, pegado = escribiendo*.
4. **Handles**: 30×30, ✕ separado con borde superior, tooltips `data-lbl` (plan A12 tal cual), y sacar la caja: fondo translúcido de la mesa, no tarjeta con borde.
5. **Duplicados**: la botonera del bloque se queda con lo frecuente (mover/borrar); el panel derecho deja de repetirlas y usa ese espacio para las propiedades reales del bloque + la ayuda — lo que arregla a la vez §3.5.3 y §3.5.5.
6. **Rehacer** al lado de Deshacer, ambos con estado disabled visible.
7. **Estado vs acción en la barra**: "Guardado ✓ / Publicado ✓" pasan a indicador no clickeable (chip), y el botón conserva un solo rótulo de acción. Una sola decisión de color: el verde queda para *estado publicado*, el acento para *acción y selección* — resuelve el hallazgo 1 sin pelear con la marca.
8. **Borrar bloque**: sin modal (es reversible) pero con toast "Bloque eliminado — Deshacer", el patrón que el prompt pide en §7.2.
9. **Un solo seg control** para toda la app (el del editor, con radio de token), reusado en la Cartelera.
10. El "+" entre bloques (B9) como acceso, no como cartel — igual que lo arbitró el plan §4.3.

Todo lo anterior son ~10 cambios acotados de CSS + JS chico sobre lo que ya existe; ninguno toca `.doc-preview` ni la lógica de guardado.
