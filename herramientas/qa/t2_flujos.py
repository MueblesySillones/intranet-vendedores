# -*- coding: utf-8 -*-
"""t2 — flujos funcionales de punta a punta (F1..F20) sobre el sandbox.

Cada flujo hace lo que haría marketing: crear una publicación, editarla,
fijarla, mandarla a la papelera, deshacer en el editor, bajar el Word, etc.
La "verdad" no es lo que muestra la UI sino el modulos.js del sandbox
(MODULOS_JS): si la UI dice OK pero el disco no cambió, es ROTO.

Estados: OK (bien) · ROTO/EXCEPCION (fallan la suite) · el resto
(INCONSISTENTE, SIN FEEDBACK, NO ENCONTRADO, RARO, VACIA, SIN DATOS,
SIN CONTROL) son avisos: molestan pero no son regresión dura.

La publicación real está bloqueada por contexto_seguro(): guardar en el
sandbox funciona (endpoint local), publicar al sitio no sale nunca.

Cada flujo corre dentro de un try: si explota, anota EXCEPCION, se re-ancla
en la cartelera y sigue con el próximo (una pantalla rota no debe esconder
el estado de los demás flujos).
"""
import io
import json
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

import arnes
from arnes import (PANEL_URL, Reporte, contexto_seguro, guardar, ir_seccion,
                   toast)

MARCA = "QA SUITE"          # prefijo de las publicaciones de prueba (y de su limpieza)
AVISOS = ("INCONSISTENTE", "SIN FEEDBACK", "NO ENCONTRADO", "RARO",
          "VACIA", "SIN DATOS", "SIN CONTROL")

rep = Reporte("t2-flujos")
F = []


def anota(flujo, estado, nota=""):
    F.append({"flujo": flujo, "estado": estado, "nota": str(nota)[:180]})
    print("  [%-12s] %-46s %s" % (estado, flujo, str(nota)[:70]))
    if estado == "OK":
        rep.oks.append({"titulo": flujo, "extra": str(nota)[:160]})
    elif estado in AVISOS:
        rep.avisos.append({"titulo": "%s: %s" % (flujo, estado), "extra": str(nota)[:160]})
    else:  # ROTO / EXCEPCION
        rep.fallas.append({"titulo": "%s: %s" % (flujo, estado), "extra": str(nota)[:160]})


def n_posts():
    """La verdad del disco: MODULOS es un `let` de script clásico, así que se
    lee el archivo del sandbox en vez de preguntarle al navegador."""
    t = io.open(arnes.MODULOS_JS, encoding="utf-8").read()
    mods = json.loads(t[t.find("["):t.rfind("]") + 1])
    for m in mods:
        c = m.get("content") or {}
        if c.get("tipo") in ("cartelera", "muro"):
            return {"docs": len(c.get("docs") or []), "pap": len(c.get("papelera") or []),
                    "titulos": [d.get("titulo") for d in (c.get("docs") or [])]}
    return None


def abrir_compositor(pg):
    pg.get_by_text("¿Qué querés comunicarle al equipo?").first.click()
    pg.wait_for_timeout(700)


