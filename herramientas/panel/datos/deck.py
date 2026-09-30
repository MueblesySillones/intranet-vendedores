# -*- coding: utf-8 -*-
"""El reporte, con el diseño del deck que ya usa la empresa.

QUÉ GENERA
  Un HTML de un solo archivo, sin nada de afuera, que sirve para tres cosas a
  la vez:
    · mirarlo en el panel,
    · pasarlo como presentación (flechas, F para pantalla completa),
    · imprimirlo a PDF en 16:9 (Ctrl+P → Guardar como PDF).

  Es el mismo lenguaje visual del reporte de vendedores que ya se hizo:
  `mys-presentaciones/index.html`. No se imita — se reusan sus tokens y sus
  componentes (`.conv-card`, `.month-card`, `.bar2`, `.eyebrow`, `.s-title`) y
  su hoja de impresión, que es la que hace que salga en 16:9 y no en A4.

LA REGLA QUE MANDA EN TODO ESTE ARCHIVO
  Cada número que se dibuja sale de `derivaciones.analizar()`. Acá no se
  calcula nada. Y cada frase que parece una conclusión tiene que estar sostenida
  por un número que está en la misma pantalla: si la afirmación no se puede
  verificar mirando el slide, no va.

  Por eso el reporte NO ordena vendedores por conversión, aunque sea lo primero
  que a uno se le ocurre: con 3% de cierre y 200 derivaciones, esa diferencia
  es azar, y publicarla como mérito es inventar una conclusión con cara de
  dato. Se rankea lo que tiene volumen y depende del vendedor (derivaciones,
  templates); la venta se muestra como resultado del equipo.
"""
import datetime
import json
import threading
from xml.sax.saxutils import escape

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
CORTO = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago",
         "sep", "oct", "nov", "dic"]

# Los mismos colores del deck. Las sucursales tienen color propio para que una
# persona reconozca la suya de un vistazo entre un slide y otro.
COLOR_SUC = {
    "hudson": "#1A1A2E", "caba": "#2C6E8A", "belgrano": "#2C6E8A",
    "canning": "#3A7A55", "norcenter": "#8A5A2C", "pilar": "#6A4A7A",
    "north delta": "#2C6E6E",
}
PALETA = ["#1A1A2E", "#2C6E8A", "#3A7A55", "#8A5A2C", "#6A4A7A", "#2C6E6E"]

# Una sola familia de color para una lista de categorías sin color propio. Con
# la paleta de arriba, los siete motivos salían en siete colores sin relación
# entre sí y parecían siete cosas distintas; con una rampa se lee lo que es:
# la misma cosa, de mayor a menor.
RAMPA_PERDIDA = ["#7A2320", "#8A2C2C", "#9C4038", "#AC5A4E", "#BC776A",
                 "#CB9488", "#D9B1A7"]

# Lo que NO se capitaliza en el medio de un nombre, y lo que va entero en
# mayúscula. `.title()` de Python escribe «Promo Esquineros Y Sillones» y
# «Ig Organico»: en algo que se proyecta eso se lee como un error nuestro.
_ATONAS = {"y", "e", "o", "u", "de", "del", "la", "el", "los", "las", "en",
           "con", "por", "para", "a", "al", "sin", "un", "una"}
_SIGLAS = {"CABA", "IG", "MYS", "MV", "TT", "WA", "OK"}


def titulo_de(s):
    """«PROMO ESQUINEROS Y SILLONES» → «Promo Esquineros y Sillones»."""
    palabras = str(s or "").split()
    out = []
    for i, w in enumerate(palabras):
        if w.upper() in _SIGLAS:
            out.append(w.upper())
        elif i and w.lower() in _ATONAS:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


class Marca(str):
    """Un texto que sabe de qué parte del reporte salió.

    Es un `str` a todos los efectos —se concatena, se formatea, se compara
    igual—, pero lleva `clave` pegada. Cuando pasa por e() sale envuelto en un
    span que la página de edición puede encontrar. Si alguien lo formatea
    (`"%s" % marca`) se convierte en str pelado y no pasa nada: se pierde la
    marca, no el texto.
    """
    clave = ""


def e(t):
    s = escape(str(t if t is not None else ""))
    clave = getattr(t, "clave", "")
    return ('<span class="ed-t" data-txt="%s">%s</span>' % (clave, s)
            if clave else s)


def plural(n, uno, muchos):
    """«1 venta» y no «1 ventas». Un reporte que escribe mal se lee peor."""
    return "%s %s" % (miles(n), uno if int(n) == 1 else muchos)


def miles(n):
    try:
        return "{:,}".format(int(n)).replace(",", ".")
    except (TypeError, ValueError):
        return str(n or "")


def pct(x, decimales=1):
    """4,4% — con coma, que es como se escribe un decimal en castellano.

    ⚠️ Algo que existe nunca se escribe «0%». Con 2 de 475 y sin decimales,
    redondear daba «0% de las derivaciones» en una frase que hablaba justamente
    de esas 2: el reporte se contradecía solo. Debajo del último decimal que
    entra, sale «<1%».
    """
    v = 100.0 * (x or 0)
    minimo = 10.0 ** (-decimales)
    if 0 < v < minimo:
        return "<" + (("%." + str(decimales) + "f") % minimo).replace(".", ",") + "%"
    t = ("%." + str(decimales) + "f") % v
    return t.replace(".", ",") + "%"


def _acortar(s, tope=20):
    """Un nombre largo cortado con puntos suspensivos, no a la mitad de una
    palabra. Adentro de una barra no entra todo y hay que cortar; lo que no
    puede es parecer que la herramienta se equivocó."""
    s = str(s)
    if len(s) <= tope:
        return s
    corto = s[:tope].rsplit(" ", 1)[0]
    return (corto if len(corto) >= tope - 8 else s[:tope]).rstrip(" ,.") + "…"


def _dia_mes(iso):
    """«2026-07-27» → «27/07/2026». Entra texto porque el análisis devuelve
    texto: nada de lo que sale de ahí es un objeto de Python."""
    try:
        a, m, d = str(iso).split("-")
        return "%s/%s/%s" % (d, m, a)
    except ValueError:
        return str(iso)


def _color(nombre, i=0):
    return COLOR_SUC.get((nombre or "").strip().lower(), PALETA[i % len(PALETA)])


def _titulo_mes(clave):
    """'2026-08' -> 'agosto 2026'."""
    try:
        a, m = clave.split("-")
        return "%s %s" % (MESES[int(m)], a)
    except (ValueError, IndexError):
        return clave


def _corto_mes(clave):
    try:
        return CORTO[int(clave.split("-")[1])]
    except (ValueError, IndexError):
        return clave


# =====================================================================
#  Piezas de slide
# =====================================================================
# ═════════════════════ LOS TEXTOS SE PUEDEN REESCRIBIR ═════════════════════
# Un reporte lo lee gente, y a veces una palabra no es la que se usa en la
# casa: «derivaciones» acá, «pases» allá. Cada texto del deck pasa por t(), que
# devuelve lo que el usuario haya escrito encima o, si no escribió nada, el de
# fábrica. De paso queda la lista de todo lo que se puede editar, que es lo que
# la pantalla necesita para armar el formulario sin tener esta lista repetida.
#
# ⚠️ Se reescriben TEXTOS, nunca números. Los números se calculan siempre. Pero
# hay frases de cierre que llevan un número adentro («bajaron un 20%»): si esas
# se reescriben, el número queda escrito a mano y NO se actualiza más. Por eso
# cada texto viaja con `numeros`, para que la pantalla lo avise donde se edita.
_CTX = threading.local()


class Textos:
    def __init__(self, over=None, ocultos=None):
        self.over = {k: v for k, v in (over or {}).items()
                     if str(v or "").strip()}
        self.ocultos = set(ocultos or ())

    def __call__(self, clave, defecto):
        """Un texto oculto vuelve vacío: el reporte lo saltea solo.

        Quien lo dibuja no tiene que saber nada de esto —cabeza() y notas() ya
        saltean lo vacío—, así que sacar un texto no puede dejar un hueco ni un
        cartel a medio escribir.
        """
        if clave in self.ocultos:
            valor = Marca("")
            valor.clave = clave
            return valor
        valor = Marca(self.over.get(clave) or defecto)
        valor.clave = clave
        return valor


class Grabador(Textos):
    """Textos que además anotan qué salió de cada clave.

    Lo usa el Word: arma la lámina del deck (el HTML se tira) y se queda con
    los textos finales —con lo editado y lo sacado ya aplicado— y con las
    notas tal como se dibujaron. Así el Word no tiene una copia propia de los
    textos que se pueda desfasar de la pantalla: pasaba, y 37 de 113 textos
    editados no llegaban al Word (30-sep-2026).
    """
    def __init__(self, over=None, ocultos=None):
        Textos.__init__(self, over, ocultos)
        self.visto = {}

    def __call__(self, clave, defecto):
        valor = Textos.__call__(self, clave, defecto)
        self.visto[clave] = str(valor)
        return valor


def grabar(fn, *args, **kw):
    """Corre una lámina del deck y devuelve (textos, notas) de lo que dibujó.

    textos = {clave: texto final}; notas = [(titulo, texto), ...] de cada
    llamada a notas(), en orden. Tiene que correr adentro de un contexto de
    textos ya puesto (el del Word): usa sus ediciones."""
    antes = getattr(_CTX, "textos", None)
    g = Grabador(getattr(antes, "over", None), getattr(antes, "ocultos", None))
    _CTX.textos = g
    _CTX.notas_grabadas = []
    try:
        fn(*args, **kw)
        return g.visto, _CTX.notas_grabadas
    finally:
        _CTX.textos = antes
        _CTX.notas_grabadas = None


def txt(clave, defecto):
    """El texto `clave`, con lo que el usuario haya puesto encima.

    Se llama `txt` y no `t` porque media docena de laminas ya usan `t` para
    `d["total"]`; un nombre corto que se pisa adentro de una funcion es un bug
    que no avisa.
    """
    tx = getattr(_CTX, "textos", None)
    return tx(clave, defecto) if tx is not None else defecto


def fondo(sec, oscuro=False):
    """Si esta lámina va clara u oscura. `oscuro` es cómo viene de fábrica.

    Se elige al editar y se guarda con el reporte. No hay colores nuevos: el
    deck ya sabía pintar una lámina oscura —la portada y los límites lo son—,
    lo que no había era manera de elegirlo.
    """
    elegido = (getattr(_CTX, "fondos", None) or {}).get(sec)
    if elegido in ("oscuro", "claro"):
        return elegido == "oscuro"
    return oscuro


def slide(cuerpo, oscuro=False, id_="", sec="", lista_=False):
    """Una lámina.

    `sec` es la sección a la que pertenece: la página de edición la usa para
    saber a qué guardar el fondo y la vista. `lista_` marca las que SON una
    lista y por eso ofrecen el interruptor de barras/columnas/tabla —el embudo
    y los límites tienen `sec` pero no son listas—.
    """
    return ('<section class="slide%s"%s%s%s><div class="slide-inner">%s</div>'
            '</section>'
            % (" dark" if oscuro else "", (' id="%s"' % id_) if id_ else "",
               (' data-sec="%s"' % sec) if sec else "",
               ' data-lista="1"' if lista_ else "", cuerpo))


def cabeza(eyebrow, titulo, sub=""):
    """Cada parte se dibuja solo si tiene algo. Un texto sacado no deja hueco."""
    out = ""
    if str(eyebrow).strip():
        out += '<div class="eyebrow">%s</div>' % e(eyebrow)
    if str(titulo).strip():
        out += '<h2 class="s-title">%s</h2>' % e(titulo)
    if str(sub).strip():
        out += '<div class="s-sub">%s</div>' % e(sub)
    return out


def conv_cards(items):
    """Tarjetas de color con un número gigante.

    items: (etiqueta, grande, sub, color, tag) y, opcional, un sexto elemento
    `cambio` = (texto, bueno) con cuánto cambió contra el período anterior.

    ⚠️ `bueno` no sale del signo. En «sin derivar» subir es MALO: pintar de
    verde un +18% ahí sería decir lo contrario de lo que pasó.
    """
    out = []
    for it in items:
        etq, grande, sub, color, tag = it[:5]
        cambio = it[5] if len(it) > 5 else None
        pie = ""
        if cambio and str(cambio[0]).strip():
            pie = ('<div class="ccmp %s">%s</div>'
                   % ("sube" if cambio[1] else "baja", e(cambio[0])))
        out.append(
            '<div class="conv-card" style="background:%s">'
            '<div class="cs">%s</div><div class="cbig">%s</div>'
            '<div class="csub">%s</div>%s%s</div>'
            % (color, e(etq), e(grande), e(sub), pie,
               ('<div class="ctag">%s</div>' % e(tag)) if tag else ""))
    return '<div class="conv-row">%s</div>' % "".join(out)


def _contra(ahora, antes, mejor_subir, etiqueta):
    """(texto, bueno) de cuánto cambió un número contra el período anterior.

    Devuelve None cuando no hay con qué comparar: inventar un «+100%» porque
    antes había cero es decir algo que el dato no dice.
    """
    if not etiqueta or antes is None:
        return None
    if not antes:
        return ("sin dato de %s" % etiqueta, True) if ahora else None
    dif = (ahora - antes) / float(antes)
    # 27-sep-2026 (pedido del usuario): el número de antes, a la vista. «−12%»
    # solo obliga a hacer la cuenta para saber de cuánto se habla.
    if abs(dif) < 0.005:
        return ("igual que %s (%s)" % (etiqueta, miles(antes)), True)
    signo = "▲" if dif > 0 else "▼"
    bueno = (dif > 0) == bool(mejor_subir)
    return ("%s %s vs %s (%s)" % (signo, pct(abs(dif), 0), etiqueta, miles(antes)), bueno)


def plata(n):
    """59262016 → «$59.262.016»."""
    return "$" + miles(int(n or 0))


def nota_monto(d, op=None):
    """(título, texto) con lo recaudado, o None si la planilla no lo tiene.

    El monto es UNO POR MES y de toda la empresa (el usuario, 27-sep-2026: «es
    un monto recaudado mensual»): la planilla no dice de qué sucursal es cada
    parte, así que en el reporte de una sucursal se aclara, en vez de
    atribuírselo."""
    total = d.get("monto_total") or 0
    if not total:
        return None
    op = op or {}
    prev = (op.get("previo") or {}).get("monto_total") if op.get("previo") else None
    cambio = _contra(total, prev, True, op.get("previo_txt") or "")
    meses = sorted((d.get("montos") or {}).keys())
    cuando = (_titulo_mes(meses[0]) if len(meses) == 1 else
              "%d meses" % len(meses)) if meses else "el período"
    texto = "%s recaudado en %s." % (plata(total), cuando)
    if cambio:
        texto += " %s." % cambio[0].replace("(", "(antes ").replace("(antes ", "(antes $", 1)
    if d.get("sucursal_foco"):
        texto += (" Es el total de la empresa: la planilla lo anota por mes, "
                  "sin decir de qué sucursal es cada parte.")
    return (txt("embudo.monto.titulo", "Lo recaudado"), txt("embudo.monto.texto", texto))


def month_cards(items, lider=None):
    """items: (etiqueta, numero, pie). `lider` marca cuál va en negro."""
    out = []
    for etq, num, pie in items:
        es_lider = (lider is not None and etq == lider)
        out.append('<div class="month-card%s"><div class="ml">%s</div>'
                   '<div class="mn">%s</div><div class="mt">%s</div></div>'
                   % (" lead" if es_lider else "", e(etq), e(num), e(pie)))
    return '<div class="month-row">%s</div>' % "".join(out)


# A partir de acá las barras van en dos columnas. Seis es donde una sola
# columna empieza a dejar media lámina de aire y a estirar cada barra a lo
# ancho de toda la hoja para decir un porcentaje. Se bajó de ocho a seis
# mirando la lámina de motivos: son siete y salían a 1.030 px cada una.
BARRAS_EN_DOS = 6


def barras(items, tope=None):
    """items: (etiqueta, valor, texto_adentro, color).

    Tres cosas que parecen detalles y no lo son:

    · Con muchas filas van en DOS COLUMNAS. Una barra de 1.030 px de ancho para
      decir «28%» es desperdicio, y encima obliga a leer doce renglones de
      arriba abajo. En dos columnas entra lo mismo en la mitad del alto.

      ⚠️ Las dos columnas comparten LA MISMA ESCALA. Si cada una se midiera
      contra su propio máximo, la primera de la derecha se vería tan larga como
      la de la izquierda con la mitad del valor: el gráfico mentiría.

    · Una barra corta NO puede llevar su número adentro: con 14 sobre 297 el
      relleno mide 30 px y el texto queda cortado en «14 ·». Debajo de cierto
      ancho el número se escribe AFUERA, al lado de la barra. El corte depende
      de cuántas columnas hay: en media lámina, un 20% ya no tiene lugar.

    · Con muchas filas la lámina se pasa de la hoja y se come el título y las
      notas, así que además van más juntas y más bajas.
    """
    if not items:
        return ""
    tope = tope or max(1, max(v for _, v, _, _ in items))
    dos = len(items) >= BARRAS_EN_DOS
    corte = 30 if dos else 16
    out = []
    for etq, val, txt, color in items:
        ancho = max(4.0, 100.0 * val / float(tope))
        afuera = ancho < corte
        out.append('<div class="bar2%s"><div class="bl">%s</div><div class="bt">'
                   '<div class="bf" style="width:%.1f%%;background:%s">'
                   '<span>%s</span></div></div></div>'
                   % (" afuera" if afuera else "", e(etq), ancho, color, e(txt)))
    if dos:
        # ⚠️ el alto de la grilla se fija acá y no en el CSS: `grid-auto-flow:
        # column` necesita saber cuántas filas tiene cada columna, y eso
        # depende de cuántos items llegaron
        filas = (len(items) + 1) // 2
        return ('<div class="bars dos" style="grid-template-rows:repeat(%d,auto)">'
                '%s</div>' % (filas, "".join(out)))
    clase = "bars densa" if len(items) > 5 else "bars"
    return '<div class="%s">%s</div>' % (clase, "".join(out))


def columnas(items):
    """La misma lista, en barras verticales. items: (etiqueta, valor, texto, color).

    Existe porque hay datos que se leen mejor parados: los días de la semana o
    los meses tienen un orden natural de izquierda a derecha, y una barra
    horizontal por día obliga a leer siete renglones para ver la forma.

    El número va ARRIBA de la columna y no adentro: una columna corta no tiene
    lugar para el número, y meterlo adentro lo corta —el mismo problema que
    tenían las barras horizontales—.
    """
    if not items:
        return ""
    tope = max(1, max(v for _, v, _, _ in items))
    out = []
    for etq, val, txt_, color in items:
        alto = max(2.0, 100.0 * val / float(tope))
        out.append('<div class="col2"><div class="cv">%s</div>'
                   '<div class="ct"><div class="cf" style="height:%.1f%%;'
                   'background:%s"></div></div><div class="cl">%s</div></div>'
                   % (e(txt_), alto, color, e(etq)))
    clase = "cols densa" if len(items) > 8 else "cols"
    return '<div class="%s">%s</div>' % (clase, "".join(out))


