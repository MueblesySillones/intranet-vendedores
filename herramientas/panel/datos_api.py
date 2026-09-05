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

from datos import (analizador, deck, deck_word, derivaciones, encabezado,
                   fuentes, lecturas, medidas, reporte, revisor)

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


def informe_nuevo(rep, nombre, desde, hasta, secciones=None):
    """Suma un informe al reporte. Devuelve (informe, error)."""
    nombre = (nombre or "").strip()
    if not nombre:
        return None, "Ponele un nombre al informe."
    for c, q in (("desde", desde), ("hasta", hasta)):
        if q and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(q)):
            return None, "La fecha «%s» no está bien escrita." % q
    if desde and hasta and str(desde) > str(hasta):
        return None, "El desde tiene que ser anterior al hasta."
    validas = set(deck.TODAS)
    elegidas = [x for x in (secciones or []) if x in validas]
    if not elegidas:
        return None, "Elegí al menos una cosa para medir."
    inf = {
        "id": "i" + hashlib.md5(
            (str(datetime.datetime.now()) + os.urandom(4).hex()).encode()).hexdigest()[:10],
        "nombre": nombre,
        "desde": str(desde or ""),
        "hasta": str(hasta or ""),
        # se guardan EN EL ORDEN del reporte, no en el que se tildaron
        "secciones": [k for k in deck.TODAS if k in elegidas],
        "creado": datetime.date.today().isoformat(),
    }
    rep.setdefault("informes", []).insert(0, inf)   # el último arriba
    return inf, None


def informe_borrar(rep, iid):
    antes = informes(rep)
    rep["informes"] = [i for i in antes if i.get("id") != iid]
    return len(rep["informes"]) != len(antes)


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
        hasta_f=_fecha_de((informe or {}).get("hasta")))
    if not d.get("ok"):
        return None, d.get("error")
    titulo = ((informe or {}).get("nombre")
              or rep.get("titulo") or "Derivaciones y ventas")
    return deck.armar(d, titulo, (informe or {}).get("secciones")), None


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
        hasta_f=_fecha_de((informe or {}).get("hasta")))
    if not d.get("ok"):
        return None, d.get("error")
    titulo = ((informe or {}).get("nombre")
              or rep.get("titulo") or "Derivaciones y ventas")
    carpeta = os.path.join(state_dir, "reportes")
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta)
    ruta = os.path.join(carpeta, deck_word.nombre_archivo(titulo))
    deck_word.a_word(d, ruta, titulo, (informe or {}).get("secciones"))
    return ruta, None


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
