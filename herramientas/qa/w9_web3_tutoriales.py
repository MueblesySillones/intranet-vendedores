# -*- coding: utf-8 -*-
"""TUTORIALES: subir un video, marcarle los minutos y saltar a cada tema.

Lo que se pidió: *«una pantalla donde se pueden cargar videos de tutoriales,
que se pueda ver en pantalla completa y grande, y que tenga una línea de tiempo
donde se coloca el minuto con el tutorial… minuto 3:25 cómo editar módulos, y
en la misma línea minuto 5 cómo subir una publicación»*.

Lo que prueba, de punta a punta y con un video de verdad:

  · la sección existe en el menú y arranca explicando para qué es
  · se sube un video y queda como tutorial
  · se le marcan capítulos MIRÁNDOLO («+ Marcar acá» toma el minuto de donde
    está parado el video), se guardan y sobreviven a recargar
  · la línea de tiempo se dibuja en TRAMOS, y el ancho de cada uno es lo que
    dura ese capítulo
  · apretar un capítulo salta ahí, y el que está sonando queda marcado
  · guardar un tutorial NO se lleva puestos los módulos

⚠️ Lo último no es paranoia: pasó. Los tutoriales viven adentro de modulos.js,
   y la función que leía los módulos buscaba su cierre con rfind("]") —que
   desde que hay un bloque más abajo agarra el cierre equivocado—. El guardado
   siguiente dejó la intranet con CERO módulos y sin un solo error a la vista.

    python correr_web3.py --solo w9
"""
import io
import json
import os
import shutil
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright  # noqa: E402

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
SANDBOX = os.environ.get("QA_SANDBOX_WEB3") or ""
AQUI = os.path.dirname(os.path.abspath(__file__))
RES = []


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:                       # noqa: la suite sigue
        RES.append(("FAIL", nombre))
        print("FAIL | %s | %s" % (nombre, e))


def video_de_prueba():
    """Un mp4 de verdad. Se toma uno que ya está en el sandbox: fabricar un
    video válido a mano no se puede, y bajarlo de internet haría que la suite
    dependa de que haya red."""
    base = os.path.join(SANDBOX or "", "intranet", "assets")
    for raiz, _dirs, arch in os.walk(base):
        for a in arch:
            if a.lower().endswith(".mp4"):
                destino = os.path.join(os.environ.get("TEMP", AQUI), "qa_tut.mp4")
                shutil.copy2(os.path.join(raiz, a), destino)
                return destino
    return None


def cuantos_modulos():
    d = json.loads(urllib.request.urlopen(BASE + "/api/modulos", timeout=30)
                   .read().decode("utf-8"))
    return len(d.get("modulos") or [])


