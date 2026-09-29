# -*- coding: utf-8 -*-
"""Leer una planilla de Google Sheets sin exponerla a internet.

La planilla de derivaciones tiene nombre, teléfono y mail de clientes reales.
Ponerla en "cualquiera con el link" o publicarla como CSV la deja al alcance de
cualquiera que adivine o reenvíe la URL: eso es una filtración, no un atajo.
La alternativa es que el panel —que corre en la PC de marketing, no en
internet— entre con la cuenta de Google del equipo, como entraría una persona,
y lea la planilla con permiso de SOLO LECTURA.

CÓMO ENTRA  (flujo de "app instalada" con PKCE, el que Google documenta para
             programas de escritorio)
  1. El panel levanta un servidor minúsculo en 127.0.0.1 (solo esta PC lo ve).
  2. Abre el navegador en la pantalla de permisos de Google.
  3. La persona entra con su cuenta de siempre y acepta.
  4. Google vuelve a ese 127.0.0.1 con un código de un solo uso.
  5. El panel cambia el código por un refresh_token y lo guarda.
  6. De ahí en más renueva el access_token solo, sin volver a molestar a nadie.

PKCE es lo que hace seguro el paso 4 sin tener un servidor propio: el código
que vuelve por 127.0.0.1 no le sirve a nadie más, porque para canjearlo hay que
presentar el "verificador" que solo conoce esta ejecución del panel.

DÓNDE VIVE EL TOKEN
  En la carpeta de estado del panel (STATE_DIR), la misma de identity.json.
  Nunca adentro de intranet/, que es lo único que el panel publica. Hay un
  cerrojo que directamente se niega a escribir ahí (ver _publicable).

QUÉ PERMISO PIDE
  spreadsheets.readonly y nada más: no puede escribir, ni borrar, ni ver el
  resto del Drive. Ni siquiera pide el mail de la cuenta, y por eso el panel no
  puede mostrar "conectado como fulano" — preferimos no saberlo a pedir de más.

Solo biblioteca estándar: urllib, json, hashlib, base64, secrets, http.server.
Ninguna dependencia nueva: el panel se distribuye como .exe y cada paquete que
se suma lo engorda.
"""
import base64
import datetime
import hashlib
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs, quote

# ── endpoints de Google ──────────────────────────────────────────────────
# Son constantes de módulo a propósito: el test las reemplaza por un servidor
# falso local y así se puede probar el flujo entero sin credenciales reales.
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

# El permiso más chico que alcanza para leer una planilla. Google lo clasifica
# como "sensible", así que agregarle scopes solo empeora la verificación.
ALCANCE = "https://www.googleapis.com/auth/spreadsheets.readonly"

# Se renueva el access_token un minuto ANTES de que venza. Sin este margen, una
# lectura larga que arranca con el token casi vencido se cae a mitad de camino.
MARGEN_VENCIMIENTO = 60

# Cuántos segundos espera el panel a que la persona termine de dar permiso.
ESPERA_NAVEGADOR = 180

# ── dónde se guarda (mismo criterio que panel_server.py) ─────────────────
# El panel resuelve STATE_DIR como hermano de la carpeta del exe. Se repite acá
# —en vez de importar panel_server— para que esta pieza funcione suelta, sin
# arrastrar Pillow ni la config del panel. Al integrar alcanza con hacer
# google_sheets.STATE_DIR = panel_server.STATE_DIR.
FROZEN = getattr(sys, "frozen", False)
EXE_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.environ.get("MYS_PANEL_STATE") or os.path.join(
    os.path.dirname(EXE_DIR), "PanelMyS_state")

ARCHIVO = "google_token.json"

# Carpetas que el panel publica. Un token acá adentro se sube a GitHub y queda
# público para siempre: es el error que este módulo NO puede cometer.
CARPETAS_PUBLICADAS = {"intranet", "public", "dist", "_site"}


class ErrorGoogle(Exception):
    """Algo salió mal y ya viene traducido a castellano para mostrar tal cual."""


# =====================================================================
#  Guardar y leer el token
# =====================================================================
def _archivo_token():
    """Se calcula en cada llamada para que reasignar STATE_DIR tenga efecto."""
    return os.path.join(STATE_DIR, ARCHIVO)


