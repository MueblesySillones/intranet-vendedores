# -*- coding: utf-8 -*-
"""Baja el paquete de actualizacion como lo haria una sucursal y verifica que
el sha256 coincida. El cliente verifica FAIL-CLOSED: si no coincide, no aplica.
Asi comprobamos que la actualizacion realmente se podria instalar."""
import sys, json, time, hashlib, zipfile, io, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

B = "http://127.0.0.1:8125"
with urllib.request.urlopen(B + "/update/version", timeout=10) as r:
    v = json.load(r)
print("la central anuncia la version %s (%.1f MB)" % (v["version"], v["size"] / 1048576))

t0 = time.time()
h = hashlib.sha256()
datos = io.BytesIO()
with urllib.request.urlopen(B + "/update/bundle?v=%d" % v["version"], timeout=180) as r:
    while True:
        c = r.read(256 * 1024)
        if not c:
            break
        h.update(c); datos.write(c)
seg = time.time() - t0
print("descargado: %.1f MB en %.1fs" % (datos.tell() / 1048576, seg))
print("sha256 esperado : %s" % v["sha256"][:32])
print("sha256 obtenido : %s" % h.hexdigest()[:32])
print("coincide        : %s" % ("SI" if h.hexdigest() == v["sha256"] else "NO !!"))

datos.seek(0)
with zipfile.ZipFile(datos) as z:
    nombres = z.namelist()
    print("archivos en el paquete: %d" % len(nombres))
    for esperado in ("PanelMyS.exe", "_internal/web/app.js", "_internal/web/styles.css"):
        hay = any(n.replace("\\", "/").endswith(esperado) for n in nombres)
        print("  %-28s %s" % (esperado, "esta" if hay else "FALTA !!"))
    # que NO viajen los archivos propios de la maquina
    for prohibido in ("panel_config.json", "proyecto.txt", "identity.json"):
        cuela = [n for n in nombres if n.replace("\\", "/").endswith(prohibido)]
        print("  %-28s %s" % ("no lleva " + prohibido, "ok" if not cuela else "SE CUELA !!"))
    # la version que viaja adentro
    ex = [n for n in nombres if n.replace("\\", "/").endswith("_internal/web/app.js")]
    if ex:
        js = z.read(ex[0]).decode("utf-8", "replace")
        print("  trae 'Avisar novedad'        : %s" % ("si" if "avisarGuardar" in js else "NO"))
        print("  trae la paleta desplegable   : %s" % ("si" if "GB_ABIERTOS" in js else "NO"))
        print("  trae el carrusel arreglado   : %s" % ("si" if "waTarjetaPublicable" in js else "NO"))
