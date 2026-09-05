# -*- coding: utf-8 -*-
"""Verifica el aviso de guardar/publicar pedido el 4-sep:
  · el botón Guardar dice Guardando… y termina en "Guardado ✓"
  · con un cambio nuevo vuelve a decir "Guardar"
  · Publicar muestra la tarjeta flotante (barra en movimiento) y termina
    con el tilde verde + la cuenta de los ~30 s de Vercel
  · el botón queda en "Publicado ✓" y vuelve a "Publicar" con el cambio siguiente
  · un fallo del servidor pinta la tarjeta en rojo y no miente
El retardo se pone DENTRO del navegador para poder mirar los estados."""
import sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

import os
BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "salida", "web3", "avisos")
os.makedirs(SHOTS, exist_ok=True)
DEMORA = 2200
RES = []

PARCHE = """(o) => {
  const orig = window.fetch;
  window.__falla = false;
  window.fetch = function (u, x) {
    const s = String(u);
    if (s.includes('/api/publicar')) {
      const cuerpo = window.__falla
        ? JSON.stringify({ok: false, log: 'el cerebro no respondio'})
        : JSON.stringify({ok: true});
      return new Promise(r => setTimeout(() => r(new Response(cuerpo,
        {status: 200, headers: {'Content-Type': 'application/json'}})), o.ms));
    }
    if (s.includes('/api/modulos') && x && x.method === 'POST')
      return new Promise(r => setTimeout(() => r(orig(u, x)), o.ms));
    return orig(u, x);
  };
}"""

FOTO = """() => {
  const b = s => { const e = document.querySelector(s); if (!e) return null;
    const r = e.querySelector('[data-rotulo]');
    return {t: (r ? r.textContent : e.textContent).trim(), dis: e.disabled,
            hecho: e.classList.contains('btn-hecho'),
            icono: !!e.querySelector('svg:not(.pubcard-ok)')}; };
  const c = document.querySelector('#pubCard');
  return {
    guardar: b('#detSave'), publicar: b('#detPublicar'),
    card: c && !c.hidden ? {
      on: c.classList.contains('on'), listo: c.classList.contains('listo'),
      error: c.classList.contains('error'),
      tit: (c.querySelector('[data-tit]')||{}).textContent,
      sub: (c.querySelector('[data-sub]')||{}).textContent,
      espera: c.querySelector('[data-espera]').hidden ? null
              : (c.querySelector('[data-espera]').textContent||'').trim(),
      barraAnim: getComputedStyle(c.querySelector('.pubcard-barra i')).animationName,
    } : null,
  };
}"""


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(("PASS", nombre, str(nota)))
        print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:
        RES.append(("FAIL", nombre, str(e).split("\n")[0][:200]))
        print("FAIL | %s | %s" % (nombre, str(e).split("\n")[0][:200]))


