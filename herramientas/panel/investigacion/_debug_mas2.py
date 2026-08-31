# -*- coding: utf-8 -*-
import os, sys, threading
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

httpd = ThreadingHTTPServer(("127.0.0.1", 8183), ps.Handler)
threading.Thread(target=threading.Thread(target=httpd.serve_forever).start if 0 else httpd.serve_forever).start()


def estado(pag, etiqueta):
    r = pag.evaluate("""() => {
        const m = document.getElementById('detMoreMenu');
        const b = document.getElementById('detMore');
        const rb = b.getBoundingClientRect(), rm = m.getBoundingClientRect();
        return {oculto: m.hidden,
                botonVisible: rb.width > 0 && rb.right <= innerWidth && rb.left >= 0,
                botonX: Math.round(rb.x), anchoVentana: innerWidth,
                menuX: Math.round(rm.x), menuY: Math.round(rm.y),
                menuW: Math.round(rm.width), menuH: Math.round(rm.height),
                dentroDePantalla: rm.right <= innerWidth && rm.left >= 0 && rm.bottom <= innerHeight,
                visibles: [...m.children].filter(c => !c.hidden).map(c => c.textContent.trim())};
    }""")
    print("  %-28s %s" % (etiqueta, r))


with sync_playwright() as pw:
    nav = pw.chromium.launch()
    for ancho in (1366, 1280):
        pag = nav.new_page(viewport={"width": ancho, "height": 768})
        pag.on("pageerror", lambda e: print("   PAGEERROR:", e))
        pag.goto("http://127.0.0.1:8183", wait_until="networkidle")
        pag.wait_for_selector(".mod-card", timeout=20000)
        pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")
        print("\n=== ventana %dpx ===" % ancho)

        # a) modulo NUEVO
        pag.evaluate("() => nuevoModulo()")
        pag.wait_for_timeout(800)
        pag.click("#detMore"); pag.wait_for_timeout(300)
        estado(pag, "modulo nuevo")
        pag.evaluate("() => mostrarDetalle(false)"); pag.wait_for_timeout(300)

        # b) biblioteca: lista
        j = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
        pag.evaluate("(j) => openDetalle(j)", j)
        pag.wait_for_selector(".col-item", timeout=20000); pag.wait_for_timeout(500)
        pag.click("#detMore"); pag.wait_for_timeout(300)
        estado(pag, "biblioteca (lista)")

        # c) biblioteca: documento abierto
        pag.evaluate("() => { document.getElementById('detMoreMenu').hidden = true; abrirDoc(0); }")
        pag.wait_for_timeout(800)
        pag.click("#detMore"); pag.wait_for_timeout(300)
        estado(pag, "biblioteca (doc abierto)")
        pag.screenshot(path=os.path.join(AQUI, "fotos", "Y-mas-%d.png" % ancho))
        pag.close()
    nav.close()
httpd.shutdown()
