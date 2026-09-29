# -*- coding: utf-8 -*-
"""Que esta mal cargado en la planilla.

Un dashboard sobre datos mal cargados no es inutil: es peor que inutil, porque
se ve bien. Este modulo mira la planilla ANTES de contar nada y devuelve lo
que no cierra, con ejemplos concretos para poder ir a arreglarlo.

No inventa reglas de negocio: solo mira lo que la planilla dice de si misma.
Cada aviso trae en que fila esta, asi se puede ir a corregirlo.

GRAVEDAD
  grave  — el numero del dashboard va a estar mal si no se arregla
  aviso  — probablemente sea un error, conviene mirarlo
  dato   — no esta mal, pero conviene saberlo
"""
import datetime
import re
from collections import Counter, defaultdict

try:
    from .analizador import _norm, _es_fecha, _claves_de, _txt        # como paquete del panel
except ImportError:                   # o suelto, al probar el archivo
    from analizador import _norm, _es_fecha, _claves_de, _txt


def _fecha(v):
    v = _txt(v).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", v)
    if m:
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a < 100:
            a += 2000
        try:
            return datetime.date(a, mes, d)
        except ValueError:
            return None
    return None


def revisar(filas, an, hoy=None):
    """filas[0] son encabezados; `an` es lo que devolvio analizar()."""
    hoy = hoy or datetime.date.today()
    avisos = []

    # `clase` es una llave estable para que otro modulo pueda reconocer un
    # aviso sin leerle el titulo. Nace porque derivaciones.acomodar_avisos
    # buscaba el texto "misma cosa" adentro del titulo, y al reescribir ese
    # titulo dejo de encontrarlo en silencio: el aviso seguia saliendo, pero
    # sin el recuento de filas que lo hacia util.
    def avisar(gravedad, titulo, detalle, filas_afectadas=None, ejemplos=None,
               clase=""):
        avisos.append({
            "gravedad": gravedad, "titulo": titulo, "detalle": detalle,
            "filas": filas_afectadas or [], "ejemplos": ejemplos or [],
            "clase": clase,
        })

    cab = [str(c).strip() for c in filas[0]]
    cuerpo = filas[1:]
    cols = {c["nombre"]: c for c in an["columnas"]}

    # ── 1. filas rotas ───────────────────────────────────────────────────
    vacias, cortas = [], []
    for n, f in enumerate(cuerpo, start=2):          # 2 = primera fila de datos en la planilla
        if not any(str(v).strip() for v in f):
            vacias.append(n)
        elif len(f) < len(cab):
            cortas.append(n)
    if vacias:
        avisar("aviso", "Hay %d filas completamente vacias" % len(vacias),
               "No aportan nada y desordenan la cuenta de filas.",
               vacias[:20])
    if cortas:
        avisar("grave", "Hay %d filas con menos columnas de las que corresponde" % len(cortas),
               "Le faltan celdas al final. Puede ser que se hayan corrido los datos.",
               cortas[:20])

    # ── 2. columnas que deberian estar llenas y no lo estan ──────────────
    for c in an["columnas"]:
        if c["tipo"] in ("fecha", "contacto") or c["nombre"] in ("Sucursal", "Vendedor"):
            total = c["llenos"] + c["vacios"]
            if total and c["vacios"] > total * 0.05:
                pct = 100.0 * c["vacios"] / total
                avisar("grave" if pct > 20 else "aviso",
                       "%s esta vacia en %d filas (%.0f%%)" % (c["nombre"], c["vacios"], pct),
                       "Esas filas no van a poder contarse en los cortes que usen esta columna.")

    # ── 3. fechas imposibles ─────────────────────────────────────────────
    for c in an["columnas"]:
        if c["tipo"] != "fecha":
            continue
        i = c["i"]
        futuras, viejas, ilegibles = [], [], []
        for n, f in enumerate(cuerpo, start=2):
            v = f[i] if i < len(f) else ""
            if not str(v).strip():
                continue
            d = _fecha(v)
            if d is None:
                ilegibles.append((n, v))
            elif d > hoy:
                futuras.append((n, v))
            elif d < hoy - datetime.timedelta(days=365 * 3):
                viejas.append((n, v))
        if futuras:
            avisar("grave", "%d fechas estan en el futuro" % len(futuras),
                   "Casi siempre es un error de tipeo en el año o el mes.",
                   [n for n, _ in futuras[:20]],
                   ["fila %d: %s" % (n, v) for n, v in futuras[:5]])
        if viejas:
            avisar("aviso", "%d fechas son de hace mas de 3 años" % len(viejas),
                   "Puede ser historico de verdad, o un año mal tipeado.",
                   [n for n, _ in viejas[:20]],
                   ["fila %d: %s" % (n, v) for n, v in viejas[:5]])
        if ilegibles:
            avisar("grave", "%d fechas no se entienden" % len(ilegibles),
                   "No tienen formato de fecha, asi que esas filas quedan afuera del tiempo.",
                   [n for n, _ in ilegibles[:20]],
                   ["fila %d: %r" % (n, v) for n, v in ilegibles[:5]])

    # ── 4. valores sueltos en una lista ──────────────────────────────────
    #     Si una columna es un desplegable, todos los valores deberian repetirse.
    #     Uno que aparece una o dos veces suele ser tipeo a mano, o una opcion
    #     que se saco de la lista.
    for c in an["columnas"]:
        if c["tipo"] != "categoria" or not c.get("valores"):
            continue
        i = c["i"]
        cuenta = Counter(str(f[i]).strip() for f in cuerpo
                         if i < len(f) and str(f[i]).strip())
        if len(cuenta) < 3:
            continue
        habitual = sorted(cuenta.values(), reverse=True)[len(cuenta) // 2]
        raros = [(v, n) for v, n in cuenta.items() if n <= 2 and habitual >= 10]
        if raros:
            avisar("aviso", "%s tiene %d valores que aparecen una o dos veces"
                   % (c["nombre"], len(raros)),
                   "Si esta columna es un desplegable, esto suele ser algo escrito a mano "
                   "o una opcion que se cambio.",
                   [], ["%s (%d %s)" % (v, n, "vez" if n == 1 else "veces")
                        for v, n in sorted(raros, key=lambda x: x[1])[:8]])

    # ── 5. la misma opcion cargada de dos formas ─────────────────────────
    #     Dos niveles, y se dicen distinto a proposito: el primero es una
    #     certeza (mismo texto salvo tildes, espacios o el orden de las
    #     palabras) y el segundo una duda. Mezclarlos hacia que la certeza se
    #     leyera como "otra queja mas".
    for c in an["columnas"]:
        pf = c.get("parecidos_filas") or []
        for i, par in enumerate(c.get("parecidos") or []):
            # ⚠️ Grave SOLO si mueve la aguja. Uno puede estar partiendo 2.983
            # filas y otro dos casos sueltos: con los nueve en grave, el Word
            # abria diciendo "hay 13 problemas graves" y cuando todo es grave
            # se dejan de leer todos. El corte es el mismo que usa
            # derivaciones.acomodar_avisos, para que las dos pantallas no
            # cuenten distinto.
            peso = pf[i] if i < len(pf) else 0
            a = {"gravedad": "grave" if peso >= 100 else "aviso",
                 "titulo": "%s: «%s» esta cargada de dos formas" % (c["nombre"], par[0]),
                 "detalle": "Es el mismo valor escrito distinto, asi que el numero "
                            "de ese valor esta partido en dos. Unificarlas lo arregla.",
                 "filas": [], "ejemplos": par[:4], "clase": "valor_duplicado"}
            # cuantas filas junta, contado sobre TODOS los valores y no sobre
            # los 25 mas frecuentes: es lo que dice cual arreglar primero
            if i < len(pf) and pf[i]:
                a["filas_afectadas"] = pf[i]
            avisos.append(a)
        for par in (c.get("sospechosos") or []):
            avisar("aviso", "%s: dos opciones se parecen mucho" % c["nombre"],
                   "Puede ser un tipeo, o pueden ser dos cosas distintas. Esto no "
                   "traba ningun numero: mirarlas y decidir es tuyo.",
                   [], par[:4], clase="valor_sospechoso")

    # ── 6. filas repetidas ───────────────────────────────────────────────
    firmas = defaultdict(list)
    for n, f in enumerate(cuerpo, start=2):
        firma = "|".join(_norm(v) for v in f)
        if firma.strip("|"):
            firmas[firma].append(n)
    repes = {k: v for k, v in firmas.items() if len(v) > 1}
    if repes:
        total = sum(len(v) - 1 for v in repes.values())
        avisar("aviso", "Hay %d filas repetidas exactas" % total,
               "La misma fila cargada mas de una vez infla todos los numeros.",
               sorted(n for v in repes.values() for n in v[1:])[:20])

    # ── 7. quien dejo de cargar ──────────────────────────────────────────
    #     Una sucursal o un vendedor que venia cargando y se corto es el error
    #     mas caro de todos, porque no se ve: el numero simplemente baja.
    fcol = next((c for c in an["columnas"] if c["tipo"] == "fecha"), None)
    if fcol:
        for c in an["columnas"]:
            if c["tipo"] != "categoria" or c["distintos"] > 25:
                continue
            # Solo tiene sentido para columnas que nombran a QUIEN carga.
            # "De redes" son cantidades: preguntarse si el numero 14 dejo de
            # cargar no significa nada.
            if not re.search(r"(sucursal|local|vendedor|operador|usuario|equipo|"
                             r"responsable|asesor|punto)", c["nombre"], re.I):
                continue
            ultima = {}
            for f in cuerpo:
                if fcol["i"] >= len(f) or c["i"] >= len(f):
                    continue
                d = _fecha(f[fcol["i"]])
                v = str(f[c["i"]]).strip()
                if d and v and (v not in ultima or d > ultima[v]):
                    ultima[v] = d
            if len(ultima) < 2:
                continue
            # ⚠️ La referencia IGNORA el futuro. Con un año tipeado mal, esa
            # fecha imposible pasaba a ser "lo mas reciente" y dejaba a todas
            # las sucursales como atrasadas 380 dias: el aviso mas util del
            # modulo se convertia en ruido por un solo error de tipeo.
            reales = [d for d in ultima.values() if d <= hoy]
            if not reales:
                continue
            masReciente = max(reales)
            callados = [(v, d) for v, d in ultima.items()
                        if d <= hoy and (masReciente - d).days >= 14]
            if callados:
                avisar("grave" if len(callados) < len(ultima) else "aviso",
                       "%s: %d no cargan hace mas de 2 semanas" % (c["nombre"], len(callados)),
                       "El resto sigue cargando, asi que el numero de estos esta bajando "
                       "por falta de carga, no porque haya menos.",
                       [], ["%s: ultima carga %s" % (v, d.isoformat())
                            for v, d in sorted(callados, key=lambda x: x[1])[:8]])

    # ── 8. numeros fuera de escala ───────────────────────────────────────
    for c in an["columnas"]:
        if c["tipo"] != "numero":
            continue
        i = c["i"]
        vals = []
        for n, f in enumerate(cuerpo, start=2):
            if i >= len(f) or not str(f[i]).strip():
                continue
            try:
                vals.append((n, float(str(f[i]).replace(".", "").replace(",", "."))))
            except ValueError:
                pass
        if len(vals) < 10:
            continue
        negativos = [(n, v) for n, v in vals if v < 0]
        if negativos:
            avisar("grave", "%s tiene %d valores negativos" % (c["nombre"], len(negativos)),
                   "Si esta columna cuenta cosas, un negativo no puede ser.",
                   [n for n, _ in negativos[:20]],
                   ["fila %d: %g" % (n, v) for n, v in negativos[:5]])
        ordenados = sorted(v for _, v in vals)
        mediana = ordenados[len(ordenados) // 2]
        if mediana > 0:
            locos = [(n, v) for n, v in vals if v > mediana * 50]
            if locos:
                avisar("aviso", "%s tiene %d valores muchisimo mas altos que el resto"
                       % (c["nombre"], len(locos)),
                       "La mediana es %g. Suele ser un cero de mas al tipear." % mediana,
                       [n for n, _ in locos[:20]],
                       ["fila %d: %g" % (n, v) for n, v in locos[:5]])

    orden = {"grave": 0, "aviso": 1, "dato": 2}
    avisos.sort(key=lambda a: orden.get(a["gravedad"], 9))
    return avisos
