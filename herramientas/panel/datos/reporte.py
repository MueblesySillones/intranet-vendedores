# -*- coding: utf-8 -*-
"""El reporte para el equipo de marketing, en Word y en PDF.

DE DONDE SALE CADA FORMATO, Y POR QUE

  · WORD (.docx) — se escribe a mano con `zipfile` y XML. Un .docx no es un
    formato binario magico: es un ZIP con unos XML adentro. Asi no hace falta
    python-docx, que el panel no puede sumar porque se distribuye como .exe.
    Probado: 18 chequeos de estructura en prueba_docx.py.

  · PDF — lo hace el navegador. El panel es una interfaz web y Chrome ya sabe
    imprimir a PDF, con texto seleccionable y buena tipografia. Una hoja de
    estilos de impresion decente y "Guardar como PDF" dan mejor resultado que
    cualquier libreria, y cuestan cero dependencias. Por eso el reporte se
    arma como HTML pensado para papel, no como pantalla.

QUE LLEVA ADENTRO
Lo que ya calculan las piezas que estan hechas: el analisis de la planilla,
los avisos de lo mal cargado, y las conclusiones. El reporte no calcula nada
nuevo — solo lo ordena para leerlo en papel.

⚠️ NUNCA lleva datos de clientes. Las columnas marcadas `sensible` se nombran
   —para que se sepa que estan— pero no se vuelca ni un valor.
"""
import datetime
import io
import os
import sys
import zipfile
from xml.sax.saxutils import escape

AQUI = os.path.dirname(os.path.abspath(__file__))

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_larga(d=None):
    d = d or datetime.date.today()
    return "%d de %s de %d" % (d.day, MESES[d.month], d.year)


def _fecha_corta(iso):
    """'2025-01-24' -> '24/01/2025'. Si no es ISO, se devuelve como vino."""
    try:
        a, m, d = iso[:10].split("-")
        return "%02d/%02d/%s" % (int(d), int(m), a)
    except (ValueError, AttributeError, TypeError):
        return iso or ""


def _mil(n):
    """1800 -> 1.800, como se escribe acá."""
    return "{:,}".format(int(n)).replace(",", ".")


# ═══════════════════════ el contenido del reporte ═══════════════════════
def armar(an, avisos, lects, titulo="Reporte de derivaciones", fuente="",
          foco=None):
    """Ordena lo que ya se calculo. No calcula nada nuevo.

    `foco` son los nombres de columna que el equipo eligio medir. No filtra:
    ORDENA. Las elegidas van primero, y como abajo se cortan las primeras seis,
    lo elegido es lo que sobrevive al corte. Un reporte que se pidio sobre
    vendedores no puede salir hablando de otra cosa porque esa columna estaba
    antes en la planilla."""
    fcol = next((c for c in an["columnas"] if c["tipo"] == "fecha"), None)
    periodo = ""
    if fcol and fcol.get("desde"):
        # ⚠️ El "hasta" sale del maximo de la columna, y ahi puede haber un año
        # mal tipeado: sin este freno el reporte anunciaba un periodo que
        # terminaba en 2027. Una fecha imposible contamina todo lo que se
        # calcule con el maximo, asi que se topa en hoy y se avisa.
        #
        # ⚠️ `desde` y `hasta` vienen en ISO del analizador —comparables como
        # texto porque en ISO el orden alfabetico ES el cronologico—, y salen
        # de aca escritos como se escriben acá. Antes se mostraban tal como
        # estaban en la planilla y el encabezado decia cosas como
        # "1/02/2026 al 2026-08-28": dos formatos en la misma linea, y ademas
        # mal, porque el minimo se habia sacado ordenando texto.
        hoy_txt = datetime.date.today().isoformat()
        hasta = fcol["hasta"]
        futuro = hasta > hoy_txt
        if futuro:
            hasta = hoy_txt
        periodo = "%s al %s" % (_fecha_corta(fcol["desde"]), _fecha_corta(hasta))
        if futuro:
            periodo += " (hay fechas posteriores, mal cargadas)"

    sensibles = [c["nombre"] for c in an["columnas"] if c["sensible"]]
    # ⚠️ Tambien las de tipo `motivo`. Antes solo entraban las `categoria`, asi
    # que «Producto» —145 formas de escribirlo que el analizador junta en
    # grupos— no aparecia nunca en el reporte, aunque fuera justo lo que se
    # habia pedido medir.
    listas = [c for c in an["columnas"]
              if c["tipo"] in ("categoria", "motivo") and not c["sensible"]]
    if foco:
        elegidas = list(foco)
        listas.sort(key=lambda c: (elegidas.index(c["nombre"])
                                   if c["nombre"] in elegidas else 999))
    graves = [a for a in avisos if a["gravedad"] == "grave"]

    return {
        "titulo": titulo,
        "fuente": fuente,
        "generado": _fecha_larga(),
        "periodo": periodo,
        "filas": an["filas"],
        "columnas": len(an["columnas"]),
        "sensibles": sensibles,
        "lecturas": lects,
        "avisos": avisos,
        "graves": len(graves),
        "cortes": [
            {"nombre": c["nombre"],
             "valores": [(v[0], v[1], 100.0 * v[1] / max(1, c["llenos"]))
                         for v in _valores_de(c)[:8]],
             "llenos": c["llenos"],
             "elegida": bool(foco and c["nombre"] in foco)}
            for c in listas[:6]
        ],
    }


