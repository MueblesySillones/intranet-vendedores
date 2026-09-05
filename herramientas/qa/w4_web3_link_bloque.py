# -*- coding: utf-8 -*-
"""El link de una publicacion tiene que llevar AL BLOQUE senalado.

Antes: se elegia "Material descargable > Promociones vigentes" y el vendedor
caia arriba de todo el modulo, a buscar la galeria a mano. El bloque `ref`
guardaba el nombre del bloque pero el link salia como #modulo a secas.

Se prueba de punta a punta: se arma una publicacion senalando un bloque
puntual, se guarda, y se comprueba que el HTML que le llega al vendedor lleve
#modulo/b<n> y que al abrir ese link la intranet scrollee hasta ese bloque.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "salida", "web3", "link-bloque")
os.makedirs(SHOTS, exist_ok=True)
RES = []
TITULO = "QA link al bloque"


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:220]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:220]))


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.route("**/api/publicar", lambda r: r.fulfill(
        status=200, content_type="application/json", body='{"ok": true}'))
    errs = []
    p = ctx.new_page()
    p.set_default_timeout(15000)
    p.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:180]))
    p.goto(BASE + "/", wait_until="domcontentloaded")
    p.wait_for_selector("#muroLista .pub", timeout=20000)
    p.wait_for_timeout(1200)

    # --- se arma la publicacion senalando un bloque puntual ---
    def armar():
        p.click("#btnNuevaPub")
        p.wait_for_selector("#fondo.on", state="visible")
        p.fill("#coTitulo", TITULO)
        p.fill("#coTexto", "Prueba: esto tiene que llevar al bloque, no al modulo.")
        # los botones de adjuntar estan a la vista; #coClip es un puente oculto
        p.click('.co-ad[data-ad="ref"]')
        p.wait_for_selector("#coPick", state="visible")
        p.wait_for_timeout(500)
        # se abre el primer modulo de la lista y se elige un BLOQUE (no "todo")
        filas = p.query_selector_all("#coPick .co-m")
        if not filas:
            raise AssertionError("el selector no listo ningun modulo")
        filas[0].click()
        p.wait_for_timeout(400)
        items = p.query_selector_all("#coPick .co-g:has(.co-bl:not([hidden])) .co-b:not(.co-b-todo)")
        elegido = None
        for it in items:
            tx = (it.text_content() or "").strip()
            if tx:
                elegido = it
                break
        if elegido is None:
            raise AssertionError("no encontre un bloque puntual para elegir")
        nombre = (elegido.text_content() or "").strip()[:40]
        elegido.click()
        p.wait_for_timeout(300)
        p.click("#coPick .co-pie-ok")
        p.wait_for_timeout(500)
        return nombre
    nombre_bloque = None
    def paso1():
        global nombre_bloque
        nombre_bloque = armar()
        # COMP vive adentro del IIFE de muro.js, no es global: se mira lo que
        # quedo en la lista de adjuntos del compositor, que es lo que ve la gente
        tx = (p.text_content("#coAdjuntos") or "").strip()
        if not tx:
            raise AssertionError("no se agrego ningun adjunto")
        return "adjunto: %r" % " ".join(tx.split())[:70]
    check("el selector guarda QUE bloque se eligio", paso1)

    def publicar():
        p.click("#coPublicar")
        p.wait_for_function("!document.querySelector('#fondo').classList.contains('on')", timeout=20000)
        p.wait_for_timeout(800)
        return "publicada"
    check("se publica", publicar)

    # --- el html que le llega al vendedor ---
    def revisar_html():
        h = p.evaluate("""(t) => {
          const m = (MODULOS||[]).find(x => x.content && x.content.tipo === 'cartelera');
          const d = ((m && m.content.docs) || []).find(x => x.titulo === t);
          return d ? d.html : null;
        }""", TITULO)
        if not h:
            raise AssertionError("no encuentro la publicacion guardada")
        import re
        m = re.search(r'<a class="[^"]*m-ref[^"]*" href="#([^"]+)"', h)
        if not m:
            raise AssertionError("el html no trae el link al modulo")
        destino = m.group(1)
        if "/b" not in destino:
            raise AssertionError("el link sigue apuntando al modulo entero: #%s" % destino)
        return "#" + destino
    check("el link apunta al bloque", revisar_html)

    # --- el vendedor: el link lo lleva hasta ese bloque ---
    def vendedor():
        destino = p.evaluate("""(t) => {
          const m = (MODULOS||[]).find(x => x.content && x.content.tipo === 'cartelera');
          const d = ((m && m.content.docs) || []).find(x => x.titulo === t);
          const mm = /href="#([^"]+)"/.exec((d && d.html) || '');
          return mm ? mm[1] : '';
        }""", TITULO)
        p.goto(BASE + "/intranet/#" + destino, wait_until="load")
        # el resaltado dura 2,6 s: mirar despues de eso es mirar tarde
        p.wait_for_timeout(1000)
        est = p.evaluate("""() => {
          const el = document.querySelector('#secBody .db.apuntada') ||
                     document.querySelector('#secBody .db[data-bi]');
          if (!el) return {hay: false};
          const r = el.getBoundingClientRect();
          return {hay: true, bi: el.dataset.bi,
                  marcado: el.classList.contains('apuntada'),
                  enPantalla: r.top > -50 && r.top < window.innerHeight,
                  scroll: Math.round(window.scrollY || document.documentElement.scrollTop)};
        }""")
        if not est["hay"]:
            raise AssertionError("la intranet no emitio anclas de bloque")
        if not est["marcado"]:
            raise AssertionError("llego al modulo pero no marco el bloque: %s" % est)
        if not est["enPantalla"]:
            raise AssertionError("marco el bloque pero no lo dejo a la vista: %s" % est)
        p.screenshot(path=os.path.join(SHOTS, "vendedor-en-el-bloque.png"))
        return "bloque %s a la vista (scroll %s px)" % (est["bi"], est["scroll"])
    check("el vendedor cae en el bloque, marcado", vendedor)

    # --- limpieza: se borra la publicacion de prueba ---
    def limpiar():
        p.goto(BASE + "/", wait_until="domcontentloaded")
        p.wait_for_selector("#muroLista .pub", timeout=20000)
        p.wait_for_timeout(1000)
        el = None
        for c in p.query_selector_all("#muroLista .pub"):
            h = c.query_selector("h3")
            if h and TITULO in h.text_content():
                el = c; break
        if el is None:
            return "ya no estaba"
        el.query_selector(".mp-mas").click()
        p.wait_for_selector("#mpMenu", state="visible")
        p.click('#mpMenu [data-a="borrar"]')
        p.wait_for_selector("#confirmModal.on", state="visible")
        p.click("#confirmYes")
        p.wait_for_timeout(1200)
        return "borrada"
    check("limpieza", limpiar)

    print("\nerrores de consola:", errs or "ninguno")
    b.close()

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
