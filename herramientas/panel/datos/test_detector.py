# -*- coding: utf-8 -*-
"""El detector de valores duplicados: los casos que motivaron el cambio.

Cada caso de FALSOS salio de la planilla de derivaciones real, donde el
detector viejo los daba por duplicados y trababa 18 de 23 numeros.
"""
import sys, csv, io, os, collections
sys.path.insert(0, r"C:\Users\Redes 1\Documents\web dinamica-mys\herramientas\panel")
from datos import analizador as A, lecturas as L, revisor, derivaciones

ok = 0; fail = []
def check(n, cond, extra=""):
    global ok
    if cond: ok += 1; print("  OK  " + n)
    else: fail.append(n); print("  XX  " + n + ("  " + str(extra) if extra else ""))

def grupos(valores, cuantas=50):
    """Corre el analizador sobre una columna inventada y devuelve sus grupos."""
    filas = [["Opcion"]] + [[v] for v in valores for _ in range(cuantas)]
    an = A.analizar(filas)
    c = an["columnas"][0]
    return (c.get("parecidos") or []), (c.get("sospechosos") or [])

def es_par(gs, a, b):
    return any(set([a, b]) <= set(g) for g in gs)

def juntados(vals, cuantas=50):
    """Cuántos valores distintos quedan después de juntar las escrituras.

    Se repite cada valor como en `grupos()`: con cuatro filas la columna no se
    clasifica como categoria y el juntado —que solo corre para categorias— no
    llega a pasar. La prueba mediria otra cosa.
    """
    filas = [["Opcion"]] + [[v] for v in vals for _ in range(cuantas)]
    c = A.analizar(filas)["columnas"][0]
    return c.get("distintos"), [x["valor"] for x in (c.get("valores") or [])]


# ─────────────────────────────────────────────────────────────────────
print("=== ESCRITURA: el mismo texto tipeado distinto se JUNTA solo ===")
# Antes esto se avisaba y trababa el número. Ahora se junta y el número sale
# bien de una: son dos escrituras del mismo texto, no dos cosas. Ver
# test_juntar_escrituras.py, que prueba el juntado en detalle.
ESCRITURA = [
    ("espacio al final",        "SAN JUAN",   "SAN JUAN "),
    ("tilde de mas",            "No respondio, se insistio 3 veces",
                                "No respondió, se insistió 3 veces"),
    ("mayusculas",              "Meta MyS",   "META MYS"),
    ("la enie",                 "MAÑANA",     "MANANA"),
    ("espacios de mas adentro", "SAN  JUAN",  "SAN JUAN"),
]
for nombre, a, b in ESCRITURA:
    n, vals = juntados([a] * 3 + [b] * 2)
    check("%-24s %r + %r" % (nombre, a, b), n == 1, vals)

# ─────────────────────────────────────────────────────────────────────
print("\n=== CIERTOS: lo que NO se puede unir solo, se avisa ===")
# Acá unir sería decidir sobre el negocio, así que se avisa y no se toca.
CIERTOS = [
    ("puntuacion",              "GALICIA, BBVA", "GALICIA BBVA"),
    ("orden de las palabras",   "IG HISTORIAS", "HISTORIAS IG"),
]
for nombre, a, b in CIERTOS:
    par, _ = grupos([a, b])
    check("%-24s %r + %r" % (nombre, a, b), es_par(par, a, b), par)

