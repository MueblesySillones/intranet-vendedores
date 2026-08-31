# PLAN DE FASES — Auditoría integral + rediseño + QA · Panel MyS e Intranet

**28-08-2026.** Este es el documento que el prompt pide aprobar antes de implementar nada. La **Fase 1 ya está corrida** (era documentación, no implementación): los cuatro entregables están en esta carpeta con evidencia en `qa/`.

## 0. Contexto (los campos `<<< >>>` del prompt, completados)

| Campo | Valor real |
|---|---|
| Proyecto | Panel MyS (`herramientas/panel/web2`, servido por un .exe local) + Intranet de Vendedores (estática, Vercel) |
| Repo | `C:\Users\Redes 1\Documents\web dinamica-mys` → GitHub `MueblesySillones/intranet-vendedores`. ⚠️ **`herramientas/` está en `.gitignore`: el panel NO vive en git.** La rama `feat/rediseno-intranet` solo tiene sentido para `intranet/`; los cambios del panel se versionan por build del .exe (y propongo empezar a commitearlos aparte — decisión tuya) |
| Stack | HTML/CSS/JS plano sin build (regla del proyecto: se distribuye como .exe, no hay dónde compilar) · Python `panel_server.py` · sin dependencias front |
| Entorno de pruebas | Panel: `http://127.0.0.1:8136` (sandbox: copia del proyecto + copia del estado, publicación interceptada) · Intranet: `http://localhost:8804/intranet/` + prod Vercel |
| Credenciales | No hay login. Roles: Central / Colaborador (config del .exe) · Vendedor = lector de la intranet pública |
| Branding | Japandi existente (paleta completa en DESIGN-SYSTEM.md), Montserrat |

## 1. Inventario de pantallas detectado

**Panel (5):** Cartelera (feed + compositor colapsable + filtros + papelera + selector "Señalar un módulo") · Módulos (lista 11) · **Editor de bloques** (canvas + paleta/inspector + barra) · Datos (lista + tablero de Derivaciones + deck + Word/PDF) · Métricas. **Transversales:** sidebar (nav, "Todo publicado ✓", Avisar novedad, Historial, Kit, Cerrar, selector Central) · modales (confirmar, avisar, historial, kit, picker) · toast.
**Intranet (vendedor):** portada-cartelera (feed, fijadas, filtros, compartir con link por publicación) · 10 módulos de lectura · buscador global · lightbox · descargas/"Enviar".
**732 controles interactivos** inventariados (`qa/evidencia/panel-inventario.json`).

## 2. Lo que la Fase 1 encontró (resumen ejecutivo)

**La sorpresa central: buena parte de los dos documentos de entrada ya está hecha.** El plan del Escritorio apuntaba a `web/` (frontend muerto); `web2` ya implementó sus tokens y la mayor parte de las tandas A/B. Y de los hallazgos del prompt: el compositor colapsado, la jerarquía título/cuerpo, las etiquetas con estado activo y **el selector de módulo (el "bug prioritario" §3.9) ya están resueltos** — el mockup sirvió de norte y alguien lo implementó. Esta auditoría separa, hallazgo por hallazgo, **vigente / parcial / resuelto** (tablas en AUDITORIA-DISENO.md y EDITOR-BLOQUES.md).

**Lo vigente que importa, priorizado:**

1. `--ink3 #6E6E6E` de la **intranet**: ~30 nodos fallan AA (axe) — un solo token lo arregla todo.
2. **Cartelera del panel desborda 66px a 768px** (tablet).
3. ~~Insertar un bloque fuera de pantalla~~ — **retirado (29-ago): ya estaba resuelto**; falsa alarma de la sonda, re-verificado con el caso real.
4. Editor: **hover y "en edición" no existen como estados**; ✕ pegado a ↓ en botones de 26×24 sin tooltip; acciones duplicadas botonera/panel; panel derecho ⅔ vacío; sin Rehacer; "Guardado ✓/Publicado ✓" alternando acción y estado en el mismo botón.
5. Vista vendedor: **105 caracteres por línea** (target 60–75), gaps de 0px entre bloques, **no existe bloque de advertencia**, sin `@media print`.
6. Sistema: 46 tamaños literales conviviendo con los tokens, 142 estilos inline en `app.js`, `--line` (1,3:1) todavía de borde, dos segmented controls distintos.
7. Funcional: Atrás del navegador saca del panel; Escape no cierra el Historial; borrar bloque no confirma ni ofrece deshacer; sidebar con targets de 29px.
8. `aria-valuenow` faltante en `.mr-linea` (critical de axe en la portada del vendedor).

