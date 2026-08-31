# -*- coding: utf-8 -*-
"""Arnés compartido de la suite QA del panel + intranet.

Todo lo que los tests tienen en común vive acá: configuración por variables
de entorno, el contexto de navegador con la publicación BLOQUEADA, axe-core,
métricas de página y los dos servidores (panel desde el código fuente e
intranet estática) pensados para correr como procesos hijos.

Variables de entorno (todas opcionales, con default):
  PANEL_URL     URL del panel            (default http://127.0.0.1:8143/)
  INTRA_URL     URL de la intranet       (default http://localhost:8813/intranet/index.html)
  QA_PROYECTO   raíz del proyecto a testear; de acá sale intranet/ para el
                sandbox (default: dos carpetas arriba de qa/, o sea el repo real)
  PANEL_SRC     carpeta con panel_server.py y web2/ (default QA_PROYECTO/herramientas/panel;
                apuntala a un snapshot para probar sin molestar a nadie)
  QA_SALIDA     carpeta de resultados    (default qa/salida)
  QA_SANDBOX    carpeta del sandbox      (default QA_SALIDA/sandbox)
  QA_MODULO     texto para elegir el módulo que abre el editor (default EMBALAJE)
  MODULOS_JS    ruta del modulos.js que es "la verdad del disco" para t2
                (default QA_SANDBOX/proyecto/intranet/modulos.js)
  QA_VISUAL_TOL tolerancia de t4 en % de píxeles distintos (default 0.5)

Por qué el bloqueo de publicación NO es opcional: la suite clickea todo, y un
"Publicar" de verdad subiría publicaciones de prueba al sitio que ven los
vendedores. Todos los contextos del panel salen de contexto_seguro().
"""
import io
import json
import os
import sys
import time
import urllib.request
from urllib.parse import urlparse

# En Windows, la consola o el pipe pueden venir en cp1252, y los textos de la
# suite usan flechas (→) y tildes: sin esto un print() adentro de un flujo
# tira UnicodeEncodeError y el flujo entero figura como EXCEPCION (pasó en la
# corrida de validación del 29-ago). UTF-8 siempre, con reemplazo por las dudas.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

QA_DIR = os.path.dirname(os.path.abspath(__file__))

# --- configuración por entorno (los nombres cortos son a propósito: se usan mucho) ---
PANEL_URL = os.environ.get("PANEL_URL") or "http://127.0.0.1:8143/"
INTRA_URL = os.environ.get("INTRA_URL") or "http://localhost:8813/intranet/index.html"
PROYECTO = os.environ.get("QA_PROYECTO") or os.path.dirname(os.path.dirname(QA_DIR))
PANEL_SRC = os.environ.get("PANEL_SRC") or os.path.join(PROYECTO, "herramientas", "panel")
SALIDA = os.environ.get("QA_SALIDA") or os.path.join(QA_DIR, "salida")
SANDBOX = os.environ.get("QA_SANDBOX") or os.path.join(SALIDA, "sandbox")
MODULO_EDITOR = os.environ.get("QA_MODULO") or "EMBALAJE"
MODULOS_JS = os.environ.get("MODULOS_JS") or os.path.join(SANDBOX, "proyecto", "intranet", "modulos.js")

FIXTURES = os.path.join(QA_DIR, "fixtures")
BASELINE = os.path.join(QA_DIR, "baseline")
AXE = os.path.join(QA_DIR, "axe.min.js")
SHOTS = os.path.join(SALIDA, "screenshots")
EVID = os.path.join(SALIDA, "evidencia")
DIFFS = os.path.join(SALIDA, "diffs")
LOGS = os.path.join(SALIDA, "logs")


def preparar_salida():
    for d in (SALIDA, SHOTS, EVID, DIFFS, LOGS):
        os.makedirs(d, exist_ok=True)


def puerto_de(url):
    """Saca el puerto de una URL (para levantar el servidor que la atienda)."""
    p = urlparse(url)
    return p.port or (443 if p.scheme == "https" else 80)


