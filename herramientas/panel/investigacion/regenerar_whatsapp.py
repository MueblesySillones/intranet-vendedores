# -*- coding: utf-8 -*-
"""El html del modulo se genera al GUARDAR y queda congelado en modulos.js, asi
que el arreglo del carrusel no llega al contenido ya guardado. Esto lo regenera
con la PROPIA bloquesHTML() del panel (lo mismo que hace apretar Guardar), sin
tocar ni un bloque.

    python regenerar_whatsapp.py            -> en seco
    python regenerar_whatsapp.py --aplicar  -> escribe (con backup)
"""
import os
import sys
import json
import shutil
import datetime
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

APLICAR = "--aplicar" in sys.argv
PORT = 8174
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")

print("=" * 70)
print("REGENERAR EL HTML DE WHATSAPP  (%s)" % ("APLICANDO" if APLICAR else "EN SECO"))
print("=" * 70)

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page()
    errores = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)

    r = pag.evaluate("""() => {
      const mods = JSON.parse(JSON.stringify(MODULOS));
      const m = mods.find(x => x.key === 'whatsapp');
      if (!m || !m.content || m.content.tipo !== 'bloques') return {error: 'no es un modulo de bloques'};
      const bl = m.content.bloques || [];
      const viejo = m.content.html || '';
      const nuevo = bloquesHTML(bl, !!m.content.presentacion);
      m.content.html = nuevo;
      const cuenta = (s, re) => (s.match(re) || []).length;
      return {
        mods,
        bloques: bl.length,
        // los bloques NO se tocan: solo se vuelve a dibujar el html
        antes: {largo: viejo.length, burbujas: cuenta(viejo, /class="wt-msg"/g),
                tarjetas: cuenta(viejo, /class="wt-card"/g)},
        despues: {largo: nuevo.length, burbujas: cuenta(nuevo, /class="wt-msg"/g),
                  tarjetas: cuenta(nuevo, /class="wt-card"/g)},
        // control: sacando lo del carrusel, el resto tiene que ser identico
        restoIgual: viejo.replace(/<div class="wt">[\\s\\S]*?<div class="wt-hint">[^<]*<\\/div><\\/div>/g, '')
                 === nuevo.replace(/<div class="wt">[\\s\\S]*?<div class="wt-hint">[^<]*<\\/div><\\/div>/g, ''),
      };
    }""")

    if r.get("error"):
        print("  " + r["error"]); nav.close(); httpd.shutdown(); sys.exit(1)

    print("\n  bloques del modulo: %d  (no se toca ninguno)" % r["bloques"])
    print("  html    : %d -> %d bytes" % (r["antes"]["largo"], r["despues"]["largo"]))
    print("  burbujas: %d -> %d   (la vacia se va)" % (r["antes"]["burbujas"], r["despues"]["burbujas"]))
    print("  tarjetas: %d -> %d   (la que no tiene foto no se publica)"
          % (r["antes"]["tarjetas"], r["despues"]["tarjetas"]))
    print("  el resto del documento queda intacto: %s" % ("SI" if r["restoIgual"] else "NO !!"))

    ok = r["restoIgual"] and not errores and r["bloques"] > 0
    if errores:
        print("  !! errores de JS: %s" % errores[:2])
    if not ok:
        print("\n  Algo no cuadra -> NO se escribe nada.")
        nav.close(); httpd.shutdown(); sys.exit(1)

    if not APLICAR:
        print("\n  En seco. Corre con --aplicar para escribirlo.")
        nav.close(); httpd.shutdown(); sys.exit(0)

    copia = os.path.join(AQUI, "modulos.js.antes-regenerar-" +
                         datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(MODULOS_JS, copia)
    print("\n  backup: %s" % os.path.basename(copia))

    g = pag.evaluate("""async (mods) => {
      const r = await fetch('/api/modulos', {method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({modulos: mods})});
      return {ok: r.ok, ...(await r.json())};
    }""", r["mods"])
    print("  guardado: %s %s" % (g["ok"], g.get("error", "")))
    nav.close()

httpd.shutdown()
if APLICAR:
    s = open(MODULOS_JS, encoding="utf-8").read()
    mods = json.loads(s[s.index('['):s.rindex(']') + 1])
    w = [x for x in mods if x.get("key") == "whatsapp"][0]
    h = (w.get("content") or {}).get("html", "")
    print("\n  EN DISCO: %d bloques · %d burbujas · %d tarjetas"
          % (len(w["content"]["bloques"]), h.count('class="wt-msg"'), h.count('class="wt-card"')))
print("=" * 70)
