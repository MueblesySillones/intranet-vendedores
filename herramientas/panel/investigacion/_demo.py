
# -*- coding: utf-8 -*-
"""Capturas del antes/despues de las barras + demostracion del pegado de Word."""
import os, sys, threading
from http.server import ThreadingHTTPServer
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps
from playwright.sync_api import sync_playwright

OUT = os.path.join(AQUI, "fotos")
os.makedirs(OUT, exist_ok=True)
PORT = 8185

WORD = """<html xmlns:o="urn:schemas-microsoft-com:office:office"><head><style>
<!-- p.MsoNormal {mso-style-parent:""; font-size:12.0pt;} --></style></head><body>
<h1 style="mso-outline-level:1"><span lang=ES>Protocolo de entrega</span></h1>
<p class=MsoNormal style='margin:0cm'><b>Antes de salir</b>: confirmar la direcci&oacute;n
y el tel&eacute;fono del cliente.<o:p></o:p></p>
<p class=MsoNormal>Si el cliente no est&aacute;, avisar por <i>WhatsApp</i> y dejar
constancia en el <a href="https://mueblesysillones.com">sistema</a>.</p>
<ul><li>Revisar que el sill&oacute;n no tenga golpes</li>
<li>Sacar foto en el domicilio</li><li>Pedir la firma</li></ul>
<table border=0><tr><td>Zona</td><td>Entregas</td><td>Demora</td></tr>
<tr><td>CABA</td><td>128</td><td>2</td></tr>
<tr><td>Zona Sur</td><td>96</td><td>4</td></tr></table>
</body></html>"""

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1366, "height": 768}, device_scale_factor=2)
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")

    pag.locator("header.top").screenshot(path=os.path.join(OUT, "A-header-nuevo.png"))

    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=20000)
    pag.evaluate("() => abrirDoc(0)")
    pag.wait_for_timeout(900)
    pag.locator(".editor-bar").screenshot(path=os.path.join(OUT, "B-barra-editor-nueva.png"))

    # documento vacio: se ve el cartel de "tambien podes pegar"
    pag.evaluate("""() => { BLOQUES.length = 0; SEL = null; renderCanvas(); renderInspector(); }""")
    pag.wait_for_timeout(400)
    pag.screenshot(path=os.path.join(OUT, "C-antes-de-pegar.png"))

    # pegar Word
    pag.evaluate("""() => { BLOQUES.length = 0; BLOQUES.push({t:'parrafo', html:'Instructivo para el equipo de entregas.'});
                            SEL = 0; renderCanvas(); selectBlock(0); }""")
    pag.wait_for_timeout(300)
    pag.evaluate("""(h) => {
        const dt = new DataTransfer();
        dt.setData('text/html', h);
        dt.setData('text/plain', 'respaldo');
        const dest = document.querySelector('#gbDoc [contenteditable]');
        dest.focus();
        dest.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
    }""", WORD)
    pag.wait_for_timeout(700)
    pag.screenshot(path=os.path.join(OUT, "D-despues-de-pegar.png"))
    print("bloques que quedaron:", pag.evaluate("() => BLOQUES.map(b => b.t)"))
    nav.close()
httpd.shutdown()
print("listo")
