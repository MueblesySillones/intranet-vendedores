# -*- coding: utf-8 -*-
"""Prueba el compositor del panel: el reparto de adjuntos y la fusion con la grilla.

Por que existe: hasta el 19-sep "Agregale algo" tenia SEIS botones (una foto,
varias fotos, un video, un PDF, una lista, un enlace). Los tres primeros eran
el mismo selector de archivos con distinto `accept`. Ahora son dos —Adjuntar y
Documento— y el reparto lo deduce el panel mirando lo que se eligio.

Y "Cargar al modulo" empujaba SIEMPRE al final: mandar una foto a un modulo de
descargables no la metia en la grilla que el modulo ya tenia, la dejaba abajo
de todo como un bloque suelto con un titulo h2 colgando.

Lo que se verifica, contra el codigo REAL de web3/muro.js:
  1. cada archivo cae en su canasta, aunque Windows no le ponga `type`
  2. la ultima grilla del modulo es la que recibe
  3. las fotos se suman ADENTRO de esa grilla, no como bloque nuevo
  4. si se fusiono todo y no habia texto, no queda un titulo huerfano
  5. los seis botones viejos ya no estan en el HTML

    python test_compositor_adjuntos.py
"""
import io
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
WEB3 = os.path.abspath(os.path.join(AQUI, "..", "panel", "web3"))
MURO = os.path.join(WEB3, "muro.js")
INDEX = os.path.join(WEB3, "index.html")

# nombre del archivo, MIME que informa el navegador, canasta esperada
ARCHIVOS = [
    ("promo.jpg",      "image/jpeg",       "imagen"),
    ("placa.PNG",      "image/png",        "imagen"),
    ("foto.heic",      "",                 "imagen"),   # iPhone, sin type
    ("clip.mp4",       "video/mp4",        "video"),
    ("EMBALAJE.MOV",   "",                 "video"),    # Windows no le pone type
    ("spot.webm",      "video/webm",       "video"),
    ("manual.pdf",     "application/pdf",  "pdf"),
    ("lista.PDF",      "",                 "pdf"),
    ("planilla.xlsx",  "",                 "otro"),
]

JS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

function sacar(nombre) {
  const marca = 'function ' + nombre + '(';
  const ini = src.indexOf(marca);
  if (ini < 0) throw new Error('no encontre ' + nombre + '()');
  let i = src.indexOf('{', ini), hondo = 0;
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') hondo++;
    else if (src[j] === '}') { hondo--; if (!hondo) return src.slice(ini, j + 1); }
  }
  throw new Error('no cierra ' + nombre);
}

const esc = s => String(s);
eval(sacar('esImagen'));
eval(sacar('esVideo'));
eval(sacar('esPdf'));
eval(sacar('ultimaGaleria'));
eval(sacar('bloquesParaModulo'));

const out = {};

out.canastas = JSON.parse(process.argv[3]).map(a => {
  const f = { name: a[0], type: a[1] };
  if (esImagen(f)) return 'imagen';
  if (esVideo(f)) return 'video';
  if (esPdf(f)) return 'pdf';
  return 'otro';
});

// la ultima grilla, no la primera
out.ultima = ultimaGaleria([
  { t: 'titulo' },
  { t: 'galeria', items: [{ src: 'a.jpg' }] },
  { t: 'parrafo' },
  { t: 'galeria', items: [{ src: 'b.jpg' }] },
  { t: 'pdf' },
]);
out.sinGrilla = ultimaGaleria([{ t: 'titulo' }, { t: 'parrafo' }]);

// fusiono todo y no habia texto -> nada suelto
out.huerfano = bloquesParaModulo('Promos de agosto', '', [], true).length;
// fusiono pero habia texto -> el texto queda, con su titulo
out.conTexto = bloquesParaModulo('Promos', 'Vence el viernes', [], true).map(b => b.t);
// sin fusion -> como siempre
out.normal = bloquesParaModulo('Promos', 'texto',
  [{ t: 'imagen', src: 'x.jpg' }], false).map(b => b.t);
// las referencias a otros modulos no viajan
out.sinRef = bloquesParaModulo('Promos', '',
  [{ t: 'ref', key: 'manuales' }, { t: 'pdf', src: 'm.pdf' }], false).map(b => b.t);

console.log(JSON.stringify(out));
"""


def main():
    for p in (MURO, INDEX):
        if not os.path.isfile(p):
            print("no encuentro", p); return 1

    fuente = io.open(MURO, encoding="utf-8").read()
    html = io.open(INDEX, encoding="utf-8").read()
    fallas = []

    # --- 1. el HTML no puede volver a los seis botones ---
    ads = sorted(set(re.findall(r'data-ad="([^"]+)"', html)))
    if ads != ["medios", "pdf"]:
        fallas.append("los botones de adjuntar son %s (esperaba medios y pdf)" % ads)

    # --- 2. lo que se saco no puede volver por la ventana ---
    for id_, qué in (("coConfirmar", "pedir confirmacion"),
                     ("coArchivar", "archivar en un modulo"),
                     ("docConfirmar", "pedir confirmacion (editor viejo)")):
        if 'id="%s"' % id_ in html:
            fallas.append("volvio %s: %s" % (id_, qué))

    # --- 3. el reparto lo hace un solo lugar ---
    if fuente.count("async function soltar(") != 1:
        fallas.append("hay mas de un reparto de archivos")
    if "await soltar(files)" not in fuente:
        fallas.append("agregarAdjunto ya no reusa soltar(): se duplico la logica")

    js = os.path.join(AQUI, "_compositor.js")
    io.open(js, "w", encoding="utf-8").write(JS)
    try:
        r = subprocess.run(["node", js, MURO, json.dumps(ARCHIVOS)],
                           capture_output=True, text=True, timeout=60)
    finally:
        try: os.remove(js)
        except OSError: pass
    if r.returncode != 0:
        print("no pude correr node:", (r.stderr or "")[:400]); return 1
    o = json.loads(r.stdout.strip().splitlines()[-1])

    ok = 0
    for (nombre, tipo, esperado), real in zip(ARCHIVOS, o["canastas"]):
        bien = real == esperado
        ok += bien
        print("%s | %-15s %-18s -> %-7s%s" % (
            "PASS" if bien else "FALLA", nombre, tipo or "(sin type)", real,
            "" if bien else "  (esperaba %s)" % esperado))
    if ok != len(ARCHIVOS):
        fallas.append("%d archivos cayeron en la canasta equivocada" % (len(ARCHIVOS) - ok))

    casos = [
        ("la grilla que recibe es la ULTIMA",        o["ultima"], 3),
        ("modulo sin grilla avisa que no hay",       o["sinGrilla"], -1),
        ("fusiono todo y sin texto: nada suelto",    o["huerfano"], 0),
        ("fusiono pero habia texto: queda el texto", o["conTexto"], ["titulo", "parrafo"]),
        ("sin fusion: titulo, texto y pieza",        o["normal"], ["titulo", "parrafo", "imagen"]),
        ("el bloque 'ref' no viaja al modulo",       o["sinRef"], ["titulo", "pdf"]),
    ]
    for nombre, real, esperado in casos:
        bien = real == esperado
        ok += bien
        print("%s | %-42s %s%s" % ("PASS" if bien else "FALLA", nombre, real,
                                   "" if bien else "  (esperaba %s)" % esperado))
        if not bien:
            fallas.append(nombre)

    total = len(ARCHIVOS) + len(casos)
    print("\n%d/%d PASS" % (ok, total))
    for f in fallas:
        print("FALLA |", f)
    return 0 if ok == total and not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
