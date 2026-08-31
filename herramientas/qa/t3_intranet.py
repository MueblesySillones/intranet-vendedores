# -*- coding: utf-8 -*-
"""t3 — la intranet como la ve el VENDEDOR (sitio estático del sandbox).

Cuatro vistas (portada, embalaje, descargables, whatsapp) en tres anchos
(1440 / 768 / 390-móvil): desborde horizontal, imágenes rotas, errores JS,
y a 1440 axe (WCAG A/AA). Además, métricas de lectura del módulo de manual
(tamaño de letra, interlineado, caracteres por línea, ritmo entre bloques)
y del feed (ancho de columna) — esas son AVISO cuando se van de rango,
porque el rango es criterio de diseño, no regresión dura.

UMBRALES QUE FALLAN (exit 1): desborde > 0, imágenes rotas > 0, errores JS,
violaciones axe NUEVAS respecto de fixtures/axe-conocidas-intranet.json
(`--aceptar-axe` fija el piso actual).
"""
import sys

from playwright.sync_api import sync_playwright

import arnes
from arnes import (INTRA_URL, Reporte, axe_nuevas, cargar_conocidas,
                   correr_axe, guardar, guardar_conocidas)

CONOCIDAS = "axe-conocidas-intranet.json"
VISTAS = [("portada", ""), ("embalaje", "#embalaje_especial"),
          ("descargables", "#descargables"), ("whatsapp", "#whatsapp")]
# criterios de lectura cómodos (avisos): tipografía >= 15px, interlineado 1.4-1.8,
# 45-95 caracteres por línea, feed <= 680px de columna
LECTURA_CH_MAX = 95
FEED_MAX = 680