# ═══════════════════════════════ WORD ═══════════════════════════════
def _valores_de(col):
    """[(etiqueta, cuenta), ...] venga de donde venga.

    Una columna `categoria` trae `valores` (el valor tal cual); una `motivo`
    trae `grupos` (las formas de escribir lo mismo, ya juntadas). Los dos se
    dibujan igual, asi que se los devuelve con la misma forma."""
    if col.get("valores"):
        return [(v["valor"], v["cuenta"]) for v in col["valores"]]
    if col.get("grupos"):
        return [(g["etiqueta"], g["cuenta"]) for g in col["grupos"]]
    return []


def _p(texto, estilo=None, negrita=False):
    pr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % estilo if estilo else ""
    rpr = "<w:rPr><w:b/></w:rPr>" if negrita else ""
    return '<w:p>%s<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (
        pr, rpr, escape(str(texto)))


def _tabla(encabezados, filas):
    def celda(txt, negrita=False, ancho=None):
        rpr = "<w:rPr><w:b/></w:rPr>" if negrita else ""
        w = '<w:tcW w:w="%d" w:type="dxa"/>' % ancho if ancho else '<w:tcW w:w="0" w:type="auto"/>'
        return ('<w:tc><w:tcPr>%s</w:tcPr><w:p><w:r>%s'
                '<w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
                % (w, rpr, escape(str(txt))))
    out = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>']
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        out.append('<w:%s w:val="single" w:sz="4" w:color="D9D9D9"/>' % lado)
    out.append("</w:tblBorders></w:tblPr>")
    out.append("<w:tr>" + "".join(celda(h, True) for h in encabezados) + "</w:tr>")
    for f in filas:
        out.append("<w:tr>" + "".join(celda(v) for v in f) + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def a_word(rep, ruta):
    c = [_p(rep["titulo"], "Title")]
    sub = [rep["fuente"], "Período: " + rep["periodo"] if rep["periodo"] else "",
           "%s filas · %d columnas" % (_mil(rep["filas"]), rep["columnas"]),
           "Generado el " + rep["generado"]]
    c.append(_p(" · ".join(x for x in sub if x), "Sub"))

    # Cuando hay algo grave, se dice ANTES de los numeros y no despues.
    if rep["graves"]:
        c.append(_p("Antes de leer los números", "H1"))
        c.append(_p("Hay %d problemas graves en la carga de la planilla. "
                    "Mientras no se arreglen, los números de este reporte "
                    "pueden estar mal. El detalle está al final."
                    % rep["graves"], negrita=True))

    c.append(_p("Lo que dicen los números", "H1"))
    if rep["lecturas"]:
        for l in rep["lecturas"][:12]:
            c.append(_p("• " + l["texto"]))
            f = (l.get("cuenta") or {}).get("formula")
            if f:
                c.append(_p("    " + f, "Chico"))
    else:
        c.append(_p("No hay nada que se pueda afirmar con estos datos."))

    for corte in rep["cortes"]:
        c.append(_p("Por " + corte["nombre"], "H1"))
        c.append(_tabla([corte["nombre"], "Cantidad", "%"],
                        [[v, _mil(n), ("%.1f%%" % p).replace(".", ",")]
                         for v, n, p in corte["valores"]]))
        c.append(_p(""))

    c.append(_p("Lo que hay que revisar en la carga", "H1"))
    if rep["avisos"]:
        c.append(_p("%d cosas, %d de ellas graves. Una grave significa que el "
                    "número de arriba está mal hasta que se arregle."
                    % (len(rep["avisos"]), rep["graves"])))
        c.append(_tabla(["", "Qué pasa", "Por qué importa"],
                        [[a["gravedad"].upper(), a["titulo"], a["detalle"]]
                         for a in rep["avisos"][:14]]))
        c.append(_p(""))
    else:
        c.append(_p("Nada. La planilla está bien cargada."))

    if rep["sensibles"]:
        c.append(_p("Datos que no salen de acá", "H1"))
        c.append(_p("La planilla tiene %d columnas con datos de clientes (%s). "
                    "Este reporte no incluye ni un valor de esas columnas, y esos "
                    "datos tampoco se publican en la intranet de vendedores, que "
                    "es pública y no tiene contraseña."
                    % (len(rep["sensibles"]), ", ".join(rep["sensibles"]))))

    documento = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<w:document %s><w:body>%s'
                 '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                 '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
                 '</w:sectPr></w:body></w:document>' % (W, "".join(c)))

    tipos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
             "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    docrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')

    def estilo(sid, nombre, tam, negrita=False, antes=0, despues=120, color=None):
        return ('<w:style w:type="paragraph" w:styleId="%s"><w:name w:val="%s"/>'
                '<w:pPr><w:spacing w:before="%d" w:after="%d"/></w:pPr>'
                '<w:rPr>%s<w:sz w:val="%d"/>%s</w:rPr></w:style>'
                % (sid, nombre, antes, despues, "<w:b/>" if negrita else "", tam,
                   '<w:color w:val="%s"/>' % color if color else ""))

    estilos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<w:styles %s>%s%s%s%s</w:styles>'
               % (W,
                  estilo("Title", "Title", 40, True, 0, 60),
                  estilo("Sub", "Subtitle", 18, False, 0, 320, "6E6E6E"),
                  estilo("H1", "heading 1", 26, True, 320, 140),
                  estilo("Chico", "Small", 16, False, 0, 120, "6E6E6E")))

    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", docrels)
        z.writestr("word/styles.xml", estilos)
        z.writestr("word/document.xml", documento)
    return ruta


