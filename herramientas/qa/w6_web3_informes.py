# -*- coding: utf-8 -*-
"""La biblioteca de reportes de una planilla.

El pedido: entrar a la planilla conectada, apretar «Crear reporte» y que
aparezca un FORMULARIO con preguntas —cómo se llama, de qué período, qué
querés medir—. Al terminar queda una TARJETA en la biblioteca, y adentro de
la tarjeta los tres botones: ver el reporte, bajarlo en PDF, bajarlo en Word.

Lo que más importa acá y por qué:
  · Los reportes ya creados NO se tocan cuando se relee la planilla.
  · El Word que baja es el del DISEÑO (una lámina por hoja, apaisado), no el
    documento de oficina de reporte.py.
  · Lo que se eligió medir manda: si se pidió una sola cosa, el reporte trae
    esa y no las nueve.
"""
import io
import json
import os
import sys
import zipfile

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
        # sin planilla no hay nada que medir, y eso no es una falla del panel
        print("SIN PLANILLA CONECTADA en el sandbox: esta suite necesita una.")
        print("\n0/0 PASS (salteada)")
        b.close()
        sys.exit(0)
    fila.click()
    p.wait_for_selector("#dtInformes", timeout=180000)
    p.wait_for_timeout(600)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000},
                        accept_downloads=True)
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

    def form_pregunta():
        """El formulario pregunta, no pide datos sueltos."""
        p.click("#dtInfNuevo")
        p.wait_for_selector("#dtInfOk", state="visible")
        preguntas = p.eval_on_selector_all(
            "#dtInfForm .dt-inf-q > b", "ns => ns.map(n => n.textContent.trim())")
        if len(preguntas) < 3:
            raise AssertionError("son %d preguntas: %s" % (len(preguntas), preguntas))
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
        return "%s | propone %r" % (" / ".join(preguntas), v["nombre"])
    check("el formulario hace las tres preguntas", form_pregunta)

    def opciones_de_medir():
        ops = p.eval_on_selector_all(
            "#dtInfForm .dt-inf-o b", "ns => ns.map(n => n.textContent.trim())")
        if len(ops) < 5:
            raise AssertionError("solo %d cosas para medir: %s" % (len(ops), ops))
        falta = [x for x in ("El embudo", "Por sucursal", "Por vendedor")
                 if x not in ops]
        if falta:
            raise AssertionError("no se puede elegir: %s" % falta)
        marcadas = p.eval_on_selector_all(
            "#dtInfForm .dt-inf-o input",
            "ns => ns.filter(n => n.checked).length")
        if marcadas != len(ops):
            raise AssertionError("no vienen todas marcadas: %d de %d"
                                 % (marcadas, len(ops)))
        return "%d cosas para medir, todas marcadas" % len(ops)
    check("se puede elegir qué medir", opciones_de_medir)

    def atajo_de_periodo():
        p.click('#dtInfForm .dt-at[data-per="semana"]')
        v = p.evaluate("""() => [document.getElementById('dtInfD').value,
                                 document.getElementById('dtInfH').value]""")
        if v[0] == v[1] or not v[0]:
            raise AssertionError("el atajo no puso 7 días: %s" % v)
        p.click('#dtInfForm .dt-at[data-per="mes-pasado"]')
        return "los atajos de período cambian las fechas"
    check("los atajos de período funcionan", atajo_de_periodo)

    def crear():
        p.fill("#dtInfN", NOMBRE)
        p.fill("#dtInfD", "2026-08-01")
        p.fill("#dtInfH", "2026-08-31")
        # se destilda "Seguimiento enviado": el reporte tiene que respetarlo
        p.evaluate("""() => {
          const os = [...document.querySelectorAll('#dtInfForm .dt-inf-o')];
          const t = os.find(o => /Seguimiento enviado/.test(o.textContent));
          if (t) t.querySelector('input').checked = false;
        }""")
        p.click("#dtInfOk")
        p.wait_for_selector("#dtInformes .dt-inf-c", timeout=30000)
        txt = p.text_content("#dtInformes") or ""
        if NOMBRE not in txt:
            raise AssertionError("no aparece en la biblioteca: %r" % txt[:120])
        return "creado y listado como tarjeta"
    check("se crea y aparece como tarjeta", crear)

    def tarjeta_completa():
        c = p.query_selector("#dtInformes .dt-inf-c")
        per = (c.query_selector(".dt-inf-p").text_content() or "").strip()
        mide = (c.query_selector(".dt-inf-m").text_content() or "").strip()
        botones = [(x.text_content() or "").strip()
                   for x in c.query_selector_all(".dt-inf-b .btn")]
        if "agosto" not in per.lower():
            raise AssertionError("el período no se lee: %r" % per)
        for b in ("Ver reporte", "Descargar PDF", "Descargar Word"):
            if b not in botones:
                raise AssertionError("falta el botón %r: %s" % (b, botones))
        if "El embudo" not in mide:
            raise AssertionError("no dice qué mide: %r" % mide)
        if "Seguimiento enviado" in mide:
            raise AssertionError("muestra algo que se destildó: %r" % mide)
        return "%s · %s · %s" % (per, mide[:40], " / ".join(botones))
    check("la tarjeta dice período, qué mide y sus tres botones", tarjeta_completa)

    def sobrevive():
        abrir_reporte(p)
        txt = p.text_content("#dtInformes") or ""
        if NOMBRE not in txt:
            raise AssertionError("se perdió al volver a entrar")
        n = len(p.query_selector_all("#dtInformes .dt-inf-c"))
        return "%d reporte(s) guardados tras releer la planilla" % n
    check("releer la planilla no toca los reportes creados", sobrevive)

    IDS = {}

    def ver_reporte():
        IDS["inf"] = p.get_attribute("#dtInformes .dt-inf-c", "data-inf")
        IDS["rep"] = p.evaluate("""async () => {
          const r = await fetch('/api/datos/estado'); const j = await r.json();
          return (j.reportes || [])[0].id;
        }""")
        with ctx.expect_page() as info:
            p.click("#dtInformes [data-ver]")
        p2 = info.value
        p2.set_default_timeout(240000)
        p2.wait_for_load_state("load")
        p2.wait_for_timeout(2500)
        t = p2.evaluate("() => (document.body.innerText || '').slice(0, 600)")
        laminas = p2.eval_on_selector_all(".slide", "ns => ns.length") or 0
        p2.close()
        if "agosto" not in t.lower():
            raise AssertionError("el reporte no dice su período: %r" % t[:140])
        if "template" in t.lower():
            raise AssertionError("trae la lámina que se destildó")
        return "abre recortado a agosto, %d láminas" % laminas
    check("«Ver reporte» abre el deck de SU período", ver_reporte)

    def word_disenado():
        with p.expect_download() as d:
            p.click("#dtInformes [data-doc]")
        des = d.value
        ruta = os.path.join(os.environ.get("TEMP", "."), "qa_deck.docx")
        des.save_as(ruta)
        if not des.suggested_filename.endswith(".docx"):
            raise AssertionError("no bajó un .docx: %s" % des.suggested_filename)
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        if 'w:orient="landscape"' not in xml:
            raise AssertionError("el Word no salió apaisado")
        if xml.count('w:type="page"') < 2:
            raise AssertionError("no hay una lámina por hoja")
        if NOMBRE not in xml:
            raise AssertionError("el Word no lleva el nombre del reporte")
        if "templates" in xml.lower():
            raise AssertionError("el Word trae la lámina que se destildó")
        os.remove(ruta)
        return "%s · %d hojas · apaisado" % (des.suggested_filename,
                                             xml.count('w:type="page"') + 1)
    check("«Descargar Word» baja el diseño, no el tablero", word_disenado)

    def pdf_imprime():
        """El PDF es el mismo deck con el diálogo de impresión abierto."""
        p3 = ctx.new_page()
        p3.set_default_timeout(240000)
        p3.goto("%s/api/datos/deck?id=%s&informe=%s&imprimir=1"
                % (BASE, IDS["rep"], IDS["inf"]), wait_until="domcontentloaded")
        tiene = p3.evaluate(
            "() => [...document.scripts].some(s => /window.print/.test(s.text))")
        p3.close()
        if not tiene:
            raise AssertionError("la página del PDF no dispara la impresión")
        return "el mismo deck, imprimiéndose"
    check("«Descargar PDF» sale del mismo deck", pdf_imprime)

    def dos_reportes():
        """Dos reportes distintos de la MISMA planilla, sin pisarse."""
        p.click("#dtInfNuevo")
        p.wait_for_selector("#dtInfOk", state="visible")
        p.fill("#dtInfN", "QA julio 2026")
        p.fill("#dtInfD", "2026-07-01")
        p.fill("#dtInfH", "2026-07-31")
        p.click("#dtInfOk")
        p.wait_for_timeout(1500)
        nombres = p.eval_on_selector_all(
            "#dtInformes .dt-inf-n", "ns => ns.map(n => n.textContent.trim())")
        if len(nombres) < 2:
            raise AssertionError("el segundo pisó al primero: %s" % nombres)
        return " + ".join(nombres)
    check("una planilla da varios reportes", dos_reportes)

    def quitar():
        antes = len(p.query_selector_all("#dtInformes .dt-inf-c"))
        p.click("#dtInformes .dt-inf-c .dt-inf-x")
        p.wait_for_timeout(1500)
        ahora = len(p.query_selector_all("#dtInformes .dt-inf-c"))
        if ahora != antes - 1:
            raise AssertionError("quedaron %d de %d" % (ahora, antes))
        return "quitado uno, queda %d" % ahora
    check("se puede quitar un reporte", quitar)

    # limpieza: que el sandbox quede como estaba
    p.evaluate("""async () => {
      const r = await fetch('/api/datos/estado'); const j = await r.json();
      const rep = (j.reportes || [])[0]; if (!rep) return;
      for (const i of (rep.informes || [])) {
        await fetch('/api/datos/informe-borrar', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id: rep.id, informe: i.id})});
      }
    }""")

    print("\nerrores de consola:", errs or "ninguno")
    b.close()

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
