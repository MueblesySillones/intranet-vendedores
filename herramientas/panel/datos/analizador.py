# -*- coding: utf-8 -*-
"""Mira una planilla y deduce que es cada columna.

La idea es no tener que saber de antemano como se llama nada. Se le da una
tabla —de un CSV, de una planilla de Google, de lo que sea— y devuelve que
tiene adentro y que se puede contar. Asi sirve para la de derivaciones y para
cualquier otra que venga despues.

Solo biblioteca estandar: esto termina adentro del panel, que se distribuye
como .exe, y sumarle pandas lo engordaria 50 MB.

QUE DECIDE
  · CONTACTO  — nombre, telefono, mail. Se marca como sensible y NO se agrega
                ni se publica jamas. Se reconoce por el nombre de la columna y,
                sobre todo, por como son los valores.
  · FECHA     — sirve para la linea de tiempo y para comparar periodos.
  · CATEGORIA — pocos valores que se repiten: sucursal, medio, vendedor.
                De estas salen los cortes.
  · MOTIVO    — texto escrito a mano que se repite PARECIDO pero no igual.
                Es el caso de los seguimientos, y el mas valioso: dice por que
                se cae una derivacion. Necesita agruparse antes de contarse.
  · NUMERO    — para sumas y promedios.
  · LIBRE     — texto que casi no se repite; no se cuenta, solo se muestra.
"""
import csv
import datetime
import io
import re
import unicodedata
from collections import Counter

# ── palabras que delatan una columna de contacto ─────────────────────────
NOMBRE_CONTACTO = re.compile(
    r"(mail|correo|e-?mail|tel|cel|whats|contacto|nombre|apellido|dni|"
    r"documento|direcci|domicilio|numero|nro|movil)", re.I)
ES_MAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
ES_TEL = re.compile(r"^[\d\s()+\-\.]{7,20}$")

# palabras vacias: no sirven para agrupar motivos
VACIAS = {
    "de", "la", "el", "en", "y", "a", "que", "se", "un", "una", "los", "las",
    "por", "con", "para", "su", "al", "lo", "le", "es", "del", "no", "mas",
    "muy", "ya", "pero", "o", "sin", "sobre", "dijo", "dice", "esta", "fue",
}


def _txt(v):
    """El texto de una celda. Vacio SOLO si no hay nada.

    ⚠️ Sin esto se usaba `str(v or "")`, que convierte el numero 0 en "" porque
    el cero es falso en Python. Una columna de cantidades con muchos ceros
    quedaba medio vacia a los ojos del analizador, y los promedios daban de mas.
    """
    return "" if v is None else str(v)


