# -*- coding: utf-8 -*-
"""Copia el bloque CSS de la Plantilla de WhatsApp de la intranet al panel,
cambiando el prefijo .manual por .doc-preview. Asi el lienzo del editor se ve
igual que el sitio publicado, que es la regla de la casa."""
import io, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r"C:\Users\Redes 1\Documents\web dinamica-mys"
intranet = os.path.join(R, "intranet", "index.html")
estilos = os.path.join(R, "herramientas", "panel", "web", "styles.css")

h = io.open(intranet, encoding="utf-8").read()
ini = h.index(".manual .wt{")
fin = h.index("\n", h.index(".manual .wt-hint{"))
bloque = h[ini:fin]
espejo = ("\n/* espejo del bloque Plantilla de WhatsApp en el lienzo del editor.\n"
          "   Si tocas uno, toca el otro: el lienzo tiene que verse igual que el sitio. */\n"
          + bloque.replace(".manual .wt", ".doc-preview .wt") + "\n")

css = io.open(estilos, encoding="utf-8").read()
if ".doc-preview .wt{" in css:
    print("ya estaba")
else:
    io.open(estilos, "w", encoding="utf-8", newline="").write(css + espejo)
    print("espejo agregado: %d caracteres, %d reglas"
          % (len(espejo), espejo.count("{")))
print("llaves intranet: %d / %d" % (h.count("{"), h.count("}")))
