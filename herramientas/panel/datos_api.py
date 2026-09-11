# -*- coding: utf-8 -*-
"""Las rutas de la seccion Datos.

Vive aparte de panel_server.py a proposito: es una funcion entera, con sus
propias reglas, y meterla en el archivo grande lo haria todavia mas grande.
panel_server la llama y listo.

⚠️ REGLA QUE NO SE NEGOCIA
Las columnas marcadas `sensible` no viajan al navegador. Ni siquiera al del
panel. Se manda el NOMBRE de la columna —para que se vea que existe y que esta
protegida— pero ni un valor. Si alguna vez hace falta mostrar el detalle,
tiene que ser una decision explicita y con su propia ruta, no un descuido de
esta.
"""
import datetime
import hashlib
import io
import json
import os
import re

from datos import (a_pdf, analizador, deck, deck_word, derivaciones,
                   encabezado, fuentes, lecturas, medidas, reporte, revisor)

try:
    from datos import google_sheets
except Exception:                          # noqa: si falta, el resto anda igual
    google_sheets = None

try:
    from datos import google_cuenta
except Exception:                          # noqa
    google_cuenta = None

try:
    from datos import google_link
except Exception:                          # noqa
    google_link = None


# ── leer, venga de donde venga ───────────────────────────────────────────
def _leer_google(f):
    """Lee de Drive y devuelve la MISMA forma que fuentes.leer().

    Que las dos fuentes hablen igual es lo que permite que arriba haya un solo
    camino. Antes no era así —google_sheets.leer() devuelve una lista pelada— y
    el código de arriba le pedía .get("ok") a una lista.

    Se prefiere la cuenta de servicio cuando está cargada: no se vence a los
    siete días, ve solo los archivos que le compartieron, y no hay que
    reconectarla nunca. El OAuth sigue andando para quien ya lo tenga."""
    hay_cuenta = bool(google_cuenta and google_cuenta.estado().get("conectado"))
    hay_oauth = bool(google_sheets and google_sheets.estado().get("conectado"))
    planilla = f.get("planilla", "")
    origen = f.get("link") or planilla

    # Una planilla en «cualquiera con el link» se baja sin credenciales. Es el
    # unico caso que anda sin configurar nada en Google, y por eso se decide al
    # conectarla y queda ANOTADO en la fuente (clase="publico") en vez de
    # adivinarse en cada lectura: asi la pantalla puede decirlo, y nadie termina
    # leyendo por link creyendo que lee en privado.
    if f.get("clase") == "publico":
        if google_link is None:
            return {"ok": False, "filas": [], "origen": origen,
                    "error": "falta el modulo de lectura por link"}
        try:
            return google_link.leer(f.get("link") or planilla, _cache_dir())
        except Exception as e:             # noqa: ya viene en castellano
            return {"ok": False, "filas": [], "origen": origen, "error": str(e)}

    try:
        if f.get("clase") == "doc":
            # Un documento no tiene hojas: tiene tablas. Se usa la primera, que
            # es lo que hay cuando alguien pega el link de un Doc esperando que
            # el panel entienda lo que hay adentro.
            if not hay_cuenta:
                return {"ok": False, "filas": [], "origen": origen,
                        "error": "Para leer un documento de Google hace falta la "
                                 "cuenta de Google del panel (la forma simple de "
                                 "conectar). Cargala y probá de nuevo."}
            d = google_cuenta.leer_documento(planilla)
            if not d.get("tablas"):
                return {"ok": False, "filas": [], "origen": origen,
                        "error": "Ese documento no tiene ninguna tabla adentro, "
                                 "y un reporte necesita datos en filas y columnas."}
            filas = d["tablas"][0]
            origen = "Documento de Google · %s" % (d.get("titulo") or "")
        elif hay_cuenta:
            filas = google_cuenta.leer(planilla, f.get("rango", ""))
        elif hay_oauth:
            filas = google_sheets.leer(planilla, f.get("rango", ""))
        else:
            return {"ok": False, "filas": [], "origen": origen,
                    "error": "El panel no está conectado con Google. Andá a "
                             "«Agregar un reporte» → «Una planilla de Google»."}
    except Exception as e:                 # noqa: ErrorGoogle ya viene en castellano
        return {"ok": False, "filas": [], "origen": origen, "error": str(e)}

    if not filas:
        return {"ok": False, "filas": [], "origen": origen,
                "error": "Esa hoja está vacía."}

    # ⚠️ Recien ACA, y no mas arriba. Todo lo que pasa por `fuentes.leer()`
    # —archivos de la PC y planillas bajadas por link— ya viene recortado: ese
    # modulo saltea los titulos de arriba desde antes. Lo que llega por la API
    # de Google, en cambio, viene crudo: son filas que devolvio Google, sin
    # pasar por ningun lector. Correrlo en los dos lados seria recortar dos
    # veces la misma tabla.
    filas, aviso = encabezado.recortar(filas)
    avisos = [aviso] if aviso else []

    return {
        "ok": True,
        "filas": filas,
        "origen": origen,
        "cuando": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "desde_cache": False,
        "archivo": f.get("archivo") or "Planilla de Google",
        "tipo": "google",
        "avisos": avisos,
        "total_filas": len(filas) - 1,
        "total_columnas": len(filas[0]),
    }


