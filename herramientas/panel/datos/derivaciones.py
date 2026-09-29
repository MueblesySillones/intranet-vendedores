# -*- coding: utf-8 -*-
"""Lo que el panel sabe sobre la planilla de derivaciones.

POR QUÉ HAY UN MÓDULO SOLO PARA ESTO
  El resto de `datos/` es genérico: le das cualquier planilla y te dice qué
  columnas tiene. Eso alcanza para un tablero, pero no para un reporte. Un
  reporte necesita saber que «derivación» significa que hay un vendedor
  asignado, que la venta está escondida adentro de una respuesta de texto, y
  que la columna «Sucursal» no sirve para contar sucursales.

  Nada de eso se puede deducir de los datos: lo explicó el equipo. Este módulo
  es donde vive esa explicación, escrita una vez, en vez de repartida en
  comentarios por todos lados.

LAS REGLAS, TAL COMO LAS DIO EL EQUIPO
  · Consulta      = una fila.
  · Derivación    = la columna Vendedor NO está vacía. Es el número de
                    marketing: su trabajo es lograr que la consulta llegue a un
                    vendedor. La venta la cierra el vendedor.
  · Venta         = Respuesta Final dice «Realizó la compra». Vale igual para
                    derivadas y no derivadas.
  · Sucursal      = PRIMERO lo que dice la fila, y si no, el mapa del vendedor.
                    La columna «Sucursal» sigue mezclando locales con la
                    provincia del cliente (Santa Fe, Córdoba, Río Negro…), así
                    que NO se usa cruda: solo cuando dice uno de los locales
                    (ver LOCALES). Cuando lo dice, vale más que el mapa, porque
                    es lo que pasó en ESA fila —una vendedora puede estar hoy en
                    un local y mañana en otro, y una que ya no trabaja más
                    conserva sus derivaciones donde estuvo—. El mapa queda de
                    respaldo para las filas que traen una provincia o nada.
                    Medido sobre la planilla real: con el mapa solo quedaban 102
                    derivaciones sin ubicar; combinando fila + mapa, 5.
  · Seguimiento_1 y Seguimiento_2 son el PROCESO, no el resultado. Que diga
                    «el vendedor está en contacto» no es un desenlace.
  · Respuesta Final es el desenlace. Vacía NO significa «sin resultado»:
                    significa «todavía en proceso», casi siempre porque el
                    cliente postergó y el seguimiento quedó en Seguimiento_2.
  · Vacío ≠ error. Tarjeta está vacía en el 98% porque el cliente no la
                    menciona; Producto, porque no dijo qué buscaba. Eso es un
                    dato, no un problema de carga.

EL MAPA DE VENDEDORES SE MANTIENE SOLO
  Entran vendedores y sucursales todo el tiempo (Pilar ya está, North Delta
  viene). Un mapa escrito a mano nace vencido: en la planilla de agosto había 5
  nombres que el mapa viejo no conocía, y sus 69 derivaciones desaparecían del
  corte por sucursal sin que nadie se enterara. Por eso acá el mapa se guarda,
  y los nombres que no están se DEVUELVEN para que el panel pregunte, en vez de
  descartarlos callado.
"""
import datetime
import json
import os
import re
import unicodedata

# El mapa arranca con lo que ya se sabía en junio de 2026. No es la verdad
# eterna: es el punto de partida, y el panel lo va completando preguntando.
MAPA_INICIAL = {
    "Hudson": ["Walter", "Gonzalo", "Rosana", "Dora", "Agustina", "Adriana", "Joan"],
    "CABA": ["Viviana", "Alexa", "Matias", "Marcelo"],
    "Norcenter": ["Flor", "Mario"],
    "Canning": ["Tomas", "Malena", "Andrea", "Maria Marta"],
}

ARCHIVO_MAPA = "vendedores.json"

# ────────────────────────── LOS LOCALES ──────────────────────────
# La columna «Sucursal» de la planilla NO es solo la sucursal: mezcla los
# locales con la provincia o la localidad del cliente (SANTA FE, MAR DEL PLATA,
# TIERRA DEL FUEGO…). Medido sobre 9.170 filas: cinco valores son locales y los
# otros treinta y seis son lugares. Por eso la columna no se puede usar cruda,
# pero SÍ cuando dice uno de estos.
#
# Vale más que el mapa vendedor→sucursal, porque es lo que pasó EN ESA FILA:
# una vendedora puede estar un día en un local y otro día en otro, y una que ya
# no trabaja más sigue teniendo sus derivaciones con la sucursal donde estuvo.
# Con el mapa solo quedaban 102 derivaciones sin ubicar (Lourdes, Carolina,
# Yesica, Pamela, Mauricio); combinando fila + mapa quedan 5.
LOCALES = {
    "CABA": "CABA",
    "HUDSON": "Hudson",
    "NORCENTER": "Norcenter",
    "CANNING": "Canning",
    "PILAR": "Pilar",
}


from . import zonas

# Como se llama, en el cruce producto x origen, la consulta que no tiene el
# origen cargado. Esta escrito una sola vez porque la lamina lo compara: si
# aca dijera una cosa y alla otra, el cruce dejaria de marcarlas sin avisar.
SIN_ORIGEN = "(sin origen)"

def local_de_fila(valor):
    """El local que dice la fila, o '' si lo que dice es una provincia."""
    return LOCALES.get(norm(valor), "")

# Los textos que marcan cada cosa. Se comparan sin acentos y en mayúsculas
# porque la planilla los tiene escritos de las dos formas — «Realizo» y
# «Realizó», «insistio» e «insistió»— y son lo mismo.
VENTA = "REALIZO LA COMPRA"
PRECIO = "TIENE EL PRECIO"
TEMPLATE = "SE LE ENVIO TEMPLATE"
NO_RESPONDIO = "NO RESPONDIO"

