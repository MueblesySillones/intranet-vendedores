# REPORTE — FASE 3 · Suite de QA visual y funcional permanente

**29-08-2026.** Los scripts sueltos de la auditoría del 28-ago quedaron convertidos en una suite ordenada, reusable y documentada en `herramientas\qa\` (carpeta nueva; no toca `herramientas\panel\` ni `intranet\`). Python + Playwright, sin pytest ni dependencias nuevas, estilo ok/aviso/falla con contadores y comentarios en castellano, como el resto del proyecto.

## 1. Estructura entregada

```
herramientas\qa\
  arnes.py            helpers compartidos: config por entorno, contexto con la
                      publicación SIEMPRE bloqueada (/api/publicar, /api/enviar,
                      /api/shutdown, /api/set-publish-token, /api/update-apply),
                      axe-core, métricas, lanzadores de panel e intranet
  crear_sandbox.py    arma el sandbox (intranet copiada + estado desde fixtures)
  t1_crawl.py         panel: 5 pantallas × 3 anchos — desborde, imgs rotas,
                      errores JS, axe nuevas FALLAN; targets <40/<32 avisan
  t2_flujos.py        F1–F20 de punta a punta, verdad = modulos.js del sandbox;
                      ROTO/EXCEPCION fallan, el resto avisa
  t3_intranet.py      vista vendedor: 4 vistas × 3 anchos + axe + lectura + feed
  t4_visual.py        regresión visual vs baseline/ con tolerancia (Pillow;
                      fallback stdlib por hash de bloques de scanlines)
  correr_todo.py      orquesta: sandbox → servidores (8143/8813) → t1–t4 →
                      resumen y exit code global; baja los servidores SIEMPRE
  README.md           cómo correr, variables, umbrales, baseline, seguridad
  axe.min.js          axe-core 4.13 local
  fixtures\
    estado-base\          copia ÚNICA (28-ago) de %LOCALAPPDATA%\PanelMyS_state:
                          la suite no depende más de la máquina
    config-colaborador.json  identidad rol colaborador para ensayar /api/enviar
    axe-conocidas-panel.json / axe-conocidas-intranet.json  piso de violaciones
                          conocidas — fijado en CERO (el snapshot ya está limpio)
  baseline\           VACÍA a propósito (solo LEEME.md) — ver §4
  salida\             todo lo generado (evidencia de la validación incluida)
```

Parametrización por entorno (defaults apuntan al repo real): `PANEL_URL` (8143), `INTRA_URL` (8813), `QA_PROYECTO`, `PANEL_SRC` (para apuntar el server a un snapshot), `QA_SALIDA`, `QA_SANDBOX`, `QA_MODULO`, `MODULOS_JS`, `QA_VISUAL_TOL`. Puertos elegidos para no chocar con 8124/8125/8136/8141/8811.

## 2. Cómo se corre

```bat
cd "C:\Users\Redes 1\Documents\web dinamica-mys\herramientas\qa"
python correr_todo.py
```

Variantes: `--solo t2 t3` · `--sin-sandbox` · `--capturar-baseline`. Detalle completo en el README (incluye la advertencia de seguridad: la publicación se bloquea en el navegador y NUNCA se corre contra el estado real — siempre sandbox).

## 3. Corrida de validación (29-ago, contra snapshots congelados)

Validado contra **snapshots de mitad de obra** (panel/web2 e intranet copiados mientras los agentes de 2b/2c editaban), con `QA_PROYECTO`/`PANEL_SRC` apuntando a esos snapshots y puertos 8143/8813. Números por bloque:

| Bloque | Resultado | Tiempo | Detalle |
|---|---|---|---|
| t1 crawl | **OK — 34 ok / 9 avisos / 0 fallas** | 106 s | 0 desbordes en 15 pantalla×ancho (el 66px@768 ya no está), 0 imágenes rotas, 0 errores JS, **axe 0 violaciones en las 5 pantallas** @1440, 732 controles inventariados. Avisos: targets <32px (grips del editor 26×24, `#detCancel` 82×31, switches `dt-sw-i` 1×1) |
| t2 flujos | **OK — 19 ok / 2 avisos / 0 fallas** | 109 s | Los 20 flujos completos: crear/doble-click/editar/fijar/duplicar/papelera→restaurar/archivar-select/undo/eliminar bloque/guardar (toast "Guardado ✓")/datos/deck 9 slides/Word/métricas/avisar 11 módulos/historial 103 filas + Escape/título recortado a 120. Avisos legítimos de la obra: F5 ocultar no ofrece "Mostrar"; F17 Atrás → about:blank |
| t3 intranet | **OK — 29 ok / 5 avisos / 0 fallas** | 119 s | 0 desbordes y 0 rotas en 4 vistas × 3 anchos, **axe 0 en las 4 vistas** (fix 2a confirmado). Avisos = lo que 2c aún no atacó: letra 14.5px, 105 ch/línea, feed 692px, sin @media print |
| t4 visual | **PENDIENTE (sin baseline, exit 2)** | 0 s | Comportamiento diseñado: sin baseline no falla, avisa |

