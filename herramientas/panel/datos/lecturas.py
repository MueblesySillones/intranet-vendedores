# -*- coding: utf-8 -*-
"""Lo que la planilla ya dice y nadie tiene tiempo de leer.

No opina, no adivina y no proyecta. Cada lectura es una cuenta que se puede
rehacer a mano: viene con los operandos, la formula y las columnas que uso.
Si el numero no se puede sostener, la lectura no sale.

QUE SACA
  · CONCENTRACION   — una opcion que se lleva una parte grande de una lista
  · REPARTO         — cuantas veces mas tiene una opcion que otra
  · EMBUDO          — cuanto se cae entre dos etapas de una misma familia
                      (Seguimiento 1 / 2 / 3), y cuantos no empiezan nunca
  · TENDENCIA       — las ultimas N semanas contra las N anteriores
  · TOTAL, SUMA POR CATEGORIA, PROPORCION — para las columnas de cantidades

LO QUE NO HACE, A PROPOSITO
  · No cruza dos listas ("en Hudson entra mas por WhatsApp que en el resto").
    Probado contra la planilla de prueba, que es azarosa: el cruce igual
    devuelve un "hallazgo". Con cientos de combinaciones alguna siempre se
    pasa de la raya por casualidad, y desde adentro no hay con que separarla
    de una de verdad. Un numero que parece bien y esta mal es lo peor que
    puede publicar este panel.
  · No dice por que pasa algo. Que dos numeros se muevan juntos no dice cual
    mueve a cual.
  · No compara meses de calendario: el primero y el ultimo casi siempre estan
    cortados por la mitad, y la caida termina siendo del calendario y no del
    negocio. Por eso las ventanas son de N dias corridos contra los N previos.
  · No promedia una columna que tiene un valor 50 veces mas alto que el resto
    sin decirlo: el promedio se lo come el error de tipeo.

QUE DEVUELVE CADA LECTURA
  id             texto estable, para que el interruptor de publicar se acuerde
  tipo           familia de lectura (concentracion, embudo, tendencia, ...)
  texto          la frase corta, ya armada
  valor          el numero protagonista
  unidad         "%", "veces" o "" (cantidad)
  columnas       que columnas se usaron
  base           cuantas filas la respaldan
  cuenta         {operacion, operandos, formula, resultado} — para rehacerla
  peso           0-100, para ordenarlas en pantalla
  apto_publicar  si hay o no una razon TECNICA para no mandarla a la intranet
  motivo_no_apto por que, cuando no es apto
  reparos        advertencias que no invalidan el numero pero lo condicionan

`apto_publicar` no es un permiso: el interruptor de cada numero sigue apagado
hasta que una persona lo prenda (regla 3 del contrato). Es solo el filtro de
lo que NO puede irse a una pagina sin contraseña.

Las columnas con `sensible: True` no se usan para nada: ni contar, ni agrupar,
ni ejemplificar. Se descartan en la primera linea y no vuelven a aparecer.
"""
import datetime
import os
import re
import sys
from collections import Counter, defaultdict

from .analizador import _misma_escritura

# Relativo cuando corre como paquete del panel —que es como lo usa el panel—
# y absoluto cuando alguien abre el archivo suelto para probarlo.
try:
    from .analizador import _norm, _txt
except ImportError:                       # noqa: sirve al correr el archivo solo
    from analizador import _norm, _txt


# ── cuanto es "poco" ─────────────────────────────────────────────────────
# Con menos de 15 filas un porcentaje no es una conclusion, es una anecdota:
# una fila mas lo mueve 7 puntos. Y 30 es el piso para hablar de una parte del
# total sin que dos casos den vuelta el numero.
MIN_FILAS = 15
MIN_BASE = 30
MIN_VENTANA = 25          # filas por ventana para comparar dos periodos

# Columnas que nombran a alguien del equipo. Se pueden contar —el dashboard es
# privado— pero no salen a la intranet, que la ve cualquiera con el link.
PERSONA = re.compile(r"(vendedor|vendedora|operador|asesor|usuario|responsable|"
                     r"empleado|encargado|cajero|promotor)", re.I)
