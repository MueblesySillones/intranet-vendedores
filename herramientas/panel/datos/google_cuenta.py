# -*- coding: utf-8 -*-
"""Entrar a Drive con una "cuenta de servicio": compartirle el archivo y listo.

POR QUÉ EXISTE ESTE MÓDULO SI YA ESTÁ google_sheets.py
  google_sheets.py usa OAuth: la persona aprieta un botón, se abre el navegador,
  entra con su cuenta y acepta. Funciona, está probado, y sigue disponible. Pero
  tiene tres asperezas que no dependen de nuestro código sino de cómo Google
  trata a las aplicaciones chicas:

    1. Antes de poder apretar el botón hay que crear un "cliente OAuth" en la
       consola de Google, configurar la pantalla de consentimiento y copiar dos
       claves largas al panel.
    2. En esa pantalla Google avisa "Google no verificó esta aplicación" y hay
       que entrar a "Configuración avanzada" para seguir. Da miedo, y con razón:
       es el mismo cartel que aparece cuando algo es realmente sospechoso.
    3. Mientras el proyecto esté en modo "prueba", Google vence el permiso a los
       SIETE DÍAS. El panel deja de leer solo, sin que nadie haya tocado nada.

  Una cuenta de servicio es un usuario de Google que no es una persona: tiene
  una dirección de mail y nada más. Le compartís la planilla desde Drive igual
  que se la compartirías a un compañero, con "Lector", y el panel entra con ella.
  No hay pantalla de consentimiento, no hay cartel de aplicación no verificada,
  y el permiso no se vence: dura hasta que le saques el acceso al archivo.

  Y como el permiso es "te compartí este archivo", el panel ve EXACTAMENTE los
  archivos que le compartieron. Ni uno más. Eso es más chico que el OAuth, donde
  el permiso alcanza a todas las planillas de la cuenta que aceptó.

CÓMO PIDE EL TOKEN
  Se arma un JWT (un texto firmado), se lo manda a Google, y Google devuelve un
  access_token que dura una hora. No hay navegador, no hay ida y vuelta.

  El problema es la firma: Google exige RS256, o sea RSA con SHA-256, y eso
  normalmente pide `cryptography` o `PyJWT`. El panel se distribuye como .exe y
  cada paquete que se suma lo engorda: `cryptography` sola pesa más que todo el
  panel.

  Pero una firma RSA, abajo de todo, es una sola cuenta: pow(mensaje, d, n).
  Python trae enteros de precisión arbitraria y un `pow` con módulo escrito en C.
  Lo único que falta es sacar `n` y `d` del archivo de la clave, que es DER
  adentro de base64 — unas cuarenta líneas de parseo. Eso es lo que hace este
  módulo, y la prueba lo verifica contra OPENSSL: si un verificador de verdad,
  ajeno a este código, acepta la firma, está bien hecha.

  Tarda ~19 ms y se firma una vez por hora.

QUÉ PERMISO PIDE
  Tres, y los tres de lectura:
    · spreadsheets.readonly  — leer planillas
    · documents.readonly     — leer documentos
    · drive.metadata.readonly — ver el NOMBRE y la fecha de los archivos, para
      poder armar la lista donde se elige. No da el contenido de nada.

  No puede escribir, ni borrar, ni modificar. Y lo que alcanza es solo lo que le
  compartieron a esta cuenta: no "el Drive de la empresa", sino la bandeja del
  panel. Un archivo que nadie le compartió no existe para el panel.

DÓNDE VIVE LA CLAVE
  En la carpeta de estado del panel, junto al token de OAuth. Nunca adentro de
  intranet/, que es lo único que el panel publica: hay un cerrojo que se niega a
  escribir ahí (se reusa el de google_sheets).

  OJO: el archivo que baja Google trae una clave privada de verdad. El que la
  tenga puede entrar a todo lo que se le haya compartido a esa cuenta. Se guarda
  con permisos 0600 y no se muestra nunca en pantalla — de todo el archivo, el
  panel solo muestra la dirección de mail, que es la parte que hay que copiar.

Solo biblioteca estándar.
"""
import base64
import datetime
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, quote

