# -*- coding: utf-8 -*-
"""Le devuelve las diapositivas a "Marzo-Mayo 2026": tiene sus 88 bloques y sus
14 cortes intactos, pero perdio el flag `presentacion` y su html se regenero en
modo Pagina (0 dk-slide). Se regenera con la PROPIA bloquesHTML() del panel.

Verificacion fuerte: el html resultante se compara contra el que esta PUBLICADO
(git HEAD). Si coincide, el rescate devuelve exactamente lo que ve la gente hoy.

    python rescatar_marzo_mayo.py            -> en seco
    python rescatar_marzo_mayo.py --aplicar  -> escribe (con backup)
"""
import os
import sys
import json
import shutil
import difflib
import datetime
import subprocess
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

APLICAR = "--aplicar" in sys.argv
PORT = 8193
RAIZ = os.path.dirname(ps.INTRANET)
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")

print("=" * 70)
print("RESCATE DE 'Marzo-Mayo 2026'  (%s)" % ("APLICANDO" if APLICAR else "EN SECO"))
print("=" * 70)

# --- el html tal cual esta publicado hoy ---
crudo = subprocess.run(["git", "show", "HEAD:intranet/modulos.js"], cwd=RAIZ,
                       capture_output=True, text=True, encoding="utf-8").stdout
pub = json.loads(crudo[crudo.index('['):crudo.rindex(']') + 1])
doc_pub = next(d for m in pub if m.get("key") == "reporte"
               for d in m["content"]["docs"] if "Marzo" in d["titulo"])
html_pub = doc_pub.get("html") or ""
print("\npublicado: presentacion=%s  dk-slide=%d  html=%d bytes"
      % (doc_pub.get("presentacion"), html_pub.count("dk-slide"), len(html_pub)))

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page()
    errores = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")

    res = pag.evaluate("""() => {
      const mods = JSON.parse(JSON.stringify(MODULOS));
      const rep = mods.find(m => m.key === 'reporte');
      const d = rep.content.docs.find(x => x.titulo.includes('Marzo'));
      const bloques = d.bloques || [];
      d.presentacion = true;
      d.html = bloquesHTML(bloques, true);
      return {
        mods,
        titulo: d.titulo,
        bloques: bloques.length,
        cortes: bloques.filter(b => b.t === 'diapo').length,
        slidesContados: contarSlides(bloques),
        slidesEnHtml: (d.html.match(/<section class="dk-slide"/g) || []).length,
        html: d.html,
        // los OTROS documentos no se tocan
        otros: rep.content.docs.filter(x => !x.titulo.includes('Marzo'))
                  .map(x => ({t: x.titulo, pres: !!x.presentacion, b: (x.bloques||[]).length})),
      };
    }""")

    print("\nregenerado: %s" % res["titulo"])
    print("   bloques=%d  cortes=%d" % (res["bloques"], res["cortes"]))
    print("   diapositivas: %d contadas / %d en el html" % (res["slidesContados"], res["slidesEnHtml"]))
    print("   html=%d bytes" % len(res["html"]))
    print("   otros documentos: %s" % res["otros"])

    igual = res["html"] == html_pub
    print("\n   ¿identico al publicado?  %s" % ("SI" if igual else "NO"))
    ok = True
    if not igual:
        print("   diferencias (primeras lineas):")
        for l in list(difflib.unified_diff(html_pub.split("><"), res["html"].split("><"),
                                           "publicado", "regenerado", n=0))[:14]:
            print("     " + l[:150])
        # sigue siendo aceptable si solo AGREGA diapositivas que antes se perdian
        if res["slidesEnHtml"] < html_pub.count("dk-slide"):
            print("   !! genera MENOS diapositivas que el sitio publicado")
            ok = False

    if res["slidesEnHtml"] < 14:
        print("   !! esperaba al menos 14 diapositivas")
        ok = False
    if errores:
        print("   !! errores de JS: %s" % errores[:2])
        ok = False

    if not ok:
        print("\n  Algo no cuadra -> NO se escribe nada.")
        nav.close(); httpd.shutdown(); sys.exit(1)

    if not APLICAR:
        print("\n  En seco. Corre con --aplicar para escribirlo.")
        nav.close(); httpd.shutdown(); sys.exit(0)

    copia = os.path.join(AQUI, "modulos.js.antes-rescate-" +
                         datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(MODULOS_JS, copia)
    print("\n  backup: %s" % os.path.basename(copia))

    guardado = pag.evaluate("""async (mods) => {
      const r = await fetch('/api/modulos', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({modulos: mods})
      });
      return {ok: r.ok, ...(await r.json())};
    }""", res["mods"])
    print("  guardado: %s %s" % (guardado["ok"], guardado.get("error", "")))
    nav.close()

httpd.shutdown()

s = open(MODULOS_JS, encoding="utf-8").read()
docs = next(m for m in json.loads(s[s.index('['):s.rindex(']') + 1])
            if m.get("key") == "reporte")["content"]["docs"]
print("\n  VERIFICACION en disco:")
for d in docs:
    h = d.get("html") or ""
    print("     %-18s bloques=%-3d presentacion=%-5s dk-slide=%d"
          % (d.get("titulo"), len(d.get("bloques") or []), d.get("presentacion"),
             h.count('<section class="dk-slide"')))
print("=" * 70)
