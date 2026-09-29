# -*- coding: utf-8 -*-
"""Leer una planilla de Google que está compartida "por link".

CUÁNDO SIRVE ESTO
  Cuando la planilla está en «Cualquier persona con el link», Google la deja
  bajar como CSV sin pedir nada: ni cuenta, ni token, ni permiso. El panel puede
  leerla en el acto, sin la configuración de Google Cloud.

  Es el camino más rápido que existe, y por eso está. Pero conviene saber qué
  significa.

⚠️ LO QUE HAY QUE SABER
  «Cualquiera con el link» es literal: cualquiera. No hace falta estar invitado
  ni tener cuenta. Un link reenviado por WhatsApp, pegado en un mail que se
  filtra, o encontrado por un buscador, alcanza para bajar la planilla entera.

  Si la planilla tiene nombre, teléfono o mail de clientes, eso es una
  exposición real — no del panel, sino de la planilla, y existe con o sin el
  panel. Este módulo no la crea: la usa, y avisa.

  La forma privada es `google_cuenta.py`: se le comparte el archivo a una
  dirección concreta y deja de estar al alcance de cualquiera. Cuando el panel
  tiene una cuenta cargada, esa gana: ver `datos_api._leer_google`.

CÓMO LEE
  Google publica dos formas de bajar una hoja como CSV. Se prueban las dos
  porque no siempre están las mismas habilitadas:
    · /export?format=csv  — la de siempre, respeta el `gid` de la pestaña
    · /gviz/tq?tqx=out:csv — la de las visualizaciones, sirve de reserva

  Lo que baja se guarda como un .csv común y lo lee `fuentes.py`, que ya sabe
  adivinar la codificación y el separador y emparejar las filas cortas. No hay
  ninguna razón para escribir un segundo lector de CSV.

Solo biblioteca estándar.
"""
import csv
import io
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from datos import google_sheets
from datos.google_sheets import ErrorGoogle

# Cuánto puede pesar lo que bajamos. Una planilla de derivaciones de un año
# entero anda por los pocos MB; 40 es holgado. El tope existe para que un link
# equivocado que apunte a algo enorme no llene el disco en silencio.
TOPE = 40 * 1024 * 1024

# La pestaña. Google la pone en el link como #gid=443938206 o ?gid=...
_RE_GID = re.compile(r"[#?&]gid=(\d+)")


def gid_de(link):
    """El número de pestaña que trae el link, o "" si no dice.

    Importa: sin el gid, Google devuelve SIEMPRE la primera hoja. Si alguien
    copió el link parado en la pestaña «Agosto», espera Agosto — y recibir
    Enero sin que nadie avise es peor que un error."""
    m = _RE_GID.search(link or "")
    return m.group(1) if m else ""


def urls(link):
    """Las dos formas de bajar la hoja, en orden de preferencia."""
    pid = google_sheets.id_de_planilla(link)
    gid = gid_de(link)
    base = "https://docs.google.com/spreadsheets/d/%s" % urllib.parse.quote(pid, safe="")
    exportar = base + "/export?format=csv" + ("&gid=" + gid if gid else "")
    gviz = base + "/gviz/tq?tqx=out:csv" + ("&gid=" + gid if gid else "")
    return [exportar, gviz]