# ─────────────── CÓMO SE COMPORTÓ CADA CLIENTE (27-sep-2026) ───────────────
# Pedido del usuario: «no digo que mostremos cada paso, sino una evaluación de
# patrones de las personas, de sus reacciones». Se leen JUNTOS Seguimiento_1,
# Seguimiento_2 y Respuesta Final, y cada cliente cae en UN patrón.
# Las reglas son del negocio, dictadas por el usuario:
#   · «Tiene el precio, lo analiza» cuenta como que recibió el precio.
#   · Fuera de presupuesto: siempre se le ofrecieron otras opciones, y aun así.
#   · Si dijo «fuera de presupuesto», se le mandó la plantilla y no respondió
#     más, es fuera de presupuesto («es como casi cerrado»), no «nunca respondió».
#   · Si el seguimiento está incompleto igual cae en algún patrón: se usa lo
#     que haya.
PATRONES = [
    ("precio_silencio", "Recibió el precio y dejó de responder",
     "Tuvo el precio o la información completa, y después no contestó más"),
    ("nunca", "Nunca respondió",
     "No contestó en ningún momento, aunque se le insistió"),
    ("nunca_plantilla", "Nunca respondió, ni a la plantilla",
     "Tampoco contestó cuando se le mandó la plantilla de seguimiento"),
    ("prometio", "Prometió pasar y no volvió a responder",
     "Quedó en pasar o coordinó una visita, y después desapareció"),
    ("presupuesto_ya", "Fuera de presupuesto de entrada",
     "Lo dijo de entrada; se le ofrecieron otras opciones y aun así"),
    ("presupuesto_luego", "Lo analizó y quedó fuera de presupuesto",
     "Recibió la información, se le ofrecieron otras opciones y aun así"),
    ("solo_miraba", "Solo miraba precios", "No estaba interesado en comprar"),
    ("otro_lugar", "Compró en otro lugar", "Por precio, por comodidad u otro motivo"),
    ("sin_producto", "No teníamos el producto", "Buscaba algo que no hay"),
    ("postergo", "Lo postergó", "Dijo que más adelante"),
    ("otro_motivo", "Otro motivo", "Le queda lejos, el envío, cuestiones personales"),
    ("compro_prometio", "Compró después de prometer pasar",
     "Quedó en pasar y cumplió"),
    ("compro", "Compró", "Cerró la venta"),
    ("proceso", "Todavía en proceso",
     "Tiene seguimiento pero la respuesta final está vacía"),
]
NOMBRE_PATRON = {k: n for k, n, _ in PATRONES}


def _senal(v):
    """Qué dice una celda de seguimiento, reducido a una señal."""
    t = norm(v)
    if not t:
        return None
    if "TEMPLATE" in t:
        return "TEMPLATE"
    if VENTA in t:
        return "COMPRA"
    if "COMPRO EN OTRO" in t:
        return "OTRO_LUGAR"
    if "PRESUPUESTO" in t and "FUERA" in t:
        return "PRESUPUESTO"
    if "QUEDO EN PASAR Y NO VINO" in t or "COORDINO VISITA PERO NO" in t:
        return "NO_VINO"
    if "QUEDO EN PASAR" in t or "REALIZARA UN VIAJE" in t or "COORDINO VISITA" in t:
        return "PROMETIO"
    if "DESPUES DEL PRECIO" in t or "NOS DEJO EN VISTO" in t:
        return "PRECIO"
    if ("LO ANALIZA" in t or "EVALUA" in t or "DEFINIENDO" in t or "COTIZACION" in t
            or "VIO PRECIOS" in t or PRECIO in t):
        return "PRECIO"
    if "SOLO MIRABA" in t:
        return "SOLO_MIRABA"
    if "NO TENEMOS EL PRODUCTO" in t:
        return "SIN_PRODUCTO"
    if "POSTERGO" in t or "MAS ADELANTE" in t or "POR EL MOMENTO NO" in t:
        return "POSTERGO"
    if ("LEJOS" in t or "EL ENVIO" in t or "EXTERNAS" in t or "PERSONALES" in t
            or "ENCARECIO" in t):
        return "OTRO_MOTIVO"
    if "ESPERANDO RESPUESTA" in t:
        return "SILENCIO"
    if NO_RESPONDIO in t or "SE INSISTI" in t or "CAMBIO DE LINEA" in t:
        return "SILENCIO"
    return "CONTACTO"                   # seguimiento de redes, el vendedor escribió…


def patron_de(s1, s2, final):
    """La clave del patrón de un cliente, o None si no tiene ningún dato."""
    a, b, f = _senal(s1), _senal(s2), _senal(final)
    antes = [x for x in (a, b) if x]
    if f is None and not antes:
        return None
    prometio = "PROMETIO" in antes or "NO_VINO" in antes
    presupuesto = "PRESUPUESTO" in antes
    if f == "COMPRA":
        return "compro_prometio" if prometio else "compro"
    # dijo presupuesto y después se calló (o no hay final): casi cerrado
    if f == "PRESUPUESTO" or (presupuesto and f in (None, "SILENCIO", "TEMPLATE", "CONTACTO")):
        return "presupuesto_ya" if a == "PRESUPUESTO" else "presupuesto_luego"
    if f is None:
        return "proceso"
    if f in ("SILENCIO", "NO_VINO", "TEMPLATE", "CONTACTO", "PRECIO", "PROMETIO"):
        if prometio or f in ("NO_VINO", "PROMETIO"):
            return "prometio"
        if "PRECIO" in antes or f == "PRECIO":
            return "precio_silencio"
        if "TEMPLATE" in antes or f == "TEMPLATE":
            return "nunca_plantilla"
        return "nunca"
    return {"OTRO_LUGAR": "otro_lugar", "SOLO_MIRABA": "solo_miraba",
            "SIN_PRODUCTO": "sin_producto", "POSTERGO": "postergo",
            "OTRO_MOTIVO": "otro_motivo"}.get(f, "otro_motivo")


