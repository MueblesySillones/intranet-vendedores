# -*- coding: utf-8 -*-
"""El reporte de derivaciones en Word, con el DISEÑO del deck.

POR QUE EXISTE ESTE ARCHIVO Y NO ALCANZA CON reporte.a_word

`reporte.a_word` saca un documento de oficina: títulos, párrafos y tablas.
Sirve para leer, pero no es lo que se muestra en una reunión. Lo que se
muestra es el deck: una lámina por tema, apaisada, con el número grande
adelante y la explicación abajo. Este archivo saca ESO en Word — misma
estructura, mismos colores, mismo orden— para el que necesita el archivo
editable y no un PDF.

COMO SE HACE UN .docx SIN LIBRERIAS
Un .docx es un ZIP con XML adentro. Se escribe a mano con `zipfile`, igual
que en reporte.py, porque el panel viaja como .exe y no puede sumar
python-docx.

LO QUE WORD NO PUEDE, Y QUE SE HACE EN VEZ
  · Fondo de página entero: en Word es del documento, no de una hoja. La
    portada oscura se hace con una tabla ancha sombreada, que se ve igual.
  · Barras: no hay gráficos. Cada barra es una tabla de dos celdas —la
    llena y la vacía— con el ancho repartido a proporción. Se imprime bien
    y no depende de ninguna imagen.

⚠️ NUNCA lleva datos de clientes: se cuentan filas, no se copia ni un valor
   de las columnas sensibles.
"""
import datetime
import unicodedata
import zipfile

from . import deck
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# apaisada A4, en veinteavos de punto
ANCHO_HOJA, ALTO_HOJA, MARGEN = 16838, 11906, 1134
ANCHO = ANCHO_HOJA - MARGEN * 2          # 14570: lo que entra en la hoja

TINTA = "1B1B1B"
GRIS = "6E6E6E"
CREMA = "F0EDE8"
AZUL = "2C6E8A"       # derivaciones
VERDE = "1A6A3A"      # ventas
VERDE2 = "3A7A55"     # conducta (templates)
BORDO = "8A2C2C"      # lo que se pierde

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _mil(n):
    return "{:,}".format(int(n)).replace(",", ".")


def _plural(n, uno, muchos):
    """«1 fila» y no «1 filas». Nadie lee un reporte que escribe mal."""
    return "%s %s" % (_mil(n), uno if int(n) == 1 else muchos)


def _pct(x, dec=1):
    return (("%." + str(dec) + "f%%") % (x * 100)).replace(".", ",")


def _mes_largo(iso):
    """'2026-08' -> 'agosto de 2026'."""
    try:
        a, m = iso.split("-")
        return "%s de %s" % (MESES[int(m)], a)
    except (ValueError, IndexError, AttributeError):
        return iso or ""


# Las únicas palabras que se escriben en mayúscula entera. Es una lista y no
# una regla («si tiene 4 letras y vino en mayúscula») porque esa regla también
# le pega a FLOR y a DORA, que son nombres de personas y no siglas.
SIGLAS = {"CABA"}


def _nombre(s):
    """VIVIANA -> Viviana, pero CABA sigue siendo CABA."""
    return " ".join(w if w.upper() in SIGLAS else w.capitalize()
                    for w in str(s or "").split())


def _mes_corto(iso):
    try:
        return MESES[int(iso.split("-")[1])][:3].capitalize()
    except (ValueError, IndexError, AttributeError):
        return iso or ""


# ───────────────────────── ladrillos de XML ─────────────────────────
def _run(t, tam=22, negrita=False, color=None, mayus=False, espaciado=None):
    """Un pedazo de texto con su formato. `tam` es en medios puntos."""
    rpr = ""
    if negrita:
        rpr += "<w:b/>"
    if color:
        rpr += '<w:color w:val="%s"/>' % color
    if mayus:
        rpr += "<w:caps/>"
    if espaciado:
        rpr += '<w:spacing w:val="%d"/>' % espaciado
    rpr += '<w:sz w:val="%d"/><w:rFonts w:ascii="Segoe UI" w:hAnsi="Segoe UI"/>' % tam
    return ('<w:r><w:rPr>%s</w:rPr><w:t xml:space="preserve">%s</w:t></w:r>'
            % (rpr, escape(t or "")))


