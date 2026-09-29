# -*- coding: utf-8 -*-
"""Proponer qué se puede medir en una planilla, en castellano.

DE DÓNDE SALEN LAS PROPUESTAS
  No de una lista fija: de las columnas que el analizador encontró. Una columna
  que es una lista de valores («Vendedor», «Sucursal») se puede contar; una de
  fechas se puede seguir en el tiempo; una de números se puede sumar. Eso es
  todo lo que una tabla puede contestar sin inventar nada.

POR QUÉ SE PREGUNTA EN VEZ DE MOSTRAR TODO
  Una planilla de derivaciones tiene 18 columnas y el tablero sale con 85
  tarjetas. Ahí adentro está lo que uno buscaba, pero también todo lo demás, y
  un reporte que dice todo no dice nada. Preguntar «¿qué querés medir?» convierte
  un volcado en un reporte sobre algo.

  Lo que NO se elige sigue estando: no se borra ni se esconde, queda más abajo.
  La elección ordena, no recorta.

QUÉ NO SE PROPONE NUNCA
  · Las columnas con datos de clientes (`sensible`). Contar «cuántas por
    Teléfono» no significa nada, y una columna que no se puede publicar no tiene
    por qué aparecer en la lista de lo que el reporte va a mostrar.
  · Las columnas de texto libre. «Descripción» tiene 790 valores distintos en
    1052 filas: agrupar eso da 790 grupos de uno, que es una lista, no una medida.
  · Las que tienen un solo valor: contar algo que siempre es lo mismo da una
    barra sola.

⚠️ SOBRE LOS CRUCES
  Se ofrece «{número} por {categoría}» —el monto por sucursal— pero como algo que
  ALGUIEN PIDE, nunca como un hallazgo automático. La diferencia importa: buscar
  cruces solo, entre 18 columnas, encuentra "diferencias significativas" hasta en
  datos puestos al azar. Un cruce que el usuario eligió es una descripción de lo
  que hay; uno que el programa encontró solo es, casi siempre, ruido con cara de
  conclusión.
"""

# Cuántos valores distintos hacen que una columna sirva para agrupar. Con menos
# de 2 hay una sola barra; con más de 60 la lista es más larga que la pantalla y
# lo que se ve es una cola de valores de una fila cada uno.
MIN_DISTINTOS = 2
MAX_DISTINTOS = 60

# Cuántas se marcan solas. Si vinieran todas marcadas, la pregunta sería
# decorativa: el reporte saldría igual de largo que sin preguntar.
CUANTAS_SUGERIDAS = 4

# Debajo de esto, la columna está casi vacía y medirla dice más de lo que falta
# que de lo que hay. Igual se propone (a veces es justo lo que se quiere mirar),
# pero no se sugiere sola y se avisa.
LLENADO_FLOJO = 0.35


def _fecha_corta(iso):
    """'2025-01-24' -> '24/01/2025'. El analizador guarda las fechas en ISO
    para poder ordenarlas; acá se escriben como se leen."""
    try:
        a, m, d = (iso or "")[:10].split("-")
        return "%02d/%02d/%s" % (int(d), int(m), a)
    except (ValueError, AttributeError, TypeError):
        return iso or ""


def _cuantas_filas(an):
    return max(1, int(an.get("filas") or 0))


def _pinta(col, filas):
    """Qué proporción de la columna está cargada."""
    return (col.get("llenos") or 0) / float(filas)


def _mas_comun(col):
    """(valor, cuenta) del valor que más aparece, o None.

    Sirve para que la propuesta muestre algo concreto: «22 valores, la que más
    aparece es AGUSTINA con 448». Sin eso, «Cuántas por Vendedor» es una
    promesa; con eso, ya se ve de qué se está hablando."""
    vs = col.get("valores") or []
    if vs:
        v = vs[0]
        return v.get("valor"), v.get("cuenta")
    gs = col.get("grupos") or []
    if gs:
        g = gs[0]
        return g.get("etiqueta"), g.get("cuenta")
    return None


def _cuantos_grupos(col):
    """Cuántos grupos DE VERDAD tiene la columna.

    ⚠️ En una columna de tipo `motivo` no sirve mirar `distintos`. «Producto»
    tiene 145 valores escritos a mano —«Sillón 3 cuerpos», «sillon 3c», «SILLON
    3 CUERPOS»— que el analizador ya juntó en un puñado de grupos. Mirando los
    145 crudos, la columna quedaba afuera por «demasiados valores», y «cuántas
    por Producto» es justo de lo más útil que tiene esta planilla."""
    gs = col.get("grupos")
    if gs:
        return len(gs)
    return col.get("distintos") or 0


def _agrupable(col, filas):
    """¿Esta columna sirve para agrupar?"""
    if col.get("sensible"):
        return False
    if col.get("tipo") not in ("categoria", "motivo"):
        return False
    d = _cuantos_grupos(col)
    if d < MIN_DISTINTOS:
        return False
    # El tope se mide contra los grupos, no contra las filas: 50 vendedores en
    # 3000 filas agrupa bien; 50 valores en 60 filas es una lista de casi-únicos
    # disfrazada de categoría. Las de tipo `motivo` tienen mas manga: agrupar es
    # su razon de ser, y de todos modos se muestran los primeros.
    tope = MAX_DISTINTOS * 3 if col.get("tipo") == "motivo" else MAX_DISTINTOS
    if d > tope:
        return False
    llenos = col.get("llenos") or 0
    return llenos >= d * 2