def limpiar():
    q = urllib.request.Request(
        BASE + "/api/tutoriales", data=json.dumps({"tutoriales": []}).encode(),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(q, timeout=60).read()


VIDEO = video_de_prueba()
if not VIDEO:
    print("SIN VIDEO en el sandbox: esta suite necesita uno para probar.")
    print("\n0/0 PASS (salteada)")
    sys.exit(0)

MODULOS_ANTES = cuantos_modulos()
limpiar()

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    errs = []
    p = ctx.new_page()
    p.set_default_timeout(180000)
    p.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:180]))
    p.on("dialog", lambda d: d.accept())

    def entrar():
        p.goto(BASE + "/", wait_until="domcontentloaded")
        p.wait_for_selector("#muroLista .pub", timeout=60000)
        p.click('[data-sec="tutoriales"]')
        p.wait_for_selector("#viewTutoriales", state="visible")
        p.wait_for_timeout(1200)

    def la_seccion_existe():
        entrar()
        if not p.is_visible('[data-sec="tutoriales"]'):
            raise AssertionError("no hay Tutoriales en el menú")
        t = (p.text_content("#tutVacio") or "")
        if "línea de tiempo" not in t:
            raise AssertionError("el estado vacío no explica qué es: %r" % t[:60])
        return "menú + estado vacío que explica para qué sirve"
    check("hay una sección Tutoriales y arranca explicando", la_seccion_existe)

    def subir_un_video():
        p.click("#tutNuevo")
        p.wait_for_selector("#tutModal.on", state="visible", timeout=25000)
        p.wait_for_timeout(500)
        p.fill("#tutTitulo", "QA cómo editar un módulo")
        p.fill("#tutNota", "Del panel a la intranet")
        p.set_input_files("#tutArchivo", VIDEO)
        p.click("#tutSubir")
        p.wait_for_selector("#tutVideo", timeout=300000)
        p.wait_for_function(
            """() => { const v = document.getElementById('tutVideo');
                       return v && isFinite(v.duration) && v.duration > 0; }""",
            timeout=90000)
        d = p.evaluate("() => document.getElementById('tutVideo').duration")
        if not p.get_attribute("#tutVideo", "src").startswith("/intranet/"):
            raise AssertionError("el video no sale por /intranet/: daría 404")
        return "subido y sonando · %.0f s" % d
    check("se sube un video y queda como tutorial", subir_un_video)

    def sin_controles_del_navegador():
        """El <video controls> trae su propia barra de progreso: con ella
        quedaban DOS barras, una arriba de la otra, y ninguna manda."""
        if p.get_attribute("#tutVideo", "controls") is not None:
            raise AssertionError("quedaron los controles del navegador")
        for b_ in ("tutPlay", "tutMudo", "tutFull"):
            if not p.is_visible("#" + b_):
                raise AssertionError("falta el botón %s" % b_)
        return "una sola barra: la de capítulos"
    check("el reproductor tiene sus propios controles", sin_controles_del_navegador)

    def marcar_capitulos():
        """«+ Marcar acá» toma el minuto de donde está parado el video: es la
        forma de cargarlos mirándolo, sin anotar los minutos en un papel."""
        p.click("#tutEditar")
        p.wait_for_timeout(600)
        for seg, txt in ((3, "Entrar al panel"), (11, "Editar el bloque"),
                         (21, "Publicar el cambio")):
            p.evaluate("(s) => { document.getElementById('tutVideo').currentTime = s; }", seg)
            p.wait_for_timeout(500)
            p.click("#tutMarcar")
            p.wait_for_timeout(400)
            p.keyboard.type(txt)
            p.wait_for_timeout(220)
        tiempos = p.eval_on_selector_all(
            "#tutCaps .tut-cap.edit .tut-t", "n => n.map(x => x.value)")
        if tiempos != ["0:03", "0:11", "0:21"]:
            raise AssertionError("los minutos quedaron %s" % tiempos)
        p.click("#tutGuardar")
        p.wait_for_timeout(2500)
        textos = p.eval_on_selector_all(
            "#tutCaps .tut-cap .tut-x2", "n => n.map(x => x.textContent)")
        if textos != ["Entrar al panel", "Editar el bloque", "Publicar el cambio"]:
            raise AssertionError("los capítulos quedaron %s" % textos)
        return " · ".join(tiempos)
    check("se marcan capítulos mirando el video y se guardan", marcar_capitulos)

    def la_linea_es_proporcional():
        """⚠️ La prueba que importa de la línea: el ancho de cada tramo tiene
        que ser lo que DURA ese capítulo. Con todos iguales, la línea sería un
        adorno que no dice nada."""
        anchos = p.eval_on_selector_all(
            "#tutBarra .tut-seg", "n => n.map(x => x.getBoundingClientRect().width)")
        if len(anchos) != 4:
            raise AssertionError("%d tramos para 3 capítulos (falta el de la "
                                 "punta): %s" % (len(anchos), anchos))
        # 0-3s, 3-11s, 11-21s, 21-fin: el primero es el más corto y el tercero
        # más ancho que el segundo
        if not (anchos[0] < anchos[1] < anchos[2]):
            raise AssertionError("los tramos no siguen lo que dura cada "
                                 "capítulo: %s" % [round(a) for a in anchos])
        return "4 tramos de %s px" % ", ".join(str(round(a)) for a in anchos)
    check("la línea de tiempo dibuja un tramo por capítulo",
          la_linea_es_proporcional)

    def saltar_a_un_capitulo():
        p.evaluate("() => { document.getElementById('tutVideo').pause(); }")
        p.evaluate("() => [...document.querySelectorAll('#tutCaps .tut-cap')][2].click()")
        p.wait_for_timeout(1200)
        t = p.evaluate("() => document.getElementById('tutVideo').currentTime")
        if not (20 <= t <= 25):
            raise AssertionError("saltó a %.1f y el capítulo estaba en 21" % t)
        marcado = (p.evaluate(
            "() => (document.querySelector('#tutCaps .tut-cap.on')||{}).textContent") or "")
        if "Publicar" not in marcado:
            raise AssertionError("no marcó el capítulo que suena: %r" % marcado)
        ahora = p.text_content("#tutCapAhora") or ""
        if "Publicar" not in ahora:
            raise AssertionError("la línea no dice el capítulo: %r" % ahora)
        return "salta a %.0f s y queda marcado «%s»" % (t, ahora.strip())
    check("apretar un capítulo salta ahí", saltar_a_un_capitulo)

    def sobrevive_a_recargar():
        entrar()
        txt = p.text_content("#tutRaiz") or ""
        if "QA cómo editar un módulo" not in txt:
            raise AssertionError("el tutorial no quedó guardado")
        if "3 capítulos" not in txt:
            raise AssertionError("la tarjeta no cuenta los capítulos: %r" % txt[:90])
        return "la tarjeta dice la duración y los 3 capítulos"
    check("el tutorial y sus capítulos sobreviven a recargar", sobrevive_a_recargar)

    def no_se_lleva_puestos_los_modulos():
        """⚠️ Pasó de verdad: los tutoriales viven adentro de modulos.js y el
        lector de módulos buscaba su cierre con rfind(«]»), que desde que hay
        un bloque más abajo agarra el equivocado. Guardar un tutorial dejó la
        intranet con CERO módulos, sin un solo error a la vista."""
        ahora = cuantos_modulos()
        if ahora != MODULOS_ANTES:
            raise AssertionError("los módulos pasaron de %d a %d"
                                 % (MODULOS_ANTES, ahora))
        if not MODULOS_ANTES:
            raise AssertionError("no había módulos: la prueba no prueba nada")
        return "los %d módulos siguen enteros" % ahora
    check("guardar un tutorial no toca los módulos",
          no_se_lleva_puestos_los_modulos)

    def entra_en_la_pantalla():
        """Con el video a 64vh, el título y el botón de volver quedaban arriba
        del borde: había que scrollear para saber qué se estaba mirando."""
        p.click("#tutRaiz [data-ver-tut]")
        p.wait_for_selector("#tutVideo", timeout=60000)
        p.wait_for_timeout(1500)
        r = p.evaluate("""() => {
          const h = document.querySelector('#tutRaiz .tut-h');
          const caps = document.getElementById('tutCaps');
          return {cabecera: h.getBoundingClientRect().top,
                  ultimo: caps.lastElementChild
                    ? caps.lastElementChild.getBoundingClientRect().bottom : 0};
        }""")
        if r["cabecera"] < 55:
            raise AssertionError("la cabecera quedó tapada: top %s" % r["cabecera"])
        if r["ultimo"] > 900:
            raise AssertionError("el último capítulo queda fuera de la pantalla")
        return "cabecera y capítulos a la vista sin scrollear"
    check("el reproductor entra en la pantalla", entra_en_la_pantalla)

    def quitar_el_tutorial():
        p.click("#tutVolver")
        p.wait_for_timeout(800)
        p.click("#tutRaiz [data-borrar-tut]")
        p.wait_for_timeout(2500)
        if "QA cómo editar un módulo" in (p.text_content("#tutRaiz") or ""):
            raise AssertionError("sigue en la lista")
        # y el video se borra con él: un mp4 huérfano se publica igual
        quedan = []
        carpeta = os.path.join(SANDBOX or "", "intranet", "assets", "_tutoriales")
        if os.path.isdir(carpeta):
            quedan = [x for x in os.listdir(carpeta) if x.lower().endswith(".mp4")]
        if quedan:
            raise AssertionError("quedó el video huérfano: %s" % quedan)
        return "se va de la lista y el video se borra con él"
    check("quitar un tutorial se lleva su video", quitar_el_tutorial)

    print("\nerrores de consola:", errs or "ninguno")
    b.close()

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
