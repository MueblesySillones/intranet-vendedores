# -*- coding: utf-8 -*-
"""El botón «Actualizar a la última versión».

El pedido, textual: «cuando apreto actualizar me dice que no se puede
actualizar… debería salir la ventana flotante que diga que está descargando
actualización, en un momento se abrirá nueva pestaña actualizada».

Qué había pasado: el servidor pasó a hacer la actualización en un hilo —
contesta al toque con un número de trabajo y va informando el avance por
/api/job—, y la pantalla siguió esperando el `{aplicando: true}` de antes. Como
ese campo ya no llega, caía SIEMPRE en la rama del error, aunque la
actualización estuviera corriendo de verdad.

Acá se prueba contra un servidor de actualización SIMULADO (se interceptan las
tres rutas en el navegador), así que no se toca ninguna instalación real.

    python w7_web3_actualizar.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
RES = []
VERSION = {"version": 99, "label": "9.9.9 - la de prueba",
           "notes": "una version inventada por la auditoria"}


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:220]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:220]))


def json_ok(ruta, cuerpo):
    ruta.fulfill(status=200, content_type="application/json",
                 body=json.dumps(cuerpo))


def montar(ctx, pasos, apply_respuesta=None):
    """Simula el servidor de actualización.

    `pasos` es lo que /api/job va devolviendo, uno por consulta; el último se
    repite. `apply_respuesta` reemplaza lo que contesta /api/update-apply.
    """
    estado = {"i": 0}

    ctx.route("**/api/update-status", lambda r: json_ok(
        r, dict(VERSION, disponible=True)))
    ctx.route("**/api/update-apply", lambda r: json_ok(
        r, apply_respuesta if apply_respuesta is not None
        else {"ok": True, "job": "update_prueba"}))

    def job(r):
        i = min(estado["i"], len(pasos) - 1)
        estado["i"] += 1
        json_ok(r, pasos[i])
    ctx.route("**/api/job**", job)
    return estado


def abrir(p):
    p.goto(BASE + "/", wait_until="domcontentloaded")
    p.wait_for_selector("#muroLista .pub", timeout=25000)
    p.wait_for_selector("#updateBar:not([hidden])", timeout=20000)


def apretar(p):
    """Aprieta Actualizar y confirma el cartel de «¿seguro?»."""
    p.click("#btnUpdate")
    p.wait_for_selector("#confirmModal.on", state="visible", timeout=10000)
    p.click("#confirmYes")


with sync_playwright() as pw:
    b = pw.chromium.launch()
    errs = []

    # ───────────────────────── el camino feliz ─────────────────────────
    ctx = b.new_context(viewport={"width": 1440, "height": 1000})
    montar(ctx, [
        {"estado": "corriendo", "pct": 5, "msg": "Descargando la versión nueva…"},
        {"estado": "corriendo", "pct": 40,
         "msg": "Descargando la última versión… 8 de 20 MB"},
        {"estado": "corriendo", "pct": 84,
         "msg": "Revisando que el archivo llegó completo…"},
        {"estado": "corriendo", "pct": 97,
         "msg": "Instalando y reiniciando el panel…"},
        {"estado": "listo", "pct": 100, "msg": "Listo. El panel se está reiniciando…"},
    ])
    p = ctx.new_page()
    p.set_default_timeout(60000)
    p.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:180]))

    check("la barra avisa que hay versión nueva", lambda: (
        abrir(p), p.text_content("#updateBar .update-txt").strip())[-1][:70])

    def abre_la_ventana():
        apretar(p)
        p.wait_for_selector("#mActualizando.on", state="visible", timeout=15000)
        return "se abre «Actualizando el panel»"
    check("al apretar se abre la ventana flotante", abre_la_ventana)

    def dice_que_descarga():
        p.wait_for_function(
            "() => /Descargando/i.test(document.getElementById('updProgMsg').textContent)",
            timeout=15000)
        return p.text_content("#updProgMsg").strip()
    check("la ventana dice que está descargando", dice_que_descarga)

    def avanza():
        p.wait_for_function(
            "() => parseInt(document.getElementById('updProgPct').textContent) >= 40",
            timeout=20000)
        pct = p.text_content("#updProgPct").strip()
        ancho = p.evaluate(
            "() => document.getElementById('updProgFill').style.width")
        return "la barra va en %s (ancho %s)" % (pct, ancho)
    check("la barra de progreso avanza", avanza)

    def enciende_los_pasos():
        p.wait_for_function(
            """() => document.querySelector('#updPasos [data-paso=instalar]')
                       .classList.contains('ahora')""", timeout=25000)
        cl = p.evaluate("""() => [...document.querySelectorAll('#updPasos .prog-paso')]
              .map(n => n.dataset.paso + ':' + (n.className.replace('prog-paso','').trim() || '-'))""")
        return " · ".join(cl)
    check("los pasos se van encendiendo", enciende_los_pasos)

    def nunca_dice_que_fallo():
        """Lo que el usuario veía: el cartel de error con la actualización andando."""
        txt = p.text_content("#updateBar") or ""
        if "No se pudo" in txt:
            raise AssertionError("sigue diciendo que no se pudo: %r" % txt[:120])
        if p.is_visible("#toast") and "No se pudo" in (p.text_content("#toast") or ""):
            raise AssertionError("el aviso rojo apareció igual")
        return "sin «No se pudo actualizar»"
    check("NO dice que no se pudo actualizar", nunca_dice_que_fallo)

    def termina_esperando_el_reinicio():
        p.wait_for_function(
            """() => document.querySelector('#updPasos [data-paso=reabrir]')
                       .classList.contains('ahora')""", timeout=25000)
        return p.text_content("#updProgMsg").strip()
    check("al terminar queda esperando el reinicio", termina_esperando_el_reinicio)
    p.close(); ctx.close()

    # ── el server se muere en medio de instalar: NO es un error ──
    ctx2 = b.new_context(viewport={"width": 1440, "height": 1000})
    st = montar(ctx2, [
        {"estado": "corriendo", "pct": 92, "msg": "Instalando la nueva versión…"},
    ])
    p2 = ctx2.new_page()
    p2.set_default_timeout(60000)

    def caida_es_reinicio():
        abrir(p2)
        apretar(p2)
        p2.wait_for_function(
            """() => document.querySelector('#updPasos [data-paso=instalar]')
                       .classList.contains('ahora')""", timeout=20000)
        # a partir de acá el panel se mata solo: /api/job deja de responder
        ctx2.route("**/api/job**", lambda r: r.abort())
        p2.wait_for_function(
            """() => document.querySelector('#updPasos [data-paso=reabrir]')
                       .classList.contains('ahora')""", timeout=25000)
        txt = p2.text_content("#updateBar") or ""
        if "No se pudo" in txt:
            raise AssertionError("tomó el reinicio como una falla")
        return "la caída del server se lee como reinicio, no como error"
    check("que el panel se cierre para instalar no es un error", caida_es_reinicio)
    p2.close(); ctx2.close()

    # ───────── y si de verdad falla, se dice y se puede reintentar ─────────
    ctx3 = b.new_context(viewport={"width": 1440, "height": 1000})
    montar(ctx3, [
        {"estado": "error", "pct": 5,
         "error": "No se pudo bajar la versión nueva: sin internet"},
    ])
    p3 = ctx3.new_page()
    p3.set_default_timeout(60000)

    def falla_de_verdad():
        abrir(p3)
        apretar(p3)
        p3.wait_for_function(
            "() => /No se pudo/.test(document.getElementById('updateBar').textContent)",
            timeout=20000)
        txt = p3.text_content("#updateBar") or ""
        if "sin internet" not in txt:
            raise AssertionError("no dice el motivo: %r" % txt[:140])
        if p3.is_visible("#mActualizando.on"):
            raise AssertionError("dejó la ventana de progreso abierta")
        if p3.get_attribute("#btnUpdate", "disabled") is not None:
            raise AssertionError("el botón quedó apagado, no se puede reintentar")
        return "dice el motivo y deja reintentar"
    check("un error de verdad se avisa y deja reintentar", falla_de_verdad)
    p3.close(); ctx3.close()

    print("\nerrores de consola:", errs or "ninguno")
    b.close()

ok = sum(1 for r in RES if r[0] == "PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(1 if ok != len(RES) else 0)
