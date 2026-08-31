# -*- coding: utf-8 -*-
"""Verifica si el auto-update realmente le va a llegar a las sucursales."""
import os, sys, json, socket, datetime, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ESC = r"C:\Users\Redes 1\Desktop\Panel MyS"
print("=" * 72)
print("¿LES VA A LLEGAR LA ACTUALIZACION A LAS SUCURSALES?")
print("=" * 72)

print("\n[1] La central esta sirviendo la version nueva")
for ruta in ("/ping", "/update/version"):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8125" + ruta, timeout=6) as r:
            d = json.load(r)
        if ruta == "/update/version":
            print("     version que anuncia : %s" % d.get("version"))
            print("     tamano del paquete  : %.1f MB" % (d.get("size", 0) / 1048576))
            print("     tiene sha256        : %s" % ("si" if d.get("sha256") else "NO"))
        else:
            print("     receptor            : responde (%s)" % d.get("rol"))
    except Exception as e:
        print("     %-20s FALLA: %s" % (ruta, str(e)[:50]))

print("\n[2] ¿Se puede llegar desde afuera? (por Tailscale)")
try:
    import subprocess
    r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=10)
    ip = (r.stdout or "").strip().splitlines()
    print("     IP de Tailscale     : %s" % (ip[0] if ip else "(sin IP)"))
except Exception as e:
    print("     tailscale           : no pude consultarlo (%s)" % str(e)[:40])
try:
    r = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=10)
    lineas = [l for l in (r.stdout or "").splitlines() if l.strip()]
    print("     equipos en la red   : %d" % len(lineas))
    for l in lineas[:8]:
        print("       " + l[:90])
except Exception as e:
    print("     estado de la red    : no pude consultarlo")

print("\n[3] El puerto escucha para afuera, no solo local")
try:
    s = socket.socket(); s.settimeout(3)
    s.connect(("127.0.0.1", 8125)); s.close()
    print("     8125 local          : abierto")
except Exception as e:
    print("     8125 local          : cerrado (%s)" % str(e)[:40])

print("\n[4] El instalador que se manda a una sucursal NUEVA")
for f in sorted(os.listdir(ESC)) if os.path.isdir(ESC) else []:
    p = os.path.join(ESC, f)
    if os.path.isfile(p):
        print("     %-42s %6.1f MB   %s" % (
            f[:42], os.path.getsize(p) / 1048576,
            datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%d/%m/%Y")))
print("=" * 72)
