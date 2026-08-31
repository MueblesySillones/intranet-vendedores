# -*- coding: utf-8 -*-
"""t4 — regresión visual: las pantallas clave, pixel contra pixel.

Modo normal: captura cada pantalla a salida/visual/ y la compara con
qa/baseline/<nombre>.png. Si difiere más que la tolerancia (QA_VISUAL_TOL,
% de píxeles, default 0.5) FALLA y deja el diff pintado en salida/diffs/.

`--capturar-baseline` regenera qa/baseline/ con lo que se ve AHORA. La
baseline se captura recién cuando el rediseño está integrado y revisado a
ojo — una baseline de una obra a medio hacer solo congela los defectos.
IMPORTANTE: capturar la baseline y comparar SIEMPRE sobre un sandbox recién
creado (correr_todo.py ya lo garantiza): t2 ensucia el contenido y el diff
te mostraría publicaciones de prueba en vez de regresiones.

Comparación: con Pillow (verificado instalado: 12.2) se comparan píxeles con
umbral por canal (>12/255 cuenta como distinto, para perdonar antialiasing).
Sin Pillow cae a un plan B de biblioteca estándar: descomprime los scanlines
del PNG (zlib) y compara hashes por bloques de 16 filas — más grueso (la
tolerancia pasa a ser % de bloques) pero suficiente para gritar "algo cambió".

Exit codes: 0 ok · 1 hay diferencias/errores · 2 no hay baseline todavía.
"""
import io
import json
import os
import struct
import sys
import zlib

from playwright.sync_api import sync_playwright

import arnes
from arnes import (INTRA_URL, PANEL_URL, Reporte, abrir_datos_reporte,
                   abrir_editor, contexto_seguro, guardar, ir_seccion)

TOL = float(os.environ.get("QA_VISUAL_TOL") or 0.5)   # % de píxeles (o bloques)
TOL_CANAL = 12                                        # delta por canal que se perdona
VISUAL = os.path.join(arnes.SALIDA, "visual")

# congelar animaciones/cursores: sin esto cada captura sale distinta "porque sí"
CSS_QUIETO = ("*,*:before,*:after{animation:none!important;transition:none!important;"
              "caret-color:transparent!important;scroll-behavior:auto!important}")

CAPTURAS = [
    # (nombre, panel|intranet, ancho, alto, móvil, navegación)
    ("panel-cartelera-1440", "panel", 1440, 900, False, lambda pg: ir_seccion(pg, "muro")),
    ("panel-modulos-1440",   "panel", 1440, 900, False, lambda pg: ir_seccion(pg, "modulos")),
    ("panel-editor-1440",    "panel", 1440, 900, False, abrir_editor),
    ("panel-datos-1440",     "panel", 1440, 900, False, abrir_datos_reporte),
    ("panel-metricas-1440",  "panel", 1440, 900, False, lambda pg: ir_seccion(pg, "metricas")),
    ("intranet-portada-1440",      "intranet", 1440, 900, False, ""),
    ("intranet-embalaje-1440",     "intranet", 1440, 900, False, "#embalaje_especial"),
    ("intranet-descargables-1440", "intranet", 1440, 900, False, "#descargables"),
    ("intranet-whatsapp-1440",     "intranet", 1440, 900, False, "#whatsapp"),
    ("intranet-portada-390",       "intranet", 390, 844, True, ""),
]


