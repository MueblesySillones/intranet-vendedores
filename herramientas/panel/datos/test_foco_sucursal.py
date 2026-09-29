# -*- coding: utf-8 -*-
"""Un reporte de UNA sucursal, y el podio para felicitar.

Lo pidió el equipo: *«que haya un apartado donde se pueda seleccionar si el
reporte que se va a hacer es por la cantidad de derivaciones a una sola
sucursal… cuántas consultas se realizaron, cuántas derivaciones se realizaron a
esa sucursal, y cuántas se vendieron»* y *«un ranking, tipo como para
felicitarlos, los primeros cuatro»*.

⚠️ LA REGLA QUE ESTAS PRUEBAS PROTEGEN

Una consulta NO TIENE SUCURSAL hasta que se deriva. Así que en el reporte de
Hudson, las derivaciones y las ventas son de Hudson, pero las consultas son las
del período entero. Repartirlas «a prorrata» daría un número redondo y falso.

    python test_foco_sucursal.py
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
CAB = ["Fecha", "Vendedor", "Sucursal", "Respuesta Final"]
HOY = datetime.date(2026, 9, 5)
VENTA = "REALIZO LA COMPRA"


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(True)
        print("PASS | %s | %s" % (nombre, nota))
    except AssertionError as e:
        RES.append(False)
        print("FAIL | %s | %s" % (nombre, e))


def fila(vend="", suc="", venta=False):
    return ["3/8/2026", vend, suc, VENTA if venta else ""]


def analizar(filas, suc=None):
    return D.analizar([CAB] + filas, tempfile.mkdtemp(prefix="foco_"),
                      hoy=HOY, sucursal_f=suc)


# Una planilla chica y clara: 2 de Hudson (1 venta), 2 de CABA (1 venta) y
# 3 consultas que nadie atendió.
PLANILLA = ([fila("ANA", "HUDSON"), fila("ANA", "HUDSON", venta=True),
             fila("BETO", "CABA"), fila("BETO", "CABA", venta=True)] +
            [fila()] * 3)


def caso_las_consultas_no_se_reparten():
    """⚠️ La que más importa. Las consultas son del período entero: sumar las
    de todas las sucursales tiene que dar MÁS que el total, no el total."""
    todo = analizar(PLANILLA)
    hud = analizar(PLANILLA, "Hudson")
    caba = analizar(PLANILLA, "CABA")
    assert todo["total"]["consultas"] == 7, todo["total"]["consultas"]
    assert hud["total"]["consultas"] == 7, (
        "el reporte de Hudson recortó las consultas a %d: una consulta que "
        "nadie atendió no es de ninguna sucursal"
        % hud["total"]["consultas"])
    assert caba["total"]["consultas"] == 7
    return "las 7 consultas del período se ven enteras en los tres reportes"


check("las consultas no se reparten entre sucursales",
      caso_las_consultas_no_se_reparten)


def caso_las_derivaciones_si_son_del_local():
    hud = analizar(PLANILLA, "Hudson")
    caba = analizar(PLANILLA, "CABA")
    assert hud["total"]["derivaciones"] == 2, hud["total"]["derivaciones"]
    assert caba["total"]["derivaciones"] == 2
    assert hud["total"]["de_otra_sucursal"] == 2, (
        "no contó las que atendió el otro local: %s" % hud["total"])
    return "Hudson 2 derivaciones y 2 que atendió otro local"


check("las derivaciones son de la sucursal", caso_las_derivaciones_si_son_del_local)


def caso_la_venta_es_del_local_que_la_hizo():
    """Sin esto, el reporte de Hudson mostraba las 2 ventas de la empresa."""
    todo = analizar(PLANILLA)
    hud = analizar(PLANILLA, "Hudson")
    assert todo["total"]["ventas"] == 2, todo["total"]["ventas"]
    assert hud["total"]["ventas"] == 1, (
        "Hudson se quedó con %d ventas y solo hizo 1" % hud["total"]["ventas"])
    return "2 en la empresa, 1 en Hudson"


check("la venta se cuenta en el local que la hizo",
      caso_la_venta_es_del_local_que_la_hizo)


def caso_coincide_con_el_corte_global():
    """El reporte de Hudson tiene que decir lo mismo que la fila «Hudson» del
    reporte general. Si no coincidieran, uno de los dos miente."""
    todo = analizar(PLANILLA)
    for nombre in ("Hudson", "CABA"):
        uno = analizar(PLANILLA, nombre)
        g = todo["sucursales"].get(nombre) or {}
        assert uno["total"]["derivaciones"] == g.get("derivaciones"), (
            "%s: %s vs %s" % (nombre, uno["total"]["derivaciones"],
                              g.get("derivaciones")))
        assert uno["total"]["ventas"] == g.get("ventas")
    return "el reporte de un local dice lo mismo que su fila en el general"


check("el corte por sucursal coincide con el general",
      caso_coincide_con_el_corte_global)


def caso_el_embudo_nombra_la_sucursal():
    """Y dice qué es del local y qué no: sin esa aclaración, alguien lee «1.592
    consultas» en el reporte de Hudson y cree que son de Hudson."""
    hud = analizar(PLANILLA, "Hudson")
    html = deck.armar(hud, "Hudson · agosto")
    plano = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    assert "Derivadas a Hudson" in plano, "la tarjeta no nombra la sucursal"
    assert "Fueron a otra" in plano, "no dice cuántas atendió otro local"
    assert "no es de ninguna sucursal" in plano, (
        "no aclara que las consultas son del período entero")
    return "«Derivadas a Hudson», «Fueron a otra», y la aclaración"


check("el embudo de una sucursal dice qué es suyo y qué no",
      caso_el_embudo_nombra_la_sucursal)


def caso_sin_foco_el_embudo_es_el_de_siempre():
    todo = analizar(PLANILLA)
    plano = re.sub(r"<[^>]+>", " ", deck.armar(todo, "Agosto"))
    assert "Sin derivar" in plano, "el embudo general perdió «Sin derivar»"
    assert "Derivadas a" not in plano
    return "sin sucursal elegida, el embudo no cambió"


check("el reporte de toda la empresa queda igual",
      caso_sin_foco_el_embudo_es_el_de_siempre)


# ─────────────── el podio ───────────────
def caso_el_podio_ordena_por_ventas():
    """⚠️ Por VENTAS, no por conversión. La conversión sobre pocos casos se
    mueve sola: quien recibe 10 y cierra 2 saca 20%, y al mes siguiente recibe
    40 y cierra 2 y saca 5% sin haber hecho nada distinto."""
    filas = ([fila("POCAS", "HUDSON", venta=True)] +
             [fila("POCAS", "HUDSON")] +                 # 1 de 2  = 50%
             [fila("MUCHAS", "CABA", venta=True) for _ in range(3)] +
             [fila("MUCHAS", "CABA") for _ in range(27)])  # 3 de 30 = 10%
    p = deck.partes_podio(analizar(filas))
    assert p, "no salió el podio"
    primero = p["filas"][0][0]
    assert "Muchas" in primero, (
        "ordenó por conversión: primero quedó %r" % primero)
    return "primero el de 3 ventas, no el de 50% sobre 2 casos"


check("el podio ordena por ventas, no por conversión",
      caso_el_podio_ordena_por_ventas)


def caso_el_podio_muestra_la_conversion_al_lado():
    filas = ([fila("ANA", "HUDSON", venta=True)] + [fila("ANA", "HUDSON")] * 3)
    p = deck.partes_podio(analizar(filas))
    # «25,0%»: el deck escribe las conversiones con un decimal en todas las
    # láminas, y acá no hay razón para escribirlas distinto
    assert "25,0%" in p["filas"][0][2], "no muestra la conversión: %r" % (p["filas"][0],)
    notas = " ".join(x for _, x in p["lineas"])
    assert "no para decir quién vende mejor" in notas, (
        "el podio no avisa cómo se lee: %s" % notas[:120])
    return "1 de 4 = 25% al lado, y la advertencia de cómo leerlo"


check("el podio muestra la conversión y avisa cómo leerlo",
      caso_el_podio_muestra_la_conversion_al_lado)


def caso_sin_ventas_no_hay_podio():
    """Un podio de cuatro ceros no felicita a nadie: no se dibuja."""
    assert deck.partes_podio(analizar([fila("ANA", "HUDSON")] * 5)) is None
    return "sin ventas, la lámina no aparece"


check("sin ventas no se dibuja el podio", caso_sin_ventas_no_hay_podio)


def caso_el_podio_se_puede_elegir():
    ids = [k for k, _, _ in deck.SECCIONES]
    assert "podio" in ids, "no se puede elegir al crear un reporte"
    assert "podio" in deck.CON_LISTA, "no ofrece barras/columnas/tabla"
    return "está en el asistente y se puede ver de las tres formas"


check("el podio se elige como cualquier otra lámina",
      caso_el_podio_se_puede_elegir)


print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
