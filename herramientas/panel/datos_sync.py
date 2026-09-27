# -*- coding: utf-8 -*-
"""
DATOS COMPARTIDOS ENTRE TODAS LAS COMPUTADORAS (26-sep-2026)
=============================================================

El pedido: «cuando creo un reporte en la central, en las otras computadoras no
se ve. Que todas tengan toda esa información, que ninguna tenga que volver a
cargarla, y que cuando se actualiza el Excel la información esté actualizada».

Hasta la v94 la sección Datos era de UNA computadora: `datos.json` (los
reportes), `vendedores.json` (a qué sucursal va cada vendedor) y los Excel
conectados vivían en la carpeta de estado de esa PC y no viajaban a ningún
lado. No podían ir por donde viaja el resto del contenido —el repo es público
y esto tiene nombres y números del equipo—, así que van al CEREBRO, a su
almacenamiento privado (`/datos`), con la misma clave con la que se publica.

QUÉ SE COMPARTE
  · los reportes enteros (planilla, informes, foco, lo publicado)
  · el mapa de vendedores → sucursal
  · los Excel/CSV conectados desde una PC: se suben por su huella, y si el
    archivo cambia en la PC que lo conectó se vuelve a subir solo. Las demás
    leen su copia bajada.
QUÉ NO
  · las credenciales de Google (`google` en datos.json, google_cuenta.json):
    el cerebro se abre con la clave del equipo, que viaja adentro del
    instalador, y una credencial ahí la podría sacar cualquiera que lo baje.
    Las planillas de Google por link no las necesitan: cada PC las lee sola.

CÓMO NO SE PISAN
  El cerebro guarda un documento con VERSIÓN. Cada PC recuerda de qué versión
  partió (la «base»). Si alguien guardó en el medio, el cerebro contesta 409 y
  se combina reporte por reporte contra la base: lo que cambió de un solo lado
  gana; si cambió de los dos, gana el que está guardando ahora. Borrar también
  viaja (un reporte que estaba en la base y ya no está, se borró).
"""
import hashlib
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request

ARCHIVO_ESTADO = "datos_sync.json"
CARPETA_COPIAS = "datos_compartidos"
TIPOS_ARCHIVO = ("csv", "xlsx")

# Lo toma también panel_server alrededor de cada cambio de la sección Datos:
# sin esto, la sincronización podía escribir datos.json entre el «leer» y el
# «guardar» de una pantalla, y uno de los dos cambios se perdía.
CANDADO = threading.RLock()
_EN_CURSO = threading.Lock()


