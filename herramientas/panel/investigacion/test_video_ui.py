# -*- coding: utf-8 -*-
"""Prueba el bloque de video EN EL NAVEGADOR: helpers, HTML publicado y el flujo
real de subir un archivo desde el editor. No guarda nada en modulos.js."""
import os
import sys
import json
import subprocess
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8196
BASE = "http://127.0.0.1:%d" % PORT
ok_total, fallos = 0, []


def check(nombre, cond, extra=""):
    global ok_total
    if cond:
        ok_total += 1
        print("  OK   %s %s" % (nombre, extra))
    else:
        fallos.append(nombre)
        print("  FALLA %s %s" % (nombre, extra))


print("=" * 70)
print("PRUEBA DEL BLOQUE DE VIDEO EN EL EDITOR")
print("=" * 70)

# video liviano de prueba (entra en el tope: no dispara compresion)
chico = os.path.join(ps.STATE_DIR, "test_chico.mp4")
subprocess.run([ps.ffmpeg_local(), "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=480x854:rate=24:duration=3",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", chico],
               timeout=120, creationflags=ps.CREATE_NO_WINDOW)
print("video de prueba VERTICAL: %.2f MB" % (os.path.getsize(chico) / 1048576.0))

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

subidos = []
with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page()
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto(BASE, wait_until="networkidle")

    # ---------- 1. helpers puros ----------
    print("\n[1] Helpers")
    r = pag.evaluate("""() => ({
      yt:      embedDeVideo('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
      corto:   embedDeVideo('https://youtube.com/shorts/AbCdEfGhIjK'),
      beShort: embedDeVideo('https://youtu.be/dQw4w9WgXcQ'),
      vimeo:   embedDeVideo('https://vimeo.com/123456789'),
      drive:   embedDeVideo('https://drive.google.com/file/d/1AbC_dEF/view?usp=sharing'),
      basura:  embedDeVideo('no soy un link'),
      arVert:  arDe({ar:'1080/1920'}),
      arNada:  arDe({orient:'vert'}),
      nuevo:   bloqueNuevo('video'),
    })""")
    check("YouTube -> /embed/", r["yt"]["url"] == "https://www.youtube.com/embed/dQw4w9WgXcQ", r["yt"]["url"])
    check("un Short se marca vertical", r["corto"]["vert"] is True)
    check("youtu.be tambien anda", r["beShort"]["url"].endswith("/embed/dQw4w9WgXcQ"))
    check("Vimeo -> player", r["vimeo"]["url"] == "https://player.vimeo.com/video/123456789", r["vimeo"]["url"])
    check("Drive -> /preview", r["drive"]["url"].endswith("/preview"), r["drive"]["url"])
    check("un texto cualquiera se marca invalido", r["basura"]["ok"] is False)
    check("proporcion real respetada", r["arVert"] == ["1080", "1920"], str(r["arVert"]))
    check("sin proporcion, vertical cae en 9/16", r["arNada"] == [9, 16], str(r["arNada"]))
    check("el bloque nuevo NO es descargable por defecto", r["nuevo"]["descargable"] is False)

    # ---------- 2. HTML publicado ----------
    print("\n[2] HTML que se publica")
    h = pag.evaluate("""() => ({
      propio: bloqueHTML({t:'video', src:'assets/_modulos/x.mp4', orient:'vert', ar:'1080/1920',
                          tam:'gr', caption:'Un pie', descargable:false}),
      conDl:  bloqueHTML({t:'video', src:'assets/_modulos/x.mp4', orient:'horiz', ar:'16/9',
                          descargable:true, dlNombre:'Como mostrar un sillon'}),
      link:   bloqueHTML({t:'video', url:'https://youtu.be/dQw4w9WgXcQ', orient:'horiz'}),
      vacio:  bloqueHTML({t:'video'}),
      malo:   bloqueHTML({t:'video', url:'pepe'}),
    })""")
    check("marca vertical y tamano", 'class="m-video vert tam-gr"' in h["propio"], h["propio"][:80])
    check("lleva la proporcion real", '--arw:1080;--arh:1920' in h["propio"])
    check("usa <video> con controles", "<video" in h["propio"] and "controls" in h["propio"])
    check("no baja el video entero de una", 'preload="metadata"' in h["propio"])
    check("playsinline (iPhone no lo abre solo)", "playsinline" in h["propio"])
    check("el pie sale", "<figcaption>Un pie</figcaption>" in h["propio"])
    check("SIN boton de descarga si esta apagado", "dl-btn" not in h["propio"])
    check("CON boton de descarga si esta prendido", "dl-btn" in h["conDl"] and 'download="Como mostrar un sillon.mp4"' in h["conDl"], h["conDl"][-90:])
    check("el link sale como iframe embebido", "<iframe" in h["link"] and "youtube.com/embed/" in h["link"])
    check("el iframe permite pantalla completa", "allowfullscreen" in h["link"])
    check("un bloque vacio no ensucia el sitio", h["vacio"] == "")
    check("un link invalido no ensucia el sitio", h["malo"] == "")

    # ---------- 3. flujo real en el editor ----------
    print("\n[3] Subir un video desde el editor")
    pag.wait_for_selector(".mod-card, .col-item, [data-key]", timeout=15000)
    tarjetas = pag.query_selector_all(".mod-card")
    check("la lista de modulos cargo", len(tarjetas) > 0, "%d modulos" % len(tarjetas))
    if tarjetas:
        tarjetas[0].click()
        pag.wait_for_selector("#gbAdd", timeout=15000)
        # la paleta es desplegable: primero se abre el grupo
        pag.evaluate('''() => { const b = document.querySelector('#gbAdd .gb-tipo[data-t="video"]');
            if (b) { const d = b.closest("details"); if (d) d.open = true; } }''')
        pag.wait_for_timeout(150)
        pag.click('#gbAdd .gb-tipo[data-t="video"]')
        pag.wait_for_timeout(400)
        check("el bloque quedo seleccionado y es video",
              pag.evaluate("() => BLOQUES[SEL] && BLOQUES[SEL].t") == "video")
        check("el inspector muestra el boton de subir",
              pag.evaluate("""() => [...document.querySelectorAll('#gbInspector button')]
                                  .some(b => b.textContent.trim() === 'Subir video')"""))
        check("el canvas muestra el cartel de vacio",
              "Subí un video" in (pag.text_content("#gbDoc .blk-ph") or ""))

        pag.set_input_files("#gbInspector input[type=file]", chico)
        pag.wait_for_function("() => BLOQUES[SEL] && !!BLOQUES[SEL].src", timeout=90000)
        bk = pag.evaluate("() => BLOQUES[SEL]")
        subidos.append(bk["src"])
        check("el video quedo cargado en el bloque", bool(bk["src"]), bk["src"])
        check("se detecto solo que es VERTICAL", bk["orient"] == "vert", bk["orient"])
        check("guardo la proporcion real medida", bk["ar"] == "480/854", bk["ar"])
        check("el <video> aparece en el canvas",
              pag.query_selector("#gbDoc .blk-video video") is not None)
        check("el navegador puede reproducirlo (Range OK)",
              pag.evaluate("""async () => {
                  const v = document.querySelector('#gbDoc .blk-video video');
                  if (!v) return false;
                  await new Promise(r => { if (v.readyState >= 1) r();
                                           else { v.onloadedmetadata = r; v.onerror = r; } });
                  return v.videoWidth > 0 && v.videoHeight > v.videoWidth;
              }"""))
        check("aparece la opcion de permitir descargar",
              pag.evaluate("""() => [...document.querySelectorAll('#gbInspector .insp-check')]
                                  .some(s => s.textContent.includes('Permitir descargar'))"""))
        check("y arranca APAGADA (son videos de ejemplo)",
              pag.evaluate("""() => { const l = [...document.querySelectorAll('#gbInspector .insp-check')]
                  .find(x => x.textContent.includes('Permitir descargar'));
                  return !!l && !l.classList.contains('on'); }"""))

    check("cero errores de consola", not errores, "; ".join(errores[:3]))
    nav.close()

print("\n[4] Limpieza")
httpd.shutdown()
try:
    os.remove(chico)
except OSError:
    pass
for s in subidos:
    p = os.path.join(ps.INTRANET, *s.split("/"))
    try:
        os.remove(p)
    except OSError:
        pass
check("se borro el video subido en la prueba",
      all(not os.path.isfile(os.path.join(ps.INTRANET, *s.split("/"))) for s in subidos))
rc = subprocess.run(["git", "status", "--short", "intranet/"], cwd=os.path.dirname(ps.INTRANET),
                    capture_output=True, text=True)
sucio = [l for l in rc.stdout.splitlines() if "_modulos" in l and "test" in l.lower()]
check("no quedaron restos de la prueba en el repo", not sucio, str(sucio))

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok_total, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
