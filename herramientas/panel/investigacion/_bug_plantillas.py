# -*- coding: utf-8 -*-
"""Busca el bug de las plantillas en Normas de WhatsApp con el contenido que
YA guardo el usuario (65 bloques, content propio)."""
import os, sys, threading, json
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

OUT = os.path.join(AQUI, "fotos"); os.makedirs(OUT, exist_ok=True)
httpd = ThreadingHTTPServer(("127.0.0.1", 8176), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    web = nav.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
    err = []
    web.on("pageerror", lambda e: err.append(str(e)))
    web.goto("http://127.0.0.1:8176/intranet/index.html", wait_until="networkidle")
    web.wait_for_selector(".tile", timeout=20000)
    web.evaluate("() => openSection('whatsapp')")
    web.wait_for_timeout(1500)

    print("errores JS:", err[:3])
    print(json.dumps(web.evaluate("""() => {
      const o = {};
      o.wt = document.querySelectorAll('.wt').length;
      o.waCarousel = document.querySelectorAll('.wa-carousel').length;
      o.waCard = document.querySelectorAll('.wa-card').length;
      o.telefono = document.querySelectorAll('.wa').length;
      o.svgGrandes = [...document.querySelectorAll('#secBody svg')]
        .filter(s => s.getBoundingClientRect().width > 40)
        .map(s => ({w: Math.round(s.getBoundingClientRect().width),
                    padre: (s.parentElement||{}).className || '',
                    abuelo: ((s.parentElement||{}).parentElement||{}).className || ''}));
      // cajas que se desbordan del contenedor
      const cont = document.getElementById('secBody').getBoundingClientRect();
      o.desbordan = [...document.querySelectorAll('#secBody *')]
        .filter(n => { const r = n.getBoundingClientRect();
                       return r.width > 0 && (r.right > cont.right + 4 || r.left < cont.left - 4); })
        .slice(0, 8)
        .map(n => ({cls: (typeof n.className === 'string' ? n.className : '') || n.tagName,
                    w: Math.round(n.getBoundingClientRect().width)}));
      return o;
    }"""), indent=1, ensure_ascii=False))

    # capturar cada zona de plantillas
    for sel, nombre in ((".wa-carousel", "carrusel-panel"), (".wt", "plantilla-nueva"), (".wa", "telefono")):
        els = web.query_selector_all(sel)
        for i, e in enumerate(els[:2]):
            try:
                e.scroll_into_view_if_needed(); web.wait_for_timeout(300)
                e.screenshot(path=os.path.join(OUT, "BUG-%s-%d.png" % (nombre, i)))
                print("captura:", nombre, i)
            except Exception as ex:
                print("no pude capturar", nombre, i, str(ex)[:60])
    nav.close()
httpd.shutdown()
