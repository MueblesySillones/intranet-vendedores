# -*- coding: utf-8 -*-
"""Borrar publicaciones SEGUIDAS sin que vuelvan (v64, 15-sep-2026).

    python w12_web3_borrar_seguidas.py      (exit 1 si algo falla)

Lo que reporto el dueno: «pongo eliminar publicacion, se va a la papelera,
pero si quiero eliminar otra, la que borre antes se ve de nuevo en la
cartelera». La causa era que la API de GitHub tarda hasta 60 s en mostrar lo
ultimo publicado. Esta suite hace lo mismo que la persona, en el navegador,
contra un GitHub FALSO que se atrasa igual que el real y un cerebro FALSO (no
toca el sitio). Borra una desde el editor y otra desde el menu ⋯, una atras de
la otra, y mira la cartelera, la papelera y lo que quedo publicado.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(AQUI, "..", "panel")
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
sys.path.insert(0, AQUI)
sys.path.insert(0, PANEL)
import fusion  # noqa: E402
import test_publicar_fusion as tpf  # noqa: E402  (GitHub y cerebro falsos)

fallas = []


def check(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  -> " + str(detalle)[:300]))
    if not cond:
        fallas.append(nombre)


def puerto_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


def main():
    tmp = tempfile.mkdtemp(prefix="sandbox-w12-")
    proc = None
    try:
        real = open(os.path.join(REPO, "intranet", "modulos.js"), encoding="utf-8").read()
        p = fusion.partes(real)
        cart = next(m for m in p["modulos"] if m["key"] == "cartelera")["content"]
        molde = cart["docs"][0]
        for i, t in (("zzbA", "QA borrar A"), ("zzbB", "QA borrar B"), ("zzbC", "QA queda C")):
            cart["docs"].insert(0, dict(molde, id=i, titulo=t, fijado=False, archivado=False))
        txt = tpf.texto_modulos(p)
        index = open(os.path.join(REPO, "intranet", "index.html"), "rb").read()
        base_arch = {"index.html": index, "galerias.js": b"window.GALLERIES = {};\n",
                     "modulos.js": txt.encode("utf-8")}
        tpf.REPO_F.commit(dict(base_arch))

        proy = os.path.join(tmp, "proyecto")
        intr = os.path.join(proy, "intranet")
        os.makedirs(os.path.join(proy, "herramientas"))
        os.makedirs(intr)
        open(os.path.join(intr, "index.html"), "wb").write(index)
        open(os.path.join(intr, "modulos.js"), "w", encoding="utf-8").write(txt)
        open(os.path.join(intr, "galerias.js"), "w", encoding="utf-8").write("window.GALLERIES = {};\n")
        estado = os.path.join(tmp, "estado")
        os.makedirs(estado)

        pf = puerto_libre()
        srv = ThreadingHTTPServer(("127.0.0.1", pf), tpf.Manejador)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        falso = "http://127.0.0.1:%d" % pf
        json.dump({"rol": "colaborador", "usuario": "Sucursal QA", "publish_token": "x",
                   "cerebro_url": falso + "/cerebro", "repo_api": falso + "/api",
                   "repo_raw": falso + "/raw", "repo_zip": falso + "/zip/main",
                   "repo_git": falso + "/git", "web_publica": falso + "/web", "central_url": ""},
                  open(os.path.join(estado, "identity.json"), "w", encoding="utf-8"))
        pp = puerto_libre()
        env = dict(os.environ, MYS_PROYECTO=proy, MYS_PANEL_STATE=estado, MYS_PANEL_PORT=str(pp),
                   MYS_PANEL_WEB="web3", BROWSER="cmd.exe /c echo")
        proc = subprocess.Popen([sys.executable, os.path.join(PANEL, "panel_server.py")], cwd=PANEL,
                                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = "http://127.0.0.1:%d" % pp
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/config", timeout=3)
                break
            except Exception:  # noqa
                time.sleep(0.5)

        def publicado():
            c = next(m for m in fusion.partes(tpf.REPO_F.texto("modulos.js"))["modulos"]
                     if m["key"] == "cartelera")["content"]
            return [d["id"] for d in c["docs"]], [d["id"] for d in c.get("papelera") or []]

        with sync_playwright() as pw:
            br = pw.chromium.launch()
            ctx = br.new_context(viewport={"width": 1400, "height": 900})
            pg = ctx.new_page()
            errores = []
            pg.on("pageerror", lambda e: errores.append(str(e)))
            pg.goto(base + "/")
            pg.wait_for_timeout(2500)
            pg.click('[data-sec="muro"]')
            pg.wait_for_selector("#viewMuro", state="visible")

            def titulos():
                return [h.text_content() for h in pg.query_selector_all("#muroLista .pub h3")]

            def tarjeta(t):
                for el in pg.query_selector_all("#muroLista .pub"):
                    h = el.query_selector("h3")
                    if h and t in h.text_content():
                        return el
                return None

            def sacar_tarjeta_publicar():
                try:
                    if pg.eval_on_selector("#pubCard", "e => !e.hidden && e.classList.contains('on')"):
                        pg.click("#pubCard")
                        pg.wait_for_timeout(300)
                except Exception:  # noqa
                    pass

            def esperar_publicacion(n_antes):
                for _ in range(100):
                    if tpf.REPO_F.publicaciones > n_antes:
                        break
                    time.sleep(0.2)
                pg.wait_for_timeout(1500)

            def menu(t, accion):
                """abre el ⋯ de una tarjeta y elige; si la lista se repinto en
                el medio (el menu se cierra), lo intenta de nuevo"""
                for _ in range(5):
                    sacar_tarjeta_publicar()
                    el = tarjeta(t)
                    if el is None:
                        raise AssertionError("no esta la tarjeta %r: %s" % (t, titulos()))
                    el.query_selector(".mp-mas").click()
                    try:
                        pg.click('#mpMenu [data-a="%s"]' % accion, timeout=2500)
                        return
                    except Exception:  # noqa
                        pg.wait_for_timeout(600)
                raise AssertionError("no pude abrir el menu de %r" % t)

            # GitHub se atrasa como el real desde aca
            tpf.REPO_F.atrasada = True

            print("borrar A desde el editor")
            menu("QA borrar A", "editar")
            pg.wait_for_selector("#fondo.on", state="visible")
            n = tpf.REPO_F.publicaciones
            pg.click("#coEliminar")
            pg.wait_for_selector("#confirmModal.on", state="visible")
            pg.click("#confirmYes")
            esperar_publicacion(n)
            check("A sale de la cartelera", "QA borrar A" not in " ".join(titulos()), titulos())
            ids, pap = publicado()
            check("A se publico borrada y en la papelera", "zzbA" not in ids and "zzbA" in pap, (ids[:4], pap))

            print("enseguida, borrar B desde el menu ⋯")
            n = tpf.REPO_F.publicaciones
            menu("QA borrar B", "borrar")
            pg.wait_for_selector("#confirmModal.on", state="visible")
            pg.click("#confirmYes")
            esperar_publicacion(n)
            check("el menu ⋯ tambien sube al sitio", tpf.REPO_F.publicaciones > n)
            vistos = " ".join(titulos())
            check("B sale de la cartelera", "QA borrar B" not in vistos, titulos())
            check("A NO vuelve a aparecer en la cartelera", "QA borrar A" not in vistos, titulos())
            check("C sigue", "QA queda C" in vistos, titulos())
            ids, pap = publicado()
            check("publicado: ni A ni B", "zzbA" not in ids and "zzbB" not in ids, ids[:5])
            check("publicado: las dos en la papelera", "zzbA" in pap and "zzbB" in pap, pap)

            print("recargar la pagina")
            pg.reload()
            pg.wait_for_timeout(2500)
            pg.click('[data-sec="muro"]')
            pg.wait_for_timeout(800)
            vistos = " ".join(titulos())
            check("despues de recargar tampoco vuelven", "QA borrar A" not in vistos and "QA borrar B" not in vistos,
                  titulos())

            print("restaurar A desde la papelera")
            pg.click('[data-sec="archivadas"]')
            pg.wait_for_timeout(1200)
            n = tpf.REPO_F.publicaciones
            fila = None
            for el in pg.query_selector_all(".en-papelera, .arch"):
                if "QA borrar A" in (el.text_content() or ""):
                    fila = el
                    break
            boton = fila.query_selector('[data-p="restaurar"], [data-a="rest"]') if fila else None
            if boton:
                boton.click()
                esperar_publicacion(n)
                ids, pap = publicado()
                check("restaurar la vuelve a publicar", "zzbA" in ids and "zzbA" not in pap, (ids[:4], pap))
                check("sin resucitar a B", "zzbB" not in ids, ids[:5])
            else:
                check("encuentro el boton de restaurar A", False,
                      [e.inner_html()[:200] for e in pg.query_selector_all(".en-papelera, .arch")][:2])
            check("sin errores de JavaScript", not errores, errores)
            br.close()
    finally:
        tpf.REPO_F.atrasada = False
        if proc:
            proc.terminate()
            try:
                proc.wait(10)
            except Exception:  # noqa
                proc.kill()
        time.sleep(0.5)
        shutil.rmtree(tmp, ignore_errors=True)
    print("")
    if fallas:
        print("FALLARON %d: %s" % (len(fallas), "; ".join(fallas)))
        sys.exit(1)
    print("todo ok")


if __name__ == "__main__":
    main()
