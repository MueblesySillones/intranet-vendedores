# -*- coding: utf-8 -*-
"""t1 — crawl del panel: 5 pantallas x 3 anchos.

Mide por pantalla/ancho: desborde horizontal, imágenes rotas, áreas táctiles
chicas (<40 y <32 px), errores JS; a 1440 además axe (WCAG A/AA) e inventario
de controles. Capturas en salida/screenshots/ y evidencia JSON en
salida/evidencia/.

UMBRALES QUE FALLAN (exit 1):
  - desborde horizontal > 0 en cualquier pantalla/ancho
  - imágenes rotas > 0
  - violaciones axe NUEVAS (ids que no están en fixtures/axe-conocidas-panel.json)
  - errores JS de página
Las áreas táctiles chicas son AVISO (se arreglan por el carril de diseño,
no frenan la suite).

`python t1_crawl.py --aceptar-axe` fija las violaciones actuales como
conocidas (correrlo una vez con el rediseño integrado y revisado).
"""
import sys

from playwright.sync_api import sync_playwright

import arnes
from arnes import (PANEL_URL, Reporte, abrir_datos_reporte, abrir_editor,
                   axe_nuevas, cargar_conocidas, contexto_seguro, correr_axe,
                   guardar, guardar_conocidas, inventario, ir_seccion,
                   metricas_pagina)

CONOCIDAS = "axe-conocidas-panel.json"
ANCHOS = [1440, 1024, 768]
PANTALLAS = [
    ("cartelera", lambda pg: ir_seccion(pg, "muro")),
    ("modulos",   lambda pg: ir_seccion(pg, "modulos")),
    ("editor",    abrir_editor),
    ("datos",     abrir_datos_reporte),
    ("metricas",  lambda pg: ir_seccion(pg, "metricas")),
]


def correr(aceptar_axe=False):
    arnes.preparar_salida()
    rep = Reporte("t1-crawl")
    resultados, inv_total, axe_total = {}, [], {}

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for ancho in ANCHOS:
            ctx = contexto_seguro(br, viewport={"width": ancho, "height": 900})
            pg = ctx.new_page()
            errsjs = []
            pg.on("pageerror", lambda e: errsjs.append(str(e)[:140]))
            pg.goto(PANEL_URL, wait_until="networkidle")
            pg.wait_for_timeout(2000)
            for nombre, nav in PANTALLAS:
                clave = "%s@%d" % (nombre, ancho)
                try:
                    nav(pg)
                except Exception as e:  # noqa: BLE001 - pantalla que no abre = falla, seguimos con la próxima
                    rep.falla("%s no abrió" % clave, str(e)[:90])
                    pg.goto(PANEL_URL, wait_until="networkidle")
                    pg.wait_for_timeout(1200)
                    continue
                m = metricas_pagina(pg)
                pg.screenshot(path=arnes.SHOTS + r"\panel-%s-%d.png" % (nombre, ancho),
                              full_page=True)
                resultados[clave] = m
                if ancho == 1440:
                    inv_total += inventario(pg, nombre)
                    try:
                        axe_total[nombre] = correr_axe(pg)
                    except Exception as e:  # noqa: BLE001 - axe caído no debe tirar el crawl
                        axe_total[nombre] = []
                        rep.falla("axe no corrió en %s" % nombre, str(e)[:90])
                print("  %-18s desborde=%-4d clicks=%-3d <40px=%-3d <32px=%-2d imgs_rotas=%d"
                      % (clave, m["desborde"], m["clickeables"], m["menores40"],
                         m["menores32"], m["imgs_rotas"]))

                # --- umbrales duros ---
                rep.check("%s sin desborde" % clave, m["desborde"] <= 0,
                          "desborde=%dpx" % m["desborde"])
                rep.check("%s sin imágenes rotas" % clave, m["imgs_rotas"] == 0,
                          "%d rotas" % m["imgs_rotas"])
                # --- targets: aviso, no falla ---
                if m["menores32"]:
                    rep.aviso("%s con %d targets <32px" % (clave, m["menores32"]),
                              "; ".join("%s %dx%d" % (p["sel"], p["w"], p["h"])
                                        for p in m["peores"][:3]))
                # cada pantalla vuelve a la home para que la nav siguiente arranque igual
                pg.goto(PANEL_URL, wait_until="networkidle")
                pg.wait_for_timeout(1200)
            resultados["errores_js@%d" % ancho] = errsjs[:8]
            rep.check("sin errores JS @%d" % ancho, not errsjs,
                      "; ".join(errsjs[:2]))
            ctx.close()
        br.close()

    guardar("t1-crawl.json", {"metricas": resultados, "axe": axe_total})
    guardar("t1-inventario.json", inv_total)

    # --- axe: comparar contra lo conocido ---
    if aceptar_axe:
        datos = guardar_conocidas(CONOCIDAS, axe_total)
        print("\naxe: %d pantallas fijadas como conocidas -> fixtures/%s"
              % (len(datos), CONOCIDAS))
    else:
        conocidas = cargar_conocidas(CONOCIDAS)
        nuevas = axe_nuevas(axe_total, conocidas)
        if conocidas is None:
            rep.aviso("no existe fixtures/%s" % CONOCIDAS,
                      "toda violación cuenta como nueva; correr --aceptar-axe para fijar el piso")
        for pant, vid, impact in nuevas:
            rep.falla("axe nueva en %s" % pant, "%s (%s)" % (vid, impact))
        if not nuevas:
            rep.ok("axe sin violaciones nuevas",
                   "%d pantallas contra fixtures/%s" % (len(axe_total), CONOCIDAS))

    print("\n== AXE (1440) ==")
    for pantalla, viols in axe_total.items():
        print("  %s: %d tipos de violación" % (pantalla, len(viols)))
        for v in viols[:6]:
            print("     [%s] %-28s x%-3s %s" % (v.get("impact"), v["id"],
                                                v.get("nodes", "?"), (v.get("help") or "")[:60]))
    print("inventario: %d controles (%d presentes pero no visibles)"
          % (len(inv_total), len([i for i in inv_total if not i["visible"]])))

    return rep.cerrar(extra={"pantallas": len(resultados)})


if __name__ == "__main__":
    sys.exit(correr(aceptar_axe="--aceptar-axe" in sys.argv))
