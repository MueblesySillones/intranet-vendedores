# -*- coding: utf-8 -*-
"""
PUBLICAR EL PANEL REDISEÑADO (web3 como panel principal)
=========================================================

Modelado sobre publicar_redisenio.py (el ritual probado v28→v33), pero para
el release donde web3 —la maqueta implementada— pasa a ser EL panel.

Qué hace, en orden, y frena solo si algo no cierra:

  1. chequea que nadie haya publicado mientras tanto (origin al día)
  2. chequeos previos: web3 completo, el .spec lo empaqueta, el server lo
     tiene como default
  3. sube VERSION a publicada+1 y escribe la versión pública / label / notas
  4. compila con PyInstaller
  5. arma el paquete (subir_update.py)
  6. VERIFICA adentro del zip antes de publicar (web3 viaja entero,
     el server de adentro arranca con web3, sin archivos per-máquina)
  7. commit del release (panel/) + commit del fuente + push

Uso, parado en herramientas/panel del proyecto real:

    python publicar_web3.py
"""
import io, os, re, subprocess, sys, json, zipfile, hashlib

NUEVA_VERSION = None          # se calcula: la publicada + 1
NUEVA_PUBLICA = "1.6.0"
NUEVO_LABEL = "1.6.0 - el reporte se arma preguntando"
NUEVAS_NOTAS = ("Crear un reporte ahora es contestar tres preguntas: como se llama, de que periodo (con atajos para el mes pasado, este mes o los ultimos 7 dias) y que querés que mida: el embudo, mes a mes, por sucursal, por vendedor, seguimiento enviado, el cuello de botella del precio o por que se pierden. Cada reporte creado queda como una tarjeta con tres botones: Ver reporte, Descargar PDF y Descargar Word, y los tres salen con el diseno de las laminas, no con el tablero de antes. El Word baja apaisado, una lamina por hoja. Releer la planilla no toca los reportes ya creados. Ademas, el reporte ahora dice cuantas filas dejo afuera al recortar el periodo, para que nadie piense que faltan datos al compararlo con el total.")

# firma de los commits que arma este guion
FIRMA = ("\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n"
         "Claude-Session: https://claude.ai/code/session_01UztbDef1C6mxrqdPB2WieL\n")

ARCHIVOS_WEB3 = ["index.html", "maqueta.css", "puente.css", "app.js", "muro.js",
                 "panel_datos.js", "panel_datos.css", "datos_puente.js",
                 "iconos-ui.js", "styles.css", "rediseno.css",
                 "logo-marca.png", "logo.png", "favicon.png",
                 "avatar-marca.png"]


def morir(msg):
    print("\n  FRENO: " + msg)
    print("  No se publico nada.")
    sys.exit(1)


def paso(n, txt):
    print("\n[%d] %s" % (n, txt))


aqui = os.getcwd()
if not os.path.isfile(os.path.join(aqui, "panel_server.py")):
    morir("corré esto parado en herramientas/panel del proyecto real")

# ---------------------------------------------------------------- 1. origin
paso(1, "Chequeando que nadie haya publicado mientras tanto")
repo_raiz = os.path.abspath(os.path.join(aqui, "..", ".."))
subprocess.run(["git", "fetch", "origin", "-q"], cwd=repo_raiz)
r = subprocess.run(["git", "rev-list", "--count", "HEAD..origin/main"],
                   cwd=repo_raiz, capture_output=True, text=True)
pendientes = (r.stdout or "0").strip()
if pendientes not in ("0", ""):
    morir("origin/main tiene %s commit(s) que no tenés. Hacé `git pull` antes." % pendientes)
print("    ok: main al dia")

vj = os.path.join(repo_raiz, "panel", "version.json")
if not os.path.isfile(vj):
    morir("no encuentro panel/version.json para saber que numero sigue")
pub = json.load(io.open(vj, encoding="utf-8"))
print("    publicado ahora: v%s - %s" % (pub.get("version"), pub.get("label")))
NUEVA_VERSION = int(pub.get("version", 0)) + 1
print("    la nueva va a ser la v%d" % NUEVA_VERSION)

# ---------------------------------------------------------------- 2. previos
paso(2, "Chequeos previos del rediseño")
for f in ARCHIVOS_WEB3:
    p = os.path.join(aqui, "web3", f)
    if not os.path.isfile(p):
        morir("falta web3/%s" % f)
