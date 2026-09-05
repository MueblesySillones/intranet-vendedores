# -*- coding: utf-8 -*-
"""Auditoría completa del panel web3 (sandbox 8132). Ejercita navegación,
cartelera (crear/editar/fijar/duplicar/archivar/borrar), robustez (doble
click, fallo 500 con rollback), editor de módulos (scroll v36, guardas),
modales, búsqueda y consola. Nada toca datos reales: proyecto y estado son
copias, y /api/publicar está interceptado."""
import json, os, re, sys, time, traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("QA_SANDBOX_WEB3") or os.path.join(HERE, "salida", "sandbox-web3")
SHOTS = os.path.join(HERE, "salida", "web3", "panel")
os.makedirs(SHOTS, exist_ok=True)

RES = []          # (estado, grupo, nombre, nota)
CONSOLA = []      # (fase, tipo, texto)
FASE = {"v": "arranque"}
MODE = {"m": "normal"}   # normal | slow | fail  (para POST /api/modulos)


def check(grupo, nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", grupo, nombre, str(nota)))
        print("PASS | %s | %s | %s" % (grupo, nombre, nota))
    except Exception as e:
        msg = str(e).split("\n")[0][:240]
        RES.append(("FAIL", grupo, nombre, msg))
        print("FAIL | %s | %s | %s" % (grupo, nombre, msg))


def shot(page, nombre):
    page.screenshot(path=os.path.join(SHOTS, nombre + ".png"), full_page=False)


def leer_modulos_sandbox():
    with open(os.path.join(SB, "intranet", "modulos.js"), encoding="utf-8") as f:
        return f.read()


def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              permissions=["clipboard-read", "clipboard-write"])

    # --- red: nada sale a publicarse de verdad ---
    ctx.route("**/api/publicar", lambda r: r.fulfill(
        status=200, content_type="application/json", body='{"ok": true}'))
    ctx.route("**/api/enviar", lambda r: r.fulfill(
        status=200, content_type="application/json", body='{"ok": true}'))

    def r_modulos(route):
        if route.request.method == "POST":
            if MODE["m"] == "fail":
                MODE["m"] = "normal"
                route.fulfill(status=500, content_type="application/json",
                              body='{"error": "falla simulada por la auditoria"}')
                return
            if MODE["m"] == "slow":
                time.sleep(1.4)
        route.continue_()
    ctx.route("**/api/modulos", r_modulos)

    page = ctx.new_page()
    page.set_default_timeout(8000)
    page.on("console", lambda m: CONSOLA.append((FASE["v"], m.type, m.text))
            if m.type == "error" else None)
    page.on("pageerror", lambda e: CONSOLA.append((FASE["v"], "pageerror", str(e))))

    # ================= A. ARRANQUE =================
    FASE["v"] = "arranque"
    page.goto(BASE + "/", wait_until="domcontentloaded")
    page.wait_for_selector("#muroLista .pub", timeout=10000)

    check("arranque", "version visible", lambda: (
        page.wait_for_function("document.querySelector('#navVersion').textContent.includes('Versión')"),
        page.text_content("#navVersion").strip())[1])
    def rol_central():
        # en modo cerebro los dos roles publican directo: Enviar/Traer/Bandeja
        # quedan ocultos a propósito, y #btnPublicar se esconde con .btn-done
        # (nada pendiente). Lo que NO puede pasar es que aparezcan los de
        # colaborador o que el botón de publicar quede visible sin nada que subir.
        est = page.evaluate("""() => {
          const s = id => { const e = document.getElementById(id); if (!e) return 'NO EXISTE';
            return {vis: e.offsetParent !== null, cls: e.className}; };
          return {pub: s('btnPublicar'), band: s('btnBandeja'), env: s('btnEnviar'),
                  traer: s('btnTraer'), rol: (document.getElementById('rolBadge')||{}).textContent};
        }""")
        if est["env"]["vis"] or est["traer"]["vis"]:
            raise AssertionError("botones de colaborador visibles siendo central: %s" % est)
        if est["pub"]["vis"] and "btn-done" in est["pub"]["cls"]:
            raise AssertionError("Publicar visible pero marcado como 'todo publicado'")
        return "publicar oculto(nada pendiente)=%s · bandeja oculta(modo cerebro)=%s" % (
            not est["pub"]["vis"], not est["band"]["vis"])
    check("arranque", "rol central: botones correctos", rol_central)
    check("arranque", "contadores del menú", lambda: "muro=%s mod=%s arch=%s datos=%s" % (
        page.text_content("#navNMuro"), page.text_content("#navNMod"),
        page.text_content("#navNArch"), page.text_content("#navNDatos")))
    shot(page, "01-cartelera")

    # ================= B. NAVEGACIÓN =================
    FASE["v"] = "navegacion"
    vistas = {"modulos": "#viewModulos", "archivadas": "#viewArch",
              "datos": "#viewDatos", "metricas": "#viewMetricas", "muro": "#viewMuro"}

    def navegar(sec):
        page.click('[data-sec="%s"]' % sec)
        page.wait_for_selector(vistas[sec], state="visible")
        otras = [v for k, v in vistas.items() if k != sec]
        vis = [v for v in otras if page.is_visible(v)]
        if vis:
            raise AssertionError("además de %s se ven %s" % (sec, vis))
        return "ok"

    for sec in ["modulos", "archivadas", "datos", "metricas", "muro"]:
        check("navegacion", "sección " + sec, lambda s=sec: navegar(s))
        if sec != "muro":
            shot(page, "02-seccion-" + sec)

    check("navegacion", "métricas: vista bloqueada renderiza", lambda: (
        navegar("metricas"),
        page.wait_for_function("document.querySelector('#viewMetricas').innerText.trim().length > 40"),
        page.text_content("#viewMetricas")[:60].replace("\n", " "))[-1])
    check("navegacion", "datos: la sección pinta contenido", lambda: (
        navegar("datos"),
        page.wait_for_function("document.querySelector('#datosRaiz') && document.querySelector('#datosRaiz').children.length > 0"),
        "hijos=%d" % page.eval_on_selector("#datosRaiz", "e=>e.children.length"))[-1])
    shot(page, "03-datos")
    navegar("muro")

    # ================= C. CARTELERA: lectura =================
    FASE["v"] = "cartelera-lectura"
    check("cartelera", "feed con publicaciones", lambda:
          "%d tarjetas" % len(page.query_selector_all("#muroLista .pub")))
    check("cartelera", "aside estado + etiquetas", lambda: (
        page.wait_for_selector("#asideEstado", state="visible"),
        "etiquetas=%d" % len(page.query_selector_all("#asideEtiquetas button, #asideEtiquetas .etq")))[-1])

    def probar_buscador():
        total = len(page.query_selector_all("#muroLista .pub"))
        page.fill("#muroBuscar", "zzzxx-no-existe")
        page.wait_for_timeout(400)
        cuantas = len(page.query_selector_all("#muroLista .pub:visible")) if False else \
            page.eval_on_selector_all("#muroLista .pub", "els=>els.filter(e=>e.offsetParent!==null).length")
        page.fill("#muroBuscar", "")
        page.wait_for_timeout(400)
        vuelta = page.eval_on_selector_all("#muroLista .pub", "els=>els.filter(e=>e.offsetParent!==null).length")
        if cuantas != 0:
            raise AssertionError("con texto inexistente quedaron %d tarjetas" % cuantas)
        if vuelta < total:
            raise AssertionError("al limpiar volvieron %d de %d" % (vuelta, total))
        return "filtra a 0 y restaura %d" % vuelta
    check("cartelera", "buscador del muro filtra y restaura", probar_buscador)

    # ================= D. CARTELERA: crear / editar / etc =================
    FASE["v"] = "cartelera-crud"
    T1 = "AUDITORÍA 4-sep — prueba creación"

    def crear_pub():
        page.click("#btnNuevaPub")
        page.wait_for_selector("#fondo.on", state="visible")
        if "Crear publicación" not in (page.text_content("#compTitulo") or ""):
            raise AssertionError("título del compositor: %r" % page.text_content("#compTitulo"))
        page.fill("#coTitulo", T1)
        page.fill("#coTexto", "Texto de prueba de la auditoría (se elimina al final).")
        shot(page, "04-compositor")
        page.click("#coPublicar")
        page.wait_for_function("!document.querySelector('#fondo').classList.contains('on')", timeout=10000)
        page.wait_for_function(
            "[...document.querySelectorAll('#muroLista .pub h3')].some(h=>h.textContent.includes(%s))" % json.dumps(T1))
        return "tarjeta en el feed"
    check("cartelera", "crear publicación", crear_pub)

    check("cartelera", "quedó persistida en modulos.js del sandbox", lambda:
          "sí" if T1 in leer_modulos_sandbox() else (_ for _ in ()).throw(AssertionError("no está en el archivo")))

    def tarjeta(titulo):
        for el in page.query_selector_all("#muroLista .pub"):
            h = el.query_selector("h3")
            if h and titulo in h.text_content():
                return el
        raise AssertionError("no encuentro la tarjeta %r" % titulo)

    def menu_de(titulo, accion):
        el = tarjeta(titulo)
        el.query_selector(".mp-mas").click()
        page.wait_for_selector("#mpMenu", state="visible")
        page.click('#mpMenu [data-a="%s"]' % accion)

    T1b = T1 + " (editada)"

    def editar_pub():
        menu_de(T1, "editar")
        page.wait_for_selector("#fondo.on", state="visible")
        rot = page.text_content("#coPublicar").strip()
        if "Guardar y publicar" not in rot:
            raise AssertionError("rótulo editando: %r" % rot)
        page.fill("#coTitulo", T1b)
        page.click("#coPublicar")
        page.wait_for_function("!document.querySelector('#fondo').classList.contains('on')", timeout=10000)
        tarjeta(T1b)
        return "título actualizado y rótulo correcto"
    check("cartelera", "editar publicación", editar_pub)

    def fijar_pub():
        menu_de(T1b, "fijar")
        page.wait_for_timeout(600)
        primera = page.eval_on_selector("#muroLista .pub h3", "e=>e.textContent")
        if T1b not in primera:
            raise AssertionError("fijada pero la primera es %r" % primera[:60])
        menu_de(T1b, "fijar")   # la desfija
        page.wait_for_timeout(400)
        return "sube arriba al fijar y se desfija"
    check("cartelera", "fijar / desfijar", fijar_pub)

    def duplicar_pub():
        menu_de(T1b, "duplicar")
        page.wait_for_function(
            "[...document.querySelectorAll('#muroLista .pub h3')].some(h=>h.textContent.includes('(copia)'))")
        return "aparece la copia"
    check("cartelera", "duplicar", duplicar_pub)

    def archivar_y_restaurar():
        copia = T1b + " (copia)"
        menu_de(copia, "ocultar")
        page.wait_for_timeout(700)
        # deja de verse en la cartelera
        if page.evaluate("[...document.querySelectorAll('#muroLista .pub h3')]"
                         ".some(h=>h.textContent.includes(%s))" % json.dumps(copia)):
            raise AssertionError("archivada pero sigue en la cartelera")
        page.click('[data-sec="archivadas"]')
        page.wait_for_selector("#viewArch", state="visible")
        page.wait_for_function(
            "document.querySelector('#archLista').innerText.includes('(copia)')")
        shot(page, "05-archivadas")
        # "Volver a publicar" en la tarjeta de Archivadas
        el = None
        for c in page.query_selector_all("#archLista .arch"):
            if copia in (c.text_content() or ""):
                el = c; break
        if el is None:
            raise AssertionError("no encuentro la tarjeta archivada")
        el.query_selector('[data-a="volver"]').click()
        page.wait_for_timeout(900)
        page.click('[data-sec="muro"]')
        page.wait_for_selector("#viewMuro", state="visible")
        tarjeta(copia)
        return "archiva (sale del feed) y vuelve con 'Volver a publicar'"
    check("cartelera", "archivar y restaurar", archivar_y_restaurar)

    def borrar(titulo):
        menu_de(titulo, "borrar")
        page.wait_for_selector("#confirmModal.on", state="visible")
        page.click("#confirmYes")
        page.wait_for_function(
            "![...document.querySelectorAll('#muroLista .pub h3')].some(h=>h.textContent.includes(%s))" % json.dumps(titulo))
        return "a la papelera"
    check("cartelera", "eliminar (papelera) con confirmación", lambda: borrar(T1b + " (copia)"))

    def compartir():
        el = tarjeta(T1b)
        el.query_selector('[data-a="compartir"]').click()
        page.wait_for_timeout(300)
        txt = page.evaluate("navigator.clipboard.readText()")
        if "/intranet/#cartelera/" not in txt:
            raise AssertionError("clipboard: %r" % txt[:80])
        return txt
    check("cartelera", "compartir copia el link público", compartir)

    # --- robustez ---
    FASE["v"] = "robustez-doble-click"
    T2 = "AUDITORÍA doble click"

    def doble_click():
        page.click("#btnNuevaPub")
        page.wait_for_selector("#fondo.on", state="visible")
        page.fill("#coTitulo", T2)
        page.fill("#coTexto", "prueba doble click")
        MODE["m"] = "slow"
        page.dblclick("#coPublicar")
        page.wait_for_function("!document.querySelector('#fondo').classList.contains('on')", timeout=15000)
        MODE["m"] = "normal"
        page.wait_for_timeout(800)
        n = page.evaluate(
            "[...document.querySelectorAll('#muroLista .pub h3')].filter(h=>h.textContent.includes(%s)).length" % json.dumps(T2))
        if n != 1:
            raise AssertionError("hay %d publicaciones con ese título" % n)
        rot = page.text_content("#coPublicar").strip()
        return "1 sola publicación; botón quedó %r" % rot
    check("robustez", "doble click no duplica", doble_click)

    FASE["v"] = "robustez-fallo"
    T3 = "AUDITORÍA fallo simulado"

    def fallo_visible():
        antes = len(page.query_selector_all("#muroLista .pub"))
        page.click("#btnNuevaPub")
        page.wait_for_selector("#fondo.on", state="visible")
        page.fill("#coTitulo", T3)
        page.fill("#coTexto", "esto tiene que fallar y avisar")
        MODE["m"] = "fail"
        page.click("#coPublicar")
        page.wait_for_selector("#toast.err", state="visible", timeout=8000)
        aviso = page.text_content("#toast")
        if not page.eval_on_selector("#fondo", "e=>e.classList.contains('on')"):
            raise AssertionError("el compositor se cerró pese al fallo")
        page.click("#coCerrar")
        # cerrar con algo escrito ahora pregunta antes de tirarlo
        page.wait_for_selector("#confirmModal.on", state="visible", timeout=4000)
        page.click("#confirmYes")
        page.wait_for_function("!document.querySelector('#fondo').classList.contains('on')")
        despues = len(page.query_selector_all("#muroLista .pub"))
        if despues != antes:
            raise AssertionError("el feed quedó con una tarjeta fantasma (%d→%d)" % (antes, despues))
        if T3 in leer_modulos_sandbox():
            raise AssertionError("el fallo igual persistió en el archivo")
        return "avisó %r, sin fantasma y sin persistir" % aviso[:60]
    check("robustez", "fallo del server avisa y deshace", fallo_visible)

    def fantasma_no_viaja():
        # tras el fallo, un guardado CUALQUIERA no debe arrastrar el doc fallido
        menu_de(T2, "fijar")
        page.wait_for_timeout(700)
        menu_de(T2, "fijar")
        page.wait_for_timeout(700)
        if T3 in leer_modulos_sandbox():
            raise AssertionError("el doc fallido viajó en el guardado siguiente")
        return "el guardado posterior no arrastra el doc fallido"
    check("robustez", "el fantasma no viaja en el próximo guardado", fantasma_no_viaja)

    # limpieza de las pruebas
    FASE["v"] = "limpieza"
    for t in (T2, T1b):
        try:
            borrar(t)
        except Exception:
            pass

    # --- Escape con el calendario abierto (trampa histórica) ---
    FASE["v"] = "escape-calendario"

    def escape_calendario():
        page.click("#btnNuevaPub")
        page.wait_for_selector("#fondo.on", state="visible")
        page.click("#coVenceBtn")
        page.wait_for_selector("#calPop", state="visible")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        if page.query_selector("#calPop"):
            raise AssertionError("Escape no cerró el calendario")
        if not page.eval_on_selector("#fondo", "e=>e.classList.contains('on')"):
            raise AssertionError("Escape cerró el compositor entero (regresión)")
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('#fondo').classList.contains('on')")
        return "1º Esc cierra el calendario, 2º Esc el compositor"
    check("robustez", "Escape escalonado calendario→compositor", escape_calendario)

    def escape_menu_etiquetas():
        page.click("#btnNuevaPub")
        page.wait_for_selector("#fondo.on", state="visible")
        page.click("#btnEtq")
        page.wait_for_timeout(350)
        if not page.eval_on_selector("#coTipos", "e=>e.classList.contains('on')"):
            raise AssertionError("no se abrió el menú de etiquetas")
        page.keyboard.press("Escape")
        page.wait_for_timeout(450)
        menu = page.eval_on_selector("#coTipos", "e=>e.classList.contains('on')")
        comp = page.eval_on_selector("#fondo", "e=>e.classList.contains('on')")
        if not comp:
            raise AssertionError("Escape cerró el COMPOSITOR entero en vez de sólo el "
                                 "menú de etiquetas (#coTipos no está en la lista 'encima' "
                                 "del handler global de muro.js)")
        if menu:
            raise AssertionError("Escape no cerró el menú de etiquetas")
        page.keyboard.press("Escape")        # y el 2º cierra el compositor vacío
        page.wait_for_timeout(400)
        return "cierra sólo el menú"
    check("robustez", "Escape con el menú de etiquetas abierto", escape_menu_etiquetas)

    def borrador_al_cerrar():
        largo = "Aviso que costó escribir. " * 8
        perdidos = []
        for como, accion in (
                ("Escape", lambda: page.keyboard.press("Escape")),
                ("la X", lambda: page.click("#coCerrar")),
                ("click en el fondo", lambda: page.mouse.click(60, 450))):
            if not page.eval_on_selector("#fondo", "e=>e.classList.contains('on')"):
                page.click("#btnNuevaPub")
                page.wait_for_selector("#fondo.on", state="visible")
            page.fill("#coTitulo", "Aviso importante")
            page.fill("#coTexto", largo)
            accion()
            page.wait_for_timeout(500)
            if page.eval_on_selector("#confirmModal", "e=>e.classList.contains('on')"):
                # preguntó, que es lo que se espera. Se comprueba que "seguir
                # editando" conserve el texto, y recién ahí se descarta.
                page.click("#confirmNo")
                page.wait_for_timeout(400)
                if not page.eval_on_selector("#coTexto", "e=>e.value"):
                    raise AssertionError("'seguir editando' igual borró el texto (%s)" % como)
                page.click("#coCerrar")
                page.wait_for_selector("#confirmModal.on", state="visible", timeout=4000)
                page.click("#confirmYes")
                page.wait_for_timeout(400)
                continue
            # no preguntó: ¿al menos conservó el borrador?
            page.click("#btnNuevaPub")
            page.wait_for_selector("#fondo.on", state="visible")
            page.wait_for_timeout(300)
            if not page.eval_on_selector("#coTexto", "e=>e.value"):
                perdidos.append(como)
        if page.eval_on_selector("#fondo", "e=>e.classList.contains('on')"):
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            if page.eval_on_selector("#confirmModal", "e=>e.classList.contains('on')"):
                page.click("#confirmYes"); page.wait_for_timeout(300)
        if perdidos:
            raise AssertionError("tiran el borrador sin preguntar ni guardarlo: " +
                                 ", ".join(perdidos))
        return "ningún camino pierde el borrador"
    check("robustez", "el borrador del compositor no se pierde al cerrar", borrador_al_cerrar)

    # ================= E. EDITOR DE MÓDULOS =================
    FASE["v"] = "editor-modulos"
    page.click('[data-sec="modulos"]')
    page.wait_for_selector("#viewModulos", state="visible")
    check("editor", "lista de módulos", lambda:
          "%d tarjetas" % len(page.query_selector_all("#modList .mod, #viewModulos .mod")))

    def abrir_por_clave(clave):
        """Abre el módulo por su key. Se busca la tarjeta por TÍTULO y no por
        índice: la Cartelera no se lista, así que las tarjetas están corridas
        un lugar respecto de MODULOS y el índice abría el módulo de al lado."""
        titulo = page.evaluate(
            "k => ((typeof MODULOS!=='undefined'?MODULOS:[]).find(m => m.key === k)||{}).title",
            clave)
        if not titulo:
            raise AssertionError("no existe el módulo %r" % clave)
        # ensure_ascii=False: el escape \uXXXX rompe el selector
        # ("Reporte de métricas" no matcheaba por la tilde)
        card = page.query_selector("#viewModulos .mod:has-text(%s)"
                                   % json.dumps(titulo, ensure_ascii=False))
        if card is None:
            raise AssertionError("no encuentro la tarjeta de %r" % titulo)
        card.click()
        page.wait_for_selector("#viewDetalle", state="visible")
        visto = (page.text_content("#detBarTitle") or "").strip()
        if titulo.strip() not in visto:
            raise AssertionError("abrí %r pero quería %r" % (visto, titulo))
        return visto

    def abrir_manual():
        nombre = abrir_por_clave("manual")
        page.wait_for_selector("#gbDoc", state="visible")
        n = page.eval_on_selector("#gbDoc", "e=>e.children.length")
        if n < 5:
            raise AssertionError("el canvas abrió con %d bloques" % n)
        return "abierto %r con %d bloques" % (nombre.strip(), n)
    check("editor", "abrir un módulo (editor de bloques)", abrir_manual)
    shot(page, "06-editor-modulo")

    check("editor", "el menú lateral sigue visible (fix v35)", lambda: (
        page.wait_for_selector('[data-sec="modulos"]', state="visible"),
        "sidebar a la vista")[-1])

    def probar_scroll():
        r = page.evaluate("""() => {
          const cands = ['.mesa', '#editorBody', '.editor-body', '#gbSidebar', '#viewDetalle'];
          for (const s of cands) {
            const e = document.querySelector(s);
            if (e && e.scrollHeight > e.clientHeight + 60) {
              e.scrollTop = 500;
              return {sel: s, top: e.scrollTop, sh: e.scrollHeight, ch: e.clientHeight};
            }
          }
          const de = document.scrollingElement;
          de.scrollTop = 500;
          return {sel: 'document', top: de.scrollTop, sh: de.scrollHeight, ch: de.clientHeight};
        }""")
        if r["top"] <= 0:
            raise AssertionError("no scrollea: %s" % r)
        page.evaluate("document.querySelectorAll('%s').forEach(e=>e.scrollTop=0)" % r["sel"] if r["sel"] != "document" else "document.scrollingElement.scrollTop=0")
        return "scrollea %s (top=%s de %s/%s)" % (r["sel"], r["top"], r["sh"], r["ch"])
    check("editor", "el editor scrollea (fix v36)", probar_scroll)

    def editar_guardar_deshacer():
        zona = page.query_selector("#gbDoc [contenteditable]")
        if not zona:
            raise AssertionError("no hay zona editable en el canvas")
        original = zona.text_content()
        zona.click()
        page.keyboard.press("End")
        page.keyboard.type(" AUDIT-MARCA")
        page.wait_for_timeout(1400)          # checkpoint del deshacer (1 s)
        rot_antes = page.text_content("#detSave").strip()
        page.click("#detUndo")
        page.wait_for_timeout(700)
        texto = page.eval_on_selector("#gbDoc", "e=>e.innerText")
        if "AUDIT-MARCA" in texto:
            raise AssertionError("deshacer no revirtió el texto")
        return "editó, deshizo (botón decía %r)" % rot_antes
    check("editor", "edición inline + deshacer", editar_guardar_deshacer)

    def guardar_modulo():
        page.click("#detSave")
        page.wait_for_function(
            "document.querySelector('#detSave').textContent.includes('Guardado')", timeout=9000)
        return page.text_content("#detSave").strip()
    check("editor", "guardar muestra 'Guardado ✓'", guardar_modulo)

    def agregar_bloque():
        add = page.query_selector("#gbAdd summary") or page.query_selector("#gbAdd")
        add.click()
        page.wait_for_timeout(300)
        b = page.query_selector("#gbAdd .pal-b:has-text('Título')") or \
            page.query_selector(".pal-b:has-text('Título')") or \
            page.query_selector("#gbAdd button:has-text('Título')")
        if not b:
            raise AssertionError("no encuentro el bloque Título en la paleta")
        antes = page.eval_on_selector("#gbDoc", "e=>e.children.length")
        b.click()
        page.wait_for_timeout(500)
        despues = page.eval_on_selector("#gbDoc", "e=>e.children.length")
        if despues <= antes:
            raise AssertionError("el bloque no se agregó (%d→%d)" % (antes, despues))
        page.wait_for_timeout(1200)
        page.click("#detUndo")
        page.wait_for_timeout(600)
        return "agrega (%d→%d) y deshacer lo saca" % (antes, despues)
    check("editor", "paleta: agregar bloque + deshacer", agregar_bloque)

    def vista_mobile():
        page.click("#vtMobile")
        page.wait_for_function("document.querySelector('#gbDoc').classList.contains('is-mobile')")
        shot(page, "07-editor-mobile")
        page.click("#vtDesktop")
        page.wait_for_function("!document.querySelector('#gbDoc').classList.contains('is-mobile')")
        return "alterna is-mobile"
    check("editor", "vista escritorio/celular", vista_mobile)

    def menu_mas():
        page.click("#detMore")
        page.wait_for_selector("#detMoreMenu", state="visible")
        tx = page.text_content("#detMoreMenu")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        return "opciones: " + " / ".join(t.strip() for t in tx.split("\n") if t.strip())[:90]
    check("editor", "menú ⋯ Más", menu_mas)

    def guardas_salida():
        zona = page.query_selector("#gbDoc [contenteditable]")
        zona.click()
        page.keyboard.type("XX")
        page.wait_for_timeout(300)
        page.click("#detBack")
        page.wait_for_selector("#confirmModal.on", state="visible")
        botones = page.text_content("#confirmModal")
        # seguir editando
        page.click("#confirmNo")
        page.wait_for_timeout(300)
        if not page.is_visible("#viewDetalle"):
            raise AssertionError("'seguir editando' salió igual")
        page.click("#detBack")
        page.wait_for_selector("#confirmModal.on", state="visible")
        alt = page.query_selector("#confirmAlt")
        if alt and alt.is_visible():
            alt.click()          # salir sin guardar
        else:
            page.click("#confirmYes")
        page.wait_for_selector("#viewModulos", state="visible")
        return "guarda de 3 botones OK (%s)" % " | ".join(b.strip() for b in botones.split("\n") if b.strip())[:80]
    check("editor", "guarda de cambios sin guardar", guardas_salida)

    def modulo_nuevo():
        page.click("#btnAddModulo")
        page.wait_for_selector("#viewDetalle", state="visible")
        page.click("#detBack")
        try:
            page.wait_for_selector("#confirmModal.on", state="visible", timeout=1500)
            alt = page.query_selector("#confirmAlt")
            if alt and alt.is_visible():
                alt.click()
            else:
                page.click("#confirmYes")
        except Exception:
            pass
        page.wait_for_selector("#viewModulos", state="visible")
        return "abre y sale"
    check("editor", "crear módulo nuevo (y cancelar)", modulo_nuevo)

    def editor_coleccion():
        # el módulo `reporte` no usa el canvas de bloques sino la colección
        # (los reportes por mes). Es la pantalla donde se perdió Marzo-Mayo.
        nombre = abrir_por_clave("reporte")
        page.wait_for_selector("#colList", state="visible", timeout=6000)
        n = page.eval_on_selector("#colList", "e=>e.children.length")
        docs = page.evaluate("""() => {
          const m = (typeof MODULOS!=='undefined'?MODULOS:[]).find(x => x.key === 'reporte');
          return ((m && m.content && m.content.docs) || []).map(d => d.titulo);
        }""")
        page.click("#detBack")
        page.wait_for_timeout(600)
        if page.eval_on_selector("#confirmModal", "e=>e.classList.contains('on')"):
            alt = page.query_selector("#confirmAlt")
            (alt.click() if alt and alt.is_visible() else page.click("#confirmNo"))
            page.wait_for_timeout(400)
        page.wait_for_selector("#viewModulos", state="visible")
        if n == 0:
            raise AssertionError("la colección abrió vacía (docs en memoria: %s)" % docs)
        if len(docs) != n:
            raise AssertionError("la lista muestra %d de %d documentos: %s" % (n, len(docs), docs))
        return "%r lista %d documentos: %s" % (nombre.strip(), n, ", ".join(docs)[:70])
    check("editor", "editor de colección (módulo reporte)", editor_coleccion)

    # ================= F. MODALES GLOBALES =================
    FASE["v"] = "modales"

    def probar_modal(boton, modal, nombre, shotname=None):
        page.click(boton)
        page.wait_for_selector(modal + ".on", state="visible")
        if shotname:
            shot(page, shotname)
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('%s').classList.contains('on')" % modal)
        return "abre y cierra"
    check("modales", "historial", lambda: probar_modal("#btnHistorial", "#histModal", "historial", "08-historial"))
    check("modales", "avisar al equipo", lambda: probar_modal("#btnAvisar", "#avisarModal", "avisar"))
    check("modales", "kit / clave del equipo", lambda: probar_modal("#btnKit", "#kitModal", "kit"))
    def bandeja():
        # en modo cerebro la bandeja está oculta a propósito (todos publican
        # directo). Se comprueba que el modal siga sano abriéndolo por código.
        if page.eval_on_selector("#btnBandeja", "e=>e.offsetParent !== null"):
            return probar_modal("#btnBandeja", "#bandeja", "bandeja")
        page.evaluate("abrirModal(document.querySelector('#bandeja'))")
        page.wait_for_selector("#bandeja.on", state="visible")
        page.click("#bandejaClose")          # su propia X (no tiene Escape propio)
        page.wait_for_function("!document.querySelector('#bandeja').classList.contains('on')")
        return "oculta por diseño (modo cerebro); el modal abre y cierra bien"
    check("modales", "bandeja de aprobaciones", bandeja)

    def publicar_cancelar():
        # el botón sólo aparece cuando hay algo pendiente: se fuerza el estado
        # anotando un módulo como editado (que es lo que hace guardar)
        page.evaluate("""() => {
          const m = (typeof MODULOS!=='undefined'?MODULOS:[])[0];
          if (m && typeof marcarEditado === 'function') marcarEditado(m.key);
          if (typeof actualizarBotones === 'function') actualizarBotones();
        }""")
        page.wait_for_selector("#btnPublicar", state="visible", timeout=4000)
        page.click("#btnPublicar")
        page.wait_for_selector("#confirmModal.on", state="visible")
        tx = (page.text_content("#confirmTitle") or "").strip()
        cuerpo = (page.text_content("#confirmMsg") or "").strip()
        page.click("#confirmNo")
        page.wait_for_function("!document.querySelector('#confirmModal').classList.contains('on')")
        if "publicar" not in (tx + cuerpo).lower():
            raise AssertionError("el cartel no habla de publicar: %r" % (tx + cuerpo)[:80])
        return "pregunta %r y cancela" % tx
    check("modales", "Publicar pide confirmación (cancelada)", publicar_cancelar)

    def publicar_ok():
        page.evaluate("""() => {
          const m = (typeof MODULOS!=='undefined'?MODULOS:[])[0];
          if (m && typeof marcarEditado === 'function') marcarEditado(m.key);
          if (typeof actualizarBotones === 'function') actualizarBotones();
        }""")
        page.wait_for_selector("#btnPublicar", state="visible", timeout=4000)
        page.click("#btnPublicar")
        page.wait_for_selector("#confirmModal.on", state="visible")
        page.click("#confirmYes")
        # el aviso ahora es la tarjeta flotante, no un toast de 11px abajo
        page.wait_for_selector("#pubCard.listo", state="visible", timeout=9000)
        aviso = (page.text_content("#pubCard") or "").strip().replace("\n", " ")
        esp = page.text_content("#pubCard [data-espera]") or ""
        if "vendedores" not in esp:
            raise AssertionError("no avisa cuándo lo van a ver: %r" % esp)
        page.click("#pubCard")                 # se saca de encima con un click
        page.wait_for_timeout(500)
        if page.eval_on_selector("#pubCard", "e=>e.classList.contains('on')"):
            raise AssertionError("la tarjeta no se cierra al tocarla")
        return "tarjeta: %r" % " ".join(aviso.split())[:78]
    check("modales", "Publicar avisa con la tarjeta flotante", publicar_ok)

    def buscador_global():
        page.click("#navBuscar")                     # es un <button> que abre el buscador
        page.wait_for_selector("#buscarTodo", state="visible", timeout=4000)
        page.fill("#buscarTodo", "manual")
        page.wait_for_timeout(600)
        n = page.eval_on_selector("#buscarRes", "e=>e.children.length")
        txt = (page.text_content("#buscarRes") or "").strip()[:60].replace("\n", " ")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        if n == 0 and not txt:
            raise AssertionError("el buscador no devolvió nada ni cartel de vacío")
        return "%d resultados: %s" % (n, txt)
    check("modales", "búsqueda global", buscador_global)

    # ================= G. CONSOLA =================
    FASE["v"] = "final"
    shot(page, "09-final-cartelera")

    esperados = [c for c in CONSOLA if c[0] in ("robustez-fallo",)]
    inesperados = [c for c in CONSOLA if c[0] not in ("robustez-fallo",)]
    print("\n===== CONSOLA =====")
    print("errores esperados (fallo forzado): %d" % len(esperados))
    for f, t, tx in inesperados:
        print("INESPERADO [%s] %s: %s" % (f, t, tx[:200]))
    if not inesperados:
        print("0 errores de consola inesperados")

    print("\n===== RESUMEN =====")
    tot = len(RES); ok = sum(1 for r in RES if r[0] == "PASS")
    print("%d/%d PASS" % (ok, tot))
    for e, g, n, nota in RES:
        if e == "FAIL":
            print("FAIL | %s | %s | %s" % (g, n, nota))

    with open(os.path.join(SHOTS, "resultado.json"), "w", encoding="utf-8") as f:
        json.dump({"res": RES, "consola_inesperada": inesperados}, f, ensure_ascii=False, indent=1)

    browser.close()
    pw.stop()
    return 1 if any(r[0] == 'FAIL' for r in RES) else 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
