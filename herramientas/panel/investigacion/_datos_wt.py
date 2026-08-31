# -*- coding: utf-8 -*-
import io, os, sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
R = r"C:\Users\Redes 1\Documents\web dinamica-mys"
s = io.open(os.path.join(R, "intranet", "modulos.js"), encoding="utf-8").read()
mods = json.loads(s[s.index('['):s.rindex(']') + 1])
w = [x for x in mods if x.get("key") == "whatsapp"][0]
for i, b in enumerate(w["content"]["bloques"]):
    if b.get("t") == "plantilla":
        print("bloque #%d" % i)
        print(json.dumps(b, ensure_ascii=False, indent=1))