def _publicable(ruta):
    """True si esa ruta terminaría publicada en la intranet (que no tiene clave).

    Es un cerrojo, no un chequeo cosmético: si mañana alguien apunta STATE_DIR
    a la carpeta del sitio por comodidad, el token no se escribe y se avisa,
    en vez de irse en el próximo Publicar.

    ⚠️ realpath y NO abspath. `abspath` solo ordena el texto de la ruta: no
    sigue los enlaces. En Windows, un junction —que se crea SIN permisos de
    administrador— hace que «PanelMyS_state» apunte de verdad a «intranet», y
    con abspath el cerrojo lo deja pasar tranquilo. Después la clave privada
    queda adentro de la carpeta que se publica, el filtro de Publicar no la
    marca (no empieza con ninguno de los prefijos prohibidos), el .gitignore
    tampoco la tapa, y se va commiteada a un repo público. Los tres controles
    fallan juntos, y el único que puede atajarlo es este.

    Se miran las dos: la real por el caso del enlace, y la de texto por si
    realpath fallara en alguna ruta rara. Ante la duda, se prohíbe."""
    for r in (os.path.realpath(ruta), os.path.abspath(ruta)):
        partes = os.path.normpath(r).split(os.sep)
        if any(p.lower() in CARPETAS_PUBLICADAS for p in partes):
            return True
    # Y el padre también: si la carpeta todavía no existe, realpath no puede
    # resolverla y devuelve el texto tal cual. El padre sí suele existir.
    padre = os.path.dirname(os.path.abspath(ruta))
    partes = os.path.normpath(os.path.realpath(padre)).split(os.sep)
    return any(p.lower() in CARPETAS_PUBLICADAS for p in partes)


def _leer_json_file(p):
    """(dict|None, ok). ok=False si el archivo EXISTE pero está corrupto."""
    if not p or not os.path.isfile(p):
        return None, True                # ausente != corrupto
    try:
        return json.load(open(p, encoding="utf-8-sig")), True
    except (ValueError, OSError):
        return None, False


def _leer_token():
    tok, ok = _leer_json_file(_archivo_token())
    if not ok:
        # Un token ilegible es lo mismo que no tener token: se pide reconectar.
        return None
    return tok


def _guardar_token(tok):
    ruta = _archivo_token()
    if _publicable(ruta):
        raise ErrorGoogle(
            "Me negué a guardar el acceso a Google en «%s»: esa carpeta se "
            "publica y el token quedaría a la vista de cualquiera." % ruta)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    datos = json.dumps(tok, ensure_ascii=False).encode("utf-8")
    # os.open con 0o600 en vez de open(): en Linux/Mac deja el archivo ilegible
    # para otros usuarios de la máquina. En Windows no hace nada, pero tampoco
    # molesta, y el día que el panel corra en otro lado ya está resuelto.
    fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, datos)
    finally:
        os.close(fd)


def desconectar():
    """Olvida el acceso. La cuenta de Google sigue teniendo el permiso dado:
    para sacárselo del todo hay que ir a myaccount.google.com/permissions."""
    try:
        os.remove(_archivo_token())
        return True
    except OSError:
        return False


def estado():
    """Lo que el panel necesita para dibujar el botón: conectado o no.

    No dice de qué cuenta es: pedir el mail requeriría el permiso 'email', y el
    trato es pedir lo mínimo. Antes que inventar un nombre, no mostramos nada."""
    tok = _leer_token()
    if not tok or not tok.get("refresh_token"):
        return {"conectado": False, "archivo": _archivo_token()}
    return {
        "conectado": True,
        "archivo": _archivo_token(),
        "desde": tok.get("desde", ""),
        "alcance": tok.get("scope", ""),
        "vence_en": max(0, int((tok.get("vence") or 0) - time.time())),
    }


# =====================================================================
#  PKCE
# =====================================================================
def _verificador():
    """El secreto de un solo uso de PKCE.

    token_urlsafe(64) da ~86 caracteres del alfabeto [A-Za-z0-9_-], que cae
    entero adentro de lo que el RFC 7636 permite (43 a 128, sin caracteres
    raros). Se usa `secrets` y no `random` porque esto es una credencial."""
    return secrets.token_urlsafe(64)


