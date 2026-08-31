# -*- coding: utf-8 -*-
"""Prueba el camino que van a recorrer las SUCURSALES: no tienen ffmpeg, el panel
lo descarga solo la primera vez. Se sirve un zip real por HTTP local (mismo formato
que el release de GitHub) para no bajar 104 MB en cada corrida."""
import os
import sys
import json
import time
import shutil
import zipfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402

ok_total, fallos = 0, []


def check(nombre, cond, extra=""):
    global ok_total
    if cond:
        ok_total += 1
        print("  OK   %s %s" % (nombre, extra))
    else:
        fallos.append(nombre)
        print("  FALLA %s %s" % (nombre, extra))


print("=" * 70)
print("PRUEBA: descarga del compresor (camino de una sucursal sin ffmpeg)")
print("=" * 70)

real = ps.ffmpeg_local()
if not real:
    print("necesito un ffmpeg de referencia para armar el zip de prueba")
    sys.exit(1)

srv_dir = os.path.join(ps.STATE_DIR, "test_srv")
os.makedirs(srv_dir, exist_ok=True)
zip_path = os.path.join(srv_dir, "ffmpeg.zip")

print("\n[1] Armando un zip con la misma estructura que el release oficial")
if not os.path.isfile(zip_path):
    # ZIP_STORED: sin comprimir, es solo para la prueba y asi tarda segundos
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as z:
        z.write(real, "ffmpeg-8.1.1-essentials_build/bin/ffmpeg.exe")
        z.writestr("ffmpeg-8.1.1-essentials_build/LICENSE", "prueba")
print("     zip de prueba: %.0f MB" % (os.path.getsize(zip_path) / 1048576.0))

print("\n[2] Sirviendolo por HTTP local")
os.chdir(srv_dir)
httpd = ThreadingHTTPServer(("127.0.0.1", 8198), SimpleHTTPRequestHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

# simular una PC virgen: sin ffmpeg en PATH y sin cache
ffdir = os.path.join(ps.STATE_DIR, "ffmpeg")
shutil.rmtree(ffdir, ignore_errors=True)
ps._FFMPEG_CACHE = ""
ps.FFMPEG_URL = "http://127.0.0.1:8198/ffmpeg.zip"
which_real = shutil.which
shutil.which = lambda *a, **k: None          # como una PC sin ffmpeg instalado

check("una PC sin ffmpeg lo reporta como ausente", ps.ffmpeg_local() == "")

print("\n[3] Descarga + instalacion")
jid = ps._job_nuevo("ffmpeg")
t0 = time.time()
hilo = threading.Thread(target=ps._bajar_ffmpeg, args=(jid,))
hilo.start()
pcts = []
while hilo.is_alive():
    e = ps.job_estado(jid)
    if e and e.get("pct") and e["pct"] not in pcts:
        pcts.append(e["pct"])
    time.sleep(0.05)
hilo.join()
est = ps.job_estado(jid)
print("     %s | %.1fs | hitos=%s" % (est.get("estado"), time.time() - t0, pcts[:8]))

check("el trabajo termino listo", est.get("estado") == "listo", est.get("error", ""))
check("informo progreso durante la descarga", len(pcts) >= 3, "%d hitos" % len(pcts))
exe = os.path.join(ffdir, "ffmpeg.exe")
check("quedo el ffmpeg.exe instalado", os.path.isfile(exe))
check("el binario instalado FUNCIONA", ps._ffmpeg_anda(exe))
check("ffmpeg_local ahora lo encuentra", ps.ffmpeg_local() == exe, ps.ffmpeg_local())
check("no quedaron restos .part", not [f for f in os.listdir(ffdir) if f.endswith(".part")],
      str(os.listdir(ffdir)))

print("\n[4] Que pasa si la descarga viene corrupta")
shutil.rmtree(ffdir, ignore_errors=True)
ps._FFMPEG_CACHE = ""
with open(os.path.join(srv_dir, "roto.zip"), "wb") as f:
    f.write(b"esto no es un zip" * 1000)
ps.FFMPEG_URL = "http://127.0.0.1:8198/roto.zip"
jid2 = ps._job_nuevo("ffmpeg")
ps._bajar_ffmpeg(jid2)
est2 = ps.job_estado(jid2)
check("un zip corrupto da error claro", est2.get("estado") == "error", est2.get("error", "")[:70])
check("no deja un ffmpeg roto instalado", not os.path.isfile(os.path.join(ffdir, "ffmpeg.exe")))
check("sigue reportando que falta el compresor", ps.ffmpeg_local() == "")

print("\n[5] Que pasa si el servidor no responde")
ps.FFMPEG_URL = "http://127.0.0.1:8197/no-existe.zip"
jid3 = ps._job_nuevo("ffmpeg")
ps._bajar_ffmpeg(jid3)
est3 = ps.job_estado(jid3)
check("un servidor caido da error, no cuelga", est3.get("estado") == "error",
      est3.get("error", "")[:70])

print("\n[6] Limpieza")
shutil.which = which_real
httpd.shutdown()
os.chdir(AQUI)
shutil.rmtree(srv_dir, ignore_errors=True)
shutil.rmtree(ffdir, ignore_errors=True)
check("se borro todo lo de la prueba", not os.path.isdir(srv_dir) and not os.path.isdir(ffdir))

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok_total, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