# ══════════════════════════ HTML PARA PAPEL ══════════════════════════
CSS = """
:root{ --bg:#fff; --ink:#111; --ink2:#444; --ink3:#6E6E6E;
       --linea:rgba(0,0,0,.12); --suave:#F0EDE8;
       --grave:#B4231F; --aviso:#9A6A00; }
*{ box-sizing:border-box; }
body{ margin:0; background:#E8E4DF; color:var(--ink);
  font:15px/1.6 "Segoe UI", system-ui, sans-serif; }
/* La hoja es una A4 de verdad: lo que se ve en pantalla es lo que sale
   impreso, sin sorpresas de "se cortó a la mitad". */
.hoja{ width:210mm; min-height:297mm; margin:16px auto; padding:18mm 16mm;
  background:#fff; box-shadow:0 6px 30px rgba(0,0,0,.14); }
h1{ font-size:30px; font-weight:700; letter-spacing:-.6px; margin:0 0 6px; }
.sub{ color:var(--ink3); font-size:12.5px; margin:0 0 4px; }
.regla{ height:2px; background:var(--ink); margin:20px 0 24px; }
h2{ font-size:12px; font-weight:700; letter-spacing:1.8px; text-transform:uppercase;
  color:var(--ink3); margin:30px 0 12px; }
.lect{ border-left:3px solid var(--ink); padding:2px 0 2px 14px; margin:0 0 14px; }
.lect .t{ font-size:16px; line-height:1.45; }
.lect .f{ font-size:11.5px; color:var(--ink3); font-family:ui-monospace,Consolas,monospace;
  margin-top:3px; }
table{ width:100%; border-collapse:collapse; font-size:13px; margin:0 0 18px; }
th{ text-align:left; font-size:10.5px; letter-spacing:1px; text-transform:uppercase;
  color:var(--ink3); border-bottom:2px solid var(--ink); padding:7px 8px; }
td{ padding:7px 8px; border-bottom:1px solid var(--linea); }
td.n{ text-align:right; font-variant-numeric:tabular-nums; }
.barra{ height:6px; background:var(--suave); position:relative; }
.barra i{ position:absolute; inset:0 auto 0 0; background:var(--ink); }
.chapa{ display:inline-block; padding:2px 8px; font-size:10px; font-weight:700;
  letter-spacing:.6px; }
.chapa.grave{ background:#FBEAE9; color:var(--grave); }
.chapa.aviso{ background:#F6EDE2; color:var(--aviso); }
.chapa.dato{ background:var(--suave); color:var(--ink3); }
.alerta{ background:#FBEAE9; border-left:3px solid var(--grave);
  padding:14px 16px; margin:0 0 22px; font-size:13.5px; line-height:1.6;
  color:var(--ink2); }
.alerta b{ color:var(--grave); }
.nota{ background:var(--suave); border-left:3px solid var(--ink);
  padding:14px 16px; font-size:13px; line-height:1.6; color:var(--ink2); }
.pie{ margin-top:26px; padding-top:12px; border-top:1px solid var(--linea);
  font-size:11px; color:var(--ink3); }

/* ── PAPEL ──
   El PDF sale de acá: Chrome imprime esto tal cual. Sin fondo de pantalla,
   sin sombra, y con los cortes de página puestos a mano para que no quede
   un título solo al pie de una hoja. */
@media print{
  body{ background:#fff; }
  .hoja{ width:auto; min-height:0; margin:0; padding:0; box-shadow:none; }
  h2{ break-after:avoid; }
  table, .lect, .nota{ break-inside:avoid; }
  .salto{ break-before:page; }
}
@page{ size:A4; margin:14mm 13mm; }
"""