from datos import google_sheets
from datos.google_sheets import (
    ErrorGoogle, SHEETS_API, TOKEN_URL, MARGEN_VENCIMIENTO,
    _publicable, _leer_json_file, _emparejar, _pedir, _explicar,
    _RE_ID_SUELTO,
)

DOCS_API = "https://docs.googleapis.com/v1/documents"
DRIVE_API = "https://www.googleapis.com/drive/v3/files"

# Los dos permisos, separados por espacio como los pide Google. Leer y nada más.
ALCANCE = ("https://www.googleapis.com/auth/spreadsheets.readonly"
           " https://www.googleapis.com/auth/documents.readonly"
           " https://www.googleapis.com/auth/drive.metadata.readonly")

# El JWT vale una hora, que es el máximo que Google acepta. Pedir menos solo
# haría firmar más seguido sin ganar nada.
VIDA_JWT = 3600

ARCHIVO = "google_cuenta.json"


def _archivo_clave():
    """Se calcula en cada llamada para que reasignar STATE_DIR tenga efecto.

    STATE_DIR se lee de google_sheets y no de una copia local: el panel le
    reasigna el suyo al arrancar, y si tuviéramos una copia quedaría apuntando
    a otro lado."""
    return os.path.join(google_sheets.STATE_DIR, ARCHIVO)


# =====================================================================
#  RSA con lo que trae Python
# =====================================================================
def _leer_largo(b, i):
    """El largo de un campo DER: corto (<128) o largo (dice cuántos bytes sigue).

    DER no permite largo indefinido (el 0x80 de BER). Si aparece, el archivo no
    es lo que decimos que es y frenamos acá en vez de leer basura."""
    n = b[i]
    i += 1
    if n < 0x80:
        return n, i
    cuantos = n & 0x7F
    if cuantos == 0 or cuantos > 4:
        raise ErrorGoogle("El archivo de la cuenta de Google está dañado "
                          "(la clave no se puede leer). Bajalo de nuevo.")
    return int.from_bytes(b[i:i + cuantos], "big"), i + cuantos


def _campos(b, i, fin):
    """Recorre una secuencia DER y devuelve [(etiqueta, contenido), ...]."""
    out = []
    while i < fin:
        etiqueta = b[i]
        largo, i = _leer_largo(b, i + 1)
        out.append((etiqueta, b[i:i + largo]))
        i += largo
    return out


def clave_privada(pem, verificar=False):
    """Devuelve (n, d) de una clave RSA en PEM. Sin librerías.

    Google entrega la clave en PKCS#8 ("BEGIN PRIVATE KEY"), que es un sobre:
    [versión, qué-algoritmo-es, la-clave-adentro]. Adentro está la clave RSA de
    verdad, en PKCS#1: [versión, n, e, d, p, q, ...]. Se abren los dos sobres y
    se sacan el primero y el tercero de los números.

    También acepta PKCS#1 pelado ("BEGIN RSA PRIVATE KEY") por si alguna vez el
    archivo viene así."""
    if "PRIVATE KEY" not in (pem or ""):
        raise ErrorGoogle("El archivo de la cuenta no trae la clave privada. "
                          "Fijate de haber bajado el archivo JSON completo.")
    cuerpo = "".join(l for l in pem.splitlines() if "-----" not in l).strip()
    try:
        der = base64.b64decode(cuerpo)
    except Exception:                                        # noqa
        raise ErrorGoogle("La clave del archivo está dañada. Bajalo de nuevo "
                          "desde Google.")

    try:
        if "BEGIN PRIVATE KEY" in pem:
            largo, i = _leer_largo(der, 1)
            partes = _campos(der, i, i + largo)
            # [0]=versión  [1]=algoritmo  [2]=OCTET STRING con la PKCS#1 adentro
            der = partes[2][1]

        largo, i = _leer_largo(der, 1)
        nums = _campos(der, i, i + largo)
        # DER guarda los enteros con signo, así que un módulo que empieza con el
        # bit alto en 1 viene con un 0x00 adelante. from_bytes sin signo lo come
        # sin problema: el cero de más no cambia el valor.
        n = int.from_bytes(nums[1][1], "big")
        e = int.from_bytes(nums[2][1], "big")
        d = int.from_bytes(nums[3][1], "big")
    except ErrorGoogle:
        raise
    except Exception:                                        # noqa
        raise ErrorGoogle("No pude leer la clave del archivo de la cuenta. "
                          "Fijate de haber elegido el formato JSON al crearla.")

    if n < 2 or not (0 < d < n):
        raise ErrorGoogle("La clave del archivo de la cuenta no es válida.")
    if n.bit_length() < 2048:
        raise ErrorGoogle("La clave de la cuenta es de %d bits. Google pide al "
                          "menos 2048: bajá una clave nueva."
                          % n.bit_length())

    if verificar:
        # ⚠️ Que n y d SEAN LA MISMA CLAVE. Los chequeos de arriba miran cada
        # número por separado, y una sola letra cambiada al copiar y pegar el
        # archivo deja los dos números "válidos" pero de claves distintas: se
        # guarda como buena y falla recién una semana después, con un mensaje
        # que manda a mirar el reloj. Elevar a d y volver a elevar a e tiene
        # que devolver lo mismo que entró; si no, la clave está rota.
        testigo = 0xC0FFEE
        if pow(pow(testigo, d, n), e, n) != testigo:
            raise ErrorGoogle(
                "La clave del archivo está corrupta: sus dos mitades no se "
                "corresponden. Suele pasar cuando se copia y pega el contenido "
                "y se pierde un carácter. Bajá el archivo de nuevo desde Google "
                "y cargalo con «Elegir el archivo…» en vez de pegarlo.")
    return n, d


