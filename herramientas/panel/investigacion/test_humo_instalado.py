# -*- coding: utf-8 -*-
"""Prueba de humo contra el panel YA INSTALADO (el .exe en 8124), no el fuente.
Solo LEE: no guarda, no arrastra, no publica."""
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = "http://127.0.0.1:8124"
ok, fallos = 0, []


def check(n, c, extra=""):
    global ok
    if c:
        ok += 1
        print("  OK   %s %s" % (n, extra))
    else:
        fallos.append(n)
        print("  FALLA %s %s" % (n, extra))


print("=" * 70)
print("HUMO SOBRE EL PANEL INSTALADO (%s)" % BASE)
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1400, "height": 1000})
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(BASE, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)

    check("el panel carga y lista los modulos",
          pag.evaluate("() => document.querySelectorAll('.mod-card').length") > 0,
          "%d modulos" % pag.evaluate("() => document.querySelectorAll('.mod-card').length"))
    check("el motor de arrastre nuevo esta cargado",
          pag.evaluate("() => typeof listaOrdenable === 'function'"))
    check("el arrastre viejo ya no existe",
          pag.evaluate("() => typeof dragDocs === 'undefined' && typeof dragMod === 'undefined'"))
    check("la lista de modulos quedo enganchada UNA vez",
          pag.evaluate("() => document.getElementById('modList').dataset.ordenable") == "1")
    check("las tarjetas ya no usan el arrastre nativo del navegador",
          pag.evaluate("() => ![...document.querySelectorAll('.mod-card')].some(c => c.draggable)"))
    check("el bloque de video esta disponible",
          pag.evaluate("""() => typeof videoInspector === 'function' &&
              Object.values(GRUPOS_BLOQUE).some(g => g.includes('video'))"""))
    check("la paleta nueva esta en el exe instalado",
          pag.evaluate("() => typeof BLOQUE_MINI === 'object' && typeof gbPane === 'function'"))
    check("el buscador de bloques existe",
          pag.evaluate("() => !!document.querySelector('#gbBuscar')"))
    check("los helpers de video responden",
          pag.evaluate("() => embedDeVideo('https://youtu.be/abc123').url").endswith("/embed/abc123"))

    # entrar a la biblioteca de reportes, SIN tocar nada
    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=20000)
    check("la lista de reportes abre",
          pag.evaluate("() => document.querySelectorAll('.col-item').length") >= 3,
          "%d reportes" % pag.evaluate("() => document.querySelectorAll('.col-item').length"))
    check("la lista de reportes quedo enganchada UNA vez",
          pag.evaluate("() => document.getElementById('colList').dataset.ordenable") == "1")
    check("Marzo-Mayo figura como presentacion",
          pag.evaluate("""() => { const d = COLECCION.find(x => x.titulo.includes('Marzo'));
                                  return !!(d && d.presentacion); }"""))
    check("y tiene sus 14 diapositivas",
          pag.evaluate("""() => { const d = COLECCION.find(x => x.titulo.includes('Marzo'));
                                  return contarSlides(d.bloques); }""") == 14)
    check("ningun reporte quedo con cortes huerfanos",
          pag.evaluate("""() => !COLECCION.some(d => !d.presentacion &&
                                (d.bloques||[]).some(b => b.t === 'diapo'))"""))
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(300)

    check("cero errores de consola", not errores, "; ".join(errores[:3]))
    nav.close()

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
