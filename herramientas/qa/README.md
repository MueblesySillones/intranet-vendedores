# Suite QA — panel + intranet

Suite permanente de QA visual y funcional del panel administrativo (web2) y
de la intranet de vendedores. Nace de la auditoría del 28-ago-2026: los
scripts sueltos de esa auditoría, ordenados, parametrizados y con umbrales
que **fallan** (exit code 1) cuando algo empeora.

## Seguridad, antes que nada

- **La publicación está bloqueada en el navegador.** Todos los contextos del
  panel salen de `contexto_seguro()` (arnes.py), que intercepta
  `/api/publicar`, `/api/enviar`, `/api/shutdown`, `/api/set-publish-token` y
  `/api/update-apply` y responde `ok:true` sin dejar pasar nada. La suite
  clickea todo; sin esto, una corrida subiría publicaciones de prueba al
  sitio que ven los vendedores.
- **Nunca correr contra el estado real.** Los tests escriben publicaciones,
  editan módulos y tocan la configuración de Datos. Por eso `correr_todo.py`
  arma siempre un **sandbox** (copia de la intranet + estado desde
  `fixtures/estado-base/`) y el panel se lanza apuntando ahí
  (`MYS_PROYECTO`/`MYS_PANEL_STATE`). El panel instalado y su estado en
  `%LOCALAPPDATA%\PanelMyS_state` no se tocan jamás.
- Los puertos por defecto (**8143** panel, **8813** intranet) están elegidos
  para no chocar con nada vivo: 8124 (panel instalado), 8125 (receptor),
  8136/8141/8811 (usados por otras corridas y pruebas).

## Requisitos

- Python 3.12 con `playwright` (y el Chromium de Playwright ya instalado:
  `python -m playwright install chromium`).
- `Pillow` para la comparación visual fina de t4 (verificado instalado:
  12.2.0). Sin Pillow, t4 cae solo a una comparación más gruesa por hash de
  bloques hecha con biblioteca estándar (ver t4 abajo).
- Sin pytest, sin dependencias nuevas: cada test es un script con
  contadores ok/aviso/falla, como el resto del código del proyecto.

## Cómo se corre

```bat
cd "C:\Users\Redes 1\Documents\web dinamica-mys\herramientas\qa"
python correr_todo.py
```

Eso: (1) arma el sandbox, (2) levanta panel e intranet como procesos hijos
con log en `salida/logs/`, (3) corre t1→t2→t3→t4, (4) imprime el resumen
OK/FALLA por bloque y (5) apaga los servidores pase lo que pase. Exit code
global: 0 limpio, 1 con fallas.

Variantes:

```bat
python correr_todo.py --solo t2 t3        &rem solo esos bloques
python correr_todo.py --sin-sandbox       &rem reusa el sandbox existente
python correr_todo.py --capturar-baseline &rem regenera qa/baseline/ (ver t4)
```

También se puede correr un bloque suelto (`python t1_crawl.py`) si ya hay
servidores arriba en `PANEL_URL`/`INTRA_URL` — por ejemplo los que deja una
corrida de `correr_todo.py` interrumpida con el sandbox armado, o un
`python arnes.py servir-panel` propio. Correr un bloque suelto contra un
panel que NO apunte a un sandbox es mala idea (ver Seguridad).

### Variables de entorno

Todas opcionales; los defaults apuntan al repo real y a los puertos de QA.

