# AUDITORÍA FUNCIONAL — Panel MyS + Intranet de Vendedores

**Fecha:** 28-08-2026 · **Agente A** · Panel `web2` servido por el .exe instalado (build 12:07), corriendo contra una **copia sandbox** del proyecto y del estado. La publicación al sitio estuvo **interceptada a nivel navegador** durante toda la auditoría: ningún click llegó a producción.

## Método

1. **Inventario automático**: enumeración por DOM de todo elemento interactivo (botones, links, inputs, selects, textareas, `[onclick]`, `[contenteditable]`, segmented controls) en las 5 pantallas → **732 controles** registrados con id/clase/texto/estado en `qa/evidencia/panel-inventario.json`. De esos, 582 estaban presentes pero no visibles al momento de capturar (menús ⋯, modales, panes ocultos): el inventario los incluye.
2. **22 flujos críticos probados de punta a punta** con Playwright, verificando el efecto real en el disco (`modulos.js` del sandbox), no solo lo que dice la pantalla.
3. Casos borde: doble click en guardar, título de 300 caracteres, cuerpo de 5.000, formulario vacío, botón Atrás del navegador, Escape en modales.

Lo no probado se dice explícitamente al final. **Roles**: no hay login; el panel distingue Central/Colaborador por `panel_config.json` (se auditó como Central). La intranet es pública.

## Los flujos, uno por uno

| # | Flujo | Estado | Evidencia |
|---|---|---|---|
| F1 | Crear publicación (compositor → Publicar) | **OK** | docs +1 en disco; el flujo entero guarda **y** dispara la subida al sitio |
| F2 | Doble click en Publicar al crear | **OK** | una sola publicación creada (guardián `conBoton`, arreglado 28-ago) |
| F3 | Editar publicación → Guardar y publicar | **OK** | título actualizado en disco |
| F4 | Fijar / desfijar desde ⋯ | **OK** | reversible; el menú ofrece lo inverso al instante |
| F5 | Ocultar / volver a mostrar | **OK** | `muro.js:459` ofrece "Volver a mostrarla"; la publicación queda listada como `oculta` (`muro.js:90`). (La primera sonda dio falsa alarma por tocar el ⋯ de otra publicación.) |
| F6 | Duplicar | **OK** | docs +1 |
| F7a | Eliminar → papelera | **OK** | confirma antes; papelera +1, docs −1 |
| F7b | Restaurar desde papelera | **OK** | docs +1 |
| F8 | "Archivar en" habilita su select dependiente | **OK** | disabled→enabled al tildar (la dependencia del §3.8.4 funciona) |
| F9 | Editor: deshacer una inserción | **OK** | bloques 14→15→14 |
| F10 | Editor: eliminar bloque con ✕ del handle | **OK con reparo** | borra **sin confirmación ni toast**; el Deshacer de arriba lo salva, pero nada lo dice (ver H3) |
| F11 | Guardar módulo (`Guardar`) | **OK** | toast "Guardado ✓ No te olvides de publicar." |
| F13 | Interruptor de publicar en Datos | **OK** | contador 0→1, persiste en el estado |
| F14 | "Ver reporte" (deck de derivaciones) | **OK** | abre pestaña nueva, 9 slides |
| F15 | Descargar Word | **OK** | `Derivaciones 2026-08-28.docx` (Word real lo abre — verificado hoy aparte) |
| F16 | Pantalla Métricas | **OK** | carga con contenido |
| F17 | **Botón Atrás del navegador** | **INCONSISTENTE** | la app no maneja historial: Atrás te saca del panel (quedó en `about:blank`). Un usuario no técnico "pierde" el panel |
| F18 | Modal Avisar novedad | **OK** | lista los 11 módulos; no se publicó |
| F19 | Historial (GitHub API) | **OK** | 103 elementos |
| F19b | **Historial cierra con Escape** | **INCONSISTENTE** | Escape no lo cierra (la X y el overlay sí — F19c OK). El resto de los modales sí cierran con Escape |
| F20 | Título 300 chars + cuerpo 5.000 | **OK** | maxlength recorta a 120; sin desborde |
| — | Formulario vacío (Publicar sin título) | **OK** | toast "Ponele un título al aviso" (verificado 28-ago en la auditoría de botones) |