def _cache_dir():
    """Donde se deja la copia de trabajo de lo que se baja de Drive.

    Va a la carpeta de estado del panel, que esta fuera de lo que se publica.
    Nunca adentro del proyecto: la copia tiene los datos de los clientes."""
    base = google_sheets.STATE_DIR if google_sheets else ""
    return os.path.join(base or os.path.expanduser("~"), "cache_google")


def _leer_fuente(f):
    """La única puerta de lectura: Google o archivo, misma forma de respuesta."""
    if (f or {}).get("tipo") == "google":
        return _leer_google(f)
    return fuentes.leer(f)


def _leer_y_analizar(rep):
    """(lectura, análisis, revisión, lecturas). El trabajo pesado, UNA vez.

    Lo comparten la pantalla y el reporte descargable. Antes cada uno leía y
    analizaba por su cuenta, así que el .docx podía traer números distintos a
    los de la pantalla si alguien tocaba la planilla en el medio."""
    r = _leer_fuente(rep.get("fuente") or {})
    if not r.get("ok"):
        return r, None, None, None

    filas = r["filas"]
    an = analizador.analizar(filas)
    return r, an, revisor.revisar(filas, an), lecturas.lecturas(filas, an)


# ── donde se guarda lo que elige marketing ───────────────────────────────
def _config_path(state_dir):
    """El archivo de configuracion, en la carpeta de estado del panel.

    Nunca adentro del proyecto: guarda la ruta de una planilla con datos de
    clientes, y `herramientas/` esta ignorado pero la carpeta de estado esta
    directamente afuera.
    """
    return os.path.join(state_dir, "datos.json")