def _desafio(verificador):
    """SHA-256 del verificador en base64url sin el relleno '='.

    El '=' final rompe la comparación del lado de Google, que espera la forma
    sin relleno que define el RFC."""
    h = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(h).decode("ascii").rstrip("=")


def url_de_permiso(client_id, redirect_uri, desafio, estado_csrf):
    """La pantalla de Google donde la persona acepta."""
    p = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ALCANCE,
        "code_challenge": desafio,
        "code_challenge_method": "S256",
        "state": estado_csrf,
        # Google dice que a las apps instaladas siempre les manda refresh_token,
        # pero lo pedimos explícito igual: si algún día cambia el default, el
        # panel volvería a pedir permiso todas las semanas y nadie sabría por qué.
        "access_type": "offline",
        # Fuerza la pantalla de consentimiento aunque la cuenta ya haya aceptado
        # antes. Sin esto, reconectar devuelve un access_token PERO NINGÚN
        # refresh_token, y el panel queda funcionando una hora y después muerto.
        "prompt": "consent",
    }
    return AUTH_URL + "?" + urlencode(p)


# =====================================================================
#  El servidor de un solo uso que atrapa el código
# =====================================================================
_PAGINA = """<!doctype html><meta charset="utf-8">
<title>Panel Muebles y Sillones</title>
<body style="font:16px/1.6 system-ui;margin:12vh auto;max-width:34rem;text-align:center">
<h2>%s</h2><p style="color:#666">%s</p></body>"""


