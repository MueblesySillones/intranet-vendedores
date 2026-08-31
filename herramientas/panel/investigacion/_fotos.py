# -*- coding: utf-8 -*-
"""Saca capturas del panel para poder MIRAR el estado actual de las barras."""
import os, sys, threading
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

OUT = os.path.join(AQUI, "fotos")
os.makedirs(OUT, exist_ok=True)
PORT = 8186
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")

    pag.locator("header.top").screenshot(path=os.path.join(OUT, "1-header-home.png"))
    pag.screenshot(path=os.path.join(OUT, "2-home.png"))

    # editor de un modulo comun
    i = pag.evaluate("() => MODULOS.findIndex(m => !(m.content && m.content.tipo === 'coleccion'))")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_timeout(1200)
    pag.locator(".editor-bar").screenshot(path=os.path.join(OUT, "3-barra-editor.png"))
    pag.screenshot(path=os.path.join(OUT, "4-editor.png"))
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(400)

    # biblioteca: lista y documento abierto (ahi aparece la segunda barra)
    j = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(j) => openDetalle(j)", j)
    pag.wait_for_selector(".col-item", timeout=20000)
    pag.wait_for_timeout(600)
    pag.screenshot(path=os.path.join(OUT, "5-biblioteca.png"))
    pag.evaluate("() => abrirDoc(0)")
    pag.wait_for_timeout(900)
    pag.screenshot(path=os.path.join(OUT, "6-doc-abierto.png"))
    pag.locator("#docBar").screenshot(path=os.path.join(OUT, "7-barra-doc.png"))
    nav.close()
httpd.shutdown()
print("capturas en:", OUT)
for f in sorted(os.listdir(OUT)):
    print(" -", f)