def cargar(state_dir):
    p = _config_path(state_dir)
    try:
        with io.open(p, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            d = {}
    except Exception:                      # noqa: sin config todavia, o rota
        d = {}
    return _migrar(d)


def _migrar(d):
    """Lo viejo tenia UNA fuente suelta; ahora hay una lista de reportes.

    Si aparece una config de las viejas se convierte en el primer reporte, con
    su titulo y lo que ya estuviera publicado. Nadie tiene que volver a
    configurar lo que ya configuro.
    """
    if isinstance(d.get("reportes"), list):
        return d
    viejo = d.get("fuente")
    d["reportes"] = []
    if viejo:
        d["reportes"].append({
            "id": nuevo_id(),
            "titulo": d.get("titulo") or "Reporte",
            "fuente": viejo,
            "publicados": d.get("publicados") or [],
        })
    d.pop("fuente", None)
    d.pop("titulo", None)
    d.pop("publicados", None)
    return d


def nuevo_id():
    """Un identificador corto y estable para cada reporte."""
    return "r" + hashlib.md5(
        (str(datetime.datetime.now()) + os.urandom(4).hex()).encode()
    ).hexdigest()[:10]


def buscar(cfg, rid):
    for r in cfg.get("reportes") or []:
        if r.get("id") == rid:
            return r
    return None


# ── los informes de una planilla ─────────────────────────────────────────
#  Una planilla conectada da MUCHOS informes, no uno: el de agosto, el de la
#  semana pasada, el que haga falta. Cada uno es un nombre y un tramo de
#  fechas; los números salen de leer la planilla en ese momento, así que un
#  informe guardado no es una foto vieja: se vuelve a calcular con lo que la
#  planilla diga hoy, recortado a su período.
#
#  Viven adentro del reporte, en `informes`. Guardar la lista y no los números
#  es lo que hace que "el informe de agosto" siga siendo cierto en octubre.
def informes(rep):
    return [i for i in (rep.get("informes") or []) if isinstance(i, dict)]


def buscar_informe(rep, iid):
    for i in informes(rep):
        if i.get("id") == iid:
            return i
    return None


def secciones_posibles():
    """Las preguntas del formulario: qué puede llevar un reporte."""
    return [{"id": k, "titulo": t, "detalle": det} for k, t, det in deck.SECCIONES]


def opciones_posibles():
    """El resto de las preguntas: detalle, comparación, nombres.

    Salen de acá y no de la pantalla por lo mismo que las secciones: el día que
    haya una forma más de comparar, aparece sola en el formulario.
    """
    return {
        "detalle": [{"id": k, "titulo": t, "detalle": d}
                    for k, t, d in deck.DETALLES],
        "comparar": [{"id": k, "titulo": t, "detalle": d}
                     for k, t, d in deck.COMPARACIONES],
        "vista": [{"id": k, "titulo": t, "detalle": d}
                  for k, t, d in deck.VISTAS],
        "hoja": [{"id": k, "titulo": t, "detalle": d}
                 for k, t, d in deck.HOJAS],
        "con_lista": list(deck.CON_LISTA),
    }


def _periodo_previo(desde, hasta, modo):
    """(desde, hasta, cómo se llama) del período contra el que se compara.

    Un mes entero se compara contra el mes ANTERIOR, no contra «los 31 días de
    antes»: si agosto se comparara contra el 1 al 31 de julio corrido desde el
    1 de agosto hacia atrás, daría del 2/7 al 1/8 y no sería julio. Para un
    rango cualquiera sí se usa la misma cantidad de días, pegados atrás.
    """
    if not desde or not hasta or modo not in ("anterior", "ano"):
        return None, None, ""
    if modo == "ano":
        try:
            a, z = desde.replace(year=desde.year - 1), hasta.replace(year=hasta.year - 1)
        except ValueError:                      # 29 de febrero
            a = desde.replace(year=desde.year - 1, day=28)
            z = hasta.replace(year=hasta.year - 1, day=28)
        return a, z, "el mismo período de %d" % a.year
    fin_de_mes = (hasta + datetime.timedelta(days=1)).day == 1
    if desde.day == 1 and fin_de_mes and desde.month == hasta.month:
        ultimo = desde - datetime.timedelta(days=1)         # el día previo
        primero = ultimo.replace(day=1)
        return primero, ultimo, deck._titulo_mes(primero.strftime("%Y-%m"))
    dias = (hasta - desde).days + 1
    z = desde - datetime.timedelta(days=1)
    return z - datetime.timedelta(days=dias - 1), z, "los %d días anteriores" % dias


def _revisar_periodo(desde, hasta):
    """El período, o el error para mostrar. Lo revisan crear Y editar: escrito
    dos veces, una de las dos se olvida de algo."""
    for _, q in (("desde", desde), ("hasta", hasta)):
        if q and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(q)):
            return "La fecha «%s» no está bien escrita." % q
    if desde and hasta and str(desde) > str(hasta):
        return "El desde tiene que ser anterior al hasta."
    return ""


def _revisar_secciones(secciones):
    """Las secciones válidas EN EL ORDEN del reporte, o el error."""
    validas = set(deck.TODAS)
    elegidas = [k for k in deck.TODAS if k in set(secciones or []) & validas]
    if not elegidas:
        return None, "Elegí al menos una cosa para medir."
    return elegidas, ""


def informe_nuevo(rep, nombre, desde, hasta, secciones=None, opciones=None):
    """Suma un informe al reporte. Devuelve (informe, error)."""
    nombre = (nombre or "").strip()
    if not nombre:
        return None, "Ponele un nombre al informe."
    mal = _revisar_periodo(desde, hasta)
    if mal:
        return None, mal
    elegidas, mal = _revisar_secciones(secciones)
    if mal:
        return None, mal
    inf = {
        "id": "i" + hashlib.md5(
            (str(datetime.datetime.now()) + os.urandom(4).hex()).encode()).hexdigest()[:10],
        "nombre": nombre,
        "desde": str(desde or ""),
        "hasta": str(hasta or ""),
        # se guardan EN EL ORDEN del reporte, no en el que se tildaron
        "secciones": elegidas,
        "opciones": _limpiar_opciones(opciones),
        "creado": datetime.date.today().isoformat(),
    }
    rep.setdefault("informes", []).insert(0, inf)   # el último arriba
    return inf, None


