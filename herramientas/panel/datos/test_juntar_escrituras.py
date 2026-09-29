# -*- coding: utf-8 -*-
"""El mismo texto escrito de dos formas tiene que contar una sola vez.

De donde sale: en la planilla de derivaciones «No respondio, se insistio 3
veces» convive con «No respondió, se insistió 3 veces » (tildes y un espacio al
final). Contados aparte dan 2.106 y 984, cuando son 3.090. Un reporte que diga
«el X% dejo de responder» sobre el numero partido se equivoca por casi la mitad.

    python test_juntar_escrituras.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos import analizador  # noqa: E402

RES = []


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(True)
        print("PASS | %s | %s" % (nombre, nota))
    except AssertionError as e:
        RES.append(False)
        print("FAIL | %s | %s" % (nombre, e))


def columna(valores, nombre="Respuesta Final"):
    """Repite la muestra hasta que la columna se lea como LISTA.

    _clasificar pide que los valores se repitan (distintos/total < 0.35) para
    tratarla como categoria; con seis filas de prueba eso no se cumple y la
    columna caia en «texto libre», donde no hay conteo por valor. Repetir no
    cambia las proporciones, que es lo que se esta probando."""
    muestra = list(valores) * 20
    filas = [[nombre]] + [[v] for v in muestra]
    return analizar_col(filas, nombre)


def analizar_col(filas, nombre):
    d = analizador.analizar(filas)
    for c in d["columnas"]:
        if c["nombre"] == nombre:
            return c
    raise AssertionError("no aparecio la columna %r" % nombre)


# ------------------------------------------------------------------ el caso real
def caso_tildes():
    c = columna(["No respondio, se insistio 3 veces"] * 3 +
                ["No respondió, se insistió 3 veces "] * 2 +
                ["Compro en otro lugar"])
    v = {x["valor"]: x["cuenta"] for x in c["valores"]}
    assert len(v) == 2, "quedaron %d valores, esperaba 2: %s" % (len(v), list(v))
    top = max(v.items(), key=lambda x: x[1])
    assert top[1] == 100, "junto %d en vez de 100 (5 x 20)" % top[1]
    assert c.get("escrituras_juntadas") == 1, "no anoto que junto escrituras"
    return "60 + 40 = %d, con el nombre %r" % (top[1], top[0][:34])


check("tildes y espacio al final cuentan como uno", caso_tildes)


def caso_mayusculas():
    c = columna(["EN CONTACTO", "En Contacto", "en contacto"])
    assert len(c["valores"]) == 1, "no junto las mayusculas: %s" % c["valores"]
    return "las tres formas dan %d" % c["valores"][0]["cuenta"]


check("mayusculas y minusculas cuentan como uno", caso_mayusculas)


def caso_nombre_mas_usado():
    """El nombre que se muestra es la forma que mas se escribio, no la primera."""
    c = columna(["Tiene el precio"] + ["Tiene el Precio"] * 4)
    assert c["valores"][0]["valor"] == "Tiene el Precio", \
        "eligio %r" % c["valores"][0]["valor"]
    return "gana la forma mas usada"


check("el nombre que queda es el mas usado", caso_nombre_mas_usado)


# --------------------------------------------- lo que NO se puede juntar solo
def caso_no_junta_distintos():
    """Dos motivos parecidos pero DISTINTOS siguen separados: unir eso es una
    decision sobre el negocio, y la sigue tomando una persona."""
    c = columna(["Esta fuera de su presupuesto"] * 2 +
                ["Fuera de su presupuesto, se le ofrecio otra opcion"] * 3)
    assert len(c["valores"]) == 2, "junto dos motivos distintos: %s" % c["valores"]
    # el aviso de "se parecen" lo sigue dando _mismos_valores, que agrupa por
    # palabras clave; es otro mecanismo y no se toco
    return "quedan separados"


check("no une motivos distintos, solo avisa", caso_no_junta_distintos)


def caso_puntuacion_cuenta():
    """La puntuacion SI distingue: se juntan escrituras, no se reescribe el texto."""
    c = columna(["Compro en otro lugar", "Compro en otro lugar."])
    assert len(c["valores"]) == 2, "junto textos con puntuacion distinta"
    return "un punto final no se da por sentado"


check("la puntuacion sigue distinguiendo", caso_puntuacion_cuenta)


def caso_distintos_al_dia():
    c = columna(["A"] * 2 + ["a"] + ["B"])
    assert c["distintos"] == 2, "distintos quedo en %s" % c["distintos"]
    return "el contador de distintos cuenta lo juntado"


check("el numero de valores distintos se corrige", caso_distintos_al_dia)

print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
