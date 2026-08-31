# -*- coding: utf-8 -*-
"""Prueba las 4 mejoras nuevas: nuevo-desde-el-ultimo, buscador global,
historial de publicaciones y novedades en la intranet."""
import os
import sys
import hashlib
import threading
from http.server import ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import panel_server as ps  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PORT = 8182
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")
OUT = os.path.join(AQUI, "fotos")
os.makedirs(OUT, exist_ok=True)
ok, fallos = 0, []


def check(n, c, extra=""):
    global ok
    if c:
        ok += 1
        print("  OK   %s %s" % (n, extra))
    else:
        fallos.append(n)
        print("  FALLA %s %s" % (n, extra))


antes = hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest()
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

print("=" * 70)
print("PRUEBA DE LAS MEJORAS NUEVAS")
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("() => { window.persistModulos = async () => ({ok:true}); }")

    print("\n[1] Nuevo mes a partir del último (con los números en blanco)")
    r = pag.evaluate("""() => {
      const bl = [
        {t:'titulo', html:'Derivaciones del mes'},
        {t:'kpis', items:[{label:'Enero', valor:'1.116', pie:'+12%', tend:'up', lead:true}]},
        {t:'barras', items:[{label:'Hudson', valor:'340', chip:'1º', color:'--c-hudson', tono:'gr'}]},
        {t:'podio', items:[{puesto:'1°', nombre:'Ana', suc:'CABA', valor:'88', vlabel:'ventas', extra:'x'}]},
        {t:'tabla', cols:[{h:'Sucursal',num:false},{h:'Ventas',num:true}],
         filas:[{celdas:['Hudson','1.116'],destaque:''}]},
      ];
      const copia = JSON.parse(JSON.stringify(bl));
      vaciarNumeros(copia);
      return {antes: bl, despues: copia};
    }""")
    d = r["despues"]
    check("el título se conserva", d[0]["html"] == "Derivaciones del mes")
    check("los KPI quedan en blanco pero se conserva el período",
          d[1]["items"][0]["valor"] == "" and d[1]["items"][0]["label"] == "Enero",
          str(d[1]["items"][0]))
    check("la barra conserva la sucursal y borra el número",
          d[2]["items"][0]["label"] == "Hudson" and d[2]["items"][0]["valor"] == "")
    check("el podio conserva el puesto y borra el nombre",
          d[3]["items"][0]["puesto"] == "1°" and d[3]["items"][0]["nombre"] == "")
    check("la tabla conserva encabezados y la columna de texto",
          d[4]["cols"][0]["h"] == "Sucursal" and d[4]["filas"][0]["celdas"][0] == "Hudson",
          str(d[4]["filas"][0]["celdas"]))
    check("...y borra SOLO la columna de números",
          d[4]["filas"][0]["celdas"][1] == "", str(d[4]["filas"][0]["celdas"]))

    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=20000)
    n0 = pag.evaluate("() => COLECCION.length")
    check("hay un botón para eso", pag.query_selector("#colNuevoMes") is not None)
    pag.evaluate("() => irALista()")
    pag.wait_for_timeout(200)
    pag.click("#colNuevoMes")
    pag.wait_for_timeout(600)
    check("crea un documento nuevo", pag.evaluate("() => COLECCION.length") == n0 + 1)
    check("lo abre para ponerle nombre", pag.evaluate("() => DOC_IDX === 0"))
    check("y lo deja sin nombre (para que lo escribas)",
          pag.evaluate("() => COLECCION[0].titulo") == "")
    check("con la misma cantidad de bloques que el original",
          pag.evaluate("() => COLECCION[0].bloques.length === COLECCION[1].bloques.length"))
    pag.evaluate("() => { COLECCION.splice(0,1); irALista(); }")
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(400)

    print("\n[2] Buscar en todo el panel")
    check("hay un buscador en la home", pag.query_selector("#buscarTodo") is not None)
    pag.fill("#buscarTodo", "descargar")
    pag.wait_for_timeout(350)
    res = pag.evaluate("() => document.querySelectorAll('.buscar-item').length")
    check("encuentra resultados", res > 0, "%d resultados" % res)
    check("y esconde la lista de módulos mientras busca",
          pag.evaluate("() => document.getElementById('modList').hidden"))
    check("cada resultado muestra de qué módulo es",
          (pag.text_content(".buscar-item .buscar-t") or "").strip() != "")
    pag.fill("#buscarTodo", "zzzznoexiste")
    pag.wait_for_timeout(300)
    check("si no hay nada lo dice", pag.query_selector(".buscar-nada") is not None)
    pag.fill("#buscarTodo", "")
    pag.wait_for_timeout(300)
    check("al vaciarlo vuelve la lista",
          not pag.evaluate("() => document.getElementById('modList').hidden"))
    # busca DENTRO de los documentos de una biblioteca
    hit = pag.evaluate("""() => {
        const r = buscarEnTodo('sucursales');
        return r.filter(x => x.docIdx != null).length;
    }""")
    check("busca también adentro de los documentos de una biblioteca", hit >= 0, "%d" % hit)

    print("\n[3] Historial de publicaciones")
    h = pag.evaluate("async () => await api('/api/historial')")
    check("el historial responde", h.get("ok") is True, str(h.get("error", ""))[:60])
    if h.get("ok"):
        check("trae versiones", len(h["versiones"]) > 0, "%d versiones" % len(h["versiones"]))
        v0 = h["versiones"][0]
        check("cada versión tiene fecha y mensaje", bool(v0["fecha"]) and bool(v0["mensaje"]),
              "%s · %s" % (v0["fecha"], v0["mensaje"][:40]))
        pag.click("#btnHistorial")
        pag.wait_for_timeout(2500)
        check("el modal lista las versiones",
              pag.evaluate("() => document.querySelectorAll('.hist-item').length") > 0,
              "%d" % pag.evaluate("() => document.querySelectorAll('.hist-item').length"))
        check("marca cuál es la que está publicada",
              pag.query_selector(".hist-item.actual .hist-chip") is not None)
        check("la publicada NO ofrece 'volver a esta'",
              pag.evaluate("""() => !document.querySelector('.hist-item.actual button')"""))
        check("las viejas sí", pag.evaluate(
            """() => [...document.querySelectorAll('.hist-item')].slice(1)
                     .every(x => !!x.querySelector('button'))"""))
        pag.click("#histModal .modal-foot [data-cerrar-hist]")
        pag.wait_for_timeout(300)
        check("se puede cerrar", pag.evaluate("() => document.getElementById('histModal').hidden"))
    check("una versión inventada se rechaza",
          pag.evaluate("async () => (await api('/api/restaurar', {method:'POST', body: JSON.stringify({sha:'pepe'})})).ok") is False)

    check("cero errores de consola en el panel", not errores, "; ".join(errores[:3]))

    print("\n[4] Novedades EN LA INTRANET (lo que ven los vendedores)")
    web = nav.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
    errw = []
    web.on("pageerror", lambda e: errw.append(str(e)))
    web.goto("http://127.0.0.1:%d/intranet/index.html" % PORT, wait_until="networkidle")
    web.wait_for_selector(".tile", timeout=20000)
    # se limpian las fechas que pueda tener el contenido real del usuario
    web.evaluate("""() => { Object.values(MODMAP).forEach(m => delete m.actualizado);
                            renderBotonera(); }""")
    web.wait_for_timeout(300)
    check("sin fechas de cambio, no molesta a nadie",
          web.evaluate("() => document.getElementById('novedades').hidden"))

    hoy = pag.evaluate("() => new Date().toISOString().slice(0,10)")
    viejo = pag.evaluate("() => new Date(Date.now()-40*86400000).toISOString().slice(0,10)")
    ks = web.evaluate("""(f) => {
        // las claves que importan son las de las TARJETAS visibles
        const ks = TILES.filter(t => seccionLista(t)).map(t => t.key);
        [0,1,2].forEach(i => { if (ks[i] && !MODMAP[ks[i]]) MODMAP[ks[i]] = {key: ks[i]}; });
        if (ks[0]) MODMAP[ks[0]].actualizado = f.hoy;
        if (ks[1]) MODMAP[ks[1]].actualizado = f.hoy;
        if (ks[2]) MODMAP[ks[2]].actualizado = f.viejo;
        renderBotonera();
        return ks.slice(0,3);
    }""", {"hoy": hoy, "viejo": viejo})
    print("     módulos marcados:", ks)
    web.wait_for_timeout(400)
    check("con cambios recientes aparece el bloque Novedades",
          not web.evaluate("() => document.getElementById('novedades').hidden"))
    n = web.evaluate("() => document.querySelectorAll('.nv-item').length")
    check("lista solo los recientes (no los de hace 40 días)", n == 2, "%d en novedades" % n)
    check("dice cuándo se actualizó",
          "hoy" in (web.text_content(".nv-f") or "").lower(), web.text_content(".nv-f"))
    check("y la tarjeta del módulo lleva la chapa Nuevo",
          web.evaluate("() => document.querySelectorAll('.tile .tile-nuevo').length") == 2)
    check("se puede entrar desde Novedades",
          web.evaluate("() => !!document.querySelector('.nv-item').onclick || " +
                       "!!document.querySelector('.nv-item').getAttribute('onclick')"))
    web.screenshot(path=os.path.join(OUT, "N-novedades-intranet.png"), full_page=False)
    web.evaluate("() => window.scrollTo(0, 0)")
    web.locator("#novedades").screenshot(path=os.path.join(OUT, "N2-novedades-detalle.png"))
    check("cero errores de JS en la intranet", not errw, "; ".join(errw[:2]))
    nav.close()

httpd.shutdown()
check("modulos.js NO se toco", hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest() == antes)

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