Resumen del orquestador: `t1 OK · t2 OK · t3 OK · t4 PENDIENTE` — exit global 0.

**El mecanismo de t4 se validó aparte** con una baseline DE PRUEBA sobre el snapshot: captura 10/10 pantallas (137 s) y comparación con Pillow 10/10 dentro de tolerancia (8 pantallas en 0.000 %; `panel-datos` 0.067 % por los relojes del tablero; `intranet-embalaje` 0.003 % — tolerancia 0.5 %), exit 0 (141 s). Esa baseline de prueba **se borró**: la definitiva no la captura esta fase (§4).

Transparencia: la primera pasada de t2 dio FALLA (8) por un bug **de la suite** — prints con "→" contra un pipe cp1252 tiraban `UnicodeEncodeError` dentro de los flujos. Se arregló (stdout UTF-8 en el arnés + `PYTHONIOENCODING` en el orquestador + F11 autosuficiente + limpieza con hover y reintentos) y la re-corrida quedó como arriba. La suite detectó y reportó bien su propio incendio, que es exactamente su trabajo.

Cierre verificado: servidores bajados por el `finally` del orquestador, sin LISTEN en 8143/8813 y sin procesos python residuales.

## 4. La baseline visual queda para DESPUÉS de integrar

`baseline\` está vacía a propósito. Capturarla hoy congelaría la obra a medio hacer de 2b/2c como "lo correcto". Cuando el rediseño esté integrado y revisado a ojo:

```bat
python correr_todo.py --capturar-baseline
```

y de ahí en más `correr_todo.py` compara cada corrida contra eso (falla >0.5 % de píxeles, diff pintado en `salida\diffs\`). Mismo criterio para el piso de axe: hoy quedó fijado en **cero** violaciones (los snapshots ya están limpios); si el criterio cambia, `--aceptar-axe` en t1/t3 lo refija.

## 5. Limitaciones conocidas

- **Los números de §3 describen los snapshots del 29-ago ~06:00**, no el estado final: para el veredicto real, correr `python correr_todo.py` sin variables (defaults = repo real) cuando 2b/2c terminen.
- F19 (historial) consulta GitHub: sin red queda `SIN DATOS` (aviso). Todo lo demás corre 100 % local.
- Fixtures pendientes: **video >40 MB** (para probar la compresión al subir video — no hay archivo así en el repo) y la automatización del flujo **colaborador** `/api/enviar` (el fixture `config-colaborador.json` ya está; el arnés además lo bloquea por seguridad).
- t4 vigila layout, no contenido: cambios legítimos de contenido piden regenerar baseline (README §t4).
- `salida\`, `fixtures\estado-base\` y `baseline\` no deberían commitearse (estado real de la casa + decenas de MB); hoy `herramientas\` ya está en `.gitignore`, pero si eso cambia, agregarlos.
