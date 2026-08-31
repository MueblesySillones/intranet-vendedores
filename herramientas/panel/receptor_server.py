# -*- coding: utf-8 -*-
"""
Receptor de propuestas (rol CENTRAL) - escucha en la RED LOCAL
==============================================================
Corre en 2o plano en la computadora central (la unica con git + credenciales).
NO publica ni toca git. Solo:

  1) GET  /snapshot  -> zip con TODO intranet/ (para que los colaboradores
                        "traigan la ultima version" y editen sobre ella).
  2) POST /inbox     -> recibe una propuesta de cambios (zip + metadatos) y la
                        guarda en la carpeta 'aprobaciones/' para que la revises
                        desde el panel (Aprobar / Rechazar).
  3) GET  /ping      -> identificacion (para que el colaborador confirme conexion).
  4) GET  /          -> pagina simple "receptor activo".

Se ejecuta como:  PanelMyS.exe --receptor   (o  python panel_server.py --receptor)
Escucha en 0.0.0.0:<RECEPTOR_PORT>. La PRIMERA vez Windows pide permiso de
firewall para redes privadas -> hay que Aceptar.

Seguridad: este proceso jamas ejecuta git, jamas borra el repo y jamas escribe
fuera de la carpeta 'aprobaciones/'. Lo peor que puede hacer un colaborador es
dejar una propuesta pendiente (que vos despues aprobas o rechazas).
"""
import os
import io
import re
import sys
import json
import base64
import hashlib
import zipfile
import datetime
import random
import threading
import ipaddress
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote, parse_qs

from panel_server import (PROYECTO, INTRANET, APROB_DIR, USUARIO, RECEPTOR_PORT,
                          EXE_DIR, VERSION, VERSION_LABEL, VERSION_NOTES)

HOST = "0.0.0.0"          # escucha en toda la red local (no solo 127.0.0.1)
MAX_ZIP = 200 * 1024 * 1024   # tope defensivo: 200 MB por propuesta
CREATE_NO_WINDOW = 0x08000000  # que PowerShell no abra ventana negra


def _pc():
    return os.environ.get("COMPUTERNAME") or "PC"


def notificar_windows(titulo, mensaje):
    """Muestra un aviso emergente (toast) de Windows, sin dependencias externas.
    Usa el AppID de PowerShell para no tener que registrar la app. Si algo falla
    (otra version de Windows, PowerShell bloqueado), no pasa nada: se ignora."""
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null\n"
        "$AppId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe'\n"
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        '$xml.LoadXml(@"\n'
        '<toast><visual><binding template="ToastGeneric"><text>%s</text><text>%s</text></binding></visual></toast>\n'
        '"@)\n'
        "$t = New-Object Windows.UI.Notifications.ToastNotification($xml)\n"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId).Show($t)\n"
    ) % (esc(titulo), esc(mensaje))
    try:
        enc = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        )
    except Exception:  # noqa
        pass


# =====================================================================
#  Snapshot: zip de TODO intranet/ (top-level + assets/)
# =====================================================================
def snapshot_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for raiz, _dirs, files in os.walk(INTRANET):
            for f in files:
                full = os.path.join(raiz, f)
                rel = os.path.relpath(full, INTRANET).replace("\\", "/")
                z.write(full, rel)
    return buf.getvalue()


# =====================================================================
#  Auto-update: bundle del PROGRAMA (allowlist) + version
# =====================================================================
#  El bundle es SOLO el programa (PanelMyS.exe + _internal/), armado por
#  ALLOWLIST (no blacklist) desde la carpeta de instalacion de la central.
#  NUNCA incluye archivos per-maquina (panel_config.json / proyecto.txt /
#  aprobaciones/) -> con un ASSERT extra antes de cachear. Asi el bundle jamas
#  puede convertir una sucursal en central ni filtrar la config de la central.
_BUNDLE_LOCK = threading.Lock()
_BUNDLE_CACHE = {}                       # version -> (bytes, sha256)
_PER_MAQUINA_FILES = {"proyecto.txt", "panel_config.json"}
_PER_MAQUINA_DIRS = {"aprobaciones"}