# ─────────────────────────────────────────────────────────────────────
print("\n=== FALSOS: valores distintos que el detector viejo unia ===")
FALSOS = [
    ("dos ciudades",        "LA PLATA",        "MAR DEL PLATA"),
    ("los dos negocios",    "Meta MV",         "Meta MyS"),
    ("una tarjeta de mas",  "GALICIA, BBVA",   "GALICIA, BBVA, SANTANDER"),
    ("dos motivos",         "Compro en otro lugar por Precio",
                            "Compro en otro lugar por Comodidad"),
    ("dos promos",          "PROMO 4X3",       "PROMO 35%"),
    ("QR contra sucursal",  "QR DOLORES",      "SUC. DOLORES"),
    ("dos redes",           "IG ANUNCIO",      "FB ANUNCIO"),
    ("una promo mas larga", "PROMO ESQUINEROS", "PROMO ESQUINEROS Y SILLONES"),
    ("insistio o no",       "No respondió el primer mensaje",
                            "No respondio el primer mensaje, se le volvio a insistir"),
]
for nombre, a, b in FALSOS:
    par, sos = grupos([a, b])
    check("%-22s %r vs %r" % (nombre, a[:26], b[:26]),
          not es_par(par, a, b) and not es_par(sos, a, b), (par, sos))

# ─────────────────────────────────────────────────────────────────────
print("\n=== SOSPECHAS: se parecen, pero no se traba nada ===")
SOSPECHAS = [
    ("un tipeo largo", "Solo miraba precios, no estaba interesado",
                       "Solo miraba precios, no esta interesado"),
    ("dos letras dadas vuelta", "PROMO NORCENTER", "PROMO NORCENETR"),
    ("singular y plural", "ESQUINERO", "ESQUINEROS"),
]
for nombre, a, b in SOSPECHAS:
    par, sos = grupos([a, b])
    check("%-24s %r vs %r" % (nombre, a[:24], b[:24]),
          es_par(sos, a, b) and not es_par(par, a, b), (par, sos))

# ─────────────────────────────────────────────────────────────────────
print("\n=== LA REGLA DE ORO: una sospecha NUNCA traba una lectura ===")
filas = [["Motivo"]]
for v in ["Solo miraba precios, no estaba interesado"] * 400 + \
         ["Solo miraba precios, no esta interesado"] * 300 + \
         ["Compro"] * 200:
    filas.append([v])
an = A.analizar(filas)
ls = L.lecturas(filas, an)
trabadas = [l for l in ls if not l["apto_publicar"]]
check("hay sospechas en la columna", bool(an["columnas"][0].get("sospechosos")))
check("y ninguna lectura quedo trabada por eso",
      not any("dos formas" in l["motivo_no_apto"] for l in trabadas),
      [l["motivo_no_apto"] for l in trabadas])

print("\n=== EL REPARO SOLO TOCA LA LECTURA QUE NOMBRA AL VALOR PARTIDO ===")
filas = [["Ciudad"]]
for v in ["CABA"] * 500 + ["ROSARIO"] * 300 + ["SALTA"] * 120 + \
         ["SAN LUIS"] * 60 + ["SAN LUÍS"] * 55:
    filas.append([v])
an = A.analizar(filas)
ls = L.lecturas(filas, an)
part = [l for l in ls if "dos formas" in l["motivo_no_apto"]]
libres = [l for l in ls if l["apto_publicar"]]
check("el analizador junta el valor partido (SAN LUIS / SAN LUÍS)",
      any(v["valor"].startswith("SAN LU") and v["cuenta"] == 115
          for v in an["columnas"][0]["valores"]),
      an["columnas"][0]["valores"])
check("las lecturas de CABA siguen publicables",
      any("CABA" in l["texto"] for l in libres),
      [l["texto"] for l in ls])
# ya no hay nada trabado: juntadas, las 115 filas de San Luis son un número
# tan publicable como el de CABA
check("San Luis deja de estar trabado: el número ya salió bien",
      not part, [l["motivo_no_apto"] for l in ls if l["motivo_no_apto"]])

