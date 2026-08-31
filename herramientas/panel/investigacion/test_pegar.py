# -*- coding: utf-8 -*-
"""Prueba pegar desde Word / Excel / una pagina: que se armen los bloques solos
y que NO entre la basura de Word al sitio publicado."""
import os
import sys
import hashlib
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8187
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")
ok, fallos = 0, []


def check(n, c, extra=""):
    global ok
    if c:
        ok += 1
        print("  OK   %s %s" % (n, extra))
    else:
        fallos.append(n)
        print("  FALLA %s %s" % (n, extra))


# HTML tal cual lo pone Word en el portapapeles (con su basura)
WORD = """<html xmlns:o="urn:schemas-microsoft-com:office:office"><head><style>
<!-- p.MsoNormal {mso-style-parent:""; font-size:12.0pt;} --></style></head><body>
<h1 style="mso-outline-level:1"><span lang=ES>Manual de derivaciones</span></h1>
<p class=MsoNormal style='margin:0cm'><b>Primer paso</b>: saludar al cliente<o:p></o:p></p>
<p class=MsoNormal>Segundo p&aacute;rrafo con <i>cursiva</i> y un
<a href="https://mueblesysillones.com">link</a>.</p>
<ul><li>Preguntar el modelo</li><li>Confirmar la sucursal</li></ul>
</body></html>"""

EXCEL = """<html><body><table border=0 cellpadding=0 cellspacing=0>
<tr><td>Sucursal</td><td>Enero</td><td>Total</td></tr>
<tr><td>Hudson</td><td>201</td><td>1.116</td></tr>
<tr><td>C&oacute;rdoba</td><td>340</td><td>2.350</td></tr>
</table></body></html>"""

SUELTO = "<html><body><p>una sola frase copiada</p></body></html>"

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
antes = hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest()

