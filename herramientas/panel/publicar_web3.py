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
NUEVA_PUBLICA = "1.4.5"
NUEVO_LABEL = "1.4.5 - la marca en cada publicacion"
NUEVAS_NOTAS = ("Cada publicacion vuelve a mostrar quien la hizo: el avatar lleva el logo de Muebles y Sillones y al lado va el nombre de quien la escribio. Antes era una letra sola, o directamente no se veia. Ademas, el boton Traer ultima version aparece solo si esa computadora tiene una central configurada: sin Tailscale no tenia a donde ir y lo unico que hacia era dar un error.")

# firma de los commits que arma este guion
FIRMA = ("\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n"
         "Claude-Session: https://claude.ai/code/session_01UztbDef1C6mxrqdPB2WieL\n")

ARCHIVOS_WEB3 = ["index.html", "maqueta.css", "puente.css", "app.js", "muro.js",
                 "panel_datos.js", "panel_datos.css", "datos_puente.js",
                 "iconos-ui.js", "styles.css", "rediseno.css",
                 "logo-marca.png", "logo.png", "favicon.png"]


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
msg = ("Panel v%d (%s): la marca en el avatar de cada publicacion\n\n"
       "El avatar mostraba las iniciales del autor: una M sola, que no dice\n"
       "nada. Una publicacion de la cartelera es un aviso de la EMPRESA, asi\n"
       "que el avatar lleva el logo y el nombre de al lado es el que dice\n"
       "quien la escribio. Mismo criterio que ya se aplico en la intranet.\n"
       "#sucAv queda afuera a proposito: ese no es el autor, es que\n"
       "computadora es esta, y ahi la inicial si sirve.\n\n"
       "Ademas: Traer ultima version se muestra solo si hay una central\n"
       "configurada. Desde que las sucursales se instalan sin Tailscale,\n"
       "muchas no la tienen y el boton solo servia para dar un error.\n"
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
