# -*- coding: utf-8 -*-
"""Prueba los 4 pedidos: bug de las plantillas, paleta desplegable, ir a
Ajustes al insertar, y el boton Avisar novedad."""
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

PORT = 8175
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


# la plantilla EXACTA que armó el usuario y se veía mal
ROTA = """{t:'plantilla', categoria:'marketing', formato:'carrusel',
  encabezado:{tipo:'ninguno', texto:'', src:''}, cuerpo:'', pie:'', botones:[],
  tarjetas:[
    {src:'assets/_modulos/x.png', cuerpo:'mega oferta',
     botones:[{tipo:'rapida',texto:'quiero precio',url:''},{tipo:'rapida',texto:'quiero precio',url:''}]},
    {src:'', cuerpo:'', botones:[{tipo:'rapida',texto:'Ver ficha',url:''}]}
  ]}"""

antes = hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest()
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

print("=" * 70)
print("PRUEBA DE LOS 4 PEDIDOS")
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

    print("\n[1] El bug de las plantillas")
    h = pag.evaluate("() => bloqueHTML(" + ROTA + ")")
    check("ya NO sale la burbuja verde vacía", 'class="wt-msg"' not in h,
          "quedó: " + h[:60])
    check("la tarjeta a medio llenar no se publica", h.count('class="wt-card"') == 1,
          "%d tarjetas" % h.count('class="wt-card"'))
    check("la tarjeta cargada sí sale", 'mega oferta' in h)
    check("el cuerpo se emite siempre (así quedan parejas)",
          h.count('class="wt-cbody"') == h.count('class="wt-card"'))
    check("los botones van en su propio contenedor", 'class="wt-cbtns"' in h)

    # en el editor sí se ven los huecos, para poder completarlos
    he = pag.evaluate("() => plantillaHTML(" + ROTA + ", true)")
    check("en el editor SÍ se ve el hueco para completar", he.count('class="wt-card"') == 2)
    check("y avisa dónde falta escribir", 'wt-ph' in he)

    av = pag.evaluate("() => plantillaAvisos(" + ROTA + ")")
    print("     avisos: %d" % len(av))
    for a in av:
        print("       · " + a.replace("<b>", "").replace("</b>", ""))
    check("avisa que falta el mensaje de arriba", any("mensaje arriba" in a for a in av))
    check("avisa que esa tarjeta no se publica", any("no se publica" in a for a in av))
    check("avisa que la foto es obligatoria", any("obligatoria" in a for a in av))

    print("\n[2] La paleta ahora es desplegable")
    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=20000)
    pag.evaluate("() => abrirDoc(0)")
    pag.wait_for_timeout(700)
    check("cada grupo es un desplegable",
          pag.evaluate("() => document.querySelectorAll('#gbAdd details.gb-grupo').length") >= 5,
          "%d grupos" % pag.evaluate("() => document.querySelectorAll('#gbAdd details.gb-grupo').length"))
    check("muestra cuántos bloques tiene cada uno",
          pag.evaluate("() => !!document.querySelector('.gb-grupo-n')"))
    abiertos = pag.evaluate("() => [...document.querySelectorAll('#gbAdd details')].filter(d => d.open).length")
    check("arranca con uno solo abierto (no todo desplegado)", abiertos == 1, "%d abiertos" % abiertos)
    pag.evaluate("""() => { const d = [...document.querySelectorAll('#gbAdd details')]
        .find(x => x.querySelector('summary').textContent.includes('Números')); d.open = true;
        d.dispatchEvent(new Event('toggle')); }""")
    pag.wait_for_timeout(200)
    pag.evaluate("() => renderGbAdd()")
    pag.wait_for_timeout(200)
    check("recuerda el grupo que abriste",
          pag.evaluate("""() => [...document.querySelectorAll('#gbAdd details')]
              .some(d => d.open && d.querySelector('summary').textContent.includes('Números'))"""))
    pag.fill("#gbBuscar", "tabla")
    pag.wait_for_timeout(250)
    check("al buscar se abren solos para ver el resultado",
          pag.evaluate("""() => [...document.querySelectorAll('#gbAdd details')].every(d => d.open)"""))
    pag.fill("#gbBuscar", "")
    pag.wait_for_timeout(200)

    print("\n[3] Al insertar un bloque va directo a sus ajustes")
    pag.evaluate("() => { BLOQUES.length = 0; renderCanvas(); gbPane('agregar'); }")
    pag.wait_for_timeout(200)
    pag.evaluate("() => insertBloque('tabla')")
    pag.wait_for_timeout(400)
    check("se abre la pestaña Ajustes sola",
          pag.evaluate("""() => document.querySelector('.gb-pane[data-pane="ajustes"]').hidden === false"""))
    check("y son los ajustes DE ESE bloque",
          "Ajustes de: Tabla" in (pag.text_content("#gbInspTitle") or ""),
          pag.text_content("#gbInspTitle"))
    pag.evaluate("() => { gbPane('agregar'); insertBloque('separador'); }")
    pag.wait_for_timeout(400)
    check("también con un bloque sin texto (Línea)",
          pag.evaluate("""() => document.querySelector('.gb-pane[data-pane="ajustes"]').hidden === false"""))

    print("\n[4] El botón Avisar novedad")
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(400)
    check("existe el botón", pag.query_selector("#btnAvisar") is not None)
    check("guardar YA NO marca novedad solo",
          "det.actualizado = " not in pag.evaluate("() => guardarModulo.toString()"))
    pag.click("#btnAvisar")
    pag.wait_for_timeout(400)
    check("abre la lista de módulos",
          pag.evaluate("() => document.querySelectorAll('#avisarLista .avisar-item').length") ==
          pag.evaluate("() => MODULOS.length"),
          "%d de %d" % (pag.evaluate("() => document.querySelectorAll('#avisarLista .avisar-item').length"),
                        pag.evaluate("() => MODULOS.length")))
    check("marca los que ya están anunciados",
          pag.evaluate("""() => { const w = MODULOS.findIndex(m => m.key === 'whatsapp');
              const c = document.querySelectorAll('#avisarLista input')[w]; return c && c.checked; }"""))
    # marcar uno nuevo y confirmar
    pag.evaluate("""() => { window.__pub = 0; window.publicarCambios = async () => { window.__pub++; }; }""")
    pag.evaluate("""() => { const c = document.querySelectorAll('#avisarLista input')[0];
        c.checked = true; c.dispatchEvent(new Event('change')); }""")
    pag.click("#avisarGuardar")
    pag.wait_for_timeout(600)
    check("le pone la fecha de hoy al módulo marcado",
          pag.evaluate("() => MODULOS[0].actualizado") == pag.evaluate("() => hoyLocal()"),
          str(pag.evaluate("() => MODULOS[0].actualizado")))
    check("y publica al confirmar", pag.evaluate("() => window.__pub") == 1)
    check("el cuadro se cierra", pag.evaluate("() => document.getElementById('avisarModal').hidden"))
    # sacar el aviso
    pag.click("#btnAvisar"); pag.wait_for_timeout(300)
    pag.evaluate("""() => { const c = document.querySelectorAll('#avisarLista input')[0];
        c.checked = false; c.dispatchEvent(new Event('change')); }""")
    pag.click("#avisarGuardar")
    pag.wait_for_timeout(600)
    check("y se puede sacar del aviso", pag.evaluate("() => MODULOS[0].actualizado === undefined"))

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