def exportar_config():
    """Fija la config resuelta en os.environ, para que los procesos hijos
    (tests y servidores) vean EXACTAMENTE lo mismo que el orquestador,
    aunque el default se haya calculado acá."""
    os.environ["PANEL_URL"] = PANEL_URL
    os.environ["INTRA_URL"] = INTRA_URL
    os.environ["QA_PROYECTO"] = PROYECTO
    os.environ["PANEL_SRC"] = PANEL_SRC
    os.environ["QA_SALIDA"] = SALIDA
    os.environ["QA_SANDBOX"] = SANDBOX
    os.environ["QA_MODULO"] = MODULO_EDITOR
    os.environ["MODULOS_JS"] = MODULOS_JS


# ---------------------------------------------------------------------------
# navegador
# ---------------------------------------------------------------------------

def contexto_seguro(browser, **kw):
    """Contexto con la publicación al sitio BLOQUEADA en el navegador.

    La suite clickea todo lo que ve; si un flujo llega a un 'Publicar' de
    verdad, sin esto subiría basura de prueba a producción. Se intercepta la
    ruta y se responde ok:true para que la UI siga su curso normal."""
    ctx = browser.new_context(**kw)

    def bloquear(route):
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"ok": True, "log": "(bloqueado por la suite QA)"}))

    for ruta in ("**/api/publicar", "**/api/enviar", "**/api/shutdown",
                 "**/api/set-publish-token", "**/api/update-apply"):
        ctx.route(ruta, bloquear)
    return ctx


def ir_seccion(pg, sec, espera=1800):
    """Click en la barra de navegación del panel (data-sec) y espera al render."""
    pg.click('.nav-s[data-sec="%s"]' % sec)
    pg.wait_for_timeout(espera)


def abrir_editor(pg):
    """Entra al editor de bloques del módulo QA_MODULO. Si ese texto no está
    (contenido distinto en otra máquina), avisa con una excepción clara."""
    ir_seccion(pg, "modulos")
    tarjeta = pg.locator("#viewModulos").get_by_text(MODULO_EDITOR, exact=False)
    if not tarjeta.count():
        raise RuntimeError("no hay módulo con texto %r (ajustar QA_MODULO)" % MODULO_EDITOR)
    tarjeta.first.click()
    pg.wait_for_timeout(2500)


def abrir_datos_reporte(pg, espera=8000):
    """Abre el primer reporte de Datos (Derivaciones). La espera es larga
    porque el análisis lee la planilla (del caché en el sandbox)."""
    ir_seccion(pg, "datos")
    pg.locator("#datosRaiz").get_by_text("Derivaciones", exact=False).first.click()
    pg.wait_for_timeout(espera)


def toast(pg):
    return pg.evaluate("(()=>{const t=document.querySelector('#toast');"
                       "return t&&!t.hidden?t.textContent.trim():null})()")


def correr_axe(pg):
    """Inyecta axe-core local y devuelve las violaciones WCAG A/AA resumidas."""
    pg.add_script_tag(path=AXE)
    return pg.evaluate("""async () => {
        const res = await axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
            resultTypes: ['violations'] });
        return res.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help,
            nodes: v.nodes.length,
            ejemplo: (v.nodes[0] && v.nodes[0].target && String(v.nodes[0].target[0]).slice(0, 90)) || '',
            detalle: (v.nodes[0] && v.nodes[0].failureSummary || '').slice(0, 220) })); }""")


def metricas_pagina(pg):
    """Desborde horizontal, áreas táctiles chicas e imágenes rotas de la vista actual."""
    return pg.evaluate("""() => {
      const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
      const clicks = [...document.querySelectorAll(
        'button, a[href], input:not([type=hidden]), select, textarea, [onclick], [role=button], .seg-b, label.insp-check')]
        .filter(vis);
      const chicos40 = [], chicos32 = [];
      for (const el of clicks) {
        const r = el.getBoundingClientRect();
        const t = { sel: (el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                          (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).slice(0,2).join('.') : '')).slice(0, 60),
                    txt: (el.textContent || el.title || el.placeholder || '').trim().slice(0, 28),
                    w: Math.round(r.width), h: Math.round(r.height) };
        if (r.width < 40 || r.height < 40) chicos40.push(t);
        if (r.width < 32 || r.height < 32) chicos32.push(t);
      }
      const rotas = [...document.images].filter(i => i.src && i.id !== 'lbimg' && i.complete && i.naturalWidth === 0).length;
      return { desborde: document.documentElement.scrollWidth - window.innerWidth,
               clickeables: clicks.length, menores40: chicos40.length, menores32: chicos32.length,
               peores: chicos32.slice(0, 12), imgs_rotas: rotas };
    }""")