# ─────────────── POR QUÉ ANUNCIO LLEGARON (27-sep-2026) ───────────────
# La columna Origen mezcla anuncios con otras puertas de entrada. Regla del
# usuario: «web es porque vienen desde la página; mailing, del mailing; el
# resto, como promo de envío o streaming session, son anuncios». Entonces:
# lo que NO está en esta lista es un ANUNCIO, y un anuncio nuevo entra solo.
#   · «Web Promo» es la sección de promos bancarias de la página → Web.
#   · «Campaña MKT Respuesta» no es un anuncio: es una acción de marketing.
#   · Influencers, Catálogo, QR Dolores: propuesta sin confirmar todavía
#     (27-sep); si el usuario dice otra cosa, se cambia acá y nada más.
GRUPOS_ORIGEN = [
    ("anuncio", "Anuncios"),
    ("web", "Web"),
    ("mailing", "Mailing"),
    ("organico", "Redes sin pauta"),
    ("influencer", "Influencers"),
    ("sucursal", "Sucursal o vidriera"),
    ("telefono", "Teléfono"),
    ("accion", "Acción de marketing"),
    ("otros", "Otros medios"),
]
_NO_ANUNCIO = {
    "WEB": "web", "WEB PROMO": "web",
    "MAILING": "mailing",
    "IG ORGANICO": "organico", "IG HISTORIAS": "organico", "HISTORIAS IG": "organico",
    "IG REEL": "organico", "TIK TOK": "organico", "TIKTOK": "organico",
    "CAMI GALANTE": "influencer", "CAMI HOMS": "influencer",
    "SUC. POLO": "sucursal", "SUC.CANNING": "sucursal", "SUC. CANNING": "sucursal",
    "SUC. QUILMES VIDRIERA": "sucursal", "SUC. DOLORES": "sucursal",
    "QR DOLORES": "sucursal", "ATENCION AL PUBLICO": "sucursal",
    "VENTA TELEFONICA": "telefono", "LLAMADA WSP": "telefono",
    "CAMPANA MKT RESPUESTA": "accion",
    "OTROS MEDIOS": "otros", "CATALOGO": "otros",
}


def grupo_de_origen(valor):
    """El grupo de un valor de Origen, o None si está vacío."""
    t = norm(valor)
    if not t:
        return None
    if t in _NO_ANUNCIO:
        return _NO_ANUNCIO[t]
    if t.startswith("SUC.") or t.startswith("SUC "):
        return "sucursal"
    return "anuncio"


def monto_de(valor):
    """«$59.262.016» → 59262016. Cero si la celda no es un monto."""
    t = "".join(c for c in str(valor or "") if c.isdigit() or c in ",.")
    if not t:
        return 0
    # los miles van con punto; si hay coma, lo de después son centavos
    t = t.split(",")[0].replace(".", "")
    try:
        return int(t)
    except ValueError:
        return 0


# Las columnas que tienen que estar para que esto sea la planilla de
# derivaciones y no otra cosa.
COLUMNAS_CLAVE = ("fecha", "vendedor", "respuesta final")


def norm(t):
    """Sin acentos, en mayúsculas, con los espacios apretados.

    Es lo que permite que «Realizó la compra», «Realizo la compra» y
    «REALIZO  LA COMPRA» cuenten como el mismo valor. Sin esto, el motivo de
    pérdida más común de la empresa aparece partido en dos barras distintas por
    una tilde, y la más grande no es la real."""
    t = unicodedata.normalize("NFKD", (t or "").strip().upper())
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).split())


def es_derivaciones(an):
    """¿Esta planilla es la de derivaciones?

    Se mira por nombre de columna y no por contenido: el equipo puede cambiar
    los valores de las listas cuando quiera, pero si están Fecha, Vendedor y
    Respuesta Final, es esta planilla."""
    nombres = {norm(c.get("nombre")) for c in (an or {}).get("columnas") or []}
    return all(norm(c) in nombres for c in COLUMNAS_CLAVE)


# =====================================================================
#  El mapa de vendedores
# =====================================================================
def _ruta_mapa(state_dir):
    return os.path.join(state_dir or "", ARCHIVO_MAPA)


def mapa_leer(state_dir):
    """{VENDEDOR_NORMALIZADO: sucursal}. Si no hay archivo, el inicial."""
    ruta = _ruta_mapa(state_dir)
    guardado = {}
    if os.path.isfile(ruta):
        try:
            guardado = json.load(open(ruta, encoding="utf-8-sig")) or {}
        except (ValueError, OSError):
            guardado = {}                  # ilegible = como si no estuviera
    mapa = {}
    for suc, gente in MAPA_INICIAL.items():
        for p in gente:
            mapa[norm(p)] = suc
    # lo guardado pisa al inicial: si alguien corrigió una asignación, manda
    for nombre, suc in guardado.items():
        if isinstance(suc, str) and suc.strip():
            mapa[norm(nombre)] = suc.strip()
    return mapa


def mapa_guardar(state_dir, asignaciones):
    """Suma o corrige asignaciones. No pisa las que no vienen."""
    ruta = _ruta_mapa(state_dir)
    actual = {}
    if os.path.isfile(ruta):
        try:
            actual = json.load(open(ruta, encoding="utf-8-sig")) or {}
        except (ValueError, OSError):
            actual = {}
    for nombre, suc in (asignaciones or {}).items():
        n = norm(nombre)
        if not n:
            continue
        if suc and str(suc).strip():
            actual[n] = str(suc).strip()
        else:
            actual.pop(n, None)            # sucursal vacía = olvidar el nombre
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(actual, f, ensure_ascii=False, indent=1, sort_keys=True)
    return actual


