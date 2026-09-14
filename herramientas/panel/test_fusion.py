# -*- coding: utf-8 -*-
"""Pruebas de fusion.py.   python test_fusion.py   (exit 1 si algo falla)

Cada caso es una situacion que pasa de verdad con varias computadoras
publicando. Los que arman sobre el modulos.js REAL del repo usan su Cartelera
y sus modulos tal cual, con un `]` suelto adentro del HTML incluido.
"""
import copy
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import fusion  # noqa: E402

REAL = os.path.join(AQUI, "..", "..", "intranet", "modulos.js")
fallas = []


def check(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  -> " + str(detalle)))
    if not cond:
        fallas.append(nombre)


def texto(p):
    return ("window.MODULES = " + json.dumps(p["modulos"], ensure_ascii=False, indent=2) + ";\n"
            "window.AJUSTES = " + json.dumps(p["ajustes"]) + ";\n"
            "window.TUTORIALES = " + json.dumps(p["tutoriales"], ensure_ascii=False) + ";\n")


def mod(key, title=None, body="x"):
    return {"key": key, "title": title or key, "builtin": False,
            "content": {"tipo": "bloques", "bloques": [body], "html": "<p>%s</p>" % body}}


def cartelera(docs):
    return {"key": "cartelera", "title": "Cartelera", "builtin": False,
            "content": {"tipo": "cartelera", "docs": docs, "papelera": []}}


def doc(i, titulo=None, cuerpo="hola"):
    return {"id": i, "titulo": titulo or i, "html": cuerpo}


def P(mods, aj=None, tut=None):
    return {"modulos": mods, "ajustes": aj or {"novedad_horas": 24}, "tutoriales": tut or []}


def keys(p):
    return [m["key"] for m in p["modulos"]]


def docs_de(p):
    for m in p["modulos"]:
        if m["key"] == "cartelera":
            return [d["id"] for d in m["content"]["docs"]]
    return None


print("lectura")
base = P([cartelera([doc("d1")]), mod("a"), mod("b")],
         tut=[{"id": "t1", "titulo": "Uno", "capitulos": []}])
raro = copy.deepcopy(base)
raro["modulos"][1]["content"]["html"] = "<p>precio [ver ] cuotas]]</p>"
p = fusion.partes(texto(raro))
check("un ] suelto en el html y TUTORIALES al final no rompen la lectura",
      p is not None and len(p["modulos"]) == 3 and p["tutoriales"][0]["id"] == "t1", p)
check("un texto que no es modulos.js da None", fusion.partes("hola") is None)

print("el caso que motivo todo: sucursal con copia vieja publica")
remota = P([cartelera([doc("d2", "de Canning"), doc("d1")]), mod("a", body="nuevo a"), mod("b"), mod("c")])
local = P([cartelera([doc("d3", "de Pinamar"), doc("d1")]), mod("a"), mod("b")])
f, inf = fusion.fusionar(base, local, remota)
check("las dos publicaciones nuevas de la cartelera quedan", set(docs_de(f)) == {"d1", "d2", "d3"}, docs_de(f))
check("el modulo que agrego otra computadora queda", "c" in keys(f), keys(f))
check("la edicion de otra computadora en 'a' queda", f["modulos"][keys(f).index("a")]["content"]["bloques"] == ["nuevo a"])
check("el informe dice que se trajo", "Cartelera: de Canning" in inf["traidos"] and "c" in inf["traidos"], inf)
check("sin choques", inf["choques"] == [], inf)

print("ediciones cruzadas")
local = P([cartelera([doc("d1")]), mod("a", body="local a"), mod("b")])
remota = P([cartelera([doc("d1")]), mod("a"), mod("b", body="remota b")])
f, inf = fusion.fusionar(base, local, remota)
ka = f["modulos"][keys(f).index("a")]["content"]["bloques"]
kb = f["modulos"][keys(f).index("b")]["content"]["bloques"]
check("cada uno conserva lo suyo", ka == ["local a"] and kb == ["remota b"], (ka, kb))

print("choque: los dos editaron el mismo modulo")
local = P([cartelera([doc("d1")]), mod("a", body="mio"), mod("b")])
remota = P([cartelera([doc("d1")]), mod("a", body="suyo"), mod("b")])
f, inf = fusion.fusionar(base, local, remota)
check("gana el que publica", f["modulos"][keys(f).index("a")]["content"]["bloques"] == ["mio"])
check("y se avisa", inf["choques"] == ["a"], inf)

print("borrados")
local = P([cartelera([doc("d1")]), mod("a"), mod("b")])
remota = P([cartelera([doc("d1")]), mod("a")])
f, _ = fusion.fusionar(base, local, remota)
check("lo que otra computadora borro y aca no se toco, se borra", keys(f) == ["cartelera", "a"], keys(f))
local = P([cartelera([]), mod("a"), mod("b")])
f, _ = fusion.fusionar(base, local, base)
check("lo que aca se borro, se borra", docs_de(f) == [], docs_de(f))
local = P([{"key": "cartelera", "title": "Cartelera", "builtin": False,
            "content": {"tipo": "cartelera", "docs": [], "papelera": [doc("d1")]}}, mod("a"), mod("b")])
remota = P([cartelera([doc("d1", cuerpo="editado alla")]), mod("a"), mod("b")])
f, inf = fusion.fusionar(base, local, remota)
cart = f["modulos"][0]["content"]
check("borrado aca + editado alla: gana la edicion y sale de la papelera",
      [d["id"] for d in cart["docs"]] == ["d1"] and cart["papelera"] == [], cart)

print("orden")
local = P([cartelera([doc("d1")]), mod("a"), mod("b"), mod("nuevo")])
remota = P([mod("b"), cartelera([doc("d1")]), mod("a")])
f, _ = fusion.fusionar(base, local, remota)
check("reordenado alla, no aca: manda el orden publicado y lo nuevo va detras de su vecino",
      keys(f) == ["b", "nuevo", "cartelera", "a"] or keys(f) == ["b", "cartelera", "a", "nuevo"], keys(f))
local = P([mod("b"), mod("a"), cartelera([doc("d1")])])
f, _ = fusion.fusionar(base, local, base)
check("reordenado aca: manda el orden local", keys(f) == ["b", "a", "cartelera"], keys(f))

print("sin base: union")
local = P([cartelera([doc("d3")]), mod("a", body="mio")])
remota = P([cartelera([doc("d2")]), mod("a", body="suyo"), mod("c")])
f, inf = fusion.fusionar(None, local, remota)
check("no se pierde nada de ningun lado", set(keys(f)) == {"cartelera", "a", "c"} and set(docs_de(f)) == {"d2", "d3"}, (keys(f), docs_de(f)))
check("lo que difiere, gana lo local", f["modulos"][keys(f).index("a")]["content"]["bloques"] == ["mio"])

print("ajustes y tutoriales")
local = P(base["modulos"], aj={"novedad_horas": 48}, tut=base["tutoriales"])
remota = P(base["modulos"], aj={"novedad_horas": 24}, tut=base["tutoriales"] + [{"id": "t2", "titulo": "Dos"}])
f, _ = fusion.fusionar(base, local, remota)
check("el ajuste cambiado aca queda y el tutorial nuevo de alla tambien",
      f["ajustes"]["novedad_horas"] == 48 and [t["id"] for t in f["tutoriales"]] == ["t1", "t2"], f)

print("sobre el modulos.js REAL")
real = fusion.partes(open(REAL, encoding="utf-8").read())
check("se lee", real is not None and len(real["modulos"]) > 5)
viejo = copy.deepcopy(real)
cart_real = next(m for m in viejo["modulos"] if m["key"] == "cartelera")
quitada = cart_real["content"]["docs"].pop(0)          # la copia vieja no tiene la ultima publicacion
local = copy.deepcopy(viejo)
next(m for m in local["modulos"] if m["key"] == "cartelera")["content"]["docs"].insert(
    0, {"id": "zzlocal", "titulo": "Nueva desde la sucursal", "html": "<p>]</p>"})
f, inf = fusion.fusionar(viejo, local, real)
ids = [d["id"] for d in next(m for m in f["modulos"] if m["key"] == "cartelera")["content"]["docs"]]
check("la publicacion de la central y la de la sucursal quedan las dos",
      quitada["id"] in ids and "zzlocal" in ids and len(ids) == len(cart_real["content"]["docs"]) + 2, ids)
check("el resto de los modulos queda identico a lo publicado",
      [m for m in f["modulos"] if m["key"] != "cartelera"] == [m for m in real["modulos"] if m["key"] != "cartelera"])
check("vuelve a leerse despues de escribirse", fusion.partes(texto(f)) == f)
check("distancia: la version de la que partio esta mas cerca que la publicada",
      fusion.distancia(viejo, local) < fusion.distancia(real, local),
      (fusion.distancia(viejo, local), fusion.distancia(real, local)))

print("")
if fallas:
    print("FALLARON %d: %s" % (len(fallas), ", ".join(fallas)))
    sys.exit(1)
print("todo ok")
