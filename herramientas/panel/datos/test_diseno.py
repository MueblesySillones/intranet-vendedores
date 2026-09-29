# -*- coding: utf-8 -*-
"""Las reglas de cómo se ve el reporte. Esto se proyecta en una reunión.

No prueba números —de eso se ocupan las otras suites— sino las decisiones de
diseño que, cuando se rompen, hacen que el reporte parezca hecho a las
apuradas:

  · una barra no ocupa toda la lámina, y con muchas van en dos columnas
  · las dos columnas comparten la escala (si no, el gráfico miente)
  · nada que exista se escribe «0%»
  · «PROMO ESQUINEROS Y SILLONES» no se muestra como «… Y Sillones»
  · una lámina que no tiene nada que contar no se dibuja

    python test_diseno.py
"""
import datetime
import os
import re
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos import deck  # noqa: E402
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


def fila(fecha, vend="AGUSTINA", prod="", origen="", suc="HUDSON"):
    return [fecha, vend, suc, "", prod, origen, ""]


def analizar(filas):
    return D.analizar([CAB] + filas, tempfile.mkdtemp(prefix="dis_"), hoy=HOY)


# Valores bien repartidos —de 100 a 2— a proposito: con todos parecidos, el
# corte del «numero afuera» no se toca nunca y la prueba no probaria nada.
VALORES = [100, 62, 48, 30, 22, 15, 11, 8, 5, 2, 2, 1]


def items(n):
    return [("Fila %02d" % i, VALORES[i], "%d" % VALORES[i], "#2C6E8A")
            for i in range(n)]


# ─────────────── las barras ───────────────
def caso_una_barra_no_ocupa_toda_la_lamina():
    """«las barras horizontales son muy largas y ocupan gran espacio de la
    pantalla… hay que administrar todo». El tope vive en el CSS, así que se
    comprueba que el CSS lo tenga: sin él, la barra vuelve a los 1.030 px."""
    assert "max-width:900px" in deck._CSS, "las barras ya no tienen tope de ancho"
    return "una columna de barras corta en 900 px, no en el borde de la hoja"


check("una barra no se estira de punta a punta",
      caso_una_barra_no_ocupa_toda_la_lamina)


def caso_muchas_barras_van_en_dos_columnas():
    pocas = deck.barras(items(5))
    muchas = deck.barras(items(10))
    assert "bars dos" not in pocas, "cinco filas no necesitan dos columnas"
    assert "bars dos" in muchas, "diez filas siguen en una sola columna"
    assert deck.BARRAS_EN_DOS <= 7, (
        "el corte quedó en %d: los siete motivos vuelven a salir a lo ancho"
        % deck.BARRAS_EN_DOS)
    return "de %d filas en adelante, dos columnas" % deck.BARRAS_EN_DOS


check("con muchas filas las barras van en dos columnas",
      caso_muchas_barras_van_en_dos_columnas)


def caso_las_dos_columnas_miden_igual():
    """⚠️ La prueba que importa de las dos columnas. Si cada una se midiera
    contra su propio máximo, la primera de la derecha se vería tan larga como
    la de la izquierda con la mitad del valor."""
    html = deck.barras(items(10))
    anchos = [float(x) for x in re.findall(r"width:([\d.]+)%", html)]
    assert len(anchos) == 10, "salieron %d barras" % len(anchos)
    # la fila 0 es la primera de la izquierda y la 5 la primera de la derecha
    assert anchos[0] > anchos[5] > anchos[9], (
        "el ancho no baja de corrido: %s" % anchos)
    assert abs(anchos[5] / anchos[0] - VALORES[5] / float(VALORES[0])) < 0.02, (
        "la columna derecha se mide contra su propio máximo: %s" % anchos[:6])
    return "una sola escala para las dos columnas"


check("las dos columnas comparten la escala",
      caso_las_dos_columnas_miden_igual)


def caso_la_barra_corta_escribe_el_numero_afuera():
    """Con la barra en media lámina, un 20% ya no tiene lugar para el texto."""
    una = deck.barras(items(5))
    dos = deck.barras(items(10))
    assert una.count("afuera") < dos.count("afuera"), (
        "en dos columnas tendrían que salir más números afuera")
    return "%d afuera en una columna, %d en dos" % (una.count("afuera"),
                                                    dos.count("afuera"))


check("en dos columnas el número sale afuera antes",
      caso_la_barra_corta_escribe_el_numero_afuera)