def _par(runs, antes=0, despues=120, fondo=None, alineado=None, interlinea=None):
    if isinstance(runs, str):
        runs = [runs]
    ppr = '<w:spacing w:before="%d" w:after="%d"%s/>' % (
        antes, despues,
        ' w:line="%d" w:lineRule="auto"' % interlinea if interlinea else "")
    if alineado:
        ppr += '<w:jc w:val="%s"/>' % alineado
    if fondo:
        ppr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fondo
    return "<w:p><w:pPr>%s</w:pPr>%s</w:p>" % (ppr, "".join(runs))


def _salto():
    """Corta la hoja: una lámina por página, como en el deck."""
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def _celda(ancho, contenido, fondo=None, margen=120, alineado_v="center"):
    tcpr = '<w:tcW w:w="%d" w:type="dxa"/>' % max(ancho, 1)
    if fondo:
        tcpr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fondo
    tcpr += '<w:vAlign w:val="%s"/>' % alineado_v
    tcpr += ('<w:tcMar><w:top w:w="%d" w:type="dxa"/><w:bottom w:w="%d" w:type="dxa"/>'
             '<w:left w:w="%d" w:type="dxa"/><w:right w:w="%d" w:type="dxa"/></w:tcMar>'
             % (margen, margen, margen, margen))
    return "<w:tc><w:tcPr>%s</w:tcPr>%s</w:tc>" % (tcpr, contenido or _par(""))


def _tabla(filas, anchos=None):
    """`filas` ya vienen como XML de celdas. Sin bordes: el color hace el trabajo."""
    grid = ""
    if anchos:
        grid = "<w:tblGrid>%s</w:tblGrid>" % "".join(
            '<w:gridCol w:w="%d"/>' % a for a in anchos)
    props = ('<w:tblPr><w:tblW w:w="%d" w:type="dxa"/>'
             '<w:tblLayout w:type="fixed"/>'
             '<w:tblCellMar><w:left w:w="0" w:type="dxa"/>'
             '<w:right w:w="0" w:type="dxa"/></w:tblCellMar></w:tblPr>' % ANCHO)
    return "<w:tbl>%s%s%s</w:tbl>" % (
        props, grid, "".join("<w:tr>%s</w:tr>" % f for f in filas))


def _barra(prop, color, ancho=None):
    """La barra propiamente dicha: una tabla de dos celdas, llena y vacía."""
    ancho = ancho or ANCHO
    lleno = max(int(round(ancho * max(0.0, min(1.0, prop)))), 60)
    vacio = max(ancho - lleno, 1)
    fila = (_celda(lleno, _par(_run(" ", 12), despues=0), fondo=color, margen=0) +
            _celda(vacio, _par(_run(" ", 12), despues=0), fondo="E3DFD9", margen=0))
    return ('<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/>'
            '<w:tblLayout w:type="fixed"/><w:tblCellMar>'
            '<w:left w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/>'
            '</w:tblCellMar></w:tblPr><w:tblGrid><w:gridCol w:w="%d"/>'
            '<w:gridCol w:w="%d"/></w:tblGrid><w:tr>%s</w:tr></w:tbl>'
            % (ancho, lleno, vacio, fila))


# Cuántas filas entran en UNA hoja apaisada sin empujar el cierre a la
# siguiente. Se midió abriendo el .docx en Word: con más de esto, la lámina se
# parte en dos y queda una hoja con una sola frase suelta.
TOPE_FILAS = 8


def _ranking(items, color, ancho_nombre=3600):
    """items = [(nombre, valor_texto, proporción, apostilla)]"""
    if not items:
        return ""
    # ⚠️ El recorte lo hace `_lamina_partes`, que sabe repartir en varias hojas.
    # Recortar acá además significaba perder filas sin decirlo.
    items = items[:TOPE_FILAS]
    a_nom = ancho_nombre
    a_val = 2400
    a_bar = ANCHO - a_nom - a_val
    filas = []
    for nom, val, prop, nota in items:
        barra = _barra(prop, color, a_bar - 240)
        filas.append(
            "<w:trPr><w:cantSplit/></w:trPr>" +
            _celda(a_nom, _par([_run(nom, 22, True)] +
                               ([_run("   " + nota, 16, color=GRIS)] if nota else []),
                               despues=0)) +
            _celda(a_bar, barra + "<w:p/>") +
            _celda(a_val, _par(_run(val, 24, True, color), despues=0),
                   alineado_v="center"))
    return _tabla(filas, [a_nom, a_bar, a_val])