# ─────────────────────────────────────────────────────────────────────
print("\n=== LA PLANILLA DE VERDAD ===")
def _csv_de_la_planilla():
    """La copia local de la planilla, la busque desde donde la busque.

    Estaba escrita como "estado/cache_google/..." relativa a donde se corriera:
    desde esta carpeta el test no arrancaba y parecía roto cuando lo único que
    faltaba era el archivo. Ahora prueba los lugares donde de verdad vive.
    """
    nombre = "google_1WvFLjirSGYkhlOT_443938206.csv"
    aqui = os.path.dirname(os.path.abspath(__file__))
    candidatos = [
        os.path.join("estado", "cache_google", nombre),
        os.path.join(aqui, "estado", "cache_google", nombre),
        os.path.join(os.environ.get("MYS_PANEL_STATE", ""), "cache_google", nombre),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "PanelMyS_state",
                     "cache_google", nombre),
    ]
    for c in candidatos:
        if c and os.path.isfile(c):
            return c
    raise SystemExit(
        "No encontré la copia de la planilla (%s). Conectala una vez desde el "
        "panel, o copiá el CSV a la carpeta cache_google del estado."
        % nombre)


filas = list(csv.reader(io.open(_csv_de_la_planilla(),
                                encoding="utf-8-sig", newline="")))
an = A.analizar(filas)
ls = L.lecturas(filas, an)
av = revisor.revisar(filas, an)
apt = [l for l in ls if l["apto_publicar"]]
# ⚠️ NO se compara contra un numero exacto. La planilla es la de verdad y esta
# VIVA: crece todos los dias, asi que cualquier cifra clavada acá falla sola en
# una semana y el que la mire va a creer que rompio algo. Lo que importa es que
# el detector afinado sigue liberando muchos numeros y no volvio a los 5 de
# antes; ese es el contrato, no el 21 de un martes.
check("los numeros publicables siguen siendo muchos (eran 5 antes del arreglo)",
      len(apt) >= 20, len(apt))
part = [l for l in ls if "dos formas" in l["motivo_no_apto"]]
# eran 3, y las 3 eran «se insistio 3 veces» partido por las tildes: ese
# par ahora se junta solo, asi que no queda ninguna trabada
check("ya no queda ninguna lectura trabada por valor partido",
      len(part) == 0, len(part))
check("y las 3 nombran a «se insistio 3 veces»",
      all("insisti" in l["texto"] for l in part), [l["texto"] for l in part])

ciertos = [(c["nombre"], g) for c in an["columnas"] for g in (c.get("parecidos") or [])]
# eran 9; 5 eran pura escritura y ahora se juntan sin avisar. Quedan los 4
# que no se pueden unir solos (orden de palabras y puntuacion).
check("4 duplicados ciertos, los que no se pueden unir solos",
      len(ciertos) == 4, len(ciertos))
NO_DEBEN = ["MAR DEL PLATA", "Meta MV", "SANTANDER", "PROMO 4X3",
            "SUC. DOLORES", "FB ANUNCIO", "Comodidad"]
malos = [(n, g) for n, g in ciertos
         if any(x in " ".join(g) for x in ["MAR DEL PLATA", "Meta MV", "PROMO 4X3",
                                           "SUC. DOLORES", "FB ANUNCIO", "Comodidad"])]
check("ninguno de los falsos positivos viejos sigue ahi", not malos, malos)

sos = [(c["nombre"], g) for c in an["columnas"] for g in (c.get("sospechosos") or [])]
check("1 sola sospecha, y es la de 'no estaba / no está'",
      len(sos) == 1 and "interesad" in " ".join(sos[0][1]), sos)

# el aviso conserva su recuento de filas despues de renombrar el titulo
ac = derivaciones.acomodar_avisos(av, an)
dup = [a for a in ac if a.get("clase") == "valor_duplicado"]
check("los avisos de duplicado siguen llegando", len(dup) == 4, len(dup))
check("y conservan el recuento de filas (clase, no texto del titulo)",
      any(a.get("filas_afectadas") for a in dup),
      [(a["titulo"], a.get("filas_afectadas")) for a in dup])
sosp = [a for a in ac if a.get("clase") == "valor_sospechoso"]
check("una sospecha nunca se marca grave",
      all(a["gravedad"] != "grave" for a in sosp),
      [(a["titulo"], a["gravedad"], a.get("filas_afectadas")) for a in sosp])


