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
NUEVA_PUBLICA = "1.31.1"
NUEVO_LABEL = "1.31.1 - las fotos pesan 75% menos"
NUEVAS_NOTAS = ("LAS FOTOS PESAN 75 POR CIENTO MENOS: las placas se guardaban en PNG. Medido: 90 placas ocupaban 70 de los 112 MB de TODO el material de la intranet. Ahora se guardan en JPG de calidad alta, sin el submuestreo de color que emborrona los textos de colores. Sobre las placas reales del sitio: de 1428 KB a 296 KB, con una diferencia por pixel de menos de 1 punto sobre 255, o sea que no se ve. Ademas bajan mucho mas rapido en el celular del vendedor. Lo unico que se sigue guardando en PNG es lo que tiene transparencia de verdad, como un logo recortado, porque el JPG no la soporta y quedaria con fondo blanco. Las fotos que ya estan subidas no se tocan: siguen viendose igual.")

# El cuerpo del commit del release. Vacio = se usa NUEVAS_NOTAS, que ya
# describe esta version. Antes esto era un texto fijo mas abajo y habia que
# acordarse de cambiarlo: la v42 se publico con el titulo de la v41, contando
# cambios que no eran los suyos. Un commit que describe otra version manda a
# leer el codigo equivocado, asi que ahora el default no puede quedar viejo.
NUEVO_CUERPO = ""

# firma de los commits que arma este guion
FIRMA = ("\n\nCo-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>\n"
         "Claude-Session: https://claude.ai/code/session_0196UcFB1vXvn57qLw8rSPAa\n")

ARCHIVOS_WEB3 = ["index.html", "maqueta.css", "puente.css", "app.js", "muro.js",
                 "panel_datos.js", "panel_datos.css", "datos_puente.js",
                 "tutoriales.js",
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

# ------------------------------------------------ 3b. la clave del equipo, adentro
# Decision del dueno (15-sep-2026): la clave viaja en el programa, asi una PC
# sin clave se arregla con Actualizar. NO va al codigo fuente (repo publico):
# se genera clave_equipo.py (gitignoreado) desde clave-equipo.iss y se verifica
# contra el cerebro antes de compilar.
paso(3, "Poniendo la clave del equipo adentro del programa")
_iss = os.path.join(aqui, "clave-equipo.iss")
if not os.path.isfile(_iss):
    morir("falta clave-equipo.iss: el programa saldria sin la clave del equipo")
_m = re.search(r'#define\s+PubKey\s+"([^"]+)"', io.open(_iss, encoding="utf-8-sig").read())
if not _m:
    morir("clave-equipo.iss no tiene #define PubKey")
CLAVE = _m.group(1).strip()
import urllib.request as _ur, urllib.error as _ue
try:
    with _ur.urlopen(_ur.Request("https://mys-cerebro.mueblesysillones.workers.dev/audit",
                                 headers={"Authorization": "Bearer " + CLAVE,
                                          "User-Agent": "PanelMyS/1.0"}), timeout=20) as _r:
        _cod = _r.status
except _ue.HTTPError as _e:
    _cod = _e.code
if _cod != 200:
    morir("el cerebro rechaza la clave de clave-equipo.iss (HTTP %s)" % _cod)
io.open(os.path.join(aqui, "clave_equipo.py"), "w", encoding="utf-8").write(
    "# Generado por publicar_web3.py desde clave-equipo.iss. NO SUBIR A GIT.\n"
    "CLAVE = %r\n" % CLAVE)
_gi = io.open(os.path.join(aqui, "..", ".gitignore"), encoding="utf-8").read()
if not subprocess.run(["git", "check-ignore", "-q", os.path.join(aqui, "clave_equipo.py")], cwd=repo_raiz).returncode == 0:
    morir("clave_equipo.py no esta en herramientas/.gitignore: se subiria al repo")
print("    ok: la clave la acepta el cerebro y va adentro (clave_equipo.py, fuera de git)")

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
             ("panel_config.json", "identity.json", "proyecto.txt", "aprobaciones/",
              "clave-equipo.iss"))]
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