def a_html(rep, ruta):
    def esc(x):
        return escape(str(x))

    p = []
    p.append('<div class="hoja">')
    p.append("<h1>%s</h1>" % esc(rep["titulo"]))
    if rep["fuente"]:
        p.append('<p class="sub">%s</p>' % esc(rep["fuente"]))
    linea2 = []
    if rep["periodo"]:
        linea2.append("Período " + rep["periodo"])
    linea2.append("%s filas · %d columnas" % (_mil(rep["filas"]), rep["columnas"]))
    linea2.append("Generado el " + rep["generado"])
    p.append('<p class="sub">%s</p>' % esc(" · ".join(linea2)))
    p.append('<div class="regla"></div>')

    # Idem: si los datos estan sucios, se dice arriba. Un reporte que sabe que
    # sus numeros pueden estar mal y lo cuenta al pie es un reporte que engaña.
    if rep["graves"]:
        p.append('<div class="alerta"><b>Antes de leer los números.</b> '
                 "Hay %d problemas graves en la carga de la planilla. Mientras "
                 "no se arreglen, los números de abajo pueden estar mal. "
                 "El detalle está al final.</div>" % rep["graves"])

    p.append("<h2>Lo que dicen los números</h2>")
    if rep["lecturas"]:
        for l in rep["lecturas"][:10]:
            f = (l.get("cuenta") or {}).get("formula") or ""
            p.append('<div class="lect"><div class="t">%s</div>%s</div>'
                     % (esc(l["texto"]),
                        '<div class="f">%s</div>' % esc(f) if f else ""))
    else:
        p.append("<p>No hay nada que se pueda afirmar con estos datos.</p>")

    for i, corte in enumerate(rep["cortes"]):
        if i == 2:
            p.append('<div class="salto"></div>')
        p.append("<h2>Por %s</h2>" % esc(corte["nombre"]))
        p.append("<table><tr><th>%s</th><th>Cantidad</th><th></th><th>%%</th></tr>"
                 % esc(corte["nombre"]))
        top = max([n for _, n, _ in corte["valores"]] or [1])
        for v, n, pc in corte["valores"]:
            p.append('<tr><td>%s</td><td class="n">%s</td>'
                     '<td style="width:34%%"><span class="barra">'
                     '<i style="width:%.1f%%"></i></span></td>'
                     '<td class="n">%s</td></tr>'
                     % (esc(v), _mil(n), 100.0 * n / top,
                        ("%.1f%%" % pc).replace(".", ",")))
        p.append("</table>")

    p.append('<div class="salto"></div>')
    p.append("<h2>Lo que hay que revisar en la carga</h2>")
    if rep["avisos"]:
        p.append("<p>%d cosas, %d de ellas graves. <b>Una grave significa que el "
                 "número de arriba está mal hasta que se arregle.</b></p>"
                 % (len(rep["avisos"]), rep["graves"]))
        p.append("<table><tr><th></th><th>Qué pasa</th><th>Por qué importa</th></tr>")
        for a in rep["avisos"][:14]:
            p.append('<tr><td><span class="chapa %s">%s</span></td>'
                     "<td>%s</td><td>%s</td></tr>"
                     % (a["gravedad"], a["gravedad"].upper(),
                        esc(a["titulo"]), esc(a["detalle"])))
        p.append("</table>")
    else:
        p.append("<p>Nada. La planilla está bien cargada.</p>")

    if rep["sensibles"]:
        p.append("<h2>Datos que no salen de acá</h2>")
        p.append('<div class="nota">La planilla tiene <b>%d columnas con datos de '
                 "clientes</b> (%s). Este reporte no incluye ni un valor de esas "
                 "columnas. Esos datos tampoco se publican en la intranet de "
                 "vendedores, que es pública y no tiene contraseña.</div>"
                 % (len(rep["sensibles"]), esc(", ".join(rep["sensibles"]))))

    p.append('<div class="pie">Mueblesysillones · Reporte interno del equipo de '
             "marketing · No contiene datos de clientes</div>")
    p.append("</div>")

    html = ("<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
            "<title>%s</title><style>%s</style></head><body>%s</body></html>"
            % (esc(rep["titulo"]), CSS, "".join(p)))
    io.open(ruta, "w", encoding="utf-8").write(html)
    return ruta
