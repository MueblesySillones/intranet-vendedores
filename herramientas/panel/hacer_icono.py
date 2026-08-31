# -*- coding: utf-8 -*-
"""Genera panel.ico a partir de web/logo.png:
logo blanco centrado sobre un cuadro oscuro con esquinas redondeadas.
Se usa como icono del .exe y de los accesos directos."""
import os
from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(AQUI, "web", "logo.png")
SALIDA = os.path.join(AQUI, "panel.ico")

FONDO = (28, 30, 33, 255)   # gris carbon (japandi oscuro)
LADO = 256
MARGEN = 40                 # aire alrededor del logo

# lienzo base a 256x256
base = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
mask = Image.new("L", (LADO, LADO), 0)
d = ImageDraw.Draw(mask)
d.rounded_rectangle([0, 0, LADO - 1, LADO - 1], radius=52, fill=255)
fondo = Image.new("RGBA", (LADO, LADO), FONDO)
base.paste(fondo, (0, 0), mask)

# logo blanco escalado dentro del margen, centrado verticalmente
logo = Image.open(LOGO).convert("RGBA")
maxw = LADO - 2 * MARGEN
maxh = LADO - 2 * MARGEN
lw, lh = logo.size
s = min(maxw / lw, maxh / lh)
logo = logo.resize((max(1, int(lw * s)), max(1, int(lh * s))), Image.LANCZOS)
lw, lh = logo.size
base.paste(logo, ((LADO - lw) // 2, (LADO - lh) // 2), logo)

# guardar como .ico multi-resolucion
base.save(SALIDA, format="ICO",
          sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Icono generado:", SALIDA)