# ------------------------------------------------------- 6b. que el exe arranque
# Un modulo que PyInstaller no empaqueto (fusion.py, por ejemplo, que se importa
# al cargar) no se ve en el zip: el exe revienta recien al abrirlo, en todas las
# computadoras a la vez. Se abre el exe compilado en una carpeta de prueba y
# tiene que contestar con la version nueva.
paso(6, "Abriendo el exe compilado en una carpeta de prueba")
import shutil, socket, tempfile, time, urllib.request
prueba = tempfile.mkdtemp(prefix="exe-release-")
try:
    os.makedirs(os.path.join(prueba, "p", "intranet"))
    os.makedirs(os.path.join(prueba, "p", "herramientas"))
    os.makedirs(os.path.join(prueba, "e"))
    for f in ("index.html", "modulos.js", "galerias.js"):
        shutil.copy2(os.path.join(repo_raiz, "intranet", f), os.path.join(prueba, "p", "intranet", f))
    so = socket.socket(); so.bind(("127.0.0.1", 0)); puerto = so.getsockname()[1]; so.close()
    # como una SUCURSAL SIN CLAVE: tiene que arrancar con la del equipo
    json.dump({"rol": "colaborador", "usuario": "prueba release", "publish_token": ""},
              io.open(os.path.join(prueba, "e", "identity.json"), "w", encoding="utf-8"))
    env = dict(os.environ, MYS_PROYECTO=os.path.join(prueba, "p"), MYS_PANEL_STATE=os.path.join(prueba, "e"),
               MYS_PANEL_PORT=str(puerto), BROWSER="cmd.exe /c echo")
    exe = subprocess.Popen([os.path.join(aqui, "dist", "PanelMyS", "PanelMyS.exe")], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cfg = None
    for _ in range(60):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/config" % puerto, timeout=3) as rr:
                cfg = json.loads(rr.read().decode("utf-8"))
            break
        except Exception:
            if exe.poll() is not None:
                break
            time.sleep(0.5)
    exe.kill()
    exe.wait(10)
    if not cfg or int(cfg.get("version") or 0) != NUEVA_VERSION:
        morir("el exe compilado no arranco o no contesta con la v%d (%s)" % (NUEVA_VERSION, cfg))
    print("    ok: el exe abre y contesta v%d" % NUEVA_VERSION)
    if not (cfg.get("clave_equipo") and cfg.get("tiene_token")):
        morir("el exe compilado NO trae la clave del equipo (%s)" % cfg)
    print("    ok: una sucursal sin clave arranca con la del equipo")
    if cfg.get("certificados") != "windows+certifi":
        morir("el exe compilado no trae sus certificados (certifi): %s" % cfg.get("certificados"))
    print("    ok: trae sus propios certificados")
finally:
    time.sleep(0.5)
    shutil.rmtree(prueba, ignore_errors=True)

# ---------------------------------------------------------------- 7. publicar
paso(7, "Publicando")
subprocess.run(["git", "add", "panel"], cwd=repo_raiz, check=True)
# El titulo sale del label, sin repetir el numero de version que ya va
# adelante: "1.6.0 - el reporte se arma preguntando" -> "el reporte se arma...".
titulo = NUEVO_LABEL.split(" - ", 1)[-1].strip()
msg = ("Panel v%d (%s): %s\n\n%s\n"
       % (NUEVA_VERSION, NUEVA_PUBLICA, titulo,
          (NUEVO_CUERPO or NUEVAS_NOTAS).strip())) + FIRMA
subprocess.run(["git", "commit", "-m", msg], cwd=repo_raiz, check=True)

# el FUENTE tambien viaja al repo: sin esto la otra compu compila otra cosa.
# ⚠️ datos_api.py es fuente, no un archivo aparte: panel_server lo llama. Falto
#    en la lista hasta la v53, y la otra maquina podia compilar un panel donde
#    el server pide cosas que su datos_api no sabe hacer. Las pruebas viajan por
#    lo mismo: una prueba que no esta al lado del codigo que prueba no corre.
subprocess.run(["git", "add", "--",
                "herramientas/panel/panel_server.py",
                "herramientas/panel/datos_api.py",
                "herramientas/panel/fusion.py",
                "herramientas/panel/test_fusion.py",
                "herramientas/panel/armar_instalador.py",
                "herramientas/panel/subir_update.py",
                "herramientas/panel/SucursalAuto.iss",
                "herramientas/panel/PanelMyS.iss",
                "herramientas/panel/PanelMyS.spec",
                "herramientas/panel/web3",
                "herramientas/panel/publicar_web3.py",
                "herramientas/.gitignore",
                "herramientas/qa"], cwd=repo_raiz, check=True)
subprocess.run(["git", "commit", "-m",
                "Fuente al dia con lo publicado: VERSION %d + web3 como panel principal"
                % NUEVA_VERSION + FIRMA], cwd=repo_raiz, check=True)

r = subprocess.run(["git", "push", "origin", "main"], cwd=repo_raiz, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-1200:])
    morir("el push fallo. Si dice 'fetch first', alguien publico algo: `git pull` y de vuelta.")

# [8] Los instaladores, al dia con esta version.
# 22-sep: se instalo una sucursal con el instalador del Escritorio y era de
# tres dias antes: panel viejo y contenido viejo. Acordarse de armarlos a mano
# despues de cada release no funciono nunca, asi que lo hace este guion. Si
# falla (falta Inno Setup) el release NO se deshace: ya quedo publicado.
print("\n[8] Armando los instaladores con esta version")
r = subprocess.run([sys.executable, os.path.join(aqui, "armar_instalador.py")],
                   cwd=aqui, capture_output=True, text=True)
if r.returncode == 0:
    print("    ok: instaladores al dia en Escritorio\\Proyecto Intranet\\Panel MyS")
else:
    print((r.stdout or "")[-1500:])
    print((r.stderr or "")[-800:])
    print("    NO se pudieron armar los instaladores. El panel SI quedo publicado.")
    print("    Armalos con: python armar_instalador.py")

print("\n" + "=" * 62)
print("  PUBLICADO: v%d (%s)" % (NUEVA_VERSION, NUEVA_PUBLICA))
print("  Vercel lo sirve en ~30s. Los paneles van a ver el boton")
print("  'Actualizar a la ultima version' y se instalan solos.")
print("=" * 62)
