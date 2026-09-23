# -*- coding: utf-8 -*-
"""Nadie tiene que cargar un codigo de publicacion (v63, 15-sep-2026).

    python test_clave_equipo.py        (exit 1 si algo falla)

Regla del dueno: «cada usuario con el instalador instalado ya debe poder
publicar sin ningun problema». Corre una COPIA del panel en una carpeta
temporal (guardar la clave escribe panel_config.json al lado del programa, y
eso no puede caer en la carpeta del codigo) contra un cerebro FALSO que solo
acepta la clave del equipo. Casos:
  1) sucursal SIN clave            -> arranca con la del equipo y publica
  2) sucursal con una clave VIEJA  -> el cerebro la rechaza, el panel pasa solo
                                      a la del equipo, publica y la guarda
  3) el panel trae sus certificados (certifi) ademas de los de Windows
"""
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(AQUI, "..", "panel")
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
CLAVE = "CLAVE-EQUIPO-DE-PRUEBA"
fallas = []
RECIBIDAS = []


def check(nombre, cond, detalle=""):
    print(("  ok    " if cond else "  FALLA ") + nombre + ("" if cond else "  -> " + str(detalle)[:300]))
    if not cond:
        fallas.append(nombre)


def puerto_libre():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


class Cerebro(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, d):
        b = json.dumps(d).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._json(500, {"ok": False})           # "GitHub" caido: se publica sin combinar

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        clave = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        RECIBIDAS.append(clave)
        if clave != CLAVE:
            return self._json(401, {"ok": False, "error": "token invalido"})
        return self._json(200, {"ok": True, "commit": "abc12345"})


def api(base, ruta, datos=None):
    req = urllib.request.Request(base + ruta, method="POST" if datos is not None else "GET",
                                 data=json.dumps(datos).encode("utf-8") if datos is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def correr(tmp, nombre, clave_local, falso):
    prog = os.path.join(tmp, nombre, "programa")
    os.makedirs(prog)
    for f in ("panel_server.py", "fusion.py", "datos_api.py", "receptor_server.py", "originales.json"):
        if os.path.exists(os.path.join(PANEL, f)):
            shutil.copy2(os.path.join(PANEL, f), prog)
    shutil.copytree(os.path.join(PANEL, "datos"), os.path.join(prog, "datos"),
                    ignore=shutil.ignore_patterns("__pycache__", "test_*"))
    shutil.copytree(os.path.join(PANEL, "web3"), os.path.join(prog, "web3"))
    # lo que publicar_web3.py genera antes de compilar
    open(os.path.join(prog, "clave_equipo.py"), "w", encoding="utf-8").write("CLAVE = %r\n" % CLAVE)
    json.dump({"rol": "colaborador", "usuario": nombre, "publish_token": clave_local,
               "cerebro_url": falso, "repo_api": falso, "repo_raw": falso, "repo_zip": "",
               "web_publica": falso, "central_url": ""},
              open(os.path.join(prog, "panel_config.json"), "w", encoding="utf-8"))
    proy = os.path.join(tmp, nombre, "proyecto")
    os.makedirs(os.path.join(proy, "intranet"))
    os.makedirs(os.path.join(proy, "herramientas"))
    for f in ("index.html", "modulos.js", "galerias.js"):
        shutil.copy2(os.path.join(REPO, "intranet", f), os.path.join(proy, "intranet", f))
    estado = os.path.join(tmp, nombre, "estado")
    os.makedirs(estado)
    pp = puerto_libre()
    env = dict(os.environ, MYS_PROYECTO=proy, MYS_PANEL_STATE=estado, MYS_PANEL_PORT=str(pp),
               BROWSER="none")
    proc = subprocess.Popen([sys.executable, os.path.join(prog, "panel_server.py")], cwd=prog,
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % pp
    for _ in range(60):
        try:
            api(base, "/api/config")
            return proc, base, prog
        except Exception:  # noqa
            time.sleep(0.5)
    proc.kill()
    raise SystemExit("no arranco el panel de prueba")


def main():
    tmp = tempfile.mkdtemp(prefix="sandbox-clave-")
    procs = []
    try:
        pf = puerto_libre()
        srv = ThreadingHTTPServer(("127.0.0.1", pf), Cerebro)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        falso = "http://127.0.0.1:%d" % pf

        print("1) sucursal sin clave")
        p1, b1, _ = correr(tmp, "sin-clave", "", falso)
        procs.append(p1)
        cfg = api(b1, "/api/config")
        check("arranca con clave", cfg.get("tiene_token") and cfg.get("clave_equipo"), cfg)
        # un cambio para que haya algo que subir
        d = api(b1, "/api/modulos")
        d["modulos"][0]["desc"] = "cambio de prueba"
        api(b1, "/api/modulos", {"modulos": d["modulos"], "ajustes": d["ajustes"]})
        RECIBIDAS.clear()
        r = api(b1, "/api/publicar", {})
        check("publica sin pedir nada", r.get("ok") and not r.get("falta_token"), r.get("log"))
        check("con la clave del equipo", RECIBIDAS and all(c == CLAVE for c in RECIBIDAS), RECIBIDAS)
        check("trae sus propios certificados", cfg.get("certificados") == "windows+certifi", cfg.get("certificados"))

        print("2) sucursal con una clave vieja que el cerebro rechaza")
        p2, b2, prog2 = correr(tmp, "clave-vieja", "vieja123", falso)
        procs.append(p2)
        d = api(b2, "/api/modulos")
        d["modulos"][0]["desc"] = "otro cambio"
        api(b2, "/api/modulos", {"modulos": d["modulos"], "ajustes": d["ajustes"]})
        RECIBIDAS.clear()
        r = api(b2, "/api/publicar", {})
        check("publica igual, sin pedir codigo", r.get("ok") and not r.get("falta_token"), r)
        check("probo la vieja y paso sola a la del equipo",
              RECIBIDAS[:1] == ["vieja123"] and CLAVE in RECIBIDAS, RECIBIDAS)
        guardada = json.load(open(os.path.join(prog2, "panel_config.json"), encoding="utf-8"))
        check("y quedo guardada para la proxima", guardada.get("publish_token") == CLAVE, guardada)
    finally:
        for pr in procs:
            pr.terminate()
            try:
                pr.wait(10)
            except Exception:  # noqa
                pr.kill()
        time.sleep(0.5)
        shutil.rmtree(tmp, ignore_errors=True)
    print("")
    if fallas:
        print("FALLARON %d: %s" % (len(fallas), "; ".join(fallas)))
        sys.exit(1)
    print("todo ok")


if __name__ == "__main__":
    main()
