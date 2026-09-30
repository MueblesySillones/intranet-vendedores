# -*- coding: utf-8 -*-
"""Lo que se edita en el reporte tiene que salir IGUAL en el Word.

El Word se arma con código propio (deck_word.py), y el 30-sep-2026 37 de 113
textos editados en pantalla no llegaban al Word: los recuadros del embudo, las
notas, las bajadas, los títulos de columna. Esta prueba edita TODOS los textos
que la pantalla deja editar y saca todas las notas y bajadas, y mira el Word.

    python test_word_ediciones.py
"""
import datetime
import os
import random
import re
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos import deck, deck_word  # noqa: E402
from datos import derivaciones as D  # noqa: E402

CAB = ["Fecha", "Vendedor", "Sucursal", "Respuesta Final", "Producto",
       "Origen", "Localidad"]
RES = []


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(True)
        print("PASS | %s | %s" % (nombre, nota))
    except AssertionError as e:
        RES.append(False)
        print("FAIL | %s | %s" % (nombre, e))


def filas():
    random.seed(7)
    out = [CAB]
    d0 = datetime.date(2026, 7, 1)
    for _ in range(700):
        f = d0 + datetime.timedelta(days=random.randint(0, 61))
        out.append([f.strftime("%d/%m/%Y"),
                    random.choice(["AGUSTINA", "MARTIN", "LUCIA", "DIEGO"]),
                    random.choice(["HUDSON", "CABA", "CANNING"]),
                    random.choice(["Realizó la compra", "NO RESPONDE", "CARO", ""]),
                    random.choice(["SILLON", "ESQUINERO", "MESA", "COLCHON"]),
                    random.choice(["INSTAGRAM", "WEB", "WHATSAPP", "SUCURSAL"]),
                    random.choice(["QUILMES", "CABA", "BERAZATEGUI"])])
    return out


def caso(sucursal=""):
    d = D.analizar(filas(), tempfile.mkdtemp(prefix="wed_"),
                   hoy=datetime.date(2026, 9, 5), sucursal_f=sucursal or None)
    op = {"detalle": "10", "sucursal": sucursal}
    html = deck.armar(d, "Prueba", None, op)
    claves = sorted(set(re.findall(r'data-txt="([a-z_0-9.]+)"', html)))
    op["textos"] = {k: "ED%03dX" % i for i, k in enumerate(claves)}
    html = deck.armar(d, "Prueba", None, op)
    en_pantalla = [k for k, v in op["textos"].items() if v in html]
    word = deck_word.armar(d, "Prueba", None, op)
    faltan = [k for k in en_pantalla if op["textos"][k] not in word]
    assert not faltan, "editados en pantalla que no salen en el Word: %s" % faltan
    op["ocultos"] = [k for k in en_pantalla
                     if ".nota" in k or k.endswith("bajada") or k == "portada.kicker"]
    word = deck_word.armar(d, "Prueba", None, op)
    siguen = [k for k in op["ocultos"] if op["textos"][k] in word]
    assert not siguen, "sacados en pantalla que siguen en el Word: %s" % siguen
    return "%d textos editados y %d sacados" % (len(en_pantalla), len(op["ocultos"]))


check("toda la empresa: lo editado y lo sacado llegan al Word", caso)
check("una sucursal: lo editado y lo sacado llegan al Word", lambda: caso("HUDSON"))

print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