| Variable        | Default                                             | Qué es |
|-----------------|-----------------------------------------------------|--------|
| `PANEL_URL`     | `http://127.0.0.1:8143/`                            | URL del panel; su puerto es el que usa el lanzador |
| `INTRA_URL`     | `http://localhost:8813/intranet/index.html`         | URL de la intranet servida del sandbox |
| `QA_PROYECTO`   | dos carpetas arriba de `qa/` (el repo)              | de acá se copia `intranet/` al sandbox |
| `PANEL_SRC`     | `QA_PROYECTO/herramientas/panel`                    | carpeta con `panel_server.py` y `web2/`; apuntala a un snapshot para probar código congelado |
| `QA_SALIDA`     | `qa/salida`                                         | resultados (screenshots, evidencia, diffs, logs) |
| `QA_SANDBOX`    | `QA_SALIDA/sandbox`                                 | dónde se arma el sandbox |
| `QA_MODULO`     | `EMBALAJE`                                          | texto del módulo que abre el editor en t1/t2/t4 |
| `MODULOS_JS`    | `QA_SANDBOX/proyecto/intranet/modulos.js`           | el archivo que t2 lee como "verdad del disco" |
| `QA_VISUAL_TOL` | `0.5`                                               | tolerancia de t4 (% de píxeles, o de bloques sin Pillow) |

Ejemplo (probar un snapshot congelado sin tocar el repo):

```bat
set QA_PROYECTO=C:\ruta\al\snapshot
set PANEL_SRC=C:\ruta\al\snapshot\herramientas\panel
python correr_todo.py
```

## Qué mide cada bloque

### t1_crawl.py — el panel, pantalla por pantalla
5 pantallas (cartelera, módulos, editor, datos, métricas) × 3 anchos
(1440/1024/768). Por cada una: captura full-page, desborde horizontal,
imágenes rotas, áreas táctiles chicas (<40 y <32 px) y errores JS; a 1440
además axe-core (WCAG A/AA, `axe.min.js` local 4.13) e inventario de
controles. **Falla** con desborde > 0, imágenes rotas, errores JS o
violaciones axe **nuevas** (ids que no figuran en
`fixtures/axe-conocidas-panel.json`). Los targets chicos son aviso.
`python t1_crawl.py --aceptar-axe` fija el piso de violaciones conocidas.

### t2_flujos.py — los flujos de marketing, de punta a punta
F1–F20 sobre la cartelera, el editor de bloques, Datos y los modales:
crear / doble-click / editar / fijar / ocultar / duplicar / eliminar →
papelera → restaurar / "Archivar en" habilita su select / undo / eliminar
bloque / guardar / interruptor de Datos / deck en pestaña nueva / descargar
Word / métricas / avisar novedad / historial + Escape / título de 300
caracteres. La verdad no es la UI sino el `modulos.js` del sandbox. Estados:
`OK`; `ROTO`/`EXCEPCION` **fallan**; el resto (`INCONSISTENTE`,
`SIN FEEDBACK`, `NO ENCONTRADO`, `RARO`, `VACIA`, `SIN DATOS`,
`SIN CONTROL`) son avisos. Cada flujo corre en su propio try: uno que
explota no esconde a los demás. Al final borra sus publicaciones de prueba
(quedan en la papelera del sandbox, que se descarta).

### t3_intranet.py — la vista del vendedor
4 vistas (portada, embalaje, descargables, whatsapp) × 3 anchos
(1440/768/390-móvil): desborde, imágenes rotas, errores JS; axe a 1440
contra `fixtures/axe-conocidas-intranet.json` (mismo mecanismo
`--aceptar-axe`). Además métricas de lectura del manual (tamaño de letra,
interlineado, caracteres por línea, ritmo entre bloques) y del feed (ancho
de columna ≤ 680 px): esas son **aviso** cuando se van de rango, porque el
rango es criterio de diseño, no regresión dura.

### t4_visual.py — regresión visual contra baseline
Captura 10 pantallas clave (5 del panel a 1440, 4 de la intranet a 1440,
portada a 390) con animaciones congeladas y las compara pixel a pixel contra
`qa/baseline/`. **Falla** si alguna difiere más que `QA_VISUAL_TOL` (default
0.5 % de píxeles, perdonando deltas de canal ≤ 12 por el antialiasing) y
deja el diff pintado en rojo en `salida/diffs/`. Sin baseline devuelve
exit 2 y `correr_todo.py` lo informa como **PENDIENTE**, no como falla.