def hay_pillow():
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def capturar_todas(destino):
    """Recorre CAPTURAS y deja los .png en `destino`. Devuelve las que fallaron."""
    os.makedirs(destino, exist_ok=True)
    caidas = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        # panel: contexto seguro SIEMPRE (por más que t4 solo mire, navega y clickea)
        ctx_p = contexto_seguro(br, viewport={"width": 1440, "height": 900},
                                reduced_motion="reduce")
        pg_p = ctx_p.new_page()
        pg_p.goto(PANEL_URL, wait_until="networkidle")
        pg_p.wait_for_timeout(2000)
        for nombre, origen, ancho, alto, mov, nav in CAPTURAS:
            try:
                if origen == "panel":
                    pg = pg_p
                    nav(pg)
                    pg.add_style_tag(content=CSS_QUIETO)
                    pg.wait_for_timeout(600)
                else:
                    ctx_i = br.new_context(viewport={"width": ancho, "height": alto},
                                           is_mobile=mov, has_touch=mov,
                                           reduced_motion="reduce")
                    pg = ctx_i.new_page()
                    pg.goto(INTRA_URL + nav, wait_until="networkidle")
                    pg.add_style_tag(content=CSS_QUIETO)
                    pg.wait_for_timeout(2000)
                pg.screenshot(path=os.path.join(destino, nombre + ".png"), full_page=True)
                print("  captura %s" % nombre)
                if origen == "panel":
                    pg.goto(PANEL_URL, wait_until="networkidle")
                    pg.wait_for_timeout(1200)
                else:
                    ctx_i.close()
            except Exception as e:  # noqa: BLE001 - una pantalla caída no frena las demás
                caidas.append((nombre, str(e)[:100]))
                print("  !! %s no se pudo capturar: %s" % (nombre, str(e)[:80]))
        ctx_p.close()
        br.close()
    return caidas


# ---------------------------------------------------------------------------
# comparación con Pillow: % de píxeles con algún canal más lejos que TOL_CANAL
# ---------------------------------------------------------------------------

