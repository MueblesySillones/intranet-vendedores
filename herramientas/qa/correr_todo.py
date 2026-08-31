# -*- coding: utf-8 -*-
"""Corre la suite completa: sandbox -> servidores -> t1..t4 -> resumen.

    python correr_todo.py                     la corrida normal
    python correr_todo.py --capturar-baseline solo regenera qa/baseline/
    python correr_todo.py --solo t2 t3        solo esos bloques (con sandbox nuevo)
    python correr_todo.py --sin-sandbox       reusa el sandbox que ya está

Levanta el panel (desde PANEL_SRC, contra el sandbox) y la intranet estática
en los puertos de PANEL_URL / INTRA_URL, como procesos hijos con log en
salida/logs/. Pase lo que pase los baja al final: cero procesos huérfanos.

El exit code global es 1 si algún bloque falló. t4 sin baseline devuelve 2 y
se informa como PENDIENTE (no es falla: la baseline se captura recién con el
rediseño integrado).

Antes de t4 el sandbox se rearma: t2 deja publicaciones de prueba y estados
cambiados, y la regresión visual tiene que comparar contenido de fábrica
contra contenido de fábrica.
"""
import os
import subprocess
import sys
import time

import arnes
import crear_sandbox

AQUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def lanzar(nombre, orden):
    """Proceso hijo con su salida en salida/logs/<nombre>.log."""
    log = open(os.path.join(arnes.LOGS, nombre + ".log"), "w", encoding="utf-8")
    p = subprocess.Popen([PY, os.path.join(AQUI, "arnes.py"), orden],
                         stdout=log, stderr=subprocess.STDOUT, cwd=AQUI)
    p._log = log  # para cerrarlo al final
    return p


def cola_log(nombre, lineas=15):
    try:
        with open(os.path.join(arnes.LOGS, nombre + ".log"), encoding="utf-8",
                  errors="replace") as f:
            for ln in f.readlines()[-lineas:]:
                print("      | " + ln.rstrip())
    except OSError:
        pass


def bajar(procs):
    """Apaga los servidores propios (solo los que lanzamos nosotros)."""
    for nombre, p in procs.items():
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
        if getattr(p, "_log", None):
            p._log.close()
        print("  servidor %s: apagado (rc=%s)" % (nombre, p.returncode))


def armar_sandbox_con_reintento():
    """En Windows un archivo momentáneamente abierto puede frenar el rmtree;
    un segundo intento tras una pausa lo resuelve casi siempre."""
    try:
        crear_sandbox.crear()
    except (OSError, PermissionError) as e:
        print("  (reintento del sandbox: %s)" % str(e)[:80])
        time.sleep(2)
        crear_sandbox.crear()


def correr_bloque(nombre, script, args=()):
    print("\n---- %s ----" % nombre)
    t0 = time.time()
    r = subprocess.run([PY, os.path.join(AQUI, script)] + list(args), cwd=AQUI)
    print("---- %s: exit %d (%.0fs) ----" % (nombre, r.returncode, time.time() - t0))
    return r.returncode


def main(argv):
    solo = []
    if "--solo" in argv:
        i = argv.index("--solo")
        solo = [a for a in argv[i + 1:] if not a.startswith("--")]
    baseline = "--capturar-baseline" in argv
    sin_sandbox = "--sin-sandbox" in argv

    arnes.exportar_config()
    # cinturón además de los tirantes del arnés: que TODOS los hijos (tests y
    # servidores) escriban UTF-8 aunque hereden un pipe cp1252
    os.environ["PYTHONIOENCODING"] = "utf-8"
    arnes.preparar_salida()
    print("== SUITE QA MyS ==")
    print("  panel:    %s (fuente: %s)" % (arnes.PANEL_URL, arnes.PANEL_SRC))
    print("  intranet: %s" % arnes.INTRA_URL)
    print("  proyecto: %s" % arnes.PROYECTO)
    print("  sandbox:  %s" % arnes.SANDBOX)

    if not sin_sandbox:
        armar_sandbox_con_reintento()
    elif not os.path.isdir(arnes.SANDBOX):
        print("--sin-sandbox pero no existe %s; lo creo igual" % arnes.SANDBOX)
        armar_sandbox_con_reintento()

    procs = {}
    resultados = {}
    try:
        procs["panel"] = lanzar("panel", "servir-panel")
        procs["intranet"] = lanzar("intranet", "servir-intranet")
        if not arnes.esperar_url(arnes.PANEL_URL, 60):
            print("  el panel no levantó; últimas líneas del log:")
            cola_log("panel")
            bajar(procs)
            return 1
        if not arnes.esperar_url(arnes.INTRA_URL, 30):
            print("  la intranet no levantó; últimas líneas del log:")
            cola_log("intranet")
            bajar(procs)
            return 1
        print("  servidores arriba.")

        if baseline:
            resultados["t4 baseline"] = correr_bloque(
                "t4 baseline", "t4_visual.py", ["--capturar-baseline"])
        else:
            bloques = [("t1 crawl", "t1_crawl.py", []),
                       ("t2 flujos", "t2_flujos.py", []),
                       ("t3 intranet", "t3_intranet.py", []),
                       ("t4 visual", "t4_visual.py", [])]
            if solo:
                bloques = [b for b in bloques if b[0].split()[0] in solo]
            for nombre, script, args in bloques:
                if nombre.startswith("t4") and not solo and not sin_sandbox:
                    print("\n(rearmo el sandbox: t4 compara contenido de fábrica)")
                    armar_sandbox_con_reintento()
                resultados[nombre] = correr_bloque(nombre, script, args)
    finally:
        print()
        bajar(procs)

    print("\n================ RESUMEN ================")
    duro = 0
    for nombre, rc in resultados.items():
        if rc == 0:
            estado = "OK"
        elif rc == 2 and nombre.startswith("t4"):
            estado = "PENDIENTE (sin baseline)"
        else:
            estado = "FALLA"
            duro = 1
        print("  %-14s %s" % (nombre, estado))
    print("=========================================")
    print("evidencia: %s" % arnes.EVID)
    return duro


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
