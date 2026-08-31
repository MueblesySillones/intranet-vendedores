# -*- coding: utf-8 -*-
"""Verifica el CSS del bloque video EN LA INTRANET real: que respete la proporcion
(sin franjas negras ni deformacion), que un vertical no se coma la pantalla,
y que en el celular y dentro de una presentacion siga entrando."""
import os
import sys
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8195
BASE = "http://127.0.0.1:%d" % PORT
ok_total, fallos = 0, []


def check(nombre, cond, extra=""):
    global ok_total
    if cond:
        ok_total += 1
        print("  OK   %s %s" % (nombre, extra))
    else:
        fallos.append(nombre)
        print("  FALLA %s %s" % (nombre, extra))


VERT = ('<figure class="m-video vert tam-md" style="--arw:1080;--arh:1920">'
        '<div class="v-box"><video></video></div><figcaption>Pie</figcaption></figure>')
HORIZ = ('<figure class="m-video horiz tam-md" style="--arw:1920;--arh:1080">'
         '<div class="v-box"><video></video></div></figure>')
GRANDE = ('<figure class="m-video horiz tam-gr" style="--arw:1920;--arh:1080">'
          '<div class="v-box"><video></video></div></figure>')
CHICO = ('<figure class="m-video horiz tam-ch" style="--arw:1920;--arh:1080">'
         '<div class="v-box"><video></video></div></figure>')
RARO = ('<figure class="m-video horiz tam-md" style="--arw:1;--arh:1">'
        '<div class="v-box"><video></video></div></figure>')

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

INYECTAR = """(html) => {
  document.body.className = '';
  let m = document.getElementById('probe');
  if (m) m.remove();
  m = document.createElement('div');
  m.id = 'probe'; m.className = 'manual';
  m.style.cssText = 'width:900px';
  m.innerHTML = html;
  document.body.appendChild(m);
  const b = m.querySelector('.v-box').getBoundingClientRect();
  return {w: Math.round(b.width), h: Math.round(b.height)};
}"""


def caja(pag, html):
    return pag.evaluate(INYECTAR, html)


print("=" * 70)
print("PRUEBA DEL CSS DE VIDEO EN LA INTRANET")
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()

    # ---------- escritorio ----------
    print("\n[1] Escritorio (1280x900)")
    pag = nav.new_page(viewport={"width": 1280, "height": 900})
    errores = []
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(BASE + "/intranet/index.html", wait_until="networkidle")

    v = caja(pag, VERT)
    check("vertical: mantiene la proporcion 9:16",
          abs(v["h"] / v["w"] - 1920 / 1080) < 0.02, "%dx%d" % (v["w"], v["h"]))
    check("vertical: NO se come el ancho del documento", v["w"] < 400, "ancho %d de 900" % v["w"])
    check("vertical: entra en la pantalla", v["h"] <= 900 * 0.75, "alto %d" % v["h"])

    h = caja(pag, HORIZ)
    check("horizontal: mantiene la proporcion 16:9",
          abs(h["w"] / h["h"] - 16 / 9) < 0.02, "%dx%d" % (h["w"], h["h"]))
    check("horizontal es mas ancho que alto", h["w"] > h["h"], "%dx%d" % (h["w"], h["h"]))

    g, c = caja(pag, GRANDE), caja(pag, CHICO)
    check("el selector de tamano hace efecto (chico < medio < grande)",
          c["w"] < h["w"] < g["w"], "ch=%d md=%d gr=%d" % (c["w"], h["w"], g["w"]))

    r = caja(pag, RARO)
    check("un video cuadrado queda cuadrado", abs(r["w"] - r["h"]) <= 2, "%dx%d" % (r["w"], r["h"]))

    check("el video llena la caja (sin franjas negras)", pag.evaluate("""() => {
        const b = document.querySelector('#probe .v-box').getBoundingClientRect();
        const v = document.querySelector('#probe video').getBoundingClientRect();
        return Math.abs(b.width - v.width) < 2 && Math.abs(b.height - v.height) < 2;
    }"""))
    check("el pie de foto se muestra",
          caja(pag, VERT) and pag.evaluate("() => !!document.querySelector('#probe figcaption')"))

    # un m-video SIN el style inline (html escrito a mano) no debe estirarse a lo ancho
    s = caja(pag, '<figure class="m-video horiz tam-md"><div class="v-box">'
                  '<video></video></div></figure>')
    check("sin proporcion declarada cae en 16:9 y no ocupa todo el ancho",
          s["w"] < 900 and abs(s["w"] / s["h"] - 16 / 9) < 0.02, "%dx%d" % (s["w"], s["h"]))
    pag.close()

    # ---------- celular ----------
    print("\n[2] Celular (390x844)")
    cel = nav.new_page(viewport={"width": 390, "height": 844})
    cel.on("pageerror", lambda e: errores.append(str(e)))
    cel.goto(BASE + "/intranet/index.html", wait_until="networkidle")
    cel.evaluate("() => { const s=document.createElement('style'); s.textContent='#probe{width:358px!important}'; document.head.appendChild(s); }")

    v = caja(cel, VERT)
    check("celular: el vertical no se sale de la pantalla", v["w"] <= 358, "ancho %d" % v["w"])
    check("celular: el vertical entra en el alto de la ventana",
          v["h"] <= 844 * 0.7, "alto %d de 844" % v["h"])
    check("celular: sigue con la proporcion correcta",
          abs(v["h"] / v["w"] - 1920 / 1080) < 0.02, "%dx%d" % (v["w"], v["h"]))
    h = caja(cel, HORIZ)
    check("celular: el horizontal usa el ancho disponible", h["w"] >= 340, "ancho %d" % h["w"])
    cel.close()

    # ---------- presentacion ----------
    print("\n[3] Dentro de una diapositiva")
    pres = nav.new_page(viewport={"width": 1280, "height": 800})
    pres.on("pageerror", lambda e: errores.append(str(e)))
    pres.goto(BASE + "/intranet/index.html", wait_until="networkidle")
    v = pres.evaluate("""(html) => {
        document.body.className = 'report-mode';
        const st = document.createElement('div');
        st.className = 'dk-stage';
        st.innerHTML = '<div class="manual" id="probe">' + html + '</div>';
        document.body.appendChild(st);
        const b = st.querySelector('.v-box').getBoundingClientRect();
        return {w: Math.round(b.width), h: Math.round(b.height)};
    }""", VERT)
    check("presentacion: el vertical entra en la diapositiva",
          v["h"] <= 800 * 0.62, "alto %d de 800" % v["h"])
    check("presentacion: sigue proporcionado",
          abs(v["h"] / v["w"] - 1920 / 1080) < 0.02, "%dx%d" % (v["w"], v["h"]))
    pres.close()

    check("cero errores de JS en la intranet", not errores, "; ".join(errores[:3]))
    nav.close()

httpd.shutdown()
print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok_total, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
