# -*- coding: utf-8 -*-
"""«Cargar al módulo»: la publicación se copia adentro del módulo como bloques.

El pedido: escribir el aviso UNA vez y que ademas de salir en la cartelera
quede como contenido del modulo (titulo + cuerpo + las piezas), para no tener
que ir a editar el modulo a mano. Y que despues el selector encuentre ese
bloque, asi otra publicacion puede senalarlo.

Se prueba: se publica con el interruptor prendido, se comprueba que el modulo
destino sumo los bloques en orden, que su HTML se regenero con las anclas, que
el selector ahora ofrece ese bloque, y que el modulo NO perdio lo que tenia.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
RES = []
TITULO = "QA aviso cargado al modulo"
CUERPO = "Primera linea del aviso.\nSegunda linea, para ver que el salto sobreviva."


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:220]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:220]))


ESTADO = """(k) => {
  const m = (MODULOS||[]).find(x => x.key === k);
  const c = (m && m.content) || {};
  const bl = c.bloques || [];
  return {tipo: c.tipo || null, n: bl.length,
          ultimos: bl.slice(-4).map(b => ({t: b.t, tx: (b.texto || b.html || '').slice(0,44)})),
          anclas: ((c.html||'').match(/data-bi=/g) || []).length};
}"""

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

    destino = {"key": None, "antes": None}

    def existe_el_control():
        est = p.evaluate("""() => {
          const w = document.getElementById('coCargarWrap');
          return w ? {existe: true} : {existe: false};
        }""")
        if not est["existe"]:
            raise AssertionError("no está el control «Cargar al módulo»")
        return "el control existe"
    check("el compositor ofrece «Cargar al módulo»", existe_el_control)

    def publicar_cargando():
        p.click("#btnNuevaPub")
        p.wait_for_selector("#fondo.on", state="visible")
        p.wait_for_timeout(500)
        if p.eval_on_selector("#coCargarWrap", "e => e.hidden"):
            raise AssertionError("el control quedó oculto: ningún módulo admite carga")
        # se elige un módulo concreto y se prende el interruptor
        opciones = p.eval_on_selector_all("#coCargarMod option", "os => os.map(o => o.value)")
        if not opciones:
            raise AssertionError("el selector de módulos vino vacío")
        destino["key"] = "comunicacion_importante" if "comunicacion_importante" in opciones else opciones[0]
        destino["antes"] = p.evaluate(ESTADO, destino["key"])
        # el interruptor primero: el <select> arranca deshabilitado a propósito
        p.click("#coCargarBtn")
        p.wait_for_timeout(300)
        p.select_option("#coCargarMod", destino["key"])
        p.wait_for_timeout(200)
        if not p.eval_on_selector("#coCargar", "e => e.checked"):
            raise AssertionError("el interruptor no quedó prendido")
        p.fill("#coTitulo", TITULO)
        p.fill("#coTexto", CUERPO)
        p.click("#coPublicar")
        p.wait_for_function("!document.querySelector('#fondo').classList.contains('on')", timeout=25000)
        p.wait_for_timeout(1500)
        return "publicada con carga a %r" % destino["key"]
    check("publica con el interruptor prendido", publicar_cargando)

    def modulo_sumo_bloques():
        d = p.evaluate(ESTADO, destino["key"])
        a = destino["antes"]
        if d["n"] != a["n"] + 2:
            raise AssertionError("esperaba 2 bloques nuevos (título y cuerpo), pasó de %d a %d"
                                 % (a["n"], d["n"]))
        ts = [x["t"] for x in d["ultimos"][-2:]]
        if ts != ["titulo", "parrafo"]:
            raise AssertionError("el orden no es título→cuerpo: %s" % ts)
        if TITULO not in d["ultimos"][-2]["tx"]:
            raise AssertionError("el título no es el de la publicación: %r" % d["ultimos"][-2]["tx"])
        return "%d → %d bloques, en orden título+cuerpo" % (a["n"], d["n"])
    check("el módulo sumó el título y el cuerpo", modulo_sumo_bloques)

    def no_perdio_nada():
        d = p.evaluate(ESTADO, destino["key"])
        if d["n"] < destino["antes"]["n"]:
            raise AssertionError("el módulo PERDIÓ bloques")
        if d["anclas"] < d["n"] - 2:
            raise AssertionError("el html no se regeneró con las anclas: %d anclas para %d bloques"
                                 % (d["anclas"], d["n"]))
        return "conserva lo que tenía y regeneró el html (%d anclas)" % d["anclas"]
    check("no pisó lo que el módulo ya tenía", no_perdio_nada)

    def quedo_en_disco():
        # se relee del servidor: lo que importa es que se haya GUARDADO
        d = p.evaluate("""async (k) => {
          const r = await fetch('/api/modulos'); const j = await r.json();
          const m = (j.modulos||[]).find(x => x.key === k);
          const bl = ((m && m.content) || {}).bloques || [];
          return bl.slice(-2).map(b => b.t + ':' + (b.texto || b.html || '').slice(0,30));
        }""", destino["key"])
        if not d or "titulo" not in d[0]:
            raise AssertionError("en el servidor no quedaron los bloques: %s" % d)
        return " | ".join(d)
    check("quedó guardado en el servidor", quedo_en_disco)

    def selector_lo_encuentra():
        # el bloque nuevo tiene que poder señalarse desde otra publicación
        p.click("#btnNuevaPub")
        p.wait_for_selector("#fondo.on", state="visible")
        p.click('.co-ad[data-ad="ref"]')
        p.wait_for_selector("#coPick", state="visible")
        p.wait_for_timeout(600)
        hay = p.evaluate("""(t) => {
          const g = [...document.querySelectorAll('#coPick .co-g')];
          return g.some(x => (x.dataset.b || '').includes(t.toLowerCase()));
        }""", TITULO)
        p.keyboard.press("Escape"); p.wait_for_timeout(300)
        p.keyboard.press("Escape"); p.wait_for_timeout(400)
        if p.eval_on_selector("#confirmModal", "e => e.classList.contains('on')"):
            p.click("#confirmYes"); p.wait_for_timeout(400)
        if not hay:
            raise AssertionError("el selector no ofrece el contenido recién cargado")
        return "el bloque nuevo aparece en el selector"
    check("después se puede señalar ese bloque", selector_lo_encuentra)

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
            return "la publicación ya no estaba"
        el.query_selector(".mp-mas").click()
        p.wait_for_selector("#mpMenu", state="visible")
        p.click('#mpMenu [data-a="borrar"]')
        p.wait_for_selector("#confirmModal.on", state="visible")
        p.click("#confirmYes")
        p.wait_for_timeout(1200)
        # y los bloques que se cargaron al módulo
        p.evaluate("""async (o) => {
          const m = (MODULOS||[]).find(x => x.key === o.k);
          if (m && m.content && Array.isArray(m.content.bloques))
            m.content.bloques.length = o.n;
          if (typeof persistModulos === 'function') await persistModulos(false);
        }""", {"k": destino["key"], "n": destino["antes"]["n"]})
        p.wait_for_timeout(1200)
        d = p.evaluate(ESTADO, destino["key"])
        return "borrada; módulo de vuelta en %d bloques" % d["n"]
    check("limpieza", limpiar)

    print("\nerrores de consola:", errs or "ninguno")
    b.close()

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