def tabla(items, rotulo="", unidad="Cantidad"):
    """La misma lista, pero en tabla. items: (etiqueta, valor, texto, color).

    Existe porque no todo el mundo lee una barra: para comparar catorce
    vendedores entre sí, una columna de números alineados se lee mejor que
    catorce barras. Es la MISMA lista y los MISMOS números —lo único que cambia
    es cómo se dibujan—, así que las dos vistas no pueden decir cosas
    distintas.
    """
    if not items:
        return ""
    # `unidad` puede ser una columna o varias: la tabla del equipo lleva
    # derivaciones, ventas y conversión, que es lo que se pidió ver junto.
    cabezas = list(unidad) if isinstance(unidad, (list, tuple)) else [unidad]
    # con varias columnas de números se saca la barrita del final: al lado de
    # cuatro números es ruido, y encima empuja las columnas hasta que no entran
    con_barra = len(cabezas) == 1
    tope = max(1, max(v for _, v, _, _ in (i[:4] for i in items)))
    filas = []
    for i, it in enumerate(items):
        etq, val, txt, color = it[:4]
        extras = list(it[4]) if len(it) > 4 else []
        celdas = ('<td class="tv" style="color:%s">%s</td>' % (color, e(txt)))
        for x in extras[:len(cabezas) - 1]:
            celdas += '<td class="tx">%s</td>' % e(x)
        if con_barra:
            celdas += ('<td class="tb"><i style="width:%.1f%%;background:%s">'
                       '</i></td>' % (max(3.0, 100.0 * val / float(tope)), color))
        filas.append('<tr><td class="tn">%d</td><td class="te">%s</td>%s</tr>'
                     % (i + 1, e(etq), celdas))
    ths = "".join('<th>%s</th>' % e(c) for c in cabezas)
    return ('<table class="tablita%s"><thead><tr><th></th><th>%s</th>%s%s</tr>'
            '</thead><tbody>%s</tbody></table>'
            % (" ancha" if not con_barra else "", e(rotulo or "Nombre"), ths,
               "<th></th>" if con_barra else "", "".join(filas)))


def lista(items, vista="barras", rotulo="", unidad="Cantidad",
          items_tabla=None, items_col=None):
    """La lista en sus TRES formas, con la elegida a la vista.

    Se dibujan las tres y se esconden dos. Parece un desperdicio y no lo es: el
    interruptor de la pantalla de edición cambia la vista EN EL ACTO, sin ir y
    volver al servidor a rearmar el reporte —que tarda segundos porque relee la
    planilla—. Lo que se guarda es cuál quedó puesta.

    Lo que se muestra es lo mismo con los tres dibujos: los números salen de la
    misma cuenta, así que ninguna de las vistas puede decir otra cosa. Lo único
    que cambia es el texto que entra en cada dibujo —adentro de una columna no
    entra «1.540 · 45% derivadas»—, y por eso van tres listas y no una.
    """
    if vista not in ("barras", "columnas", "tabla"):
        vista = "barras"
    dibujos = [("barras", barras(items)),
               ("columnas", columnas(items_col or items)),
               ("tabla", tabla(items_tabla or items, rotulo, unidad))]
    return "".join('<div class="lista-v" data-vista="%s"%s>%s</div>'
                   % (k, "" if k == vista else " hidden", cuerpo)
                   for k, cuerpo in dibujos)


def _base_de(*marcas):
    """La clave de la TARJETA a partir de las de su título y su texto.

    «embudo.nota1.titulo» y «embudo.nota1.texto» son la misma tarjeta:
    «embudo.nota1». Se necesita para poder sacar la tarjeta entera de un
    click en vez de tener que sacar sus dos textos por separado.
    """
    for m in marcas:
        k = getattr(m, "clave", "")
        if k and "." in k:
            return k.rsplit(".", 1)[0]
    return ""


def notas(items):
    """Las tarjetas de abajo, donde va la lectura escrita. items: (titulo, texto).

    Una tarjeta cuyo título y texto se sacaron no se dibuja: si no, quedaba un
    rectángulo vacío en el medio de la lámina. Y si queda UNA sola, se centra
    en vez de estirarse a todo el ancho —una tarjeta de 1180 px con dos
    renglones adentro se lee mal—.
    """
    out = []
    grabadas = getattr(_CTX, "notas_grabadas", None)
    for t, x in items:
        hay_t, hay_x = str(t).strip(), str(x).strip()
        if not hay_t and not hay_x:
            continue
        if grabadas is not None:
            grabadas.append((str(t), str(x)))
        base = _base_de(t, x)
        out.append('<div class="nota"%s>%s%s</div>'
                   % ((' data-nota="%s"' % base) if base else "",
                      ('<div class="nt">%s</div>' % e(t)) if hay_t else "",
                      ('<div class="nx">%s</div>' % e(x)) if hay_x else ""))
    if not out:
        return ""
    return '<div class="notas">%s</div>' % "".join(out)


def pintar(p, vista="barras"):
    """Las partes de una lámina, dibujadas como lámina —o varias— del deck.

    Existe para que el HTML y el Word no armen cada uno sus números por su
    cuenta: la lámina se calcula una vez y cada formato la dibuja como puede.

    ⚠️ UNA LISTA LARGA SE REPARTE EN VARIAS LÁMINAS. Con «todos» en el detalle
    entraban 18 vendedores o 40 campañas en una lámina de 720 px y la lista se
    derramaba por abajo: en pantalla se cortaba y en el PDF directamente no
    estaba. Medido con el navegador, entran 12 filas; de ahí sale TOPE_LISTA.

    Las láminas que siguen llevan «2 de 3» en el rótulo y NO repiten las notas:
    las notas hablan de la lista entera, así que van con la última.
    """
    if not p or not p.get("filas"):
        return ""
    paginas = _en_paginas(p)
    total = len(paginas)
    salida = []
    for i, pag in enumerate(paginas):
        ultima = i == total - 1
        kicker = p["kicker"]
        if total > 1:
            # se le pega el contador al rótulo, que es el texto más chico de la
            # lámina: en el título quedaría gritado
            kicker = "%s · %d de %d" % (str(p["kicker"]).strip() or "Lista",
                                        i + 1, total)
        salida.append(slide(
            cabeza(kicker, p["titulo"], p["bajada"]) +
            lista(pag["filas"], vista, p["columna"], p["unidad"],
                  pag["filas_t"], pag["filas_c"]) +
            (notas(p["lineas"]) if ultima else ""),
            oscuro=fondo(p["sec"]), sec=p["sec"], lista_=True))
    return "".join(salida)


def _en_paginas(p, tope=None):
    """La lista cortada en pedazos que entran en una lámina.

    Corta las tres vistas a la vez y por el mismo lugar: si la tabla se cortara
    distinto que las barras, cambiar de vista movería a la gente de página.
    """
    tope = tope or TOPE_LISTA
    filas = p["filas"]
    t = p.get("filas_t") or filas
    # para las columnas alcanza con el número pelado: adentro de una columna no
    # entra «1.540 · 45% derivadas»
    w = p.get("filas_w") or []
    c = [(filas[i][0], filas[i][1], (w[i][1] if i < len(w) else miles(filas[i][1])),
          filas[i][3]) for i in range(len(filas))]
    return [{"filas": filas[i:i + tope], "filas_t": t[i:i + tope],
             "filas_c": c[i:i + tope]}
            for i in range(0, len(filas), tope)] or [
        {"filas": [], "filas_t": [], "filas_c": []}]


def _coma(x):
    """1.5 → «1,5». Un promedio con punto decimal en un reporte en castellano
    se lee como si fuera un número entero con separador de miles."""
    return ("%.1f" % x).replace(".", ",")


# =====================================================================
#  Los slides del reporte de derivaciones
# =====================================================================
def _portada(d, titulo, nota=None):
    per = ""
    if d.get("mes_desde"):
        per = _titulo_mes(d["mes_desde"])
        if d.get("mes_hasta") and d["mes_hasta"] != d["mes_desde"]:
            per += " — " + _titulo_mes(d["mes_hasta"])
    # si el reporte se llama como su periodo («Agosto 2026»), repetirlo abajo
    # del titulo no agrega nada: se muestra una sola vez
    if per and per.strip().lower() == str(titulo).strip().lower():
        per = ""
    t = d["total"]
    return slide(
        '<div class="portada">'
        '<div class="eyebrow">%s</div>'
        '<h1 class="p-title">%s</h1>'
        '%s'
        '<div class="p-nums">'
        '<div><b>%s</b><span>consultas</span></div>'
        '<div><b>%s</b><span>derivaciones</span></div>'
        '<div><b>%s</b><span>ventas</span></div>'
        '</div>'
        '%s'
        '<div class="p-pie">Generado el %s desde la planilla de derivaciones</div>'
        '</div>' % (e(txt("portada.kicker",
                            "Muebles y Sillones · Reporte de marketing")),
                    e(titulo),
                    ('<div class="p-per">%s</div>' % e(per)) if per else "",
                    miles(t["consultas"]),
                    miles(t["derivaciones"]), miles(t["ventas"]),
                    ('<div class="p-nota">%s</div>' % e(nota)) if nota else "",
                    datetime.date.today().strftime("%d/%m/%Y")),
        oscuro=fondo("portada", True), sec="portada")


def _embudo(d, op=None):
    """Los cuatro números del embudo, y cuánto cambió cada uno.

    Lo pidió el equipo así: «en la hoja donde se muestran las consultas,
    derivaciones, no derivados y vendidos, en la parte de abajo tiene que
    mostrarse un porcentaje así sea positivo o negativo y un texto que diga
    "vs el mes pasado" o según como lo quiera medir el usuario».

    El período contra el que se compara es el que se eligió al crear el reporte
    —el mes anterior, el año pasado, ninguno—, así que el texto del pie sale de
    ahí y no está escrito a mano.
    """
    op = op or {}
    t = d["total"]
    prev = (op.get("previo") or {}).get("total") if op.get("previo") else None
    como = op.get("previo_txt") or ""
    foco = d.get("sucursal_foco") or ""
    sin_derivar = t["consultas"] - t["derivaciones"]
    sin_antes = ((prev["consultas"] - prev["derivaciones"]) if prev else None)

    # ⚠️ EL EMBUDO DE UNA SUCURSAL NO ES EL EMBUDO CHICO DE LA EMPRESA.
    # Una consulta no tiene sucursal hasta que se deriva: si nadie la atendió,
    # no es de ningún local. Así que acá las derivaciones y las ventas SÍ son
    # de la sucursal, y las consultas son las del período entero. La tercera
    # tarjeta deja de ser «sin derivar» —que es global— y pasa a ser «fueron a
    # otra sucursal», que es lo que de verdad se puede afirmar.
    if foco:
        otras = t.get("de_otra_sucursal", 0)
        cards = conv_cards([
            (txt("embudo.c1", "Consultas"), miles(t["consultas"]),
             txt("embudo.c1.pie", "entraron en el período"), "#1A1A2E", "",
             _contra(t["consultas"], prev and prev["consultas"], True, como)),
            (txt("embudo.c2", "Derivadas a %s" % foco), miles(t["derivaciones"]),
             txt("embudo.c2.pie", "las atendió esta sucursal" if len(d.get("sucursales_foco") or []) < 2
                 else "las atendieron estas sucursales"), "#2C6E8A",
             # qué parte de TODAS las derivaciones de la empresa se llevó
             pct(t["derivaciones"] / float(max(1, d.get("derivaciones_empresa") or t["derivaciones"])), 0)
             + " de las de la empresa",
             _contra(t["derivaciones"], prev and prev["derivaciones"], True, como)),
            (txt("embudo.c3", "Fueron a otra"), miles(otras),
             txt("embudo.c3.pie", "las atendió otro local"), "#8A5A2C", "", None),
            (txt("embudo.c4", "Ventas de %s" % foco), miles(t["ventas"]),
             txt("embudo.c4.pie", "cerradas por esta sucursal"), "#1A6A3A",
             pct(d["tasa_cierre"]) + " de sus derivaciones",
             _contra(t["ventas"], prev and prev["ventas"], True, como)),
        ])
        return slide(
            cabeza(txt("embudo.kicker", "El embudo de %s" % foco),
                   txt("embudo.titulo", "De la consulta a la venta"),
                   txt("embudo.bajada",
                       "Lo que recibió y cerró %s en el período" % foco)) + cards +
            notas([
                (txt("embudo.nota1.titulo", "Qué es de %s y qué no" % foco),
                 txt("embudo.nota1.texto",
                     "Las derivaciones y las ventas son de %s. Las consultas "
                     "son las del período entero: una consulta que todavía no "
                     "atendió nadie no es de ninguna sucursal, así que "
                     "repartirlas sería inventar un número."
                     % foco)),
                (txt("embudo.nota2.titulo", "La venta la cierra el vendedor"),
                 txt("embudo.nota2.texto",
                     "%s sobre %s que recibió %s: una conversión del %s."
                     % (plural(t["ventas"], "venta", "ventas"),
                        plural(t["derivaciones"], "derivación", "derivaciones"),
                        foco, pct(d["tasa_cierre"])))),
            ] + ([nota_monto(d, op)] if nota_monto(d, op) else [])),
            oscuro=fondo("embudo"), sec="embudo")

    cards = conv_cards([
        (txt("embudo.c1", "Consultas"), miles(t["consultas"]),
         txt("embudo.c1.pie", "entraron en el período"), "#1A1A2E", "",
         _contra(t["consultas"], prev and prev["consultas"], True, como)),
        (txt("embudo.c2", "Derivadas"), miles(t["derivaciones"]),
         txt("embudo.c2.pie", "llegaron a un vendedor"), "#2C6E8A",
         pct(d["tasa_derivacion"], 0) + " del total",
         _contra(t["derivaciones"], prev and prev["derivaciones"], True, como)),
        (txt("embudo.c3", "Sin derivar"), miles(sin_derivar),
         txt("embudo.c3.pie", "quedaron en marketing"), "#8A5A2C", "",
         # ⚠️ acá subir es malo: es la consulta que no llegó a nadie
         _contra(sin_derivar, sin_antes, False, como)),
        (txt("embudo.c4", "Ventas"), miles(t["ventas"]),
         txt("embudo.c4.pie", "cerradas por los vendedores"), "#1A6A3A",
         pct(d["tasa_cierre"]) + " de las derivadas",
         _contra(t["ventas"], prev and prev["ventas"], True, como)),
    ])
    return slide(
        cabeza(txt("embudo.kicker", "El embudo"),
               txt("embudo.titulo", "De la consulta a la venta"),
               txt("embudo.bajada", "Cada consulta que entra, hasta dónde llegó")) + cards +
        notas([
            (txt("embudo.nota1.titulo", "Derivar es el número de marketing"),
             txt("embudo.nota1.texto",
                 "De %s consultas, %s llegaron a un vendedor. Ese es el trabajo "
                 "del equipo: retomar el contacto y hacer que llegue a quien "
                 "cierra." % (miles(t["consultas"]), miles(t["derivaciones"])))),
            (txt("embudo.nota2.titulo", "La venta la cierra el vendedor"),
             txt("embudo.nota2.texto",
                 "%s sobre %s derivaciones. La conversión mide al "
                 "vendedor, no a marketing."
                 % (plural(t["ventas"], "venta", "ventas"),
                    miles(t["derivaciones"])))),
        ] + ([nota_monto(d, op)] if nota_monto(d, op) else [])),
        oscuro=fondo("embudo"), sec="embudo")


def _por_mes(d):
    meses = sorted(d["meses"])
    # ⚠️ Con UN SOLO mes no hay «mes a mes» que mostrar. Quedaba una tarjeta
    # negra sola, a lo ancho de toda la lámina, diciendo «AGO · 475»: ocupa una
    # hoja entera para repetir un número que el embudo ya dio, y en una
    # presentación se ve como un error. El reporte de un mes no lleva esta
    # lámina; la comparación contra el mes anterior vive en el embudo.
    if len(meses) < 2:
        return ""
    ult = meses[-6:]
    vals = [(_corto_mes(m), miles(d["meses"][m]["derivaciones"]),
             "%s consultas" % miles(d["meses"][m]["consultas"])) for m in ult]
    mejor = max(ult, key=lambda m: d["meses"][m]["derivaciones"])
    nota = []
    if len(ult) >= 2:
        a, b = d["meses"][ult[-2]]["derivaciones"], d["meses"][ult[-1]]["derivaciones"]
        dif = b - a
        signo = "más" if dif > 0 else "menos"
        nota.append((txt("meses.nota1.titulo",
                         "%s contra %s"
                         % (_titulo_mes(ult[-1]).split()[0].capitalize(),
                            _titulo_mes(ult[-2]).split()[0])),
                     txt("meses.nota1.texto",
                         "%s derivaciones %s que el mes anterior (%s vs %s)."
                         % (miles(abs(dif)), signo, miles(b), miles(a)))))
    nota.append((txt("meses.nota2.titulo", "El mejor mes del período"),
                 txt("meses.nota2.texto",
                     "%s, con %s derivaciones."
                     % (_titulo_mes(mejor).capitalize(),
                        miles(d["meses"][mejor]["derivaciones"])))))
    return slide(
        cabeza(txt("meses.kicker", "Mes a mes"),
               txt("meses.titulo", "Derivaciones por mes"),
               txt("meses.bajada",
                   "Cuántas consultas logramos poner en manos de un vendedor")) +
        month_cards(vals, lider=_corto_mes(mejor)) + notas(nota),
        oscuro=fondo("meses"), sec="meses")


def _por_sucursal(d, vista="barras"):
    sucs = sorted(d["sucursales"].items(), key=lambda x: -x[1]["derivaciones"])
    if not sucs:
        return ""
    items, filas = [], []
    for nombre, b in sucs[:5]:
        conv = b["ventas"] / float(max(1, b["derivaciones"]))
        items.append((nombre, miles(b["derivaciones"]),
                      "%s · %s" % (plural(b["ventas"], "venta", "ventas"),
                                  pct(conv)),
                      _color(nombre), ""))
        filas.append((nombre, b["derivaciones"],
                      "%s · %s" % (miles(b["derivaciones"]),
                                  plural(b["ventas"], "venta", "ventas")),
                      _color(nombre)))
    aviso = []
    if d.get("sin_ubicar"):
        cuantas = sum(d["sin_ubicar"].values())
        quienes = ", ".join(sorted(d["sin_ubicar"])[:4])
        aviso.append((txt("sucursales.nota1.titulo",
                          "Faltan ubicar %s derivaciones" % miles(cuantas)),
                      txt("sucursales.nota1.texto",
                          "Hay vendedores sin sucursal asignada (%s). No están "
                          "contados en este corte." % quienes)))
    else:
        aviso.append((txt("sucursales.nota1.titulo",
                          "Todos los vendedores están ubicados"),
                      txt("sucursales.nota1.texto",
                          "Cada derivación del período entró en alguna sucursal.")))
    destacan = [(n, b) for n, b in sucs if b.get("destaca")]
    if destacan:
        n, b = destacan[0]
        aviso.append((txt("sucursales.nota2.titulo",
                          "%s sí se sale del promedio" % n),
                      txt("sucursales.nota2.texto",
                          "%s en %s derivaciones, cuando lo esperable eran %s. "
                          "Entre sucursales la comparación sí tiene volumen para "
                          "sostenerse."
                          % (plural(b["ventas"], "venta", "ventas"),
                             miles(b["derivaciones"]),
                             miles(int(round(b["derivaciones"] * d["tasa_cierre"])))))))
    else:
        aviso.append((txt("sucursales.nota2.titulo", "De dónde sale la sucursal"),
                      txt("sucursales.nota2.texto",
                          "Del vendedor asignado, no de la columna «Sucursal» de la "
                          "planilla: hasta abril esa columna mezclaba sucursales con "
                          "provincias.")))
    return slide(
        cabeza(txt("sucursales.kicker", "Sucursales"),
               txt("sucursales.titulo", "Cómo se reparten las derivaciones"),
               txt("sucursales.bajada",
                   "Por la sucursal del vendedor que las recibió")) +
        # las dos vistas armadas, como en lista(): acá una es tarjetas y la
        # otra tabla, pero la regla es la misma —se ve el cambio al toque—
        ('<div class="lista-v" data-vista="barras"%s>%s</div>'
         '<div class="lista-v" data-vista="tabla"%s>%s</div>'
         % (" hidden" if vista == "tabla" else "", conv_cards(items),
            "" if vista == "tabla" else " hidden",
            tabla(filas, txt("sucursales.columna", "Sucursal"),
                  "Derivaciones"))) +
        notas(aviso), oscuro=fondo("sucursales"), sec="sucursales",
        lista_=True)