# Columnas que dicen QUIEN carga. Misma lista que usa el revisor para detectar
# al que dejo de cargar, por el mismo motivo: si uno se corta, el total baja
# solo por eso.
CARGA = re.compile(r"(sucursal|local|vendedor|operador|usuario|equipo|"
                   r"responsable|asesor|punto)", re.I)

# Cuanto pesa cada familia cuando todo lo demas es igual. El embudo y la
# tendencia son las dos que mueven una decision; un total es un dato de apoyo.
PESO_FAMILIA = {
    "embudo": 0.95,
    "tendencia": 0.90,
    "proporcion": 0.85,
    "concentracion": 0.80,
    "sin_empezar": 0.80,
    "reparto": 0.75,
    "suma_categoria": 0.70,
    "total": 0.35,
}

MILES = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$")


def _celda(fila, i):
    """La celda i de una fila que puede venir corta."""
    return fila[i] if i < len(fila) else ""


def _fecha(v):
    """La fecha de una celda, o None si no se entiende."""
    v = _txt(v).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", v)
    if m:
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a < 100:
            a += 2000
        try:
            return datetime.date(a, mes, d)
        except ValueError:
            return None
    return None


def _numero(v):
    """El numero de una celda, o None.

    ⚠️ El punto no siempre es separador de miles. "1.234" son mil doscientos,
    pero "12.5" son doce y medio: sacarle el punto a todo convertia un 12,5 en
    125 y el total quedaba diez veces mas grande sin que se notara. Solo se
    tratan como miles los puntos que separan grupos de tres.
    """
    if isinstance(v, bool):          # True/False no es una cantidad
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = _txt(v).strip().replace(" ", "")
    if not s:
        return None
    if MILES.match(s):
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _mil(n):
    """Como se escribe un numero aca: 1.800 y 2,4."""
    signo = "-" if n < 0 else ""
    n = abs(float(n))
    if abs(n - round(n)) < 0.005:
        cuerpo = "{:,}".format(int(round(n))).replace(",", ".")
    else:
        ent, dec = ("%.1f" % n).split(".")
        cuerpo = "{:,}".format(int(ent)).replace(",", ".") + "," + dec
    return signo + cuerpo


def _pct(x):
    """x va de 0 a 1. Entero, salvo que sea tan chico que el entero mienta.

    "se cae el 52%" se lee de una; "se cae el 52,3%" hace dudar de si el
    decimal importa. El numero fino queda igual en `valor` y en la cuenta,
    que es donde se va a mirar si alguien quiere rehacerla.
    """
    p = 100.0 * x
    if abs(p) >= 10:
        return _mil(round(p))
    return ("%.1f" % p).replace(".", ",")


def _dec(x):
    return ("%.1f" % x).replace(".", ",")


def _semanas(dias):
    """14 dias es "2 semanas": asi lo cuenta el que mira la planilla."""
    if dias % 7 == 0:
        n = dias // 7
        return "la última semana" if n == 1 else "las últimas %d semanas" % n
    return "los últimos %d días" % dias


def _semanas_previas(dias):
    if dias % 7 == 0:
        n = dias // 7
        return "la anterior" if n == 1 else "las %d anteriores" % n
    return "los %d anteriores" % dias


def _umbral_share(k):
    """Desde que parte del total una opcion deja de ser lo esperable.

    Con k opciones, "lo parejo" es 1/k. Un poco por encima de eso no es una
    lectura: que el mas cargado de 3 operadores tenga 34% no dice nada. Se pide
    un 10% mas que lo parejo y ademas un piso de 20%, porque un quinto del
    total ya es mucho aunque haya veinte opciones.
    Con dos opciones se pide 60%: un 55/45 es un empate, no una conclusion.
    """
    if k < 2:
        return 2.0                    # una sola opcion: no hay nada que comparar
    if k == 2:
        return 0.60
    return max(0.20, 1.1 / k)


def _peso(familia, fuerza, base):
    """Que tan arriba va en la pantalla. 0-100.

    Tres cosas, en este orden: que familia es, que tan lejos esta el numero de
    "no pasa nada" (fuerza, de 0 a 1) y cuantas filas lo respaldan. Lo ultimo
    no lo hace mas cierto, lo hace mas dificil de dar vuelta: el mismo 40% con
    30 filas o con 1.800 no se mira igual.
    """
    confianza = min(1.0, 0.45 + 0.55 * (base / 300.0))
    fuerza = max(0.0, min(1.0, fuerza))
    return int(round(100 * PESO_FAMILIA[familia] * (0.30 + 0.70 * fuerza) * confianza))


