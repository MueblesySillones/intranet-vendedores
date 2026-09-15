# -*- coding: utf-8 -*-
"""Arma los DOS instaladores del panel, al dia con la version publicada.

    python armar_instalador.py                 (y copia al Escritorio)
    python armar_instalador.py --sin-escritorio

Por que existe: los instaladores se armaban a mano y quedaban atras. El 14-sep
el del Escritorio era de la v40 (5-sep) con el panel publicado en la v60, tenia
la version escrita a mano (1.17.0) y el paquete de contenido del 5-sep. Una
sucursal instalada con eso arranca con la cartelera y los modulos de hace 10
dias, y como publicar sube modulos.js ENTERO, su primera publicacion pisaria lo
que el resto publico despues.

Lo que hace, y frena si algo no cierra:
  1) lee VERSION / VERSION_PUBLICA de panel_server.py
  2) verifica que dist/PanelMyS sea EXACTAMENTE la version publicada: compara el
     PanelMyS.exe con el que esta dentro de <repo>/panel/PanelMyS-vNN.zip (el
     codigo Python viaja adentro del exe, asi que si coincide, es la misma)
  3) verifica que el repo este al dia con origin y sin cambios en intranet/
     (si no, el instalador llevaria contenido sin publicar o viejo)
  4) rehace paquete/Proyecto MyS/intranet con los archivos de intranet/ que
     estan en git (solo lo publicado; nada per-maquina)
  5) compila SucursalAuto.iss y PanelMyS.iss con /DAppVer=<VERSION_PUBLICA>
     (ISCC se llama sin shell: Git Bash manglaba los /D...)
  6) copia los dos .exe a Escritorio\\Proyecto Intranet\\Panel MyS
"""
import ast
import hashlib
import re
import urllib.error
import urllib.request
import io
import os
import shutil
import subprocess
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
DIST = os.path.join(AQUI, "dist", "PanelMyS")
PAQUETE = os.path.join(AQUI, "paquete", "Proyecto MyS")
SALIDA = os.path.join(AQUI, "instalador")
ISCC = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe")
ESCRITORIO = os.path.join(os.path.expanduser("~"), "Desktop", "Proyecto Intranet", "Panel MyS")

INSTALADORES = [
    ("SucursalAuto.iss", "Instalar Sucursal.exe"),
    ("PanelMyS.iss", "Instalar Panel MyS.exe"),
]


def frenar(msg):
    print("\nFRENO: " + msg)
    sys.exit(1)