# El prefijo que dice "lo que sigue es un SHA-256", tal como lo fija PKCS#1 v1.5.
# Es una constante del estándar (RFC 8017): no se calcula, se copia.
_SHA256_DER = bytes.fromhex("3031300d060960864801650304020105000420")


def firmar(mensaje, n, d):
    """RSASSA-PKCS1-v1_5 con SHA-256, que es lo que Google llama RS256.

    El bloque que se firma es: 00 01 FF FF ... FF 00 <prefijo> <sha256>, del
    largo exacto del módulo. Después se lo eleva a la d, módulo n. Eso es todo:
    el resto de una librería de RSA es formato."""
    tam = (n.bit_length() + 7) // 8
    resumen = _SHA256_DER + hashlib.sha256(mensaje).digest()
    # 3 son los bytes fijos: el 00 del principio, el 01, y el 00 separador.
    if tam < len(resumen) + 11:
        raise ErrorGoogle("La clave de la cuenta es demasiado corta para firmar.")
    bloque = b"\x00\x01" + b"\xff" * (tam - len(resumen) - 3) + b"\x00" + resumen
    return pow(int.from_bytes(bloque, "big"), d, n).to_bytes(tam, "big")


def _b64url(b):
    """base64url sin el relleno '=', que es como lo quiere el JWT."""
    return base64.urlsafe_b64encode(b).rstrip(b"=")


def armar_jwt(carga, pem):
    n, d = clave_privada(pem)
    cab = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"},
                             separators=(",", ":")).encode("utf-8"))
    cue = _b64url(json.dumps(carga, separators=(",", ":")).encode("utf-8"))
    firmado = cab + b"." + cue
    return (firmado + b"." + _b64url(firmar(firmado, n, d))).decode("ascii")


# =====================================================================
#  Guardar y leer el archivo de la cuenta
# =====================================================================
_CAMPOS_PEDIDOS = ("client_email", "private_key")


