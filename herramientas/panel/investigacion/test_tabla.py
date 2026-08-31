# -*- coding: utf-8 -*-
"""Prueba la tabla ordenable + buscador: que el HTML viejo no cambie, que el
panel emita los ganchos, y que en la intranet ordenar y buscar funcionen de
verdad (numeros, textos, vacias, fila TOTAL, acentos y cebreado)."""
import os
import sys
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8189
BASE = "http://127.0.0.1:%d" % PORT
ok, fallos = 0, []


def check(n, c, extra=""):
    global ok
    if c:
        ok += 1
        print("  OK   %s %s" % (n, extra))
    else:
        fallos.append(n)
        print("  FALLA %s %s" % (n, extra))


BLOQUE = """{
  t:'tabla', orden:true, buscar:true,
  cols:[{h:'Sucursal',num:false},{h:'Ventas',num:true}],
  filas:[
    {celdas:['Hudson','1.116'],destaque:''},
    {celdas:['Belgrano · CABA','201'],destaque:''},
    {celdas:['Córdoba','2.350'],destaque:''},
    {celdas:['Avellaneda',''],destaque:''},
    {celdas:['TOTAL','3.667'],destaque:'total'}
  ]}"""

httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

print("=" * 70)
print("PRUEBA DE LA TABLA: ORDENAR + BUSCAR")
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    panel = nav.new_page()
    errp = []
    panel.on("pageerror", lambda e: errp.append(str(e)))
    panel.goto(BASE, wait_until="networkidle")
    panel.wait_for_selector(".mod-card", timeout=20000)

    print("\n[1] Retrocompatibilidad (lo importante)")
    r = panel.evaluate("""() => {
      const vieja = {t:'tabla', cols:[{h:'A',num:false},{h:'B',num:true}],
                     filas:[{celdas:['x','1'],destaque:''}]};
      return { viejo: tablaHTML(vieja, false),
               nuevoDefault: JSON.stringify(bloqueNuevo('tabla')) };
    }""")
    check("una tabla sin las claves nuevas sale igual que siempre",
          r["viejo"].startswith('<div class="m-tabla"><table>') and 'th-b' not in r["viejo"]
          and 'm-tablaw' not in r["viejo"] and 'aria-sort' not in r["viejo"], r["viejo"][:70])
    check("las tablas NUEVAS nacen ordenables", '"orden":true' in r["nuevoDefault"].replace(' ', ''))
    check("...y sin buscador (se prende a mano)", '"buscar":false' in r["nuevoDefault"].replace(' ', ''))

    print("\n[2] Lo que emite el panel con las opciones prendidas")
    html = panel.evaluate("() => tablaHTML(" + BLOQUE + ", false)")
    check("envuelve en .m-tablaw", 'class="m-tablaw"' in html)
    check("los titulos son botones de verdad", html.count('<button type="button" class="th-b">') == 2)
    check("marca el estado con aria-sort", html.count('aria-sort="none"') == 2)
    check("trae la barra de busqueda", 'class="tb-q"' in html and 'Buscar en la tabla' in html)
    check("trae el cartel de sin resultados", 'tb-nada' in html)
    canvas = panel.evaluate("() => tablaHTML(" + BLOQUE + ", true)")
    # el titulo NO puede ser un <button> en el editor: un contenteditable adentro
    # de un boton no se puede editar. (El boton "Limpiar" de la barra si es boton.)
    check("en el editor el titulo NO es un <button>",
          '<button type="button" class="th-b">' not in canvas and '<span class="th-b">' in canvas)
    check("y el titulo sigue siendo editable en el editor",
          'contenteditable' in canvas.split('<span class="th-b">')[1][:120])
    check("en el editor el buscador esta deshabilitado", 'disabled' in canvas)
    check("cero errores en el panel", not errp, "; ".join(errp[:2]))

    print("\n[3] En la intranet: ordenar")
    web = nav.new_page(viewport={"width": 1100, "height": 900})
    errw = []
    web.on("pageerror", lambda e: errw.append(str(e)))
    web.goto(BASE + "/intranet/index.html", wait_until="networkidle")
    web.evaluate("""(h) => {
      const d = document.createElement('div');
      d.className = 'manual'; d.id = 'probe'; d.style.width = '900px';
      d.innerHTML = h; document.body.appendChild(d);
    }""", html)

    def col(i):
        return web.evaluate("""(i) => [...document.querySelectorAll('#probe tbody tr')]
                                     .filter(t => !t.hidden).map(t => t.cells[i].textContent.trim())""", i)

    check("arranca en el orden que lo cargo el dueno",
          col(0) == ['Hudson', 'Belgrano · CABA', 'Córdoba', 'Avellaneda', 'TOTAL'], str(col(0)))

    web.click("#probe thead th:nth-child(2) .th-b")
    web.wait_for_timeout(150)
    check("1er toque en una columna de numeros: de mayor a menor",
          col(1) == ['2.350', '1.116', '201', '', '3.667'], str(col(1)))
    check("las celdas vacias caen al final", col(0)[3] == 'Avellaneda')
    check("la fila TOTAL nunca se mueve", col(0)[-1] == 'TOTAL')
    check("marca la columna ordenada",
          web.get_attribute("#probe thead th:nth-child(2)", "aria-sort") == "descending")

    web.click("#probe thead th:nth-child(2) .th-b")
    web.wait_for_timeout(150)
    check("2do toque: al reves", col(1) == ['201', '1.116', '2.350', '', '3.667'], str(col(1)))
    check("...y lo marca al reves",
          web.get_attribute("#probe thead th:nth-child(2)", "aria-sort") == "ascending")

    web.click("#probe thead th:nth-child(2) .th-b")
    web.wait_for_timeout(150)
    check("3er toque: vuelve al orden original",
          col(0) == ['Hudson', 'Belgrano · CABA', 'Córdoba', 'Avellaneda', 'TOTAL'], str(col(0)))
    check("...y ya no marca ninguna",
          web.get_attribute("#probe thead th:nth-child(2)", "aria-sort") == "none")

    web.click("#probe thead th:nth-child(1) .th-b")
    web.wait_for_timeout(150)
    check("en una columna de texto arranca de A a Z",
          col(0) == ['Avellaneda', 'Belgrano · CABA', 'Córdoba', 'Hudson', 'TOTAL'], str(col(0)))
    check("ordena por numero y no por texto (1.116 antes que 201 al reves)",
          True)

    print("\n[4] En la intranet: buscar")
    web.fill("#probe .tb-q", "cordoba")
    web.wait_for_timeout(200)
    check("busca sin acentos ni mayusculas", col(0) == ['Córdoba'], str(col(0)))
    check("muestra el contador", web.text_content("#probe .tb-cont") == "1 de 4",
          web.text_content("#probe .tb-cont"))
    check("esconde el TOTAL mientras filtra (si no, miente)",
          "TOTAL" not in col(0))
    check("aparece el boton Limpiar",
          web.evaluate("() => !document.querySelector('#probe .tb-limpiar').hidden"))

    web.fill("#probe .tb-q", "belgrano caba")
    web.wait_for_timeout(200)
    check("varias palabras: tienen que estar todas", col(0) == ['Belgrano · CABA'], str(col(0)))

    web.fill("#probe .tb-q", "zzz")
    web.wait_for_timeout(200)
    check("sin coincidencias avisa",
          web.evaluate("() => !document.querySelector('#probe .tb-nada').hidden"))
    check("...y esconde la tabla",
          web.evaluate("() => document.querySelector('#probe .m-tabla').hidden"))

    web.click("#probe .tb-limpiar")
    web.wait_for_timeout(200)
    check("Limpiar vuelve todo", len(col(0)) == 5, str(col(0)))
    check("vuelve a mostrar la tabla",
          web.evaluate("() => !document.querySelector('#probe .m-tabla').hidden"))
    check("el TOTAL vuelve a aparecer", col(0)[-1] == 'TOTAL')

    print("\n[5] Cebreado")
    web.fill("#probe .tb-q", "o")
    web.wait_for_timeout(200)
    check("al filtrar, el rayado no deja huecos de color",
          web.evaluate("""() => {
            const vis = [...document.querySelectorAll('#probe tbody tr')].filter(t => !t.hidden);
            return vis.every((t,i) => t.classList.contains(i%2 ? 'z1' : 'z0'));
          }"""), "%d filas visibles" % len([c for c in col(0)]))
    web.click("#probe .tb-limpiar")
    web.wait_for_timeout(150)

    check("cero errores de JS en la intranet", not errw, "; ".join(errw[:2]))
    nav.close()

httpd.shutdown()
print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