print("    ok: web3 completo (%d archivos)" % len(ARCHIVOS_WEB3))

spec = io.open(os.path.join(aqui, "PanelMyS.spec"), encoding="utf-8").read()
if "('web3', 'web3')" not in spec:
    morir("PanelMyS.spec no empaqueta web3 (falta ('web3','web3') en datas)")
print("    ok: el .spec lo empaqueta")

ps = os.path.join(aqui, "panel_server.py")
src = io.open(ps, encoding="utf-8").read()
if 'or "web3"' not in src:
    morir('panel_server.py no arranca con web3 (falta `or "web3"` en _web_pedido)')
print("    ok: el server arranca con web3")

# ---------------------------------------------------------------- 3. version
paso(3, "Subiendo la version a %d (%s)" % (NUEVA_VERSION, NUEVA_PUBLICA))
m = re.search(r"^VERSION\s*=\s*(\d+)\s*$", src, re.M)
if not m:
    morir("no encuentro `VERSION = <n>` en panel_server.py")
actual = int(m.group(1))
print("    VERSION actual: %d" % actual)
if actual >= NUEVA_VERSION:
    morir("VERSION ya esta en %d: parece que este release ya corrio." % actual)
src = re.sub(r"^VERSION\s*=\s*\d+\s*$", "VERSION = %d" % NUEVA_VERSION, src, count=1, flags=re.M)
src = re.sub(r'^VERSION_PUBLICA\s*=\s*".*?"\s*$',
             'VERSION_PUBLICA = "%s"' % NUEVA_PUBLICA, src, count=1, flags=re.M)
src = re.sub(r'^VERSION_LABEL\s*=\s*".*?"\s*$',
             'VERSION_LABEL = "%s"' % NUEVO_LABEL, src, count=1, flags=re.M)

i = src.find("VERSION_NOTES")
if i < 0:
    morir("no encuentro VERSION_NOTES en panel_server.py")
# El cierre del bloque es el ")" que esta FUERA de las comillas: el texto de
# las notas puede traer parentesis adentro (ya paso, y cortaba el bloque a la
# mitad dejando lineas colgadas -> SyntaxError al compilar).
# ⚠️ Por lo mismo, NUEVAS_NOTAS no puede llevar comillas dobles: se escriben
# tal cual adentro de un literal y rompen panel_server.py al compilar.
k, dentro = src.index("(", i) + 1, False
while True:
    c = src[k]
    if c == '"':
        dentro = not dentro
    elif c == ")" and not dentro:
        break
    k += 1
j = src.index("\n", k)
troz = ['VERSION_NOTES = (']
palabras, linea = NUEVAS_NOTAS.split(" "), ""
for w in palabras:
    if len(linea) + len(w) > 66:
        troz.append('                 "%s "' % linea.strip())
        linea = ""
    linea += w + " "
troz.append('                 "%s")' % linea.strip())
src = src[:i] + "\n".join(troz) + src[j:]
io.open(ps, "w", encoding="utf-8", newline="").write(src)
print("    -> VERSION = %d, publica %s" % (NUEVA_VERSION, NUEVA_PUBLICA))

# ---------------------------------------------------------------- 4. compilar
paso(4, "Compilando (tarda ~60s)")
r = subprocess.run([sys.executable, "-m", "PyInstaller", "PanelMyS.spec", "--noconfirm"],
                   cwd=aqui, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stdout[-2000:]); print(r.stderr[-2000:])
    morir("PyInstaller fallo")
print("    -> dist/PanelMyS listo")

# ---------------------------------------------------------------- 5. paquete
paso(5, "Armando el paquete de actualizacion")
r = subprocess.run([sys.executable, "subir_update.py"], cwd=aqui, capture_output=True, text=True)
print("    " + (r.stdout or "").strip().replace("\n", "\n    "))
if r.returncode != 0:
    print(r.stderr[-1500:]); morir("subir_update.py fallo")

# ---------------------------------------------------------------- 6. verificar
paso(6, "Verificando el zip ANTES de publicar")
zp = os.path.join(repo_raiz, "panel", "PanelMyS-v%d.zip" % NUEVA_VERSION)
if not os.path.isfile(zp):
    morir("no se genero %s" % zp)
