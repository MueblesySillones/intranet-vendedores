# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = json.load(io.open('2026-08-04-tabla-ordenar-buscar.json', encoding='utf-8'))
r = d.get('result') or {}
print("claves de result:", list(r.keys()))
props = r.get('propuestas') or []
for i, p in enumerate(props):
    print('#' * 70)
    print('PROPUESTA', i, '-', list(p.keys()))
    for k, v in p.items():
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)
        print('\n--- %s ---' % k.upper())
        print(s[:2600])
