# -*- coding: utf-8 -*-
import sys, os, glob, tempfile, importlib.util

TOOLS = r"C:\Users\Redes 1\Documents\MYS-CLAUDE\tools"
sys.path.insert(0, TOOLS)
from PIL import Image
import PIL

# importar la funcion REAL de la herramienta que usa el usuario
spec = importlib.util.spec_from_file_location("arreglar_imagen", os.path.join(TOOLS, "arreglar_imagen.py"))
ai = importlib.util.module_from_spec(spec); spec.loader.exec_module(ai)

MAX = 1568
SOPORTADOS_CLAUDE = {"JPEG", "PNG", "GIF", "WEBP"}   # formatos que la app acepta
tmp = tempfile.mkdtemp(prefix="diag_")

print("=" * 60)
print(" DIAGNOSTICO DE ENTORNO E IMAGENES")
print("=" * 60)
print("Python :", sys.version.split()[0])
print("Pillow :", PIL.__version__)
print("Tools  :", TOOLS)

# ---------- 1) BATERIA DE IMAGENES PROBLEMATICAS ----------
print("\n" + "-" * 60)
print(" PRUEBA 1: 11 imagenes problematicas -> herramienta")
print("-" * 60)

def mk(nombre, modo, size, fmt, **kw):
    im = Image.new(modo, size, kw.get("color", 0))
    p = os.path.join(tmp, nombre)
    im.save(p, format=fmt)
    return p

casos = []
casos.append(("CMYK JPEG 4000x2600",  mk("a.jpg", "CMYK", (4000,2600), "JPEG", color=(10,40,80,5))))
casos.append(("BMP RGB 2400x1600",    mk("b.bmp", "RGB",  (2400,1600), "BMP",  color=(120,30,30))))
casos.append(("TIFF RGB 3000x2000",   mk("c.tif", "RGB",  (3000,2000), "TIFF", color=(20,90,40))))
casos.append(("GIF paleta 800x600",   mk("d.gif", "P",    (800,600),   "GIF")))
casos.append(("WebP 2200x1300",       mk("e.webp","RGB",  (2200,1300), "WEBP", color=(40,40,160))))
casos.append(("PNG RGBA transp 1200", mk("f.png", "RGBA", (1200,1200), "PNG",  color=(0,128,255,128))))
casos.append(("Gris L 4000x120",      mk("g.png", "L",    (4000,120),  "PNG",  color=128)))
casos.append(("16-bit I 600x600",     mk("h.png", "I",    (600,600),   "PNG",  color=3000)))
casos.append(("1x1 minima",           mk("i.png", "RGB",  (1,1),       "PNG",  color=(255,0,0))))
casos.append(("Enorme 8000x300",      mk("j.png", "RGB",  (8000,300),  "PNG",  color=(0,0,0))))
casos.append(("Paleta+transp 700x700",mk("k.png", "P",    (700,700),   "PNG")))

ok = 0
print("%-24s %-18s -> %-22s %s" % ("CASO", "ORIGINAL", "RESULTADO", "VEREDICTO"))
for nombre, ruta in casos:
    try:
        src = Image.open(ruta)
        o_fmt, o_mode, o_size = src.format, src.mode, src.size
        norm, _ = ai.normalizar(src)
        outp = os.path.join(tmp, "out_" + os.path.basename(ruta) + ".png")
        norm.save(outp, format="PNG", optimize=True)
        # validar releyendo
        chk = Image.open(outp); chk.load()
        valido = (chk.format == "PNG"
                  and chk.mode in ("RGB", "RGBA")
                  and max(chk.size) <= MAX
                  and os.path.getsize(outp) < 5*1024*1024)
        ver = "OK" if valido else "FALLA"
        if valido: ok += 1
        print("%-24s %-18s -> %-22s %s" % (
            nombre[:24], "%s/%s" % (o_fmt, o_mode),
            "PNG/%s %sx%s" % (chk.mode, chk.size[0], chk.size[1]), ver))
    except Exception as e:
        print("%-24s ERROR: %s" % (nombre[:24], e))

print("\nRESULTADO PRUEBA 1:  %d/%d arregladas correctamente" % (ok, len(casos)))

# ---------- 2) DIAGNOSTICO DE IMAGENES REALES ----------
print("\n" + "-" * 60)
print(" PRUEBA 2: imagenes reales en tus carpetas")
print("-" * 60)

carpetas = [
    os.path.join(os.path.expanduser("~"), "Downloads"),
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "Documents"),
]
exts = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tif", "*.tiff", "*.webp", "*.gif", "*.heic")
encontrados = []
for c in carpetas:
    for e in exts:
        encontrados += glob.glob(os.path.join(c, e))
encontrados = sorted(set(encontrados))[:50]

if not encontrados:
    print("No se encontraron imagenes sueltas en Downloads/Desktop/Documents.")
else:
    print("%-42s %-12s %-9s %-8s %s" % ("ARCHIVO", "FORMATO/MODO", "TAMANO", "PESO", "DIAGNOSTICO"))
    riesgo = 0
    for f in encontrados:
        try:
            im = Image.open(f)
            fmt, mode, (w, h) = im.format, im.mode, im.size
            kb = os.path.getsize(f) / 1024.0
            probs = []
            if fmt not in SOPORTADOS_CLAUDE: probs.append("formato no soportado")
            if mode == "CMYK": probs.append("color CMYK")
            if max(w, h) > 1568: probs.append("muy grande")
            if kb > 5120: probs.append("pesa >5MB")
            diag = "OK" if not probs else " / ".join(probs)
            if probs: riesgo += 1
            nom = os.path.basename(f)
            print("%-42s %-12s %-9s %-8s %s" % (
                nom[:42], "%s/%s" % (fmt, mode), "%dx%d" % (w, h),
                "%dKB" % kb, diag))
        except Exception as e:
            print("%-42s  no se pudo leer: %s" % (os.path.basename(f)[:42], e))
    print("\n%d imagenes con riesgo de fallar en Claude (de %d)." % (riesgo, len(encontrados)))

print("\n" + "=" * 60)
print(" FIN DEL DIAGNOSTICO")
print("=" * 60)