with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    errs = []
    p.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:180]))
    p.set_default_timeout(15000)
    p.goto(BASE + "/", wait_until="domcontentloaded")
    p.wait_for_selector("#muroLista .pub", timeout=10000)
    p.evaluate(PARCHE, {"ms": DEMORA})

    p.click('[data-sec="modulos"]'); p.wait_for_selector("#viewModulos", state="visible")
    p.wait_for_timeout(500)
    titulo = p.evaluate("k => (MODULOS.find(m=>m.key===k)||{}).title", "manual")
    p.query_selector("#viewModulos .mod:has-text('%s')" % titulo).click()
    p.wait_for_selector("#gbDoc", state="visible"); p.wait_for_timeout(800)

    def tocar(marca):
        z = p.query_selector("#gbDoc [contenteditable]")
        z.click(); p.keyboard.press("End"); p.keyboard.type(marca)
        p.wait_for_timeout(1500)   # el vigilante refresca los botones cada ~1 s

    # --- GUARDAR ---
    tocar(" A")
    check("con un cambio el botón dice Guardar", lambda: (
        (lambda f: f if f["guardar"]["t"] == "Guardar" and not f["guardar"]["hecho"]
         else (_ for _ in ()).throw(AssertionError("dice %r hecho=%s" % (
             f["guardar"]["t"], f["guardar"]["hecho"]))))(p.evaluate(FOTO)),
        "Guardar")[-1])

    p.click("#detSave")
    p.wait_for_timeout(600)
    check("mientras guarda dice Guardando… y está apagado", lambda: (
        (lambda f: f if "Guardando" in f["guardar"]["t"] and f["guardar"]["dis"]
         else (_ for _ in ()).throw(AssertionError(json.dumps(f["guardar"]))))(p.evaluate(FOTO)),
        "Guardando… (disabled)")[-1])

    p.wait_for_function("document.querySelector('#detSave').textContent.includes('Guardado')",
                        timeout=12000)
    check("al terminar el botón dice 'Guardado ✓'", lambda: (
        (lambda f: f if f["guardar"]["hecho"]
         else (_ for _ in ()).throw(AssertionError("sin clase btn-hecho")))(p.evaluate(FOTO)),
        p.eval_on_selector("#detSave", "e=>e.textContent.trim()"))[-1])

    tocar(" B")
    check("con un cambio nuevo vuelve a 'Guardar'", lambda: (
        (lambda f: f if f["guardar"]["t"] == "Guardar" and not f["guardar"]["hecho"]
         else (_ for _ in ()).throw(AssertionError(json.dumps(f["guardar"]))))(p.evaluate(FOTO)),
        "vuelve a Guardar")[-1])

    # --- PUBLICAR ---
    def publicar():
        p.click("#detPublicar")
        # publicarCambios pregunta antes de subir: hay que decirle que sí
        p.wait_for_selector("#confirmModal.on", state="visible", timeout=12000)
        p.click("#confirmYes")
    publicar()
    p.wait_for_selector("#pubCard.on", timeout=12000)
    p.wait_for_timeout(500)
    def card_trabajando():
        f = p.evaluate(FOTO)
        c = f["card"]
        if not c or c["listo"] or c["error"]:
            raise AssertionError("la tarjeta no está en 'trabajando': %s" % json.dumps(c, ensure_ascii=False))
        if c["barraAnim"] in ("none", ""):
            raise AssertionError("la barra no se mueve (animation-name=%r)" % c["barraAnim"])
        return "%r · barra=%s" % (c["tit"], c["barraAnim"])
    check("tarjeta flotante 'Publicando…' con barra en movimiento", card_trabajando)
    p.screenshot(path=os.path.join(SHOTS, "publicando.png"))

    p.wait_for_selector("#pubCard.listo", timeout=15000)
    p.wait_for_timeout(400)
    def card_lista():
        c = p.evaluate(FOTO)["card"]
        if not c["listo"]:
            raise AssertionError("no quedó en listo")
        if not c["espera"] or "vendedores" not in c["espera"]:
            raise AssertionError("no avisa la espera de Vercel: %r" % c["espera"])
        return "%r · %r" % (c["tit"], c["espera"])
    check("al terminar: tilde verde + cuenta de los ~30 s", card_lista)
    p.screenshot(path=os.path.join(SHOTS, "publicado.png"))

    check("el botón queda en 'Publicado ✓' con el ícono", lambda: (
        (lambda f: f if f["publicar"]["hecho"] and "Publicado" in f["publicar"]["t"]
                        and f["publicar"]["icono"]
         else (_ for _ in ()).throw(AssertionError(json.dumps(f["publicar"]))))(p.evaluate(FOTO)),
        p.eval_on_selector("#detPublicar", "e=>e.textContent.trim()"))[-1])

    check("la cuenta baja sola", lambda: (
        p.wait_for_timeout(2200),
        (lambda t: t if "28 s" in t or "27 s" in t or "26 s" in t
         else (_ for _ in ()).throw(AssertionError("la cuenta dice %r" % t)))(
            p.eval_on_selector("#pubCard [data-espera]", "e=>e.textContent.trim()")))[-1])

    tocar(" C")
    check("con un cambio nuevo vuelve a 'Publicar'", lambda: (
        (lambda f: f if f["publicar"]["t"] == "Publicar" and not f["publicar"]["hecho"]
         else (_ for _ in ()).throw(AssertionError(json.dumps(f["publicar"]))))(p.evaluate(FOTO)),
        "vuelve a Publicar")[-1])

    # --- FALLO ---
    p.evaluate("() => { window.__falla = true; }")
    publicar()
    p.wait_for_selector("#pubCard.error", timeout=15000)
    def card_error():
        c = p.evaluate(FOTO)["card"]
        if c["espera"]:
            raise AssertionError("con error igual promete que se va a ver")
        return "%r · %r" % (c["tit"], c["sub"])
    check("si falla: tarjeta roja y sin promesa de publicación", card_error)
    p.screenshot(path=os.path.join(SHOTS, "error.png"))

    print("\nerrores de consola:", errs or "ninguno")
    ok = sum(1 for r in RES if r[0] == "PASS")
    print("\n%d/%d PASS" % (ok, len(RES)))
    b.close()
