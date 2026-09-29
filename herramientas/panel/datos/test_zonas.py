# -*- coding: utf-8 -*-
"""De dónde viene cada consulta: de la zona del local, de lejos, o del interior.

Las reglas que se prueban acá NO son de programación, son del negocio, y las
dio el equipo:

  · «de la sucursal de Hudson a la de CABA hay 28 kilómetros» → esa es la
    escala. Si dos locales propios están a esa distancia, una localidad a 23 km
    no puede contar como lejos. De ahí sale el corte de 30 km.
  · «todas las consultas que son cerca de La Plata se las mandamos a Hudson» →
    y la planilla lo confirma: 136 de 137 las atendió Hudson.
  · «si en el excel dice Norcenter, zona norte, Flor… tomá zona norte como
    Norcenter» → la atribución sigue a quien la atendió, no a la geografía.
    Pero NO se mezcla con «propia»: esas 154 consultas cerraron 0 ventas, y
    metidas ahí adentro harían desaparecer ese dato. Van en su propia fila.

Y la que más importa: se mide contra la sucursal DEL VENDEDOR, no contra la
más cercana de todas. Si a alguien de Pilar le toca una consulta de Quilmes,
para esa persona vino de lejos, aunque Quilmes esté a 12 km de Hudson.

    python test_zonas.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos import zonas as Z  # noqa: E402

RES = []


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append(True)
        print("PASS | %s | %s" % (nombre, nota))
    except AssertionError as e:
        RES.append(False)
        print("FAIL | %s | %s" % (nombre, e))


# ─────────────── la escala que dio el equipo ───────────────
def caso_la_vara():
    d = Z.km(Z.SUCURSALES["Hudson"], Z.SUCURSALES["CABA"])
    assert 26 <= d <= 32, "Hudson–CABA da %.0f km y el equipo midió 28" % d
    return "Hudson–CABA = %.0f km (el equipo midió 28)" % d


check("la distancia entre locales coincide con la medida del equipo", caso_la_vara)


def caso_las_23():
    assert len(Z.PROVINCIAS) == 23, "hay %d provincias" % len(Z.PROVINCIAS)
    for p in ("Formosa", "Tierra del Fuego", "Buenos Aires"):
        assert p in Z.PROVINCIAS, "falta %s" % p
    return "están las 23, incluidas las que todavía no aparecieron"


check("la lista de provincias está completa", caso_las_23)


# ─────────────── lo que dijo el equipo, hecho regla ───────────────
def caso_la_plata():
    cat, det = Z.clasificar("LA PLATA", "Hudson")
    assert cat == "cerca", "La Plata quedó como %r" % cat
    return "La Plata → zona de Hudson (%s)" % det


check("La Plata es zona de Hudson", caso_la_plata)


def caso_quilmes_ajeno():
    """La misma localidad, medida contra otra sucursal, NO es de la zona."""
    a, _ = Z.clasificar("QUILMES", "Hudson")
    b, _ = Z.clasificar("QUILMES", "Pilar")
    assert a == "cerca", "Quilmes/Hudson dio %r" % a
    assert b == "lejos", "Quilmes/Pilar dio %r" % b
    return "Quilmes: cerca para Hudson, lejos para Pilar"


check("se mide contra la sucursal DEL VENDEDOR", caso_quilmes_ajeno)


def caso_propia():
    a, _ = Z.clasificar("CABA", "CABA")
    b, _ = Z.clasificar("CABA", "Canning")
    assert a == "propia", "CABA/CABA dio %r" % a
    assert b == "lejos", "CABA/Canning dio %r" % b
    return "la localidad del local es «propia» solo para ese local"


check("«propia» es del local, no de cualquiera", caso_propia)


def caso_zona_de_la_sucursal():
    """«Si dice Norcenter, zona norte, Flor… tomá zona norte como Norcenter.»

    La atribución sigue a QUIEN LA ATENDIÓ, no a la geografía: la misma «zona
    norte» es de Norcenter o de Pilar según quién la haya trabajado.
    """
    for suc in ("Norcenter", "Pilar", "CABA"):
        for v in ("ZONA NORTE", "ZONA OESTE"):
            cat, det = Z.clasificar(v, suc)
            assert cat == "amplia", "%s/%s dio %r" % (v, suc, cat)
            assert suc in det, "no dice de quién es: %r" % det
    return "zona norte/oeste se atribuyen a la sucursal que las atendió"


check("«zona norte» es de la sucursal que la atendió", caso_zona_de_la_sucursal)


def caso_amplia_no_es_propia():
    """Por qué NO se mezcla con «propia»: esas 154 consultas cerraron 0 ventas.
    Metidas adentro de la zona, harían desaparecer ese dato."""
    a, _ = Z.clasificar("ZONA NORTE", "Norcenter")
    b, _ = Z.clasificar("NORCENTER", "Norcenter")
    assert a != b, "zona norte quedó igual que la localidad del local"
    assert b == "propia" and a == "amplia"
    return "«zona amplia» es su propia fila, no se mezcla con la del local"


check("la zona amplia no se confunde con la propia", caso_amplia_no_es_propia)


def caso_zonas_lejanas():
    """Estas dos dicen en el nombre que son de lejos: no hay qué atribuir."""
    for v in ("INT (BUENOS AIRES)", "COSTA ATLÁNTICA"):
        cat, _ = Z.clasificar(v, "Norcenter")
        assert cat == "lejos", "%s dio %r" % (v, cat)
    return "«int (buenos aires)» y «costa atlántica» siguen siendo lejos"


check("las zonas que dicen lejos en el nombre, siguen lejos", caso_zonas_lejanas)


def caso_interior():
    cat, det = Z.clasificar("CORDOBA", "Hudson")
    assert cat == "interior", "Córdoba dio %r" % cat
    assert det == "Córdoba", "no devolvió el nombre formal: %r" % det
    return "Córdoba → interior del país"


check("otra provincia es interior del país", caso_interior)


def caso_buenos_aires_no_es_interior():
    """Ahí están los cinco locales: Mar del Plata está lejos, pero no es Jujuy."""
    cat, _ = Z.clasificar("MAR DEL PLATA", "Canning")
    assert cat == "lejos", "Mar del Plata dio %r" % cat
    otra, _ = Z.clasificar("JUJUY", "Canning")
    assert otra == "interior"
    return "Mar del Plata = lejos · Jujuy = interior"


check("Buenos Aires NO cuenta como interior del país",
      caso_buenos_aires_no_es_interior)


def caso_lejos_de_verdad():
    """Bahía Blanca está a 544 km del local más cercano: que sea «el más
    cercano» no la hace de la zona. Es el caso que justifica el corte."""
    s, d = Z.sucursal_mas_cerca("BAHIA BLANCA")
    assert d > 400, "da %.0f km" % d
    cat, _ = Z.clasificar("BAHIA BLANCA", s)
    assert cat == "lejos", "quedó como %r" % cat
    return "Bahía Blanca: %s es el más cercano a %.0f km, y aun así es lejos" % (s, d)


check("la sucursal más cercana no alcanza para ser «de la zona»",
      caso_lejos_de_verdad)


def caso_sin_localidad():
    cat, _ = Z.clasificar("", "Hudson")
    assert cat is None, "sin localidad devolvió %r" % cat
    cat2, _ = Z.clasificar("VILLA INVENTADA", "Hudson")
    assert cat2 is None, "una localidad desconocida devolvió %r" % cat2
    return "sin dato no se clasifica: no se inventa una posición"


check("lo que no se sabe no se adivina", caso_sin_localidad)


def caso_escrituras():
    """La planilla escribe «ZÁRATE.» con punto y «LANÚS» con tilde."""
    for v in ("ZÁRATE.", "zárate", "ZARATE"):
        cat, _ = Z.clasificar(v, "Pilar")
        assert cat is not None, "%r no se reconoció" % v
    a, _ = Z.clasificar("LANÚS", "CABA")
    b, _ = Z.clasificar("LANUS", "CABA")
    assert a == b == "cerca", "Lanús con y sin tilde: %r / %r" % (a, b)
    return "tildes, mayúsculas y el punto final no cambian el resultado"


check("se banca cómo se escribe en la planilla", caso_escrituras)


def caso_parana():
    """Paraná es la capital de Entre Ríos. La búsqueda automática devolvía un
    punto en Misiones —hay más de un Paraná, y uno es el río—."""
    lat, lon = Z.LOCALIDADES["PARANA"]
    assert -32.5 < lat < -31.0, "la latitud de Paraná es %.2f" % lat
    return "Paraná apunta a Entre Ríos (%.2f, %.2f)" % (lat, lon)


check("Paraná es la de Entre Ríos, no la del río", caso_parana)


# ────────── la lámina del reparto, contra la planilla de verdad ──────────
def caso_reparto_ordena_por_provincias():
    """«Que sean los vendedores que reciben más consultas de las distintas
    provincias»: el orden es por interior, no por el bulto de todo lo lejano.

    Los dos ordenes dan cosas DISTINTAS y por eso la prueba sirve: en Buenos
    Aires lo lejano está dominado por «zona norte» y «zona oeste», así que
    ordenar por eso pone arriba a gente que casi no recibe del interior.
    """
    import csv
    import glob
    import io as _io
    from datos import derivaciones as D

    st = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PanelMyS_state")
    ar = sorted(glob.glob(os.path.join(st, "cache_google", "*")))
    if not ar:
        return "(sin la planilla a mano, salteado)"
    filas = list(csv.reader(_io.StringIO(
        _io.open(ar[-1], encoding="utf-8", errors="replace").read())))
    d = D.analizar(filas, st)
    vs = [(v, b) for v, b in d["vendedores"].items() if b.get("provincias")]
    assert vs, "nadie tiene consultas del interior"

    def del_interior(b):
        return sum(b["provincias"].values())

    def parte_lejana(b):
        z = b.get("zonas") or {}
        return ((z.get("lejos", 0) + z.get("amplia", 0) + z.get("interior", 0))
                / float(max(1, sum(z.values()))))

    por_inter = sorted(vs, key=lambda x: -del_interior(x[1]))
    por_lejos = sorted(vs, key=lambda x: -parte_lejana(x[1]))
    assert por_inter[0][0] != por_lejos[0][0], (
        "los dos ordenes dan lo mismo: la prueba no distingue nada")
    b0 = por_inter[0][1]
    assert len(b0["provincias"]) >= 2, "el primero recibe de una sola provincia"
    return ("por interior manda %s (%d consultas de %d provincias); por bulto "
            "lejano mandaría %s"
            % (por_inter[0][0].title(), del_interior(b0), len(b0["provincias"]),
               por_lejos[0][0].title()))


check("el reparto ordena por consultas del interior, no por lo lejano",
      caso_reparto_ordena_por_provincias)

print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
