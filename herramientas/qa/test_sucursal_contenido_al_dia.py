# -*- coding: utf-8 -*-
"""Una sucursal recien instalada se pone al dia SOLA con el contenido.

Por que existe (22-sep-2026): se instalo una sucursal nueva y no le aparecian
los videos. Causa: el instalador lleva el contenido del dia en que se armo, y
el panel avisaba de versiones nuevas del PROGRAMA pero nunca de contenido
nuevo. La sucursal se quedaba con lo del instalador salvo que alguien tocara
"Traer ultima version" en Configuracion.

Levanta un panel como SUCURSAL con el contenido de un commit viejo (el que
llevaba el instalador del 19-sep) y verifica contra el sitio REAL:
  1. al abrir el panel aparecen las publicaciones que se hicieron despues
  2. aparece el tutorial cargado despues del instalador
  3. el video del tutorial se reproduce aunque el archivo no este en esa PC

Solo LEE de internet: no publica nada.

    python test_sucursal_contenido_al_dia.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.abspath(os.path.join(AQUI, "..", "panel"))
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
COMMIT_INSTALADOR = "0e080ad"      # 19-sep: lo que lleva el instalador del Escritorio

fallas = []


def check(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  -> " + str(detalle)[:300]))
    if not cond:
        fallas.append(nombre)


def puerto_libre():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    tmp = tempfile.mkdtemp(prefix="sucursal-nueva-")
    proy = os.path.join(tmp, "proyecto")
    os.makedirs(os.path.join(proy, "herramientas"))
    # la intranet TAL CUAL la lleva el instalador (contenido viejo)
    tar = os.path.join(tmp, "intranet.tar")
    with open(tar, "wb") as fh:
        subprocess.run(["git", "archive", COMMIT_INSTALADOR, "intranet"], cwd=REPO,
                       stdout=fh, check=True)
    shutil.unpack_archive(tar, proy, "tar")
    # el panel, copiado como en una sucursal: SIN el panel_config.json de la
    # central (si esta, el panel de prueba se cree central y no trae nada)
    panel_copia = os.path.join(tmp, "panel")
    os.makedirs(panel_copia)
    for n_ in os.listdir(PANEL):
        if n_ in ("panel_config.json", "dist", "build", "instalador", "__pycache__",
                  "datos", "investigacion", "flyers-archivados"):
            continue
        o_ = os.path.join(PANEL, n_)
        d_ = os.path.join(panel_copia, n_)
        (shutil.copytree if os.path.isdir(o_) else shutil.copy2)(o_, d_)

    estado = os.path.join(tmp, "estado")
    os.makedirs(estado)
    json.dump({"rol": "colaborador", "usuario": "Sucursal nueva", "publish_token": "x"},
              open(os.path.join(estado, "identity.json"), "w", encoding="utf-8"))

    viejo = open(os.path.join(proy, "intranet", "modulos.js"), encoding="utf-8").read()
    pp = puerto_libre()
    env = dict(os.environ, MYS_PROYECTO=proy, MYS_PANEL_STATE=estado,
               MYS_PANEL_PORT=str(pp), MYS_PANEL_WEB="web3", BROWSER="cmd.exe /c echo")
    proc = subprocess.Popen([sys.executable, os.path.join(panel_copia, "panel_server.py")],
                            cwd=panel_copia, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % pp
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/config", timeout=3)
                break
            except Exception:  # noqa
                time.sleep(0.5)
        else:
            raise SystemExit("no arranco el panel")

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page(viewport={"width": 1400, "height": 900})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(base + "/")
            pg.wait_for_timeout(12000)       # combinar con lo publicado + repintar

            ahora = open(os.path.join(proy, "intranet", "modulos.js"), encoding="utf-8").read()
            check("el contenido se puso al dia solo", ahora != viejo,
                  "modulos.js quedo igual al del instalador")

            tut = json.loads(urllib.request.urlopen(base + "/api/tutoriales", timeout=20)
                             .read().decode("utf-8")).get("tutoriales") or []
            check("llegaron los tutoriales publicados despues", len(tut) > 0, tut)

            if tut:
                src = tut[0].get("src") or ""
                pg.goto(base + "/")
                pg.wait_for_timeout(3000)
                pg.click("nav >> text=Tutoriales")
                pg.wait_for_timeout(1000)
                pg.click("[data-ver-tut]")
                pg.wait_for_timeout(8000)
                v = pg.evaluate("""()=>{const v=document.getElementById('tutVideo');
                    return v ? {listo:v.readyState, dur:v.duration, ancho:v.videoWidth} : null}""")
                check("el video del tutorial se reproduce", bool(v) and v["ancho"] > 0 and v["listo"] >= 2, v)
                check("el archivo quedo guardado en la sucursal",
                      os.path.isfile(os.path.join(proy, "intranet", *src.split("/"))), src)

            check("sin errores de javascript", not errs, errs[:3])
            br.close()
    finally:
        proc.terminate()
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fallas:
        print("%d FALLA(S): %s" % (len(fallas), ", ".join(fallas)))
        return 1
    print("todo ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
