# -*- coding: utf-8 -*-
"""
PUBLICAR EL REDISEÑO DEL PANEL (v28) — correr en la PC que tiene el código al día
=================================================================================

Qué hace, en orden, y frena solo si algo no cierra:

  1. copia web2/redisenio2026.css desde este repo al panel
  2. le agrega el <link> al index.html del panel (si no está)
  3. sube VERSION a 28 y la versión pública a 1.3.0
  4. compila con PyInstaller
  5. arma el paquete (subir_update.py)
  6. VERIFICA adentro del zip antes de publicar
  7. git add panel && commit && push

Uso, parado en la carpeta del panel del proyecto real:

    python publicar_redisenio.py  <ruta-al-repo-mys-panel>

Ejemplo:
    cd C:\\...\\intranet-vendedores\\herramientas\\panel
    python C:\\...\\mys-panel\\publicar_redisenio.py C:\\...\\mys-panel

Por qué VERSION va a 28 y no a 27: la 27 YA está publicada y en uso. El
auto-update compara int(remota) > VERSION, así que una segunda 27 no la baja
nadie y las PCs que ya tomaron la primera quedan clavadas.
"""
import io, os, re, subprocess, sys, json, zipfile, hashlib

# La proxima version sale SOLA de la que este publicada + 1: asi no hay que
# editar este archivo cada vez, ni se repite un numero (una version repetida no
# la baja nadie, porque el auto-update compara int(remota) > VERSION).
NUEVA_VERSION = None  # se calcula abajo
NUEVA_PUBLICA = None  # se toma la del fuente si no se cambia
NUEVO_LABEL = "el panel en blanco (ajustes de color)"
NUEVAS_NOTAS = ("El panel cambio de color: donde antes era crema ahora es blanco, igual que "
                "la intranet que ven los vendedores. Asi lo que ves mientras editas se "
                "parece a lo que se publica. El boton Publicar pasa a negro para que se "
                "distinga del resto, y la chapita NUEVO tambien. Nada cambio de lugar: "
                "todo esta donde estaba.")


def morir(msg):
    print("\n  FRENO: " + msg)
    print("  No se publico nada.")
    sys.exit(1)


def paso(n, txt):
    print("\n[%d] %s" % (n, txt))


aqui = os.getcwd()
if not os.path.isfile(os.path.join(aqui, "panel_server.py")):
    morir("corré esto parado en herramientas/panel del proyecto real "
          "(no encuentro panel_server.py acá)")

if len(sys.argv) < 2:
    morir("falta la ruta al repo mys-panel.\n"
          "  Uso: python publicar_redisenio.py <ruta-al-repo-mys-panel>")
repo_backup = sys.argv[1]
origen_css = os.path.join(repo_backup, "panel", "web2", "redisenio2026.css")
if not os.path.isfile(origen_css):
    morir("no encuentro redisenio2026.css en %s" % origen_css)

# ---------------------------------------------------------------- 0. avisos
paso(0, "Chequeando que nadie haya publicado mientras tanto")
repo_raiz = os.path.abspath(os.path.join(aqui, "..", ".."))
subprocess.run(["git", "fetch", "origin", "-q"], cwd=repo_raiz)
r = subprocess.run(["git", "rev-list", "--count", "HEAD..origin/main"],
                   cwd=repo_raiz, capture_output=True, text=True)
pendientes = (r.stdout or "0").strip()
if pendientes not in ("0", ""):
    morir("origin/main tiene %s commit(s) que no tenés. Hacé `git pull` y "
          "revisá si alguien publico otra version del panel antes de seguir." % pendientes)
print("    ok: main al dia")

vj = os.path.join(repo_raiz, "panel", "version.json")
if os.path.isfile(vj):
    pub = json.load(io.open(vj, encoding="utf-8"))
    print("    publicado ahora: v%s - %s" % (pub.get("version"), pub.get("label")))
    NUEVA_VERSION = int(pub.get("version", 0)) + 1
    print("    la nueva va a ser la v%d" % NUEVA_VERSION)
else:
    morir("no encuentro panel/version.json para saber que numero sigue")

# ---------------------------------------------------------------- 1. el CSS
paso(1, "El CSS del rediseño ya esta en web2/")
print("    ok: %d bytes" % os.path.getsize(origen_css))

# ---------------------------------------------------------------- 2. el link
paso(2, "Enlazandolo en web2/index.html")
idx = os.path.join(aqui, "web2", "index.html")
html = io.open(idx, encoding="utf-8").read()
if "redisenio2026.css" in html:
    print("    ya estaba enlazado")
else:
    ancla = '<link rel="stylesheet" href="/static/mejoras.css">'
    if ancla not in html:
        morir("no encuentro la linea de mejoras.css en index.html para poner el link despues")
    html = html.replace(ancla, ancla +
                        '\n<!-- Redisenio 2026: va ULTIMO, solo pisa colores. Borrar esta linea revierte. -->'
                        '\n<link rel="stylesheet" href="/static/redisenio2026.css">', 1)
    io.open(idx, "w", encoding="utf-8").write(html)
    print("    -> link agregado al final")

# ---------------------------------------------------------------- 3. version
paso(3, "Subiendo la version a %d (%s)" % (NUEVA_VERSION, NUEVA_PUBLICA))
ps = os.path.join(aqui, "panel_server.py")
src = io.open(ps, encoding="utf-8").read()

m = re.search(r"^VERSION\s*=\s*(\d+)\s*$", src, re.M)
if not m:
    morir("no encuentro `VERSION = <n>` en panel_server.py")
actual = int(m.group(1))
print("    VERSION actual: %d" % actual)
if actual >= NUEVA_VERSION:
    morir("VERSION ya esta en %d. Subí NUEVA_VERSION arriba de ese numero." % actual)