def _reparos_de(reparo_lista, columna, valores=(), extremos=None):
    """Los reparos de `columna` que de verdad tocan a ESTA lectura.

    ⚠️ Antes se pegaba el reparo de la columna a TODAS sus lecturas. Eso esta
    mal, y de un modo que se puede demostrar: que «SAN JUAN» este cargada dos
    veces no cambia en nada el numero de CABA, ni el total de la columna —el
    total cuenta las filas igual, se escriba como se escriba—. Lo unico que
    cambia es la cuenta del valor partido. Con la regla vieja, un espacio de
    mas al final de un valor marginal trababa las nueve lecturas de la columna.

    Toca a la lectura si la lectura NOMBRA uno de los valores partidos.

    Y para la lectura de reparto hay un caso mas, que se pasa en `extremos`
    como (piso, nmin, nmax): el valor partido puede no llamarse ni como el
    maximo ni como el minimo y aun asi cambiar la comparacion, si entero
    hubiera pasado a ser uno de los dos. Solo eso: un valor partido que
    entero queda en el medio no cambia nada, y trabar por el era la version
    exagerada del mismo error.
    """
    salida = []
    for r in reparo_lista.get(columna) or []:
        toca = any(v in r["valores"] for v in valores)
        if not toca and extremos:
            piso, nmin, nmax = extremos
            junto = r["junto"]
            toca = junto > nmax or (junto >= piso and junto < nmin)
        if toca:
            salida.append(r["texto"])
    return salida


