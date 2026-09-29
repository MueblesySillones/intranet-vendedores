# -*- coding: utf-8 -*-
"""El ritmo de la semana, el cruce producto × campaña, y que los dos formatos
del reporte digan lo mismo.

QUÉ SE PRUEBA Y POR QUÉ

Las cuatro preguntas que faltaban de la lista del equipo:

  · «¿cuántas derivaciones se realizan por día? un promedio»
  · «¿cuáles son los días que se reciben más consultas?»
  · «¿de cuántos orígenes no sabemos de dónde vienen?»
  · «¿de qué origen vienen las consultas de x productos?»

Y una que no se pidió pero que las sostiene: el reporte sale en PDF y en Word,
y hasta ahora cada formato armaba sus láminas por su cuenta. Las notas de esas
láminas no son adornos, son cuentas —el sábado que se deriva a la mitad, el
10× de la zona contra lo lejano—. Escritas dos veces, tarde o temprano el PDF
y el Word dicen números distintos y nadie se entera salvo abriendo los dos.
La prueba de abajo compara los dos formatos fila por fila.

    python test_ritmo.py
"""
import datetime
import json
import os
import re
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos import deck  # noqa: E402
from datos import deck_word  # noqa: E402
from datos import derivaciones as D  # noqa: E402

RES = []
CAB = ["Fecha", "Vendedor", "Sucursal", "Respuesta Final", "Producto",
       "Origen", "Localidad"]
HOY = datetime.date(2026, 9, 5)


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(True)
        print("PASS | %s | %s" % (nombre, nota))
    except AssertionError as e:
        RES.append(False)
        print("FAIL | %s | %s" % (nombre, e))


def analizar(filas):
    tmp = tempfile.mkdtemp(prefix="ritmo_")
    return D.analizar([CAB] + filas, tmp, hoy=HOY)


def fila(fecha, vend="AGUSTINA", prod="", origen="", suc="HUDSON"):
    return [fecha, vend, suc, "", prod, origen, ""]


# Agosto 2026: el 3 es lunes. Se usan días sueltos a propósito —hay huecos—
# para que se note si el promedio se calcula sobre el calendario.
LUNES, SABADO = "3/8/2026", "8/8/2026"


# ─────────────────── el promedio por día ───────────────────
def caso_promedio_sobre_dias_con_movimiento():
    """⚠️ La cuenta es sobre los días QUE TUVIERON ALGO, no sobre los del
    calendario. Entre el 3 y el 20 de agosto hay 18 días corridos; si se
    dividiera por ahí, el promedio daría 0,3 en vez de 2."""
    filas = ([fila(LUNES)] * 3 + [fila("10/8/2026")] * 1
             + [fila("20/8/2026")] * 2)
    d = analizar(filas)
    assert d["dias_con_movimiento"] == 3, (
        "conto %s dias" % d["dias_con_movimiento"])
    prom = d["total"]["consultas"] / float(d["dias_con_movimiento"])
    assert abs(prom - 2.0) < 0.01, "el promedio dio %.2f" % prom
    return "6 consultas en 3 días con movimiento = 2 por día (no 0,3)"


check("el promedio se divide por los días que tuvieron movimiento",
      caso_promedio_sobre_dias_con_movimiento)


def caso_dia_pico():
    filas = [fila(LUNES)] * 3 + [fila("10/8/2026")] * 7
    d = analizar(filas)
    p = d["dia_mas_cargado"]
    assert p["fecha"] == "2026-08-10", "el pico dio %r" % p
    assert p["consultas"] == 7, "conto %s" % p["consultas"]
    return "el día más cargado es el 10/8 con 7"


check("el día más cargado es el que más entró", caso_dia_pico)


def caso_todo_viaja_como_texto():
    """El diccionario del análisis tiene que poder ir en un JSON entero. Un
    objeto `date` adentro no falla acá: falla el día que alguien lo serialice."""
    d = analizar([fila(LUNES)] * 2)
    json.dumps(d)
    return "el análisis entero entra en un JSON"


check("nada del análisis es un objeto de Python", caso_todo_viaja_como_texto)


# ─────────────────── qué días entran ───────────────────
def caso_dias_de_la_semana():
    d = analizar([fila(LUNES)] * 4 + [fila(SABADO)] * 2)
    ds = d["dias_semana"]
    assert ds[0]["consultas"] == 4, "el lunes conto %s" % ds[0]["consultas"]
    assert ds[5]["consultas"] == 2, "el sabado conto %s" % ds[5]["consultas"]
    assert sum(v["consultas"] for v in ds.values()) == 6
    return "lunes 4, sábado 2, y nada en los otros"


check("cada consulta cae en su día de la semana", caso_dias_de_la_semana)


def caso_un_dia_sin_nada_no_aparece():
    p = deck.partes_ritmo(analizar([fila(LUNES)] * 3))
    dias = [f[0] for f in p["filas"]]
    assert dias == ["Lunes"], "la lámina muestra %r" % dias
    return "una semana con un solo día no dibuja seis renglones en cero"


check("un día sin consultas no ocupa una fila", caso_un_dia_sin_nada_no_aparece)


