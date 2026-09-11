# -*- coding: utf-8 -*-
"""Corre las suites de web3 (el panel que está EN PRODUCCIÓN desde v34).

Por qué vive aparte de correr_todo.py: t1-t4 fueron escritas para **web2** y
usan sus selectores (`.nav-s[data-sec]`, entre otros). web3 tiene otro
armazón, así que sus suites son otras. Un solo panel puede servir una sola
carpeta web por corrida, de modo que las dos familias no pueden convivir en
la misma ejecución.

    python correr_web3.py            # arma el sandbox, levanta, corre todas
    python correr_web3.py --solo w1  # sólo una

Seguridad (igual que el resto de la suite): el sandbox es una COPIA
descartable —intranet, scripts sueltos y estado— y el panel se lanza
apuntando ahí con MYS_PROYECTO/MYS_PANEL_STATE. Encima, cada suite intercepta
`/api/publicar` y `/api/enviar` en el navegador, así que ni una publicación de
prueba puede llegar al sitio que ven los vendedores.
"""
import os
import shutil
import json
import re
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
          ("w3 avisos", "w3_web3_avisos.py"),
          ("w4 link a un bloque", "w4_web3_link_bloque.py"),
          ("w5 cargar a un modulo", "w5_web3_cargar_modulo.py"),
          ("w6 reportes de una planilla", "w6_web3_informes.py"),
          ("w7 boton actualizar", "w7_web3_actualizar.py"),
          ("w8 pendientes y avisos", "w8_web3_pendientes_avisos.py"),
          ("w9 tutoriales", "w9_web3_tutoriales.py")]


def armar_sandbox():
    """Copia descartable. El estado sale del estado de desarrollo si existe
    (trae los reportes de Datos conectados); si no, arranca vacío.

    ⚠️ SE FRENA SI NO PUDO BORRAR LA COPIA VIEJA. `rmtree(ignore_errors=True)`
    deja en silencio los archivos que no puede tocar —y no puede tocar los que
    tiene abiertos un panel que quedó corriendo de una prueba anterior—. El
    sandbox queda mitad viejo y mitad nuevo, y las suites empiezan a fallar por
    cosas que no pasaron: tres pruebas del editor de módulos fallaron así,
    varias corridas seguidas, con el código intacto. Mejor frenar y decirlo.
    """
    if os.path.isdir(SANDBOX):
        shutil.rmtree(SANDBOX, ignore_errors=True)
    if os.path.isdir(SANDBOX):
        quedan = sum(len(a) for _r, _d, a in os.walk(SANDBOX))
        raise SystemExit(
            "No pude borrar la copia de prueba: quedan %d archivos en\n"
            "  %s\n"
            "Casi siempre es un panel de una prueba anterior que sigue "
            "corriendo y tiene los archivos abiertos.\n"
            "Cerralo (Administrador de tareas -> python.exe) y probá de nuevo."
            % (quedan, SANDBOX))
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
    # w6 necesita una planilla YA conectada para tener qué medir. El estado de
    # desarrollo tiene los reportes pero no la copia local de la planilla, que
    # vive en el estado del panel instalado. Si está, se trae: así la suite
    # corre contra la planilla de verdad en vez de contra un invento.
    instalado = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PanelMyS_state")
    cache = os.path.join(SANDBOX, "state", "cache_google")
    if not os.path.isdir(cache) and os.path.isdir(instalado):
        if os.path.isdir(os.path.join(instalado, "cache_google")):
            shutil.copytree(os.path.join(instalado, "cache_google"), cache)
            shutil.copy2(os.path.join(instalado, "datos.json"),
                         os.path.join(SANDBOX, "state", "datos.json"))
            print("planilla conectada tomada del panel instalado")
    print("sandbox en %s" % SANDBOX)


def levantar():
    env = dict(os.environ)
    env.update({"MYS_PROYECTO": SANDBOX,
                "MYS_PANEL_STATE": os.path.join(SANDBOX, "state"),
                "MYS_PANEL_WEB": "web3",
                "MYS_PANEL_PORT": str(PUERTO),
                "BROWSER": "none"})       # que no abra el navegador en la cara
    # ⚠️ SI EL PUERTO YA ESTA OCUPADO, FRENAR. Si hay otro panel escuchando ahi
    #    —un PanelMyS.exe olvidado, una prueba anterior— el que arrancamos acá
    #    no puede tomar el puerto y muere; pero el chequeo de abajo le pega al
    #    VIEJO, lo encuentra vivo y la corrida sigue. Todas las suites terminan
    #    probando codigo viejo: paso, y durante varias corridas los fallos
    #    parecian del codigo nuevo cuando el codigo nuevo ni siquiera corria.
    try:
        urllib.request.urlopen(BASE + "/api/config", timeout=2).read()
        ocupado = True
    except (urllib.error.URLError, OSError):
        ocupado = False
    if ocupado:
        raise SystemExit(
            "Ya hay un panel escuchando en %s.\n"
            "Las pruebas le hablarian a ESE y no al codigo de ahora.\n"
            "Cerralo (Administrador de tareas -> PanelMyS.exe o python.exe) "
            "y proba de nuevo." % BASE)

    log = open(os.path.join(SALIDA, "panel-web3.log"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, "panel_server.py"], cwd=PANEL_SRC,
                         env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(40):
        try:
            crudo = urllib.request.urlopen(BASE + "/api/config", timeout=1).read()
            cfg = json.loads(crudo.decode("utf-8"))
            # y que sea EL NUESTRO: se compara la version que dice con la que
            # tiene el fuente que acabamos de arrancar
            if _version_del_fuente() and cfg.get("version") != _version_del_fuente():
                p.terminate()
                raise SystemExit(
                    "El panel que contesta en %s dice VERSION %s y el fuente "
                    "es %s: hay otro panel ocupando el puerto."
                    % (BASE, cfg.get("version"), _version_del_fuente()))
            print("panel web3 arriba en %s/ (VERSION %s)" % (BASE, cfg.get("version")))
            return p
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(0.5)
    p.terminate()
    raise SystemExit("el panel no levantó; mirá salida/panel-web3.log")


def _version_del_fuente():
    """El VERSION que declara panel_server.py, para poder comprobar que el que
    contesta es el que acabamos de arrancar."""
    try:
        txt = open(os.path.join(PANEL_SRC, "panel_server.py"),
                   encoding="utf-8").read()
        m = re.search(r"^VERSION = (\d+)", txt, re.M)
        return int(m.group(1)) if m else 0
    except (OSError, ValueError):
        return 0


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