def _limpiar_opciones(op, antes=None):
    """Solo lo que el reporte entiende. Lo que llega de afuera no se guarda tal cual.

    `antes` son las opciones que ya tenía el informe: al editar llega solo lo
    que se tocó, y lo que no viene tiene que quedar como estaba en vez de
    volver al valor de fábrica.
    """
    op = op if isinstance(op, dict) else {}
    vieja = antes if isinstance(antes, dict) else {}
    validos_det = {k for k, _, _ in deck.DETALLES}
    validos_cmp = {k for k, _, _ in deck.COMPARACIONES}
    validos_vis = {k for k, _, _ in deck.VISTAS}
    validos_hoja = {k for k, _, _ in deck.HOJAS}
    det = str(op.get("detalle") or vieja.get("detalle") or "10")
    cmp_ = str(op.get("comparar") or vieja.get("comparar") or "anterior")
    vis = str(op.get("vista") or vieja.get("vista") or "barras")
    # el tamaño de hoja del PDF. Los reportes de antes de que esto existiera no
    # lo tienen, y caen en «pantalla», que es como salian.
    hoja = str(op.get("hoja") or vieja.get("hoja") or "pantalla")
    # ⚠️ La sucursal NO se valida contra una lista fija: los locales salen de
    # la planilla y el día que abra uno nuevo tiene que poder elegirse sin
    # tocar el código. Se limpia el texto y listo; una sucursal que no existe
    # da un reporte vacío, que es visible, y no un error escondido.
    suc = str(op.get("sucursal") if "sucursal" in op
              else vieja.get("sucursal") or "").strip()[:60]

    # las vistas por sección: solo las que son una lista, y solo valores validos
    vistas = dict(vieja.get("vistas") or {})
    vistas.update(op.get("vistas") if isinstance(op.get("vistas"), dict) else {})
    vistas = {k: v for k, v in vistas.items()
              if k in deck.CON_LISTA and v in validos_vis}

    # el fondo de cada lámina: claro u oscuro. Se acepta para CUALQUIER
    # sección —el embudo y los límites no son listas y también se pintan—,
    # pero solo esos dos valores: un color suelto rompería el contraste que
    # el deck ya tiene resuelto para las dos variantes.
    fondos = dict(vieja.get("fondos") or {})
    fondos.update(op.get("fondos") if isinstance(op.get("fondos"), dict) else {})
    validas_sec = set(deck.TODAS) | {"portada", "limites"}
    fondos = {str(k): v for k, v in fondos.items()
              if str(k) in validas_sec and v in ("claro", "oscuro")}

    # los textos reescritos. Un texto vacio BORRA el de encima y devuelve el de
    # fabrica: es la unica forma de arrepentirse sin tener que acordarse del
    # original.
    textos = dict(vieja.get("textos") or {})
    nuevos = op.get("textos") if isinstance(op.get("textos"), dict) else {}
    for k, v in nuevos.items():
        k = str(k)[:80]
        v = str(v or "").strip()[:600]
        if v:
            textos[k] = v
        else:
            textos.pop(k, None)

    # los textos que el usuario saco del reporte. Llega la lista ENTERA cada
    # vez —no un agregado—, porque «volver a mostrar» tiene que poder sacar uno
    # de la lista, y con un merge eso sería imposible.
    if isinstance(op.get("ocultos"), list):
        ocultos = sorted({str(k)[:80] for k in op["ocultos"] if str(k).strip()})
    else:
        ocultos = list(vieja.get("ocultos") or [])

    return {
        "detalle": det if det in validos_det else "10",
        "comparar": cmp_ if cmp_ in validos_cmp else "anterior",
        "vista": vis if vis in validos_vis else "barras",
        "hoja": hoja if hoja in validos_hoja else "pantalla",
        "sucursal": suc,
        "vistas": vistas,
        "fondos": fondos,
        "textos": textos,
        "ocultos": ocultos,
        "nota": str(op.get("nota") if "nota" in op
                    else (vieja.get("nota") or ""))[:280],
    }


