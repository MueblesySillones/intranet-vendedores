# -*- coding: utf-8 -*-
"""Prueba el motor de arrastre nuevo y el arreglo de diapositivas.

El check clave es arrastrar VARIAS VECES SEGUIDAS: con el bug viejo (listeners
que se acumulaban en cada render) el segundo arrastre movia doble y el tercero
triple. No escribe nada en modulos.js (se anula persistModulos y ademas se
verifica el archivo al final)."""
import os
import sys
import json
import hashlib
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8192
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")
ok_total, fallos = 0, []


def check(nombre, cond, extra=""):
    global ok_total
    if cond:
        ok_total += 1
        print("  OK   %s %s" % (nombre, extra))
    else:
        fallos.append(nombre)
        print("  FALLA %s %s" % (nombre, extra))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


antes_hash = sha(MODULOS_JS)

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

print("=" * 70)
print("PRUEBA: ARRASTRE FLUIDO + DIAPOSITIVAS")
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1400, "height": 1000})
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=15000)

    # nada de esta prueba debe tocar el disco
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")
    check("se anulo el guardado en disco para la prueba",
          pag.evaluate("() => persistModulos.toString().includes('ok:true')"))

    # ---------- 1. diapositivas: funciones puras ----------
    print("\n[1] Generacion de diapositivas")
    r = pag.evaluate("""() => {
      const D = t => ({t:'diapo', titulo:t||'', grupo:''});
      const P = h => ({t:'parrafo', html:h});
      const casos = {
        paginaConCortes: [P('a'), D('X'), P('b')],
        corteAlFinalConTitulo: [P('a'), D('Cierre')],
        corteAlFinalSinTitulo: [P('a'), D('')],
        dosCortesSeguidos: [P('a'), D('A'), D('B'), P('b')],
        corteAlPrincipio: [D('Portada'), P('a')],
        soloUnCorte: [D('Sola')],
        vacio: [],
        bloqueVacio: [P('a'), D('X'), {t:'imagen', src:''}],
      };
      const out = {};
      for (const [k, bl] of Object.entries(casos)) {
        const pag_ = bloquesHTML(bl, false);
        const pre = bloquesHTML(bl, true);
        out[k] = {
          paginaVacios: (pag_.match(/<div class="db"><\\/div>/g) || []).length,
          slides: (pre.match(/<section class="dk-slide"/g) || []).length,
          contados: contarSlides(bl),
          titulos: [...pre.matchAll(/data-titulo="([^"]*)"/g)].map(m => m[1]),
        };
      }
      return out;
    }""")

    check("modo Pagina: un corte ya no deja un div vacio",
          r["paginaConCortes"]["paginaVacios"] == 0)
    check("un bloque a medio cargar tampoco ensucia",
          r["bloqueVacio"]["paginaVacios"] == 0, str(r["bloqueVacio"]))
    check("corte al final CON titulo genera su diapositiva",
          r["corteAlFinalConTitulo"]["slides"] == 2, str(r["corteAlFinalConTitulo"]))
    check("...y con el titulo puesto",
          "Cierre" in r["corteAlFinalConTitulo"]["titulos"], str(r["corteAlFinalConTitulo"]["titulos"]))
    check("corte al final SIN titulo no inventa una diapositiva vacia",
          r["corteAlFinalSinTitulo"]["slides"] == 1, str(r["corteAlFinalSinTitulo"]))
    check("corte al principio no genera una diapositiva fantasma",
          r["corteAlPrincipio"]["slides"] == 1, str(r["corteAlPrincipio"]))
    check("un unico corte con titulo vale como portada",
          r["soloUnCorte"]["slides"] == 1, str(r["soloUnCorte"]))
    check("documento vacio no genera nada", r["vacio"]["slides"] == 0)

    desajustes = [k for k, v in r.items() if v["slides"] != v["contados"]]
    check("el contador del panel coincide SIEMPRE con el html generado",
          not desajustes, "difieren en: %s" % desajustes)

    # ---------- 2. la paleta segun el modo ----------
    print("\n[2] La paleta de bloques segun el modo")
    tarjeta_reporte = pag.evaluate("""() => {
      const i = MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion');
      return i;
    }""")
    check("hay un modulo biblioteca para probar", tarjeta_reporte >= 0)
    pag.evaluate("(i) => openDetalle(i)", tarjeta_reporte)
    pag.wait_for_selector(".col-item", timeout=15000)

    docs = pag.query_selector_all(".col-item")
    check("la lista de reportes cargo", len(docs) >= 3, "%d documentos" % len(docs))

    # abrir un documento que NO es presentacion -> no debe ofrecer "Nueva diapositiva"
    idx_pagina = pag.evaluate("() => COLECCION.findIndex(d => !d.presentacion)")
    pag.evaluate("(i) => abrirDoc(i)", idx_pagina)
    pag.wait_for_timeout(300)
    # el rotulo ahora trae el contador al lado, se compara por el nombre solo
    grupos = pag.evaluate("""() => [...document.querySelectorAll('#gbAdd .gb-grupo-t')]
        .map(s => (s.firstChild ? s.firstChild.textContent : s.textContent).trim())""")
    check("en modo Pagina NO se ofrece 'Nueva diapositiva'", "Presentación" not in grupos, str(grupos))

    idx_pres = pag.evaluate("() => COLECCION.findIndex(d => d.presentacion)")
    check("Marzo-Mayo quedo como presentacion", idx_pres >= 0)
    pag.evaluate("() => irALista()")
    pag.wait_for_timeout(200)
    pag.evaluate("(i) => abrirDoc(i)", idx_pres)
    pag.wait_for_timeout(300)
    grupos = pag.evaluate("""() => [...document.querySelectorAll('#gbAdd .gb-grupo-t')]
        .map(s => (s.firstChild ? s.firstChild.textContent : s.textContent).trim())""")
    check("en presentacion SI se ofrece 'Nueva diapositiva'", "Presentación" in grupos, str(grupos))

    pag.evaluate("() => irALista()")
    pag.wait_for_selector(".col-item", timeout=10000)

    # ---------- 3. arrastre de reportes ----------
    print("\n[3] Arrastre de la lista de reportes")

    def orden_docs():
        return pag.evaluate("() => COLECCION.map(d => d.titulo)")

    def arrastrar(item_sel, grip_sel, desde, hasta):
        """Devuelve True si el arrastre realmente arranco (aparecio el fantasma)."""
        items = pag.query_selector_all(item_sel)
        items[desde].scroll_into_view_if_needed()
        items[hasta].scroll_into_view_if_needed()
        pag.wait_for_timeout(120)
        items = pag.query_selector_all(item_sel)          # re-medir tras el scroll
        g = items[desde].query_selector(grip_sel).bounding_box()
        d = items[hasta].bounding_box()
        x = g["x"] + g["width"] / 2
        pag.mouse.move(x, g["y"] + g["height"] / 2)
        pag.mouse.down()
        pag.mouse.move(x, g["y"] + g["height"] / 2 + 30, steps=5)   # bien pasado el umbral
        arranco = pag.evaluate("() => !!document.querySelector('.ord-flota')")
        # apuntar bien adentro de la mitad de destino segun la direccion
        y = d["y"] + (d["height"] * 0.85 if hasta > desde else d["height"] * 0.15)
        pag.mouse.move(x, y, steps=12)
        pag.mouse.up()
        pag.wait_for_timeout(600)   # dejar terminar el aterrizaje
        return arranco

    inicial = orden_docs()
    print("     orden inicial: %s" % inicial)

    arranco = arrastrar(".col-item", ".col-grip", 0, 2)
    check("el arrastre arranca (aparece la tarjeta flotante)", arranco)
    esperado = inicial[1:] + [inicial[0]]
    d1 = orden_docs()
    check("1er arrastre: el reporte va al lugar pedido", d1 == esperado, "%s" % d1)

    # EL CHECK QUE IMPORTA: con el bug viejo el 2do arrastre movia doble
    arrastrar(".col-item", ".col-grip", 0, 1)
    d2 = orden_docs()
    esperado2 = [d1[1], d1[0], d1[2]]
    check("2do arrastre seguido: mueve UN lugar, no dos", d2 == esperado2, "%s (esperaba %s)" % (d2, esperado2))

    arrastrar(".col-item", ".col-grip", 2, 0)
    d3 = orden_docs()
    esperado3 = [d2[2], d2[0], d2[1]]
    check("3er arrastre seguido: sigue moviendo UN lugar", d3 == esperado3, "%s (esperaba %s)" % (d3, esperado3))

    check("no quedo ninguna tarjeta escondida",
          pag.evaluate("""() => ![...document.querySelectorAll('.col-item')].some(n => n.style.display === 'none')"""))
    check("no quedo el fantasma pegado en pantalla",
          pag.evaluate("() => !document.querySelector('.ord-flota')"))
    check("no quedo ningun hueco",
          pag.evaluate("() => !document.querySelector('.ord-hueco')"))
    check("el body quedo limpio",
          pag.evaluate("() => !document.body.classList.contains('ord-arrastrando')"))
    check("la lista visible coincide con el modelo",
          pag.evaluate("""() => [...document.querySelectorAll('.col-t')]
                                .map(n => n.childNodes[0].textContent.trim())
                                .join('|') === COLECCION.map(d => d.titulo).join('|')"""))
    check("un solo listener de arrastre en la lista",
          pag.evaluate("() => document.getElementById('colList').dataset.ordenable") == "1")

    # un click corto NO debe reordenar (umbral de 6px)
    print("\n[4] Un click no es un arrastre")
    antes_click = orden_docs()
    g = pag.query_selector_all(".col-item .col-grip")[0].bounding_box()
    pag.mouse.move(g["x"] + g["width"] / 2, g["y"] + g["height"] / 2)
    pag.mouse.down()
    pag.mouse.move(g["x"] + g["width"] / 2 + 2, g["y"] + g["height"] / 2 + 2)
    pag.mouse.up()
    pag.wait_for_timeout(300)
    check("tocar el ⠿ sin mover no cambia el orden", orden_docs() == antes_click)
    check("y no dejo basura", pag.evaluate("() => !document.querySelector('.ord-flota, .ord-hueco')"))

    # tocar la tarjeta sigue abriendo el documento
    pag.query_selector_all(".col-item .col-info")[0].click()
    pag.wait_for_timeout(400)
    check("tocar la tarjeta todavia abre el documento",
          pag.evaluate("() => DOC_IDX !== null"), "DOC_IDX=%s" % pag.evaluate("() => DOC_IDX"))
    pag.evaluate("() => irALista()")
    pag.wait_for_timeout(200)

    # ---------- 5. arrastre de modulos ----------
    print("\n[5] Arrastre de la lista de modulos")
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_selector(".mod-card", timeout=15000)

    def orden_mods():
        return pag.evaluate("() => MODULOS.map(m => m.key)")

    m0 = orden_mods()
    print("     orden inicial: %s" % m0[:4])
    arrastrar(".mod-card", ".mod-grip", 0, 2)
    m1 = orden_mods()
    check("1er arrastre de modulos", m1 == m0[1:3] + [m0[0]] + m0[3:], "%s" % m1[:4])
    arrastrar(".mod-card", ".mod-grip", 0, 1)
    m2 = orden_mods()
    check("2do arrastre de modulos: un solo lugar",
          m2 == [m1[1], m1[0]] + m1[2:], "%s" % m2[:4])
    check("las posiciones se renumeraron",
          pag.evaluate("""() => [...document.querySelectorAll('.mod-card .icon-pos')]
                                .map(n => n.textContent).slice(0,3).join(',') === '1,2,3'"""))
    check("no quedo fantasma ni hueco en modulos",
          pag.evaluate("() => !document.querySelector('.ord-flota, .ord-hueco')"))

    # dejar el orden como estaba
    pag.evaluate("(o) => { MODULOS.sort((a,b) => o.indexOf(a.key) - o.indexOf(b.key)); pintarModulos(); }", m0)
    check("orden de modulos restaurado", orden_mods() == m0)

    # ---------- 6. casos feos ----------
    print("\n[6] Casos feos (lo que levanto la revision)")
    pag.evaluate("(i) => openDetalle(i)", tarjeta_reporte)
    pag.wait_for_selector(".col-item", timeout=15000)
    base = orden_docs()

    def empezar_arrastre():
        items = pag.query_selector_all(".col-item")
        items[0].scroll_into_view_if_needed()
        pag.wait_for_timeout(100)
        items = pag.query_selector_all(".col-item")
        g = items[0].query_selector(".col-grip").bounding_box()
        d = items[2].bounding_box()
        pag.mouse.move(g["x"] + g["width"] / 2, g["y"] + g["height"] / 2)
        pag.mouse.down()
        pag.mouse.move(g["x"] + g["width"] / 2, d["y"] + d["height"] * 0.85, steps=10)
        return g

    # (a) pointercancel tiene que CANCELAR, no confirmar
    empezar_arrastre()
    check("durante el arrastre hay tarjeta flotante",
          pag.evaluate("() => !!document.querySelector('.ord-flota')"))
    pag.evaluate("""() => document.dispatchEvent(
        new PointerEvent('pointercancel', {pointerId: 1, bubbles: true}))""")
    pag.wait_for_timeout(300)
    check("pointercancel NO reordena (cancela de verdad)", orden_docs() == base, str(orden_docs()))
    check("pointercancel no deja la tarjeta escondida",
          pag.evaluate("""() => ![...document.querySelectorAll('.col-item')]
                                .some(n => n.style.display === 'none')"""))
    check("pointercancel no deja fantasma ni hueco",
          pag.evaluate("() => !document.querySelector('.ord-flota, .ord-hueco')"))
    pag.mouse.up()
    pag.wait_for_timeout(200)

    # (b) un segundo dedo no debe romper nada
    empezar_arrastre()
    pag.evaluate("""() => {
        const g = document.querySelectorAll('.col-item .col-grip')[1];
        g.dispatchEvent(new PointerEvent('pointerdown',
            {pointerId: 99, button: 0, bubbles: true, clientX: 100, clientY: 100}));
    }""")
    pag.wait_for_timeout(150)
    check("un segundo dedo no arranca un arrastre paralelo",
          pag.evaluate("() => document.querySelectorAll('.ord-flota').length") == 1,
          "%d flotantes" % pag.evaluate("() => document.querySelectorAll('.ord-flota').length"))
    check("tampoco aparece un segundo hueco",
          pag.evaluate("() => document.querySelectorAll('.ord-hueco').length") == 1)
    pag.mouse.up()
    pag.wait_for_timeout(600)
    check("tras el segundo dedo, el arrastre igual se completa bien",
          orden_docs() == base[1:] + [base[0]], str(orden_docs()))

    # (c) que la lista se re-dibuje EN MEDIO del arrastre no debe dejar basura
    b2 = orden_docs()
    empezar_arrastre()
    pag.evaluate("() => renderColeccion()")           # como si algo refrescara la lista
    pag.mouse.move(300, 400, steps=4)
    pag.mouse.up()
    pag.wait_for_timeout(600)
    check("re-dibujar a mitad del arrastre no deja el fantasma pegado",
          pag.evaluate("() => !document.querySelector('.ord-flota')"))
    check("...ni huecos sueltos",
          pag.evaluate("() => !document.querySelector('.ord-hueco')"))
    check("...ni tarjetas escondidas",
          pag.evaluate("""() => ![...document.querySelectorAll('.col-item')]
                                .some(n => n.style.display === 'none')"""))
    check("...y la lista sigue mostrando todos los reportes",
          pag.evaluate("() => document.querySelectorAll('.col-item').length") == len(b2))
    check("se puede seguir arrastrando despues de eso",
          pag.evaluate("() => !document.body.classList.contains('ord-arrastrando')"))
    arranco = arrastrar(".col-item", ".col-grip", 0, 1)
    check("y efectivamente arrastra de nuevo", arranco)

    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(200)

    # ---------- 7. animaciones ----------
    print("\n[7] Animaciones")
    pag.wait_for_selector(".mod-card", timeout=15000)

    # la copia flotante NO puede tener transicion de transform: iria retrasada del cursor
    trans = pag.evaluate("""() => {
        const c = document.querySelector('.mod-card').cloneNode(true);
        c.classList.add('ord-flota'); document.body.appendChild(c);
        const t = getComputedStyle(c).transitionProperty;
        c.remove(); return t;
    }""")
    check("la tarjeta flotante NO transiciona transform", "transform" not in trans, trans)
    check("...pero la tarjeta normal si tiene transicion",
          "transform" in pag.evaluate(
              "() => getComputedStyle(document.querySelector('.mod-card')).transitionProperty"))

    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=15000)
    pag.evaluate("() => abrirDoc(0)")
    pag.wait_for_timeout(400)

    n0 = pag.evaluate("() => BLOQUES.length")
    pag.evaluate("() => insertBloque('parrafo')")
    pag.wait_for_timeout(60)
    check("el bloque nuevo entra con animacion",
          pag.evaluate("""() => { const b = document.querySelector('.gb-block.gb-nuevo');
                                  return !!b && b.getAnimations().length > 0; }"""))
    check("y se agrego de verdad", pag.evaluate("() => BLOQUES.length") == n0 + 1)

    sel = pag.evaluate("() => SEL")
    pag.evaluate("(i) => borrarBloque(i)", sel)
    pag.wait_for_timeout(60)
    check("el bloque borrado se desvanece antes de irse",
          pag.evaluate("() => !!document.querySelector('.gb-block.gb-saliendo')"))
    pag.wait_for_timeout(400)
    check("...y despues efectivamente desaparece",
          pag.evaluate("() => BLOQUES.length") == n0, "%d" % pag.evaluate("() => BLOQUES.length"))
    check("no quedo ningun bloque a medio desvanecer",
          pag.evaluate("() => !document.querySelector('.gb-block.gb-saliendo')"))

    check("los grupos de la paleta aparecen con animacion",
          pag.evaluate("""() => {
            const g = document.querySelector('#gbAdd .gb-grupo');
            return !!g && getComputedStyle(g).animationName !== 'none';
          }"""))
    check("las tarjetas de bloque se levantan al pasar el mouse",
          pag.evaluate("""() => {
            const t = document.querySelector('#gbAdd .gb-tipo');
            return !!t && getComputedStyle(t).transitionProperty.includes('transform');
          }"""))
    check("el inspector se refresca con un fundido",
          pag.evaluate("""() => { renderInspector();
                                  return document.getElementById('gbInspector')
                                         .classList.contains('mov-cambio'); }"""))
    check("se respeta 'reducir movimiento' del sistema",
          pag.evaluate("() => typeof sinMovimiento === 'function'"))
    pag.evaluate("() => irALista()")
    pag.wait_for_timeout(200)
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(200)

    check("cero errores de consola en todo el recorrido", not errores, "; ".join(errores[:3]))
    nav.close()

httpd.shutdown()
print("\n[6] Integridad")
check("modulos.js NO se modifico durante la prueba", sha(MODULOS_JS) == antes_hash)

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok_total, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
