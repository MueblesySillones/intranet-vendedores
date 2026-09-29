# -*- coding: utf-8 -*-
"""De dónde viene cada consulta: ¿de la zona del local, de lejos, o del interior?

POR QUÉ EXISTE

La planilla tiene una columna `Localidad`, pero mezcla tres cosas distintas:
localidades del conurbano (Quilmes, Lanús), zonas sin punto fijo («ZONA
NORTE», «INT (BUENOS AIRES)») y provincias enteras (Córdoba, Neuquén). Con eso
no se puede contestar la pregunta que se hizo el equipo: *«la derivación que
cerró el vendedor, ¿es de su zona o del interior?»*.

Acá se traduce cada valor a una de cinco categorías, SIEMPRE medidas contra la
sucursal del vendedor que la atendió:

    propia    la localidad es la del local
    cerca     otra localidad, a menos de TOPE_KM de SU sucursal
    amplia    «zona norte» / «zona oeste»: se le atribuyen a la sucursal que
              las atendió, pero no se mezclan con las de arriba
    lejos     misma provincia pero fuera de ese radio, o una zona sin punto
    interior  otra provincia

⚠️ Se mide contra la sucursal DEL VENDEDOR, no contra la más cercana de todas.
   Quilmes está a 12 km de Hudson, pero si la atendió alguien de Pilar, para
   ESE vendedor la consulta vino de lejos. Es la única forma de que el número
   diga algo sobre el trabajo de la persona.

POR QUÉ EL CORTE ES 30 KM, Y NO UN NÚMERO CUALQUIERA

Lo dio el propio negocio: de la sucursal de Hudson a la de CABA hay 28 km
—medido por el equipo, y el cálculo de acá da 30—. Si dos locales propios están
a esa distancia, una localidad a 23 km no puede contar como «lejos». O sea que
la escala sale de la red de sucursales y no de una preferencia.

Además los datos se parten solos: ordenadas por distancia, las localidades van
4, 6, 7, 10, 12, 13, 15, 20, 22, 23, 32, 41 km… y después saltan a 89, 165,
175, 232. Entre 41 y 89 no hay nada. Mover el corte entre 30 y 60 km cambia el
resultado en 2 derivaciones sobre 1.851.

POR QUÉ LAS COORDENADAS ESTÁN ESCRITAS ACÁ

Se sacaron una vez de OpenStreetMap (dato abierto) y quedaron horneadas. El
panel corre en las sucursales y tiene que funcionar sin internet; además una
tabla de 30 lugares que casi nunca cambia no justifica una dependencia de red
que puede fallar justo cuando alguien está armando el reporte del mes.
Si aparece una localidad nueva, cae en «sin ubicar» y el reporte lo dice, que
es mejor que inventarle una posición.
"""
import math
import unicodedata

# Las 23 provincias argentinas. Escrito completo a propósito: una lista armada
# con «las que aparecieron en la planilla» se rompe el día que entre una
# consulta de Formosa —que hoy no aparece ninguna, y por eso mismo—.
PROVINCIAS = [
    "Buenos Aires", "Catamarca", "Chaco", "Chubut", "Córdoba", "Corrientes",
    "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza",
    "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan", "San Luis",
    "Santa Cruz", "Santa Fe", "Santiago del Estero", "Tierra del Fuego",
    "Tucumán",
]

TOPE_KM = 30.0

# Dónde está cada local. CABA es Av. Belgrano 2419, que lo confirmó el equipo:
# tomar «el centro de CABA» corría el punto y con él todas sus distancias.
SUCURSALES = {
    "CABA":      (-34.6143, -58.4004),
    "Hudson":    (-34.7911, -58.1554),
    "Norcenter": (-34.5296, -58.5220),
    "Canning":   (-34.8632, -58.5010),
    "Pilar":     (-34.4571, -58.9142),
}

# Las localidades que aparecen en la planilla y SÍ son un punto en el mapa.
LOCALIDADES = {
    "ADROGUE": (-34.7974, -58.3886),
    "AVELLANEDA": (-34.6648, -58.3628),
    "BAHIA BLANCA": (-38.7177, -62.2655),
    "BANFIELD": (-34.7437, -58.3961),
    "BENAVIDEZ": (-34.4093, -58.6846),
    "CANUELAS": (-35.0540, -58.7617),
    "CHASCOMUS": (-35.5787, -58.0138),
    "DOLORES": (-36.3154, -57.6755),
    "EZEIZA": (-34.8168, -58.5474),
    "LA PLATA": (-34.9207, -57.9538),
    "LANUS": (-34.7074, -58.3906),
    "LOMAS DE ZAMORA": (-34.7573, -58.4027),
    "LUJAN": (-34.5662, -59.1153),
    "MAR DEL PLATA": (-37.9976, -57.5482),
    "MONTE GRANDE": (-34.8193, -58.4664),
    # ⚠️ Paraná, ENTRE RÍOS. La búsqueda automática devolvía un punto en
    # Misiones —hay más de un «Paraná», y uno es el río—. Corregido a mano:
    # la categoría no cambiaba (lejos igual), pero el número estaba mal.
    "PARANA": (-31.7333, -60.5333),
    "PERGAMINO": (-33.8975, -60.5750),
    "PINAMAR": (-37.1099, -56.8539),
    "QUILMES": (-34.7244, -58.2588),
    "ROSARIO": (-32.9594, -60.6617),
    "SAN ANDRES": (-34.5635, -58.5407),
    "TIGRE": (-34.4235, -58.5818),
    "ZARATE": (-34.0955, -59.0245),
}