def sucursales_conocidas(state_dir):
    """Las sucursales que el mapa ya usa, para ofrecerlas en una lista."""
    return sorted(set(mapa_leer(state_dir).values()))


# =====================================================================
#  Qué vacíos son normales en esta planilla
# =====================================================================
# El revisor generico avisa cuando una columna esta muy vacia, y hace bien: en
# una planilla cualquiera, una columna vacia al 97% suele ser un error de carga.
#
# En ESTA planilla, no. El equipo explico por que esta vacia cada una, y son
# todas razones validas. Sin esta lista, el panel abre gritando cuatro avisos
# "graves" de los cuales tres son el funcionamiento normal — y cuando todo es
# grave, nada lo es: se dejan de leer, incluidos los que si importan.
VACIO_ESPERADO = {
    "TARJETA": "El cliente solo la menciona a veces. Que este vacia es lo normal.",
    "PRODUCTO": "Se llena cuando el cliente dice que busca. Vacio = no lo dijo.",
    "EMAIL": "Ya casi no se cargan mails; la columna se va a reusar para otra cosa.",
    "VENDEDOR": "Vacio significa que la consulta NO se derivo. Es el dato, no un error.",
    "SUCURSAL": "Solo se carga cuando hay derivacion, y algo mas de la mitad no se deriva.",
    "LOCALIDAD": "Se completa cuando el cliente dice de donde es.",
    "SEGUIMIENTO_1": "Se llena a medida que avanza el seguimiento.",
    "SEGUIMIENTO_2": "Solo llega aca lo que necesito un segundo contacto.",
    "RESPUESTA FINAL": "Vacia = todavia en proceso, no 'sin resultado'.",
    "DESCRIPCION": "Campo libre, se usa solo cuando hace falta.",
    "NP": "Campo suelto, casi no se usa.",
}


def por_que_vacia(columna):
    """La razon por la que esa columna esta vacia, si es una razon esperable."""
    return VACIO_ESPERADO.get(norm(columna), "")


def acomodar_avisos(avisos, an):
    """Baja de grave a dato los avisos que en ESTA planilla no son problemas, y
    sube los que si lo son.

    Devuelve la misma lista, con `gravedad` y `detalle` retocados. No borra
    nada: un aviso que se esconde es un aviso que nadie puede discutir. Se
    reordena y se explica.

    ⚠️ Solo se aplica si la planilla ES la de derivaciones. En cualquier otra,
    el criterio generico manda."""
    if not es_derivaciones(an):
        return avisos
    for a in avisos:
        titulo = a.get("titulo") or ""
        # "Email esta vacia en 6933 filas (97%)" -> la columna es lo de adelante.
        # ⚠️ La comparacion va en MAYUSCULAS: norm() devuelve mayusculas, asi que
        # buscar "vacia" en minuscula no coincide nunca. Ese era el bug que dejaba
        # los tres falsos "graves" en pantalla igual.
        t = norm(titulo)
        if " VACIA" in t or t.startswith("VACIA"):
            col = t.split(" ESTA")[0].strip()
            razon = por_que_vacia(col)
            if razon:
                a["gravedad"] = "dato"
                a["esperado"] = True
                a["detalle"] = razon + " " + (a.get("detalle") or "")
        # Los valores escritos de dos formas parten un numero en dos. Pero no
        # todos pesan igual: uno puede estar partiendo 2.983 filas —el motivo
        # de perdida mas comun de la empresa, cortado por una tilde— y otro
        # juntar dos casos sueltos. Sin el numero al lado, los 24 avisos se ven
        # iguales y no se puede saber cual atender.
        # ⚠️ Por `clase` primero y por el titulo solo como respaldo. Buscar
        # texto adentro del titulo ya fallo una vez: al reescribir el aviso
        # dejo de coincidir y el recuento de filas desaparecio sin que nada
        # se rompiera a la vista.
        clase = a.get("clase") or ""
        if (clase in ("valor_duplicado", "valor_sospechoso")
                or "MISMA COSA" in t or "PARECID" in t):
            # Si el aviso ya trae el recuento, ese manda: lo calculo el
            # analizador sobre TODOS los valores de la columna, mientras que
            # _filas_de solo puede mirar los 25 mas frecuentes y devuelve 0
            # para un valor partido que no entre en ese corte.
            cuantas = a.get("filas_afectadas") or _filas_de(
                a.get("ejemplos") or [], titulo, an)
            if cuantas:
                a["filas_afectadas"] = cuantas
                a["detalle"] = ("Juntas son %s filas. %s"
                                % (_miles(cuantas), a.get("detalle") or ""))
            # Grave solo si mueve la aguja. Marcar los 24 como graves es el
            # mismo error que gritar por una columna vacia: cuando todo es
            # grave, se dejan de leer todos.
            # ⚠️ Y una SOSPECHA no llega a grave por muchas filas que toque:
            # todavia no se sabe si es un problema. Subirla de nivel por peso
            # seria darle a una duda la cara de una certeza.
            if cuantas >= 100 and clase != "valor_sospechoso":
                a["gravedad"] = "grave"
                a["prioridad"] = True
            elif a.get("gravedad") == "grave":
                a["gravedad"] = "aviso"
    orden = {"grave": 0, "aviso": 1, "dato": 2}
    avisos.sort(key=lambda a: (orden.get(a.get("gravedad"), 3),
                               -(a.get("filas_afectadas") or 0)))
    return avisos


def _miles(n):
    try:
        return "{:,}".format(int(n)).replace(",", ".")
    except (TypeError, ValueError):
        return str(n or "")


