# -*- coding: utf-8 -*-
import json, io, re, sys

s = io.open(r'intranet\modulos.js', encoding='utf-8').read()
mods = json.loads(s[s.index('['):s.rindex(']') + 1])

def texto(b):
    for k in ('html', 'texto', 'titulo', 'nombre'):
        v = b.get(k)
        if isinstance(v, str) and v.strip():
            return re.sub(r'<[^>]+>', '', v).strip()[:60]
    return ''

for m in mods:
    c = m.get('content') or {}
    if c.get('tipo') != 'coleccion':
        continue
    for d in c.get('docs') or []:
        if d.get('titulo', '').upper() not in ('JULIO 2026', 'JUNIO 2026'):
            continue
        print('=' * 66)
        print(d.get('titulo'), ' presentacion=', d.get('presentacion'))
        print('=' * 66)
        n = 0
        for i, b in enumerate(d.get('bloques') or []):
            t = b.get('t')
            if t == 'diapo':
                n += 1
                print('  ---- CORTE DE DIAPOSITIVA #%d  titulo=%r' % (n, b.get('titulo', '')))
            else:
                print('  %2d. %-10s %s' % (i, t, texto(b)))
        print()