class _Recibidor(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        # El navegador pide /favicon.ico apenas ve la página. Si tomáramos ese
        # pedido como "ya llegó la respuesta", cerraríamos la escucha sin el
        # código y el usuario vería un error sin haber hecho nada mal.
        if "code" not in q and "error" not in q:
            self.send_response(204)
            self.end_headers()
            return
        self.server.respuesta = {k: v[0] for k, v in q.items()}
        if "code" in q:
            html = _PAGINA % ("Listo", "Ya podés cerrar esta pestaña y volver al panel.")
        else:
            html = _PAGINA % ("No se dio el permiso",
                              "Volvé al panel y probá de nuevo si fue sin querer.")
        cuerpo = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass                      # el panel no tiene consola: ensuciarla no sirve


def _esperar_codigo(srv, espera):
    """Atiende pedidos hasta que llegue el código o se acabe la paciencia."""
    srv.respuesta = None
    srv.timeout = 1               # despertarse cada segundo para mirar el reloj
    limite = time.time() + espera
    while srv.respuesta is None and time.time() < limite:
        srv.handle_request()
    return srv.respuesta


# =====================================================================
#  Hablar con el endpoint de tokens
# =====================================================================
_MOTIVOS = {
    "invalid_grant":
        "Google no reconoce el acceso guardado: caducó o alguien lo revocó. "
        "Hay que volver a apretar «Conectar con Google».",
    "invalid_client":
        "El ID de cliente o la clave están mal pegados (fijate que no haya "
        "quedado un espacio al principio o al final).",
    "redirect_uri_mismatch":
        "El cliente que creaste en Google no es del tipo «App de escritorio». "
        "Creá uno nuevo eligiendo ese tipo.",
    "access_denied":
        "No se dio el permiso en la pantalla de Google.",
    "unauthorized_client":
        "Ese cliente de Google no tiene habilitado este tipo de acceso.",
    "invalid_scope":
        "Google rechazó el permiso pedido. Revisá que la API de Google Sheets "
        "esté activada en el proyecto.",
}


def _post_token(campos, timeout=30):
    """POST x-www-form-urlencoded al endpoint de tokens. Devuelve el dict.

    Los errores de Google vienen en el CUERPO del 400, no en el código: sin
    leerlo, el usuario se queda con un «HTTP 400» que no le dice qué tocar."""
    cuerpo = urlencode(campos).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "PanelMyS/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:                                    # noqa
            d = {}
        codigo = (d.get("error") or "").strip()
        detalle = (d.get("error_description") or "").strip()
        texto = _MOTIVOS.get(codigo) or (detalle or "Google respondió %d." % e.code)
        raise ErrorGoogle(texto)
    except urllib.error.URLError as e:
        raise ErrorGoogle("No pude contactar a Google (¿hay internet?): %s" % e.reason)
    except ValueError:
        raise ErrorGoogle("Google respondió algo que no pude entender.")


def _campos_cliente(tok):
    """client_id siempre; client_secret solo si hay.

    Google documenta el secret como OPCIONAL para apps instaladas, pero a los
    clientes tipo «App de escritorio» igual les emite uno y hay tipos de cliente
    que lo exigen. Mandarlo cuando existe funciona en los dos casos; mandarlo
    vacío, en ninguno."""
    campos = {"client_id": tok.get("client_id", "")}
    if tok.get("client_secret"):
        campos["client_secret"] = tok["client_secret"]
    return campos


# =====================================================================
#  Conectar (una sola vez en la vida del panel)
# =====================================================================
def conectar(client_id, client_secret="", puerto=0, espera=ESPERA_NAVEGADOR,
             abrir=None, timeout=30):
    """Hace el baile entero y deja el refresh_token guardado.

    `puerto=0` deja que el sistema elija uno libre: los clientes de escritorio
    de Google aceptan cualquier puerto de 127.0.0.1 sin declararlo en la consola,
    así que no hay nada que configurar y no chocamos con el 8123 del panel.

    `abrir` es quién abre el navegador (el test le pasa otra cosa)."""
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()
    if not client_id.endswith(".apps.googleusercontent.com"):
        raise ErrorGoogle("Ese no parece un ID de cliente de Google: tiene que "
                          "terminar en .apps.googleusercontent.com")

    # Chequear ANTES de mandar a nadie al navegador: hacer todo el trámite para
    # después negarse a guardar sería una tomada de pelo.
    if _publicable(_archivo_token()):
        raise ErrorGoogle(
            "La carpeta de estado (%s) es una que se publica. No voy a guardar "
            "ahí el acceso a Google." % STATE_DIR)

    verificador = _verificador()
    estado_csrf = secrets.token_urlsafe(24)

    srv = HTTPServer(("127.0.0.1", puerto), _Recibidor)
    try:
        # Sin barra final: es la forma exacta que después se repite en el canje,
        # y Google compara los dos redirect_uri caracter por caracter.
        redirect_uri = "http://127.0.0.1:%d" % srv.server_address[1]
        url = url_de_permiso(client_id, redirect_uri, _desafio(verificador), estado_csrf)
        # webbrowser.open devuelve False cuando no encontró navegador (pasa con
        # algunas PCs sin navegador por defecto). Dejar al usuario mirando una
        # pantalla que dice "esperando" sin que se haya abierto nada es la peor
        # salida: mejor cortar y darle el link para que lo pegue a mano.
        if (abrir or webbrowser.open)(url) is False:
            raise ErrorGoogle("No pude abrir el navegador solo. Copiá esta "
                              "dirección y pegala en el navegador:\n\n%s" % url)
        resp = _esperar_codigo(srv, espera)
    finally:
        srv.server_close()

    if resp is None:
        raise ErrorGoogle("Se pasaron los %d segundos esperando el permiso en el "
                          "navegador. Probá de nuevo." % espera)
    if resp.get("error"):
        raise ErrorGoogle(_MOTIVOS.get(resp["error"], "Google devolvió: %s" % resp["error"]))
    # Si el `state` no vuelve igual, esa respuesta no es la nuestra: puede ser
    # otra pestaña o alguien tirándole pedidos al 127.0.0.1. No se canjea.
    if resp.get("state") != estado_csrf:
        raise ErrorGoogle("La respuesta de Google no coincide con el pedido. "
                          "Por seguridad no la usé: volvé a intentar.")

    datos = _post_token(dict(_campos_cliente(
        {"client_id": client_id, "client_secret": client_secret}),
        code=resp["code"],
        code_verifier=verificador,
        redirect_uri=redirect_uri,
        grant_type="authorization_code"), timeout=timeout)

    if not datos.get("refresh_token"):
        raise ErrorGoogle("Google no devolvió el permiso permanente. Desconectá "
                          "el panel en myaccount.google.com/permissions y "
                          "volvé a conectar.")
    # Si la persona destildó el permiso en la pantalla de Google, el token llega
    # igual pero sin el scope. Mejor decirlo ahora que fallar recién al leer.
    if ALCANCE not in (datos.get("scope") or ALCANCE).split():
        raise ErrorGoogle("Faltó tildar el permiso para ver las planillas. "
                          "Volvé a conectar y dejá la casilla marcada.")

    tok = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": datos["refresh_token"],
        "access_token": datos.get("access_token", ""),
        "vence": time.time() + int(datos.get("expires_in") or 0),
        "scope": datos.get("scope", ALCANCE),
        "desde": datetime.date.today().isoformat(),
    }
    _guardar_token(tok)
    return {"ok": True, "archivo": _archivo_token()}