def _encabezado(kicker, titulo, bajada, color):
    """El arranque de cada lámina, igual que en el deck.

    Cada parte solo si tiene algo: un texto que se sacó desde el reporte no
    puede dejar un renglón en blanco en el Word.
    """
    x = ""
    if str(kicker).strip():
        x += _par(_run(kicker, 17, True, color, mayus=True, espaciado=40),
                  antes=0, despues=60)
    if str(titulo).strip():
        x += _par(_run(titulo, 40, True, TINTA), despues=40, interlinea=240)
    if str(bajada).strip():
        x += _par(_run(bajada, 21, color=GRIS), despues=320)
    return x


def _notas(lineas, color, tope=2):
    """Las notas de abajo, como las tarjetas del deck: título chico de color y
    el texto debajo.

    En Word una lámina es una hoja, y tres bloques sombreados abajo de ocho
    filas se pasan de la hoja. Entran dos: si hay una tercera, se le suma al
    segundo bloque en vez de perderse.
    """
    lineas = [(t, x) for t, x in lineas if str(t).strip() or str(x).strip()]
    if not lineas:
        return ""
    grupos = [[l] for l in lineas[:tope]]
    for extra in lineas[tope:]:
        grupos[-1].append(extra)
    out = []
    for g in grupos:
        dentro = ""
        for i, (t, x) in enumerate(g):
            if str(t).strip():
                dentro += _par(_run(t, 18, True, color, mayus=True,
                                    espaciado=30),
                               antes=(120 if i else 0), despues=40)
            if str(x).strip():
                dentro += _par(_run(x, 20, color=TINTA), despues=0)
        out.append(_tabla([_celda(ANCHO, dentro, fondo="E8E4DF", margen=200)],
                          [ANCHO]))
    return "<w:p/>".join(out)


def _cierre(texto, color):
    """La frase de abajo: qué significa el número. Sin esto es un adorno."""
    if not texto:
        return ""
    return _tabla([_celda(ANCHO, _par(_run(texto, 21, color=TINTA), despues=0),
                          fondo="E8E4DF", margen=200)], [ANCHO])


# ───────────────────────────── las láminas ─────────────────────────────
def _portada(d, titulo, nota=None):
    t = d["total"]
    per = "toda la planilla"
    if d.get("mes_desde"):
        per = _mes_largo(d["mes_desde"])
        if d.get("mes_hasta") and d["mes_hasta"] != d["mes_desde"]:
            per += " — " + _mes_largo(d["mes_hasta"])

    if per and per.strip().lower() == str(titulo).strip().lower():
        per = ""
    dentro = (_par(_run("Muebles y Sillones", 18, True, "C9C2B8",
                        mayus=True, espaciado=60), despues=200) +
              _par(_run(titulo, 60, True, "FFFFFF"), despues=120, interlinea=240) +
              _par(_run(per, 24, color="C9C2B8"),
                   despues=0 if not nota else 180) +
              (_par(_run(nota, 20, color="9A948C"), despues=0) if nota else ""))
    tapa = _tabla([_celda(ANCHO, dentro, fondo="1E2A2E", margen=460)], [ANCHO])

    tercio = ANCHO // 3
    def cubo(n, rot, color):
        return _celda(tercio - 60,
                      _par(_run(_mil(n), 56, True, color), despues=40) +
                      _par(_run(rot, 19, color=GRIS, mayus=True, espaciado=30),
                           despues=0),
                      fondo="FFFFFF", margen=300, alineado_v="top")
    cubos = _tabla([cubo(t["consultas"], "consultas", TINTA) +
                    _celda(60, _par("")) +
                    cubo(t["derivaciones"], "derivaciones", AZUL) +
                    _celda(60, _par("")) +
                    cubo(t["ventas"], "ventas", VERDE)],
                   [tercio - 60, 60, tercio - 60, 60, tercio - 60])
    return tapa + "<w:p/>" + cubos