# ─────────────────────────────────────────────────────────────────────
print()
print("=== FECHAS: ordenarlas como texto daba un periodo falso ===")
import datetime
from datos import reporte

CASOS = [
    ("dia/mes/anio",      "24/01/2025",  datetime.date(2025, 1, 24)),
    ("ISO",               "2026-08-28",  datetime.date(2026, 8, 28)),
    ("anio de dos cifras", "3/4/26",     datetime.date(2026, 4, 3)),
    ("un digito",         "1/1/2026",    datetime.date(2026, 1, 1)),
    ("bisiesto",          "29/02/2024",  datetime.date(2024, 2, 29)),
    ("31 de febrero",     "31/02/2026",  None),
    ("no es fecha",       "no es fecha", None),
    ("vacio",             "",            None),
]
for nombre, v, esperado in CASOS:
    check("%-20s %-13r -> %s" % (nombre, v, esperado), A._a_fecha(v) == esperado, A._a_fecha(v))

# El caso real: ordenadas como texto, el minimo era "1/02/2026" y el maximo
# "9/08/2026" — se perdia un anio entero y ademas "9/..." > "2026-..." disparaba
# el aviso de fechas futuras.
filas_f = [["Fecha"]] + [[v] for v in
    ["24/01/2025", "1/02/2026", "9/08/2026", "28/08/2026", "2/01/2026"]]
cf = A.analizar(filas_f)["columnas"][0]
check("la columna se reconoce como fecha", cf["tipo"] == "fecha", cf["tipo"])
check("desde = la mas vieja de verdad, no la primera alfabeticamente",
      cf["desde"] == "2025-01-24", cf["desde"])
check("hasta = la mas nueva de verdad", cf["hasta"] == "2026-08-28", cf["hasta"])
check("se guardan en ISO, para poder compararlas", cf["desde"] < cf["hasta"],
      (cf["desde"], cf["hasta"]))

print()
print("=== EL PERIODO DEL REPORTE ===")
an2 = A.analizar(filas)
av2 = revisor.revisar(filas, an2)
ls2 = L.lecturas(filas, an2)
rep = reporte.armar(an2, av2, ls2, "Derivaciones", "Planilla de Google")
check("un solo formato de fecha, y el de aca (dd/mm/aaaa)",
      rep["periodo"].count("/") == 4 and "-" not in rep["periodo"], rep["periodo"])
check("arranca en 2025 y no en febrero de 2026",
      rep["periodo"].startswith("24/01/2025"), rep["periodo"])
check("sin el falso «hay fechas posteriores, mal cargadas»",
      "mal cargadas" not in rep["periodo"], rep["periodo"])

print()
print("=== GRAVEDAD: el reporte y el panel tienen que contar igual ===")
dup2 = [a for a in av2 if a.get("clase") == "valor_duplicado"]
check("grave solo lo que pesa 100 filas o mas",
      all((a["gravedad"] == "grave") == ((a.get("filas_afectadas") or 0) >= 100)
          for a in dup2),
      [(a["gravedad"], a.get("filas_afectadas")) for a in dup2])
ac2 = derivaciones.acomodar_avisos(revisor.revisar(filas, an2), an2)
d3 = [a for a in ac2 if a.get("clase") == "valor_duplicado"]
check("las dos vias dan la misma gravedad",
      sorted(a["gravedad"] for a in dup2) == sorted(a["gravedad"] for a in d3))
# Eran 2 y los 2 pesaban mas de 100 filas: los dos eran el mismo texto con y
# sin tildes. Juntados solos, ya no hay ningun duplicado grave: lo que queda
# avisado es orden de palabras, y ninguno llega a 100 filas.
check("ningun duplicado queda grave: los pesados se juntan solos",
      sum(1 for a in dup2 if a["gravedad"] == "grave") == 0,
      [(a["gravedad"], a.get("filas_afectadas")) for a in dup2])

print("\n================ %d OK, %d fallas ================" % (ok, len(fail)))
for f in fail: print("  XX " + f)
sys.exit(1 if fail else 0)
