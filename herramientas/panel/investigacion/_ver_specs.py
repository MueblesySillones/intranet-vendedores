# -*- coding: utf-8 -*-
import json, io, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
d = json.load(io.open('2026-08-04-bug-presentacion-y-bloque-video.json', encoding='utf-8'))
for i, s in enumerate(d['result']['specs']):
    print('#' * 70)
    print('SPEC', i)
    print('#' * 70)
    print('RESUMEN:', s['resumen'][:2000])
    print()
    print('RIESGOS:', json.dumps(s.get('riesgos'), ensure_ascii=False, indent=1)[:1500])
    print()
    for c in s.get('cambios', []):
        if isinstance(c, dict):
            print(' -', json.dumps({k: (str(v)[:200]) for k, v in c.items()
                                    if 'codigo' not in k.lower()},
                                   ensure_ascii=False))
        else:
            print(' -', str(c)[:250])
    print()