def _es_programa(rel):
    """Allowlist: True solo para PanelMyS.exe y todo el arbol _internal/."""
    partes = rel.replace("\\", "/").split("/")
    top = partes[0].lower()
    return top == "panelmys.exe" or top == "_internal"


def construir_bundle():
    """(bytes_zip, sha256) del programa instalado en EXE_DIR. Cacheado por VERSION.
    Lanza si por algun motivo se colara un archivo per-maquina."""
    with _BUNDLE_LOCK:
        if VERSION in _BUNDLE_CACHE:
            return _BUNDLE_CACHE[VERSION]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for raiz, _dirs, files in os.walk(EXE_DIR):
                for f in files:
                    full = os.path.join(raiz, f)
                    rel = os.path.relpath(full, EXE_DIR).replace("\\", "/")
                    if _es_programa(rel):
                        z.write(full, rel)
        data = buf.getvalue()
        # ASSERT defensivo: nada per-maquina se colo en ninguna ruta
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for nombre in z.namelist():
                partes = nombre.replace("\\", "/").split("/")
                if partes[-1].lower() in _PER_MAQUINA_FILES or partes[0].lower() in _PER_MAQUINA_DIRS:
                    raise RuntimeError("bundle inseguro: contiene %s" % nombre)
        sha = hashlib.sha256(data).hexdigest()
        _BUNDLE_CACHE[VERSION] = (data, sha)
        return data, sha


def _es_tailnet(ip):
    """True si la IP viene de la red Tailscale (CGNAT 100.64.0.0/10) o es loopback."""
    if ip.startswith("127.") or ip == "::1":
        return True
    try:
        return ipaddress.ip_address(ip) in ipaddress.ip_network("100.64.0.0/10")
    except ValueError:
        return False


# =====================================================================
#  Guardar una propuesta entrante en aprobaciones/<id>/
# =====================================================================
def _id_propuesta(usuario):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    s = re.sub(r'[^a-zA-Z0-9]+', '-', usuario or "").strip('-').lower() or "colab"
    return "%s_%s_%03d" % (ts, s, random.randint(0, 999))