def _bajar(url, timeout):
    """(bytes, None) o (None, motivo). No levanta: arriba se prueba la otra."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "PanelMyS/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            # ⚠️ Google contesta 200 con una PÁGINA DE LOGIN cuando la planilla
            # no es pública. Si no se mira el tipo de contenido, esa página se
            # guarda como si fuera la planilla y el analizador después informa
            # sobre columnas que son HTML.
            tipo = (r.headers.get("Content-Type") or "").lower()
            crudo = r.read(TOPE + 1)
            if len(crudo) > TOPE:
                return None, "la planilla pesa más de 40 MB"
            if "text/html" in tipo:
                return None, "no es pública"
            if not crudo.strip():
                return None, "esa hoja está vacía"
            return crudo, None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            return None, "no es pública"
        return None, "Google respondió %d" % e.code
    except urllib.error.URLError as e:
        return None, "no pude contactar a Google (¿hay internet?): %s" % e.reason


def es_publica(link, timeout=20):
    """True si se puede bajar sin credenciales. Para decidir y para avisar."""
    try:
        for u in urls(link):
            crudo, _ = _bajar(u, timeout)
            if crudo:
                return True
    except ErrorGoogle:
        return False
    return False


def bajar_a_csv(link, carpeta, timeout=30):
    """Baja la hoja y devuelve la ruta del .csv. Lo lee después fuentes.py.

    El archivo se pisa en cada lectura a propósito: es una copia de trabajo, no
    un archivo del usuario. Guardar una por vez llenaría la carpeta de estado de
    copias de una planilla que ya está en Drive."""
    motivos = []
    for u in urls(link):
        crudo, motivo = _bajar(u, timeout)
        if crudo:
            os.makedirs(carpeta, exist_ok=True)
            pid = google_sheets.id_de_planilla(link)
            gid = gid_de(link)
            ruta = os.path.join(carpeta, "google_%s%s.csv" % (pid[:16],
                                                              "_" + gid if gid else ""))
            with open(ruta, "wb") as f:
                f.write(crudo)
            return ruta
        motivos.append(motivo)

    if "no es pública" in motivos:
        raise ErrorGoogle(
            "Esa planilla no está compartida por link, así que no la puedo leer "
            "sin una cuenta. Dos opciones: cargá la cuenta de Google del panel "
            "(la forma privada, en COMO-CONECTAR-DRIVE.md), o en Drive ponela en "
            "«Cualquier persona con el link».")
    raise ErrorGoogle("No pude bajar la planilla: %s." % (motivos[0] or "error desconocido"))


def leer(link, carpeta, timeout=30):
    """Las filas, usando el lector de CSV de siempre.

    Devuelve lo mismo que `fuentes.leer()` porque va al mismo lugar."""
    from datos import fuentes
    ruta = bajar_a_csv(link, carpeta, timeout)
    r = fuentes.leer({"ruta": ruta, "tipo": "csv", "cache": False})
    if r.get("ok"):
        # El origen que se muestra tiene que ser el de Drive, no el del archivo
        # temporal: nadie pidió un reporte de "google_1WvFLjirSGYkhl.csv".
        r["origen"] = "Planilla de Google (por link)"
        r["archivo"] = "Planilla de Google"
        r["publica"] = True
        r["cuando"] = time.strftime("%d/%m/%Y %H:%M")
    return r

# =====================================================================
#  Las pestanas de la planilla
# =====================================================================
# En el HTML de vista de una planilla publica, Google deja los nombres y los
# gid de las pestanas. No hay endpoint publico que los de en limpio, asi que se
# leen de ahi. Es fragil por naturaleza —depende del HTML de Google— y por eso
# quien llama tiene que aguantar una lista vacia sin romperse.
_RE_TAB = re.compile(r'\{name:\s*"(.*?)".*?gid:\s*"(\d+)"')
_RE_TAB2 = re.compile(r'id="sheet-button-(\d+)"[^>]*>([^<]{1,60})<')


def pestanas(link, timeout=25):
    """[(nombre, gid), ...] de una planilla publica. [] si no se pudieron leer.

    Sirve para preguntar «que hoja queres leer» en vez de agarrar la primera y
    que despues nadie entienda por que los numeros no son los que esperaba."""
    pid = google_sheets.id_de_planilla(link)
    u = "https://docs.google.com/spreadsheets/d/%s/htmlview" % urllib.parse.quote(pid, safe="")
    req = urllib.request.Request(u)
    req.add_header("User-Agent", "PanelMyS/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            h = r.read(4 * 1024 * 1024).decode("utf-8", "replace")
    except Exception:                                        # noqa
        return []

    salida = [(n.strip(), g) for n, g in _RE_TAB.findall(h) if n.strip()]
    if not salida:
        # el otro formato: primero el gid, despues el nombre
        salida = [(n.strip(), g) for g, n in _RE_TAB2.findall(h) if n.strip()]

    # sin repetidos y en orden
    vistos, limpio = set(), []
    for n, g in salida:
        if g not in vistos:
            vistos.add(g)
            limpio.append((n, g))
    return limpio


def _asomarse(url, cuantos_bytes, timeout):
    """Los primeros bytes de una descarga, sin bajarla entera.

    Para preguntar «que hoja queres» no se pueden bajar nueve planillas
    completas: la de derivaciones sola pesa 1,5 MB. Con 64 KB alcanza para ver
    los encabezados y unas cuantas filas."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "PanelMyS/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if "text/html" in (r.headers.get("Content-Type") or "").lower():
                return None, "no es pública"
            return r.read(cuantos_bytes), None
    except urllib.error.HTTPError as e:
        return None, ("no es pública" if e.code in (401, 403, 404)
                      else "Google respondió %d" % e.code)
    except urllib.error.URLError as e:
        return None, "no pude contactar a Google: %s" % e.reason


def vistazo(link, gid="", filas_max=60, timeout=25):
    """Una mirada corta a una hoja, para decidir si sirve SIN bajarla entera.

    ⚠️ Se usa la exportación a CSV y NO gviz. gviz decide por su cuenta que la
    fila 1 son los encabezados, y cuando arriba hay un título lo pega al nombre
    de la primera columna: «ENERO - METRICA SEMANAL MEDIOS DE COMUNICACION».
    El CSV crudo devuelve las filas como están y deja que `encabezado.py`
    encuentre dónde empieza la tabla de verdad."""
    from datos import encabezado
    pid = google_sheets.id_de_planilla(link)
    u = ("https://docs.google.com/spreadsheets/d/%s/export?format=csv"
         % urllib.parse.quote(pid, safe=""))
    if gid:
        u += "&gid=" + str(gid)

    crudo, motivo = _asomarse(u, 64 * 1024, timeout)
    if not crudo:
        return {"ok": False, "error": motivo or "no pude mirarla"}

    texto = crudo.decode("utf-8", "replace")
    # La ultima linea de un corte a la mitad casi siempre queda partida: se tira.
    if "\n" in texto:
        texto = texto[:texto.rindex("\n")]
    filas = list(csv.reader(io.StringIO(texto)))[:filas_max]
    recortadas, aviso = encabezado.recortar(filas)
    cab = [c.strip() for c in (recortadas[0] if recortadas else []) if c.strip()]
    cuerpo = [f for f in recortadas[1:] if any(str(c).strip() for c in f)]

    # ¿Es una tabla? Dos columnas con nombre y algo abajo. Las hojas que son un
    # tablero —varios cuadros sueltos en las mismas filas— no lo son, y decirlo
    # es mas util que dejar que alguien arme un reporte de la nada.
    sirve = len(cab) >= 2 and len(cuerpo) >= 1
    return {
        "ok": True,
        "columnas": cab,
        "cuantas": len(cab),
        "muestra": [f[:len(cab)] for f in cuerpo[:3]],
        "sirve": sirve,
        "aviso": aviso,
        "motivo": ("" if sirve else
                   "No parece una tabla: no encontré una fila de encabezados con "
                   "datos abajo. Pasa con las hojas que son un tablero, con "
                   "varios cuadros sueltos."),
    }
