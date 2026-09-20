# -*- coding: utf-8 -*-
"""Prueba la deteccion de plataforma de la intranet y a que camino manda cada una.

Por que existe: hasta el 19-sep la intranet NO detectaba plataforma. Todo salia
de `navigator.canShare`, que da true en iPhone, en Android y en Chrome de
Windows, asi que los tres terminaban en la hoja de compartir. En Android eso
estorba —el vendedor quiere la foto en la galeria, no un menu— y en la
computadora directamente sobra.

Lo que se verifica, contra el codigo REAL de intranet/index.html:
  1. cada navegador cae en la plataforma correcta (el iPad moderno incluido,
     que se reporta como Macintosh y hay que delatarlo por el touch)
  2. la hoja de compartir se usa SOLO en iOS

    python test_plataforma_descargas.py
"""
import io
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.abspath(os.path.join(AQUI, "..", "..", "intranet", "index.html"))

# nombre, userAgent, maxTouchPoints, plataforma esperada, usa hoja de compartir
CASOS = [
    ("iPhone Safari", "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 Version/26.0 Mobile/15E148 Safari/604.1", 5, "ios", True),
    ("iPhone Chrome", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 CriOS/126.0 Mobile/15E148 Safari/604.1", 5, "ios", True),
    ("iPhone Firefox", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 FxiOS/127.0 Mobile/15E148 Safari/605.1.15", 5, "ios", True),
    ("iPhone Edge", "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 EdgiOS/126.0 Mobile/15E148 Safari/605.1.15", 5, "ios", True),
    ("iPad moderno", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15", 5, "ios", True),
    ("iPad viejo", "Mozilla/5.0 (iPad; CPU OS 12_0 like Mac OS X) AppleWebKit/605.1.15 Version/12.0 Mobile/15E148 Safari/604.1", 5, "ios", True),
    ("Android Chrome", "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 Chrome/126.0.0.0 Mobile Safari/537.36", 5, "android", False),
    ("Android Samsung", "Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-A536E) AppleWebKit/537.36 SamsungBrowser/23.0 Chrome/115 Mobile Safari/537.36", 5, "android", False),
    ("Android Firefox", "Mozilla/5.0 (Android 14; Mobile; rv:127.0) Gecko/127.0 Firefox/127.0", 5, "android", False),
    ("Android tablet", "Mozilla/5.0 (Linux; Android 13; SM-X200) AppleWebKit/537.36 Chrome/126 Safari/537.36", 5, "android", False),
    ("Windows Chrome", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36", 0, "escritorio", False),
    ("Windows tactil", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36 Edg/126", 10, "escritorio", False),
    ("Mac Safari real", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15", 0, "escritorio", False),
]

JS = r"""
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const marca = 'const PLATAFORMA = (function(){';
const ini = html.indexOf(marca);
if (ini < 0) { console.log(JSON.stringify({error: 'no encontre PLATAFORMA en index.html'})); process.exit(0); }
const desde = ini + marca.length;
const hasta = html.indexOf('})();', desde);
// el cuerpo REAL del archivo; se le pasa `navigator` como parametro porque
// node trae uno propio que no se deja pisar
const detectar = new Function('navigator', html.slice(desde, hasta));
const casos = JSON.parse(process.argv[3]);
console.log(JSON.stringify(casos.map(c => detectar({ userAgent: c[1], maxTouchPoints: c[2] }))));
"""


def main():
    if not os.path.isfile(INDEX):
        print("no encuentro intranet/index.html"); return 1

    fuente = io.open(INDEX, encoding="utf-8").read()

    # la hoja de compartir tiene que estar condicionada a iOS, no solo a canShare
    m = re.search(r"function usaHojaDeCompartir\(\)\{(.*?)\}", fuente, re.S)
    if not m:
        print("FALLA | no existe usaHojaDeCompartir(): la intranet volvio a decidir solo por canShare")
        return 1
    if "'ios'" not in m.group(1):
        print("FALLA | usaHojaDeCompartir() no mira la plataforma")
        return 1

    js = os.path.join(AQUI, "_plataforma.js")
    io.open(js, "w", encoding="utf-8").write(JS)
    try:
        r = subprocess.run(["node", js, INDEX, json.dumps(CASOS)],
                           capture_output=True, text=True, timeout=60)
    finally:
        try: os.remove(js)
        except OSError: pass
    if r.returncode != 0:
        print("no pude correr node:", r.stderr[:300]); return 1
    obtenidos = json.loads(r.stdout.strip().splitlines()[-1])
    if isinstance(obtenidos, dict):
        print("FALLA |", obtenidos.get("error")); return 1

    ok = 0
    for (nombre, _ua, _t, esperado, hoja), real in zip(CASOS, obtenidos):
        bien = real == esperado
        ok += bien
        camino = "hoja de compartir" if hoja else "descarga directa"
        print("%s | %-16s -> %-11s %s" % ("PASS" if bien else "FALLA", nombre, real,
                                          camino if bien else "(esperaba %s)" % esperado))
    print("\n%d/%d PASS" % (ok, len(CASOS)))
    return 0 if ok == len(CASOS) else 1


if __name__ == "__main__":
    sys.exit(main())
