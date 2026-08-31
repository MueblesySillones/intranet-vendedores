# -*- coding: utf-8 -*-
"""Actualiza las pruebas al comportamiento NUEVO (la paleta volvio a ser
desplegable, insertar lleva a Ajustes, y una tarjeta sin foto no se publica)."""
import io, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
D = os.path.dirname(os.path.abspath(__file__))

# helper que abre el grupo antes de tocar una tarjeta de bloque
ABRIR = """    # la paleta es desplegable: hay que abrir el grupo antes de tocar el bloque
    pag.evaluate('''(t) => { const b = document.querySelector('#gbAdd .gb-tipo[data-t="'+t+'"]');
        if (b) { const d = b.closest('details'); if (d) d.open = true; } }''', "%s")
    pag.wait_for_timeout(150)
"""

CAMBIOS = {
    "test_video_ui.py": [
        ('        # la paleta ahora es una grilla siempre visible: se toca la tarjeta directo\n'
         '        pag.click(\'#gbAdd .gb-tipo[data-t="video"]\')',
         '        # la paleta es desplegable: primero se abre el grupo\n'
         '        pag.evaluate(\'\'\'() => { const b = document.querySelector(\'#gbAdd .gb-tipo[data-t="video"]\');\n'
         '            if (b) { const d = b.closest("details"); if (d) d.open = true; } }\'\'\')\n'
         '        pag.wait_for_timeout(150)\n'
         '        pag.click(\'#gbAdd .gb-tipo[data-t="video"]\')'),
    ],
    "test_plantilla.py": [
        ('    check("arma una tarjeta por cada una", hc.count(\'class="wt-card"\') == 2)',
         '    # una tarjeta SIN foto no se publica: Meta la pide obligatoria\n'
         '    check("publica solo las tarjetas con foto", hc.count(\'class="wt-card"\') == 1,\n'
         '          "%d de 2" % hc.count(\'class="wt-card"\'))'),
        ('    check("la tarjeta sin foto muestra el marcador", \'wt-cimg"><span class="ico"><svg\' in hc)',
         '    hce = pag.evaluate("""() => plantillaHTML({t:\'plantilla\', categoria:\'utilidad\', formato:\'carrusel\',\n'
         '        encabezado:{tipo:\'ninguno\'}, cuerpo:\'Mirá estos modelos\', pie:\'\', botones:[],\n'
         '        tarjetas:[{src:\'assets/_modulos/a.png\', cuerpo:\'Berlín\', botones:[]},\n'
         '                  {src:\'\', cuerpo:\'\', botones:[]}]}, true)""")\n'
         '    check("en el editor la tarjeta sin foto se ve como hueco",\n'
         '          hce.count(\'class="wt-card"\') == 2 and \'wt-cimg"><span class="ico"><svg\' in hce)'),
        ('    pag.click(\'#gbAdd .gb-tipo[data-t="plantilla"]\')',
         '    pag.evaluate(\'\'\'() => { const b = document.querySelector(\'#gbAdd .gb-tipo[data-t="plantilla"]\');\n'
         '        if (b) { const d = b.closest("details"); if (d) d.open = true; } }\'\'\')\n'
         '    pag.wait_for_timeout(150)\n'
         '    pag.click(\'#gbAdd .gb-tipo[data-t="plantilla"]\')'),
    ],
    "test_rediseno.py": [
        ('    check("ya no hay desplegables cerrados",\n'
         '          pag.evaluate("() => document.querySelectorAll(\'#gbAdd details\').length") == 0)',
         '    # los grupos volvieron a ser desplegables (25 bloques a la vista era mucho scroll)\n'
         '    check("los grupos son desplegables",\n'
         '          pag.evaluate("() => document.querySelectorAll(\'#gbAdd details.gb-grupo\').length") >= 5)'),
        ('    check("la paleta se ve sin tener que abrir nada",\n'
         '          pag.evaluate("() => document.querySelectorAll(\'#gbAdd .gb-tipo\').length") >= 20,',
         '    pag.evaluate("() => document.querySelectorAll(\'#gbAdd details\').forEach(d => d.open = true)")\n'
         '    pag.wait_for_timeout(150)\n'
         '    check("estan todos los bloques",\n'
         '          pag.evaluate("() => document.querySelectorAll(\'#gbAdd .gb-tipo\').length") >= 20,'),
        ('    check("tras insertar sigue en la paleta (para encadenar)",\n'
         '          pag.evaluate("""() => document.querySelector(\'.gb-pane[data-pane="agregar"]\').hidden === false"""))\n'
         '    check("...pero avisa que hay ajustes nuevos",\n'
         '          pag.evaluate("() => document.querySelector(\'#gbTabAjustes\').classList.contains(\'avisa\')"))',
         '    # al insertar se pasa DERECHO a los ajustes del bloque nuevo\n'
         '    check("tras insertar se abren sus ajustes",\n'
         '          pag.evaluate("""() => document.querySelector(\'.gb-pane[data-pane="ajustes"]\').hidden === false"""))\n'
         '    check("y el titulo dice cual es",\n'
         '          "Ajustes de:" in (pag.text_content("#gbInspTitle") or ""))'),
    ],
    "test_nuevas.py": [
        ('    check("sin fechas de cambio, no molesta a nadie",\n'
         '          web.evaluate("() => document.getElementById(\'novedades\').hidden"))',
         '    # se limpian las fechas que pueda tener el contenido real del usuario\n'
         '    web.evaluate("""() => { Object.values(MODMAP).forEach(m => delete m.actualizado);\n'
         '                            renderBotonera(); }""")\n'
         '    web.wait_for_timeout(300)\n'
         '    check("sin fechas de cambio, no molesta a nadie",\n'
         '          web.evaluate("() => document.getElementById(\'novedades\').hidden"))'),
    ],
    "test_arrastre_y_diapos.py": [
        ('    grupos = pag.evaluate("""() => [...document.querySelectorAll(\'#gbAdd .gb-grupo-t\')].map(s => s.textContent.trim())""")',
         '    # el rotulo ahora trae el contador al lado, se compara por el nombre solo\n'
         '    grupos = pag.evaluate("""() => [...document.querySelectorAll(\'#gbAdd .gb-grupo-t\')]\n'
         '        .map(s => (s.firstChild ? s.firstChild.textContent : s.textContent).trim())""")'),
    ],
}

for archivo, pares in CAMBIOS.items():
    p = os.path.join(D, archivo)
    c = io.open(p, encoding="utf-8").read()
    n = 0
    for viejo, nuevo in pares:
        if viejo in c:
            c = c.replace(viejo, nuevo, 1)
            n += 1
    io.open(p, "w", encoding="utf-8", newline="").write(c)
    print("%-28s %d de %d" % (archivo, n, len(pares)))
