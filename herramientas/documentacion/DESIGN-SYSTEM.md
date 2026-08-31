# DESIGN SYSTEM — lo que existe, lo que falta, y la decisión pendiente

**Fecha:** 28-08-2026. Este documento no inventa un sistema nuevo: documenta el que **ya está en producción** en `web2/styles.css` (:root) y `rediseno.css`, lo contrasta con lo que pide el prompt (§3.2), y deja UNA decisión para el dueño.

## 1. Los tokens vigentes (fuente: `styles.css` de web2)

```css
/* identidad de marca (japandi) */
--bg:#F4F1EC  --panel:#FBFAF7  --ink:#2C2A26  --ink2:#5B574F  --ink3:#6E6960
--line:#E4DFD6  --accent:#7C6A55  --accent2:#9C8B73
--ok:#5B7A5B  --warn:#B07A4A  --danger:#B5503F

/* legibilidad */
--linea-int:var(--accent2)   /* borde de control aislado: 3,30:1 */
--foco:2px solid var(--accent)
--tap:32px

/* superficies */         /* tipografía (6 pasos) */      /* radios (5) */
--mesa:#E9E3D9            --t-xs:11px   --t-sm:12.5px    --r-xs:6  --r-sm:9
--hoja:#F0EDE8            --t-md:13.5px --t-lg:15px      --r-md:12 --r-lg:16
                          --t-xl:17px   --t-2xl:20px     --r-full:999

/* sombras (4, en tinta cálida) */
--sombra-1 … --sombra-4

/* movimiento (rediseno.css) */
--mov:cubic-bezier(.2,.8,.2,1)
--accent-soft:#EFE9E0  --accent-ink:#5E4F3E  /* chip del acento, 6,53:1 */
```

**Contra el checklist del prompt**: paleta de marca + semánticos ✓ (sin escala de 9 neutros formal — los 4 tintas + 4 superficies cumplen ese rol); tipografía 1 familia (Montserrat) con 6 tamaños ✓; radios: **5 donde el prompt pide 3** — decisión ya tomada y defendida en el plan ("el radio también comunica escala", D6); sombras 4 ≤ 3+1 aceptable; espaciado: **no hay escala de spacing tokenizada** (gap real: valores sueltos); easing tokenizado ✓ (`--mov`) con `prefers-reduced-motion` global ✓.

## 2. Las brechas reales (medidas en AUDITORIA-DISENO.md)

1. **Migración a medias**: 46 `font-size` literales en el panel y 24 radios distintos en styles.css conviven con los tokens. La Tanda C1 del plan quedó pendiente; el plan ya deja el orden seguro de migración por grupos.
2. **`app.js` con 142 puntos de estilo inline** (32 `cssText` + 78 `.style.x` + 32 `style="…"`): estilo fuera del sistema que ninguna pasada de CSS va a arreglar sola.
3. **La intranet nunca entró al sistema**: 107 colores, 29 tamaños, 27 sombras propios. Comparte fuente y paleta de hecho, pero cada valor está escrito a mano. (Ojo: su HTML publicado en `modulos.js` limita qué se puede renombrar — el sistema de la intranet se hace con variables nuevas por encima, no renombrando clases.)
4. **`--line` (1,3:1) sigue de borde** en controles que debían pasar a `--linea-int` (A2 se aplicó parcialmente).
5. **Dos componentes para el mismo patrón**: segmented control del muro vs `.seg-b` del editor.
6. **Sin escala de espaciado**: definir `--sp-1..6` (base 4px) y usarla en la migración C1, en vez de una pasada aparte.

## 3. Componentes: estado real

| Componente | Estado |
|---|---|
| Botón (primario `.active` / publicar `.btn-pub` / fantasma / peligro / disabled / **loading**) | ✓ todos — loading agregado el 28-ago (`conBoton`: rótulo + disabled + guardián de doble click) |
| Input / textarea / select | ✓ (`--linea-int` a medias, ver brecha 4) |
| Checkbox | ✓ unificado en el inspector (`insp-check` con estado prendido visible); quedan los `label.fld.row` viejos fuera del inspector |
| Toast | ✓ (`#toast`, 3 tonos) — falta variante con acción ("Deshacer") |
| Modal | ✓ (`confirmar()` con tono ok/peligro) — Historial no cierra con Escape (bug F19b) |
| Badge / chip | ✓ (badges de módulo, chips de estado del tablero de Datos, `.co-tipo` con 3 intensidades) |
| Tabla | ✓ en Datos (`.dt-*`) |
| Tooltip | **falta** como pieza del sistema (los handles del editor no tienen; hoy solo `title` nativo) |
| Skeleton | **falta** (todo carga en seco) |
| Segmented | ✓ pero duplicado (brecha 5) |

## 4. LA DECISIÓN PENDIENTE: la dirección estética

Hay **dos direcciones en la mesa**, y el prompt exige elegir una y sostenerla (§3.2 y §3.3 "nada genérico"):

**A · Japandi actual, completado** *(recomendada)*
La que ya está en producción: fondo cálido `#F4F1EC`, acento marrón `#7C6A55`, Montserrat, verde solo para estados. La Fase 2 completa lo que falta (brechas 1–6) sin cambiar identidad. **Costo bajo, cero riesgo de desincronizar el espejo `.doc-preview`/intranet, y el vendedor no nota un cambio de marca de un día para otro.** El conflicto marrón-vs-verde del editor se resuelve por regla semántica (acento = acción/selección, verde = publicado/ok), no cambiando la paleta.

**B · La dirección del mockup** (`mockup-selector-bloques.html` del Escritorio)
Acento verde `#2C7A4B` con escala 900–050, tipografías **Instrument Sans/Serif**, superficies `#E8E5DC/#FFF`, 3 radios, 3 sombras. Es más "producto SaaS" — pega con la visión multi-cliente — pero implica **re-tokenizar el panel entero, cambiar la fuente (hoy Google Fonts: Montserrat), revisar cada contraste de nuevo, y decidir qué pasa con la intranet** (¿la marca del sitio del vendedor también cambia? el espejo obliga a que panel y sitio cuenten lo mismo). Costo alto; tiene sentido como tema del SaaS futuro más que como retrofit de hoy.

*(El selector de módulo ya tomó del mockup lo estructural — filas compactas, módulo entero primero, previews — sin adoptar su piel. Ese mismo criterio, "anatomía sí, estética después", es el que recomiendo para todo lo demás.)*

## 5. Reglas que quedan escritas (del plan, verificadas hoy)

- **Mostrar le gana a explicar** — el árbitro de todo empate.
- **Un estado que no se ve, no existe.**
- Borde fuerte (`--linea-int`) para el control aislado; borde suave (`--line`) para el ítem repetido en grilla.
- `.active` = **un** primario constructivo por pantalla; `.btn-pub` = publicar; dos primarios juntos es un bug.
- La decisión se dice con punteado y fondo hundido, **nunca con opacidad** (opacidad apaga también los controles para revertirla).
- Anillo lejos = seleccionado; anillo pegado = escribiendo.
- `.doc-preview` solo se toca para parecerse **más** a la intranet.
- Grave solo si mueve la aguja; cuando todo es grave, nada lo es.