# Valores que NO son un punto: son regiones. Geocodificar «ZONA NORTE» da una
# coordenada inventada, así que se resuelven por regla.
#
# ⚠️ «ZONA NORTE» y «ZONA OESTE» se le atribuyen A LA SUCURSAL QUE LAS ATENDIÓ,
#    como pidió el equipo: «si dice Norcenter, zona norte, Flor… tomá zona
#    norte como Norcenter». Pero NO se meten adentro de «propia», y la razón es
#    un dato duro: esas 154 consultas cerraron CERO ventas. Mezclarlas con las
#    de la localidad del local —que cierran 3,5%— hace desaparecer eso.
#    Por eso son su propia fila: se ve de quién son Y se ve que no cierran.
ZONA_DE_LA_SUCURSAL = {
    "ZONA NORTE": "norte",
    "ZONA OESTE": "oeste",
}
# Estas otras dicen en el nombre que son de lejos, y no hay nada que atribuir.
ZONAS_SIN_PUNTO = {
    "INT (BUENOS AIRES)": "interior bonaerense",
    "COSTA ATLANTICA": "costa",
}

CATEGORIAS = [
    ("propia", "De la localidad del local"),
    ("cerca", "De la zona (a menos de %d km)" % int(TOPE_KM)),
    ("amplia", "De su zona amplia (norte / oeste)"),
    ("lejos", "De lejos, misma provincia"),
    ("interior", "Del interior del país"),
]


def norm(s):
    """Mayúsculas, sin tildes y sin el punto final que a veces queda («ZÁRATE.»)."""
    s = unicodedata.normalize("NFKD", str(s or "").upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().rstrip(".").strip()


_PROV = {norm(p) for p in PROVINCIAS}
# Buenos Aires NO cuenta como interior del país: ahí están los cinco locales.
# Una consulta de Mar del Plata está lejos, pero no es lo mismo que una de
# Jujuy, y meterlas en la misma bolsa borra esa diferencia.
_OTRAS_PROVINCIAS = _PROV - {norm("Buenos Aires")}
_SUC = {norm(s): s for s in SUCURSALES}


def km(a, b):
    """Distancia en línea recta. Alcanza de sobra para decidir cerca o lejos:
    contra los 28 km que midió el equipo entre Hudson y CABA, esto da 30."""
    R = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = (math.sin(dp / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


# ⚠️ 27-sep-2026: Rosario y Paraná tienen coordenadas en LOCALIDADES, así que
# se medían en km contra el local y caían en «lejos, misma provincia» —que es
# Buenos Aires—. Son de Santa Fe y de Entre Ríos: interior del país. En la
# planilla eran 60 consultas contadas en el lugar equivocado.
CIUDADES_DE_OTRA_PROVINCIA = {
    "ROSARIO": "Santa Fe",
    "PARANA": "Entre Ríos",
}


def provincia_del_lugar(localidad):
    """La provincia de lo que dice la columna Localidad, si NO es Buenos Aires:
    el valor puede ser una provincia («NEUQUEN») o una ciudad de otra
    («ROSARIO»). None = Buenos Aires o CABA."""
    u = norm(localidad)
    if u in CIUDADES_DE_OTRA_PROVINCIA:
        return CIUDADES_DE_OTRA_PROVINCIA[u]
    p = provincia_de(localidad)
    if p and norm(p) != norm("Buenos Aires"):
        return p
    return None


def provincia_de(localidad):
    """El nombre formal de la provincia, si el valor ES una provincia."""
    u = norm(localidad)
    for p in PROVINCIAS:
        if norm(p) == u:
            return p
    return None


def clasificar(localidad, sucursal_vendedor):
    """(categoria, detalle) para una consulta. `None` si no se puede saber.

    `detalle` es para poder explicar el número: los kilómetros cuando se
    calcularon, o el nombre de la provincia/zona cuando salió por regla.
    """
    u = norm(localidad)
    if not u:
        return None, ""                      # sin localidad: no entra al corte
    if u in _OTRAS_PROVINCIAS:
        return "interior", provincia_de(localidad) or ""
    if u in CIUDADES_DE_OTRA_PROVINCIA:
        return "interior", CIUDADES_DE_OTRA_PROVINCIA[u]
    if norm("Buenos Aires") == u:
        return "lejos", "provincia de Buenos Aires, sin precisar"
    if u in ZONA_DE_LA_SUCURSAL:
        # de la sucursal que la atendió, sea cual sea: la atribución sigue a
        # quien la trabajó y no a la geografía
        return "amplia", "%s de %s" % (ZONA_DE_LA_SUCURSAL[u],
                                       sucursal_vendedor or "?")
    if u in ZONAS_SIN_PUNTO:
        return "lejos", ZONAS_SIN_PUNTO[u]
    if u in _SUC:
        # la localidad es un local: propia solo si es EL DE ESTE VENDEDOR
        return (("propia", "") if _SUC[u] == sucursal_vendedor
                else ("lejos", "es zona de %s" % _SUC[u]))
    p = LOCALIDADES.get(u)
    q = SUCURSALES.get(sucursal_vendedor)
    if not p or not q:
        return None, ""                      # no la conocemos: no se inventa
    d = km(p, q)
    return (("cerca" if d <= TOPE_KM else "lejos"), "%.0f km" % d)


def sucursal_mas_cerca(localidad):
    """(sucursal, km) del local más cercano. Para explicar, no para clasificar:
    «la más cercana» no es «de la zona» —Bahía Blanca cae en Canning a 544 km—."""
    p = LOCALIDADES.get(norm(localidad))
    if not p:
        return None, None
    d, s = min((km(p, q), n) for n, q in SUCURSALES.items())
    return s, d