def guardar_propuesta(zip_bytes, usuario, pc, mensaje, resumen):
    """Valida el zip y lo guarda como propuesta pendiente. Devuelve el id."""
    # validar que sea un zip legible (sin path traversal en los nombres)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for nombre in z.namelist():
            n = nombre.replace("\\", "/")
            if n.startswith("/") or ".." in n.split("/"):
                raise ValueError("nombre inseguro en el zip: %s" % nombre)

    os.makedirs(APROB_DIR, exist_ok=True)
    pid = _id_propuesta(usuario)
    carpeta = os.path.join(APROB_DIR, pid)
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "paquete.zip"), "wb") as fh:
        fh.write(zip_bytes)
    meta = {
        "id": pid,
        "usuario": usuario or "Colaborador",
        "pc": pc or "",
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "mensaje": mensaje or "",
        "resumen": resumen if isinstance(resumen, dict) else {},
        "estado": "pendiente",
        "bytes": len(zip_bytes),
    }
    with open(os.path.join(carpeta, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return pid, meta


# =====================================================================
#  HTTP handler
# =====================================================================
class Handler(BaseHTTPRequestHandler):
    server_version = "ReceptorMyS/1.0"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _tailnet_ok(self):
        """Solo la tailnet (o loopback) puede pedir el programa. Firewall = capa extra."""
        return _es_tailnet(self.client_address[0])

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/ping":
            return self._json({"ok": True, "rol": "central", "usuario": USUARIO, "pc": _pc()})
        if path == "/update/version":
            if not self._tailnet_ok():
                return self.send_error(403)
            try:
                data, sha = construir_bundle()
            except Exception as e:  # noqa
                return self._json({"error": str(e)}, 500)
            return self._json({"version": VERSION, "label": VERSION_LABEL,
                               "notes": VERSION_NOTES, "sha256": sha, "size": len(data)})
        if path == "/update/bundle":
            if not self._tailnet_ok():
                return self.send_error(403)
            # pin por version: si la sucursal pidio ?v=N y ya no somos N (deploy en el
            # medio), devolvemos 409 para que reintente con la version nueva.
            v = (parse_qs(urlparse(self.path).query).get("v") or [""])[0]
            if v and v != str(VERSION):
                return self._json({"error": "la version cambio; reintenta", "version": VERSION}, 409)
            try:
                data, sha = construir_bundle()
            except Exception as e:  # noqa
                return self._json({"error": str(e)}, 500)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=panelmys-update.zip")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Bundle-SHA256", sha)
            self.send_header("X-Bundle-Version", str(VERSION))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/snapshot":
            try:
                data = snapshot_zip()
            except Exception as e:  # noqa
                return self._json({"error": str(e)}, 500)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=intranet.zip")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/" or path == "/index.html":
            html = ("<!doctype html><meta charset=utf-8>"
                    "<title>Receptor Muebles y Sillones</title>"
                    "<body style='font-family:system-ui;background:#1c1e21;color:#eee;"
                    "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
                    "<div style='text-align:center'>"
                    "<h1 style='font-weight:600'>Receptor activo &#10003;</h1>"
                    "<p style='color:#aaa'>Esta computadora (%s) esta recibiendo las propuestas "
                    "de los colaboradores en la red local.</p></div></body>" % _pc())
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/inbox":
            return self.send_error(404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0:
                return self._json({"error": "cuerpo vacio"}, 400)
            if n > MAX_ZIP:
                return self._json({"error": "propuesta demasiado grande"}, 413)
            zip_bytes = self.rfile.read(n)
            usuario = unquote(self.headers.get("X-Usuario", "") or "")
            pc = unquote(self.headers.get("X-PC", "") or "")
            mensaje = unquote(self.headers.get("X-Mensaje", "") or "")
            resumen_raw = unquote(self.headers.get("X-Resumen", "") or "")
            try:
                resumen = json.loads(resumen_raw) if resumen_raw else {}
            except ValueError:
                resumen = {}
            pid, meta = guardar_propuesta(zip_bytes, usuario, pc, mensaje, resumen)
            print("  [propuesta recibida] %s  de '%s' (%s)  %d KB" %
                  (pid, meta["usuario"], meta["pc"], len(zip_bytes) // 1024))
            quien = meta["usuario"] + ((" (" + meta["pc"] + ")") if meta.get("pc") else "")
            cuerpo = meta["mensaje"] or "Abrí el panel para revisar y aprobar."
            notificar_windows("Nueva propuesta de " + quien, cuerpo)
            return self._json({"ok": True, "id": pid})
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa
            return self._json({"error": str(e)}, 500)


def serve_silencioso():
    """Arranca el receptor sin banner (para correr como hilo dentro del panel central)."""
    if not PROYECTO:
        return
    os.makedirs(APROB_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, RECEPTOR_PORT), Handler)
    httpd.serve_forever()


def main():
    if not PROYECTO:
        print("Receptor: no encontre la carpeta del proyecto (revisa proyecto.txt).")
        return
    os.makedirs(APROB_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, RECEPTOR_PORT), Handler)
    print("=" * 60)
    print("  RECEPTOR - Muebles y Sillones (computadora central)")
    print("=" * 60)
    print("  Escuchando en la red local, puerto %d" % RECEPTOR_PORT)
    print("  Las otras PCs se conectan a:  http://%s:%d" % (_pc(), RECEPTOR_PORT))
    print("  Propuestas se guardan en:  %s" % APROB_DIR)
    print("  (Cerra esta ventana para apagar el receptor.)")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
