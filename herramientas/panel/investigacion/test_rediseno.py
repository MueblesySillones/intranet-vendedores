# -*- coding: utf-8 -*-
"""Prueba la TANDA A del rediseño: que el panel diga en que estado esta.
No guarda ni publica nada (se anulan persistModulos y la publicacion real)."""
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

PORT = 8188
MODULOS_JS = os.path.join(ps.INTRANET, "modulos.js")
ok, fallos = 0, []


def check(n, c, extra=""):
    global ok
    if c:
        ok += 1
        print("  OK   %s %s" % (n, extra))
    else:
        fallos.append(n)
        print("  FALLA %s %s" % (n, extra))


def lum(hexs):
    h = hexs.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    def canal(v):
        v = int(v, 16) / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = canal(h[0:2]), canal(h[2:4]), canal(h[4:6])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


antes = hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest()
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), ps.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

print("=" * 70)
print("PRUEBA DEL REDISEÑO — TANDA A")
print("=" * 70)

with sync_playwright() as pw:
    nav = pw.chromium.launch()
    pag = nav.new_page(viewport={"width": 1366, "height": 768})
    errores = []
    pag.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: errores.append(str(e)))
    pag.goto("http://127.0.0.1:%d" % PORT, wait_until="networkidle")
    pag.wait_for_selector(".mod-card", timeout=20000)
    pag.evaluate("""() => { window.persistModulos = async () => ({ok:true}); }""")

    print("\n[1] Legibilidad")
    ink3 = pag.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--ink3').trim()")
    bg = pag.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
    c = contraste(ink3, bg)
    check("el texto de ayuda es legible sobre el fondo", c >= 4.5, "%s sobre %s = %.2f:1" % (ink3, bg, c))
    check("el enlace del Kit ya no es casi invisible",
          float(pag.evaluate("() => getComputedStyle(document.querySelector('#btnKit')).opacity")) >= 0.95)
    kc = pag.evaluate("""() => getComputedStyle(document.querySelector('#btnKit')).color""")
    check("...y usa el gris legible", "110, 105, 96" in kc, kc)

    print("\n[2] El panel dice que falta publicar")
    pag.evaluate("() => { editados.clear(); guardarEditados(); pintarModulos(); }")
    pag.wait_for_timeout(150)
    check("sin cambios dice 'Todo publicado'",
          "Todo publicado" in pag.text_content("#btnPublicar"), pag.text_content("#btnPublicar"))
    check("...y se ve en verde (btn-done)",
          pag.evaluate("() => document.querySelector('#btnPublicar').classList.contains('btn-done')"))
    check("nunca se deshabilita (republicar es inofensivo)",
          pag.evaluate("() => !document.querySelector('#btnPublicar').disabled"))

    pag.evaluate("() => { marcarEditado(MODULOS[0].key); pintarModulos(); }")
    pag.wait_for_timeout(150)
    check("con 1 cambio dice 'Publicar 1 cambio'",
          pag.text_content("#btnPublicar").strip() == "Publicar 1 cambio", pag.text_content("#btnPublicar"))
    pag.evaluate("() => { marcarEditado(MODULOS[1].key); pintarModulos(); }")
    pag.wait_for_timeout(150)
    check("con 2 dice 'Publicar 2 cambios'",
          pag.text_content("#btnPublicar").strip() == "Publicar 2 cambios", pag.text_content("#btnPublicar"))
    check("...y vuelve al color de accion",
          pag.evaluate("() => document.querySelector('#btnPublicar').classList.contains('btn-pub')"))

    print("\n[3] Las chapas de los modulos")
    check("ya no existe la chapa 'Sistema'",
          pag.evaluate("() => !document.querySelector('.badge.sys')"))
    check("aparece 'Sin publicar' en los editados",
          pag.evaluate("() => document.querySelectorAll('.badge.pend').length") == 2,
          "%d" % pag.evaluate("() => document.querySelectorAll('.badge.pend').length"))
    check("y es la unica chapa con color de accion",
          pag.evaluate("""() => {
            const b = document.querySelector('.badge.pend');
            const a = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
            const bg = getComputedStyle(b).backgroundColor;
            return bg === 'rgb(124, 106, 85)';
          }"""))

    print("\n[4] Un modulo oculto se lee como decision, no como roto")
    pag.evaluate("() => { MODULOS[0].hidden = true; pintarModulos(); }")
    pag.wait_for_timeout(150)
    est = pag.evaluate("""() => {
        const c = document.querySelector('.mod-card.hidden-mod');
        const s = getComputedStyle(c);
        return {op: s.opacity, borde: s.borderStyle,
                titulo: getComputedStyle(c.querySelector('.mod-t')).color};
    }""")
    check("ya no se atenua la tarjeta entera", float(est["op"]) >= 0.99, "opacity=%s" % est["op"])
    check("se marca con borde punteado", est["borde"] == "dashed", est["borde"])
    check("el titulo sigue legible", est["titulo"] != "rgba(0, 0, 0, 0)", est["titulo"])
    check("la chapa explica que pasa",
          "No se ve en el menú" in pag.text_content(".badge.hid"))
    pag.evaluate("() => { MODULOS[0].hidden = false; pintarModulos(); }")

    print("\n[5] Densidad: 9 modulos en 1366x768")
    pag.wait_for_timeout(200)
    r = pag.evaluate("""() => {
        const cs = [...document.querySelectorAll('.mod-card')];
        const ult = cs[cs.length-1].getBoundingClientRect();
        return {n: cs.length, fin: Math.round(ult.bottom), alto: window.innerHeight};
    }""")
    check("entran todos los modulos sin scrollear",
          r["fin"] <= r["alto"], "%d modulos, el ultimo termina en %dpx de %d" % (r["n"], r["fin"], r["alto"]))
    check("el titulo dice cuantos son",
          ("(%d)" % r["n"]) in pag.text_content("#viewModulos .main-head h2"),
          pag.text_content("#viewModulos .main-head h2"))

    print("\n[6] Agregar modulo al final de la lista")
    check("hay un boton punteado que cierra la lista",
          pag.query_selector("#btnAddModulo2") is not None)
    check("el de arriba dejo de competir con Publicar",
          not pag.evaluate("() => document.querySelector('#btnAddModulo').classList.contains('active')"))
    pag.click("#btnAddModulo2")
    pag.wait_for_timeout(400)
    check("y abre el editor de un modulo nuevo",
          pag.evaluate("() => !document.getElementById('viewDetalle').hidden && detNew === true"))
    # BUG REPORTADO: en un modulo nuevo los 3 items del menu estan ocultos, asi que
    # "⋯ Más" abria una cajita blanca VACIA
    check("en un modulo nuevo el boton '⋯ Más' no se ofrece vacio",
          pag.evaluate("() => document.querySelector('.ebar-more').hidden === true"))
    pag.evaluate("() => { $('#detDelete').hidden = false; $('#detHide').hidden = false; actualizarMenuMas(); }")
    pag.wait_for_timeout(150)
    check("...y vuelve a aparecer cuando hay algo adentro",
          pag.evaluate("() => document.querySelector('.ebar-more').hidden === false"))
    pag.click("#detMore")
    pag.wait_for_timeout(200)
    check("y ahi si muestra opciones de verdad",
          pag.evaluate("""() => { const m = document.getElementById('detMoreMenu');
              return !m.hidden && [...m.children].filter(c => !c.hidden).length >= 2; }"""))
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(300)

    print("\n[7] Publicar pregunta con el cuadro del panel, no con el de Windows")
    pag.evaluate("() => { window.__nativo = false; window.confirm = () => { window.__nativo = true; return false; }; }")
    pag.click("#btnPublicar")
    pag.wait_for_timeout(400)
    check("NO usa el cuadro nativo del navegador",
          pag.evaluate("() => window.__nativo === false"))
    check("abre el modal del panel",
          pag.evaluate("() => !document.getElementById('confirmModal').hidden"))
    msg = pag.text_content("#confirmMsg")
    check("dice QUE se va a publicar", "Se van a publicar" in msg, msg[:60].replace("\n", " / "))
    check("lista los modulos editados", msg.count("·") == 2, "%d modulos" % msg.count("·"))
    check("aclara cuando lo ven los vendedores", "30 segundos" in msg)
    check("el boton de confirmar NO es rojo (no destruye nada)",
          pag.evaluate("() => document.querySelector('#confirmYes').classList.contains('active')"))
    pag.click("#confirmNo")
    pag.wait_for_timeout(300)
    check("cancelar cierra sin publicar",
          pag.evaluate("() => document.getElementById('confirmModal').hidden"))

    print("\n[8] Foco visible con teclado")
    check("hay reglas de :focus-visible",
          pag.evaluate("""() => [...document.styleSheets].some(s => {
              try { return [...s.cssRules].some(r => (r.selectorText||'').includes('focus-visible')); }
              catch(e){ return false; }
          })"""))
    check("el token de foco existe",
          pag.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--foco').trim()") != "")

    print("\n[9] Deshacer apagado explica por que")
    pag.evaluate("() => { openDetalle(0); }")
    pag.wait_for_timeout(600)
    u = pag.evaluate("""() => { const b = document.querySelector('#detUndo');
        return {dis: b.disabled, tit: b.title, cur: getComputedStyle(b).cursor}; }""")
    check("arranca deshabilitado", u["dis"] is True)
    check("y dice por que", "Nada para deshacer" in (u["tit"] or ""), u["tit"])
    check("con cursor de 'no se puede'", u["cur"] == "not-allowed", u["cur"])
    pag.evaluate("() => mostrarDetalle(false)")
    pag.wait_for_timeout(300)

    print("\n[10] TANDA B — la paleta de bloques")
    i = pag.evaluate("() => MODULOS.findIndex(m => m.content && m.content.tipo === 'coleccion')")
    pag.evaluate("(i) => openDetalle(i)", i)
    pag.wait_for_selector(".col-item", timeout=20000)
    pag.evaluate("() => abrirDoc(0)")
    pag.wait_for_timeout(500)

    pag.evaluate("() => document.querySelectorAll('#gbAdd details').forEach(d => d.open = true)")
    pag.wait_for_timeout(150)
    check("estan todos los bloques",
          pag.evaluate("() => document.querySelectorAll('#gbAdd .gb-tipo').length") >= 20,
          "%d bloques a la vista" % pag.evaluate("() => document.querySelectorAll('#gbAdd .gb-tipo').length"))
    # los grupos volvieron a ser desplegables (25 bloques a la vista era mucho scroll)
    check("los grupos son desplegables",
          pag.evaluate("() => document.querySelectorAll('#gbAdd details.gb-grupo').length") >= 5)
    check("cada bloque muestra su forma (miniatura)",
          pag.evaluate("() => document.querySelectorAll('#gbAdd .gb-tipo svg.gb-mini').length") ==
          pag.evaluate("() => document.querySelectorAll('#gbAdd .gb-tipo').length"))
    check("los grupos hablan en criollo",
          "Fotos, videos y archivos" in pag.text_content("#gbAdd"),
          [t.strip() for t in pag.evaluate("() => [...document.querySelectorAll('.gb-grupo-t')].map(n=>n.textContent)")][:3].__str__())

    print("\n[11] Buscador de bloques con sinonimos")
    for palabra, espera in (("excel", "Tabla"), ("foto", "Imagen"),
                            ("whatsapp", "Chat"), ("descargas", "Placas"),
                            ("ranking", "Podio")):
        pag.fill("#gbBuscar", palabra)
        pag.wait_for_timeout(120)
        vis = pag.evaluate("() => [...document.querySelectorAll('#gbAdd .gb-tipo')].map(b=>b.textContent.trim())")
        check("buscar '%s' encuentra %s" % (palabra, espera),
              any(espera.lower() in v.lower() for v in vis), str(vis[:3]))
    pag.fill("#gbBuscar", "xyzqw")
    pag.wait_for_timeout(120)
    check("sin resultados lo dice y sugiere",
          "Ningún bloque se llama así" in pag.text_content("#gbAdd"))
    pag.fill("#gbBuscar", "excel")
    pag.wait_for_timeout(120)
    n0 = pag.evaluate("() => BLOQUES.length")
    pag.press("#gbBuscar", "Enter")
    pag.wait_for_timeout(300)
    check("Enter inserta el primer resultado",
          pag.evaluate("() => BLOQUES.length") == n0 + 1 and
          pag.evaluate("() => BLOQUES[SEL].t") == "tabla", pag.evaluate("() => BLOQUES[SEL].t"))
    check("...y limpia el buscador", pag.input_value("#gbBuscar") == "")

    print("\n[12] Los dos paneles se turnan")
    # al insertar se pasa DERECHO a los ajustes del bloque nuevo
    check("tras insertar se abren sus ajustes",
          pag.evaluate("""() => document.querySelector('.gb-pane[data-pane="ajustes"]').hidden === false"""))
    check("y el titulo dice cual es",
          "Ajustes de:" in (pag.text_content("#gbInspTitle") or ""))
    pag.evaluate("() => selectBlock(0)")
    pag.wait_for_timeout(250)
    check("tocar un bloque del documento abre Ajustes",
          pag.evaluate("""() => document.querySelector('.gb-pane[data-pane="ajustes"]').hidden === false"""))
    check("y se apaga el aviso",
          pag.evaluate("() => !document.querySelector('#gbTabAjustes').classList.contains('avisa')"))
    check("el titulo dice QUE bloque es",
          "Ajustes de:" in pag.text_content("#gbInspTitle"), pag.text_content("#gbInspTitle"))
    pag.click('#gbPanes .seg-b[data-pane="agregar"]')
    pag.wait_for_timeout(200)
    check("se puede volver a la paleta a mano",
          pag.evaluate("""() => document.querySelector('.gb-pane[data-pane="agregar"]').hidden === false"""))

    print("\n[13b] TANDA B — un solo vocabulario en el inspector")
    pag.evaluate("""() => {
      BLOQUES.length = 0;
      BLOQUES.push({t:'tabla', orden:true, buscar:false,
                    cols:[{h:'A',num:false},{h:'B',num:true}],
                    filas:[{celdas:['',''],destaque:''}]});
      renderCanvas(); selectBlock(0);
    }""")
    pag.wait_for_timeout(250)
    check("la ayuda de 'donde se escribe' aparece arriba de todo",
          pag.evaluate("""() => { const n = document.querySelector('#gbInspector .insp-ayuda');
              return !!n && n === document.querySelector('#gbInspector > *:nth-child(1)'); }"""))
    check("dice donde se escribe de verdad",
          "en la tabla" in pag.text_content("#gbInspector .insp-ayuda"))
    check("y aparece UNA sola vez (no duplicada abajo)",
          pag.evaluate("() => document.querySelectorAll('#gbInspector .insp-ayuda').length") == 1)
    check("los checkboxes son todos el mismo componente",
          pag.evaluate("() => document.querySelectorAll('#gbInspector .insp-check').length") >= 2)
    check("un checkbox prendido SE NOTA en toda la fila",
          pag.evaluate("""() => { const l = [...document.querySelectorAll('#gbInspector .insp-check')]
                                    .find(x => x.querySelector('input').checked);
              return !!l && l.classList.contains('on'); }"""))
    check("y uno apagado no",
          pag.evaluate("""() => { const l = [...document.querySelectorAll('#gbInspector .insp-check')]
                                    .find(x => !x.querySelector('input').checked);
              return !!l && !l.classList.contains('on'); }"""))
    check("el boton de agregar es punteado y de ancho completo",
          pag.evaluate("""() => { const b = document.querySelector('#gbInspector .insp-add');
              return !!b && getComputedStyle(b).borderStyle === 'dashed'; }"""))
    check("la cruz de quitar es GRIS, no roja permanente",
          pag.evaluate("""() => { const b = document.querySelector('#gbInspector .insp-del');
              return !!b && getComputedStyle(b).color === 'rgb(110, 105, 96)'; }"""),
          pag.evaluate("""() => { const b = document.querySelector('#gbInspector .insp-del');
              return b ? getComputedStyle(b).color : 'sin cruz'; }"""))

    print("\n[13c] La trampa: no dar vuelta lo ya publicado")
    # un PDF guardado hace meses NO tiene la clave `descargable` (era "true por omision")
    pag.evaluate("""() => {
      BLOQUES.length = 0;
      BLOQUES.push({t:'pdf', src:'assets/_modulos/x.pdf', nombre:'Catalogo', modo:'tarjeta'});
      renderCanvas(); selectBlock(0);
    }""")
    pag.wait_for_timeout(250)
    check("un PDF viejo sigue con su boton de descarga PRENDIDO",
          pag.evaluate("() => BLOQUES[0].descargable === true"),
          "descargable=%s" % pag.evaluate("() => String(BLOQUES[0].descargable)"))
    check("...y el checkbox lo muestra tildado",
          pag.evaluate("""() => { const l = [...document.querySelectorAll('#gbInspector .insp-check')]
              .find(x => x.textContent.includes('Descargar')); return !!l && l.classList.contains('on'); }"""))
    check("el HTML publicado sigue trayendo el boton",
          "dl-btn" in pag.evaluate("() => bloqueHTML(BLOQUES[0])"))

    pag.evaluate("""() => {
      BLOQUES.length = 0;
      BLOQUES.push({t:'situacion', tag:'Situación', tagColor:'--c-warn', titulo:'X',
                    resp:'Respuesta recomendada', respIcono:'arrowDR', respColor:'--c-success',
                    mensajes:[{lado:'out', html:'hola'}]});
      renderCanvas(); selectBlock(0);
    }""")
    pag.wait_for_timeout(250)
    check("una Situación vieja conserva su 'Respuesta recomendada'",
          pag.evaluate("() => BLOQUES[0].conResp === true"),
          "conResp=%s" % pag.evaluate("() => String(BLOQUES[0].conResp)"))
    check("...y sigue saliendo en el HTML publicado",
          "sit-arrow" in pag.evaluate("() => bloqueHTML(BLOQUES[0])"))

    print("\n[13d] El boton + entre bloques")
    pag.evaluate("""() => {
      BLOQUES.length = 0;
      ['Uno','Dos','Tres'].forEach(t => BLOQUES.push({t:'parrafo', html:t}));
      SEL = 0; renderCanvas(); renderInspector();
    }""")
    pag.wait_for_timeout(250)
    check("arranca escondido", pag.evaluate("() => document.querySelector('.gb-mas').hidden"))

    # poner el mouse en el borde de abajo del PRIMER bloque
    caja = pag.evaluate("""() => { const r = document.querySelectorAll('.gb-block')[0].getBoundingClientRect();
        return {x: r.left + r.width/2, y: r.bottom}; }""")
    pag.mouse.move(caja["x"], caja["y"])
    pag.wait_for_timeout(200)
    check("aparece al acercarse al hueco",
          pag.evaluate("() => !document.querySelector('.gb-mas').hidden"))
    check("y queda en ese hueco, no en otro lado",
          pag.evaluate("""(y) => {
              const r = document.querySelector('.gb-mas').getBoundingClientRect();
              return Math.abs((r.top + r.height/2) - y) < 18;
          }""", caja["y"]))

    n0 = pag.evaluate("() => BLOQUES.length")
    pag.click(".gb-mas")
    pag.wait_for_timeout(250)
    check("al tocarlo deja lista la paleta",
          pag.evaluate("""() => document.querySelector('.gb-pane[data-pane="agregar"]').hidden === false"""))
    check("con el foco puesto en el buscador",
          pag.evaluate("() => document.activeElement.id === 'gbBuscar'"))
    check("y apunta al bloque de arriba del hueco",
          pag.evaluate("() => SEL") == 0, "SEL=%s" % pag.evaluate("() => SEL"))

    pag.evaluate("() => insertBloque('separador')")
    pag.wait_for_timeout(250)
    check("el bloque nuevo cae EN EL MEDIO, no al final",
          pag.evaluate("() => BLOQUES.length") == n0 + 1 and
          pag.evaluate("() => BLOQUES[1].t") == "separador",
          pag.evaluate("() => BLOQUES.map(b=>b.t).join(',')"))

    pag.mouse.move(5, 5)
    pag.wait_for_timeout(200)
    check("se esconde al salir del lienzo",
          pag.evaluate("() => document.querySelector('.gb-mas').hidden"))
    check("no ensucia el HTML que se publica",
          "gb-mas" not in pag.evaluate("() => bloquesHTML(BLOQUES, false)"))

    print("\n[13] El vacio dice la verdad")
    pag.evaluate("() => { BLOQUES.length = 0; SEL = null; renderCanvas(); renderInspector(); }")
    pag.wait_for_timeout(200)
    check("sin bloques invita a agregar uno",
          "Todavía no hay bloques" in pag.text_content("#gbInspector"),
          pag.text_content("#gbInspector")[:50])

    check("cero errores de consola", not errores, "; ".join(errores[:3]))
    nav.close()

httpd.shutdown()
check("modulos.js NO se toco", hashlib.sha256(open(MODULOS_JS, 'rb').read()).hexdigest() == antes)

print("\n" + "=" * 70)
print("%d checks OK, %d fallas" % (ok, len(fallos)))
if fallos:
    print("FALLARON: " + ", ".join(fallos))
print("=" * 70)
sys.exit(1 if fallos else 0)
