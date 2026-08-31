# -*- coding: utf-8 -*-
import os, sys, threading
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

httpd = ThreadingHTTPServer(("127.0.0.1", 8191), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1400, "height": 1000})
    pag.on("console", lambda m: print("   consola[%s]: %s" % (m.type, m.text)))
    pag.on("pageerror", lambda e: print("   PAGEERROR: %s" % e))
    pag.goto("http://127.0.0.1:8191", wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=15000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")

    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=15000)

    # espiar los eventos
    pag.evaluate("""() => {
      window.__log = [];
      const cont = document.getElementById('colList');
      ['pointerdown','pointermove','pointerup'].forEach(t =>
        cont.addEventListener(t, e => window.__log.push(t + ' target=' + e.target.tagName + '.' + e.target.className + ' btn=' + e.button), true));
      document.addEventListener('pointermove', () => window.__log.push('docmove'), true);
      window.__estado = () => ({
        hueco: !!document.querySelector('.ord-hueco'),
        flota: !!document.querySelector('.ord-flota'),
        ocultos: [...document.querySelectorAll('.col-item')].filter(n => n.style.display === 'none').length,
      });
    }""")

    items = pag.query_selector_all(".col-item")
    grip = items[0].query_selector(".col-grip")
    g = grip.bounding_box()
    d = items[2].bounding_box()
    print("grip box:", g)
    print("destino box:", d)

    pag.mouse.move(g["x"] + g["width"]/2, g["y"] + g["height"]/2)
    pag.mouse.down()
    print("tras down:", pag.evaluate("() => window.__estado()"))
    pag.mouse.move(g["x"] + g["width"]/2, g["y"] + g["height"]/2 + 30, steps=5)
    print("tras mover 30px:", pag.evaluate("() => window.__estado()"))
    pag.mouse.move(g["x"] + g["width"]/2, d["y"] + d["height"]*0.85, steps=10)
    print("tras mover al destino:", pag.evaluate("() => window.__estado()"))
    print("posicion del hueco:", pag.evaluate("""() => {
      const h = document.querySelector('.ord-hueco');
      if (!h) return 'sin hueco';
      return [...document.getElementById('colList').children].indexOf(h);
    }"""))
    pag.mouse.up()
    pag.wait_for_timeout(800)
    print("tras soltar:", pag.evaluate("() => window.__estado()"))
    print("orden final:", pag.evaluate("() => COLECCION.map(d => d.titulo)"))
    print("\neventos vistos:")
    for l in pag.evaluate("() => window.__log")[:14]:
        print("   ", l)
    nav.close()
httpd.shutdown()
