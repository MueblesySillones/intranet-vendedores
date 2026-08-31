# -*- coding: utf-8 -*-
"""Empareja las tarjetas del carrusel: misma altura, texto arriba y botones
pegados abajo. Aplica el mismo cambio en la intranet y en el panel."""
import io, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r"C:\Users\Redes 1\Documents\web dinamica-mys"

CAMBIOS = [
    # las tarjetas se estiran a la misma altura
    ("{P} .wt-car{{ display:flex; gap:6px; overflow-x:auto; padding:6px 0 4px; scroll-snap-type:x mandatory; }}",
     "{P} .wt-car{{ display:flex; gap:6px; overflow-x:auto; padding:6px 0 4px; scroll-snap-type:x mandatory; align-items:stretch; }}"),
    # cada tarjeta es una columna: el cuerpo empuja y los botones quedan al pie
    ("{P} .wt-card{{ flex:0 0 210px; background:#fff; border-radius:8px; overflow:hidden;",
     "{P} .wt-card{{ display:flex; flex-direction:column; flex:0 0 210px; background:#fff; border-radius:8px; overflow:hidden;"),
    ("{P} .wt-cbody{{ padding:7px 9px 8px; font-size:13.2px; line-height:1.38; color:#111b21; white-space:pre-wrap; }}",
     "{P} .wt-cbody{{ flex:1; padding:7px 9px 8px; font-size:13.2px; line-height:1.38; color:#111b21; white-space:pre-wrap; min-height:1.4em; }}\n"
     "{P} .wt-cbtns{{ display:flex; flex-direction:column; }}\n"
     "{P} .wt-ph{{ color:#9aa7ad; font-style:italic; }}"),
]

for archivo, pref in ((os.path.join(R, "intranet", "index.html"), ".manual"),
                      (os.path.join(R, "herramientas", "panel", "web", "styles.css"), ".doc-preview")):
    c = io.open(archivo, encoding="utf-8").read()
    n = 0
    for viejo, nuevo in CAMBIOS:
        v, u = viejo.format(P=pref), nuevo.format(P=pref)
        if v in c and u not in c:
            c = c.replace(v, u)
            n += 1
    io.open(archivo, "w", encoding="utf-8", newline="").write(c)
    print("%-14s %d de %d cambios" % (os.path.basename(archivo), n, len(CAMBIOS)))