def correr():
    arnes.preparar_salida()
    puerto_propio = str(urlparse(PANEL_URL).port or "")

    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = contexto_seguro(br, viewport={"width": 1440, "height": 900})
        # 15s de espera máxima por acción: si un control no aparece, mejor un
        # EXCEPCION rápido y seguir, que 30s de default colgando cada flujo roto
        ctx.set_default_timeout(15000)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
        pg.goto(PANEL_URL, wait_until="networkidle")
        pg.wait_for_timeout(2000)
        ir_seccion(pg, "muro")

        def reanclar():
            """Después de una excepción, volver a un estado navegable conocido."""
            try:
                pg.keyboard.press("Escape")
                pg.goto(PANEL_URL, wait_until="networkidle")
                pg.wait_for_timeout(1500)
                ir_seccion(pg, "muro")
            except Exception:  # noqa: BLE001 - si ni esto anda, lo dirá el próximo flujo
                pass

        def paso(nombre, fn):
            try:
                fn()
            except Exception as e:  # noqa: BLE001 - el flujo anota y la suite sigue
                anota(nombre, "EXCEPCION", str(e)[:130])
                reanclar()

        base = n_posts()
        print("estado inicial:", base)
        if base is None:
            anota("F0 módulo cartelera/muro presente", "ROTO",
                  "modulos.js sin content.tipo cartelera/muro: no hay dónde probar el muro")

        # ---- F1 crear publicación completa ----
        def f1():
            antes = n_posts()
            abrir_compositor(pg)
            pg.fill("#coTitulo", MARCA + " F1 — publicación de prueba")
            pg.fill("#coTexto", "Cuerpo de prueba de la suite QA.")
            pg.evaluate("document.querySelector('#coTipos .co-tipo').click()")
            pg.wait_for_timeout(300)
            pg.locator("#coPublicar").click()
            pg.wait_for_timeout(4000)
            d = n_posts()
            anota("F1 crear publicación", "OK" if d and d["docs"] == antes["docs"] + 1 else "ROTO",
                  "docs %s→%s, toast=%r" % (antes["docs"], d and d["docs"], toast(pg)))
        paso("F1 crear publicación", f1)

        # ---- F2 doble click al crear: una sola ----
        def f2():
            antes = n_posts()
            abrir_compositor(pg)
            pg.fill("#coTitulo", MARCA + " F2 — doble click")
            pg.fill("#coTexto", "x")
            pg.locator("#coPublicar").click(force=True)
            try:
                pg.locator("#coPublicar").click(force=True, timeout=1500)
            except Exception:  # noqa: BLE001 - si el botón ya se deshabilitó, mejor
                pass
            pg.wait_for_timeout(4000)
            d = n_posts()
            anota("F2 doble click no duplica", "OK" if d["docs"] == antes["docs"] + 1 else "ROTO",
                  "docs %s→%s" % (antes["docs"], d["docs"]))
        paso("F2 doble click no duplica", f2)

        # ---- F3 editar y guardar ----
        def f3():
            pg.locator(".mp-mas").first.click()
            pg.wait_for_timeout(500)
            pg.locator(".mp-mi").filter(has_text="Editar").first.click()
            pg.wait_for_timeout(1000)
            pg.fill("#coTitulo", pg.input_value("#coTitulo").rstrip() + " (editada)")
            pg.locator("#coPublicar").click()
            pg.wait_for_timeout(4000)
            ed = any("(editada)" in (t or "") for t in n_posts()["titulos"])
            anota("F3 editar publicación", "OK" if ed else "ROTO", "título actualizado=%s" % ed)
        paso("F3 editar publicación", f3)

        # ---- F4 fijar / desfijar reversible ----
        def f4():
            pg.locator(".mp-mas").first.click()
            pg.wait_for_timeout(500)
            fij = pg.locator(".mp-mi").filter(has_text="Fijar")
            des = pg.locator(".mp-mi").filter(has_text="Dejar de fijar")
            accion = "Fijar" if fij.count() and not des.count() else "Dejar de fijar"
            (fij if accion == "Fijar" else des).first.click()
            pg.wait_for_timeout(2500)
            pg.locator(".mp-mas").first.click()
            pg.wait_for_timeout(500)
            contra = pg.locator(".mp-mi").filter(
                has_text="Dejar de fijar" if accion == "Fijar" else "Fijar arriba")
            anota("F4 fijar/desfijar reversible", "OK" if contra.count() else "INCONSISTENTE",
                  "%s → el menú ofrece lo inverso: %s" % (accion, bool(contra.count())))
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(400)
        paso("F4 fijar/desfijar reversible", f4)

        # ---- F5 ocultar / volver a mostrar ----
        def f5():
            pg.locator(".mp-mas").first.click()
            pg.wait_for_timeout(500)
            oc = pg.locator(".mp-mi").filter(has_text="Ocultar")
            if not oc.count():
                anota("F5 ocultar", "NO ENCONTRADO", "sin opción Ocultar en ⋯")
                pg.keyboard.press("Escape")
                return
            oc.first.click()
            pg.wait_for_timeout(2500)
            pg.locator(".mp-mas").first.click()
            pg.wait_for_timeout(500)
            rev = pg.locator(".mp-mi").filter(has_text="Mostrar")
            anota("F5 ocultar reversible", "OK" if rev.count() else "INCONSISTENTE",
                  "ofrece 'Mostrar': %s" % bool(rev.count()))
            if rev.count():
                rev.first.click()
                pg.wait_for_timeout(2000)
            else:
                pg.keyboard.press("Escape")
        paso("F5 ocultar reversible", f5)

        # ---- F6 duplicar ----
        def f6():
            antes = n_posts()
            pg.locator(".mp-mas").first.click()
            pg.wait_for_timeout(500)
            dup = pg.locator(".mp-mi").filter(has_text="Duplicar")
            if not dup.count():
                anota("F6 duplicar", "NO ENCONTRADO")
                pg.keyboard.press("Escape")
                return
            dup.first.click()
            pg.wait_for_timeout(2500)
            desp = n_posts()
            anota("F6 duplicar", "OK" if desp["docs"] == antes["docs"] + 1 else "ROTO",
                  "docs %s→%s" % (antes["docs"], desp["docs"]))
        paso("F6 duplicar", f6)

        # ---- F7 eliminar → papelera → restaurar ----
        def f7():
            antes = n_posts()
            pg.locator(".mp-mas").first.click()
            pg.wait_for_timeout(500)
            pg.locator(".mp-mi").filter(has_text="Eliminar").first.click()
            pg.wait_for_timeout(800)
            hubo_conf = pg.locator("#confirmYes:visible").count() > 0
            if hubo_conf:
                pg.locator("#confirmYes").click()
            pg.wait_for_timeout(2500)
            tras = n_posts()
            a_pap = tras["pap"] == antes["pap"] + 1 and tras["docs"] == antes["docs"] - 1
            anota("F7a eliminar → papelera", "OK" if a_pap else "ROTO",
                  "confirmó=%s, docs %s→%s, papelera %s→%s"
                  % (hubo_conf, antes["docs"], tras["docs"], antes["pap"], tras["pap"]))
            pg.locator(".mf-tacho, .mf").filter(has_text="Papelera").first.click()
            pg.wait_for_timeout(1200)
            rest = pg.get_by_text("Restaurar", exact=False).filter(visible=True)
            if rest.count():
                rest.first.click()
                pg.wait_for_timeout(2500)
                fin = n_posts()
                anota("F7b restaurar de papelera",
                      "OK" if fin["docs"] == tras["docs"] + 1 else "ROTO",
                      "docs %s→%s" % (tras["docs"], fin["docs"]))
            else:
                anota("F7b restaurar de papelera", "SIN CONTROL",
                      "no hay botón Restaurar visible en la papelera")
            pg.locator(".mf").filter(has_text="Todas").first.click()
            pg.wait_for_timeout(800)
        paso("F7 eliminar/restaurar", f7)

        # ---- F8 'Archivar en' habilita su select ----
        def f8():
            abrir_compositor(pg)
            dep = pg.evaluate("""() => { const c = document.getElementById('coArchivar'),
                s = document.getElementById('coArchivarMod');
                const antes = s.disabled; c.click();
                return new Promise(r => setTimeout(() => r({ antes, despues: s.disabled }), 250)); }""")
            anota("F8 'Archivar en' habilita su select",
                  "OK" if dep["antes"] and not dep["despues"] else "INCONSISTENTE", dep)
            pg.locator("#coCerrar").click()
            pg.wait_for_timeout(500)
        paso("F8 archivar-en", f8)

        # ---- F9/F10 editor: deshacer y eliminar bloque ----
        def f9_f10():
            ir_seccion(pg, "modulos")
            pg.locator("#viewModulos").get_by_text(arnes.MODULO_EDITOR, exact=False).first.click()
            pg.wait_for_timeout(2500)
            pg.evaluate("typeof gbPane === 'function' && gbPane('agregar')")
            pg.wait_for_timeout(500)
            nb = pg.locator(".gb-block").count()
            pg.evaluate("typeof gbPane === 'function' && gbPane('agregar')")
            pg.evaluate("document.querySelector('.gb-tipo[data-t=separador]').click()")
            pg.wait_for_timeout(700)
            pg.locator("#detUndo").click()
            pg.wait_for_timeout(700)
            anota("F9 deshacer una inserción",
                  "OK" if pg.locator(".gb-block").count() == nb else "ROTO",
                  "bloques %d → %d tras undo" % (nb, pg.locator(".gb-block").count()))
            pg.locator(".gb-block").nth(1).click()
            pg.wait_for_timeout(400)
            borro = pg.evaluate("""() => { const sel = document.querySelector('.gb-block.is-selected .gb-h-del, .gb-block.is-selected .gb-handle button:last-child');
                if (!sel) return 'sin boton'; sel.click(); return 'clickeado'; }""")
            pg.wait_for_timeout(700)
            conf = pg.locator("#confirmYes:visible")
            if conf.count():
                conf.first.click()
                pg.wait_for_timeout(600)
            tras = pg.locator(".gb-block").count()
            anota("F10 eliminar bloque (✕)",
                  "OK" if tras == nb - 1 else ("SIN FEEDBACK" if tras == nb else "RARO"),
                  "%s · bloques %d→%d · confirmó=%s" % (borro, nb, tras, bool(conf.count())))
            pg.locator("#detUndo").click()          # devolvemos el bloque borrado
            pg.wait_for_timeout(700)
        paso("F9/F10 editor undo+eliminar", f9_f10)

        # ---- F11 guardar desde el editor ----
        def f11():
            # autosuficiente: si F9/F10 explotó y nos re-ancló en la cartelera,
            # F11 vuelve a entrar al editor en vez de heredar el naufragio
            if not pg.locator("#detSave").count() or not pg.locator("#detSave").first.is_visible():
                ir_seccion(pg, "modulos")
                pg.locator("#viewModulos").get_by_text(arnes.MODULO_EDITOR, exact=False).first.click()
                pg.wait_for_timeout(2500)
            pg.locator("#detSave").click()
            pg.wait_for_timeout(2500)
            anota("F11 guardar módulo",
                  "OK" if (toast(pg) or "").startswith("Guardado") else "SIN FEEDBACK",
                  "toast=%r" % toast(pg))
        paso("F11 guardar módulo", f11)

        # ---- F17 botón Atrás del navegador ----
        def f17():
            pg.go_back()
            pg.wait_for_timeout(1000)
            donde = pg.evaluate("location.href")
            anota("F17 botón Atrás del navegador",
                  "OK" if puerto_propio and puerto_propio in donde else "INCONSISTENTE",
                  "quedó en %s" % donde[:50])
            pg.go_forward()
            pg.wait_for_timeout(1500)
        paso("F17 botón Atrás", f17)

        # ---- F13 datos: interruptor y contador ----
        def f13():
            pg.goto(PANEL_URL, wait_until="networkidle")
            pg.wait_for_timeout(1500)
            ir_seccion(pg, "datos")
            pg.locator("#datosRaiz").get_by_text("Derivaciones", exact=False).first.click()
            pg.wait_for_timeout(8000)
            pg.locator(".dt-nums .dt-sw").first.click()
            pg.wait_for_timeout(1500)
            cuenta = pg.locator(".dt-cuenta-n").inner_text().strip()
            anota("F13 interruptor de Datos", "OK" if cuenta == "1" else "ROTO",
                  "contador=%s" % cuenta)
            pg.locator(".dt-apagar").click()
            pg.wait_for_timeout(1200)
        paso("F13 interruptor de Datos", f13)

        # ---- F14 'Ver reporte' abre el deck en pestaña nueva ----
        def f14():
            with ctx.expect_page(timeout=15000) as nueva:
                pg.get_by_text("Ver reporte", exact=False).first.click()
            deck = nueva.value
            deck.wait_for_load_state()
            deck.wait_for_timeout(2500)
            slides = deck.locator(".slide, section").count()
            anota("F14 'Ver reporte' abre el deck", "OK" if slides > 3 else "RARO",
                  "slides=%d" % slides)
            deck.close()
        paso("F14 'Ver reporte'", f14)

        # ---- F15 descargar Word ----
        def f15():
            with pg.expect_download(timeout=30000) as dl:
                pg.get_by_text("Descargar Word", exact=False).first.click()
            anota("F15 Descargar Word", "OK", dl.value.suggested_filename)
        paso("F15 Descargar Word", f15)

        # ---- F16 métricas ----
        def f16():
            ir_seccion(pg, "metricas")
            mtxt = pg.evaluate("document.getElementById('viewMetricas') ? "
                               "document.getElementById('viewMetricas').innerText.slice(0, 200) : ''")
            anota("F16 pantalla Métricas", "OK" if len(mtxt) > 40 else "VACIA",
                  mtxt[:70].replace("\n", " · "))
        paso("F16 pantalla Métricas", f16)

        # ---- F18 avisar novedad (el envío real está bloqueado) ----
        def f18():
            pg.locator("#btnAvisar").click()
            pg.wait_for_timeout(1000)
            lista = pg.locator("#avisarLista input[type=checkbox]").count()
            anota("F18 modal Avisar novedad", "OK" if lista >= 5 else "RARO",
                  "%d módulos listados" % lista)
            pg.locator("[data-cerrar-avisar]").last.click()
            pg.wait_for_timeout(500)
        paso("F18 modal Avisar", f18)

        # ---- F19 historial (GitHub) + cierre con Escape ----
        def f19():
            pg.locator("#btnHistorial").click()
            pg.wait_for_timeout(6000)
            filas = pg.evaluate("""() => { const m = document.querySelector('.modal:not([hidden])');
                return m ? m.querySelectorAll('button, li, [class*=hist]').length : 0; }""")
            anota("F19 Historial (GitHub)", "OK" if filas > 2 else "SIN DATOS",
                  "%d elementos (sin red o sin repo => SIN DATOS)" % filas)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(600)
            esc = pg.evaluate("(()=>{const m=document.getElementById('histModal');return !m || m.hidden})()")
            anota("F19b Historial cierra con Escape", "OK" if esc else "INCONSISTENTE",
                  "" if esc else "hubo que cerrarlo por otro lado")
            if not esc:
                overlay = pg.evaluate("""() => { const ov = document.querySelector('#histModal [data-cerrar-hist]');
                    if (ov) ov.click();
                    return new Promise(r => setTimeout(() => r(document.getElementById('histModal').hidden), 400)); }""")
                anota("F19c Historial cierra con el overlay", "OK" if overlay else "ROTO",
                      "" if overlay else "ni la X ni el fondo lo cierran por click JS")
                if not overlay:
                    pg.evaluate("document.getElementById('histModal').hidden = true")
                pg.wait_for_timeout(400)
        paso("F19 Historial", f19)

        # ---- F20 título al tope del maxlength + cuerpo larguísimo ----
        def f20():
            ir_seccion(pg, "muro")
            abrir_compositor(pg)
            pg.fill("#coTitulo", "A" * 300)
            largo = len(pg.input_value("#coTitulo"))
            pg.fill("#coTexto", ("Texto larguísimo. " * 300).strip())
            pg.locator("#coPublicar").click()
            pg.wait_for_timeout(4500)
            desb = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            anota("F20 título 300 chars + cuerpo 5k", "OK" if largo <= 120 and desb <= 1 else "ROTO",
                  "maxlength recorta a %d, desborde=%d" % (largo, desb))
        paso("F20 título largo", f20)

        # ---- limpieza: las publicaciones de prueba, a la papelera ----
        # Best-effort: el sandbox se descarta entero igual; esto es para que una
        # corrida --sin-sandbox no acumule basura. Cada intento va en su try y el
        # ⋯ se busca con hover (puede aparecer recién al pasar el mouse).
        def limpiar():
            ir_seccion(pg, "muro")
            errores = 0
            for _ in range(8):
                quedan = n_posts()
                con_marca = [t for t in (quedan["titulos"] if quedan else [])
                             if t and (MARCA in t or t.startswith("AAAA"))]
                if not con_marca or errores >= 2:
                    break
                try:
                    fila = pg.locator(".mu-post").filter(has_text=MARCA).first
                    if not fila.count():
                        fila = pg.locator(".mu-post").first
                    fila.hover()
                    fila.locator(".mp-mas").first.click(timeout=5000)
                    pg.wait_for_timeout(400)
                    pg.locator(".mp-mi").filter(has_text="Eliminar").first.click(timeout=5000)
                    pg.wait_for_timeout(600)
                    c = pg.locator("#confirmYes:visible")
                    if c.count():
                        c.first.click()
                    pg.wait_for_timeout(1800)
                except Exception:  # noqa: BLE001 - limpieza a medias no es falla
                    errores += 1
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(500)
            if con_marca and errores:
                print("  (limpieza incompleta: quedan %d de prueba en el sandbox)" % len(con_marca))
        paso("limpieza de publicaciones de prueba", limpiar)

        print("estado final:", n_posts(), "| errores JS:", errs[:4])
        if errs:
            rep.falla("errores JS durante los flujos", "; ".join(errs[:3]))
        ctx.close()
        br.close()

    guardar("t2-flujos.json", {"flujos": F})
    return rep.cerrar(extra={"flujos": len(F)})


if __name__ == "__main__":
    sys.exit(correr())
