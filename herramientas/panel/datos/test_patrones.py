# -*- coding: utf-8 -*-
"""Las reglas de los PATRONES de comportamiento, dichas por el usuario (27-sep-2026).

Cada caso usa textos que están de verdad en la planilla.
    python datos/test_patrones.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datos.derivaciones import patron_de, monto_de   # noqa: E402

RES = []


def caso(nombre, s1, s2, final, esperado):
    got = patron_de(s1, s2, final)
    ok = got == esperado
    RES.append(ok)
    print("%s | %s | %s" % ("PASS" if ok else "FAIL", nombre,
                            got if ok else "dio %r, se esperaba %r" % (got, esperado)))


# «se le hizo seguimiento, nunca nos respondió; marketing le envió una
# plantilla, pero tampoco respondió: el cliente nunca respondió para nada»
caso("nunca respondió, ni a la plantilla",
     "No respondio el primer mensaje, se le volvio a insistir",
     "Se le envió TEMPLATE de seguimiento",
     "No respondio, se insistio 3 veces", "nunca_plantilla")
caso("nunca respondió (sin plantilla)",
     "No respondio el primer mensaje, se le volvio a insistir",
     "No respondió, se le volvió a escribir",
     "No respondio, se insistio 3 veces", "nunca")
# «en el seguimiento 1 dijo que iba a pasar por la sucursal, pero la respuesta
# final fue que no respondió… por más que nos prometió que iba a pasar»
caso("prometió pasar y no volvió",
     "Quedo en pasar en los proximos dias", "",
     "No respondio, se insistio 3 veces", "prometio")
caso("recibió el precio y dejó de responder",
     "Despues del precio dejó en visto", "Se le envió TEMPLATE de seguimiento",
     "No respondio, se insistió 3 veces", "precio_silencio")
caso("«tiene el precio, lo analiza» cuenta como recibió el precio",
     "Tiene el precio, lo analiza", "", "No respondio, se insistio 3 veces",
     "precio_silencio")
# «no respondieron la primera, después quedaron en analizar, y la respuesta
# final es que está fuera de su presupuesto: recibió la información, la
# analizó y está fuera de su presupuesto»
caso("lo analizó y quedó fuera de presupuesto",
     "No respondio el primer mensaje, se le volvio a insistir",
     "Tiene el precio, lo analiza",
     "Fuera de su presupuesto, se le ofrecio opciones", "presupuesto_luego")
caso("fuera de presupuesto de entrada",
     "Esta fuera de su presupuesto", "Esta fuera de su presupuesto",
     "Fuera de su presupuesto, se le ofrecio opciones", "presupuesto_ya")
# «el cliente dice que está fuera de su presupuesto, le enviamos la plantilla y
# nunca respondió: ya es un cliente fuera de presupuesto, casi cerrado»
caso("dijo presupuesto, plantilla, silencio → fuera de presupuesto",
     "Esta fuera de su presupuesto", "Se le envió TEMPLATE de seguimiento",
     "No respondio, se insistio 3 veces", "presupuesto_ya")
# «puede haber comportamientos incompletos… al menos debería pasar»
caso("incompleto: solo la respuesta final", "", "", "Compro en otro lugar", "otro_lugar")
caso("incompleto: solo el seguimiento 1", "Tiene el precio, lo analiza", "", "", "proceso")
caso("sin ningún dato no es un patrón", "", "", "", None)
caso("compró después de prometer pasar",
     "Quedo en pasar en los proximos dias", "Quedo en pasar en los proximos dias",
     "Realizo la compra", "compro_prometio")

# «es un monto recaudado mensual»
for texto, n in (("$59.262.016", 59262016), ("$ 1.234,50", 1234), ("", 0), ("abc", 0)):
    ok = monto_de(texto) == n
    RES.append(ok)
    print("%s | el monto %r se lee como %s" % ("PASS" if ok else "FAIL", texto, monto_de(texto)))

# Lugares (27-sep-2026): Rosario y Paraná son de OTRA provincia, no «lejos» en Buenos Aires
from datos import zonas   # noqa: E402
for lugar, prov in (("ROSARIO", "Santa Fe"), ("Paraná", "Entre Ríos"), ("NEUQUEN", "Neuquén"),
                    ("LA PLATA", None), ("ZONA NORTE", None)):
    ok = zonas.provincia_del_lugar(lugar) == prov
    RES.append(ok)
    print("%s | %s es de %s" % ("PASS" if ok else "FAIL", lugar,
                                zonas.provincia_del_lugar(lugar) or "Buenos Aires"))
ok = zonas.clasificar("ROSARIO", "Hudson")[0] == "interior"
RES.append(ok)
print("%s | Rosario cuenta como interior del país" % ("PASS" if ok else "FAIL"))

# Origen (27-sep-2026): «web es de la página, mailing del mailing, el resto
# —promo de envío, streaming session— son anuncios»; «Web Promo» es la sección
# de promos de la web; «Campaña MKT Respuesta» no es un anuncio.
from datos.derivaciones import grupo_de_origen   # noqa: E402
for valor, grupo in (("WEB", "web"), ("Web Promo", "web"), ("MAILING", "mailing"),
                     ("PROMO ENVÍOS", "anuncio"), ("STREAMING SESSION", "anuncio"),
                     ("PROMO ESQUINEROS Y SILLONES", "anuncio"),
                     ("CAMPAÑA MKT RESPUESTA", "accion"), ("SUC. POLO", "sucursal"),
                     ("", None)):
    ok = grupo_de_origen(valor) == grupo
    RES.append(ok)
    print("%s | origen %r es %s" % ("PASS" if ok else "FAIL", valor, grupo_de_origen(valor)))

print("\n%d/%d PASS" % (sum(RES), len(RES)))
sys.exit(0 if all(RES) else 1)
