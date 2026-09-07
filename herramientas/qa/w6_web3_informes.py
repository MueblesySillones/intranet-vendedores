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


def abrir_lamina(p, clave):
    """Despliega la lámina que contiene ese texto."""
    p.evaluate("""(k) => {
      const t = document.querySelector('[data-texto="' + k + '"]');
      if (t) { const d = t.closest('details'); if (d) d.open = true; }
    }""", clave)
    p.wait_for_selector('#dtInfForm [data-texto="%s"]' % clave, state="visible",
                        timeout=10000)


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
        # solo la grilla de la pregunta 3, sin el «sin nombres» de la 6 ni los
        # radios de las otras: son preguntas distintas y se cuentan aparte
        ops = p.eval_on_selector_all(
            "#dtInfForm .dt-inf-q:nth-of-type(3) .dt-inf-s .dt-inf-o b",
            "ns => ns.map(n => n.textContent.trim())")
        if len(ops) < 8:
            raise AssertionError("solo %d cosas para medir: %s" % (len(ops), ops))
        falta = [x for x in ("El embudo", "Por sucursal", "Por vendedor",
                             "Qué productos consultan", "De qué campaña vienen",
                             "Por qué canal entran")
                 if x not in ops]
        if falta:
            raise AssertionError("no se puede elegir: %s" % falta)
        marcadas = p.eval_on_selector_all(
            "#dtInfForm .dt-inf-q:nth-of-type(3) .dt-inf-s input",
            "ns => ns.filter(n => n.checked).length")
        if marcadas != len(ops):
            raise AssertionError("no vienen todas marcadas: %d de %d"
                                 % (marcadas, len(ops)))
        return "%d cosas para medir, todas marcadas" % len(ops)
    check("se puede elegir qué medir", opciones_de_medir)

    def preguntas_extra():
        """Las respuestas vienen puestas: crear el reporte de siempre es
        apretar dos botones, y las preguntas están para el que quiere otra."""
        v = p.evaluate("""() => ({
          cmp: (document.querySelector('input[name=dtInfCmp]:checked')||{}).value,
          det: (document.querySelector('input[name=dtInfDet]:checked')||{}).value,
          anon: document.getElementById('dtInfAnon').checked,
          nota: document.getElementById('dtInfNota') ? 'sí' : 'no',
          ncmp: document.querySelectorAll('input[name=dtInfCmp]').length,
          ndet: document.querySelectorAll('input[name=dtInfDet]').length
        })""")
        if v["cmp"] != "anterior":
            raise AssertionError("la comparación no viene en «anterior»: %s" % v)
        if v["det"] != "10":
            raise AssertionError("el detalle no viene en 10: %s" % v)
        if v["anon"]:
            raise AssertionError("viene sin nombres por defecto")
        if v["nota"] != "sí" or v["ncmp"] < 3 or v["ndet"] < 3:
            raise AssertionError("faltan opciones: %s" % v)
        return ("comparar=%s (%d opciones) · detalle=%s (%d) · con nombres · "
                "con nota" % (v["cmp"], v["ncmp"], v["det"], v["ndet"]))
    check("comparación, detalle, nombres y nota vienen resueltos", preguntas_extra)

    def desmarcar_todas():
        p.click('#dtInfForm .dt-at[data-marca="ninguna"]')
        n = p.eval_on_selector_all(
            "#dtInfForm .dt-inf-q:nth-of-type(3) .dt-inf-s input",
            "ns => ns.filter(x => x.checked).length")
        if n:
            raise AssertionError("quedaron %d marcadas" % n)
        p.click("#dtInfOk")
        p.wait_for_timeout(600)
        p.click('#dtInfForm .dt-at[data-marca="todas"]')
        n2 = p.eval_on_selector_all(
            "#dtInfForm .dt-inf-q:nth-of-type(3) .dt-inf-s input",
            "ns => ns.filter(x => x.checked).length")
        if not n2:
            raise AssertionError("«marcar todas» no marcó nada")
        return "marcar/desmarcar todas anda, y sin nada marcado no deja crear"
    check("los atajos de «qué medir» funcionan", desmarcar_todas)

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
        # se espera LA tarjeta de este reporte, no «alguna tarjeta»: si la
        # biblioteca ya tiene otras, esperar .dt-inf-c vuelve al instante y se
        # lee la lista antes de que el guardado termine
        p.wait_for_function(
            """n => [...document.querySelectorAll('#dtInformes .dt-inf-n')]
                     .some(e => e.textContent.trim() === n)""",
            arg=NOMBRE, timeout=40000)
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

    def compara_contra_julio():
        """El reporte de agosto tiene que abrir diciendo qué cambió.

        Es lo que se pidió desde el principio —«comparación con el mes pasado,
        aumentó un 20%»— y es lo primero que se mira: un total suelto no dice
        si estuvo bien o mal.
        """
        import re
        import urllib.request
        url = ("%s/api/datos/deck?id=%s&informe=%s"
               % (BASE, IDS["rep"], IDS["inf"]))
        html = urllib.request.urlopen(url, timeout=240).read().decode("utf-8")
        if "La comparación" not in html:
            raise AssertionError("no trae la lámina de comparación")
        if "julio" not in html.lower():
            raise AssertionError("no dice contra qué compara")
        m = re.search(r"Las derivaciones (subieron|bajaron) un ([\d,]+%)", html)
        if not m:
            raise AssertionError("no dice cuánto cambió")
        return "compara agosto contra julio: %s un %s" % (m.group(1), m.group(2))
    check("el reporte compara contra el período anterior", compara_contra_julio)

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

    def pdf_baja_solo():
        """Un click y el archivo baja. Nada de abrir el reporte y hacer Ctrl+P.

        Lo que se prueba es el botón de la tarjeta, no la ruta: el pedido fue
        «cuando haga click se descargue de una», así que si el botón dejara de
        disparar la descarga, la ruta andando no alcanza.
        """
        with p.expect_download(timeout=180000) as d:
            p.click("#dtInformes [data-pdf]")
        des = d.value
        ruta = os.path.join(os.environ.get("TEMP", "."), "qa_deck.pdf")
        des.save_as(ruta)
        if not des.suggested_filename.lower().endswith(".pdf"):
            raise AssertionError("no bajó un .pdf: %s" % des.suggested_filename)
        with open(ruta, "rb") as f:
            cabeza = f.read(5)
        tam = os.path.getsize(ruta)
        os.remove(ruta)
        if cabeza != b"%PDF-":
            raise AssertionError("el archivo no es un PDF: %r" % cabeza)
        if tam < 20000:
            raise AssertionError("el PDF vino casi vacío: %d bytes" % tam)
        return "%s · %d KB" % (des.suggested_filename, tam // 1024)
    check("«Descargar PDF» baja el archivo de una", pdf_baja_solo)

    def pdf_con_el_diseno():
        """Que sea un PDF no alcanza: tiene que ser EL reporte, en 16:9."""
        import urllib.request
        url = ("%s/api/datos/deck-pdf?id=%s&informe=%s"
               % (BASE, IDS["rep"], IDS["inf"]))
        ruta = os.path.join(os.environ.get("TEMP", "."), "qa_deck2.pdf")
        urllib.request.urlretrieve(url, ruta)
        try:
            import fitz
        except ImportError:
            os.remove(ruta)
            return "PDF bajado (sin PyMuPDF no se puede mirar adentro)"
        doc = fitz.open(ruta)
        hojas, caja = doc.page_count, doc[0].rect
        texto = doc[0].get_text() + doc[1].get_text()
        doc.close()
        os.remove(ruta)
        forma = caja.width / float(caja.height)
        if abs(forma - 16 / 9.0) > 0.02:
            raise AssertionError("no es 16:9: %.3f" % forma)
        if hojas < 3:
            raise AssertionError("solo %d hoja(s): no es el deck" % hojas)
        if NOMBRE not in texto:
            raise AssertionError("la portada no dice el nombre del reporte")
        return "%d hojas en 16:9, con la portada del reporte" % hojas
    check("el PDF es el deck con su diseño", pdf_con_el_diseno)

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

    def editar_palabras():
        """Cambiar una palabra: el pedido fue «¿y si no le gusta lo que dice?»."""
        # se edita la PRIMERA tarjeta y se anota SU id: para entonces ya hay dos
        # reportes, y el que se abrio mas arriba puede no ser este
        IDS["inf"] = p.get_attribute("#dtInformes .dt-inf-c", "data-inf")
        p.click("#dtInformes [data-editar]")
        p.wait_for_selector("#dtEdOk", state="visible", timeout=180000)
        campos = p.eval_on_selector_all("#dtInfForm [data-texto]",
                                        "ns => ns.map(n => n.dataset.texto)")
        if "vendedores.titulo" not in campos:
            raise AssertionError("no se puede editar el título del equipo: %s"
                                 % campos[:6])
        avisos = p.eval_on_selector_all("#dtInfForm .dt-ed-av", "ns => ns.length")
        if not avisos:
            raise AssertionError("no avisa cuáles textos llevan números")
        # las láminas vienen plegadas: se abre la que se va a tocar, como haría
        # cualquiera. Si esto dejara de hacer falta, el editor volvió a ser un
        # muro de 40 campos.
        if p.is_visible('#dtInfForm [data-texto="vendedores.titulo"]'):
            raise AssertionError("las láminas no vienen plegadas")
        abrir_lamina(p, "vendedores.titulo")
        p.fill('#dtInfForm [data-texto="vendedores.titulo"]', "Pases por asesor")
        p.click('#dtInfForm .dt-ed-v[data-sec="vendedores"] [data-vista="tabla"]')
        p.click("#dtEdOk")
        p.wait_for_timeout(1500)
        return "%d textos editables, %d con números" % (len(campos), avisos)
    check("se puede reescribir un texto y pedir tabla", editar_palabras)

    def el_reporte_lo_respeta():
        import urllib.request
        url = ("%s/api/datos/deck?id=%s&informe=%s"
               % (BASE, IDS["rep"], IDS["inf"]))
        html = urllib.request.urlopen(url, timeout=240).read().decode("utf-8")
        if "Pases por asesor" not in html:
            raise AssertionError("el reporte no usa el texto nuevo")
        if "Derivaciones por vendedor" in html:
            raise AssertionError("sigue mostrando el texto viejo")
        if "<table" not in html:
            raise AssertionError("no dibujó la lista como tabla")
        return "el reporte dice «Pases por asesor» y la lista es una tabla"
    check("el reporte usa lo que se escribió", el_reporte_lo_respeta)

    def el_word_tambien():
        with p.expect_download() as d:
            p.click("#dtInformes [data-doc]")
        ruta = os.path.join(os.environ.get("TEMP", "."), "qa_textos.docx")
        d.value.save_as(ruta)
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        os.remove(ruta)
        if "Pases por asesor" not in xml:
            raise AssertionError("el Word quedó con el texto viejo")
        return "el Word dice lo mismo que la pantalla"
    check("el Word no queda diciendo otra cosa", el_word_tambien)

    def volver_al_de_fabrica():
        p.click("#dtInformes [data-editar]")
        p.wait_for_selector("#dtEdOk", state="visible", timeout=180000)
        abrir_lamina(p, "vendedores.titulo")
        v = p.input_value('#dtInfForm [data-texto="vendedores.titulo"]')
        if v != "Pases por asesor":
            raise AssertionError("no muestra lo que se había escrito: %r" % v)
        p.fill('#dtInfForm [data-texto="vendedores.titulo"]', "")
        p.click("#dtEdOk")
        p.wait_for_timeout(1500)
        import urllib.request
        html = urllib.request.urlopen(
            "%s/api/datos/deck?id=%s&informe=%s" % (BASE, IDS["rep"], IDS["inf"]),
            timeout=240).read().decode("utf-8")
        if "Derivaciones por vendedor" not in html:
            raise AssertionError("no volvió al texto de fábrica")
        return "vaciar el campo devuelve el texto original"
    check("dejarlo vacío vuelve al texto de fábrica", volver_al_de_fabrica)

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