def correr(aceptar_axe=False):
    arnes.preparar_salida()
    rep = Reporte("t3-intranet")
    V, axe_total = {}, {}

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for ancho, alto, mov, tag in ((1440, 900, False, "1440"),
                                      (768, 1000, False, "768"),
                                      (390, 844, True, "390")):
            ctx = br.new_context(viewport={"width": ancho, "height": alto},
                                 is_mobile=mov, has_touch=mov)
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
            for nombre, hash_ in VISTAS:
                pg.goto(INTRA_URL + hash_, wait_until="networkidle")
                pg.wait_for_timeout(2200)
                m = pg.evaluate("""() => ({
                    desborde: document.documentElement.scrollWidth - window.innerWidth,
                    rotas: [...document.images].filter(i => i.src && i.id !== 'lbimg' && i.complete && i.naturalWidth === 0).length })""")
                clave = "%s@%s" % (nombre, tag)
                V[clave] = m
                pg.screenshot(path=arnes.SHOTS + r"\intranet-%s-%s.png" % (nombre, tag),
                              full_page=(nombre != "portada"))
                rep.check("%s sin desborde" % clave, m["desborde"] <= 0,
                          "desborde=%dpx" % m["desborde"])
                rep.check("%s sin imágenes rotas" % clave, m["rotas"] == 0,
                          "%d rotas" % m["rotas"])
                if tag == "1440":
                    try:
                        axe_total[nombre] = correr_axe(pg)
                    except Exception as e:  # noqa: BLE001 - axe caído no tira el resto
                        axe_total[nombre] = []
                        rep.falla("axe no corrió en %s" % nombre, str(e)[:90])
                print("  %-18s desborde=%-4d rotas=%d" % (clave, m["desborde"], m["rotas"]))
            V["errores@" + tag] = errs[:6]
            rep.check("sin errores JS @%s" % tag, not errs, "; ".join(errs[:2]))
            ctx.close()

        # --- lectura del manual y feed, a 1440 ---
        ctx = br.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.goto(INTRA_URL + "#embalaje_especial", wait_until="networkidle")
        pg.wait_for_timeout(2200)
        V["lectura"] = pg.evaluate("""() => {
            const p = document.querySelector('#view .manual p, #view .m-p, #view p');
            if (!p) return null;
            const s = getComputedStyle(p);
            const fs = parseFloat(s.fontSize), lh = parseFloat(s.lineHeight);
            const w = p.getBoundingClientRect().width;
            const ch = Math.round(w / (fs * 0.5));   // ~0.5em por carácter
            const bloques = [...document.querySelectorAll('#view .manual > *')].slice(0, 20);
            const gaps = [];
            for (let i = 1; i < bloques.length; i++) {
                const a = bloques[i-1].getBoundingClientRect(), b = bloques[i].getBoundingClientRect();
                const g = Math.round(b.top - a.bottom);
                if (g >= 0 && g < 200) gaps.push(g);
            }
            const nota = document.querySelector('#view .note');
            const warn = document.querySelector('#view .warn, #view .m-warn, #view [class*=alerta]');
            const st = el => el ? (x => x.backgroundColor + '|' + x.borderLeftColor)(getComputedStyle(el)) : null;
            return { fontSize: s.fontSize, lineHeight: s.lineHeight,
                     interlineado: Math.round(lh / fs * 100) / 100,
                     ancho_parrafo: Math.round(w), caracteres_por_linea: ch,
                     gaps_entre_bloques: gaps, nota_estilo: st(nota), warn_estilo: st(warn),
                     warn_existe: !!warn }; }""")
        lect = V["lectura"]
        if not lect:
            rep.aviso("lectura: no encontré párrafos del manual",
                      "revisar selectores #view .manual p / .m-p")
        else:
            fs = float(str(lect["fontSize"]).replace("px", "") or 0)
            if fs < 15:
                rep.aviso("lectura: letra chica en el manual", lect["fontSize"])
            if not (1.35 <= (lect["interlineado"] or 0) <= 1.85):
                rep.aviso("lectura: interlineado fuera de 1.35-1.85",
                          lect["interlineado"])
            if (lect["caracteres_por_linea"] or 0) > LECTURA_CH_MAX:
                rep.aviso("lectura: línea larga (> %d ch)" % LECTURA_CH_MAX,
                          "%s ch" % lect["caracteres_por_linea"])
            rep.ok("lectura medida", "fs=%s lh=%s %sch" %
                   (lect["fontSize"], lect["interlineado"], lect["caracteres_por_linea"]))

        pg.goto(INTRA_URL, wait_until="networkidle")
        pg.wait_for_timeout(2000)
        V["feed_1440"] = pg.evaluate("""() => {
            const post = document.querySelector('#feed .mu-post');
            const lat = document.getElementById('lateral');
            return { ancho_post: post ? Math.round(post.getBoundingClientRect().width) : null,
                     lateral: lat ? Math.round(lat.getBoundingClientRect().width) : null,
                     marca_nueva: !!document.querySelector('.mu-nueva'),
                     fijadas_rotulo: !!document.querySelector('.fijados, .fix-row'),
                     skeletons: !!document.querySelector('[class*=skeleton]') }; }""")
        feed = V["feed_1440"]
        if feed.get("ancho_post") is None:
            rep.aviso("feed: no hay publicaciones visibles en la portada")
        elif feed["ancho_post"] > FEED_MAX:
            rep.aviso("feed: columna ancha (> %dpx)" % FEED_MAX, "%spx" % feed["ancho_post"])
        else:
            rep.ok("feed medido", "post=%spx lateral=%spx" % (feed["ancho_post"], feed["lateral"]))
        V["media_print"] = pg.evaluate("""() => [...document.styleSheets].some(s => {
            try { return [...s.cssRules].some(r => r.media && [...r.media].join().includes('print')); }
            catch(e) { return false; } })""")
        if not V["media_print"]:
            rep.aviso("sin estilos @media print", "imprimir un manual sale como la pantalla")
        ctx.close()
        br.close()

    # --- axe: conocidas vs nuevas ---
    if aceptar_axe:
        datos = guardar_conocidas(CONOCIDAS, axe_total)
        print("\naxe: %d vistas fijadas como conocidas -> fixtures/%s" % (len(datos), CONOCIDAS))
    else:
        conocidas = cargar_conocidas(CONOCIDAS)
        nuevas = axe_nuevas(axe_total, conocidas)
        if conocidas is None:
            rep.aviso("no existe fixtures/%s" % CONOCIDAS,
                      "toda violación cuenta como nueva; correr --aceptar-axe para fijar el piso")
        for vista, vid, impact in nuevas:
            rep.falla("axe nueva en %s" % vista, "%s (%s)" % (vid, impact))
        if not nuevas:
            rep.ok("axe sin violaciones nuevas",
                   "%d vistas contra fixtures/%s" % (len(axe_total), CONOCIDAS))

    V["axe"] = axe_total
    guardar("t3-intranet.json", V)
    print("\n== LECTURA ==", V.get("lectura"))
    print("== FEED 1440 ==", V.get("feed_1440"))
    return rep.cerrar()


if __name__ == "__main__":
    sys.exit(correr(aceptar_axe="--aceptar-axe" in sys.argv))
