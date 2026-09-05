# -*- coding: utf-8 -*-
"""La biblioteca de reportes de una planilla.

El pedido: entrar a la planilla conectada y poder CREAR reportes —el de
agosto, el de la semana pasada— que queden listados ahí, para ir armando
varios de la misma planilla.

Se prueba de punta a punta: el botón existe, el formulario propone el mes
pasado, se crea, aparece en la lista, sobrevive a recargar la página, abre el
reporte recortado a SU período, y se puede quitar.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
RES = []
NOMBRE = "QA agosto 2026"


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:220]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:220]))


def abrir_reporte(p):
    p.goto(BASE + "/", wait_until="domcontentloaded")
    p.wait_for_selector("#muroLista .pub", timeout=25000)
    p.click('[data-sec="datos"]')
    p.wait_for_selector("#viewDatos", state="visible")
    p.wait_for_timeout(2000)
    fila = p.query_selector("#datosRaiz .dt-reps > *")
    if fila is None:
        raise AssertionError("no hay ninguna planilla conectada en el sandbox")
    fila.click()
    p.wait_for_selector("#dtInformes", timeout=180000)
    p.wait_for_timeout(600)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000})
    ctx.route("**/api/publicar", lambda r: r.fulfill(
        status=200, content_type="application/json", body='{"ok": true}'))
    errs = []
    p = ctx.new_page()
    p.set_default_timeout(180000)
    p.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:180]))
    p.on("dialog", lambda d: d.accept())        # el confirm al quitar

    check("la planilla muestra la sección Reportes", lambda: (
        abrir_reporte(p),
        p.wait_for_selector("#dtInfNuevo", state="visible"),
        p.text_content("#dtInformes .dt-inf-h h3").strip())[-1])

    def form_propone():
        p.click("#dtInfNuevo")
        p.wait_for_selector("#dtInfOk", state="visible")
        v = p.evaluate("""() => ({
          nombre: document.getElementById('dtInfN').value,
          desde: document.getElementById('dtInfD').value,
          hasta: document.getElementById('dtInfH').value
        })""")
        if not v["desde"] or not v["hasta"]:
            raise AssertionError("no propuso un período: %s" % v)
        if v["desde"][8:] != "01":
            raise AssertionError("el desde no arranca el día 1: %s" % v["desde"])
        if v["desde"][:7] != v["hasta"][:7]:
            raise AssertionError("propuso un rango que cruza meses: %s" % v)
        return "propone %r (%s → %s)" % (v["nombre"], v["desde"], v["hasta"])
    check("el formulario propone el mes pasado entero", form_propone)

    def crear():
        p.fill("#dtInfN", NOMBRE)
        p.fill("#dtInfD", "2026-08-01")
        p.fill("#dtInfH", "2026-08-31")
        p.click("#dtInfOk")
        p.wait_for_timeout(1200)
        txt = p.text_content("#dtInformes") or ""
        if NOMBRE not in txt:
            raise AssertionError("no aparece en la lista: %r" % txt[:120])
        return "creado y listado"
    check("se crea y aparece en la lista", crear)

    def periodo_legible():
        fila = p.query_selector('#dtInformes .dt-inf-i')
        t = (fila.query_selector(".dt-inf-p").text_content() or "").strip()
        if "agosto" not in t.lower():
            raise AssertionError("el período no se lee: %r" % t)
        return "dice %r" % t
    check("el período se lee en castellano", periodo_legible)

    def sobrevive():
        abrir_reporte(p)
        txt = p.text_content("#dtInformes") or ""
        if NOMBRE not in txt:
            raise AssertionError("se perdió al volver a entrar")
        n = len(p.query_selector_all("#dtInformes .dt-inf-i"))
        return "%d reporte(s) guardados" % n
    check("queda guardado al volver a entrar", sobrevive)

    def abre_recortado():
        # se pide el deck del informe y se comprueba que el período del
        # encabezado sea el suyo, no el de toda la planilla
        iid = p.evaluate("""() => {
          const f = document.querySelector('#dtInformes .dt-inf-i');
          return f ? f.getAttribute('data-inf') : '';
        }""")
        rid = p.evaluate("""async () => {
          const r = await fetch('/api/datos/estado'); const j = await r.json();
          return (j.reportes || [])[0].id;
        }""")
        p2 = ctx.new_page()
        p2.set_default_timeout(240000)
        p2.goto(BASE + "/api/datos/deck?id=" + rid + "&informe=" + iid,
                wait_until="load")
        p2.wait_for_timeout(2500)
        t = p2.evaluate("() => (document.body.innerText || '').slice(0, 400)")
        p2.close()
        if "agosto" not in t.lower():
            raise AssertionError("el reporte no dice su período: %r" % t[:140])
        return "el reporte abre recortado a agosto"
    check("abre el reporte de SU período", abre_recortado)

    def quitar():
        p.click("#dtInformes .dt-inf-x")
        p.wait_for_timeout(1500)
        txt = p.text_content("#dtInformes") or ""
        if NOMBRE in txt:
            raise AssertionError("sigue en la lista")
        return "quitado"
    check("se puede quitar", quitar)

    print("\nerrores de consola:", errs or "ninguno")
    b.close()

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
