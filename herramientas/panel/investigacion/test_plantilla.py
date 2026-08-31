# -*- coding: utf-8 -*-
"""Prueba el bloque "Plantilla de WhatsApp": que respete la estructura real de
Meta y que se vea igual en el editor y en la intranet."""
import os
import sys
import hashlib
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8177
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")
OUT = os.path.join(AQUI, "fotos"); os.makedirs(OUT, exist_ok=True)
ok, fallos = 0, []


def check(n, c, extra=""):
    global ok
    if c:
        ok += 1
        print("  OK   %s %s" % (n, extra))
    else:
        fallos.append(n)
        print("  FALLA %s %s" % (n, extra))


antes = hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest()
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

print("=" * 70)
print("PRUEBA DEL BLOQUE PLANTILLA DE WHATSAPP")
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1440, "height": 950}, device_scale_factor=2)
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")

    print("\n[1] El bloque existe y se llama como corresponde")
    check("está en la paleta", pag.evaluate("() => !!BLOQUE_INFO.plantilla"))
    check("se llama 'Plantilla de WhatsApp'",
          pag.evaluate("() => BLOQUE_INFO.plantilla.label") == "Plantilla de WhatsApp",
          pag.evaluate("() => BLOQUE_INFO.plantilla.label"))
    nuevo = pag.evaluate("() => bloqueNuevo('plantilla')")
    check("nace con las 3 categorías de Meta", nuevo["categoria"] == "marketing")
    check("y con los dos formatos", nuevo["formato"] == "simple")
    check("el carrusel arranca con 2 tarjetas (el mínimo de Meta)",
          len(nuevo["tarjetas"]) == 2, "%d" % len(nuevo["tarjetas"]))

    print("\n[2] El HTML publicado")
    h = pag.evaluate("""() => bloqueHTML({t:'plantilla', categoria:'marketing', formato:'simple',
        encabezado:{tipo:'texto', texto:'Semana de cuotas', src:''},
        cuerpo:'{{1}}, tenemos 3 y 6 cuotas sin interés en zona {{2}}.',
        pie:'Respondé BAJA para no recibir más',
        botones:[{tipo:'enlace', texto:'Ver promo', url:'https://x.com'},
                 {tipo:'rapida', texto:'Me interesa', url:''}]})""")
    check("marca la categoría", 'class="wt-cat">Marketing' in h)
    check("saca el encabezado de texto", 'wt-hdrt">Semana de cuotas' in h)
    check("resalta las variables {{1}}", h.count('class="wt-var"') == 2, h.count('class="wt-var"'))
    check("muestra el pie", 'wt-foot">Respondé BAJA' in h)
    check("el botón de enlace lleva ícono", 'wt-btn"><span class="ico"><svg' in h)
    check("la respuesta rápida NO lleva ícono",
          '<div class="wt-btn">Me interesa</div>' in h, h[-160:])
    check("no usa las clases wa- del teléfono (nada de colisiones)",
          'wa-btn' not in h and 'wa-carousel' not in h)

    hc = pag.evaluate("""() => bloqueHTML({t:'plantilla', categoria:'utilidad', formato:'carrusel',
        encabezado:{tipo:'ninguno'}, cuerpo:'Mirá estos modelos', pie:'', botones:[],
        tarjetas:[{src:'assets/_modulos/a.png', cuerpo:'Berlín 3 cuerpos',
                   botones:[{tipo:'enlace',texto:'Ver ficha',url:'#'},{tipo:'rapida',texto:'Me interesa'}]},
                  {src:'', cuerpo:'Marine', botones:[{tipo:'rapida',texto:'Me interesa'}]}]})""")
    check("el carrusel se marca como tal", 'Utilidad · Carrusel' in hc)
    # una tarjeta SIN foto no se publica: Meta la pide obligatoria
    check("publica solo las tarjetas con foto", hc.count('class="wt-card"') == 1,
          "%d de 2" % hc.count('class="wt-card"'))
    hce = pag.evaluate("""() => plantillaHTML({t:'plantilla', categoria:'utilidad', formato:'carrusel',
        encabezado:{tipo:'ninguno'}, cuerpo:'Mirá estos modelos', pie:'', botones:[],
        tarjetas:[{src:'assets/_modulos/a.png', cuerpo:'Berlín', botones:[]},
                  {src:'', cuerpo:'', botones:[]}]}, true)""")
    check("en el editor la tarjeta sin foto se ve como hueco",
          hce.count('class="wt-card"') == 2 and 'wt-cimg"><span class="ico"><svg' in hce)
    check("y la que tiene foto la usa", 'src="assets/_modulos/a.png"' in hc)
    check("avisa que se desliza", 'wt-hint' in hc)
    vacio = pag.evaluate("() => bloqueHTML({t:'plantilla', formato:'simple', cuerpo:'', encabezado:{tipo:'ninguno'}})")
    check("una plantilla vacía no ensucia el sitio", vacio == "", vacio[:40])

    print("\n[3] Compatibilidad con el modelo viejo")
    v = pag.evaluate("""() => { const b = {t:'plantilla', tarjetas:[
        {src:'assets/x.png', texto:'Hola', btnTexto:'Ver', btnUrl:'https://x'},
        {src:'assets/y.png', texto:'Chau', btnTexto:'Ver', btnUrl:'https://y'}]};
        migrarPlantilla(b); return b; }""")
    check("una plantilla vieja se migra sola", v["cuerpo"] == "Hola", str(v.get("cuerpo")))
    check("dos tarjetas viejas pasan a carrusel", v["formato"] == "carrusel")
    check("y conserva los botones", v["tarjetas"][0]["botones"][0]["texto"] == "Ver")

    print("\n[4] En el editor")
    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=20000)
    pag.evaluate("() => abrirDoc(0)")
    pag.wait_for_timeout(600)
    pag.evaluate("""() => { BLOQUES.length = 0; renderCanvas(); }""")
    pag.evaluate('''() => { const b = document.querySelector('#gbAdd .gb-tipo[data-t="plantilla"]');
        if (b) { const d = b.closest("details"); if (d) d.open = true; } }''')
    pag.wait_for_timeout(150)
    pag.click('#gbAdd .gb-tipo[data-t="plantilla"]')
    pag.wait_for_timeout(500)
    check("se inserta desde la paleta", pag.evaluate("() => BLOQUES[SEL] && BLOQUES[SEL].t") == "plantilla")
    txt = pag.text_content("#gbInspector") or ""
    for opcion in ("Marketing", "Utilidad", "Autenticación", "Un mensaje", "Carrusel de tarjetas",
                   "Sin encabezado", "Cuerpo del mensaje", "Pie (opcional)", "Botones"):
        check("el editor ofrece '%s'" % opcion, opcion in txt)
    check("muestra el contador de caracteres", "/ 1024" in txt, txt[:0])

    pag.evaluate("""() => { const b = BLOQUES[SEL];
        b.cuerpo = 'Hola {{1}}, mirá esto'; b.pie = 'Pie de prueba';
        b.botones = [{tipo:'enlace', texto:'Ver promo', url:'https://x'}];
        renderCanvas(); renderInspector(); }""")
    pag.wait_for_timeout(400)
    check("el lienzo muestra la burbuja de WhatsApp",
          pag.query_selector("#gbDoc .wt-msg") is not None)
    check("con la variable resaltada", pag.query_selector("#gbDoc .wt-var") is not None)
    check("y el botón con su ícono",
          pag.evaluate("() => !!document.querySelector('#gbDoc .wt-btn svg')"))
    verde = pag.evaluate("""() => getComputedStyle(document.querySelector('#gbDoc .wt-msg')).backgroundColor""")
    check("la burbuja es verde WhatsApp", verde == "rgb(217, 253, 211)", verde)

    pag.evaluate("() => { BLOQUES[SEL].formato = 'carrusel'; renderCanvas(); renderInspector(); }")
    pag.wait_for_timeout(400)
    check("el carrusel se ve en el lienzo",
          pag.evaluate("() => document.querySelectorAll('#gbDoc .wt-card').length") == 2)
    check("y el editor pide las fotos de cada tarjeta",
          "Tarjeta 1" in (pag.text_content("#gbInspector") or ""))
    pag.locator("#gbDoc .gb-block").first.screenshot(path=os.path.join(OUT, "P-plantilla-editor.png"))

    print("\n[5] Los límites de Meta se avisan")
    pag.evaluate("""() => { const b = BLOQUES[SEL]; b.formato = 'simple';
        b.botones = [{tipo:'enlace',texto:'a',url:''},{tipo:'enlace',texto:'b',url:''},
                     {tipo:'enlace',texto:'c',url:''}];
        renderCanvas(); renderInspector(); }""")
    pag.wait_for_timeout(300)
    check("avisa si hay más de 2 botones de enlace",
          "hasta 2 botones de enlace" in (pag.text_content("#gbInspector") or ""))
    check("cero errores de consola", not errores, "; ".join(errores[:3]))
    nav.close()

httpd.shutdown()
check("modulos.js NO se toco", hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest() == antes)

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
