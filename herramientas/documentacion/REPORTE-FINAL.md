# REPORTE FINAL — Auditoría, rediseño y QA · Panel MyS + Intranet

**28–29 de agosto de 2026.** Programa completo del prompt de auditoría, ejecutado en dos días con 6 agentes + orquestador. Todo lo afirmado acá está verificado dos veces: por el agente que lo hizo y por una revisión independiente.

## Lo que cambió, fase por fase

| Fase | Resultado | Dónde está |
|---|---|---|
| **1 · Auditoría** | 732 controles inventariados, 22 flujos probados, hallazgos del prompt marcados vigente/parcial/resuelto. Sorpresa central: el plan viejo apuntaba a un frontend muerto y el "bug prioritario" del selector ya estaba resuelto | 5 documentos en esta carpeta + `qa/` |
| **2a · Quick wins** | Intranet AA (30 nodos de contraste + 1 critical de aria → **0**), desborde tablet del panel, targets ≥32px, Escape en modales | Producción (`b379e48`) + panel |
| **2b · Editor** | Estados hover/seleccionado/escribiendo (con el nombre del bloque a la vista), handles 30×30 con tooltips y ✕ separado, **Rehacer**, inspector sin duplicados, borrar con "Deshacer" ofrecido, estado ≠ acción en la barra, bloque **Advertencia** | Panel v17 |
| **2c · Vendedor** | Columna de lectura 75 caracteres (era 105), ritmo sin bloques pegados, bloque de advertencia, impresión decente | Producción (`ffda38d`) |
| **2d · Sistema** | Literales→tokens (font-sizes 188→59, radios 112→6, sombras negras 0), `cssText` inline 32→0, espejo verificado byte a byte | Panel v17 |
| **3 · Suite QA** | `herramientas/qa/`: crawl+axe, 20 flujos, intranet, regresión visual con baseline. Un comando: `python correr_todo.py` | Repo local |
| **4 · Animaciones** | Tokens de duración/curvas, modales y toasts con entrada Y salida, bloques que se despiden al borrarse, todo bajo `prefers-reduced-motion` | Panel v17 |
| **5 · Rendimiento** | El LCP era texto frenado por Google Fonts y 257 KB re-bajados por visita. Fuente async, datos en paralelo con ETag (frescura intacta, verificado), CLS→0, TBT→0, **peso 612→190 KiB**, esqueletos | Producción (`bf208eb`, `df85c1d`) |

## Números de producción (Lighthouse móvil, antes → después)

Accesibilidad **86 → 100** · CLS **0,058 → 0** · TBT **40 → 0 ms** · Peso **612 → 190 KiB** · Speed Index 3,6 → 3,1 s. Nota honesta: el FCP de la **primera visita fría** subió ~1 s (las descargas tempranas compiten en red angosta); a cambio, las visitas **repetidas** — el patrón real del vendedor, que entra muchas veces por día — pasan de re-bajar 257 KB a un 304 vacío. Perf global 92→87 por ese canje; CLS/TBT/peso/A11y todos mejores.

## El panel para el equipo de marketing (pedido del 29-08)

- **`instalador/Instalar Panel MyS.exe` (v1.17.0, 14,9 MB)** — recompilado con todo lo de arriba. Instala sin admin, respeta la config existente.
- **El botón de actualizar funciona, probado de punta a punta**: se montó una central v17 y un colaborador v16 en sandbox → el colaborador mostró la barra *"Hay una versión nueva del panel"* con el botón **Actualizar a la última versión** → confirmación → descarga verificada por SHA-256 → swap casi-atómico con rollback → quedó en v17 **byte-idéntico al build**, conservando su configuración de colaborador. El bundle jamás incluye archivos de configuración (allowlist verificada): un panel de sucursal no puede convertirse en central ni filtrar credenciales.
- La versión del panel subió **16 → 17** con notas de versión en castellano: es lo que hace aparecer el botón en los paneles del equipo apenas la central corra v17.
- ⚠️ **Decisión pendiente del dueño**: el sistema de updates, tal como fue diseñado, solo acepta consultas desde **Tailscale** (ni siquiera la red local del negocio). Para repartirlo a marketing hay que elegir: (A) instalar Tailscale (funciona desde cualquier lado, existe el instalador automático de sucursal que lo configura todo, requiere crear la red y una clave) o (B) permitir también la red local del negocio (cambio chico y acotado en el receptor; funciona solo en la oficina, con la PC central prendida — IP actual: 192.168.0.116).

## Deuda y pendientes conocidos (con dueño)

1. **Instalar v17 en la PC central**: el build está listo; el panel del dueño estaba abierto — se instala apenas se cierre. Sin esto, el equipo no ve el botón.
2. Las **placas de Descargables pesan 45,9 MB** en total (PNGs de 1–2 MB mostrados a 110px): la propuesta es que el **panel genere variantes webp al subir** (como ya hace con el póster de video). Está presupuestado en RENDIMIENTO.md.
3. **Tiempo real** (que el vendedor vea publicaciones sin refrescar): recomendado polling de 90s con ETag (costo cero backend) sobre SSE. No implementado — decisión del dueño.
4. La sonda F5 de la suite tiene un falso positivo conocido (documentado en REPORTE-FASE3.md).
5. Contenido: EMBALAJE ESPECIAL tiene palabras pegadas de un pegado viejo ("correctapreservación", "mueblesespecificadas") — es limpieza editorial, no código.
6. El botón Atrás del navegador saca del panel (H4 de la auditoría) — quedó fuera del alcance de esta pasada.

## Bugs encontrados vs. resueltos

De los 8 hallazgos funcionales de la auditoría: **6 resueltos** (desborde tablet, Escape en Historial, targets, imagen rota del lightbox, btnAddModulo, borrar-sin-avisar), 1 retirado por falsa alarma (insertar-bloque), 1 pendiente con dueño (botón Atrás). De los 13 hallazgos §3.5 del prompt sobre el editor: 9 resueltos en esta pasada, 2 ya estaban resueltos, 1 no reproducido, 1 es contenido.
