# -*- coding: utf-8 -*-
import os, sys, threading, json
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

OUT = os.path.join(AQUI, "fotos"); os.makedirs(OUT, exist_ok=True)
httpd = ThreadingHTTPServer(("127.0.0.1", 8179), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    web = nav.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
    web.goto("http://127.0.0.1:8179/intranet/index.html", wait_until="networkidle")
    web.wait_for_selector(".tile", timeout=20000)
    web.evaluate("() => openSection('whatsapp')")
    web.wait_for_timeout(1200)

    info = web.evaluate("""() => {
      const out = {clases: {}, svgGrandes: []};
      document.querySelectorAll('#secBody *').forEach(n => {
        (n.className && typeof n.className === 'string' ? n.className.split(/\\s+/) : []).forEach(c => {
          if (c) out.clases[c] = (out.clases[c]||0)+1; });
      });
      document.querySelectorAll('#secBody svg').forEach(s => {
        const r = s.getBoundingClientRect();
        if (r.width > 40) out.svgGrandes.push({
          w: Math.round(r.width), h: Math.round(r.height),
          padre: s.parentElement ? (s.parentElement.className || s.parentElement.tagName) : '',
          abuelo: s.parentElement && s.parentElement.parentElement ? (s.parentElement.parentElement.className||'') : ''
        });
      });
      out.totalSvg = document.querySelectorAll('#secBody svg').length;
      return out;
    }""")
    print("SVG grandes (rotos):", len(info["svgGrandes"]))
    for s in info["svgGrandes"][:8]:
        print("   ", s)
    print("\nclases con 'wa' o 'tpl' o 'phone':")
    for c, n in sorted(info["clases"].items()):
        if any(k in c.lower() for k in ("wa", "tpl", "phone", "tel", "mock", "plant")):
            print("   %-24s x%d" % (c, n))

    # capturar el bloque roto
    el = web.query_selector(".wa-mock, .phone, .tpl-phone, .wa-phone")
    if not el:
        # buscar el ancestro comun de los svg grandes
        el = web.evaluate_handle("""() => {
            const s = [...document.querySelectorAll('#secBody svg')].filter(x => x.getBoundingClientRect().width > 40);
            if (!s.length) return null;
            let p = s[0];
            for (let i=0;i<6 && p.parentElement;i++) p = p.parentElement;
            return p;
        }""").as_element()
    if el:
        el.screenshot(path=os.path.join(OUT, "W3-bloque-roto.png"))
        print("\ncaptura del bloque roto lista")
        print("html del bloque (primeros 900):")
        print(web.evaluate("(e) => e.outerHTML.slice(0,900)", el))
    nav.close()
httpd.shutdown()