def leer_version():
    src = io.open(os.path.join(AQUI, "panel_server.py"), encoding="utf-8").read()
    out = {}
    for nodo in ast.parse(src).body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            t = nodo.targets[0]
            if isinstance(t, ast.Name) and t.id in ("VERSION", "VERSION_PUBLICA"):
                out[t.id] = ast.literal_eval(nodo.value)
    if len(out) != 2:
        frenar("no encontre VERSION / VERSION_PUBLICA en panel_server.py")
    return out["VERSION"], out["VERSION_PUBLICA"]


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def verificar_dist(version):
    exe = os.path.join(DIST, "PanelMyS.exe")
    if not os.path.isfile(exe):
        frenar("no existe dist/PanelMyS/PanelMyS.exe. Compila la version publicada primero.")
    zpath = os.path.join(REPO, "panel", "PanelMyS-v%d.zip" % version)
    if not os.path.isfile(zpath):
        frenar("no esta %s. El fuente dice v%d pero esa version no esta publicada "
               "(o falta hacer git pull)." % (zpath, version))
    with zipfile.ZipFile(zpath) as z:
        publicado = sha1(z.read("PanelMyS.exe"))
    local = sha1(open(exe, "rb").read())
    if publicado != local:
        frenar("dist/PanelMyS NO es la v%d publicada (el exe no coincide con el del zip). "
               "Recompila con PanelMyS.spec antes de armar el instalador." % version)
    for f in ("proyecto.txt", "panel_config.json", "identity.json"):
        if os.path.exists(os.path.join(DIST, f)):
            frenar("dist/PanelMyS tiene %s: es de una maquina y no puede viajar." % f)
    print("  dist = v%d publicada (exe %s)" % (version, local[:10]))


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        frenar("git %s fallo: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def verificar_repo():
    git("fetch", "-q", "origin")
    local, remoto = git("rev-parse", "HEAD").strip(), git("rev-parse", "origin/main").strip()
    if local != remoto:
        base = git("merge-base", "HEAD", "origin/main").strip()
        if base == local:
            frenar("el repo esta ATRAS de origin/main: hace git pull (el contenido del paquete saldria viejo).")
        if base != remoto:
            frenar("el repo y origin/main se separaron: hace git pull antes de armar el instalador.")
        # adelante de origin: solo importa si esos commits tocan el contenido
        if git("diff", "--name-only", "origin/main", "HEAD", "--", "intranet").strip():
            frenar("hay commits locales en intranet/ que origin/main no tiene: "
                   "el paquete llevaria contenido que no esta publicado.")
    sucio = git("status", "--porcelain", "--", "intranet").strip()
    if sucio:
        frenar("hay cambios sin publicar en intranet/:\n" + sucio)
    print("  repo al dia con origin/main (%s), intranet/ limpio" % local[:7])


def rehacer_paquete():
    destino = os.path.join(PAQUETE, "intranet")
    if os.path.isdir(destino):
        shutil.rmtree(destino)
    archivos = [l for l in git("ls-files", "-z", "--", "intranet").split("\0") if l]
    for rel in archivos:
        src = os.path.join(REPO, *rel.split("/"))
        dst = os.path.join(PAQUETE, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    # herramientas/ vacia: panel_server reconoce la raiz del proyecto por
    # tener intranet/ Y herramientas/
    herr = os.path.join(PAQUETE, "herramientas")
    os.makedirs(herr, exist_ok=True)
    if os.listdir(herr):
        frenar("paquete/Proyecto MyS/herramientas tiene archivos y tiene que viajar vacia.")
    if not os.path.isfile(os.path.join(destino, "modulos.js")):
        frenar("el paquete quedo sin intranet/modulos.js")
    print("  paquete de contenido rehecho: %d archivos de intranet/" % len(archivos))


CEREBRO = "https://mys-cerebro.mueblesysillones.workers.dev"


def verificar_clave():
    """Regla del dueno: quien instala, publica sin cargar nada. Entonces la
    clave que viaja en el instalador tiene que ANDAR: se le pregunta al cerebro
    con una lectura (/audit) antes de compilar. Un 401 frena todo."""
    ruta = os.path.join(AQUI, "clave-equipo.iss")
    if not os.path.isfile(ruta):
        frenar("falta clave-equipo.iss: los instaladores saldrian sin la clave de publicacion.")
    m = re.search(r'#define\s+PubKey\s+"([^"]+)"', io.open(ruta, encoding="utf-8-sig").read())
    if not m or not m.group(1).strip():
        frenar("clave-equipo.iss no tiene la clave (#define PubKey \"...\").")
    req = urllib.request.Request(CEREBRO + "/audit", headers={
        "Authorization": "Bearer " + m.group(1).strip(), "User-Agent": "PanelMyS/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            codigo = r.status
    except urllib.error.HTTPError as e:
        codigo = e.code
    except Exception as e:  # noqa
        frenar("no pude verificar la clave con el cerebro (%s). Sin internet no se arma." % e)
    if codigo != 200:
        frenar("el cerebro RECHAZA la clave de clave-equipo.iss (HTTP %s): las sucursales "
               "no podrian publicar. Actualizar la clave antes de armar." % codigo)
    print("  la clave del equipo la acepta el cerebro")


def compilar(version_publica):
    if not os.path.isfile(ISCC):
        frenar("no encuentro Inno Setup en %s" % ISCC)
    hechos = []
    for iss, exe in INSTALADORES:
        salida = os.path.join(SALIDA, exe)
        if os.path.exists(salida):
            os.remove(salida)
        r = subprocess.run([ISCC, "/Q", "/DAppVer=" + version_publica, iss], cwd=AQUI,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not os.path.isfile(salida):
            frenar("ISCC fallo con %s:\n%s\n%s" % (iss, r.stdout[-3000:], r.stderr[-3000:]))
        mb = os.path.getsize(salida) / 1024 / 1024
        print("  %s  (%.0f MB, version %s)" % (exe, mb, version_publica))
        hechos.append(salida)
    return hechos


def main():
    al_escritorio = "--sin-escritorio" not in sys.argv
    version, publica = leer_version()
    print("Armando los instaladores del panel v%d (%s)" % (version, publica))
    verificar_dist(version)
    verificar_repo()
    verificar_clave()
    rehacer_paquete()
    hechos = compilar(publica)
    if al_escritorio:
        if not os.path.isdir(ESCRITORIO):
            frenar("no existe %s (los instaladores quedaron en %s)" % (ESCRITORIO, SALIDA))
        for h in hechos:
            shutil.copy2(h, os.path.join(ESCRITORIO, os.path.basename(h)))
        print("  copiados a %s" % ESCRITORIO)
    print("\nListo.")


if __name__ == "__main__":
    main()