def _filas_de(ejemplos, titulo, an):
    """Cuantas filas suman los valores que el aviso senala como parecidos.

    El aviso trae los dos textos pero no cuanto pesan; el conteo esta en el
    analisis, columna por columna. Se busca ahi."""
    if not ejemplos:
        return 0
    col = norm(titulo.split(":")[0])
    for c in (an or {}).get("columnas") or []:
        if norm(c.get("nombre")) != col:
            continue
        # ⚠️ Se ACUMULA, no se pisa. Cuando los dos valores parecidos difieren
        # solo por una tilde o un espacio —que es el caso mas comun y el mas
        # importante— norm() los manda a la misma clave, y asignar en vez de
        # sumar dejaba afuera al otro. Justo el que hay que contar.
        cuenta = {}
        for v in (c.get("valores") or []):
            k = norm(v.get("valor"))
            cuenta[k] = cuenta.get(k, 0) + (v.get("cuenta") or 0)
        for g in (c.get("grupos") or []):
            k = norm(g.get("etiqueta"))
            cuenta[k] = cuenta.get(k, 0) + (g.get("cuenta") or 0)
        # y las claves se cuentan UNA vez: si los dos ejemplos normalizan igual,
        # su cuenta ya esta sumada arriba y volver a sumarla la duplicaria
        claves = []
        for x in ejemplos:
            k = norm(x)
            if k not in claves:
                claves.append(k)
        return sum(cuenta.get(k, 0) for k in claves)
    return 0


# =====================================================================
#  Leer una fecha de la planilla
# =====================================================================
_RE_FECHA = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$")


def _fecha(t):
    """date o None. La planilla usa d/m/aaaa, que es como se escribe acá.

    ⚠️ No se ordenan las fechas como texto. «15/01/2026» es menor que
    «1/02/2026» alfabéticamente, así que un mínimo sacado del texto puede
    devolver una fecha que no es la primera."""
    m = _RE_FECHA.match(t or "")
    if not m:
        return None
    d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if a < 100:
        a += 2000
    try:
        return datetime.date(a, mes, d)
    except ValueError:
        return None


# =====================================================================
#  ¿La diferencia es real o es azar?
# =====================================================================
def es_real(exitos, intentos, tasa):
    """(bool, 'arriba'|'abajo'|'', 1_en_cuantos).

    ⚠️ ESTO EXISTE PARA NO PUBLICAR RANKINGS DE SUERTE.
    Con una tasa de cierre del 3% y 200 derivaciones, la diferencia entre 3
    ventas y 10 es azar. Un tablero que ordena vendedores por conversión le
    dice «sos el peor» a alguien que no hizo nada mal, y lo hace con la
    autoridad de un número. Antes de mostrar una diferencia como si fuera
    mérito o culpa, hay que preguntarse si el azar la explica.

    Se usa la cola de una Poisson, que es la aproximación correcta cuando los
    éxitos son pocos y los intentos muchos — que es exactamente este caso."""
    import math
    n, k = int(intentos or 0), int(exitos or 0)
    lam = n * float(tasa or 0)
    if n <= 0 or lam <= 0:
        return False, "", 0

    def acumulada(hasta):
        s, t = 0.0, math.exp(-lam)
        for i in range(0, hasta + 1):
            s += t
            t *= lam / (i + 1)
        return min(1.0, s)

    if k <= lam:
        p, lado = acumulada(k), "abajo"
    else:
        p, lado = 1.0 - acumulada(k - 1), "arriba"
    if p < 0.05:
        return True, lado, int(round(1.0 / max(p, 1e-12)))
    return False, "", 0


