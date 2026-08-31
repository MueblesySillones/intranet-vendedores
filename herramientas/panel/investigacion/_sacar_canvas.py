# -*- coding: utf-8 -*-
import json, io, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
J = (r"C:\Users\Redes 1\.claude\projects\C--Users-Redes-1"
     r"\f223039b-4d2f-4d1c-b8ac-c14d001c7fc2\subagents\workflows"
     r"\wf_86d8ed88-92b\journal.jsonl")
salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canvas_propuestas.md")
buf = []
for linea in io.open(J, encoding="utf-8"):
    try:
        d = json.loads(linea)
    except ValueError:
        continue
    if d.get("type") != "result":
        continue
    r = d.get("result")
    if isinstance(r, str):
        try:
            r = json.loads(r)
        except ValueError:
            continue
    if not isinstance(r, dict) or "canvas" not in str(r.get("zona", "")).lower():
        continue
    for p in r.get("propuestas", []):
        buf.append("## %s\n**Donde:** %s\n\n%s\n" %
                   (p.get("titulo"), p.get("donde"), p.get("propuesta")))
txt = "\n".join(buf)
io.open(salida, "w", encoding="utf-8").write(txt)
print("escrito:", salida, len(txt))
print("initMasEntre:", "MasEntre" in txt or "mas-entre" in txt)
