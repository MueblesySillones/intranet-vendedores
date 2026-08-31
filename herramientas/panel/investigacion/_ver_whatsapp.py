# -*- coding: utf-8 -*-
import os, sys, threading, json
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

OUT = os.path.join(AQUI, "fotos"); os.makedirs(OUT, exist_ok=True)
PORT = 8180
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()

    # --- como lo ve el VENDEDOR ---
    web = nav.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=2)
    errw = []
    web.on("pageerror", lambda e: errw.append(str(e)))
    web.goto("http://127.0.0.1:%d/intranet/index.html" % PORT, wait_until="networkidle")
    web.wait_for_selector(".tile", timeout=20000)
    web.evaluate("() => openSection('whatsapp')")
    web.wait_for_timeout(1200)
    web.screenshot(path=os.path.join(OUT, "W1-whatsapp-intranet.png"), full_page=True)
    print("errores intranet:", errw[:3])
    print("bloques wa en la intranet:", web.evaluate("""() => ({
        waCarousel: document.querySelectorAll('.wa-carousel').length,
        waCard: document.querySelectorAll('.wa-card').length,
        chat: document.querySelectorAll('.chat').length,
        situ: document.querySelectorAll('.situ').length,
    })"""))

    # --- como lo ve el PANEL ---
    pag = nav.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
    errp = []
    pag.on("pageerror", lambda e: errp.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")
    i = pag.evaluate("() => MODULOS.findIndex(m => m.key === 'whatsapp')")
    print("indice whatsapp:", i)
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_timeout(1800)
    pag.screenshot(path=os.path.join(OUT, "W2-whatsapp-panel.png"), full_page=True)
    print("tipos de bloque en el editor:", pag.evaluate("() => BLOQUES.map(b => b.t)"))
    print("errores panel:", errp[:3])
    nav.close()
httpd.shutdown()
print("listo")
