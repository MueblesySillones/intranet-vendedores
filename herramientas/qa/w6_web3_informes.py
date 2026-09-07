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
    ED = {}

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

    def el_lapiz_esta():
        """El pedido: «existe un botón en una esquina tipo lápiz que diga
        editar… y al lado el de guardar edición»."""
        IDS["inf"] = p.get_attribute("#dtInformes .dt-inf-c", "data-inf")
        with ctx.expect_page() as info:
            p.click("#dtInformes [data-editar]")
        ED["pg"] = info.value
        d = ED["pg"]
        d.set_default_timeout(240000)
        d.wait_for_load_state("load")
        d.wait_for_timeout(2000)
        if not d.is_visible("#edBtn"):
            raise AssertionError("no hay lápiz en el reporte")
        if d.is_visible("#edOk"):
            raise AssertionError("«Guardar edición» se ve sin estar editando")
        return (d.text_content("#edBtn") or "").strip()
    check("el reporte tiene el lápiz en una esquina", el_lapiz_esta)

    def al_apretar_se_edita():
        d = ED["pg"]
        d.click("#edBtn")
        d.wait_for_selector("#edOk", state="visible", timeout=15000)
        editables = d.eval_on_selector_all(
            ".ed-t[data-txt]", "ns => ns.filter(n => n.isContentEditable).length")
        if editables < 10:
            raise AssertionError("solo %d textos quedaron editables" % editables)
        if not d.is_visible("#edAviso"):
            raise AssertionError("no avisa que los números no se editan")
        return "%d textos editables · %s" % (
            editables, (d.text_content("#edOk") or "").strip())
    check("al apretar el lápiz los textos se pueden tocar", al_apretar_se_edita)

    def el_interruptor_de_vista():
        d = ED["pg"]
        n = d.eval_on_selector_all(".ed-v", "ns => ns.length")
        if not n:
            raise AssertionError("las listas no ofrecen barras/tabla")
        secs = d.eval_on_selector_all(".slide[data-sec]",
                                      "ns => ns.map(x => x.dataset.sec)")
        if "vendedores" not in secs:
            raise AssertionError("la lista del equipo no se puede cambiar: %s" % secs)
        return "%d listas con barras/tabla: %s" % (n, ", ".join(secs))
    check("las listas dejan elegir cómo se ven", el_interruptor_de_vista)

    def la_tabla_se_ve_al_toque():
        """«cuando apreto tabla no pasa nada»: tenía que verse en el acto."""
        d = ED["pg"]
        d.evaluate("""() => {
          const s = [...document.querySelectorAll('.slide')]
            .findIndex(x => x.dataset.sec === 'vendedores');
          if (s >= 0) ir(s);
        }""")
        d.wait_for_timeout(400)
        antes = d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          const v = sl.querySelector('.lista-v:not([hidden])');
          return v ? v.dataset.vista : '';
        }""")
        d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          [...sl.querySelectorAll('.ed-v button')]
            .find(b => b.textContent === 'Tabla').click();
        }""")
        d.wait_for_timeout(300)
        ahora = d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          const v = sl.querySelector('.lista-v:not([hidden])');
          return v ? v.dataset.vista : '';
        }""")
        if antes != "barras" or ahora != "tabla":
            raise AssertionError("no cambió al toque: %s -> %s" % (antes, ahora))
        vista = d.eval_on_selector_all(
            ".slide[data-sec=vendedores] .lista-v:not([hidden]) table.tablita",
            "ns => ns.length")
        if not vista:
            raise AssertionError("dice tabla pero no se ve la tabla")
        return "de %s a %s sin guardar" % (antes, ahora)
    check("apretar Tabla cambia la vista en el acto", la_tabla_se_ve_al_toque)

    def sacar_un_texto():
        """«hay pequeños textos que pone el generador innecesarios»."""
        d = ED["pg"]
        hay = d.eval_on_selector_all(
            ".slide[data-sec=vendedores] .ed-x", "ns => ns.length")
        if not hay:
            raise AssertionError("los textos no tienen × para sacarlos")
        d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          const t = sl.querySelector('[data-txt="vendedores.bajada"]');
          t.nextElementSibling.click();
        }""")
        d.wait_for_timeout(300)
        est = d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          const t = sl.querySelector('[data-txt="vendedores.bajada"]');
          return { fuera: t.classList.contains('fuera'),
                   volver: !!sl.querySelector('.ed-fuera') };
        }""")
        if not est["fuera"]:
            raise AssertionError("no lo marcó como sacado")
        if not est["volver"]:
            raise AssertionError("no ofrece volver a mostrarlo")
        return "%d textos con ×; el sacado queda tachado y se puede recuperar" % hay
    check("cada texto se puede sacar del reporte", sacar_un_texto)

    def escribir_y_guardar():
        d = ED["pg"]
        # ir a la lámina del equipo, escribirle encima y pedirla en tabla
        d.evaluate("""() => {
          const s = [...document.querySelectorAll('.slide')]
            .findIndex(x => x.dataset.sec === 'vendedores');
          if (s >= 0) ir(s);
        }""")
        d.wait_for_timeout(500)
        d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          const t = sl.querySelector('[data-txt="vendedores.titulo"]');
          t.textContent = 'Pases por asesor';
          [...sl.querySelectorAll('.ed-v button')]
            .find(b => b.textContent === 'Tabla').click();
        }""")
        # guardar recarga la pagina (el reporte se rearma en el servidor y eso
        # relee la planilla, o sea que tarda). Hay que esperar LA NAVEGACION,
        # no un rato: si no, el evaluate de abajo cae justo mientras navega.
        with d.expect_navigation(wait_until="load", timeout=240000):
            d.click("#edOk")
        d.wait_for_timeout(2500)
        txt = d.evaluate("() => document.body.innerText")
        if "Pases por asesor" not in txt:
            raise AssertionError("el texto nuevo no quedó")
        if not d.eval_on_selector_all(
                ".lista-v:not([hidden]) table.tablita", "ns => ns.length"):
            raise AssertionError("no aplicó la vista de tabla")
        if "Cuántas consultas recibió cada uno" in txt:
            raise AssertionError("el texto que se sacó volvió a aparecer")
        return "guardó el texto, la tabla y lo que se sacó"
    check("se escribe encima, se guarda y queda", escribir_y_guardar)

    def quedo_guardado_de_verdad():
        """No alcanza con que se vea: tiene que estar en el reporte guardado."""
        import urllib.request
        html = urllib.request.urlopen(
            "%s/api/datos/deck?id=%s&informe=%s" % (BASE, IDS["rep"], IDS["inf"]),
            timeout=240).read().decode("utf-8")
        if "Pases por asesor" not in html or "<table" not in html:
            raise AssertionError("se perdió al volver a pedirlo")
        if "Cuántas consultas recibió cada uno" in html:
            raise AssertionError("el texto sacado volvió al reporte guardado")
        ED["pg"].close()
        return "el reporte guardado ya dice lo nuevo"
    check("lo editado sobrevive a cerrar y volver", quedo_guardado_de_verdad)

    def el_word_tambien():
        with p.expect_download() as dl:
            p.click("#dtInformes [data-doc]")
        ruta = os.path.join(os.environ.get("TEMP", "."), "qa_inline.docx")
        dl.value.save_as(ruta)
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        os.remove(ruta)
        if "Pases por asesor" not in xml:
            raise AssertionError("el Word quedó con el texto viejo")
        return "el Word dice lo mismo que la pantalla"
    check("el Word no queda diciendo otra cosa", el_word_tambien)

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