def inventario(pg, pantalla):
    """Censo de controles visibles/invisibles (para detectar controles perdidos)."""
    return pg.evaluate("""(pantalla) => {
      const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'; };
      return [...document.querySelectorAll(
        'button, a[href], input:not([type=hidden]), select, textarea, [onclick], [role=button], .seg-b, label.insp-check, [contenteditable]')]
        .map(el => ({ pantalla,
          el: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
          clase: (typeof el.className === 'string' ? el.className.trim().split(/\\s+/).slice(0, 3).join(' ') : ''),
          texto: (el.textContent || el.value || '').trim().slice(0, 40),
          titulo: (el.title || el.placeholder || '').slice(0, 50),
          deshabilitado: !!el.disabled, visible: vis(el) }));
    }""", pantalla)


def guardar(nombre, datos):
    """Evidencia en JSON, siempre en la misma carpeta para poder compararla."""
    preparar_salida()
    with io.open(os.path.join(EVID, nombre), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------------
# axe: violaciones conocidas vs nuevas
# ---------------------------------------------------------------------------
# La regla del umbral es "violaciones NUEVAS": lo ya relevado en la auditoría
# no frena la suite (se arregla por su carril), pero un id de violación que
# aparece donde antes no estaba sí es regresión y falla.

def cargar_conocidas(nombre):
    """Lee fixtures/<nombre> -> {pantalla: [ids]}. Si no existe devuelve None
    (y el test trata TODA violación como nueva, avisando cómo aceptarlas)."""
    p = os.path.join(FIXTURES, nombre)
    if not os.path.isfile(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


def guardar_conocidas(nombre, axe_por_pantalla):
    """--aceptar-axe: fija el estado actual como 'conocido'."""
    datos = {pant: sorted({v["id"] for v in viols if v.get("id")})
             for pant, viols in axe_por_pantalla.items()}
    with io.open(os.path.join(FIXTURES, nombre), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    return datos


def axe_nuevas(axe_por_pantalla, conocidas):
    """[(pantalla, id, impact)] de violaciones que no figuran como conocidas."""
    nuevas = []
    for pant, viols in axe_por_pantalla.items():
        ya = set((conocidas or {}).get(pant, []))
        for v in viols:
            if v.get("id") and v["id"] not in ya:
                nuevas.append((pant, v["id"], v.get("impact")))
    return nuevas


# ---------------------------------------------------------------------------
# reporte homogéneo: ok / aviso / falla con contadores y exit code
# ---------------------------------------------------------------------------

class Reporte(object):
    """El mismo estilo ok/fail de los scripts de la auditoría, con memoria:
    al cerrar escribe salida/evidencia/<nombre>-resumen.json y devuelve el
    exit code (0 limpio, 1 con fallas) para que correr_todo.py sume."""

    def __init__(self, nombre):
        self.nombre = nombre
        self.oks, self.avisos, self.fallas = [], [], []

    def ok(self, titulo, extra=""):
        self.oks.append({"titulo": titulo, "extra": str(extra)[:160]})
        print("  OK  %s%s" % (titulo, ("  " + str(extra)[:90]) if extra else ""))

    def aviso(self, titulo, extra=""):
        self.avisos.append({"titulo": titulo, "extra": str(extra)[:160]})
        print("  !!  %s%s" % (titulo, ("  " + str(extra)[:90]) if extra else ""))

    def falla(self, titulo, extra=""):
        self.fallas.append({"titulo": titulo, "extra": str(extra)[:160]})
        print("  XX  %s%s" % (titulo, ("  " + str(extra)[:90]) if extra else ""))

    def check(self, titulo, cond, extra=""):
        (self.ok if cond else self.falla)(titulo, extra)
        return bool(cond)

    def cerrar(self, extra=None):
        print("\n== %s: %d ok, %d avisos, %d fallas ==" %
              (self.nombre, len(self.oks), len(self.avisos), len(self.fallas)))
        for f in self.fallas:
            print("   XX %s  %s" % (f["titulo"], f["extra"]))
        resumen = {"nombre": self.nombre, "ok": len(self.oks), "avisos": len(self.avisos),
                   "fallas": len(self.fallas), "detalle_fallas": self.fallas,
                   "detalle_avisos": self.avisos}
        if extra:
            resumen.update(extra)
        guardar(self.nombre + "-resumen.json", resumen)
        return 1 if self.fallas else 0


# ---------------------------------------------------------------------------
# servidores (pensados para correr como procesos hijos de correr_todo.py)
# ---------------------------------------------------------------------------

def esperar_url(url, segundos=40):
    """Espera a que la URL conteste (el panel tarda en importar y analizar)."""
    fin = time.time() + segundos
    ultimo = ""
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return True
        except Exception as e:  # noqa: BLE001 - reintentamos hasta el timeout
            ultimo = str(e)[:80]
        time.sleep(0.5)
    print("!! %s no contesta (%s)" % (url, ultimo))
    return False


def servir_panel():
    """Levanta el panel DESDE EL CÓDIGO FUENTE (PANEL_SRC) contra el sandbox.

    Bloqueante: correr como `python arnes.py servir-panel` en un proceso hijo.
    El orden importa: primero el entorno MYS_*, después importar panel_server
    (lee todo al importar). setdefault deja que quien llama apunte a otro
    proyecto/estado sin tocar este archivo."""
    os.environ.setdefault("MYS_PROYECTO", os.path.join(SANDBOX, "proyecto"))
    os.environ.setdefault("MYS_PANEL_STATE", os.path.join(SANDBOX, "estado"))
    os.environ.setdefault("MYS_PANEL_PORT", str(puerto_de(PANEL_URL)))
    os.environ.setdefault("MYS_PANEL_WEB", "web2")

    # nada de abrir Edge en plena corrida automática
    import webbrowser
    webbrowser.open = lambda *a, **k: True

    sys.path.insert(0, PANEL_SRC)
    import panel_server  # noqa: E402  (necesita el entorno ya puesto)
    from http.server import ThreadingHTTPServer

    srv = ThreadingHTTPServer((panel_server.HOST, panel_server.PORT), panel_server.Handler)
    print("panel QA en http://%s:%d/  (web=%s, proyecto=%s, estado=%s)" % (
        panel_server.HOST, panel_server.PORT, panel_server._web_pedido,
        os.environ["MYS_PROYECTO"], panel_server.STATE_DIR), flush=True)
    srv.serve_forever()


def servir_intranet():
    """Sirve el sandbox como sitio estático para la vista del vendedor.

    Cache-Control: no-store porque los tests editan modulos.js entre vistas y
    un caché del navegador mostraría contenido viejo."""
    import functools
    import http.server
    import socketserver

    raiz = os.environ.get("INTRA_RAIZ") or os.path.join(SANDBOX, "proyecto")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            http.server.SimpleHTTPRequestHandler.end_headers(self)

    puerto = puerto_de(INTRA_URL)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(
        ("127.0.0.1", puerto), functools.partial(Quiet, directory=raiz))
    srv.daemon_threads = True
    print("intranet QA en http://localhost:%d/intranet/  (raíz=%s)" % (puerto, raiz), flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "servir-panel":
        servir_panel()
    elif orden == "servir-intranet":
        servir_intranet()
    else:
        print("uso: python arnes.py servir-panel | servir-intranet")
        print("(los tests se corren con t1_crawl.py ... t4_visual.py o correr_todo.py)")
        sys.exit(2)