# ────────── el sábado: la lectura que se destaca sola ──────────
def caso_el_sabado_que_no_deriva():
    """Lo que se marca es el fin de semana que se DERIVA mucho menos que un día
    hábil. No es una frase escrita a mano: sale de comparar las dos tasas."""
    filas = ([fila(LUNES)] * 5 + [fila(LUNES, vend="")] * 5      # lunes: 50%
             + [fila(SABADO)] * 1 + [fila(SABADO, vend="")] * 9)  # sábado: 10%
    p = deck.partes_ritmo(analizar(filas))
    notas = " ".join(x for _, x in p["lineas"])
    assert "sábado" in notas, "no dijo nada del sábado:\n%s" % notas
    assert "10%" in notas and "50%" in notas, "faltan las dos tasas:\n%s" % notas
    return "compara el 10% del sábado contra el 50% de lunes a viernes"


check("el fin de semana que no se deriva queda señalado",
      caso_el_sabado_que_no_deriva)


def caso_un_sabado_normal_no_se_señala():
    """Y al revés: si el sábado deriva como cualquier día, no hay nada que
    decir. Una lámina que siempre encuentra un problema no sirve para nada."""
    filas = ([fila(LUNES)] * 5 + [fila(LUNES, vend="")] * 5
             + [fila(SABADO)] * 5 + [fila(SABADO, vend="")] * 5)
    p = deck.partes_ritmo(analizar(filas))
    assert len(p["lineas"]) == 1, "inventó una nota: %r" % p["lineas"][1:]
    return "un sábado que deriva igual no genera advertencia"


check("no se inventa un problema donde no lo hay",
      caso_un_sabado_normal_no_se_señala)


# ─────────────────── de dónde viene cada producto ───────────────────
def caso_cruce_producto_origen():
    filas = ([fila(LUNES, prod="Sillones", origen="PROMO SILLONES")] * 7
             + [fila(LUNES, prod="Sillones", origen="WEB")] * 3
             + [fila(LUNES, prod="Mesas", origen="WEB")] * 4)
    d = analizar(filas)
    assert d["producto_origen"]["Sillones"]["PROMO SILLONES"] == 7
    p = deck.partes_prod_origen(d)
    assert p["filas"][0][0] == "Sillones", "primero quedó %r" % p["filas"][0][0]
    assert "70%" in p["filas"][0][2], "no dice la parte: %r" % p["filas"][0][2]
    return "Sillones: 10 consultas, el 70% de Promo Sillones"


check("cada producto dice qué campaña lo trae", caso_cruce_producto_origen)


def caso_sin_origen_se_cuenta_y_se_marca():
    """«¿De cuántos orígenes no sabemos de dónde vienen?» Y el producto que
    llega sobre todo sin origen se marca: ahí no hay nada que aprender."""
    filas = ([fila(LUNES, prod="Mesas", origen="")] * 6
             + [fila(LUNES, prod="Mesas", origen="WEB")] * 2)
    d = analizar(filas)
    assert d["sin_origen"] == 6, "conto %s" % d["sin_origen"]
    nota = deck.nota_sin_origen(d)
    assert nota and "75%" in nota[1], "la nota dice %r" % (nota,)
    p = deck.partes_prod_origen(d)
    assert D.SIN_ORIGEN in p["filas_t"][0][2], (
        "no marcó la fila sin origen: %r" % p["filas_t"][0][2])
    assert "no se puede decir qué campaña" in " ".join(x for _, x in p["lineas"])
    return "6 de 8 sin origen: lo dice la lámina y lo marca la fila"


check("las consultas sin origen se cuentan y se muestran",
      caso_sin_origen_se_cuenta_y_se_marca)


def caso_los_porcentajes_no_cuentan_las_sin_origen():
    """La lámina de orígenes reparte el 100% entre las que SÍ tienen origen.
    Si contara las vacías, «Web con el 50%» significaría otra cosa."""
    filas = ([fila(LUNES, origen="WEB")] * 5
             + [fila(LUNES, origen="")] * 5)
    d = analizar(filas)
    html = deck.armar(d, "x", ["origenes"])
    plano = re.sub(r"<[^>]+>", " ", html)
    assert "100%" in plano, "Web no quedó como el 100% de las que tienen origen"
    assert "50%" in plano, "no avisa que la mitad entró sin origen"
    return "Web es el 100% de las que tienen origen, y la mitad no tiene"


check("los porcentajes se calculan sobre las que tienen origen",
      caso_los_porcentajes_no_cuentan_las_sin_origen)


# ────────── que el PDF y el Word digan lo mismo ──────────
def _planilla_completa():
    """Una planilla chica pero con todo: días, productos, orígenes, provincias
    y localidades, para que las cinco láminas tengan algo que mostrar."""
    filas = []
    for i, dia in enumerate(("3/8/2026", "4/8/2026", "8/8/2026")):
        filas += [fila(dia, prod="Sillones", origen="PROMO SILLONES")] * (3 + i)
        filas += [fila(dia, prod="Mesas", origen="")] * 2
    for loc in ("HUDSON", "QUILMES", "CORDOBA", "NEUQUEN", "ZONA NORTE"):
        f = fila("5/8/2026", prod="Sillas", origen="WEB")
        f[6] = loc
        filas.append(f)
    f = fila("5/8/2026", vend="MALENA", prod="Sillas", origen="WEB")
    f[6] = "CORDOBA"
    filas.append(f)
    return analizar(filas)