def partes_ranking(d, campo, titulo, sub, eyebrow, unidad, color="#2C6E8A",
                   cuantos=10, clave="equipo", con_ventas=False):
    """Cuánto le llegó a cada uno. Devuelve las partes, no el HTML.

    ⚠️ Ordena por CANTIDAD, nunca por conversión. Con `con_ventas` la tabla
    muestra además las ventas y el porcentaje de cierre —que es lo que se
    pidió ver junto—, pero el orden no cambia: con 3% de cierre y unas 90
    derivaciones por cabeza, la diferencia entre 3 y 10 ventas es azar. La
    lámina de límites lo explica; ordenar por ahí sería armar justo el ranking
    que el reporte dice que no se puede armar.
    """
    vs = [(v, b) for v, b in d["vendedores"].items() if b.get(campo)]
    vs.sort(key=lambda x: -x[1][campo])
    if not vs:
        return None

    # Las tres listas se arman juntas porque la lámina lleva las tres vistas y
    # el interruptor cambia de una a otra sin volver al servidor. En la tabla
    # el rótulo ya está en el encabezado, así que repetirlo en cada fila
    # («62 derivaciones» diez veces) es ruido.
    filas, filas_t, filas_w = [], [], []
    for i, (v, b) in enumerate(vs[:cuantos]):
        etq = titulo_de(v)[:18]
        n = b[campo]
        suc = titulo_de(b.get("sucursal"))
        un = {"derivaciones": "derivación", "enviados": "enviado"}.get(unidad, unidad) if n == 1 else unidad
        filas.append((etq, n, "%s %s" % (miles(n), un), color))
        if con_ventas:
            ven = b.get("ventas", 0)
            conv = ven / float(max(1, b.get("derivaciones", 0)))
            filas_t.append((etq, n, miles(n), color, [miles(ven), pct(conv)]))
            # el Word no tiene columnas: las ventas y la conversión van en la
            # apostilla, para que diga lo mismo que la tabla de la pantalla
            filas_w.append((etq, miles(n),
                            " · ".join(x for x in (
                                suc, plural(ven, "venta", "ventas"),
                                pct(conv)) if x)))
        else:
            filas_t.append((etq, n, miles(n), color))
            filas_w.append((etq, miles(n), suc))

    cabezas = ([unidad.capitalize(), "Ventas", "Conversión"] if con_ventas
               else unidad.capitalize())
    prim = vs[0]
    quien = titulo_de(prim[0])
    lineas = [(txt(clave + ".nota1.titulo", "Arriba de la tabla"),
               txt(clave + ".nota1.texto",
                   "%s con %s %s, sobre %s en total."
                   % (quien, miles(prim[1][campo]), unidad,
                      plural(len(vs), "persona", "personas"))))]
    if con_ventas:
        lineas.append((txt(clave + ".nota2.titulo",
                           "La conversión está para verla, no para rankear"),
                       txt(clave + ".nota2.texto",
                           "Va al lado del número que sí se puede comparar. Con "
                           "%s de cierre, la diferencia entre 3 y 10 ventas "
                           "entra dentro de lo que produce el azar — la última "
                           "lámina lo explica." % pct(d["tasa_cierre"]))))
    else:
        lineas.append((txt(clave + ".nota2.titulo",
                           "Este número sí se puede comparar"),
                       txt(clave + ".nota2.texto",
                           "Depende de lo que hace el equipo y tiene volumen "
                           "suficiente para que la diferencia signifique algo.")))
    resto = len(vs) - len(filas)
    if resto > 0:
        lineas.append((txt(clave + ".nota3.titulo", "Los que no entran"),
                       txt(clave + ".nota3.texto",
                           "Hay %s más en la lista. Se cortó acá para que el "
                           "reporte se pueda leer; con «todos» en el detalle "
                           "entran en las hojas que hagan falta."
                           % plural(resto, "persona", "personas"))))
    return {
        "sec": clave, "color": color,
        "kicker": txt(clave + ".kicker", eyebrow),
        "titulo": txt(clave + ".titulo", titulo),
        "bajada": txt(clave + ".bajada", sub),
        "columna": txt(clave + ".columna", "Vendedor"), "unidad": cabezas,
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


def partes_conteo(d, clave, eyebrow, titulo, sub, cierre, color="#2C6E8A",
                  cuantos=10, columna="Valor", extra=None):
    """Una lámina de «cuántas por X» sobre un diccionario del análisis.

    Sirve para productos, origen y medio de entrada: las tres son la misma
    forma —etiqueta y cantidad— y no hay razón para escribir tres láminas
    iguales. El corte se hace acá y no en el análisis: el análisis cuenta
    todo, la lámina decide cuánto entra.
    """
    datos = d.get(clave) or {}
    items = sorted(((k, v) for k, v in datos.items() if k and v),
                   key=lambda x: -x[1])
    if not items:
        return None
    total = sum(datos.values()) or 1
    top = items[:cuantos]
    filas, filas_t, filas_w = [], [], []
    for k, v in top:
        etq = _acortar(titulo_de(k), 30)
        parte = pct(v / float(total), 0)
        filas.append((etq, v, "%s · %s" % (miles(v), parte), color))
        filas_t.append((etq, v, "%s · %s" % (miles(v), parte), color))
        filas_w.append((etq, miles(v), parte))
    resto = len(items) - len(top)
    lineas = [(txt(clave + ".nota1.titulo", cierre[0]),
               txt(clave + ".nota1.texto", cierre[1] % {
                   "primero": titulo_de(top[0][0]),
                   "cuantas": miles(top[0][1]),
                   "parte": pct(top[0][1] / float(total), 0),
                   "distintos": miles(len(items)),
               }))]
    if extra:
        lineas.append(extra)
    if resto > 0:
        lineas.append((txt(clave + ".nota_resto.titulo",
                           "Lo que no entra en la lámina"),
                       txt(clave + ".nota_resto.texto",
                           "Hay %s valores más, que juntan %s consultas. Se "
                           "cortó acá para que se pueda leer."
                           % (miles(resto),
                              miles(sum(v for _, v in items[cuantos:]))))))
    return {
        "sec": clave, "color": color,
        "kicker": txt(clave + ".kicker", eyebrow),
        "titulo": txt(clave + ".titulo", titulo),
        "bajada": txt(clave + ".bajada", sub),
        "columna": txt(clave + ".columna", columna), "unidad": "Consultas",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


def partes_productos(d, cuantos=10):
    return partes_conteo(
        d, "productos", "Qué consultan", "Los productos más preguntados",
        "Qué pidió la gente que escribió, ordenado por cantidad",
        ("El más pedido",
         "%(primero)s con %(cuantas)s consultas, el %(parte)s de todo lo que "
         "se pregunta. En total se nombraron %(distintos)s productos distintos."),
        cuantos=cuantos, columna="Producto")


def partes_origenes(d, cuantos=10):
    """Qué campaña trajo cada consulta — y de cuántas no lo sabemos.

    Lo segundo lo preguntó el equipo aparte («¿de cuántos orígenes no sabemos
    de dónde vienen?») y va como nota y no como lámina propia porque es un
    número solo. Pero es el número que decide cuánto vale la lámina: los
    porcentajes de arriba son sobre las consultas que SÍ tienen origen, así que
    hay que decir sobre cuántas se está calculando.
    """
    return partes_conteo(
        d, "origenes", "De dónde vienen", "Qué campaña las trajo",
        "El origen que quedó anotado en cada consulta",
        ("La que más trae",
         "%(primero)s con %(cuantas)s consultas, el %(parte)s de las que "
         "tienen origen. Hay %(distintos)s orígenes cargados."),
        color="#7A4FA3", cuantos=cuantos, columna="Origen",
        extra=nota_sin_origen(d))


def laminas_anuncios(d):
    """«¿Por qué tipo de anuncio llegaron?» (27-sep-2026). Dos listas: por qué
    puerta entraron (anuncios, web, mailing…) y el detalle de cada anuncio.
    En el reporte de una sucursal se cuentan sus derivaciones."""
    from .derivaciones import GRUPOS_ORIGEN
    foco = d.get("sucursal_foco") or ""
    campo = "derivaciones" if foco else "consultas"
    nombre = dict(GRUPOS_ORIGEN)
    gr = [(k, v) for k, v in (d.get("grupos_origen") or {}).items() if v.get(campo)]
    out = []
    if gr:
        gr.sort(key=lambda x: -x[1][campo])
        tot = sum(v[campo] for _, v in gr)
        filas, filas_t, filas_w = [], [], []
        for k, v in gr:
            etq = nombre.get(k, k)
            color = "#7A4FA3" if k == "anuncio" else "#2C6E8A"
            n = v[campo]
            filas.append((etq, n, "%s · %s" % (miles(n), pct(n / float(tot), 0)), color))
            extra = [miles(v["ventas"])] if foco else [miles(v["derivaciones"]), miles(v["ventas"])]
            filas_t.append((etq, n, miles(n), color, extra))
            filas_w.append((etq, miles(n), pct(n / float(tot), 0)))
        an = (d.get("grupos_origen") or {}).get("anuncio") or {}
        out.append({
            "sec": "anuncios", "color": "#7A4FA3",
            "kicker": txt("anuncios.grupos.kicker", "Por dónde entraron"),
            "titulo": txt("anuncios.grupos.titulo", "Anuncios, web, mailing…"),
            "bajada": txt("anuncios.grupos.bajada",
                          ("Las derivaciones de %s, según su origen" % foco) if foco
                          else "Las consultas del período, según su origen"),
            "columna": txt("anuncios.columna", "Origen"),
            "unidad": (["Derivadas", "Ventas"] if foco else ["Consultas", "Derivadas", "Ventas"]),
            "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
            "lineas": [
                (txt("anuncios.nota1.titulo", "Lo que traen los anuncios"),
                 txt("anuncios.nota1.texto",
                     "%s de %s (%s) llegaron por un anuncio."
                     % (miles(an.get(campo, 0)), miles(tot),
                        pct(an.get(campo, 0) / float(tot), 0)))),
                (txt("anuncios.nota2.titulo", "Qué cuenta como anuncio"),
                 txt("anuncios.nota2.texto",
                     "Todo origen que no sea web, mailing, redes sin pauta, "
                     "influencers, sucursal, teléfono u otros medios. Las "
                     "consultas sin origen cargado no entran.")),
            ],
        })
    ans = [v for v in (d.get("anuncios") or {}).values() if v.get(campo)]
    if ans:
        ans.sort(key=lambda x: (-x[campo], x["nombre"]))
        tot = sum(x[campo] for x in ans)
        filas, filas_t, filas_w = [], [], []
        for x in ans:
            etq = _acortar(titulo_de(x["nombre"]), 30)
            n = x[campo]
            filas.append((etq, n, "%s · %s" % (miles(n), pct(n / float(tot), 0)), "#7A4FA3"))
            extra = [miles(x["ventas"])] if foco else [miles(x["derivaciones"]), miles(x["ventas"])]
            filas_t.append((etq, n, miles(n), "#7A4FA3", extra))
            filas_w.append((etq, miles(n), "%s · %s" % (
                pct(n / float(tot), 0), plural(x["ventas"], "venta", "ventas"))))
        p = ans[0]
        out.append({
            "sec": "anuncios", "color": "#7A4FA3",
            "kicker": txt("anuncios.detalle.kicker", "Los anuncios"),
            "titulo": txt("anuncios.detalle.titulo", "Qué anuncio trajo cada consulta"),
            "bajada": txt("anuncios.detalle.bajada",
                          "Cada anuncio, con lo que se derivó y lo que se vendió"),
            "columna": txt("anuncios.columna2", "Anuncio"),
            "unidad": (["Derivadas", "Ventas"] if foco else ["Consultas", "Derivadas", "Ventas"]),
            "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
            "lineas": [
                (txt("anuncios.nota3.titulo", "El que más trajo"),
                 txt("anuncios.nota3.texto",
                     "%s, con %s de %s que llegaron por anuncios (%s)."
                     % (titulo_de(p["nombre"]), miles(p[campo]), miles(tot),
                        pct(p[campo] / float(tot), 0)))),
            ],
        })
    return out


def nota_sin_origen(d):
    """«¿De cuántos orígenes no sabemos de dónde vienen?» — la pregunta del
    equipo, en una nota.

    Va acá afuera y no adentro de la lámina porque la escriben los dos
    formatos: si la calculara cada uno por su lado, el PDF y el Word podrían
    terminar diciendo porcentajes distintos del mismo dato.
    """
    sin = d.get("sin_origen") or 0
    if not sin:
        return None
    con = sum((d.get("origenes") or {}).values())
    return (txt("origenes.nota_sin.titulo",
                "De estas no sabemos de dónde vienen"),
            txt("origenes.nota_sin.texto",
                "%s entraron sin origen cargado: %s de todo lo que llegó. "
                "No están acá arriba — los porcentajes de la lámina son "
                "sobre las %s que sí lo tienen."
                % (plural(sin, "consulta", "consultas"),
                   pct(sin / float(max(1, sin + con)), 0), miles(con))))


def partes_medios(d, cuantos=10):
    return partes_conteo(
        d, "medios", "Por dónde entran", "El medio de entrada",
        "Por qué canal llegó la consulta",
        ("El canal principal",
         "%(primero)s con %(cuantas)s consultas, el %(parte)s del total."),
        color="#2C7A6E", cuantos=cuantos, columna="Medio")


def partes_motivos(d):
    """Por qué se pierden. Es la Respuesta Final de los que no compraron."""
    mo = sorted(d["motivos"].items(), key=lambda x: -x[1])
    mo = [(k, v) for k, v in mo if not k.startswith("REALIZO LA COMPRA")][:7]
    if not mo:
        return None
    tot = sum(v for _, v in mo)
    filas, filas_t, filas_w = [], [], []
    for i, (k, v) in enumerate(mo):
        etq = _acortar(k.capitalize(), 42)
        color = RAMPA_PERDIDA[min(i, len(RAMPA_PERDIDA) - 1)]
        filas.append((etq, v, miles(v), color))
        filas_t.append((etq, v, miles(v), color))
        filas_w.append((etq, miles(v), pct(v / float(max(1, tot)), 0)))
    top = mo[0]
    return {
        "sec": "motivos", "color": "#8A2C2C",
        "kicker": txt("motivos.kicker", "Por qué se pierden"),
        "titulo": txt("motivos.titulo", "Los motivos que quedaron registrados"),
        "bajada": txt("motivos.bajada",
                      "Respuesta final de los clientes que no compraron"),
        "columna": txt("motivos.columna", "Motivo"), "unidad": "Casos",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": [
            (txt("motivos.nota1.titulo", "El motivo más común, lejos"),
             txt("motivos.nota1.texto",
                 "«%s» con %s casos, el %s de los motivos registrados."
                 % (top[0].capitalize()[:52], miles(top[1]),
                    pct(top[1] / float(max(1, tot)), 0)))),
            (txt("motivos.nota2.titulo", "Se unificaron las formas de escribirlo"),
             txt("motivos.nota2.texto",
                 "El mismo motivo aparecía escrito de varias maneras en la "
                 "planilla; acá están sumados.")),
        ],
    }


DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes",
               "sábado", "domingo"]


