# -*- coding: utf-8 -*-
"""Enviar una publicacion a UNA grilla elegida del modulo, sin el texto.

Por que existe (22-sep-2026), pedido del usuario: "cuando creo una publicacion
la cual solo voy a subir una imagen que se vincule a material descargable, me
gustaria poder seleccionar a que bloque o grilla quiero dejar la imagen. Y el
titulo y cuerpo que le pongo a la publicacion que no aparezca en ese modulo,
ya que el modulo de material descargables literalmente solo se cargan archivos
para descargar".

Antes: el panel elegia SOLO la ultima grilla y copiaba ademas el titulo y el
cuerpo como bloques del modulo, que despues habia que ir a borrar a mano.

Levanta el panel sobre una copia de la intranet (nada real: la publicacion se
intercepta en el navegador) y verifica:
  1. el selector ofrece las grillas del modulo + "al final, como bloque nuevo"
  2. la foto entra en la grilla ELEGIDA (no en la ultima)
  3. NO se agregan el titulo ni el cuerpo al modulo
  4. eligiendo "al final" si se agregan, como antes

    python test_cargar_en_grilla.py
"""
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.abspath(os.path.join(AQUI, "..", "panel"))
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
FOTO = os.path.join(REPO, "intranet", "assets", "promos_bancarias")

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


def main():
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="grilla-")
    proy = os.path.join(tmp, "proyecto")
    os.makedirs(os.path.join(proy, "herramientas"))
    shutil.copytree(os.path.join(REPO, "intranet"), os.path.join(proy, "intranet"))
    estado = os.path.join(tmp, "estado")
    os.makedirs(estado)
    mod_js = os.path.join(proy, "intranet", "modulos.js")

    def grillas_de(key="descargables"):
        s = io.open(mod_js, encoding="utf-8").read()
        i = s.index("window.MODULES = ")
        j = s.index("\n];", i) + 2
        mods = json.loads(s[i + len("window.MODULES = "):j])
        m = [x for x in mods if x.get("key") == key][0]
        return m["content"]["bloques"]

    fotos = [f for f in os.listdir(FOTO) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
    if not fotos:
        print("sin foto de prueba en assets/promos_bancarias: salteada")
        return 0
    foto = os.path.join(FOTO, fotos[0])

    pp = puerto_libre()
    env = dict(os.environ, MYS_PROYECTO=proy, MYS_PANEL_STATE=estado,
               MYS_PANEL_PORT=str(pp), MYS_PANEL_WEB="web3", BROWSER="none")
    # ⚠️ desde una COPIA del panel sin panel_config.json: desde herramientas/panel
    # lee la clave y el cerebro REALES de la central, y asi esta prueba publico
    # en el sitio real el 23-sep (vacio las galerias).
    import test_publicar_fusion as _tpf
    _pan = _tpf.copia_del_panel(os.path.dirname(proy))
    proc = subprocess.Popen([sys.executable, os.path.join(_pan, "panel_server.py")],
                            cwd=_pan, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

        antes = grillas_de()
        idx_grillas = [i for i, b in enumerate(antes) if b.get("t") == "galeria"]
        if len(idx_grillas) < 2:
            print("el modulo de descargables tiene menos de 2 grillas: salteada")
            return 0
        elegida = idx_grillas[0]          # la PRIMERA, que no es la que se elegia sola
        ultima = idx_grillas[-1]
        n_elegida = len(antes[elegida]["items"])
        n_ultima = len(antes[ultima]["items"])

        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page(viewport={"width": 1440, "height": 950})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route("**/api/publicar", lambda r: r.fulfill(
                status=200, content_type="application/json",
                body=json.dumps({"ok": True, "log": "", "fusion": {
                    "traidos": [], "choques": [], "imagenes": 0, "aviso": ""}})))
            pg.goto(base + "/")
            pg.wait_for_timeout(2500)

            def publicar_con(destino):
                pg.click("text=¿Qué querés comunicarle al equipo?")
                pg.wait_for_timeout(1000)
                pg.fill("#coTitulo", "Placa de prueba")
                pg.fill("#coTexto", "Texto que NO va al modulo")
                with pg.expect_file_chooser() as fc:
                    pg.click('.co-ad[data-ad="medios"]')
                fc.value.set_files(foto)
                pg.wait_for_timeout(6000)
                pg.click("#coCargarBtn")
                pg.wait_for_timeout(400)
                pg.select_option("#coCargarMod", "descargables")
                pg.wait_for_timeout(400)
                op = pg.eval_on_selector_all("#coCargarGrilla option", "e=>e.map(o=>o.value)")
                # se elige por la lista LINDA (la que ve la persona), no por el
                # <select> tapado: asi la prueba pasa por el mismo camino
                pg.query_selector_all(".sel2-b")[1].click()
                pg.wait_for_timeout(400)
                i = op.index(destino)
                pg.click('.sel2-pop.on button[data-i="%d"]' % i)
                pg.wait_for_timeout(300)
                pg.click("#coPublicar")
                pg.wait_for_timeout(9000)
                return op

            op = publicar_con(str(elegida))
            check("ofrece cada grilla y el bloque nuevo",
                  len(op) == len(idx_grillas) + 1 and op[-1] == "", op)
            desp = grillas_de()
            check("la foto entro en la grilla ELEGIDA",
                  len(desp[elegida]["items"]) == n_elegida + 1,
                  [n_elegida, len(desp[elegida]["items"])])
            check("no toco la ultima grilla",
                  len(desp[ultima]["items"]) == n_ultima,
                  [n_ultima, len(desp[ultima]["items"])])
            check("no agrego el titulo ni el cuerpo al modulo",
                  len(desp) == len(antes), [len(antes), len(desp)])

            antes2 = grillas_de()
            publicar_con("")                     # al final, como bloque nuevo
            desp2 = grillas_de()
            agregados = [b.get("t") for b in desp2[len(antes2):]]
            check("eligiendo 'al final' si copia titulo, texto y foto",
                  agregados[:3] == ["titulo", "parrafo", "imagen"], agregados)

            check("sin errores de javascript", not errs, errs[:3])
            br.close()
    finally:
        proc.terminate()
        time.sleep(1)
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fallas:
        print("%d FALLA(S): %s" % (len(fallas), ", ".join(fallas)))
        return 1
    print("todo ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
