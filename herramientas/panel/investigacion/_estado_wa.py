# -*- coding: utf-8 -*-
import io, os, sys, json, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r"C:\Users\Redes 1\Documents\web dinamica-mys"


def cargar_texto(t):
    return json.loads(t[t.index('['):t.rindex(']') + 1])


disco = io.open(os.path.join(R, "intranet", "modulos.js"), encoding="utf-8").read()
pub = subprocess.run(["git", "show", "origin/main:intranet/modulos.js"], cwd=R,
                     capture_output=True, text=True, encoding="utf-8").stdout

for etiqueta, txt in (("EN DISCO", disco), ("PUBLICADO", pub)):
    mods = cargar_texto(txt)
    w = [x for x in mods if x.get("key") == "whatsapp"]
    print("=" * 60)
    print(etiqueta)
    print("  modulos:", len(mods))
    print("  bloques 'plantilla':", txt.count('"t": "plantilla"') + txt.count('"t":"plantilla"'))
    if w:
        c = w[0].get("content") or {}
        print("  whatsapp -> content:", c.get("tipo", "(SIN content: usa el diseno del sistema)"))
        print("  whatsapp -> bloques:", len(c.get("bloques") or []))
        print("  whatsapp -> actualizado:", w[0].get("actualizado", "(sin fecha)"))
    print("  modulos con fecha:", [x.get("key") for x in mods if x.get("actualizado")])

a, b = cargar_texto(disco), cargar_texto(pub)
print("=" * 60)
print("mismo contenido (comparando datos, no texto):", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
