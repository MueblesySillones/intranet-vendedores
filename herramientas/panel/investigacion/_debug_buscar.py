# -*- coding: utf-8 -*-
import os, sys, threading, json
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

httpd = ThreadingHTTPServer(("127.0.0.1", 8181), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page()
    pag.on("pageerror", lambda e: print("PAGEERROR:", e))
    pag.on("console", lambda m: print("consola:", m.type, m.text) if m.type == "error" else None)
    pag.goto("http://127.0.0.1:8181", wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)

    print(pag.evaluate("""() => {
      const out = {};
      out.hayModulos = MODULOS.length;
      out.tipos = MODULOS.map(m => (m.content||{}).tipo || 'sin content');
      out.sinTilde = typeof sinTilde;
      out.txtOf = typeof txtOf;
      const m = MODULOS.find(x => x.key === 'descargables');
      out.descargablesTipo = m && (m.content||{}).tipo;
      out.primerBloque = m && m.content && m.content.bloques && m.content.bloques[0];
      try { out.texto1 = textoDeBloque(out.primerBloque || {}).slice(0,120); }
      catch(e){ out.errTexto = String(e); }
      try { out.res = buscarEnTodo('descargar').length; }
      catch(e){ out.errBuscar = String(e); }
      try { out.res2 = buscarEnTodo('material').length; }
      catch(e){ out.errBuscar2 = String(e); }
      return out;
    }"""))
    nav.close()
httpd.shutdown()
