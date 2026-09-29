# -*- coding: utf-8 -*-
"""El deck en PDF, bajado de una, sin diálogo de impresión.

POR QUE ASI Y NO DE OTRA MANERA

El botón «Descargar PDF» abría el reporte y disparaba Ctrl+P: el navegador
mostraba el diálogo, había que elegir «Guardar como PDF», el destino y el
nombre. Eso no es descargar, es imprimir. Ahora el archivo se arma acá y baja
solo.

El PDF lo sigue haciendo un navegador —el mismo motor que dibuja el deck en
pantalla—, pero en modo **headless**: se le pasa el HTML y devuelve el PDF.
Se usa el navegador que YA está en la máquina (Edge viene con Windows), así
que no se suma ninguna dependencia al .exe. Escribir un PDF a mano, como se
hace con el .docx en deck_word.py, no da: habría que reimplementar tipografía,
color y layout, y el resultado no sería el diseño sino una imitación.

La hoja sale de `@media print` del propio deck (13.333in x 7.5in = 16:9, una
lámina por página, colores forzados). O sea que el PDF es exactamente lo que
se ve en pantalla, porque es la misma hoja de estilos.

⚠️ `--user-data-dir` a una carpeta aparte es OBLIGATORIO. Sin eso, si la
   persona tiene Edge abierto —y lo tiene—, el proceso nuevo se engancha al
   que ya corre, no imprime nada y termina en silencio con éxito.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata

# Dónde vive un navegador con motor Chromium, en orden de preferencia. Edge
# primero porque viene con Windows: es el único que se puede dar por hecho en
# la computadora de una sucursal.
CANDIDATOS = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\SxS\Application\chrome.exe",
]
EN_EL_PATH = ["msedge", "chrome", "chromium", "brave"]

FALTA_NAVEGADOR = ("No encontré Microsoft Edge ni Chrome en esta computadora, "
                   "y el PDF lo arma el navegador. Abrí el reporte con «Ver "
                   "reporte» y guardalo con Ctrl+P.")


def buscar_navegador():
    """La ruta del navegador que puede imprimir, o None."""
    for patron in CANDIDATOS:
        ruta = os.path.expandvars(patron)
        if "%" not in ruta and os.path.isfile(ruta):
            return ruta
    for nombre in EN_EL_PATH:
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    return None


def _sin_ventana():
    """Que no parpadee una consola negra en la cara de la persona."""
    if os.name != "nt":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"startupinfo": si,
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _url_de(ruta):
    return "file:///" + os.path.abspath(ruta).replace("\\", "/")


def _barrer_viejas(edad=1800):
    """Tira las carpetas de trabajo que quedaron de otras veces.

    El perfil temporal se borra al terminar, pero a veces Edge lo suelta unos
    segundos después y el borrado no llega. Sin esto queda una carpeta de
    varios MB por cada PDF y nadie la limpia nunca. Se barren solo las de más
    de media hora, para no pisar un PDF que se esté armando en paralelo.
    """
    base = tempfile.gettempdir()
    try:
        nombres = os.listdir(base)
    except OSError:
        return
    ahora = time.time()
    for n in nombres:
        if not n.startswith("mys_pdf_"):
            continue
        ruta = os.path.join(base, n)
        try:
            if os.path.isdir(ruta) and ahora - os.path.getmtime(ruta) > edad:
                shutil.rmtree(ruta, ignore_errors=True)
        except OSError:
            pass


def desde_html(html, ruta_pdf, espera_ms=9000, timeout=120):
    """Escribe `html` en un PDF. Devuelve (ruta, error).

    `espera_ms` es el presupuesto de tiempo virtual: le da al navegador margen
    para bajar la tipografía y acomodar todo ANTES de imprimir. Sin eso, un
    deck grande sale con la fuente de respaldo.
    """
    navegador = buscar_navegador()
    if not navegador:
        return None, FALTA_NAVEGADOR

    _barrer_viejas()
    tmp = tempfile.mkdtemp(prefix="mys_pdf_")
    fuente = os.path.join(tmp, "reporte.html")
    perfil = os.path.join(tmp, "perfil")
    try:
        with open(fuente, "w", encoding="utf-8") as f:
            f.write(html)
        cmd = [
            navegador,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--hide-scrollbars",
            "--user-data-dir=" + perfil,
            "--virtual-time-budget=%d" % espera_ms,
            "--run-all-compositor-stages-before-draw",
            # el mismo trapo con los dos nombres: cambió entre versiones y
            # Chromium ignora en silencio el que no conoce
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            "--print-to-pdf=" + ruta_pdf,
            _url_de(fuente),
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                               **_sin_ventana())
        except subprocess.TimeoutExpired:
            return None, ("El navegador tardó demasiado en armar el PDF. "
                          "Probá de nuevo, o abrilo con «Ver reporte».")
        # Edge/Chrome devuelven 0 y escriben el archivo; si no está, algo pasó
        if not os.path.isfile(ruta_pdf) or os.path.getsize(ruta_pdf) < 1000:
            detalle = (r.stderr or b"").decode("utf-8", "replace").strip()
            detalle = detalle.split("\n")[-1][:180] if detalle else ""
            return None, ("El navegador no pudo armar el PDF. %s" % detalle).strip()
        return ruta_pdf, None
    finally:
        # el perfil temporal puede quedar tomado un instante despues de salir
        for _ in range(3):
            shutil.rmtree(tmp, ignore_errors=True)
            if not os.path.isdir(tmp):
                break
            time.sleep(0.3)


def nombre_archivo(titulo):
    """Un nombre de archivo que no rompa en Windows ni en la cabecera HTTP.

    Se pasa a ASCII a proposito. El nombre viaja en `Content-Disposition`, que
    http.server escribe en latin-1: un titulo con un emoji o una comilla
    tipografica -cosas que se pegan sin querer al copiar de un documento- tira
    la respuesta entera, y el archivo no baja sin que se entienda por que.
    """
    limpio = unicodedata.normalize("NFKD", str(titulo or "Reporte"))
    limpio = "".join(c for c in limpio
                     if (c.isalnum() or c in " -_") and ord(c) < 128).strip()
    return "%s.pdf" % (limpio[:70] or "Reporte")


if __name__ == "__main__":                      # prueba a mano
    print("navegador:", buscar_navegador() or "NINGUNO")
    if len(sys.argv) > 2:
        print(desde_html(open(sys.argv[1], encoding="utf-8").read(), sys.argv[2]))