def _lamina_embudo(d, op=None):
    """Los cuatro números del embudo, con cuánto cambió cada uno.

    El cambio sale de `deck._contra`, la misma cuenta que usa el deck: si lo
    calculara acá, el Word y el PDF podrían decir porcentajes distintos del
    mismo par de números.
    """
    op = op or {}
    t = d["total"]
    prev = (op.get("previo") or {}).get("total") if op.get("previo") else None
    como = op.get("previo_txt") or ""
    sin_derivar = t["consultas"] - t["derivaciones"]
    sin_antes = ((prev["consultas"] - prev["derivaciones"]) if prev else None)

    def apostilla(fijo, ahora, antes, mejor_subir):
        cambio = deck._contra(ahora, antes, mejor_subir, como)
        if not cambio:
            return fijo
        # el ▲▼ de la pantalla no está en las fuentes de Word en todas las
        # máquinas: acá va escrito con palabras, que se lee igual de rápido
        texto = cambio[0].replace("▲", "+").replace("▼", "−")
        return (fijo + " · " + texto) if fijo else texto

    foco = d.get("sucursal_foco") or ""
    if foco:
        # el embudo de una sucursal (igual que en el deck): las consultas son
        # del período entero; derivaciones y ventas, del local
        empresa = d.get("derivaciones_empresa") or t["derivaciones"]
        otras = t.get("de_otra_sucursal", 0)
        pasos = [
            ("Consultas que entraron", _mil(t["consultas"]), 1.0,
             apostilla("toda la empresa", t["consultas"], prev and prev["consultas"], True), TINTA),
            ("Derivadas a " + foco, _mil(t["derivaciones"]),
             t["derivaciones"] / float(t["consultas"] or 1),
             apostilla(_pct(t["derivaciones"] / float(empresa or 1), 0) + " de las de la empresa",
                       t["derivaciones"], prev and prev["derivaciones"], True), AZUL),
            ("Fueron a otra sucursal", _mil(otras), otras / float(t["consultas"] or 1),
             "las atendió otro local", BORDO),
            ("Ventas de " + foco, _mil(t["ventas"]), t["ventas"] / float(t["consultas"] or 1),
             apostilla(_pct(d["tasa_cierre"]) + " de conversión",
                       t["ventas"], prev and prev["ventas"], True), VERDE),
        ]
    else:
        pasos = None
    pasos = pasos or [
        ("Consultas que entraron", _mil(t["consultas"]), 1.0,
         apostilla("", t["consultas"], prev and prev["consultas"], True), TINTA),
        ("Llegaron a un vendedor", _mil(t["derivaciones"]),
         t["derivaciones"] / float(t["consultas"] or 1),
         apostilla(_pct(d["tasa_derivacion"], 0) + " del total",
                   t["derivaciones"], prev and prev["derivaciones"], True), AZUL),
        ("Nunca llegaron a nadie", _mil(sin_derivar),
         sin_derivar / float(t["consultas"] or 1),
         apostilla("se perdieron antes", sin_derivar, sin_antes, False), BORDO),
        ("Terminaron en venta", _mil(t["ventas"]),
         t["ventas"] / float(t["consultas"] or 1),
         apostilla(_pct(d["tasa_cierre"]) + " de las derivadas",
                   t["ventas"], prev and prev["ventas"], True), VERDE),
    ]
    filas = []
    a_nom, a_bar, a_val = 4200, 7970, 2400
    for nom, val, prop, nota, color in pasos:
        filas.append(
            _celda(a_nom, _par([_run(nom, 22, True)] +
                               ([_run("   " + nota, 16, color=GRIS)] if nota else []),
                               despues=0)) +
            _celda(a_bar, _barra(prop, color, a_bar - 240) + "<w:p/>") +
            _celda(a_val, _par(_run(val, 26, True, color), despues=0)))
    return (_encabezado(deck.txt("embudo.kicker", "El embudo"),
                        deck.txt("embudo.titulo", "De la consulta a la venta"),
                        deck.txt("embudo.bajada",
                                 "Cada consulta que entra, hasta dónde llegó"),
                        AZUL) +
            _tabla(filas, [a_nom, a_bar, a_val]) + "<w:p/>" +
            _cierre(((("%s recibió %s y cerró %s: una conversión del %s."
                        % (foco, _mil(t["derivaciones"]) + " derivaciones",
                           _mil(t["ventas"]) + " ventas", _pct(d["tasa_cierre"])))
                      if foco else
                      ("El %s de las consultas llega a un vendedor y el %s "
                       "termina en venta. Antes de llegar a alguien se pierden "
                       "%s consultas."
                       % (_pct(d["tasa_derivacion"], 0),
                          _pct(t["ventas"] / float(t["consultas"] or 1)),
                          _mil(sin_derivar))))
                     + ((" " + deck.nota_monto(d, op)[1]) if deck.nota_monto(d, op) else "")),
                    AZUL))