def informe_editar(rep, iid, nombre=None, opciones=None, desde=None,
                   hasta=None, secciones=None):
    """Cambia un informe ya creado. Devuelve (informe, error).

    Los números NO se guardan nunca: se recalculan al abrirlo. Acá solo se
    guarda cómo se llama, qué período toma, qué mide y cómo se muestra.

    Cada cosa se toca solo si vino: el lápiz de adentro del reporte manda
    `opciones` y nada más, y no puede quedarse sin período por eso.
    """
    inf = buscar_informe(rep, iid)
    if not inf:
        return None, "no encuentro ese reporte"
    if nombre is not None:
        nombre = str(nombre).strip()[:80]
        if not nombre:
            return None, "Ponele un nombre."
        inf["nombre"] = nombre
    if desde is not None or hasta is not None:
        d = str(desde if desde is not None else inf.get("desde") or "")
        h = str(hasta if hasta is not None else inf.get("hasta") or "")
        mal = _revisar_periodo(d, h)
        if mal:
            return None, mal
        inf["desde"], inf["hasta"] = d, h
    if secciones is not None:
        elegidas, mal = _revisar_secciones(secciones)
        if mal:
            return None, mal
        inf["secciones"] = elegidas
    inf["opciones"] = _limpiar_opciones(opciones, inf.get("opciones"))
    return inf, None


def informe_borrar(rep, iid):
    antes = informes(rep)
    rep["informes"] = [i for i in antes if i.get("id") != iid]
    return len(rep["informes"]) != len(antes)


def _sucursal_de(informe):
    """La sucursal a la que está recortado el reporte, o "" si es de todas."""
    return ((informe or {}).get("opciones") or {}).get("sucursal") or ""


def _fecha_de(txt):
    """'2026-08-01' -> date, o None."""
    try:
        return datetime.date(*[int(x) for x in str(txt).split("-")])
    except (ValueError, TypeError):
        return None


def guardar(state_dir, d):
    p = _config_path(state_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)                     # o queda el viejo entero, o el nuevo


# ── lo que se le manda al navegador ──────────────────────────────────────
def _sin_datos_de_cliente(an):
    """El analisis, con las columnas sensibles vaciadas de contenido.

    Se conserva el nombre y la marca —la pantalla tiene que poder decir "esta
    columna existe y esta protegida"— pero se borra todo lo que sea un valor.
    """
    salida = {"filas": an.get("filas", 0), "columnas": []}
    for c in an.get("columnas", []):
        c2 = dict(c)
        if c2.get("sensible"):
            c2.pop("valores", None)
            c2.pop("grupos", None)
            c2.pop("parecidos", None)
            c2.pop("desde", None)
            c2.pop("hasta", None)
        salida["columnas"].append(c2)
    return salida


def _avisos_sin_ejemplos(avisos, an):
    """Los avisos, sin ejemplos que vengan de una columna sensible.

    Un aviso del tipo "esta columna tiene valores repetidos" trae ejemplos, y
    si esa columna fuera la de telefonos los ejemplos SERIAN telefonos.
    """
    sens = set(c["nombre"] for c in an.get("columnas", []) if c.get("sensible"))
    out = []
    for a in avisos:
        a2 = dict(a)
        if any(s.lower() in (a.get("titulo") or "").lower() for s in sens):
            a2["ejemplos"] = []
            a2["_recortado"] = True
        out.append(a2)
    return out


def _periodo_txt(d):
    """'enero 2026 — agosto 2026' del analisis de derivaciones, o ''.

    Usa deck._titulo_mes y no una traduccion propia: el encabezado del tablero
    y la portada del reporte tienen que decir el MISMO periodo, y dos funciones
    que hacen lo mismo se desincronizan en cuanto alguien toca una.
    """
    desde = d.get("mes_desde") or ""
    if not desde:
        return ""
    txt = deck._titulo_mes(desde)
    hasta = d.get("mes_hasta") or ""
    if hasta and hasta != desde:
        txt += " — " + deck._titulo_mes(hasta)
    return txt