# ─────────────── los números escritos ───────────────
def caso_nunca_dice_cero_por_ciento_de_algo_que_existe():
    """2 de 475 sin decimales daba «0%» en una frase que hablaba justamente de
    esas 2: el reporte se desmentía solo."""
    assert deck.pct(2 / 475.0, 0) == "<1%", deck.pct(2 / 475.0, 0)
    assert deck.pct(0, 0) == "0%", "cero de verdad sí es 0%"
    assert deck.pct(0.00004, 1) == "<0,1%", deck.pct(0.00004, 1)
    assert deck.pct(0.53, 0) == "53%"
    return "2 sobre 475 se escribe «<1%», y el cero de verdad sigue siendo 0%"


check("algo que existe nunca se escribe 0%",
      caso_nunca_dice_cero_por_ciento_de_algo_que_existe)


def caso_los_nombres_no_gritan():
    assert deck.titulo_de("PROMO ESQUINEROS Y SILLONES") == \
        "Promo Esquineros y Sillones", deck.titulo_de("PROMO ESQUINEROS Y SILLONES")
    assert deck.titulo_de("IG ORGANICO") == "IG Organico"
    assert deck.titulo_de("CABA") == "CABA"
    assert deck.titulo_de("MARIA MARTA") == "Maria Marta"
    return "«Promo Esquineros y Sillones», no «… Y Sillones»"


check("los nombres se escriben como se escriben", caso_los_nombres_no_gritan)


# ─────────────── láminas que no tienen nada que contar ───────────────
def caso_un_solo_mes_no_lleva_lamina_de_meses():
    """Quedaba una tarjeta negra sola, a lo ancho de la lámina, diciendo
    «AGO · 475»: una hoja entera para repetir un número que el embudo ya dio."""
    uno = analizar([fila("%d/8/2026" % d) for d in (3, 10, 20)])
    dos = analizar([fila("%d/7/2026" % d) for d in (3, 10)] +
                   [fila("%d/8/2026" % d) for d in (3, 10)])
    assert 'data-sec="meses"' not in deck.armar(uno, "Agosto"), (
        "con un solo mes dibuja la lámina de mes a mes")
    assert 'data-sec="meses"' in deck.armar(dos, "Julio y agosto"), (
        "con dos meses NO la dibuja")
    return "un mes no la lleva; dos sí"


check("con un solo mes no hay «mes a mes»",
      caso_un_solo_mes_no_lleva_lamina_de_meses)


def caso_no_quedo_la_lamina_de_comparacion():
    """Se sacó: decía lo mismo que las cuatro tarjetas del embudo, en otra
    hoja y con otro dibujo."""
    a = analizar([fila("%d/8/2026" % d) for d in (3, 10, 20)])
    b = analizar([fila("%d/7/2026" % d) for d in (3, 10)])
    html = deck.armar(a, "Agosto", None, {"previo": b, "previo_txt": "julio"})
    assert 'data-sec="comparacion"' not in html, "volvió la lámina"
    assert "La comparación" not in html
    # dos chips alcanzan: en una planilla de prueba sin ventas, «ventas» y
    # «sin derivar» no tienen contra qué compararse y no inventan un numero
    chips = re.findall(r'class="ccmp [^"]*">([^<]+)<', html)
    assert len(chips) >= 2 and all("julio" in c for c in chips), (
        "el embudo no compara: %s" % chips)
    return "la comparación vive en el embudo: %s" % " · ".join(chips[:2])


check("la comparación no está duplicada en una lámina",
      caso_no_quedo_la_lamina_de_comparacion)


# ─────────────── las columnas ───────────────
def caso_las_columnas_tienen_linea_de_base():
    """Sin línea, las barras paradas flotan; con el carril pintado, la columna
    se lee como si tuviera dos partes."""
    assert ".cols::after" in deck._CSS, "las columnas perdieron la línea de base"
    assert "max-width:84px" in deck._CSS, (
        "las columnas no tienen ancho máximo: con siete días eran bloques")
    return "línea de base propia y columnas de 84 px como mucho"


check("el gráfico de columnas se lee como un gráfico",
      caso_las_columnas_tienen_linea_de_base)


def caso_las_tres_vistas_dicen_lo_mismo():
    d = analizar([fila("3/8/2026", prod="Sillones", origen="WEB")] * 9 +
                 [fila("4/8/2026", prod="Mesas", origen="PROMO")] * 4)
    p = deck.partes_productos(d)
    for i, (etq, val, _, _) in enumerate(p["filas"]):
        assert p["filas_t"][i][0] == etq and p["filas_t"][i][1] == val, (
            "la tabla dice otra cosa en la fila %d" % i)
        assert p["filas_w"][i][0] == etq, "el Word dice otra cosa"
    return "las mismas filas y los mismos valores en las tres vistas"


check("barras, columnas y tabla son la misma lista",
      caso_las_tres_vistas_dicen_lo_mismo)


print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