print("=" * 70)
print("PRUEBA: PEGAR DESDE WORD / EXCEL")
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1400, "height": 950})
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")

    print("\n[1] Decidir si romper en bloques o dejar inline")
    r = pag.evaluate("""(d) => ({
        word: pegarEsEstructurado(d.word),
        excel: pegarEsEstructurado(d.excel),
        suelto: pegarEsEstructurado(d.suelto),
    })""", {"word": WORD, "excel": EXCEL, "suelto": SUELTO})
    check("Word se reconoce como estructurado", r["word"] is True)
    check("Excel tambien", r["excel"] is True)
    check("una frase suelta NO (entra inline, como siempre)", r["suelto"] is False)

    print("\n[2] Word -> bloques")
    bl = pag.evaluate("(h) => pegarABloques(h)", WORD)
    tipos = [b["t"] for b in bl]
    print("     bloques: %s" % tipos)
    check("sale un titulo", tipos and tipos[0] == "titulo", str(tipos[:1]))
    check("con el texto del titulo", bl[0]["html"] == "Manual de derivaciones", bl[0]["html"])
    check("salen los parrafos", tipos.count("parrafo") == 2, str(tipos))
    check("conserva la negrita", "<b>Primer paso</b>" in bl[1]["html"], bl[1]["html"][:60])
    check("conserva la cursiva", "<i>cursiva</i>" in bl[2]["html"], bl[2]["html"][:70])
    check("conserva el link", 'href="https://mueblesysillones.com"' in bl[2]["html"])
    check("la vinieta sale como lista", "lista" in tipos)
    lista = next(b for b in bl if b["t"] == "lista")
    check("con sus 2 items", len(lista["items"]) == 2, str([i["html"] for i in lista["items"]]))

    print("\n[3] La basura de Word NO entra")
    todo = pag.evaluate("(h) => JSON.stringify(pegarABloques(h))", WORD)
    for basura in ("mso-", "MsoNormal", "<style", "urn:schemas", "lang=", "style="):
        check("no se cuela '%s'" % basura, basura not in todo)
    check("ni queda un bloque html crudo (el pasamanos)",
          "html" not in [b["t"] for b in bl], str(tipos))
    publicado = pag.evaluate("(h) => bloquesHTML(pegarABloques(h), false)", WORD)
    check("el HTML que se publicaria esta limpio",
          "mso" not in publicado and "MsoNormal" not in publicado)
    check("...y usa las clases de la intranet",
          'class="m-h"' in publicado and 'class="m-p"' in publicado)

    print("\n[4] Excel -> tabla de verdad")
    bl = pag.evaluate("(h) => pegarABloques(h)", EXCEL)
    check("sale UN bloque tabla", len(bl) == 1 and bl[0]["t"] == "tabla", str([b["t"] for b in bl]))
    t = bl[0]
    check("toma la primera fila como encabezado",
          [c["h"] for c in t["cols"]] == ["Sucursal", "Enero", "Total"], str([c["h"] for c in t["cols"]]))
    check("y el resto como filas", len(t["filas"]) == 2, "%d filas" % len(t["filas"]))
    check("detecta las columnas de numeros",
          [c["num"] for c in t["cols"]] == [False, True, True], str([c["num"] for c in t["cols"]]))
    check("los acentos llegan bien", t["filas"][1]["celdas"][0] == "Córdoba", t["filas"][1]["celdas"][0])
    check("nace ordenable", t["orden"] is True)

    print("\n[5] Pegar de verdad en el editor")
    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=20000)
    pag.evaluate("() => abrirDoc(0)")
    pag.wait_for_timeout(400)
    pag.evaluate("""() => {
        BLOQUES.length = 0;
        BLOQUES.push({t:'parrafo', html:'antes'});
        SEL = 0; renderCanvas(); selectBlock(0);
    }""")
    pag.wait_for_timeout(250)

    # simular el pegado real con un DataTransfer
    pag.evaluate("""(h) => {
        const dt = new DataTransfer();
        dt.setData('text/html', h);
        dt.setData('text/plain', 'texto plano de respaldo');
        const dest = document.querySelector('#gbDoc [contenteditable]');
        dest.focus();
        dest.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
    }""", WORD)
    pag.wait_for_timeout(400)
    tipos = pag.evaluate("() => BLOQUES.map(b => b.t)")
    check("se insertaron los bloques en el documento", len(tipos) > 1, str(tipos))
    check("y quedaron DESPUES del bloque donde estaba el cursor",
          tipos[0] == "parrafo" and "titulo" in tipos[1:], str(tipos))
    check("no entro el texto plano de respaldo",
          "texto plano de respaldo" not in pag.evaluate("() => JSON.stringify(BLOQUES)"))

    print("\n[5b] EL BUG QUE REPORTO EL USUARIO: documento vacio + Ctrl+V")
    pag.evaluate("""() => { BLOQUES.length = 0; SEL = null; renderCanvas(); renderInspector(); }""")
    pag.wait_for_timeout(300)
    check("el documento quedo sin ningun texto editable",
          pag.evaluate("() => !document.querySelector('#gbDoc [contenteditable]')"))
    # pegar con el foco en cualquier lado (como hace el usuario de verdad)
    pag.evaluate("""(h) => {
        const dt = new DataTransfer();
        dt.setData('text/html', h);
        dt.setData('text/plain', 'respaldo');
        document.body.dispatchEvent(new ClipboardEvent('paste',
            {clipboardData: dt, bubbles: true, cancelable: true}));
    }""", WORD)
    pag.wait_for_timeout(500)
    tipos = pag.evaluate("() => BLOQUES.map(b => b.t)")
    check("AHORA SI pega en un documento vacio", len(tipos) > 0, str(tipos))
    check("y arma los bloques correctos", "titulo" in tipos and "lista" in tipos, str(tipos))

    print("\n[5c] Hay un boton visible, no solo el atajo")
    check("existe el boton de pegar", pag.query_selector("#btnPegar") is not None)
    check("dice de donde se pega",
          "Word o Excel" in (pag.text_content("#btnPegar") or ""), pag.text_content("#btnPegar"))
    check("y aclara el atajo tambien", "Ctrl+V" in (pag.text_content("#btnPegar") or ""))
    check("esta en la paleta, a la vista",
          pag.evaluate("""() => { const b = document.querySelector('#btnPegar');
              return !!b.closest('.gb-pane[data-pane="agregar"]'); }"""))
    # el cartel del vacio solo existe si el documento ESTA vacio
    pag.evaluate("""() => { BLOQUES.length = 0; SEL = null; renderCanvas(); renderInspector(); }""")
    pag.wait_for_timeout(250)
    check("el cartel del documento vacio tambien lo dice",
          "Ctrl+V" in pag.evaluate("""() => {
              const s = getComputedStyle(document.querySelector('#gbDoc'), ':before').content;
              return s || ''; }"""))

    print("\n[6] Una frase suelta sigue entrando como texto")
    pag.evaluate("""() => {
        BLOQUES.length = 0; BLOQUES.push({t:'parrafo', html:''});
        SEL = 0; renderCanvas(); selectBlock(0);
    }""")
    pag.wait_for_timeout(250)
    n0 = pag.evaluate("() => BLOQUES.length")
    pag.evaluate("""(h) => {
        const dt = new DataTransfer();
        dt.setData('text/html', h);
        dt.setData('text/plain', 'una sola frase copiada');
        const dest = document.querySelector('#gbDoc [contenteditable]');
        dest.focus();
        dest.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
    }""", SUELTO)
    pag.wait_for_timeout(300)
    check("no crea bloques nuevos", pag.evaluate("() => BLOQUES.length") == n0,
          "%d" % pag.evaluate("() => BLOQUES.length"))

    check("cero errores de consola", not errores, "; ".join(errores[:3]))
    nav.close()

httpd.shutdown()
check("modulos.js NO se toco", hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest() == antes)

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