def analizar_fuente(rep, state_dir):
    """Lee la planilla de UN reporte y devuelve lo que la pantalla necesita."""
    if not rep or not rep.get("fuente"):
        return {"ok": False, "error": "ese reporte no tiene planilla conectada"}

    r, an, av, ls = _leer_y_analizar(rep)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error") or "no se pudo leer la planilla"}

    es_der = derivaciones.es_derivaciones(an)
    der_resumen = {}
    if es_der:
        try:
            d = derivaciones.analizar(r["filas"], state_dir)
            if d.get("ok"):
                der_resumen = {
                    "sin_ubicar": d.get("sin_ubicar") or {},
                    "sucursales_conocidas": d.get("sucursales_conocidas") or [],
                    "consultas": d["total"]["consultas"],
                    "derivaciones": d["total"]["derivaciones"],
                    "ventas": d["total"]["ventas"],
                    # El periodo, para que el encabezado del tablero diga de
                    # cuando son esos tres numeros. Se arma ACA y con la misma
                    # funcion que la portada del reporte (deck._titulo_mes):
                    # son los meses ya limpios de los sueltos de los bordes, y
                    # si cada pantalla los escribiera por su cuenta, el mismo
                    # dato leido en dos lugares terminaria diciendo periodos
                    # distintos.
                    "periodo": _periodo_txt(d),
                    # para que el asistente pueda ofrecer «solo esta sucursal»
                    "sucursales": sorted((d.get("sucursales") or {}).keys()),
                }
        except Exception:              # noqa: el tablero anda igual sin esto
            der_resumen = {}

    return {
        "ok": True,
        "origen": r.get("origen") or r.get("archivo") or "",
        "cuando": r.get("cuando") or "",
        "desde_cache": bool(r.get("desde_cache")),
        "avisos_lectura": r.get("avisos") or [],
        "analisis": _sin_datos_de_cliente(an),
        # ⚠️ Antes de mandarlos, se acomodan segun lo que se sabe de ESTA
        # planilla: un Vendedor vacio no es un error de carga, es una
        # consulta que no se derivo. Sin esto el panel abria con cuatro
        # "graves" de los cuales tres eran el funcionamiento normal.
        "revision": derivaciones.acomodar_avisos(
            _avisos_sin_ejemplos(av, an), an),
        "lecturas": ls,
        "publicados": rep.get("publicados") or [],
        "id": rep.get("id"),
        "titulo": rep.get("titulo") or "Reporte",
        # los informes que ya se crearon de esta planilla. Van con el analisis
        # y no en una ruta aparte para que la pantalla los tenga en el mismo
        # viaje en que dibuja el reporte
        "informes": informes(rep),
        "secciones_posibles": secciones_posibles(),
        "opciones_posibles": opciones_posibles(),
        # Que se puede medir en esta planilla, y que se eligio medir. Van con el
        # analisis y no en una ruta aparte porque salen de el: pedirlos por
        # separado obligaria a analizar la planilla dos veces.
        "medidas": medidas.proponer(an),
        "foco": rep.get("foco") or [],
        # si es la planilla de derivaciones hay un reporte con diseno
        # ademas del generico, y el panel ofrece el boton
        "es_derivaciones": es_der,
        # ⚠️ Viaja CON el analisis y no en una llamada aparte. Pedirlo
        # despues significaba leer y analizar la planilla entera otra vez:
        # cuatro segundos, y el aviso de "faltan ubicar vendedores"
        # apareciendo cuando la persona ya se puso a mirar los numeros.
        "derivaciones": der_resumen,
    }


def deck_derivaciones(rep, state_dir, informe=None):
    """(html, error) del reporte con diseño, si la planilla es la de derivaciones.

    Es un camino aparte del reporte genérico a propósito. El genérico sirve para
    cualquier planilla y por eso no puede decir nada sobre el negocio; este sabe
    qué es una derivación y qué es una venta, y por eso puede escribir
    conclusiones en vez de listar columnas."""
    r, an, _, _ = _leer_y_analizar(rep)
    if not r.get("ok"):
        return None, r.get("error")
    if not derivaciones.es_derivaciones(an):
        return None, ("Este reporte con diseño es para la planilla de "
                      "derivaciones. Necesita las columnas Fecha, Vendedor y "
                      "Respuesta Final.")
    # con informe, el reporte es de ESE tramo; sin informe, de toda la planilla
    d = derivaciones.analizar(
        r["filas"], state_dir,
        desde_f=_fecha_de((informe or {}).get("desde")),
        hasta_f=_fecha_de((informe or {}).get("hasta")),
        sucursal_f=_sucursal_de(informe))
    if not d.get("ok"):
        return None, d.get("error")
    titulo = ((informe or {}).get("nombre")
              or rep.get("titulo") or "Derivaciones y ventas")
    return deck.armar(d, titulo, (informe or {}).get("secciones"),
                      _opciones_de(informe, r["filas"], state_dir)), None