def partes_ritmo(d):
    """Cuántas consultas entran por día y qué días entran.

    Son dos preguntas del equipo puestas en una lámina porque salen de la
    misma cuenta: «¿cuántas derivaciones se realizan por día, un promedio?» y
    «¿cuáles son los días que se reciben más consultas?».

    ⚠️ El promedio es sobre los días QUE TUVIERON MOVIMIENTO, no sobre los del
    calendario. Dividir por los días corridos mete adentro los feriados y los
    días que la planilla no se cargó, y baja el número sin que eso signifique
    nada.

    Lo que hay que mirar no es qué día entra más —eso lo maneja la pauta— sino
    la parte que se llega a derivar. Un día con muchas consultas y pocas
    derivaciones es un día que se está perdiendo.
    """
    ds = d.get("dias_semana") or {}
    dias = d.get("dias_con_movimiento") or 0
    tot_c = sum(v["consultas"] for v in ds.values())
    if not tot_c or not dias:
        return None
    tot_d = sum(v["derivaciones"] for v in ds.values())

    # De lunes a viernes: es la vara contra la que se mide el finde. Sin esto
    # la lámina diría «el sábado se deriva poco» sin decir poco respecto de qué.
    habil = [ds[i] for i in range(5) if (ds.get(i) or {}).get("consultas")]
    c_habil = sum(x["consultas"] for x in habil)
    tasa_habil = sum(x["derivaciones"] for x in habil) / float(max(1, c_habil))

    filas, filas_t, filas_w, flojo = [], [], [], None
    for i, nombre in enumerate(DIAS_SEMANA):
        v = ds.get(i) or {}
        c = v.get("consultas", 0)
        if not c:
            continue
        der = v.get("derivaciones", 0)
        tasa = der / float(c)
        # se pinta distinto el día del fin de semana que se deriva mucho menos
        # que uno hábil: es lo único de esta lámina sobre lo que se puede
        # hacer algo
        cae = i >= 5 and tasa < tasa_habil * 0.8
        if cae and (flojo is None or tasa < flojo[3]):
            flojo = (nombre, c, der, tasa)
        color = "#8A5A2C" if cae else "#2C6E8A"
        cola = "%s · %s" % (plural(der, "derivación", "derivaciones"),
                            pct(tasa, 0))
        filas.append((nombre.title(), c,
                      "%s · %s derivadas" % (miles(c), pct(tasa, 0)), color))
        filas_t.append((nombre.title(), c, "%s   (%s)" % (miles(c), cola),
                        color))
        filas_w.append((nombre.title(), miles(c), cola))

    pico = d.get("dia_mas_cargado")
    cuando = _dia_mes(pico["fecha"]) if pico else ""
    lineas = [(txt("ritmo.nota1.titulo", "Cuánto entra por día"),
               txt("ritmo.nota1.texto",
                   "Sobre %s con movimiento entran %s consultas por día y se "
                   "derivan %s.%s"
                   % (plural(dias, "día", "días"), _coma(tot_c / float(dias)),
                      _coma(tot_d / float(dias)),
                      (" El día más cargado fue el %s, con %s."
                       % (cuando, plural(pico["consultas"], "consulta",
                                         "consultas"))) if pico else "")))]
    if flojo:
        nombre, c, der, tasa = flojo
        medio = c_habil / float(max(1, len(habil)))
        lineas.append((txt("ritmo.nota2.titulo",
                           "El %s entra y no se deriva" % nombre),
                       txt("ritmo.nota2.texto",
                           "El %s entran %s y se derivan %s: el %s, contra el "
                           "%s de lunes a viernes. %s"
                           % (nombre, plural(c, "consulta", "consultas"),
                              miles(der), pct(tasa, 0), pct(tasa_habil, 0),
                              ("Y no es que entre menos: entra casi lo mismo "
                               "que un día de semana."
                               if c >= medio * 0.75 else
                               "Entra menos que un día de semana, y además se "
                               "deriva menos.")))))
    return {
        "sec": "ritmo", "color": "#2C6E8A",
        "kicker": txt("ritmo.kicker", "El ritmo"),
        "titulo": txt("ritmo.titulo", "Cuánto entra por día, y qué días"),
        "bajada": txt("ritmo.bajada",
                      "Consultas por día de la semana, y qué parte se derivó"),
        "columna": txt("ritmo.columna", "Día"), "unidad": "Consultas",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


def partes_prod_origen(d, cuantos=10):
    """De qué campaña viene cada producto.

    Es el cruce que pidió el equipo con esas palabras: «¿de qué origen vienen
    más las consultas de sillones?». Las láminas de productos y de orígenes por
    separado dicen cuánto hay de cada cosa; esta dice qué trajo qué, que es
    otra pregunta —y la que sirve para decidir dónde poner la pauta—.

    Cuando lo que más trae un producto es una consulta sin origen cargado, la
    fila se pinta distinto: ahí no hay nada que aprender, hay algo que cargar.
    """
    from . import derivaciones as DV
    po = d.get("producto_origen") or {}
    items = sorted(((k, v) for k, v in po.items() if k and v),
                   key=lambda x: -sum(x[1].values()))
    if not items:
        return None
    top = items[:min(cuantos, TOPE_LISTA)]
    filas, filas_t, filas_w, huerfanos = [], [], [], 0
    for prod, orig in top:
        n = sum(orig.values())
        cual, cuantas = max(orig.items(), key=lambda x: (x[1], x[0]))
        vacio = cual == DV.SIN_ORIGEN
        if vacio:
            huerfanos += 1
        nombre = cual if vacio else titulo_de(cual)  # el centinela va como está
        color = "#8A5A2C" if vacio else "#7A4FA3"
        parte = pct(cuantas / float(n), 0)
        etq = _acortar(titulo_de(prod), 28)
        # adentro de la barra el nombre de la campaña va CORTO: «Promo
        # Esquineros Y Sillo» cortado a lo bruto se lee como un error de la
        # herramienta. En la tabla y en el Word, que tienen ancho, va entero.
        filas.append((etq, n, "%s · %s %s" % (miles(n), parte,
                                              _acortar(nombre)), color))
        filas_t.append((etq, n, "%s   (%s · %s)" % (miles(n), nombre, parte),
                        color))
        filas_w.append((etq, miles(n), "%s · %s" % (nombre, parte)))

    prod, orig = top[0]
    n = sum(orig.values())
    cual, cuantas = max(orig.items(), key=lambda x: (x[1], x[0]))
    lineas = [(txt("prod_origen.nota1.titulo", "El más consultado"),
               txt("prod_origen.nota1.texto",
                   "%s junta %s, y el %s de esas viene de %s."
                   % (titulo_de(prod), plural(n, "consulta", "consultas"),
                      pct(cuantas / float(n), 0), titulo_de(cual))))]
    if huerfanos:
        lineas.append((txt("prod_origen.nota2.titulo", "Los que no se sabe"),
                       txt("prod_origen.nota2.texto",
                           ("De uno de los productos de arriba, lo que más lo "
                            "trae es una consulta sin origen cargado. De ese "
                            "no se puede decir qué campaña lo mueve: hay que "
                            "cargar el origen para saberlo."
                            if huerfanos == 1 else
                            "De %d de los productos de arriba, lo que más los "
                            "trae es una consulta sin origen cargado. De esos "
                            "no se puede decir qué campaña los mueve: hay que "
                            "cargar el origen para saberlo." % huerfanos))))
    return {
        "sec": "prod_origen", "color": "#7A4FA3",
        "kicker": txt("prod_origen.kicker", "Qué trae qué"),
        "titulo": txt("prod_origen.titulo",
                      "De qué campaña viene cada producto"),
        "bajada": txt("prod_origen.bajada",
                      "Cada producto con la campaña que más consultas le trae"),
        "columna": txt("prod_origen.columna", "Producto"),
        "unidad": "Consultas · de dónde",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


def partes_podio(d, cuantos=4):
    """Los que más cerraron, para felicitarlos.

    Lo pidió el equipo así: «un ranking, tipo como para felicitarlos, los
    primeros cuatro que tienen mejor venta y mejor conversión».

    ⚠️ Ordena por VENTAS, no por conversión, y la lámina lo dice. La conversión
    sobre pocos casos se mueve sola: quien recibió 10 y cerró 2 saca 20%, y el
    mes que viene recibe 40 y cierra 2 y saca 5% sin haber hecho nada distinto.
    Las ventas son lo que la persona efectivamente hizo. La conversión va al
    lado, que para eso sirve: para mirar, no para ordenar.
    """
    vs = [(v, b) for v, b in d["vendedores"].items() if b.get("ventas")]
    if not vs:
        return None
    def conv(b):
        return b["ventas"] / float(max(1, b["derivaciones"]))
    vs.sort(key=lambda x: (-x[1]["ventas"], -conv(x[1]), x[0]))
    top = vs[:max(1, min(cuantos, 6))]
    filas, filas_t, filas_w = [], [], []
    ORO = ["#8A6B2C", "#6E7A85", "#7A5A3A", "#2C6E8A", "#2C6E8A", "#2C6E8A"]
    for i, (v, b) in enumerate(top):
        suc = titulo_de(b.get("sucursal"))
        cola = "%s · %s" % (pct(conv(b)), suc or "sin sucursal")
        filas.append(("%dº · %s" % (i + 1, titulo_de(v)), b["ventas"],
                      "%s · %s" % (plural(b["ventas"], "venta", "ventas"),
                                   pct(conv(b))), ORO[i]))
        filas_t.append(("%dº · %s" % (i + 1, titulo_de(v)), b["ventas"],
                        miles(b["ventas"]), ORO[i], [pct(conv(b)), suc]))
        filas_w.append(("%dº · %s" % (i + 1, titulo_de(v)), miles(b["ventas"]),
                        cola))
    primero = top[0]
    return {
        "sec": "podio", "color": "#8A6B2C",
        "kicker": txt("podio.kicker", "Para felicitar"),
        "titulo": txt("podio.titulo", "Los que más cerraron en el período"),
        "bajada": txt("podio.bajada",
                      "Ordenados por ventas, con su conversión al lado"),
        "columna": txt("podio.columna", "Vendedor"),
        "unidad": ["Ventas", "Conversión", "Sucursal"],
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": [
            (txt("podio.nota1.titulo", "El primero del período"),
             txt("podio.nota1.texto",
                 "%s con %s sobre %s, una conversión de %s."
                 % (titulo_de(primero[0]),
                    plural(primero[1]["ventas"], "venta", "ventas"),
                    plural(primero[1]["derivaciones"], "derivación",
                           "derivaciones"),
                    pct(primero[1]["ventas"] /
                        float(max(1, primero[1]["derivaciones"])))))),
            (txt("podio.nota2.titulo", "Cómo leer este podio"),
             txt("podio.nota2.texto",
                 "Está ordenado por ventas, que es lo que cada uno hizo. Con "
                 "los volúmenes de un mes, el orden de estos cuatro se mueve "
                 "solo de un período a otro: sirve para reconocer el mes, no "
                 "para decir quién vende mejor.")),
        ],
    }


def partes_zonas(d):
    """De dónde viene la clientela, y qué cierra cada origen.

    Es la lámina que contesta lo que preguntó el equipo: «la derivación que
    cerró el vendedor, ¿es de su zona o del interior?». Y el número que aparece
    es fuerte: lo de la zona cierra diez veces más que lo de lejos.
    """
    z = d.get("zonas") or {}
    tot = sum(v["derivaciones"] for v in z.values())
    if not tot:
        return None
    from . import zonas as Z
    filas, filas_t, filas_w = [], [], []
    COLOR = {"propia": "#1A6A3A", "cerca": "#2C6E8A", "amplia": "#7A7A5A",
             "lejos": "#8A5A2C", "interior": "#8A2C2C"}
    for k, rot in Z.CATEGORIAS:
        n = z.get(k, {}).get("derivaciones", 0)
        if not n:
            continue
        v = z[k]["ventas"]
        cola = "%s · %s" % (plural(v, "venta", "ventas"), pct(v / float(n)))
        filas.append((rot, n, "%s · %s" % (miles(n), pct(n / float(tot), 0)),
                      COLOR[k]))
        filas_t.append((rot, n, "%s   (%s)" % (miles(n), cola), COLOR[k]))
        filas_w.append((rot, miles(n), cola))

    # ⚠️ «amplia» va del lado de LEJOS para esta cuenta, aunque se le atribuya a
    # la sucursal. No es una decisión de criterio: cerró 0 de 154. Ponerla del
    # lado de la zona diría que la zona cierra peor de lo que cierra.
    zona = (z.get("propia", {}).get("derivaciones", 0)
            + z.get("cerca", {}).get("derivaciones", 0))
    zona_v = (z.get("propia", {}).get("ventas", 0)
              + z.get("cerca", {}).get("ventas", 0))
    lejos = (z.get("lejos", {}).get("derivaciones", 0)
             + z.get("interior", {}).get("derivaciones", 0)
             + z.get("amplia", {}).get("derivaciones", 0))
    lejos_v = (z.get("lejos", {}).get("ventas", 0)
               + z.get("interior", {}).get("ventas", 0)
               + z.get("amplia", {}).get("ventas", 0))
    tz = zona_v / float(max(1, zona))
    tl = lejos_v / float(max(1, lejos))
    cuantas = ("%.0f veces" % (tz / tl)) if tl else "muchísimas veces"

    lineas = [(txt("zonas.nota1.titulo", "Lo de la zona es lo que cierra"),
               txt("zonas.nota1.texto",
                   "%s de la zona dieron %s (%s). Las %s de lejos dieron %s "
                   "(%s): %s menos."
                   % (plural(zona, "derivación", "derivaciones"),
                      plural(zona_v, "venta", "ventas"), pct(tz),
                      miles(lejos), plural(lejos_v, "venta", "ventas"),
                      pct(tl), cuantas)))]
    sin = d.get("zonas_sin_localidad") or 0
    if sin:
        # ⚠️ Cuánto pesa lo que falta se CALCULA. La frase decía «es casi la
        # mitad» siempre, escrita el día que efectivamente lo era; en un mes
        # con la localidad bien cargada el reporte se desmentía solo.
        parte = sin / float(max(1, sin + tot))
        if parte >= 0.35:
            cuanto = ("Es %s de las derivaciones: el número es sólido, pero "
                      "para que sea completo hay que cargar la localidad "
                      "siempre." % pct(parte, 0))
        elif parte >= 0.12:
            cuanto = ("Es %s de las derivaciones: no cambia la lectura, pero "
                      "conviene cargar la localidad siempre." % pct(parte, 0))
        else:
            cuanto = ("Es %s de las derivaciones, así que la lectura de arriba "
                      "no se mueve." % pct(parte, 0))
        lineas.append((txt("zonas.nota2.titulo", "Ojo con esta lámina"),
                       txt("zonas.nota2.texto",
                           "%s no %s la localidad cargada y %s afuera de este "
                           "corte. %s"
                           % (plural(sin, "derivación", "derivaciones"),
                              "tiene" if sin == 1 else "tienen",
                              "queda" if sin == 1 else "quedan", cuanto))))
    return {
        "sec": "zonas", "color": "#1A6A3A",
        "kicker": txt("zonas.kicker", "De dónde viene"),
        "titulo": txt("zonas.titulo", "De la zona del local, o de lejos"),
        "bajada": txt("zonas.bajada",
                      "Cada derivación medida contra la sucursal del vendedor "
                      "que la atendió"),
        "columna": txt("zonas.columna", "Procedencia"),
        "unidad": "Derivaciones",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


def partes_provincias(d, cuantos=10):
    """El interior del país: de qué provincias llegan las consultas.

    Se pidió aparte de la lámina anterior porque son dos preguntas distintas:
    una es «cuánto de lo que atiendo es de lejos» y esta es «de dónde
    exactamente». El equipo reparte el interior entre vendedores de distintas
    sucursales, así que acá no hay una sucursal a la que atribuirlo.
    """
    pr = d.get("zonas_provincias") or {}
    items = sorted(pr.items(), key=lambda x: -x[1]["derivaciones"])
    if not items:
        return None
    tot = sum(v["derivaciones"] for v in pr.values())
    ven = sum(v["ventas"] for v in pr.values())
    top = items[:cuantos]
    filas = [(k, v["derivaciones"],
              "%s · %s" % (miles(v["derivaciones"]),
                           pct(v["derivaciones"] / float(tot), 0)), "#8A2C2C")
             for k, v in top]
    filas_t = [(k, v["derivaciones"], miles(v["derivaciones"]), "#8A2C2C")
               for k, v in top]
    filas_w = [(k, miles(v["derivaciones"]),
                pct(v["derivaciones"] / float(tot), 0)) for k, v in top]
    resto = len(items) - len(top)
    empate = len(items) > 1 and items[0][1]["derivaciones"] == items[1][1]["derivaciones"]
    lineas = [(txt("provincias.nota1.titulo", "De cuántos lugares"),
               txt("provincias.nota1.texto",
                   "%s, repartidas entre %s. Ninguna provincia se despega del resto."
                   % (plural(tot, "consulta", "consultas"),
                      plural(len(items), "provincia", "provincias"))))
              ] if empate else [(txt("provincias.nota1.titulo", "La que más consulta"),
               txt("provincias.nota1.texto",
                   "%s con %s, el %s de todo lo que llega del interior. En "
                   "total escribieron desde %s."
                   % (top[0][0],
                      plural(top[0][1]["derivaciones"], "consulta", "consultas"),
                      pct(top[0][1]["derivaciones"] / float(tot), 0),
                      plural(len(items), "provincia", "provincias"))))]
    foco = d.get("sucursal_foco") or ""
    if foco:
        lineas.append((txt("provincias.nota2.titulo", "Lo que recibió %s del interior" % foco),
                       txt("provincias.nota2.texto",
                           "%s de otras provincias, que dieron %s (%s). Cuentan "
                           "solo las que tienen la Localidad cargada: el número "
                           "real puede ser mayor."
                           % (plural(tot, "derivación", "derivaciones"),
                              plural(ven, "venta", "ventas"),
                              pct(ven / float(max(1, tot)))))))
    else:
        lineas.append((txt("provincias.nota2.titulo", "Cuánto cierra el interior"),
                       txt("provincias.nota2.texto",
                           "%s del interior dieron %s (%s). Se reparten entre "
                           "vendedores de distintas sucursales, así que no son de "
                           "ninguna en particular."
                           % (plural(tot, "derivación", "derivaciones"),
                              plural(ven, "venta", "ventas"),
                              pct(ven / float(max(1, tot)))))))
    if resto > 0:
        lineas.append((txt("provincias.nota3.titulo", "Las que no entran"),
                       txt("provincias.nota3.texto",
                           "Hay %s más, con %s entre todas."
                           % (plural(resto, "provincia", "provincias"),
                              plural(sum(v["derivaciones"] for _, v in items[cuantos:]),
                                     "consulta", "consultas")))))
    return {
        "sec": "provincias", "color": "#8A2C2C",
        "kicker": txt("provincias.kicker", "El interior del país"),
        "titulo": txt("provincias.titulo", "De qué provincias nos escriben"),
        "bajada": txt("provincias.bajada",
                      ("Las derivaciones de otras provincias que recibió %s" % d["sucursal_foco"])
                      if d.get("sucursal_foco") else
                      "Consultas de fuera de Buenos Aires, donde no hay local"),
        "columna": txt("provincias.columna", "Provincia"),
        "unidad": "Consultas",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas[:3],
    }


def partes_reparto(d, cuantos=10):
    """Quién recibe más consultas del interior del país.

    Lo pidió el equipo así: «que sean los vendedores que reciben más consultas
    de las distintas provincias». O sea que el orden es por CANTIDAD del
    interior, no por el bulto de todo lo lejano —que en Buenos Aires está
    dominado por «zona norte» y «zona oeste» y pondría arriba a gente que casi
    no recibe del interior—.

    Al lado va de cuántas provincias distintas le llega: no es lo mismo recibir
    diez consultas de Córdoba que diez de diez lugares. Y va la parte de su
    cartera que representa, porque comparar a alguien de 476 derivaciones con
    alguien de 42 por número pelado no dice nada.

    ⚠️ Importa por lo que muestra la lámina de zonas: el interior cierra 0,8%.
    Repartirlo NO es repartir trabajo parejo — es repartir trabajo que casi no
    cierra. Por eso conviene mirar esta ANTES de comparar conversiones.
    """
    vs = [(v, b) for v, b in d["vendedores"].items() if b.get("provincias")]
    if not vs:
        return None
    inter = lambda b: sum(b["provincias"].values())        # noqa: E731
    vs.sort(key=lambda x: (-inter(x[1]), x[0]))
    top = vs[:min(cuantos, TOPE_LISTA)]

    tot = sum(inter(b) for _, b in vs)
    medio = tot / float(max(1, len(vs)))

    filas, filas_t, filas_w = [], [], []
    for i, (v, b) in enumerate(top):
        n = inter(b)
        cuantas_prov = plural(len(b["provincias"]), "provincia", "provincias")
        suyo = sum(b.get("zonas", {}).values())
        parte = pct(n / float(max(1, suyo)), 0)
        etq = titulo_de(v)
        color = "#8A2C2C" if n > medio * 1.6 else "#2C6E8A"
        cola = "de %s · %s de lo suyo" % (cuantas_prov, parte)
        filas.append((etq, n, "%s · de %s" % (miles(n), cuantas_prov), color))
        filas_t.append((etq, n, "%s   (%s)" % (miles(n), cola), color))
        filas_w.append((etq, miles(n), cola))

    primero = top[0]
    lineas = [(txt("reparto.nota1.titulo", "Quién recibe más del interior"),
               txt("reparto.nota1.texto",
                   "%s con %s de %s, sobre %s repartidas entre %d personas. El "
                   "promedio es %s por cabeza."
                   % (titulo_de(primero[0]),
                      plural(inter(primero[1]), "consulta", "consultas"),
                      plural(len(primero[1]["provincias"]), "provincia",
                             "provincias"),
                      plural(tot, "consulta", "consultas"), len(vs),
                      _coma(medio))))]
    lineas.append((txt("reparto.nota2.titulo", "Por qué mirar esto"),
                   txt("reparto.nota2.texto",
                       "El interior cierra %s. No es una lámina sobre cómo "
                       "vende cada uno: es sobre qué le llega. Antes de "
                       "comparar conversiones, mirá esta."
                       % pct(_cierre_interior(d)))))
    return {
        "sec": "reparto", "color": "#2C6E8A",
        "kicker": txt("reparto.kicker", "El reparto del interior"),
        "titulo": txt("reparto.titulo",
                      "Quién atiende las consultas de más lejos"),
        "bajada": txt("reparto.bajada",
                      "Consultas de otras provincias que recibió cada vendedor"),
        "columna": txt("reparto.columna", "Vendedor"), "unidad": "Del interior",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


# De qué color va cada patrón: lo que se cayó en silencio, lo que se cerró
# por plata, lo que se vendió y lo que sigue abierto.
_COLOR_PATRON = {
    "precio_silencio": "#8A2C2C", "nunca": "#8A2C2C", "nunca_plantilla": "#8A2C2C",
    "prometio": "#8A2C2C", "presupuesto_ya": "#8A5A2C", "presupuesto_luego": "#8A5A2C",
    "compro": "#1A6A3A", "compro_prometio": "#1A6A3A", "proceso": "#8A8A8A",
}


def partes_patrones(d):
    """Cómo se comportaron los clientes, leyendo juntos los seguimientos y la
    respuesta final (ver derivaciones.PATRONES). Cada cliente cae en uno.

    Pedido del usuario (27-sep-2026): «no digo que mostremos cada paso, sino
    una evaluación de patrones de las personas, de sus reacciones».
    """
    from .derivaciones import PATRONES
    pat = d.get("patrones") or {}
    tot = sum(pat.values())
    if not tot:
        return None
    nombre = {k: n for k, n, _ in PATRONES}
    # «Todavía en proceso» no es un comportamiento todavía: va en una nota y no
    # en las barras. Y las dos de «Compró» van juntas, con el detalle al lado:
    # así la lista entra en una sola lámina.
    en_proceso = pat.get("proceso", 0)
    compras = pat.get("compro", 0) + pat.get("compro_prometio", 0)
    items = [(k, v) for k, v in pat.items()
             if v and k not in ("proceso", "compro", "compro_prometio")]
    if compras:
        items.append(("compro", compras))
    items.sort(key=lambda x: -x[1])
    filas, filas_t, filas_w = [], [], []
    for k, v in items:
        etq = txt("patrones.%s" % k, nombre.get(k, k))
        color = _COLOR_PATRON.get(k, "#2C6E8A")
        cola = ""
        if k == "compro" and pat.get("compro_prometio"):
            cola = " (%s después de prometer pasar)" % miles(pat["compro_prometio"])
        filas.append((etq, v, "%s · %s%s" % (miles(v), pct(v / float(tot), 0), cola), color))
        filas_t.append((etq, v, "%s   (%s)" % (miles(v), pct(v / float(tot), 0)), color))
        filas_w.append((etq, miles(v), pct(v / float(tot), 0)))
    silencio = sum(pat.get(k, 0) for k in ("precio_silencio", "nunca", "nunca_plantilla", "prometio"))
    plata_ = sum(pat.get(k, 0) for k in ("presupuesto_ya", "presupuesto_luego"))
    foco = d.get("sucursal_foco") or ""
    de_quien = ("los clientes derivados a %s" % foco) if foco else "los clientes con seguimiento"
    lineas = [
        (txt("patrones.nota1.titulo", "Los que se fueron en silencio"),
         txt("patrones.nota1.texto",
             "%s de %s (%s) dejaron de contestar: recibieron el precio, "
             "prometieron pasar o nunca respondieron, ni a la plantilla."
             % (miles(silencio), miles(tot), pct(silencio / float(tot), 0)))),
        (txt("patrones.nota2.titulo", "Fuera de presupuesto"),
         txt("patrones.nota2.texto",
             "%s (%s). A todos se les ofrecieron otras opciones y aun así "
             "no les alcanzó: es prácticamente una consulta cerrada."
             % (miles(plata_), pct(plata_ / float(tot), 0)))),
    ]
    if en_proceso:
        lineas.append((txt("patrones.nota3.titulo", "Todavía abiertos"),
                       txt("patrones.nota3.texto",
                           "%s (%s) tienen seguimiento pero todavía no tienen "
                           "respuesta final: no se cuentan en las barras."
                           % (miles(en_proceso), pct(en_proceso / float(tot), 0)))))
    return {
        "sec": "patrones", "color": "#8A2C2C",
        "kicker": txt("patrones.kicker", "Cómo se comportan los clientes"),
        "titulo": txt("patrones.titulo", "Qué hizo cada cliente"),
        "bajada": txt("patrones.bajada",
                      "Leyendo juntos los seguimientos y la respuesta final de %s" % de_quien),
        "columna": txt("patrones.columna", "Comportamiento"), "unidad": "Clientes",
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


# Qué lugares muestra la lámina de localidades (27-sep-2026). «Las dos»
# salen en láminas separadas: juntas serían una lista de 50 renglones.
LUGARES = [
    ("ambas", "Las dos",
     "Sale una lámina con las otras provincias y otra con Buenos Aires"),
    ("provincias", "Solo otras provincias",
     "Neuquén, Córdoba, Rosario… lo que llega de fuera de Buenos Aires"),
    ("buenos_aires", "Solo Buenos Aires",
     "La Plata, Quilmes, Zona Norte, Pinamar, CABA… localidades y zonas de la provincia"),
]


def partes_localidades(d, grupo):
    """Cuántas consultas llegaron de cada lugar, tal cual dice la columna
    Localidad. `grupo` = "provincias" o "buenos_aires".

    Pedido del usuario: «si yo quisiera saber cuántas consultas llegaron de
    Neuquén… o de La Plata, que se pueda mostrar el resultado». Va la lista
    ENTERA (repartida en las láminas que hagan falta), no las diez primeras:
    la pregunta es por un lugar puntual, y cortarla escondería justo ese.
    """
    foco = d.get("sucursal_foco") or ""
    campo = "derivaciones" if foco else "consultas"
    ls = [x for x in (d.get("lugares") or {}).values()
          if x["grupo"] == grupo and x.get(campo)]
    if not ls:
        return None
    ls.sort(key=lambda x: (-x[campo], x["nombre"]))
    tot = sum(x[campo] for x in ls)
    color = "#8A2C2C" if grupo == "provincias" else "#2C6E8A"
    filas, filas_t, filas_w = [], [], []
    for x in ls:
        etq = _NOMBRE_LUGAR.get(norm_txt(x["nombre"]), titulo_de(x["nombre"]))[:28]
        if x.get("provincia") and norm_txt(x["provincia"]) != norm_txt(x["nombre"]):
            etq = "%s (%s)" % (etq, x["provincia"])          # Rosario (Santa Fe)
        n = x[campo]
        filas.append((etq, n, "%s · %s" % (miles(n), pct(n / float(tot), 0)), color))
        if foco:
            filas_t.append((etq, n, miles(n), color, [miles(x["ventas"])]))
            filas_w.append((etq, miles(n), plural(x["ventas"], "venta", "ventas")))
        else:
            filas_t.append((etq, n, miles(n), color,
                            [miles(x["derivaciones"]), miles(x["ventas"])]))
            filas_w.append((etq, miles(n), "%s derivadas · %s"
                            % (miles(x["derivaciones"]), plural(x["ventas"], "venta", "ventas"))))
    primero = ls[0]
    uno, varios = (("derivación", "derivaciones") if foco else ("consulta", "consultas"))
    empate = len(ls) > 1 and ls[0][campo] == ls[1][campo]
    if empate:
        lineas = [(txt("localidades.%s.nota1.titulo" % grupo, "De cuántos lugares"),
                   txt("localidades.%s.nota1.texto" % grupo,
                       "%s repartidas entre %s. Ninguno se despega del resto."
                       % (plural(tot, uno, varios), plural(len(ls), "lugar", "lugares"))))]
    else:
        lineas = [(txt("localidades.%s.nota1.titulo" % grupo, "De dónde llegan más"),
                   txt("localidades.%s.nota1.texto" % grupo,
                       "%s con %s, el %s de lo que tiene lugar cargado. En total, "
                       "%s distintos."
                       % (_NOMBRE_LUGAR.get(norm_txt(primero["nombre"]), titulo_de(primero["nombre"])),
                          plural(primero[campo], uno, varios),
                          pct(primero[campo] / float(tot), 0),
                          plural(len(ls), "lugar", "lugares"))))]
    lineas.append((txt("localidades.%s.nota2.titulo" % grupo, "Lo que no se ve acá"),
                   txt("localidades.%s.nota2.texto" % grupo,
                       "Solo cuentan las filas con la Localidad cargada, tal cual "
                       "dice el desplegable%s." %
                       (" («Zona Norte» o «Interior de Buenos Aires» son un lugar "
                        "más, no se reparten)" if grupo == "buenos_aires" else ""))))
    if grupo == "provincias":
        kicker, titulo, bajada = ("De qué provincias", "Consultas de otras provincias",
                                  "Cuántas llegaron de cada provincia o ciudad de fuera de Buenos Aires")
    else:
        kicker, titulo, bajada = ("De qué lugares de Buenos Aires", "Consultas de Buenos Aires",
                                  "Cuántas llegaron de cada localidad o zona de la provincia y de CABA")
    if foco:
        bajada = bajada.replace("Cuántas llegaron", "Cuántas derivaciones recibió %s" % foco)
        titulo = titulo.replace("Consultas", "Derivaciones")
    return {
        "sec": "localidades", "color": color,
        "kicker": txt("localidades.%s.kicker" % grupo, kicker),
        "titulo": txt("localidades.%s.titulo" % grupo, titulo),
        "bajada": txt("localidades.%s.bajada" % grupo, bajada),
        "columna": txt("localidades.columna", "Lugar"),
        "unidad": (["Derivadas", "Ventas"] if foco else ["Consultas", "Derivadas", "Ventas"]),
        "filas": filas, "filas_t": filas_t, "filas_w": filas_w,
        "lineas": lineas,
    }


# cómo se escriben los valores del desplegable que no son un nombre propio
_NOMBRE_LUGAR = {
    "INT (BUENOS AIRES)": "Interior de Buenos Aires",
    "CABA": "CABA",
    "COSTA ATLANTICA": "Costa Atlántica",
}


def norm_txt(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "").upper())
    return "".join(c for c in t if not unicodedata.combining(c)).strip()


def laminas_localidades(d, op=None):
    """Las partes a dibujar según lo elegido: una o dos listas."""
    lugares = str((op or {}).get("lugares") or "ambas")
    grupos = {"provincias": ["provincias"], "buenos_aires": ["buenos_aires"]}.get(
        lugares, ["provincias", "buenos_aires"])
    return [p for p in (partes_localidades(d, g) for g in grupos) if p]


def _cierre_interior(d):
    z = (d.get("zonas") or {}).get("interior") or {}
    n = z.get("derivaciones", 0)
    return (z.get("ventas", 0) / float(n)) if n else 0.0


def _precio(d):
    t = d["total"]
    if not t.get("precio"):
        return ""
    tasa = t["fantasma"] / float(max(1, t["precio"]))
    peor = []
    for v, b in d["vendedores"].items():
        if b.get("precio", 0) >= 10:
            peor.append((v, b["fantasma"] / float(b["precio"]), b["precio"]))
    peor.sort(key=lambda x: -x[1])
    rango = ""
    if len(peor) >= 2:
        rango = ("Va de %s a %s según el vendedor — es parejo en todos."
                 % (pct(peor[-1][1], 0), pct(peor[0][1], 0)))
    return slide(
        cabeza(txt("precio.kicker", "El cuello de botella"),
               txt("precio.titulo", "Qué pasa después de mandar el precio"),
               txt("precio.bajada",
                   "De cada 100 clientes que recibieron precio, cuántos dejaron "
                   "de responder")) +
        conv_cards([
            (txt("precio.c1", "Recibieron precio"), miles(t["precio"]),
             txt("precio.c1.pie", "en el período"), "#1A1A2E", ""),
            (txt("precio.c2", "Dejaron de responder"), miles(t["fantasma"]),
             txt("precio.c2.pie", "no volvieron a contestar"), "#B4231F",
             pct(tasa, 0) + " de los que vieron precio"),
        ]) +
        notas([(txt("precio.nota1.titulo", "No es un problema de quién atiende"),
                txt("precio.nota1.texto",
                    rango or "El patrón se repite en todo el equipo.")),
               (txt("precio.nota2.titulo", "Es el punto donde se pierde la venta"),
                txt("precio.nota2.texto",
                    "Más gente se cae acá que en cualquier otro paso del "
                    "seguimiento."))]),
        oscuro=fondo("precio"), sec="precio")


def _honestidad(d, nombrar=False):
    """El slide que dice qué NO se puede afirmar con estos datos.

    Va al final y no se saca. Un reporte que solo muestra lo que sí sabe deja
    que el lector complete el resto por su cuenta, y ahí es donde se arman las
    conclusiones que nadie verificó.

    ⚠️ `nombrar` está en False a propósito. Este deck se le muestra al equipo de
    ventas, y señalar a una persona con nombre y apellido en base a una prueba
    estadística es algo que decide un jefe, no un programa. El hallazgo se
    calcula igual y queda disponible en el panel, que es privado; acá sale sin
    nombre, como cantidad."""
    t = d["total"]
    destacan = [(v, b) for v, b in d["vendedores"].items() if b.get("destaca")]
    n_vend = len(d["vendedores"])
    lineas = []

    if n_vend:
        if destacan:
            texto = ("De %d vendedores, %d tiene%s una conversión que el azar no "
                     "explica. El resto está dentro de lo esperable."
                     % (n_vend, len(destacan), "" if len(destacan) == 1 else "n"))
        else:
            texto = ("De %d vendedores, ninguno tiene una conversión que se salga "
                     "de lo esperable para su sucursal. Las diferencias que se ven "
                     "son del tamaño que produce el azar." % n_vend)
        lineas.append((txt("limites.nota1.titulo",
                           "No hay ranking de conversión, a propósito"),
                       txt("limites.nota1.texto",
                           "Con %s de cierre y unas %s derivaciones por cabeza, la "
                           "diferencia entre 3 y 10 ventas es suerte. %s"
                           % (pct(d["tasa_cierre"]),
                              miles(int(t["derivaciones"] / max(1, n_vend))),
                              texto))))

    lineas.append((
        txt("limites.nota2.titulo", "Cada uno se compara con su sucursal"),
        txt("limites.nota2.texto",
            "No contra el promedio de la empresa. Si una sucursal cierra al %s y "
            "otra al %s, medir a todos con la misma vara convierte una diferencia "
            "entre locales en una diferencia entre personas."
            % (pct(min((b["ventas"] / float(max(1, b["derivaciones"])))
                       for b in d["sucursales"].values()) if d["sucursales"] else 0),
               pct(max((b["ventas"] / float(max(1, b["derivaciones"])))
                       for b in d["sucursales"].values()) if d["sucursales"] else 0)))))

    if nombrar:
        for v, b in destacan[:2]:
            lineas.append((
                "%s se sale de lo esperable" % titulo_de(v),
                "%s ventas en %s derivaciones, cuando lo esperable eran %s."
                % (miles(b["ventas"]), miles(b["derivaciones"]),
                   miles(int(round(b["derivaciones"] * b.get("referencia", 0)))))))

    if d.get("fechas_sueltas"):
        f = d["fechas_sueltas"][0]
        cuantas = f["filas"]
        lineas.append((txt("limites.nota3.titulo",
                           "Hay fechas fuera del período"),
                       txt("limites.nota3.texto",
                           "%s fila%s con fecha de %s. Quedaron afuera del cálculo."
                           % (miles(cuantas), "" if cuantas == 1 else "s",
                              _titulo_mes(f["mes"])))))
    if d.get("sin_ubicar"):
        n = sum(d["sin_ubicar"].values())
        lineas.append((txt("limites.nota4.titulo", "Faltan ubicar vendedores"),
                       txt("limites.nota4.texto",
                           "%s derivaci%s de vendedores sin sucursal asignada "
                           "y no entra%s en el corte por sucursal."
                           % (miles(n), "ón es" if n == 1 else "ones son",
                              "" if n == 1 else "n"))))
    # Con un período pedido, lo primero que hay que poder contestar es «¿y las
    # otras filas?». Si el reporte no lo dice, el que compare este total con el
    # de la planilla entera va a pensar que faltan datos.
    if d.get("periodo_pedido"):
        fuera = d.get("fuera_del_periodo") or 0
        sf = d.get("sin_fecha_fuera") or 0
        if fuera or sf:
            partes = []
            if fuera:
                partes.append("%s fila%s de otras fechas"
                              % (miles(fuera), "" if fuera == 1 else "s"))
            if sf:
                partes.append("%s sin fecha cargada"
                              % (miles(sf) + (" fila" if sf == 1 else " filas")))
            lineas.append((txt("limites.nota5.titulo",
                               "Este reporte es de un período"),
                           txt("limites.nota5.texto",
                               "Se dejaron afuera %s. De una fila sin fecha no se "
                               "puede afirmar que haya pasado en este período."
                               % " y ".join(partes))))

    return slide(
        cabeza(txt("limites.kicker", "Los límites"),
               txt("limites.titulo", "Lo que estos datos NO permiten afirmar"),
               txt("limites.bajada",
                   "Para que nadie saque una conclusión que los números no "
                   "sostienen")) +
        notas(lineas[:4]), oscuro=fondo("limites", True), sec="limites")


# =====================================================================
#  El documento
# =====================================================================
# Las secciones que se pueden pedir, con el nombre que ve la persona.
# El orden de esta lista es el orden del reporte: lo primero es el embudo,
# porque es la pregunta que se hace cualquiera que lo abre.
SECCIONES = [
    # ── Los números del período ──
    ("embudo",    "¿Cuántas llegaron, se derivaron y se vendieron?",
     "Consultas, derivadas, ventas, conversión y lo recaudado, con el período anterior al lado"),
    ("meses",     "¿Cómo viene mes a mes?",
     "Las derivaciones de cada mes, para ver si sube o baja (con un reporte de un solo mes no sale)"),
    ("ritmo",     "¿Qué días entran más consultas?",
     "Cuántas entran cada día de la semana y cuántas se derivan"),
    # ── Sucursales y vendedores ──
    ("sucursales", "¿Cómo se reparten entre las sucursales?",
     "Derivaciones, ventas y conversión de cada local, uno al lado del otro"),
    ("vendedores", "¿Cuánto recibió y cerró cada vendedor?",
     "Tabla de quien recibió más a quien recibió menos, con sus ventas y su conversión"),
    ("podio",     "¿Quiénes cerraron más ventas?",
     "Un podio de cuatro para felicitar"),
    ("template",  "¿Quién manda las plantillas de seguimiento?",
     "Cuántas plantillas envió cada vendedor (mide la tarea, no la venta)"),
    # ── Los clientes ──
    ("patrones",  "¿Cómo se comportaron los clientes?",
     "Recibió el precio y no respondió, prometió pasar, fuera de presupuesto, compró…"),
    ("precio",    "¿Qué pasa después de darles el precio?",
     "Cuántos dejan de responder una vez que tienen el precio"),
    ("motivos",   "¿Por qué no compraron?",
     "Las respuestas finales, de la más repetida a la menos"),
    ("productos", "¿Qué productos consultan?",
     "Los más preguntados, de mayor a menor"),
    # ── De dónde vienen ──
    ("anuncios",  "¿Por qué anuncio llegaron?",
     "Anuncios, web, mailing, redes… y cuántas consultas, derivaciones y ventas trajo cada anuncio"),
    ("origenes",  "¿Qué dice la columna Origen?",
     "Cada valor tal cual está cargado, sin agrupar"),
    ("prod_origen", "¿Qué anuncio trae cada producto?",
     "El cruce: de qué origen vienen las consultas de cada producto"),
    ("medios",    "¿Por qué teléfono o red escriben?",
     "El medio de entrada: MyS, MV, Meta MyS, Meta MV…"),
    # ── Los lugares ──
    ("localidades", "¿De qué lugares consultan?",
     "Cuántas llegaron de cada provincia, localidad o zona (Neuquén, La Plata, Zona Norte…)"),
    ("provincias", "¿Cuántas llegaron del interior del país?",
     "Solo las otras provincias, con lo que se vendió"),
    ("zonas",     "¿Es de la zona del local o de lejos?",
     "Si lo que atiende cada sucursal es de su zona, y cuánto cierra cada cosa"),
    ("reparto",   "¿A qué vendedor le toca lo de lejos?",
     "Cuántas consultas del interior recibió cada vendedor"),
]
# En qué bloque va cada pregunta del asistente (27-sep-2026: «que se entienda
# para qué es cada pregunta»). El orden de SECCIONES es el orden en pantalla.
GRUPO_DE_SECCION = {
    "embudo": "Los números del período", "meses": "Los números del período",
    "ritmo": "Los números del período",
    "sucursales": "Sucursales y vendedores", "vendedores": "Sucursales y vendedores",
    "podio": "Sucursales y vendedores", "template": "Sucursales y vendedores",
    "patrones": "Los clientes", "precio": "Los clientes", "motivos": "Los clientes",
    "productos": "Los clientes",
    "anuncios": "De dónde vienen", "origenes": "De dónde vienen",
    "prod_origen": "De dónde vienen", "medios": "De dónde vienen",
    "localidades": "Los lugares", "provincias": "Los lugares", "zonas": "Los lugares",
    "reparto": "Los lugares",
}
TODAS = [k for k, _, _ in SECCIONES]

# Cuántas filas entran cómodas en una lámina. Más que esto y hay que
# achicar tanto que deja de leerse de lejos, que es para lo que está.
TOPE_LISTA = 12

# Las secciones que son una LISTA y por eso se pueden ver de dos maneras.
# El embudo, la comparación y el precio no entran: no son listas, son cuatro
# números puestos en un orden que significa algo.
CON_LISTA = ["sucursales", "vendedores", "productos", "origenes", "medios",
             "template", "motivos", "zonas", "provincias", "reparto",
             "ritmo", "prod_origen", "podio", "patrones", "localidades", "anuncios"]
VISTAS = [
    ("barras", "Barras", "Se ve de un golpe quién puntea"),
    ("columnas", "Columnas",
     "Barras paradas. Para lo que tiene un orden natural, como los días"),
    ("tabla", "Tabla", "Los números alineados, para comparar uno por uno"),
]

# Cómo sale la hoja del PDF. Las tres son APAISADAS o verticales de verdad —no
# es una lámina 16:9 metida adentro de una hoja más grande con bandas blancas—:
# se le cambia el tamaño a la lámina y el diseño se reacomoda solo, porque el
# cuerpo de cada lámina es flex y va centrado.
#
# La de fábrica sigue siendo 16:9 porque el reporte se hizo para mostrarse. Las
# otras dos son para el que lo va a imprimir o mandar por mail: una lámina de
# 13,33 pulgadas de ancho en una impresora sale reducida y con margen blanco.
HOJAS = [
    ("pantalla", "Pantalla 16:9",
     "Como se ve acá. Para mostrar en una reunión o proyectar"),
    ("a4h", "Hoja A4 apaisada",
     "Para imprimir: entra derecha en cualquier impresora"),
    ("a4v", "Hoja A4 vertical",
     "Para mandar por mail o archivar. Queda más aire arriba y abajo"),
]
# El ancho y el alto de cada una. Van en la MISMA unidad que el `@page` a
# propósito: con la hoja en milímetros y la lámina en píxeles, redondear medio
# píxel de más mete una página en blanco entre lámina y lámina.
_MEDIDAS_HOJA = {
    "pantalla": ("13.333in", "7.5in"),
    "a4h": ("297mm", "210mm"),
    "a4v": ("210mm", "297mm"),
}


def css_hoja(hoja):
    """El tamaño de página del PDF, como CSS que se agrega al final.

    Vacío para la de fábrica: el `@media print` del deck ya está en 16:9 y
    repetirlo sería tener el mismo número escrito en dos lados.
    """
    hoja = str(hoja or "pantalla")
    if hoja not in _MEDIDAS_HOJA or hoja == "pantalla":
        return ""
    an, al = _MEDIDAS_HOJA[hoja]
    return ("@media print{@page{size:%s %s;margin:0}"
            "html,body,.deck,.slide{width:%s}"
            ".slide{height:%s}}" % (an, al, an, al))

# Cuánto detalle entra en las listas. Es una pregunta y no un número fijo
# porque «los 5 primeros» y «todos» son dos reportes distintos: uno para
# mostrar en una reunión, el otro para revisar con la planilla al lado.
DETALLES = [
    ("5", "Los 5 primeros", "Corto, para mostrar en una reunión"),
    ("10", "Los 10 primeros", "Lo habitual"),
    ("todos", "Todos",
     "Hasta 48 por lista, repartidos en las hojas que hagan falta"),
]

# Contra qué se compara. «anterior» es el default porque es la pregunta que se
# hace cualquiera al ver un total: ¿esto es mucho o poco?
# Contra qué se comparan los números. ⚠️ NO es una lámina: es el porcentaje
# que va DEBAJO de cada tarjeta del embudo («▲ 27% vs el mes anterior»). Hubo
# una lámina de comparación hasta la v55 y se sacó porque decía lo mismo que
# esas cuatro tarjetas, en una hoja aparte: dos láminas que cuentan lo mismo
# obligan a elegir cuál mirar.
COMPARACIONES = [
    ("anterior", "Contra el período anterior",
     "Si el reporte es de agosto, contra julio: «▼ 12% vs julio (206)»"),
    ("ano", "Contra el año pasado",
     "El mismo período, doce meses antes"),
    ("nada", "Sin comparación", "Solo los números de este período"),
]


# Cuántas láminas puede ocupar UNA lista, como mucho. Sin este tope, «la lista
# larga» sobre los productos daba 12 láminas seguidas de productos: el reporte
# dejaba de ser un reporte. Lo que no entra se dice en la nota del final, que
# es la diferencia entre cortar y esconder.
TOPE_PAGINAS = 4

# La vista con la que sale cada lámina cuando el reporte no dice otra cosa.
# 27-sep-2026: los vendedores salen en TABLA, que es donde se ven las ventas y
# la conversión al lado de lo recibido (en barras solo va lo recibido).
VISTA_DE_FABRICA = {"ritmo": "columnas", "vendedores": "tabla", "localidades": "tabla",
                    "anuncios": "tabla"}


def _cuantos(opciones):
    d = str((opciones or {}).get("detalle") or "10")
    if d == "todos":
        return TOPE_LISTA * TOPE_PAGINAS
    return 5 if d == "5" else 10


def armar(d, titulo="Reporte de derivaciones", secciones=None, opciones=None):
    """El HTML completo, listo para mirar, presentar o imprimir.

    `secciones` = las claves de SECCIONES que se quieren. None = todas, que es
    lo de siempre. La portada y el slide de límites van SIEMPRE: la portada
    porque dice de qué período habla, y los límites porque es donde el reporte
    aclara lo que no puede afirmar. Un reporte que deja elegir si muestra sus
    propios límites no es un reporte, es un folleto.

    `opciones` = lo que se eligió al crearlo:
        detalle   '5' | '10' | 'todos'   cuánto entra en cada lista
        nota      texto                  una aclaración en la portada
        previo    otro análisis          el período contra el que se compara
        previo_txt  cómo se llama ese período
    """
    if not d or not d.get("ok"):
        raise ValueError((d or {}).get("error") or "no hay datos")
    op = opciones or {}
    quiere = (lambda k: True) if not secciones else (lambda k: k in set(secciones))
    n = _cuantos(op)
    vistas = op.get("vistas") or {}
    por_defecto = op.get("vista") or ""
    # El ritmo sale en columnas porque los días de la semana tienen un orden
    # natural de izquierda a derecha: siete barras horizontales obligan a leer
    # renglón por renglón para ver la forma. Se puede cambiar como cualquier
    # otra, pero de fábrica sale como se lee mejor.
    # ⚠️ El orden importa. Primero lo que se eligió PARA ESA lámina; después la
    # que le queda bien de fábrica; recién al final la vista general del
    # reporte. Al revés, el «barras» que el reporte guarda de fábrica pisaba el
    # gráfico de columnas del ritmo y nadie entendía por qué no aparecía.
    v = lambda k: (vistas.get(k) or VISTA_DE_FABRICA.get(k)   # noqa: E731
                   or por_defecto or "barras")
    _CTX.textos = Textos(op.get("textos"), op.get("ocultos"))
    # el fondo elegido para cada lámina: {"embudo": "oscuro", ...}
    _CTX.fondos = {k: str(x) for k, x in (op.get("fondos") or {}).items()}
    # Lo que la página de edición necesita saber y no puede ver en pantalla:
    # los textos que ya se sacaron (no se dibujan) y las láminas que lleva el
    # reporte. Sin esto, cada guardado mandaba solo lo sacado en ESA vuelta y
    # lo de antes volvía a aparecer (30-sep-2026).
    op = dict(op)
    op["_edinfo"] = {"secciones": [k for k in TODAS if quiere(k)],
                     "ocultos": sorted(str(k) for k in (op.get("ocultos") or [])),
                     # lo guardado entero: «Deshacer lo guardado» lo necesita
                     # para volver exactamente a como estaba
                     "textos": dict(op.get("textos") or {}),
                     "vistas": dict(op.get("vistas") or {}),
                     "fondos": dict(op.get("fondos") or {})}
    try:
        return _armar(d, titulo, quiere, n, v, op)
    finally:
        _CTX.textos = None
        _CTX.fondos = None


def _armar(d, titulo, quiere, n, v, op):
    partes = [
        _portada(d, titulo, op.get("nota")),
        _embudo(d, op) if quiere("embudo") else "",
        _por_mes(d) if quiere("meses") else "",
        pintar(partes_ritmo(d), v("ritmo")) if quiere("ritmo") else "",
        _por_sucursal(d, v("sucursales")) if quiere("sucursales") else "",
        pintar(partes_ranking(
            d, "derivaciones", "Derivaciones por vendedor",
            "Cuántas consultas recibió cada uno, con lo que cerró al lado",
            "El equipo", "derivaciones", cuantos=n,
            clave="vendedores", con_ventas=True), v("vendedores"))
        if quiere("vendedores") else "",
        pintar(partes_podio(d), v("podio")) if quiere("podio") else "",
        pintar(partes_productos(d, n), v("productos"))
        if quiere("productos") else "",
        pintar(partes_origenes(d, n), v("origenes"))
        if quiere("origenes") else "",
        "".join(pintar(x, v("anuncios")) for x in laminas_anuncios(d))
        if quiere("anuncios") else "",
        pintar(partes_prod_origen(d, n), v("prod_origen"))
        if quiere("prod_origen") else "",
        pintar(partes_medios(d, n), v("medios")) if quiere("medios") else "",
        "".join(pintar(x, v("localidades")) for x in laminas_localidades(d, op))
        if quiere("localidades") else "",
        pintar(partes_zonas(d), v("zonas")) if quiere("zonas") else "",
        pintar(partes_provincias(d, n), v("provincias"))
        if quiere("provincias") else "",
        pintar(partes_reparto(d, n), v("reparto"))
        if quiere("reparto") else "",
        pintar(partes_ranking(
            d, "template", "Quién manda más templates",
            "Seguimiento enviado — es conducta, no resultado", "Cumplimiento",
            "enviados", color="#3A7A55", cuantos=n,
            clave="template"), v("template")) if quiere("template") else "",
        _precio(d) if quiere("precio") else "",
        pintar(partes_patrones(d), v("patrones")) if quiere("patrones") else "",
        pintar(partes_motivos(d), v("motivos")) if quiere("motivos") else "",
        _honestidad(d),
    ]
    partes = [p for p in partes if p]
    return _PAGINA % {
        "titulo": e(titulo),
        "slides": "".join(partes),
        "total": len(partes),
        "edinfo": json.dumps(op.get("_edinfo") or {},
                             ensure_ascii=False).replace("<", "\\u003c"),
        # la hoja va al final del CSS para poder pisar el @media print de
        # arriba sin repetir toda la hoja de estilos
        "css": _CSS + css_hoja(op.get("hoja")),
    }


_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#F0EDE8; --bg2:#E8E4DF; --surface:#FFFFFF;
  --ink:#111111; --ink2:#444444; --ink3:#8A8A8A;
  --border:rgba(0,0,0,.10); --border2:rgba(0,0,0,.06);
  --c-success:#1A6A3A; --c-danger:#B4231F;
}
html,body{height:100%;overflow:hidden;background:var(--bg);
  font-family:'Montserrat',system-ui,-apple-system,'Segoe UI',sans-serif;
  color:var(--ink);-webkit-font-smoothing:antialiased}
.deck{position:relative;width:100%;height:100%;overflow:hidden}
.slide{position:absolute;inset:0;opacity:0;transform:translateX(28px);
  transition:opacity .34s ease,transform .34s ease;pointer-events:none;
  overflow:hidden;background:var(--bg)}
.slide.active{opacity:1;transform:none;pointer-events:auto}
.slide.dark{background:var(--ink);color:#fff}
.slide-inner{max-width:1180px;margin:0 auto;padding:64px 56px;height:100%;
  display:flex;flex-direction:column;justify-content:center}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:3px;text-transform:uppercase;
  color:var(--ink3);margin-bottom:14px}
.slide.dark .eyebrow{color:rgba(255,255,255,.4)}
.s-title{font-size:clamp(30px,3.6vw,48px);font-weight:800;line-height:1.05;
  letter-spacing:-1px;margin-bottom:6px}
.slide.dark .s-title{color:#fff}
.s-sub{font-size:15px;color:var(--ink3);font-weight:400;margin-bottom:32px}
.slide.dark .s-sub{color:rgba(255,255,255,.45)}

.conv-row{display:flex;gap:18px}
.conv-card{flex:1;border-radius:18px;padding:30px 26px;color:#fff}
.conv-card .cs{font-size:13px;font-weight:700;letter-spacing:2px;
  text-transform:uppercase;opacity:.8}
.conv-card .cbig{font-size:clamp(40px,5vw,60px);
  font-weight:800;letter-spacing:-2px;margin:6px 0 2px}
.conv-card .csub{font-size:13px;opacity:.85;font-weight:500}
.conv-card .ctag{margin-top:14px;font-size:12px;font-weight:700;
  background:rgba(255,255,255,.16);display:inline-block;padding:5px 12px;border-radius:20px}

/* con dos o tres meses, tarjetas de 590 px cada una son bloques, no tarjetas:
   tienen ancho maximo y la fila va centrada */
.month-row{display:flex;justify-content:center;gap:18px}
.month-card{flex:1 1 0;max-width:214px;background:var(--surface);
  border:1px solid var(--border);border-radius:18px;padding:30px 16px;
  text-align:center}
.month-card.lead{background:var(--ink);border-color:var(--ink)}
.month-card .ml{font-size:13px;font-weight:700;letter-spacing:3px;
  text-transform:uppercase;color:var(--ink3);margin-bottom:8px}
.month-card.lead .ml{color:rgba(255,255,255,.55)}
.month-card .mn{font-size:clamp(40px,5.6vw,74px);font-weight:800;letter-spacing:-3px;
  line-height:.95;color:var(--ink)}
.month-card.lead .mn{color:#fff}
.month-card .mt{margin-top:12px;font-size:12.5px;font-weight:600;color:var(--ink3)}
.month-card.lead .mt{color:rgba(255,255,255,.6)}

/* la misma lista, en tabla: para comparar de a uno en vez de de un golpe */
.tablita{width:100%;border-collapse:collapse;font-size:15px}
.tablita th{padding:0 12px 9px;text-align:left;font-size:11.5px;font-weight:700;
  letter-spacing:2px;text-transform:uppercase;color:var(--ink3);
  border-bottom:1px solid var(--border)}
.tablita td{padding:9px 12px;border-bottom:1px solid rgba(0,0,0,.05)}
.tablita tbody tr:last-child td{border-bottom:0}
.tablita .tn{width:34px;color:var(--ink3);font-size:13px;font-variant-numeric:tabular-nums}
.tablita .te{font-weight:700}
.tablita .tv{width:170px;font-weight:700;font-variant-numeric:tabular-nums;
  white-space:nowrap}
.tablita .tb{width:34%;padding-right:0}
.tablita .tb i{display:block;height:8px;border-radius:4px}
.slide.dark .tablita td{border-bottom-color:rgba(255,255,255,.08)}
.slide.dark .tablita th{border-bottom-color:rgba(255,255,255,.16)}
/* ⚠️ La barra NO llega hasta el borde de la lamina. Una barra de 1.030 px de
   largo para decir «53%» hace que la lamina sea la barra; con un tope, el
   grafico ocupa lo que necesita y el resto es aire a proposito. */
.bars{display:flex;flex-direction:column;gap:11px;max-width:900px}
/* muchas filas: mas juntas y mas bajas, para que la lamina no se pase */
.bars.densa{gap:7px}
.bars.densa .bar2 .bt{height:32px}
.bars.densa .bar2 .bl{font-size:13.5px}
/* DOS COLUMNAS. Se llenan hacia abajo primero —1 a 6 a la izquierda, 7 a 12 a
   la derecha— para que «de mayor a menor» se siga leyendo de corrido. */
/* ⚠️ `max-width:none` a proposito: el tope de 900 px es para UNA columna. En
   dos, ese tope dejaba las dos apretadas contra la izquierda y 280 px de aire
   a la derecha, que se ve como si la lamina estuviera mal armada. */
.bars.dos{display:grid;grid-auto-flow:column;grid-template-columns:1fr 1fr;
  column-gap:44px;row-gap:9px;max-width:none}
.bars.dos .bar2{gap:13px}
.bars.dos .bar2 .bl{width:150px;font-size:12.5px}
.bars.dos .bar2 .bt{height:31px}
.bars.dos .bar2 .bf{padding:0 12px;font-size:12.5px}
/* barra corta: el numero va afuera, en tinta, o queda cortado */
.bar2.afuera .bf{overflow:visible;position:relative}
.bar2.afuera .bf span{position:absolute;left:calc(100% + 9px);color:var(--ink2);white-space:nowrap}
.slide.dark .bar2.afuera .bf span{color:rgba(255,255,255,.78)}
.bar2{display:flex;align-items:center;gap:18px;min-width:0}
/* el rotulo entra en DOS renglones antes de cortarse. Un nombre real —«Promo
   Esquineros y Sillones», «No respondio, se insistio 3 veces»— no entra en uno
   solo, y cortado con puntos suspensivos se lee como un error de la
   herramienta, no como una decision. */
.bar2 .bl{width:174px;font-size:14px;font-weight:700;text-align:right;
  flex:0 0 auto;line-height:1.22;overflow:hidden;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
/* el carril, apenas marcado. En blanco puro sobre la crema de la lamina, un
   valor chico dejaba una caja blanca enorme con un puntito de color adentro:
   lo que saltaba a la vista era el hueco y no el dato. */
.bar2 .bt{flex:1;min-width:0;height:38px;background:rgba(0,0,0,.055);
  border-radius:10px;overflow:hidden}
.slide.dark .bar2 .bt{background:rgba(255,255,255,.1)}
.bar2 .bf{height:100%;border-radius:10px;display:flex;align-items:center;
  padding:0 16px;color:#fff;font-weight:700;font-size:13.5px;white-space:nowrap}

/* columnas: la misma lista, parada. El numero va ARRIBA de la columna: una
   columna corta no tiene lugar adentro y el texto queda cortado.

   ⚠️ La columna tiene ANCHO MAXIMO. Con siete dias repartiendose 1.180 px,
   cada una medía 167 px y el grafico dejaba de leerse como un grafico: eran
   siete bloques.

   ⚠️ Y NO hay carril de fondo, solo una linea de base. Con el carril pintado,
   aunque sea apenas, la columna se lee como si tuviera dos partes —lo lleno y
   lo vacio— y eso no es lo que dice el dato: el dato es la altura. */
/* ⚠️ La linea de base va donde TERMINAN LAS COLUMNAS, no abajo de todo. Con
   el borde en la caja entera quedaba debajo de los rotulos, o sea flotando 50
   px mas abajo que las barras: se leia como si las barras no apoyaran en
   ningun lado. Por eso el rotulo tiene alto FIJO y la linea se dibuja ahi. */
.cols{position:relative;display:flex;align-items:flex-end;
  justify-content:space-around;gap:16px;height:286px;margin-top:10px}
.cols::after{content:"";position:absolute;left:0;right:0;bottom:50px;
  height:1px;background:var(--border)}
.slide.dark .cols::after{background:rgba(255,255,255,.18)}
.col2{flex:1 1 0;min-width:0;max-width:84px;display:flex;flex-direction:column;
  align-items:center;height:100%}
.col2 .cv{font-size:14px;font-weight:800;margin-bottom:7px;white-space:nowrap}
.col2 .ct{flex:1;width:100%;display:flex;align-items:flex-end}
.col2 .cf{width:100%;min-height:3px;border-radius:7px 7px 0 0}
.col2 .cl{margin-top:10px;height:40px;font-size:12px;font-weight:700;
  text-align:center;line-height:1.24;overflow:hidden;overflow-wrap:anywhere;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
.cols.densa{gap:10px}
.cols.densa .col2{max-width:64px}
.cols.densa .cv{font-size:12px}
.cols.densa .cl{font-size:11px}

/* cuanto cambio contra el periodo anterior, en la tarjeta del embudo */
/* verde o rojo segun si el cambio es BUENO, no segun el signo: en «sin
   derivar» subir es malo, y pintarlo de verde diria lo contrario de lo que
   paso. El chip va en blanco para que el color se lea sobre cualquiera de los
   cuatro fondos de tarjeta. */
.conv-card .ccmp{margin-top:8px;font-size:12.5px;font-weight:800;
  display:inline-block;padding:4px 11px;border-radius:20px;
  background:rgba(255,255,255,.93)}
.conv-card .ccmp.sube{color:#12683A}
.conv-card .ccmp.baja{color:#A32C1E}

/* tabla con varias columnas de numeros: derivaciones, ventas y conversion */
.tablita .tx{padding:7px 14px;font-size:14px;font-weight:600;text-align:right;
  white-space:nowrap;color:var(--ink2)}
.slide.dark .tablita .tx{color:rgba(255,255,255,.72)}
.tablita.ancha .tv{text-align:right}
.tablita.ancha th:nth-child(n+3){text-align:right}

.notas{display:flex;gap:16px;margin-top:30px}
.nota{flex:1;background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:18px 20px;position:relative}
/* una tarjeta sola no se estira a 1180 px: dos renglones perdidos en un
   rectangulo enorme se leen peor que centrados */
.notas .nota:only-child,.notas.sola .nota:not(.fuera){flex:0 1 auto;
  max-width:64%;margin:0 auto}
.slide.dark .nota{background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.12)}
.nota .nt{font-size:15px;font-weight:700;margin-bottom:5px}
.nota .nx{font-size:13px;line-height:1.6;color:var(--ink2)}
.slide.dark .nota .nx{color:rgba(255,255,255,.7)}

.portada{text-align:left}
.p-title{font-size:clamp(38px,5.2vw,68px);font-weight:800;letter-spacing:-2px;
  line-height:1.02;color:#fff;margin-bottom:10px}
.p-per{font-size:17px;color:rgba(255,255,255,.5);margin-bottom:44px;
  text-transform:capitalize}
.p-nums{display:flex;gap:56px;margin-bottom:44px}
.p-nums b{display:block;font-size:clamp(34px,4.4vw,54px);font-weight:800;
  letter-spacing:-2px;color:#fff}
.p-nums span{font-size:13px;letter-spacing:2px;text-transform:uppercase;
  color:rgba(255,255,255,.45)}
.p-nota{max-width:640px;margin:0 0 18px;font-size:15px;line-height:1.55;
  color:rgba(255,255,255,.62)}
.p-pie{font-size:12.5px;color:rgba(255,255,255,.35)}

#nav{position:fixed;bottom:22px;right:26px;display:flex;gap:8px;z-index:50}
#nav button{padding:9px 16px;border:1px solid var(--border);background:var(--surface);
  border-radius:9px;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer}
#nav button:last-child{background:var(--ink);color:#fff;border-color:var(--ink)}
#contador{position:fixed;bottom:28px;left:28px;font-size:12.5px;color:var(--ink3);z-index:50}
#barra{position:fixed;top:0;left:0;height:3px;background:var(--ink);z-index:60;
  transition:width .3s ease}
#pista{position:fixed;top:18px;right:26px;font-size:11px;letter-spacing:1px;
  text-transform:uppercase;color:var(--ink3);z-index:50}

@media (max-width:860px){
  .slide-inner{padding:32px 22px}
  .conv-row,.month-row,.notas{flex-wrap:wrap;gap:10px}
  .conv-card{flex:1 1 45%}
  .month-card{flex:1 1 44%}
  .nota{flex:1 1 100%}
  .bar2 .bl{width:96px;font-size:13px}
  .p-nums{gap:26px}
}

/* ── EDITAR EL REPORTE ADENTRO DEL REPORTE ──
   El lápiz vive arriba a la izquierda, lejos de las flechas de pasar y del
   contador. Nada de esto sale impreso: en papel no hay botones. */
/* La barra va arriba a la DERECHA: a la izquierda se apoyaba justo encima del
   rótulo y del título de la lámina, que es lo que se está por editar. La ayuda
   de las flechas se va cuando hay editor, que es quien ocupaba ese lugar. */
#ed{position:fixed;top:16px;right:20px;display:flex;gap:8px;z-index:70}
body.con-editor #pista{display:none}
#ed button{padding:8px 14px;border:1px solid var(--border);background:var(--surface);
  border-radius:9px;font-family:inherit;font-size:13px;font-weight:600;
  color:var(--ink2);cursor:pointer;display:inline-flex;align-items:center;gap:7px}
#ed button:hover{border-color:var(--ink3);color:var(--ink)}
#ed button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
#ed button[hidden]{display:none}
#ed button:disabled{opacity:.45;cursor:default}
#ed button.rojo{border-color:#B5503F;color:#B5503F}
#ed button.rojo:hover{background:#B5503F;color:#fff}
#ed .pt{font-size:15px;line-height:1}
body.editando .ed-t{outline:1px dashed rgba(44,110,138,.55);outline-offset:3px;
  border-radius:3px;cursor:text;transition:background .12s ease}
body.editando .ed-t:hover{background:rgba(44,110,138,.09)}
body.editando .ed-t:focus{outline:2px solid #2C6E8A;background:rgba(44,110,138,.06)}
.slide.dark .ed-t{outline-color:rgba(255,255,255,.4)}
/* el interruptor de vista, adentro de la lámina que es una lista */
/* el interruptor de la lámina, debajo de la barra de edición */
.ed-v{position:absolute;top:64px;right:24px;display:flex;
  flex-direction:column;align-items:flex-end;gap:6px;z-index:6}
.ed-fila{display:flex;gap:5px;align-items:center}
.ed-fila > span{font-size:10px;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink3);margin-right:3px}
.slide.dark .ed-fila > span{color:rgba(255,255,255,.5)}
.ed-v button{padding:5px 11px;border:1px solid var(--border);background:var(--surface);
  border-radius:999px;font-family:inherit;font-size:12px;font-weight:600;
  color:var(--ink3);cursor:pointer}
.ed-v button.on{background:#2C6E8A;color:#fff;border-color:#2C6E8A}
/* la × que saca una TARJETA entera, no solo uno de sus textos */
.ed-nx{position:absolute;top:9px;right:10px;width:21px;height:21px;padding:0;
  border:1px solid var(--border);background:var(--surface);border-radius:50%;
  font-size:13px;line-height:1;color:var(--ink3);cursor:pointer;z-index:8}
.ed-nx:hover{background:#B5503F;border-color:#B5503F;color:#fff}
.nota.fuera{opacity:.45}
/* una lámina marcada para sacar: se ve apagada hasta guardar */
.slide.sacada .slide-inner{opacity:.28;filter:grayscale(1)}
.ed-v button.ed-sacar{border-color:#B5503F;color:#B5503F}
.ed-v button.ed-sacar.on{background:#B5503F;color:#fff}
.nota.fuera .nt,.nota.fuera .nx{text-decoration:line-through}
.ed-nv{position:absolute;top:9px;right:10px;padding:2px 9px;
  border:1px dashed var(--ink3);background:var(--surface);border-radius:999px;
  font-family:inherit;font-size:10.5px;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;color:var(--ink3);cursor:pointer;z-index:8}
.ed-nv:hover{color:var(--ink);border-color:var(--ink)}
/* el aviso va ABAJO: arriba tapaba justamente el titulo que se esta por
   tocar, que es lo peor que puede hacer un cartel de ayuda */
/* la ayuda se muestra al entrar y se va sola: cualquier lugar fijo termina
   tapando algo de la lámina, y una vez leída no hace falta más */
#edAviso{position:fixed;left:20px;bottom:20px;max-width:420px;padding:10px 13px;
  background:#FFF6E5;border:1px solid #E8D6AE;border-radius:9px;font-size:12.5px;
  line-height:1.5;color:#6B5426;z-index:70;transition:opacity .5s ease}
#edAviso.yendose{opacity:0}
#edAviso[hidden]{display:none}
/* la × que saca un texto del reporte */
.ed-x{position:absolute;margin-left:6px;width:19px;height:19px;padding:0;
  border:1px solid var(--border);background:var(--surface);border-radius:50%;
  font-size:12px;line-height:1;color:var(--ink3);cursor:pointer;z-index:8}
.ed-x:hover{background:#B5503F;border-color:#B5503F;color:#fff}
/* un texto sacado no desaparece mientras se edita: queda en gris, tachado y
   con un botón para traerlo de vuelta. Si desapareciera del todo, sacar algo
   sin querer no tendría arreglo salvo acordarse de qué decía. */
.ed-t.fuera{opacity:.4;text-decoration:line-through}
.ed-fuera{display:inline-flex;align-items:center;gap:5px;margin-left:8px;
  padding:2px 8px;border:1px dashed var(--ink3);border-radius:999px;
  font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
  color:var(--ink3);background:var(--surface);cursor:pointer;vertical-align:middle}
.ed-fuera:hover{color:var(--ink);border-color:var(--ink)}
/* editando, la ayuda de las flechas sobra y encima choca con el interruptor
   de vista; el contador tambien estorba al aviso */
body.editando #pista,body.editando #contador{display:none}
@media print{
  #ed,#edAviso,.ed-v{display:none !important}
  .ed-t{outline:0 !important;background:none !important}
  @page{size:13.333in 7.5in;margin:0}
  *{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important}
  html,body{width:1280px;height:auto;overflow:visible;background:#fff}
  .deck{width:1280px;height:auto;position:static;overflow:visible}
  .slide{position:relative;inset:auto;opacity:1 !important;transform:none !important;
    width:1280px;height:720px;overflow:hidden;background:var(--bg);
    page-break-after:always;break-after:page;page-break-inside:avoid}
  .slide.dark{background:var(--ink)}
  .slide:last-of-type{page-break-after:auto;break-after:auto}
  .tablita{font-size:13.5px}
  .tablita td{padding:6px 12px}
  #nav,#contador,#barra,#pista{display:none !important}
}
"""

_PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(titulo)s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>%(css)s</style></head>
<body>
<div id="barra"></div>
<div class="deck" id="deck">%(slides)s</div>
<div id="contador"><span id="ahora">1</span> / %(total)d</div>
<div id="pista">← → para pasar · F pantalla completa · Ctrl+P para PDF</div>
<div id="ed" hidden>
  <button type="button" id="edPdf"><span class="pt">&#8681;</span>Descargar PDF</button>
  <button type="button" id="edDeshGuardado" hidden><span class="pt">&#8630;</span>Deshacer lo guardado</button>
  <button type="button" id="edHoja" class="rojo" hidden>Eliminar esta hoja</button>
  <button type="button" id="edBtn"><span class="pt">&#9998;</span>Editar</button>
  <button type="button" id="edDeshacer" hidden disabled><span class="pt">&#8630;</span>Deshacer</button>
  <button type="button" id="edVolver" hidden>Volver a mostrar lo sacado</button>
  <button type="button" id="edOk" hidden>Guardar edición</button>
  <button type="button" id="edNo" hidden>Cancelar</button>
</div>
<div id="edAviso" hidden></div>
<div id="nav">
  <button type="button" onclick="mover(-1)">← Anterior</button>
  <button type="button" onclick="mover(1)">Siguiente →</button>
</div>
<script>
/* ═══════════════════ EDITAR EL REPORTE, EN EL REPORTE ═══════════════════
   Se aprieta el lápiz, se toca cualquier título o texto y se escribe encima.
   Al lado queda «Guardar edición». Las láminas que son una lista muestran
   además el interruptor de barras/tabla.

   Solo aparece si la página sabe a qué reporte guardar (viene con id e
   informe): el deck de toda la planilla no es de nadie y no se edita.

   ⚠️ Se editan TEXTOS, no números. Los números se calculan cada vez que se
   abre el reporte; si se reescribe una frase que lleva uno adentro, ese queda
   escrito a mano. Por eso se avisa al entrar en edición. */
var ED = (function () {
  var q = new URLSearchParams(location.search);
  return { id: q.get('id') || '', inf: q.get('informe') || '' };
}());
var EDIT = false, ORIG = {}, VISTAS = {}, FUERA = {}, FONDOS = {}, SACADAS = {};
/* Lo que ya estaba sacado NO se dibuja, así que la página no lo puede ver: el
   servidor se lo pasa. Arranca adentro de FUERA para que el próximo guardado
   lo mande de nuevo; antes se mandaba solo lo sacado en esa vuelta y todo lo
   de antes volvía a aparecer (30-sep-2026). */
var EDINF = %(edinfo)s;
(EDINF.ocultos || []).forEach(function (k) { FUERA[k] = true; });
/* cómo estaba guardado al abrir: es lo que vuelve con «Deshacer lo guardado» */
var GUARDADO = JSON.parse(JSON.stringify(EDINF));
/* «Deshacer»: una foto del estado antes de cada cambio, y se vuelve a la última */
var HIST = [], FOTO_PEND = null;

function edTextos() { return document.querySelectorAll('.ed-t[data-txt]'); }

/* Un cartel que se va solo. Fijo tapa algo de la lámina; leído una vez, ya
   cumplió. Si vuelve a hacer falta (un error al guardar), se lo llama de
   nuevo y reaparece. */
function edDecir(html, quedarse) {
  var av = document.getElementById('edAviso');
  av.innerHTML = html;
  av.hidden = false;
  av.classList.remove('yendose');
  clearTimeout(edDecir._t); clearTimeout(edDecir._t2);
  if (quedarse) return;
  edDecir._t = setTimeout(function () {
    av.classList.add('yendose');
    edDecir._t2 = setTimeout(function () { av.hidden = true; }, 600);
  }, 6000);
}

function edPrender(v) {
  EDIT = v;
  document.body.classList.toggle('editando', v);
  document.getElementById('edBtn').classList.toggle('on', v);
  document.getElementById('edOk').hidden = !v;
  document.getElementById('edNo').hidden = !v;
  /* editando, el PDF saldria SIN lo que se acaba de escribir —el reporte lo
     arma el servidor con lo ultimo guardado—, asi que el boton se esconde
     hasta guardar o cancelar */
  document.getElementById('edPdf').hidden = v;
  document.getElementById('edDeshGuardado').hidden = v || !edPrevio();
  edBotonDeshacer();
  var nOc = (EDINF.ocultos || []).length;
  document.getElementById('edVolver').hidden = !(v && nOc);
  document.getElementById('edVolver').textContent =
    'Volver a mostrar lo sacado (' + nOc + ')';
  document.getElementById('edBtn').innerHTML = v
    ? '<span class="pt">&#9998;</span>Editando'
    : '<span class="pt">&#9998;</span>Editar';
  var ns = edTextos(), i;
  for (i = 0; i < ns.length; i++) {
    ns[i].contentEditable = v ? 'true' : 'false';
    if (v && !(ns[i].dataset.txt in ORIG)) ORIG[ns[i].dataset.txt] = ns[i].textContent;
  }
  edEquis(v);
  edNotas(v);
  if (v) {
    edDecir('Tocá cualquier texto y escribí encima, o sacalo con la <b>×</b>. ' +
            'La <b>×</b> de la esquina saca la tarjeta entera. Arriba a la ' +
            'derecha de cada lámina elegís <b>cómo se ve la lista</b> y si el ' +
            '<b>fondo</b> va claro u oscuro. <b>Eliminar esta hoja</b> la saca entera, y ' +
            '<b>Deshacer</b> vuelve atrás el último cambio. Los <b>números no se editan</b>: ' +
            'se calculan solos cada vez que abrís el reporte.');
  } else {
    document.getElementById('edAviso').hidden = true;
  }
  edVistas(v);
  edHojaPintar();
}

/* La × de cada texto. Sacar no borra: el texto queda tachado y con un botón
   para traerlo de vuelta, así sacar algo sin querer tiene arreglo. Lo que se
   guarda es la lista de los que quedaron afuera. */
function edEquis(v) {
  var viejos = document.querySelectorAll('.ed-x, .ed-fuera'), i;
  for (i = 0; i < viejos.length; i++) viejos[i].remove();
  if (!v) return;
  var ns = edTextos();
  for (i = 0; i < ns.length; i++) {
    (function (n) {
      var k = n.dataset.txt;
      if (FUERA[k]) edPintarFuera(n, true);
      var x = document.createElement('button');
      x.type = 'button'; x.className = 'ed-x'; x.title = 'Sacar del reporte';
      x.textContent = '\u00D7';
      x.onclick = function (ev) {
        ev.preventDefault(); ev.stopPropagation();
        edMarca();
        FUERA[k] = true; edPintarFuera(n, true);
      };
      n.insertAdjacentElement('afterend', x);
    }(ns[i]));
  }
}

function edPintarFuera(n, fuera) {
  var k = n.dataset.txt;
  n.classList.toggle('fuera', fuera);
  n.contentEditable = fuera ? 'false' : 'true';
  var x = n.nextElementSibling;
  if (x && x.classList.contains('ed-x')) x.hidden = fuera;
  var viejo = n.parentNode.querySelector('.ed-fuera[data-de="' + k + '"]');
  if (viejo) viejo.remove();
  if (!fuera) return;
  var b = document.createElement('button');
  b.type = 'button'; b.className = 'ed-fuera'; b.dataset.de = k;
  b.textContent = 'Volver a mostrar';
  b.onclick = function (ev) {
    ev.preventDefault(); ev.stopPropagation();
    edMarca();
    delete FUERA[k]; edPintarFuera(n, false);
  };
  n.insertAdjacentElement('afterend', b);
}

/* Una TARJETA entera se saca de un click.

   Antes se sacaban los textos de a uno: para que la tarjeta desapareciera
   había que sacar su título Y su texto, y no era evidente que eso la hiciera
   desaparecer. Sacarla no la borra: queda tachada con un botón para traerla
   de vuelta, igual que un texto. */
function edNotas(v) {
  var viejos = document.querySelectorAll('.ed-nx, .ed-nv'), i;
  for (i = 0; i < viejos.length; i++) viejos[i].remove();
  var ns = document.querySelectorAll('.nota');
  for (i = 0; i < ns.length; i++) ns[i].classList.remove('fuera');
  if (!v) { edSolas(); return; }
  var cs = document.querySelectorAll('.nota[data-nota]');
  for (i = 0; i < cs.length; i++) {
    (function (n) {
      var claves = [], ts = n.querySelectorAll('.ed-t[data-txt]'), j;
      for (j = 0; j < ts.length; j++) claves.push(ts[j].dataset.txt);
      var x = document.createElement('button');
      var volver = document.createElement('button');
      var poner = function (fuera) {
        for (var k = 0; k < claves.length; k++) {
          var t = n.querySelector('.ed-t[data-txt="' + claves[k] + '"]');
          if (fuera) { FUERA[claves[k]] = true; } else { delete FUERA[claves[k]]; }
          if (t) edPintarFuera(t, fuera);
        }
        n.classList.toggle('fuera', fuera);
        x.hidden = fuera; volver.hidden = !fuera;
        edSolas();
      };
      x.type = 'button'; x.className = 'ed-nx';
      x.title = 'Sacar esta tarjeta del reporte';
      x.textContent = '\u00D7';
      x.onclick = function (ev) { ev.preventDefault(); edMarca(); poner(true); };
      volver.type = 'button'; volver.className = 'ed-nv';
      volver.textContent = 'Volver a mostrar';
      volver.hidden = true;
      volver.onclick = function (ev) { ev.preventDefault(); edMarca(); poner(false); };
      n.appendChild(x); n.appendChild(volver);
      // una tarjeta que ya venía sacada arranca tachada
      var todas = claves.length && claves.every(function (k) { return FUERA[k]; });
      if (todas) poner(true);
    }(cs[i]));
  }
  edSolas();
}

/* Si queda UNA tarjeta a la vista, se centra. Una tarjeta sola estirada a
   1180 px con dos renglones adentro se lee peor que centrada. */
function edSolas() {
  var cajas = document.querySelectorAll('.notas'), i;
  for (i = 0; i < cajas.length; i++) {
    var vivas = 0, ns = cajas[i].querySelectorAll('.nota'), j;
    for (j = 0; j < ns.length; j++) {
      if (!ns[j].classList.contains('fuera')) vivas++;
    }
    cajas[i].classList.toggle('sola', vivas === 1);
  }
}

/* Los interruptores de cada lámina: cómo se ve la lista y de qué color va el
   fondo. Se dibujan al entrar en edición y se sacan al salir: no tienen por
   qué estar en la lámina cuando se está mostrando.

   ⚠️ Mandan sobre TODAS las láminas de la misma sección. Una lista larga son
   varias láminas con el mismo `data-sec`, y que la página 1 quede clara y la
   2 oscura no es una elección: es un descuido. */
function edVistas(v) {
  var viejos = document.querySelectorAll('.ed-v'), i;
  for (i = 0; i < viejos.length; i++) viejos[i].remove();
  if (!v) return;
  var secs = document.querySelectorAll('.slide[data-sec]');
  for (i = 0; i < secs.length; i++) {
    (function (sl) {
      var sec = sl.dataset.sec;
      var hermanas = document.querySelectorAll('.slide[data-sec="' + sec + '"]');
      var caja = document.createElement('div');
      caja.className = 'ed-v';
      if (sl.dataset.lista) {
        var puesta = sl.querySelector('.lista-v:not([hidden])');
        if (!(sec in VISTAS)) {
          VISTAS[sec] = puesta ? puesta.dataset.vista : 'barras';
        }
        caja.appendChild(edFila('Vista',
          [['barras', 'Barras'], ['columnas', 'Columnas'], ['tabla', 'Tabla']],
          VISTAS[sec], function (cual) {
            VISTAS[sec] = cual;
            /* la lámina trae las tres listas armadas: cambiar de vista es
               mostrar una y esconder las otras, y se ve en el acto. Antes esto
               solo anotaba la elección y no pasaba nada hasta guardar. */
            for (var h = 0; h < hermanas.length; h++) {
              var vs = hermanas[h].querySelectorAll('.lista-v');
              for (var m = 0; m < vs.length; m++) {
                vs[m].hidden = vs[m].dataset.vista !== cual;
              }
            }
          }));
      }
      if (!(sec in FONDOS)) {
        FONDOS[sec] = sl.classList.contains('dark') ? 'oscuro' : 'claro';
      }
      caja.appendChild(edFila('Fondo',
        [['claro', 'Claro'], ['oscuro', 'Oscuro']], FONDOS[sec],
        function (cual) {
          FONDOS[sec] = cual;
          for (var h = 0; h < hermanas.length; h++) {
            hermanas[h].classList.toggle('dark', cual === 'oscuro');
          }
        }));
      /* Sacar la lámina entera. La portada y los límites no: la portada dice
         de qué período habla y los límites lo que el reporte no puede afirmar.
         Sacarla la marca y recién se va al guardar; hasta entonces se puede
         volver atrás. Una lista larga son varias láminas: se van todas. */
      if (sec !== 'portada' && sec !== 'limites') edBotonSacar(caja, sec, hermanas);
      sl.appendChild(caja);
    }(secs[i]));
  }
}

function edBotonSacar(caja, sec, hermanas) {
  var b = document.createElement('button');
  b.type = 'button'; b.className = 'ed-sacar';
  var pintar = function () {
    var fuera = !!SACADAS[sec];
    b.textContent = fuera ? 'Volver a poner esta hoja' : 'Eliminar esta hoja';
    b.classList.toggle('on', fuera);
    for (var h = 0; h < hermanas.length; h++) hermanas[h].classList.toggle('sacada', fuera);
  };
  b.onclick = function (ev) {
    ev.preventDefault();
    edMarca();
    if (SACADAS[sec]) { delete SACADAS[sec]; } else { SACADAS[sec] = true; }
    /* el mismo botón está en cada lámina de la sección: se pintan todos */
    var bs = document.querySelectorAll('.slide[data-sec="' + sec + '"] .ed-sacar');
    for (var j = 0; j < bs.length; j++) bs[j]._pintar();
    if (SACADAS[sec]) {
      edDecir((hermanas.length > 1
               ? 'Esta lista ocupa ' + hermanas.length + ' hojas: se eliminan todas '
               : 'Esta hoja se elimina ') +
              'cuando aprietes <b>Guardar edición</b>. Hasta entonces, ' +
              '<b>Deshacer</b> la trae de vuelta.');
    }
    edHojaPintar();
  };
  b._pintar = pintar;
  var fila = document.createElement('div');
  fila.className = 'ed-fila';
  fila.appendChild(b);
  caja.appendChild(fila);
  pintar();
}

/* Una fila de botones que se excluyen entre sí. */
function edFila(rotulo, opciones, puesto, alElegir) {
  var fila = document.createElement('div');
  fila.className = 'ed-fila';
  var r = document.createElement('span');
  r.textContent = rotulo;
  fila.appendChild(r);
  opciones.forEach(function (par) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = par[1];
    if (puesto === par[0]) b.className = 'on';
    b.onclick = function () {
      edMarca();
      var bs = fila.querySelectorAll('button');
      for (var j = 0; j < bs.length; j++) bs[j].className = '';
      b.className = 'on';
      alElegir(par[0]);
    };
    fila.appendChild(b);
  });
  return fila;
}

/* Bajar el PDF sin salir del reporte.

   Antes, mirando el reporte, la unica salida era «Ctrl+P» —que es imprimir, no
   descargar— o cerrar la pestana y volver al panel a buscar la tarjeta.

   Se pide con fetch y no con un <a download> a proposito: si el servidor
   contesta un error, un link se lleva puesta la pagina y deja un JSON en crudo
   donde estaba el reporte. Asi, el error se dice y el reporte no se mueve. */
function edPdf() {
  var b = document.getElementById('edPdf');
  var antes = b.innerHTML;
  b.disabled = true;
  b.innerHTML = '<span class="pt">&#8681;</span>Armando el PDF…';
  var volver = function () { b.disabled = false; b.innerHTML = antes; };
  fetch('/api/datos/deck-pdf?id=' + encodeURIComponent(ED.id) +
        '&informe=' + encodeURIComponent(ED.inf)).then(function (r) {
    var tipo = r.headers.get('content-type') || '';
    if (!r.ok || tipo.indexOf('application/json') >= 0) {
      return r.json().then(function (j) {
        throw new Error((j && j.error) || 'no se pudo armar el PDF');
      }, function () { throw new Error('no se pudo armar el PDF'); });
    }
    var nombre = 'reporte.pdf';
    var cd = r.headers.get('content-disposition') || '';
    var i = cd.toLowerCase().indexOf('filename=');
    if (i >= 0) {
      nombre = cd.slice(i + 9).split(';')[0].trim();
      if (nombre.charAt(0) === '"') nombre = nombre.slice(1, -1);
    }
    return r.blob().then(function (bl) {
      var u = URL.createObjectURL(bl);
      var a = document.createElement('a');
      a.href = u; a.download = nombre;
      document.body.appendChild(a); a.click(); a.remove();
      /* el revoke va diferido: cortando el objeto en el mismo tic hay
         navegadores que bajan un archivo de 0 bytes */
      setTimeout(function () { URL.revokeObjectURL(u); }, 4000);
      edDecir('Listo: <b>' + nombre + '</b>');
      volver();
    });
  }).catch(function (e) {
    edDecir('No pude armar el PDF: ' + (e.message || 'proba de nuevo') + '.', true);
    volver();
  });
}

function edGuardar() {
  var ts = {}, ns = edTextos(), i, hubo = false;
  for (i = 0; i < ns.length; i++) {
    var k = ns[i].dataset.txt;
    if (FUERA[k]) continue;          // sacado: no es un texto cambiado
    var v = ns[i].textContent.replace(/\\s+/g, ' ').trim();
    if (v !== (ORIG[k] || '').replace(/\\s+/g, ' ').trim()) { ts[k] = v; hubo = true; }
  }
  var ok = document.getElementById('edOk');
  var cuerpo = { id: ED.id, informe: ED.inf,
                 opciones: { textos: ts, vistas: VISTAS, fondos: FONDOS,
                             ocultos: Object.keys(FUERA) } };
  /* las láminas sacadas: el reporte deja de medir esa sección */
  if (Object.keys(SACADAS).length) {
    var quedan = (EDINF.secciones || []).filter(function (k) { return !SACADAS[k]; });
    if (!quedan.length) {
      edDecir('Tiene que quedar al menos una lámina además de la portada.', true);
      return false;
    }
    cuerpo.secciones = quedan;
  }
  ok.disabled = true; ok.textContent = 'Guardando…';
  edMandar(cuerpo).then(function () {
    /* se recarga a propósito: el reporte se arma en el servidor, así que lo
       que se ve después de guardar es EXACTAMENTE lo que se va a bajar en PDF
       o en Word. Sin esto, la pantalla y el archivo podrían no coincidir. */
    edRecargar();
  }).catch(function (err) {
    ok.disabled = false; ok.textContent = 'Guardar edición';
    edDecir('No pude guardar: ' + (err.message || 'probá de nuevo') + '.', true);
  });
  return hubo;
}

/* Manda un cambio y guarda antes cómo estaba, para «Deshacer lo guardado». */
function edMandar(cuerpo) {
  try {
    sessionStorage.setItem('deck-previo-' + ED.inf, JSON.stringify(GUARDADO));
  } catch (e) { /* sin sessionStorage no hay «deshacer lo guardado»: guarda igual */ }
  return fetch('/api/datos/informe-editar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo)
  }).then(function (r) { return r.json(); }).then(function (j) {
    if (j && j.error) throw new Error(j.error);
    return j;
  });
}

function edPrevio() {
  try {
    var t = sessionStorage.getItem('deck-previo-' + ED.inf);
    return t ? JSON.parse(t) : null;
  } catch (e) { return null; }
}

/* Vuelve a como estaba antes del último guardado. Se manda el estado entero
   con `reemplazar`: si solo se sumara, lo agregado en ese guardado quedaría. */
function edDeshacerGuardado() {
  var p = edPrevio();
  if (!p) return;
  var b = document.getElementById('edDeshGuardado');
  b.disabled = true;
  fetch('/api/datos/informe-editar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: ED.id, informe: ED.inf, secciones: p.secciones,
                           opciones: { textos: p.textos || {}, vistas: p.vistas || {},
                                       fondos: p.fondos || {},
                                       ocultos: p.ocultos || [], reemplazar: true } })
  }).then(function (r) { return r.json(); }).then(function (j) {
    if (j && j.error) throw new Error(j.error);
    try { sessionStorage.removeItem('deck-previo-' + ED.inf); } catch (e) {}
    edRecargar();
  }).catch(function (err) {
    b.disabled = false;
    edDecir('No pude deshacer: ' + (err.message || 'probá de nuevo') + '.', true);
  });
}

/* ── Deshacer, de a un paso ── */
function edFoto() {
  var t = [], ns = edTextos(), i;
  for (i = 0; i < ns.length; i++) t.push(ns[i].textContent);
  var c = function (x) { return JSON.parse(JSON.stringify(x)); };
  return { t: t, fuera: c(FUERA), vistas: c(VISTAS), fondos: c(FONDOS), sacadas: c(SACADAS) };
}
function edMarca() {
  HIST.push(edFoto());
  if (HIST.length > 80) HIST.shift();
  edBotonDeshacer();
}
function edBotonDeshacer() {
  var b = document.getElementById('edDeshacer');
  b.hidden = !EDIT;
  b.disabled = !HIST.length;
}
/* pone en pantalla lo que dicen VISTAS, FONDOS y SACADAS */
function edAplicar() {
  var sls = document.querySelectorAll('.slide[data-sec]'), i, m;
  for (i = 0; i < sls.length; i++) {
    var sec = sls[i].dataset.sec;
    if (sec in FONDOS) sls[i].classList.toggle('dark', FONDOS[sec] === 'oscuro');
    if (sec in VISTAS) {
      var vs = sls[i].querySelectorAll('.lista-v');
      for (m = 0; m < vs.length; m++) vs[m].hidden = vs[m].dataset.vista !== VISTAS[sec];
    }
    sls[i].classList.toggle('sacada', !!SACADAS[sec]);
  }
}
function edDeshacer() {
  var f = HIST.pop();
  if (!f) return;
  var ns = edTextos(), i;
  for (i = 0; i < ns.length; i++) {
    if (i < f.t.length) ns[i].textContent = f.t[i];
    ns[i].classList.remove('fuera');
    ns[i].contentEditable = 'true';
  }
  FUERA = f.fuera; VISTAS = f.vistas; FONDOS = f.fondos; SACADAS = f.sacadas;
  edAplicar();
  edEquis(true); edNotas(true); edVistas(true);
  edBotonDeshacer(); edHojaPintar();
}
/* escribir en un texto: una foto al empezar, no una por letra */
document.addEventListener('focusin', function (ev) {
  if (EDIT && ev.target.classList && ev.target.classList.contains('ed-t')) FOTO_PEND = edFoto();
});
document.addEventListener('input', function (ev) {
  if (EDIT && FOTO_PEND && ev.target.classList && ev.target.classList.contains('ed-t')) {
    HIST.push(FOTO_PEND); FOTO_PEND = null; edBotonDeshacer();
  }
});

/* ── Eliminar la hoja que se está mirando ──
   Editando, la marca (se va al guardar, y Deshacer la trae). Sin editar,
   pregunta y la saca en el acto. La portada y los límites no se eliminan. */
function edHojaActual() {
  var s = SLIDES[actual];
  var sec = (s && s.dataset.sec) || '';
  return (sec === 'portada' || sec === 'limites') ? '' : sec;
}
function edHojaPintar() {
  var b = document.getElementById('edHoja');
  if (!b || !(ED.id && ED.inf) || typeof SLIDES === 'undefined') return;
  var sec = edHojaActual();
  b.hidden = !sec;
  b.textContent = (EDIT && SACADAS[sec]) ? 'Volver a poner esta hoja' : 'Eliminar esta hoja';
}
function edHojaClick() {
  var sec = edHojaActual();
  if (!sec) return;
  if (EDIT) {
    var bs = SLIDES[actual].querySelector('.ed-sacar');
    if (bs) bs.click();
    return;
  }
  var n = document.querySelectorAll('.slide[data-sec="' + sec + '"]').length;
  var quedan = (EDINF.secciones || []).filter(function (k) { return k !== sec; });
  if (!quedan.length) {
    edDecir('Tiene que quedar al menos una hoja además de la portada.', true);
    return;
  }
  if (!window.confirm((n > 1 ? '¿Eliminar esta lista del reporte? Ocupa ' + n + ' hojas.'
                             : '¿Eliminar esta hoja del reporte?') +
                      '\\n\\nSe puede volver atrás con «Deshacer lo guardado».')) return;
  var b = document.getElementById('edHoja');
  b.disabled = true;
  edMandar({ id: ED.id, informe: ED.inf, opciones: {}, secciones: quedan })
    .then(edRecargar)
    .catch(function (err) {
      b.disabled = false;
      edDecir('No pude eliminarla: ' + (err.message || 'probá de nuevo') + '.', true);
    });
}

/* ── Volver a la misma hoja después de guardar ──
   La recarga arrancaba siempre en la portada. Se anota dónde estaba (la
   sección y qué hoja de ella) y se vuelve ahí; si esa hoja ya no está
   (se eliminó), se queda en la que ocupó su lugar. */
function edRecargar() {
  var s = SLIDES[actual], sec = (s && s.dataset.sec) || '';
  var hs = document.querySelectorAll('.slide[data-sec="' + sec + '"]');
  var k = Array.prototype.indexOf.call(hs, s);
  try {
    history.replaceState(null, '', location.pathname + location.search +
                         '#l=' + actual + '&s=' + encodeURIComponent(sec) + '&k=' + k);
  } catch (e) {}
  location.reload();
}
function edLugarGuardado() {
  var h = new URLSearchParams((location.hash || '').replace(/^#/, ''));
  if (!h.has('l')) return 0;
  var sec = h.get('s') || '', k = parseInt(h.get('k') || '0', 10) || 0;
  var hs = sec ? document.querySelectorAll('.slide[data-sec="' + sec + '"]') : [];
  if (hs.length) {
    return Array.prototype.indexOf.call(SLIDES, hs[Math.min(k, hs.length - 1)]);
  }
  return parseInt(h.get('l'), 10) || 0;
}

if (ED.id && ED.inf) {
  document.body.classList.add('con-editor');
  document.getElementById('ed').hidden = false;
  document.getElementById('edPdf').onclick = edPdf;
  document.getElementById('edBtn').onclick = function () { edPrender(!EDIT); };
  document.getElementById('edOk').onclick = edGuardar;
  document.getElementById('edVolver').onclick = function () {
    /* se sacan de la lista y se guarda: vuelven a dibujarse */
    (EDINF.ocultos || []).forEach(function (k) { delete FUERA[k]; });
    EDINF.ocultos = [];
    edGuardar();
  };
  document.getElementById('edNo').onclick = function () { edRecargar(); };
  document.getElementById('edDeshacer').onclick = edDeshacer;
  document.getElementById('edHoja').onclick = edHojaClick;
  document.getElementById('edDeshGuardado').onclick = edDeshacerGuardado;
  document.getElementById('edDeshGuardado').hidden = !edPrevio();
}

var SLIDES = document.querySelectorAll('.slide');
var TOTAL = SLIDES.length, actual = 0;
function ir(n){
  actual = Math.max(0, Math.min(TOTAL - 1, n));
  for (var i = 0; i < TOTAL; i++) SLIDES[i].classList.toggle('active', i === actual);
  document.getElementById('ahora').textContent = actual + 1;
  document.getElementById('barra').style.width = (100 * (actual + 1) / TOTAL) + '%%';
  edHojaPintar();
}
function mover(d){ ir(actual + d); }
document.addEventListener('keydown', function (ev) {
  /* editando, las teclas son para escribir: pasar de lámina con la flecha
     mientras se está tipeando es perder lo escrito sin entender por qué */
  if (EDIT) {
    if (ev.key === 'Escape') { document.activeElement.blur(); }
    return;
  }
  if (ev.key === 'ArrowRight' || ev.key === 'PageDown' || ev.key === ' ') { mover(1); ev.preventDefault(); }
  else if (ev.key === 'ArrowLeft' || ev.key === 'PageUp') { mover(-1); ev.preventDefault(); }
  else if (ev.key === 'Home') ir(0);
  else if (ev.key === 'End') ir(TOTAL - 1);
  else if (ev.key === 'f' || ev.key === 'F') {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  }
});
/* deslizar con el dedo, para mirarlo en el celular */
var x0 = null;
document.addEventListener('touchstart', function (ev) { x0 = ev.touches[0].clientX; });
document.addEventListener('touchend', function (ev) {
  if (x0 === null) return;
  var dx = ev.changedTouches[0].clientX - x0;
  if (Math.abs(dx) > 55) mover(dx < 0 ? 1 : -1);
  x0 = null;
});
ir((ED.id && ED.inf) ? edLugarGuardado() : 0);
</script>
</body></html>"""