def revisar_json(texto):
    """Valida el archivo que bajó de Google y devuelve el dict.

    Se valida ANTES de guardar: un archivo incompleto guardado es un error que
    recién aparece la primera vez que alguien quiere leer una planilla, y para
    entonces ya nadie se acuerda de qué pegó."""
    t = (texto or "").strip()
    if not t:
        raise ErrorGoogle("Pegá el contenido del archivo que bajaste de Google.")
    try:
        d = json.loads(t)
    except ValueError:
        raise ErrorGoogle("Eso no es el archivo de la cuenta. Tiene que ser el "
                          "archivo .json que baja Google, pegado entero "
                          "(empieza con { y termina con }).")
    if not isinstance(d, dict):
        raise ErrorGoogle("Ese archivo no tiene la forma que esperaba Google.")

    # El error más probable de todos: bajar el archivo del lugar equivocado de
    # la consola. Vale la pena reconocerlo y decir a dónde ir.
    if d.get("type") == "authorized_user" or "refresh_token" in d:
        raise ErrorGoogle("Ese es un archivo de credenciales de usuario, no de "
                          "una cuenta de servicio. En Google hay que ir a "
                          "«Cuentas de servicio», no a «ID de cliente de OAuth».")
    if "installed" in d or "web" in d:
        raise ErrorGoogle("Ese es el archivo de un cliente de OAuth, no el de "
                          "una cuenta de servicio. Está explicado en "
                          "COMO-CONECTAR-DRIVE.md, paso 2.")

    faltan = [c for c in _CAMPOS_PEDIDOS if not d.get(c)]
    if faltan:
        raise ErrorGoogle("Al archivo le falta «%s». Fijate de haber bajado el "
                          "archivo completo, en formato JSON." % faltan[0])
    if "@" not in str(d.get("client_email")):
        raise ErrorGoogle("El archivo no trae una dirección de mail válida.")
    # ⚠️ Tiene que ser texto. Un `private_key` que venga como número o como
    # objeto —pasa si alguien arma el JSON a mano— reventaba con un TypeError
    # crudo en vez de un mensaje que se entienda.
    if not isinstance(d.get("private_key"), str):
        raise ErrorGoogle("El campo «private_key» del archivo no es texto. "
                          "Bajá el archivo de nuevo desde Google, sin editarlo.")
    # Se valida la clave de verdad, parseándola Y comprobando que sus dos
    # mitades se correspondan. Si está rota, mejor saberlo ahora que dentro de
    # una semana, cuando nadie se acuerde de qué se pegó.
    clave_privada(d["private_key"], verificar=True)
    return d


def guardar(texto):
    """Deja el archivo de la cuenta guardado y devuelve el mail para copiar."""
    d = revisar_json(texto)
    ruta = _archivo_clave()
    if _publicable(ruta):
        raise ErrorGoogle(
            "Me negué a guardar la clave de Google en «%s»: esa carpeta se "
            "publica y la clave quedaría a la vista de cualquiera." % ruta)
    # Se guarda SOLO lo que hace falta. El archivo de Google trae además ids y
    # URLs que no usamos: no copiarlas es una credencial menos en disco.
    limpio = {
        "client_email": d["client_email"],
        "private_key": d["private_key"],
        "project_id": d.get("project_id", ""),
        "desde": datetime.date.today().isoformat(),
    }
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    # 0600: en Linux/Mac queda ilegible para otros usuarios de la máquina. En
    # Windows no hace nada, pero tampoco molesta.
    try:
        fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    except OSError as e:
        raise ErrorGoogle("No pude escribir la cuenta en «%s»: %s" % (ruta, e))
    try:
        os.write(fd, json.dumps(limpio, ensure_ascii=False).encode("utf-8"))
    finally:
        os.close(fd)
    # ⚠️ El modo de os.open SOLO se aplica al crear. Si el archivo ya existía
    # con permisos abiertos, se queda como estaba — y es justo en Linux/Mac,
    # donde esto importa, donde el archivo sobrevive entre cargas.
    try:
        os.chmod(ruta, 0o600)
    except OSError:                        # en Windows no aplica; no es motivo de error
        pass
    _CACHE.clear()
    return {"ok": True, "mail": d["client_email"]}


def _leer_clave():
    d, ok = _leer_json_file(_archivo_clave())
    if not ok or not d or not d.get("private_key"):
        return None
    return d


