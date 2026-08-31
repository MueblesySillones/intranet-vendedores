# -*- coding: utf-8 -*-
"""
Escanea intranet/assets/<seccion>/ y genera intranet/galerias.js
para que las imagenes aparezcan solas en la intranet con boton de descarga.
Marketing: dejen las imagenes en la carpeta de la seccion y ejecuten este script
(o el acceso directo "Actualizar imagenes.bat").

Portable: las rutas se calculan desde la ubicacion de este archivo,
asi funciona aunque muevas la carpeta del proyecto.
"""
import os, re, json

# raiz del proyecto = carpeta que contiene "herramientas" e "intranet"
PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTRANET = os.path.join(PROYECTO, "intranet")
ASSETS = os.path.join(INTRANET, "assets")
SECCIONES = ["promos_bancarias", "promos_mensuales", "entregas", "fechas_especiales", "porque", "competencia", "chatbot"]
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

def titulo(nombre):
    stem = os.path.splitext(nombre)[0]
    stem = re.sub(r'^\d+\s*[-_.]\s*', '', stem)
    stem = re.sub(r'[-_]+', ' ', stem).strip()
    return (stem[:1].upper() + stem[1:]) if stem else nombre

os.makedirs(ASSETS, exist_ok=True)
data = {}
total = 0
print("=" * 54)
print(" GALERIAS DE LA INTRANET")
print("=" * 54)
for sec in SECCIONES:
    carpeta = os.path.join(ASSETS, sec)
    os.makedirs(carpeta, exist_ok=True)
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith(EXTS)]
    archivos.sort(key=lambda s: s.lower())
    if archivos:
        data[sec] = [{"file": "assets/%s/%s" % (sec, f), "title": titulo(f), "download": f} for f in archivos]
        total += len(archivos)
    print("  %-20s %d imagen(es)" % (sec, len(archivos)))

salida = os.path.join(INTRANET, "galerias.js")
with open(salida, "w", encoding="utf-8") as fh:
    fh.write("/* Generado automaticamente por actualizar_galerias.py. No editar a mano. */\n")
    fh.write("window.GALLERIES = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n")

print("-" * 54)
print(" Total: %d imagenes en %d seccion(es)" % (total, len(data)))
print(" Generado: %s" % salida)
print("=" * 54)
