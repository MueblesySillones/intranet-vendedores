# -*- coding: utf-8 -*-
"""Publicar y traer desde varias computadoras sin pisarse (v61, 14-sep-2026).

    python test_publicar_fusion.py        (exit 1 si algo falla)

Levanta el panel_server del REPO como SUCURSAL contra un GitHub FALSO y un
cerebro FALSO que viven en este mismo proceso. No toca el sitio, ni el panel
instalado, ni el estado real: todo corre en una carpeta temporal y el panel
recibe las direcciones falsas por su identidad (repo_api, repo_raw, repo_zip,
cerebro_url).

Los casos son los que pasan de verdad:
  1) una sucursal instalada con la copia VIEJA publica una publicacion nueva
     -> lo que otros publicaron despues sigue estando
  2) otra computadora publica mientras tanto -> las dos ediciones quedan
  3) no hay nada propio que publicar pero otros si -> la copia se pone al dia
     y NO se sube un commit vacio
  4) "Traer ultima version" con cambios sin publicar -> se conservan
  5) otra computadora sube una imagen a una galeria -> la galeria publicada
     la sigue teniendo
  6) GitHub no responde -> se publica igual y se avisa
  7) borrar dos publicaciones seguidas con la API de GitHub ATRASADA (el caso
     real del 15-sep: la API cachea 60 s y la primera borrada volvia a
     aparecer al borrar la segunda)
  8) traer la ultima version con el zip de GitHub atrasado
"""
import copy
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(AQUI, "..", "panel")
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
sys.path.insert(0, PANEL)
import fusion  # noqa: E402

fallas = []


def check(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  -> " + str(detalle)[:400]))
    if not cond:
        fallas.append(nombre)


def puerto_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ------------------------------------------------------------ GitHub falso
class RepoFalso(object):
    def __init__(self):
        self.commits = []            # [(sha, {rel: bytes})], el ultimo es la cabeza
        self.caido = False
        self.atrasada = False        # la API (y el zip por rama) contesta la cabeza ANTERIOR
        self.git_caido = False       # el protocolo de git no responde (queda la API)
        self.publicaciones = 0
        self.lock = threading.Lock()

    def commit(self, archivos):
        with self.lock:
            sha = ("%040x" % (len(self.commits) + 1))
            self.commits.append((sha, dict(archivos)))
            return sha

    def cabeza(self):
        return self.commits[-1]

    def texto(self, rel, sha=None):
        d = self.cabeza()[1] if sha is None else dict(self.commits)[sha]
        return d[rel].decode("utf-8")


REPO_F = RepoFalso()


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, code, cuerpo, tipo="application/octet-stream"):
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        u = urlparse(self.path)
        partes = [unquote(p) for p in u.path.split("/") if p]
        if REPO_F.caido and partes[:1] in (["api"], ["raw"]):
            return self._enviar(500, "caido")
        if partes[:3] == ["api", "commits", "main"]:
            if REPO_F.atrasada and len(REPO_F.commits) > 1:
                return self._enviar(200, REPO_F.commits[-2][0], "text/plain")
            return self._enviar(200, REPO_F.cabeza()[0], "text/plain")
        if partes[:2] == ["git", "info"] and REPO_F.git_caido:
            return self._enviar(500, "no")
        if partes[:2] == ["git", "info"]:
            # el protocolo de git: siempre al dia (no tiene cache)
            sha = REPO_F.cabeza()[0]
            linea = "%s refs/heads/main\n" % sha
            cuerpo = ("001e# service=git-upload-pack\n0000" + "%04x" % (len(linea) + 4) + linea + "0000")
            return self._enviar(200, cuerpo, "application/x-git-upload-pack-advertisement")
        if partes[:2] == ["api", "commits"]:
            lista = []
            previo = None
            for sha, arch in REPO_F.commits:           # solo los que tocan modulos.js
                if arch.get("modulos.js") != previo:
                    lista.append({"sha": sha})
                previo = arch.get("modulos.js")
            return self._enviar(200, json.dumps(list(reversed(lista))), "application/json")
        if partes[:1] == ["raw"] and len(partes) >= 4 and partes[2] == "intranet":
            sha, rel = partes[1], "/".join(partes[3:])
            arch = dict(REPO_F.commits).get(sha)
            if arch is None or rel not in arch:
                return self._enviar(404, "no")
            return self._enviar(200, arch[rel])
        if partes[:1] == ["zip"]:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                todos = {}
                for _sha, arch in REPO_F.commits:      # como el repo: los huerfanos quedan
                    todos.update(arch)
                cab = REPO_F.cabeza()
                if partes[1:2] and partes[1] != "main":            # zip por commit
                    cab = (partes[1], dict(REPO_F.commits)[partes[1]])
                elif REPO_F.atrasada and len(REPO_F.commits) > 1:   # zip por rama, atrasado
                    cab = REPO_F.commits[-2]
                todos.update(cab[1])
                for rel, b in todos.items():
                    z.writestr("repo-main/intranet/" + rel, b)
            return self._enviar(200, buf.getvalue(), "application/zip")
        return self._enviar(404, "no")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(n)
        if self.path.endswith("/publish"):
            d = json.loads(cuerpo.decode("utf-8"))
            arch = dict(REPO_F.cabeza()[1])
            import base64
            for a in d["archivos"]:
                rel = a["path"][len("intranet/"):]
                arch[rel] = (a["content"].encode("utf-8") if a["encoding"] == "utf-8"
                             else base64.b64decode(a["content"]))
            REPO_F.publicaciones += 1
            sha = REPO_F.commit(arch)
            return self._enviar(200, json.dumps({"ok": True, "commit": sha}), "application/json")
        return self._enviar(200, json.dumps({"ok": True}), "application/json")


