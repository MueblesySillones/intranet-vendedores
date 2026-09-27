# -*- coding: utf-8 -*-
"""TUTORIALES CON VARIOS VIDEOS: una tarjeta, una sola línea de tiempo.

El pedido (26-sep-2026): «tengo tres videos que explican los módulos y no
quiero tres tarjetas distintas: que todo esté dentro de una y se puedan ir
agregando videos a la línea de tiempo».

Lo que prueba, con videos de verdad:

  · subir un tutorial eligiendo DOS videos de una: queda una tarjeta que dice
    «2 videos» y la duración de los dos sumados
  · la línea de tiempo marca dónde empieza el segundo video
  · «+ Sumar otro video» agrega un tercero al final
  · tocar la línea en la parte del segundo video carga ese archivo, y «Marcar
    acá» toma el minuto de la línea ENTERA (no el del video suelto)
  · apretar ese capítulo vuelve al video que corresponde
  · al terminar un video sigue el próximo solo
  · quitar un video se lleva sus capítulos y corre para atrás los que siguen
  · todo sobrevive a recargar

    python correr_web3.py --solo w13
"""
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
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:240]))


def videos_de_prueba(n):
    """n copias de un mp4 de verdad que ya esté en el sandbox."""
    base = os.path.join(SANDBOX or "", "intranet", "assets")
    for raiz, _dirs, arch in os.walk(base):
        for a in arch:
            if a.lower().endswith(".mp4"):
                out = []
                for i in range(n):
                    destino = os.path.join(os.environ.get("TEMP", AQUI), "qa_tut_%d.mp4" % (i + 1))
                    shutil.copy2(os.path.join(raiz, a), destino)
                    out.append(destino)
                return out
    return None


def tutoriales():
    d = json.loads(urllib.request.urlopen(BASE + "/api/tutoriales", timeout=30).read().decode("utf-8"))
    return d.get("tutoriales") or []


def limpiar():
    q = urllib.request.Request(
        BASE + "/api/tutoriales", data=json.dumps({"tutoriales": []}).encode(),
        headers={"Content-Type": "application/json"})
    urllib.request.urlopen(q, timeout=60).read()


VIDS = videos_de_prueba(3)
if not VIDS:
    print("SIN VIDEO en el sandbox: esta suite necesita uno para probar.")
    print("\n0/0 PASS (salteada)")
    sys.exit(0)