**0 errores de JavaScript** en consola durante los 22 flujos.

## Los problemas, por severidad

| Sev. | Hallazgo | Detalle / reproducción |
|---|---|---|
| ~~Alto~~ | ~~H1 · Insertar un bloque no produce nada visible~~ | **RETIRADO (29-ago): falsa alarma de la sonda.** `insertBloque` de web2 sí hace `scrollIntoView` en los dos casos; re-verificado con el caso real: el bloque insertado entra en pantalla (top 206px, visible). La primera medición miró el último bloque del documento en vez del insertado |
| **Alto** | **H2 · Cartelera desborda 66px a 768px** | `.head-actions` (456px, con el buscador `#muroBuscar` de 290px) no entra en tablet → scroll horizontal en toda la pantalla. `panel-cartelera-768.png` |
| Medio | **H3 · Borrar un bloque no confirma ni avisa** (F10) | El ✕ del handle elimina en seco. Hay Deshacer arriba pero nada lo señala. El prompt (7.2) pide confirmación **o** "Deshacer" ofrecido en un toast |
| Medio | **H4 · Atrás del navegador saca del panel** (F17) | Sin historial interno (las secciones no usan hash). Alt+← o el gesto del mouse pierden la sesión de trabajo |
| Medio | **H5 · Escape no cierra el Historial** (F19b) | Inconsistente con los otros modales |
| Bajo | **H6 · El lightbox del panel cuenta como imagen rota** | `#imgLightboxImg` vive con `src=""` — mismo patrón ya corregido en la intranet con `id=lbimg` excluido |
| Bajo | **H7 · `#btnAddModulo` sigue siendo `.btn.active`** | El plan (A9) lo bajaba a secundario para que no compita con Publicar; quedó a medias: el `mod-add` punteado del final sí existe |

## Estados faltantes (prompt §2.4)

- **Carga**: los botones que guardan ya muestran "Guardando…/Publicando…" (arreglado 28-ago). El tablero de Datos muestra "Leyendo la planilla…". **Falta**: esqueletos en la lista de módulos y el feed del panel (aparecen en seco), y estado de carga en "Ver reporte" (la pestaña tarda ~2s en blanco).
- **Vacíos**: el muro tiene vacío con voz ("Todo lo importante está arriba…"). El canvas del editor nuevo muestra la paleta. Papelera vacía: no verificado con papelera en cero.
- **Error**: cubierto en guardar/publicar/datos (toasts con el motivo, desde el arreglo del 28-ago). El bloque Video valida peso con mensaje (no probado en vivo: requiere subir >40MB; verificado en código `app.js`).

## No probado (a propósito, con motivo)

- **Kit de recuperación**: muestra la clave real de publicación en claro; no se abrió para no exponerla en captura ni log.
- **Cerrar panel**: apagaría el .exe de la auditoría.
- **Subida real de video >40MB** y **rol Colaborador** (`/api/enviar`): el primero por peso, el segundo porque esta instalación es Central; ambos quedan para la Fase 3 con un fixture dedicado.
- **Pegado de texto con formato** (hallazgo 3.5.13 del prompt): pendiente de sonda específica.

## Nota de contexto

Cuatro de los problemas que el prompt traía como hallazgos ya no existen en `web2` (se corrigieron el 28-ago, antes de esta auditoría): botones de guardar sin reacción, doble click que duplicaba publicaciones, fallos silenciosos al guardar, y "Publicar" que no subía al sitio. La tabla de flujos los cubre como F1–F3.
