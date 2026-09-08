# -*- coding: utf-8 -*-
"""Tres cosas que reportó el usuario el 8-sep.

1. «cuando elimino un módulo el botón que dice todo publicado no cambia, o sea
   que si hago ajustes fuera de los módulos o quiero eliminar no veo una opción
   para publicar el cambio».

   Era cierto: `editados` guarda CLAVES DE MÓDULO, y un módulo borrado no tiene
   dónde ponerse. Peor: al borrar se hacía `editados.delete(key)`, así que el
   contador BAJABA y el botón podía quedar en «Todo publicado» con el borrado
   sin subir.

2. «el botón de duplicar métricas en reporte de métricas (módulo) está roto».

   Estaba: la etiqueta se armaba con `textContent` y adentro le metían un
   `<svg>`. El botón mostraba el código del ícono como texto, se estiraba a lo
   ancho de la fila y empujaba a los otros dos botones fuera de la pantalla.

3. «veo que siguen tildadas algunas comunicaciones antiguas… eso debería tener
   vigencia de al menos 24hs… solo había que poner un temporizador».

   La chapita «Nuevo» duraba 14 días fijos. Ahora se elige, y de fábrica dura
   24 horas.

    python w8_web3_pendientes_avisos.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
SANDBOX = os.environ.get("QA_SANDBOX_WEB3") or ""
RES = []


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:220]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:220]))


def ir_a(p, sec):
    """Vuelve a una sección desde donde sea.

    Si quedó abierto el editor de un módulo, el menú lateral está tapado: se
    sale primero, aceptando la guarda de «cambios sin guardar» si aparece.
    """
    if p.is_visible("#viewDetalle"):
        p.click("#detBack")
        try:
            p.wait_for_selector("#confirmModal.on", state="visible", timeout=1500)
            alt = p.query_selector("#confirmAlt")
            if alt and alt.is_visible():
                alt.click()
            else:
                p.click("#confirmYes")
        except Exception:
            pass
        p.wait_for_timeout(600)
    p.click('[data-sec="%s"]' % sec)
    p.wait_for_selector("#view" + sec.capitalize(), state="visible")
    p.wait_for_timeout(900)


def confirmar_si(p, timeout=8000):
    """El panel pregunta con SU modal, no con el del navegador."""
    p.wait_for_selector("#confirmModal.on", state="visible", timeout=timeout)
    p.click("#confirmYes")


def texto_publicar(p):
    return (p.text_content("#btnPublicar") or "").strip()


with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000})
    # ningún cambio de prueba puede llegar al sitio de los vendedores
    ctx.route("**/api/publicar", lambda r: r.fulfill(
        status=200, content_type="application/json", body='{"ok": true}'))
    errs = []
    p = ctx.new_page()
    p.set_default_timeout(60000)
    p.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:180]))
    p.on("dialog", lambda d: d.accept())

    p.goto(BASE + "/", wait_until="domcontentloaded")
    p.wait_for_selector("#muroLista .pub", timeout=25000)
    # se arranca de cero: sin pendientes anotados de otra corrida
    p.evaluate("""() => { try {
      localStorage.removeItem('mys_editados_sin_publicar');
      localStorage.removeItem('mys_otros_cambios_sin_publicar');
    } catch (e) {} }""")
    p.reload(wait_until="domcontentloaded")
    p.wait_for_selector("#muroLista .pub", timeout=25000)
    p.wait_for_timeout(800)

    # ───────────── 1. borrar un módulo deja algo para publicar ─────────────
    check("de entrada dice «Todo publicado»", lambda: (
        p.wait_for_function(
            "() => /Todo publicado/.test(document.getElementById('btnPublicar').textContent)",
            timeout=15000), texto_publicar(p))[-1])

    def crear_y_borrar():
        """Se crea un módulo de prueba y se lo borra: el borrado tiene que
        quedar pendiente. Se usa uno propio para no tocar los de verdad."""
        ir_a(p, "modulos")
        p.click("#btnAddModulo")
        p.wait_for_selector("#viewDetalle", state="visible")
        p.fill("#dTitle", "QA para borrar")
        # el panel NO guarda un módulo vacío («Agregá al menos un bloque»), y
        # hace bien: un módulo sin nada no le sirve a nadie. Se le pone uno.
        add = p.query_selector("#gbAdd summary") or p.query_selector("#gbAdd")
        add.click()
        p.wait_for_timeout(400)
        bt = (p.query_selector("#gbAdd .pal-b:has-text('Título')")
              or p.query_selector(".pal-b:has-text('Título')")
              or p.query_selector("#gbAdd button:has-text('Título')"))
        if not bt:
            raise AssertionError("no encuentro un bloque para agregar")
        bt.click()
        p.wait_for_timeout(700)
        p.click("#detSave")
        p.wait_for_timeout(3500)
        t = p.evaluate("() => { const t = document.getElementById('toast');"
                       " return t && !t.hidden ? t.textContent : ''; }")
        if "Agregá" in t or "Poné" in t:
            raise AssertionError("no se pudo guardar: %r" % t)
        p.click("#detBack")
        p.wait_for_timeout(1500)
        p.wait_for_selector("#viewModulos", state="visible")
        # y ahora se borra
        p.evaluate("""() => {
          const c = [...document.querySelectorAll('.card.mod')]
            .find(x => /QA para borrar/.test(x.textContent));
          if (c) c.click();
        }""")
        p.wait_for_selector("#viewDetalle", state="visible")
        p.wait_for_timeout(900)
        p.click("#detMore")
        p.wait_for_selector("#detMoreMenu", state="visible")
        p.click("#detDelete")
        confirmar_si(p)                       # «¿Estás seguro…?»
        p.wait_for_selector("#viewModulos", state="visible", timeout=30000)
        p.wait_for_timeout(1500)
        quedo = p.evaluate("""() => [...document.querySelectorAll('.card.mod')]
          .some(x => /QA para borrar/.test(x.textContent))""")
        if quedo:
            raise AssertionError("el módulo de prueba no se borró")
        return "creado y borrado"
    check("se crea y se borra un módulo de prueba", crear_y_borrar)

    def el_boton_lo_nota():
        txt = texto_publicar(p)
        if "Todo publicado" in txt:
            raise AssertionError("después de borrar sigue diciendo %r" % txt)
        if "Publicar" not in txt:
            raise AssertionError("no ofrece publicar: %r" % txt)
        return txt
    check("borrar un módulo deja el botón en «Publicar»", el_boton_lo_nota)

    def el_estado_del_menu():
        t = (p.text_content("#estadoTit") or "").strip()
        if "Todo publicado" in t:
            raise AssertionError("el estado del menú no se enteró: %r" % t)
        return t
    check("el estado del menú también lo dice", el_estado_del_menu)

    def sobrevive_a_recargar():
        p.reload(wait_until="domcontentloaded")
        p.wait_for_selector("#muroLista .pub", timeout=25000)
        p.wait_for_timeout(1200)
        txt = texto_publicar(p)
        if "Todo publicado" in txt:
            raise AssertionError("se olvidó al recargar: %r" % txt)
        return txt
    check("el pendiente sobrevive a recargar el panel", sobrevive_a_recargar)

    def publicar_lo_limpia():
        ir_a(p, "modulos")
        p.click("#btnPublicar")
        p.wait_for_selector("#confirmModal.on", state="visible", timeout=10000)
        aviso = (p.text_content("#confirmModal") or "")
        if "No hay cambios anotados" in aviso:
            raise AssertionError("el cartel dice que no hay nada que publicar")
        p.click("#confirmYes")
        p.wait_for_function(
            "() => /Todo publicado/.test(document.getElementById('btnPublicar').textContent)",
            timeout=45000)
        return "publicado y el botón vuelve a «Todo publicado»"
    check("al publicar, el pendiente se limpia", publicar_lo_limpia)

    # ───────────── 2. el botón Duplicar ─────────────
    def duplicar_se_ve_bien():
        ir_a(p, "modulos")
        p.evaluate("""() => {
          const c = [...document.querySelectorAll('.card.mod')]
            .find(x => /Reporte de m.tricas/i.test(x.textContent));
          if (c) c.click();
        }""")
        p.wait_for_selector("#colDup", state="visible", timeout=20000)
        p.wait_for_timeout(800)
        v = p.evaluate("""() => {
          const d = document.getElementById('colDup');
          return { txt: d.textContent, ancho: Math.round(d.getBoundingClientRect().width),
                   otros: [...document.querySelectorAll('.head-actions .btn')]
                     .filter(b => !b.hidden && b.getBoundingClientRect().width > 0).length };
        }""")
        if "<svg" in v["txt"]:
            raise AssertionError("muestra el código del ícono: %r" % v["txt"][:60])
        if v["ancho"] > 400:
            raise AssertionError("el botón mide %dpx: se comió la fila" % v["ancho"])
        if v["otros"] < 3:
            raise AssertionError("solo se ven %d botones de los 3" % v["otros"])
        return "%r · %dpx · %d botones a la vista" % (v["txt"], v["ancho"], v["otros"])
    check("«Duplicar» se ve como un botón, no como código", duplicar_se_ve_bien)

    def duplicar_duplica():
        n = p.eval_on_selector_all("#colList > *", "ns => ns.length")
        if not n:
            raise AssertionError("el módulo no tiene documentos para duplicar")
        p.click("#colDup")
        p.wait_for_timeout(1500)
        n2 = p.eval_on_selector_all("#colList > *", "ns => ns.length")
        if n2 != n + 1:
            raise AssertionError("de %d pasó a %d" % (n, n2))
        # se deshace: era una prueba, no un documento de verdad. La copia entra
        # PRIMERA, así que la × de la primera fila es la suya.
        p.evaluate("""() => {
          const f = document.querySelector('#colList > *');
          const x = f && [...f.querySelectorAll('button')]
            .find(b => /^\s*(×|✕|x)\s*$/i.test(b.textContent));
          if (x) x.click();
        }""")
        try:
            confirmar_si(p, 3000)
        except Exception:
            pass
        p.wait_for_timeout(1200)
        n3 = p.eval_on_selector_all("#colList > *", "ns => ns.length")
        return "%d → %d documentos (y vuelve a %d)" % (n, n2, n3)
    check("«Duplicar» agrega una copia", duplicar_duplica)

    # ───────────── 3. la vigencia de la chapita ─────────────
    def el_modal_pregunta():
        ir_a(p, "modulos")
        p.click("#btnAvisar")
        p.wait_for_selector("#avisarModal.on", state="visible", timeout=15000)
        p.wait_for_timeout(600)
        v = p.evaluate("""() => {
          const s = document.getElementById('avisarVig');
          return s ? { hay: true, puesto: s.value,
                       ops: [...s.options].map(o => o.textContent) } : { hay: false };
        }""")
        if not v["hay"]:
            raise AssertionError("no se puede elegir la vigencia")
        if v["puesto"] != "24":
            raise AssertionError("de fábrica no son 24 horas: %s" % v["puesto"])
        return "%s · opciones: %s" % (v["puesto"] + "h", ", ".join(v["ops"]))
    check("se elige cuánto dura la chapita, y son 24h de fábrica", el_modal_pregunta)

    def los_viejos_ya_no_estan_tildados():
        """Lo que motivó el pedido: avisos de hace semanas seguían marcados."""
        v = p.evaluate("""() => {
          const filas = [...document.querySelectorAll('#avisarLista .chk')];
          return filas.map(f => ({
            t: f.querySelector('b') ? f.querySelector('b').textContent : '',
            sub: f.querySelector('.t span') ? f.querySelector('.t span').textContent : '',
            marcado: f.getAttribute('aria-pressed') === 'true'
          }));
        }""")
        if not v:
            raise AssertionError("la lista de avisos vino vacía")
        viejos = [x for x in v if "venció" in x["sub"]]
        mal = [x for x in v if x["marcado"] and "venció" in x["sub"]]
        if mal:
            raise AssertionError("hay vencidos que siguen tildados: %s"
                                 % [x["t"] for x in mal])
        return "%d avisos, %d ya vencidos y ninguno tildado" % (len(v), len(viejos))
    check("un aviso vencido no queda tildado", los_viejos_ya_no_estan_tildados)

    def cambiar_la_vigencia_se_guarda():
        p.select_option("#avisarVig", "72")
        p.wait_for_timeout(900)
        p.click("#avisarGuardar")
        p.wait_for_timeout(3500)
        r = p.evaluate("""async () => {
          const j = await (await fetch('/api/modulos')).json();
          return j.ajustes || {};
        }""")
        if r.get("novedad_horas") != 72:
            raise AssertionError("no se guardó: %s" % r)
        return "guardado: %s horas" % r["novedad_horas"]
    check("cambiar la vigencia se guarda en el sitio", cambiar_la_vigencia_se_guarda)

    def viaja_al_sitio():
        """El vendedor lo lee de modulos.js: si no viaja, no sirve de nada."""
        if not SANDBOX:
            return "(sin sandbox a mano, salteado)"
        ruta = os.path.join(SANDBOX, "intranet", "modulos.js")
        with open(ruta, encoding="utf-8") as f:
            txt = f.read()
        if "window.AJUSTES" not in txt:
            raise AssertionError("modulos.js no lleva los ajustes")
        i = txt.index("window.AJUSTES")
        aj = json.loads(txt[txt.index("{", i):txt.index("}", i) + 1])
        if aj.get("novedad_horas") != 72:
            raise AssertionError("el sitio tiene otra vigencia: %s" % aj)
        return "modulos.js dice novedad_horas=%d" % aj["novedad_horas"]
    check("la vigencia viaja al sitio en modulos.js", viaja_al_sitio)

    def volver_a_24():
        ir_a(p, "modulos")
        p.click("#btnAvisar")
        p.wait_for_selector("#avisarModal.on", state="visible", timeout=15000)
        p.wait_for_timeout(600)
        p.select_option("#avisarVig", "24")
        p.wait_for_timeout(800)
        p.click("#avisarGuardar")
        p.wait_for_timeout(3000)
        r = p.evaluate("""async () => {
          const j = await (await fetch('/api/modulos')).json();
          return (j.ajustes || {}).novedad_horas;
        }""")
        if r != 24:
            raise AssertionError("quedó en %s" % r)
        return "el sandbox vuelve a 24 horas"
    check("limpieza: vuelve a 24 horas", volver_a_24)

    print("\nerrores de consola:", errs or "ninguno")
    b.close()

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