# =====================================================================
#  Renovar solo
# =====================================================================
def _access_token(forzar=False, timeout=30):
    tok = _leer_token()
    if not tok or not tok.get("refresh_token"):
        raise ErrorGoogle("El panel todavía no está conectado con Google. "
                          "Apretá «Conectar con Google».")
    vigente = tok.get("access_token") and time.time() < (tok.get("vence") or 0) - MARGEN_VENCIMIENTO
    if vigente and not forzar:
        return tok["access_token"]

    datos = _post_token(dict(_campos_cliente(tok),
                             refresh_token=tok["refresh_token"],
                             grant_type="refresh_token"), timeout=timeout)
    tok["access_token"] = datos.get("access_token", "")
    tok["vence"] = time.time() + int(datos.get("expires_in") or 0)
    # Google puede rotar el refresh_token; si manda uno nuevo hay que quedarse
    # con ese, porque el viejo deja de servir.
    if datos.get("refresh_token"):
        tok["refresh_token"] = datos["refresh_token"]
    _guardar_token(tok)
    if not tok["access_token"]:
        raise ErrorGoogle("Google renovó el acceso pero no mandó el token.")
    return tok["access_token"]


# =====================================================================
#  Leer la planilla
# =====================================================================
_RE_ID = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_RE_ID_SUELTO = re.compile(r"^[a-zA-Z0-9-_]{20,}$")


def id_de_planilla(texto):
    """Acepta la URL entera pegada del navegador o el ID pelado.

    Nadie va a buscar el ID adentro de la URL: se pega el link y listo."""
    t = (texto or "").strip()
    m = _RE_ID.search(t)
    if m:
        return m.group(1)
    if _RE_ID_SUELTO.match(t):
        return t
    raise ErrorGoogle("No reconocí la planilla. Pegá el link entero de Google "
                      "Sheets, el que empieza con https://docs.google.com/spreadsheets/d/...")