def _lamina_meses(d):
    meses = sorted(d["meses"])
    if len(meses) < 2:
        return ""
    ult = meses[-8:]
    tope = max(d["meses"][m]["derivaciones"] for m in ult) or 1
    items = [(_mes_corto(m) + " " + m[:4], _mil(d["meses"][m]["derivaciones"]),
              d["meses"][m]["derivaciones"] / float(tope),
              "%s consultas" % _mil(d["meses"][m]["consultas"])) for m in ult]
    a, b = d["meses"][ult[-2]]["derivaciones"], d["meses"][ult[-1]]["derivaciones"]
    if a:
        dif = (b - a) / float(a)
        frase = ("%s pasó de %s a %s derivaciones contra %s: %s%s."
                 % (_mes_largo(ult[-1]).capitalize(), _mil(a), _mil(b),
                    _mes_largo(ult[-2]), "+" if dif >= 0 else "", _pct(dif, 0)))
    else:
        frase = ""
    return (_encabezado(deck.txt("meses.kicker", "Mes a mes"),
                        deck.txt("meses.titulo", "Derivaciones por mes"),
                        "Derivaciones por mes; abajo, las consultas que "
                        "entraron", AZUL) +
            _ranking(items, AZUL) + "<w:p/>" + _cierre(frase, AZUL))


def _lamina_sucursales(d):
    sucs = sorted(d["sucursales"].items(), key=lambda x: -x[1]["derivaciones"])
    sucs = [(n, b) for n, b in sucs if b["derivaciones"]]
    if not sucs:
        return ""
    tope = sucs[0][1]["derivaciones"] or 1
    items = [(_nombre(n), _mil(b["derivaciones"]),
              b["derivaciones"] / float(tope),
              "%s ventas" % _mil(b["ventas"])) for n, b in sucs[:TOPE_FILAS]]
    frase = ""
    if d.get("sin_ubicar"):
        frase = ("Quedan %s derivaciones sin sucursal (%s): son vendedores que "
                 "no figuran en ningún local."
                 % (_mil(sum(d["sin_ubicar"].values())),
                    ", ".join(_nombre(x) for x in sorted(d["sin_ubicar"])[:4])))
    return (_encabezado(deck.txt("sucursales.kicker", "Sucursales"),
                        deck.txt("sucursales.titulo",
                                 "Cómo se reparten las derivaciones"),
                        "Derivaciones por local, de mayor a menor", AZUL) +
            _ranking(items, AZUL) + "<w:p/>" + _cierre(frase, AZUL))


def _lamina_partes(p, ancho_nombre=5200):
    """Una lámina del deck, dibujada en Word. Puede salir en VARIAS hojas.

    `p` son las partes que calculó deck.py —las mismas que dibuja el HTML—.
    Acá solo se eligen los anchos y se arma la tabla: ni un número se vuelve a
    calcular, que es todo el punto.

    ⚠️ Una lista larga se reparte, igual que en el deck. En una hoja apaisada
    entran 8 filas (`TOPE_FILAS`, medido en Word de verdad); con 19 vendedores,
    las 11 que sobraban simplemente no estaban. Las hojas que siguen dicen
    «2 de 3» en el rótulo y las notas van con la última, porque hablan de la
    lista entera.
    """
    if not p or not p.get("filas"):
        return ""
    color = str(p["color"]).lstrip("#")
    tope = max(v for _, v, _, _ in p["filas"]) or 1
    todos = [(nom, val, p["filas"][i][1] / float(tope), nota)
             for i, (nom, val, nota) in enumerate(p["filas_w"])]
    paginas = [todos[i:i + TOPE_FILAS]
               for i in range(0, len(todos), TOPE_FILAS)] or [[]]
    hojas = []
    for i, items in enumerate(paginas):
        ultima = i == len(paginas) - 1
        kicker = p["kicker"]
        if len(paginas) > 1:
            kicker = "%s · %d de %d" % (str(p["kicker"]).strip() or "Lista",
                                        i + 1, len(paginas))
        hojas.append(
            _encabezado(kicker, p["titulo"], p["bajada"], color) +
            _ranking(items, color, ancho_nombre=ancho_nombre) + "<w:p/>" +
            (_notas(p["lineas"], color) if ultima else ""))
    return _salto().join(hojas)


