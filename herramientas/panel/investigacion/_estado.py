# -*- coding: utf-8 -*-
"""Chequeo de estado: que lo instalado, lo empaquetado y lo publicado sean
lo mismo que el codigo fuente. Sin suponer nada."""
import io, os, re, sys, json, hashlib, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

R = r"C:\Users\Redes 1\Documents\web dinamica-mys"
P = os.path.join(R, "herramientas", "panel")
INST = os.path.join(os.environ["LOCALAPPDATA"], "PanelMyS")
DIST = os.path.join(P, "dist", "PanelMyS")
ESC = r"C:\Users\Redes 1\Desktop\Panel MyS"
ok, mal = [], []


def chk(n, c, extra=""):
    (ok if c else mal).append(n)
    print("  %s %s %s" % ("OK  " if c else "MAL ", n, extra))


def sha(p):
    return hashlib.sha256(io.open(p, "rb").read()).hexdigest()[:12] if os.path.isfile(p) else "(falta)"


print("=" * 72)
print("ESTADO DEL BUILD Y LA PUBLICACION")
print("=" * 72)

# --- 1. version en el codigo ---
src = io.open(os.path.join(P, "panel_server.py"), encoding="utf-8").read()
ver_src = int(re.search(r"^VERSION\s*=\s*(\d+)", src, re.M).group(1))
print("\n[1] Version")
print("     codigo fuente: %d" % ver_src)

# --- 2. el dist tiene lo mismo que web/ ---
print("\n[2] Lo empaquetado (dist) vs el codigo fuente")
for f in ("app.js", "styles.css", "index.html"):
    a = os.path.join(P, "web", f)
    b = os.path.join(DIST, "_internal", "web", f)
    chk("dist/%s igual al fuente" % f, sha(a) == sha(b), "%s vs %s" % (sha(a), sha(b)))

# --- 3. lo instalado tiene lo mismo que el dist ---
print("\n[3] Lo instalado vs lo empaquetado")
for f in ("app.js", "styles.css", "index.html"):
    a = os.path.join(DIST, "_internal", "web", f)
    b = os.path.join(INST, "_internal", "web", f)
    chk("instalado/%s igual al dist" % f, sha(a) == sha(b), "%s vs %s" % (sha(a), sha(b)))
chk("el .exe instalado es el del dist",
    sha(os.path.join(DIST, "PanelMyS.exe")) == sha(os.path.join(INST, "PanelMyS.exe")))

# --- 4. lo que anuncia el panel andando ---
print("\n[4] El panel que esta corriendo")
try:
    with urllib.request.urlopen("http://127.0.0.1:8125/update/version", timeout=6) as r:
        v = json.load(r)
    chk("anuncia la version del codigo", v.get("version") == ver_src,
        "anuncia %s, codigo %s" % (v.get("version"), ver_src))
except Exception as e:
    chk("el receptor responde", False, str(e)[:60])
try:
    with urllib.request.urlopen("http://127.0.0.1:8124/api/config", timeout=6) as r:
        c = json.load(r)
    chk("el panel responde", True, "rol=%s cerebro=%s token=%s"
        % (c.get("rol"), c.get("cerebro"), c.get("tiene_token")))
except Exception as e:
    chk("el panel responde", False, str(e)[:60])

# --- 5. archivos propios de esta maquina ---
print("\n[5] Lo propio de esta computadora (no se debe pisar)")
for f in ("proyecto.txt", "panel_config.json"):
    chk("sobrevive %s" % f, os.path.isfile(os.path.join(INST, f)))
chk("el lanzador vive fuera del arbol que se reemplaza",
    os.path.isfile(os.path.join(os.path.dirname(INST), "PanelMyS_run", "PanelMyS_run.vbs")))

# --- 6. instalador del escritorio ---
print("\n[6] Instalador para llevar a otra PC")
inst_p = os.path.join(P, "instalador", "Instalar Panel MyS.exe")
esc_p = os.path.join(ESC, "Instalar Panel MyS.exe")
chk("el del Escritorio es el recien compilado", sha(inst_p) == sha(esc_p), "%s vs %s" % (sha(inst_p), sha(esc_p)))
if os.path.isfile(esc_p):
    import datetime
    print("     fecha: %s  (%.1f MB)" % (
        datetime.datetime.fromtimestamp(os.path.getmtime(esc_p)).strftime("%d/%m %H:%M"),
        os.path.getsize(esc_p) / 1048576))

# --- 7. git ---
print("\n[7] Publicacion por git (codigo de la intranet)")
def g(*a):
    return subprocess.run(["git"] + list(a), cwd=R, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()
g("fetch", "origin")
chk("no hay cambios sin commitear", g("status", "--short") == "", g("status", "--short")[:80])
chk("local y el sitio estan a la par", g("rev-list", "--left-right", "--count", "HEAD...origin/main") == "0\t0",
    g("rev-list", "--left-right", "--count", "HEAD...origin/main"))
print("     ultimo commit: " + g("log", "--oneline", "-1"))

# --- 8. contenido publicado en el sitio ---
print("\n[8] Lo que quedo en el sitio")
idx = g("show", "origin/main:intranet/index.html")
for nombre, marca in (("plantilla de WhatsApp", ".manual .wt-msg"),
                      ("iconos blindados", ".wa-btn .ico svg"),
                      ("tablas ordenables", ".m-tablaw"),
                      ("novedades", "renderNovedades"),
                      ("video", ".manual .m-video")):
    chk("esta publicado: %s" % nombre, marca in idx)

print("\n" + "=" * 72)
print("%d bien, %d mal" % (len(ok), len(mal)))
if mal:
    print("REVISAR: " + " · ".join(mal))
print("=" * 72)
