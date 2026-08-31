# -*- coding: utf-8 -*-
import json, io, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
J = (r"C:\Users\Redes 1\.claude\projects\C--Users-Redes-1"
     r"\f223039b-4d2f-4d1c-b8ac-c14d001c7fc2\subagents\workflows"
     r"\wf_86d8ed88-92b\journal.jsonl")
salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paleta_propuestas.md")
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
    if not isinstance(r, dict) or "paleta" not in str(r.get("zona", "")):
        continue
    buf.append("# DIAGNOSTICO\n" + r.get("diagnostico", ""))
    for p in r.get("propuestas", []):
        buf.append("\n\n## %s  [%s/%s]\n**Donde:** %s\n\n%s" %
                   (p.get("titulo"), p.get("impacto"), p.get("esfuerzo"),
                    p.get("donde"), p.get("propuesta")))
txt = "\n".join(buf)
io.open(salida, "w", encoding="utf-8").write(txt)
print("escrito:", salida, len(txt), "caracteres")
print("tiene BLOQUE_MINI:", "BLOQUE_MINI" in txt)
print("tiene ALIAS:", "ALIAS" in txt)
