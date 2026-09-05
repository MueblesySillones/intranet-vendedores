# -*- coding: utf-8 -*-
"""
Panel de administracion local - Intranet Muebles y Sillones (Fase 1)
====================================================================
Mini-servidor local (solo libreria estandar + Pillow) que permite
gestionar las imagenes de la intranet sin tocar codigo:

  - Ver las secciones y sus imagenes
  - Subir imagenes arrastrando (se normalizan a PNG <=1568px)
  - Borrar y reordenar imagenes
  - Regenerar galerias.js corriendo el script real (salida identica)
  - Publicar (git add selectivo + commit + push a origin/main)

Vive en herramientas/panel/ y se lanza con "Panel de administracion.bat".
Ambos estan en .gitignore, asi que el panel NUNCA se publica.

Seguridad: el server escucha SOLO en 127.0.0.1 (no se expone a la red).
"""
import os
import sys
import re
import io
import mmap
import json
import time
import base64
import shutil
import hashlib
import subprocess
import threading
import webbrowser
import email
import zipfile
import datetime
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote, quote

from PIL import Image, ImageOps

# --- rutas (funciona tanto como script suelto como empaquetado en .exe) ---
# Cuando corre dentro de un .exe de PyInstaller:
#   - sys.frozen == True
#   - sys._MEIPASS = carpeta temporal con los recursos empaquetados (web/, originales.json)
#   - sys.executable = ruta del .exe (NO de Python)
# Cuando corre como .py normal (doble clic al .bat), se comporta como antes.
FROZEN = getattr(sys, "frozen", False)

# En modo ventana (sin consola) sys.stdout/stderr son None -> cualquier print() romperia.
if FROZEN and (sys.stdout is None or sys.stderr is None):
    try:
        _null = open(os.devnull, "w")
        if sys.stdout is None:
            sys.stdout = _null
        if sys.stderr is None:
            sys.stderr = _null
    except Exception:  # noqa
        pass

if FROZEN:
    RES_DIR = sys._MEIPASS                          # recursos empaquetados dentro del exe
    EXE_DIR = os.path.dirname(sys.executable)       # carpeta donde vive el .exe instalado
else:
    RES_DIR = os.path.dirname(os.path.abspath(__file__))   # herramientas/panel
    EXE_DIR = RES_DIR


def encontrar_proyecto():
    """Ubica la raiz del proyecto = carpeta que contiene 'intranet' y 'herramientas'.
    Orden de busqueda: variable de entorno -> proyecto.txt junto al exe ->
    subir carpetas desde el exe/script. Devuelve la ruta o None."""
    def es_proyecto(d):
        return d and os.path.isdir(os.path.join(d, "intranet")) \
                 and os.path.isdir(os.path.join(d, "herramientas"))

    # 1) variable de entorno explicita
    env = os.environ.get("MYS_PROYECTO")
    if env and es_proyecto(env):
        return os.path.abspath(env)

    # 2) archivo proyecto.txt junto al exe (lo escribe el instalador)
    cfg = os.path.join(EXE_DIR, "proyecto.txt")
    if os.path.isfile(cfg):
        try:
            # utf-8-sig tolera un BOM al inicio (Notepad/PowerShell lo agregan)
            ruta = open(cfg, encoding="utf-8-sig").read().strip().strip('﻿').strip('"')
            if es_proyecto(ruta):
                return os.path.abspath(ruta)
        except OSError:
            pass

    # 3) subir carpetas desde el exe (por si el exe vive dentro del proyecto)
    d = EXE_DIR
    for _ in range(8):
        if es_proyecto(d):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd

    # 4) modo script suelto: dos niveles arriba de este archivo (comportamiento original)
    if not FROZEN:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return None


PROYECTO = encontrar_proyecto()
INTRANET = os.path.join(PROYECTO, "intranet") if PROYECTO else ""
ASSETS = os.path.join(INTRANET, "assets") if PROYECTO else ""
# La carpeta del frontend se puede cambiar por variable de entorno. Sirve
# para levantar un rediseno en otro puerto SIN tocar el panel instalado:
#   MYS_PANEL_WEB=web2  MYS_PANEL_PORT=8130  python panel_server.py
# `web2` es el frontend con la seccion Datos, el muro y el compositor. `web` es
# el anterior y queda de red: si por lo que sea web2 no viajo en el paquete, el
# panel abre igual con el viejo en vez de mostrar una pagina en blanco.
_web_pedido = os.environ.get("MYS_PANEL_WEB") or "web3"
WEB = os.path.join(RES_DIR, _web_pedido)
if not os.path.isdir(WEB):
    WEB = os.path.join(RES_DIR, "web2")
if not os.path.isdir(WEB):
    WEB = os.path.join(RES_DIR, "web")
GALERIAS_JS = os.path.join(INTRANET, "galerias.js") if PROYECTO else ""
MODULOS_JS = os.path.join(INTRANET, "modulos.js") if PROYECTO else ""
ORIGINALES = os.path.join(RES_DIR, "originales.json")     # empaquetado en el exe
MOD_ASSETS = os.path.join(ASSETS, "_modulos") if PROYECTO else ""   # imagenes de contenido de modulos


# --- configuracion de rol: central (esta PC) vs colaborador (las otras) ---
# Se lee de panel_config.json junto al exe. Si no existe => central (comportamiento
# de siempre, una sola computadora). El colaborador manda propuestas al central en vez
# de publicar directo.
# Identidad DURABLE fuera del arbol de instalacion (que un auto-update podria pisar):
# %LOCALAPPDATA%\PanelMyS_state\identity.json (hermano de la carpeta del exe).
# Regla FAIL-CLOSED: ante config ausente-pero-antes-vista, corrupta o ambigua, NUNCA
# se asume 'central'; la identidad 'central' exige una senal explicita y positiva.
# MYS_PANEL_STATE permite apuntar el estado a otra carpeta. Es para las pruebas:
# sin esto, probar el panel escribe en el estado de verdad, y una prueba que
# pisa la configuracion real de marketing no es una prueba, es un accidente.
STATE_DIR = os.environ.get("MYS_PANEL_STATE") or (
    os.path.join(os.path.dirname(EXE_DIR), "PanelMyS_state") if EXE_DIR else "")
IDENTITY_FILE = os.path.join(STATE_DIR, "identity.json") if STATE_DIR else ""


def _leer_json_file(p):
    """(dict|None, ok). ok=False si el archivo EXISTE pero esta corrupto/ilegible."""
    if not p or not os.path.isfile(p):
        return None, True                # ausente != corrupto
    try:
        return json.load(open(p, encoding="utf-8-sig")), True
    except (ValueError, OSError):
        return None, False


def _guardar_identidad(cfg):
    """Persiste rol/usuario/central_url/receptor_port fuera del arbol de update."""
    if not IDENTITY_FILE or not cfg.get("rol"):
        return
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        datos = {k: cfg.get(k) for k in ("rol", "usuario", "central_url", "receptor_port")
                 if cfg.get(k) is not None}
        with open(IDENTITY_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f)
    except OSError:
        pass


def cargar_config():
    """Resuelve (config, rol) con rol FAIL-CLOSED. Prioridad:
    1) panel_config.json valido en la instalacion -> fuente de verdad (refresca identidad durable).
    2) identidad durable (sobrevive a un swap de la carpeta durante un auto-update).
    3) si habia config pero estaba CORRUPTA -> 'colaborador' (jamas central).
    4) nada configurado (fresh install / dev) -> 'central' (retrocompat 1 PC)."""
    cfg, cfg_corrupta = None, False
    for base in (EXE_DIR, RES_DIR):
        c, ok = _leer_json_file(os.path.join(base, "panel_config.json"))
        if c is not None:
            cfg = c
            break
        if not ok:
            cfg_corrupta = True
    if cfg is not None:
        _guardar_identidad(cfg)
        return cfg, (cfg.get("rol") or "central").strip().lower()
    ident, _ = _leer_json_file(IDENTITY_FILE)
    if ident is not None:
        return ident, (ident.get("rol") or "colaborador").strip().lower()
    if cfg_corrupta:
        return {}, "colaborador"                     # FAIL-CLOSED: corrupta nunca es central
    return {}, "central"                             # genuinamente sin configurar


# La seccion Datos vive en su propio paquete. Si algo ahi falla —falta un
# archivo, se rompio un import— el panel TIENE que seguir andando: cargar y
# publicar contenido es lo que no se puede perder. Por eso el try.
#
# ⚠️ Y antes, la carpeta de este archivo tiene que estar en sys.path. Suena de
# mas, pero panel_server se carga de tres formas distintas —doble click, desde
# el .exe, o importado por un lanzador— y en algunas de esas su propia carpeta
# NO queda en el camino: `import datos_api` falla con el archivo al lado.
_aqui = os.path.dirname(os.path.abspath(__file__))
if _aqui not in sys.path:
    sys.path.insert(0, _aqui)

# Como viene el baile de OAuth con Google. Se comparte entre pedidos porque
# el baile corre en un hilo aparte y la pantalla pregunta cada tanto.
_GOOGLE_BAILE = {}

try:
    import datos_api
except Exception as _e:                    # noqa: el panel anda igual sin esto
    datos_api = None
    _datos_error = str(_e)
else:
    _datos_error = ""
    # ⚠️ Los modulos de Google calculan su propia carpeta de estado para poder
    # funcionar sueltos (sin arrastrar la config del panel). Al integrarlos hay
    # que darles la del panel, o el token y la clave quedan en OTRA carpeta:
    # todo anda hasta que alguien mueve la instalacion y el acceso a Drive
    # desaparece sin motivo visible.
    try:
        from datos import google_sheets as _gs
        _gs.STATE_DIR = STATE_DIR
    except Exception:                      # noqa: sin Google el panel anda igual
        pass

CONFIG, ROL = cargar_config()
ROL = ROL.strip().lower()                                        # 'central' | 'colaborador'
ES_CENTRAL = ROL != "colaborador"
USUARIO = (CONFIG.get("usuario") or ("Central" if ES_CENTRAL else "Colaborador")).strip()
CENTRAL_URL = (CONFIG.get("central_url") or "").strip().rstrip("/")   # solo colaborador
# Fuentes por INTERNET (sin Tailscale ni central prendida): la web publica sirve
# el paquete de actualizacion (panel/version.json + panel/PanelMyS-vNN.zip) y el
# repo publico el contenido de la intranet. La central queda como RESPALDO.
WEB_PUBLICA = (CONFIG.get("web_publica") or "https://intranet-vendedores.vercel.app").strip().rstrip("/")
REPO_ZIP = (CONFIG.get("repo_zip") or "https://codeload.github.com/MueblesySillones/intranet-vendedores/zip/refs/heads/main").strip()
RECEPTOR_PORT = int(CONFIG.get("receptor_port") or 8125)
# Publicacion DIRECTA via el cerebro Cloudflare (todos publican: central y colaboradores).
CEREBRO_URL = (CONFIG.get("cerebro_url") or "https://mys-cerebro.mueblesysillones.workers.dev").strip().rstrip("/")
def _sanear_clave(t):
    """La clave como la espera el cerebro: sin espacios y SIN el prefijo
    "nombre:" de la lista del administrador. El Bearer es SOLO la parte
    despues de los dos puntos, pero pegar la linea entera es el error mas
    natural del mundo: mejor tolerarlo que explicarlo. Un token legitimo
    nunca contiene ':' (token_urlsafe), asi que el recorte no rompe nada."""
    t = (t or "").strip().strip('"').strip("'")
    if ":" in t:
        antes, despues = t.split(":", 1)
        if antes and " " not in antes and len(antes) <= 24 and not despues.startswith("/"):
            t = despues.strip()
    return t


PUBLISH_TOKEN = _sanear_clave(CONFIG.get("publish_token"))   # la clave de esta persona (Bearer)
PUBLISH_MANIFEST = os.path.join(STATE_DIR, "publish_manifest.json") if STATE_DIR else ""
# Sello del contenido del sitio que esta PC ya tiene aplicado (ETag de modulos.js).
# Sirve para saber si en la web hay contenido mas nuevo SIN bajarlo.
SELLO_CONTENIDO = os.path.join(STATE_DIR, "sello_contenido.json") if STATE_DIR else ""
# Buzon de propuestas del central (fuera de git; junto al exe/instalacion).
APROB_DIR = os.path.join(EXE_DIR, "aprobaciones")
TIPOS_CONTENT = {"html", "embed", "imagen", "link", "bloques", "coleccion",
                 "cartelera", "muro"}   # "muro" es el nombre viejo, se sigue leyendo
# tipos de publicacion del muro (tienen que ser los mismos de MURO_TAGS en la intranet)
ETIQUETAS_MURO = {"anuncio", "promo", "capacitacion", "logro", "importante", "equipo"}
# lo eliminado del muro se retiene estos dias por si fue sin querer
DIAS_PAPELERA = 15

# --- Versionado para el auto-update (ver receptor_server.py /update/*) ---
# VERSION es un entero MONOTONICO: SUBIR en CADA release del programa (si no, el
# cache del bundle en la central puede quedar stale y las sucursales no ven el update).
# La central anuncia su VERSION; cada sucursal compara contra la suya (este exe).
VERSION = 41
# --- Version PUBLICA: la que se muestra en pantalla ---------------------------
# Es texto libre y NO se compara con nada. Va aparte de VERSION a proposito:
# VERSION tiene que seguir siendo un entero que sube, porque el auto-update hace
# `int(remota) > VERSION`. Si se pusiera "1.2.2" ahi, int() reventaria y ademas
# 1.2.2 < 25, asi que ninguna sucursal volveria a ver una actualizacion nunca.
# Para el equipo: subir VERSION_PUBLICA cuando el cambio se nota; VERSION sube
# SIEMPRE, en cada release, aunque el cambio sea invisible.
VERSION_PUBLICA = "1.5.0"
VERSION_LABEL = "1.5.0 - el link va al bloque, y cargar al modulo"
VERSION_NOTES = (
                 "Cuando una publicacion senala un bloque puntual de un modulo, "
                 "ahora el vendedor cae en ESE bloque y no arriba de todo el modulo. "
                 "Y aparece el interruptor Cargar al modulo: lo que se escribe en la "
                 "publicacion se copia adentro del modulo elegido como contenido de "
                 "verdad, con el titulo, el texto y las piezas, asi no hay que "
                 "escribirlo dos veces. De paso, el selector ahora deja senalar "
                 "tambien los titulos, que son las secciones de cada modulo.")

# Carpetas del auto-update (FUERA del arbol de instalacion que el swap reemplaza).
UPDATE_DIR = os.path.join(os.path.dirname(EXE_DIR), "PanelMyS_update") if EXE_DIR else ""
UPDATER_SRC = os.path.join(RES_DIR, "updater", "aplicar.bat")   # empaquetado en el exe
_UPDATE_LOCK = threading.Lock()
_UPDATE_EN_CURSO = False

# iconos y colores disponibles (deben existir en el objeto I / la paleta de index.html)
ICONOS_VALIDOS = {
    "book", "card", "tag", "truck", "award", "search", "chart", "play", "ext",
    "clock", "download", "image", "check", "users", "user", "map", "mic",
    "shield", "box", "store", "ruler", "whatsapp", "chatBubble", "megaphone",
    "lock", "funnel", "refresh", "verified", "phone", "reply", "home", "layers",
}
COLORES_VALIDOS = {
    "--c-hudson", "--c-caba", "--c-canning", "--c-norcenter",
    "--c-success", "--c-warn", "--c-danger", "--c-info",
}

# --- lista FIJA de secciones, MISMO orden y extensiones que el script canonico ---
SECCIONES = ["promos_bancarias", "promos_mensuales", "entregas",
             "fechas_especiales", "porque", "competencia", "chatbot"]
ETIQUETAS = {
    "promos_bancarias": "Promociones bancarias",
    "promos_mensuales": "Promociones vigentes",
    "entregas":         "Placas de envio",
    "fechas_especiales": "Fechas especiales",
    "porque":           "Por que elegirnos",
    "competencia":      "Mini competencia",
    "chatbot":          "Tutorial chatbot",
}
# grupos del módulo "Material descargable" (mismo orden y títulos que el intranet real)
GRUPOS_DESCARGABLES = [
    ("fechas_especiales", "Fechas especiales"),
    ("promos_bancarias", "Promociones bancarias"),
    ("promos_mensuales", "Promociones vigentes"),
    ("entregas", "Placas de envío"),
    ("porque", "¿Por qué elegirnos?"),
]
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
MAX_LADO = 1568
PORT = int(os.environ.get("MYS_PANEL_PORT") or 8124)
HOST = "127.0.0.1"

# ---- video -----------------------------------------------------------
EXTS_VIDEO = (".mp4", ".webm", ".mov", ".m4v")
# Tope de lo que se GUARDA (ya comprimido). El limite real no lo pone GitHub
# (acepta blobs de 100 MB) sino el Worker de Cloudflare: publica en base64 (+33%)
# y conviven ~4 copias del texto en los 128 MB de memoria del isolate.
# 16 MB crudos = ~21,4 MB en base64 = ~86 MB de pico. Ese es el techo seguro.
MAX_VIDEO = 16 * 1024 * 1024
# Lo que aceptamos RECIBIR antes de comprimir (un video de celular es pesado).
# Se recibe en streaming a disco, no a memoria: el limite es de espacio, no de RAM.
MAX_VIDEO_SUBIDA = 200 * 1024 * 1024
# Objetivo al comprimir: bien por debajo del tope, para que entre siempre.
OBJETIVO_VIDEO = 12 * 1024 * 1024


