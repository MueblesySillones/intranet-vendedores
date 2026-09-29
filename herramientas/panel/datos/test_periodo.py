# -*- coding: utf-8 -*-
"""Un reporte de UN PERÍODO: agosto, la semana pasada, lo que se pida.

Sin esto, la planilla conectada solo puede dar UN reporte, el de todo el
rango, y siempre dice lo mismo. Es lo que hace falta para que de una misma
planilla salgan varios reportes —uno por mes, uno por semana— en vez de uno.

La regla que más importa acá: las filas SIN FECHA quedan afuera de un reporte
con período, porque no se puede afirmar que una consulta sin fecha haya pasado
en agosto. Son 1.744 de 9.170 en la planilla real, así que el reporte tiene que
poder DECIRLO en vez de dejar un total que no cierra.

    python test_periodo.py
"""
import datetime
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos import derivaciones as D  # noqa: E402

RES = []
CAB = ["Fecha", "Vendedor", "Sucursal", "Respuesta Final"]
HOY = datetime.date(2026, 9, 5)


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(True)
        print("PASS | %s | %s" % (nombre, nota))
    except AssertionError as e:
        RES.append(False)
        print("FAIL | %s | %s" % (nombre, e))


def analizar(filas, desde=None, hasta=None):
    tmp = tempfile.mkdtemp(prefix="per_")
    return D.analizar([CAB] + filas, tmp, hoy=HOY, desde_f=desde, hasta_f=hasta)


JULIO = [["%d/7/2026" % d, "AGUSTINA", "HUDSON", ""] for d in (3, 10, 20)]
AGOSTO = [["%d/8/2026" % d, "AGUSTINA", "HUDSON", ""] for d in (1, 5, 9, 28)]
SIN_FECHA = [["", "AGUSTINA", "HUDSON", ""]] * 2


def caso_sin_periodo():
    d = analizar(JULIO + AGOSTO)
    assert d["total"]["consultas"] == 7, "conto %s" % d["total"]["consultas"]
    assert d["periodo_pedido"] is None, "dice que recorto sin que se lo pidieran"
    return "sin período mira toda la planilla: 7"


check("sin período, todo como siempre", caso_sin_periodo)


def caso_un_mes():
    d = analizar(JULIO + AGOSTO,
                 datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert d["total"]["consultas"] == 4, "conto %s en vez de 4" % d["total"]["consultas"]
    assert d["fuera_del_periodo"] == 3, "dejo afuera %s" % d["fuera_del_periodo"]
    assert d["sucursales"]["Hudson"]["derivaciones"] == 4, "sucursales: %s" % d["sucursales"]
    return "agosto = 4 consultas; las 3 de julio quedan afuera"


check("un mes en particular", caso_un_mes)


def caso_una_semana():
    d = analizar(AGOSTO, datetime.date(2026, 8, 3), datetime.date(2026, 8, 9))
    assert d["total"]["consultas"] == 2, "conto %s en vez de 2" % d["total"]["consultas"]
    return "del 3 al 9 de agosto = 2"


check("una semana suelta", caso_una_semana)


def caso_un_dia():
    d = analizar(AGOSTO, datetime.date(2026, 8, 5), datetime.date(2026, 8, 5))
    assert d["total"]["consultas"] == 1, "conto %s en vez de 1" % d["total"]["consultas"]
    return "un solo día = 1"


check("un día solo", caso_un_dia)


def caso_bordes():
    """El primero y el último día ENTRAN: un mes es del 1 al 31, no del 2 al 30."""
    d = analizar(AGOSTO, datetime.date(2026, 8, 1), datetime.date(2026, 8, 28))
    assert d["total"]["consultas"] == 4, "se comio un borde: %s" % d["total"]["consultas"]
    return "el 1 y el 28 entran"


check("los dos bordes entran", caso_bordes)


def caso_sin_fecha_afuera_y_dicho():
    d = analizar(AGOSTO + SIN_FECHA,
                 datetime.date(2026, 8, 1), datetime.date(2026, 8, 31))
    assert d["total"]["consultas"] == 4, "metio las que no tienen fecha"
    assert d["sin_fecha_fuera"] == 2, "no las conto aparte: %s" % d["sin_fecha_fuera"]
    return "2 sin fecha quedan afuera, y se pueden nombrar"


check("las filas sin fecha quedan afuera Y se cuentan", caso_sin_fecha_afuera_y_dicho)


def caso_sin_fecha_entran_sin_periodo():
    """Sin período no se descarta nada: es el comportamiento de siempre."""
    d = analizar(AGOSTO + SIN_FECHA)
    assert d["total"]["consultas"] == 6, "conto %s en vez de 6" % d["total"]["consultas"]
    assert d["total"]["sin_fecha"] == 2, "no las marco: %s" % d["total"]["sin_fecha"]
    return "6 consultas, 2 de ellas sin fecha"


check("sin período, las sin fecha siguen contando", caso_sin_fecha_entran_sin_periodo)


def caso_vacio():
    """Un período sin ninguna fila no explota: da cero y lo dice."""
    d = analizar(JULIO, datetime.date(2026, 12, 1), datetime.date(2026, 12, 31))
    assert d["total"]["consultas"] == 0, "conto %s" % d["total"]["consultas"]
    assert d["fuera_del_periodo"] == 3, "no dice cuantas quedaron afuera"
    return "diciembre = 0, y avisa que hay 3 fuera"


check("un período sin datos no rompe", caso_vacio)


def caso_solo_desde():
    d = analizar(JULIO + AGOSTO, datetime.date(2026, 8, 1), None)
    assert d["total"]["consultas"] == 4, "conto %s" % d["total"]["consultas"]
    return "de agosto en adelante = 4"


check("solo desde, sin tope", caso_solo_desde)

print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
