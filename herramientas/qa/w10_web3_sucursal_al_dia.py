# -*- coding: utf-8 -*-
"""La pantalla de una SUCURSAL se puede poner al dia (v61, 14-sep-2026).

    python w10_web3_sucursal_al_dia.py      (exit 1 si algo falla)

Antes de la v61 el boton «Traer ultima version» se escondia en toda sucursal
sin central, y despues de publicar la pantalla seguia con la lista de modulos
que tenia en memoria. Esta suite levanta web3 como SUCURSAL en una carpeta
temporal (nada real) y mira:
  · que el boton este a la vista y que su pregunta diga que lo propio se conserva
  · que despues de publicar con cosas traidas de otra computadora, la pantalla
    recargue los modulos (si no, el proximo guardado borraria lo traido) y avise
  · que la central siga sin ver el boton
La publicacion esta interceptada en el navegador: no sale nada.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(AQUI, "..", "panel")
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
sys.path.insert(0, PANEL)
import fusion  # noqa: E402

fallas = []


def check(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  -> " + str(detalle)[:300]))
    if not cond:
        fallas.append(nombre)


def puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def copia_del_panel(tmp):
    """El panel, copiado SIN el panel_config.json de la central.

    ⚠️ Si se corre desde herramientas/panel, el panel lee ESE panel_config.json
    y las dos instancias arrancan como CENTRAL: la "sucursal" de la prueba no
    era una sucursal y los checks de sucursal median otra cosa."""
    dest = os.path.join(tmp, "panel")
    os.makedirs(dest)
    for n_ in os.listdir(PANEL):
        if n_ in ("panel_config.json", "dist", "build", "instalador", "paquete",
                  "__pycache__", "datos", "investigacion"):
            continue
        o_ = os.path.join(PANEL, n_)
        (shutil.copytree if os.path.isdir(o_) else shutil.copy2)(o_, os.path.join(dest, n_))
    return dest


def levantar(tmp, rol, panel_dir):
    proy = os.path.join(tmp, rol, "proyecto")
    intr = os.path.join(proy, "intranet")
    os.makedirs(os.path.join(proy, "herramientas"))
    os.makedirs(intr)
    for f in ("index.html", "modulos.js", "galerias.js"):
        shutil.copy2(os.path.join(REPO, "intranet", f), os.path.join(intr, f))
    estado = os.path.join(tmp, rol, "estado")
    os.makedirs(estado)
    if rol == "sucursal":
        json.dump({"rol": "colaborador", "usuario": "Sucursal prueba", "publish_token": "x",
                   "central_url": "", "web_publica": "http://127.0.0.1:9/",
                   "cerebro_url": "http://127.0.0.1:9", "repo_api": "http://127.0.0.1:9",
                   "repo_raw": "http://127.0.0.1:9", "repo_zip": ""},
                  open(os.path.join(estado, "identity.json"), "w", encoding="utf-8"))
    pp = puerto_libre()
    env = dict(os.environ, MYS_PROYECTO=proy, MYS_PANEL_STATE=estado, MYS_PANEL_PORT=str(pp),
               MYS_PANEL_WEB="web3", BROWSER="none")
    proc = subprocess.Popen([sys.executable, os.path.join(panel_dir, "panel_server.py")], cwd=panel_dir,
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % pp
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/config", timeout=3)
            return proc, base, intr
        except Exception:  # noqa
            time.sleep(0.5)
    proc.kill()
    raise SystemExit("no arranco el panel (%s)" % rol)


def main():
    tmp = tempfile.mkdtemp(prefix="sandbox-w10-")
    procs = []
    try:
        panel_dir = copia_del_panel(tmp)
        suc, base_s, intr_s = levantar(tmp, "sucursal", panel_dir)
        procs.append(suc)
        cen, base_c, _ = levantar(tmp, "central", panel_dir)
        procs.append(cen)
        with sync_playwright() as p:
            br = p.chromium.launch()
            errores = []

            print("sucursal")
            ctx = br.new_context(viewport={"width": 1400, "height": 900})
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errores.append(str(e)))
            pg.goto(base_s + "/")
            pg.wait_for_timeout(2500)
            # ⚠️ Desde la v69 "Traer ultima version" vive DENTRO de Configuracion
            # (antes era #btnTraer suelto en el pie). La suite lo seguia buscando
            # afuera y fallaba desde el 19-sep sin que nada estuviera roto.
            pg.click("#btnConfig")
            pg.wait_for_timeout(500)
            check("el boton Traer ultima version esta a la vista", pg.locator("#cfgTraer").is_visible())
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(300)
            pg.evaluate("void traerUltima()")
            pg.wait_for_timeout(500)
            msg = pg.locator("#confirmMsg").inner_text()
            check("la pregunta dice que lo no publicado se conserva", "se conserva" in msg, msg)
            pg.click("#confirmNo")
            pg.wait_for_timeout(400)

            # lo que hace el servidor al publicar: combina y reescribe modulos.js.
            # Se simula escribiendo en disco una publicacion "de otra PC" y
            # respondiendo como el servidor.
            ruta = os.path.join(intr_s, "modulos.js")
            partes = fusion.partes(open(ruta, encoding="utf-8").read())
            cart = next(m for m in partes["modulos"] if m["key"] == "cartelera")
            nueva = dict(cart["content"]["docs"][0], id="zzdeotrapc", titulo="De otra PC")
            cart["content"]["docs"].insert(0, nueva)
            open(ruta, "w", encoding="utf-8").write(
                "window.MODULES = " + json.dumps(partes["modulos"], ensure_ascii=False) + ";\n"
                "window.AJUSTES = " + json.dumps(partes["ajustes"]) + ";\n"
                "window.TUTORIALES = " + json.dumps(partes["tutoriales"], ensure_ascii=False) + ";\n")
            respuesta = {"ok": True, "log": "", "fusion": {
                "traidos": ["Cartelera: De otra PC"], "choques": ["Manual"], "imagenes": 0, "aviso": ""}}
            pg.route("**/api/publicar", lambda r: r.fulfill(
                status=200, content_type="application/json", body=json.dumps(respuesta)))
            antes = pg.evaluate("MODULOS.find(m => m.key === 'cartelera').content.docs.length")
            pg.evaluate("publicarCambios(false, true)")
            pg.wait_for_timeout(2000)
            despues = pg.evaluate("MODULOS.find(m => m.key === 'cartelera').content.docs.map(d => d.id)")
            check("la pantalla recargo los modulos con lo traido",
                  "zzdeotrapc" in despues and len(despues) == antes + 1, despues)
            toast = pg.locator("#toast").inner_text()
            check("avisa lo que se sumo", "De otra PC" in toast, toast)
            check("y avisa el choque", "Manual" in toast and "quedó tu versión" in toast, toast)
            pg.wait_for_timeout(5000)
            check("el aviso dura lo suficiente para leerlo", pg.locator("#toast").is_visible())
            check("sin errores de JavaScript", not errores, errores)
            ctx.close()

            print("central")
            ctx = br.new_context(viewport={"width": 1400, "height": 900})
            pg = ctx.new_page()
            pg.goto(base_c + "/")
            pg.wait_for_timeout(2500)
            pg.click("#btnConfig")
            pg.wait_for_timeout(500)
            check("la central no ve el boton Traer", not pg.locator("#cfgTraer").is_visible())
            ctx.close()
            br.close()
    finally:
        for pr in procs:
            pr.terminate()
            try:
                pr.wait(10)
            except Exception:  # noqa
                pr.kill()
        time.sleep(0.5)
        shutil.rmtree(tmp, ignore_errors=True)
    print("")
    if fallas:
        print("FALLARON %d: %s" % (len(fallas), "; ".join(fallas)))
        sys.exit(1)
    print("todo ok")


if __name__ == "__main__":
    main()