def _opciones_de(informe, filas, state_dir):
    """Las opciones del informe, ya con el período de comparación calculado.

    El análisis del período anterior se hace acá y NO en el deck: el deck
    dibuja, no lee planillas. Así también queda claro que los dos números
    salen del mismo archivo leído una sola vez.
    """
    op = dict((informe or {}).get("opciones") or {})
    op.setdefault("detalle", "10")
    op.setdefault("comparar", "anterior")
    desde = _fecha_de((informe or {}).get("desde"))
    hasta = _fecha_de((informe or {}).get("hasta"))
    a, z, comollama = _periodo_previo(desde, hasta, op.get("comparar"))
    if a and z:
        # ⚠️ con la MISMA sucursal: el reporte de Hudson de agosto contra la
        # empresa entera de julio daría porcentajes que no significan nada
        previo = derivaciones.analizar(filas, state_dir, desde_f=a, hasta_f=z,
                                       sucursal_f=_sucursal_de(informe))
        if previo.get("ok") and previo["total"]["consultas"]:
            op["previo"] = previo
            op["previo_txt"] = comollama
    return op


def deck_derivaciones_pdf(rep, state_dir, informe=None):
    """(ruta, error) del reporte con diseño en PDF, listo para bajar.

    Sale del MISMO html que se ve en pantalla, impreso por el navegador con la
    hoja `@media print` del deck. Por eso el PDF no puede quedar desfasado del
    reporte: no hay una segunda versión del diseño que mantener.
    """
    html, err = deck_derivaciones(rep, state_dir, informe)
    if err or not html:
        return None, err or "no pude armar el reporte"
    titulo = ((informe or {}).get("nombre")
              or rep.get("titulo") or "Derivaciones y ventas")
    carpeta = os.path.join(state_dir, "reportes")
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    return a_pdf.desde_html(html, os.path.join(carpeta,
                                               a_pdf.nombre_archivo(titulo)))


def deck_derivaciones_word(rep, state_dir, informe=None):
    """(ruta, error) del MISMO reporte con diseño, pero en .docx.

    El Word sale de acá y no de `reporte.a_word` a propósito: aquel escribe un
    documento de oficina —títulos y tablas— y lo que se pide bajar es la
    presentación, la misma que se ve en pantalla. Los números salen del mismo
    análisis, así que el Word y el deck no pueden decir cosas distintas.
    """
    r, an, _, _ = _leer_y_analizar(rep)
    if not r.get("ok"):
        return None, r.get("error")
    if not derivaciones.es_derivaciones(an):
        return None, ("Este reporte con diseño es para la planilla de "
                      "derivaciones.")
    d = derivaciones.analizar(
        r["filas"], state_dir,
        desde_f=_fecha_de((informe or {}).get("desde")),
        hasta_f=_fecha_de((informe or {}).get("hasta")),
        sucursal_f=_sucursal_de(informe))
    if not d.get("ok"):
        return None, d.get("error")
    titulo = ((informe or {}).get("nombre")
              or rep.get("titulo") or "Derivaciones y ventas")
    carpeta = os.path.join(state_dir, "reportes")
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    ruta = os.path.join(carpeta, deck_word.nombre_archivo(titulo))
    deck_word.a_word(d, ruta, titulo, (informe or {}).get("secciones"),
                     _opciones_de(informe, r["filas"], state_dir))
    return ruta, None



def _pc(x):
    """«20%» si es redondo, «13,33%» si no. Copia el formato de los documentos
    que ya hay en el módulo: ahí conviven los dos y esa es la regla."""
    v = 100.0 * (x or 0)
    if abs(v - round(v)) < 0.005:
        return "%d%%" % int(round(v))
    return ("%.2f%%" % v).replace(".", ",")


def _cambio(ahora, antes):
    """«+27,4% vs período anterior», como en los documentos hechos a mano."""
    if not antes:
        return "", "up"
    dif = 100.0 * (ahora - antes) / float(antes)
    signo = "+" if dif > 0 else ("-" if dif < 0 else "")
    return (("%s%.1f%% vs período anterior" % (signo, abs(dif))).replace(".", ","),
            "up" if dif >= 0 else "down")


