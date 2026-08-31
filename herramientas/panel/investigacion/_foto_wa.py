# -*- coding: utf-8 -*-
import os, sys, threading
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

OUT = os.path.join(AQUI, "fotos"); os.makedirs(OUT, exist_ok=True)
httpd = ThreadingHTTPServer(("127.0.0.1", 8178), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    web = nav.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=3)
    web.goto("http://127.0.0.1:8178/intranet/index.html", wait_until="networkidle")
    web.wait_for_selector(".tile", timeout=20000)
    web.evaluate("() => openSection('whatsapp')")
    web.wait_for_timeout(1200)
    tel = web.query_selector_all(".wa")
    print("telefonos encontrados:", len(tel))
    for i, t in enumerate(tel):
        t.scroll_into_view_if_needed()
        web.wait_for_timeout(250)
        t.screenshot(path=os.path.join(OUT, "WA-fix-%d.png" % i))
    print("botones y su tamaño de icono:", web.evaluate("""() => {
        return [...document.querySelectorAll('.wa-btn')].slice(0,3).map(b => {
            const s = b.querySelector('svg');
            const r = s ? s.getBoundingClientRect() : null;
            return {texto: b.textContent.trim(), display: getComputedStyle(b).display,
                    icono: r ? Math.round(r.width) + 'x' + Math.round(r.height) : 'sin icono'};
        });
    }"""))
    nav.close()
httpd.shutdown()