def lecturas(filas, an, hoy=None):
    """filas[0] son los encabezados; `an` es lo que devolvio analizar().

    Devuelve la lista ordenada de la mas a la menos relevante. Si no hay nada
    que se pueda sostener, devuelve la lista vacia: eso tambien es una
    respuesta, y es mejor que rellenar la pantalla.
    """
    hoy = hoy or datetime.date.today()
    salida = []
    vistos = set()

    if not filas or len(filas) < 2 or not isinstance(an, dict) or an.get("error"):
        return salida
    if not an.get("columnas"):
        return salida

    cuerpo = filas[1:]
    total_filas = len(cuerpo)
    if total_filas < MIN_FILAS:
        return salida

    # Las sensibles se van aca y no vuelven a entrar en ninguna cuenta.
    cols = [c for c in an["columnas"] if not c.get("sensible")]
    if not cols:
        return salida

    def agregar(tipo, ident, texto, valor, unidad, columnas, base,
                operacion, operandos, formula, resultado, fuerza, reparos=None):
        clave = "%s|%s" % (tipo, ident)
        if clave in vistos:           # dos caminos a la misma lectura: una sola
            return
        vistos.add(clave)
        reparos = [r for r in (reparos or []) if r]
        motivos = []
        gente = [c for c in columnas if PERSONA.search(c)]
        if gente:
            motivos.append("Nombra a alguien del equipo (%s)." % ", ".join(gente))
        if reparos:
            # Un numero con reparo se muestra puertas adentro, pero no se manda
            # a una pagina publica donde nadie va a leer la letra chica.
            motivos.append("Tiene un reparo: %s" % reparos[0])
        motivo = " ".join(motivos)
        # Y tampoco puede encabezar la pantalla: si primero hay que arreglar la
        # planilla, la lectura baja hasta que este arreglada. Sin esto, una fila
        # con un cero de mas se lleva el titular con un "+209%" que no existe.
        peso = _peso(tipo, fuerza, base)
        if reparos:
            peso = int(round(peso * 0.7))
        salida.append({
            "id": clave,
            "tipo": tipo,
            "texto": texto,
            "valor": round(valor, 2),
            "unidad": unidad,
            "columnas": list(columnas),
            "base": base,
            "cuenta": {
                "operacion": operacion,
                "operandos": operandos,
                "formula": formula,
                "resultado": round(resultado, 2),
            },
            "peso": peso,
            "apto_publicar": not motivo,
            "motivo_no_apto": motivo,
            "reparos": reparos,
        })

    # ── 0. lo que hay para contar ────────────────────────────────────────
    #    Se recuenta desde las filas y no se usa `valores` del analizador:
    #    esa lista viene cortada en las 25 mas frecuentes, y con ella el "el
    #    que menos tiene" seria el que menos tiene DE LAS 25, que es otra cosa.
    cuentas, reparo_lista = {}, {}
    for c in cols:
        if c["tipo"] != "categoria":
            continue
        # ⚠️ Se junta el MISMO texto escrito de dos formas, igual que el
        # analizador. Sin esto, «No respondio, se insistio 3 veces» y su gemelo
        # con tildes se contaban aparte: la tarjeta del tablero decia 2.106 y
        # el reporte con diseño 3.090, para el mismo dato y en la misma
        # pantalla. Se juntan tildes, mayusculas y espacios; nada mas.
        crudas = Counter()
        for f in cuerpo:
            v = _txt(_celda(f, c["i"])).strip()
            if v:
                crudas[v] += 1
        cn, por_clave = Counter(), {}
        for v, k in crudas.items():
            por_clave.setdefault(_misma_escritura(v), Counter())[v] = k
        for formas in por_clave.values():
            cn[formas.most_common(1)[0][0]] = sum(formas.values())
        cuentas[c["nombre"]] = cn
        # ⚠️ SOLO `parecidos`, nunca `sospechosos`. `parecidos` es una
        # certeza —el mismo valor escrito dos veces— y por eso puede trabar
        # una lectura; `sospechosos` es una duda, y trabar por las dudas es
        # lo que dejaba 18 de 23 números afuera por nada.
        # ⚠️ RECORTADOS, y no como vienen del analizador. `cn` de acá cuenta
        # sobre `.strip()`, así que «SAN JUAN» y «SAN JUAN » YA están sumadas
        # en un mismo renglón y ese número no está partido en nada. El
        # analizador, que mira los valores crudos, las ve como dos: si se
        # comparan tal cual, el reparo traba una lectura que está bien.
        # Un grupo que al recortarlo queda en una sola forma no es un reparo
        # acá — sí lo sigue siendo para el revisor, que avisa de la planilla.
        reparos = []
        for g in (c.get("parecidos") or []):
            formas = []
            for v in g:
                v = _txt(v).strip()
                if v and v not in formas:
                    formas.append(v)
            if len(formas) < 2:
                continue
            reparos.append({
                "texto": ("en %s, «%s» está cargada de dos formas (%s), así "
                          "que este número está partido en dos."
                          % (c["nombre"], formas[0], " / ".join(formas[:2]))),
                "valores": set(formas),
                # cuánto pesaría el valor escrito de una sola forma: es lo que
                # decide si el reparto de la columna habría sido otro
                # sobre el contador YA juntado: buscar las formas crudas
                # ahi no encontraria nada, porque solo quedo una de cada
                "junto": sum(n for et, n in cn.items()
                             if _misma_escritura(et) in
                             {_misma_escritura(v) for v in formas}),
            })
        if reparos:
            reparo_lista[c["nombre"]] = reparos

    numericas = []
    for c in cols:
        if c["tipo"] != "numero":
            continue
        vals = []
        for n, f in enumerate(cuerpo):
            x = _numero(_celda(f, c["i"]))
            if x is not None:
                vals.append((n, x))
        if not vals:
            continue
        rep = []
        ordenados = sorted(x for _, x in vals)
        mediana = ordenados[len(ordenados) // 2]
        if mediana > 0 and ordenados[-1] > mediana * 50:
            # Mismo criterio que usa el revisor para cazar el cero de mas: si
            # ese valor esta mal, la suma y todo lo que salga de ella tambien.
            rep.append("%s tiene un valor de %s contra una mediana de %s; si es un "
                       "cero de más, la suma queda inflada."
                       % (c["nombre"], _mil(ordenados[-1]), _mil(mediana)))
        if ordenados[0] < 0:
            rep.append("%s tiene valores negativos, que se restan de la suma." % c["nombre"])
        numericas.append({"col": c, "vals": vals, "suma": sum(x for _, x in vals),
                          "reparos": rep})

    # ── 1. una opcion que se lleva una parte grande ──────────────────────
    for c in cols:
        cn = cuentas.get(c["nombre"])
        if not cn:
            continue
        base = sum(cn.values())
        k = len(cn)
        if base < MIN_BASE or k < 2:
            continue
        piso = _umbral_share(k)
        orden = sorted(cn.items(), key=lambda x: (-x[1], x[0]))
        elegidos = []
        for pos, (v, n) in enumerate(orden[:3]):
            parte = n / float(base)
            # dos motivos para decirlo: es una tajada grande del total, o es la
            # opcion de arriba y le saca mucho a lo que seria repartir parejo
            if parte >= piso or (pos == 0 and parte >= 1.5 / k and parte >= 0.10):
                elegidos.append((v, n, parte))
        for v, n, parte in elegidos[:2]:
            agregar(
                "concentracion", "%s=%s" % (c["nombre"], v),
                "En %s, %s se lleva el %s%% (%s de %s)"
                % (c["nombre"], v, _pct(parte), _mil(n), _mil(base)),
                100.0 * parte, "%", [c["nombre"]], base,
                "porcentaje",
                [{"que": "filas con %s = %s" % (c["nombre"], v), "valor": n},
                 {"que": "filas con %s cargado" % c["nombre"], "valor": base}],
                "%d / %d * 100" % (n, base), 100.0 * n / base,
                (parte - 1.0 / k) / (1.0 - 1.0 / k),
                # el porcentaje de V solo se parte si el partido es V: el
                # denominador (las filas cargadas) no depende de como se
                # escriba cada valor
                _reparos_de(reparo_lista, c["nombre"], [v]))

    # ── 2. cuanto mas tiene uno que otro ─────────────────────────────────
    for c in cols:
        cn = cuentas.get(c["nombre"])
        if not cn:
            continue
        base = sum(cn.values())
        k = len(cn)
        # con dos opciones esto ya lo dijo la lectura de arriba
        if base < MIN_BASE or k < 3:
            continue
        # Un valor que aparece cuatro veces suele ser un tipeo suelto —el
        # revisor los marca aparte—. Comparar contra eso da "500 veces mas",
        # que es cierto y no significa nada.
        piso_soporte = max(10, int(0.02 * base))
        firmes = [(v, n) for v, n in cn.items() if n >= piso_soporte]
        if len(firmes) < 2:
            continue
        vmax, nmax = sorted(firmes, key=lambda x: (-x[1], x[0]))[0]
        vmin, nmin = sorted(firmes, key=lambda x: (x[1], x[0]))[0]
        razon = nmax / float(nmin)
        if razon < 1.5:
            continue                  # menos que eso es reparto parejo
        agregar(
            "reparto", "%s:%s/%s" % (c["nombre"], vmax, vmin),
            "En %s, %s tiene %s veces lo de %s (%s vs %s)"
            % (c["nombre"], vmax, _dec(razon), vmin, _mil(nmax), _mil(nmin)),
            razon, "veces", [c["nombre"]], base,
            "razon",
            [{"que": "filas con %s = %s" % (c["nombre"], vmax), "valor": nmax},
             {"que": "filas con %s = %s" % (c["nombre"], vmin), "valor": nmin}],
            "%d / %d" % (nmax, nmin), nmax / float(nmin),
            min(1.0, (razon - 1.0) / 4.0),
            # acá además de los dos nombrados importa si un valor partido,
            # entero, habría pasado a ser el máximo o el mínimo: en dos
            # mitades pudo no llegar a `piso_soporte` y quedar afuera
            _reparos_de(reparo_lista, c["nombre"], [vmax, vmin],
                        (piso_soporte, nmin, nmax)))

    # ── 3. el embudo: familias de columnas numeradas ─────────────────────
    #     "Seguimiento 1 / 2 / 3" son la misma pregunta en tres momentos. Lo
    #     unico que se cuenta es en cuantas filas esta cargada cada una.
    familias = defaultdict(list)
    for c in cols:
        if c["tipo"] in ("fecha", "numero"):
            continue
        m = re.match(r"^(.*?)[\s_\-]*(\d+)$", _norm(c["nombre"]))
        if m and m.group(1):
            familias[m.group(1)].append((int(m.group(2)), c))

    for _, miembros in sorted(familias.items()):
        if len(miembros) < 2:
            continue
        miembros.sort(key=lambda x: x[0])
        llenos = {}
        for _, c in miembros:
            llenos[c["nombre"]] = set(
                n for n, f in enumerate(cuerpo) if _txt(_celda(f, c["i"])).strip())

        primera = miembros[0][1]["nombre"]
        sin_empezar = total_filas - len(llenos[primera])
        if len(llenos[primera]) >= MIN_BASE and sin_empezar >= 0.05 * total_filas:
            parte = sin_empezar / float(total_filas)
            agregar(
                "sin_empezar", primera,
                "El %s%% no llega ni a %s (%s de %s)"
                % (_pct(parte), primera, _mil(sin_empezar), _mil(total_filas)),
                100.0 * parte, "%", [primera], total_filas,
                "porcentaje",
                [{"que": "filas con %s vacío" % primera, "valor": sin_empezar},
                 {"que": "filas en total", "valor": total_filas}],
                "%d / %d * 100" % (sin_empezar, total_filas),
                100.0 * sin_empezar / total_filas, parte)

        for (_, ca), (_, cb) in zip(miembros, miembros[1:]):
            a, b = ca["nombre"], cb["nombre"]
            na, nb = len(llenos[a]), len(llenos[b])
            # ⚠️ Sin esto no hay embudo, hay dos columnas. Si hay filas con la
            # etapa 3 cargada y la 2 vacia, la resta no es "los que se cayeron":
            # es un numero que suena bien y no corresponde a nada. En ese caso
            # no se dice nada.
            if llenos[b] - llenos[a]:
                continue
            if na < MIN_BASE or nb >= na:
                continue
            caida = (na - nb) / float(na)
            agregar(
                "embudo", "%s>%s" % (a, b),
                "Entre %s y %s se cae el %s%% (%s → %s)"
                % (a, b, _pct(caida), _mil(na), _mil(nb)),
                100.0 * caida, "%", [a, b], na,
                "caida",
                [{"que": "filas con %s cargado" % a, "valor": na},
                 {"que": "filas con %s cargado" % b, "valor": nb}],
                "(%d - %d) / %d * 100" % (na, nb, na),
                100.0 * (na - nb) / na, caida)

    # ── 4. contra el periodo anterior ────────────────────────────────────
    fcol = next((c for c in cols if c["tipo"] == "fecha"), None)
    if fcol:
        # ⚠️ El futuro se ignora para elegir el ultimo dia. Con un año tipeado
        # mal, esa fecha imposible pasaba a ser "lo mas reciente" y las dos
        # ventanas caian en un pozo sin filas: la comparacion daba -100%.
        porfila = [_fecha(_celda(f, fcol["i"])) for f in cuerpo]
        reales = [d for d in porfila if d and d <= hoy]
        if len(reales) >= MIN_VENTANA * 2:
            fin, arranque = max(reales), min(reales)
            # Ultimo dia que cargo cada sucursal / vendedor. No depende de la
            # ventana, asi que se calcula una sola vez.
            ultimo_de = {}
            for c in cols:
                cn = cuentas.get(c["nombre"])
                if not cn or len(cn) > 25 or not CARGA.search(c["nombre"]):
                    continue
                u = {}
                for n, d in enumerate(porfila):
                    if not d or d > fin:
                        continue
                    v = _txt(_celda(cuerpo[n], c["i"])).strip()
                    if v and (v not in u or d > u[v]):
                        u[v] = d
                ultimo_de[c["nombre"]] = u
            ventanas = [v for v in (14, 28) if arranque <= fin - datetime.timedelta(days=2 * v - 1)]
            if not ventanas and arranque <= fin - datetime.timedelta(days=13):
                ventanas = [7]        # planilla corta: al menos semana contra semana
            for v in ventanas:
                ini_rec = fin - datetime.timedelta(days=v - 1)
                ini_pre = fin - datetime.timedelta(days=2 * v - 1)
                rec = [n for n, d in enumerate(porfila) if d and ini_rec <= d <= fin]
                pre = [n for n, d in enumerate(porfila) if d and ini_pre <= d < ini_rec]
                if len(rec) < MIN_VENTANA or len(pre) < MIN_VENTANA:
                    continue
                periodo = "del %s al %s" % (ini_rec.isoformat(), fin.isoformat())
                previo = "del %s al %s" % (ini_pre.isoformat(),
                                           (ini_rec - datetime.timedelta(days=1)).isoformat())

                # ⚠️ El error mas caro de todos: una sucursal que dejo de
                # cargar hace baja el total sin que se vea. El numero sigue
                # siendo cierto —esas filas no estan— pero solo dice que se
                # cargo menos, no que haya menos movimiento. No alcanza con
                # mirar si desaparecio del periodo: si se corto en el medio,
                # la ventana la agarra a medias y enmascara igual. Por eso se
                # mira desde cuando no carga.
                mudos = []
                corte = fin - datetime.timedelta(days=7)
                for c in cols:
                    u = ultimo_de.get(c["nombre"])
                    if not u:
                        continue
                    en_pre = Counter(_txt(_celda(cuerpo[n], c["i"])).strip() for n in pre)
                    for val, cant in sorted(en_pre.items()):
                        if val and cant >= 0.05 * len(pre) and u.get(val, fin) <= corte:
                            mudos.append("%s = %s no carga desde el %s; parte de la baja "
                                         "puede ser falta de carga y no menos movimiento."
                                         % (c["nombre"], val, u[val].isoformat()))

                # 4a. cuantas filas
                cambio = (len(rec) - len(pre)) / float(len(pre))
                # el reparo solo tiene sentido cuando el numero BAJA
                reparo_ventana = mudos[:1] if cambio < 0 else []
                if abs(cambio) >= 0.12:
                    agregar(
                        "tendencia", "filas|%d" % v,
                        "%s %s %s%% contra %s (%s vs %s)"
                        % (_semanas(v).capitalize(), "subieron" if cambio > 0 else "cayeron",
                           _pct(abs(cambio)), _semanas_previas(v),
                           _mil(len(rec)), _mil(len(pre))),
                        100.0 * cambio, "%", [fcol["nombre"]], len(rec) + len(pre),
                        "variacion",
                        [{"que": "filas %s" % periodo, "valor": len(rec)},
                         {"que": "filas %s" % previo, "valor": len(pre)}],
                        "(%d - %d) / %d * 100" % (len(rec), len(pre), len(pre)),
                        100.0 * (len(rec) - len(pre)) / len(pre),
                        min(1.0, abs(cambio) / 0.5), reparo_ventana)

                # 4b. cada columna de cantidades
                for nu in numericas:
                    porn = dict(nu["vals"])
                    sr = sum(porn[n] for n in rec if n in porn)
                    sp = sum(porn[n] for n in pre if n in porn)
                    if sp <= 0 or sr < 0:
                        continue
                    cam = (sr - sp) / float(sp)
                    if abs(cam) < 0.12:
                        continue
                    nom = nu["col"]["nombre"]
                    reparo_ventana = mudos[:1] if cam < 0 else []
                    agregar(
                        "tendencia", "%s|%d" % (nom, v),
                        "%s: %s %s %s%% contra %s (%s vs %s)"
                        % (nom, _semanas(v), "subió" if cam > 0 else "cayó",
                           _pct(abs(cam)), _semanas_previas(v), _mil(sr), _mil(sp)),
                        100.0 * cam, "%", [fcol["nombre"], nom], len(rec) + len(pre),
                        "variacion",
                        [{"que": "suma de %s %s" % (nom, periodo), "valor": sr},
                         {"que": "suma de %s %s" % (nom, previo), "valor": sp}],
                        "(%s - %s) / %s * 100" % (_mil(sr), _mil(sp), _mil(sp)),
                        100.0 * (sr - sp) / sp, min(1.0, abs(cam) / 0.5),
                        reparo_ventana + nu["reparos"])

    # ── 5. las cantidades: total, suma por lista y proporcion ────────────
    for nu in numericas:
        nom = nu["col"]["nombre"]
        vals, suma = nu["vals"], nu["suma"]
        if len(vals) < MIN_FILAS or suma <= 0:
            continue
        agregar(
            "total", nom,
            "%s suma %s en %s filas" % (nom, _mil(suma), _mil(len(vals))),
            suma, "", [nom], len(vals),
            "suma",
            [{"que": "suma de %s" % nom, "valor": suma},
             {"que": "filas con %s cargado" % nom, "valor": len(vals)}],
            "suma de %d filas" % len(vals), suma, 0.25, nu["reparos"])

        porn = dict(vals)
        for c in cols:
            cn = cuentas.get(c["nombre"])
            if not cn or len(cn) < 2 or len(cn) > 25:
                continue
            porval = Counter()
            usadas = 0
            for n, f in enumerate(cuerpo):
                v = _txt(_celda(f, c["i"])).strip()
                if v and n in porn:
                    porval[v] += porn[n]
                    usadas += 1
            base_suma = sum(porval.values())
            if usadas < MIN_BASE or base_suma <= 0:
                continue
            v, sv = sorted(porval.items(), key=lambda x: (-x[1], x[0]))[0]
            parte = sv / float(base_suma)
            if parte < _umbral_share(len(porval)) or sv <= 0:
                continue
            agregar(
                "suma_categoria", "%s|%s=%s" % (nom, c["nombre"], v),
                "En %s, %s junta el %s%% de %s (%s de %s)"
                % (c["nombre"], v, _pct(parte), nom, _mil(sv), _mil(base_suma)),
                100.0 * parte, "%", [c["nombre"], nom], usadas,
                "porcentaje",
                [{"que": "suma de %s con %s = %s" % (nom, c["nombre"], v), "valor": sv},
                 {"que": "suma de %s en filas con %s cargado" % (nom, c["nombre"]),
                  "valor": base_suma}],
                "%s / %s * 100" % (_mil(sv), _mil(base_suma)), 100.0 * sv / base_suma,
                (parte - 1.0 / len(porval)) / (1.0 - 1.0 / len(porval)),
                # mismo criterio que la concentración: solo importa si el
                # valor del que habla la lectura es el que está partido
                _reparos_de(reparo_lista, c["nombre"], [v]) + nu["reparos"])

    # proporcion entre dos columnas de cantidades
    for a in numericas:
        for b in numericas:
            if a["col"]["i"] == b["col"]["i"]:
                continue
            pa, pb = dict(a["vals"]), dict(b["vals"])
            juntas = [n for n in pa if n in pb]
            if len(juntas) < MIN_BASE:
                continue
            # Que una columna sea parte de la otra no se adivina por el nombre:
            # se mira si fila por fila una siempre entra adentro de la otra. Se
            # tolera un 5% de excepciones por errores de carga sueltos.
            # Esto prueba que una entra en la otra, no que sean lo mismo. Por
            # eso el texto dice "es el X% de" y nada mas: no afirma que una
            # salga de la otra, que es lo que no se puede saber desde aca.
            dentro = sum(1 for n in juntas if pa[n] <= pb[n])
            if dentro < 0.95 * len(juntas):
                continue
            sa = sum(pa[n] for n in juntas)
            sb = sum(pb[n] for n in juntas)
            if sb <= 0 or sa <= 0 or sa / float(sb) > 0.98:
                continue
            na, nb = a["col"]["nombre"], b["col"]["nombre"]
            parte = sa / float(sb)
            agregar(
                "proporcion", "%s/%s" % (na, nb),
                "%s es el %s%% de %s (%s de %s)"
                % (na, _pct(parte), nb, _mil(sa), _mil(sb)),
                100.0 * parte, "%", [na, nb], len(juntas),
                "porcentaje",
                [{"que": "suma de %s" % na, "valor": sa},
                 {"que": "suma de %s en las mismas filas" % nb, "valor": sb}],
                "%s / %s * 100" % (_mil(sa), _mil(sb)), 100.0 * sa / sb,
                0.6, a["reparos"] + b["reparos"])

    salida.sort(key=lambda l: (-l["peso"], l["id"]))
    return salida


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from analizador import analizar, leer_csv

    aqui = os.path.dirname(os.path.abspath(__file__))
    ruta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(aqui), "derivaciones_prueba.csv")
    f = leer_csv(ruta)
    for l in lecturas(f, analizar(f)):
        print("[%3d] %-12s %s" % (l["peso"], l["tipo"], l["texto"]))
        print("      %s = %g %s   (%s)"
              % (l["cuenta"]["formula"], l["cuenta"]["resultado"], l["unidad"],
                 ", ".join(l["columnas"])))
        for r in l["reparos"]:
            print("      reparo: %s" % r)
        if not l["apto_publicar"]:
            print("      no publicable: %s" % l["motivo_no_apto"])
