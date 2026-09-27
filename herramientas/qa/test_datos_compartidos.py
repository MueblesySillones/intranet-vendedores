# -*- coding: utf-8 -*-
"""DATOS COMPARTIDOS: lo que conecta una computadora lo tienen todas.

El pedido (26-sep-2026): «cuando creo un reporte en la central, en las otras
computadoras no se ven. Que todas tengan toda esa información, que ninguna
tenga que volver a cargarla, y cuando se actualiza el Excel la información
tiene que estar actualizada».

Se levantan DOS paneles de prueba (una «central» y una «sucursal», cada uno con
su carpeta de estado) contra un cerebro LOCAL (`wrangler dev`), nunca contra el
real. Y se prueba:

  · la central conecta un Excel → la sucursal ve el reporte y lo puede leer
    (la planilla le llega aunque en su disco no exista)
  · la central cambia el Excel → la sucursal lee los números nuevos
  · un informe creado en la sucursal aparece en la central
  · las dos cambian cosas distintas a la vez → no se pisan
  · borrar un reporte en una lo borra en la otra
  · el mapa de vendedores viaja
  · las credenciales de Google NO viajan

Uso (con el cerebro de prueba corriendo en 8799, ver el final del archivo):
    python test_datos_compartidos.py
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
AQUI = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.join(os.path.dirname(AQUI), "panel")
PROYECTO = os.path.dirname(os.path.dirname(AQUI))
CEREBRO = os.environ.get("QA_CEREBRO") or "http://127.0.0.1:8799"
TOKENS = {"central": "prueba_central_123", "sucursal": "prueba_suc_456"}
PUERTOS = {"central": 8151, "sucursal": 8152}
RES = []

if "mys-cerebro." in CEREBRO:
    raise SystemExit("Esta prueba NO corre contra el cerebro real.")


def check(nombre, fn):
    try:
        nota = fn() or ""
        RES.append("PASS"); print("PASS | %s | %s" % (nombre, nota))
    except Exception as e:                   # noqa
        RES.append("FAIL"); print("FAIL | %s | %s" % (nombre, str(e)[:260]))


def pedir(quien, metodo, ruta, datos=None):
    url = "http://127.0.0.1:%d%s" % (PUERTOS[quien], ruta)
    body = json.dumps(datos).encode("utf-8") if datos is not None else None
    q = urllib.request.Request(url, data=body, method=metodo,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(q, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def cerebro_vacio():
    """El doc del cerebro de prueba arranca en la version que tenga; la prueba
    no depende de que este vacio, pero se avisa."""
    q = urllib.request.Request(CEREBRO + "/datos", headers={
        "Authorization": "Bearer " + TOKENS["central"], "User-Agent": "PanelMyS/1.0"})
    return json.loads(urllib.request.urlopen(q, timeout=20).read().decode("utf-8"))["doc"]


def escribir_csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(filas)


RAIZ = tempfile.mkdtemp(prefix="qa_datos_comp_")
PROCS = []


def copia_del_panel():
    """El panel sin el panel_config.json de la central: corriendo desde
    herramientas/panel leeria la config real (clave y cerebro de verdad)."""
    dest = os.path.join(RAIZ, "panel_copia")
    if os.path.isdir(dest):
        return dest
    os.makedirs(dest)
    for n in os.listdir(PANEL):
        if n in ("panel_config.json", "clave_equipo.py", "dist", "build", "instalador", "paquete",
                 "__pycache__", "investigacion"):
            continue
        o = os.path.join(PANEL, n)
        (shutil.copytree if os.path.isdir(o) else shutil.copy2)(
            o, os.path.join(dest, n), **({"ignore": shutil.ignore_patterns("__pycache__")} if os.path.isdir(o) else {}))
    return dest


def proyecto_falso():
    """Una intranet minima: Datos no la usa, y asi nada toca la de verdad."""
    proy = os.path.join(RAIZ, "proyecto")
    if os.path.isdir(proy):
        return proy
    intr = os.path.join(proy, "intranet")
    os.makedirs(intr)
    os.makedirs(os.path.join(proy, "herramientas"))
    for n in ("index.html", "modulos.js", "galerias.js"):
        shutil.copy2(os.path.join(PROYECTO, "intranet", n), os.path.join(intr, n))
    return proy


def levantar(quien):
    estado = os.path.join(RAIZ, quien)
    os.makedirs(estado, exist_ok=True)
    # la identidad de esta «PC»: su clave y el cerebro DE PRUEBA
    with open(os.path.join(estado, "identity.json"), "w", encoding="utf-8") as f:
        json.dump({"rol": "colaborador", "usuario": quien, "publish_token": TOKENS[quien],
                   "cerebro_url": CEREBRO, "central_url": ""}, f)
    env = dict(os.environ)
    env.update({"MYS_PROYECTO": proyecto_falso(), "MYS_PANEL_STATE": estado, "MYS_PANEL_WEB": "web3",
                "MYS_PANEL_PORT": str(PUERTOS[quien]), "BROWSER": "none", "PYTHONIOENCODING": "utf-8"})
    log = open(os.path.join(RAIZ, quien + ".log"), "w", encoding="utf-8")
    panel = copia_del_panel()
    p = subprocess.Popen([sys.executable, os.path.join(panel, "panel_server.py")], cwd=panel, env=env,
                         stdout=log, stderr=subprocess.STDOUT)
    PROCS.append(p)
    for _ in range(60):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/api/config" % PUERTOS[quien], timeout=1).read()
            return estado
        except Exception:                      # noqa
            time.sleep(0.5)
    raise SystemExit("no levantó el panel de %s (mirá %s)" % (quien, log.name))


def sync(quien):
    return pedir(quien, "POST", "/api/datos/sincronizar", {})


try:
    print("cerebro de prueba en", CEREBRO, "· doc en versión", cerebro_vacio().get("version"))
    EST = {q: levantar(q) for q in ("central", "sucursal")}
    EXCEL = os.path.join(RAIZ, "derivaciones_qa.csv")
    escribir_csv(EXCEL, [["Fecha", "Vendedor", "Sucursal", "Estado"],
                         ["01/09/2026", "Ana", "CABA", "Vendido"],
                         ["02/09/2026", "Beto", "Canning", "Derivado"]])
    S = {}

    def central_conecta():
        r = pedir("central", "POST", "/api/datos/fuente", {"ruta": EXCEL, "titulo": "QA compartido"})
        S["id"] = r["id"]
        s = sync("central")
        if not s.get("ok"):
            raise AssertionError("la central no pudo sincronizar: %r" % s)
        return "reporte %s conectado y subido" % r["id"]
    check("la central conecta un Excel y lo comparte", central_conecta)

    def sucursal_lo_ve():
        sync("sucursal")
        e = pedir("sucursal", "GET", "/api/datos/estado")
        tit = [x["titulo"] for x in e["reportes"]]
        if "QA compartido" not in tit:
            raise AssertionError("la sucursal ve %r" % tit)
        return "la sucursal ve %r" % tit
    check("la sucursal ve el reporte sin cargar nada", sucursal_lo_ve)

    def filas_en(quien):
        a = pedir(quien, "GET", "/api/datos/analizar?id=" + S["id"])
        if a.get("error"):
            raise AssertionError("%s no pudo leer: %s" % (quien, a["error"]))
        return a

    def sucursal_lee():
        # la sucursal NO tiene el Excel en esa ruta: se lo saca del medio
        # para asegurarlo (en la vida real, esa ruta es de otra PC)
        oculto = EXCEL + ".oculto"
        shutil.move(EXCEL, oculto)
        try:
            a = filas_en("sucursal")
        finally:
            shutil.move(oculto, EXCEL)
        return "leyó %s filas desde la copia compartida" % (a.get("total_filas") or a.get("lectura", {}).get("total_filas") or "las")
    check("la sucursal puede leer la planilla (sin tenerla en su disco)", sucursal_lee)

    def excel_actualizado():
        time.sleep(1.2)
        escribir_csv(EXCEL, [["Fecha", "Vendedor", "Sucursal", "Estado"],
                             ["01/09/2026", "Ana", "CABA", "Vendido"],
                             ["02/09/2026", "Beto", "Canning", "Derivado"],
                             ["03/09/2026", "Caro", "CABA", "Vendido"],
                             ["04/09/2026", "Dani", "Hudson", "Vendido"]])
        sync("central")
        sync("sucursal")
        comp = [r for r in json.load(open(os.path.join(EST["sucursal"], "datos.json"), encoding="utf-8"))["reportes"]
                if r["id"] == S["id"]][0]["fuente"]["compartido"]
        copias = os.listdir(os.path.join(EST["sucursal"], "datos_compartidos"))
        if not any(c.startswith(comp["sha"]) for c in copias):
            raise AssertionError("la sucursal no bajó la versión nueva: %r / %r" % (comp, copias))
        # y la vieja se fue
        if len(copias) != 1:
            raise AssertionError("quedaron copias viejas: %r" % copias)
        return "la sucursal tiene la planilla nueva (%d bytes)" % comp["size"]
    check("el Excel cambia en la central y a la sucursal le llega el nuevo", excel_actualizado)

    def informe_desde_sucursal():
        r = pedir("sucursal", "POST", "/api/datos/renombrar", {"id": S["id"], "titulo": "QA renombrado en sucursal"})
        if r.get("error"):
            raise AssertionError(r["error"])
        sync("sucursal")
        sync("central")
        e = pedir("central", "GET", "/api/datos/estado")
        tit = [x["titulo"] for x in e["reportes"]]
        if "QA renombrado en sucursal" not in tit:
            raise AssertionError("la central ve %r" % tit)
        return "el cambio de la sucursal llegó a la central"
    check("lo que cambia una sucursal llega a la central", informe_desde_sucursal)

    def a_la_vez():
        # las dos cambian cosas DISTINTAS sin sincronizar en el medio
        otro = os.path.join(RAIZ, "otro.csv")
        escribir_csv(otro, [["Fecha", "Vendedor"], ["01/09/2026", "Ana"]])
        r = pedir("central", "POST", "/api/datos/fuente", {"ruta": otro, "titulo": "QA segundo"})
        S["id2"] = r["id"]
        pedir("sucursal", "POST", "/api/datos/vendedores", {"asignaciones": {"Zoe Prueba": "Canning"}})
        time.sleep(0.5)
        sync("sucursal"); sync("central"); sync("sucursal")
        ec = [x["titulo"] for x in pedir("central", "GET", "/api/datos/estado")["reportes"]]
        es = [x["titulo"] for x in pedir("sucursal", "GET", "/api/datos/estado")["reportes"]]
        mapa_c = json.load(open(os.path.join(EST["central"], "vendedores.json"), encoding="utf-8"))
        if "QA segundo" not in es or "QA segundo" not in ec:
            raise AssertionError("el reporte nuevo no llegó a las dos: %r / %r" % (ec, es))
        if not any("ZOE" in k.upper() for k in mapa_c):
            raise AssertionError("el vendedor asignado en la sucursal no llegó: %r" % mapa_c)
        return "las dos tienen los dos cambios"
    check("dos cambios a la vez no se pisan (y el mapa de vendedores viaja)", a_la_vez)

    def borrar():
        pedir("sucursal", "POST", "/api/datos/borrar", {"id": S["id2"]})
        sync("sucursal"); sync("central")
        ec = [x["id"] for x in pedir("central", "GET", "/api/datos/estado")["reportes"]]
        if S["id2"] in ec:
            raise AssertionError("sigue en la central")
        return "borrado en las dos"
    check("borrar en una borra en la otra", borrar)

    def sin_credenciales():
        cfg_path = os.path.join(EST["central"], "datos.json")
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        cfg["google"] = {"client_id": "SECRETO-QA", "client_secret": "SECRETO-QA"}
        json.dump(cfg, open(cfg_path, "w", encoding="utf-8"))
        sync("central")
        doc = json.dumps(cerebro_vacio())
        if "SECRETO-QA" in doc:
            raise AssertionError("la credencial de Google viajó al cerebro")
        cfg2 = json.load(open(cfg_path, encoding="utf-8"))
        if (cfg2.get("google") or {}).get("client_id") != "SECRETO-QA":
            raise AssertionError("sincronizar le borró la credencial a la central")
        return "no viaja, y la central la conserva"
    check("las credenciales de Google no viajan", sin_credenciales)
finally:
    for p in PROCS:
        p.terminate()
    time.sleep(0.5)
    shutil.rmtree(RAIZ, ignore_errors=True)

ok = RES.count("PASS")
print("\n%d/%d PASS" % (ok, len(RES)))
sys.exit(0 if ok == len(RES) else 1)

# Cerebro de prueba (desde herramientas/cerebro, con un .dev.vars que tenga
# PUBLISH_TOKENS="central:prueba_central_123,sucursal:prueba_suc_456"):
#     npx wrangler dev --port 8799 --persist-to <carpeta temporal>
