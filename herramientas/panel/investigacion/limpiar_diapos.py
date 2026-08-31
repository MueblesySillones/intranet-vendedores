# -*- coding: utf-8 -*-
"""Saca los cortes de diapositiva HUERFANOS de JULIO 2026 y JUNIO 2026 (quedan
como pagina, decision del usuario). Hoy esos cortes generan <div class="db"></div>
vacios en la intranet.

Regenera el html con la PROPIA funcion bloquesHTML() del panel (cargada en un
navegador real), para que salga byte a byte igual a lo que produciria el panel.

    python limpiar_diapos.py            -> en seco, no toca nada
    python limpiar_diapos.py --aplicar  -> escribe (con backup previo)
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
OBJETIVO = {"JULIO 2026", "JUNIO 2026"}
PORT = 8194
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")

print("=" * 70)
print("LIMPIAR CORTES HUERFANOS  (%s)" % ("APLICANDO" if APLICAR else "EN SECO"))
print("=" * 70)

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page()
    errores = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")

    res = pag.evaluate("""(objetivo) => {
      const mods = JSON.parse(JSON.stringify(MODULOS));
      const informe = [];
      mods.forEach(m => {
        const c = m.content;
        if (!c || c.tipo !== 'coleccion') return;
        (c.docs || []).forEach(d => {
          if (!objetivo.includes((d.titulo || '').toUpperCase())) return;
          const antes = (d.bloques || []).length;
          const cortes = (d.bloques || []).filter(b => b.t === 'diapo').length;
          const limpios = (d.bloques || []).filter(b => b.t !== 'diapo');
          const htmlAntes = d.html || '';
          const htmlNuevo = bloquesHTML(limpios, false);
          informe.push({
            modulo: m.key, titulo: d.titulo, antes, cortes, despues: limpios.length,
            presentacion: !!d.presentacion,
            vaciosAntes: (htmlAntes.match(/<div class="db"><\\/div>/g) || []).length,
            vaciosDespues: (htmlNuevo.match(/<div class="db"><\\/div>/g) || []).length,
            largoAntes: htmlAntes.length, largoDespues: htmlNuevo.length,
            // control: sacando los huecos vacios, el resto del html tiene que ser IDENTICO
            iguales: htmlAntes.split('<div class="db"></div>').join('') ===
                     htmlNuevo.split('<div class="db"></div>').join(''),
          });
          d.bloques = limpios;
          d.html = htmlNuevo;
        });
      });
      return { informe, mods };
    }""", list(OBJETIVO))

    print()
    todo_ok = True
    for r in res["informe"]:
        print("  %s / %s" % (r["modulo"], r["titulo"]))
        print("     bloques      %d -> %d   (saca %d cortes)" % (r["antes"], r["despues"], r["cortes"]))
        print("     huecos vacios %d -> %d" % (r["vaciosAntes"], r["vaciosDespues"]))
        print("     html          %d -> %d bytes" % (r["largoAntes"], r["largoDespues"]))
        print("     el resto del contenido queda intacto: %s" % ("SI" if r["iguales"] else "NO !!"))
        if not r["iguales"] or r["vaciosDespues"] or r["presentacion"]:
            todo_ok = False
        print()

    check_docs = len(res["informe"]) == 2
    if not check_docs:
        print("  !! esperaba 2 documentos y encontre %d -> no toco nada" % len(res["informe"]))
        todo_ok = False
    if errores:
        print("  !! errores de JS: %s" % errores[:2])
        todo_ok = False

    # que Marzo-Mayo NO se haya tocado
    intactos = pag.evaluate("""(mods) => {
      const orig = MODULOS.find(m => m.key === 'reporte').content.docs;
      const nuevo = mods.find(m => m.key === 'reporte').content.docs;
      const mm = orig.find(d => d.titulo.includes('Marzo'));
      const mn = nuevo.find(d => d.titulo.includes('Marzo'));
      return JSON.stringify(mm) === JSON.stringify(mn);
    }""", res["mods"])
    print("  Marzo-Mayo 2026 sin tocar: %s" % ("SI" if intactos else "NO !!"))
    if not intactos:
        todo_ok = False

    if not todo_ok:
        print("\n  Algo no cuadra -> NO se escribe nada.")
        nav.close(); httpd.shutdown(); sys.exit(1)

    if not APLICAR:
        print("\n  En seco. Corre con --aplicar para escribirlo.")
        nav.close(); httpd.shutdown(); sys.exit(0)

    copia = MODULOS_JS + ".backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(MODULOS_JS, copia)
    print("\n  backup: %s" % os.path.basename(copia))

    guardado = pag.evaluate("""async (mods) => {
      const r = await fetch('/api/modulos', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({modulos: mods})
      });
      const j = await r.json();
      return {ok: r.ok, error: j.error || ''};
    }""", res["mods"])
    print("  guardado: %s %s" % (guardado["ok"], guardado["error"]))
    nav.close()

httpd.shutdown()

if APLICAR:
    s = open(MODULOS_JS, encoding="utf-8").read()
    datos = json.loads(s[s.index('['):s.rindex(']') + 1])
    docs = next(m for m in datos if m.get("key") == "reporte")["content"]["docs"]
    print("\n  VERIFICACION en disco:")
    for d in docs:
        bl = d.get("bloques") or []
        print("     %-18s bloques=%-3d cortes=%d  huecos=%d  presentacion=%s"
              % (d.get("titulo"), len(bl), sum(1 for b in bl if b.get("t") == "diapo"),
                 (d.get("html") or "").count('<div class="db"></div>'), d.get("presentacion")))
print("=" * 70)