def _norm(s):
    """Minusculas, sin tildes, sin puntuacion, espacios parejos."""
    s = unicodedata.normalize("NFKD", _txt(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("ñ", "n")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _es_fecha(v):
    v = _txt(v).strip()
    if not v:
        return False
    return bool(re.match(r"^\d{4}-\d{1,2}-\d{1,2}", v) or
                re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", v))


_RE_DMA = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$")


def _a_fecha(v):
    """El valor como date, o None. Acepta 'aaaa-mm-dd' y 'd/m/aaaa'.

    ⚠️ EXISTE PORQUE ORDENAR FECHAS COMO TEXTO ESTA MAL, y en esta planilla
    estaba dando un periodo falso: con formato d/m/aaaa, '1/02/2026' es la
    menor alfabeticamente y '9/08/2026' la mayor, asi que el reporte anunciaba
    "1/02/2026 al 9/08/2026" cuando los datos iban del 24/01/2025 al 28/08/2026
    — se perdia un año entero. Y como '9/...' es mayor que '2026-...' en texto,
    encima disparaba el aviso de "hay fechas posteriores, mal cargadas" sin que
    hubiera ninguna.
    """
    v = _txt(v).strip()
    if not v:
        return None
    m = _RE_DMA.match(v)
    if m:
        d, mes, anio = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if anio < 100:
            anio += 2000
        try:
            return datetime.date(anio, mes, d)
        except ValueError:          # 31/02, o un año imposible
            return None
    try:
        return datetime.date(*[int(x) for x in v[:10].split("-")])
    except (ValueError, TypeError):
        return None


def _es_numero(v):
    v = _txt(v).strip().replace(".", "").replace(",", ".")
    if not v:
        return False
    try:
        float(v)
        return True
    except ValueError:
        return False


def _clasificar(nombre, valores):
    """Que es esta columna. `valores` ya viene sin vacios."""
    if not valores:
        return "libre"
    muestra = valores[:400]
    n = len(muestra)
    distintos = len(set(valores))
    repite = distintos / float(len(valores))

    # 1) contacto: manda como se ven los valores, y si no, el nombre
    mails = sum(1 for v in muestra if ES_MAIL.match(str(v).strip()))
    if mails > n * 0.6:
        return "contacto"
    tels = sum(1 for v in muestra if ES_TEL.match(str(v).strip()))
    if tels > n * 0.7 and distintos > n * 0.5:
        return "contacto"
    # ⚠️ El nombre de la columna ALCANZA, sin pedirle nada a los valores.
    # Antes se exigia ademas que fueran mayormente distintos, y con 1.800 filas
    # y nombres que se repiten esa condicion no se cumplia: la columna "Nombre"
    # quedaba sin marcar y podia terminar publicada. Ante la duda gana
    # "sensible": marcar de mas cuesta un chequeo, marcar de menos cuesta el
    # telefono de un cliente en una pagina publica.
    if NOMBRE_CONTACTO.search(nombre):
        return "contacto"

    # 2) fecha
    if sum(1 for v in muestra if _es_fecha(v)) > n * 0.8:
        return "fecha"

    # 3) numero
    if sum(1 for v in muestra if _es_numero(v)) > n * 0.9:
        return "numero"

    # 4) LISTA: pocos valores distintos que se repiten exactos.
    #    Es el caso normal en esta planilla: casi todas las columnas son
    #    desplegables con estados precargados, asi que no hay variantes de
    #    tipeo y contar por valor exacto es correcto.
    #    ⚠️ Antes esto ademas exigia que la etiqueta fuera CORTA, y estaba mal:
    #    una opcion de desplegable como "No respondio, se le envio mensaje"
    #    tiene cinco palabras y es una lista igual. Lo que separa una lista de
    #    un texto libre no es el largo: es que los valores se repitan exactos.
    #    El tope de 60 da lugar a listas largas de estados.
    largo = sum(len(_norm(v).split()) for v in muestra) / float(n)
    if distintos <= 60 and repite < 0.35:
        return "categoria"

    # 5) motivo: texto que se repite PARECIDO. Se mide con las palabras: si
    #    unas pocas palabras cubren casi todo, es un motivo escrito a mano y
    #    no un texto libre de verdad.
    palabras = Counter()
    for v in muestra:
        palabras.update(p for p in _norm(v).split() if p not in VACIAS and len(p) > 3)
    if palabras:
        top = sum(c for _, c in palabras.most_common(12))
        concentrado = top / float(sum(palabras.values())) > 0.45
        if concentrado and distintos < len(valores) * 0.6:
            return "motivo"
    # frases largas con muchas variantes: texto escrito a mano de verdad.
    # Con desplegables esto no deberia dispararse nunca; queda como red de
    # seguridad para una planilla vieja, o para cuando la lista de opciones se
    # edito y conviven la forma vieja y la nueva.
    if largo >= 3.5 and repite < 0.6:
        return "motivo"

    return "libre"


NEGACIONES = {"no", "nunca", "sin", "tampoco", "ni"}


def _claves_de(texto):
    """Las palabras que definen una frase, con la negacion pegada al verbo.

    "no respondio, se le envio mensaje" -> ["no_respondio", "envio", "mensaje"]
    "respondio, pidio informacion"      -> ["respondio", "pidio", "informacion"]
    Asi los opuestos dejan de parecerse.
    """
    salida, negar = [], False
    for p in _norm(texto).split():
        if p in NEGACIONES:
            negar = True
            continue
        if len(p) <= 3 or p in VACIAS:
            continue
        salida.append(("no_" + p) if negar else p)
        negar = False
    return salida


# =====================================================================
#  DOS OPCIONES QUE SON LA MISMA
#
#  Esto existe porque alguien edita el desplegable y las filas viejas se
#  quedan con el texto anterior: el numero queda partido en dos y nadie se
#  entera.
#
#  ⚠️ LO QUE HABIA ANTES Y POR QUE NO SERVIA (28-ago-2026)
#  La regla era "si comparten sus DOS primeras palabras significativas, son
#  la misma cosa", con _claves_de, que descarta las palabras de 3 letras o
#  menos. Resultado: `MAR DEL PLATA` -> ["plata"] y `LA PLATA` -> ["plata"],
#  o sea la MISMA clave. Sobre la planilla de derivaciones daba 23 grupos de
#  los cuales 2 eran de verdad: acusaba a `LA PLATA / MAR DEL PLATA`,
#  `Meta MV / Meta MyS` (que son los dos negocios distintos),
#  `Compro por Precio / Compro por Comodidad`, `QR DOLORES / SUC. DOLORES` y
#  `PROMO 4X3 / PROMO 35% / PROMO 10%OFF`. Y como un reparo TRABA la lectura,
#  esos falsos positivos bloqueaban 18 de los 23 numeros del tablero.
#
#  Y encima se le escapaban duplicados reales: `GALICIA, BBVA` y
#  `BBVA, GALICIA` tienen claves distintas y pasaban de largo.
#
#  AHORA SON DOS NIVELES, con consecuencias distintas:
#
#    parecidos    CERTEZA. El mismo valor escrito dos veces. Solo cuenta lo
#                 que no cambia el significado: mayusculas, tildes, la ñ,
#                 puntuacion, espacios de mas — y el orden de las palabras,
#                 porque `IG HISTORIAS` y `HISTORIAS IG` son lo mismo.
#                 Esto TRABA la lectura, y puede, porque no se equivoca.
#
#    sospechosos  UNA DUDA. Se parecen tanto que puede haber un tipeo en el
#                 medio ("no estaba interesado" / "no está interesado").
#                 Esto NO traba nada: se avisa y decide la persona. Un
#                 parecido no es una certeza, y trabar por las dudas fue
#                 exactamente el error anterior.
# =====================================================================

def _bolsa(norm):
    """Las palabras de un valor ya normalizado, ordenadas.

    'ig historias' y 'historias ig' devuelven las dos 'historias ig'. Es el
    unico permiso que se toma el nivel de CERTEZA, y se lo toma porque el
    orden de dos etiquetas sueltas no cambia que sean las mismas etiquetas.
    """
    return " ".join(sorted(norm.split()))


def _distancia(a, b, tope):
    """Damerau-Levenshtein con corte: si pasa `tope`, devuelve tope+1.

    Con transposicion porque el tipeo mas comun es cambiar dos letras de
    lugar ('Norcenter' -> 'Norcenetr'), y sin ella eso cuenta como dos
    errores y no lo agarra ningun umbral razonable.

    El corte no es por elegancia: sin el, comparar todos contra todos en una
    columna de cientos de valores se vuelve lento de verdad.
    """
    if abs(len(a) - len(b)) > tope:
        return tope + 1
    ant2, ant = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        fila = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            fila[j] = min(ant[j] + 1, fila[j - 1] + 1, ant[j - 1] + (ca != cb))
            if ant2 and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                fila[j] = min(fila[j], ant2[j - 2] + 1)
        if min(fila) > tope:
            return tope + 1
        ant2, ant = ant, fila
    return ant[len(b)]


# Cuantos valores se comparan entre si en el nivel de SOSPECHA. Es todos
# contra todos: con 80 son 3.160 comparaciones y ni se siente; sin tope, una
# columna con mil valores distintos son medio millon.
TOPE_SOSPECHA = 80


def _casi_igual(a, b):
    """True si `a` y `b` (ya normalizados) se parecen como para dudar.

    El umbral sube con el largo, y esa es toda la gracia: en 'ig anuncio' y
    'fb anuncio' dos letras de diferencia son dos etiquetas distintas; en
    'solo miraba precios no esta interesad' son un tipeo. Con un umbral fijo
    de 2 no hay forma de separar esos dos casos.
    """
    largo = max(len(a), len(b))
    if largo < 5:
        return False
    tope = 2 if largo >= 12 else 1
    if _distancia(a, b, tope) <= tope:
        return True
    corto, largo_s = (a, b) if len(a) < len(b) else (b, a)
    return largo_s in (corto + "s", corto + "es")     # singular y plural


def _mismos_valores(cuenta):
    """(grupos, filas). Los valores que SON el mismo, escrito de varias formas.

    `filas[i]` es cuantas filas junta el grupo `i`. Va calculado ACA y no
    despues: el que quiera contarlo mas tarde solo tiene `col["valores"]`, que
    viene cortado en los 25 mas frecuentes, y un valor partido que no entra en
    ese corte se queda sin numero — que es justo el que uno quiere ver para
    saber si vale la pena arreglarlo.
    """
    porBolsa = {}
    for v in cuenta:
        n = _norm(v)
        if not n:
            continue
        porBolsa.setdefault(_bolsa(n), []).append(v)
    grupos, filas = [], []
    for vs in porBolsa.values():
        if len(vs) < 2:
            continue
        # el mas cargado primero: es la forma que conviene dejar al unificar
        grupos.append(sorted(vs, key=lambda x: -cuenta[x]))
        filas.append(sum(cuenta[v] for v in vs))
    return grupos, filas


def _valores_sospechosos(cuenta, ciertos):
    """Pares que se parecen demasiado, sin ser el mismo valor.

    Lo que ya entro en `ciertos` no vuelve a salir acá: es una certeza y
    repetirla como duda hace que la duda no se lea.
    """
    ya = set(v for g in ciertos for v in g)
    vistos, reps = set(), []
    for v, _ in cuenta.most_common(TOPE_SOSPECHA):
        if v in ya:
            continue
        n = _norm(v)
        if n and n not in vistos:
            vistos.add(n)
            reps.append((n, v))
    salida = []
    for i in range(len(reps)):
        for j in range(i + 1, len(reps)):
            if _casi_igual(reps[i][0], reps[j][0]):
                salida.append([reps[i][1], reps[j][1]])
    return salida


def _agrupar_motivos(valores, minimo=2):
    """Junta las formas distintas de decir lo mismo.

    Agrupa por las DOS primeras palabras significativas. Dos coincidencias no
    pasan por casualidad; una sola si —y ese fue el error del primer intento,
    que metia "respondio" y "no respondio" en la misma bolsa.

    Lo que queda solo, queda solo: es preferible mostrar dos renglones que el
    usuario une con un click, antes que un numero que junta cosas distintas.
    """
    grupos = {}
    for v in valores:
        if not str(v).strip():
            continue
        cs = _claves_de(v)
        if not cs:
            clave = "(vacio)"
        elif len(cs) == 1:
            clave = cs[0]
        else:
            clave = cs[0] + " " + cs[1]
        g = grupos.setdefault(clave, {"clave": clave, "cuenta": 0, "formas": Counter()})
        g["cuenta"] += 1
        g["formas"][str(v).strip()] += 1

    salida = []
    for g in sorted(grupos.values(), key=lambda x: -x["cuenta"]):
        formas = g["formas"].most_common()
        salida.append({
            "etiqueta": formas[0][0],           # la forma mas usada, como nombre propuesto
            "clave": g["clave"],
            "cuenta": g["cuenta"],
            "formas": [f for f, _ in formas],   # todo lo que entro, para poder revisarlo
            "revisar": len(formas) > 1,         # si junto varias, que se pueda mirar
        })
    return salida


def _misma_escritura(s):
    """La clave para juntar el MISMO texto escrito de dos formas.

    Solo tildes, mayusculas y espacios. NO toca la puntuacion ni las palabras:
    la idea es juntar lo que es identico salvo como se tipeo, y nada mas.
    """
    t = unicodedata.normalize("NFKD", _txt(s).strip())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


def _contar_juntando(valores):
    """Cuenta los valores juntando los que son el mismo texto mal tipeado.

    Por que existe: en la planilla de derivaciones, «No respondio, se insistio
    3 veces» convive con «No respondió, se insistió 3 veces » (con tildes y un
    espacio al final). Contados aparte dan 2.106 y 984; son 3.090. Cualquier
    porcentaje calculado sobre el numero partido esta mal, y por casi la mitad.

    El reporte de derivaciones ya normalizaba (ver derivaciones.norm); el
    analisis generico no, y es sobre el generico que se arman las medidas que
    elige el usuario.

    ⚠️ Esto NO es lo mismo que `_mismos_valores`, que agrupa por palabras clave
    y puede juntar cosas parecidas pero distintas: ese sigue avisando sin unir,
    porque unir ahi si es una decision sobre el negocio. Aca se juntan dos
    escrituras del MISMO texto, que no es una decision de nadie.

    Devuelve (Counter con la forma mas usada como nombre, cuantos grupos se
    juntaron de verdad).
    """
    grupos = {}
    for v in valores:
        g = grupos.setdefault(_misma_escritura(v), {"formas": Counter(), "crudas": set()})
        g["formas"][_txt(v).strip()] += 1
        # las crudas incluyen los espacios: "SAN JUAN " y "SAN JUAN" son dos
        # escrituras aunque al recortarlas queden iguales, y contarlas como una
        # sola dejaba el aviso en cero cuando si se habia juntado algo
        g["crudas"].add(_txt(v))
    cuenta = Counter()
    juntados = 0
    for g in grupos.values():
        etiqueta, _ = g["formas"].most_common(1)[0]   # la forma mas usada da el nombre
        cuenta[etiqueta] = sum(g["formas"].values())
        if len(g["crudas"]) > 1:
            juntados += 1
    return cuenta, juntados


def analizar(filas, tope_valores=25):
    """filas[0] son los encabezados. Devuelve que tiene la planilla."""
    if not filas or len(filas) < 2:
        return {"error": "la planilla no tiene datos"}
    cab = [str(c).strip() for c in filas[0]]
    cuerpo = filas[1:]
    cols = []
    for i, nombre in enumerate(cab):
        if not nombre:
            continue
        crudos = [(f[i] if i < len(f) else "") for f in cuerpo]
        llenos = [v for v in crudos if str(v).strip()]
        tipo = _clasificar(nombre, llenos)
        col = {
            "i": i, "nombre": nombre, "tipo": tipo,
            "llenos": len(llenos), "vacios": len(crudos) - len(llenos),
            "distintos": len(set(llenos)),
            "sensible": tipo == "contacto",
        }
        if tipo == "categoria":
            # se juntan primero las dos escrituras del mismo texto (tildes,
            # mayusculas, espacios); recien despues se cuenta y se busca lo
            # parecido, que ya no va a incluir esos pares
            cuenta, juntados = _contar_juntando(llenos)
            col["distintos"] = len(cuenta)
            if juntados:
                col["escrituras_juntadas"] = juntados
            col["valores"] = [{"valor": v, "cuenta": c}
                              for v, c in cuenta.most_common(tope_valores)]
            # El mismo valor escrito de varias formas, y los que se le
            # parecen demasiado. Se AVISA, nunca se une solo: unir es una
            # decision sobre el negocio y no le toca al que lee la planilla.
            col["parecidos"], col["parecidos_filas"] = _mismos_valores(cuenta)
            col["sospechosos"] = _valores_sospechosos(cuenta, col["parecidos"])
        elif tipo == "motivo":
            col["grupos"] = _agrupar_motivos(llenos)
        elif tipo == "fecha":
            fs = [v for v in llenos if _es_fecha(v)]
            # ⚠️ Se ordenan como FECHAS y se guardan en ISO, no como vinieron.
            # Ordenarlas como texto daba un periodo falso (ver _a_fecha), y
            # devolverlas en el formato de la planilla obligaba a cada lector a
            # adivinar si "3/4/2026" es marzo o abril. En ISO se comparan y se
            # ordenan solas; el formato lindo lo pone quien las muestra.
            reales = sorted(x for x in (_a_fecha(v) for v in fs) if x)
            col["desde"] = reales[0].isoformat() if reales else ""
            col["hasta"] = reales[-1].isoformat() if reales else ""
        cols.append(col)
    return {"filas": len(cuerpo), "columnas": cols}


def leer_csv(ruta):
    with io.open(ruta, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.reader(f)]


if __name__ == "__main__":
    import sys, os
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "derivaciones_prueba.csv")
    r = analizar(leer_csv(ruta))
    print("PLANILLA: %d filas, %d columnas\n" % (r["filas"], len(r["columnas"])))
    for c in r["columnas"]:
        marca = "  [SENSIBLE — no se publica]" if c["sensible"] else ""
        print("%-16s %-10s %d distintos, %d vacios%s"
              % (c["nombre"], c["tipo"].upper(), c["distintos"], c["vacios"], marca))
        if c.get("valores"):
            for v in c["valores"][:5]:
                print("       %-28s %d" % (v["valor"][:28], v["cuenta"]))
        if c.get("grupos"):
            for g in c["grupos"][:6]:
                print("       %-34s %4d   (%d formas)"
                      % (g["etiqueta"][:34], g["cuenta"], len(g["formas"])))
        if c.get("desde"):
            print("       de %s a %s" % (c["desde"], c["hasta"]))
