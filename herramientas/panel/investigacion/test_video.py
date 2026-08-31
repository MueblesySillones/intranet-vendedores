# -*- coding: utf-8 -*-
"""Prueba end-to-end del bloque de video en el backend del panel.
Genera un video VERTICAL pesado, lo sube por el endpoint real, espera la
compresion, y verifica peso / orientacion / Range. Limpia todo al final."""
import os
import sys
import json
import time
import subprocess
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402

PORT = 8199
BASE = "http://127.0.0.1:%d" % PORT
KEY = "zz_test_video_borrar"
ok_total, fallos = 0, []


def check(nombre, cond, extra=""):
    global ok_total
    if cond:
        ok_total += 1
        print("  OK   %s %s" % (nombre, extra))
    else:
        fallos.append(nombre)
        print("  FALLA %s %s" % (nombre, extra))


def pedir(path, datos=None, headers=None, metodo=None):
    req = urllib.request.Request(BASE + path, data=datos, method=metodo)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def multipart(campos, nombre_archivo, contenido):
    b = "----testboundary9182736455"
    partes = []
    for k, v in campos.items():
        partes.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                       % (b, k, v)).encode("utf-8"))
    partes.append(("--%s\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"%s\"\r\n"
                   "Content-Type: video/mp4\r\n\r\n" % (b, nombre_archivo)).encode("utf-8"))
    partes.append(contenido)
    partes.append(("\r\n--%s--\r\n" % b).encode("utf-8"))
    return b"".join(partes), "multipart/form-data; boundary=" + b


def medir(ruta):
    """(ancho, alto) leyendo la salida de ffmpeg."""
    exe = ps.ffmpeg_local()
    r = subprocess.run([exe, "-hide_banner", "-i", ruta], capture_output=True,
                       timeout=60, creationflags=ps.CREATE_NO_WINDOW)
    import re
    m = re.search(rb"Video:.*?[, ](\d{2,5})x(\d{2,5})", r.stderr or b"")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


print("=" * 70)
print("PRUEBA DEL BLOQUE DE VIDEO")
print("=" * 70)

exe = ps.ffmpeg_local()
check("ffmpeg detectado", bool(exe), "-> %s" % exe)
if not exe:
    sys.exit(1)

# ---------- 1. loteo por PESO ----------
print("\n[1] Loteo de publicacion por peso")


def lotear(archivos, LOTE=40, LOTE_BYTES=20 * 1024 * 1024):
    lotes, actual, peso = [], [], 0
    for a in archivos:
        p = len(a["content"])
        if actual and (len(actual) >= LOTE or peso + p > LOTE_BYTES):
            lotes.append(actual)
            actual, peso = [], 0
        actual.append(a)
        peso += p
    if actual:
        lotes.append(actual)
    return lotes


gordos = [{"content": "x" * (9 * 1024 * 1024)} for _ in range(3)]
check("3 archivos de 9MB -> 2 lotes", len(lotear(gordos)) == 2, "(dio %d)" % len(lotear(gordos)))
chicos = [{"content": "x" * 1000} for _ in range(100)]
check("100 chicos -> 3 lotes por cantidad", len(lotear(chicos)) == 3, "(dio %d)" % len(lotear(chicos)))
enorme = [{"content": "x" * (30 * 1024 * 1024)}]
check("1 archivo mas grande que el tope viaja igual", len(lotear(enorme)) == 1)
check("ningun lote queda vacio", all(len(l) > 0 for l in lotear(gordos + chicos)))

# ---------- 2. firma de contenedor ----------
print("\n[2] Validacion de firma")
check("mp4 reconocido", ps.firma_video(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 40) == "mp4")
check("webm reconocido", ps.firma_video(b"\x1a\x45\xdf\xa3" + b"\x00" * 40) == "webm")
check("PDF rechazado", ps.firma_video(b"%PDF-1.7" + b"\x00" * 40) is None)
check("basura rechazada", ps.firma_video(b"hola") is None)

# ---------- 3. video de prueba ----------
print("\n[3] Generando un video VERTICAL pesado")
crudo = os.path.join(ps.STATE_DIR, "test_crudo.mp4")
subprocess.run([exe, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=15",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=15",
                "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "20M",
                "-c:a", "aac", "-pix_fmt", "yuv420p", crudo],
               timeout=300, creationflags=ps.CREATE_NO_WINDOW)
peso_crudo = os.path.getsize(crudo)
print("     video crudo: %.1f MB, %s" % (peso_crudo / 1048576.0, medir(crudo)))
check("el crudo supera el tope publicable", peso_crudo > ps.MAX_VIDEO)