def estado():
    """Lo que la pantalla necesita: si hay cuenta, y cuál es el mail.

    El mail SÍ se muestra, al revés que en OAuth: es la parte que hay que
    copiar y pegar en Drive para compartir el archivo. Sin verlo, esto no se
    puede usar."""
    d = _leer_clave()
    if not d:
        return {"conectado": False, "archivo": _archivo_clave()}
    return {
        "conectado": True,
        "mail": d.get("client_email", ""),
        "proyecto": d.get("project_id", ""),
        "desde": d.get("desde", ""),
        "archivo": _archivo_clave(),
    }


def desconectar():
    """Olvida la cuenta. Los archivos que le compartieron le siguen compartidos:
    para cortar del todo hay que sacarle el acceso desde Drive."""
    _CACHE.clear()
    try:
        os.remove(_archivo_clave())
        return True
    except OSError:
        return False


# =====================================================================
#  El token
# =====================================================================
# El access_token dura una hora. Se guarda en memoria y no en disco: si el panel
# se reinicia se firma otro, que cuesta 19 ms. Escribirlo sería un archivo más
# con una credencial adentro a cambio de nada.
_CACHE = {}


def _motivo(d, codigo):
    """Traduce el rechazo de Google a algo que se pueda ir a arreglar."""
    err = (d.get("error") or "").strip()
    desc = (d.get("error_description") or "").strip()
    bajo = desc.lower()
    if "invalid_grant" in err:
        # Este es el error raro que sin explicación cuesta horas: el JWT lleva
        # la hora adentro, y Google rechaza el que viene del futuro o de muy
        # atrás. Una PC con la fecha corrida falla siempre, sin motivo visible.
        if "invalid jwt" in bajo or "signature" in bajo or "too early" in bajo:
            return ("Google rechazó la firma. Casi siempre es el reloj de esta "
                    "PC: fijate que la hora y la fecha estén bien y probá de "
                    "nuevo. Si la hora está bien, volvé a cargar el archivo de "
                    "la cuenta (puede haberse copiado incompleto).")
        return ("Google no aceptó la cuenta. Puede ser que la hayan borrado o "
                "que le hayan dado de baja la clave.")
    if "unauthorized_client" in err:
        return ("La cuenta existe pero no tiene permiso para esto. Fijate de "
                "haber activado las APIs de Sheets y Docs en el proyecto.")
    if "invalid_client" in err:
        return "El archivo de la cuenta no es válido. Bajalo de nuevo desde Google."
    if desc:
        # Recortado: esto viene de afuera y va derecho a la pantalla. Google no
        # manda secretos acá, pero un eco sin límite de algo remoto no es algo
        # que uno quiera tener.
        return "Google respondió: %s" % desc[:300]
    return "Google rechazó la cuenta (error %d)." % codigo


def _access_token(forzar=False, timeout=30):
    # El cache se ata al ALCANCE: si manana se agrega un permiso, un token
    # viejo guardado con los permisos de antes serviria igual y fallaria
    # recien al usar lo nuevo, con un 403 que no se entiende.
    d = _leer_clave()
    if not d:
        raise ErrorGoogle("Todavía no cargaste la cuenta de Google en el panel.")
    quien = d.get("client_email") or ""
    if not quien:
        raise ErrorGoogle("El archivo de la cuenta guardado no tiene dirección "
                          "de mail. Volvé a cargarlo.")

    # ⚠️ El cache se ata a QUIEN pidió el token, no solo al alcance. Si cambia
    # la cuenta cargada, un token guardado de la anterior seguiría sirviendo
    # hasta una hora: la pantalla mostraría una cuenta y el panel leería Drive
    # con las credenciales de otra. Hoy no pasa porque el panel fija la carpeta
    # de estado al arrancar, pero el día que haya más de un cliente, esto es
    # acceso cruzado entre clientes.
    if not forzar and _CACHE.get("token") and _CACHE.get("alcance") == ALCANCE \
            and _CACHE.get("quien") == quien \
            and time.time() < _CACHE.get("vence", 0) - MARGEN_VENCIMIENTO:
        return _CACHE["token"]

    ahora = int(time.time())
    jwt = armar_jwt({
        "iss": d["client_email"],
        "scope": ALCANCE,
        "aud": TOKEN_URL,
        "iat": ahora,
        "exp": ahora + VIDA_JWT,
    }, d["private_key"])

    cuerpo = urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=cuerpo, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "PanelMyS/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            d2 = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:                                    # noqa
            d2 = {}
        raise ErrorGoogle(_motivo(d2, e.code))
    except urllib.error.URLError as e:
        raise ErrorGoogle("No pude contactar a Google (¿hay internet?): %s" % e.reason)
    except ValueError:
        raise ErrorGoogle("Google respondió algo que no pude entender.")

    tok = datos.get("access_token") or ""
    if not tok:
        raise ErrorGoogle("Google aceptó la cuenta pero no mandó el permiso.")
    _CACHE["token"] = tok
    _CACHE["alcance"] = ALCANCE
    _CACHE["quien"] = quien
    try:
        vive = int(datos.get("expires_in") or 0)
    except (TypeError, ValueError):        # Google mandó algo que no es número
        vive = 0
    _CACHE["vence"] = time.time() + vive
    return tok


