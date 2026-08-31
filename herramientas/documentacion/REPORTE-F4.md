# REPORTE — FASE 4 · Animaciones del panel

**29-08-2026.** Implementación: agente F4 (interrumpido dos veces por límites de sesión, con el trabajo ya hecho) + cierre y validación del orquestador. Criterio aplicado: **la animación explica el cambio de estado, no decora** — solo `transform` y `opacity`, duraciones como tokens, todo bajo `prefers-reduced-motion`.

## Qué quedó implementado (web2)

1. **Tokens de movimiento** en `:root` de styles.css: `--dur-1:140ms` (micro) · `--dur-2:240ms` (aparición/layout) · `--dur-3:360ms` (techo) · `--ease-in` (curva de salida; `--mov` sigue siendo la de entrada). Las duraciones sueltas (.13s/.16s/.18s/.2s/.24s) migradas a tokens en styles.css, rediseno.css y panel_datos.css.
2. **Modales**: entrada con velo en fade + caja `translateY(8px) scale(.985)`→normal; **salida real** con el patrón `.yendose` (tomado del picker del muro): `esconderModal()` en app.js pone la clase, deja terminar el fade acelerado y recién ahí `hidden`. `pointer-events:none` durante la despedida para no comerse el click siguiente. Cubre confirmar, historial, avisar, kit y el lightbox de imagen.
3. **Toast**: entra desde abajo (`movEntraAbajo`) y se despide por fade (`ocultarToast()`); un toast nuevo pisa al que estaba saliendo. Con atajo directo a `hidden` cuando el sistema pide reducir movimiento.
4. **Editor**: cambio de pestaña Agregar↔Ajustes con `movPane` (4px + fade); bloque nuevo con `movBloque`; **bloque eliminado se desvanece antes de irse** (`.gb-saliendo` aplicado en `borrarBloque`); el handle y el outline transicionan con `--dur-1`; entrada del editor a pantalla completa suave.
5. **Tarjetas y botones**: hover con elevación de 1px + sombra en `.mod-card`/`.col-item` — **excluyendo la copia flotante del arrastre** (`.ord-flota`), que con transición de transform se arrastraría retrasada respecto del cursor; `:active` con `scale(.97)`.
6. **Reduced motion**: el bloque global anula todo (animation/transition a .01ms) y los caminos JS tienen atajo (`sinMovimiento()` → `hidden` directo, sin timers).

## Decisiones documentadas

- La **salida** de modales se implementó (no solo la entrada) porque el patrón `.yendose` ya existía en el picker y extenderlo costó una función chica, no una reestructura.
- La copia flotante del drag quedó **sin transición** a propósito (ver arriba) — es el tipo de detalle que convierte "animado" en "pegajoso".
- Nada dentro de `.doc-preview`.

## Validación

- `node --check` verde en app.js/muro.js.
- **Suite QA completa: t1 34/0 · t2 19/0 · t3 29/0 fallas.**
- t4 (regresión visual): 8 diferencias, **todas ajenas a F4** y verificadas una por una: publicación nueva + 3 placas cargadas por el dueño desde su panel durante la corrida (cartelera/portada/descargables/métricas más altas) y los cambios ya publicados de la fase de rendimiento (embalaje/whatsapp). Las dos pantallas sin cambios de contexto — **editor 0,000% y módulos 0,004%** — prueban que las animaciones no alteraron ningún estado estático. Baseline regenerada después de sincronizar el contenido nuevo.
- Verificación de no-daño: los modales no desplazan elementos vecinos (overlay absoluto + caja centrada), el click inmediato tras abrir funciona (la caja no arranca con pointer-events bloqueado), 0 errores de consola en el crawl completo.

## Aviso conocido de la suite (no es de F4)

La sonda F5 de t2 ("ocultar reversible") toca el ⋯ de otra publicación y reporta un aviso falso — ya documentado en el reporte de la Fase 3; pendiente de corregir en la suite.
