import json, io, sys

def cargar(p):
    s = io.open(p, encoding='utf-8').read()
    return json.loads(s[s.index('['):s.rindex(']')+1])

for etiqueta, path in (('HEAD', sys.argv[1]), ('DISCO', sys.argv[2])):
    mods = cargar(path)
    print('=' * 64)
    print(etiqueta, '- modulos:', len(mods))
    for m in mods:
        c = m.get('content') or {}
        docs = c.get('docs')
        if docs:
            print("  [%s] BIBLIOTECA, %d docs" % (m.get('key'), len(docs)))
            for d in docs:
                bl = d.get('bloques') or []
                diapo = sum(1 for b in bl if b.get('t') == 'diapo')
                html = d.get('html') or ''
                print("     - %-40r pres=%s bloques=%3d diapo=%2d dk=%2d html=%d"
                      % (str(d.get('titulo', '?'))[:38], d.get('presentacion'),
                         len(bl), diapo, html.count('dk-slide'), len(html)))
        elif c.get('tipo') == 'bloques':
            bl = c.get('bloques') or []
            print("  [%s] bloques=%3d pres=%s dk=%d"
                  % (m.get('key'), len(bl), c.get('presentacion'),
                     (c.get('html') or '').count('dk-slide')))