def _explicar_cuenta(codigo, cuerpo):
    """Como _explicar de OAuth, pero el 403/404 se cuentan distinto.

    Con una cuenta de servicio, "no lo veo" casi siempre significa una sola
    cosa: falta compartirle el archivo. Decir eso, con el mail al lado, resuelve
    el problema; decir "revisá los permisos" no."""
    msg = ""
    try:
        msg = ((json.loads(cuerpo) or {}).get("error") or {}).get("message") or ""
    except Exception:                                        # noqa
        pass
    if codigo == 403 and ("has not been used" in msg.lower()
                          or "disabled" in msg.lower()):
        return ("Falta activar la API de Google en el proyecto. Está explicado "
                "en COMO-CONECTAR-DRIVE.md, paso 3.")
    if codigo in (403, 404):
        mail = (_leer_clave() or {}).get("client_email", "la cuenta del panel")
        return ("El archivo no está compartido con la cuenta del panel. Abrilo "
                "en Drive, tocá «Compartir» y agregá esta dirección como "
                "Lector:  %s" % mail)
    return _explicar(codigo, cuerpo)


def _pedir_api(url, timeout):
    """El JSON de la respuesta, o ErrorGoogle ya traducido.

    El 401 se reintenta UNA vez con token nuevo: el caso normal es un token que
    venció antes de tiempo. Si vuelve a dar 401 el problema no es el token y
    reintentar sería pegarle a Google al pedo."""
    cod, cuerpo = _pedir(url, _access_token(timeout=timeout), timeout)
    if cod == 401:
        cod, cuerpo = _pedir(url, _access_token(forzar=True, timeout=timeout), timeout)
    if cod != 200:
        raise ErrorGoogle(_explicar_cuenta(cod, cuerpo))
    try:
        return json.loads(cuerpo)
    except ValueError:
        raise ErrorGoogle("Google devolvió algo que no pude leer.")


# =====================================================================
#  Leer
# =====================================================================
_RE_DOC = re.compile(r"/document/d/([a-zA-Z0-9-_]+)")


def es_documento(texto):
    """True si el link es un Google Doc y no una planilla.

    Sirve para que en la pantalla haya UNA sola caja donde pegar el link, y el
    panel se de cuenta solo de que le pegaron."""
    return bool(_RE_DOC.search((texto or "").strip()))


def id_de_documento(texto):
    """El id de un Google Doc, desde el link entero o el id pelado.

    ⚠️ El id pelado tiene que PARECER un id (los de Google andan por los 44
    caracteres). Sin ese filtro, cualquier texto sin barras se tomaba como id
    valido y se le mandaba a Google, que contestaba un 404 confuso en vez de
    "eso no es un link de documento". Lo encontro la prueba, no la produccion."""
    t = (texto or "").strip()
    m = _RE_DOC.search(t)
    if m:
        return m.group(1)
    if _RE_ID_SUELTO.match(t):
        return t
    raise ErrorGoogle("Ese link no es de un documento de Google. Pegá el link "
                      "entero, el que empieza con "
                      "https://docs.google.com/document/d/...")


