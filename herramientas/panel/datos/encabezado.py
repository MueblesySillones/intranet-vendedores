# -*- coding: utf-8 -*-
"""Encontrar en qué fila empieza la tabla de verdad.

DONDE SE USA (y donde NO)
  Solo para las filas que llegan por la API de Google, o sea cuando el panel
  entra con la cuenta de servicio. Esas filas vienen crudas: Google las
  devuelve tal cual y no pasan por ningun lector.

  Todo lo demas —los archivos de la PC y las planillas bajadas por link— pasa
  por fuentes.py, que YA hace este mismo trabajo (ver alli
  _saltar_hasta_encabezado). Correr los dos seria recortar dos veces la
  misma tabla. Si algun dia se unifican, el que sobra es este.

EL PROBLEMA
  El analizador da por hecho que la fila 1 son los encabezados. En un CSV
  exportado eso es casi siempre cierto. En una planilla de trabajo, casi nunca:

      (fila vacía)
      DESEMPEÑO VENDEDORES — MARZO 2026
      (fila vacía)
      Vendedor | Consultas | Ventas | %
      AGUSTINA | 448       | 61     | 13,6%

  Leyendo la fila 1 se encuentra una fila vacía, y el resultado es un reporte de
  cero columnas. Le pasa a cuatro de las nueve hojas de la planilla real de
  derivaciones, y es la forma más común que tiene una planilla hecha por una
  persona: título arriba, tabla abajo.

CÓMO SE DECIDE
  Se miran las primeras filas y se busca la primera que parezca una FILA DE
  ENCABEZADOS. Tres condiciones, y las tres tienen que darse:

    1. Está bastante llena. Un título ocupa una celda sola; una fila de
       encabezados ocupa casi todo el ancho de la tabla.
    2. Sus celdas son palabras, no números ni fechas. «Vendedor», «Consultas».
       Si la fila son números, es la primera fila de datos de una tabla sin
       encabezados, y ahí no hay nada que recortar.
    3. Abajo hay al menos dos filas con la misma pinta. Sin esto, un subtítulo
       largo o una fila de notas al pie se haría pasar por encabezado.

  Si ninguna fila cumple las tres, se devuelve 0 y todo queda como antes. Esa
  es la regla que importa: esto puede mejorar el resultado, nunca empeorarlo.
"""
import re

# Cuántas filas se miran antes de rendirse. Un título más un par de líneas de
# aire entran de sobra en 25; más abajo, lo que hay ya es contenido.
MIRAR = 25

# Qué tan llena tiene que estar una fila para ser candidata a encabezado,
# comparada con la fila más llena que se vio.
LLENA = 0.6

# Cuántas filas parecidas tiene que haber abajo para creerle.
CONFIRMAN = 2

_NUMERO = re.compile(r"^-?[\d.,]+\s*%?$")
_FECHA = re.compile(r"^\d{1,4}[/\-.]\d{1,2}([/\-.]\d{1,4})?$")


def _lleno(fila):
    return sum(1 for c in fila if str(c or "").strip())


def _es_palabra(v):
    """True si la celda parece un nombre de columna y no un dato.

    Un encabezado es texto corto. Un número, una fecha o un párrafo no lo son.
    El tope de largo está para que una frase suelta —«Los datos de marzo se
    cargaron tarde»— no cuente como encabezado."""
    t = str(v or "").strip()
    if not t or len(t) > 60:
        return False
    return not (_NUMERO.match(t) or _FECHA.match(t))


def _parece_encabezado(fila, ancho):
    """¿Esta fila tiene forma de fila de encabezados?"""
    lleno = _lleno(fila)
    if lleno < 2 or lleno < ancho * LLENA:
        return False
    llenas = [c for c in fila if str(c or "").strip()]
    # La mayoría tienen que ser palabras. «La mayoría» y no «todas» porque es
    # común que una columna se llame "2026" o que quede una celda sin nombre.
    palabras = sum(1 for c in llenas if _es_palabra(c))
    return palabras >= len(llenas) * 0.7


def encontrar(filas, mirar=MIRAR):
    """(indice_de_la_fila_de_encabezados, motivo).

    `motivo` es para poder contarlo en pantalla: si el panel recortó ocho filas
    de adorno, conviene decirlo, no hacerlo callado."""
    if not filas:
        return 0, ""

    tope = min(len(filas), mirar)
    # El ancho de referencia sale de toda la tabla y no solo de las primeras
    # filas: si arriba hay puro título, el ancho de arriba es 1 y cualquier
    # cosa pasaría el filtro de "está bastante llena".
    ancho = max((_lleno(f) for f in filas[:200]), default=0)
    if ancho < 2:
        return 0, ""

    for i in range(tope):
        if not _parece_encabezado(filas[i], ancho):
            continue
        # Que abajo siga una tabla, no otro título.
        abajo = 0
        for f in filas[i + 1:i + 1 + CONFIRMAN + 3]:
            if _lleno(f) >= ancho * LLENA:
                abajo += 1
        if abajo < CONFIRMAN:
            continue
        if i == 0:
            return 0, ""
        return i, ("Arriba de la tabla había %d fila%s de título o de espacio. "
                   "Empecé a leer desde la fila %d, donde están los nombres de "
                   "las columnas." % (i, "" if i == 1 else "s", i + 1))

    return 0, ""


def recortar(filas):
    """(filas_desde_el_encabezado, motivo). Si no hay nada que sacar, devuelve
    las mismas filas."""
    i, motivo = encontrar(filas)
    return (filas[i:] if i else filas), motivo