def comparar_pillow(ruta_base, ruta_act, ruta_diff):
    from PIL import Image, ImageChops
    a = Image.open(ruta_base).convert("RGB")
    b = Image.open(ruta_act).convert("RGB")
    if a.size != b.size:
        return None, "tamaño distinto: baseline %sx%s vs actual %sx%s" % (a.size + b.size)
    d = ImageChops.difference(a, b)
    r, g, az = d.split()
    # el máximo de los tres canales: un cambio solo de color no se diluye
    mx = ImageChops.lighter(ImageChops.lighter(r, g), az)
    mask = mx.point(lambda v: 255 if v > TOL_CANAL else 0)
    distintos = mask.histogram()[255]
    pct = 100.0 * distintos / float(a.size[0] * a.size[1])
    if pct > TOL:
        # diff visible: la captura actual apagada, con lo distinto en rojo
        apagada = b.point(lambda v: v // 3)
        rojo = Image.new("RGB", b.size, (255, 60, 60))
        Image.composite(rojo, apagada, mask).save(ruta_diff)
    return pct, ""


# ---------------------------------------------------------------------------
# plan B sin Pillow: hashes por bloques de scanlines del PNG (stdlib pura)
# ---------------------------------------------------------------------------
# Se descomprime el stream IDAT (zlib) SIN desfiltrar: cada fila queda en una
# posición fija (1 byte de filtro + ancho*canales), así que hashear bloques de
# 16 filas localiza el cambio con precisión de bloque. Es más grueso que por
# píxel (un pixel cambiado marca todo su bloque, y el filtro PNG puede
# arrastrar la marca a la fila siguiente), por eso acá la tolerancia se lee
# como % de BLOQUES distintos. Alcanza como alarma cuando no está Pillow.

FILAS_POR_BLOQUE = 16


def _scanlines_png(ruta):
    d = open(ruta, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("no es un PNG")
    pos, ancho, alto, canales, idat = 8, 0, 0, 4, []
    while pos < len(d):
        (largo,), tipo = struct.unpack(">I", d[pos:pos + 4]), d[pos + 4:pos + 8]
        cuerpo = d[pos + 8:pos + 8 + largo]
        if tipo == b"IHDR":
            ancho, alto, prof, color = struct.unpack(">IIBB", cuerpo[:10])
            canales = {0: 1, 2: 3, 4: 2, 6: 4}.get(color, 4) * (2 if prof == 16 else 1)
        elif tipo == b"IDAT":
            idat.append(cuerpo)
        elif tipo == b"IEND":
            break
        pos += 12 + largo
    crudo = zlib.decompress(b"".join(idat))
    paso = 1 + ancho * canales
    return ancho, alto, [crudo[i:i + paso] for i in range(0, len(crudo), paso)]


def comparar_bloques(ruta_base, ruta_act, ruta_diff):
    import hashlib
    wa, ha, filas_a = _scanlines_png(ruta_base)
    wb, hb, filas_b = _scanlines_png(ruta_act)
    if (wa, ha) != (wb, hb):
        return None, "tamaño distinto: baseline %dx%d vs actual %dx%d" % (wa, ha, wb, hb)

    def hashes(filas):
        return [hashlib.md5(b"".join(filas[i:i + FILAS_POR_BLOQUE])).digest()
                for i in range(0, len(filas), FILAS_POR_BLOQUE)]
    ha_, hb_ = hashes(filas_a), hashes(filas_b)
    distintos = sum(1 for x, y in zip(ha_, hb_) if x != y)
    pct = 100.0 * distintos / max(1, len(ha_))
    if pct > TOL:
        with io.open(ruta_diff.replace(".png", ".txt"), "w", encoding="utf-8") as f:
            f.write("bloques distintos (de %d filas): %d de %d\n"
                    % (FILAS_POR_BLOQUE, distintos, len(ha_)))
            f.write("filas aprox: " + ", ".join(
                str(i * FILAS_POR_BLOQUE) for i, (x, y) in enumerate(zip(ha_, hb_)) if x != y)[:800])
    return pct, ""


def correr(capturar_baseline=False):
    arnes.preparar_salida()
    rep = Reporte("t4-visual")

    if capturar_baseline:
        print("capturando BASELINE en %s" % arnes.BASELINE)
        caidas = capturar_todas(arnes.BASELINE)
        with io.open(os.path.join(arnes.BASELINE, "INFO.json"), "w", encoding="utf-8") as f:
            json.dump({"panel_url": PANEL_URL, "intra_url": INTRA_URL,
                       "capturas": [c[0] for c in CAPTURAS],
                       "nota": "regenerar con: python correr_todo.py --capturar-baseline"},
                      f, ensure_ascii=False, indent=1)
        for nombre, err in caidas:
            rep.falla("baseline %s no capturada" % nombre, err)
        if not caidas:
            rep.ok("baseline regenerada", "%d capturas" % len(CAPTURAS))
        return rep.cerrar()

    hay_base = any(f.endswith(".png") for f in os.listdir(arnes.BASELINE)) \
        if os.path.isdir(arnes.BASELINE) else False
    if not hay_base:
        print("no hay baseline en %s" % arnes.BASELINE)
        print("cuando el rediseño esté integrado y revisado, correr:")
        print("    python correr_todo.py --capturar-baseline")
        return 2

    con_pillow = hay_pillow()
    comparar = comparar_pillow if con_pillow else comparar_bloques
    print("comparando con %s (tolerancia %.2f%% de %s)"
          % ("Pillow" if con_pillow else "hash de bloques (stdlib)", TOL,
             "píxeles" if con_pillow else "bloques"))

    caidas = capturar_todas(VISUAL)
    for nombre, err in caidas:
        rep.falla("no se pudo capturar %s" % nombre, err)

    medidas = {}
    for nombre, _, _, _, _, _ in CAPTURAS:
        base = os.path.join(arnes.BASELINE, nombre + ".png")
        act = os.path.join(VISUAL, nombre + ".png")
        diff = os.path.join(arnes.DIFFS, nombre + "-diff.png")
        if not os.path.isfile(base):
            rep.falla("%s sin baseline" % nombre,
                      "recapturar la baseline completa (--capturar-baseline)")
            continue
        if not os.path.isfile(act):
            continue    # ya falló arriba como captura caída
        try:
            pct, err = comparar(base, act, diff)
        except Exception as e:  # noqa: BLE001 - un PNG ilegible no tira el resto
            rep.falla("%s no se pudo comparar" % nombre, str(e)[:90])
            continue
        if pct is None:
            rep.falla("%s cambió de tamaño" % nombre, err)
            medidas[nombre] = {"error": err}
        else:
            medidas[nombre] = {"pct": round(pct, 3)}
            rep.check("%s dentro de tolerancia" % nombre, pct <= TOL,
                      "%.3f%% distinto (tol %.2f%%)%s"
                      % (pct, TOL, " -> " + diff if pct > TOL else ""))

    guardar("t4-visual.json", {"tolerancia": TOL, "con_pillow": con_pillow,
                               "medidas": medidas})
    return rep.cerrar()


if __name__ == "__main__":
    sys.exit(correr(capturar_baseline="--capturar-baseline" in sys.argv))