class Sincronizador(object):
    def __init__(self, state_dir, url_fn, token_fn, habilitado_fn, datos_api, mapa_ruta_fn):
        self.state_dir = state_dir
        self.url_fn = url_fn
        self.token_fn = token_fn
        self.habilitado_fn = habilitado_fn
        self.datos_api = datos_api
        self.mapa_ruta_fn = mapa_ruta_fn
        self.ultimo = {"ok": None, "ts": 0, "error": "", "traidos": 0, "intento": 0}
        self._pendiente = None

    # ───────────── el estado propio de esta PC ─────────────
    def _ruta_estado(self):
        return os.path.join(self.state_dir, ARCHIVO_ESTADO)

    def _leer_estado(self):
        try:
            with io.open(self._ruta_estado(), encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _guardar_estado(self, d):
        _escribir_json(self._ruta_estado(), d)

    # ───────────── hablar con el cerebro ─────────────
    def _pedir(self, metodo, ruta, datos=None, tipo="application/json", timeout=30):
        req = urllib.request.Request(self.url_fn() + ruta, data=datos, method=metodo)
        req.add_header("Authorization", "Bearer " + (self.token_fn() or ""))
        req.add_header("User-Agent", "PanelMyS/1.0")   # el de Python lo bloquea Cloudflare (1010)
        if datos is not None:
            req.add_header("Content-Type", tipo)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    def _doc_remoto(self, timeout):
        r = json.loads(self._pedir("GET", "/datos", timeout=timeout).decode("utf-8"))
        return r.get("doc") or {"version": 0, "reportes": [], "vendedores": {}}

    # ───────────── lo de esta PC ─────────────
    def _mapa_local(self):
        try:
            with io.open(self.mapa_ruta_fn(self.state_dir), encoding="utf-8-sig") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _doc_local(self):
        cfg = self.datos_api.cargar(self.state_dir)
        return {"reportes": list(cfg.get("reportes") or []), "vendedores": self._mapa_local()}

    def _escribir_local(self, doc):
        """Deja esta PC igual al documento. Se toca solo lo compartido: las
        credenciales de Google que haya en datos.json quedan como estaban."""
        with CANDADO:
            cfg = self.datos_api.cargar(self.state_dir)
            if _huella(cfg.get("reportes") or []) != _huella(doc.get("reportes") or []):
                cfg["reportes"] = doc.get("reportes") or []
                self.datos_api.guardar(self.state_dir, cfg)
            if _huella(self._mapa_local()) != _huella(doc.get("vendedores") or {}):
                _escribir_json(self.mapa_ruta_fn(self.state_dir), doc.get("vendedores") or {})

    # ───────────── los Excel ─────────────
    def _subir_archivos(self, est, timeout):
        """Los Excel/CSV que ESTA PC tiene en su disco: si cambiaron desde la
        última vez (o nunca se subieron), se suben y el reporte anota la huella
        nueva. Así «actualicé el Excel» llega a todas."""
        huellas = est.setdefault("huellas", {})
        with CANDADO:
            cfg = self.datos_api.cargar(self.state_dir)
        cambios = []
        for r in cfg.get("reportes") or []:
            f = r.get("fuente") or {}
            ruta = f.get("ruta") or ""
            if f.get("tipo") not in TIPOS_ARCHIVO or not ruta or not os.path.isfile(ruta):
                continue
            try:
                st = os.stat(ruta)
            except OSError:
                continue
            marca = [st.st_size, int(st.st_mtime)]
            h = huellas.get(ruta)
            if h and h[:2] == marca:
                sha = h[2]
            else:
                sha = _sha_de(ruta)
                if not sha:
                    continue                    # abierto en Excel, sin permiso: la próxima
                huellas[ruta] = marca + [sha]
            comp = f.get("compartido") or {}
            if comp.get("sha") == sha:
                continue
            with open(ruta, "rb") as fh:
                datos = fh.read()
            self._pedir("PUT", "/datos/archivo/" + sha, datos, "application/octet-stream",
                        timeout=max(timeout, 120))
            _guardar_copia(self.state_dir, sha, _ext(ruta), datos)
            cambios.append((r.get("id"), {"sha": sha, "nombre": os.path.basename(ruta),
                                          "size": len(datos), "ts": int(time.time())}))
        if cambios:
            with CANDADO:
                cfg = self.datos_api.cargar(self.state_dir)
                for rid, comp in cambios:
                    for r in cfg.get("reportes") or []:
                        if r.get("id") == rid:
                            r.setdefault("fuente", {})["compartido"] = comp
                self.datos_api.guardar(self.state_dir, cfg)

    def _bajar_archivos(self, doc, timeout):
        for r in doc.get("reportes") or []:
            f = r.get("fuente") or {}
            comp = f.get("compartido") or {}
            sha = comp.get("sha") or ""
            if f.get("tipo") not in TIPOS_ARCHIVO or len(sha) != 64:
                continue
            # la copia se guarda aunque esta PC tenga el original: si el
            # archivo se mueve o se renombra, el reporte sigue leyendose
            if os.path.isfile(ruta_copia(self.state_dir, sha, _ext(comp.get("nombre") or f.get("ruta") or ""))):
                continue
            datos = self._pedir("GET", "/datos/archivo/" + sha, timeout=max(timeout, 120))
            if hashlib.sha256(datos).hexdigest() != sha:
                raise ValueError("una planilla llegó dañada; se reintenta después")
            _guardar_copia(self.state_dir, sha, _ext(comp.get("nombre") or f.get("ruta") or ""), datos)

    # ───────────── la vuelta completa ─────────────
    def sincronizar(self, timeout=30):
        """Sube lo de acá, baja lo de las otras, y las deja iguales.
        Devuelve {ok, traidos, error}. Nunca levanta: sin internet, el panel
        sigue andando con lo que tiene."""
        if not self.habilitado_fn():
            return {"ok": False, "error": "sin cerebro", "apagado": True}
        if not _EN_CURSO.acquire(blocking=False):
            return {"ok": True, "en_curso": True}
        try:
            self.ultimo["intento"] = time.time()
            r = self._vuelta(timeout)
            self.ultimo.update({"ok": True, "ts": time.time(), "error": "",
                                "traidos": r.get("traidos", 0)})
            return r
        except Exception as e:                 # noqa: se informa, no se cae
            self.ultimo.update({"ok": False, "error": _legible(e)})
            return {"ok": False, "error": _legible(e)}
        finally:
            _EN_CURSO.release()

    def _vuelta(self, timeout):
        est = self._leer_estado()
        self._subir_archivos(est, timeout)
        self._guardar_estado(est)
        for _intento in range(4):
            remoto = self._doc_remoto(timeout)
            rver = int(remoto.get("version") or 0)
            local = self._doc_local()
            base = est.get("base") if est.get("version") else None
            if base is not None and rver == est.get("version") and _igual(local, base):
                self._bajar_archivos(remoto, timeout)
                return {"ok": True, "traidos": 0}
            nuevo = combinar(base, local, remoto)
            traidos = 0 if _igual(nuevo, local) else 1
            if not _igual(nuevo, remoto):
                cuerpo = json.dumps({"base": rver, "reportes": nuevo["reportes"],
                                     "vendedores": nuevo["vendedores"]},
                                    ensure_ascii=False).encode("utf-8")
                try:
                    resp = json.loads(self._pedir("POST", "/datos", cuerpo, timeout=timeout).decode("utf-8"))
                except urllib.error.HTTPError as e:
                    if e.code == 409:
                        continue                # alguien guardó en el medio: se combina de nuevo
                    raise
                rver = int((resp.get("doc") or {}).get("version") or rver + 1)
            self._escribir_local(nuevo)
            est["version"] = rver
            est["base"] = nuevo
            self._guardar_estado(est)
            self._bajar_archivos(nuevo, timeout)
            _barrer_copias(self.state_dir, nuevo)
            return {"ok": True, "traidos": traidos}
        raise ValueError("otras computadoras están guardando al mismo tiempo; se reintenta solo")

    def pedir_pronto(self, espera=2.0):
        """Después de un cambio: sincroniza en un ratito, en segundo plano.
        Varios cambios seguidos se juntan en una sola vuelta."""
        if self._pendiente is not None:
            self._pendiente.cancel()
        t = threading.Timer(espera, self.sincronizar)
        t.daemon = True
        self._pendiente = t
        t.start()

    def arrancar_ciclo(self, cada=120):
        def ciclo():
            time.sleep(5)
            while True:
                self.sincronizar()
                time.sleep(cada)
        threading.Thread(target=ciclo, daemon=True, name="datos-sync").start()


# ───────────── combinar ─────────────
def combinar(base, local, remoto):
    """Tres vías, reporte por reporte (por id) y vendedor por vendedor.
    Sin base (la primera vez de una PC): se juntan los dos lados."""
    b_rep = _por_id((base or {}).get("reportes")) if base is not None else None
    l_rep = _por_id(local.get("reportes"))
    r_rep = _por_id(remoto.get("reportes"))
    orden = [k for k in r_rep] + [k for k in l_rep if k not in r_rep]
    reportes = []
    for k in orden:
        v = _tres(None if b_rep is None else b_rep.get(k), l_rep.get(k), r_rep.get(k), b_rep is None)
        if v is not None:
            reportes.append(v)
    b_v = (base or {}).get("vendedores") if base is not None else None
    l_v = local.get("vendedores") or {}
    r_v = remoto.get("vendedores") or {}
    vendedores = {}
    for k in list(r_v) + [k for k in l_v if k not in r_v]:
        v = _tres(None if b_v is None else b_v.get(k), l_v.get(k), r_v.get(k), b_v is None)
        if v is not None:
            vendedores[k] = v
    return {"reportes": reportes, "vendedores": vendedores}


def _tres(b, l, r, sin_base):
    if _huella(l) == _huella(r):
        return l
    if sin_base:
        return l if l is not None else r       # primera vez: nada se borra, se junta
    if _huella(l) == _huella(b):
        return r                                # solo cambió del otro lado
    if _huella(r) == _huella(b):
        return l                                # solo cambió acá
    return l if l is not None else r           # los dos: gana el que guarda (y no se pierde)


def _por_id(lista):
    out = {}
    for r in lista or []:
        if isinstance(r, dict) and r.get("id"):
            out[r["id"]] = r
    return out


def _igual(a, b):
    return (_huella(a.get("reportes") or []) == _huella(b.get("reportes") or [])
            and _huella(a.get("vendedores") or {}) == _huella(b.get("vendedores") or {}))


def _huella(x):
    return hashlib.sha1(json.dumps(x, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ───────────── archivos ─────────────
def _ext(nombre):
    e = os.path.splitext(str(nombre or ""))[1].lower()
    return e if e in (".csv", ".xlsx", ".xlsm", ".xls") else ".xlsx"


def ruta_copia(state_dir, sha, ext):
    return os.path.join(state_dir, CARPETA_COPIAS, sha + ext)


def fuente_para_leer(state_dir, fuente):
    """Si esta PC no tiene el Excel original pero sí la copia compartida, la
    fuente apunta a la copia. Lo usa datos_api antes de leer."""
    f = fuente or {}
    comp = f.get("compartido") or {}
    if f.get("tipo") not in TIPOS_ARCHIVO or not comp.get("sha"):
        return f
    if f.get("ruta") and os.path.isfile(f["ruta"]):
        return f
    copia = ruta_copia(state_dir, comp["sha"], _ext(comp.get("nombre") or f.get("ruta") or ""))
    if os.path.isfile(copia):
        g = dict(f)
        g["ruta"] = copia
        return g
    return f


def _guardar_copia(state_dir, sha, ext, datos):
    d = os.path.join(state_dir, CARPETA_COPIAS)
    os.makedirs(d, exist_ok=True)
    destino = os.path.join(d, sha + ext)
    tmp = destino + ".tmp"
    with open(tmp, "wb") as f:
        f.write(datos)
    os.replace(tmp, destino)


def _barrer_copias(state_dir, doc):
    """Las copias que ya no usa ningún reporte se van."""
    d = os.path.join(state_dir, CARPETA_COPIAS)
    if not os.path.isdir(d):
        return
    usadas = set()
    for r in doc.get("reportes") or []:
        sha = ((r.get("fuente") or {}).get("compartido") or {}).get("sha")
        if sha:
            usadas.add(sha)
    for n in os.listdir(d):
        if os.path.splitext(n)[0] in usadas:
            continue
        try:
            os.remove(os.path.join(d, n))
        except OSError:
            pass


def _sha_de(ruta):
    h = hashlib.sha256()
    try:
        with open(ruta, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
    except OSError:
        return ""
    return h.hexdigest()


def _escribir_json(ruta, d):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def _legible(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            return "el cerebro contestó %d: %s" % (e.code, json.loads(e.read().decode("utf-8")).get("error", ""))
        except Exception:                      # noqa
            return "el cerebro contestó %d" % e.code
    if isinstance(e, urllib.error.URLError):
        return "sin conexión con el cerebro"
    return str(e) or e.__class__.__name__
