# -*- coding: utf-8 -*-
"""Publica la actualizacion del panel en la web (via el repo -> Vercel).

Arma el zip del programa desde dist/PanelMyS con la MISMA allowlist que el
receptor (solo PanelMyS.exe + _internal/, jamas config per-maquina), lo deja en
<repo>/panel/PanelMyS-vNN.zip junto a panel/version.json, y borra los zips de
versiones viejas del arbol de trabajo. El commit+push se hace aparte (git).

Uso:  python subir_update.py
"""
import ast
import hashlib
import io
import json
import os
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(AQUI, "dist", "PanelMyS")
REPO = os.path.abspath(os.path.join(AQUI, "..", ".."))
DESTINO = os.path.join(REPO, "panel")

_PER_MAQUINA_FILES = {"proyecto.txt", "panel_config.json", "identity.json"}
_PER_MAQUINA_DIRS = {"aprobaciones"}


def leer_version():
    """VERSION / VERSION_LABEL / VERSION_NOTES parseados del fuente (sin importarlo,
    que el modulo tiene efectos al cargar)."""
    src = io.open(os.path.join(AQUI, "panel_server.py"), encoding="utf-8").read()
    quiero = {"VERSION", "VERSION_LABEL", "VERSION_NOTES"}
    out = {}
    for nodo in ast.parse(src).body:
        if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1:
            t = nodo.targets[0]
            if isinstance(t, ast.Name) and t.id in quiero:
                out[t.id] = ast.literal_eval(nodo.value)
    faltan = quiero - set(out)
    if faltan:
        raise SystemExit("no encontre %s en panel_server.py" % ", ".join(sorted(faltan)))
    return out


def _es_programa(rel):
    top = rel.replace("\\", "/").split("/")[0].lower()
    return top == "panelmys.exe" or top == "_internal"


def armar_zip():
    if not os.path.isfile(os.path.join(DIST, "PanelMyS.exe")):
        raise SystemExit("no existe dist/PanelMyS/PanelMyS.exe (compilar primero)")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for raiz, _dirs, files in os.walk(DIST):
            for f in files:
                full = os.path.join(raiz, f)
                rel = os.path.relpath(full, DIST).replace("\\", "/")
                if _es_programa(rel):
                    z.write(full, rel)
    data = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        nombres = z.namelist()
        for nombre in nombres:
            partes = nombre.replace("\\", "/").split("/")
            if partes[-1].lower() in _PER_MAQUINA_FILES or partes[0].lower() in _PER_MAQUINA_DIRS:
                raise SystemExit("bundle inseguro: contiene %s" % nombre)
        if "PanelMyS.exe" not in nombres:
            raise SystemExit("bundle sin PanelMyS.exe")
    return data


def main():
    v = leer_version()
    data = armar_zip()
    sha = hashlib.sha256(data).hexdigest()
    os.makedirs(DESTINO, exist_ok=True)
    nombre = "PanelMyS-v%d.zip" % v["VERSION"]
    # borrar zips de versiones viejas del arbol (git los recuerda igual)
    for f in os.listdir(DESTINO):
        if f.startswith("PanelMyS-v") and f.endswith(".zip") and f != nombre:
            os.remove(os.path.join(DESTINO, f))
    with open(os.path.join(DESTINO, nombre), "wb") as f:
        f.write(data)
    meta = {
        "version": v["VERSION"],
        "label": v["VERSION_LABEL"],
        "notes": v["VERSION_NOTES"],
        "sha256": sha,
        "size": len(data),
        "url": "panel/" + nombre,
    }
    with open(os.path.join(DESTINO, "version.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("listo: panel/%s (%.1f MB, sha %s...)" % (nombre, len(data) / 1e6, sha[:12]))
    print("ahora: git add panel && git commit && git push")


if __name__ == "__main__":
    main()
