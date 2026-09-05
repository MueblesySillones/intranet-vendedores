# -*- coding: utf-8 -*-
"""Corre las suites de web3 (el panel que está EN PRODUCCIÓN desde v34).

Por qué vive aparte de correr_todo.py: t1-t4 fueron escritas para **web2** y
usan sus selectores (`.nav-s[data-sec]`, entre otros). web3 tiene otro
armazón, así que sus suites son otras. Un solo panel puede servir una sola
carpeta web por corrida, de modo que las dos familias no pueden convivir en
la misma ejecución.

    python correr_web3.py            # arma el sandbox, levanta, corre las 3
    python correr_web3.py --solo w1  # sólo una

Seguridad (igual que el resto de la suite): el sandbox es una COPIA
descartable —intranet, scripts sueltos y estado— y el panel se lanza
apuntando ahí con MYS_PROYECTO/MYS_PANEL_STATE. Encima, cada suite intercepta
`/api/publicar` y `/api/enviar` en el navegador, así que ni una publicación de
prueba puede llegar al sitio que ven los vendedores.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PROYECTO = os.environ.get("QA_PROYECTO") or os.path.dirname(os.path.dirname(AQUI))
PANEL_SRC = os.path.join(PROYECTO, "herramientas", "panel")
SALIDA = os.environ.get("QA_SALIDA") or os.path.join(AQUI, "salida")
SANDBOX = os.path.join(SALIDA, "sandbox-web3")
PUERTO = int(os.environ.get("QA_WEB3_PORT") or 8144)   # 8143 lo usa correr_todo
BASE = "http://127.0.0.1:%d" % PUERTO
SUITES = [("w1 panel", "w1_web3_panel.py"),
          ("w2 intranet", "w2_web3_intranet.py"),
          ("w3 avisos", "w3_web3_avisos.py")]


def armar_sandbox():
    """Copia descartable. El estado sale del estado de desarrollo si existe
    (trae los reportes de Datos conectados); si no, arranca vacío."""
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX, ignore_errors=True)
    os.makedirs(os.path.join(SANDBOX, "herramientas"), exist_ok=True)
    os.makedirs(os.path.join(SANDBOX, "state"), exist_ok=True)
    shutil.copytree(os.path.join(PROYECTO, "intranet"),
                    os.path.join(SANDBOX, "intranet"))
    for n in os.listdir(os.path.join(PROYECTO, "herramientas")):
        if n.endswith(".py"):
            shutil.copy2(os.path.join(PROYECTO, "herramientas", n),
                         os.path.join(SANDBOX, "herramientas", n))
    estado = os.path.join(PROYECTO, "herramientas", "PanelMyS_state")
    if os.path.isdir(estado):
        shutil.copytree(estado, os.path.join(SANDBOX, "state"), dirs_exist_ok=True)
    print("sandbox en %s" % SANDBOX)


def levantar():
    env = dict(os.environ)
    env.update({"MYS_PROYECTO": SANDBOX,
                "MYS_PANEL_STATE": os.path.join(SANDBOX, "state"),
                "MYS_PANEL_WEB": "web3",
                "MYS_PANEL_PORT": str(PUERTO),
                "BROWSER": "none"})       # que no abra el navegador en la cara
    log = open(os.path.join(SALIDA, "panel-web3.log"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "panel_server.py"], cwd=PANEL_SRC,
                         env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(40):
        try:
            urllib.request.urlopen(BASE + "/api/config", timeout=1).read()
            print("panel web3 arriba en %s/" % BASE)
            return p
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    p.terminate()
    raise SystemExit("el panel no levantó; mirá salida/panel-web3.log")


def main():
    solo = None
    if "--solo" in sys.argv:
        solo = sys.argv[sys.argv.index("--solo") + 1]
    os.makedirs(SALIDA, exist_ok=True)
    armar_sandbox()
    panel = levantar()
    fallos = []
    try:
        for nombre, script in SUITES:
            if solo and not nombre.startswith(solo):
                continue
            print("\n" + "=" * 60 + "\n%s\n" % nombre + "=" * 60)
            env = dict(os.environ, QA_BASE=BASE, QA_SANDBOX_WEB3=SANDBOX)
            r = subprocess.run([sys.executable, os.path.join(AQUI, script)],
                               cwd=AQUI, env=env)
            if r.returncode != 0:
                fallos.append(nombre)
    finally:
        panel.terminate()
        try:
            panel.wait(timeout=8)
        except subprocess.TimeoutExpired:
            panel.kill()
    print("\n" + "=" * 60)
    print("TERMINÓ con fallas en: %s" % ", ".join(fallos) if fallos
          else "TERMINÓ sin fallas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
