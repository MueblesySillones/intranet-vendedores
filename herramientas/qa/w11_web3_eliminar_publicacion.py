# -*- coding: utf-8 -*-
"""Eliminar una publicacion DESDE el editor (v62, 15-sep-2026).

    python w11_web3_eliminar_publicacion.py     (exit 1 si algo falla)

Pedido del dueno: «en editar la publicacion tiene que haber el boton de
eliminar». Levanta web3 en una carpeta temporal (nada real; publicar esta
interceptado en el navegador) y mira:
  · al CREAR no aparece el boton (no hay nada que eliminar)
  · al EDITAR aparece, abajo, con su rotulo
  · Cancelar en la pregunta no toca nada y el editor sigue abierto
  · Eliminar: pregunta, cierra el editor, saca la tarjeta del feed, la manda
    a la papelera (recuperable) y la sube al sitio en el momento
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
SALIDA = os.path.join(AQUI, "salida")
sys.path.insert(0, PANEL)
import fusion  # noqa: E402

fallas = []
TITULO = "QA eliminar desde el editor"


def check(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  -> " + str(detalle)[:300]))
    if not cond:
        fallas.append(nombre)


def main():
    tmp = tempfile.mkdtemp(prefix="sandbox-w11-")
    proc = None
    try:
        proy = os.path.join(tmp, "proyecto")
        intr = os.path.join(proy, "intranet")
        os.makedirs(os.path.join(proy, "herramientas"))
        os.makedirs(intr)
        for f in ("index.html", "modulos.js", "galerias.js"):
            shutil.copy2(os.path.join(REPO, "intranet", f), os.path.join(intr, f))
        estado = os.path.join(tmp, "estado")
        os.makedirs(estado)
        s = socket.socket(); s.bind(("127.0.0.1", 0)); pp = s.getsockname()[1]; s.close()
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

        def en_disco():
            return fusion.partes(open(os.path.join(intr, "modulos.js"), encoding="utf-8").read())

        with sync_playwright() as p:
            br = p.chromium.launch()
            ctx = br.new_context(viewport={"width": 1400, "height": 900})
            publicados = []

            def bloquear(r):
                publicados.append(1)
                r.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"ok": True, "log": "(bloqueado por la suite QA)"}))
            ctx.route("**/api/publicar", bloquear)
            pg = ctx.new_page()
            errores = []
            pg.on("pageerror", lambda e: errores.append(str(e)))
            pg.goto(base + "/")
            pg.wait_for_timeout(2500)
            pg.click('[data-sec="muro"]')
            pg.wait_for_selector("#viewMuro", state="visible")

            print("crear")
            pg.click("#btnNuevaPub")
            pg.wait_for_selector("#fondo.on", state="visible")
            check("al crear NO aparece Eliminar", not pg.is_visible("#coEliminar"))
            pg.fill("#coTitulo", TITULO)
            pg.fill("#coTexto", "Se elimina en esta misma prueba.")
            pg.click("#coPublicar")
            pg.wait_for_function("!document.querySelector('#fondo').classList.contains('on')", timeout=10000)

            def tarjeta():
                for el in pg.query_selector_all("#muroLista .pub"):
                    h = el.query_selector("h3")
                    if h and TITULO in h.text_content():
                        return el
                return None
            check("la publicacion esta en el feed", tarjeta() is not None)

            def abrir_editor():
                try:
                    if pg.eval_on_selector("#pubCard", "e => !e.hidden && e.classList.contains('on')"):
                        pg.click("#pubCard")
                        pg.wait_for_timeout(350)
                except Exception:  # noqa
                    pass
                tarjeta().query_selector(".mp-mas").click()
                pg.wait_for_selector("#mpMenu", state="visible")
                pg.click('#mpMenu [data-a="editar"]')
                pg.wait_for_selector("#fondo.on", state="visible")

            print("editar")
            abrir_editor()
            check("al editar SI aparece Eliminar", pg.is_visible("#coEliminar"))
            check("con su rotulo", "Eliminar publicación" in pg.text_content("#coEliminar"),
                  pg.text_content("#coEliminar"))
            caja = pg.locator("#coEliminar").bounding_box()
            pie = pg.locator("#fondo .modal-pie").bounding_box()
            check("queda adentro de la ventana, abajo",
                  caja and pie and caja["y"] >= pie["y"] and caja["y"] + caja["height"] <= pie["y"] + pie["height"] + 1,
                  (caja, pie))
            os.makedirs(SALIDA, exist_ok=True)
            pg.screenshot(path=os.path.join(SALIDA, "w11-editar-con-eliminar.png"))

            print("cancelar")
            pg.click("#coEliminar")
            pg.wait_for_selector("#confirmModal.on", state="visible")
            check("pregunta antes", "Eliminar publicación" in pg.text_content("#confirmTitle"),
                  pg.text_content("#confirmTitle"))
            check("y dice que se puede recuperar", "papelera" in pg.text_content("#confirmMsg"),
                  pg.text_content("#confirmMsg"))
            pg.screenshot(path=os.path.join(SALIDA, "w11-pregunta.png"))
            antes = len(publicados)
            pg.click("#confirmNo")
            pg.wait_for_timeout(600)
            check("Cancelar deja el editor abierto", pg.is_visible("#fondo.on"))
            check("y la publicacion sigue", tarjeta() is not None and
                  any(d.get("titulo") == TITULO for d in
                      next(m for m in en_disco()["modulos"] if m["key"] == "cartelera")["content"]["docs"]))
            check("y no sube nada", len(publicados) == antes)

            print("eliminar")
            pg.click("#coEliminar")
            pg.wait_for_selector("#confirmModal.on", state="visible")
            pg.click("#confirmYes")
            pg.wait_for_function("!document.querySelector('#fondo').classList.contains('on')", timeout=10000)
            pg.wait_for_timeout(1500)
            check("se cierra el editor", not pg.is_visible("#fondo.on"))
            check("la tarjeta sale del feed", tarjeta() is None)
            cont = next(m for m in en_disco()["modulos"] if m["key"] == "cartelera")["content"]
            check("sale de las publicaciones", not any(d.get("titulo") == TITULO for d in cont["docs"]))
            check("queda en la papelera, recuperable",
                  any(d.get("titulo") == TITULO for d in cont.get("papelera") or []))
            check("y se sube al sitio en el momento", len(publicados) == antes + 1, len(publicados) - antes)
            check("sin errores de JavaScript", not errores, errores)
            br.close()
    finally:
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