def proponer(an):
    """[{id, titulo, detalle, tipo, columna, sugerida, aviso}, ...]

    `an` es lo que devuelve analizador.analizar(). Cada propuesta se puede leer
    sola, sin saber nada de la planilla."""
    cols = (an or {}).get("columnas") or []
    filas = _cuantas_filas(an)
    fuera = []

    # ── contar por cada columna que agrupe ──
    for c in cols:
        if not _agrupable(c, filas):
            continue
        d = _cuantos_grupos(c)
        pinta = _pinta(c, filas)
        top = _mas_comun(c)
        detalle = ("%d formas de escribirlo, juntadas en %d grupos"
                   % (c.get("distintos") or 0, d)
                   if c.get("tipo") == "motivo" else
                   "%d valores distintos" % d)
        if top and top[0]:
            detalle += " · el más frecuente es «%s» (%s)" % (
                str(top[0])[:38], _miles(top[1]))
        fuera.append({
            "id": "conteo:%d" % c["i"],
            "tipo": "conteo",
            "columna": c["nombre"],
            "titulo": "Cuántas por %s" % c["nombre"],
            "detalle": detalle,
            "pinta": pinta,
            "aviso": ("Esta columna está cargada en %d de cada 100 filas."
                      % round(pinta * 100)) if pinta < LLENADO_FLOJO else "",
        })

    # ── el tiempo ──
    for c in cols:
        if c.get("tipo") != "fecha" or c.get("sensible"):
            continue
        # vienen en ISO del analizador; acá se escriben como se leen
        desde, hasta = _fecha_corta(c.get("desde")), _fecha_corta(c.get("hasta"))
        fuera.append({
            "id": "tiempo:%d" % c["i"],
            "tipo": "tiempo",
            "columna": c["nombre"],
            "titulo": "Cómo evoluciona en el tiempo",
            "detalle": ("por %s, del %s al %s" % (c["nombre"], desde, hasta)
                        if desde and hasta else "por %s" % c["nombre"]),
            "pinta": _pinta(c, filas),
            "aviso": "",
        })

    # ── los números ──
    numeros = [c for c in cols if c.get("tipo") == "numero" and not c.get("sensible")]
    for c in numeros:
        fuera.append({
            "id": "numero:%d" % c["i"],
            "tipo": "numero",
            "columna": c["nombre"],
            "titulo": "Total y promedio de %s" % c["nombre"],
            "detalle": "%s filas con un número cargado" % _miles(c.get("llenos")),
            "pinta": _pinta(c, filas),
            "aviso": "",
        })

    # ── los cruces: un número, abierto por una categoría ──
    # Solo con las categorías más limpias, y pocos: la idea es ofrecer «el monto
    # por sucursal», no las 18x3 combinaciones posibles.
    if numeros:
        buenas = sorted(
            [c for c in cols if _agrupable(c, filas) and _cuantos_grupos(c) <= 25],
            key=lambda c: -(c.get("llenos") or 0))[:3]
        for n in numeros[:2]:
            for c in buenas:
                fuera.append({
                    "id": "cruce:%d:%d" % (n["i"], c["i"]),
                    "tipo": "cruce",
                    "columna": "%s / %s" % (n["nombre"], c["nombre"]),
                    "titulo": "%s por %s" % (n["nombre"], c["nombre"]),
                    "detalle": "suma y promedio de %s, abierto por %s"
                               % (n["nombre"], c["nombre"]),
                    "pinta": min(_pinta(n, filas), _pinta(c, filas)),
                    "aviso": "",
                })

    # ── cuáles vienen marcadas ──
    # Se ordena por lo que probablemente le importe a alguien: primero lo que
    # está bien cargado, y entre lo demás, las categorías con pocos valores
    # («Estado» con 4 dice algo de un vistazo; «Localidad» con 55 es un listado).
    distintos_de = {c["nombre"]: _cuantos_grupos(c) for c in cols}

    def utilidad(p):
        # Primero lo que esta bien cargado. Entre lo demas, las categorias con
        # pocos valores: «Estado» con 4 se entiende de un vistazo, «Localidad»
        # con 55 es un listado.
        pocos = distintos_de.get(p["columna"], 0) if p["tipo"] == "conteo" else 0
        return (-round(p["pinta"], 2), pocos)

    orden = sorted(fuera, key=utilidad)
    marcadas = set()
    for p in orden:
        if len(marcadas) >= CUANTAS_SUGERIDAS:
            break
        # No sugerir dos cosas de la misma columna, ni cruces sin que se pida.
        if p["tipo"] == "cruce" or p["pinta"] < LLENADO_FLOJO:
            continue
        marcadas.add(p["id"])

    for p in fuera:
        p["sugerida"] = p["id"] in marcadas
    return fuera


def _miles(n):
    """1234 -> «1.234». Los números de un reporte se leen, no se descifran."""
    try:
        return "{:,}".format(int(n)).replace(",", ".")
    except (TypeError, ValueError):
        return str(n or "")


def columnas_del_foco(foco, an):
    """Los nombres de columna que tocan las medidas elegidas, sin repetir.

    Sirve para ordenar el tablero y el reporte: lo elegido primero."""
    cols = (an or {}).get("columnas") or []
    porindice = {c["i"]: c["nombre"] for c in cols}
    nombres, vistos = [], set()
    for f in (foco or []):
        for parte in str(f).split(":")[1:]:
            try:
                nom = porindice.get(int(parte))
            except ValueError:
                continue
            if nom and nom not in vistos:
                vistos.add(nom)
                nombres.append(nom)
    return nombres