# ---------- 4. servidor ----------
print("\n[4] Levantando el panel en el puerto %d" % PORT)
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

cod, _, cuerpo = pedir("/api/video-capacidad")
cap = json.loads(cuerpo)
check("/api/video-capacidad responde", cod == 200 and cap.get("compresor") is True, str(cap))

# ---------- 5. rechazo de no-video ----------
print("\n[5] Rechazo de archivos que no son video")
cuerpo_m, ct = multipart({"key": KEY}, "truco.mp4", b"%PDF-1.7" + b"\x00" * 5000)
cod, _, resp = pedir("/api/upload-video", cuerpo_m, {"Content-Type": ct}, "POST")
check("un PDF disfrazado de .mp4 se rechaza", cod == 400 and b"no parece un video" in resp)

# ---------- 6. subida + compresion ----------
print("\n[6] Subida con compresion")
with open(crudo, "rb") as f:
    datos = f.read()
cuerpo_m, ct = multipart({"key": KEY}, "vertical.mp4", datos)
t0 = time.time()
cod, _, resp = pedir("/api/upload-video", cuerpo_m, {"Content-Type": ct}, "POST")
r = json.loads(resp)
check("la subida devuelve un job", cod == 200 and r.get("job"), str(r)[:200])

jid = r.get("job")
estado, vistos = {}, []
for _ in range(600):
    cod, _, resp = pedir("/api/job?id=" + jid)
    estado = json.loads(resp)
    if estado.get("pct") and estado["pct"] not in vistos:
        vistos.append(estado["pct"])
    if estado.get("estado") != "corriendo":
        break
    time.sleep(0.5)

print("     %s | %s | %.0fs" % (estado.get("estado"), estado.get("info", ""), time.time() - t0))
check("la compresion termino bien", estado.get("estado") == "listo", estado.get("error", ""))
check("el progreso avanzo (no salto de 0 a 100)", len(vistos) >= 2, "hitos=%s" % vistos[:6])

final = os.path.join(ps.MOD_ASSETS, KEY + ".mp4")
check("el archivo quedo en _modulos", os.path.isfile(final))
if os.path.isfile(final):
    peso_final = os.path.getsize(final)
    check("entra en el tope publicable", peso_final <= ps.MAX_VIDEO,
          "%.1f MB <= %d MB" % (peso_final / 1048576.0, ps.MAX_VIDEO // 1048576))
    a, al = medir(final)
    check("sigue siendo VERTICAL", al > a, "%dx%d" % (a, al))
    check("el lado largo quedo capado en 1280", max(a, al) <= 1280, "%dx%d" % (a, al))
    with open(final, "rb") as f:
        check("el resultado es un mp4 valido", ps.firma_video(f.read(64)) == "mp4")

# ---------- 7. Range ----------
print("\n[7] HTTP Range (Safari lo exige para reproducir)")
cod, hdr, cuerpo = pedir("/intranet/assets/_modulos/%s.mp4" % KEY, headers={"Range": "bytes=0-1023"})
check("responde 206 parcial", cod == 206, "(dio %d)" % cod)
check("manda Content-Range", bool(hdr.get("Content-Range")), hdr.get("Content-Range", ""))
check("manda exactamente 1024 bytes", len(cuerpo) == 1024, "(dio %d)" % len(cuerpo))
check("el content-type es video/mp4", hdr.get("Content-Type") == "video/mp4", hdr.get("Content-Type", ""))
cod, hdr, cuerpo = pedir("/intranet/assets/_modulos/%s.mp4" % KEY)
check("sin Range responde 200 entero", cod == 200 and len(cuerpo) == os.path.getsize(final))
check("avisa Accept-Ranges", hdr.get("Accept-Ranges") == "bytes")
cod, hdr, _ = pedir("/intranet/assets/_modulos/%s.mp4" % KEY,
                    headers={"Range": "bytes=99999999999-"})
check("un rango imposible da 416", cod == 416, "(dio %d)" % cod)

# ---------- limpieza ----------
print("\n[8] Limpieza")
httpd.shutdown()
borrados = 0
for f in (crudo, final):
    try:
        os.remove(f)
        borrados += 1
    except OSError:
        pass
for f in os.listdir(ps.STATE_DIR):
    if f.startswith(("subida_", "comprimido_")):
        try:
            os.remove(os.path.join(ps.STATE_DIR, f))
        except OSError:
            pass
check("se borro el video de prueba de _modulos", not os.path.isfile(final))
check("no quedaron temporales", not [f for f in os.listdir(ps.STATE_DIR)
                                     if f.startswith(("subida_", "comprimido_"))])

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok_total, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