def firma_video(data):
    """Reconoce el contenedor por su firma. Devuelve 'mp4' | 'webm' | None.
    (.mov y .m4v son variantes del contenedor ISO-BMFF, igual que mp4.)"""
    if len(data) < 16:
        return None
    if data[:4] == b"\x1a\x45\xdf\xa3":              # EBML -> webm/mkv
        return "webm"
    # ISO Base Media: [4 bytes de tamano]"ftyp"
    if data[4:8] == b"ftyp":
        return "mp4"
    return None


# =====================================================================
#  Compresor de video (ffmpeg)
#
#  El panel es stdlib + Pillow y ffmpeg no viene con Python. Estrategia:
#  si la PC ya tiene ffmpeg (PATH) se usa ese; si no, se descarga UNA vez a
#  %LOCALAPPDATA%\PanelMyS_state\ffmpeg\ y queda cacheado para siempre.
#  Asi el instalador de sucursal no engorda 100 MB.
#
#  Nada de esto corre solo: el frontend avisa y pide confirmacion antes.
# =====================================================================
CREATE_NO_WINDOW = 0x08000000     # la app es windowed: sin esto parpadea una consola negra

FFMPEG_DIR = os.path.join(STATE_DIR, "ffmpeg") if STATE_DIR else ""
# Release fijo (tag inmutable) del build "essentials" de gyan.dev espejado en GitHub.
FFMPEG_URL = ("https://github.com/GyanD/codexffmpeg/releases/download/"
              "8.1.1/ffmpeg-8.1.1-essentials_build.zip")
FFMPEG_MB = 104                   # lo que se le muestra al usuario antes de bajarlo
FFMPEG_ZIP_MAX = 250 * 1024 * 1024

_FFMPEG_CACHE = ""
_RE_DUR = re.compile(rb"Duration:\s*(\d+):(\d\d):(\d\d)\.(\d\d)")
_RE_TIME = re.compile(rb"time=\s*(\d+):(\d\d):(\d\d)\.(\d\d)")


def _ffmpeg_anda(exe):
    """Un binario sirve solo si CORRE. Es tambien la verificacion de integridad
    de la descarga: un zip corrupto no produce un exe que responda -version."""
    try:
        r = subprocess.run([exe, "-version"], capture_output=True, timeout=25,
                           creationflags=CREATE_NO_WINDOW)
        return r.returncode == 0 and b"ffmpeg version" in (r.stdout or b"")
    except (OSError, subprocess.SubprocessError):
        return False


def ffmpeg_local():
    """Ruta a un ffmpeg usable, o '' si todavia no hay. NO descarga nada."""
    global _FFMPEG_CACHE
    if _FFMPEG_CACHE and os.path.isfile(_FFMPEG_CACHE):
        return _FFMPEG_CACHE
    candidatos = []
    if FFMPEG_DIR:
        candidatos.append(os.path.join(FFMPEG_DIR, "ffmpeg.exe"))
    delsistema = shutil.which("ffmpeg")
    if delsistema:
        candidatos.append(delsistema)
    for c in candidatos:
        if c and os.path.isfile(c) and _ffmpeg_anda(c):
            _FFMPEG_CACHE = c
            return c
    return ""


# ---- trabajos largos (descarga / compresion) que corren en su propio hilo ----
# El server es ThreadingHTTPServer, asi que el panel sigue respondiendo mientras
# esto trabaja y el frontend puede ir preguntando el progreso.
_JOBS = {}
_JOBS_LOCK = threading.Lock()


def _job_nuevo(tipo):
    jid = tipo + "_" + base64.b16encode(os.urandom(6)).decode("ascii").lower()
    with _JOBS_LOCK:
        # no acumular para siempre: limpiar los terminados cuando se juntan varios
        if len(_JOBS) > 20:
            for k in [k for k, v in _JOBS.items() if v["estado"] != "corriendo"][:10]:
                _JOBS.pop(k, None)
        _JOBS[jid] = {"estado": "corriendo", "pct": 0, "msg": "", "error": "", "src": "", "info": ""}
    return jid


def _job_set(jid, **kw):
    with _JOBS_LOCK:
        j = _JOBS.get(jid)
        if j:
            j.update(kw)


def job_estado(jid):
    with _JOBS_LOCK:
        j = _JOBS.get(jid)
        return dict(j) if j else None