def _lamina_precio(d):
    t = d["total"]
    if not t.get("precio"):
        return ""
    prop = t["precio"] / float(t["derivaciones"] or 1)
    ventas_prop = t["ventas"] / float(t["precio"] or 1)
    items = [("Recibieron precio", _mil(t["precio"]), 1.0, ""),
             ("Terminaron comprando", _mil(t["ventas"]), ventas_prop, "")]
    return (_encabezado(deck.txt("precio.kicker", "El cuello de botella"),
                        deck.txt("precio.titulo",
                                 "Qué pasa después de mandar el precio"),
                        "De los que ya saben cuánto sale, cuántos compran",
                        BORDO) +
            _ranking(items, BORDO) + "<w:p/>" +
            _cierre("A %s consultas derivadas se les pasó precio (%s de las "
                    "derivadas) y compraron %s: %s. Ahí está el cuello."
                    % (_mil(t["precio"]), _pct(prop, 0), _mil(t["ventas"]),
                       _pct(ventas_prop)), BORDO))


def _lamina_limites(d):
    t = d["total"]
    lineas = []
    if d.get("periodo_pedido"):
        if d.get("fuera_del_periodo"):
            lineas.append("Quedaron afuera %s por estar fuera del período."
                          % _plural(d["fuera_del_periodo"], "fila", "filas"))
        n = d.get("sin_fecha_fuera") or 0
        if n:
            lineas.append("Otra%s %s no tiene%s fecha, así que no se puede "
                          "afirmar que haya pasado en este período. También "
                          "quedó afuera." % ("" if n == 1 else "s",
                                             _plural(n, "fila", "filas"),
                                             "" if n == 1 else "n"))
    elif t.get("sin_fecha"):
        lineas.append("%s sin fecha: cuenta%s en los totales pero no en el mes "
                      "a mes." % (_plural(t["sin_fecha"], "fila", "filas"),
                                  "" if t["sin_fecha"] == 1 else "n"))
    if d.get("sin_ubicar"):
        n = sum(d["sin_ubicar"].values())
        lineas.append("%s no %s sucursal asignada."
                      % (_plural(n, "derivación", "derivaciones"),
                         "tiene" if n == 1 else "tienen"))
    lineas.append("Una venta es una fila con «Realizó la compra» en Respuesta "
                  "Final. Si no se carga, no se cuenta.")
    lineas.append("Este reporte no incluye ningún dato de clientes.")
    cuerpo = "".join(_par([_run("— ", 21, color=GRIS), _run(l, 21)], despues=140)
                     for l in lineas)
    return (_encabezado(deck.txt("limites.kicker", "Los límites"),
                        deck.txt("limites.titulo",
                                 "Lo que estos datos NO permiten afirmar"),
                        "Para leerlo sabiendo qué hay atrás", GRIS) + cuerpo)


# ───────────────────────────── el documento ─────────────────────────────
def armar(d, titulo="Reporte de derivaciones", secciones=None, opciones=None):
    """El XML del cuerpo. Mismo orden y mismas secciones que el deck."""
    op = opciones or {}
    deck._CTX.textos = deck.Textos(op.get("textos"), op.get("ocultos"))
    try:
        return _armar(d, titulo, secciones, opciones)
    finally:
        deck._CTX.textos = None


