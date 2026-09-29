# -*- coding: utf-8 -*-
"""De dónde sale la sucursal de una derivación.

La regla vieja era: del VENDEDOR, con un mapa escrito a mano. El problema
medido sobre la planilla real: 102 derivaciones quedaban sin ubicar, todas de
gente que el mapa no conocía (Lourdes, Carolina, Yesica, Pamela, Mauricio), y
sus filas SÍ decían la sucursal en la columna «Sucursal».

La regla nueva: primero lo que dice la fila —cuando dice un local y no una
provincia—, y el mapa como respaldo. Con eso quedan 5 sin ubicar.

    python test_sucursal_de_la_fila.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos import derivaciones as D  # noqa: E402

RES = []
CAB = ["Fecha", "Vendedor", "Sucursal", "Respuesta Final"]


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(True)
        print("PASS | %s | %s" % (nombre, nota))
    except AssertionError as e:
        RES.append(False)
        print("FAIL | %s | %s" % (nombre, e))


def analizar(filas_datos):
    """Corre el análisis con un estado vacío (mapa = el inicial, sin guardados)."""
    tmp = tempfile.mkdtemp(prefix="deriv_")
    return D.analizar([CAB] + filas_datos, tmp, hoy=None)


def suc(d):
    return {k: v["derivaciones"] for k, v in d["sucursales"].items()}


# --------------------------------------------------------- el caso que fallaba
def caso_ex_vendedora():
    """Lourdes no está en el mapa, pero sus filas dicen NORCENTER."""
    d = analizar([["1/8/2026", "LOURDES", "NORCENTER", ""]] * 4)
    assert suc(d) == {"Norcenter": 4}, "quedo en %s" % suc(d)
    assert not d["sin_ubicar"], "la dio por sin ubicar: %s" % d["sin_ubicar"]
    return "4 derivaciones de una ex vendedora, ubicadas"


check("una vendedora que el mapa no conoce", caso_ex_vendedora)


def caso_provincia_no_es_sucursal():
    """Si la fila dice una provincia, NO es una sucursal: manda el mapa."""
    d = analizar([["1/8/2026", "AGUSTINA", "SANTA FE", ""]] * 3)
    assert suc(d) == {"Hudson": 3}, "quedo en %s" % suc(d)
    return "Santa Fe no crea una sucursal; Agustina sigue en Hudson"


check("una provincia no cuenta como sucursal", caso_provincia_no_es_sucursal)


def caso_provincia_y_sin_mapa():
    """Provincia + vendedor desconocido = sin ubicar, y se avisa quién."""
    d = analizar([["1/8/2026", "LOURDES", "SALTA", ""]])
    assert not d["sucursales"], "invento una sucursal: %s" % suc(d)
    assert d["sin_ubicar"].get("LOURDES") == 1, "no aviso: %s" % d["sin_ubicar"]
    return "queda sin ubicar y se nombra a quién preguntarle"


check("provincia y vendedor desconocido: se avisa", caso_provincia_y_sin_mapa)


# ------------------------------------------------- la fila le gana al mapa
def caso_la_fila_manda():
    """Agustina está mapeada a Hudson, pero ese día atendió en Canning."""
    d = analizar([["1/8/2026", "AGUSTINA", "HUDSON", ""]] * 2 +
                 [["2/8/2026", "AGUSTINA", "CANNING", ""]])
    assert suc(d) == {"Hudson": 2, "Canning": 1}, "quedo en %s" % suc(d)
    return "2 en Hudson y 1 en Canning, como paso de verdad"


check("una vendedora que cambia de local", caso_la_fila_manda)


def caso_pilar():
    """Pilar es una sucursal nueva que el mapa inicial no tiene."""
    d = analizar([["1/8/2026", "YESICA", "PILAR", ""]] * 5)
    assert suc(d) == {"Pilar": 5}, "quedo en %s" % suc(d)
    return "Pilar cuenta como sucursal"


check("una sucursal que el mapa no tiene", caso_pilar)


def caso_escritura():
    """La columna viene con mayúsculas y espacios de todo tipo."""
    d = analizar([["1/8/2026", "LOURDES", " norcenter ", ""],
                  ["1/8/2026", "LOURDES", "NorCenter", ""]])
    assert suc(d) == {"Norcenter": 2}, "quedo en %s" % suc(d)
    return "se lee igual escrito de cualquier forma"


check("no importa como este escrita la sucursal", caso_escritura)


def caso_sin_vendedor_no_es_derivacion():
    """Una consulta sin vendedor no es derivación, aunque diga la sucursal."""
    d = analizar([["1/8/2026", "", "CABA", ""]] * 3)
    assert d["total"]["consultas"] == 3, "consultas: %s" % d["total"]["consultas"]
    assert d["total"]["derivaciones"] == 0, "conto derivaciones de mas"
    assert not d["sucursales"], "le puso sucursal a algo sin derivar: %s" % suc(d)
    return "3 consultas, 0 derivaciones"


check("sin vendedor no hay derivacion", caso_sin_vendedor_no_es_derivacion)

print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
