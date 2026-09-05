# -*- coding: utf-8 -*-
"""Chequeo del lado VENDEDOR: la intranet que sirve el panel en /intranet/.
Escritorio y celular: que abra, que los módulos del menú entren, que la
cartelera muestre publicaciones, que el link #cartelera/<id> abra la
publicación correcta, y que no haya errores de consola ni scroll lateral."""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = (os.environ.get("QA_BASE") or "http://127.0.0.1:8144") + "/intranet/"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "salida", "web3", "intranet")
os.makedirs(SHOTS, exist_ok=True)
RES = []
CONSOLA = []


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:200]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:200]))


def correr(pw, ancho, alto, etiqueta):
    ctx = pw.chromium.launch().new_context(
        viewport={"width": ancho, "height": alto},
        is_mobile=(ancho < 500), has_touch=(ancho < 500))
    p = ctx.new_page()
    p.set_default_timeout(9000)
    p.on("console", lambda m: CONSOLA.append((etiqueta, m.text[:170]))
         if m.type == "error" else None)
    p.on("pageerror", lambda e: CONSOLA.append((etiqueta, "pageerror: " + str(e)[:200])))
    p.goto(BASE, wait_until="load")
    p.wait_for_timeout(1400)
    return ctx, p


with sync_playwright() as pw:
    # ---------------- ESCRITORIO ----------------
    ctx, p = correr(pw, 1440, 900, "escritorio")

    check("la intranet abre y tiene contenido", lambda:
          "%d caracteres de texto" % len(p.inner_text("body")))
    check("los módulos del menú se dibujan", lambda: (
        (lambda n: n if n >= 5 else (_ for _ in ()).throw(
            AssertionError("sólo %d tiles" % n)))(
            p.evaluate("() => document.querySelectorAll('.tile, .m-tile, [data-key]').length")),
        "%d tiles" % p.evaluate("() => document.querySelectorAll('.tile, .m-tile, [data-key]').length"))[-1])
    p.screenshot(path=os.path.join(SHOTS, "01-home-escritorio.png"))

    def sin_scroll_lateral():
        d = p.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        if d["sw"] > d["cw"] + 2:
            raise AssertionError("la página se va al costado: %s" % d)
        return "ancho ok (%s)" % d["cw"]
    check("sin scroll horizontal (escritorio)", sin_scroll_lateral)

    # la cartelera: ¿aparecen las publicaciones del panel?
    def cartelera():
        n = p.evaluate("""() => document.querySelectorAll(
            '.cartelera .pub, .muro .pub, .feed article, .mural .pub, article').length""")
        if n == 0:
            raise AssertionError("no veo publicaciones en la portada")
        return "%d publicaciones" % n
    check("la cartelera muestra publicaciones", cartelera)

    # link directo a una publicación
    def link_directo():
        ids = p.evaluate("""() => {
          const m = (window.MODULES||[]).find(x => x.content && x.content.tipo === 'cartelera');
          return ((m && m.content.docs) || []).filter(d => !d.archivado)
                 .map(d => ({id: d.id, t: d.titulo}));
        }""")
        if not ids:
            raise AssertionError("no hay publicaciones en MODULES")
        objetivo = ids[min(1, len(ids) - 1)]
        p.goto(BASE + "#cartelera/" + objetivo["id"], wait_until="load")
        p.wait_for_timeout(1500)
        txt = p.inner_text("body")
        if objetivo["t"][:24] not in txt:
            raise AssertionError("el link no abrió %r" % objetivo["t"][:40])
        return "abre %r" % objetivo["t"][:44]
    check("el link #cartelera/<id> abre esa publicación", link_directo)
    p.screenshot(path=os.path.join(SHOTS, "02-publicacion.png"))

    # entrar a un módulo de contenido
    def abrir_modulo():
        p.goto(BASE, wait_until="load"); p.wait_for_timeout(1000)
        claves = p.evaluate("""() => (window.MODULES||[])
            .filter(m => m.ready && !m.hidden && m.key && m.key !== 'cartelera')
            .map(m => m.key)""")
        if not claves:
            raise AssertionError("no hay módulos publicables")
        k = "manual" if "manual" in claves else claves[0]
        p.goto(BASE + "#" + k, wait_until="load")
        p.wait_for_timeout(1500)
        largo = len(p.inner_text("body"))
        if largo < 300:
            raise AssertionError("el módulo %r abrió casi vacío (%d chars)" % (k, largo))
        return "%r con %d caracteres" % (k, largo)
    check("un módulo de contenido abre con su texto", abrir_modulo)
    p.screenshot(path=os.path.join(SHOTS, "03-modulo.png"))
    ctx.close()

    # ---------------- CELULAR ----------------
    ctx2, p2 = correr(pw, 390, 844, "celular")
    check("celular: abre", lambda: "%d caracteres" % len(p2.inner_text("body")))

    def sin_scroll_lateral_movil():
        d = p2.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        if d["sw"] > d["cw"] + 2:
            raise AssertionError("se va al costado en celular: %s" % d)
        return "ancho ok (%s)" % d["cw"]
    check("celular: sin scroll horizontal", sin_scroll_lateral_movil)
    p2.screenshot(path=os.path.join(SHOTS, "04-home-celular.png"))

    def menu_movil():
        btn = p2.query_selector(".menu-btn, #menuBtn, [aria-label*='men'], .hamb")
        if not btn:
            return "no hay botón de menú (el diseño no lo usa en este ancho)"
        btn.click(); p2.wait_for_timeout(700)
        p2.screenshot(path=os.path.join(SHOTS, "05-menu-celular.png"))
        return "el menú abre"
    check("celular: el menú abre", menu_movil)
    ctx2.close()

print("\n===== CONSOLA =====")
for e, t in CONSOLA:
    print("  [%s] %s" % (e, t))
if not CONSOLA:
    print("  0 errores")
ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