def _armar(d, titulo, secciones, opciones):
    op = opciones or {}
    quiere = (lambda k: True) if not secciones else (lambda k: k in set(secciones))
    # ⚠️ El mismo corte que el deck, no uno propio. Con TOPE_FILAS acá, el Word
    # se quedaba con 8 vendedores de 19 y no lo decía: las 11 que faltaban no
    # aparecían ni en la lámina ni en una nota. Ahora entran todas y
    # _lamina_partes las reparte en las hojas que hagan falta.
    n = deck._cuantos(op)
    laminas = [_portada(d, titulo, op.get("nota"))]
    if quiere("embudo"):
        laminas.append(_lamina_embudo(d, op))
    if quiere("meses"):
        laminas.append(_lamina_meses(d))
    if quiere("ritmo"):
        laminas.append(_lamina_partes(deck.partes_ritmo(d), ancho_nombre=3600))
    if quiere("sucursales"):
        laminas.append(_lamina_sucursales(d))
    if quiere("vendedores"):
        laminas.append(_lamina_partes(deck.partes_ranking(
            d, "derivaciones", "Derivaciones por vendedor",
            "Cuántas consultas recibió cada uno, con lo que cerró al lado",
            "El equipo", "derivaciones", cuantos=n,
            clave="vendedores", con_ventas=True), ancho_nombre=5200))
    if quiere("productos"):
        laminas.append(_lamina_partes(deck.partes_productos(d, n),
                                      ancho_nombre=6800))
    if quiere("origenes"):
        laminas.append(_lamina_partes(deck.partes_origenes(d, n),
                                      ancho_nombre=6800))
    if quiere("anuncios"):
        for x in deck.laminas_anuncios(d):
            laminas.append(_lamina_partes(x, ancho_nombre=5600))
    if quiere("prod_origen"):
        laminas.append(_lamina_partes(deck.partes_prod_origen(d, n),
                                      ancho_nombre=6800))
    if quiere("medios"):
        laminas.append(_lamina_partes(deck.partes_medios(d, n),
                                      ancho_nombre=6800))
    if quiere("localidades"):
        for x in deck.laminas_localidades(d, op):
            laminas.append(_lamina_partes(x, ancho_nombre=5200))
    if quiere("zonas"):
        laminas.append(_lamina_partes(deck.partes_zonas(d), ancho_nombre=6000))
    if quiere("provincias"):
        laminas.append(_lamina_partes(deck.partes_provincias(d, n),
                                      ancho_nombre=4200))
    if quiere("reparto"):
        laminas.append(_lamina_partes(deck.partes_reparto(d, n),
                                      ancho_nombre=5600))
    if quiere("template"):
        laminas.append(_lamina_partes(deck.partes_ranking(
            d, "template", "Quién manda más templates",
            "Seguimiento enviado — es conducta, no resultado", "Cumplimiento",
            "enviados", color=VERDE2, cuantos=n,
            clave="template"), ancho_nombre=5200))
    if quiere("precio"):
        laminas.append(_lamina_precio(d))
    if quiere("patrones"):
        laminas.append(_lamina_partes(deck.partes_patrones(d),
                                      ancho_nombre=6800))
    if quiere("motivos"):
        laminas.append(_lamina_partes(deck.partes_motivos(d),
                                      ancho_nombre=6800))
    laminas.append(_lamina_limites(d))
    return _salto().join(x for x in laminas if x)


def a_word(d, ruta, titulo="Reporte de derivaciones", secciones=None,
           opciones=None):
    cuerpo = armar(d, titulo, secciones, opciones)
    documento = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<w:document %s><w:body>%s'
                 '<w:sectPr><w:pgSz w:w="%d" w:h="%d" w:orient="landscape"/>'
                 '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d"/>'
                 '</w:sectPr></w:body></w:document>'
                 % (W, cuerpo, ANCHO_HOJA, ALTO_HOJA,
                    MARGEN, MARGEN, MARGEN, MARGEN))

    tipos = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", documento)
    return ruta


def nombre_archivo(titulo):
    """Un nombre de archivo que no rompa en Windows ni en la cabecera HTTP.

    ASCII a proposito: el nombre viaja en `Content-Disposition`, que se escribe
    en latin-1, y un emoji pegado sin querer en el titulo tiraba la respuesta
    entera sin que se entendiera por que.
    """
    limpio = unicodedata.normalize("NFKD", str(titulo or "Reporte"))
    limpio = "".join(c for c in limpio
                     if (c.isalnum() or c in " -_") and ord(c) < 128).strip()
    return "%s - %s.docx" % (limpio[:60] or "Reporte",
                             datetime.date.today().strftime("%d-%m-%Y"))
