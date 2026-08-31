# -*- coding: utf-8 -*-
import os, sys, threading
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

httpd = ThreadingHTTPServer(("127.0.0.1", 8184), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    pag.on("pageerror", lambda e: print("   PAGEERROR:", e))
    pag.goto("http://127.0.0.1:8184", wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")
    pag.evaluate("() => openDetalle(0)")
    pag.wait_for_timeout(1200)

    print("antes de tocar:", pag.evaluate("() => document.getElementById('detMoreMenu').hidden"))
    pag.click("#detMore")
    pag.wait_for_timeout(400)
    print("despues de tocar:", pag.evaluate("() => document.getElementById('detMoreMenu').hidden"))
    print(pag.evaluate("""() => {
        const m = document.getElementById('detMoreMenu');
        const r = m.getBoundingClientRect();
        const s = getComputedStyle(m);
        return {
          rect: {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)},
          display: s.display, visibility: s.visibility, opacity: s.opacity,
          position: s.position, zIndex: s.zIndex, overflow: s.overflow,
          items: [...m.children].map(b => ({id: b.id, hidden: b.hidden,
                  disp: getComputedStyle(b).display, txt: b.textContent.trim()})),
          padreOverflow: getComputedStyle(m.closest('.editor-bar')).overflow,
          padreRect: (function(){ const q = m.closest('.editor-bar').getBoundingClientRect();
                      return {y: Math.round(q.y), h: Math.round(q.height)}; })(),
        };
    }"""))
    pag.screenshot(path=os.path.join(AQUI, "fotos", "X-menu-mas.png"))
    nav.close()
httpd.shutdown()