def _bajar_ffmpeg(jid):
    """Descarga + instala ffmpeg. Corre en un hilo."""
    tmp = ""
    try:
        if not FFMPEG_DIR:
            raise ValueError("no se donde guardarlo")
        os.makedirs(FFMPEG_DIR, exist_ok=True)
        exe = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
        tmp = os.path.join(FFMPEG_DIR, "descarga.part")
        _job_set(jid, msg="Descargando el compresor de video…")
        req = urllib.request.Request(FFMPEG_URL, headers={"User-Agent": "PanelMyS/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            total = int(r.headers.get("Content-Length") or 0)
            bajado = 0
            with open(tmp, "wb") as f:
                while True:
                    trozo = r.read(256 * 1024)
                    if not trozo:
                        break
                    bajado += len(trozo)
                    if bajado > FFMPEG_ZIP_MAX:
                        raise ValueError("la descarga pesa mucho mas de lo esperado")
                    f.write(trozo)
                    if total:
                        _job_set(jid, pct=int(bajado * 90 / total))
        _job_set(jid, pct=92, msg="Instalando…")
        with zipfile.ZipFile(tmp) as z:
            miembro = next((n for n in z.namelist()
                            if n.lower().replace("\\", "/").endswith("bin/ffmpeg.exe")), None)
            if not miembro:
                raise ValueError("el paquete no traia ffmpeg.exe")
            with z.open(miembro) as src, open(exe + ".part", "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        os.replace(exe + ".part", exe)
        if not _ffmpeg_anda(exe):
            raise ValueError("el compresor descargado no arranca")
        global _FFMPEG_CACHE
        _FFMPEG_CACHE = exe
        _job_set(jid, estado="listo", pct=100, msg="Compresor listo.")
    except Exception as e:      # noqa - cualquier fallo tiene que llegar al usuario
        _job_set(jid, estado="error", error="No se pudo preparar el compresor: %s" % e)
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def _repo_del_cerebro():
    """Lee owner/repo/rama del wrangler.toml si está a mano; si no, los conocidos."""
    datos = {"owner": "MueblesySillones", "repo": "intranet-vendedores", "rama": "main"}
    ruta = os.path.join(PROYECTO, "herramientas", "cerebro", "wrangler.toml") if PROYECTO else ""
    try:
        with open(ruta, encoding="utf-8") as f:
            txt = f.read()
        for clave, campo in (("REPO_OWNER", "owner"), ("REPO_NAME", "repo"), ("REPO_BRANCH", "rama")):
            m = re.search(clave + r'\s*=\s*"([^"]+)"', txt)
            if m:
                datos[campo] = m.group(1)
    except OSError:
        pass
    return datos


def kit_recuperacion():
    """Junta TODO lo necesario para recuperar el control del sistema si esta
    computadora se pierde. El panel no puede fabricar credenciales de GitHub ni
    de Cloudflare (solo las emiten ellos): lo que hace es dejar asentado dónde
    vive cada acceso, qué desbloquea y cómo retomarlo."""
    r = _repo_del_cerebro()
    return {
        "generado": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "pc": _pc(),
        "usuario": USUARIO,
        "rol": ROL,
        "version_panel": VERSION,
        "proyecto": PROYECTO,
        "cerebro_url": CEREBRO_URL,
        "publish_token": PUBLISH_TOKEN,
        "central_url": CENTRAL_URL,
        "receptor_port": RECEPTOR_PORT,
        "repo": r,
        "sitio": "https://github.com/%s/%s" % (r["owner"], r["repo"]),
        "servicios": [
            {"nombre": "GitHub", "que_es": "Guarda el sitio (codigo y contenido).",
             "desbloquea": "TODO el contenido y el codigo de la intranet.",
             "donde": "El token con permiso de escritura vive SOLO adentro del Worker de Cloudflare, "
                      "como secreto GITHUB_TOKEN. No esta en esta computadora.",
             "si_lo_perdes": "Entra a github.com con la cuenta duena del repositorio y genera un token "
                             "nuevo (fine-grained, permiso Contents: Read and write sobre ese repo). "
                             "Despues cargalo en Cloudflare con: wrangler secret put GITHUB_TOKEN"},
            {"nombre": "Cloudflare", "que_es": "Corre el 'cerebro' que publica al sitio.",
             "desbloquea": "El cerebro entero. Quien tenga esto puede leer o reemplazar el token de GitHub.",
             "donde": "dash.cloudflare.com con la cuenta del negocio. El Worker se llama mys-cerebro.",
             "si_lo_perdes": "Recupera la cuenta por mail. Sin ella no se puede cambiar como se publica."},
            {"nombre": "Vercel", "que_es": "Publica el sitio en internet.",
             "desbloquea": "El hosting y la direccion web.",
             "donde": "vercel.com, conectado al repositorio de GitHub.",
             "si_lo_perdes": "Se puede volver a conectar el repo desde una cuenta nueva."},
            {"nombre": "Tailscale", "que_es": "Red privada que une la central con las sucursales.",
             "desbloquea": "Que una PC nueva se sume a la red.",
             "donde": "login.tailscale.com. La clave de invitacion va incrustada en el instalador de sucursal.",
             "si_lo_perdes": "Genera otra clave reusable en Settings -> Keys y recompila el instalador."},
        ],
        "pasos": [
            "1. Consegui acceso a la cuenta de Cloudflare: es la que manda sobre como se publica.",
            "2. Verifica que el cerebro responda: abri <CEREBRO>/health en el navegador.",
            "3. Si el token de GitHub no anda mas, genera uno nuevo y cargalo con wrangler secret put GITHUB_TOKEN.",
            "4. Instala el panel en otra computadora con 'Instalar Panel MyS.exe' y elegi Central.",
            "5. Clona el repositorio en esa PC y apunta el panel a esa carpeta.",
            "6. Pega la clave de publicacion (esta mas arriba en este mismo kit) cuando el panel te la pida.",
            "7. Desde ahi ya podes publicar y actualizar como antes.",
        ],
        "avisos": [
            "La contrasena de este archivo NO se puede recuperar. Si la perdes, el kit no sirve.",
            "Guardalo en dos lugares distintos (por ejemplo un pendrive y tu correo).",
            "La clave de publicacion que figura aca permite publicar en el sitio: tratala como una contrasena.",
            "Si alguna vez pegaste el token de GitHub o la clave de Tailscale en un chat, rotalos.",
        ],
    }


def _pedir_json(url, timeout=25):
    req = urllib.request.Request(url, headers={
        "User-Agent": "PanelMyS/1.0", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def historial_publicaciones(limite=20):
    """Ultimas publicaciones del contenido. Sale de la API publica de GitHub:
    el repo es publico, asi que NO hace falta ninguna credencial (el token vive
    solo adentro del Worker y no queremos sacarlo de ahi)."""
    r = _repo_del_cerebro()
    url = ("https://api.github.com/repos/%s/%s/commits?path=intranet/modulos.js"
           "&sha=%s&per_page=%d" % (r["owner"], r["repo"], r["rama"], limite))
    try:
        datos = _pedir_json(url)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {"ok": False, "error": "GitHub esta limitando las consultas. Proba de nuevo en un rato."}
        return {"ok": False, "error": "GitHub respondio %d" % e.code}
    except Exception as e:  # noqa
        return {"ok": False, "error": "No pude consultar el historial: %s" % e}

    # cual es la version que hay AHORA en disco (para no ofrecer volver a ella)
    try:
        with open(os.path.join(INTRANET, "modulos.js"), "rb") as f:
            actual = hashlib.sha1(f.read()).hexdigest()
    except OSError:
        actual = ""

    versiones = []
    for c in datos:
        cm = c.get("commit") or {}
        fecha = ((cm.get("author") or {}).get("date") or "")[:19].replace("T", " ")
        versiones.append({
            "sha": c.get("sha", ""),
            "corto": (c.get("sha") or "")[:8],
            "fecha": fecha,
            "mensaje": (cm.get("message") or "").split("\n")[0][:120],
        })
    return {"ok": True, "versiones": versiones, "hash_actual": actual,
            "repo": "%s/%s" % (r["owner"], r["repo"])}


def restaurar_version(sha):
    """Trae el modulos.js de una publicacion vieja y lo deja EN DISCO.
    NO publica: el usuario lo revisa en el panel y recien despues aprieta
    Publicar. Guarda antes una copia de lo que habia."""
    if not re.match(r"^[0-9a-f]{7,40}$", (sha or "").strip()):
        return {"ok": False, "error": "version invalida"}
    r = _repo_del_cerebro()
    url = "https://raw.githubusercontent.com/%s/%s/%s/intranet/modulos.js" % (
        r["owner"], r["repo"], sha)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PanelMyS/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            crudo = resp.read().decode("utf-8")
    except Exception as e:  # noqa
        return {"ok": False, "error": "No pude bajar esa version: %s" % e}

    # que sea de verdad un modulos.js antes de pisar nada
    try:
        i, j = crudo.index("["), crudo.rindex("]") + 1
        mods = json.loads(crudo[i:j])
        if not isinstance(mods, list) or not mods:
            raise ValueError("vacio")
    except Exception:  # noqa
        return {"ok": False, "error": "Esa version no se pudo leer (archivo dañado)."}

    destino = os.path.join(INTRANET, "modulos.js")
    try:
        if STATE_DIR:
            os.makedirs(STATE_DIR, exist_ok=True)
            marca = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(destino, os.path.join(STATE_DIR, "modulos.js.antes-de-restaurar-%s" % marca))
        with open(destino, "w", encoding="utf-8", newline="\n") as f:
            f.write(crudo)
    except OSError as e:
        return {"ok": False, "error": "No pude escribir el archivo: %s" % e}
    return {"ok": True, "modulos": len(mods), "sha": sha[:8]}


def duracion_video(exe, ruta):
    """Segundos, leyendo lo que ffmpeg imprime al abrir el archivo (sin ffprobe)."""
    try:
        r = subprocess.run([exe, "-hide_banner", "-i", ruta], capture_output=True,
                           timeout=60, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return 0.0
    m = _RE_DUR.search((r.stderr or b"") + (r.stdout or b""))
    if not m:
        return 0.0
    h, mi, s, c = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + c / 100.0


# Formatos que TODO navegador sabe mostrar. Fuera de esta lista hay que
# convertir, pese lo que pese el archivo.
CODECS_WEB = {"h264"}
ANCHO_MAX_CRUDO = 1920          # mas grande que esto, se reescala igual


def _codec_por_firma(ruta):
    """El codec leido del propio contenedor, sin ffmpeg.

    En un mp4/mov el codec se declara con un fourcc dentro del atomo `moov`:
    avc1/avc3 = H.264, hvc1/hev1 = HEVC. Sirve de respaldo para no obligar a
    bajar 104 MB de compresor solo para AVERIGUAR si hace falta convertir.
    Devuelve 'h264' | 'hevc' | '' (no se pudo saber)."""
    TROZO = 4 * 1024 * 1024
    try:
        with open(ruta, "rb") as f:
            datos = f.read(TROZO)
            # ⚠️ Las camaras (iPhone incluido) escriben el `moov` al FINAL, no al
            # principio: mirando solo la cabeza, un HEVC pasaba por desconocido.
            f.seek(0, 2)
            fin = f.tell()
            if fin > TROZO:
                f.seek(max(TROZO, fin - TROZO))
                datos += f.read(TROZO)
    except OSError:
        return ""
    if b"hvc1" in datos or b"hev1" in datos:
        return "hevc"
    if b"avc1" in datos or b"avc3" in datos:
        return "h264"
    return ""


def _leer_pistas(ruta):
    """Codec, medidas y profundidad, leyendo lo que ffmpeg imprime al abrir el
    archivo (no hace falta ffprobe: `ffmpeg -i` ya lo dice todo en stderr).
    Devuelve {} si no se pudo averiguar."""
    exe = ffmpeg_local()
    if not exe:
        return {}
    try:
        pr = subprocess.run([exe, "-hide_banner", "-i", ruta],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=40, creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return {}
    txt = (pr.stdout or b"").decode("utf-8", "replace")
    m = re.search(r"Stream #\d+:\d+.*?: Video:\s*([A-Za-z0-9_]+)(.*)", txt)
    if not m:
        return {}
    resto = m.group(2)
    med = re.search(r"(\d{2,5})x(\d{2,5})", resto)
    pix = re.search(r"\b(yuv[a-z0-9]*|gbr[a-z0-9]*|rgb[a-z0-9]*)\b", resto)
    au = re.search(r"Stream #\d+:\d+.*?: Audio:\s*([A-Za-z0-9_]+)", txt)
    return {
        "codec": m.group(1).lower(),
        "ancho": int(med.group(1)) if med else 0,
        "alto": int(med.group(2)) if med else 0,
        "pix": (pix.group(1) if pix else ""),
        "audio": (au.group(1).lower() if au else ""),
    }


def video_apto(ruta, peso):
    """¿Se puede publicar tal cual? Devuelve (apto, motivo_legible).

    ⚠️ Antes esto se decidia SOLO por peso, y ahi estaba el problema: un video
    de iPhone en HEVC de 11 MB entra bajo el tope, se guardaba crudo, y en la
    intranet se veia un rectangulo NEGRO con sonido — el navegador carga el
    audio pero no sabe decodificar el video. Ahora manda el codec."""
    if peso > MAX_VIDEO:
        return False, "pesa %.1f MB" % (peso / 1048576.0)
    t = _leer_pistas(ruta)
    if not t:
        # sin ffmpeg no se puede medir, pero el contenedor igual dice el codec.
        # Si declara H.264 se acepta: obligar a bajar 104 MB de compresor solo
        # para CONFIRMAR lo que el archivo ya dice seria una molestia al pedo.
        firma = _codec_por_firma(ruta)
        if firma == "h264":
            return True, ""
        if firma == "hevc":
            return False, "esta en HEVC y los navegadores solo muestran H.264"
        # mas vale reencodear de mas que publicar algo que no se ve
        return False, "no se pudo identificar el formato"
    if t["codec"] not in CODECS_WEB:
        return False, "esta en %s y los navegadores solo muestran H.264" % t["codec"].upper()
    if "10le" in t["pix"] or "10be" in t["pix"] or "12le" in t["pix"]:
        return False, "esta en 10 bits y muchos navegadores no lo muestran"
    if max(t["ancho"], t["alto"]) > ANCHO_MAX_CRUDO:
        return False, "mide %dx%d, demasiado grande para el celular" % (t["ancho"], t["alto"])
    if t["audio"] and t["audio"] not in ("aac", "mp3"):
        return False, "el audio esta en %s" % t["audio"].upper()
    return True, ""


def _comprimir(jid, origen, destino, objetivo=OBJETIVO_VIDEO):
    """Reencoda a 720p/h264 apuntando a `objetivo` bytes. Corre en un hilo."""
    p = None
    try:
        exe = ffmpeg_local()
        if not exe:
            raise ValueError("falta el compresor")
        dur = duracion_video(exe, origen)
        _job_set(jid, msg="Comprimiendo el video…")

        cmd = [exe, "-y", "-hide_banner", "-loglevel", "error", "-stats", "-i", origen,
               # cap del lado largo en 1280 SIN agrandar los que ya son chicos; el
               # alto/ancho par lo exige yuv420p. Respeta vertical y horizontal solo.
               "-vf", ("scale=w='min(1280,iw)':h='min(1280,ih)'"
                       ":force_original_aspect_ratio=decrease:force_divisible_by=2"),
               "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart",
               "-c:a", "aac", "-b:a", "96k", "-ac", "2"]

        # con la duracion conocida se puede apuntar al peso; si no, calidad fija
        vb = 0
        if dur > 1:
            vb = int(objetivo * 8 / dur) - 96000
        if vb <= 0 or vb > 2_500_000:
            cmd += ["-crf", "24"]                      # corto: por calidad sale chico igual
        else:
            vb = max(vb, 300_000)                      # piso: por debajo se ve inmirable
            cmd += ["-b:v", str(vb), "-maxrate", str(int(vb * 1.5)), "-bufsize", str(vb * 3)]
        cmd.append(destino)

        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             creationflags=CREATE_NO_WINDOW)
        cola = b""
        while True:
            trozo = p.stderr.read1(4096)
            if not trozo:
                break
            cola = (cola + trozo)[-8192:]
            marcas = _RE_TIME.findall(cola)
            if marcas and dur > 0:
                h, mi, s, c = (int(x) for x in marcas[-1])
                t = h * 3600 + mi * 60 + s + c / 100.0
                _job_set(jid, pct=max(1, min(99, int(t * 100 / dur))))
        rc = p.wait(timeout=60)
        p = None
        if rc != 0:
            raise ValueError("ffmpeg termino con error %d" % rc)
        if not os.path.isfile(destino) or os.path.getsize(destino) == 0:
            raise ValueError("no se genero el archivo")
        return True, ""
    except Exception as e:      # noqa
        return False, str(e)
    finally:
        if p is not None:
            try:
                p.kill()
            except OSError:
                pass

# rutas que NUNCA deben publicarse (gate de seguridad del boton Publicar)
PREFIJOS_PROHIBIDOS = ("datos/", "herramientas/", "memoria-diseno/", ".claude/")


# =====================================================================
#  Logica de imagenes (copia fiel de normalizar() + exif_transpose)
# =====================================================================
def normalizar(img):
    """Lleva la imagen a RGB/RGBA y la achica a <=1568px (nunca agranda).
    Copia textual de herramientas/arreglar_imagen.py para mantener paridad."""
    cambios = []
    m = img.mode
    if m not in ("RGB", "RGBA"):
        tiene_alpha = (m in ("LA", "PA", "RGBa", "La")) or \
                      (m == "P" and img.info.get("transparency") is not None)
        if m.startswith("I") or m == "F":
            img = img.convert("L")
        destino = "RGBA" if tiene_alpha else "RGB"
        img = img.convert(destino)
        cambios.append("modo %s -> %s" % (m, destino))
    w, h = img.size
    if max(w, h) > MAX_LADO:
        s = MAX_LADO / float(max(w, h))
        img = img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
        cambios.append("redimensionada a %dx%d" % img.size)
    return img, cambios


# =====================================================================
#  Utilidades de nombres (paridad con titulo() del script)
# =====================================================================
def titulo(nombre):
    stem = os.path.splitext(nombre)[0]
    stem = re.sub(r'^\d+\s*[-_.]\s*', '', stem)
    stem = re.sub(r'[-_]+', ' ', stem).strip()
    return (stem[:1].upper() + stem[1:]) if stem else nombre


def base_sin_prefijo(nombre):
    """stem sin el prefijo numerico de ordenamiento (para no apilar '01 - 02 - ')."""
    stem = os.path.splitext(nombre)[0]
    return re.sub(r'^\d+\s*[-_.]\s*', '', stem)


def sanear(stem):
    """Deja solo caracteres seguros para nombre de archivo."""
    stem = re.sub(r'[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ \-_().]', '', stem).strip()
    return stem or "imagen"


def nombre_unico(carpeta, base, ext=".png"):
    cand = base + ext
    i = 2
    while os.path.exists(os.path.join(carpeta, cand)):
        cand = "%s (%d)%s" % (base, i, ext)
        i += 1
    return cand


def seccion_valida(sec):
    return sec in SECCIONES


def carpeta_de(sec):
    c = os.path.join(ASSETS, sec)
    os.makedirs(c, exist_ok=True)
    return c


def listar(sec):
    """Devuelve las imagenes de una seccion en el MISMO orden que el script
    (alfabetico case-insensitive), con file/title/download."""
    carpeta = carpeta_de(sec)
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith(EXTS)]
    archivos.sort(key=lambda s: s.lower())
    return [{
        "file": "assets/%s/%s" % (sec, f),
        "title": titulo(f),
        "download": f,
    } for f in archivos]


def estado_secciones():
    out = []
    for sec in SECCIONES:
        imgs = listar(sec)
        out.append({
            "key": sec,
            "label": ETIQUETAS.get(sec, sec),
            "count": len(imgs),
            "images": imgs,
        })
    return out


def grupos_descargables():
    """Los grupos del módulo Material descargable, con sus imágenes (orden del intranet)."""
    return [{"key": k, "label": lbl, "images": listar(k)} for k, lbl in GRUPOS_DESCARGABLES]


# =====================================================================
#  Git helpers
# =====================================================================
def git(*args):
    try:
        p = subprocess.run(["git"] + list(args), cwd=PROYECTO,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        # git no esta instalado en esta computadora (tipico en un colaborador)
        return 127, "", "git no esta instalado"
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def _git_stub(sin_git=False):
    return {"pendientes": 0, "pendientes_sitio": 0, "ahead": 0, "behind": 0,
            "limpio": True, "sin_git": sin_git}


def estado_git():
    # un COLABORADOR no publica ni usa git: no lo llamamos (muchas PCs no tienen git).
    if not ES_CENTRAL:
        return _git_stub()
    rc, out, err = git("status", "--porcelain")
    if rc == 127:                      # git no instalado en la central
        return _git_stub(sin_git=True)
    cambios = [l for l in out.splitlines() if l.strip()]
    # cuantos de esos cambios son del sitio (intranet/)
    del_site = [l for l in cambios if l[3:].startswith("intranet/")]
    rc2, ab, _ = git("rev-list", "--left-right", "--count", "origin/main...main")
    ahead = behind = 0
    if rc2 == 0 and ab.strip():
        try:
            behind, ahead = [int(x) for x in ab.split()]
        except ValueError:
            pass
    return {
        "pendientes": len(cambios),
        "pendientes_sitio": len(del_site),
        "ahead": ahead,
        "behind": behind,
        "limpio": len(cambios) == 0,
    }


def publicar():
    log = []

    def paso(titulo_, rc, out, err):
        log.append("$ " + titulo_)
        if out.strip():
            log.append(out.rstrip())
        if err.strip():
            log.append(err.rstrip())
        log.append("")

    # 1) regenerar galerias.js con el script real
    rc, out, err = regenerar_galerias()
    paso("regenerar galerias.js", rc, out, err)
    if rc != 0:
        return {"ok": False, "log": "\n".join(log) + "\nError al regenerar galerias.js."}

    # 2) add SELECTIVO solo del sitio
    rc, out, err = git("add", "--", "intranet/")
    paso("git add -- intranet/", rc, out, err)

    # 3) gate de seguridad: nada sensible staged
    rc, out, err = git("diff", "--cached", "--name-only")
    staged = [l.strip() for l in out.splitlines() if l.strip()]
    peligrosos = [p for p in staged
                  if p.startswith(PREFIJOS_PROHIBIDOS) or p.endswith(".bat") or p == "LEEME.md"]
    if peligrosos:
        git("reset")
        log.append("ABORTADO: se detectaron rutas sensibles en el commit:")
        log.extend("  - " + p for p in peligrosos)
        return {"ok": False, "log": "\n".join(log)}

    if not staged:
        return {"ok": True, "nada": True, "log": "\n".join(log) + "No hay cambios para publicar."}

    log.append("Archivos a publicar:")
    log.extend("  + " + p for p in staged)
    log.append("")

    # 4) commit
    import datetime
    msg = "Actualizar imagenes/galerias desde el panel"
    rc, out, err = git("commit", "-m", msg)
    paso("git commit", rc, out, err)
    if rc != 0:
        return {"ok": False, "log": "\n".join(log) + "\nError al commitear."}

    # 5) push normal (jamas --force)
    rc, out, err = git("push", "origin", "main")
    paso("git push origin main", rc, out, err)
    if rc != 0:
        return {"ok": False, "log": "\n".join(log) +
                "\nError al publicar. Revisa tu conexion o las credenciales de GitHub."}

    log.append("LISTO. Vercel redeploya solo en ~30 segundos.")
    return {"ok": True, "log": "\n".join(log)}


def regenerar_galerias():
    """Genera intranet/galerias.js EN PROCESO (sin llamar a Python por subprocess).
    Reproduce byte-a-byte la salida de herramientas/actualizar_galerias.py:
    mismas secciones, mismo orden (alfabetico case-insensitive), mismos campos
    file/title/download y el mismo encabezado. Se hace asi porque dentro del .exe
    no hay un interprete de Python al que invocar."""
    try:
        data = {}
        for sec in SECCIONES:
            imgs = listar(sec)        # ya viene ordenado y con los campos correctos
            if imgs:
                data[sec] = imgs
        with open(GALERIAS_JS, "w", encoding="utf-8") as fh:
            fh.write("/* Generado automaticamente por actualizar_galerias.py. No editar a mano. */\n")
            fh.write("window.GALLERIES = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n")
        return 0, "galerias.js regenerado: %d imagen(es) en %d seccion(es)." % (
            sum(len(v) for v in data.values()), len(data)), ""
    except Exception as e:  # noqa
        return 1, "", "No se pudo regenerar galerias.js: %s" % e


# =====================================================================
#  Publicacion DIRECTA via el cerebro Cloudflare (central Y colaboradores)
# =====================================================================
def guardar_publish_token(token):
    """Guarda la clave de publicacion de esta persona en panel_config.json."""
    token = _sanear_clave(token)
    global PUBLISH_TOKEN
    token = (token or "").strip()
    p = os.path.join(EXE_DIR, "panel_config.json")
    cfg = {}
    if os.path.isfile(p):
        try:
            cfg = json.load(open(p, encoding="utf-8-sig"))
        except (ValueError, OSError):
            cfg = {}
    cfg["publish_token"] = token
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as e:  # noqa
        return {"ok": False, "error": "no pude guardar la clave: %s" % e}
    PUBLISH_TOKEN = token
    _guardar_identidad(cfg)
    return {"ok": True}


def publicar_cerebro(mensaje=""):
    """Publica DIRECTO al sitio via el cerebro: regenera galerias, arma los archivos
    gestionados que CAMBIARON (manifiesto de hashes) y hace POST /publish. Los que se
    borraron quedan huerfanos en el repo (no afectan el sitio)."""
    if not CEREBRO_URL:
        return {"ok": False, "log": "No esta configurada la direccion del cerebro."}
    if not PUBLISH_TOKEN:
        return {"ok": False, "falta_token": True,
                "log": "Falta tu clave de publicacion. Cargala una vez y volve a publicar."}
    log = []
    rc, out, err = regenerar_galerias()
    log.append(out or err)
    if rc != 0:
        return {"ok": False, "log": "\n".join(log)}

    rels = rel_gestionados(INTRANET)
    if os.path.isfile(GALERIAS_JS):
        rels.append("galerias.js")

    manifest = {}
    if PUBLISH_MANIFEST and os.path.isfile(PUBLISH_MANIFEST):
        try:
            manifest = json.load(open(PUBLISH_MANIFEST, encoding="utf-8"))
        except (ValueError, OSError):
            manifest = {}

    actual, contenidos = {}, {}
    for rel in rels:
        full = os.path.join(INTRANET, *rel.split("/"))
        try:
            with open(full, "rb") as fh:
                b = fh.read()
        except OSError:
            continue
        actual[rel] = hashlib.sha1(b).hexdigest()
        contenidos[rel] = b

    cambiados = [rel for rel in actual if manifest.get(rel) != actual[rel]]
    if not cambiados:
        return {"ok": True, "nada": True, "log": "No hay cambios para publicar."}

    archivos = []
    for rel in cambiados:
        b = contenidos[rel]
        if rel.endswith(".js"):
            # normalizar a LF (como git): evita que cada publish muestre todo el
            # archivo "cambiado" solo por el CRLF de Windows.
            txt = b.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
            archivos.append({"path": "intranet/" + rel, "content": txt, "encoding": "utf-8"})
        else:
            archivos.append({"path": "intranet/" + rel, "content": base64.b64encode(b).decode("ascii"), "encoding": "base64"})

    # Cloudflare (plan free) permite ~50 subrequests por invocacion del Worker
    # (1 blob por archivo + overhead), asi que mandamos en LOTES aunque cambien
    # muchos archivos de una. Normalmente cambian pocos y va en un solo lote.
    #
    # Ademas del tope por CANTIDAD hay uno por PESO: el Worker hace request.json()
    # del lote entero, lo vuelve a stringify-ear y el Durable Object lo re-parsea
    # (worker.js:32,37,96,125) => conviven ~4 copias del texto dentro del limite de
    # 128 MB de memoria por isolate. Con imagenes de <1,5 MB nunca importo, pero un
    # solo video hace estallar eso y el error vuelve como un 500 opaco.
    LOTE = 40
    LOTE_BYTES = 20 * 1024 * 1024        # peso del contenido YA codificado del lote
    lotes, actual_lote, peso = [], [], 0
    for a in archivos:
        p = len(a["content"])
        # un archivo solo mas grande que el tope igual tiene que viajar: va en su
        # propio lote (el tope de subida lo mantiene por debajo del limite real)
        if actual_lote and (len(actual_lote) >= LOTE or peso + p > LOTE_BYTES):
            lotes.append(actual_lote)
            actual_lote, peso = [], 0
        actual_lote.append(a)
        peso += p
    if actual_lote:
        lotes.append(actual_lote)
    commits = []
    for k, lote in enumerate(lotes):
        msg = mensaje or "Actualizacion desde el panel"
        if len(lotes) > 1:
            msg += " (parte %d/%d)" % (k + 1, len(lotes))
        body = json.dumps({"mensaje": msg, "archivos": lote}).encode("utf-8")
        req = urllib.request.Request(CEREBRO_URL + "/publish", data=body, method="POST")
        req.add_header("Authorization", "Bearer " + PUBLISH_TOKEN)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "PanelMyS/1.0")   # el UA por defecto de Python lo bloquea Cloudflare (error 1010)
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                r = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detalle = ""
            try:
                detalle = json.loads(e.read().decode("utf-8")).get("error", "")
            except Exception:  # noqa
                pass
            # Clave rechazada: no es un error para mostrar y abandonar, es una
            # clave para VOLVER A PEDIR. Sin esto, una clave mal pegada dejaba
            # a la persona presa de un toast eterno, sin ninguna pantalla
            # donde corregirla.
            if e.code == 401:
                msj = ("La clave cargada no es valida. Pegala de nuevo "
                       "(solo el valor, sin el nombre de adelante).")
                return {"ok": False, "falta_token": True,
                        "log": chr(10).join(log + [msj])}
            cual = "clave de publicacion invalida" if e.code == 401 else detalle
            return {"ok": False, "log": "El cerebro rechazo la publicacion (HTTP %d). %s" % (e.code, cual)}
        except Exception as e:  # noqa
            return {"ok": False, "log": "No pude contactar el cerebro: %s" % e}
        if not r.get("ok"):
            return {"ok": False, "log": "El cerebro no pudo publicar: %s" % r.get("error", "")}
        commits.append((r.get("commit") or "")[:8])

    # exito TOTAL -> guardar el manifiesto nuevo (si falla algun lote no se guarda,
    # asi el proximo intento reintenta todo; re-commitear lo ya subido es inofensivo)
    try:
        if PUBLISH_MANIFEST:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(PUBLISH_MANIFEST, "w", encoding="utf-8") as fh:
                json.dump(actual, fh)
    except OSError:
        pass
    log.append("Publicado: %d archivo(s) en %d commit(s). Vercel actualiza en ~30s." %
               (len(archivos), len(commits)))
    return {"ok": True, "log": "\n".join(log), "commit": commits[-1] if commits else None}


# =====================================================================
#  Colaboracion central <-> colaborador (Fase 2)
# =====================================================================
#  Modelo: ESTA PC (central) es la unica con git+credenciales; las otras
#  (colaboradores en la misma red local) editan una copia local y mandan
#  PROPUESTAS al central. El central las revisa (Bandeja de aprobaciones),
#  las APLICA a su copia (espeja solo los archivos "gestionados") y despues
#  publica con el boton de siempre. Nada de git corre nunca en el colaborador.
#
#  "Archivos gestionados" = lo unico que el panel deja editar y, por lo tanto,
#  lo unico que viaja/se aplica de una propuesta:
#     - intranet/modulos.js
#     - intranet/assets/<seccion>/*   (las 7 secciones)
#     - intranet/assets/_modulos/*    (imagenes de contenido de modulos)
#  El CODIGO del sitio (index.html, app.js, galerias.js, etc.) NUNCA se pisa
#  con una propuesta: galerias.js se regenera localmente tras aplicar.
CENTRAL_TIMEOUT = 40                     # segundos para hablar con la central
SECCIONES_ASSETS = list(SECCIONES) + ["_modulos"]


def _pc():
    return os.environ.get("COMPUTERNAME") or "PC"


def _es_gestionado_rel(rel):
    """True si un path relativo (posix, dentro de intranet/) es un archivo gestionado."""
    rel = rel.replace("\\", "/").lstrip("/")
    if rel == "modulos.js":
        return True
    partes = rel.split("/")
    return len(partes) >= 3 and partes[0] == "assets" and partes[1] in SECCIONES_ASSETS


def rel_gestionados(base_intranet):
    """relpaths (posix) de los archivos gestionados que existen bajo una carpeta intranet."""
    rels = []
    if os.path.isfile(os.path.join(base_intranet, "modulos.js")):
        rels.append("modulos.js")
    for sec in SECCIONES_ASSETS:
        d = os.path.join(base_intranet, "assets", sec)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if os.path.isfile(os.path.join(d, f)):
                    rels.append("assets/%s/%s" % (sec, f))
    return rels


def _zip_seguro(nombres):
    """Aborta si algun nombre del zip intenta escapar (path traversal / drive / UNC / ADS)."""
    for n in nombres:
        crudo = n
        n = n.replace("\\", "/")
        if (n.startswith("/") or ".." in n.split("/") or ":" in crudo
                or crudo.startswith("\\\\") or crudo.startswith("//")):
            raise ValueError("ruta insegura en el paquete: %s" % crudo)


def resumen_local():
    """Conteos para que la central sepa de un vistazo que trae la propuesta."""
    r = {"modulos": len(leer_modulos())}
    for sec in SECCIONES:
        r[sec] = len(listar(sec))
    return r


# ---------- lado COLABORADOR: armar y enviar propuesta, traer snapshot ----------
def propuesta_zip():
    """Zip con TODOS los archivos gestionados locales (mirror para la central)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in rel_gestionados(INTRANET):
            z.write(os.path.join(INTRANET, *rel.split("/")), rel)
    return buf.getvalue()


def enviar_propuesta(mensaje):
    if ES_CENTRAL:
        return {"ok": False, "error": "Esta PC es la central: no manda propuestas, las recibe."}
    if not CENTRAL_URL:
        return {"ok": False, "error": "No esta configurada la direccion de la central (central_url en panel_config.json)."}
    data = propuesta_zip()
    req = urllib.request.Request(CENTRAL_URL + "/inbox", data=data, method="POST")
    req.add_header("Content-Type", "application/zip")
    req.add_header("X-Usuario", quote(USUARIO))
    req.add_header("X-PC", quote(_pc()))
    req.add_header("X-Mensaje", quote(mensaje or ""))
    req.add_header("X-Resumen", quote(json.dumps(resumen_local(), ensure_ascii=False)))
    try:
        with urllib.request.urlopen(req, timeout=CENTRAL_TIMEOUT) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return {"ok": False, "error": "No me pude conectar con la central. Fijate que este prendida y en la misma red. (%s)" % e}
    except Exception as e:  # noqa
        return {"ok": False, "error": str(e)}
    return {"ok": True, "id": out.get("id"), "bytes": len(data)}


def _bajar_con_progreso(url, timeout, jid, tope_pct=88):
    """Descarga `url` a memoria informando el avance al job: si el servidor
    declara el tamano total, el porcentaje sube hasta tope_pct; si no (GitHub
    manda el zip sin Content-Length), va contando los MB bajados."""
    req = urllib.request.Request(url, headers={"User-Agent": "PanelMyS/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = int(r.headers.get("Content-Length") or 0)
        partes = []
        bajado = 0
        while True:
            trozo = r.read(256 * 1024)
            if not trozo:
                break
            partes.append(trozo)
            bajado += len(trozo)
            if jid:
                mb = bajado // 1048576
                if total:
                    _job_set(jid, pct=int(bajado * tope_pct / total),
                             msg="Descargando la última versión… %d de %d MB" % (mb, total // 1048576))
                else:
                    _job_set(jid, msg="Descargando la última versión… %d MB" % mb)
    return b"".join(partes)


def _volcar_zip_en_intranet(data, mapear=None):
    """Escribe en intranet/ las entradas de un zip y despues BORRA lo que el
    paquete ya no trae (espejo: la copia local queda IGUAL a lo publicado, sin
    archivos viejos acumulados). Solo borra si el paquete luce completo
    (index + modulos): un zip roto o a medias jamas puede vaciar la intranet.
    `mapear` traduce cada nombre del zip a su ruta relativa (None = saltear)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        pares = []
        for n in z.namelist():
            if n.endswith("/"):
                continue
            rel = n.replace("\\", "/")
            if mapear is not None:
                rel = mapear(rel)
                if rel is None:
                    continue
            pares.append((n, rel))
        if not pares:
            raise ValueError("el paquete no trae archivos de la intranet")
        _zip_seguro([rel for _n, rel in pares])
        for n, rel in pares:
            dest = os.path.join(INTRANET, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(n) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
        # ---- espejo: sacar lo que el paquete ya no trae ----
        traidos = set(rel.replace("\\", "/").casefold() for _n, rel in pares)
        completo = "modulos.js" in traidos and "index.html" in traidos
        if completo:
            for raiz, _dirs, files in os.walk(INTRANET, topdown=False):
                for f in files:
                    full = os.path.join(raiz, f)
                    rel = os.path.relpath(full, INTRANET).replace("\\", "/").casefold()
                    if rel not in traidos:
                        try:
                            os.remove(full)
                        except OSError:
                            pass
                if raiz != INTRANET:
                    try:
                        if not os.listdir(raiz):
                            os.rmdir(raiz)
                    except OSError:
                        pass
        return len(pares)


def _mapear_repo(rel):
    """En el zip del repo todo cuelga de '<carpeta>/' y la intranet es la
    subcarpeta intranet/. Devuelve la ruta relativa a intranet/ o None."""
    partes = rel.split("/")
    if len(partes) >= 3 and partes[1] == "intranet":
        return "/".join(partes[2:])
    return None


def traer_de_central(jid=None):
    """Reemplaza la copia local de intranet/ con la ultima version publicada.
    Primero por INTERNET (el repo publico: la misma fuente que ve la web);
    si eso falla, con la central por Tailscale como siempre. Si le pasan un
    job, va informando cada etapa para la barra de progreso del frontend."""
    if ES_CENTRAL:
        return {"ok": False, "error": "Esta PC es la central: ya tiene la ultima version."}
    fallas = []
    if REPO_ZIP:
        try:
            if jid:
                _job_set(jid, pct=1, msg="Conectando con el cerebro…")
            data = _bajar_con_progreso(REPO_ZIP, 120, jid)
            if jid:
                _job_set(jid, pct=92, msg="Instalando la nueva versión…")
            _volcar_zip_en_intranet(data, _mapear_repo)
            _guardar_sello(_sello_publicado())   # quedamos al dia
            return {"ok": True, "fuente": "internet"}
        except Exception as e:  # noqa
            fallas.append("internet: %s" % e)
    if not CENTRAL_URL:
        return {"ok": False, "error": "No pude bajar la ultima version por internet. (%s)" % "; ".join(fallas)}
    try:
        if jid:
            _job_set(jid, pct=2, msg="Internet no respondió; probando con la computadora central…")
        data = _bajar_con_progreso(CENTRAL_URL + "/snapshot", CENTRAL_TIMEOUT, jid)
        if jid:
            _job_set(jid, pct=92, msg="Instalando la nueva versión…")
        _volcar_zip_en_intranet(data)
        return {"ok": True, "fuente": "central"}
    except Exception as e:  # noqa
        fallas.append("central: %s" % e)
        return {"ok": False, "error": "No pude bajar la ultima version ni por internet ni de la central. (%s)" % "; ".join(fallas)}


# =====================================================================
#  AUTO-UPDATE del programa (solo colaborador; la central la actualiza el dev)
# =====================================================================
def _sello_local():
    """El ETag del contenido que esta PC ya tiene. Vacio = nunca se trajo nada."""
    if not SELLO_CONTENIDO or not os.path.isfile(SELLO_CONTENIDO):
        return ""
    try:
        with open(SELLO_CONTENIDO, encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("etag", "")
    except (ValueError, OSError):
        return ""


def _guardar_sello(etag):
    if not (SELLO_CONTENIDO and etag):
        return
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(SELLO_CONTENIDO, "w", encoding="utf-8") as fh:
            json.dump({"etag": etag, "ts": int(time.time())}, fh)
    except OSError:
        pass


def _sello_publicado(timeout=8):
    """El ETag de modulos.js en la web. Un HEAD: no baja el archivo.

    Es la forma barata de preguntar 'cambio algo?': Vercel devuelve ETag y
    Last-Modified, y el pedido no descarga ni un byte del contenido."""
    if not WEB_PUBLICA:
        return ""
    try:
        req = urllib.request.Request(WEB_PUBLICA + "/intranet/modulos.js",
                                     headers={"User-Agent": "PanelMyS/1.0"},
                                     method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (r.headers.get("ETag") or r.headers.get("Last-Modified") or "").strip()
    except Exception:  # noqa
        return ""


def novedades(timeout=8):
    """UNA sola respuesta para UN solo boton.

    Al equipo no le importa si lo nuevo es el programa o el contenido: quiere
    estar al dia. Antes eran dos botones ('Actualizar a la ultima version' y
    'Traer ultima version') y habia que saber cual apretar, ademas de que el
    segundo bajaba a ciegas, sin decir si habia algo nuevo.

    Devuelve que hay pendiente de cada cosa. El programa se compara por numero
    de version; el contenido, por el ETag de modulos.js contra el que esta PC
    tiene aplicado."""
    prog = chequear_update(timeout)
    hay_prog = bool(prog.get("disponible"))

    remoto = _sello_publicado(timeout)
    local = _sello_local()
    # Sin sello local no se puede afirmar que haya novedad: se siembra con el
    # valor actual para que el primer aviso sea por un cambio de verdad y no
    # por no tener con que comparar.
    if remoto and not local:
        _guardar_sello(remoto)
        local = remoto
    hay_cont = bool(remoto and local and remoto != local)

    return {
        "hay": hay_prog or hay_cont,
        "programa": {"hay": hay_prog, "version": prog.get("version"),
                     "local": prog.get("local"), "label": prog.get("label", ""),
                     "notas": prog.get("notes", "")},
        "contenido": {"hay": hay_cont},
        "es_central": bool(prog.get("es_central")),
        "error": prog.get("error", ""),
    }


def chequear_update(timeout=8):
    """Consulta la version publicada y dice si hay una mas nueva que la local.
    Primero por INTERNET (version.json en la web publica); si falla, la central.
    TODOS los roles chequean (v27): el codigo puede publicarse desde cualquier
    maquina con el fuente, asi que la central tambien se actualiza desde la web.
    La central solo mira internet (preguntarse a si misma no informa nada)."""
    data = None
    fallas = []
    if WEB_PUBLICA:
        try:
            nc = str(int(datetime.datetime.now().timestamp()))
            req = urllib.request.Request(WEB_PUBLICA + "/panel/version.json?nc=" + nc,
                                         headers={"User-Agent": "PanelMyS/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa
            fallas.append("internet: %s" % e)
    if data is None and CENTRAL_URL and not ES_CENTRAL:
        try:
            with urllib.request.urlopen(CENTRAL_URL + "/update/version", timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa
            fallas.append("central: %s" % e)
    if data is None:
        return {"disponible": False, "error": "no pude consultar la version (%s)" % "; ".join(fallas), "local": VERSION}
    remota = int(data.get("version") or 0)
    return {
        "disponible": remota > VERSION,
        "version": remota, "local": VERSION,
        "label": data.get("label", ""), "notes": data.get("notes", ""),
        "sha256": data.get("sha256", ""), "size": int(data.get("size") or 0),
        "url": (data.get("url") or "").strip(),
    }


def _lanzar_aplicar():
    """Lanza aplicar.bat DETACHED pasando el PID de este panel. NO sale del proceso
    (el endpoint responde y despues programa el os._exit)."""
    bat = os.path.join(UPDATE_DIR, "aplicar.bat")
    pid = str(os.getpid())
    # CREATE_NO_WINDOW y no DETACHED: el cmd necesita SU consola (timeout /t la
    # usa) pero invisible -- con DETACHED aparecia la ventana negra con el
    # "find <pid>" del actualizador en la cara del usuario.
    NOWIN, NEWGRP, BREAKAWAY = 0x08000000, 0x00000200, 0x01000000
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    try:
        subprocess.Popen(["cmd", "/c", bat, pid],
                         creationflags=NOWIN | NEWGRP | BREAKAWAY, close_fds=True,
                         cwd=sysroot, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        # fallback si BREAKAWAY_FROM_JOB fue rechazado: reintentar sin ese flag pero
        # conservando ventana oculta + grupo nuevo + DEVNULL (sobrevive al os._exit del padre)
        subprocess.Popen(["cmd", "/c", bat, pid],
                         creationflags=NOWIN | NEWGRP, close_fds=True, cwd=sysroot,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def aplicar_update(dry=False, jid=None):
    """Descarga el bundle de la central, VERIFICA tamano+sha256, lo extrae, deja
    listo aplicar.bat y (salvo dry) lanza el swap. Single-flight. Nada toca la
    instalacion si la verificacion falla.

    `jid` es un trabajo para ir contando en que anda. El progreso es REAL: sale
    de los bytes que van llegando, no de un temporizador. Una barra que avanza
    sola mientras el proceso esta trabado miente, y la persona se entera cuando
    el panel no vuelve."""
    global _UPDATE_EN_CURSO
    if not UPDATE_DIR or not os.path.isfile(UPDATER_SRC):
        return {"ok": False, "error": "falta el componente de actualizacion (aplicar.bat)"}
    with _UPDATE_LOCK:
        if _UPDATE_EN_CURSO:
            return {"ok": False, "error": "ya hay una actualizacion en curso"}
        _UPDATE_EN_CURSO = True
    liberar = True
    try:
        if jid:
            _job_set(jid, pct=2, msg="Buscando la versión nueva…")
        info = chequear_update()
        if not info.get("disponible"):
            return {"ok": False, "error": info.get("error") or "no hay actualizacion disponible"}
        # FAIL-CLOSED: sin sha (64 hex) y tamano valido NO se puede verificar -> abortar.
        sha_esp = (info.get("sha256") or "").strip().lower()
        size_esp = int(info.get("size") or 0)
        version_esp = int(info.get("version") or 0)
        if not re.fullmatch(r"[0-9a-f]{64}", sha_esp) or size_esp <= 0:
            return {"ok": False, "error": "la central no informó el hash/tamaño del paquete; no se puede verificar la actualización"}

        os.makedirs(UPDATE_DIR, exist_ok=True)
        # un "lock" huerfano de un intento cortado (ventana cerrada a mano, corte
        # de luz) haria que el proximo aplicar.bat salga sin hacer nada: fuera.
        try:
            os.remove(os.path.join(UPDATE_DIR, "lock"))
        except OSError:
            pass
        new_dir = os.path.join(UPDATE_DIR, "new")
        tmp_new = os.path.join(UPDATE_DIR, "new.tmp")
        part = os.path.join(UPDATE_DIR, "bundle.zip.part")
        final = os.path.join(UPDATE_DIR, "bundle.zip")
        for d in (new_dir, tmp_new):
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
        for f in (part, final):
            if os.path.isfile(f):
                os.remove(f)

        # 1) descargar a .part (pineado por version) con sha256 al vuelo y TOPE de tamano
        h = hashlib.sha256()
        total = 0
        overflow = False
        rel = (info.get("url") or "").strip().lstrip("/")
        if rel and WEB_PUBLICA:
            url = WEB_PUBLICA + "/" + rel + "?v=" + str(version_esp)
        elif CENTRAL_URL and not ES_CENTRAL:
            url = CENTRAL_URL + "/update/bundle?v=" + str(version_esp)
        else:
            return {"ok": False, "error": "no hay de donde bajar el paquete (ni internet ni central)"}
        req_b = urllib.request.Request(url, headers={"User-Agent": "PanelMyS/1.0"})
        if jid:
            _job_set(jid, pct=5, msg="Descargando la versión nueva…")
        ultimo_aviso = 0
        with urllib.request.urlopen(req_b, timeout=120) as r, open(part, "wb") as out:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                # avisar cada ~2% para no inundar el estado del trabajo
                if jid and size_esp:
                    pct = 5 + int(total * 75 / size_esp)
                    if pct >= ultimo_aviso + 2:
                        ultimo_aviso = pct
                        _job_set(jid, pct=min(pct, 80),
                                 msg="Descargando… %.0f de %.0f MB" %
                                     (total / 1048576.0, size_esp / 1048576.0))
                if total > size_esp + 1024:      # no dejamos que un server hostil llene el disco
                    overflow = True
                    break
                out.write(chunk)
                h.update(chunk)
        if overflow:
            if os.path.isfile(part):
                os.remove(part)
            return {"ok": False, "error": "el paquete llegó más grande de lo declarado; se canceló"}

        # 2) VERIFICAR (OBLIGATORIO) antes de tocar nada
        if jid:
            _job_set(jid, pct=82, msg="Revisando que el archivo llegó completo…")
        if total != size_esp:
            os.remove(part)
            return {"ok": False, "error": "la descarga quedó incompleta (%d de %d bytes). Probá de nuevo." % (total, size_esp)}
        if h.hexdigest() != sha_esp:
            os.remove(part)
            return {"ok": False, "error": "el archivo llegó corrupto (sha256 no coincide). Probá de nuevo."}

        # 3) espacio libre defensivo (>=3x el bundle) antes de extraer
        try:
            if shutil.disk_usage(UPDATE_DIR).free < total * 3:
                os.remove(part)
                return {"ok": False, "error": "no hay suficiente espacio en disco para actualizar"}
        except Exception:  # noqa
            pass
        if jid:
            _job_set(jid, pct=88, msg="Preparando la instalación…")
        os.replace(part, final)

        # 4) extraer a new.tmp\ con guardas anti path-traversal
        with zipfile.ZipFile(final) as z:
            nombres = [n for n in z.namelist() if not n.endswith("/")]
            _zip_seguro(nombres)
            z.extractall(tmp_new)
        if not os.path.isfile(os.path.join(tmp_new, "PanelMyS.exe")):
            shutil.rmtree(tmp_new, ignore_errors=True)
            return {"ok": False, "error": "el paquete no trae el programa (PanelMyS.exe)"}
        # espejo del ASSERT del server: el bundle JAMAS debe traer archivos per-maquina
        _prohibidos = {"panel_config.json", "proyecto.txt", "identity.json"}
        for _raiz, _dirs, _files in os.walk(tmp_new):
            if any(f.lower() in _prohibidos for f in _files):
                shutil.rmtree(tmp_new, ignore_errors=True)
                return {"ok": False, "error": "el paquete trae archivos que no debería; se canceló por seguridad"}

        # 5) marker de extraccion COMPLETA + commit ATOMICO (rename new.tmp -> new)
        with open(os.path.join(tmp_new, "update_ok.marker"), "w", encoding="utf-8") as f:
            f.write("ok")
        os.rename(tmp_new, new_dir)
        shutil.copy(UPDATER_SRC, os.path.join(UPDATE_DIR, "aplicar.bat"))

        if dry:
            return {"ok": True, "dry": True, "new": new_dir, "version": version_esp}

        # 6) en la central puede haber OTRO PanelMyS.exe corriendo (el receptor
        #    oculto que lanza iniciar_receptor.vbs al login): retiene archivos de
        #    la carpeta instalada y el swap fallaria con "no pude mover". Se baja
        #    antes; al reiniciar, el panel levanta su receptor en hilo propio.
        if ES_CENTRAL:
            try:
                subprocess.run(["taskkill", "/F", "/IM", "PanelMyS.exe",
                                "/FI", "PID ne %d" % os.getpid()],
                               creationflags=0x08000000, timeout=15,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:  # noqa
                pass

        # 7) lanzar el swap; el endpoint responde y programa el os._exit
        if jid:
            _job_set(jid, pct=97, msg="Instalando y reiniciando el panel…")
        _lanzar_aplicar()
        liberar = False   # el proceso se va a morir; no re-habilitamos el flag
        return {"ok": True, "aplicando": True, "version": version_esp}
    except Exception as e:  # noqa
        return {"ok": False, "error": str(e)}
    finally:
        if liberar:
            _UPDATE_EN_CURSO = False


def ping_central():
    if not CENTRAL_URL:
        return {"ok": False, "error": "Sin central configurada."}
    try:
        with urllib.request.urlopen(CENTRAL_URL + "/ping", timeout=8) as resp:
            return {"ok": True, "central": json.loads(resp.read().decode("utf-8"))}
    except Exception as e:  # noqa
        return {"ok": False, "error": str(e)}


# ---------- lado CENTRAL: bandeja de aprobaciones ----------
def _pid_seguro(pid):
    return bool(pid) and re.fullmatch(r'[A-Za-z0-9_\-]+', pid) is not None


def listar_aprobaciones():
    out = []
    if not os.path.isdir(APROB_DIR):
        return out
    for pid in sorted(os.listdir(APROB_DIR), reverse=True):
        mp = os.path.join(APROB_DIR, pid, "meta.json")
        if os.path.isfile(mp):
            try:
                out.append(json.load(open(mp, encoding="utf-8-sig")))
            except (ValueError, OSError):
                pass
    return out


def detalle_propuesta(pid):
    """Compara los gestionados de la propuesta contra los actuales del central."""
    if not _pid_seguro(pid):
        return {"error": "id invalido"}
    zpath = os.path.join(APROB_DIR, pid, "paquete.zip")
    if not os.path.isfile(zpath):
        return {"error": "no encuentro la propuesta"}
    nuevos, modificados, borrados, iguales = [], [], [], 0
    with zipfile.ZipFile(zpath) as z:
        nombres = [n.replace("\\", "/") for n in z.namelist() if not n.endswith("/")]
        _zip_seguro(nombres)
        en_prop = [n for n in nombres if _es_gestionado_rel(n)]
        for rel in sorted(en_prop):
            fp = os.path.join(INTRANET, *rel.split("/"))
            if not os.path.isfile(fp):
                nuevos.append(rel)
            elif open(fp, "rb").read() == z.read(rel):
                iguales += 1
            else:
                modificados.append(rel)
    prop_set = set(en_prop)
    for rel in rel_gestionados(INTRANET):
        if rel not in prop_set:
            borrados.append(rel)
    return {"nuevos": nuevos, "modificados": modificados, "borrados": borrados, "iguales": iguales}


def aplicar_propuesta(pid):
    """Espeja los archivos gestionados de la propuesta en la copia local del central,
    regenera galerias.js y deja los cambios listos para revisar y Publicar."""
    if not ES_CENTRAL:
        return {"ok": False, "error": "Solo la central aplica propuestas."}
    if not _pid_seguro(pid):
        return {"ok": False, "error": "id invalido"}
    carpeta = os.path.join(APROB_DIR, pid)
    zpath = os.path.join(carpeta, "paquete.zip")
    if not os.path.isfile(zpath):
        return {"ok": False, "error": "no encuentro la propuesta"}

    with zipfile.ZipFile(zpath) as z:
        nombres = [n.replace("\\", "/") for n in z.namelist() if not n.endswith("/")]
        _zip_seguro(nombres)
        gestion_zip = set(n for n in nombres if _es_gestionado_rel(n))
        # 1) escribir/actualizar los gestionados que trae la propuesta
        for rel in gestion_zip:
            dest = os.path.join(INTRANET, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(rel) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    # 2) mirror: borrar los gestionados actuales que la propuesta ya no tiene
    for rel in rel_gestionados(INTRANET):
        if rel not in gestion_zip:
            fp = os.path.join(INTRANET, *rel.split("/"))
            if os.path.isfile(fp):
                os.remove(fp)
    # 3) regenerar galerias.js (nunca viaja en la propuesta)
    regenerar_galerias()
    # 4) marcar la propuesta como aplicada (queda archivada, no vuelve a aparecer)
    mp = os.path.join(carpeta, "meta.json")
    try:
        meta = json.load(open(mp, encoding="utf-8-sig"))
    except (ValueError, OSError):
        meta = {}
    meta["estado"] = "aplicada"
    meta["aplicada_en"] = datetime.datetime.now().isoformat(timespec="seconds")
    json.dump(meta, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "aplicados": len(gestion_zip)}


def rechazar_propuesta(pid):
    if not _pid_seguro(pid):
        return {"ok": False, "error": "id invalido"}
    carpeta = os.path.join(APROB_DIR, pid)
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta, ignore_errors=True)
    return {"ok": True}


def aprobaciones_pendientes():
    return [a for a in listar_aprobaciones() if a.get("estado") == "pendiente"]


# =====================================================================
#  Modulos (botones del menu) - leer/escribir modulos.js
# =====================================================================
def leer_modulos():
    if not os.path.exists(MODULOS_JS):
        return []
    txt = open(MODULOS_JS, encoding="utf-8").read()
    i, j = txt.find("["), txt.rfind("]")
    if i == -1 or j == -1 or j < i:
        return []
    try:
        return json.loads(txt[i:j + 1])
    except ValueError:
        return []


def escribir_modulos(lista):
    cuerpo = json.dumps(lista, ensure_ascii=False, indent=2)
    with open(MODULOS_JS, "w", encoding="utf-8") as fh:
        fh.write("/* Generado/editado por el Panel de administracion. Define los modulos (botones)\n"
                 "   de la intranet. builtin:true = el contenido vive en index.html (no editable\n"
                 "   desde el panel); builtin:false = modulo creado en el panel, su texto esta en \"body\". */\n")
        fh.write("window.MODULES = " + cuerpo + ";\n")


def leer_originales():
    if not os.path.exists(ORIGINALES):
        return {}
    try:
        return json.load(open(ORIGINALES, encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def validar_content(c):
    """Sanea el objeto content de un modulo. Devuelve dict valido o None."""
    if not isinstance(c, dict):
        return None
    tipo = c.get("tipo")
    if tipo not in TIPOS_CONTENT:
        return None
    if tipo == "html":
        return {"tipo": "html", "html": str(c.get("html") or "")}
    if tipo == "bloques":
        bl = c.get("bloques")
        out = {"tipo": "bloques",
               "bloques": bl if isinstance(bl, list) else [],
               "html": str(c.get("html") or "")}
        if c.get("presentacion"):
            out["presentacion"] = True     # el modulo se ve como diapositivas
        return out
    if tipo == "coleccion":
        # biblioteca: el modulo guarda VARIOS documentos (ej. un reporte por mes)
        docs = []
        for d in (c.get("docs") or []):
            if not isinstance(d, dict):
                continue
            titulo = str(d.get("titulo") or "").strip()
            if not titulo:
                continue
            bl = d.get("bloques")
            docs.append({
                "id": str(d.get("id") or "")[:40] or slug(titulo),
                "titulo": titulo[:80],
                "etiqueta": str(d.get("etiqueta") or "").strip()[:40],
                "archivado": bool(d.get("archivado")),
                "presentacion": bool(d.get("presentacion")),
                "bloques": bl if isinstance(bl, list) else [],
                "html": str(d.get("html") or ""),
            })
        if not docs:
            return None
        # como llama el usuario a cada pieza ("reporte", "capacitacion"...)
        palabra = re.sub(r"[^0-9a-záéíóúüñ ]", "", str(c.get("palabra") or "").strip().lower())[:20]
        return {"tipo": "coleccion", "palabra": palabra or "documento", "docs": docs}
    if tipo in ("cartelera", "muro"):
        # muro: el modulo es un feed de publicaciones. Misma forma que la
        # biblioteca (docs) mas quien publica, cuando y de que tipo.
        def _post(d):
            """Sanea una publicacion. Devuelve None si no sirve."""
            if not isinstance(d, dict):
                return None
            titulo = str(d.get("titulo") or "").strip()
            if not titulo:
                return None
            fecha = str(d.get("fecha") or "").strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
                fecha = ""          # sin fecha valida la intranet no muestra nada
            # ultimo dia que se ve; despues la intranet la esconde sola
            vence = str(d.get("vence") or "").strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", vence):
                vence = ""
            etiqueta = str(d.get("etiqueta") or "").strip().lower()
            # ARCHIVAR EN UN MODULO: la publicacion no se copia a ningun lado,
            # solo deja anotado a que modulo pertenece. La intranet pregunta
            # cuales lo señalan y las dibuja ahi. Por eso corregirla o borrarla
            # se ve en los dos lugares sin sincronizar nada.
            archivar = str(d.get("archivar") or "").strip()
            if not re.match(r"^[a-z0-9_-]{1,60}$", archivar):
                archivar = ""
            bl = d.get("bloques")
            return {
                "id": str(d.get("id") or "")[:40] or slug(titulo),
                "titulo": titulo[:120],
                "autor": str(d.get("autor") or "").strip()[:40],
                "sucursal": str(d.get("sucursal") or "").strip()[:40],
                "fecha": fecha,
                "etiqueta": etiqueta if etiqueta in ETIQUETAS_MURO else "",
                "fijado": bool(d.get("fijado")),
                "confirmar": bool(d.get("confirmar")),   # pide acuse de lectura
                "vence": vence,
                "archivado": bool(d.get("archivado")),
                "archivar": archivar,
                "bloques": bl if isinstance(bl, list) else [],
                "html": str(d.get("html") or ""),
            }

        posts = []
        for d in (c.get("docs") or []):
            po = _post(d)
            if po:
                posts.append(po)

        # PAPELERA: lo que se elimina no se pierde, queda DIAS_PAPELERA dias por
        # si fue sin querer. Vive aparte de docs, asi la intranet no la ve nunca.
        # El vencimiento se aplica ACA porque es el unico lugar por el que pasa
        # todo lo que se guarda: si dependiera del panel, una papelera vieja
        # sobreviviria para siempre en la maquina de quien no abre esa pantalla.
        hoy = datetime.date.today()
        papelera = []
        for d in (c.get("papelera") or []):
            po = _post(d)
            if not po:
                continue
            borrado = str((d or {}).get("borradoEl") or "").strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", borrado):
                borrado = hoy.isoformat()      # sin fecha, se cuenta desde hoy
            try:
                cuando = datetime.date.fromisoformat(borrado)
            except ValueError:
                cuando = hoy
            if (hoy - cuando).days >= DIAS_PAPELERA:
                continue                        # se cumplio el plazo: se va
            po["borradoEl"] = borrado
            papelera.append(po)

        # un muro sin publicaciones validas sigue siendo un muro: si devolviera
        # None, validar_modulos no escribiria "content" y el modulo perderia su
        # tipo en silencio (respondiendo "Guardado" igual)
        # se guarda SIEMPRE con el nombre nuevo: asi lo viejo se migra solo
        # la primera vez que alguien toca Guardar
        return {"tipo": "cartelera", "docs": posts, "papelera": papelera}
    if tipo == "embed":
        return {"tipo": "embed", "url": str(c.get("url") or "").strip()}
    if tipo == "imagen":
        return {"tipo": "imagen", "src": str(c.get("src") or "").strip(),
                "download": str(c.get("download") or "").strip()}
    if tipo == "link":
        return {"tipo": "link", "url": str(c.get("url") or "").strip(),
                "texto": str(c.get("texto") or "").strip()}
    return None


def contenido_actual(key):
    """Lo que muestra hoy un modulo + su original del sistema (para 'restaurar')."""
    mods = {m.get("key"): m for m in leer_modulos()}
    m = mods.get(key, {})
    return {
        "key": key,
        "builtin": bool(m.get("builtin")),
        "esDescargables": key == "descargables",
        "original": leer_originales().get(key),   # HTML diseñado original (o None)
        "content": m.get("content"),              # override actual (o None)
    }


def slug(texto):
    s = texto.lower().strip()
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    for a, b in reemplazos.items():
        s = s.replace(a, b)
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    return s or "modulo"


def validar_modulos(lista):
    """Sanea y valida la lista recibida del panel. Devuelve (lista_ok, error)."""
    if not isinstance(lista, list) or not lista:
        return None, "La lista de modulos esta vacia."
    previos = {m.get("key"): m for m in leer_modulos()}
    vistos, salida = set(), []
    for m in lista:
        if not isinstance(m, dict):
            return None, "Modulo invalido."
        title = (m.get("title") or "").strip()
        if not title:
            return None, "Cada modulo necesita un titulo."
        key = (m.get("key") or "").strip() or slug(title)
        key = slug(key)
        # claves unicas
        base, i = key, 2
        while key in vistos:
            key = "%s_%d" % (base, i); i += 1
        vistos.add(key)
        builtin = bool(previos.get(key, {}).get("builtin")) if key in previos else bool(m.get("builtin"))
        icon = m.get("icon") if m.get("icon") in ICONOS_VALIDOS else "layers"
        color = m.get("color") if m.get("color") in COLORES_VALIDOS else "--c-hudson"
        out = {
            "key": key,
            "title": title,
            "desc": (m.get("desc") or "").strip(),
            "icon": icon,
            "color": color,
            "ready": bool(m.get("ready", True)),
            "builtin": builtin,
        }
        if m.get("hidden"):
            out["hidden"] = True
        # fecha del ultimo cambio (AAAA-MM-DD): la intranet marca con esto las
        # novedades para los vendedores. Se valida el formato para que no entre
        # cualquier cosa al archivo publicado.
        act = (m.get("actualizado") or "").strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", act):
            out["actualizado"] = act
        if not builtin and m.get("body") and not m.get("content"):
            out["body"] = m.get("body")
        c = validar_content(m.get("content"))
        if c:
            out["content"] = c     # contenido propio/reemplazado (permitido en cualquier módulo)
        salida.append(out)
    # asegurar que no se pierdan modulos builtin (su contenido vive en codigo)
    faltan = [m for k, m in previos.items() if m.get("builtin") and k not in vistos]
    salida.extend(faltan)  # se reanexan ocultos al final para no romper el sitio
    for m in faltan:
        m.setdefault("hidden", True)
    return salida, None


# =====================================================================
#  HTTP handler
# =====================================================================
class Handler(BaseHTTPRequestHandler):
    server_version = "PanelMyS/1.0"

    # --- helpers de respuesta ---
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _htm(self, html, code=200):
        """Manda una pagina HTML entera. La usa el reporte con diseno, que se
        abre en una pestana en vez de bajarse como archivo."""
        body = html.encode("utf-8") if isinstance(html, str) else html
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ═══════════════════ SECCION DATOS ═══════════════════
    # Todo lo de aca es LOCAL: lee una planilla de la maquina o de la cuenta de
    # Drive de marketing, y devuelve numeros. Nada sale a internet, y lo que se
    # publica a la intranet lo decide una persona, numero por numero.

    def _datos_get(self, path, q):
        if datos_api is None:
            return self._json({"error": "la seccion Datos no cargo: %s" % _datos_error}, 500)
        cfg = datos_api.cargar(STATE_DIR)

        if path == "/api/datos/estado":
            # la lista entera: cada reporte con su planilla y cuanto publica
            reps = []
            for r in cfg.get("reportes") or []:
                f = r.get("fuente") or {}
                reps.append({
                    "id": r.get("id"),
                    "titulo": r.get("titulo") or "Reporte",
                    "tipo": f.get("tipo") or "",
                    "archivo": f.get("archivo") or os.path.basename(f.get("ruta") or ""),
                    # que se vea cual se lee por link publico: es la diferencia
                    # entre "lo ve el equipo" y "lo ve cualquiera"
                    "publica": bool(f.get("clase") == "publico"),
                    "publicados": len(r.get("publicados") or []),
                })
            return self._json({
                "reportes": reps,
                "publicados_total": sum(x["publicados"] for x in reps),
            })

        if path == "/api/datos/google":
            try:
                from datos import google_sheets as gs
            except Exception as e:         # noqa
                return self._json({"disponible": False, "error": str(e)})
            d = gs.estado()
            d["disponible"] = True
            d["client_id"] = bool((cfg.get("google") or {}).get("client_id"))
            # como viene el baile de OAuth, si hay uno en curso
            d["conectando"] = dict(_GOOGLE_BAILE)
            # y la forma simple: la cuenta de servicio. Va aparte para que la
            # pantalla pueda mostrar las dos y decir cual esta en uso.
            try:
                from datos import google_cuenta as gcu
                d["cuenta"] = gcu.estado()
            except Exception as e:         # noqa
                d["cuenta"] = {"conectado": False, "error": str(e)}
            # cual se usa para leer, si estan las dos (datos_api prefiere la
            # cuenta: no se vence y ve menos archivos)
            d["usando"] = "cuenta" if d["cuenta"].get("conectado") else (
                "oauth" if d.get("conectado") else "")
            return self._json(d)

        if path == "/api/datos/google-hojas":
            # Las pestanas de una planilla, con un vistazo a cada una. Se
            # pregunta "que hoja queres" en vez de agarrar la primera: una
            # planilla de trabajo tiene ocho, y solo una es la que se busca.
            link = (q.get("link") or [""])[0]
            if not link:
                return self._json({"error": "falta el link"}, 400)
            try:
                from datos import google_link as gl
                pes = gl.pestanas(link)
            except Exception as e:         # noqa
                return self._json({"error": str(e)}, 400)
            if not pes:
                return self._json({"ok": True, "hojas": [], "sin_lista": True})
            salida = []
            for nombre, gid in pes[:30]:
                v = {}
                try:
                    v = gl.vistazo(link, gid)
                except Exception:          # noqa: una hoja rara no tumba la lista
                    v = {}
                salida.append({
                    "nombre": nombre, "gid": gid,
                    "columnas": (v.get("columnas") or [])[:12],
                    "cuantas": v.get("cuantas") or 0,
                    "sirve": bool(v.get("sirve")),
                    "motivo": v.get("motivo") or "",
                    "aviso": v.get("aviso") or "",
                })
            return self._json({"ok": True, "hojas": salida})

        if path == "/api/datos/google-archivos":
            # La lista de lo que le compartieron a la cuenta del panel, para
            # elegir de ahi en vez de pegar un link.
            try:
                from datos import google_cuenta as gcu
            except Exception as e:         # noqa
                return self._json({"error": str(e)}, 500)
            try:
                arch = gcu.archivos((q.get("buscar") or [""])[0])
            except Exception as e:         # noqa: ya viene en castellano
                return self._json({"error": str(e)}, 400)
            return self._json({"ok": True, "archivos": arch})

        if path == "/api/datos/analizar":
            rid = (q.get("id") or [""])[0]
            rep = datos_api.buscar(cfg, rid)
            if not rep:
                return self._json({"ok": False, "error": "no encuentro ese reporte"}, 404)
            return self._json(datos_api.analizar_fuente(rep, STATE_DIR))

        if path == "/api/datos/deck":
            # El reporte con diseño. Se sirve como HTML entero y no como JSON:
            # se abre en una pestaña, se pasa con las flechas y se imprime a PDF
            # con Ctrl+P. Es el mismo archivo para las tres cosas.
            rep = datos_api.buscar(cfg, (q.get("id") or [""])[0])
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            # ?informe=<id> recorta el reporte al periodo de ese informe; sin
            # el, se mira toda la planilla, como siempre
            inf = datos_api.buscar_informe(rep, (q.get("informe") or [""])[0])
            try:
                html, err = datos_api.deck_derivaciones(rep, STATE_DIR, inf)
            except Exception as ex:        # noqa
                html, err = None, str(ex)
            if err or not html:
                from xml.sax.saxutils import escape as _esc
                html = ("<!doctype html><meta charset='utf-8'><body style='"
                        "font:16px/1.6 system-ui;margin:12vh auto;max-width:34rem;"
                        "color:#333'><h2>No pude armar el reporte</h2><p>%s</p>"
                        "</body>" % _esc(err or "error"))
                return self._htm(html, 400)
            # ?imprimir=1 abre el dialogo de impresion solo: es el boton
            # "Descargar PDF". El PDF lo hace el navegador desde este mismo
            # HTML, asi que sale identico a lo que se ve en pantalla.
            if (q.get("imprimir") or [""])[0] == "1":
                html = html.replace(
                    "</body>",
                    "<script>window.addEventListener('load',function(){"
                    "setTimeout(function(){window.print();},350);});</script>"
                    "</body>", 1)
            return self._htm(html)

        if path == "/api/datos/derivaciones":
            rep = datos_api.buscar(cfg, (q.get("id") or [""])[0])
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            try:
                return self._json(datos_api.resumen_derivaciones(rep, STATE_DIR))
            except Exception as ex:        # noqa
                return self._json({"ok": False, "error": str(ex)}, 400)

        if path == "/api/datos/deck-word":
            # El mismo reporte con diseno, pero en .docx: una lamina por hoja,
            # apaisada. No es el reporte generico de reporte.py, que es otro
            # documento y otra cosa.
            rep = datos_api.buscar(cfg, (q.get("id") or [""])[0])
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            inf = datos_api.buscar_informe(rep, (q.get("informe") or [""])[0])
            try:
                ruta, err = datos_api.deck_derivaciones_word(
                    rep, STATE_DIR, inf)
            except Exception as ex:        # noqa
                ruta, err = None, str(ex)
            if err or not ruta:
                return self._json({"error": err or "no pude armarlo"}, 400)
            return self._file(
                ruta, "application/vnd.openxmlformats-officedocument"
                      ".wordprocessingml.document",
                nombre=os.path.basename(ruta))

        if path == "/api/datos/reporte":
            formato = (q.get("formato") or ["html"])[0]
            rep = datos_api.buscar(cfg, (q.get("id") or [""])[0])
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            ruta, err = datos_api.armar_reporte(rep, STATE_DIR, formato)
            if err:
                return self._json({"error": err}, 400)
            tipo = ("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document" if formato == "word"
                    else "text/html; charset=utf-8")
            # `descargar` hace que el navegador lo baje en vez de abrirlo: para
            # el Word es lo unico que sirve, y para el HTML depende de si se
            # quiere imprimir (abrirlo) o guardarlo.
            baja = formato == "word" or (q.get("descargar") or [""])[0] == "1"
            return self._file(ruta, tipo, nombre=os.path.basename(ruta) if baja else "")

        return self._json({"error": "no existe %s" % path}, 404)

    def _datos_post(self, path):
        if datos_api is None:
            return self._json({"error": "la seccion Datos no cargo: %s" % _datos_error}, 500)
        try:
            largo = int(self.headers.get("Content-Length") or 0)
            cuerpo = json.loads(self.rfile.read(largo).decode("utf-8")) if largo else {}
        except Exception as e:              # noqa
            return self._json({"error": "no entendi el pedido: %s" % e}, 400)
        cfg = datos_api.cargar(STATE_DIR)

        if path == "/api/datos/fuente":
            # crea un reporte nuevo, o le cambia la planilla a uno que ya existe
            ruta = str(cuerpo.get("ruta") or "").strip().strip('"')
            if not ruta or not os.path.isfile(ruta):
                return self._json({"error": "no encuentro ese archivo"}, 400)
            fuente = {"tipo": "csv" if ruta.lower().endswith(".csv") else "xlsx",
                      "ruta": ruta, "archivo": os.path.basename(ruta)}
            titulo = str(cuerpo.get("titulo") or "").strip()
            rid = str(cuerpo.get("id") or "").strip()
            rep = datos_api.buscar(cfg, rid) if rid else None
            if rep:
                rep["fuente"] = fuente
                if titulo:
                    rep["titulo"] = titulo
                # ⚠️ al cambiarle la planilla a un reporte se BORRA lo publicado.
                # Los numeros de la anterior no tienen por que valer para esta,
                # y arrastrarlos publicaria algo que nadie miro.
                rep["publicados"] = []
            else:
                if len(cfg.get("reportes") or []) >= 30:
                    return self._json({"error": "ya hay 30 reportes, es demasiado"}, 400)
                rep = {"id": datos_api.nuevo_id(),
                       "titulo": titulo or os.path.splitext(fuente["archivo"])[0],
                       "fuente": fuente, "publicados": []}
                cfg.setdefault("reportes", []).append(rep)
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "id": rep["id"], "titulo": rep["titulo"],
                               "archivo": fuente["archivo"]})

        if path == "/api/datos/google-conectar":
            try:
                from datos import google_sheets as gs
            except Exception as e:         # noqa
                return self._json({"error": "no cargo el modulo: %s" % e}, 500)
            cid = str(cuerpo.get("client_id") or "").strip()
            sec = str(cuerpo.get("client_secret") or "").strip()
            if not cid:
                g = cfg.get("google") or {}
                cid, sec = g.get("client_id") or "", g.get("client_secret") or ""
            if not cid:
                return self._json({"error": "falta el ID de cliente de Google"}, 400)
            # se guarda para no tener que pegarlo cada vez. Va a la carpeta de
            # estado, que esta fuera del proyecto: no puede llegar al sitio.
            cfg["google"] = {"client_id": cid, "client_secret": sec}
            datos_api.guardar(STATE_DIR, cfg)

            if _GOOGLE_BAILE.get("estado") == "esperando":
                return self._json({"ok": True, "ya": True})

            # ⚠️ EN UN HILO: conectar() abre el navegador y espera a que la
            # persona acepte. En el hilo que atiende pedidos, el panel entero
            # quedaria congelado mientras tanto.
            def _bailar():
                _GOOGLE_BAILE.update({"estado": "esperando", "error": ""})
                try:
                    gs.conectar(cid, sec)
                    _GOOGLE_BAILE.update({"estado": "listo", "error": ""})
                except Exception as e:     # noqa: se lo cuenta a la pantalla
                    _GOOGLE_BAILE.update({"estado": "error", "error": str(e)})

            threading.Thread(target=_bailar, daemon=True).start()
            return self._json({"ok": True, "esperando": True})

        if path == "/api/datos/google-cuenta":
            # Llega el archivo .json que bajo de Google, pegado entero. Trae una
            # clave privada: no se loguea, no se devuelve, y el modulo se niega
            # a guardarlo en una carpeta que se publique.
            try:
                from datos import google_cuenta as gcu
            except Exception as e:         # noqa
                return self._json({"error": "no cargo el modulo: %s" % e}, 500)
            try:
                r = gcu.guardar(str(cuerpo.get("json") or ""))
            except Exception as e:         # noqa: viene en castellano
                return self._json({"error": str(e)}, 400)
            return self._json({"ok": True, "mail": r["mail"]})

        if path == "/api/datos/google-cuenta-borrar":
            try:
                from datos import google_cuenta as gcu
            except Exception as e:         # noqa
                return self._json({"error": str(e)}, 500)
            gcu.desconectar()
            return self._json({"ok": True})

        if path == "/api/datos/google-desconectar":
            try:
                from datos import google_sheets as gs
            except Exception as e:         # noqa
                return self._json({"error": str(e)}, 500)
            gs.desconectar()
            _GOOGLE_BAILE.clear()
            return self._json({"ok": True})

        if path == "/api/datos/fuente-google":
            link = str(cuerpo.get("link") or "").strip()
            if not link:
                return self._json({"error": "falta el link de la planilla"}, 400)
            # Una sola caja donde pegar: el panel se da cuenta solo de si le
            # pegaron una planilla o un documento. Pedirle a alguien que elija
            # el tipo antes de pegar el link es hacerle hacer un trabajo que la
            # computadora puede hacer sola.
            clase, pid = "hoja", ""
            try:
                from datos import google_cuenta as gcu
                if gcu.es_documento(link):
                    clase, pid = "doc", gcu.id_de_documento(link)
            except Exception:              # noqa: si no esta el modulo, es hoja
                pass
            if not pid:
                try:
                    from datos import google_sheets as gs
                    pid = gs.id_de_planilla(link)
                except Exception as e:     # noqa
                    return self._json(
                        {"error": "Ese link no parece de Drive. Pegá el link "
                                  "entero de una planilla o un documento de "
                                  "Google. (%s)" % e}, 400)
            titulo = str(cuerpo.get("titulo") or "").strip()
            rango = str(cuerpo.get("rango") or "").strip()
            rid = str(cuerpo.get("id") or "").strip()
            # Sin cuenta cargada todavia queda un camino: si la planilla esta
            # en «cualquier persona con el link», Google la deja bajar sin
            # credenciales. Se prueba ACA, antes de guardar, para no dejar
            # armado un reporte que despues no se va a poder leer.
            publica = False
            if clase != "doc":
                # ⚠️ Imports normales y no __import__("datos." + mod): PyInstaller
                # arma la lista de modulos leyendo el codigo, y un nombre que se
                # calcula en tiempo de ejecucion no lo puede ver. El modulo no
                # entraria al .exe y esto reventaria recien al apretar el boton.
                hay = False
                try:
                    from datos import google_cuenta as _gc
                    hay = hay or bool(_gc.estado().get("conectado"))
                except Exception:          # noqa
                    pass
                try:
                    from datos import google_sheets as _gsh
                    hay = hay or bool(_gsh.estado().get("conectado"))
                except Exception:          # noqa
                    pass
                if not hay:
                    try:
                        from datos import google_link as gl
                        publica = gl.es_publica(link)
                    except Exception:      # noqa
                        publica = False
                    if not publica:
                        return self._json({"error":
                            "Esa planilla no esta compartida por link, y el "
                            "panel todavia no tiene una cuenta de Google "
                            "cargada. Carga la cuenta mas abajo, o en Drive "
                            "ponela en «Cualquier persona con el link»."}, 400)
                    clase = "publico"

            fuente = {"tipo": "google", "clase": clase, "planilla": pid,
                      "rango": rango, "link": link, "publica": publica,
                      "archivo": ("Documento de Google" if clase == "doc"
                                  else "Planilla de Google")}
            rep = datos_api.buscar(cfg, rid) if rid else None
            if rep:
                rep["fuente"] = fuente
                if titulo:
                    rep["titulo"] = titulo
                rep["publicados"] = []     # otra planilla, otros numeros
            else:
                if len(cfg.get("reportes") or []) >= 30:
                    return self._json({"error": "ya hay 30 reportes"}, 400)
                rep = {"id": datos_api.nuevo_id(),
                       "titulo": titulo or fuente["archivo"],
                       "fuente": fuente, "publicados": []}
                cfg.setdefault("reportes", []).append(rep)
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "id": rep["id"], "titulo": rep["titulo"]})

        if path == "/api/datos/vendedores":
            # A qué sucursal pertenece cada vendedor. El panel pregunta cuando
            # aparece un nombre que no conoce, en vez de descartar sus
            # derivaciones en silencio.
            asign = cuerpo.get("asignaciones")
            if not isinstance(asign, dict):
                return self._json({"error": "esperaba un objeto"}, 400)
            from datos import derivaciones as dvv
            limpio = {str(k)[:60]: str(v)[:40] for k, v in list(asign.items())[:60]}
            dvv.mapa_guardar(STATE_DIR, limpio)
            return self._json({"ok": True, "cuantos": len(limpio)})

        if path == "/api/datos/foco":
            # Que eligio medir el equipo en este reporte. Ordena el tablero y el
            # reporte descargable; no borra nada, lo no elegido queda mas abajo.
            rep = datos_api.buscar(cfg, str(cuerpo.get("id") or ""))
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            ids = cuerpo.get("foco")
            if not isinstance(ids, list):
                return self._json({"error": "esperaba una lista"}, 400)
            rep["foco"] = [str(x)[:40] for x in ids][:40]
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "cuantas": len(rep["foco"])})

        if path == "/api/datos/informe-crear":
            rep = datos_api.buscar(cfg, str(cuerpo.get("id") or ""))
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            secs = cuerpo.get("secciones")
            inf, err = datos_api.informe_nuevo(
                rep, str(cuerpo.get("nombre") or "")[:80],
                str(cuerpo.get("desde") or ""), str(cuerpo.get("hasta") or ""),
                [str(x) for x in secs] if isinstance(secs, list) else None)
            if err:
                return self._json({"error": err}, 400)
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "informe": inf,
                               "informes": datos_api.informes(rep)})

        if path == "/api/datos/informe-borrar":
            rep = datos_api.buscar(cfg, str(cuerpo.get("id") or ""))
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            if not datos_api.informe_borrar(rep, str(cuerpo.get("informe") or "")):
                return self._json({"error": "no encuentro ese informe"}, 404)
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "informes": datos_api.informes(rep)})

        if path == "/api/datos/renombrar":
            rep = datos_api.buscar(cfg, str(cuerpo.get("id") or ""))
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            t = str(cuerpo.get("titulo") or "").strip()[:80]
            if not t:
                return self._json({"error": "el nombre no puede quedar vacio"}, 400)
            rep["titulo"] = t
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "titulo": t})

        if path == "/api/datos/borrar":
            rid = str(cuerpo.get("id") or "")
            antes = len(cfg.get("reportes") or [])
            cfg["reportes"] = [r for r in (cfg.get("reportes") or [])
                               if r.get("id") != rid]
            if len(cfg["reportes"]) == antes:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "quedan": len(cfg["reportes"])})

        if path == "/api/datos/publicados":
            rep = datos_api.buscar(cfg, str(cuerpo.get("id") or ""))
            if not rep:
                return self._json({"error": "no encuentro ese reporte"}, 404)
            ids = cuerpo.get("publicados")
            if not isinstance(ids, list):
                return self._json({"error": "esperaba una lista"}, 400)
            rep["publicados"] = [str(x) for x in ids][:200]
            datos_api.guardar(STATE_DIR, cfg)
            return self._json({"ok": True, "cuantos": len(rep["publicados"])})

        return self._json({"error": "no existe %s" % path}, 404)

    def _file(self, path, ctype, rango=False, nombre=""):
        """Sirve un archivo. Con rango=True habilita HTTP Range (206), que el <video>
        necesita para poder adelantar y que Safari EXIGE para reproducir siquiera."""
        try:
            st = os.stat(path)
        except OSError:
            self.send_error(404)
            return
        tam = st.st_size
        # con `nombre`, el navegador lo baja con ese nombre en vez de abrirlo
        _descarga = ('attachment; filename="%s"' % nombre.replace('"', "")) if nombre else ""
        inicio, fin, parcial = 0, tam - 1, False

        if rango:
            cabecera = (self.headers.get("Range") or "").strip()
            m = re.match(r"^bytes=(\d*)-(\d*)$", cabecera) if cabecera else None
            if m and (m.group(1) or m.group(2)):
                if not m.group(1):                       # "bytes=-500" = los ultimos 500
                    inicio, fin = max(0, tam - int(m.group(2))), tam - 1
                else:
                    inicio = int(m.group(1))
                    fin = int(m.group(2)) if m.group(2) else tam - 1
                if inicio >= tam or inicio > fin:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % tam)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                fin = min(fin, tam - 1)
                parcial = True

        largo = fin - inicio + 1
        try:
            fh = open(path, "rb")
        except OSError:
            self.send_error(404)
            return
        with fh:
            self.send_response(206 if parcial else 200)
            self.send_header("Content-Type", ctype)
            # El panel corre en una ventana de Chrome, y Chrome se guarda el
            # index.html y los .css entre sesiones. Al actualizar el programa,
            # el numero de version cambiaba (viene por /api/config, que no se
            # cachea) pero la PANTALLA seguia siendo la vieja: parecia que la
            # actualizacion no habia entrado. Reinstalar tampoco lo arregla,
            # porque la cache es del navegador, no del programa.
            self.send_header("Cache-Control", "no-store, must-revalidate")
            # Sin esto el navegador intenta MOSTRAR el .docx, que es un ZIP:
            # se ve basura binaria en pantalla en vez de bajarse el archivo.
            if _descarga:
                self.send_header("Content-Disposition", _descarga)
            self.send_header("Content-Length", str(largo))
            if rango:
                # revalida siempre (asi un video reemplazado no queda pegado en cache)
                # pero sin volver a bajar el archivo entero en cada render del canvas
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-cache")
                if parcial:
                    self.send_header("Content-Range", "bytes %d-%d/%d" % (inicio, fin, tam))
            else:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            fh.seek(inicio)
            restante = largo
            while restante > 0:
                trozo = fh.read(min(64 * 1024, restante))
                if not trozo:
                    break
                try:
                    self.wfile.write(trozo)
                except (BrokenPipeError, ConnectionResetError):
                    return       # el navegador corto la descarga (normal al hacer seek)
                restante -= len(trozo)

    def _servir_index(self):
        """Sirve index.html con `?v=<VERSION>` inyectado en cada css/js local.
        La direccion de cada archivo CAMBIA con la version -> la cache vieja
        del navegador (guardada bajo la direccion sin ?v=) queda huerfana y no
        se puede volver a usar. Es la garantia que los headers no dan: el
        no-store solo protege lo que se baja DESPUES de tenerlo, mientras que
        esto invalida tambien lo que el navegador guardo ANTES del arreglo."""
        try:
            with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
                html = f.read()
        except OSError:
            self.send_error(404)
            return
        html = re.sub(r'((?:href|src)="/(?:static|intranet)/[^"?]+)"',
                      r'\1?v=%d"' % VERSION, html)
        cuerpo = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        try:
            self.wfile.write(cuerpo)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *a):
        pass  # silenciar log ruidoso

    # --- GET ---
    def do_GET(self):
        u = urlparse(self.path)
        path = unquote(u.path)

        if path == "/" or path == "/index.html":
            return self._servir_index()
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            return self._servir_estatico(WEB, rel)
        if path.startswith("/intranet/"):
            rel = path[len("/intranet/"):]
            return self._servir_estatico(INTRANET, rel)

        if path == "/api/config":
            return self._json({
                "rol": ROL, "es_central": ES_CENTRAL, "usuario": USUARIO,
                "central_url": CENTRAL_URL, "pc": _pc(),
                "version": VERSION, "version_label": VERSION_LABEL,
                "version_publica": VERSION_PUBLICA,
                "pendientes": (len(aprobaciones_pendientes()) if ES_CENTRAL else 0),
                "cerebro": bool(CEREBRO_URL), "tiene_token": bool(PUBLISH_TOKEN),
                "web_publica": WEB_PUBLICA,
            })
        if path == "/api/aprobaciones":
            if not ES_CENTRAL:
                return self._json({"error": "solo la central"}, 403)
            return self._json({"aprobaciones": listar_aprobaciones()})
        if path == "/api/aprobacion":
            if not ES_CENTRAL:
                return self._json({"error": "solo la central"}, 403)
            q = parse_qs(u.query)
            return self._json(detalle_propuesta((q.get("id") or [""])[0]))
        if path == "/api/ping-central":
            return self._json(ping_central())
        if path == "/api/novedades":
            return self._json(novedades())
        if path == "/api/update-status":
            return self._json(chequear_update())
        if path == "/api/historial":
            return self._json(historial_publicaciones())
        if path == "/api/video-capacidad":
            return self._json({
                "compresor": bool(ffmpeg_local()), "mb_descarga": FFMPEG_MB,
                "max": MAX_VIDEO, "max_subida": MAX_VIDEO_SUBIDA,
            })
        if path == "/api/job":
            q = parse_qs(u.query)
            j = job_estado((q.get("id") or [""])[0])
            return self._json(j or {"estado": "error", "error": "ese trabajo ya no existe"})
        if path == "/api/secciones":
            return self._json({"secciones": estado_secciones(), "git": estado_git()})
        if path == "/api/modulos":
            return self._json({"modulos": leer_modulos()})
        if path == "/api/contenido":
            q = parse_qs(u.query)
            key = (q.get("key") or [""])[0]
            return self._json(contenido_actual(key))
        if path == "/api/descargables":
            return self._json({"grupos": grupos_descargables()})
        if path == "/api/estado-git":
            return self._json(estado_git())
        if path.startswith("/api/datos/"):
            return self._datos_get(path, parse_qs(u.query))
        if path == "/api/imagenes":
            q = parse_qs(u.query)
            sec = (q.get("seccion") or [""])[0]
            if not seccion_valida(sec):
                return self._json({"error": "seccion invalida"}, 400)
            return self._json({"images": listar(sec)})

        self.send_error(404)

    def _servir_estatico(self, raiz, rel):
        rel = rel.replace("\\", "/")
        if ".." in rel.split("/"):
            return self.send_error(403)
        full = os.path.normpath(os.path.join(raiz, rel))
        if not full.startswith(os.path.normpath(raiz)):
            return self.send_error(403)
        # una carpeta se sirve con su index.html, como cualquier servidor web.
        # Sin esto, "/intranet/" daba el 404 pelado de Python: el boton "Vista
        # previa en la intranet" y los links "#cartelera/<id>" abiertos en local
        # terminaban en una pagina de error en vez del sitio.
        if not rel or rel.endswith("/") or os.path.isdir(full):
            full = os.path.join(full, "index.html")
        ext = os.path.splitext(full)[1].lower()
        ctypes = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                  ".css": "text/css; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg",
                  ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
                  ".svg": "image/svg+xml", ".pdf": "application/pdf",
                  ".json": "application/json", ".webmanifest": "application/manifest+json",
                  ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
                  ".m4v": "video/mp4"}
        # los video van con Range; en Vercel esto ya lo resuelve el hosting, pero la
        # vista previa local del panel sin Range no reproduce en Safari ni deja adelantar
        return self._file(full, ctypes.get(ext, "application/octet-stream"), rango=(ext in EXTS_VIDEO))

    # --- POST ---
    def do_POST(self):
        u = urlparse(self.path)
        path = u.path
        # Anti-CSRF: si viene un Origin y NO es el propio panel (localhost), rechazar.
        # (una pagina web cualquiera podria POSTear a 127.0.0.1 sin poder leer la respuesta,
        #  pero igual dispararia acciones mutadoras como /api/update-apply.)
        origin = self.headers.get("Origin", "")
        if origin:
            try:
                oh = urlparse(origin).hostname
            except ValueError:
                oh = None
            if oh not in ("127.0.0.1", "localhost", "::1"):
                return self._json({"error": "origen no permitido"}, 403)
        try:
            if path == "/api/upload":
                return self._upload()
            if path == "/api/upload-contenido":
                return self._upload_contenido()
            if path == "/api/upload-pdf":
                return self._upload_pdf()
            if path == "/api/upload-video":
                return self._upload_video()
            if path == "/api/preparar-compresor":
                if ffmpeg_local():
                    return self._json({"ok": True, "ya": True})
                jid = _job_nuevo("ffmpeg")
                threading.Thread(target=_bajar_ffmpeg, args=(jid,), daemon=True).start()
                return self._json({"ok": True, "job": jid, "mb": FFMPEG_MB})
            if path == "/api/borrar":
                return self._borrar()
            if path.startswith("/api/datos/"):
                return self._datos_post(path)
            if path == "/api/reordenar":
                return self._reordenar()
            if path == "/api/reorganizar":
                return self._reorganizar()
            if path == "/api/modulos":
                d = self._leer_json()
                lista, err = validar_modulos(d.get("modulos"))
                if err:
                    return self._json({"error": err}, 400)
                escribir_modulos(lista)
                return self._json({"ok": True, "modulos": lista})
            if path == "/api/regenerar":
                rc, out, err = regenerar_galerias()
                return self._json({"ok": rc == 0, "log": (out + err).strip()})
            if path == "/api/publicar" or path == "/api/enviar":
                # Publicacion DIRECTA via el cerebro (central Y colaboradores).
                try:
                    d = self._leer_json()
                except Exception:  # noqa
                    d = {}
                return self._json(publicar_cerebro(d.get("mensaje", "")))
            if path == "/api/restaurar":
                d = self._leer_json()
                return self._json(restaurar_version(d.get("sha", "")))
            if path == "/api/kit-recuperacion":
                # va por POST para que aplique el guard de Origin: devuelve la
                # clave de publicacion en claro y no queremos que la pida otra web
                return self._json(kit_recuperacion())
            if path == "/api/set-publish-token":
                d = self._leer_json()
                return self._json(guardar_publish_token(d.get("token", "")))
            if path == "/api/shutdown":
                # cerrar el panel (no hay consola para cerrar): respondemos y salimos
                self._json({"ok": True})
                try:
                    self.wfile.flush()
                except Exception:  # noqa
                    pass
                threading.Timer(0.6, lambda: os._exit(0)).start()
                return
            if path == "/api/traer":
                if ES_CENTRAL:
                    return self._json(traer_de_central())
                jid = _job_nuevo("traer")

                def _traer_fondo(j=jid):
                    try:
                        r = traer_de_central(j)
                    except Exception as e:  # noqa
                        r = {"ok": False, "error": str(e)}
                    if r.get("ok"):
                        _job_set(j, estado="listo", pct=100,
                                 msg="¡Listo! Ya tenés la última versión.",
                                 info=r.get("fuente", ""))
                    else:
                        _job_set(j, estado="error", error=r.get("error") or "No se pudo traer.")

                threading.Thread(target=_traer_fondo, daemon=True).start()
                return self._json({"ok": True, "job": jid})
            if path == "/api/update-apply":
                # Responde AL TOQUE con un numero de trabajo y hace la descarga
                # en un hilo. Asi la pantalla puede ir mostrando en que anda en
                # vez de quedarse congelada: bajar 20 MB puede tardar un minuto
                # largo en la conexion de una sucursal, y un minuto sin ninguna
                # senal se siente como que se colgo.
                jid = _job_nuevo("update")

                def _correr_update():
                    try:
                        r = aplicar_update(jid=jid)
                    except Exception as e:  # noqa
                        _job_set(jid, estado="error", error=str(e))
                        return
                    if r.get("aplicando"):
                        _job_set(jid, pct=100, estado="listo",
                                 msg="Listo. El panel se está reiniciando…")
                        # aplicar.bat espera que ESTE proceso muera para hacer el
                        # cambio. Los 2,5s le dan tiempo a la pantalla a leer el
                        # ultimo estado antes de que se corte la conexion.
                        threading.Timer(2.5, lambda: os._exit(0)).start()
                    else:
                        _job_set(jid, estado="error",
                                 error=r.get("error") or "no se pudo actualizar")

                threading.Thread(target=_correr_update, daemon=True).start()
                return self._json({"ok": True, "job": jid})
            if path == "/api/aprobar":
                if not ES_CENTRAL:
                    return self._json({"ok": False, "error": "solo la central"}, 403)
                d = self._leer_json()
                return self._json(aplicar_propuesta(d.get("id", "")))
            if path == "/api/rechazar":
                if not ES_CENTRAL:
                    return self._json({"ok": False, "error": "solo la central"}, 403)
                d = self._leer_json()
                return self._json(rechazar_propuesta(d.get("id", "")))
        except Exception as e:  # noqa
            return self._json({"error": str(e)}, 500)
        self.send_error(404)

    def _leer_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n)

    def _leer_json(self):
        return json.loads(self._leer_body().decode("utf-8") or "{}")

    def _upload(self):
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return self._json({"error": "esperaba multipart"}, 400)
        raw = b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + self._leer_body()
        msg = email.message_from_bytes(raw)

        seccion = None
        partes = []
        for part in msg.walk():
            if part.is_multipart():
                continue
            cd = part.get("Content-Disposition", "")
            nombre_campo = re.search(r'name="([^"]*)"', cd)
            nombre_campo = nombre_campo.group(1) if nombre_campo else ""
            filename = re.search(r'filename="([^"]*)"', cd)
            filename = filename.group(1) if filename else ""
            payload = part.get_payload(decode=True)
            if nombre_campo == "seccion" and not filename:
                seccion = (payload or b"").decode("utf-8", "replace").strip()
            elif filename:
                partes.append((filename, payload))

        if not seccion_valida(seccion):
            return self._json({"error": "seccion invalida"}, 400)
        carpeta = carpeta_de(seccion)

        guardados, errores = [], []
        for filename, data in partes:
            if not data:
                continue
            try:
                img = Image.open(io.BytesIO(data))
                img.load()
                img = ImageOps.exif_transpose(img)  # foto de celular -> orientacion correcta
                img, _ = normalizar(img)
                base = sanear(os.path.splitext(os.path.basename(filename))[0])
                destino = nombre_unico(carpeta, base, ".png")
                img.save(os.path.join(carpeta, destino), format="PNG", optimize=True)
                guardados.append(destino)
            except Exception as e:  # noqa
                errores.append("%s: %s" % (filename, e))

        return self._json({"ok": not errores, "guardados": guardados,
                           "errores": errores, "images": listar(seccion)})

    def _upload_contenido(self):
        """Sube UNA imagen como contenido de un módulo -> assets/_modulos/<key>.png"""
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return self._json({"error": "esperaba multipart"}, 400)
        raw = b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + self._leer_body()
        msg = email.message_from_bytes(raw)
        key, data, fmt = None, None, "png"
        for part in msg.walk():
            if part.is_multipart():
                continue
            cd = part.get("Content-Disposition", "")
            campo = re.search(r'name="([^"]*)"', cd)
            campo = campo.group(1) if campo else ""
            filename = re.search(r'filename="([^"]*)"', cd)
            filename = filename.group(1) if filename else ""
            payload = part.get_payload(decode=True)
            if campo == "key" and not filename:
                key = (payload or b"").decode("utf-8", "replace").strip()
            elif campo == "fmt" and not filename:
                fmt = (payload or b"").decode("utf-8", "replace").strip().lower()
            elif filename:
                data = payload
        key = slug(key or "")
        if not key or not data:
            return self._json({"error": "faltan datos"}, 400)
        os.makedirs(MOD_ASSETS, exist_ok=True)
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            img = ImageOps.exif_transpose(img)
            img, _ = normalizar(img)
            # JPEG solo cuando se pide: es para los posters de video, donde un
            # cuadro fotografico en PNG pesa mas que el propio video (medido).
            # Todo lo demas sigue yendo a PNG, que es lo que espera el resto.
            if fmt in ("jpg", "jpeg"):
                if img.mode == "RGBA":
                    fondo = Image.new("RGB", img.size, (255, 255, 255))
                    fondo.paste(img, mask=img.split()[-1])
                    img = fondo
                img.save(os.path.join(MOD_ASSETS, key + ".jpg"),
                         format="JPEG", quality=78, optimize=True, progressive=True)
                ext = "jpg"
            else:
                img.save(os.path.join(MOD_ASSETS, key + ".png"), format="PNG", optimize=True)
                ext = "png"
        except Exception as e:  # noqa
            return self._json({"error": "no se pudo procesar la imagen: %s" % e}, 400)
        return self._json({"ok": True, "src": "assets/_modulos/%s.%s" % (key, ext)})

    def _upload_pdf(self):
        """Sube UN PDF como contenido de un modulo -> assets/_modulos/<key>.pdf (sin procesar)."""
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            return self._json({"error": "esperaba multipart"}, 400)
        raw = b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + self._leer_body()
        msg = email.message_from_bytes(raw)
        key, data = None, None
        for part in msg.walk():
            if part.is_multipart():
                continue
            cd = part.get("Content-Disposition", "")
            campo = re.search(r'name="([^"]*)"', cd)
            campo = campo.group(1) if campo else ""
            filename = re.search(r'filename="([^"]*)"', cd)
            filename = filename.group(1) if filename else ""
            payload = part.get_payload(decode=True)
            if campo == "key" and not filename:
                key = (payload or b"").decode("utf-8", "replace").strip()
            elif filename:
                data = payload
        key = slug(key or "")
        if not key or not data:
            return self._json({"error": "faltan datos"}, 400)
        if len(data) > 25 * 1024 * 1024:
            return self._json({"error": "el PDF supera el limite de 25 MB"}, 400)
        if not data.startswith(b"%PDF"):
            return self._json({"error": "el archivo no parece un PDF valido"}, 400)
        os.makedirs(MOD_ASSETS, exist_ok=True)
        try:
            with open(os.path.join(MOD_ASSETS, key + ".pdf"), "wb") as f:
                f.write(data)
        except Exception as e:  # noqa
            return self._json({"error": "no se pudo guardar el PDF: %s" % e}, 400)
        return self._json({"ok": True, "src": "assets/_modulos/%s.pdf" % key})

    # ---- video -------------------------------------------------------
    def _multipart_a_disco(self, limite, destino):
        """Lee un multipart GRANDE sin cargarlo en memoria: vuelca el body a un
        temporal, lo recorre con mmap y copia el archivo adjunto a `destino`.
        (El camino de las imagenes usa email.message_from_bytes, que duplica todo
         en RAM: con un video de 200 MB eso tumba una PC de sucursal.)
        Devuelve (campos, nombre_original, error)."""
        ctype = self.headers.get("Content-Type", "")
        mb = re.search(r'boundary="?([^";]+)"?', ctype)
        if "multipart/form-data" not in ctype or not mb:
            return None, "", "esperaba multipart"
        try:
            total = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            total = 0
        if total <= 0:
            return None, "", "falta el tamano del archivo"
        if total > limite:
            return None, "", "el archivo supera el limite de %d MB" % (limite // (1024 * 1024))

        crudo = destino + ".body"
        campos, nombre = {}, ""
        try:
            leido = 0
            with open(crudo, "wb") as f:
                while leido < total:
                    trozo = self.rfile.read(min(256 * 1024, total - leido))
                    if not trozo:
                        break
                    f.write(trozo)
                    leido += len(trozo)
            if leido < total:
                return None, "", "la subida se corto por la mitad"

            sep = b"--" + mb.group(1).encode("ascii", "replace")
            with open(crudo, "rb") as f:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                try:
                    pos = mm.find(sep)
                    while pos != -1:
                        ini = mm.find(b"\r\n\r\n", pos)
                        if ini == -1:
                            break
                        cab = mm[pos:ini].decode("utf-8", "replace")
                        ini += 4
                        sig = mm.find(sep, ini)
                        fin = (sig - 2) if sig != -1 else len(mm)   # -2 = el \r\n previo
                        mcampo = re.search(r'name="([^"]*)"', cab)
                        march = re.search(r'filename="([^"]*)"', cab)
                        if march and march.group(1):
                            nombre = march.group(1)
                            with open(destino, "wb") as dst:
                                paso = 1024 * 1024
                                for off in range(ini, fin, paso):
                                    dst.write(mm[off:min(off + paso, fin)])
                        elif mcampo:
                            campos[mcampo.group(1)] = mm[ini:fin].decode("utf-8", "replace").strip()
                        pos = sig
                finally:
                    mm.close()
        except (OSError, ValueError) as e:
            return None, "", "no se pudo recibir el archivo: %s" % e
        finally:
            try:
                os.remove(crudo)
            except OSError:
                pass
        if not os.path.isfile(destino):
            return None, "", "no vino ningun archivo"
        return campos, nombre, ""

    def _upload_video(self):
        """Sube UN video como contenido de un modulo -> assets/_modulos/<key>.mp4.
        Si pesa mas del tope publicable, lo comprime (en un hilo) y devuelve un job."""
        if not STATE_DIR:
            return self._json({"error": "no hay carpeta de trabajo"}, 500)
        os.makedirs(MOD_ASSETS, exist_ok=True)
        os.makedirs(STATE_DIR, exist_ok=True)
        # nombre unico: dos subidas a la vez no se pueden pisar el temporal
        marca = base64.b16encode(os.urandom(4)).decode("ascii").lower()
        tmp = os.path.join(STATE_DIR, "subida_%s.tmp" % marca)
        campos, _nombre, err = self._multipart_a_disco(MAX_VIDEO_SUBIDA, tmp)
        if err:
            self._borrar_tmp(tmp)
            return self._json({"error": err}, 400)

        key = slug((campos or {}).get("key", ""))
        if not key:
            self._borrar_tmp(tmp)
            return self._json({"error": "faltan datos"}, 400)

        with open(tmp, "rb") as f:
            cabeza = f.read(64)
        if not firma_video(cabeza):
            self._borrar_tmp(tmp)
            return self._json({"error": "el archivo no parece un video (se aceptan mp4, mov y webm)"}, 400)

        peso = os.path.getsize(tmp)
        final = os.path.join(MOD_ASSETS, key + ".mp4")
        src = "assets/_modulos/%s.mp4" % key

        # ¿se puede publicar tal cual? Manda el CODEC, no solo el peso.
        apto, porque = video_apto(tmp, peso)

        # ya entra: se guarda tal cual
        if apto and (campos or {}).get("forzar") != "1":
            self._limpiar_videos_previos(key)
            try:
                os.replace(tmp, final)
            except OSError as e:
                self._borrar_tmp(tmp)
                return self._json({"error": "no se pudo guardar el video: %s" % e}, 400)
            return self._json({"ok": True, "src": src, "peso": peso})

        # hay que convertir
        if not ffmpeg_local():
            self._borrar_tmp(tmp)
            return self._json({"ok": False, "falta_ffmpeg": True, "peso": peso,
                               "mb": FFMPEG_MB, "motivo": porque,
                               "error": "Para convertir este video necesito el compresor."}, 200)

        jid = _job_nuevo("video")

        def tarea():
            salida = os.path.join(STATE_DIR, "comprimido_%s_%s.mp4" % (key, marca))
            ok, motivo = _comprimir(jid, tmp, salida)
            try:
                if not ok:
                    _job_set(jid, estado="error", error="No se pudo comprimir el video: %s" % motivo)
                    return
                nuevo = os.path.getsize(salida)
                if nuevo > MAX_VIDEO:
                    _job_set(jid, estado="error",
                             error=("Aun comprimido el video pesa %.1f MB y el tope para publicar "
                                    "es %d MB. Proba con un video mas corto."
                                    % (nuevo / 1048576.0, MAX_VIDEO // 1048576)))
                    return
                self._limpiar_videos_previos(key)
                os.replace(salida, final)
                _job_set(jid, estado="listo", pct=100, src=src,
                         info="%.1f MB -> %.1f MB" % (peso / 1048576.0, nuevo / 1048576.0))
            except OSError as e:
                _job_set(jid, estado="error", error="No se pudo guardar el video: %s" % e)
            finally:
                self._borrar_tmp(tmp)
                self._borrar_tmp(salida)

        threading.Thread(target=tarea, daemon=True).start()
        return self._json({"ok": True, "job": jid, "peso": peso})

    @staticmethod
    def _borrar_tmp(ruta):
        try:
            os.remove(ruta)
        except OSError:
            pass

    @staticmethod
    def _limpiar_videos_previos(key):
        """Un video de 16 MB que queda huerfano se publica igual y se clona en cada
        build para siempre. Al reemplazar, borrar la version con otra extension."""
        for ext in EXTS_VIDEO:
            viejo = os.path.join(MOD_ASSETS, key + ext)
            if ext != ".mp4" and os.path.isfile(viejo):
                try:
                    os.remove(viejo)
                except OSError:
                    pass

    def _borrar(self):
        d = self._leer_json()
        sec = d.get("seccion", "")
        archivo = d.get("download", "")
        if not seccion_valida(sec):
            return self._json({"error": "seccion invalida"}, 400)
        if "/" in archivo or "\\" in archivo or ".." in archivo or not archivo:
            return self._json({"error": "nombre invalido"}, 400)
        ruta = os.path.join(carpeta_de(sec), archivo)
        if os.path.isfile(ruta):
            os.remove(ruta)
        return self._json({"ok": True, "images": listar(sec)})

    def _reordenar(self):
        d = self._leer_json()
        sec = d.get("seccion", "")
        orden = d.get("orden", [])
        if not seccion_valida(sec):
            return self._json({"error": "seccion invalida"}, 400)
        carpeta = carpeta_de(sec)
        existentes = [f for f in os.listdir(carpeta) if f.lower().endswith(EXTS)]
        # validar que el orden pedido corresponde a archivos reales
        orden = [a for a in orden if a in existentes]
        if not orden:
            return self._json({"ok": True, "images": listar(sec)})
        W = max(2, len(str(len(orden))))
        # fase 1: a nombres temporales unicos
        tmp = []
        for i, a in enumerate(orden):
            t = "__tmp_%d__%s" % (i, a)
            os.rename(os.path.join(carpeta, a), os.path.join(carpeta, t))
            tmp.append((t, a))
        # fase 2: a nombre definitivo con prefijo numerico
        for i, (t, a) in enumerate(tmp, start=1):
            base = sanear(base_sin_prefijo(a))
            final = nombre_unico(carpeta, "%0*d - %s" % (W, i, base), ".png")
            # si el original no era png igual lo dejamos con su contenido; renombramos
            ext = os.path.splitext(a)[1].lower()
            if ext != ".png":
                final = nombre_unico(carpeta, "%0*d - %s" % (W, i, base), ext)
            os.rename(os.path.join(carpeta, t), os.path.join(carpeta, final))
        return self._json({"ok": True, "images": listar(sec)})

    def _reorganizar(self):
        """Reacomoda imágenes entre los grupos de Material descargable.
        Payload: { orden: { <destino>: [ {download, from}, ... ], ... } }
        Mueve cada archivo de su seccion 'from' al 'destino' en el orden dado,
        aplicando prefijo numerico para fijar la posicion. Dos fases anti-colision."""
        d = self._leer_json()
        orden = d.get("orden", {})
        if not isinstance(orden, dict):
            return self._json({"error": "payload invalido"}, 400)
        for dest in orden:
            if not seccion_valida(dest):
                return self._json({"error": "seccion invalida: %s" % dest}, 400)

        # Fase 1: mover cada archivo a un nombre temporal en su carpeta destino
        plan = {}  # destino -> [(tmpname, base, ext)]
        for dest, items in orden.items():
            carpeta_dest = carpeta_de(dest)
            plan[dest] = []
            for i, it in enumerate(items if isinstance(items, list) else []):
                origen = it.get("from")
                download = it.get("download", "")
                if not seccion_valida(origen):
                    continue
                if "/" in download or "\\" in download or ".." in download or not download:
                    continue
                src = os.path.join(carpeta_de(origen), download)
                if not os.path.isfile(src):
                    continue
                base = sanear(base_sin_prefijo(download))
                ext = os.path.splitext(download)[1].lower() or ".png"
                tmp = "__org_%d__%s" % (i, download)
                tmp_path = os.path.join(carpeta_dest, tmp)
                # evitar pisar un temporal previo
                k = 0
                while os.path.exists(tmp_path):
                    k += 1
                    tmp = "__org_%d_%d__%s" % (i, k, download)
                    tmp_path = os.path.join(carpeta_dest, tmp)
                os.rename(src, tmp_path)
                plan[dest].append((tmp, base, ext))

        # Fase 2: renombrar temporales a nombre final con prefijo de orden
        for dest, lst in plan.items():
            carpeta_dest = carpeta_de(dest)
            W = max(2, len(str(len(lst))))
            for i, (tmp, base, ext) in enumerate(lst, start=1):
                final = nombre_unico(carpeta_dest, "%0*d - %s" % (W, i, base), ext)
                os.rename(os.path.join(carpeta_dest, tmp), os.path.join(carpeta_dest, final))

        return self._json({"ok": True, "grupos": grupos_descargables()})


def arrancar_receptor_en_hilo():
    """Levanta el receptor de propuestas (red local) en un hilo daemon, sin
    tumbar el panel si el puerto ya esta en uso u otro error."""
    def _run():
        try:
            import receptor_server
            receptor_server.serve_silencioso()
        except OSError as e:
            print("  (aviso) no pude abrir el receptor en el puerto %d: %s" % (RECEPTOR_PORT, e))
        except Exception as e:  # noqa
            print("  (aviso) receptor no disponible: %s" % e)
    threading.Thread(target=_run, daemon=True).start()


def _msgbox(texto, titulo="Panel Muebles y Sillones"):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, texto, titulo, 0x10)
    except Exception:  # noqa
        print(texto)


def _abrir_panel(url):
    """Abre el panel como PESTANA normal del navegador (localhost), no en la
    ventana modo --app de Edge (v32, pedido del usuario: la ventana separada
    confundia y arrastraba su propia cache/perfil). webbrowser usa el navegador
    por defecto del sistema; con BROWSER definido se respeta igual que siempre
    (lo usan las pruebas para no abrir nada en la cara del usuario)."""
    try:
        webbrowser.open(url)
    except Exception:  # noqa
        pass


def main():
    if not PROYECTO:
        _msgbox("No encontre la carpeta del proyecto de la intranet.\n\n"
                "Solucion: crea un archivo 'proyecto.txt' junto a este programa\n"
                "con la ruta de la carpeta (la que contiene 'intranet' y 'herramientas').")
        return

    url = "http://%s:%d/" % (HOST, PORT)
    # Bindeo primero: si el puerto ya esta ocupado, el panel YA esta abierto ->
    # solo abrimos el navegador en esa instancia y salimos (sin ventana ni error).
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        # el panel ya esta abierto en otra instancia: solo abrir su ventana
        _abrir_panel(url)
        return

    # La central escucha ademas las propuestas de los colaboradores (receptor).
    if ES_CENTRAL:
        arrancar_receptor_en_hilo()
    print("Panel abierto en %s (rol: %s)" % (url, ROL))
    _abrir_panel(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if "--receptor" in sys.argv:
        # modo receptor (central en 2o plano): escucha en la red local las
        # propuestas de los colaboradores. No publica ni toca git.
        import receptor_server
        receptor_server.main()
    else:
        main()