# =====================================================================
#  El análisis
# =====================================================================
def analizar(filas, state_dir, hoy=None, desde_f=None, hasta_f=None,
             sucursal_f=None):
    """Todo lo que el reporte de derivaciones necesita, ya calculado.

    `filas` viene del lector: filas[0] son los encabezados.

    EL PERIODO (desde_f / hasta_f, dos `date` o None)
      Sin ellos se mira toda la planilla, que es lo de siempre. Con ellos, el
      reporte es de ESE tramo: agosto, la semana pasada, lo que se pida. Es lo
      que permite tener varios reportes colgando de una misma planilla en vez
      de uno solo que siempre dice lo mismo.

      ⚠️ Las filas SIN FECHA quedan afuera de un reporte con período, y no es
      un descuido: no se puede afirmar que una consulta sin fecha haya pasado
      en agosto. Se cuentan aparte (`sin_fecha_fuera`) para poder decirlo, en
      vez de que el total no cierre y nadie sepa por que. En la planilla real
      son 1.744 de 9.170, o sea uno de cada cinco: callarlo seria mentir por
      omision.
    """
    if not filas or len(filas) < 2:
        return {"ok": False, "error": "La planilla no tiene datos."}

    cab = [norm(c) for c in filas[0]]

    def col(*nombres):
        for n in nombres:
            if norm(n) in cab:
                return cab.index(norm(n))
        return -1

    iF, iV = col("Fecha"), col("Vendedor")
    iRF = col("Respuesta Final")
    iS1, iS2 = col("Seguimiento_1", "Seguimiento 1"), col("Seguimiento_2", "Seguimiento 2")
    iME, iOR = col("Medio de entrada"), col("Origen")
    iPR = col("Producto")
    iSU = col("Sucursal")
    iLO = col("Localidad")
    iMO = col("Monto")
    if min(iF, iV, iRF) < 0:
        return {"ok": False,
                "error": "Faltan columnas: hacen falta Fecha, Vendedor y Respuesta Final."}

    mapa = mapa_leer(state_dir)
    hoy = hoy or datetime.date.today()

    tot = {"consultas": 0, "derivaciones": 0, "ventas": 0,
           # las que atendió OTRO local; solo se llena con el corte puesto
           "de_otra_sucursal": 0,
           "precio": 0, "fantasma": 0, "template": 0, "sin_fecha": 0}
    # El corte por sucursal. ⚠️ NO recorta las filas: una consulta sin
    # vendedor no es de ninguna sucursal, así que sacarla del total diría que
    # en el período entraron menos consultas de las que entraron. Lo que hace
    # es no contar como DERIVACIÓN la que atendió otro local.
    # 27-sep-2026: se puede pedir VARIAS sucursales (una lista). Una sola
    # sigue viniendo como texto.
    if isinstance(sucursal_f, (list, tuple)):
        _focos = [str(x).strip() for x in sucursal_f if str(x).strip()]
    else:
        _focos = [sucursal_f] if sucursal_f else []
    suc_f = set(norm(x) for x in _focos)
    foco_txt = (" y ".join([", ".join(_focos[:-1]), _focos[-1]])
                if len(_focos) > 1 else (_focos[0] if _focos else ""))
    # cómo se comportó cada cliente (ver PATRONES)
    patrones = {}
    # lo recaudado: UN monto por mes, anotado en una fila de ese mes (el
    # usuario, 27-sep: «es un monto recaudado mensual»). Es de toda la
    # empresa: la planilla no dice de qué sucursal es cada parte.
    montos = {}
    # De qué LUGAR llegan, tal cual dice la columna Localidad (27-sep-2026:
    # «cuántas consultas llegaron de Neuquén… de La Plata»). `grupo` separa
    # otras provincias de Buenos Aires, que se pueden mostrar juntas o aparte.
    lugares = {}
    # por qué puerta entraron (anuncio, web, mailing…) y cada anuncio
    grupos_origen, anuncios = {}, {}

    def cuenta_origen(valor):
        g = grupo_de_origen(valor)
        if not g:
            return None, None
        b = grupos_origen.setdefault(g, {"consultas": 0, "derivaciones": 0, "ventas": 0})
        a = None
        if g == "anuncio":
            k = norm(valor)
            a = anuncios.setdefault(k, {"nombre": str(valor).strip(), "consultas": 0,
                                        "derivaciones": 0, "ventas": 0})
        return b, a

    def lugar(valor):
        k = norm(valor)
        if not k:
            return None
        if k not in lugares:
            prov = zonas.provincia_del_lugar(valor)
            nombre = (zonas.provincia_de(valor) or str(valor).strip().rstrip(".")
                      if prov else str(valor).strip().rstrip("."))
            lugares[k] = {"nombre": nombre, "provincia": prov or "",
                          "grupo": "provincias" if prov else "buenos_aires",
                          "consultas": 0, "derivaciones": 0, "ventas": 0}
        return lugares[k]
    por_vend, por_mes, por_suc = {}, {}, {}
    motivos, medios, origenes, productos = {}, {}, {}, {}
    # De donde viene la clientela. `zonas` cuenta el total; `zonas_prov` dice
    # de que provincia son las del interior; y cada vendedor lleva su propio
    # reparto, porque «de su zona» se mide contra SU sucursal.
    zonas_tot = {k: {"derivaciones": 0, "ventas": 0} for k, _ in zonas.CATEGORIAS}
    zonas_prov, zonas_sin = {}, 0
    # El ritmo: que dias entran las consultas y cuantas por dia. `dias_semana`
    # guarda consultas Y derivaciones porque lo interesante no es el volumen
    # sino la DIFERENCIA: el sabado entra casi como un dia de semana y se
    # deriva la mitad.
    dias_semana = {i: {"consultas": 0, "derivaciones": 0} for i in range(7)}
    por_fecha = {}
    # De que origen viene cada producto, y cuantas filas no tienen origen
    prod_origen, sin_origen = {}, 0
    sin_ubicar = {}
    desde = hasta = None

    def bolsa(d, k):
        return d.setdefault(k, {"consultas": 0, "derivaciones": 0, "ventas": 0,
                                "precio": 0, "fantasma": 0, "template": 0})

    recorta = bool(desde_f or hasta_f)
    fuera, sin_fecha_fuera = 0, 0

    for f in filas[1:]:
        if not any(str(c).strip() for c in f):
            continue
        def celda(i):
            return f[i] if 0 <= i < len(f) else ""

        fecha = _fecha(celda(iF))
        # ⚠️ Una fecha del futuro es un error de tipeo, no un dato. Sin este
        # freno, un 2027 mal cargado corre el período de todo el reporte.
        if fecha and fecha > hoy:
            fecha = None

        # el recorte va ANTES de contar: si no, los totales incluirían filas
        # que el reporte dice no estar mirando
        if recorta:
            if not fecha:
                sin_fecha_fuera += 1
                continue
            if (desde_f and fecha < desde_f) or (hasta_f and fecha > hasta_f):
                fuera += 1
                continue

        tot["consultas"] += 1
        if fecha:
            desde = fecha if not desde else min(desde, fecha)
            hasta = fecha if not hasta else max(hasta, fecha)
        else:
            tot["sin_fecha"] += 1

        vend = norm(celda(iV))
        rf = norm(celda(iRF))
        s1, s2 = norm(celda(iS1)), norm(celda(iS2))
        venta = rf.startswith(VENTA)
        con_precio = PRECIO in s1 or PRECIO in s2
        con_tpl = TEMPLATE in s1 or TEMPLATE in s2
        # «fantasma»: le mandaron el precio y no contestó más. Cuenta también
        # el que quedó sin respuesta final, porque ese TAMPOCO contestó.
        fantasma = con_precio and not venta and (rf.startswith(NO_RESPONDIO) or not rf)

        # El ritmo. Va acá porque ya está la fecha parseada y ya se sabe si la
        # fila tiene vendedor: contar el día en otro lado obligaría a recorrer
        # la planilla dos veces.
        if fecha:
            ds = dias_semana[fecha.weekday()]
            ds["consultas"] += 1
            if vend:
                ds["derivaciones"] += 1
            pf = por_fecha.setdefault(fecha, {"consultas": 0, "derivaciones": 0})
            pf["consultas"] += 1
            if vend:
                pf["derivaciones"] += 1

        # De qué origen viene cada producto. Es el cruce que se pidió:
        # «¿de qué origen vienen más las consultas de sillones?».
        _pr = celda(iPR).strip() if iPR >= 0 else ""
        _or = celda(iOR).strip() if iOR >= 0 else ""
        if not _or:
            sin_origen += 1
        if _pr:
            po = prod_origen.setdefault(_pr, {})
            k = _or or SIN_ORIGEN
            po[k] = po.get(k, 0) + 1

        clave_mes = fecha.strftime("%Y-%m") if fecha else ""
        if clave_mes and iMO >= 0:
            _m = monto_de(celda(iMO))
            if _m:
                montos[clave_mes] = montos.get(clave_mes, 0) + _m
        pat = patron_de(celda(iS1), celda(iS2), celda(iRF))
        # la consulta cuenta en su lugar SIN corte; con corte, una consulta
        # sin derivar no es de ninguna sucursal (se cuenta más abajo)
        lg = lugar(celda(iLO)) if iLO >= 0 else None
        if lg and not suc_f:
            lg["consultas"] += 1
        og, an_ = cuenta_origen(celda(iOR)) if iOR >= 0 else (None, None)
        if og and not suc_f:
            og["consultas"] += 1
            if an_:
                an_["consultas"] += 1
        # sin corte, el patrón es de toda la empresa; con corte, se cuenta
        # más abajo, cuando ya se sabe que la derivación es de ese local
        if pat and not suc_f:
            patrones[pat] = patrones.get(pat, 0) + 1
        if clave_mes:
            m = bolsa(por_mes, clave_mes)
            m["consultas"] += 1
            if vend:
                m["derivaciones"] += 1
            if venta:
                m["ventas"] += 1

        # ⚠️ Con el corte por sucursal, la venta se cuenta MAS ABAJO, después
        # de saber de qué local fue. Acá arriba vale «una venta es una venta,
        # la haya derivado alguien o no», que es lo correcto para toda la
        # empresa; en el reporte de Hudson, la venta de CABA no es de Hudson.
        if venta and not suc_f:
            tot["ventas"] += 1
        if con_precio:
            tot["precio"] += 1
        if fantasma:
            tot["fantasma"] += 1
        if con_tpl:
            tot["template"] += 1

        if rf:
            motivos[rf] = motivos.get(rf, 0) + 1
        for i, d in ((iME, medios), (iOR, origenes), (iPR, productos)):
            v = norm(celda(i))
            if v:
                d[v] = d.get(v, 0) + 1

        if not vend:
            continue                       # no derivada: ya se contó arriba

        # ⚠️ La sucursal se resuelve ACA, antes de contar. Con un reporte de
        # una sucursal, lo que atendió otro local no es una derivación de este
        # reporte: es una consulta que se fue a otro lado, y se cuenta aparte
        # para poder decirlo. PRIMERO lo que dice la fila, después el mapa: la
        # fila sabe dónde pasó ESA derivación; el mapa solo sabe dónde suele
        # estar la persona, y se equivoca con quien cambió de local.
        suc = local_de_fila(celda(iSU)) or mapa.get(vend)
        if suc_f and norm(suc or "") not in suc_f:
            tot["de_otra_sucursal"] += 1
            continue

        tot["derivaciones"] += 1
        if venta and suc_f:
            tot["ventas"] += 1
        if pat and suc_f:
            patrones[pat] = patrones.get(pat, 0) + 1
        if lg:
            lg["derivaciones"] += 1
            if venta:
                lg["ventas"] += 1
        for x in (og, an_):
            if x:
                x["derivaciones"] += 1
                if venta:
                    x["ventas"] += 1
        b = bolsa(por_vend, vend)
        b["derivaciones"] += 1
        if venta:
            b["ventas"] += 1
        if con_precio:
            b["precio"] += 1
        if fantasma:
            b["fantasma"] += 1
        if con_tpl:
            b["template"] += 1

        if suc:
            s = bolsa(por_suc, suc)
            s["derivaciones"] += 1
            if venta:
                s["ventas"] += 1
            if pat:
                sp = s.setdefault("patrones", {})
                sp[pat] = sp.get(pat, 0) + 1
        else:
            sin_ubicar[vend] = sin_ubicar.get(vend, 0) + 1

        # De donde vino, medido contra la sucursal de ESTE vendedor. Sin
        # localidad cargada no se clasifica: se cuenta aparte y el reporte lo
        # dice, porque hoy falta en casi la mitad de las filas.
        cat, _detalle = zonas.clasificar(celda(iLO) if iLO >= 0 else "", suc)
        if cat is None:
            zonas_sin += 1
        else:
            zonas_tot[cat]["derivaciones"] += 1
            b.setdefault("zonas", {k: 0 for k, _ in zonas.CATEGORIAS})
            b["zonas"][cat] += 1
            if venta:
                zonas_tot[cat]["ventas"] += 1
                b.setdefault("zonas_ventas", {k: 0 for k, _ in zonas.CATEGORIAS})
                b["zonas_ventas"][cat] += 1
            if cat == "interior":
                pr = zonas.provincia_del_lugar(celda(iLO)) or "(sin precisar)"
                p = zonas_prov.setdefault(pr, {"derivaciones": 0, "ventas": 0})
                p["derivaciones"] += 1
                if venta:
                    p["ventas"] += 1
                # de CUÁNTAS provincias distintas le llega a cada uno: no es lo
                # mismo recibir 10 consultas de Córdoba que 10 de diez lugares
                b.setdefault("provincias", {})
                b["provincias"][pr] = b["provincias"].get(pr, 0) + 1

    # ⚠️ EL PERIODO NO SE SACA DEL MINIMO Y EL MAXIMO A SECAS.
    # Una sola fila con la fecha mal cargada —un 2025 donde iba 2026— estira el
    # periodo del reporte a 19 meses cuando los datos son de 8. El encabezado
    # entero queda mintiendo por una tecla. Se recortan los meses de los bordes
    # que tienen menos del 1% de las filas: son ruido, no periodo.
    sueltas = []
    if por_mes:
        piso = max(1, tot["consultas"] * 0.01)
        ordenados = sorted(por_mes)
        vivos = [m for m in ordenados if por_mes[m]["consultas"] >= piso]
        if vivos:
            sueltas = [(m, por_mes[m]["consultas"])
                       for m in ordenados if m < vivos[0] or m > vivos[-1]]
            for m, _ in sueltas:
                por_mes.pop(m, None)
            desde_txt, hasta_txt = vivos[0], vivos[-1]
        else:
            desde_txt, hasta_txt = ordenados[0], ordenados[-1]
    else:
        desde_txt = hasta_txt = ""

    tasa = tot["ventas"] / float(max(1, tot["derivaciones"]))

    # ⚠️ CADA VENDEDOR SE COMPARA CONTRA SU PROPIA SUCURSAL, no contra el
    # promedio de la empresa. Es la diferencia entre medir a la persona y medir
    # al lugar donde trabaja.
    #
    # Caso real: FLOR tenia 0 ventas en 185 derivaciones. Contra el 3,2% global
    # eso parecia clarisimo (1 en 346) y el reporte la senalaba con nombre. Pero
    # Norcenter entero cierra al 1,0%: contra la tasa de SU sucursal, cero
    # ventas en 185 es lo esperable y no hay nada que senalar. Comparar contra
    # el promedio general convierte una diferencia entre sucursales en una acusacion
    # a una persona.
    tasa_de = {}
    for suc, b in por_suc.items():
        tasa_de[suc] = b["ventas"] / float(max(1, b["derivaciones"]))
    for v, b in por_vend.items():
        suc = mapa.get(v)
        referencia = tasa_de.get(suc, tasa)
        real, lado, uno_en = es_real(b["ventas"], b["derivaciones"], referencia)
        b["destaca"] = real
        b["lado"] = lado
        b["uno_en"] = uno_en
        b["sucursal"] = suc or ""
        b["referencia"] = referencia

    # Las SUCURSALES si se pueden comparar entre si: tienen volumen (cientos de
    # derivaciones cada una) y la diferencia habla de un lugar y de un proceso,
    # no de una persona. Es la comparacion que el equipo puede accionar.
    for suc, b in por_suc.items():
        real, lado, uno_en = es_real(b["ventas"], b["derivaciones"], tasa)
        b["destaca"] = real
        b["lado"] = lado
        b["uno_en"] = uno_en

    _pico = (max(por_fecha.items(), key=lambda x: x[1]["consultas"])
             if por_fecha else None)
    return {
        "ok": True,
        "total": tot,
        # el ritmo: por dia de la semana, y cuantos dias tuvieron movimiento
        # ⚠️ El dia pico sale como TEXTO, no como date: todo lo que devuelve
        #    esta funcion tiene que poder viajar en un JSON, y un date no.
        "dias_semana": dias_semana,
        "dias_con_movimiento": len(por_fecha),
        "dia_mas_cargado": ({"fecha": _pico[0].isoformat(),
                             "consultas": _pico[1]["consultas"],
                             "derivaciones": _pico[1]["derivaciones"]}
                            if _pico else None),
        # de que origen viene cada producto, y cuantas filas no tienen origen
        "producto_origen": prod_origen,
        "sin_origen": sin_origen,
        # de donde viene la clientela, y de que provincia son las del interior
        "zonas": zonas_tot,
        "zonas_provincias": zonas_prov,
        "zonas_sin_localidad": zonas_sin,
        # la sucursal del corte, para que la lámina pueda nombrarla y para
        # que nadie lea estos números creyendo que son de toda la empresa
        "sucursal_foco": foco_txt,
        "sucursales_foco": _focos,
        # cómo se comportaron los clientes, y lo recaudado por mes
        "patrones": patrones,
        "lugares": lugares,
        "grupos_origen": grupos_origen,
        "anuncios": anuncios,
        "montos": montos,
        "monto_total": sum(montos.values()),
        # todas las derivaciones del período, de cualquier local: para decir
        # qué parte se llevó la sucursal del corte
        "derivaciones_empresa": tot["derivaciones"] + tot["de_otra_sucursal"],
        "tasa_derivacion": tot["derivaciones"] / float(max(1, tot["consultas"])),
        "tasa_cierre": tasa,
        "desde": desde.isoformat() if desde else "",
        "hasta": hasta.isoformat() if hasta else "",
        # el periodo de verdad, ya sin los meses sueltos de los bordes
        "mes_desde": desde_txt,
        "mes_hasta": hasta_txt,
        # y cuales se dejaron afuera, para poder decirlo en vez de esconderlo
        "fechas_sueltas": [{"mes": m, "filas": c} for m, c in sueltas],
        "vendedores": por_vend,
        "meses": por_mes,
        "sucursales": por_suc,
        "motivos": motivos,
        "medios": medios,
        "origenes": origenes,
        "productos": productos,
        # ⚠️ Los nombres que el mapa no ubica. NO se descartan en silencio: el
        # panel tiene que preguntar de qué sucursal son.
        "sin_ubicar": sin_ubicar,
        "sucursales_conocidas": sorted(set(mapa.values())),
        # el recorte, para que el reporte pueda decirlo en vez de que el
        # total no cierre y nadie sepa por que
        "periodo_pedido": {
            "desde": desde_f.isoformat() if desde_f else "",
            "hasta": hasta_f.isoformat() if hasta_f else "",
        } if recorta else None,
        "fuera_del_periodo": fuera,
        "sin_fecha_fuera": sin_fecha_fuera,
    }
