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


def asistente(p, nombre, desde, hasta, sacar=None):
    """Contesta el asistente de punta a punta y crea el reporte.

    `sacar` es lo que se destilda en «qué querés medir»: sirve para comprobar
    después que el reporte respeta lo que NO se pidió.
    """
    p.click("#dtInfNuevo")
    p.wait_for_selector("#repModal.on", state="visible", timeout=25000)
    p.wait_for_timeout(400)
    p.fill("#repNombre", nombre)
    p.click("#repSiguiente"); p.wait_for_timeout(400)
    p.fill("#repDesde", desde)
    p.fill("#repHasta", hasta)
    p.click("#repSiguiente"); p.wait_for_timeout(400)
    if sacar:
        p.evaluate("""(t) => {
          const os = [...document.querySelectorAll('#repCuerpo .dt-inf-o')];
          const o = os.find(x => x.textContent.indexOf(t) >= 0);
          if (o) o.querySelector('input').checked = false;
        }""", sacar)
    while "Crear reporte" not in (p.text_content("#repSiguiente") or ""):
        p.click("#repSiguiente")
        p.wait_for_timeout(300)
    p.click("#repSiguiente")
    p.wait_for_timeout(2500)


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

    def paso_uno_es_el_nombre():
        """El pedido: «que se abra una ventana flotante con las distintas
        preguntas para ir creando paso a paso, empezando desde el nombre»."""
        p.click("#dtInfNuevo")
        p.wait_for_selector("#repModal.on", state="visible", timeout=25000)
        p.wait_for_timeout(600)
        v = p.evaluate("""() => ({
          sub: document.getElementById('repSub').textContent,
          preg: (document.querySelector('#repCuerpo .rep-p b')||{}).textContent,
          nombre: (document.getElementById('repNombre')||{}).value,
          atras: document.getElementById('repAtras').disabled,
          foco: (document.activeElement||{}).id
        })""")
        if "nombre" not in (v["preg"] or "").lower() and "llamar" not in (v["preg"] or "").lower():
            raise AssertionError("el paso 1 no pregunta el nombre: %r" % v["preg"])
        if not v["nombre"]:
            raise AssertionError("no propone un nombre")
        if not v["atras"]:
            raise AssertionError("«Atrás» está habilitado en el primer paso")
        if v["foco"] != "repNombre":
            raise AssertionError("el foco no está en el campo: %r" % v["foco"])
        return "%s · %r · propone %r" % (v["sub"], v["preg"], v["nombre"])
    check("el paso 1 es el nombre, en una ventana flotante", paso_uno_es_el_nombre)

    def los_pasos_llevan_a_crear():
        """⚠️ No se cuentan los clicks: se avanza hasta que el botón ofrece
        crear. Contar a ciegas se rompe el día que hay una pregunta más, y eso
        no es una falla del asistente."""
        vistos = []
        for _ in range(20):
            if "Crear reporte" in (p.text_content("#repSiguiente") or ""):
                break
            p.click("#repSiguiente")
            p.wait_for_timeout(400)
            vistos.append(p.evaluate(
                "() => (document.querySelector('#repCuerpo .rep-p b')||{}).textContent"))
        else:
            raise AssertionError("el asistente nunca llega a crear")
        falta = [x for x in ("¿De qué período?", "¿Qué querés medir?",
                             "¿Contra qué lo comparás?", "¿Cómo sale el PDF?")
                 if x not in vistos]
        if falta:
            raise AssertionError("no pasó por: %s" % falta)
        return "%d pasos · %s" % (len(vistos) + 1,
                                  " → ".join(v[:20] for v in vistos))
    check("las preguntas llevan a crear el reporte", los_pasos_llevan_a_crear)

    def el_ultimo_repasa():
        """Sin un repaso, revisar lo contestado obliga a volver paso por paso."""
        t = p.evaluate("() => (document.getElementById('repResumen')||{}).textContent || ''")
        for x in ("Nombre", "Período", "Mide", "Compara", "PDF"):
            if x not in t:
                raise AssertionError("el repaso no dice %r: %r" % (x, t[:90]))
        return "repasa nombre, período, qué mide, contra qué y cómo sale el PDF"
    check("el último paso repasa lo contestado", el_ultimo_repasa)

    def atras_no_pierde():
        # se vuelve hasta el paso de «qué querés medir», que es el que tiene
        # algo que perder. Se busca la opción POR SU VALOR y no por la clase:
        # otros pasos usan la misma clase para sus opciones y el bucle frenaba
        # en el primero que encontraba. Contar clicks a ciegas tampoco sirve:
        # se rompe el día que haya un paso más, o uno menos.
        while not p.evaluate("""() => !!document.querySelector(
                '#repCuerpo input[value=template]')"""):
            if p.evaluate("() => document.getElementById('repAtras').disabled"):
                raise AssertionError("no encontré el paso de las opciones")
            p.click("#repAtras")
            p.wait_for_timeout(350)
        # se cambia algo y se vuelve adelante: tiene que seguir puesto
        p.evaluate("""() => {
          const os = [...document.querySelectorAll('#repCuerpo .dt-inf-s input')];
          const t = os.find(i => i.value === 'template');
          if (t) t.checked = false;
        }""")
        p.click("#repSiguiente"); p.wait_for_timeout(300)
        p.click("#repAtras"); p.wait_for_timeout(400)
        sigue = p.evaluate("""() => {
          const t = [...document.querySelectorAll('#repCuerpo .dt-inf-s input')]
            .find(i => i.value === 'template');
          return t ? t.checked : null;
        }""")
        if sigue is not False:
            raise AssertionError("ir y volver perdió lo destildado: %s" % sigue)
        while "Crear reporte" not in (p.text_content("#repSiguiente") or ""):
            p.click("#repSiguiente")
            p.wait_for_timeout(300)
        return "ir y volver entre pasos no pierde lo contestado"
    check("ir y volver no pierde las respuestas", atras_no_pierde)

    def crear():
        # el asistente quedó abierto de las pruebas de arriba: se cierra y se
        # arranca de cero, que es lo que haría cualquiera
        if p.is_visible("#repModal.on"):
            p.keyboard.press("Escape")
            p.wait_for_timeout(500)
        asistente(p, NOMBRE, "2026-08-01", "2026-08-31",
                  sacar="Seguimiento enviado")
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

    def cambiar_que_mide():
        """Un reporte guarda las láminas que se tildaron el día que se creó.
        Cuando el panel aprende a mostrar algo nuevo, ese reporte no lo tiene
        destildado: nunca se lo preguntaron. Sin esta puerta habría que
        borrarlo y hacerlo de nuevo."""
        c = p.query_selector("#dtInformes .dt-inf-c")
        if not c.query_selector("[data-cambiar]"):
            raise AssertionError("la tarjeta no ofrece cambiar qué mide")
        p.click("#dtInformes .dt-inf-c [data-cambiar]")
        p.wait_for_selector("#repModal.on", state="visible", timeout=25000)
        p.wait_for_timeout(700)
        v = p.evaluate("""() => ({
          nombre: (document.getElementById('repNombre')||{}).value,
          paso: (document.querySelector('#repCuerpo .rep-p b')||{}).textContent
        })""")
        if (v["nombre"] or "").strip() != NOMBRE:
            raise AssertionError("no vino con el nombre puesto: %r" % v["nombre"])
        # hasta el paso de las láminas
        while not p.evaluate("""() => !!document.querySelector(
                '#repCuerpo input[value=ritmo]')"""):
            p.click("#repSiguiente")
            p.wait_for_timeout(350)
        puesto = p.evaluate("""() => {
          const q = v => {
            const i = [...document.querySelectorAll('#repCuerpo .dt-inf-s input')]
              .find(x => x.value === v);
            return i ? i.checked : null;
          };
          return {template: q('template'), embudo: q('embudo')};
        }""")
        if puesto["template"] is not False:
            raise AssertionError("no trajo lo destildado: %s" % puesto)
        if puesto["embudo"] is not True:
            raise AssertionError("perdió lo que sí estaba tildado: %s" % puesto)
        # se tilda una lámina que el reporte no tenía
        p.evaluate("""() => {
          const i = [...document.querySelectorAll('#repCuerpo .dt-inf-s input')]
            .find(x => x.value === 'ritmo');
          if (i) i.checked = true;
        }""")
        while "Guardar cambios" not in (p.text_content("#repSiguiente") or ""):
            p.click("#repSiguiente")
            p.wait_for_timeout(350)
        return "vino contestado (%s) y el botón final guarda" % v["paso"][:24]
    check("cambiar qué mide reabre el asistente contestado", cambiar_que_mide)

    def guardar_el_cambio():
        antes = len(p.query_selector_all("#dtInformes .dt-inf-c"))
        p.click("#repSiguiente")
        p.wait_for_function(
            """() => !document.querySelector('#repModal.on')""", timeout=40000)
        p.wait_for_timeout(1200)
        ahora = len(p.query_selector_all("#dtInformes .dt-inf-c"))
        if ahora != antes:
            raise AssertionError("creó otro en vez de editar: %d → %d"
                                 % (antes, ahora))
        mide = (p.text_content("#dtInformes .dt-inf-c .dt-inf-m") or "").strip()
        if "ritmo" not in mide.lower():
            raise AssertionError("no tomó la lámina nueva: %r" % mide)
        if "Seguimiento enviado" in mide:
            raise AssertionError("volvió a poner lo destildado: %r" % mide)
        return "la tarjeta ahora mide también el ritmo, y sigue siendo una"
    check("guardar cambia el reporte y no crea otro", guardar_el_cambio)

    def el_reporte_muestra_la_lamina_nueva():
        """Y lo que importa: que la lámina esté de verdad adentro del reporte."""
        rid = p.evaluate("""async () => {
          const r = await fetch('/api/datos/estado'); const j = await r.json();
          return (j.reportes || [])[0].id;
        }""")
        iid = p.get_attribute("#dtInformes .dt-inf-c", "data-inf")
        import urllib.request
        html = urllib.request.urlopen(
            "%s/api/datos/deck?id=%s&informe=%s" % (BASE, rid, iid),
            timeout=240).read().decode("utf-8")
        if 'data-sec="ritmo"' not in html:
            raise AssertionError("el reporte sigue sin la lámina del ritmo")
        if "Cuánto entra por día" not in html:
            raise AssertionError("la lámina está vacía")
        return "el reporte ya trae «Cuánto entra por día»"
    check("la lámina nueva aparece en el reporte",
          el_reporte_muestra_la_lamina_nueva)

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

        ⚠️ Vive DEBAJO DE CADA TARJETA del embudo, no en una lámina aparte.
        Hubo una lámina de comparación hasta la v55 y se sacó: decía lo mismo
        que estas cuatro tarjetas, en otra hoja y con otro dibujo. Por eso acá
        se comprueba las dos cosas —que el porcentaje esté, y que la lámina no
        haya vuelto—: una prueba que solo mira lo nuevo deja pasar que lo viejo
        siga ahí duplicando.
        """
        import re
        import urllib.request
        url = ("%s/api/datos/deck?id=%s&informe=%s"
               % (BASE, IDS["rep"], IDS["inf"]))
        html = urllib.request.urlopen(url, timeout=240).read().decode("utf-8")
        if 'data-sec="comparacion"' in html or "La comparación" in html:
            raise AssertionError("volvió la lámina de comparación")
        chips = re.findall(r'class="ccmp [^"]*">([^<]+)<', html)
        if len(chips) < 4:
            raise AssertionError("el embudo no compara: %s" % chips)
        if not all("vs" in c for c in chips):
            raise AssertionError("no dicen contra qué comparan: %s" % chips)
        if "julio" not in " ".join(chips).lower():
            raise AssertionError("no compara contra julio: %s" % chips)
        return "en las tarjetas del embudo: %s" % " · ".join(chips)
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

    def la_hoja_del_pdf_se_elige():
        """El pedido: «la generación de pdf en horizontal, que sea ajustable».

        Ya salía horizontal (16:9), pero era el único tamaño posible. Se prueba
        que elegir A4 apaisada cambie de verdad la hoja del archivo —no que se
        guarde la opción y el PDF salga igual, que es el bug que tuvo el
        interruptor de barras/tabla—.
        """
        import urllib.request
        try:
            import fitz
        except ImportError:
            return "(sin PyMuPDF no se puede medir la hoja, salteado)"

        def hoja_de(cual):
            p.evaluate("""async (d) => {
              await fetch('/api/datos/informe-editar', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: d.rep, informe: d.inf,
                                      opciones: {hoja: d.hoja}})});
            }""", {"rep": IDS["rep"], "inf": IDS["inf"], "hoja": cual})
            ruta = os.path.join(os.environ.get("TEMP", "."), "qa_hoja.pdf")
            urllib.request.urlretrieve(
                "%s/api/datos/deck-pdf?id=%s&informe=%s"
                % (BASE, IDS["rep"], IDS["inf"]), ruta)
            doc = fitz.open(ruta)
            r, n = doc[0].rect, doc.page_count
            doc.close()
            os.remove(ruta)
            return round(r.width, 1), round(r.height, 1), n

        an1, al1, n1 = hoja_de("a4h")
        # A4 apaisada = 297 x 210 mm = 842 x 595 puntos
        if not (835 < an1 < 850 and 590 < al1 < 600):
            raise AssertionError("A4 apaisada dio %sx%s pt" % (an1, al1))
        an2, al2, n2 = hoja_de("a4v")
        if not (590 < an2 < 600 and 835 < al2 < 850):
            raise AssertionError("A4 vertical dio %sx%s pt" % (an2, al2))
        if n1 != n2:
            raise AssertionError("cambiar la hoja cambió la cantidad de "
                                 "láminas: %d vs %d" % (n1, n2))
        an3, al3, _ = hoja_de("pantalla")     # y se deja como estaba
        if abs(an3 / float(al3) - 16 / 9.0) > 0.02:
            raise AssertionError("no volvió a 16:9: %sx%s" % (an3, al3))
        return ("A4 apaisada %sx%s · A4 vertical %sx%s · pantalla %sx%s, "
                "siempre %d hojas" % (an1, al1, an2, al2, an3, al3, n1))
    check("la hoja del PDF se elige y cambia el archivo",
          la_hoja_del_pdf_se_elige)

    def dos_reportes():
        """Dos reportes distintos de la MISMA planilla, sin pisarse."""
        asistente(p, "QA julio 2026", "2026-07-01", "2026-07-31")
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

    def el_pdf_se_baja_desde_el_reporte():
        """El pedido: «cuando apretes descargar en pdf se pueda descargar con
        facilidad». Mirando el reporte no había forma de bajarlo: había que
        cerrar la pestaña y volver al panel a buscar la tarjeta."""
        d = ED["pg"]
        if not d.is_visible("#edPdf"):
            raise AssertionError("no hay botón de bajar el PDF en el reporte")
        with d.expect_download(timeout=180000) as des:
            d.click("#edPdf")
        ruta = os.path.join(os.environ.get("TEMP", "."), "qa_desde_deck.pdf")
        des.value.save_as(ruta)
        with open(ruta, "rb") as f:
            cabeza = f.read(5)
        tam = os.path.getsize(ruta)
        os.remove(ruta)
        if cabeza != b"%PDF-":
            raise AssertionError("no bajó un PDF: %r" % cabeza)
        if tam < 20000:
            raise AssertionError("el PDF vino casi vacío: %d bytes" % tam)
        d.wait_for_timeout(400)
        if d.is_disabled("#edPdf"):
            raise AssertionError("el botón quedó trabado después de bajar")
        return "%s · %d KB, sin salir del reporte" % (
            des.value.suggested_filename, tam // 1024)
    check("el PDF se baja desde adentro del reporte",
          el_pdf_se_baja_desde_el_reporte)

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

    def editando_no_se_baja():
        """El reporte lo arma el servidor con lo ÚLTIMO GUARDADO: bajarlo con
        cambios sin guardar daría un PDF sin ellos y nadie entendería por qué."""
        d = ED["pg"]
        if d.is_visible("#edPdf"):
            raise AssertionError("se puede bajar el PDF con cambios sin guardar")
        d.click("#edBtn")                       # sale de edición
        d.wait_for_timeout(500)
        if not d.is_visible("#edPdf"):
            raise AssertionError("al salir de edición no volvió el botón")
        d.click("#edBtn")                       # vuelve a entrar, como estaba
        d.wait_for_selector("#edOk", state="visible", timeout=15000)
        return "editando no está, y vuelve al salir"
    check("editando, el PDF no se puede bajar a medias", editando_no_se_baja)

    def el_interruptor_de_vista():
        """La vista es de las LISTAS; el fondo es de todas.

        El embudo y los límites no son listas: ofrecerles «barras o tabla» es
        ofrecer algo que no existe. El fondo sí, porque cualquier lámina se
        puede pintar clara u oscura.
        """
        d = ED["pg"]
        r = d.evaluate("""() => {
          const out = {conVista: [], sinVista: [], sinFondo: []};
          document.querySelectorAll('.slide[data-sec]').forEach(sl => {
            const filas = [...sl.querySelectorAll('.ed-fila > span')]
              .map(x => x.textContent);
            if (filas.indexOf('Vista') >= 0) out.conVista.push(sl.dataset.sec);
            else out.sinVista.push(sl.dataset.sec);
            if (filas.indexOf('Fondo') < 0) out.sinFondo.push(sl.dataset.sec);
          });
          return out;
        }""")
        if "vendedores" not in r["conVista"]:
            raise AssertionError("la lista del equipo no ofrece vista: %s" % r)
        for sec in ("embudo", "limites"):
            if sec in r["conVista"]:
                raise AssertionError("«%s» no es una lista y ofrece vista" % sec)
        if r["sinFondo"]:
            raise AssertionError("sin interruptor de fondo: %s" % r["sinFondo"])
        return ("%d listas eligen vista, %d láminas más solo fondo"
                % (len(r["conVista"]), len(r["sinVista"])))
    check("la vista es de las listas y el fondo es de todas",
          el_interruptor_de_vista)

    def hay_tres_vistas():
        """«así sea un gráfico barra horizontal o vertical»: columnas."""
        d = ED["pg"]
        botones = d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=ritmo]');
          if (!sl) return null;
          const f = [...sl.querySelectorAll('.ed-fila')]
            .find(x => x.querySelector('span').textContent === 'Vista');
          return f ? [...f.querySelectorAll('button')].map(b => b.textContent) : null;
        }""")
        if not botones or "Columnas" not in botones:
            raise AssertionError("no se puede elegir columnas: %s" % botones)
        puesta = d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=ritmo]');
          const v = sl.querySelector('.lista-v:not([hidden])');
          return {vista: v ? v.dataset.vista : '', cols: !!v.querySelector('.cols')};
        }""")
        if puesta["vista"] != "columnas" or not puesta["cols"]:
            raise AssertionError("el ritmo no sale en columnas: %s" % puesta)
        return "barras · columnas · tabla, y el ritmo sale en columnas"
    check("el ritmo se muestra como gráfico de columnas", hay_tres_vistas)

    def la_tabla_del_equipo_tiene_las_columnas():
        """«si hay que mostrar en una tabla entera vendedores, derivaciones,
        ventas y conversión, hagámoslo más prolijo»."""
        d = ED["pg"]
        d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          [...sl.querySelectorAll('.ed-fila')]
            .find(f => f.querySelector('span').textContent === 'Vista')
            .querySelectorAll('button').forEach(b => {
              if (b.textContent === 'Tabla') b.click();
            });
        }""")
        d.wait_for_timeout(350)
        cols = d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          const t = sl.querySelector('.lista-v:not([hidden]) table');
          if (!t) return null;
          return {
            cabezas: [...t.querySelectorAll('thead th')].map(
              x => (x.querySelector('.ed-t') || x).textContent.trim()),
            celdas: [...t.querySelectorAll('tbody tr')][0]
              ? [...t.querySelectorAll('tbody tr')][0].children.length : 0
          };
        }""")
        if not cols:
            raise AssertionError("no hay tabla en la lámina del equipo")
        for c in ("Vendedor", "Derivaciones", "Ventas", "Conversión"):
            if c not in cols["cabezas"]:
                raise AssertionError("falta la columna %r: %s" % (c, cols["cabezas"]))
        # se la deja en barras: el caso que sigue prueba justamente el paso
        # de barras a tabla, y encontrarla ya en tabla no probaría nada
        d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=vendedores]');
          [...sl.querySelectorAll('.ed-fila')]
            .find(f => f.querySelector('span').textContent === 'Vista')
            .querySelectorAll('button').forEach(b => {
              if (b.textContent === 'Barras') b.click();
            });
        }""")
        d.wait_for_timeout(300)
        return " · ".join(x for x in cols["cabezas"] if x)
    check("la tabla del equipo muestra ventas y conversión",
          la_tabla_del_equipo_tiene_las_columnas)

    def el_embudo_dice_cuanto_cambio():
        """«en la parte de abajo tiene que mostrarse un porcentaje así sea
        positivo o negativo y un texto que diga "vs el mes pasado"»."""
        d = ED["pg"]
        chips = d.evaluate("""() => [...document.querySelectorAll(
          '.slide[data-sec=embudo] .conv-card .ccmp')].map(x => ({
            texto: x.textContent.trim(),
            bueno: x.classList.contains('sube')}))""")
        if len(chips) < 4:
            raise AssertionError("solo %d tarjetas comparan: %s" % (len(chips), chips))
        if not all("vs" in c["texto"] for c in chips):
            raise AssertionError("no dicen contra qué: %s" % chips)
        # «sin derivar» sube y eso es MALO: el color no puede salir del signo
        sd = chips[2]
        if sd["texto"].startswith("▲") and sd["bueno"]:
            raise AssertionError("pintó de bueno que suba lo que no se deriva")
        return " · ".join(c["texto"] for c in chips)
    check("el embudo dice cuánto cambió contra el período anterior",
          el_embudo_dice_cuanto_cambio)

    def sacar_una_tarjeta_entera():
        """«eso tiene que tener la opción de editarlo o eliminar esa tarjeta…
        si el usuario quiere dejar 1, que la tarjeta se centre»."""
        d = ED["pg"]
        antes = d.evaluate("""() => {
          const c = document.querySelector('.slide[data-sec=embudo] .notas');
          return {tarjetas: c.querySelectorAll('.nota').length,
                  equis: c.querySelectorAll('.ed-nx').length,
                  sola: c.classList.contains('sola')};
        }""")
        if antes["tarjetas"] < 2:
            raise AssertionError("el embudo no tiene dos tarjetas")
        if antes["equis"] != antes["tarjetas"]:
            raise AssertionError("no todas las tarjetas tienen ×: %s" % antes)
        if antes["sola"]:
            raise AssertionError("dice «sola» con dos tarjetas")
        d.evaluate("""() => document.querySelector(
          '.slide[data-sec=embudo] .notas .nota .ed-nx').click()""")
        d.wait_for_timeout(350)
        ahora = d.evaluate("""() => {
          const c = document.querySelector('.slide[data-sec=embudo] .notas');
          const n = c.querySelector('.nota');
          return {fuera: n.classList.contains('fuera'),
                  volver: !!c.querySelector('.ed-nv:not([hidden])'),
                  sola: c.classList.contains('sola')};
        }""")
        if not ahora["fuera"]:
            raise AssertionError("no marcó la tarjeta como sacada")
        if not ahora["volver"]:
            raise AssertionError("no ofrece volver a mostrarla")
        if not ahora["sola"]:
            raise AssertionError("la que queda no se centró")
        # se la devuelve: esta prueba no tiene que dejar el reporte cambiado
        d.evaluate("""() => document.querySelector(
          '.slide[data-sec=embudo] .notas .ed-nv').click()""")
        d.wait_for_timeout(300)
        return "sacada, la otra se centra, y vuelve con un click"
    check("una tarjeta se saca entera y la que queda se centra",
          sacar_una_tarjeta_entera)

    def el_fondo_se_elige():
        """«que puedas elegir de qué color querés el fondo, si oscuro o claro»."""
        d = ED["pg"]
        r = d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=embudo]');
          const f = [...sl.querySelectorAll('.ed-fila')]
            .find(x => x.querySelector('span').textContent === 'Fondo');
          if (!f) return null;
          const antes = sl.classList.contains('dark');
          [...f.querySelectorAll('button')]
            .find(b => b.textContent === 'Oscuro').click();
          return {antes: antes, ahora: sl.classList.contains('dark')};
        }""")
        if not r:
            raise AssertionError("la lámina no ofrece elegir el fondo")
        if r["antes"] or not r["ahora"]:
            raise AssertionError("el fondo no cambió en el acto: %s" % r)
        d.evaluate("""() => {
          const sl = document.querySelector('.slide[data-sec=embudo]');
          [...sl.querySelectorAll('.ed-fila')]
            .find(x => x.querySelector('span').textContent === 'Fondo')
            .querySelectorAll('button').forEach(b => {
              if (b.textContent === 'Claro') b.click();
            });
        }""")
        d.wait_for_timeout(200)
        return "de claro a oscuro en el acto, y vuelve"
    check("el fondo de cada lámina se elige al editar", el_fondo_se_elige)

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

    def una_lista_larga_se_reparte():
        """«esta tabla acá es una lista enorme… así tenga que usar más hojas,
        usémoslas, pero demos el dato prolijo».

        Se mide con el navegador en modo IMPRESIÓN, que es la hoja del PDF: en
        pantalla una lista que se derrama se puede scrollear y no se nota.
        """
        p.evaluate("""async (d) => {
          await fetch('/api/datos/informe-editar', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id: d.rep, informe: d.inf,
                                  opciones: {detalle: 'todos', fondos: {embudo: 'oscuro'}}})});
        }""", {"rep": IDS["rep"], "inf": IDS["inf"]})
        d2 = ctx.new_page()
        d2.set_default_timeout(240000)
        d2.emulate_media(media="print")
        d2.goto(BASE + "/api/datos/deck?id=%s&informe=%s" % (IDS["rep"], IDS["inf"]))
        d2.wait_for_timeout(2500)
        r = d2.evaluate("""() => {
          const secs = {}, malas = [];
          document.querySelectorAll('.slide').forEach(s => {
            const k = s.dataset.sec || '?';
            secs[k] = (secs[k] || 0) + 1;
            const inner = s.querySelector('.slide-inner');
            if (inner.scrollHeight - s.clientHeight > 1) malas.push(k);
          });
          return {secs: secs, malas: malas,
                  oscuro: document.querySelector('.slide[data-sec=embudo]')
                            .classList.contains('dark')};
        }""")
        d2.close()
        if r["malas"]:
            raise AssertionError("se pasan de la hoja: %s" % r["malas"])
        if r["secs"].get("vendedores", 0) < 2:
            raise AssertionError("19 vendedores siguen en una sola lámina: %s"
                                 % r["secs"])
        if not r["oscuro"]:
            raise AssertionError("el fondo elegido no quedó guardado")
        return ("el equipo en %d láminas, ninguna se pasa, y el fondo oscuro "
                "quedó guardado" % r["secs"]["vendedores"])
    check("una lista larga se reparte en varias láminas y ninguna se derrama",
          una_lista_larga_se_reparte)

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
