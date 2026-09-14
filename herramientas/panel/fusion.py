# -*- coding: utf-8 -*-
"""Fusion de contenido: que publicar desde una computadora NO borre lo que
publicaron las otras.

EL PROBLEMA (14-sep-2026). Cada computadora tiene su copia de intranet/ y al
publicar sube modulos.js ENTERO. El cerebro no fusiona nada: reemplaza el
archivo. Una sucursal con la copia de hace una semana que publica un cambio
chiquito se lleva puestos todos los modulos y las publicaciones de la cartelera
que el resto subio en esa semana. Y a las sucursales sin central ni siquiera
se les mostraba el boton para traer la ultima version.

LA IDEA: fusion de tres versiones, como hace git.
  · base   = lo publicado de lo que partio esta computadora
  · local  = lo que tiene ahora (con sus cambios)
  · remota = lo que esta publicado hoy
Para cada cosa: si esta computadora no la toco, gana lo publicado; si la toco
y lo publicado no cambio, gana la local; si cambiaron las dos igual, da lo
mismo; si cambiaron las dos distinto, gana la local (es quien esta publicando
ahora) y se anota como choque para avisarlo.

"Cada cosa" es fina a proposito: cada MODULO por su `key`, y adentro de los
modulos con lista de documentos (la Cartelera, el Reporte de metricas) cada
PUBLICACION por su `id`. Asi dos sucursales que publican en la Cartelera el
mismo dia suman las dos publicaciones en vez de pisarse. El contenido de un
modulo de bloques se trata entero: `bloques` y `html` van juntos (el html sale
de los bloques) y mezclarlos de dos versiones daria un modulo que no existe.

SIN BASE (una computadora que nunca guardo de donde partio): se hace UNION.
Lo que hay de un solo lado queda; lo que esta en los dos y difiere, gana la
local. No se pierde nada; lo peor que pasa es que algo que otro borro vuelva a
aparecer.

Este archivo no toca disco ni red: recibe textos y devuelve estructuras. Asi
se prueba solo (test_fusion.py).
"""
import json

AUSENTE = object()          # "esta clave / este elemento no existe de este lado"
LISTAS_POR_ID = ("docs", "papelera")


# ---------------------------------------------------------------- lectura
def _valor_de(txt, nombre, abre):
    """El valor JSON que sigue a `window.<nombre>` (ver `_lista_de` en
    panel_server: se usa el decodificador de JSON, nunca contar corchetes)."""
    k = txt.find("window." + nombre)
    if k == -1:
        return None
    i = txt.find(abre, k)
    if i == -1:
        return None
    try:
        valor, _fin = json.JSONDecoder().raw_decode(txt, i)
    except ValueError:
        return None
    return valor


def partes(txt):
    """modulos.js -> {"modulos": [...], "ajustes": {...}, "tutoriales": [...]}.
    None si el texto no es un modulos.js legible (jamas se fusiona a ciegas)."""
    if not isinstance(txt, str) or not txt.strip():
        return None
    mods = _valor_de(txt, "MODULES", "[")
    if not isinstance(mods, list):
        return None
    aj = _valor_de(txt, "AJUSTES", "{")
    tut = _valor_de(txt, "TUTORIALES", "[")
    return {
        "modulos": mods,
        "ajustes": aj if isinstance(aj, dict) else {},
        "tutoriales": tut if isinstance(tut, list) else [],
    }


def galerias(txt):
    """galerias.js -> set de rutas 'assets/<seccion>/<archivo>'. None si no se lee."""
    if not isinstance(txt, str):
        return None
    d = _valor_de(txt, "GALLERIES", "{")
    if not isinstance(d, dict):
        return None
    out = set()
    for lista in d.values():
        for it in (lista if isinstance(lista, list) else []):
            if isinstance(it, dict) and isinstance(it.get("file"), str):
                out.add(it["file"])
    return out


