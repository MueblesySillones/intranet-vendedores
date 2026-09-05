# -*- coding: utf-8 -*-
"""Vuelve a generar el HTML guardado de todos los modulos.

Para que existe: el HTML de cada modulo se arma en el panel y queda guardado
en modulos.js. Cuando el generador cambia —por ejemplo, al empezar a emitir el
`data-bi` que permite que una publicacion mande al vendedor A UN BLOQUE y no al
modulo entero— los modulos que ya estaban guardados siguen con el HTML viejo
hasta que alguien los abre y los guarda de a uno.

Esto hace eso mismo, pero de una: le pide al panel que recalcule
content.html con bloquesHTML (la MISMA funcion que usa al guardar) y persiste.

    python regenerar_html_modulos.py                 # contra el panel de QA
    QA_BASE=http://127.0.0.1:8124 python regenerar_html_modulos.py --aplicar

Sin --aplicar solo informa que cambiaria. La publicacion al sitio NO se toca:
queda como un cambio pendiente, para publicarlo desde el panel.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = os.environ.get("QA_BASE") or "http://127.0.0.1:8144"
APLICAR = "--aplicar" in sys.argv

RECALCULAR = """() => {
  const out = [];
  (MODULOS || []).forEach(m => {
    const c = m && m.content;
    if (!c) return;

    if (c.tipo === 'bloques' && Array.isArray(c.bloques)) {
      const antes = c.html || '';
      const ahora = bloquesHTML(c.bloques, c.presentacion);
      if (antes !== ahora) {
        c.html = ahora;
        out.push({key: m.key, titulo: m.title, bloques: c.bloques.length,
                  anclasAntes: (antes.match(/data-bi=/g) || []).length,
                  anclasAhora: (ahora.match(/data-bi=/g) || []).length});
      }
      return;
    }

    /* La cartelera: cada publicacion tiene su propio html, y ahi vive el link
       a los modulos. Regenerarlo es lo que hace que una publicacion vieja
       —que guardo el NOMBRE del bloque pero no su posicion— pase a apuntar al
       bloque en vez de al modulo entero.
       ⚠️ Solo las que tienen `bloques`. Una publicacion cargada a mano trae el
       html ya armado y ninguna lista de bloques: regenerarla la dejaria EN
       BLANCO. Es el mismo patron que una vez se llevo puesto Marzo-Mayo. */
    if (c.tipo === 'cartelera' && Array.isArray(c.docs)) {
      c.docs.forEach((d, i) => {
        if (!d || !Array.isArray(d.bloques) || !d.bloques.length) return;
        const antes = d.html || '';
        const ahora = bloquesHTML(d.bloques, false);
        if (antes !== ahora) {
          d.html = ahora;
          const link = /<a class="[^"]*m-ref[^"]*" href="#([^"]+)"/.exec(ahora);
          out.push({key: m.key + ' › ' + (d.titulo || ('publicacion ' + i)),
                    titulo: (d.titulo || '(sin titulo)'), bloques: d.bloques.length,
                    anclasAntes: 0, anclasAhora: 0,
                    link: link ? '#' + link[1] : ''});
        }
      });
    }
  });
  return out;
}"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    # nada sale al sitio: esto solo toca el archivo local
    ctx.route("**/api/publicar", lambda r: r.fulfill(
        status=200, content_type="application/json", body='{"ok": true}'))
    if not APLICAR:
        ctx.route("**/api/modulos", lambda r: r.abort()
                  if r.request.method == "POST" else r.continue_())
    p = ctx.new_page()
    p.set_default_timeout(20000)
    p.goto(BASE + "/", wait_until="domcontentloaded")
    p.wait_for_selector("#muroLista .pub", timeout=25000)
    p.wait_for_timeout(1500)

    cambios = p.evaluate(RECALCULAR)
    if not cambios:
        print("nada que regenerar: el HTML guardado ya esta al dia")
    else:
        print("modulos con el HTML desactualizado: %d" % len(cambios))
        for c in cambios:
            extra = ("  link " + c["link"]) if c.get("link") else (
                "  anclas %d -> %d" % (c["anclasAntes"], c["anclasAhora"]))
            print("  %-30s %2d bloques %s" % (c["titulo"][:30], c["bloques"], extra))
        if APLICAR:
            r = p.evaluate("() => persistModulos(false).then(() => 'ok', e => 'ERROR: ' + e.message)")
            print("\nguardado: %s" % r)
            p.wait_for_timeout(1500)
            quedan = p.evaluate(RECALCULAR)
            print("verificacion: %s" % ("todo al dia" if not quedan
                                        else "AUN quedan %d sin actualizar" % len(quedan)))
        else:
            print("\n(simulacion: no se guardo nada. Corré con --aplicar)")
    b.close()
