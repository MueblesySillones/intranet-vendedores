# -*- coding: utf-8 -*-
"""
Arregla imagenes que Claude (u otras apps) no pueden leer.
- Toma una imagen desde un archivo (arrastrado o pasado como argumento)
  o, si no hay archivo, desde el PORTAPAPELES.
- La normaliza a un PNG estandar (sRGB, sin perfiles raros) y de tamano seguro.
- La guarda en el Escritorio como 'imagen_arreglada.png' y abre la carpeta.
Uso:  python arreglar_imagen.py [ruta_opcional_a_imagen]
"""
import sys, os, subprocess
from PIL import Image, ImageGrab

MAX_LADO = 1568   # lado maximo recomendado para vision de Claude

def escritorio():
    d = os.path.join(os.path.expanduser("~"), "Desktop")
    return d if os.path.isdir(d) else os.path.expanduser("~")

def cargar():
    # 1) archivo pasado como argumento (o arrastrado al .bat)
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        return Image.open(sys.argv[1]), sys.argv[1]
    # 2) portapapeles
    cb = ImageGrab.grabclipboard()
    if isinstance(cb, list) and cb:               # se copiaron archivos
        return Image.open(cb[0]), cb[0]
    if cb is not None:                            # imagen directa en portapapeles
        return cb, "(portapapeles)"
    print("\n[!] No encontre ninguna imagen.")
    print("    Copia una imagen (o una captura) y volve a ejecutar,")
    print("    o arrastra un archivo de imagen sobre 'Arreglar imagen.bat'.")
    sys.exit(2)

def normalizar(img):
    """Convierte una imagen PIL a un formato seguro (RGB/RGBA, <=MAX_LADO).
    Devuelve (img_normalizada, lista_de_cambios)."""
    cambios = []
    # Normalizar CUALQUIER modo a RGB/RGBA (lo unico 100% aceptado).
    m = img.mode
    if m not in ("RGB", "RGBA"):
        tiene_alpha = (m in ("LA", "PA", "RGBa", "La") or
                       (m == "P" and img.info.get("transparency") is not None))
        # modos de alta profundidad (16/32 bits) -> primero a 8 bits
        if m.startswith("I") or m == "F":
            img = img.convert("L")
        destino = "RGBA" if tiene_alpha else "RGB"
        img = img.convert(destino)
        cambios.append("modo %s -> %s" % (m, destino))
    # redimensionar si es muy grande
    w, h = img.size
    if max(w, h) > MAX_LADO:
        s = MAX_LADO / float(max(w, h))
        img = img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
        cambios.append("redimensionada a %sx%s" % img.size)
    return img, cambios

def main():
    img, origen = cargar()
    print("Origen :", origen)
    print("Formato:", img.format, "| Modo:", img.mode, "| Tamano:", img.size)

    img, cambios = normalizar(img)

    salida = os.path.join(escritorio(), "imagen_arreglada.png")
    # guardar PNG limpio, SIN perfil ICC (info vacia)
    img.save(salida, format="PNG", optimize=True)

    kb = round(os.path.getsize(salida) / 1024.0, 1)
    print("\nCambios:", ", ".join(cambios) if cambios else "ninguno (ya estaba bien)")
    print("GUARDADA:", salida, "(%s KB)" % kb)
    print("\n>> Arrastra ESE archivo a Claude (es mas confiable que pegar).")

    try:
        subprocess.Popen(["explorer.exe", "/select,", salida])
    except Exception:
        pass

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[ERROR]", type(e).__name__, "-", e)
        sys.exit(1)