def _igual(a, b):
    if a is AUSENTE or b is AUSENTE:
        return a is b
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == \
        json.dumps(b, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------- fusion
class Informe(object):
    """Lo que la fusion trajo de afuera y donde hubo choque. Son NOMBRES para
    mostrarle a una persona, no claves internas."""

    def __init__(self):
        self.traidos = []
        self.choques = []

    def a_dict(self):
        def unicos(xs):
            vistos, out = set(), []
            for x in xs:
                if x not in vistos:
                    vistos.add(x)
                    out.append(x)
            return out
        return {"traidos": unicos(self.traidos), "choques": unicos(self.choques)}


def _tres(b, l, r):
    """Decision de tres versiones de un valor atomico. Devuelve (valor, origen)
    con origen en 'igual' | 'local' | 'remota' | 'choque'."""
    if _igual(l, r):
        return l, "igual"
    if b is not AUSENTE and _igual(l, b):
        return r, "remota"
    if b is not AUSENTE and _igual(r, b):
        return l, "local"
    if b is AUSENTE and l is AUSENTE:
        return r, "remota"          # union: solo existe publicado -> se suma
    if b is AUSENTE and r is AUSENTE:
        return l, "local"           # union: solo existe aca -> queda
    # cambiaron los dos. Borrado de un lado y editado del otro: gana la
    # edicion (borrar de mas es peor que dejar de mas)
    if l is AUSENTE:
        return r, "choque"
    return l, "choque"


def _orden(base, local, remota, finales):
    """Orden del resultado. Si esta computadora no reordeno, manda el orden
    publicado; si reordeno, el suyo. Lo que falta en ese esqueleto se inserta
    detras de su vecino en la otra lista."""
    fin = set(finales)
    b = [k for k in base if k in fin]
    lo = [k for k in local if k in fin]
    re_ = [k for k in remota if k in fin]
    if base and [k for k in lo if k in set(b)] != [k for k in b if k in set(lo)]:
        esqueleto, otra = lo, re_
    else:
        esqueleto, otra = re_, lo
    out = list(esqueleto)
    puestos = set(out)
    for i, k in enumerate(otra):
        if k in puestos:
            continue
        pos = 0
        for j in range(i - 1, -1, -1):
            if otra[j] in puestos:
                pos = out.index(otra[j]) + 1
                break
        out.insert(pos, k)
        puestos.add(k)
    for k in finales:               # lo que no esta en ninguna de las dos listas
        if k not in puestos:
            out.append(k)
            puestos.add(k)
    return out


def _nombre(item, clave, contexto=""):
    if not isinstance(item, dict):
        return contexto or "?"
    n = item.get("title") or item.get("titulo") or item.get(clave) or "?"
    return ("%s: %s" % (contexto, n)) if contexto else str(n)


def _fusionar_lista(base, local, remota, clave, informe, contexto, fusionar_item):
    """Listas de dicts identificados por `clave`. base None = union."""
    def indice(lista):
        d, orden = {}, []
        for it in (lista if isinstance(lista, list) else []):
            if isinstance(it, dict) and it.get(clave) is not None:
                k = str(it.get(clave))
                if k not in d:
                    d[k] = it
                    orden.append(k)
        return d, orden

    bd, bo = indice(base) if base is not None else ({}, [])
    ld, lo = indice(local)
    rd, ro = indice(remota)
    resultado = {}
    for k in _unicos(lo + ro + bo):
        b = bd.get(k, AUSENTE) if base is not None else AUSENTE
        l, r = ld.get(k, AUSENTE), rd.get(k, AUSENTE)
        valor = fusionar_item(b, l, r, informe, contexto)
        if valor is not AUSENTE:
            resultado[k] = valor
    orden = _orden(bo, lo, ro, list(resultado.keys()))
    return [resultado[k] for k in orden]


def _unicos(xs):
    vistos, out = set(), []
    for x in xs:
        if x not in vistos:
            vistos.add(x)
            out.append(x)
    return out


def _anotar(origen, valor_l, valor_r, b, informe, clave, contexto):
    if origen == "remota":
        informe.traidos.append(_nombre(valor_r if valor_r is not AUSENTE else b, clave, contexto))
    elif origen == "choque":
        informe.choques.append(_nombre(valor_l if valor_l is not AUSENTE else valor_r, clave, contexto))


def _fusionar_doc(b, l, r, informe, contexto):
    valor, origen = _tres(b, l, r)
    _anotar(origen, l, r, b, informe, "id", contexto)
    return valor


def _fusionar_modulo(b, l, r, informe, _contexto=""):
    """Un modulo. Si los tres lados son modulos (dicts) se fusiona campo por
    campo, y el `content` con documentos se fusiona publicacion por publicacion."""
    if _igual(l, r):
        return l
    todos_dict = all(x is AUSENTE or isinstance(x, dict) for x in (b, l, r))
    if not (todos_dict and l is not AUSENTE and r is not AUSENTE):
        valor, origen = _tres(b, l, r)
        _anotar(origen, l, r, b, informe, "key", "")
        return valor
    titulo = _nombre(l, "key")
    out = {}
    bdict = b if isinstance(b, dict) else None
    for campo in _unicos(list(l.keys()) + list(r.keys()) + (list(bdict.keys()) if bdict else [])):
        cb = bdict.get(campo, AUSENTE) if bdict is not None else AUSENTE
        cl, cr = l.get(campo, AUSENTE), r.get(campo, AUSENTE)
        if campo == "content" and _tiene_docs(cl) and _tiene_docs(cr):
            valor = _fusionar_content_docs(cb, cl, cr, informe, titulo, bdict is not None)
        else:
            valor, origen = _tres(cb, cl, cr)
            if origen == "remota":
                informe.traidos.append(titulo)
            elif origen == "choque":
                informe.choques.append(titulo)
        if valor is not AUSENTE:
            out[campo] = valor
    return out


def _tiene_docs(c):
    return isinstance(c, dict) and isinstance(c.get("docs"), list)


def _fusionar_content_docs(cb, cl, cr, informe, titulo, hay_base):
    out = {}
    cbd = cb if (hay_base and isinstance(cb, dict)) else None
    for campo in _unicos(list(cl.keys()) + list(cr.keys()) + (list(cbd.keys()) if cbd else [])):
        vb = cbd.get(campo, AUSENTE) if cbd is not None else AUSENTE
        vl, vr = cl.get(campo, AUSENTE), cr.get(campo, AUSENTE)
        if campo in LISTAS_POR_ID and (isinstance(vl, list) or isinstance(vr, list)):
            base_lista = (vb if isinstance(vb, list) else []) if cbd is not None else None
            out[campo] = _fusionar_lista(
                base_lista,
                vl if isinstance(vl, list) else [],
                vr if isinstance(vr, list) else [],
                "id", informe, titulo if campo == "docs" else titulo + " (papelera)",
                _fusionar_doc)
            continue
        valor, origen = _tres(vb, vl, vr)
        if origen == "remota":
            informe.traidos.append(titulo)
        elif origen == "choque":
            informe.choques.append(titulo)
        if valor is not AUSENTE:
            out[campo] = valor
    # una publicacion que quedo viva en `docs` no puede estar tambien en la
    # papelera (pasa si aca se borro y alla se edito: gana la edicion)
    if isinstance(out.get("docs"), list) and isinstance(out.get("papelera"), list):
        vivos = set(str(d.get("id")) for d in out["docs"] if isinstance(d, dict))
        out["papelera"] = [d for d in out["papelera"]
                           if not (isinstance(d, dict) and str(d.get("id")) in vivos)]
    return out


def _fusionar_ajustes(b, l, r, informe):
    out = {}
    bd = b if isinstance(b, dict) else None
    for k in _unicos(list(l.keys()) + list(r.keys()) + (list(bd.keys()) if bd else [])):
        vb = bd.get(k, AUSENTE) if bd is not None else AUSENTE
        valor, origen = _tres(vb, l.get(k, AUSENTE), r.get(k, AUSENTE))
        if origen == "remota":
            informe.traidos.append("Ajustes del sitio")
        elif origen == "choque":
            informe.choques.append("Ajustes del sitio")
        if valor is not AUSENTE:
            out[k] = valor
    return out


def fusionar(base, local, remota):
    """Fusiona tres `partes()`. base puede ser None (union).
    Devuelve (partes_fusionadas, informe_dict)."""
    inf = Informe()
    hay = base is not None
    mods = _fusionar_lista(base["modulos"] if hay else None, local["modulos"],
                           remota["modulos"], "key", inf, "", _fusionar_modulo)
    aj = _fusionar_ajustes(base["ajustes"] if hay else None, local["ajustes"],
                           remota["ajustes"], inf)

    def fus_tut(b, l, r, informe, contexto):
        valor, origen = _tres(b, l, r)
        if origen == "remota":
            informe.traidos.append("Tutorial: " + _nombre(r if r is not AUSENTE else b, "id"))
        elif origen == "choque":
            informe.choques.append("Tutorial: " + _nombre(l if l is not AUSENTE else r, "id"))
        return valor

    tut = _fusionar_lista(base["tutoriales"] if hay else None, local["tutoriales"],
                          remota["tutoriales"], "id", inf, "", fus_tut)
    return {"modulos": mods, "ajustes": aj, "tutoriales": tut}, inf.a_dict()


def iguales(a, b):
    return a is not None and b is not None and _igual(a, b)


def distancia(candidata, local):
    """Cuantas piezas (modulos, y publicaciones adentro de los que tienen) estan
    de un solo lado entre una version publicada y la copia local. Sirve para
    adivinar de que version partio una computadora que nunca lo anoto: es la
    mas cercana a lo que tiene.

    ⚠️ Cuenta lo que FALTA de los dos lados, no solo lo que coincide. Contando
    coincidencias, la version de la que partio y una posterior con una
    publicacion mas EMPATAN (la copia local no tiene esa publicacion, asi que
    no suma en ninguna) y elegir la posterior como base haria creer que esta
    computadora la borro: se borraria al publicar. En un empate, quien llama
    elige la version MAS VIEJA: equivocarse para ese lado resucita algo, no
    borra nada."""
    def piezas(p):
        out = set()
        for m in p["modulos"]:
            if not isinstance(m, dict):
                continue
            c = m.get("content")
            if _tiene_docs(c):
                sin_docs = dict(m)
                sin_docs["content"] = {k: v for k, v in c.items() if k not in LISTAS_POR_ID}
                out.add(json.dumps(sin_docs, sort_keys=True, ensure_ascii=False))
                for d in c.get("docs") or []:
                    out.add(json.dumps(d, sort_keys=True, ensure_ascii=False))
            else:
                out.add(json.dumps(m, sort_keys=True, ensure_ascii=False))
        for t in p["tutoriales"]:
            out.add(json.dumps(t, sort_keys=True, ensure_ascii=False))
        return out
    return len(piezas(candidata) ^ piezas(local))