def _pedir(url, token, timeout):
    """(codigo, texto). No levanta excepción en 4xx a propósito: el 401 es parte
    del flujo normal (token vencido) y la decisión de reintentar es de arriba."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("User-Agent", "PanelMyS/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception:                                    # noqa
            return e.code, ""
    except urllib.error.URLError as e:
        raise ErrorGoogle("No pude contactar a Google (¿hay internet?): %s" % e.reason)


def _explicar(codigo, cuerpo):
    """Traduce el error de la API a algo accionable."""
    msg = ""
    try:
        msg = ((json.loads(cuerpo) or {}).get("error") or {}).get("message") or ""
    except Exception:                                        # noqa
        pass
    bajo = msg.lower()
    if codigo == 403 and ("has not been used in project" in bajo or "disabled" in bajo):
        return ("Falta activar la API de Google Sheets en el proyecto de Google "
                "Cloud. Está explicado en COMO-CONECTAR-DRIVE.md, paso 2.")
    if codigo == 403:
        return ("La cuenta de Google con la que se conectó el panel no tiene "
                "acceso a esa planilla. Compartísela desde Drive (alcanza con "
                "«Lector»).")
    if codigo == 404:
        return ("No hay ninguna planilla con ese link, o la cuenta conectada no "
                "la ve. Revisá el link y con qué cuenta conectaste el panel.")
    if codigo == 400 and "unable to parse range" in bajo:
        return ("El rango está mal escrito. Se escribe como en la planilla: "
                "«Hoja 1!A:Z», o dejalo vacío para leer la primera hoja entera.")
    if codigo == 401:
        return ("Google rechazó el acceso aun después de renovarlo. Volvé a "
                "apretar «Conectar con Google».")
    if codigo == 429:
        return "Google está limitando las consultas. Esperá un minuto y probá de nuevo."
    return "Google respondió %d%s" % (codigo, (": " + msg) if msg else ".")


def _emparejar(values):
    """Las filas de la API vienen de largos distintos y hay que emparejarlas.

    La documentación de Sheets lo dice así: «Empty trailing rows and columns are
    omitted». O sea que una fila donde no se cargó el teléfono ni el mail llega
    con dos celdas menos, y hasta el encabezado puede llegar corto. Si no se
    rellena, cada fila desalinea las columnas del analizador y la columna 5 de
    una fila termina comparándose contra la 7 de la otra.

    Se rellena con "" y NO se inventa nombre para un encabezado que vino vacío:
    una columna sin título es un problema de la planilla, y el revisor tiene que
    poder verlo."""
    if not values:
        return []
    ancho = max(len(f) for f in values)
    return [[("" if c is None else str(c)) for c in f] + [""] * (ancho - len(f))
            for f in values]


def _pedir_api(url, timeout):
    """El texto de la respuesta, o ErrorGoogle ya traducido.

    La regla del 401 vive acá y en un solo lugar a propósito: cada llamada que
    la reimplemente es una oportunidad de reintentar de más."""
    cod, cuerpo = _pedir(url, _access_token(timeout=timeout), timeout)
    if cod == 401:
        # Un 401 casi siempre es el access_token vencido antes de tiempo (reloj
        # de la PC corrido, permiso revocado y vuelto a dar). Se renueva y se
        # reintenta UNA sola vez: si vuelve a dar 401 el problema no es el token
        # y reintentar sería un loop contra Google.
        cod, cuerpo = _pedir(url, _access_token(forzar=True, timeout=timeout), timeout)
    if cod != 200:
        raise ErrorGoogle(_explicar(cod, cuerpo))
    try:
        return json.loads(cuerpo)
    except ValueError:
        raise ErrorGoogle("Google devolvió algo que no pude leer.")


def leer(planilla, rango="", timeout=30):
    """filas: lista de listas, filas[0] son los encabezados (como el resto).

    `planilla` es el link o el ID. `rango` en notación de la planilla
    («Hoja 1!A:Z»); vacío = primera hoja entera."""
    pid = id_de_planilla(planilla)
    # Sin nombre de hoja, Google usa la primera. "A:ZZ" son 702 columnas: como
    # las vacías del final no vuelven, pedir de más no cuesta nada y evita que
    # una planilla ancha llegue cortada sin que nadie se entere.
    r = (rango or "").strip() or "A:ZZ"
    url = "%s/%s/values/%s?%s" % (
        SHEETS_API, quote(pid, safe=""), quote(r, safe=""),
        urlencode({"majorDimension": "ROWS",
                   # FORMATTED_VALUE devuelve lo que se ve en pantalla: las
                   # fechas como "26/08/2026" y no como el número 46260. Es lo
                   # mismo que daría exportar a CSV, que es lo que el analizador
                   # ya sabe leer.
                   "valueRenderOption": "FORMATTED_VALUE"}))

    datos = _pedir_api(url, timeout)
    # Sin la clave "values" el rango está vacío. Devolver [] y que el panel diga
    # "esa hoja no tiene nada" es mejor que devolver una tabla fantasma.
    return _emparejar(datos.get("values") or [])


def hojas(planilla, timeout=30):
    """Los nombres de las hojas, para que el panel las ofrezca en una lista en
    vez de hacer que alguien las tipee bien de memoria."""
    pid = id_de_planilla(planilla)
    url = "%s/%s?%s" % (SHEETS_API, quote(pid, safe=""),
                        urlencode({"fields": "properties.title,sheets.properties.title"}))
    d = _pedir_api(url, timeout)
    return {
        "titulo": (d.get("properties") or {}).get("title", ""),
        "hojas": [(h.get("properties") or {}).get("title", "")
                  for h in (d.get("sheets") or [])],
    }