**Línea base de rendimiento (el "antes" de la Fase 5):** Intranet prod (móvil): Perf **92** · A11y **86** · BP **100** · LCP 2,9s (target 2,5) · CLS 0,058 · TBT 40ms · 612 KiB. Panel local: FCP 48ms · LCP 456ms · 1,2MB, 13 recursos. Reportes Lighthouse en `qa/`.

## 3. Las fases propuestas (ajustadas a lo que de verdad falta)

| Fase | Contenido | Riesgo |
|---|---|---|
| **2a · Quick wins** | ✅ **EJECUTADA (29-ago, madrugada).** Intranet: `--ink3`→`#67635B` (0 violaciones de contraste en las 4 vistas, eran 30 nodos; #6E6960 no alcanzaba sobre la mesa) + `aria-valuenow` vivo en el slider del video → **axe A/AA limpio en producción**. Panel: desborde 66px@768 resuelto (buscador baja de fila), targets ≥32px (links del pie, toggles de vista, volver/deshacer, dt-volver), Escape cierra Historial/Avisar, `#btnAddModulo` a secundario, lightbox sin src vacío, espejo `.doc-preview` sincronizado. 13/13 checks antes/después. Commit `b379e48` + .exe 00:28 instalado | Hecha |
| **2b · Editor** | La dirección de EDITOR-BLOQUES.md §5: tríada de estados, handles 30×30 con tooltips y ✕ separado, des-duplicar acciones (y con eso llenar el panel derecho), Rehacer, estado≠acción en la barra, toast con Deshacer al borrar bloque, un solo seg control | Medio |
| **2c · Vendedor** | Ancho de línea 68ch, ritmo sin gaps 0, bloque de advertencia (intranet + paleta del editor), `@media print` básico | Medio (toca la intranet publicada: rama + verificación en vivo) |
| **2d · Sistema** | C1 por grupos (el orden seguro ya está escrito en el plan), escala de espaciado, barrido de inline styles de `app.js`, `--linea-int` donde falta | Medio-alto (muchos sitios, cambios mecánicos) |
| **3 · QA visual permanente** | Formalizar los scripts de esta auditoría como suite (ya existen: crawl + axe + targets + desbordes + flujos), baseline de screenshots para regresión visual, fixtures de Colaborador y video >40MB | Bajo |
| **4 · Animaciones** | Sobre `--mov` existente: entradas de bloque, colapso al borrar, toasts, panes — con las duraciones/easings del prompt §6 como tokens | Bajo |
| **5 · Rendimiento + estados** | Re-medir contra la línea base; LCP intranet 2,9→<2,5 (imágenes del feed); skeletons; **la parte de tiempo real (SSE/polling) queda EXPLÍCITAMENTE fuera hasta un OK aparte** — es la única excepción de backend que el prompt permite y exige presupuestar antes | Medio |
| **6 · Cierre** | REPORTE-FINAL.md con antes/después y bugs resueltos vs. encontrados | — |

Commits atómicos por tanda; en `intranet/` sobre rama `feat/rediseno-intranet`; el panel se rebuildea e instala al final de cada tanda (regla del proyecto: tocar el .py/.js no cambia nada hasta recompilar).

## 4. Lo que necesito de vos (las 2 decisiones del prompt §9)

1. **OK para arrancar la Fase 2a** (quick wins) — o decime qué recortás.
2. **La dirección estética** (DESIGN-SYSTEM.md §4): **A** japandi actual completado *(mi recomendación)* o **B** la dirección verde/Instrument del mockup para todo el panel. La 2b depende de esto.

Herramientas que faltaban, ya bajadas y funcionando: **axe-core 4.13** (del repo de GitHub, vía su paquete publicado) y **Lighthouse 12** (global). Playwright ya estaba.
