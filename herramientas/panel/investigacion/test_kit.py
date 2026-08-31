# -*- coding: utf-8 -*-
"""Prueba el Kit de recuperacion: generarlo desde el panel, descargarlo, abrirlo
en un navegador limpio y descifrarlo. Verifica tambien que con la contrasena
equivocada NO se abra y que el secreto no viaje en claro dentro del archivo."""
import os
import re
import sys
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8190
CLAVE = "muebles-2026-secreta"
ok, fallos = 0, []


def check(n, c, extra=""):
    global ok
    if c:
        ok += 1
        print("  OK   %s %s" % (n, extra))
    else:
        fallos.append(n)
        print("  FALLA %s %s" % (n, extra))


# Corriendo desde el codigo fuente no hay panel_config.json (el real vive junto al
# .exe instalado), asi que la clave de publicacion vendria vacia y las
# verificaciones de "no viaja en claro" serian vacuas. Le ponemos una de prueba.
if not ps.PUBLISH_TOKEN:
    ps.PUBLISH_TOKEN = "CLAVE-DE-PRUEBA-9f3a7b2c"
    print("(sin panel_config.json: se usa una clave de prueba)")

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

print("=" * 70)
print("PRUEBA DEL KIT DE RECUPERACION")
print("=" * 70)

destino = os.path.join(ps.STATE_DIR, "kit_test.html")
with sync_playwright() as pw:
    nav = pw.chromium.launch()
    ctx = nav.new_context(accept_downloads=True)
    pag = ctx.new_page()
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)

    print("\n[1] La entrada es discreta pero existe")
    check("hay un enlace al kit", pag.query_selector("#btnKit") is not None)
    # discreto por TAMAÑO y POSICION, no por opacidad: atenuarlo lo dejaba en
    # 1,79:1 de contraste, o sea ilegible, y es la unica puerta al kit
    check("es discreto (chico y en gris secundario)", pag.evaluate("""() => {
        const s = getComputedStyle(document.querySelector('#btnKit'));
        return parseFloat(s.fontSize) <= 13 && s.color !== getComputedStyle(document.body).color;
    }"""))
    check("pero se lee (no esta atenuado)",
          float(pag.evaluate("() => getComputedStyle(document.querySelector('#btnKit')).opacity")) >= 0.95)
    check("no grita en el medio de la pantalla",
          pag.evaluate("() => !!document.querySelector('#btnKit').closest('.pie-discreto')"))

    print("\n[2] Validaciones antes de generar")
    pag.click("#btnKit")
    pag.wait_for_timeout(300)
    check("se abre el cuadro", pag.evaluate("() => !document.getElementById('kitModal').hidden"))
    check("viene con una clave ya generada", len(pag.input_value("#kitPass")) >= 12,
          pag.input_value("#kitPass"))
    check("la clave es dictable (palabras, no simbolos raros)",
          re.match(r"^[a-z]+(-[a-z]+){3}-\d\d$", pag.input_value("#kitPass")) is not None,
          pag.input_value("#kitPass"))
    primera = pag.input_value("#kitPass")
    pag.click("#kitOtra")
    pag.wait_for_timeout(150)
    check("el boton Generar otra da una distinta", pag.input_value("#kitPass") != primera)
    pag.fill("#kitPass", "corta")
    pag.click("#kitGenerar")
    pag.wait_for_timeout(200)
    check("rechaza una clave corta", "8 caracteres" in pag.text_content("#kitAviso"))

    print("\n[3] Generar y descargar")
    pag.fill("#kitPass", CLAVE)
    with pag.expect_download(timeout=30000) as dl:
        pag.click("#kitGenerar")
    bajado = dl.value
    bajado.save_as(destino)
    check("se descarga un archivo", os.path.isfile(destino), bajado.suggested_filename)
    check("el nombre dice lo que es", "Kit de recuperacion" in bajado.suggested_filename)
    check("el cuadro se cierra solo", pag.evaluate("() => document.getElementById('kitModal').hidden"))

    contenido = open(destino, encoding="utf-8").read()
    print("     tamano del kit: %.1f KB" % (len(contenido) / 1024))
    check("es un HTML autocontenido", contenido.startswith("<!doctype html"))
    check("no depende de internet ni de nada externo",
          not re.search(r'(src|href)=["\']https?://', contenido))

    print("\n[4] El secreto NO viaja en claro")
    kit = ps.kit_recuperacion()
    token = kit.get("publish_token") or ""
    check("hay una clave de publicacion para proteger", bool(token))
    check("la clave NO aparece en claro en el archivo", token not in contenido)
    check("la carpeta del proyecto tampoco", kit["proyecto"] not in contenido)
    check("el cifrado es AES-GCM con PBKDF2", "AES-GCM" in contenido and "PBKDF2" in contenido)

    print("\n[5] Abrirlo como lo haria el usuario (doble clic)")
    visor = ctx.new_page()
    errv = []
    visor.on("pageerror", lambda e: errv.append(str(e)))
    visor.goto("file:///" + destino.replace("\\", "/"))
    visor.wait_for_selector("#p", timeout=15000)
    check("pide la contrasena", visor.is_visible("#p"))

    visor.fill("#p", "la-equivocada")
    visor.click("#b")
    visor.wait_for_timeout(1500)
    check("con la contrasena equivocada NO abre", "no es la correcta" in visor.text_content("#e"))
    check("...y no muestra nada del contenido",
          visor.evaluate("() => document.getElementById('cont').className === 'oculto'"))

    visor.fill("#p", CLAVE)
    visor.click("#b")
    visor.wait_for_function("() => document.getElementById('cont').className === ''", timeout=25000)
    texto = visor.text_content("#cont")
    check("con la correcta abre", len(texto) > 200)
    check("muestra el repositorio", kit["repo"]["repo"] in texto)
    check("muestra la direccion del cerebro", kit["cerebro_url"] in texto)
    check("muestra la clave de publicacion", token in texto)
    check("muestra la carpeta del proyecto", kit["proyecto"] in texto)
    for s in ("GitHub", "Cloudflare", "Vercel", "Tailscale"):
        check("explica la cuenta de %s" % s, s in texto)
    check("trae el paso a paso", "Instala el panel en otra computadora" in texto)
    check("trae los avisos", "no se puede recuperar" in texto.lower())
    check("avisa que hay que guardarlo en dos lugares", "dos lugares" in texto.lower())
    check("el formulario de contrasena se esconde",
          visor.evaluate("() => document.getElementById('login').className === 'oculto'"))
    check("cero errores de JS en el visor", not errv, "; ".join(errv[:2]))

    check("cero errores de consola en el panel", not errores, "; ".join(errores[:3]))
    nav.close()

httpd.shutdown()
try:
    os.remove(destino)
except OSError:
    pass

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
