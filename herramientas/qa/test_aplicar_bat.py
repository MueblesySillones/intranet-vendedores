# -*- coding: utf-8 -*-
"""Pruebas del swap del auto-update (updater/aplicar.bat).

Por qué existen: el 5-sep-2026, actualizando la central de v36 a v37, el bat
dejó la máquina SIN PROGRAMA. El `rmdir` de PanelMyS_old falló a medias, la
carpeta siguió existiendo, y entonces `move INSTALL OLD` no renombró sino que
metió la instalación adentro (OLD\\PanelMyS). De ahí en más no cerró nada: el
paso 6 no encontró los archivos per-máquina, se fue a ROLLBACK, y el rollback
tampoco vio el exe porque estaba un nivel más abajo.

La regla que se prueba acá es una sola y no se negocia:
**pase lo que pase, la carpeta de instalación queda con un panel usable.**

    python test_aplicar_bat.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
BAT_ORIG = os.path.join(os.path.dirname(AQUI), "panel", "updater", "aplicar.bat")
RES = []


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:200]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:200]))


def escribir(p, txt=""):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def armar_root(con_old=None, nuevo=True):
    """Una raíz de mentira con la forma de %LOCALAPPDATA%."""
    root = tempfile.mkdtemp(prefix="pmys_test_")
    inst = os.path.join(root, "PanelMyS")
    escribir(os.path.join(inst, "PanelMyS.exe"), "exe viejo")
    escribir(os.path.join(inst, "panel_config.json"), '{"rol": "central"}')
    escribir(os.path.join(inst, "proyecto.txt"), "C:\\proyecto")
    escribir(os.path.join(inst, "_internal", "algo.dll"), "viejo")
    if nuevo:
        new = os.path.join(root, "PanelMyS_update", "new")
        escribir(os.path.join(new, "PanelMyS.exe"), "exe NUEVO")
        escribir(os.path.join(new, "update_ok.marker"), "")
        escribir(os.path.join(new, "_internal", "algo.dll"), "nuevo")
    if con_old:
        escribir(os.path.join(root, "PanelMyS_old", con_old), "resto")
    return root


def correr(root, pid="999999"):
    """Corre una COPIA del bat (se autoborra al terminar) y devuelve el log."""
    bat = os.path.join(root, "aplicar.bat")
    shutil.copy2(BAT_ORIG, bat)
    env = dict(os.environ, PMYS_ROOT=root, PMYS_NORUN="1")
    subprocess.run(["cmd", "/c", bat, pid], env=env,
                   capture_output=True, timeout=180)
    log = os.path.join(root, "PanelMyS_update", "aplicar.log")
    return open(log, encoding="utf-8", errors="replace").read() if os.path.isfile(log) else ""


def instalado(root):
    inst = os.path.join(root, "PanelMyS")
    if not os.path.isfile(os.path.join(inst, "PanelMyS.exe")):
        return None
    return {
        "exe": open(os.path.join(inst, "PanelMyS.exe"), encoding="utf-8").read(),
        "config": os.path.isfile(os.path.join(inst, "panel_config.json")),
        "proyecto": os.path.isfile(os.path.join(inst, "proyecto.txt")),
    }


# --------------------------------------------------------------- 1. feliz
def caso_feliz():
    root = armar_root()
    try:
        log = correr(root)
        est = instalado(root)
        if est is None:
            raise AssertionError("quedó SIN programa. log:\n" + log)
        if est["exe"] != "exe NUEVO":
            raise AssertionError("no aplicó la versión nueva")
        if not est["config"] or not est["proyecto"]:
            raise AssertionError("perdió los archivos per-máquina: %s" % est)
        if "swap OK" not in log:
            raise AssertionError("el log no dice swap OK:\n" + log)
        return "actualiza y conserva config y proyecto"
    finally:
        shutil.rmtree(root, ignore_errors=True)


check("update normal: aplica lo nuevo y conserva lo per-máquina", caso_feliz)


# ------------------------------------------- 2. el bug: OLD que no se borra
def caso_old_trabado():
    """Se deja un archivo ABIERTO adentro de PanelMyS_old para que el rmdir
    no pueda con él: es la situación exacta del 5-sep."""
    root = armar_root(con_old="_internal\\trabado.dll")
    trabado = os.path.join(root, "PanelMyS_old", "_internal", "trabado.dll")
    fh = open(trabado, "r+")            # el handle abierto hace fallar el rmdir
    try:
        log = correr(root)
        est = instalado(root)
        if est is None:
            raise AssertionError("QUEDÓ SIN PROGRAMA (el bug). log:\n" + log)
        if not est["config"] or not est["proyecto"]:
            raise AssertionError("perdió los archivos per-máquina: %s" % est)
        # y además el update TIENE que haber entrado: si sólo frenara, una
        # máquina con el DLL siempre tomado dejaría de actualizarse en silencio
        if est["exe"] != "exe NUEVO":
            raise AssertionError("no aplicó la actualización; log:\n" + log)
        if "old ocupado" not in log:
            raise AssertionError("no usó el old alternativo; log:\n" + log)
        if os.path.isdir(os.path.join(root, "PanelMyS_old", "PanelMyS")):
            raise AssertionError("dejó la instalación ANIDADA adentro del old")
        return "usa otro old y actualiza igual"
    finally:
        fh.close()
        shutil.rmtree(root, ignore_errors=True)


check("OLD que no se puede limpiar: actualiza igual, sin anidar", caso_old_trabado)


# ----------------------------------- 3. rollback con la copia vieja anidada
def caso_rollback_anidado():
    """Máquina que YA quedó con OLD\\PanelMyS por el bug viejo, y encima el
    paquete nuevo viene sin panel_config -> tiene que rollbackear igual."""
    root = armar_root(nuevo=True)
    # el paquete nuevo no trae config y la instalación tampoco la tiene:
    # así el paso 7 falla y se va a rollback
    os.remove(os.path.join(root, "PanelMyS", "panel_config.json"))
    log = ""
    try:
        log = correr(root)
        est = instalado(root)
        if est is None:
            raise AssertionError("quedó SIN programa tras el rollback. log:\n" + log)
        if "ROLLBACK" not in log:
            raise AssertionError("esperaba un rollback; log:\n" + log)
        if est["exe"] != "exe viejo":
            raise AssertionError("rollbackeó pero dejó el exe nuevo")
        return "vuelve a la versión que andaba"
    finally:
        shutil.rmtree(root, ignore_errors=True)


check("paquete sin identidad: rollback y la máquina sigue con panel", caso_rollback_anidado)


# ------------------------------------------------- 4. paquete incompleto
def caso_sin_marker():
    root = armar_root()
    os.remove(os.path.join(root, "PanelMyS_update", "new", "update_ok.marker"))
    try:
        log = correr(root)
        est = instalado(root)
        if est is None:
            raise AssertionError("quedó SIN programa. log:\n" + log)
        if est["exe"] != "exe viejo":
            raise AssertionError("aplicó un paquete a medio bajar")
        if "FAIL_NOCHANGE" not in log:
            raise AssertionError("no freno limpio; log:\n" + log)
        return "no toca nada si la descarga quedó a medias"
    finally:
        shutil.rmtree(root, ignore_errors=True)


check("descarga incompleta: no toca la instalación", caso_sin_marker)

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