def leer(planilla, rango="", timeout=30):
    """Las filas de una planilla. Mismo formato que google_sheets.leer()."""
    pid = google_sheets.id_de_planilla(planilla)
    # "A:ZZ" son 702 columnas: como las vacías del final no vuelven, pedir de
    # más no cuesta nada y evita que una planilla ancha llegue cortada.
    r = (rango or "").strip() or "A:ZZ"
    url = "%s/%s/values/%s?%s" % (
        SHEETS_API, quote(pid, safe=""), quote(r, safe=""),
        urlencode({"majorDimension": "ROWS",
                   # FORMATTED_VALUE devuelve lo que se ve en pantalla: las
                   # fechas como "26/08/2026" y no como el número 46260.
                   "valueRenderOption": "FORMATTED_VALUE"}))
    return _emparejar(_pedir_api(url, timeout).get("values") or [])


def hojas(planilla, timeout=30):
    """Los nombres de las hojas, para ofrecerlas en una lista."""
    pid = google_sheets.id_de_planilla(planilla)
    url = "%s/%s?%s" % (SHEETS_API, quote(pid, safe=""),
                        urlencode({"fields": "properties.title,sheets.properties.title"}))
    d = _pedir_api(url, timeout)
    return {
        "titulo": (d.get("properties") or {}).get("title", ""),
        "hojas": [(h.get("properties") or {}).get("title", "")
                  for h in (d.get("sheets") or [])],
    }


def _escapar(t):
    """Deja un texto listo para meter entre comillas simples en una consulta
    de Drive.

    Google usa comillas simples para delimitar, asi que un archivo llamado
    "Ventas de O'Brien" cierra la comilla antes de tiempo y rompe la
    consulta entera. Primero la barra (o escaparia el escape) y despues la
    comilla, que es el orden que importa."""
    return (t or "").replace("\\", "\\\\").replace("'", "\\'")


# Los dos tipos que sabemos leer. Google los identifica por "mimeType".
HOJA = "application/vnd.google-apps.spreadsheet"
DOCUMENTO = "application/vnd.google-apps.document"


def archivos(buscar="", cuantos=100, timeout=30):
    """Los archivos que le compartieron a la cuenta del panel.

    POR QUÉ UNA LISTA Y NO PEGAR EL LINK
      Pegar un link es pedirle a alguien que haga de cartero. Se puede pegar el
      de la pestaña equivocada, el de un archivo parecido, o el de uno al que el
      panel no tiene acceso — y recién se entera al final, con un error.

      La lista, además, contesta sola la pregunta que más se hace en esta
      pantalla: «¿lo compartí bien?». Si el archivo está en la lista, sí. Si no
      está, falta compartirlo. No hace falta probar y ver qué pasa.

    QUÉ ALCANZA A VER
      Solo lo que se le compartió a esta cuenta. No es el Drive de la empresa:
      es la bandeja del panel. Un archivo que nadie le compartió no aparece acá
      ni existe para el panel.
    """
    # trashed=false: un archivo en la papelera todavía se "ve" por la API, y
    # ofrecerlo para armar un reporte es ofrecer algo que alguien ya descartó.
    q = "(mimeType='%s' or mimeType='%s') and trashed=false" % (HOJA, DOCUMENTO)
    t = (buscar or "").strip()
    if t:
        # El apóstrofo cierra la comilla de la consulta: hay que escaparlo, o un
        # archivo llamado "Ventas de O'Brien" rompe la búsqueda entera.
        q += " and name contains '%s'" % _escapar(t)

    url = "%s?%s" % (DRIVE_API, urlencode({
        "q": q,
        "fields": "files(id,name,mimeType,modifiedTime,owners(displayName))",
        "orderBy": "modifiedTime desc",
        "pageSize": max(1, min(int(cuantos or 100), 200)),
        # Por si el archivo vive en una unidad compartida y no en "Mi unidad".
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "corpora": "allDrives",
    }))
    d = _pedir_api(url, timeout)

    # Google pagina. Sin seguir el nextPageToken, con muchos archivos
    # compartidos la lista se corta SIN AVISAR — y esa lista es justo la que
    # contesta "¿lo compartí bien?". Un archivo que falta por paginación se lee
    # como "no lo compartiste", que es una respuesta equivocada.
    archivos_crudos = list(d.get("files") or [])
    vueltas = 0
    while d.get("nextPageToken") and vueltas < 10:
        vueltas += 1
        d = _pedir_api(url + "&pageToken=" + quote(d["nextPageToken"], safe=""), timeout)
        archivos_crudos.extend(d.get("files") or [])

    salida = []
    for f in archivos_crudos:
        es_doc = f.get("mimeType") == DOCUMENTO
        duenos = [o.get("displayName") for o in (f.get("owners") or [])
                  if o.get("displayName")]
        fid = f.get("id") or ""            # `or` y no el default de get: Drive
        if not fid:                        # puede mandar id: null explicito
            continue
        salida.append({
            "id": fid,
            "nombre": f.get("name") or "(sin nombre)",
            "clase": "doc" if es_doc else "hoja",
            "que_es": "Documento" if es_doc else "Planilla",
            "cuando": _fecha_corta(f.get("modifiedTime", "")),
            "de": duenos[0] if duenos else "",
            "link": ("https://docs.google.com/document/d/%s/edit" if es_doc
                     else "https://docs.google.com/spreadsheets/d/%s/edit") % fid,
        })
    return salida