# ------------------------------------------------------------ utilidades
def modulos_de(txt):
    return fusion.partes(txt)


def cartelera(p):
    return next(m for m in p["modulos"] if m["key"] == "cartelera")


def ids_cartelera(p):
    return [d["id"] for d in cartelera(p)["content"]["docs"]]


def texto_modulos(p):
    return ("window.MODULES = " + json.dumps(p["modulos"], ensure_ascii=False, indent=2) + ";\n"
            "window.AJUSTES = " + json.dumps(p["ajustes"], ensure_ascii=False) + ";\n"
            "window.TUTORIALES = " + json.dumps(p["tutoriales"], ensure_ascii=False, indent=2) + ";\n")


def api(base, ruta, datos=None, timeout=120):
    req = urllib.request.Request(base + ruta, method="POST" if datos is not None else "GET",
                                 data=json.dumps(datos).encode("utf-8") if datos is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    tmp = tempfile.mkdtemp(prefix="sandbox-fusion-")
    proc = None
    try:
        # ---- el repo publicado: la intranet real, recortada a lo que importa
        real = io.open(os.path.join(REPO, "intranet", "modulos.js"), encoding="utf-8").read()
        index = open(os.path.join(REPO, "intranet", "index.html"), "rb").read()
        p_real = modulos_de(real)
        # H0 = la version VIEJA: sin la ultima publicacion de la cartelera
        p_viejo = copy.deepcopy(p_real)
        doc_nuevo_central = cartelera(p_viejo)["content"]["docs"].pop(0)
        viejo_txt = texto_modulos(p_viejo)
        # galerias vacias de los dos lados: el sandbox no copia las imagenes (82 MB).
        # Con la galeria real publicada y ninguna imagen aca, la sucursal estaria
        # "borrando" todas, que es otro caso (y se propagaria, como corresponde).
        base_arch = {"index.html": index, "galerias.js": b"window.GALLERIES = {};\n"}
        REPO_F.commit(dict(base_arch, **{"modulos.js": viejo_txt.encode("utf-8")}))
        REPO_F.commit(dict(base_arch, **{"modulos.js": real.encode("utf-8")}))

        # ---- la sucursal: instalada con la copia VIEJA, sin base anotada
        proy = os.path.join(tmp, "proyecto")
        intr = os.path.join(proy, "intranet")
        os.makedirs(os.path.join(proy, "herramientas"))
        os.makedirs(intr)
        open(os.path.join(intr, "index.html"), "wb").write(index)
        open(os.path.join(intr, "modulos.js"), "w", encoding="utf-8").write(viejo_txt)
        open(os.path.join(intr, "galerias.js"), "w", encoding="utf-8").write("window.GALLERIES = {};\n")
        estado = os.path.join(tmp, "estado")
        os.makedirs(estado)

        pf = puerto_libre()
        srv = ThreadingHTTPServer(("127.0.0.1", pf), Manejador)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        falso = "http://127.0.0.1:%d" % pf
        json.dump({"rol": "colaborador", "usuario": "Sucursal prueba", "publish_token": "x",
                   "cerebro_url": falso + "/cerebro", "repo_api": falso + "/api",
                   "repo_raw": falso + "/raw", "repo_zip": falso + "/zip/main",
                   "repo_git": falso + "/git",
                   "web_publica": falso + "/web", "central_url": ""},
                  open(os.path.join(estado, "identity.json"), "w", encoding="utf-8"))

        pp = puerto_libre()
        env = dict(os.environ, MYS_PROYECTO=proy, MYS_PANEL_STATE=estado,
                   MYS_PANEL_PORT=str(pp), BROWSER="cmd.exe /c echo", PYTHONIOENCODING="utf-8")
        log = open(os.path.join(tmp, "panel.log"), "w", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, os.path.join(PANEL, "panel_server.py")],
                                cwd=PANEL, env=env, stdout=log, stderr=subprocess.STDOUT)
        base = "http://127.0.0.1:%d" % pp
        for _ in range(60):
            try:
                cfg = api(base, "/api/config", timeout=3)
                break
            except Exception:  # noqa
                time.sleep(0.5)
        else:
            raise SystemExit("el panel no arranco; ver " + log.name)
        check("el panel arranca como sucursal", cfg.get("es_central") is False, cfg)

        print("1) sucursal con copia vieja publica una publicacion nueva")
        d = api(base, "/api/modulos")
        mods = d["modulos"]
        c = next(m for m in mods if m["key"] == "cartelera")
        nueva = copy.deepcopy(c["content"]["docs"][0])
        nueva.update({"id": "zzsucursal1", "titulo": "Desde la sucursal"})
        c["content"]["docs"].insert(0, nueva)
        r = api(base, "/api/modulos", {"modulos": mods, "ajustes": d["ajustes"]})
        check("guardar la publicacion", r.get("ok"), r)
        antes = REPO_F.publicaciones
        r = api(base, "/api/publicar", {})
        check("publica", r.get("ok") and not r.get("nada"), r.get("log"))
        pub = modulos_de(REPO_F.texto("modulos.js"))
        ids = ids_cartelera(pub)
        check("la publicacion de la central que la sucursal no tenia SIGUE publicada",
              doc_nuevo_central["id"] in ids, ids)
        check("la publicacion de la sucursal quedo publicada", "zzsucursal1" in ids, ids)
        check("los demas modulos quedaron identicos a lo publicado",
              [m for m in pub["modulos"] if m["key"] != "cartelera"] ==
              [m for m in p_real["modulos"] if m["key"] != "cartelera"])
        check("la respuesta avisa lo que se sumo", bool((r.get("fusion") or {}).get("traidos")), r.get("fusion"))
        check("un solo commit", REPO_F.publicaciones == antes + 1, REPO_F.publicaciones - antes)
        check("quedo anotada la base", os.path.isfile(os.path.join(estado, "base_publicada", "modulos.js")))
        local = modulos_de(open(os.path.join(intr, "modulos.js"), encoding="utf-8").read())
        check("la copia local tambien quedo al dia", fusion.iguales(local, pub))

        print("2) otra computadora publica mientras tanto")
        otra = modulos_de(REPO_F.texto("modulos.js"))
        m_otro = next(m for m in otra["modulos"] if m["key"] == "whatsapp")
        m_otro["title"] = "WhatsApp (editado por otra PC)"
        REPO_F.commit(dict(REPO_F.cabeza()[1], **{"modulos.js": texto_modulos(otra).encode("utf-8")}))
        d = api(base, "/api/modulos")
        mods = d["modulos"]
        m_mio = next(m for m in mods if m["key"] == "manual")
        m_mio["desc"] = "Editado en la sucursal"
        api(base, "/api/modulos", {"modulos": mods, "ajustes": d["ajustes"]})
        r = api(base, "/api/publicar", {})
        pub = modulos_de(REPO_F.texto("modulos.js"))
        check("queda la edicion de la otra computadora",
              next(m for m in pub["modulos"] if m["key"] == "whatsapp")["title"] == "WhatsApp (editado por otra PC)")
        check("y la de esta", next(m for m in pub["modulos"] if m["key"] == "manual")["desc"] == "Editado en la sucursal")
        check("sin choques", not (r.get("fusion") or {}).get("choques"), r.get("fusion"))

        print("3) nada propio que publicar, pero otros si")
        otra = modulos_de(REPO_F.texto("modulos.js"))
        cartelera(otra)["content"]["docs"].insert(0, dict(nueva, id="zzotra3", titulo="De otra PC"))
        REPO_F.commit(dict(REPO_F.cabeza()[1], **{"modulos.js": texto_modulos(otra).encode("utf-8")}))
        antes = REPO_F.publicaciones
        r = api(base, "/api/publicar", {})
        check("dice que no habia nada para publicar", r.get("ok") and r.get("nada"), r.get("log"))
        check("no manda un commit vacio", REPO_F.publicaciones == antes)
        local = modulos_de(open(os.path.join(intr, "modulos.js"), encoding="utf-8").read())
        check("pero la copia local se puso al dia", "zzotra3" in ids_cartelera(local))

        print("4) traer la ultima version con cambios sin publicar")
        otra = modulos_de(REPO_F.texto("modulos.js"))
        cartelera(otra)["content"]["docs"].insert(0, dict(nueva, id="zzotra4", titulo="Otra mas"))
        REPO_F.commit(dict(REPO_F.cabeza()[1], **{"modulos.js": texto_modulos(otra).encode("utf-8")}))
        d = api(base, "/api/modulos")
        mods = d["modulos"]
        next(m for m in mods if m["key"] == "cartelera")["content"]["docs"].insert(
            0, dict(nueva, id="zzsinpublicar", titulo="Sin publicar"))
        api(base, "/api/modulos", {"modulos": mods, "ajustes": d["ajustes"]})
        img_local = os.path.join(intr, "assets", "_modulos", "subida-aca.png")
        os.makedirs(os.path.dirname(img_local), exist_ok=True)
        open(img_local, "wb").write(b"\x89PNG local")
        antes = REPO_F.publicaciones
        j = api(base, "/api/traer", {})
        for _ in range(120):
            e = api(base, "/api/job?id=" + j["job"])
            if e.get("estado") in ("listo", "error"):
                break
            time.sleep(0.3)
        check("traer termina bien", e.get("estado") == "listo", e)
        local = modulos_de(open(os.path.join(intr, "modulos.js"), encoding="utf-8").read())
        ids = ids_cartelera(local)
        check("llego lo de la otra computadora", "zzotra4" in ids, ids)
        check("se conservo lo que no estaba publicado", "zzsinpublicar" in ids, ids)
        check("se conservo la imagen subida aca", os.path.isfile(img_local))
        check("traer no publico nada", REPO_F.publicaciones == antes)
        r = api(base, "/api/publicar", {})
        ids = ids_cartelera(modulos_de(REPO_F.texto("modulos.js")))
        check("despues se publica y quedan las dos", "zzsinpublicar" in ids and "zzotra4" in ids, ids)

        print("5) otra computadora sube una imagen a una galeria")
        gal = json.loads(REPO_F.texto("galerias.js").split("=", 1)[1].rstrip().rstrip(";"))
        gal.setdefault("promos_bancarias", []).append(
            {"file": "assets/promos_bancarias/otra-pc.png", "title": "Otra pc", "download": "otra-pc.png"})
        REPO_F.commit(dict(REPO_F.cabeza()[1], **{
            "galerias.js": ("window.GALLERIES = " + json.dumps(gal, ensure_ascii=False, indent=2) + ";\n").encode("utf-8"),
            "assets/promos_bancarias/otra-pc.png": b"\x89PNG otra"}))
        d = api(base, "/api/modulos")
        mods = d["modulos"]
        next(m for m in mods if m["key"] == "manual")["desc"] = "Otra edicion"
        api(base, "/api/modulos", {"modulos": mods, "ajustes": d["ajustes"]})
        r = api(base, "/api/publicar", {})
        check("publica", r.get("ok"), r.get("log"))
        check("la imagen de la otra computadora se bajo aca",
              os.path.isfile(os.path.join(intr, "assets", "promos_bancarias", "otra-pc.png")))
        check("y la galeria publicada la sigue listando",
              "assets/promos_bancarias/otra-pc.png" in fusion.galerias(REPO_F.texto("galerias.js")))

        print("6) GitHub no responde")
        REPO_F.caido = True
        d = api(base, "/api/modulos")
        mods = d["modulos"]
        next(m for m in mods if m["key"] == "manual")["desc"] = "Sin GitHub"
        api(base, "/api/modulos", {"modulos": mods, "ajustes": d["ajustes"]})
        r = api(base, "/api/publicar", {})
        REPO_F.caido = False
        check("publica igual", r.get("ok") and not r.get("nada"), r.get("log"))
        check("y lo avisa", bool((r.get("fusion") or {}).get("aviso")), r.get("fusion"))

        print("7) borrar dos publicaciones seguidas con GitHub atrasado")
        def borrar_doc(doc_id):
            d = api(base, "/api/modulos")
            mods = d["modulos"]
            c = next(m for m in mods if m["key"] == "cartelera")["content"]
            doc = next(x for x in c["docs"] if x["id"] == doc_id)
            c["docs"] = [x for x in c["docs"] if x["id"] != doc_id]
            c.setdefault("papelera", []).insert(0, dict(doc, borradoEl="2026-09-15"))
            api(base, "/api/modulos", {"modulos": mods, "ajustes": d["ajustes"]})
            return api(base, "/api/publicar", {})
        REPO_F.atrasada = True
        r1 = borrar_doc("zzotra3")
        r2 = borrar_doc("zzotra4")
        pub = modulos_de(REPO_F.texto("modulos.js"))
        ids = ids_cartelera(pub)
        pap = [x["id"] for x in cartelera(pub)["content"].get("papelera") or []]
        check("la primera borrada NO vuelve a aparecer", "zzotra3" not in ids, (ids, r2.get("fusion")))
        check("la segunda tampoco", "zzotra4" not in ids, ids)
        check("las dos quedan en la papelera", "zzotra3" in pap and "zzotra4" in pap, pap)
        local = modulos_de(open(os.path.join(intr, "modulos.js"), encoding="utf-8").read())
        check("y la copia local igual", "zzotra3" not in ids_cartelera(local), ids_cartelera(local))
        check("sin avisar cosas traidas que no existen", not (r2.get("fusion") or {}).get("traidos"),
              r2.get("fusion"))

        print("8) traer la ultima version con GitHub atrasado")
        j = api(base, "/api/traer", {})
        for _ in range(120):
            e = api(base, "/api/job?id=" + j["job"])
            if e.get("estado") in ("listo", "error"):
                break
            time.sleep(0.3)
        local = modulos_de(open(os.path.join(intr, "modulos.js"), encoding="utf-8").read())
        check("traer no resucita lo borrado", "zzotra4" not in ids_cartelera(local), ids_cartelera(local))

        print("9) lo mismo pero SIN el protocolo de git: solo la API atrasada")
        REPO_F.git_caido = True
        # dos publicaciones nuevas para borrar
        d = api(base, "/api/modulos")
        mods = d["modulos"]
        cc = next(m for m in mods if m["key"] == "cartelera")["content"]
        cc["docs"].insert(0, dict(nueva, id="zzborrar9a", titulo="Borrar 9a"))
        cc["docs"].insert(0, dict(nueva, id="zzborrar9b", titulo="Borrar 9b"))
        api(base, "/api/modulos", {"modulos": mods, "ajustes": d["ajustes"]})
        REPO_F.atrasada = False
        api(base, "/api/publicar", {})
        # un commit de otra cosa (no toca modulos.js): asi la API atrasada, que
        # contesta el ANTERIOR, muestra justo la version con las dos publicaciones
        REPO_F.commit(dict(REPO_F.cabeza()[1], **{"index.html": b"<!-- otro commit -->"}))
        REPO_F.atrasada = True
        r9a = borrar_doc("zzborrar9a")          # ve la version con 9a y 9b = su base: bien
        r9 = borrar_doc("zzborrar9b")           # ve la version ANTERIOR, donde 9a vivia
        ids = ids_cartelera(modulos_de(REPO_F.texto("modulos.js")))
        check("sin git tampoco resucita lo borrado",
              "zzborrar9a" not in ids and "zzborrar9b" not in ids, (ids, r9.get("fusion")))
        REPO_F.git_caido = False
        REPO_F.atrasada = False

        print("restaurar una version vieja")
        r = api(base, "/api/restaurar", {"sha": REPO_F.commits[1][0]})
        check("se puede (antes toda version daba 'dañada')", r.get("ok"), r)
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(10)
            except Exception:  # noqa
                proc.kill()
        time.sleep(0.5)
        shutil.rmtree(tmp, ignore_errors=True)
    print("")
    if fallas:
        print("FALLARON %d: %s" % (len(fallas), "; ".join(fallas)))
        sys.exit(1)
    print("todo ok")


if __name__ == "__main__":
    main()