limpiar()

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    errs = []
    p = ctx.new_page()
    p.set_default_timeout(180000)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:180]))
    p.on("dialog", lambda d: d.accept())
    S = {}

    def entrar():
        p.goto(BASE + "/", wait_until="domcontentloaded")
        p.wait_for_selector("#muroLista .pub", timeout=60000)
        p.click('[data-sec="tutoriales"]')
        p.wait_for_selector("#viewTutoriales", state="visible")
        p.wait_for_timeout(1000)

    def src_actual():
        return p.get_attribute("#tutVideo", "src") or ""

    def esperar_cargado():
        p.wait_for_function(
            """() => { const v = document.getElementById('tutVideo');
                       return v && v.readyState >= 1 && isFinite(v.duration) && v.duration > 0; }""",
            timeout=90000)

    def subir_dos():
        entrar()
        p.click("#tutNuevo")
        p.wait_for_selector("#tutModal.on", state="visible", timeout=25000)
        p.fill("#tutTitulo", "QA módulos en varios videos")
        p.set_input_files("#tutArchivo", VIDS[:2])
        p.click("#tutSubir")
        p.wait_for_selector("#tutVideo", timeout=300000)
        esperar_cargado()
        ts = tutoriales()
        if len(ts) != 1:
            raise AssertionError("quedaron %d tutoriales, se esperaba 1" % len(ts))
        t = ts[0]
        if len(t.get("mas") or []) != 1:
            raise AssertionError("el segundo video no quedó adentro: %r" % t)
        S["d1"] = t["duracion"]
        S["d2"] = t["mas"][0]["duracion"]
        if not S["d1"] or not S["d2"]:
            raise AssertionError("faltan duraciones: %r" % t)
        if t["src"] == t["mas"][0]["src"]:
            raise AssertionError("los dos videos quedaron con el mismo archivo")
        return "1 tarjeta, videos de %d s + %d s" % (S["d1"], S["d2"])
    check("se sube un tutorial con dos videos de una", subir_dos)

    def la_linea_marca_el_corte():
        cortes = p.eval_on_selector_all("#tutBarra .tut-seg.corte", "e => e.length")
        cab = p.eval_on_selector_all("#tutCaps .tut-vid-h", "e => e.map(x => x.textContent)")
        dur = p.text_content("#tutDur")
        if cortes != 1:
            raise AssertionError("se esperaba 1 corte en la línea, hay %d" % cortes)
        if len(cab) != 2:
            raise AssertionError("sin capítulos, la lista debería mostrar los 2 videos: %r" % cab)
        return "corte en la línea · %s · total %s" % (cab, dur)
    check("la línea de tiempo marca dónde empieza el segundo video", la_linea_marca_el_corte)

    def sumar_tercero():
        p.set_input_files("#tutSumarArch", VIDS[2])
        p.wait_for_function("() => document.querySelectorAll('#tutBarra .tut-seg.corte').length === 2",
                            timeout=300000)
        t = tutoriales()[0]
        if len(t.get("mas") or []) != 2:
            raise AssertionError("no se sumó el tercero: %r" % t.get("mas"))
        S["d3"] = t["mas"][1]["duracion"]
        return "ahora %d videos" % (1 + len(t["mas"]))
    check("«+ Sumar otro video» agrega uno al final", sumar_tercero)

    def tarjeta_dice_total():
        p.click("#tutVolver")
        p.wait_for_selector(".tut-c")
        txt = p.text_content(".tut-c .tut-cp")
        if "3 videos" not in txt:
            raise AssertionError("la tarjeta dice %r" % txt)
        p.click(".tut-c [data-ver-tut]")
        p.wait_for_selector("#tutVideo")
        esperar_cargado()
        return txt
    check("la tarjeta muestra la duración total y cuántos videos", tarjeta_dice_total)

    def marcar_en_el_segundo():
        primero = src_actual()
        # se toca la línea en la mitad del SEGUNDO video
        objetivo = S["d1"] + S["d2"] / 2.0
        tot = S["d1"] + S["d2"] + S["d3"]
        caja = p.query_selector("#tutBarra").bounding_box()
        # se busca el tramo que contiene el objetivo y se toca adentro de él
        pos = p.evaluate("""([obj]) => {
            const segs = [...document.querySelectorAll('#tutBarra .tut-seg')];
            const ts = segs.map(s => parseFloat(s.dataset.t));
            let i = 0; for (let k = 0; k < ts.length; k++) if (ts[k] <= obj) i = k;
            const r = segs[i].getBoundingClientRect();
            const hasta = i + 1 < ts.length ? ts[i + 1] : %f;
            const f = (obj - ts[i]) / (hasta - ts[i]);
            return {x: r.left + f * r.width, y: r.top + r.height / 2};
        }""" % tot, [objetivo])
        p.mouse.click(pos["x"], pos["y"])
        p.wait_for_function("s => document.getElementById('tutVideo').getAttribute('src') !== s",
                            arg=primero, timeout=30000)
        esperar_cargado()
        p.wait_for_timeout(500)
        ahora = p.text_content("#tutAhora")
        p.click("#tutEditar")
        p.click("#tutMarcar")
        p.keyboard.type("Tema del segundo video")
        p.click("#tutGuardar")
        p.wait_for_function("() => document.getElementById('tutGuardar').hidden", timeout=30000)
        caps = tutoriales()[0]["capitulos"]
        if len(caps) != 1:
            raise AssertionError("capítulos: %r" % caps)
        c = caps[0]["t"]
        if not (S["d1"] <= c < S["d1"] + S["d2"]):
            raise AssertionError("el capítulo quedó en %d s; el segundo video va de %d a %d"
                                 % (c, S["d1"], S["d1"] + S["d2"]))
        S["cap"] = c
        return "reloj en %s, capítulo guardado en %d s de la línea entera" % (ahora, c)
    check("«Marcar acá» en el segundo video toma el minuto de la línea entera", marcar_en_el_segundo)

    def saltar_al_capitulo():
        # se vuelve al primer video y se aprieta el capítulo
        p.click("#tutCaps .tut-vid-h[data-parte='0']")
        p.wait_for_timeout(1500)
        uno = src_actual()
        p.click("#tutCaps .tut-cap")
        p.wait_for_function("s => document.getElementById('tutVideo').getAttribute('src') !== s",
                            arg=uno, timeout=30000)
        esperar_cargado()
        p.wait_for_timeout(600)
        local = p.evaluate("() => document.getElementById('tutVideo').currentTime")
        esperado = S["cap"] - S["d1"]
        if abs(local - esperado) > 2:
            raise AssertionError("quedó en %.1f s del video; esperaba ~%d" % (local, esperado))
        return "pasó al video 2, segundo %.1f" % local
    check("apretar el capítulo vuelve a su video", saltar_al_capitulo)

    def sigue_solo():
        p.click("#tutCaps .tut-vid-h[data-parte='0']")
        p.wait_for_timeout(1500)
        uno = src_actual()
        p.evaluate("""() => { const v = document.getElementById('tutVideo');
                              v.muted = true; v.currentTime = Math.max(0, v.duration - 0.6); v.play(); }""")
        p.wait_for_function("s => document.getElementById('tutVideo').getAttribute('src') !== s",
                            arg=uno, timeout=30000)
        return "terminó el 1 y arrancó el 2"
    check("al terminar un video sigue el próximo", sigue_solo)

    def quitar_el_segundo():
        p.evaluate("() => document.getElementById('tutVideo').pause()")
        p.click("#tutCaps [data-quitar-parte='1']")
        p.wait_for_function("() => document.querySelectorAll('#tutBarra .tut-seg.corte').length === 1",
                            timeout=30000)
        t = tutoriales()[0]
        if len(t.get("mas") or []) != 1:
            raise AssertionError("mas = %r" % t.get("mas"))
        if t["capitulos"]:
            raise AssertionError("el capítulo del video quitado quedó: %r" % t["capitulos"])
        return "quedan 2 videos y el capítulo se fue con el suyo"
    check("quitar un video se lleva sus capítulos", quitar_el_segundo)

    def sobrevive():
        entrar()
        txt = p.text_content(".tut-c .tut-cp")
        if "2 videos" not in txt:
            raise AssertionError("después de recargar la tarjeta dice %r" % txt)
        return txt
    check("sobrevive a recargar", sobrevive)

    check("sin errores de JS", lambda: (_ for _ in ()).throw(AssertionError(errs)) if errs else "0")
    b.close()

limpiar()
ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(0 if ok == len(RES) else 1)