with zipfile.ZipFile(zp) as z:
    nombres = z.namelist()
    for f in ARCHIVOS_WEB3:
        quiero = "web3/" + f
        if not any(n.endswith(quiero) for n in nombres):
            morir("adentro del zip falta %s (revisar datas del .spec)" % quiero)
    print("    ok: web3 viaja entero (%d archivos)" % len(ARCHIVOS_WEB3))
    idxs = [n for n in nombres if n.endswith("web3/index.html")]
    idx_html = z.read(idxs[0]).decode("utf-8", "replace")
    if "maqueta.css" not in idx_html or "puente.css" not in idx_html:
        morir("el index de web3 adentro del zip no enlaza maqueta.css/puente.css")
    print("    ok: el index enlaza la maqueta y el puente")
    malos = [n for n in nombres if any(x in n.lower() for x in
             ("panel_config.json", "identity.json", "proyecto.txt", "aprobaciones/"))]
    if malos:
        morir("se colaron archivos per-maquina en el zip: %s" % malos)
    print("    ok: sin archivos per-maquina")
dec = json.load(io.open(vj, encoding="utf-8"))
sha = hashlib.sha256(io.open(zp, "rb").read()).hexdigest()
if sha != dec["sha256"] or os.path.getsize(zp) != dec["size"]:
    morir("el sha256/tamano del version.json no coincide con el zip")
print("    ok: sha256 y tamano coinciden")
if int(dec["version"]) != NUEVA_VERSION:
    morir("version.json quedo en %s y esperaba %d" % (dec["version"], NUEVA_VERSION))
print("    ok: version.json en v%d" % NUEVA_VERSION)

# ---------------------------------------------------------------- 7. publicar
paso(7, "Publicando")
subprocess.run(["git", "add", "panel"], cwd=repo_raiz, check=True)
msg = ("Panel v%d (%s): el link va al bloque, y cargar al modulo\n\n"
       "1) El bloque `ref` guardaba QUE bloque se habia elegido, pero el\n"
       "   link salia como #modulo a secas: se senalaba una galeria y al\n"
       "   vendedor lo dejaba arriba de todo. Ahora piezasDe anota la\n"
       "   posicion del bloque, bloquesHTML emite data-bi en cada uno, y\n"
       "   el link sale como #modulo/b<n>. Las publicaciones viejas, que\n"
       "   no guardaron la posicion, la resuelven por nombre.\n\n"
       "2) Cargar al modulo: copia el titulo, el cuerpo y las piezas\n"
       "   adentro del modulo como bloques. Es distinto de Archivar en un\n"
       "   modulo, que solo espeja la publicacion, y por eso es otro\n"
       "   interruptor. Va en el MISMO guardado que la publicacion, y si\n"
       "   ese guardado falla se deshacen las dos cosas. Un modulo del\n"
       "   sistema sin content estrena uno con su diseno original adentro,\n"
       "   para no borrarle lo que ya mostraba.\n\n"
       "3) El selector ahora ofrece tambien los TITULOS: son las secciones\n"
       "   del modulo, y es lo que hace util a lo anterior (se carga el\n"
       "   aviso una vez y despues se lo senala).\n\n"
       "Con suites: qa/w4 (link al bloque, 5 checks) y qa/w5 (cargar al\n"
       "modulo, 7 checks), las dos de punta a punta.\n"
       % (NUEVA_VERSION, NUEVA_PUBLICA)) + FIRMA
subprocess.run(["git", "commit", "-m", msg], cwd=repo_raiz, check=True)

# el FUENTE tambien viaja al repo: sin esto la otra compu compila otra cosa
subprocess.run(["git", "add", "--",
                "herramientas/panel/panel_server.py",
                "herramientas/panel/PanelMyS.spec",
                "herramientas/panel/web3",
                "herramientas/panel/publicar_web3.py"], cwd=repo_raiz, check=True)
subprocess.run(["git", "commit", "-m",
                "Fuente al dia con lo publicado: VERSION %d + web3 como panel principal"
                % NUEVA_VERSION + FIRMA], cwd=repo_raiz, check=True)

r = subprocess.run(["git", "push", "origin", "main"], cwd=repo_raiz, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1200:])
    morir("el push fallo. Si dice 'fetch first', alguien publico algo: `git pull` y de vuelta.")

print("\n" + "=" * 62)
print("  PUBLICADO: v%d (%s)" % (NUEVA_VERSION, NUEVA_PUBLICA))
print("  Vercel lo sirve en ~30s. Los paneles van a ver el boton")
print("  'Actualizar a la ultima version' y se instalan solos.")
print("=" * 62)