Comparación: con **Pillow** (instalado, 12.2.0) es por píxel. Si Pillow no
estuviera, cae a un plan B de biblioteca estándar: descomprime los scanlines
del PNG con zlib y compara hashes por bloques de 16 filas — más grueso (la
tolerancia pasa a ser % de bloques y un pixel cambiado marca su bloque
entero), pero suficiente como alarma de "algo cambió"; el detalle queda en
un `.txt` en `salida/diffs/` con las filas aproximadas.

**La baseline todavía no existe, a propósito.** Se captura recién cuando el
rediseño (web2 + intranet) esté integrado y revisado a ojo:

```bat
python correr_todo.py --capturar-baseline
```

Capturarla antes solo congelaría los defectos de una obra a medio hacer.
Regenerarla cada vez que se cambia el diseño **a propósito** (y revisar el
diff a ojo antes: la baseline nueva bendice lo que muestre). Importante:
baseline y comparación corren siempre sobre un sandbox recién armado
(`correr_todo.py` rearma el sandbox antes de t4, porque t2 ensucia el
contenido); si cambia el contenido real de la intranet (publicaciones,
imágenes), la baseline también hay que regenerarla — t4 vigila layout, no
contenido.

## Fixtures

- `fixtures/estado-base/` — copia del estado del panel
  (`%LOCALAPPDATA%\PanelMyS_state`) hecha **una sola vez** (28-ago-2026).
  La suite depende de esta copia, no de la máquina. Si algún día hace falta
  refrescarla (nuevos reportes de Datos, por ejemplo):
  `robocopy "%LOCALAPPDATA%\PanelMyS_state" fixtures\estado-base /E /PURGE`
  — y revisar que no viaje nada sensible antes de compartirla.
- `fixtures/config-colaborador.json` — identidad de prueba con rol
  **colaborador**. El flujo `/api/enviar` (propuesta al central) queda
  **pendiente de automatizar**: para ensayarlo a mano, copiar este archivo
  como `identity.json` dentro de `salida/sandbox/estado/` antes de lanzar el
  panel y apuntar `central_url` a un receptor de prueba. Ningún test lo usa
  todavía (el arnés además bloquea `/api/enviar` por seguridad).
- `fixtures/axe-conocidas-panel.json` / `axe-conocidas-intranet.json` — el
  piso de violaciones axe conocidas. Regenerarlas (`--aceptar-axe`) cuando
  el rediseño integrado quede revisado, igual que la baseline.
- **Fixture que falta:** un video de más de 40 MB para probar la compresión
  al subir video en el editor (el flujo existe en el panel; sin un archivo
  así de pesado en el repo, la suite no lo cubre).

## Salida

Todo lo generado vive en `salida/` (se puede borrar entero sin miedo):
`screenshots/` (t1/t3), `visual/` (capturas actuales de t4), `diffs/`
(diferencias visuales), `evidencia/` (JSON por bloque + `*-resumen.json`),
`logs/` (servidores), `sandbox/` (la copia descartable).

**Ni `salida/` ni `fixtures/estado-base/` ni `baseline/` deberían
commitearse** (estado real de la casa, decenas de MB de capturas): si el
repo se comparte, agregarlos a `.gitignore`.

## Limitaciones conocidas

- t2/F19 (historial) consulta GitHub: sin red queda `SIN DATOS` (aviso, no
  falla). El resto corre 100 % local.
- La pantalla Datos analiza la planilla desde los cachés del fixture; si el
  fixture se refresca con otra planilla, los tiempos de espera (8 s) pueden
  quedar cortos.
- t4 compara contra contenido congelado: cambios legítimos de contenido
  (una publicación nueva en la intranet real) piden regenerar baseline.
- El flujo colaborador (`/api/enviar`) y la compresión de video >40 MB
  quedan pendientes (ver Fixtures).