def _fecha_corta(iso):
    """2026-08-27T11:04:02.000Z -> 27/08/2026. Vacío si no se entiende.

    Se muestra la fecha y no "hace 3 días": una fecha se compara de un vistazo
    con la que uno se acuerda de haber tocado el archivo."""
    t = (iso or "")[:10]
    try:
        a, m, d = t.split("-")
    except ValueError:
        return ""
    # ⚠️ Que además sean números. Sin esto, "no-es-fecha" salía como
    # "fech/es/no": el docstring prometía vacío y devolvía basura con forma de
    # fecha, que es peor que no mostrar nada.
    if not (a.isdigit() and m.isdigit() and d.isdigit()):
        return ""
    if not (len(a) == 4 and 1 <= int(m) <= 12 and 1 <= int(d) <= 31):
        return ""
    return "%s/%s/%s" % (d, m, a)


def _texto_de(elementos):
    """El texto suelto de un párrafo de Google Docs.

    La API devuelve cada párrafo partido en pedacitos por formato: si una
    palabra está en negrita, es un pedazo aparte. Se pegan todos."""
    partes = []
    for e in elementos or []:
        t = ((e.get("textRun") or {}).get("content") or "")
        if t:
            partes.append(t)
    return "".join(partes)


def _tabla_de(tabla):
    """Una tabla de Google Docs como lista de filas de texto."""
    filas = []
    for fila in (tabla.get("tableRows") or []):
        celdas = []
        for celda in (fila.get("tableCells") or []):
            trozos = []
            for c in (celda.get("content") or []):
                p = c.get("paragraph")
                if p:
                    trozos.append(_texto_de(p.get("elements")))
            # Una celda puede tener varios párrafos; se pegan con un espacio y
            # se aplastan los saltos, porque abajo esto va a una tabla plana.
            celdas.append(" ".join(" ".join(trozos).split()))
        filas.append(celdas)
    return filas


def leer_documento(documento, timeout=30):
    """{titulo, texto, tablas} de un Google Doc.

    Las tablas se devuelven aparte y con la misma forma que una planilla (lista
    de filas), así una tabla de un documento puede alimentar un reporte igual
    que una hoja de cálculo."""
    did = id_de_documento(documento)
    d = _pedir_api("%s/%s" % (DOCS_API, quote(did, safe="")), timeout)
    lineas, tablas = [], []
    for el in ((d.get("body") or {}).get("content") or []):
        p = el.get("paragraph")
        if p:
            t = _texto_de(p.get("elements")).rstrip("\n")
            if t.strip():
                lineas.append(t)
        t = el.get("table")
        if t:
            filas = _tabla_de(t)
            if filas:
                tablas.append(_emparejar(filas))
    return {"titulo": d.get("title", ""), "texto": "\n".join(lineas),
            "tablas": tablas}