src = re.sub(r"^VERSION\s*=\s*\d+\s*$", "VERSION = %d" % NUEVA_VERSION, src, count=1, flags=re.M)

if NUEVA_PUBLICA:
    src = re.sub(r'^VERSION_PUBLICA\s*=\s*".*?"\s*$',
                 'VERSION_PUBLICA = "%s"' % NUEVA_PUBLICA, src, count=1, flags=re.M)
src = re.sub(r'^VERSION_LABEL\s*=\s*".*?"\s*$',
             'VERSION_LABEL = "%s"' % NUEVO_LABEL, src, count=1, flags=re.M)

i = src.find("VERSION_NOTES")
if i < 0:
    morir("no encuentro VERSION_NOTES en panel_server.py")
j = src.index("\n", src.index(")", i))
troz = ['VERSION_NOTES = (']
palabras, linea = NUEVAS_NOTAS.split(" "), ""
for w in palabras:
    if len(linea) + len(w) > 66:
        troz.append('                 "%s "' % linea.strip())
        linea = ""
    linea += w + " "
troz.append('                 "%s")' % linea.strip())
src = src[:i] + "\n".join(troz) + src[j:]
io.open(ps, "w", encoding="utf-8").write(src)
print("    -> VERSION = %d, publica %s" % (NUEVA_VERSION, NUEVA_PUBLICA))

# ---------------------------------------------------------------- 4. compilar
paso(4, "Compilando (tarda ~30s)")
r = subprocess.run([sys.executable, "-m", "PyInstaller", "PanelMyS.spec", "--noconfirm"],
                   cwd=aqui, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stdout[-2000:]); print(r.stderr[-2000:])
    morir("PyInstaller fallo")
print("    -> dist/PanelMyS listo")

# ---------------------------------------------------------------- 5. paquete
paso(5, "Armando el paquete de actualizacion")
r = subprocess.run([sys.executable, "subir_update.py"], cwd=aqui, capture_output=True, text=True)
print("    " + (r.stdout or "").strip().replace("\n", "\n    "))
if r.returncode != 0:
    print(r.stderr[-1500:]); morir("subir_update.py fallo")

# ---------------------------------------------------------------- 6. verificar
paso(6, "Verificando el zip ANTES de publicar")
zp = os.path.join(repo_raiz, "panel", "PanelMyS-v%d.zip" % NUEVA_VERSION)
if not os.path.isfile(zp):
    morir("no se genero %s" % zp)
with zipfile.ZipFile(zp) as z:
    nombres = z.namelist()
    css = [n for n in nombres if "redisenio2026" in n]
    if not css:
        morir("el CSS del redisenio NO viajo adentro del zip (revisar 'web2' en datas del .spec)")
    print("    ok: el CSS viaja (%s)" % css[0])
    idxs = [n for n in nombres if n.endswith("web2/index.html")]
    if not idxs or "redisenio2026" not in z.read(idxs[0]).decode("utf-8", "replace"):
        morir("el index adentro del zip no enlaza el CSS")
    print("    ok: el index lo enlaza")
    malos = [n for n in nombres if any(x in n.lower() for x in
             ("panel_config.json", "identity.json", "proyecto.txt", "aprobaciones/"))]
    if malos:
        morir("se colaron archivos per-maquina en el zip: %s" % malos)
    print("    ok: sin archivos per-maquina")
dec = json.load(io.open(os.path.join(repo_raiz, "panel", "version.json"), encoding="utf-8"))
sha = hashlib.sha256(io.open(zp, "rb").read()).hexdigest()
if sha != dec["sha256"] or os.path.getsize(zp) != dec["size"]:
    morir("el sha256/tamano del version.json no coincide con el zip")
print("    ok: sha256 y tamano coinciden")
if int(dec["version"]) != NUEVA_VERSION:
    morir("version.json quedo en %s y esperaba %d" % (dec["version"], NUEVA_VERSION))
print("    ok: version.json en v%d" % NUEVA_VERSION)

# ---------------------------------------------------------------- 7. publicar
paso(7, "Publicando")
subprocess.run(["git", "add", "panel"], cwd=repo_raiz, check=True)
msg = ("Panel v%d (%s): el panel en blanco\n\n"
       "El panel pasa de crema a blanco, igual que la intranet. Los tokens de color se\n"
       "redefinen en web2/redisenio2026.css, que se carga ULTIMO y no toca una sola\n"
       "regla de layout: nada cambia de lugar.\n\n"
       "Verificado adentro del zip antes de publicar: el CSS viaja, el index lo enlaza,\n"
       "no se colo ningun archivo per-maquina, y el sha256/tamano coinciden.\n\n"
       "VERSION va a %d y no a 27 porque la 27 ya estaba publicada: el auto-update\n"
       "compara int(remota) > VERSION y una version repetida no la baja nadie.\n"
       % (NUEVA_VERSION, NUEVA_PUBLICA, NUEVA_VERSION))
subprocess.run(["git", "commit", "-m", msg], cwd=repo_raiz, check=True)
r = subprocess.run(["git", "push", "origin", "main"], cwd=repo_raiz, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1200:])
    morir("el push fallo. Si dice 'fetch first', alguien publico algo: hace `git pull` "
          "y volve a correr esto con NUEVA_VERSION = %d" % (NUEVA_VERSION + 1))

print("\n" + "=" * 62)
print("  PUBLICADO: v%d (%s)" % (NUEVA_VERSION, NUEVA_PUBLICA))
print("  Los paneles de las sucursales lo van a ver como actualizacion.")
print("  Falta solo instalarlo en la central (paso 4 del release).")
print("=" * 62)