def metricas_de(rep, state_dir, informe=None):
    """Los números del reporte de vendedores, listos para armar el documento.

    ⚠️ Devuelve NÚMEROS, no HTML. El documento lo arma la pantalla con el mismo
    armador que el editor de módulos, para que quede editable como si lo
    hubieran hecho a mano. Ver el comentario de arriba del archivo del parche.
    """
    r, an, _, _ = _leer_y_analizar(rep)
    if not r.get("ok"):
        return None, r.get("error")
    if not derivaciones.es_derivaciones(an):
        return None, ("El reporte de vendedores sale de la planilla de "
                      "derivaciones.")
    foco = _sucursal_de(informe)
    d = derivaciones.analizar(
        r["filas"], state_dir,
        desde_f=_fecha_de((informe or {}).get("desde")),
        hasta_f=_fecha_de((informe or {}).get("hasta")),
        sucursal_f=foco)
    if not d.get("ok"):
        return None, d.get("error")

    op = _opciones_de(informe, r["filas"], state_dir)
    prev = (op.get("previo") or {}).get("total") if op.get("previo") else None
    t = d["total"]

    def conv(b):
        return b.get("ventas", 0) / float(max(1, b.get("derivaciones", 0)))

    vs = sorted(d["vendedores"].items(),
                key=lambda x: (-conv(x[1]), -x[1].get("ventas", 0), x[0]))
    podio = sorted(d["vendedores"].items(),
                   key=lambda x: (-x[1].get("ventas", 0), -conv(x[1]), x[0]))
    podio = [x for x in podio if x[1].get("ventas")][:4]

    sucs = sorted(d["sucursales"].items(),
                  key=lambda x: -x[1]["derivaciones"])
    cam_der, tend_der = _cambio(t["derivaciones"],
                                prev and prev.get("derivaciones"))
    cam_ven, tend_ven = _cambio(t["ventas"], prev and prev.get("ventas"))
    cam_con, tend_con = _cambio(t["consultas"], prev and prev.get("consultas"))
    return {
        "ok": True,
        "titulo": ((informe or {}).get("nombre") or _periodo_txt(d) or
                   "Derivaciones").upper(),
        "sucursal": foco,
        "periodo": _periodo_txt(d),
        "kpis": [
            {"label": "Derivaciones totales", "valor": str(t["derivaciones"]),
             "pie": cam_der, "tend": tend_der, "lead": True},
            {"label": "Ventas", "valor": str(t["ventas"]),
             "pie": cam_ven, "tend": tend_ven, "lead": False},
            {"label": "Consultas", "valor": str(t["consultas"]),
             "pie": cam_con, "tend": tend_con, "lead": False},
        ],
        "sucursales": [{"label": n.upper(), "valor": str(b["derivaciones"])}
                       for n, b in sucs],
        "podio": [{"puesto": "%d°" % (i + 1), "nombre": v.upper(),
                   "suc": (b.get("sucursal") or "").upper(),
                   "valor": str(b.get("ventas", 0)), "vlabel": "ventas",
                   "extra": "conv. " + _pc(conv(b)), "lead": i == 0}
                  for i, (v, b) in enumerate(podio)],
        "tabla": [[v.upper(), str(b.get("derivaciones", 0)),
                   str(b.get("ventas", 0)), _pc(conv(b))]
                  for v, b in vs if b.get("derivaciones")],
    }, None

def resumen_derivaciones(rep, state_dir):
    """Los números del embudo, para mostrarlos en el panel sin abrir el deck."""
    r, an, _, _ = _leer_y_analizar(rep)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error")}
    if not derivaciones.es_derivaciones(an):
        return {"ok": False, "es_derivaciones": False}
    d = derivaciones.analizar(r["filas"], state_dir)
    d["es_derivaciones"] = True
    return d


def armar_reporte(rep, state_dir, formato="html"):
    """El reporte, en Word o en HTML listo para imprimir a PDF."""
    # ⚠️ UNA sola lectura. El reporte se arma con el análisis COMPLETO (es para
    # marketing, y queda en esta PC), pero reporte.py ya tiene la regla de no
    # volcar valores sensibles.
    r, an, av, ls = _leer_y_analizar(rep)
    if not r.get("ok"):
        return None, r.get("error")

    titulo = rep.get("titulo") or "Reporte"
    # Lo que el equipo eligio medir ordena tambien el documento, no solo la
    # pantalla: si en el panel se ve primero «Vendedor», el Word no puede
    # arrancar por otra cosa.
    foco = medidas.columnas_del_foco(rep.get("foco"), an)
    rep = reporte.armar(an, av, ls, titulo, r.get("origen", ""), foco=foco)

    carpeta = os.path.join(state_dir, "reportes")
    os.makedirs(carpeta, exist_ok=True)
    sello = datetime.datetime.now().strftime("%Y-%m-%d")
    base = "".join(ch for ch in titulo if ch.isalnum() or ch in " -_").strip()

    if formato == "word":
        ruta = os.path.join(carpeta, "%s %s.docx" % (base, sello))
        reporte.a_word(rep, ruta)
        return ruta, None

    ruta = os.path.join(carpeta, "%s %s.html" % (base, sello))
    reporte.a_html(rep, ruta)
    return ruta, None