def caso_word_tiene_las_cinco_laminas():
    """Zonas, provincias y reparto nunca se habían escrito del lado del Word:
    el mismo reporte, bajado en Word, no las tenía."""
    d = _planilla_completa()
    ruta = os.path.join(tempfile.mkdtemp(prefix="ritmo_"), "r.docx")
    deck_word.a_word(d, ruta, "Prueba")
    x = zipfile.ZipFile(ruta).read("word/document.xml").decode("utf-8")
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))
    faltan = [t for t in ("Cuánto entra por día",
                          "De qué campaña viene cada producto",
                          "De la zona del local",
                          "De qué provincias nos escriben",
                          "Quién atiende las consultas")
              if t not in texto]
    assert not faltan, "el Word no tiene: %s" % ", ".join(faltan)
    return "las cinco láminas están también en el Word"


check("el Word no se queda atrás del PDF", caso_word_tiene_las_cinco_laminas)


def caso_los_dos_formatos_dicen_lo_mismo():
    """La prueba que justifica el refactor: cada número de cada fila de cada
    lámina tiene que aparecer igual en los dos formatos."""
    d = _planilla_completa()
    ruta = os.path.join(tempfile.mkdtemp(prefix="ritmo_"), "r.docx")
    deck_word.a_word(d, ruta, "Prueba")
    x = zipfile.ZipFile(ruta).read("word/document.xml").decode("utf-8")
    word = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))
    html = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", deck.armar(d, "Prueba")))

    partes = [deck.partes_ritmo(d), deck.partes_prod_origen(d),
              deck.partes_zonas(d), deck.partes_provincias(d),
              deck.partes_reparto(d)]
    revisadas = 0
    for p in partes:
        assert p, "una lámina quedó vacía con esta planilla"
        for (nom, valor, _), (_, _, _, _) in zip(p["filas_w"], p["filas"]):
            assert nom in word, "%s: «%s» no está en el Word" % (p["sec"], nom)
            assert nom in html, "%s: «%s» no está en el HTML" % (p["sec"], nom)
            assert valor in word, "%s: «%s» sin su número" % (p["sec"], nom)
            revisadas += 1
        for _, texto in p["lineas"]:
            t = str(texto).strip()
            if t:
                assert t in word, "%s: la nota no está en el Word" % p["sec"]
                assert t in html, "%s: la nota no está en el HTML" % p["sec"]
    return "%d filas y sus notas, iguales en los dos formatos" % revisadas


check("el PDF y el Word no pueden decir números distintos",
      caso_los_dos_formatos_dicen_lo_mismo)


def caso_una_lamina_sin_datos_no_se_dibuja():
    """Sin localidad no hay zonas ni provincias. Lo que no se sabe no se
    dibuja en cero: se saca."""
    d = analizar([fila(LUNES)] * 3)
    assert deck.partes_provincias(d) is None, "dibujó provincias sin ninguna"
    assert deck.partes_reparto(d) is None, "dibujó el reparto sin interior"
    html = deck.armar(d, "x")
    assert 'data-sec="provincias"' not in html
    return "sin datos, la lámina no aparece"


check("una lámina sin nada que mostrar no se dibuja",
      caso_una_lamina_sin_datos_no_se_dibuja)


# ────────── que las dos vistas digan lo mismo ──────────
def caso_barras_y_tabla_no_discrepan():
    d = _planilla_completa()
    for p in (deck.partes_ritmo(d), deck.partes_prod_origen(d),
              deck.partes_zonas(d)):
        for (a, va, _, _), (b, vb, _, _) in zip(p["filas"], p["filas_t"]):
            assert a == b and va == vb, (
                "%s: barras dice %r y la tabla %r" % (p["sec"], (a, va), (b, vb)))
    return "las mismas filas y los mismos valores en barras y en tabla"


check("barras y tabla son la misma lista", caso_barras_y_tabla_no_discrepan)


def caso_las_secciones_nuevas_se_pueden_elegir():
    """Si no están en SECCIONES, el asistente no las ofrece; si no están en
    CON_LISTA, el interruptor de barras/tabla no aparece."""
    ids = [k for k, _, _ in deck.SECCIONES]
    for k in ("ritmo", "prod_origen"):
        assert k in ids, "«%s» no se puede elegir al crear un reporte" % k
        assert k in deck.CON_LISTA, "«%s» no ofrece barras/tabla" % k
    assert ids.index("ritmo") == ids.index("meses") + 1, "el ritmo quedó suelto"
    return "las dos aparecen en el asistente y se pueden ver en tabla"


check("las láminas nuevas se pueden elegir y ver en tabla",
      caso_las_secciones_nuevas_se_pueden_elegir)


print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
